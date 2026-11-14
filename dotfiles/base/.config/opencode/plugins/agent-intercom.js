import { homedir } from "node:os"
import { isAbsolute, join } from "node:path"
import { pathToFileURL } from "node:url"

const dataHome = process.env.XDG_DATA_HOME && isAbsolute(process.env.XDG_DATA_HOME)
  ? process.env.XDG_DATA_HOME
  : join(homedir(), ".local", "share")
const bundle = join(dataHome, "agent-intercom", "agent-intercom-opencode", "dist", "plugin-v2.mjs")
const { default: plugin } = await import(pathToFileURL(bundle).href)
export default plugin
