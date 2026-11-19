import { spawn } from 'node:child_process'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@deepseek-ai/dsh-tools', () => ({ defineTool: (options: unknown) => options }))
vi.mock('node:child_process', () => ({ spawn: vi.fn() }))

import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { apply } from '../src/index.ts'
import { installSpawn, spawnedCommand } from './fake-child.ts'

/** One tool call, as the registry would make it. */
interface Tool {
  name: string
  parameters: Record<string, { type: string; required?: true; items?: { type: string } }>
  timeoutMs?: number
  execute: (args: Record<string, unknown>, exec: { signal: AbortSignal }) => Promise<string>
}

const exec = { signal: new AbortController().signal }
const made: string[] = []
const saved = { BOARDWISE_EXE: process.env['BOARDWISE_EXE'] }

function tempDir(prefix = 'boardwise-parts-hunt-'): string {
  const dir = mkdtempSync(join(tmpdir(), prefix))
  made.push(dir)
  return dir
}

/** A real, existing file — the pre-flight check only asks whether it is there. */
function fixture(name = 'board.epro2', body = ''): string {
  const file = join(tempDir('boardwise-fixture-'), name)
  writeFileSync(file, body)
  return file
}

function registered(): Map<string, Tool> {
  const tools = new Map<string, Tool>()
  apply({ tools: { register: (definition: unknown) => {
    const tool = definition as Tool
    tools.set(tool.name, tool)
    return () => {}
  } } } as never)
  return tools
}

async function call(args: Record<string, unknown>): Promise<string> {
  const tool = registered().get('boardwise_parts_hunt')
  if (tool === undefined) throw new Error('boardwise_parts_hunt is not registered')
  return await tool.execute(args, exec)
}

/** The value of `--flag` in a spawned command. */
function flagValue(argv: readonly string[], flag: string): string | undefined {
  const index = argv.indexOf(flag)
  return index === -1 ? undefined : argv[index + 1]
}

/** How many times the CLI was spawned, for the "refused before spawn" pins. */
function spawnCount(): number {
  return (vi.mocked(spawn) as unknown as { mock: { calls: unknown[] } }).mock.calls.length
}

beforeEach(() => {
  const exe = join(tempDir('boardwise-bin-'), 'boardwise.exe')
  writeFileSync(exe, '')
  process.env['BOARDWISE_EXE'] = exe
  ;(vi.mocked(spawn) as unknown as { mock: { calls: unknown[] } }).mock.calls.length = 0
})

afterEach(() => {
  for (const dir of made.splice(0)) rmSync(dir, { recursive: true, force: true })
  if (saved.BOARDWISE_EXE === undefined) delete process.env['BOARDWISE_EXE']
  else process.env['BOARDWISE_EXE'] = saved.BOARDWISE_EXE
})

describe('boardwise_parts_hunt: the three ways to name a design', () => {
  it('passes --file and the given --out, and reports the four artifacts', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    const mock = installSpawn((child, _command, args) => {
      const dir = flagValue(args, '--out') as string
      for (const name of ['hunt-report.json', 'hunt-plan.json', 'hunt-report.md', 'hunt-audit.jsonl']) {
        writeFileSync(join(dir, name), '{}')
      }
      child.out('parts: 3 hunted, 1 needs a search\n')
      child.finish(0)
    })

    const message = await call({ file, out })

    const argv = spawnedCommand(mock)
    expect(argv.slice(1)).toEqual(['parts', 'hunt', '--file', file, '--out', out])
    expect(message).toContain('boardwise_parts_hunt: exit 0')
    expect(message).toContain(`hunt-report.json: ${join(out, 'hunt-report.json')} [present]`)
    expect(message).toContain(`hunt-plan.json: ${join(out, 'hunt-plan.json')} [present]`)
    expect(message).toContain(`hunt-report.md: ${join(out, 'hunt-report.md')} [present]`)
    expect(message).toContain(`hunt-audit.jsonl: ${join(out, 'hunt-audit.jsonl')} [present]`)
    expect(message).toContain('parts: 3 hunted, 1 needs a search')
  })

  it('turns project= into --live --project, and instance= into --live --instance', async () => {
    const out = join(tempDir(), 'hunt')
    const mock = installSpawn(child => child.finish(1))

    await call({ project: 'test', out })
    expect(spawnedCommand(mock).slice(1)).toEqual(['parts', 'hunt', '--live', '--project', 'test', '--out', out])

    await call({ instance: 'win-1', out })
    expect(spawnedCommand(mock).slice(1)).toEqual(['parts', 'hunt', '--live', '--instance', 'win-1', '--out', out])
  })

  it('refuses zero or two design sources before spawning', async () => {
    const out = join(tempDir(), 'hunt')
    const file = fixture()
    installSpawn(child => child.finish(0))

    await expect(call({ out })).rejects.toThrow(/exactly one of file, project or instance/)
    await expect(call({ file, project: 'test', out })).rejects.toThrow(/exactly one of file, project or instance/)
    await expect(call({ file, instance: 'win-1', out })).rejects.toThrow(/exactly one of file, project or instance/)
    expect(spawnCount()).toBe(0)
  })

  it('requires out before spawning', async () => {
    const file = fixture()
    installSpawn(child => child.finish(0))
    await expect(call({ file })).rejects.toThrow(/out is required/)
    expect(spawnCount()).toBe(0)
  })
})

describe('boardwise_parts_hunt: optional flags are passed only when given', () => {
  it('passes --from-report with the report it was handed', async () => {
    const file = fixture()
    const report = fixture('report.json', '{"needs_datasheet": []}')
    const out = join(tempDir(), 'hunt')
    const mock = installSpawn(child => child.finish(0))

    await call({ file, fromReport: report, out })

    expect(flagValue(spawnedCommand(mock), '--from-report')).toBe(report)
  })

  it('passes offline, limit, cache and noCache, and nothing else by default', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    const cache = join(tempDir(), 'pdf-cache')
    const mock = installSpawn(child => child.finish(0))

    await call({ file, out })
    const bare = spawnedCommand(mock)
    for (const flag of ['--offline', '--limit', '--cache', '--no-cache', '--shelf', '--apply', '--apply-facts']) {
      expect(bare).not.toContain(flag)
    }

    await call({ file, out, offline: true, limit: 7, cache })
    const full = spawnedCommand(mock)
    expect(full).toContain('--offline')
    expect(flagValue(full, '--limit')).toBe('7')
    expect(flagValue(full, '--cache')).toBe(cache)

    await call({ file, out, noCache: true })
    expect(spawnedCommand(mock)).toContain('--no-cache')
  })

  it('refuses cache together with noCache before spawning', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    installSpawn(child => child.finish(0))

    await expect(call({ file, out, cache: join(tempDir(), 'c'), noCache: true }))
      .rejects.toThrow(/cache.*noCache|noCache.*cache/)
    expect(spawnCount()).toBe(0)
  })

  it('writes answers to its own transport file and passes it as --apply', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    const answers = [{ designator: 'U1', url: 'https://example.invalid/ds.pdf' }]
    let body = ''
    const mock = installSpawn((child, _command, args) => {
      body = readFileSync(flagValue(args, '--apply') as string, 'utf8')
      child.finish(0)
    })

    await call({ file, out, answers })

    const path = flagValue(spawnedCommand(mock), '--apply') as string
    expect(path.startsWith(join(tmpdir(), 'boardwise-dsh-'))).toBe(true)
    expect(existsSync(path)).toBe(true)
    expect(JSON.parse(body)).toEqual(answers)
  })

  it('writes claims to its own transport file and passes it as --apply-facts', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    const claims = [{ designator: 'U2', facts: { vin: '5V' }, quotes: [{ page: 3, text: 'Vin 5 V' }] }]
    let body = ''
    const mock = installSpawn((child, _command, args) => {
      const path = flagValue(args, '--apply-facts') as string
      expect(flagValue(args, '--apply')).toBeUndefined()
      body = readFileSync(path, 'utf8')
      child.finish(0)
    })

    await call({ file, out, claims })

    expect(JSON.parse(body)).toEqual(claims)
  })

  it('passes --shelf only when an explicit path is given', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    const shelf = join(tempDir(), 'shelf', 'parts.json')
    const mock = installSpawn(child => child.finish(0))

    await call({ file, out, shelf })

    expect(flagValue(spawnedCommand(mock), '--shelf')).toBe(shelf)
  })
})

describe('boardwise_parts_hunt: outcomes', () => {
  it('marks a missing artifact MISSING and keeps a non-zero exit as the answer', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    const mock = installSpawn((child, _command, args) => {
      const dir = flagValue(args, '--out') as string
      writeFileSync(join(dir, 'hunt-report.json'), '{}')
      child.err('boardwise parts hunt: the answers file cannot be read\n')
      child.finish(2)
    })

    const message = await call({ file, out })

    expect(spawnedCommand(mock)).toContain('--out')
    expect(message).toContain('boardwise_parts_hunt: exit 2')
    expect(message).toContain(`hunt-report.json: ${join(out, 'hunt-report.json')} [present]`)
    expect(message).toContain(`hunt-audit.jsonl: ${join(out, 'hunt-audit.jsonl')} [MISSING]`)
    expect(message).toContain('the answers file cannot be read')
  })

  it('propagates a CLI that cannot be started instead of answering', async () => {
    const file = fixture()
    const out = join(tempDir(), 'hunt')
    installSpawn((child, command) => child.failToStart(new Error(`spawn ${command} ENOENT`)))

    await expect(call({ file, out })).rejects.toThrow(/ENOENT/)
  })
})
