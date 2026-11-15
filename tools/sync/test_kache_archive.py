import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import unittest

source = Path(__file__).resolve().parents[2] / "dotfiles/setup-kache-test.py"
spec = importlib.util.spec_from_file_location("setup_kache_test", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TarKacheTest(module.SetupKacheRecord):
    def test_tar_xz_install(self):
        sums = []
        for name in ("kache", "kache-engine"):
            member = f"{name}-{module.TRIPLE}"
            data = (module.FAKE_KACHE + f"# {name}\n").encode()
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w:xz") as archive:
                info = tarfile.TarInfo(member)
                info.mode, info.size = 0o755, len(data)
                archive.addfile(info, io.BytesIO(data))
            asset = member + ".tar.xz"
            (self.fixture / "assets" / asset).write_bytes(buffer.getvalue())
            sums.append(f"{hashlib.sha256(buffer.getvalue()).hexdigest()}  {asset}\n")
        (self.fixture / "assets/SHA256SUMS").write_text("".join(sums))
        self.assertTrue(any(url.endswith(".tar.xz") for url in self.setup_kache()))
        self.assertTrue((self.cargo_bin / "kache").stat().st_mode & 0o111)
        self.assertTrue((self.cargo_bin / "kache-engine").stat().st_mode & 0o111)


if __name__ == "__main__":
    unittest.main()
