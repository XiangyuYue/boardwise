/**
 * 541R3: the review stage checkpoint gate, driven through the listener `apply`
 * actually mounts and through a real `dsh-session` Session + a real
 * `SessionProjectionRegistry`.
 *
 * Nothing here hand-writes a projection state: every batch, checkpoint and
 * model step is produced by appending the real `tool/call` / `tool/result`
 * events (and, for a checkpoint, 537D3a's real `plugin:boardwise-dsh/review-finalized`
 * record), so these cases prove the fold as well as the decision.
 *
 * The wall clock is the one thing a test must own: `createReviewStageGate` takes
 * an injected `now`, and the budget cases drive that gate directly. The mounted
 * chain is driven for the wiring, the refusals and the "old listener still
 * fires" contract.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@deepseek-ai/dsh-tools', () => ({ defineTool: (options: unknown) => options }))
vi.mock('node:child_process', () => ({ spawn: vi.fn() }))

import { mkdtempSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, sep } from 'node:path'
import { Context } from '@deepseek-ai/cordis'
import { Session, appendPluginRecord } from '@deepseek-ai/dsh-session'
import { createToolResultMessage } from '@deepseek-ai/dsh-llm'
import { SessionProjectionRegistry } from '@deepseek-ai/dsh-session-projection'
import { apply } from '../src/index.ts'
import {
  REVIEW_FINALIZED_KEY,
  REVIEW_FINALIZED_RECORD,
  REVIEW_FINALIZE_AUTHORITY,
  REVIEW_FINALIZE_SCHEMA,
  REVIEW_FINALIZE_SCOPE,
  REVIEW_FINALIZE_TOOL,
  directoryKeyOf,
} from '../src/review-finalize.ts'
import { REVIEW_DELIVERY_EVENT, type DeliveryFileSystem, type DeliveryTarget } from '../src/review-delivery.ts'
import {
  REVIEW_STAGE_CHECKPOINT_HISTORY,
  REVIEW_STAGE_DEEP_DIVE_TOOLS,
  REVIEW_STAGE_EVENT,
  REVIEW_STAGE_PROJECTION_KEY,
  REVIEW_STAGE_STATE_VERSION,
  REVIEW_STAGE_STEP_LIMIT,
  REVIEW_STAGE_TIME_LIMIT_MS,
  createReviewStageGate,
  type BoardwiseReviewStageState,
  type ReviewStageReader,
} from '../src/review-stage-gate.ts'
import { installSpawn, spawnedCommand } from './fake-child.ts'

type Decision = { kind: 'allow' } | { kind: 'deny'; reason: string }
type Listener = (exec: Exec, next: () => Promise<Decision>) => Promise<Decision>

interface Exec {
  name: string
  arguments: unknown
  agent?: { session: InstanceType<typeof Session> }
  signal: AbortSignal
  callId: string
  token: symbol
}

interface Tool {
  name: string
  parameters: Record<string, unknown>
  execute: (args: Record<string, unknown>, exec: Record<string, unknown>) => Promise<unknown>
}

const savedExe = process.env['BOARDWISE_EXE']

/**
 * A fresh temporary directory. These are deliberately **not** cleaned up: this
 * repository forbids direct deletion (every discarded file goes to the recycle
 * bin), so a test's scratch directories stay in the OS temp folder.
 */
function tempDir(prefix = 'boardwise-stage-'): string {
  return mkdtempSync(join(tmpdir(), prefix))
}

/** The receipt the CLI signs for an empty delivery — 537D3a's frozen envelope. */
const RECEIPT = {
  schema: REVIEW_FINALIZE_SCHEMA,
  ok: true,
  scope: REVIEW_FINALIZE_SCOPE,
  boardConclusionAuthority: REVIEW_FINALIZE_AUTHORITY,
  files: [],
} as const

/**
 * Compose every listener of one cordis waterfall in registration order, which
 * is how the registry composes them. 537D3b's `present` gate and 541R3's stage
 * gate are two listeners on `tools/pre-execute`; a single-slot map would keep
 * only the last and hide a regression.
 */
function chainOf(listeners: Map<string, Listener[]>, event: string): Listener | undefined {
  const chain = listeners.get(event)
  if (chain === undefined || chain.length === 0) return undefined
  const step = (index: number): Listener => async (exec, next) => {
    const listener = chain[index]
    if (listener === undefined) return next()
    return listener(exec, () => step(index + 1)(exec, next))
  }
  return step(0)
}

/**
 * A real directory-inspecting `ctx.fs`: enough for 537D3b's `present` gate to
 * recognize a review directory (so the composed waterfall really reaches it),
 * and never able to hash a file — the stage gate itself reads nothing.
 */
function inspectingFileSystem(): DeliveryFileSystem {
  const target = (path: string): DeliveryTarget => {
    const absolute = path.startsWith('/') || /^[A-Za-z]:/.test(path) ? path : join(process.cwd(), path)
    return { targetKey: absolute, displayPath: absolute }
  }
  return {
    resolve: (path: string) => Promise.resolve(target(path)),
    processPath: value => value.targetKey,
    stat: targetValue =>
      Promise.resolve().then(() => {
        const info = statSync(targetValue.targetKey, { throwIfNoEntry: false })
        if (info === undefined) return undefined
        return info.isFile() ? { type: 'file' as const, size: info.size } : { type: 'directory' as const }
      }),
    contains: (parent, child) =>
      child.targetKey === parent.targetKey || child.targetKey.startsWith(`${parent.targetKey}${sep}`),
    readByteRange: () => Promise.reject(new Error('the stage gate must not read files')),
  }
}

interface Harness {
  projections: InstanceType<typeof SessionProjectionRegistry>
  listeners: Map<string, Listener[]>
  names: string[]
  tools: Map<string, Tool>
  session: (id: string) => InstanceType<typeof Session>
  /** The production wiring: everything `apply` mounted, composed in order. */
  chain: Listener
  /** The same services with a clock the test owns. */
  gate: (now: () => number) => Listener
  stageState: (session: InstanceType<typeof Session>) => BoardwiseReviewStageState | undefined
}

/** Register the real plugin on a real registry and capture every listener. */
async function harness(): Promise<Harness> {
  const cordis = new Context()
  const projections = new SessionProjectionRegistry(cordis)
  const listeners = new Map<string, Listener[]>()
  const names: string[] = []
  const tools = new Map<string, Tool>()
  const pluginCtx = {
    tools: {
      register: (definition: unknown) => {
        const tool = definition as Tool
        tools.set(tool.name, tool)
        names.push(tool.name)
        return () => {}
      },
    },
    sessionProjections: projections,
    fs: inspectingFileSystem(),
    workingDirectory: { get: () => process.cwd() },
    on: (event: string, listener: Listener) => {
      const existing = listeners.get(event)
      if (existing === undefined) listeners.set(event, [listener])
      else existing.push(listener)
      return () => true
    },
  }
  await apply(pluginCtx as never)

  const chain = chainOf(listeners, REVIEW_STAGE_EVENT)
  if (chain === undefined) throw new Error(`apply did not register ${REVIEW_STAGE_EVENT}`)
  const stage: ReviewStageReader = {
    stateOf: session => projections.stateOf(session, REVIEW_STAGE_PROJECTION_KEY),
  }
  const receipts = { stateOf: (session: InstanceType<typeof Session>) => projections.stateOf(session, REVIEW_FINALIZED_KEY) }

  return {
    projections,
    listeners,
    names,
    tools,
    session: id => Session.create(id as never),
    chain,
    gate: now => createReviewStageGate({ receipts, stage, now }),
    stageState: session => projections.stateOf(session, REVIEW_STAGE_PROJECTION_KEY),
  }
}

/* ---------------------------------------------------------------- session log */

/** One committed `tool/call`. */
function call(
  session: InstanceType<typeof Session>,
  options: { callId: string; name: string; args?: unknown; step: number },
): void {
  session.append('tool/call', {
    turn: 1,
    step: options.step,
    callId: options.callId as never,
    name: options.name,
    arguments: JSON.stringify(options.args ?? {}),
  })
}

/** The matching committed `tool/result` — what "the call completed" means. */
function result(
  session: InstanceType<typeof Session>,
  options: { callId: string; step: number; isError?: boolean },
): void {
  session.append(
    'tool/result',
    {
      turn: 1,
      step: options.step,
      message: createToolResultMessage({
        callId: options.callId as never,
        content: [{ type: 'text', text: 'done' }],
        isError: options.isError ?? false,
      }),
    },
    { surfaceOp: 'append' },
  )
}

/**
 * A legacy Session log's `tool/result`: the message carries **no** `isError`
 * field at all, as every log written before 541R4 did.
 */
function legacyResult(
  session: InstanceType<typeof Session>,
  options: { callId: string; step: number },
): void {
  const message: Record<string, unknown> = {
    ...createToolResultMessage({
      callId: options.callId as never,
      content: [{ type: 'text', text: 'done' }],
      isError: false,
    }),
  }
  delete message['isError']
  session.append(
    'tool/result',
    { turn: 1, step: options.step, message: message as never },
    { surfaceOp: 'append' },
  )
}

/** One completed managed deep dive for `out`. */
function dive(
  session: InstanceType<typeof Session>,
  out: string,
  options: { callId: string; step: number; name?: string },
): void {
  const name = options.name ?? 'boardwise_checkup'
  call(session, { callId: options.callId, name, args: { out }, step: options.step })
  result(session, { callId: options.callId, step: options.step })
}

/**
 * One completed `boardwise_review_finalize` **plus** the Session record 537D3a
 * writes on success — the only pair that can be a checkpoint.
 */
function finalize(
  session: InstanceType<typeof Session>,
  out: string,
  options: { callId: string; step: number; stage?: 'initial' | 'partial'; receiptDir?: string; record?: boolean },
): void {
  call(session, {
    callId: options.callId,
    name: REVIEW_FINALIZE_TOOL,
    args: options.stage === undefined ? { out } : { out, stage: options.stage },
    step: options.step,
  })
  result(session, { callId: options.callId, step: options.step })
  if (options.record === false) return
  const dir = options.receiptDir ?? out
  appendPluginRecord(session, REVIEW_FINALIZED_RECORD, {
    receipts: {
      [directoryKeyOf(dir)]: { reviewDir: dir, receipt: RECEIPT, callId: options.callId },
    },
  } as never)
}

/** An ordinary, unmanaged tool call that still moves the model-step clock. */
function otherCall(session: InstanceType<typeof Session>, step: number): void {
  call(session, { callId: `call-other-${step}`, name: 'boardwise_arch', args: {}, step })
}

/* ------------------------------------------------------------------- driving */

function execFor(
  session: InstanceType<typeof Session> | undefined,
  name: string,
  args: unknown,
  signal = new AbortController().signal,
): Exec {
  return {
    name,
    arguments: args,
    ...(session === undefined ? {} : { agent: { session } }),
    signal,
    callId: 'call-under-test',
    // A recognisable secret: no denial reason may echo it.
    token: Symbol('stage-gate-secret-token'),
  }
}

async function decide(
  listener: Listener,
  session: InstanceType<typeof Session> | undefined,
  name: string,
  args: unknown,
  controller = new AbortController(),
): Promise<{ decision: Decision; nextCalls: number; aborted: boolean }> {
  const next = vi.fn(async (): Promise<Decision> => ({ kind: 'allow' }))
  const decision = await listener(execFor(session, name, args, controller.signal), next)
  return { decision, nextCalls: next.mock.calls.length, aborted: controller.signal.aborted }
}

function expectAllowed(outcome: { decision: Decision; nextCalls: number }): void {
  expect(outcome.decision).toEqual({ kind: 'allow' })
  expect(outcome.nextCalls).toBe(1)
}

function expectDenied(
  outcome: { decision: Decision; nextCalls: number; aborted: boolean },
  pattern: RegExp,
): void {
  // A refusal is a decision, never a cancellation: the gate must not abort the
  // execution it declined (a call already dispatched finishes on its own).
  expect(outcome.aborted).toBe(false)
  expect(outcome.decision.kind).toBe('deny')
  expect(outcome.nextCalls).toBe(0)
  if (outcome.decision.kind === 'deny') {
    expect(outcome.decision.reason).toMatch(pattern)
    expect(outcome.decision.reason).not.toContain('stage-gate-secret-token')
  }
}

const ALWAYS_NOW = (): number => Date.now()

beforeEach(() => {
  const exe = join(tempDir('boardwise-stage-bin-'), 'boardwise.exe')
  writeFileSync(exe, '')
  process.env['BOARDWISE_EXE'] = exe
  // A stage finalize that succeeds: the CLI writes a valid receipt into --out.
  vi.useRealTimers()
})

afterEach(() => {
  if (savedExe === undefined) delete process.env['BOARDWISE_EXE']
  else process.env['BOARDWISE_EXE'] = savedExe
})

/* -------------------------------------------------------------------- tests */

describe('541R3 registration: both gates on one waterfall', () => {
  it('keeps the twelve-tool order and mounts the stage gate beside the present gate', async () => {
    const h = await harness()
    expect(h.names).toEqual([
      'boardwise_checkup',
      'boardwise_arch',
      'boardwise_doctor',
      'boardwise_bridge',
      'boardwise_review_read',
      'boardwise_review_evidence',
      'boardwise_triage_batch',
      'boardwise_review_finalize',
      'boardwise_parts_hunt',
      'boardwise_draw_compile',
      'boardwise_draw_lint',
      'boardwise_draw_v4_facts',
      'boardwise_draw_plan',
    ])
    // Two listeners, not one: the old `present` gate is not overwritten.
    expect(h.listeners.get(REVIEW_STAGE_EVENT)?.length).toBe(2)
    expect(h.listeners.get(REVIEW_DELIVERY_EVENT)?.length).toBe(2)
    expect(REVIEW_STAGE_EVENT).toBe(REVIEW_DELIVERY_EVENT)
    expect(REVIEW_STAGE_STATE_VERSION).toBe(1)
    expect(REVIEW_STAGE_DEEP_DIVE_TOOLS).toEqual(['boardwise_checkup', 'boardwise_review_evidence'])
  })

  it('composes the two listeners so the present gate still denies its own case', async () => {
    const h = await harness()
    const session = h.session('session-stage-compose')
    // A present of a review directory nobody finalized: the 537D3b gate's
    // denial must still be reached through the shared waterfall.
    const dir = tempDir()
    writeFileSync(join(dir, 'review-summary.md'), '# summary\n')
    const outcome = await decide(h.chain, session, 'present', { files: [{ path: join(dir, 'report.json') }] })
    expectDenied(outcome, /has not finalized/)
  })
})

describe('541R3 first dive and the finishing tools', () => {
  it('lets the first checkup with an explicit out through', async () => {
    const h = await harness()
    const session = h.session('session-stage-first')
    expectAllowed(await decide(h.chain, session, 'boardwise_checkup', { file: 'x.epro2', out: tempDir() }))
  })

  it('refuses a managed checkup that names no out, before any state is read', async () => {
    const h = await harness()
    const session = h.session('session-stage-no-out')
    expectDenied(
      await decide(h.chain, session, 'boardwise_checkup', { file: 'x.epro2' }),
      /must be given explicitly/,
    )
    expectDenied(await decide(h.chain, session, 'boardwise_review_evidence', {}), /must be given explicitly/)
    // Nothing was booked: an out-less call cannot open a batch.
    expect(h.stageState(session)?.batches).toEqual({})
  })

  it('always lets review_read, review_finalize and doctor through', async () => {
    const h = await harness()
    const session = h.session('session-stage-finish')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-1', step: 1 })
    // The batch has one dive and no checkpoint, yet the way out stays open.
    for (const name of ['boardwise_review_read', 'boardwise_review_finalize', 'boardwise_doctor']) {
      expectAllowed(await decide(h.chain, session, name, { out }))
    }
    // … and the deep dive itself is refused.
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out }), /no \*current\* stage checkpoint/)
  })

  it('refuses the next dive in the same batch, and a fresh out too while that checkpoint is owed', async () => {
    const h = await harness()
    const session = h.session('session-stage-same-out')
    const a = tempDir('boardwise-stage-a-')
    const b = tempDir('boardwise-stage-b-')
    dive(session, a, { callId: 'call-dive-a1', step: 1 })

    const owed = /no \*current\* stage checkpoint/
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out: a }), owed)
    expectDenied(await decide(h.chain, session, 'boardwise_review_evidence', { out: a }), owed)
    // The same directory spelled relatively or with a trailing separator is the
    // same batch: the key is `resolve` + `directoryKeyOf`, exactly as 537D3a.
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out: `${a}/` }), owed)
    // §3.2: another explicit out is **not** a way around the undelivered
    // batch. The refusal names the out that is still owed.
    const fresh = await decide(h.chain, session, 'boardwise_checkup', { out: b })
    expectDenied(fresh, owed)
    expect(fresh.decision.kind === 'deny' ? fresh.decision.reason : '').toContain(JSON.stringify(a))

    // Once that batch is delivered, a fresh out may start its own batch (§3.3).
    finalize(session, a, { callId: 'call-fin-a1', step: 2, stage: 'initial' })
    expectAllowed(await decide(h.chain, session, 'boardwise_checkup', { out: a }))
    expectAllowed(await decide(h.chain, session, 'boardwise_checkup', { out: b }))
  })

  it('refuses a fresh out while a receipt of another batch went stale', async () => {
    const h = await harness()
    const session = h.session('session-stage-cross-stale')
    const a = tempDir('boardwise-stage-stale-a-')
    const b = tempDir('boardwise-stage-stale-b-')
    dive(session, a, { callId: 'call-dive-stale', step: 1 })
    finalize(session, a, { callId: 'call-fin-stale-stage', step: 2, stage: 'initial' })
    // A later staged finalize that recorded nothing leaves A owing a checkpoint:
    // the recorded receipt still belongs to the *previous* call.
    finalize(session, a, { callId: 'call-fin-stale-silent', step: 3, stage: 'partial', record: false })

    const owed = /no \*current\* stage checkpoint/
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out: a }), owed)
    const fresh = await decide(h.chain, session, 'boardwise_checkup', { out: b })
    expectDenied(fresh, owed)
    expect(fresh.decision.kind === 'deny' ? fresh.decision.reason : '').toContain(JSON.stringify(a))

    // A real new checkpoint for A opens both A and B again.
    finalize(session, a, { callId: 'call-fin-stale-real', step: 4, stage: 'partial' })
    expectAllowed(await decide(h.chain, session, 'boardwise_checkup', { out: b }))
  })

  it('never books a refused tool/call, so a denial cannot switch the batch', async () => {
    const h = await harness()
    const session = h.session('session-stage-denied-call')
    const a = tempDir('boardwise-stage-denied-a-')
    const b = tempDir('boardwise-stage-denied-b-')
    dive(session, a, { callId: 'call-dive-denied', step: 1 })

    // The refusal is the *pre-execute* decision: no `tool/result` follows, so
    // the fold keeps A's dive count and never creates B.
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out: b }), /no \*current\* stage checkpoint/)
    const state = h.stageState(session)
    expect(Object.keys(state?.batches ?? {})).toEqual([directoryKeyOf(a)])
    expect(state?.batches[directoryKeyOf(a)]?.diveCount).toBe(1)

    // B becomes a batch only once its dive actually completes — and only after
    // A's checkpoint is delivered, since nothing else may start while A owes one.
    finalize(session, a, { callId: 'call-fin-denied', step: 2, stage: 'initial' })
    dive(session, b, { callId: 'call-dive-b', step: 3 })
    expect(Object.keys(h.stageState(session)?.batches ?? {}).sort()).toEqual(
      [directoryKeyOf(a), directoryKeyOf(b)].sort(),
    )
    expect(h.stageState(session)?.batches[directoryKeyOf(b)]?.diveCount).toBe(1)
  })
})

describe('541R3 the checkpoint is the Session pair, never a file', () => {
  it('does not accept a hand-written finalize.json (no Session receipt)', async () => {
    const h = await harness()
    const session = h.session('session-stage-handwritten')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-hw', step: 1 })
    // The receipt file exists on disk, and even a staged finalize completed —
    // but nothing was recorded in the Session, so no checkpoint exists.
    writeFileSync(join(out, 'finalize.json'), JSON.stringify(RECEIPT), 'utf8')
    finalize(session, out, { callId: 'call-fin-hw', step: 2, stage: 'initial', record: false })
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out }), /no \*current\* stage checkpoint/)
  })

  it('does not accept a plain finalize without a stage', async () => {
    const h = await harness()
    const session = h.session('session-stage-plain')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-plain', step: 1 })
    finalize(session, out, { callId: 'call-fin-plain', step: 2 })
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out }), /no \*current\* stage checkpoint/)
  })

  it('does not accept a staged finalize whose receipt names another directory', async () => {
    const h = await harness()
    const session = h.session('session-stage-other-dir')
    const out = tempDir('boardwise-stage-other-')
    const elsewhere = tempDir('boardwise-stage-elsewhere-')
    dive(session, out, { callId: 'call-dive-other', step: 1 })
    finalize(session, out, { callId: 'call-fin-other', step: 2, stage: 'initial', receiptDir: elsewhere })
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out }), /no \*current\* stage checkpoint/)
  })

  it('does not accept a checkpoint whose recorded receipt was replaced by another call', async () => {
    const h = await harness()
    const session = h.session('session-stage-replaced')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-replaced', step: 1 })
    finalize(session, out, { callId: 'call-fin-stage', step: 2, stage: 'initial' })
    // The same directory is finalized again without a stage: its receipt now
    // belongs to another call, so the staged checkpoint is stale.
    finalize(session, out, { callId: 'call-fin-plain-2', step: 3 })
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out }), /no \*current\* stage checkpoint/)
  })

  it('unlocks on a matching initial checkpoint and on a matching partial one', async () => {
    for (const stage of ['initial', 'partial'] as const) {
      const h = await harness()
      const session = h.session(`session-stage-${stage}`)
      const out = tempDir(`boardwise-stage-${stage}-`)
      dive(session, out, { callId: `call-dive-${stage}`, step: 1 })
      expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out }), /no \*current\* stage checkpoint/)
      finalize(session, out, { callId: `call-fin-${stage}`, step: 2, stage })
      expectAllowed(await decide(h.chain, session, 'boardwise_checkup', { out }))
      expectAllowed(await decide(h.chain, session, 'boardwise_review_evidence', { out }))
    }
  })
})

describe('541R3 budgets run from the current checkpoint', () => {
  it('allows just under the wall-clock limit and refuses at it', async () => {
    const h = await harness()
    const session = h.session('session-stage-clock')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-clock', step: 1 })
    finalize(session, out, { callId: 'call-fin-clock', step: 2, stage: 'initial' })
    const checkpointAt = h.stageState(session)?.batches[directoryKeyOf(out)]?.checkpoints.at(-1)?.time
    expect(typeof checkpointAt).toBe('number')

    const justUnder = await decide(h.gate(() => (checkpointAt as number) + REVIEW_STAGE_TIME_LIMIT_MS - 1), session, 'boardwise_checkup', { out })
    expectAllowed(justUnder)
    const atLimit = await decide(h.gate(() => (checkpointAt as number) + REVIEW_STAGE_TIME_LIMIT_MS), session, 'boardwise_checkup', { out })
    expectDenied(atLimit, /minute\(s\) old/)
    // One millisecond past the limit is still a refusal, never a pass.
    expectDenied(
      await decide(h.gate(() => (checkpointAt as number) + REVIEW_STAGE_TIME_LIMIT_MS + 1), session, 'boardwise_checkup', { out }),
      /minute\(s\) old/,
    )
    // The finishing tools are never refused by a budget.
    expectAllowed(await decide(h.gate(() => (checkpointAt as number) + REVIEW_STAGE_TIME_LIMIT_MS * 4), session, 'boardwise_review_finalize', { out }))
  })

  it('allows just under the model-step limit and refuses at it', async () => {
    const h = await harness()
    const session = h.session('session-stage-steps')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-steps', step: 5 })
    finalize(session, out, { callId: 'call-fin-steps', step: 6, stage: 'partial' })
    const at = h.stageState(session)?.batches[directoryKeyOf(out)]?.checkpoints.at(-1)?.step
    expect(at).toBe(6)

    otherCall(session, 6 + REVIEW_STAGE_STEP_LIMIT - 1)
    expectAllowed(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }))
    otherCall(session, 6 + REVIEW_STAGE_STEP_LIMIT)
    expectDenied(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }), /model steps behind/)
  })

  it('measures the step budget from the deepest committed model step, not from tool-call counts', async () => {
    const h = await harness()
    const session = h.session('session-stage-stepclock')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-clock2', step: 1 })
    finalize(session, out, { callId: 'call-fin-clock2', step: 2, stage: 'initial' })
    // Ten unmanaged calls inside the SAME step must not spend the budget…
    for (let index = 0; index < 10; index += 1) otherCall(session, 2)
    expectAllowed(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }))
    // … while one model step advances it by one.
    otherCall(session, 3)
    expect(h.stageState(session)?.lastStep).toBe(3)
    expectAllowed(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }))
  })

  it('opens a new budget segment on a newer checkpoint and never on the old receipt', async () => {
    const h = await harness()
    const session = h.session('session-stage-segment')
    const out = tempDir()
    dive(session, out, { callId: 'call-dive-seg', step: 1 })
    finalize(session, out, { callId: 'call-fin-seg-1', step: 2, stage: 'initial' })
    otherCall(session, 2 + REVIEW_STAGE_STEP_LIMIT)
    expectDenied(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }), /model steps behind/)

    // A newer staged finalize starts the next segment…
    finalize(session, out, { callId: 'call-fin-seg-2', step: 70, stage: 'partial' })
    expectAllowed(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }))
    otherCall(session, 70 + REVIEW_STAGE_STEP_LIMIT)
    expectDenied(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }), /model steps behind/)

    // … and the *old* checkpoint alone cannot reset anything: a further staged
    // finalize that records nothing leaves the stale one as the baseline.
    finalize(session, out, { callId: 'call-fin-seg-3', step: 140, stage: 'partial', record: false })
    expectDenied(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }), /no \*current\* stage checkpoint/)
  })
})

describe('541R4 an errored tool/result books nothing', () => {
  it('does not let a refused managed call open a second batch or a second dive', async () => {
    const h = await harness()
    const session = h.session('session-stage-error-refused')
    const a = tempDir('boardwise-stage-err-a-')
    const b = tempDir('boardwise-stage-err-b-')
    dive(session, a, { callId: 'call-dive-err-a', step: 1 })
    // The real DSH 0.2.2-rc.3 shape of a pre-execute refusal: the host booked
    // the call, the gate denied it, and the host still answered it with a
    // `tool/result` carrying `isError: true`.
    call(session, { callId: 'call-refused-err', name: 'boardwise_review_evidence', args: { out: a }, step: 2 })
    result(session, { callId: 'call-refused-err', step: 2, isError: true })

    const state = h.stageState(session)
    expect(Object.keys(state?.batches ?? {})).toEqual([directoryKeyOf(a)])
    expect(state?.batches[directoryKeyOf(a)]?.diveCount).toBe(1)
    expect(state?.pending).toEqual({})
    // The error result only moved the step clock.
    expect(state?.lastStep).toBe(2)

    // … and the refusal for another directory still reports one dive, not two.
    const refused = await decide(h.chain, session, 'boardwise_checkup', { out: b })
    expectDenied(refused, /no \*current\* stage checkpoint/)
    const reason = refused.decision.kind === 'deny' ? refused.decision.reason : ''
    expect(reason).toContain(`${JSON.stringify(a)} has 1 completed deep dive(s)`)
    expect(reason).not.toContain('2 completed deep dive(s)')
    // B was never created by the refused call.
    expect(Object.keys(h.stageState(session)?.batches ?? {})).toEqual([directoryKeyOf(a)])
  })

  it('does not let an errored staged finalize start a checkpoint or reset the budget', async () => {
    const h = await harness()
    const session = h.session('session-stage-error-finalize')
    const out = tempDir('boardwise-stage-err-fin-')
    dive(session, out, { callId: 'call-dive-err-fin', step: 1 })
    finalize(session, out, { callId: 'call-fin-err-c1', step: 2, stage: 'initial' })
    otherCall(session, 2 + REVIEW_STAGE_STEP_LIMIT)
    expectDenied(await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out }), /model steps behind/)

    // A staged finalize that fails at the CLI writes no receipt, and its
    // `isError: true` result must not become a checkpoint either: the old
    // receipt stays the baseline, so this error cannot reset the segment.
    const failedAt = 2 + REVIEW_STAGE_STEP_LIMIT + 18
    call(session, {
      callId: 'call-fin-err-failed',
      name: REVIEW_FINALIZE_TOOL,
      args: { out, stage: 'partial' },
      step: failedAt,
    })
    result(session, { callId: 'call-fin-err-failed', step: failedAt, isError: true })

    const batch = h.stageState(session)?.batches[directoryKeyOf(out)]
    expect(batch?.checkpoints.length).toBe(1)
    expect(batch?.checkpoints.at(-1)?.callId).toBe('call-fin-err-c1')
    expect(batch?.diveCount).toBe(1)
    expect(h.stageState(session)?.pending).toEqual({})
    expect(h.stageState(session)?.lastStep).toBe(failedAt)

    const stillDenied = await decide(h.gate(ALWAYS_NOW), session, 'boardwise_checkup', { out })
    expectDenied(stillDenied, /model steps behind/)
    const reason = stillDenied.decision.kind === 'deny' ? stillDenied.decision.reason : ''
    // Measured from the surviving checkpoint, not from the errored finalize.
    expect(reason).toContain(`${failedAt - 2} model steps behind`)
  })

  it('still books a completed exit 3 result and a legacy result without isError', async () => {
    const h = await harness()
    const session = h.session('session-stage-error-legacy')
    const protocol = tempDir('boardwise-stage-err-exit-')
    const legacy = tempDir('boardwise-stage-err-legacy-')
    // A boardwise checkup answering protocol-level exit 3 is a completed result:
    // DSH marks it `isError: false`, so it is a dive like any other.
    call(session, { callId: 'call-dive-exit3', name: 'boardwise_checkup', args: { out: protocol }, step: 1 })
    result(session, { callId: 'call-dive-exit3', step: 1, isError: false })
    // An older log recorded its result message with no `isError` field at all.
    call(session, { callId: 'call-dive-legacy', name: 'boardwise_review_evidence', args: { out: legacy }, step: 2 })
    legacyResult(session, { callId: 'call-dive-legacy', step: 2 })

    const state = h.stageState(session)
    expect(state?.batches[directoryKeyOf(protocol)]?.diveCount).toBe(1)
    expect(state?.batches[directoryKeyOf(legacy)]?.diveCount).toBe(1)
    expect(state?.pending).toEqual({})
    expectDenied(await decide(h.chain, session, 'boardwise_checkup', { out: protocol }), /no \*current\* stage checkpoint/)
  })

  it('clears the pending call on an error, so a repeated result books nothing twice', async () => {
    const h = await harness()
    const session = h.session('session-stage-error-repeat')
    const a = tempDir('boardwise-stage-err-repeat-')
    call(session, { callId: 'call-dive-err-repeat', name: 'boardwise_checkup', args: { out: a }, step: 1 })
    result(session, { callId: 'call-dive-err-repeat', step: 1, isError: true })
    expect(h.stageState(session)?.pending).toEqual({})
    expect(h.stageState(session)?.batches).toEqual({})
    // A later non-error result for the same callId finds no pending call: the
    // errored call was settled, not queued for a second booking.
    result(session, { callId: 'call-dive-err-repeat', step: 1 })
    expect(h.stageState(session)?.batches).toEqual({})

    // The same holds for a completed dive: a repeated result adds no dive.
    dive(session, a, { callId: 'call-dive-ok-repeat', step: 2 })
    expect(h.stageState(session)?.batches[directoryKeyOf(a)]?.diveCount).toBe(1)
    result(session, { callId: 'call-dive-ok-repeat', step: 2 })
    expect(h.stageState(session)?.batches[directoryKeyOf(a)]?.diveCount).toBe(1)
  })
})

describe('541R3 fail closed', () => {
  it('refuses a managed dive with no Session at all', async () => {
    const h = await harness()
    expectDenied(
      await decide(h.chain, undefined, 'boardwise_checkup', { out: tempDir() }),
      /no current Session/,
    )
  })

  it('refuses when the projection state cannot be read, and keeps ordinary tools free', async () => {
    const broken = createReviewStageGate({
      receipts: { stateOf: () => undefined },
      stage: { stateOf: () => undefined },
    })
    const h = await harness()
    const session = h.session('session-stage-broken')
    expectDenied(await decide(broken, session, 'boardwise_checkup', { out: tempDir() }), /unavailable or unreadable/)
    // A tool outside the managed pair is untouched even then.
    expectAllowed(await decide(broken, session, 'boardwise_arch', { file: 'x.epro2' }))
    expectAllowed(await decide(broken, session, 'boardwise_doctor', {}))
  })

  it('refuses when a helper throws, without echoing the execution token', async () => {
    const stage: ReviewStageReader = {
      stateOf: () => {
        throw new Error('the projection exploded')
      },
    }
    const gate = createReviewStageGate({ receipts: { stateOf: () => undefined }, stage })
    const h = await harness()
    const session = h.session('session-stage-throws')
    expectDenied(await decide(gate, session, 'boardwise_review_evidence', { out: tempDir() }), /could not be verified/)
  })
})

describe('541R3 finalize stage argument', () => {
  it('appends --strict-partial only for a staged call and echoes the stage', async () => {
    const h = await harness()
    const tool = h.tools.get(REVIEW_FINALIZE_TOOL)
    expect(tool).toBeDefined()
    expect(Object.keys(tool?.parameters ?? {})).toEqual(['out', 'stage'])
    const out = tempDir()
    writeFileSync(
      join(out, 'finalize.json'),
      JSON.stringify(RECEIPT),
      'utf8',
    )
    const spawnMock = installSpawn(child => child.finish(0))
    const session = h.session('session-stage-argv')

    const staged = (await tool?.execute({ out, stage: 'partial' }, {
      signal: new AbortController().signal,
      agent: { session },
      callId: 'call-finalize-staged',
    })) as { stage?: string; argv?: unknown }
    expect(spawnedCommand(spawnMock).slice(1)).toEqual([
      'review', 'finalize', '--out', out, '--strict-partial',
    ])
    expect(staged.stage).toBe('partial')

    const plain = (await tool?.execute({ out }, {
      signal: new AbortController().signal,
      agent: { session },
      callId: 'call-finalize-plain',
    })) as { stage?: string }
    // The default call is the old call: no flag, and no `stage` field at all.
    expect(spawnedCommand(spawnMock).slice(1)).toEqual(['review', 'finalize', '--out', out])
    expect(plain.stage).toBeUndefined()

    // An unknown stage never reaches a child process.
    await expect(
      tool?.execute({ out, stage: 'final' }, {
        signal: new AbortController().signal,
        agent: { session },
        callId: 'call-finalize-bad',
      }),
    ).rejects.toThrow(/not one of/)
    expect(REVIEW_STAGE_CHECKPOINT_HISTORY).toBe(8)
  })
})
