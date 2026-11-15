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
 * 2. **A batch starts at its first *completed* deep dive.** Only a matching
 *    `tool/result` books a dive — a `tool/call` the gate denied never produces a
 *    result, so a refused attempt cannot open a batch (or switch one to another
 *    `out`). A protocol-level exit 1/3 is still a completed review and counts.
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
import type { Context } from '@deepseek-ai/cordis';
import type { PreToolDecision, ToolExecution } from '@deepseek-ai/dsh-tools';
import type { Session } from '@deepseek-ai/dsh-session';
import { type ReviewProjectionReader } from './review-finalize.ts';
/** The two managed deep-dive / recompute entries. Nothing else is inspected. */
export declare const REVIEW_STAGE_DEEP_DIVE_TOOLS: readonly ['boardwise_checkup', 'boardwise_review_evidence'];
/** The finishing entries: always `next()`, so the model can always get out. */
export declare const REVIEW_STAGE_FINISHING_TOOLS: readonly ['boardwise_review_read', "boardwise_review_finalize", 'boardwise_doctor'];
/** The cordis waterfall the gate is mounted on. */
export declare const REVIEW_STAGE_EVENT = "tools/pre-execute";
/** The host-only projection this module registers. */
export declare const REVIEW_STAGE_PROJECTION_KEY = "boardwiseReviewStage";
/** Bumped only when the serialized state or its fold changes. */
export declare const REVIEW_STAGE_STATE_VERSION = 1;
/** One batch's wall-clock budget: 30 minutes from its current checkpoint. */
export declare const REVIEW_STAGE_TIME_LIMIT_MS: number;
/** One batch's model-step budget: 60 steps from its current checkpoint. */
export declare const REVIEW_STAGE_STEP_LIMIT = 60;
/** How many checkpoints one batch keeps (the last one is the baseline). */
export declare const REVIEW_STAGE_CHECKPOINT_HISTORY = 8;
/** How many `tool/call`s may wait for their result before the oldest is dropped. */
export declare const REVIEW_STAGE_PENDING_LIMIT = 32;
/** The two stages a checkpoint may be signed under. Neither is a board verdict. */
export declare const REVIEW_STAGE_KINDS: readonly ['initial', 'partial'];
export type ReviewStageKind = (typeof REVIEW_STAGE_KINDS)[number];
/** The model step and wall clock a projection entry was booked at. */
export interface ReviewStageStamp {
    readonly callId: string;
    /** Unix epoch milliseconds of the booking `tool/result` event. */
    readonly time: number;
    /** The model step of that event (never a tool-call count or a token count). */
    readonly step: number;
}
/** One signed stage delivery: a `finalize --strict-partial` that completed. */
export interface ReviewStageCheckpoint extends ReviewStageStamp {
    /** The absolute `out` as resolved from the call's arguments. */
    readonly out: string;
    /** `directoryKeyOf(resolve(out))` — the batch this checkpoint belongs to. */
    readonly outKey: string;
    readonly stage: ReviewStageKind;
}
/** One review directory's deep-dive history, aggregated so it never grows. */
export interface ReviewStageBatch {
    readonly outKey: string;
    readonly out: string;
    readonly diveCount: number;
    readonly firstDive: ReviewStageStamp;
    readonly lastDive: ReviewStageStamp;
    /** Oldest first; the last entry is the budget baseline. */
    readonly checkpoints: ReviewStageCheckpoint[];
}
/** A managed `tool/call` that has not produced its `tool/result` yet. */
export interface ReviewStagePendingCall {
    readonly name: string;
    readonly out: string | null;
    readonly stage: ReviewStageKind | null;
    readonly step: number;
    readonly time: number;
}
/** The complete host-only state: every batch this Session has worked in. */
export interface BoardwiseReviewStageState {
    readonly version: typeof REVIEW_STAGE_STATE_VERSION;
    /** The highest committed `tool/call` (or `tool/result`) model step, or null. */
    readonly lastStep: number | null;
    readonly batches: Record<string, ReviewStageBatch>;
    readonly pending: Record<string, ReviewStagePendingCall>;
}
declare module '@deepseek-ai/dsh-session-projection/types' {
    interface SessionProjectionStateMap {
        /** 541R3: host-only fold of the Session's managed deep dives and checkpoints. */
        boardwiseReviewStage: BoardwiseReviewStageState;
    }
}
/** The `tools/pre-execute` listener shape (the registry waterfall contract). */
export type ReviewStageListener = (exec: ToolExecution, next: () => Promise<PreToolDecision>) => Promise<PreToolDecision>;
/** The gate's read face over the stage projection. */
export interface ReviewStageReader {
    stateOf(session: Session): BoardwiseReviewStageState | undefined;
}
/** 0.2.1's synchronous reader, 0.2.2's pending registration, or a partial mount. */
export type ReviewStageProjectionRegistration = ReviewStageReader | Promise<ReviewStageReader | undefined> | undefined;
/** Everything the listener needs; `now` is injectable so tests own the clock. */
export interface ReviewStageServices {
    /** 537D3a's receipt projection: the only checkpoint authority. */
    readonly receipts: ReviewProjectionReader;
    readonly stage: ReviewStageReader;
    /** Wall clock in epoch milliseconds; defaults to `Date.now`. */
    readonly now?: () => number;
}
/**
 * Register the host-only stage projection.
 *
 * As in `registerReviewFinalize`, 0.2.1's `register` answers a then-only
 * awaitable **disposer** and 0.2.2's answers a full promise of a ready handle;
 * only the full promise face is awaited (awaiting the disposer would unregister
 * the unit we just registered).
 */
export declare function registerReviewStageProjection(ctx: Context): ReviewStageProjectionRegistration;
/**
 * Is this registration result a promise, or 0.2.1's awaitable **disposer**?
 *
 * Both are callable and answer `then`; only a complete promise face
 * (`then` + `catch` + `finally`) may be awaited — awaiting the disposer disposes
 * the registration. The recipe lives in `review-finalize.ts` (one definition for
 * both registrations) and is re-exported here so a caller of this module does
 * not have to know that.
 */
export { hasPromiseFace } from './review-finalize.ts';
/**
 * Mount the gate on the root context: one `tools/pre-execute` listener that
 * composes with 537D3b's `present` gate (the registry waterfalls both; this is
 * not a replacement).
 */
export declare function mountReviewStageGate(ctx: Context, services: ReviewStageServices): (() => boolean) | undefined;
/**
 * Build the listener itself. Kept separate from registration so a test (or the
 * main agent's independent verification) can drive it directly.
 */
export declare function createReviewStageGate(services: ReviewStageServices): ReviewStageListener;
