"""Install only the pinned FX experiment into a repository-local scratch home."""
import hashlib
import json
import platform
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools/sync"))
sys.path.insert(0, str(ROOT))
from tools.sync.installer import Installer  # noqa: E402

PIN = json.loads(Path(__file__).with_name("pin.json").read_text())
BASE = "https://github.com/vercel-labs/fx/releases/download/" + PIN["tag"] + "/"


class PinnedFxInstaller(Installer):
    def latest_tag(self, feed_url, *, prefix="", exclude_prefix=""):
        if feed_url != "https://github.com/vercel-labs/fx/releases.atom" or prefix or exclude_prefix:
            raise ValueError("Unexpected release lookup in pinned experiment")
        return PIN["tag"]

    def download(self, url, target):
        if url == BASE + PIN["asset"] + ".sha256":
            target.write_text(PIN["sha256"] + "  " + PIN["asset"] + "\n")
            return True
        if url != BASE + PIN["asset"]:
            raise ValueError("Unsupported FX experiment platform or download")
        return super().download(url, target)


def main():
    if len(sys.argv) != 2:
        raise ValueError("usage: setup.py SCRATCH_HOME")
    if sys.platform != "darwin" or platform.machine().lower() != "arm64":
        raise ValueError("This experiment pin supports native macOS ARM64 only")
    home = Path(sys.argv[1]).resolve()
    if not home.is_relative_to(ROOT / ".work"):
        raise ValueError("FX experiment installation must be under usr/.work/")
    home.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / ".work/tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(temporary)
    import tempfile
    tempfile.tempdir = str(temporary)
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    installer = PinnedFxInstaller(home, env=env)
    installer.dest.mkdir(parents=True, exist_ok=True)
    installer.state.mkdir(parents=True, exist_ok=True)
    installer.install_fx()
    record = installer.state / "fx"
    if not record.is_file() or record.read_text().strip() != PIN["tag"] + ":" + PIN["sha256"]:
        raise ValueError("Pinned FX installation was not verified")
    binary = installer.dest / "fx"
    if hashlib.sha256(binary.read_bytes()).hexdigest() != PIN["binary_sha256"]:
        raise ValueError("Installed FX binary does not match the qualification pin")
    print(binary)


if __name__ == "__main__":
    main()
