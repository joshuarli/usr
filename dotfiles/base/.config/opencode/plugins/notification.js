export const NotificationPlugin = async ({ project, client, $, directory, worktree }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        await $`/usr/bin/afplay /System/Library/Sounds/Glass.aiff`
      }
    },
  }
}
