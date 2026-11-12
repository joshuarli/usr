#!/usr/bin/env python3
"""True offline Pi acceptance: real pinned release closure and hostile npm environment."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools/sync"))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pi_offline
import pi_release
from release_cache import seed

ROOT=Path(__file__).resolve().parents[2]

class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="pi-no-npm-")
        cls.home=Path(cls.tmp.name)
        environment = patch.dict(os.environ, {"XDG_DATA_HOME": str(cls.home / ".local/share"),
                                              "XDG_CACHE_HOME": str(cls.home / ".cache")})
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.pin=pi_release.load_pin()
        cls.key=pi_offline.platform_key()
        cls.prefix=pi_offline.runtime_dir(cls.home)
        cls.cache=pi_offline.cache_dir(cls.home)
        seed(cls.cache)
        network = patch.object(pi_release.urllib.request, "urlopen", side_effect=AssertionError("network"))
        network.start()
        cls.addClassCleanup(network.stop)
        cls.generation=pi_release.install(cls.prefix,cls.pin,cls.key,cls.cache)
        cls.root=cls.prefix/"current"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_cli_manifest_and_idempotence(self):
        self.assertTrue(pi_offline.version_matches(self.root))
        self.assertEqual(pi_release.install(self.prefix,self.pin,self.key,self.cache),self.generation)
        receipt=json.loads((self.root/pi_release.RECEIPT).read_text())
        self.assertEqual((receipt["pin"],receipt["target"]),(self.pin,self.key))

    def test_local_broker_and_no_auto_wakeup(self):
        self.assertTrue(pi_offline.configure_intercom(self.home,self.root))
        self.assertFalse(pi_offline.configure_intercom(self.home,self.root))
        cfg=json.loads((self.home/".pi/agent/intercom/config.json").read_text())
        self.assertEqual(cfg["brokerCommand"],"node")
        self.assertEqual(cfg["inboundTrigger"],"never")
        self.assertTrue(Path(cfg["brokerArgs"][-1]).is_file())
        self.assertNotIn("npx",json.dumps(cfg))

    def test_bridge_single_closure_and_foreign_preservation(self):
        legacy=self.home/"legacy-pi"
        project=self.home/"project/tools/pi-subagent-bridge"
        self.assertTrue(pi_release.link_bridge(project,self.prefix,legacy))
        self.assertTrue(pi_release.bridge_current(project,self.prefix))
        self.assertFalse(pi_release.link_bridge(project,self.prefix,legacy))
        self.assertEqual((project/"node_modules").resolve(),self.generation/"node_modules")
        foreign=self.home/"foreign/node_modules/.pnpm"
        foreign.mkdir(parents=True)
        (foreign/"sentinel").write_text("keep")
        with self.assertRaisesRegex(ValueError,"unmanaged"):
            pi_release.link_bridge(foreign.parent.parent,self.prefix,legacy)
        self.assertEqual((foreign/"sentinel").read_text(),"keep")

    def test_bridge_link_to_legacy_runtime_migrates_and_foreign_link_is_kept(self):
        legacy=self.home/"legacy-pi"
        (legacy/"bin").mkdir(parents=True)
        (legacy/"node_modules").mkdir()
        (legacy/"bin/pi").write_text("#!/bin/sh\n")
        (legacy/pi_offline.LEGACY_STAMP).write_text("{}")
        migrated=self.home/"migrated"
        migrated.mkdir()
        (migrated/"node_modules").symlink_to(legacy/"node_modules")
        self.assertTrue(pi_release.link_bridge(migrated,self.prefix,legacy))
        self.assertEqual(os.readlink(migrated/"node_modules"),str(self.prefix/"current/node_modules"))
        self.assertTrue((legacy/"bin/pi").is_file())
        kept=self.home/"kept"
        kept.mkdir()
        (kept/"node_modules").symlink_to(self.home/"elsewhere")
        with self.assertRaisesRegex(ValueError,"unmanaged bridge symlink"):
            pi_release.link_bridge(kept,self.prefix,legacy)
        self.assertEqual(os.readlink(kept/"node_modules"),str(self.home/"elsewhere"))

    def test_modified_generation_fails_closed_and_is_preserved(self):
        cli = self.root/"bin/pi"
        old = cli.read_text()
        try:
            cli.write_text(old.replace("export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1", ""))
            self.assertIsNone(pi_release.current(self.prefix,self.pin,self.key))
            with self.assertRaisesRegex(ValueError,"modified"):
                pi_release.install(self.prefix,self.pin,self.key,self.cache)
            self.assertNotIn("PI_OFFLINE=1", cli.read_text())
        finally:
            cli.write_text(old)
        self.assertEqual(pi_release.current(self.prefix,self.pin,self.key),self.generation)

    def test_corrupt_cached_archive_is_not_trusted(self):
        with tempfile.TemporaryDirectory(dir=self.home) as tmp:
            cache=Path(tmp)
            entry=pi_release.pin_entry(self.pin,self.key)
            (cache/(entry["sha256"]+".tar.gz")).write_bytes(b"corrupt")
            with self.assertRaisesRegex(AssertionError,"network"):
                pi_release.acquire(self.pin,self.key,cache)

    def test_managed_pi_launcher_uses_only_bundle(self):
        node = shutil.which("node")
        if not node: self.skipTest("Node not available")
        version = subprocess.check_output([node, "-p", "process.versions.node"], text=True)
        if int(version.split(".")[0]) < 26: self.skipTest("Node 26 required")
        with tempfile.TemporaryDirectory() as temp:
            bin_dir = Path(temp)
            npm = bin_dir / "npm"
            marker = bin_dir / "npm-called"
            npm.write_text("#!/bin/sh\\nprintf bad > " + repr(str(marker)) + "\\nexit 99\\n")
            npm.chmod(0o755)
            env = dict(os.environ, HOME=str(self.home),
                       PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                       npm_config_registry="http://127.0.0.1:9")
            p = subprocess.run([str(self.root/"bin/pi"), "--version"],
                               env=env, capture_output=True, text=True, timeout=25)
            self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
            self.assertIn("1.5.0", p.stdout)
            self.assertFalse(marker.exists(), "Pi launcher invoked npm")

    def test_bundled_cli_and_typescript_import_without_npm(self):
        node=shutil.which("node")
        if not node:self.skipTest("Node not available")
        version=subprocess.check_output([node,"-p","process.versions.node"],text=True)
        if int(version.split(".")[0])<26:self.skipTest("Node 26 required")
        env=dict(os.environ,HOME=str(self.home),npm_config_registry="http://127.0.0.1:9")
        cli=self.root/"node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"
        p=subprocess.run([node,str(cli),"--version"],env=env,capture_output=True,text=True,timeout=25)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn("1.5.0",p.stdout)
        loader=self.root/"node_modules/tsx/dist/loader.mjs"
        extension=self.root/"node_modules/@dataforxyz/agent-intercom-pi/index.ts"
        code=f"await import({json.dumps(extension.as_uri())});console.log('intercom-ok')"
        p=subprocess.run([node,"--import",str(loader),"--input-type=module","-e",code],
                         cwd=self.root,env=env,capture_output=True,text=True,timeout=25)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn("intercom-ok",p.stdout)

    def test_real_muse_msp_host_opens_scoped_workspace_before_turn(self):
        if not shutil.which("muse"): self.skipTest("Separately installed Muse executable unavailable; live host bootstrap unverified")
        node = shutil.which("node")
        if not node: self.skipTest("Node not available")
        version = subprocess.check_output([node, "-p", "process.versions.node"], text=True)
        if int(version.split(".")[0]) < 26: self.skipTest("Node 26 required")
        loader = self.root/"node_modules/tsx/dist/loader.mjs"
        fixture = ROOT/"tools/pi/test_runtime_protocol.mjs"
        env = dict(os.environ, HOME=str(self.home), PI_OFFLINE="1",
                   npm_config_registry="http://127.0.0.1:9")
        p = subprocess.run([node, "--import", str(loader), str(fixture), str(self.root)],
                           cwd=self.root, env=env, capture_output=True,
                           text=True, timeout=25)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertIn("installed Muse accepted scoped session/start", p.stdout)

    def test_delegated_sdk_workers_inherit_no_package_network_mode(self):
        port = (ROOT/"tools/pi-subagent-bridge/src/pi-port.ts").read_text()
        sdk = (ROOT/"tools/pi-subagent-bridge/src/sdk-worker.ts").read_text()
        self.assertIn('PI_OFFLINE: "1"', port)
        self.assertIn('PI_SKIP_VERSION_CHECK: "1"', port)
        self.assertIn('process.env.PI_OFFLINE = "1"', sdk)

    def test_pi_update_cannot_invoke_online_package_manager(self):
        env = dict(os.environ, HOME=str(self.home),
                   npm_config_registry="http://127.0.0.1:9")
        cmd = str(self.root/"bin/pi")
        for subcommand in ("update", "install"):
            p = subprocess.run([cmd, subcommand, "npm:untrusted@latest"],
                               env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(p.returncode, 64)
            self.assertIn("/pi-update", p.stderr)

    def test_sdk_resolves_and_initializes_both_extensions_offline(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node not available")
        version = subprocess.check_output([node, "-p", "process.versions.node"], text=True)
        if int(version.split(".")[0]) < 26:
            self.skipTest("Node 26 required")
        loader = self.root/"node_modules/tsx/dist/loader.mjs"
        checker = ROOT/"tools/pi/verify-extensions.mjs"
        env = dict(os.environ, HOME=str(self.home), PI_OFFLINE="1",
                   npm_config_registry="http://127.0.0.1:9")
        p = subprocess.run([node, "--import", str(loader), str(checker), str(self.root)],
                           cwd=self.root, env=env, capture_output=True,
                           text=True, timeout=35)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        self.assertIn("ok: Pi SDK bound subagents, intercom, and Muse", p.stdout)

if __name__=="__main__":unittest.main()
