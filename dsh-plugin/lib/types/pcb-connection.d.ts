/**
 * `boardwise_pcb_connection`: the direct-only PCB copper probe, as argv and a
 * text result only.
 *
 * Tasks 559 / 559B put the whole question in the Python CLI: whether the
 * running editor handed back proof that two named pads share copper, and which
 * of the three verdicts that amounts to. This module owns two mechanical
 * things and nothing else: the two endpoints (which must be given) and the
 * three optional selectors of *which* editor window answers. It never rewrites
 * a verdict, never asks for `getEntireTrack`, and never adds a `--file`,
 * `--board`, `--live` or `--json`: the focused PCB **is** the board identity,
 * the JSON answer is stdout, and nothing here writes a design.
 */
import type { Context } from '@deepseek-ai/cordis';
/** Register the direct-only copper probe between parts hunt and the draw tools. */
export declare function registerPcbConnection(ctx: Context): void;
