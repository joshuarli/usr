import { execFile } from "node:child_process"
import { Plugin } from "@opencode/plugin"

export default Plugin.define({
  id: "notification",
  setup(ctx) {
    const controller = new AbortController()

    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
          if (event.type === "session.idle") {
            execFile("notify-sound", [], () => {})
          }
        }
      } catch {
        // Aborted on unload; ignore.
      }
    })()

    return () => controller.abort()
  },
})
