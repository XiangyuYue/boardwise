/**
 * boardwise tools for DeepSeek Harness: line-owned registration only (540B7).
 * Every judgement stays in the Python CLI; TypeScript owns argv and file transport.
 */

import type { Context } from '@deepseek-ai/cordis'
import { isPendingRegistration } from './review-finalize.ts'
import type { ReviewProjectionReader } from './review-finalize.ts'
import { registerDrawTools } from './draw-tools.ts'
import { registerPartsHunt } from './parts-hunt.ts'
import { registerReviewDelivery } from './review-delivery.ts'
import {
  hasPromiseFace,
  mountReviewStageGate,
  registerReviewStageProjection,
  type ReviewStageReader,
} from './review-stage-gate.ts'
import { registerReviewCheckup, registerReviewWorkflow } from './review-tools.ts'
import { registerSharedTools } from './shared-tools.ts'

/** Cordis plugin name; the row id in `cordis.patch.yml` is `tool-boardwise`. */
export const name = 'boardwise-dsh'
/**
 * Tools plus the host-only finalize/stage projections and the delivery and
 * stage gates' services.
 */
export const inject = ['tools', 'sessionProjections', 'fs', 'workingDirectory']

/**
 * Preserve the old eight-tool order, then append offline draw compile/lint.
 *
 * `register` is synchronous in 0.2.1 and awaitable in 0.2.2. Only an awaitable
 * registration makes this function return a promise: the tool order is the same
 * either way, but on 0.2.2 the tools and gates that read a projection — the draw
 * tools, 537D3b's `present` gate and 541R3's stage gate — are published only
 * after **both** projection handles are ready.
 */
export function apply(ctx: Context): void | Promise<void> {
  registerReviewCheckup(ctx)
  registerSharedTools(ctx)
  const finalizeRegistration = registerReviewWorkflow(ctx)
  const stageRegistration = registerReviewStageProjection(ctx)

  if (!isPendingRegistration(finalizeRegistration) && !hasPromiseFace(stageRegistration)) {
    publish(ctx, finalizeRegistration, stageRegistration)
    return
  }
  // Awaited, not fired and forgotten: the caller (the Cordis loader) must see a
  // rejected registration as a failed activation, and everything that reads a
  // projection must come after the handles are ready. Only a full promise face
  // is awaited — 0.2.1's then-only disposer stays on the synchronous branch
  // (awaiting it would dispose the registration, see `hasPromiseFace`).
  return (async () => {
    const finalizeReader: ReviewProjectionReader | undefined = isPendingRegistration(finalizeRegistration)
      ? await finalizeRegistration
      : finalizeRegistration
    const stageReader: ReviewStageReader | undefined = hasPromiseFace(stageRegistration)
      ? await stageRegistration
      : stageRegistration
    publish(ctx, finalizeReader, stageReader)
  })()
}

/** Everything that reads a finalize or stage projection, published at once. */
function publish(
  ctx: Context,
  finalizeReader: ReviewProjectionReader | undefined,
  stageReader: ReviewStageReader | undefined,
): void {
  // 555: the batch datasheet hunt reads a design the way checkup does and
  // draws nothing, so it lands after the old eight tools and before draw.
  registerPartsHunt(ctx)
  registerDrawTools(ctx)
  registerReviewDelivery(ctx, finalizeReader)
  // The stage gate proves a checkpoint with **both** projections: a stage
  // checkpoint without the Session receipt it belongs to proves nothing, and the
  // receipt without a staged finalize proves nothing either. A partial mount
  // therefore gets no stage gate rather than a gate that cannot decide.
  if (finalizeReader === undefined || stageReader === undefined) return
  mountReviewStageGate(ctx, { receipts: finalizeReader, stage: stageReader })
}
