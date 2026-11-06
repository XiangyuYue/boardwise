/**
 * boardwise tools for DeepSeek Harness: line-owned registration only (540B7).
 * Every judgement stays in the Python CLI; TypeScript owns argv and file transport.
 */
import { registerDrawTools } from './draw-tools.js';
import { isPendingRegistration } from './review-finalize.js';
import { registerReviewDelivery } from './review-delivery.js';
import { registerReviewCheckup, registerReviewWorkflow } from './review-tools.js';
import { registerSharedTools } from './shared-tools.js';
/** Cordis plugin name; the row id in `cordis.patch.yml` is `tool-boardwise`. */
export const name = 'boardwise-dsh';
/** Tools plus the host-only finalize projection and delivery gate services. */
export const inject = ['tools', 'sessionProjections', 'fs', 'workingDirectory'];
/**
 * Preserve the old eight-tool order, then append offline draw compile/lint.
 *
 * `register` is synchronous in 0.2.1 and awaitable in 0.2.2. Only the awaitable
 * shape makes this function return a promise: the tool order is the same either
 * way, but on 0.2.2 the tools that read the finalize projection — the draw tools
 * come after it, the delivery gate reads it — are published only after the
 * registration's handle is ready.
 */
export function apply(ctx) {
    registerReviewCheckup(ctx);
    registerSharedTools(ctx);
    const registration = registerReviewWorkflow(ctx);
    if (!isPendingRegistration(registration)) {
        registerDrawTools(ctx);
        registerReviewDelivery(ctx);
        return;
    }
    // Awaited, not fired and forgotten: the caller (the Cordis loader) must see a
    // rejected registration as a failed activation, and everything that reads the
    // projection must come after the handle is ready.
    return (async () => {
        const reader = await registration;
        registerDrawTools(ctx);
        registerReviewDelivery(ctx, reader);
    })();
}
