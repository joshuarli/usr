import { readFileSync } from 'node:fs'

const release = JSON.parse(readFileSync(new URL('./pin.json', import.meta.url), 'utf8'))
export const FX_TARGET = process.platform + '-' + process.arch
const target = release.targets[FX_TARGET]
/** The checked-in FX release artifact for this host, or null when this platform has no pin. */
export const pin = target ? { version: release.version, tag: release.tag, source_revision: release.source_revision, target: FX_TARGET, ...target } : null
export function requirePin() {
  if (!pin) throw new Error('No pinned FX ' + release.version + ' artifact for ' + FX_TARGET)
  return pin
}
