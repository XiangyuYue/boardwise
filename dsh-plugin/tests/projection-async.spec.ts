/**
 * DSH 0.2.2-rc.1: `SessionProjectionRegistry.register` returns
 * `Promise<ProjectionHandle<S>>`, `handle.stateOf(session)` is synchronous and
 * `registry.stateOf(session, key)` is deprecated. This spec pins the two-shaped
 * contract the plugin now honours:
 *
 * - **awaitable registration** — the finalize tool (and every later reader:
 *   the delivery gate) is published only after the handle is ready, and both
 *   read through the handle, never through the deprecated registry read;
 * - **synchronous registration** (0.2.1, and every light fake context) — the
 *   tool is registered at once and reads the registry exactly as before.
 *
 * The fakes here are deliberately minimal: 0.2.1's class is not needed to prove
 * the shape dispatch, and a fake that *throws* on the deprecated read is the
 * only way to prove the new branch never takes it.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@deepseek-ai/dsh-tools', () => ({ defineTool: (options: unknown) => options }))
vi.mock('node:child_process', () => ({ spawn: vi.fn() }))

import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, sep } from 'node:path'
import { apply } from '../src/index.ts'
import {
  REVIEW_FINALIZED_KEY,
  REVIEW_FINALIZED_STATE_VERSION,
  REVIEW_FINALIZE_TOOL,
  isPendingRegistration,
  registerReviewFinalize,
  type ReviewProjectionReader,
} from '../src/review-finalize.ts'
import { REVIEW_DELIVERY_EVENT, type DeliveryFileSystem, type DeliveryTarget } from '../src/review-delivery.ts'
import { installSpawn } from './fake-child.ts'

/** One registered tool, as `defineTool` would pass it to the registry. */
interface Tool {
  name: string
  description: string
  parameters: Record<string, unknown>
  output: { schema: { type: string; [key: string]: unknown }; render: (a: unknown, v: unknown) => unknown }
  execute: (args: Record<string, unknown>, exec: Record<string, unknown>) => Promise<unknown>
  timeoutMs?: number
}

type Decision = { kind: 'allow' } | { kind: 'deny'; reason: string }
type Listener = (exec: unknown, next: () => Promise<Decision>) => Promise<Decision>

/** The whole eight-plus-draw order `apply` has always published. */
const TOOL_ORDER = [
  'boardwise_checkup',
  'boardwise_arch',
  'boardwise_doctor',
  'boardwise_bridge',
  'boardwise_review_read',
  'boardwise_review_evidence',
  'boardwise_triage_batch',
  'boardwise_review_finalize',
  'boardwise_draw_compile',
  'boardwise_draw_lint',
] as const

/** Everything before the finalize tool: registered without touching projections. */
const BEFORE_FINALIZE = TOOL_ORDER.slice(0, 7)

/** A fixed absolute root, so the gate's path folding has something stable. */
const ROOT = resolve('/boardwise-handle-root')

const made: string[] = []
const savedExe = process.env['BOARDWISE_EXE']

afterEach(() => {
  for (const dir of made.splice(0)) rmSync(dir, { recursive: true, force: true })
  if (savedExe === undefined) delete process.env['BOARDWISE_EXE']
  else process.env['BOARDWISE_EXE'] = savedExe
  vi.useRealTimers()
})

function tempDir(prefix: string): string {
  const dir = mkdtempSync(join(tmpdir(), prefix))
  made.push(dir)
  return dir
}

/** One promise settled by hand — the "registration is still in flight" state. */
function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let settle!: (value: T) => void
  const promise = new Promise<T>(resolvePromise => {
    settle = resolvePromise
  })
  return { promise, resolve: value => settle(value) }
}

interface AwaitableRegistry {
  readonly registry: { stateOf: unknown; register: (definition: unknown) => unknown }
  /** The projection keys `register` was called with, in order. */
  readonly keys: string[]
  /** The registry's own (deprecated) read: every call fails this test. */
  readonly registryStateOf: ReturnType<typeof vi.fn>
  /** Resolve the registration with a ready handle over `stateOf`. */
  readonly ready: () => void
}

/** A 0.2.2-shaped registry: awaitable `register`, deprecated `stateOf`. */
function awaitableRegistry(handleStateOf: (session: unknown) => unknown = () => ({ receipts: {} })): AwaitableRegistry {
  const pending = deferred<{ stateOf: (session: unknown) => unknown }>()
  const keys: string[] = []
  const registryStateOf = vi.fn((): never => {
    throw new Error('the deprecated registry read must not be used on the 0.2.2 branch')
  })
  return {
    registry: {
      stateOf: registryStateOf,
      register: (definition: unknown) => {
        keys.push((definition as { key: string }).key)
        return pending.promise
      },
    },
    keys,
    registryStateOf,
    ready: () => pending.resolve({ stateOf: handleStateOf }),
  }
}

interface FakeContext {
  readonly tools: Tool[]
  readonly names: string[]
  readonly listeners: Map<string, unknown>
  readonly ctx: Record<string, unknown>
}

function fakeContext(sessionProjections?: unknown, services: { fs?: DeliveryFileSystem } = {}): FakeContext {
  const tools: Tool[] = []
  const names: string[] = []
  const listeners = new Map<string, unknown>()
  const ctx: Record<string, unknown> = {
    tools: {
      register: (definition: unknown) => {
        const tool = definition as Tool
        tools.push(tool)
        names.push(tool.name)
        return () => {}
      },
    },
    sessionProjections,
    fs: services.fs,
    workingDirectory: { get: () => ROOT },
    on: (event: string, listener: unknown) => {
      listeners.set(event, listener)
      return () => true
    },
  }
  return { tools, names, listeners, ctx }
}

/**
 * The slice of `ctx.fs` the gate touches for these cases. Nothing exists on
 * disk: `stat` always says "missing", so no marker is ever found and no file is
 * ever hashed.
 */
function fakeFileSystem(): DeliveryFileSystem {
  const target = (path: string): DeliveryTarget => {
    const absolute = resolve(path)
    return { targetKey: absolute, displayPath: absolute }
  }
  return {
    resolve: (path: string) => Promise.resolve(target(path)),
    processPath: value => value.targetKey,
    stat: () => Promise.resolve(undefined),
    contains: (parent: DeliveryTarget, child: DeliveryTarget) =>
      child.targetKey === parent.targetKey || child.targetKey.startsWith(`${parent.targetKey}${sep}`),
    readByteRange: () => Promise.reject(new Error('the gate must not read any file in this case')),
  }
}

function toolNamed(tools: readonly Tool[], name: string): Tool {
  const found = tools.find(tool => tool.name === name)
  if (found === undefined) throw new Error(`no such tool: ${name}`)
  return found
}

describe('session projections: the awaitable 0.2.2 registration', () => {
  it('withholds the finalize tool until the handle is ready, then reads through the handle', async () => {
    const state = { receipts: { 'c:/review': { reviewDir: 'C:/review', receipt: {}, callId: null } } }
    const handleStateOf = vi.fn((_session: unknown) => state)
    const awaitable = awaitableRegistry(handleStateOf)
    const fake = fakeContext(awaitable.registry)

    const registration = registerReviewFinalize(fake.ctx as never)

    // Still pending: nothing may be published while `register` is in flight, or
    // a call could read a projection that is not registered yet.
    expect(isPendingRegistration(registration)).toBe(true)
    expect(fake.names).toEqual([])
    expect(awaitable.keys).toEqual([REVIEW_FINALIZED_KEY])

    awaitable.ready()
    const reader = await (registration as Promise<ReviewProjectionReader | undefined>)

    expect(fake.names).toEqual([REVIEW_FINALIZE_TOOL])
    expect(reader).toBeDefined()
    const session = { id: 'session-handle' }
    expect(reader?.stateOf(session as never)).toBe(state)
    expect(handleStateOf).toHaveBeenCalledWith(session)
    // The deprecated registry read is never taken on this branch.
    expect(awaitable.registryStateOf).not.toHaveBeenCalled()
  })

  it('keeps the tool order and publishes the delivery gate only after the handle is ready', async () => {
    const awaitable = awaitableRegistry()
    const fake = fakeContext(awaitable.registry, { fs: fakeFileSystem() })

    const pending = apply(fake.ctx as never)
    expect(pending).toBeInstanceOf(Promise)

    // The synchronous part of the registration is already published …
    expect(fake.names).toEqual([...BEFORE_FINALIZE])
    // … and neither the finalize-dependent tools nor the gate exist yet.
    expect(fake.listeners.has(REVIEW_DELIVERY_EVENT)).toBe(false)

    awaitable.ready()
    await pending

    expect(fake.names).toEqual([...TOOL_ORDER])
    expect(fake.listeners.has(REVIEW_DELIVERY_EVENT)).toBe(true)
    expect(awaitable.registryStateOf).not.toHaveBeenCalled()

    // The definition still went through with 537D3a's frozen version.
    expect(awaitable.keys).toEqual([REVIEW_FINALIZED_KEY])
    expect(REVIEW_FINALIZED_STATE_VERSION).toBe(1)
  })

  it('lets the delivery gate read the ready handle instead of the deprecated registry read', async () => {
    const reviewDir = join(ROOT, 'review')
    const key = process.platform === 'win32' ? reviewDir.toLowerCase() : reviewDir
    // A record whose `reviewDir` is not absolute cannot authorize anything.
    const state = { receipts: { [key]: { reviewDir: 'relative/review', receipt: {}, callId: null } } }
    const awaitable = awaitableRegistry(() => state)
    const fake = fakeContext(awaitable.registry, { fs: fakeFileSystem() })

    const pending = apply(fake.ctx as never)
    awaitable.ready()
    await pending

    const listener = fake.listeners.get(REVIEW_DELIVERY_EVENT) as Listener
    expect(listener).toBeDefined()

    const next = vi.fn(async (): Promise<Decision> => ({ kind: 'allow' }))
    const decision = await listener(
      {
        name: 'present',
        arguments: { files: [{ path: join(reviewDir, 'report.json') }] },
        agent: { session: { id: 'session-handle-delivery' } },
        signal: new AbortController().signal,
        callId: 'call-present-handle',
        token: Symbol('handle-secret-token'),
      },
      next,
    )

    // The reader's (broken) record was seen: the denial comes from the handle's
    // state, and the registry's deprecated read was never asked.
    expect(decision.kind).toBe('deny')
    expect(decision.kind === 'deny' ? decision.reason : '').toMatch(/receipt is not usable/)
    expect(next).not.toHaveBeenCalled()
    expect(awaitable.registryStateOf).not.toHaveBeenCalled()
  })

  it('fails closed when the ready handle serves no state for the Session', async () => {
    const awaitable = awaitableRegistry(() => undefined)
    const fake = fakeContext(awaitable.registry)
    const out = tempDir('boardwise-handle-out-')
    const exe = join(tempDir('boardwise-handle-bin-'), 'boardwise.exe')
    writeFileSync(exe, '')
    process.env['BOARDWISE_EXE'] = exe
    // A receipt that passes 537D3a's envelope check: the refusal must come from
    // the missing projection state, not from the receipt.
    installSpawn((child, _command, args) => {
      const index = args.indexOf('--out')
      writeFileSync(
        join(args[index + 1] as string, 'finalize.json'),
        JSON.stringify({
          schema: 'boardwise.review-finalize/1',
          ok: true,
          scope: 'delivery-content',
          boardConclusionAuthority: 'report.conclusion',
          files: [],
        }),
        'utf8',
      )
      child.finish(0)
    })

    const registration = registerReviewFinalize(fake.ctx as never)
    awaitable.ready()
    await registration

    const session = { id: 'session-handle-missing-state' }
    await expect(
      toolNamed(fake.tools, REVIEW_FINALIZE_TOOL).execute(
        { out },
        { signal: new AbortController().signal, agent: { session }, callId: 'call-handle-1' },
      ),
    ).rejects.toThrow(/does not serve/)
    expect(awaitable.registryStateOf).not.toHaveBeenCalled()
  })
})

describe('session projections: the 0.2.1 synchronous registration is unchanged', () => {
  it('registers the tool at once and reads the registry, not a handle', () => {
    const state = { receipts: {} }
    const registryStateOf = vi.fn(() => state)
    const registry = {
      stateOf: registryStateOf,
      // 0.2.1: a plain synchronous disposer. The real one is a callable with an
      // awaitable `then`; the negative case below covers that exact shape.
      register: vi.fn(() => () => {}),
    }
    const fake = fakeContext(registry)

    const registration = registerReviewFinalize(fake.ctx as never)

    expect(isPendingRegistration(registration)).toBe(false)
    expect(fake.names).toEqual([REVIEW_FINALIZE_TOOL])
    const reader = registration as ReviewProjectionReader
    const session = { id: 'session-sync' }
    expect(reader.stateOf(session as never)).toBe(state)
    expect(registryStateOf).toHaveBeenCalledWith(session, REVIEW_FINALIZED_KEY)
  })

  it('treats a then-only callable disposer as the synchronous branch: not awaited, not disposed', () => {
    const state = { receipts: {} }
    const registryStateOf = vi.fn(() => state)
    /** What the plugin must never do to this value: awaiting it disposes. */
    const calls: string[] = []
    // Exactly what 0.2.1 hands back: cordis's `ctx.effect` disposer is a
    // **callable** with one extra `then` (no `catch`, no `finally`), and its
    // `then` disposes the registration before it resolves.
    const disposer = Object.assign(
      () => {
        calls.push('dispose')
        return true
      },
      {
        then: async (onFulfilled?: (value: unknown) => unknown): Promise<unknown> => {
          calls.push('awaited')
          return onFulfilled?.(undefined)
        },
      },
    )
    const registry = { stateOf: registryStateOf, register: vi.fn(() => disposer) }
    const fake = fakeContext(registry)

    const registration = registerReviewFinalize(fake.ctx as never)

    // A then-only callable is a disposer, not a registration: the tool is
    // published at once and the disposer is neither called nor awaited.
    expect(isPendingRegistration(registration)).toBe(false)
    expect(fake.names).toEqual([REVIEW_FINALIZE_TOOL])
    expect(calls).toEqual([])

    const session = { id: 'session-then-only' }
    const reader = registration as ReviewProjectionReader
    expect(reader.stateOf(session as never)).toBe(state)
    expect(registryStateOf).toHaveBeenCalledWith(session, REVIEW_FINALIZED_KEY)
    // Reading through the reader must not have touched the disposer either.
    expect(calls).toEqual([])
  })

  it('publishes the whole order synchronously and returns no promise from apply', () => {
    const registry = { stateOf: vi.fn(() => ({ receipts: {} })), register: vi.fn(() => () => {}) }
    const fake = fakeContext(registry, { fs: fakeFileSystem() })

    const returned = apply(fake.ctx as never)

    expect(returned).toBeUndefined()
    expect(fake.names).toEqual([...TOOL_ORDER])
    expect(fake.listeners.has(REVIEW_DELIVERY_EVENT)).toBe(true)
  })

  it('still mounts the finalize tool on a light fake and fails loudly without a projection', async () => {
    const fake = fakeContext(undefined)

    const registration = apply(fake.ctx as never)

    expect(registration).toBeUndefined()
    expect(fake.names).toEqual([...TOOL_ORDER])
    // No gate without the services it needs — the older contract, unchanged.
    expect(fake.listeners.has(REVIEW_DELIVERY_EVENT)).toBe(false)

    await expect(
      toolNamed(fake.tools, REVIEW_FINALIZE_TOOL).execute(
        { out: join(ROOT, 'review') },
        { signal: new AbortController().signal, agent: { session: { id: 'session-light' } }, callId: 'c-1' },
      ),
    ).rejects.toThrow(/session-projection service/)
  })
})
