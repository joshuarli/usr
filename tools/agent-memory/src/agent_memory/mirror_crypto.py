"""age encryption for mirror objects, driven through an external executable."""
import hashlib
import os
import shutil
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Sequence

INSTALL_HINT = "install age or rage (for example `brew install age`), or set AGE_BIN"
MAX_RECIPIENT = 4096


class CryptoError(RuntimeError):
    pass


def binary() -> str:
    configured = os.environ.get("AGE_BIN")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise CryptoError("AGE_BIN is not an executable file")
        return str(path)
    for name in ("rage", "age"):
        found = shutil.which(name)
        if found:
            return found
    raise CryptoError("no age or rage executable found; " + INSTALL_HINT)


def _keygen() -> str:
    primary = Path(binary())
    for name in ("rage-keygen", "age-keygen"):
        sibling = primary.with_name(name)
        if sibling.is_file() and os.access(sibling, os.X_OK):
            return str(sibling)
    for name in ("rage-keygen", "age-keygen"):
        found = shutil.which(name)
        if found:
            return found
    raise CryptoError("no age-keygen or rage-keygen executable found next to " + primary.name)


def _run(argv, what, sensitive=()):
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        raise CryptoError(what + " could not run: " + exc.strerror) from exc
    if result.returncode != 0:
        detail = [line.strip() for line in (result.stderr or result.stdout).splitlines() if line.strip()]
        message = next((line for line in detail if line.lower().startswith(("error", "age:", "rage:"))),
                       detail[0] if detail else "no diagnostic")
        for item in sensitive:
            message = message.replace(str(item), "<path>")
        raise CryptoError("%s failed (exit %d): %s" % (what, result.returncode, message[:500]))
    return result


def _recipients(recipients: Sequence[str]) -> list[str]:
    clean = []
    for recipient in recipients:
        if not isinstance(recipient, str) or not recipient or recipient.startswith("-"):
            raise CryptoError("invalid age recipient")
        if len(recipient) > MAX_RECIPIENT:
            raise CryptoError("age recipient is too long")
        clean.append(recipient)
    if not clean:
        raise CryptoError("at least one age recipient is required")
    return clean


def keygen(identity_path) -> str:
    path = Path(identity_path)
    if path.exists():
        raise CryptoError("identity already exists")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _run([_keygen(), "-o", str(path)], "age-keygen", sensitive=[path])
    os.chmod(path, 0o600)
    return recipient(path)


def recipient(identity_path) -> str:
    path = Path(identity_path)
    result = _run([_keygen(), "-y", str(path)], "age-keygen", sensitive=[path])
    value = result.stdout.strip()
    if not value:
        raise CryptoError("identity has no recipient")
    return value


def encrypt_file(source, destination, recipients: Sequence[str]) -> dict[str, object]:
    source = Path(source)
    destination = Path(destination)
    recipients = _recipients(recipients)
    if not source.is_file():
        raise CryptoError("plaintext is not a readable file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".age-" + uuid.uuid4().hex)
    argv = [binary()]
    for value in recipients:
        argv += ["-r", value]
    argv += ["-o", str(temporary), str(source)]
    try:
        _run(argv, "age encryption", sensitive=[source, destination])
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    with destination.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"ciphertext_sha256": digest, "ciphertext_size": destination.stat().st_size}


def decrypt_file(source, destination, identity_path) -> None:
    source = Path(source)
    destination = Path(destination)
    identity_path = Path(identity_path)
    if destination.exists():
        raise CryptoError("refusing to overwrite an existing plaintext destination")
    if not source.is_file():
        raise CryptoError("ciphertext is not a readable file")
    if not identity_path.is_file():
        raise CryptoError("age identity is not a readable file")
    if stat.S_IMODE(identity_path.stat().st_mode) & 0o077:
        raise CryptoError("age identity is accessible to other users; expected mode 0600")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".age-" + uuid.uuid4().hex)
    try:
        _run([binary(), "-d", "-i", str(identity_path), "-o", str(temporary), str(source)],
             "age decryption", sensitive=[source, destination, identity_path])
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
