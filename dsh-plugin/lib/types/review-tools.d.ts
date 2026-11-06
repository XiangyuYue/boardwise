/** Review-owned boardwise tools: no review judgement is reimplemented in TS. */
import type { Context } from '@deepseek-ai/cordis';
import { type ReviewProjectionRegistration } from './review-finalize.ts';
/** Keep checkup first, ahead of the shared tools, for old registration order. */
export declare function registerReviewCheckup(ctx: Context): void;
/** Register review-read/evidence/triage/finalize in their historical order. */
export declare function registerReviewWorkflow(ctx: Context): ReviewProjectionRegistration;
