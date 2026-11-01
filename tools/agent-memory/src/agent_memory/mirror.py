#!/usr/bin/env python3
"""Cloudflare mirror protocol: validators, configuration, and a pooled HTTPS client."""
import base64
import http.client
import json
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROTOCOL = 1
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_OBJECT_BYTES = 8 * 1024 * 1024
MAX_MISSING_OBJECTS = 20000
MAX_CURSOR_CHARS = 512
MAX_CURSOR_PARTS = 4
MAX_CURSOR_PART_CHARS = 256
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
REQUEST_TIMEOUT = 30
ATTEMPTS = 5
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
ERROR_CODES = frozenset({
    "forbidden",
    "not_found",
    "method_not_allowed",
    "unavailable",
    "invalid_request",
    "unsupported_version",
    "payload_too_large",
})
CONFIG_KEYS = frozenset({
    "transport",
    "url",
    "service_token_file",
    "age_recipients_file",
    "age_identity_file",
    "learning_projection",
})
ENCODINGS = frozenset({"identity", "zlib"})
DIGEST = re.compile(r"^[0-9a-f]{64}$")
ORIGIN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
TOKEN_PART = re.compile(r"^[A-Za-z0-9._-]{1,256}$")


class MirrorError(RuntimeError):
    def __init__(self, code, message, status=None, retryable=False):
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True)
class MirrorConfig:
    url: str
    service_token_file: Path
    age_recipients_file: Path
    age_identity_file: Path
    learning_projection: bool


def _record(value):
    return isinstance(value, dict)


def _exact_keys(value, keys):
    return _record(value) and set(value) == set(keys)


def decode_digest(value):
    return value if isinstance(value, str) and DIGEST.match(value) else None


def decode_origin(value):
    return value if isinstance(value, str) and ORIGIN.match(value) else None


def decode_protocol(value):
    return PROTOCOL if value == PROTOCOL and not isinstance(value, bool) else None


def _decode_size(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= MAX_OBJECT_BYTES else None


def decode_hello(value):
    if not _exact_keys(value, ("protocol", "origin")):
        return None
    if decode_protocol(value.get("protocol")) is None:
        return None
    origin = decode_origin(value.get("origin"))
    return None if origin is None else {"protocol": PROTOCOL, "origin": origin}


def decode_missing_request(value):
    if not _exact_keys(value, ("protocol", "origin", "objects")):
        return None
    if decode_protocol(value.get("protocol")) is None:
        return None
    origin = decode_origin(value.get("origin"))
    objects = value.get("objects")
    if origin is None or not isinstance(objects, list) or len(objects) > MAX_MISSING_OBJECTS:
        return None
    decoded = []
    digests = set()
    for item in objects:
        if not _exact_keys(item, ("plaintext_digest", "size")):
            return None
        digest = decode_digest(item.get("plaintext_digest"))
        size = _decode_size(item.get("size"))
        if digest is None or size is None or digest in digests:
            return None
        digests.add(digest)
        decoded.append({"plaintext_digest": digest, "size": size})
    return {"protocol": PROTOCOL, "origin": origin, "objects": decoded}


def _valid_cursor_part(value):
    return isinstance(value, str) and 0 < len(value) <= MAX_CURSOR_PART_CHARS


def encode_cursor(parts):
    parts = list(parts)
    if not parts or len(parts) > MAX_CURSOR_PARTS or not all(_valid_cursor_part(part) for part in parts):
        raise ValueError("cursor parts are invalid")
    encoded = base64.urlsafe_b64encode(
        json.dumps(parts, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii").rstrip("=")
    if len(encoded) > MAX_CURSOR_CHARS:
        raise ValueError("cursor is too long")
    return encoded


def decode_cursor(value):
    if not isinstance(value, str) or not value or len(value) > MAX_CURSOR_CHARS or not BASE64URL.match(value):
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        parts = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(parts, list) or not parts or len(parts) > MAX_CURSOR_PARTS:
        return None
    if not all(_valid_cursor_part(part) for part in parts):
        return None
    return parts


def _decode_path(value, key):
    if not isinstance(value, str) or not value:
        raise MirrorError("invalid_config", "cloudflare config needs a " + key + " path")
    return Path(value).expanduser()


def decode_config(value):
    if not _record(value):
        raise MirrorError("invalid_config", "cloudflare config must be an object")
    unknown = set(value) - CONFIG_KEYS
    if unknown:
        raise MirrorError("invalid_config", "unknown cloudflare config key: " + sorted(unknown)[0])
    if value.get("transport") != "cloudflare":
        raise MirrorError("invalid_config", "cloudflare config needs transport=cloudflare")
    url = value.get("url")
    if not isinstance(url, str):
        raise MirrorError("invalid_config", "cloudflare config needs a url")
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError as exc:
        raise MirrorError("invalid_config", "cloudflare url has an invalid port") from exc
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in ("", "/")):
        raise MirrorError("invalid_config", "cloudflare url must be an https origin")
    normalized = "https://" + parts.hostname + ((":" + str(port)) if port else "")
    projection = value.get("learning_projection", False)
    if not isinstance(projection, bool):
        raise MirrorError("invalid_config", "learning_projection must be a boolean")
    return MirrorConfig(
        url=normalized,
        service_token_file=_decode_path(value.get("service_token_file"), "service_token_file"),
        age_recipients_file=_decode_path(value.get("age_recipients_file"), "age_recipients_file"),
        age_identity_file=_decode_path(value.get("age_identity_file"), "age_identity_file"),
        learning_projection=projection,
    )


def load_config(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text())
    except OSError as exc:
        raise MirrorError("invalid_config", "agent-sessions config is not readable") from exc
    except ValueError as exc:
        raise MirrorError("invalid_config", "agent-sessions config is not valid JSON") from exc
    if not _record(value) or not _record(value.get("central")):
        raise MirrorError("invalid_config", "agent-sessions config has no central object")
    return decode_config(value["central"])


def load_service_token(path):
    path = Path(path)
    try:
        info = path.stat()
    except OSError as exc:
        raise MirrorError("invalid_config", "service token file is missing") from exc
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise MirrorError("invalid_config", "service token file must be regular and mode 0600")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise MirrorError("invalid_config", "service token file is not valid JSON") from exc
    if not _exact_keys(value, ("client_id", "client_secret")):
        raise MirrorError("invalid_config", "service token file must hold client_id and client_secret")
    for key in ("client_id", "client_secret"):
        if not isinstance(value[key], str) or not TOKEN_PART.match(value[key]):
            raise MirrorError("invalid_config", "service token " + key + " is invalid")
    return value["client_id"], value["client_secret"]


def _decode_learning(value):
    if not _exact_keys(value, ("revision", "digest", "records")):
        return None
    revision, records = value.get("revision"), value.get("records")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        return None
    if isinstance(records, bool) or not isinstance(records, int) or records < 0:
        return None
    digest = value.get("digest")
    if digest is not None and decode_digest(digest) is None:
        return None
    return {"revision": revision, "digest": digest, "records": records}


def decode_hello_response(value):
    if not _record(value):
        return None
    if decode_protocol(value.get("protocol")) is None:
        return None
    store = value.get("store_id")
    origin = decode_origin(value.get("origin"))
    if not isinstance(store, str) or not ORIGIN.match(store) or origin is None:
        return None
    revision = value.get("revision")
    watermark = value.get("tombstone_watermark")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        return None
    if isinstance(watermark, bool) or not isinstance(watermark, int) or watermark < 0:
        return None
    learning = _decode_learning(value.get("learning"))
    if learning is None:
        return None
    return {
        "protocol": PROTOCOL, "store_id": store, "origin": origin,
        "revision": revision, "tombstone_watermark": watermark, "learning": learning,
    }


def _decode_remote_object(value):
    if not _exact_keys(value, ("plaintext_digest", "plaintext_size", "encoding", "ciphertext_digest", "ciphertext_size")):
        return None
    plaintext = decode_digest(value.get("plaintext_digest"))
    ciphertext = decode_digest(value.get("ciphertext_digest"))
    encoding = value.get("encoding")
    size = value.get("plaintext_size")
    ciphertext_size = value.get("ciphertext_size")
    if plaintext is None or ciphertext is None or encoding not in ENCODINGS:
        return None
    if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= MAX_OBJECT_BYTES:
        return None
    if isinstance(ciphertext_size, bool) or not isinstance(ciphertext_size, int) or not 0 <= ciphertext_size <= MAX_OBJECT_BYTES:
        return None
    return {
        "plaintext_digest": plaintext, "plaintext_size": size, "encoding": encoding,
        "ciphertext_digest": ciphertext, "ciphertext_size": ciphertext_size,
    }


def decode_missing_response(value):
    if not _record(value):
        return None
    if decode_protocol(value.get("protocol")) is None:
        return None
    origin = decode_origin(value.get("origin"))
    missing = value.get("missing")
    known = value.get("known")
    if origin is None or not isinstance(missing, list) or not isinstance(known, list):
        return None
    decoded_missing = []
    for item in missing:
        if not _exact_keys(item, ("plaintext_digest", "size")):
            return None
        digest = decode_digest(item.get("plaintext_digest"))
        size = _decode_size(item.get("size"))
        if digest is None or size is None:
            return None
        decoded_missing.append({"plaintext_digest": digest, "size": size})
    decoded_known = []
    for item in known:
        object_row = _decode_remote_object(item)
        if object_row is None:
            return None
        decoded_known.append(object_row)
    return {"protocol": PROTOCOL, "origin": origin, "missing": decoded_missing, "known": decoded_known}


def decode_error_response(value):
    if not _record(value) or not _exact_keys(value, ("error",)):
        return None
    error = value.get("error")
    if not _exact_keys(error, ("code", "message")):
        return None
    code, message = error.get("code"), error.get("message")
    if code not in ERROR_CODES or not isinstance(message, str) or len(message) > 500:
        return None
    return MirrorError(code, message)


class ConnectionPool:
    def __init__(self, host, port, timeout, factory=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._factory = factory or (lambda: http.client.HTTPSConnection(host, port, timeout=timeout))
        self._connection = None
        self.connections = 0

    def get(self):
        if self._connection is None:
            self._connection = self._factory()
            self.connections += 1
        return self._connection

    def discard(self):
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

    def close(self):
        self.discard()


class MirrorClient:
    def __init__(self, config, token=None, timeout=REQUEST_TIMEOUT, attempts=ATTEMPTS,
                 factory=None, sleep=time.sleep):
        self.config = config
        self.token = token if token is not None else load_service_token(config.service_token_file)
        self.attempts = attempts
        self._sleep = sleep
        parts = urlsplit(config.url)
        self.pool = ConnectionPool(parts.hostname, parts.port or 443, timeout, factory)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.pool.close()

    def _auth_headers(self):
        return {
            "CF-Access-Client-Id": self.token[0],
            "CF-Access-Client-Secret": self.token[1],
            "Accept": "application/json",
            "User-Agent": "agent-sessions-mirror/1",
        }

    def _retry_delay(self, attempt, headers):
        retry_after = headers.get("retry-after") if headers else None
        if isinstance(retry_after, str) and retry_after.isdigit():
            return min(60, max(1, int(retry_after)))
        return min(60, 2 ** attempt)

    def _request(self, method, path, body, headers):
        for attempt in range(self.attempts):
            try:
                connection = self.pool.get()
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse()
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                response_headers = {key.lower(): item for key, item in response.getheaders()}
                if len(payload) > MAX_RESPONSE_BYTES:
                    self.pool.discard()
                    raise MirrorError("invalid_response", "mirror response exceeds the limit")
                if getattr(response, "will_close", False):
                    self.pool.discard()
                if response.status >= 400:
                    error = decode_error_response(_loads(payload))
                    if error is None:
                        error = MirrorError("http_error", "mirror returned status %d" % response.status,
                                            status=response.status)
                    error.status = response.status
                    error.retryable = response.status in RETRY_STATUSES
                    if error.retryable and attempt + 1 < self.attempts:
                        self.pool.discard()
                        self._sleep(self._retry_delay(attempt, response_headers))
                        continue
                    raise error
                return payload
            except MirrorError:
                raise
            except (OSError, http.client.HTTPException) as exc:
                self.pool.discard()
                if attempt + 1 >= self.attempts:
                    raise MirrorError("network", "mirror request failed: " + type(exc).__name__) from exc
                self._sleep(self._retry_delay(attempt, None))
        raise MirrorError("network", "mirror request failed")

    def _json(self, method, path, value=None) -> dict[str, Any]:
        body = None
        headers = self._auth_headers()
        if value is not None:
            body = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
            if len(body) > MAX_JSON_BYTES:
                raise MirrorError("invalid_request", "request body exceeds the limit")
            headers["Content-Type"] = "application/json"
        payload = self._request(method, path, body, headers)
        decoded = _loads(payload)
        if not isinstance(decoded, dict):
            raise MirrorError("invalid_response", "mirror response is not an object")
        return decoded

    def status(self):
        value = self._json("GET", "/api/v1/status")
        if decode_protocol(value.get("protocol")) is None:
            raise MirrorError("unsupported_version", "mirror status protocol is not supported")
        return value

    def hello(self, origin):
        request = {"protocol": PROTOCOL, "origin": origin}
        if decode_hello(request) is None:
            raise MirrorError("invalid_request", "hello request is invalid")
        value = self._json("POST", "/api/v1/sync/hello", request)
        decoded = decode_hello_response(value)
        if decoded is None:
            raise MirrorError("invalid_response", "hello response is invalid")
        return decoded

    def missing(self, origin, objects):
        request = {
            "protocol": PROTOCOL,
            "origin": origin,
            "objects": [{"plaintext_digest": digest, "size": size} for digest, size in objects],
        }
        if decode_missing_request(request) is None:
            raise MirrorError("invalid_request", "missing-objects request is invalid")
        value = self._json("POST", "/api/v1/sync/objects/missing", request)
        decoded = decode_missing_response(value)
        if decoded is None:
            raise MirrorError("invalid_response", "missing-objects response is invalid")
        return decoded


def _loads(payload):
    try:
        return json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        return None
