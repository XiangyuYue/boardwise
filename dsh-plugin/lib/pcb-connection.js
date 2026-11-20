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
import { defineTool } from '@deepseek-ai/dsh-tools';
import { TEXT_OUTPUT, executeCli, text } from './transport.js';
/** 559: one probe is a version pair plus two host reads — never a batch. */
const PCB_CONNECTION_TIMEOUT_MS = 120_000;
/**
 * One end of the question, refused before anything is spawned when it is blank.
 *
 * Only emptiness is this plugin's business: whether `U9.2` is a well-formed
 * REF.PAD, whether it resolves to exactly one pad, whether the two ends share a
 * net and whether they share copper are all Python's judgement. Trimming is the
 * transport's (`text`), so a padded name is the same question, not a new one.
 */
function requireEndpoint(tool, name, value, example) {
    const endpoint = text(value);
    if (endpoint === '') {
        throw new Error(`${tool}: ${name} is required (one end as REF.PAD, for example ${example}); ` +
            'the pad reference and the verdict are the CLI\'s, so a blank end is not forwarded.');
    }
    return endpoint;
}
/**
 * The daemon port, when given: a finite positive integer, else refused unspawned.
 *
 * `--port` takes an int in argparse, so a fraction, `0`, a negative number or a
 * non-number can only ever be an argparse error (exit 2, which this tool reads
 * as NOT_PROVEN's code). Refusing it here keeps that ambiguity out of the
 * answer: a malformed port is an input mistake, not a probe result.
 */
function optionalPort(tool, value) {
    if (value === undefined || value === null)
        return undefined;
    if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value) || value <= 0) {
        throw new Error(`${tool}: port must be a finite positive integer (the daemon port, default 61190), ` +
            `got ${JSON.stringify(value)}.`);
    }
    return value;
}
/** Register the direct-only copper probe between parts hunt and the draw tools. */
export function registerPcbConnection(ctx) {
    ctx.tools.register(defineTool({
        name: 'boardwise_pcb_connection',
        description: 'Ask the live editor one closed, read-only question: do these two pads share copper, as far as ' +
            'the host can prove directly? `from` and `to` are REF.PAD strings (e.g. U9.2, CN3.1) on the ' +
            '**focused** PCB — the focused page is the board identity, so there is no file, no board name, ' +
            'no live flag and no document switch; this tool never opens, focuses or writes a design. ' +
            'The answer is one machine JSON on stdout (`schema` = boardwise.pcbConnection/1) and one of ' +
            'three verdicts, all of which are **results**, not tool failures: exit 0 = CONNECTED (a typed, ' +
            'sourced direct intersection: both ends\' getConnectedPrimitives(false) name the same Line/Arc, ' +
            'or one end\'s direct answer names the other pad), exit 2 = NOT_PROVEN, exit 3 = INDETERMINATE ' +
            'or a refusal (the refusal case prints one line on stderr with an **empty stdout**). ' +
            'This contract is **direct-only** and never reads getEntireTrack: an id set is not a connected ' +
            'component, so multi-hop copper is not claimed here. NOT_PROVEN therefore means 「在 direct ' +
            '范围内两端没有共享图元」 — **not 「开路」**: via/fill/pour adjacency and multi-hop copper are ' +
            'outside this contract and are listed in `unknown`/`scope`, so read the JSON before quoting a ' +
            'negative. An INDETERMINATE carries the evidence gap that could overturn a negative. ' +
            'The only two actions reached are `sys.probe` (the version pair) and the `risk: read` ' +
            '`pcb.connection_probe`; an older daemon or connector bundle without that action refuses with ' +
            'exit 3 and an empty stdout — that is a refusal to answer, never a verdict. ' +
            'project= / instance= route the question to one editor window when several are connected ' +
            '(the daemon never guesses); port= is the daemon port. ' +
            'Judgement — REF.PAD syntax, which pad, which net, the intersection and the verdict — stays in ' +
            'the CLI; this tool only builds the command and hands back its exit code, stdout and stderr.',
        parameters: {
            from: {
                type: 'string',
                required: true,
                description: 'One end as DESIGNATOR.PAD, for example U9.2 (the CLI judges the syntax).',
            },
            to: {
                type: 'string',
                required: true,
                description: 'The other end as DESIGNATOR.PAD, for example CN3.1.',
            },
            project: {
                type: 'string',
                description: 'Which editor project to ask, by name or uuid. A mismatch is refused by the daemon, ' +
                    'never re-routed to another window.',
            },
            instance: {
                type: 'string',
                description: 'The same choice spelled as the window key `bridge status` prints.',
            },
            port: {
                type: 'number',
                description: 'Daemon port (default 61190). A finite positive integer.',
            },
        },
        output: TEXT_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_pcb_connection';
            const from = requireEndpoint(tool, 'from', args.from, 'U9.2');
            const to = requireEndpoint(tool, 'to', args.to, 'CN3.1');
            // The fixed head first, so the two ends of the question are never behind
            // an optional flag; only what was actually given is appended.
            const argv = ['pcb', 'connection', '--from', from, '--to', to];
            const project = text(args.project);
            if (project !== '')
                argv.push('--project', project);
            const instance = text(args.instance);
            if (instance !== '')
                argv.push('--instance', instance);
            const port = optionalPort(tool, args.port);
            if (port !== undefined)
                argv.push('--port', String(port));
            // Text transport on purpose: the CLI's answer is stdout JSON and there is
            // no `--json PATH`, so exit 0/2/3, stdout, stderr and any truncation are
            // handed back as they arrived. Nothing here re-reads or re-words them.
            return await executeCli(tool, argv, PCB_CONNECTION_TIMEOUT_MS, exec);
        },
        timeoutMs: PCB_CONNECTION_TIMEOUT_MS,
    }));
}
