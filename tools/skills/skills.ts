import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync, unlinkSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'

type Record = { id: string; description: string; invocation: 'auto' | 'explicit'; path: string; body: string; references: string[]; sha256: string }
type Skill = { record: Record; text: string; front: string[]; yaml: string | null; file: string; yamlFile: string; missing: string[] }
const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const globalRoot = resolve(repo, 'dotfiles/base/.agents/skills')
const rel = (path: string) => relative(repo, path)
const read = (path: string) => readFileSync(path, 'utf8')
function parse(root: string): Skill[] {
  return readdirSync(root, { withFileTypes: true }).filter(e => e.isDirectory()).map(e => {
    const id = e.name, file = join(root, id, 'SKILL.md'), text = read(file), lines = text.split('\n')
    if (lines[0] !== '---') throw Error(`${rel(file)}:1: expected frontmatter`)
    const end = lines.indexOf('---', 1)
    if (end < 0) throw Error(`${rel(file)}:1: unterminated frontmatter`)
    const front = lines.slice(1, end), fields = new Map<string, string>(); let metadata = false
    front.forEach((line, i) => {
      if (line === 'metadata:') { if (fields.has('metadata')) throw Error(`${rel(file)}:${i + 2}: duplicate metadata`); fields.set('metadata', ''); metadata = true; return }
      const m = line.match(metadata && line.startsWith(' ') ? /^  ([\w./-]+): "([^"]*)"$/ : /^([\w-]+): (.+)$/)
      if (!m) throw Error(`${rel(file)}:${i + 2}: invalid frontmatter`)
      if (!line.startsWith(' ') && (/^[\[\]{},|>&*!%@`]/.test(m[2]) || /^['"].*[^'"]$/.test(m[2]))) throw Error(`${rel(file)}:${i + 2}: invalid scalar`)
      const key = metadata && line.startsWith(' ') ? `metadata.${m[1]}` : m[1]
      if (!line.startsWith(' ')) metadata = false
      if (fields.has(key)) throw Error(`${rel(file)}:${i + 2}: duplicate ${key}`)
      fields.set(key, m[2])
    })
    const scalar = (s: string) => s.startsWith('"') && s.endsWith('"') ? JSON.parse(s) as string : s.startsWith("'") && s.endsWith("'") ? s.slice(1, -1).replaceAll("''", "'") : s
    const description = scalar(fields.get('description') ?? '')
    if (fields.get('disable-model-invocation') && fields.get('disable-model-invocation') !== 'true') throw Error(`${rel(file)}: invalid disable-model-invocation`)
    const body = lines.slice(end + 1).join('\n'), yamlFile = join(root, id, 'agents/openai.yaml')
    const record: Record = { id, description, invocation: fields.has('disable-model-invocation') ? 'explicit' : 'auto', path: rel(file), body, references: [], sha256: createHash('sha256').update(readFileSync(file)).digest('hex') }
    if (fields.get('name') !== id) throw Error(`${rel(file)}: name does not match directory: ${id}`)
    if (!description) throw Error(`${rel(file)}: missing description`)
    return { record, text, front, yaml: existsSync(yamlFile) ? read(yamlFile) : null, file, yamlFile, missing: [] }
  }).sort((a,b) => a.record.id.localeCompare(b.record.id))
}
function references(skills: Skill[], root: string) {
  const ids = new Set(skills.map(s => s.record.id))
  for (const s of skills) {
    const refs = new Set<string>(), missing = new Set<string>()
    for (const m of s.record.body.matchAll(/\]\(([^\s)]+)(?:\s+[^)]*)?\)/g)) {
      const target = m[1].split('#')[0]; if (!target || /^(?:[a-z]+:|\/)/i.test(target)) continue
      const path = resolve(dirname(s.file), decodeURIComponent(target)), parts = relative(root, path).split('/')
      if (parts.length >= 1 && parts[0] !== '..' && parts[0] !== s.record.id) {
        if (ids.has(parts[0])) refs.add(parts[0]); else missing.add(parts[0])
      }
    }
    let column = -1
    for (const line of s.record.body.split('\n')) {
      if (!line.startsWith('|')) { column = -1; continue }
      const cells = line.split('|').slice(1, -1).map(x => x.trim())
      const header = cells.indexOf('Skill'); if (header >= 0) { column = header; continue }
      if (column < 0 || /^[-: ]+$/.test(cells[column] ?? '')) continue
      for (const m of (cells[column] ?? '').matchAll(/`([^`]+)`/g)) { if (ids.has(m[1])) refs.add(m[1]); else missing.add(m[1]) }
    }
    s.record.references = [...refs].sort(); s.missing = [...missing].sort()
  }
}
function outputs(s: Skill): { file: string; old: string | null; content: string | null }[] {
  const explicit = s.record.invocation === 'explicit', lines = [...s.front]
  const idx = lines.findIndex(x => /^  opencode\/autoinvoke: /.test(x))
  if (idx >= 0 && !explicit) lines.splice(idx, 1)
  if (idx >= 0 && explicit) lines[idx] = '  opencode/autoinvoke: "false"'
  let meta = lines.indexOf('metadata:')
  if (explicit && idx < 0) { if (meta < 0) { lines.push('metadata:'); meta = lines.length - 1 }; lines.splice(meta + 1, 0, '  opencode/autoinvoke: "false"') }
  else if (meta >= 0 && !(lines[meta + 1] ?? '').startsWith('  ')) lines.splice(meta, 1)
  const text = ['---', ...lines, '---', s.record.body].join('\n')
  let yaml = s.yaml ?? '', yl = yaml ? yaml.split('\n') : []
  const policy = yl.findIndex(x => x === 'policy:')
  if (policy >= 0) {
    let end = policy + 1; while (end < yl.length && /^  /.test(yl[end])) end++
    const block = yl.slice(policy + 1, end)
    const invocation = block.findIndex(x => /^  allow_implicit_invocation:/.test(x))
    if (invocation >= 0) { if (explicit) block[invocation] = '  allow_implicit_invocation: false'; else block.splice(invocation, 1) }
    else if (explicit) block.push('  allow_implicit_invocation: false')
    yl.splice(policy, end - policy, ...(block.length ? ['policy:', ...block] : []))
  } else if (explicit) { if (yl.at(-1) === '') yl.pop(); yl.push('policy:', '  allow_implicit_invocation: false', '') }
  yaml = yl.join('\n')
  return [{ file: s.file, old: s.text, content: text }, { file: s.yamlFile, old: s.yaml, content: yaml.trim() ? yaml : null }]
}
function main(args: string[]): number {
  const cmd = args.shift(), rootIndex = args.indexOf('--root'); let root = globalRoot
  if (rootIndex >= 0) { if (!args[rootIndex + 1]) throw Error('missing root'); root = resolve(repo, args[rootIndex + 1]); args.splice(rootIndex, 2) }
  const json = args.includes('--json'), check = args.includes('--check'); args = args.filter(x => x !== '--json' && x !== '--check')
  if (!cmd || !['list','show','refs','check','generate'].includes(cmd) || (json && !['list','show','refs'].includes(cmd)) || (check && cmd !== 'generate') || args.length !== (['show','refs'].includes(cmd) ? 1 : 0)) throw Error('usage: skills.ts <list|show|refs|check|generate> [id] [--json|--check] [--root DIR]')
  const skills = parse(root); references(skills, root)
  const byId = new Map(skills.map(s => [s.record.id, s]))
  if (['list','show','refs'].includes(cmd)) {
    const selected = args.length ? byId.get(args[0]) : undefined
    if (args.length && !selected) throw Error(`unknown skill: ${args[0]}`)
    const result = cmd === 'list' ? skills.map(s => s.record) : cmd === 'show' ? selected!.record : selected!.record.references.map(id => { const { path, invocation, description } = byId.get(id)!.record; return { id, path, invocation, description } })
    if (json) console.log(JSON.stringify(result, null, 2))
    else if (cmd === 'show') console.log(`${selected!.record.path} (${selected!.record.invocation})\n${selected!.record.body}`)
    else for (const r of [result].flat() as { id: string; invocation: string; path: string }[]) console.log(`${r.id}\t${r.invocation}\t${r.path}`)
    return 0
  }
  const rendered = skills.flatMap(outputs), changed = rendered.filter(o => o.old !== o.content)
  if (cmd === 'generate') {
    if (check) { for (const o of changed) console.error(`stale adapter: ${rel(o.file)}`); return changed.length ? 1 : 0 }
    for (const o of rendered) { const actual = existsSync(o.file) ? read(o.file) : null; if (actual !== o.old) throw Error(`input changed: ${rel(o.file)}`) }
    for (const o of changed) { if (o.content === null) unlinkSync(o.file); else { mkdirSync(dirname(o.file), { recursive: true }); writeFileSync(o.file, o.content) }; console.log(rel(o.file)) }
    return 0
  }
  let bad = false; const error = (message: string) => { console.error(message); bad = true }
  const commands = new Set(execFileSync('python3', ['-I', join(repo,'dotfiles/base/.local/bin/mdtool'), 'commands'], { encoding: 'utf8' }).trim().split(/\s+/))
  for (const s of skills) {
    const r = s.record
    if (r.invocation === 'auto' && !r.description.includes('Skip')) error(`${r.id}: auto skill has no Skip clause`)
    for (const id of s.missing) error(`${r.id}: unknown referenced skill: ${id}`)
    for (const m of s.text.matchAll(/`mdtool ([a-z][a-z-]*)/g)) if (!commands.has(m[1])) error(`${r.id}: unknown mdtool command: ${m[1]}`)
    const limit = r.id === 'orchestrate' ? 12000 : 8000
    if (r.id !== 'ultrareview' && Buffer.byteLength(s.text) > limit) console.log(`warning: ${r.id} is over ${limit} bytes`)
    if (!/^\*\*Report:\*\*/m.test(s.text)) console.log(`warning: ${r.id} has no closing **Report:**`)
  }
  for (const o of changed) error(`stale adapter: ${rel(o.file)}`)
  if (root === globalRoot) {
    let skillCol = -1, modeCol = -1
    for (const line of read(join(repo,'SKILLS.md')).split('\n')) {
      if (!line.startsWith('|')) { skillCol = -1; continue }
      const cells = line.split('|').slice(1,-1).map(x => x.trim())
      if (cells.includes('Skill') && cells.includes('Mode')) { skillCol = cells.indexOf('Skill'); modeCol = cells.indexOf('Mode'); continue }
      if (skillCol < 0) continue
      const id = cells[skillCol]?.match(/^`([^` ]+)/)?.[1], skill = id && byId.get(id)
      if (skill && cells[modeCol]?.toLowerCase() !== skill.record.invocation) error(`SKILLS.md: mode mismatch: ${id}`)
    }
  }
  return bad ? 1 : 0
}
try { process.exitCode = main(process.argv.slice(2)) } catch (e) { console.error(e instanceof Error ? e.message : String(e)); process.exitCode = 1 }
