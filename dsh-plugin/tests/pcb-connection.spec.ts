import { spawn } from 'node:child_process'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@deepseek-ai/dsh-tools', () => ({ defineTool: (options: unknown) => options }))
vi.mock('node:child_process', () => ({ spawn: vi.fn() }))

import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { apply } from '../src/index.ts'
import { installSpawn, spawnedCommand } from './fake-child.ts'

/** One tool call, as the registry would make it. */
interface Tool {
  name: string
  parameters: Record<string, { type: string; required?: true }>
  timeoutMs?: number
  execute: (args: Record<string, unknown>, exec: { signal: AbortSignal }) => Promise<string>
}

const exec = { signal: new AbortController().signal }
const made: string[] = []
const saved = { BOARDWISE_EXE: process.env['BOARDWISE_EXE'] }

function tempDir(prefix = 'boardwise-pcb-connection-'): string {
  const dir = mkdtempSync(join(tmpdir(), prefix))
  made.push(dir)
  return dir
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
  const tool = registered().get('boardwise_pcb_connection')
  if (tool === undefined) throw new Error('boardwise_pcb_connection is not registered')
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

describe('boardwise_pcb_connection: the registered surface', () => {
  it('declares only the two ends and the three optional selectors, with a two-minute budget', () => {
    const tool = registered().get('boardwise_pcb_connection') as Tool
    expect(Object.keys(tool.parameters)).toEqual(['from', 'to', 'project', 'instance', 'port'])
    // The CLI requires both ends; refusing a missing one before the spawn keeps
    // argparse's exit 2 (NOT_PROVEN's code) out of an input mistake.
    expect(tool.parameters['from']?.required).toBe(true)
    expect(tool.parameters['to']?.required).toBe(true)
    for (const field of ['project', 'instance', 'port']) {
      expect(tool.parameters[field]?.required).toBeUndefined()
    }
    expect(tool.parameters['from']?.type).toBe('string')
    expect(tool.parameters['to']?.type).toBe('string')
    expect(tool.parameters['port']?.type).toBe('number')
    expect(tool.timeoutMs).toBe(120_000)
  })

  it('promises direct-only, NOT_PROVEN ≠ 开路, an old build refusing, and no design write', () => {
    const tool = registered().get('boardwise_pcb_connection') as Tool & { description: string }
    expect(tool.description).toMatch(/direct-only/)
    expect(tool.description).toMatch(/getEntireTrack/)
    expect(tool.description).toMatch(/not 「开路」|not .开路./)
    expect(tool.description).toMatch(/older daemon or connector/)
    expect(tool.description).toMatch(/never opens, focuses or writes a design/)
  })
})

describe('boardwise_pcb_connection: argv', () => {
  it('passes the fixed head and nothing else for a bare call', async () => {
    const mock = installSpawn(child => child.finish(0))

    await call({ from: 'U9.2', to: 'CN3.1' })

    expect(spawnedCommand(mock).slice(1)).toEqual([
      'pcb', 'connection', '--from', 'U9.2', '--to', 'CN3.1',
    ])
    // No second way to name a board and no structured transport: the CLI has no
    // `--json` file here and the focused PCB is the identity.
    for (const flag of ['--file', '--board', '--live', '--json', '--out', '--project', '--instance', '--port']) {
      expect(spawnedCommand(mock)).not.toContain(flag)
    }
  })

  it('appends project, instance and port in order when they are given', async () => {
    const mock = installSpawn(child => child.finish(0))

    await call({ from: 'U9.2', to: 'CN3.1', project: 'test', instance: 'win-1', port: 61190 })

    const argv = spawnedCommand(mock).slice(1)
    expect(argv).toEqual([
      'pcb', 'connection', '--from', 'U9.2', '--to', 'CN3.1',
      '--project', 'test', '--instance', 'win-1', '--port', '61190',
    ])
    expect(flagValue(argv, '--port')).toBe('61190')
  })

  it('trims the ends without inventing a REF.PAD syntax check', async () => {
    const mock = installSpawn(child => child.finish(0))

    // `not-a-ref` is forwarded as given: the syntax is the CLI's judgement.
    await call({ from: '  U9.2  ', to: ' not-a-ref ' })

    expect(spawnedCommand(mock).slice(1)).toEqual([
      'pcb', 'connection', '--from', 'U9.2', '--to', 'not-a-ref',
    ])
  })
})

describe('boardwise_pcb_connection: refusals before the spawn', () => {
  it('refuses a blank from or to', async () => {
    installSpawn(child => child.finish(0))

    await expect(call({ from: '', to: 'CN3.1' })).rejects.toThrow(/from is required/)
    await expect(call({ from: '   ', to: 'CN3.1' })).rejects.toThrow(/from is required/)
    await expect(call({ from: 'U9.2', to: '' })).rejects.toThrow(/to is required/)
    await expect(call({ from: 'U9.2', to: '  ' })).rejects.toThrow(/to is required/)
    // A missing end is the same refusal as an empty one: argparse's exit 2 must
    // never be mistaken for a NOT_PROVEN answer.
    await expect(call({ to: 'CN3.1' })).rejects.toThrow(/from is required/)
    await expect(call({ from: 'U9.2' })).rejects.toThrow(/to is required/)
    expect(spawnCount()).toBe(0)
  })

  it('refuses a port that is not a finite positive integer', async () => {
    installSpawn(child => child.finish(0))

    for (const port of [0, -1, 61190.5, Number.NaN, Number.POSITIVE_INFINITY, '61190']) {
      await expect(call({ from: 'U9.2', to: 'CN3.1', port })).rejects.toThrow(/port must be a finite positive integer/)
    }
    expect(spawnCount()).toBe(0)
  })
})

describe('boardwise_pcb_connection: every exit code is an answer', () => {
  it('hands back exit 0 CONNECTED as text', async () => {
    const mock = installSpawn(child => {
      child.out('{"schema":"boardwise.pcbConnection/1","verdict":"CONNECTED"}\n')
      child.finish(0)
    })

    const message = await call({ from: 'U9.2', to: 'CN3.1' })

    expect(spawnedCommand(mock).slice(1)).toEqual(['pcb', 'connection', '--from', 'U9.2', '--to', 'CN3.1'])
    expect(message).toContain('boardwise_pcb_connection: exit 0')
    expect(message).toContain('"verdict":"CONNECTED"')
  })

  it('hands back exit 2 NOT_PROVEN as a result, never as a thrown error', async () => {
    installSpawn(child => {
      child.out('{"schema":"boardwise.pcbConnection/1","verdict":"NOT_PROVEN","sharedIds":[]}\n')
      child.finish(2)
    })

    const message = await call({ from: 'U9.2', to: 'CN3.1' })

    // A thrown error would be the plugin inventing a verdict of its own: the
    // negative answer, and its JSON, must survive intact.
    expect(message).toContain('boardwise_pcb_connection: exit 2')
    expect(message).toContain('"verdict":"NOT_PROVEN"')
    expect(message).toContain('"sharedIds":[]')
  })

  it('hands back exit 3 INDETERMINATE, and a stderr refusal with empty stdout, as results', async () => {
    installSpawn(child => {
      child.out('{"schema":"boardwise.pcbConnection/1","verdict":"INDETERMINATE"}\n')
      child.finish(3)
    })
    const indeterminate = await call({ from: 'U9.2', to: 'CN3.1' })
    expect(indeterminate).toContain('boardwise_pcb_connection: exit 3')
    expect(indeterminate).toContain('"verdict":"INDETERMINATE"')

    // An older daemon/connector without the action: one line on stderr, empty
    // stdout, exit 3. That is a refusal to answer — still not a TS exception.
    installSpawn(child => {
      child.err("boardwise: unknown action 'pcb.connection_probe'\n")
      child.finish(3)
    })
    const refused = await call({ from: 'U9.2', to: 'CN3.1' })
    expect(refused).toContain('boardwise_pcb_connection: exit 3')
    expect(refused).toContain('--- stdout ---\n(empty)')
    expect(refused).toContain("--- stderr ---\nboardwise: unknown action 'pcb.connection_probe'")
    // The verdict word must not be manufactured by the plugin on a refusal.
    expect(refused).not.toContain('NOT_PROVEN')
    expect(refused).not.toContain('CONNECTED')
  })

  it('propagates a CLI that cannot be started instead of answering', async () => {
    installSpawn((child, command) => child.failToStart(new Error(`spawn ${command} ENOENT`)))

    await expect(call({ from: 'U9.2', to: 'CN3.1' })).rejects.toThrow(/ENOENT/)
  })
})
