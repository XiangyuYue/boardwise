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
import { defineTool } from '@deepseek-ai/dsh-tools';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { TEXT_OUTPUT, executeCli, text, } from './transport.js';
import { ensureDirectory, requireExistingFile, requireExistingInput, transportDir, } from './tool-utils.js';
/** Thirty minutes: the ceiling task 555 allows a whole-board batch. */
const PARTS_HUNT_TIMEOUT_MS = 1_800_000;
/** The four files `parts hunt --out` is contracted to leave behind. */
const HUNT_ARTIFACTS = [
    'hunt-report.json',
    'hunt-plan.json',
    'hunt-report.md',
    'hunt-audit.jsonl',
];
/**
 * The design a hunt addresses: exactly one of `file` / `project` / `instance`.
 *
 * `project` and `instance` are the live route — there is no file to read, so
 * both spell `--live`, and the daemon (not this plugin) decides which window
 * the names select. Refused here, before anything is spawned: a hunt with no
 * input would classify nothing, and one with two inputs has no single answer.
 */
function requireDesign(argv, tool, args) {
    const file = text(args.file);
    const project = text(args.project);
    const instance = text(args.instance);
    const given = [file, project, instance].filter(value => value !== '');
    if (given.length !== 1) {
        throw new Error(`${tool}: exactly one of file, project or instance is required — a .epro2/.eprj3 export to read, ` +
            'or a live editor window by project name / window key (`--live`). ' +
            `Got ${given.length === 0 ? 'none' : String(given.length)}.`);
    }
    if (file !== '') {
        argv.push('--file', requireExistingFile(tool, file));
        return;
    }
    argv.push('--live');
    if (project !== '')
        argv.push('--project', project);
    else
        argv.push('--instance', instance);
}
/**
 * Write one returned list to this plugin's own transport file.
 *
 * The arrays are written as given: trimming, identity matching, the quote gate
 * and every refusal are Python's. An empty list hands over no file at all —
 * the CLI has nothing to apply, so the flag would only ask it to read `[]`.
 */
async function writeTransportList(tool, name, fileName, value, shape) {
    if (value === undefined || value === null)
        return '';
    if (!Array.isArray(value)) {
        throw new Error(`${tool}: ${name} must be an array (${shape}), got ${typeof value}`);
    }
    if (value.length === 0)
        return '';
    const path = join(await transportDir(tool), fileName);
    try {
        await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
    }
    catch (error) {
        throw new Error(`${tool}: cannot write the ${name} input ${path}: ${error.message}`);
    }
    return path;
}
/** Register the batch hunt between review finalize and the offline draw tools. */
export function registerPartsHunt(ctx) {
    ctx.tools.register(defineTool({
        name: 'boardwise_parts_hunt',
        description: 'Address every part of a board at once and carry a datasheet hunt through its three stages — ' +
            'the batch half of a datasheet checkup. Stage one classifies each part (a valid 立创 C-number is ' +
            'asked about by that number and nothing else; MPN-only parts become a search work order) and writes ' +
            'the leftovers to hunt-plan.json. Stage two hands hand-found URLs back as `answers` ' +
            '[{designator|lcsc|mpn, url}] and replays them through the same download/extract path. Stage three ' +
            'hands back what an AI or engineer read as `claims` [{designator|lcsc|mpn, facts, quotes}]: every ' +
            'quote must appear verbatim on the page it cites or the claim is rejected. ' +
            'Name the design exactly one way: `file` (an exported .epro2/.eprj3), or `project`/`instance` for ' +
            'the live editor (spelled `--live`; several connected windows need one of the two, the daemon will ' +
            'not guess). `out` is required and receives four artifacts: hunt-report.json, hunt-plan.json, ' +
            'hunt-report.md and hunt-audit.jsonl (one line per outbound call — the evidence that only a ' +
            'C-number or an MPN left the machine). `fromReport` points at a checkup report.json and restricts ' +
            'the hunt to its `needs_datasheet` designators; `offline` makes it classification and work order ' +
            'only, with not a single outbound call. ' +
            'Nothing here verifies a datasheet: landed facts stay `facts_verified: false` (喂 PDF ≠ 清闸), the ' +
            'shell never writes a shelf by default — only when `shelf` names an explicit path, and never a write ' +
            'to the user\'s global one. Long PDF text never comes back through this tool; read the ' +
            'artifacts. Exit 0 = report written, 2 = the input, the report or an answers file cannot be read.',
        parameters: {
            file: {
                type: 'string',
                description: 'The .epro2 / .eprj3 export to hunt (read-only). Exactly one design source.',
            },
            project: {
                type: 'string',
                description: 'Live route: the editor window to read, by project name or uuid (implies --live).',
            },
            instance: {
                type: 'string',
                description: 'Live route: the same choice by window key (`bridge status` prints them).',
            },
            out: {
                type: 'string',
                required: true,
                description: 'Directory for the four artifacts and the candidate sidecars (created if missing).',
            },
            fromReport: {
                type: 'string',
                description: 'A checkup report.json: hunt only its `needs_datasheet` designators, not the whole board. ' +
                    'Paths are read as given; a missing file is refused before the CLI runs.',
            },
            offline: {
                type: 'boolean',
                description: 'Classification and work order only — not a single outbound call.',
            },
            limit: {
                type: 'number',
                description: 'Only the first N parts after the report filter (default: all).',
            },
            cache: {
                type: 'string',
                description: 'Cross-board PDF cache directory (default: the boardwise home). Conflicts with noCache.',
            },
            noCache: {
                type: 'boolean',
                description: 'Keep this run\'s downloads inside `out`; the next run starts from nothing.',
            },
            shelf: {
                type: 'string',
                description: 'Write extracted facts into this parts.json as candidates. Omitted = no shelf is touched; ' +
                    'the global shelf is never written by this tool implicitly.',
            },
            answers: {
                type: 'array',
                description: 'Stage two: [{designator|lcsc|mpn, url}]. Written to a transport file and passed as --apply; ' +
                    'Python decides which parts it can match.',
            },
            claims: {
                type: 'array',
                description: 'Stage three: [{designator|lcsc|mpn, facts, quotes}]. Written to a transport file and passed as ' +
                    '--apply-facts; the verbatim-quote gate and every trust tier stay in Python.',
            },
        },
        output: TEXT_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_parts_hunt';
            const out = text(args.out);
            if (out === '')
                throw new Error(`${tool}: out is required (the directory the four hunt artifacts land in)`);
            const argv = ['parts', 'hunt'];
            requireDesign(argv, tool, args);
            const fromReport = text(args.fromReport);
            if (fromReport !== '') {
                argv.push('--from-report', requireExistingInput(tool, 'fromReport', fromReport, 'the checkup report.json whose needs_datasheet list selects the parts'));
            }
            if (args.offline === true)
                argv.push('--offline');
            const limit = typeof args.limit === 'number' && Number.isFinite(args.limit) ? Math.floor(args.limit) : 0;
            if (limit > 0)
                argv.push('--limit', String(limit));
            // `--cache` and `--no-cache` are opposite answers to the same question:
            // the CLI would pick one silently, so both together is refused here, with
            // no spawn and no half-written report.
            const cache = text(args.cache);
            const noCache = args.noCache === true;
            if (cache !== '' && noCache) {
                throw new Error(`${tool}: cache and noCache are mutually exclusive — ` +
                    'a reused cross-board cache and a run whose downloads stay inside `out` cannot both be asked for.');
            }
            if (cache !== '')
                argv.push('--cache', cache);
            if (noCache)
                argv.push('--no-cache');
            // No default: a batch run must never quietly edit a shelf. Only an
            // explicit path is forwarded.
            const shelf = text(args.shelf);
            if (shelf !== '')
                argv.push('--shelf', shelf);
            const answers = await writeTransportList(tool, 'answers', 'hunt-answers.json', args.answers, 'one {designator|lcsc|mpn, url} per part');
            if (answers !== '')
                argv.push('--apply', answers);
            const claims = await writeTransportList(tool, 'claims', 'hunt-claims.json', args.claims, 'one {designator|lcsc|mpn, facts, quotes} per part');
            if (claims !== '')
                argv.push('--apply-facts', claims);
            await ensureDirectory(tool, out);
            argv.push('--out', out);
            const artifacts = HUNT_ARTIFACTS.map(name => ({ label: name, path: join(out, name) }));
            return await executeCli(tool, argv, PARTS_HUNT_TIMEOUT_MS, exec, artifacts);
        },
        timeoutMs: PARTS_HUNT_TIMEOUT_MS,
    }));
}
