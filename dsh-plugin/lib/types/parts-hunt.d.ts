/**
 * `boardwise_parts_hunt`: the batch datasheet half of a checkup, as argv and
 * file transport only.
 *
 * Task 555 §3: every judgement — classification, download, extraction, the
 * quote gate, the three facts tiers, `facts_verified` — stays in the Python
 * CLI. This module owns three mechanical things and nothing else: which design
 * the hunt addresses (`--file`, or `--live` with `--project`/`--instance`),
 * where its four artifacts go (`--out`), and the two arrays an AI hands back
 * (written to this plugin's own temp files and passed as `--apply` /
 * `--apply-facts`). It never writes a shelf by default and never claims a
 * datasheet is verified: a landed PDF is still `facts_verified: false`.
 */
import type { Context } from '@deepseek-ai/cordis';
/** Register the batch hunt between review finalize and the offline draw tools. */
export declare function registerPartsHunt(ctx: Context): void;
