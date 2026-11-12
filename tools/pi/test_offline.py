#!/usr/bin/env python3
"""True offline Pi acceptance: real committed closure and hostile npm environment."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/sync"))
import pi_offline

class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="pi-no-npm-")
        cls.home=Path(cls.tmp.name)
        cls.root=pi_offline.runtime_dir(cls.home)
        cls.entry,_=pi_offline.verify_archive()
        assert pi_offline.install(cls.root)
        assert pi_offline.current(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_cli_manifest_and_idempotence(self):
        self.assertTrue(pi_offline.version_matches(self.root))
        self.assertFalse(pi_offline.install(self.root))
        self.assertEqual(json.loads((self.root/pi_offline.STAMP).read_text())["sha256"],self.entry["sha256"])

    def test_local_broker_and_no_auto_wakeup(self):
        self.assertTrue(pi_offline.configure_intercom(self.home,self.root))
        self.assertFalse(pi_offline.configure_intercom(self.home,self.root))
        cfg=json.loads((self.home/".pi/agent/intercom/config.json").read_text())
        self.assertEqual(cfg["brokerCommand"],"node")
        self.assertEqual(cfg["inboundTrigger"],"never")
        self.assertTrue(Path(cfg["brokerArgs"][-1]).is_file())
        self.assertNotIn("npx",json.dumps(cfg))

    def test_bridge_single_closure_and_foreign_preservation(self):
        project=self.home/"project/tools/pi-subagent-bridge"
        self.assertTrue(pi_offline.link_bridge(project,self.root))
        self.assertTrue(pi_offline.bridge_current(project,self.root))
        self.assertFalse(pi_offline.link_bridge(project,self.root))
        foreign=self.home/"foreign/node_modules/.pnpm"
        foreign.mkdir(parents=True)
        (foreign/"sentinel").write_text("keep")
        with self.assertRaisesRegex(ValueError,"unmanaged"):
            pi_offline.link_bridge(foreign.parent.parent,self.root)
        self.assertEqual((foreign/"sentinel").read_text(),"keep")

    def test_local_wrapper_is_repaired_when_offline_flags_change(self):
        cli = self.root/"bin/pi"
        old = cli.read_text()
        try:
            cli.write_text(old.replace("export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1", ""))
            self.assertFalse(pi_offline.current(self.root))
            self.assertTrue(pi_offline.install(self.root))
            self.assertTrue(pi_offline.current(self.root))
            self.assertIn("export PI_OFFLINE=1", cli.read_text())
        finally:
            if not pi_offline.current(self.root):
                pi_offline.install(self.root)

    def test_corrupt_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            data=json.loads((pi_offline.ARCHIVES/"artifacts.json").read_text())
            (root/"artifacts.json").write_text(json.dumps(data))
            archive=root/(pi_offline.platform_key()+".tar.gz")
            archive.write_bytes(b"corrupt")
            with patch.object(pi_offline,"ARCHIVES",root):
                with self.assertRaisesRegex(ValueError,"malformed"):
                    pi_offline.verify_archive()

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
        self.assertIn("ok: Pi SDK loaded", p.stdout)

if __name__=="__main__":unittest.main()
