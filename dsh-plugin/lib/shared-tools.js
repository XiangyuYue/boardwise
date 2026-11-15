/** Shared transport/environment tools: thin CLI adapters only. */
import { defineTool } from '@deepseek-ai/dsh-tools';
import { dirname, join } from 'node:path';
import { TEXT_OUTPUT, executeCli, text, } from './transport.js';
import { ensureDirectory, requireExistingFile, requireJsonObject } from './tool-utils.js';
const ARCH_TIMEOUT_MS = 120_000;
const DOCTOR_TIMEOUT_MS = 60_000;
const BRIDGE_TIMEOUT_MS = 120_000;
/**
 * 541I: the token `bridge call --read-only` refuses with, as the CLI spells it
 * (537A). It is a **capability disclosure** — the action is outside the public
 * read-only interface — not a board finding, so it rides in front of the CLI's
 * own answer and changes neither that text nor its exit code.
 */
const READ_ONLY_VIOLATION = 'READ_ONLY_VIOLATION';
const READ_ONLY_TOOL_GAP = 'tool-gap: the requested bridge action is outside the public read-only interface; nothing was forwarded to the editor.\n' +
    'tool-gap: the managed reads are boardwise_checkup, boardwise_review_evidence and boardwise_review_read; ' +
    'each answers only the read it names, and none is claimed to replace this action.';
/**
 * 541I: prefix the tool-gap disclosure when the CLI refused the action.
 *
 * The refusal reaches here already formatted, with its own exit code and the
 * catalogue risk the CLI read from protocol — that text is passed through
 * verbatim. Only an outcome carrying the token gets the disclosure, so a
 * successful read and every other CLI error keep their exact spelling.
 */
function discloseReadOnlyGap(outcome) {
    return outcome.includes(READ_ONLY_VIOLATION) ? `${READ_ONLY_TOOL_GAP}\n${outcome}` : outcome;
}
/** Register arch/doctor/bridge between the two review registration phases. */
export function registerSharedTools(ctx) {
    ctx.tools.register(defineTool({
        name: 'boardwise_arch',
        description: 'Generate the architecture skeleton boardwise builds for one exported .epro2/.enet (task 044): power tree, ' +
            'analog chains, control chains, buses and design-intent slots, with every judgement a tool cannot make left ' +
            'as a TODO slot for the engineer to fill. Offline and deterministic — the same model yields byte-identical ' +
            'markdown. The skeleton is **generated and overwritten**; the answers belong in the paired `design-intent.md` ' +
            'beside `out` (created once as an all-TODO template, then read-only, 053 §2.2) and are merged back into the ' +
            'report`s architecture section. ' +
            'Without `out` the markdown comes back on stdout (long; it may be truncated); with `out` it is written to that ' +
            'file and the path is returned. Exit 0 = generated, 2 = the input cannot be used.',
        parameters: {
            file: {
                type: 'string',
                required: true,
                description: 'The .epro2 / .enet export to read (read-only).',
            },
            out: {
                type: 'string',
                description: 'Write the markdown here instead of stdout (parent directories are created).',
            },
        },
        output: TEXT_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_arch';
            const file = requireExistingFile(tool, text(args.file));
            const out = text(args.out);
            const argv = ['arch', file];
            const artifacts = [];
            if (out !== '') {
                await ensureDirectory(tool, dirname(out));
                argv.push('--out', out);
                artifacts.push({ label: 'architecture', path: out });
                // The CLI keeps the pair: the skeleton at `out`, the engineer's answers
                // in `design-intent.md` beside it.
                artifacts.push({ label: 'design-intent', path: join(dirname(out), 'design-intent.md') });
            }
            return await executeCli(tool, argv, ARCH_TIMEOUT_MS, exec, artifacts);
        },
        timeoutMs: ARCH_TIMEOUT_MS,
    }));
    ctx.tools.register(defineTool({
        name: 'boardwise_doctor',
        description: 'Diagnose the local boardwise installation in one run: the daemon answers ping, the editor extension is ' +
            'connected, the five methods the harness depends on exist, the running daemon and connector versions match ' +
            'this install, the editor is new enough, and the focused project can be read. ' +
            'project= / instance= name which editor window the online checks ask: as soon as several windows are ' +
            'connected the daemon refuses to guess, and those checks answer "not verified" instead of inventing an answer. ' +
            'Green exits 0; anything else exits 1 with one suggested fix per failing line. Read-only.',
        parameters: {
            project: {
                type: 'string',
                description: 'Editor window to ask, by project name or uuid.',
            },
            instance: {
                type: 'string',
                description: 'The same choice by window key (`bridge status` prints them); decides when both are given.',
            },
        },
        output: TEXT_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_doctor';
            const argv = ['doctor'];
            if (text(args.project) !== '')
                argv.push('--project', text(args.project));
            if (text(args.instance) !== '')
                argv.push('--instance', text(args.instance));
            return await executeCli(tool, argv, DOCTOR_TIMEOUT_MS, exec);
        },
        timeoutMs: DOCTOR_TIMEOUT_MS,
    }));
    ctx.tools.register(defineTool({
        name: 'boardwise_bridge',
        description: 'Escape hatch: call one action of the boardwise connector catalogue directly on the live editor, for probes ' +
            'and diagnosis that no higher-level tool covers (e.g. sys.probe, sys.identity, doc.list, sch.readback, ' +
            'export.render). `action` is the catalogue name and `params` a JSON object literal; project= / instance= route ' +
            'the call to one editor window when several are connected (without them the daemon answers WINDOW_UNSPECIFIED ' +
            'rather than guessing). Every call is made with `--read-only`, so the CLI refuses — before contacting the ' +
            'editor — any action whose catalogue risk is not `read` (doc.focus and every other write, create or dangerous ' +
            'tier, and unknown names). Designs are changed with the boardwise CLI under its own identity discipline, never ' +
            'through this tool. Daemon tokens are never printed.',
        parameters: {
            action: {
                type: 'string',
                required: true,
                description: 'Action name from the connector catalogue, e.g. "sys.probe" or "doc.list".',
            },
            params: {
                type: 'string',
                required: true,
                description: 'Action params as a JSON object literal, e.g. "{}" for no params. Passed to the CLI verbatim.',
            },
            project: {
                type: 'string',
                description: 'Route the call to the editor window with this project name or uuid.',
            },
            instance: {
                type: 'string',
                description: 'The same choice by window key; decides when both project= and instance= are given.',
            },
        },
        output: TEXT_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_bridge';
            const action = text(args.action);
            if (action === '')
                throw new Error(`${tool}: action is required (a name from the connector catalogue)`);
            const params = requireJsonObject(tool, text(args.params));
            // `--read-only` is the 537A hard gate: the CLI refuses a non-read action
            // (write / create / dangerous / unknown) before it reaches for the daemon
            // or the editor. It is pinned in argv on every call, not left to the
            // prompt: the tool's own promise must be enforced by the command it runs.
            const argv = ['bridge', 'call', '--read-only', '--action', action, '--params', params];
            if (text(args.project) !== '')
                argv.push('--project', text(args.project));
            if (text(args.instance) !== '')
                argv.push('--instance', text(args.instance));
            return discloseReadOnlyGap(await executeCli(tool, argv, BRIDGE_TIMEOUT_MS, exec));
        },
        timeoutMs: BRIDGE_TIMEOUT_MS,
    }));
}
