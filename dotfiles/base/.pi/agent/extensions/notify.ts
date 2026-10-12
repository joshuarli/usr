import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawnSync } from "node:child_process";

export default function (pi: ExtensionAPI): void {
  pi.on("agent_end", async () => {
    try {
      spawnSync("notify-sound", [], {
        stdio: "ignore",
        timeout: 5000,
      });
    } catch {
      // Silently ignore errors (e.g., notify-sound missing)
    }
  });
}
