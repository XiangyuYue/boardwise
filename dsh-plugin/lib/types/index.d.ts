/**
 * boardwise tools for DeepSeek Harness: line-owned registration only (540B7).
 * Every judgement stays in the Python CLI; TypeScript owns argv and file transport.
 */
import type { Context } from '@deepseek-ai/cordis';
/** Cordis plugin name; the row id in `cordis.patch.yml` is `tool-boardwise`. */
export declare const name = "boardwise-dsh";
/**
 * Tools plus the host-only finalize/stage projections and the delivery and
 * stage gates' services.
 */
export declare const inject: string[];
/**
 * Preserve the old eight-tool order, then append offline draw compile/lint.
 *
 * `register` is synchronous in 0.2.1 and awaitable in 0.2.2. Only an awaitable
 * registration makes this function return a promise: the tool order is the same
 * either way, but on 0.2.2 the tools and gates that read a projection — the draw
 * tools, 537D3b's `present` gate and 541R3's stage gate — are published only
 * after **both** projection handles are ready.
 */
export declare function apply(ctx: Context): void | Promise<void>;
