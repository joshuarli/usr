#!/usr/bin/env python3
"""Qualify tailnet Intercom between two real hosts with interactive Pi coordinators.

Starts a disposable hub (own state directory, port and fleets) on the hub host
over SSH, enrolls disposable coordinators, drives real `pi` sessions in tmux on
both hosts through the `/intercom` overlay, and checks discovery, delivery in
both directions, identity retention, fleet isolation, forged-credential denial,
revocation, scoped-worker refusal and hub-loss behavior. No model is called.
Everything it starts is stopped and its scratch is removed unless --keep.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'PATH="$HOME/.local/bin:$PATH"; '


class Failure(RuntimeError):
    pass


class Host:
    def __init__(self, label: str, ssh: str | None, scratch: str, control: str | None = None):
        self.label, self.ssh, self.scratch = label, ssh, scratch
        # One multiplexed connection per run; a connection per tmux call trips sshd's MaxStartups.
        self.options = ["-o", "BatchMode=yes", "-o", "ControlMaster=auto", "-o", f"ControlPath={control}",
                        "-o", "ControlPersist=120"] if control else []

    def sh(self, script: str, *, check: bool = True, timeout: float = 60) -> subprocess.CompletedProcess[str]:
        argv = ["ssh", *self.options, self.ssh, PREFIX + script] if self.ssh else ["sh", "-c", PREFIX + script]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        if check and result.returncode != 0:
            raise Failure(f"{self.label}: `{script}` exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}")
        return result

    def write(self, path: str, text: str, mode: str = "600") -> None:
        self.sh(f"umask 077; cat > {shlex.quote(path)} <<'QUALIFY_EOF'\n{text}QUALIFY_EOF\nchmod {mode} {shlex.quote(path)}")


class Pane:
    def __init__(self, host: Host, name: str):
        self.host, self.name = host, name
        self.model_turns: int | None = None

    def start(self, command: str) -> None:
        script = f"{self.host.scratch}/{self.name}.sh"
        self.host.write(script, f"#!/bin/sh\n{PREFIX}\ncd {shlex.quote(self.host.scratch)}\n{command}\nsleep 3600\n", "700")
        self.host.sh(f"tmux new-session -d -s {self.name} -x 200 -y 60 {shlex.quote('sh ' + script)}")

    def capture(self) -> str:
        return self.host.sh(f"tmux capture-pane -p -S -500 -t {self.name}").stdout

    def screen(self) -> str:
        return self.host.sh(f"tmux capture-pane -p -t {self.name}").stdout

    def keys(self, *keys: str) -> None:
        self.host.sh(f"tmux send-keys -t {self.name} " + " ".join(shlex.quote(key) for key in keys))

    def type(self, text: str) -> None:
        self.host.sh(f"tmux send-keys -t {self.name} -l {shlex.quote(text)}")

    def wait(self, pattern: str, timeout: float = 30, *, screen: bool = False) -> re.Match[str]:
        deadline = time.monotonic() + timeout
        while True:
            text = self.screen() if screen else self.capture()
            match = re.search(pattern, text)
            if match:
                return match
            if time.monotonic() > deadline:
                raise Failure(f"{self.host.label}/{self.name}: timed out waiting for {pattern!r}\n{text[-3000:]}")
            time.sleep(0.5)

    def count_model_turns(self) -> int:
        """Coordinators run without credentials, so any model turn leaves a local provider error."""
        if self.model_turns is None:
            self.model_turns = len(re.findall(r"No API key|GoUsageLimitError|429:", self.capture()))
        return self.model_turns

    def stop(self) -> None:
        self.count_model_turns()
        self.host.sh(f"tmux kill-session -t {self.name}", check=False)

    def overlay(self, timeout: float = 30) -> str:
        """Open the Intercom overlay with its shortcut and return the rendered session list.

        Nothing is typed into the prompt editor, so no keystroke can become a model turn.
        """
        self.keys("Escape")
        time.sleep(0.3)
        self.keys("M-m")
        self.wait(r"Other Sessions[\s\S]*Close", timeout, screen=True)
        text = self.screen()
        return text[text.index("Current Session"):]

    def roster(self, target: str, *, present: bool, timeout: float = 30) -> str:
        deadline = time.monotonic() + timeout
        while True:
            listing = self.overlay()
            others = listing.split("Other Sessions", 1)[1]
            if (target in others) == present:
                self.keys("Escape")
                return listing
            self.keys("Escape")
            if time.monotonic() > deadline:
                raise Failure(f"{self.name}: {target} {'missing from' if present else 'still in'} roster\n{listing}")
            time.sleep(1)

    def peers(self) -> set[str]:
        others = self.overlay().split("Other Sessions", 1)[1]
        self.keys("Escape")
        return set(re.findall(r"(\S+/\S+) \([0-9a-f]{4}\)", others))

    def send(self, target: str, text: str) -> None:
        self.overlay()
        self.type(target)
        time.sleep(0.5)
        self.keys("Enter")
        time.sleep(0.5)
        self.type(text)
        self.keys("Enter")
        self.wait(r"Message sent to " + re.escape(target))
        self.keys("Escape")


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}{': ' + detail if detail else ''}", flush=True)
    if not condition:
        raise Failure(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hub-ssh", required=True, help="SSH destination of the always-on hub host, e.g. josh@lisa")
    parser.add_argument("--hub-address", required=True, help="the hub host's literal Tailscale address")
    parser.add_argument("--port", type=int, default=47839, help="disposable hub port (default 47839)")
    parser.add_argument("--hub-label", default="hub", help="host label for the hub-side coordinator")
    parser.add_argument("--local-label", default="local", help="host label for this machine's coordinators")
    parser.add_argument("--keep", action="store_true", help="keep scratch, panes and the hub for inspection")
    args = parser.parse_args(argv)

    run = f"icq-{int(time.time())}"
    local_scratch = str(ROOT / ".work/tmp" / run)
    os.makedirs(local_scratch, mode=0o700, exist_ok=True)
    control = f"{local_scratch}/ssh-%C"
    remote = Host(args.hub_label, args.hub_ssh, f"$HOME/usr/.work/tmp/{run}", control)
    remote.scratch = remote.sh(f"mkdir -p {remote.scratch} && cd {remote.scratch} && pwd -P").stdout.strip()
    local = Host(args.local_label, None, local_scratch)
    endpoint = f"tcp://{args.hub_address}:{args.port}"
    hub_dir = f"{remote.scratch}/hub"
    panes: list[Pane] = []

    def agent_dir(host: Host) -> str:
        """Tracked Pi settings and Intercom policy, without auth.json: no coordinator can reach a model."""
        path = f"{host.scratch}/agent"
        host.sh(f"mkdir -p {path}/intercom && cp -L ~/.pi/agent/settings.json {path}/ "
                f"&& cp ~/.pi/agent/intercom/config.json {path}/intercom/ && test ! -e {path}/auth.json")
        return path

    agents = {}

    def coordinator(host: Host, name: str, credential: str, *, rejected: str | None = None) -> Pane:
        if host.label not in agents:
            agents[host.label] = agent_dir(host)
        pane = Pane(host, f"{run}-{name}")
        pane.start(f"PI_CODING_AGENT_DIR={agents[host.label]} intercom-tailnet run --endpoint {endpoint} "
                   f"--credential {credential} -- pi --no-session")
        panes.append(pane)
        if rejected:
            deadline = time.monotonic() + 60
            while True:
                pane.keys("Escape")
                pane.keys("M-m")
                try:
                    pane.wait(rejected, 5)
                    pane.keys("Escape")
                    return pane
                except Failure:
                    if time.monotonic() > deadline:
                        raise
        deadline = time.monotonic() + 60
        while True:
            try:
                pane.overlay(5)
                pane.keys("Escape")
                return pane
            except Failure:
                if time.monotonic() > deadline:
                    raise

    def enroll(fleet: str, host_label: str, name: str) -> str:
        path = f"{remote.scratch}/{host_label}-{name}.json"
        remote.sh(f"intercom-tailnet enroll --hub-dir {hub_dir} --fleet {fleet} --host {host_label} "
                  f"--name {name} --ttl-ms 900000 --output {path}")
        return path

    def fetch(path: str) -> str:
        target = f"{local_scratch}/{Path(path).name}"
        content = remote.sh(f"cat {path} && rm {path}").stdout
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(content)
        return target

    def session_id(path: str, host: Host) -> str:
        return str(json.loads(host.sh(f"cat {path}").stdout)["sessionId"])

    hub = f"{args.hub_label}/a"
    peer = f"{args.local_label}/b"
    fleet, other_fleet = f"{run}-f1", f"{run}-f2"
    try:
        remote.write(f"{remote.scratch}/hub.sh",
                     f"#!/bin/sh\n{PREFIX}\nexec intercom-tailnet hub --hub-dir {hub_dir} --listen {endpoint}\n", "700")
        remote.sh(f"cd {remote.scratch} && setsid nohup sh hub.sh > hub.log 2>&1 < /dev/null & echo $! > {remote.scratch}/hub.pid")
        deadline = time.monotonic() + 20
        while "Intercom broker started" not in remote.sh(f"cat {remote.scratch}/hub.log", check=False).stdout:
            if time.monotonic() > deadline:
                raise Failure("hub did not start: " + remote.sh(f"cat {remote.scratch}/hub.log", check=False).stdout)
            time.sleep(0.5)
        listeners = [line.split()[3] for line in remote.sh("netstat -ltn").stdout.splitlines()
                     if line.startswith("tcp") and line.split()[3].endswith(f":{args.port}")]
        check("hub listens only on the tailnet address", listeners == [f"{args.hub_address}:{args.port}"], ", ".join(listeners))

        cred_a = enroll(fleet, args.hub_label, "a")
        cred_b = fetch(enroll(fleet, args.local_label, "b"))
        cred_x = fetch(enroll(other_fleet, args.local_label, "x"))
        forged = f"{local_scratch}/forged.json"
        local.write(forged, json.dumps({"version": 1, "enrollmentToken": "forged-" + run}) + "\n")
        doctor = local.sh(f"intercom-tailnet doctor --endpoint {endpoint} --credential {cred_b} --connect").stdout
        check("transport reachable from this host", "transport: reachable" in doctor)
        refused = local.sh(f"USR_SCOPED_WORKER=1 intercom-tailnet run --endpoint {endpoint} --credential {cred_b} -- pi", check=False)
        check("launcher refuses scoped workers", refused.returncode == 1 and "scoped workers" in refused.stderr)

        pane_a = coordinator(remote, "a", cred_a)
        pane_b = coordinator(local, "b", cred_b)
        listing = pane_b.roster(hub, present=True)
        check("local coordinator discovers hub coordinator", f"{hub} (" in listing and f"{peer} (" in listing.split("Other Sessions")[0])
        pane_a.roster(peer, present=True)
        id_b = session_id(cred_b, local)

        nonce = f"{run}-local-to-hub"
        pane_b.send(hub, nonce)
        pane_a.wait(r"From: " + re.escape(peer) + r" \[remote:[^\]]+\][\s\S]*" + re.escape(nonce))
        check("hub coordinator receives the local message", True, nonce)
        nonce = f"{run}-hub-to-local"
        pane_a.send(peer, nonce)
        pane_b.wait(r"From: " + re.escape(hub) + r" \[remote:[^\]]+\][\s\S]*" + re.escape(nonce))
        check("local coordinator receives the hub message", True, nonce)

        pane_b.stop()
        pane_b = coordinator(local, "b2", cred_b)
        pane_a.roster(peer, present=True)
        check("restart keeps the stable session identity", session_id(cred_b, local) == id_b, id_b)

        pane_x = coordinator(local, "x", cred_x)
        listing = pane_x.roster(hub, present=False, timeout=5)
        check("other fleet cannot discover this fleet", "No other intercom-connected sessions" in listing)
        coordinator(local, "forged", forged, rejected=r"Remote registration credential was rejected")
        check("forged enrollment is rejected", True)
        seen = pane_a.peers()
        check("hub coordinator sees exactly its fleet peer (no other fleet, no forged session)", seen == {peer}, ", ".join(sorted(seen)))

        sessions = json.loads(remote.sh(f"intercom-tailnet inspect --hub-dir {hub_dir} --fleet {fleet}").stdout)
        ids = sorted(str(item.get("id")) for item in sessions)
        check("inspect lists the coordinator without secrets", id_b in ids and "sessionCredential" not in json.dumps(sessions), ", ".join(ids))
        remote.sh(f"intercom-tailnet revoke --hub-dir {hub_dir} --session {id_b}")
        pane_a.roster(peer, present=False)
        check("revoked coordinator disappears from the roster", True)
        pane_b.stop()
        pane_b = coordinator(local, "b3", cred_b, rejected=r"Intercom unavailable[^\n]*(rejected|revoked)")
        pane_a.roster(peer, present=False, timeout=5)
        check("revoked credential cannot reconnect", True, pane_b.wait(r"Intercom unavailable[^\n]*").group(0))

        model_errors = {pane.name.removeprefix(run + "-"): pane.count_model_turns() for pane in panes}
        check("no coordinator attempted a model turn (no automatic wakeup)", not any(model_errors.values()), str(model_errors))

        remote.sh(f"kill $(cat {remote.scratch}/hub.pid)")
        started = time.monotonic()
        pane_a.keys("Escape")
        pane_a.keys("M-m")
        failure = pane_a.wait(r"Intercom unavailable[^\n]*|ECONNREFUSED[^\n]*|disconnected[^\n]*", 30)
        check("hub loss is reported within 30 s", time.monotonic() - started < 30, failure.group(0).strip())
        brokers = remote.sh(f"ls {agents[args.hub_label]}/intercom", check=False).stdout.split()
        check("hub loss starts no local broker", not any(name.startswith("broker") for name in brokers), " ".join(brokers))
        print("qualification finished", flush=True)
        return 0
    except Failure as exc:
        print(f"FAIL  {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if not args.keep:
            for pane in panes:
                pane.stop()
            remote.sh(f"test -f {remote.scratch}/hub.pid && kill $(cat {remote.scratch}/hub.pid) 2>/dev/null; true", check=False)
            remote.sh(f"rm -rf {shlex.quote(remote.scratch)}", check=False)
            subprocess.run(["ssh", *remote.options, "-O", "exit", args.hub_ssh], capture_output=True, check=False)
            subprocess.run(["rm", "-rf", local_scratch], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
