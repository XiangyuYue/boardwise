import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@deepseek-ai/dsh-tools', () => ({ defineTool: (options: unknown) => options }))
vi.mock('node:child_process', () => ({ spawn: vi.fn() }))

import { existsSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { apply } from '../src/index.ts'
import { installSpawn, spawnedCommand } from './fake-child.ts'

interface Tool {
  name: string
  parameters: Record<string, { required?: boolean }>
  timeoutMs: number
  description: string
  execute: (args: Record<string, unknown>, exec: { signal: AbortSignal }) => Promise<unknown>
}

const exec = { signal: new AbortController().signal }
const savedExe = process.env['BOARDWISE_EXE']

function tempDir(): string { return mkdtempSync(join(tmpdir(), 'boardwise-draw-plan-')) }
function input(name: string): string {
  const path = join(tempDir(), name)
  writeFileSync(path, '{}\n', 'utf8')
  return path
}
function inputs(): Record<string, string> {
  return { layout: input('cand1.page.json'), circuit: input('circuit.json'),
    presentation: input('presentation.json'), profiles: input('profiles.json') }
}
function tool(): Tool {
  let found: Tool | undefined
  apply({ tools: { register: (definition: unknown) => {
    const candidate = definition as Tool
    if (candidate.name === 'boardwise_draw_plan') found = candidate
    return () => {}
  } } } as never)
  if (!found) throw new Error('boardwise_draw_plan is not registered')
  return found
}
function flag(argv: readonly string[], name: string): string {
  const index = argv.indexOf(name)
  if (index < 0 || !argv[index + 1]) throw new Error(`missing ${name}`)
  return argv[index + 1] as string
}
function payload(ok = true): Record<string, unknown> {
  return { command: 'plan', document: 'page', ok, exitCode: ok ? 0 : 5,
    outcome: ok ? 'planned' : 'refused', reason: ok ? '' : 'readability_refused',
    plan: ok ? { change: { layoutSha256: 'a'.repeat(64) } } : null,
    page: ok ? { geometrySha256: 'b'.repeat(64), modules: [{ id: 'pwr' }] } : null,
    pageDocument: ok ? '/output/plan.page.json' : '', layoutSource: '/input/cand1.page.json',
    notes: ['z'.repeat(48 * 1024)], extraPythonField: { neverTruncate: [1, 2, 3] } }
}
function writeJson(path: string, value: unknown): void {
  writeFileSync(path, JSON.stringify(value), 'utf8')
}

beforeEach(() => {
  const exe = input('boardwise.exe')
  process.env['BOARDWISE_EXE'] = exe
})
afterEach(() => {
  if (savedExe === undefined) delete process.env['BOARDWISE_EXE']
  else process.env['BOARDWISE_EXE'] = savedExe
})

describe('boardwise_draw_plan: saved page preflight transport', () => {
  it('registers only four required inputs and an offline output directory', () => {
    const found = tool()
    expect(Object.keys(found.parameters)).toEqual(['layout', 'circuit', 'presentation', 'profiles', 'out'])
    for (const name of ['layout', 'circuit', 'presentation', 'profiles']) {
      expect(found.parameters[name]?.required).toBe(true)
    }
    expect(found.timeoutMs).toBe(120_000)
    expect(found.description).toMatch(/PageLayoutPlan/)
    expect(found.description).toMatch(/visual/)
  })

  it('passes the exact saved-page argv and returns the whole large JSON without stdout', async () => {
    const args = inputs()
    const out = join(tempDir(), 'nested')
    const value = payload()
    let jsonPath = ''
    const mock = installSpawn((child, _command, argv) => {
      jsonPath = flag(argv, '--json')
      writeJson(jsonPath, value)
      child.out('{invalid stdout' + 'q'.repeat(48 * 1024))
      child.finish(0)
    })
    expect(await tool().execute({ ...args, out }, exec)).toEqual(value)
    expect(spawnedCommand(mock).slice(1)).toEqual([
      'draw', 'plan', '--layout', args['layout'], '--circuit', args['circuit'],
      '--presentation', args['presentation'], '--profiles', args['profiles'],
      '--out', join(out, 'plan.json'), '--json', jsonPath,
    ])
    expect(existsSync(out)).toBe(true)
    expect(dirname(jsonPath)).not.toBe(out)
  })

  it('keeps exit 5 refusal JSON unchanged', async () => {
    const value = payload(false)
    installSpawn((child, _command, argv) => { writeJson(flag(argv, '--json'), value); child.finish(5) })
    expect(await tool().execute(inputs(), exec)).toEqual(value)
  })

  it('uses a fresh persistent output directory by default', async () => {
    const mock = installSpawn((child, _command, argv) => {
      writeJson(flag(argv, '--json'), payload()); child.finish(0)
    })
    await tool().execute(inputs(), exec)
    const first = dirname(flag(spawnedCommand(mock), '--out'))
    await tool().execute(inputs(), exec)
    const second = dirname(flag(spawnedCommand(mock), '--out'))
    expect(first).not.toBe(second)
    expect(existsSync(first)).toBe(true)
    expect(existsSync(second)).toBe(true)
  })

  it.each(['layout', 'circuit', 'presentation', 'profiles'])('rejects missing %s without spawning', async name => {
    const args = inputs()
    args[name] = join(tempDir(), 'absent.json')
    const mock = installSpawn(child => child.finish(0))
    await expect(tool().execute(args, exec)).rejects.toThrow(/not found/)
    expect(mock).not.toHaveBeenCalled()
  })

  it.each([2, 3])('rejects unexpected exit %s even if JSON exists', async code => {
    installSpawn((child, _command, argv) => { writeJson(flag(argv, '--json'), payload(false)); child.finish(code) })
    await expect(tool().execute(inputs(), exec)).rejects.toThrow(new RegExp(`exit ${code}`))
  })

  it.each(['missing', 'malformed'])('rejects %s JSON instead of interpreting stdout', async mode => {
    installSpawn((child, _command, argv) => {
      if (mode === 'malformed') writeFileSync(flag(argv, '--json'), '{broken', 'utf8')
      child.out(JSON.stringify(payload())); child.finish(0)
    })
    await expect(tool().execute(inputs(), exec)).rejects.toThrow(/JSON|read|transport/i)
  })

  it.each(['command', 'document', 'ok', 'plan', 'pageDocument'])('rejects an invalid %s envelope', async field => {
    const value = payload()
    delete value[field]
    installSpawn((child, _command, argv) => { writeJson(flag(argv, '--json'), value); child.finish(0) })
    await expect(tool().execute(inputs(), exec)).rejects.toThrow()
  })
})
