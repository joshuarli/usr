import { closeSync, fstatSync, openSync, readSync } from "node:fs"

export function readBoundedLog(path: string): string {
  const fd = openSync(path, "r")
  try {
    const size = fstatSync(fd).size
    const prefixSize = Math.min(size, 65536)
    const tailStart = Math.max(prefixSize, size - 1024 * 1024)
    const prefix = Buffer.alloc(prefixSize)
    const tail = Buffer.alloc(size - tailStart)
    const head = prefix.subarray(0, readSync(fd, prefix, 0, prefix.length, 0))
    const end = tail.subarray(0, readSync(fd, tail, 0, tail.length, tailStart))
    if (tailStart <= head.length) return Buffer.concat([head, end.subarray(head.length - tailStart)]).toString("utf8")
    const headEnd = head.lastIndexOf(10) + 1
    const previous = Buffer.alloc(1)
    const precedingRead = readSync(fd, previous, 0, 1, tailStart - 1)
    const firstNewline = end.indexOf(10)
    const tailOffset = precedingRead === 1 && previous[0] === 10 ? 0 : firstNewline < 0 ? end.length : firstNewline + 1
    return Buffer.concat([head.subarray(0, headEnd), end.subarray(tailOffset)]).toString("utf8")
  } finally { closeSync(fd) }
}
