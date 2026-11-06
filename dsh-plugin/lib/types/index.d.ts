/**
 * boardwise tools for DeepSeek Harness: line-owned registration only (540B7).
 * Every judgement stays in the Python CLI; TypeScript owns argv and file transport.
 */
import type { Context } from '@deepseek-ai/cordis';
/** Cordis plugin name; the row id in `cordis.patch.yml` is `tool-boardwise`. */
export declare const name = "boardwise-dsh";
/** Tools plus the host-only finalize projection and delivery gate services. */
export declare const inject: string[];
/**
 * Preserve the old eight-tool order, then append offline draw compile/lint.
 *
 * `register` is synchronous in 0.2.1 and awaitable in 0.2.2. Only the awaitable
 * shape makes this function return a promise: the tool order is the same either
 * way, but on 0.2.2 the tools that read the finalize projection — the draw tools
 * come after it, the delivery gate reads it — are published only after the
 * registration's handle is ready.
 */
export declare function apply(ctx: Context): void | Promise<void>;
