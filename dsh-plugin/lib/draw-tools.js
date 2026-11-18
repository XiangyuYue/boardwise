/** Offline draw tools (540B7): Python judges, TypeScript transports JSON files. */
import { defineTool } from '@deepseek-ai/dsh-tools';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { OUT_DIR_PREFIX } from './cli.js';
import { STRUCTURED_OUTPUT, describeValue, runStructuredCli, text, } from './transport.js';
import { ensureDirectory, requireArrayField, requireExistingInput, requireField, requireObjectField, requirePresentField, transportDir, } from './tool-utils.js';
const DRAW_COMPILE_TIMEOUT_MS = 600_000;
const DRAW_LINT_TIMEOUT_MS = 120_000;
const DRAW_V4_FACTS_TIMEOUT_MS = 300_000;
const DRAW_PLAN_TIMEOUT_MS = 120_000;
/** Append offline draw tools after the historical eight; no apply surface. */
export function registerDrawTools(ctx) {
    ctx.tools.register(defineTool({
        name: 'boardwise_draw_compile',
        description: 'Compile one CircuitSpec + PresentationSpec + symbol profile library entirely offline through ' +
            '`boardwise draw compile`. No editor, daemon, live page or apply route is contacted. The CLI writes the ' +
            'result to a private JSON file and this tool returns that whole object unchanged: a single-module ' +
            'presentation answers `candidates` + `failureRounds`, while a page presentation (the CLI marks it ' +
            '`document: "page"`) answers `pages` + `moduleFailureRounds`; both carry `failures`, `categories`, ' +
            '`rejected`, `notes` and the `previews` artifact paths. `ok` and every verdict are Python\'s, never ' +
            'recomputed in TypeScript. Exit 0 (at least one candidate) and exit 5 (a documented compiler refusal) are ' +
            'both transported **when the CLI wrote the JSON file**; a run whose input could not be read exits 5 without ' +
            'writing one, and that is an error — as is an unreadable transport or an unexpected exit. A partial or ' +
            'stdout-derived answer is never returned.',
        parameters: {
            circuit: {
                type: 'string',
                required: true,
                description: 'The CircuitSpec JSON to read (read-only).',
            },
            presentation: {
                type: 'string',
                required: true,
                description: 'The PresentationSpec JSON to read (read-only).',
            },
            profiles: {
                type: 'string',
                required: true,
                description: 'The symbol profile library JSON to read (read-only).',
            },
            pageBox: {
                type: 'string',
                description: 'Optional canvas box X0,Y0,X1,Y1, passed to --page-box without interpretation in TS. ' +
                    'The CLI itself requires one when the presentation describes a page.',
            },
            intent: {
                type: 'string',
                description: 'Optional DesignIntent JSON passed to --intent (read-only).',
            },
            out: {
                type: 'string',
                description: 'Directory for candidate SVG/LayoutPlan artifacts (created if missing). Default: a fresh temp directory.',
            },
        },
        output: STRUCTURED_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_draw_compile';
            const circuit = requireExistingInput(tool, 'circuit', text(args.circuit), 'the CircuitSpec JSON');
            const presentation = requireExistingInput(tool, 'presentation', text(args.presentation), 'the PresentationSpec JSON');
            const profiles = requireExistingInput(tool, 'profiles', text(args.profiles), 'the symbol profile JSON');
            const intent = text(args.intent);
            if (intent !== '')
                requireExistingInput(tool, 'intent', intent, 'the DesignIntent JSON');
            const requestedOut = text(args.out);
            const outDir = requestedOut !== '' ? requestedOut : await mkdtemp(join(tmpdir(), OUT_DIR_PREFIX));
            await ensureDirectory(tool, outDir);
            const target = join(await transportDir(tool), 'draw-compile.json');
            const argv = [
                'draw', 'compile',
                '--circuit', circuit,
                '--presentation', presentation,
                '--profiles', profiles,
                '--out', outDir,
                '--json', target,
            ];
            const pageBox = text(args.pageBox);
            if (pageBox !== '')
                argv.push('--page-box', pageBox);
            if (intent !== '')
                argv.push('--intent', intent);
            const result = await runStructuredCli(tool, argv, DRAW_COMPILE_TIMEOUT_MS, exec, target, [0, 5]);
            requireField(tool, result, 'command', 'compile');
            requireBooleanField(tool, result, 'ok');
            // `draw compile` has two payload shapes and Python names which one this is:
            // a page presentation is compiled by the page compiler and answers `pages`
            // (+ `moduleFailureRounds`), a single-module one answers `candidates`
            // (+ `failureRounds`). This is a transport route, not a verdict: `ok` stays
            // exactly as Python wrote it, and the complete object is returned either way.
            if (result['document'] === 'page') {
                requireArrayField(tool, result, 'pages');
            }
            else {
                requireArrayField(tool, result, 'candidates');
            }
            requireArrayField(tool, result, 'failures');
            requireArrayField(tool, result, 'previews');
            return result;
        },
        timeoutMs: DRAW_COMPILE_TIMEOUT_MS,
    }));
    ctx.tools.register(defineTool({
        name: 'boardwise_draw_lint',
        description: 'Replay one captured schematic page offline through `boardwise draw lint --snapshot ... --render ...`. ' +
            'Both inputs are required; bodies= optionally supplies measured part boxes. There is deliberately no page=, ' +
            'project=, instance= or apply parameter, so this tool cannot focus or modify a live design. Python writes ' +
            'the complete findings/counts/thresholds/notes object to a private JSON file and this tool returns it whole. ' +
            'Exit 0 (no ERROR) and exit 1 (ERROR findings) are both lint results and return that JSON; exit 2 is an ' +
            'input/transport error. The tool never derives a finding, severity, verdict or pass from the JSON in TS.',
        parameters: {
            snapshot: {
                type: 'string',
                required: true,
                description: 'Captured sch.geometry JSON to replay offline (read-only).',
            },
            render: {
                type: 'string',
                required: true,
                description: 'The matching captured SVG render used for text geometry (read-only).',
            },
            bodies: {
                type: 'string',
                description: 'Optional measured body boxes JSON passed to --bodies (read-only).',
            },
        },
        output: STRUCTURED_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_draw_lint';
            const snapshot = requireExistingInput(tool, 'snapshot', text(args.snapshot), 'the captured geometry JSON');
            const render = requireExistingInput(tool, 'render', text(args.render), 'the captured SVG render');
            const bodies = text(args.bodies);
            if (bodies !== '')
                requireExistingInput(tool, 'bodies', bodies, 'the measured body-box JSON');
            const target = join(await transportDir(tool), 'draw-lint.json');
            const argv = ['draw', 'lint', '--snapshot', snapshot, '--render', render];
            if (bodies !== '')
                argv.push('--bodies', bodies);
            argv.push('--json', target);
            const result = await runStructuredCli(tool, argv, DRAW_LINT_TIMEOUT_MS, exec, target, [0, 1]);
            requireField(tool, result, 'source', 'replay');
            requirePresentField(tool, result, 'page');
            requireArrayField(tool, result, 'findings');
            requireObjectField(tool, result, 'counts');
            requirePresentField(tool, result, 'exitCode');
            requireBooleanField(tool, result, 'textReadable');
            requireArrayField(tool, result, 'notes');
            requireObjectField(tool, result, 'thresholds');
            return result;
        },
        timeoutMs: DRAW_LINT_TIMEOUT_MS,
    }));
    ctx.tools.register(defineTool({
        name: 'boardwise_draw_v4_facts',
        description: 'Read an EasyEDA Pro V4 **folder project** (`*.eprj3`, or its index file) entirely offline through ' +
            '`boardwise draw v4-facts` and return the `boardwise.v4-facts/1` document whole. No editor, daemon or ' +
            'live page is contacted. The document is an evidence layer, not a rebuilt model: every pin, flag and ' +
            'label keeps the page it came from, a `Global Net Name` flag stays distinct from a page `NET` label, and ' +
            'the raw `Pin Type` code is carried as read. It deliberately guesses nothing — pin direction, voltage, ' +
            'bus membership and cross-page connectivity stay unanswered (`crossPageConnectivityProven` is always ' +
            'false), and the questions are listed in `notes`. Optional outputs write the derived documents next to ' +
            '`out`: `writeCircuit` (a CircuitSpec), `writePresentation` (a PresentationSpec seed), `writeProfiles` ' +
            '(the profile book augmented with this project\'s measured poses; needs `profiles`) and ' +
            '`writeEvidence` (page evidence) as `circuit.json` / `presentation.json` / `profiles.json` / ' +
            '`evidence.json`. When any of them is written the returned document carries one extra top-level key, ' +
            '`dshArtifacts` (kind -> path), which is this transport\'s addition and never Python\'s. Exit 2 means the ' +
            'project cannot be read and no document exists, so no JSON is returned; every fact and verdict is ' +
            'Python\'s and nothing here is recomputed in TypeScript.',
        parameters: {
            file: {
                type: 'string',
                required: true,
                description: 'The .eprj3 folder project (or its index file) to read (read-only).',
            },
            board: {
                type: 'string',
                description: 'Board uuid or title, passed to --board without interpretation in TS. The CLI requires one when the ' +
                    'project holds several boards.',
            },
            profiles: {
                type: 'string',
                description: 'Optional measured symbol library JSON passed to --profiles (read-only). Also required by ' +
                    'writeProfiles.',
            },
            circuit: {
                type: 'string',
                description: 'Optional existing CircuitSpec JSON passed to --circuit: the CLI enriches that spec instead of ' +
                    'deriving one, and requires one of the write outputs.',
            },
            writeCircuit: {
                type: 'boolean',
                description: 'Write the derived/enriched CircuitSpec to <out>/circuit.json.',
            },
            writePresentation: {
                type: 'boolean',
                description: 'Write the PresentationSpec seed to <out>/presentation.json.',
            },
            writeProfiles: {
                type: 'boolean',
                description: 'Write the pose-augmented profile book to <out>/profiles.json (needs profiles).',
            },
            writeEvidence: {
                type: 'boolean',
                description: 'Write the page evidence document to <out>/evidence.json.',
            },
            out: {
                type: 'string',
                description: 'Directory for the optional outputs (created if missing). Default: a fresh temp directory. Ignored ' +
                    'when no write* parameter is set.',
            },
        },
        output: STRUCTURED_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_draw_v4_facts';
            const file = requireExistingInput(tool, 'file', text(args.file), 'an .eprj3 folder project (or its index file) to read');
            const board = text(args.board);
            const profiles = text(args.profiles);
            if (profiles !== '') {
                requireExistingInput(tool, 'profiles', profiles, 'the measured symbol library JSON');
            }
            const circuit = text(args.circuit);
            if (circuit !== '') {
                requireExistingInput(tool, 'circuit', circuit, 'the existing CircuitSpec JSON to enrich');
            }
            // The four document writes are independent switches; the directory exists
            // only when one of them is on, so a plain read leaves no stray folder.
            const writes = [
                { flag: '--out-circuit', name: 'circuit.json', key: 'circuit', on: args.writeCircuit === true },
                { flag: '--out-presentation', name: 'presentation.json', key: 'presentation', on: args.writePresentation === true },
                { flag: '--out-profiles', name: 'profiles.json', key: 'profiles', on: args.writeProfiles === true },
                { flag: '--out-evidence', name: 'evidence.json', key: 'evidence', on: args.writeEvidence === true },
            ];
            const requestedOut = text(args.out);
            const outDir = writes.some(item => item.on)
                ? (requestedOut !== '' ? requestedOut : await mkdtemp(join(tmpdir(), OUT_DIR_PREFIX)))
                : '';
            if (outDir !== '')
                await ensureDirectory(tool, outDir);
            const target = join(await transportDir(tool), 'draw-v4-facts.json');
            const argv = ['draw', 'v4-facts', '--file', file, '-o', target];
            if (board !== '')
                argv.push('--board', board);
            if (profiles !== '')
                argv.push('--profiles', profiles);
            if (circuit !== '')
                argv.push('--circuit', circuit);
            const artifacts = {};
            for (const item of writes) {
                if (!item.on)
                    continue;
                const path = join(outDir, item.name);
                argv.push(item.flag, path);
                artifacts[item.key] = path;
            }
            // Only exit 0 is a transported answer: exit 2 is "this project cannot be
            // read", which writes no document, so it stays an error carrying the
            // CLI's own words rather than an empty facts object.
            const result = await runStructuredCli(tool, argv, DRAW_V4_FACTS_TIMEOUT_MS, exec, target, [0]);
            requireField(tool, result, 'schema', 'boardwise.v4-facts/1');
            requireArrayField(tool, result, 'nets');
            requireArrayField(tool, result, 'instances');
            requireArrayField(tool, result, 'pages');
            if (Object.keys(artifacts).length === 0)
                return result;
            // `StructuredResult` is the parsed envelope (`Record<string, never>`), so
            // the one key this transport adds is stated as what it is: `dshArtifacts`
            // names where the optional documents landed, and the tool description
            // says so. Python's own keys are never touched.
            return { ...result, dshArtifacts: artifacts };
        },
        timeoutMs: DRAW_V4_FACTS_TIMEOUT_MS,
    }));
    ctx.tools.register(defineTool({
        name: 'boardwise_draw_plan',
        description: 'Preflight one saved PageLayoutPlan through `boardwise draw plan --layout ...`, without recompiling. ' +
            'Requires an existing saved page candidate and the current circuit, presentation and profile JSON files. ' +
            'The configured CLI must support `draw plan --layout`; this tool does not install or upgrade it. ' +
            'This is entirely offline: no page/project/instance or apply route is exposed, and no editor is written. ' +
            'Python rechecks the candidate and writes a ChangePlan; the complete CLI JSON is returned unchanged ' +
            'on exit 0 or a documented refusal on exit 5. An unreadable input/JSON or any other exit is an error. ' +
            'The report pageDocument locates the adjacent plan.json artifact. Preflight acceptance does not mean ' +
            'a finished drawing, editor pin-connectivity read-back or visual acceptance; apply and final review ' +
            'remain separate. No verdict or ok value is recomputed in TypeScript.',
        parameters: {
            layout: {
                type: 'string', required: true,
                description: 'Saved PageLayoutPlan JSON candidate to preflight (read-only).',
            },
            circuit: {
                type: 'string', required: true,
                description: 'Current CircuitSpec JSON (read-only).',
            },
            presentation: {
                type: 'string', required: true,
                description: 'Current PresentationSpec JSON (read-only).',
            },
            profiles: {
                type: 'string', required: true,
                description: 'Current symbol profile library JSON (read-only).',
            },
            out: {
                type: 'string',
                description: 'Directory for plan.json and plan.page.json. Default: a fresh persistent temp directory.',
            },
        },
        output: STRUCTURED_OUTPUT,
        execute: async (args, exec) => {
            const tool = 'boardwise_draw_plan';
            const layout = requireExistingInput(tool, 'layout', text(args.layout), 'the saved PageLayoutPlan JSON');
            const circuit = requireExistingInput(tool, 'circuit', text(args.circuit), 'the current CircuitSpec JSON');
            const presentation = requireExistingInput(tool, 'presentation', text(args.presentation), 'the current PresentationSpec JSON');
            const profiles = requireExistingInput(tool, 'profiles', text(args.profiles), 'the current symbol profile JSON');
            const requestedOut = text(args.out);
            const outDir = requestedOut !== '' ? requestedOut : await mkdtemp(join(tmpdir(), OUT_DIR_PREFIX));
            await ensureDirectory(tool, outDir);
            const target = join(await transportDir(tool), 'draw-plan.json');
            const argv = [
                'draw', 'plan', '--layout', layout,
                '--circuit', circuit, '--presentation', presentation, '--profiles', profiles,
                '--out', join(outDir, 'plan.json'), '--json', target,
            ];
            const result = await runStructuredCli(tool, argv, DRAW_PLAN_TIMEOUT_MS, exec, target, [0, 5]);
            requireField(tool, result, 'command', 'plan');
            requireField(tool, result, 'document', 'page');
            requireBooleanField(tool, result, 'ok');
            requirePresentField(tool, result, 'plan');
            requirePresentField(tool, result, 'page');
            requirePresentField(tool, result, 'pageDocument');
            requirePresentField(tool, result, 'exitCode');
            requireArrayField(tool, result, 'notes');
            return result;
        },
        timeoutMs: DRAW_PLAN_TIMEOUT_MS,
    }));
}
/** Transport shape only; whether the boolean is true remains Python's answer. */
function requireBooleanField(tool, value, field) {
    const actual = value[field];
    if (typeof actual !== 'boolean') {
        throw new Error(`${tool}: the --json result has \`${field}\` ${describeValue(actual)}, not a boolean; ` +
            'refusing to report a malformed envelope.');
    }
}
