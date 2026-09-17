import { execFile } from "node:child_process"

export default {
  id: "notification",
  setup(ctx) {
    const controller = new AbortController()

    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
          if (event.type === "session.idle") {
            execFile("/usr/bin/afplay", ["/System/Library/Sounds/Glass.aiff"], () => {})
          }
        }
      } catch {
        // Aborted on unload; ignore.
      }
    })()

    return () => controller.abort()
  },
}
