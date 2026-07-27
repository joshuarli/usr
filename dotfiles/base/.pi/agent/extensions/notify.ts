import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawnSync } from "node:child_process";

export default function (pi: ExtensionAPI): void {
  pi.on("agent_end", async () => {
    try {
      spawnSync("/usr/bin/afplay", ["/System/Library/Sounds/Glass.aiff"], {
        stdio: "ignore",
        timeout: 5000,
      });
    } catch {
      // Silently ignore errors (e.g., sound file missing, afplay unavailable)
    }
  });
}
