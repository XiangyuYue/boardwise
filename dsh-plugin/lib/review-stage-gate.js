/**
 * 541R3: the review **stage checkpoint** gate.
 *
 * R1/R2/R4 made "finalize this delivery" a hard gate; R3 still left "deliver the
 * first checkpoint before digging deeper, and stop digging when the batch budget
 * is spent" to the model's conscience. This module turns both into a
 * `tools/pre-execute` refusal on exactly two managed deep-dive tools
 * (`boardwise_checkup`, `boardwise_review_evidence`):
 *
 * 1. **A batch is a review directory.** `out` is resolved and folded exactly the
 *    way `review-finalize.ts` keys its receipts (`resolve` + `directoryKeyOf`),
 *    so the same directory spelled relatively, absolutely, with a trailing
 *    separator or in another case is one batch. A managed checkup without an
 *    explicit `out` is refused up front: a temp directory can never be bound to
 *    a checkpoint.
 * 2. **A batch starts at its first *completed* deep dive.** Only a successful
 *    matching `tool/result` books a dive. A refused attempt cannot open a batch
 *    (or switch one to another `out`): DSH 0.2.2-rc.3 answers a pre-execute
 *    denial with a `tool/result` whose `message.isError` is `true` (541R4), so
 *    the fold settles that pending call without booking anything. A missing
 *    `isError` is a legacy success. A protocol-level exit 1/3 is still a
 *    completed review and counts.
 * 3. **The next deep dive in a batch needs a checkpoint.** The checkpoint is
 *    the *Session* pair, never a file: the `boardwiseReviewFinalized` receipt
 *    recorded by 537D3a (its `reviewDir` folds to this batch's key) plus a
 *    `boardwise_review_finalize` call that carried `stage: initial|partial`, and
 *    the two must name the same `callId`. A hand-written `finalize.json`, a
 *    plain finalize without a stage, a receipt from another directory and a
 *    stale receipt are all "no checkpoint". The finishing tools
 *    (`boardwise_review_read`, `boardwise_review_finalize`, `boardwise_doctor`)
 *    always pass through — a gate that also blocked the way out would deadlock.
 * 4. **The budget runs from the current checkpoint** (`REVIEW_STAGE_TIME_LIMIT_MS`
 *    of the injected clock, `REVIEW_STAGE_STEP_LIMIT` model steps of the
 *    Session's committed `tool/call` steps), `>=` not `>`. A *newer* matching
 *    checkpoint starts the next segment; an old receipt does not reset anything,
 *    because the baseline is measured from the checkpoint itself, not from the
 *    last refusal.
 * 5. **Everything unprovable fails closed**: no Session, no projection state, an
 *    unreadable state, a missing model step, or a helper exception denies the
 *    managed call. Ordinary tools, draw tools, `boardwise_bridge` and the
 *    finishing tools are never touched, and no denial reason ever echoes the
 *    execution token.
 *
 * The projection is host-only (no `wire`): the fold records what the Session
 * itself committed, and nothing here is ever sent to a client or written to a
 * file the model could forge.
 *
 * @module
 */
import { resolve } from 'node:path';
import { z } from 'zod';
import { REVIEW_FINALIZE_TOOL, directoryKeyOf, hasPromiseFace, } from './review-finalize.js';
import { text } from './transport.js';
/** The two managed deep-dive / recompute entries. Nothing else is inspected. */
export const REVIEW_STAGE_DEEP_DIVE_TOOLS = ['boardwise_checkup', 'boardwise_review_evidence'];
/** The finishing entries: always `next()`, so the model can always get out. */
export const REVIEW_STAGE_FINISHING_TOOLS = [
    'boardwise_review_read',
    REVIEW_FINALIZE_TOOL,
    'boardwise_doctor',
];
/** The cordis waterfall the gate is mounted on. */
export const REVIEW_STAGE_EVENT = 'tools/pre-execute';
/** The host-only projection this module registers. */
export const REVIEW_STAGE_PROJECTION_KEY = 'boardwiseReviewStage';
/** Bumped only when the serialized state or its fold changes. */
export const REVIEW_STAGE_STATE_VERSION = 1;
/** One batch's wall-clock budget: 30 minutes from its current checkpoint. */
export const REVIEW_STAGE_TIME_LIMIT_MS = 30 * 60 * 1000;
/** One batch's model-step budget: 60 steps from its current checkpoint. */
export const REVIEW_STAGE_STEP_LIMIT = 60;
/** How many checkpoints one batch keeps (the last one is the baseline). */
export const REVIEW_STAGE_CHECKPOINT_HISTORY = 8;
/** How many `tool/call`s may wait for their result before the oldest is dropped. */
export const REVIEW_STAGE_PENDING_LIMIT = 32;
/** The two stages a checkpoint may be signed under. Neither is a board verdict. */
export const REVIEW_STAGE_KINDS = ['initial', 'partial'];
const stampSchema = z.object({
    callId: z.string().min(1),
    time: z.number().int().nonnegative(),
    step: z.number().int().nonnegative(),
});
const checkpointSchema = stampSchema.extend({
    out: z.string().min(1),
    outKey: z.string().min(1),
    stage: z.enum(REVIEW_STAGE_KINDS),
});
const batchSchema = z.object({
    outKey: z.string().min(1),
    out: z.string().min(1),
    diveCount: z.number().int().nonnegative(),
    firstDive: stampSchema,
    lastDive: stampSchema,
    checkpoints: z.array(checkpointSchema),
});
const pendingSchema = z.object({
    name: z.string().min(1),
    out: z.string().nullable(),
    stage: z.enum(REVIEW_STAGE_KINDS).nullable(),
    step: z.number().int().nonnegative(),
    time: z.number().int().nonnegative(),
});
const stageStateSchema = z.object({
    version: z.literal(REVIEW_STAGE_STATE_VERSION),
    lastStep: z.number().int().nonnegative().nullable(),
    batches: z.record(z.string(), batchSchema),
    pending: z.record(z.string(), pendingSchema),
});
/**
 * Register the host-only stage projection.
 *
 * As in `registerReviewFinalize`, 0.2.1's `register` answers a then-only
 * awaitable **disposer** and 0.2.2's answers a full promise of a ready handle;
 * only the full promise face is awaited (awaiting the disposer would unregister
 * the unit we just registered).
 */
export function registerReviewStageProjection(ctx) {
    const projections = ctx.sessionProjections;
    if (projections === undefined)
        return undefined;
    const registered = projections.register({
        key: REVIEW_STAGE_PROJECTION_KEY,
        stateVersion: REVIEW_STAGE_STATE_VERSION,
        stateSchema: stageStateSchema,
        init: () => initialState(),
        apply: (state, event) => {
            const parsed = stageStateSchema.safeParse(state);
            // Fail closed: a state we cannot read is a state we cannot extend, and a
            // broken fold must not take the Session (or the log) down with it.
            if (!parsed.success)
                return state;
            return fold(parsed.data, event);
        },
    });
    if (hasPromiseFace(registered)) {
        return Promise.resolve(registered).then(handle => handleReader(handle));
    }
    return registryReader(projections);
}
/** The empty state: no batch has been seen in this Session. */
function initialState() {
    return { version: REVIEW_STAGE_STATE_VERSION, lastStep: null, batches: {}, pending: {} };
}
/**
 * Is this registration result a promise, or 0.2.1's awaitable **disposer**?
 *
 * Both are callable and answer `then`; only a complete promise face
 * (`then` + `catch` + `finally`) may be awaited — awaiting the disposer disposes
 * the registration. The recipe lives in `review-finalize.ts` (one definition for
 * both registrations) and is re-exported here so a caller of this module does
 * not have to know that.
 */
export { hasPromiseFace } from './review-finalize.js';
/** The 0.2.2 read face over a ready handle. */
function handleReader(handle) {
    if (handle === null || typeof handle !== 'object')
        return undefined;
    const stateOf = handle.stateOf;
    if (typeof stateOf !== 'function')
        return undefined;
    const read = stateOf.bind(handle);
    return { stateOf: session => read(session) };
}
/** The 0.2.1 read face: the registry's own `stateOf(session, key)`. */
function registryReader(projections) {
    return {
        stateOf: session => projections.stateOf(session, REVIEW_STAGE_PROJECTION_KEY),
    };
}
/* --------------------------------------------------------------------- fold */
function isRecord(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
}
/** `text()` of a parsed argument object's `out`, or null when absent/blank. */
function callOut(args) {
    if (!isRecord(args))
        return null;
    const out = text(args['out']);
    return out === '' ? null : out;
}
/** The `stage` of a parsed argument object, or null when it is absent/unknown. */
function callStage(args) {
    if (!isRecord(args))
        return null;
    const stage = args['stage'];
    return stage === 'initial' || stage === 'partial' ? stage : null;
}
function isDeepDive(name) {
    return REVIEW_STAGE_DEEP_DIVE_TOOLS.includes(name);
}
/** One `tool/call`: remember the managed ones, and move the step clock. */
function foldCall(state, callId, step, time, name, rawArguments) {
    const lastStep = state.lastStep === null ? step : Math.max(state.lastStep, step);
    if (!isDeepDive(name) && name !== REVIEW_FINALIZE_TOOL) {
        return lastStep === state.lastStep ? state : { ...state, lastStep };
    }
    let args;
    try {
        args = JSON.parse(rawArguments);
    }
    catch {
        // A call whose arguments are not JSON cannot be attributed to an `out`; the
        // result still books nothing, which leaves the batch history untouched.
        args = null;
    }
    const out = callOut(args);
    const pending = {
        ...state.pending,
        [callId]: {
            name,
            out: out === null ? null : resolve(out),
            stage: callStage(args),
            step,
            time,
        },
    };
    const callIds = Object.keys(pending);
    for (const stale of callIds.slice(0, Math.max(0, callIds.length - REVIEW_STAGE_PENDING_LIMIT))) {
        delete pending[stale];
    }
    return { ...state, lastStep, pending };
}
/** One `tool/result`: book the completed dive or checkpoint it answers. */
function foldResult(state, callId, step, time, failed) {
    const lastStep = state.lastStep === null ? step : Math.max(state.lastStep, step);
    const booked = state.pending[callId];
    if (booked === undefined) {
        return lastStep === state.lastStep ? state : { ...state, lastStep };
    }
    const pending = { ...state.pending };
    delete pending[callId];
    // 541R4: a managed call the gate refused is still answered by the host with a
    // `tool/result` carrying `message.isError: true`. That result advances the
    // step clock and settles the pending call, but it is neither a completed deep
    // dive nor a delivery, so it books no dive and no checkpoint.
    if (failed)
        return { ...state, lastStep, pending };
    // A dive or checkpoint that cannot name its directory cannot be bound to a
    // batch, so it books nothing: the gate refuses such calls up front, and a
    // legacy `tool/call` from before this gate must not silently unlock a batch.
    if (booked.out === null)
        return { ...state, lastStep, pending };
    const out = booked.out;
    const outKey = directoryKeyOf(out);
    const existing = state.batches[outKey];
    const stamp = { callId, time, step };
    if (isDeepDive(booked.name)) {
        const batch = existing === undefined
            ? {
                outKey,
                out,
                diveCount: 1,
                firstDive: stamp,
                lastDive: stamp,
                checkpoints: [],
            }
            : { ...existing, out, diveCount: existing.diveCount + 1, lastDive: stamp };
        return { ...state, lastStep, pending, batches: { ...state.batches, [outKey]: batch } };
    }
    // `boardwise_review_finalize` completed. Only a staged call is a checkpoint;
    // the Session receipt that proves it was recorded is read by the gate itself,
    // never by this fold (the two are matched on `callId`).
    if (booked.stage === null)
        return { ...state, lastStep, pending };
    const base = existing ?? { outKey, out, diveCount: 0, firstDive: stamp, lastDive: stamp, checkpoints: [] };
    const checkpoints = [
        ...base.checkpoints,
        { ...stamp, out, outKey, stage: booked.stage },
    ].slice(-REVIEW_STAGE_CHECKPOINT_HISTORY);
    return {
        ...state,
        lastStep,
        pending,
        batches: { ...state.batches, [outKey]: { ...base, out, checkpoints } },
    };
}
/** The pure transition: only `tool/call` and `tool/result` matter here. */
function fold(state, event) {
    if (event.type === 'tool/call') {
        const data = event.data;
        return foldCall(state, String(data.callId), data.step, event.time, data.name, data.arguments);
    }
    if (event.type === 'tool/result') {
        const data = event.data;
        // `isError` is optional on the message: an older Session log without it
        // is a success, exactly as before this rule existed.
        return foldResult(state, String(data.message.toolCallId), data.step, event.time, data.message.isError === true);
    }
    return state;
}
/* ---------------------------------------------------------------------- gate */
function deny(reason) {
    return { kind: 'deny', reason };
}
/**
 * Mount the gate on the root context: one `tools/pre-execute` listener that
 * composes with 537D3b's `present` gate (the registry waterfalls both; this is
 * not a replacement).
 */
export function mountReviewStageGate(ctx, services) {
    // A partial mount (a light fake context without an event bus) gets no gate
    // rather than a gate nothing can call — the same rule the delivery gate
    // applies to its missing services.
    if (typeof ctx.on !== 'function')
        return undefined;
    return ctx.on(REVIEW_STAGE_EVENT, createReviewStageGate(services));
}
/**
 * Build the listener itself. Kept separate from registration so a test (or the
 * main agent's independent verification) can drive it directly.
 */
export function createReviewStageGate(services) {
    return async (exec, next) => {
        // Only the two managed deep-dive entries are inspected: no projection read,
        // no path resolution and no argv for anything else — including every
        // finishing tool, drawn tools and `boardwise_bridge`.
        if (!isDeepDive(exec.name))
            return next();
        try {
            return await decide(services, exec, next);
        }
        catch (error) {
            // Fail closed, including helper exceptions. `exec.token` is deliberately
            // never interpolated here (or anywhere else in this module).
            const message = error instanceof Error ? error.message : String(error);
            return deny(`${exec.name}: the review stage checkpoint could not be verified (${message}); ` +
                'refusing the next deep dive until a staged finalize receipt is proven.');
        }
    };
}
/** The state machine of §3, one call at a time. */
async function decide(services, exec, next) {
    const args = exec.arguments;
    const out = callOut(args);
    if (out === null) {
        return deny(`${exec.name}: \`out\` must be given explicitly in a managed review workflow. A temporary ` +
            'or default directory cannot be bound to a stage checkpoint, so the next deep dive would ' +
            'be unaccountable. Pass the same `out` directory the review is delivered in.');
    }
    const outKey = directoryKeyOf(resolve(out));
    const session = exec.agent?.session;
    if (session === undefined) {
        return deny(`${exec.name}: this call has no current Session, so the deep-dive batch and its checkpoint ` +
            'cannot be proven from Session events. Refusing the managed deep dive.');
    }
    const parsed = stageStateSchema.safeParse(services.stage.stateOf(session));
    if (!parsed.success) {
        return deny(`${exec.name}: the Session's review-stage projection is unavailable or unreadable ` +
            `(${parsed.error.issues[0]?.message ?? 'no state'}), so this batch has no provable ` +
            'checkpoint history. Refusing the next deep dive.');
    }
    const state = parsed.data;
    // §3.2: a checkpoint that is still owed for **any** batch blocks every
    // managed deep dive — in that directory and in every other one. Switching
    // `out` starts a batch only once nothing is owed (see §3.3 below), so naming
    // a fresh directory is never a way around an undelivered checkpoint.
    const owed = firstOwedCheckpoint(services, session, state);
    if (owed !== null) {
        return deny(`${exec.name}: the batch ${JSON.stringify(owed.out)} has ${owed.diveCount} completed deep dive(s) ` +
            'and no *current* stage checkpoint, so no next deep dive is allowed — not in that directory ' +
            'and not in another one either: switching `out` does not deliver anything. Deliver that batch ' +
            `first: call ${REVIEW_FINALIZE_TOOL} with stage=initial (or stage=partial) and ` +
            `out=${JSON.stringify(owed.out)}; a hand-written finalize.json, a plain finalize without a ` +
            'stage, a receipt for another directory and a receipt replaced by a later finalize are all ' +
            'refused. The finishing tools (review_read / review_finalize / doctor) stay available.');
    }
    const batch = state.batches[outKey];
    // §3.1 / §3.3: with nothing owed, the first dive of this directory — or the
    // first dive of a fresh directory — starts an independent batch.
    if (batch === undefined || batch.diveCount === 0)
        return next();
    const checkpoint = lastCheckpoint(batch);
    if (checkpoint === null) {
        // Unreachable after the scan above; kept as defence in depth so a future
        // change to that scan cannot silently turn "no checkpoint" into a pass.
        return deny(`${exec.name}: this batch (${JSON.stringify(batch.out)}) has ${batch.diveCount} completed deep ` +
            'dive(s) and no *current* stage checkpoint. Deliver it first with ' +
            `${REVIEW_FINALIZE_TOOL} stage=initial|partial and this out.`);
    }
    // §3.4 / §3.5: budgets measured from the current checkpoint, `>=` not `>`.
    const now = (services.now ?? Date.now)();
    const elapsed = now - checkpoint.time;
    if (elapsed >= REVIEW_STAGE_TIME_LIMIT_MS) {
        return deny(`${exec.name}: the current checkpoint for ${JSON.stringify(batch.out)} is ${minutes(elapsed)} ` +
            `old (limit ${minutes(REVIEW_STAGE_TIME_LIMIT_MS)}). Stop deepening this batch and deliver the ` +
            `current stage: call ${REVIEW_FINALIZE_TOOL} with stage=initial|partial and this out; its ` +
            'receipt starts the next budget segment.');
    }
    if (state.lastStep === null) {
        return deny(`${exec.name}: the Session records no committed model step for this batch, so the step budget ` +
            'cannot be proven. Refusing the next deep dive (finishing tools stay available).');
    }
    const steps = state.lastStep - checkpoint.step;
    if (steps >= REVIEW_STAGE_STEP_LIMIT) {
        return deny(`${exec.name}: the current checkpoint for ${JSON.stringify(batch.out)} is ${steps} model steps ` +
            `behind (limit ${REVIEW_STAGE_STEP_LIMIT}). Stop deepening this batch and deliver the current ` +
            `stage: call ${REVIEW_FINALIZE_TOOL} with stage=initial|partial and this out; its receipt ` +
            'starts the next budget segment.');
    }
    return next();
}
/**
 * The first batch that still owes a checkpoint, in the order the Session booked
 * them: it has completed deep dives and no **current** checkpoint (no staged
 * finalize, or one whose recorded Session receipt is missing, for another
 * directory, or replaced by a later finalize). §3.2: while one exists, every
 * managed deep dive is refused wherever it points.
 */
function firstOwedCheckpoint(services, session, state) {
    for (const [outKey, batch] of Object.entries(state.batches)) {
        if (batch.diveCount === 0)
            continue;
        const checkpoint = lastCheckpoint(batch);
        if (checkpoint === null)
            return { outKey, out: batch.out, diveCount: batch.diveCount };
        const entry = receiptOf(services, session, outKey);
        if (entry === null || entry.callId === null || entry.callId !== checkpoint.callId) {
            return { outKey, out: batch.out, diveCount: batch.diveCount };
        }
    }
    return null;
}
/** The baseline checkpoint of a batch (oldest first, so the last one wins). */
function lastCheckpoint(batch) {
    const last = batch.checkpoints[batch.checkpoints.length - 1];
    if (last === undefined)
        return null;
    if (last.outKey !== batch.outKey)
        return null;
    if (last.stage !== 'initial' && last.stage !== 'partial')
        return null;
    return last;
}
/** The recorded receipt for one directory key, or null when it is unusable. */
function receiptOf(services, session, outKey) {
    const state = services.receipts.stateOf(session);
    if (!isRecord(state))
        return null;
    const receipts = state['receipts'];
    if (!isRecord(receipts))
        return null;
    const entry = receipts[outKey];
    if (!isRecord(entry))
        return null;
    const reviewDir = entry['reviewDir'];
    const callId = entry['callId'];
    if (typeof reviewDir !== 'string' || reviewDir === '')
        return null;
    if (directoryKeyOf(resolve(reviewDir)) !== outKey)
        return null;
    return { reviewDir, callId: typeof callId === 'string' && callId !== '' ? callId : null };
}
function minutes(ms) {
    const value = Math.round((ms / 60_000) * 10) / 10;
    return `${value} minute(s)`;
}
