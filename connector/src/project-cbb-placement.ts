/**
 * `sch.place_project_cbb` — place a project-local native CBB block (038Q16B).
 *
 * This is the **second** CBB placement path, and it exists because the two kinds
 * of block live in different places. `sch.place_cbb` (038Q15) places a library
 * module through `createCbbSymbol({libraryUuid, cbbUuid, uuid}, …)`. A block
 * that was imported *into the open project* is not a library module: measured
 * 2026-11-15, `lib_Cbb.get(ca89…, 'project')` is refused while
 * `lib_Symbol.get(ca89…, 'project')` answers it (`type=17`, `libraryType='2'`,
 * `name=晶振`). So it is placed by the ordinary project-symbol call —
 *
 *     sch_PrimitiveComponent.create({libraryType: '2', libraryUuid: projectUuid,
 *       uuid: symbolUuid}, x, y, '', 0, false, true, true)
 *
 * — the upstream `cbbProjectPlace` path, and `rotation`/`mirror` are fixed at
 * `0`/`false` for this batch rather than guessed from a generic pose API.
 *
 * The order refuses before the write:
 *
 * 1. **The schematic document is the one the caller named.** `dmt_Schematic.
 *    getSchematicInfo(schematicUuid)` must answer the same uuid, the same
 *    `parentProjectUuid`, the same `name`, `itemType === 'CBB Schematic'` and a
 *    `cbbSymbol` of `type === 17`. The graph's own fields are kept as the
 *    *source identity* in the answer — this is what says which block, not the
 *    search index.
 * 2. **The name resolves to exactly one project-local symbol.** The 038Q16A
 *    `lib.cbb.search` project scope is reused for the candidate list, and then
 *    **every** candidate is re-read through `lib_Symbol.get(uuid, 'project')`:
 *    the *host symbol's* display name is the authority (a search row's `name` is
 *    an index field, and the upstream code warns it can be an internal title),
 *    so `expectedName` is matched against that, not against the row. Zero
 *    matches, more than one, or a `symbolUuid` that is not the matched local
 *    uuid are all refusals **before** anything is written.
 * 3. **Project and page are verbatim**, `documentType === 1`, checked before the
 *    write and again after it.
 * 4. **The page inventory is complete first** (unique ids, finite geometry) and
 *    compared again afterwards: exactly one new component, every pre-existing
 *    one unchanged, the new primitive `block_symbol`, `getState_Symbol().uuid`
 *    equal to the requested symbol, the fixed pose, and
 *    `getAllPinsByPrimitiveId` **as an array** (an empty array is a real reading
 *    — this sample has no pins). Pin fields are read only through the accessors
 *    the type package declares; nothing is invented.
 *
 * Every failure **after** the host call is returned as `{partial: true,
 * verified: false, primitiveId, state, problems}`: the evidence (what landed,
 * what changed) travels with the failure, and there is no retry and no rollback.
 *
 * Not reachable from here, on purpose: `lib_Cbb.get` with the project scope
 * (the reader that refuses these blocks), `createCbbSymbol` (the library path),
 * and every library write. `eda`/`ActionHandler` are type-only imports —
 * `actions.ts` imports this handler for its registry.
 */

import { ActionError } from './protocol';
import type { ActionHandler, Eda } from './actions';
import { libCbbSearch } from './library-cbb';

/** Parameters `sch.place_project_cbb` accepts — anything else is refused. */
const PLACE_KEYS = [
  'schematicUuid', 'expectedName', 'symbolUuid', 'projectUuid', 'pageUuid',
  'x', 'y', 'rotation', 'mirror',
] as const;

const SYMBOL_NAMESPACE = 'lib_Symbol';
const COMPONENTS = 'sch_PrimitiveComponent';
const CREATE_PATH = `${COMPONENTS}.create`;
const PINS_PATH = `${COMPONENTS}.getAllPinsByPrimitiveId`;
const SCHEMATIC_PATH = 'dmt_Schematic.getSchematicInfo';
/** The project's own library, as the project-symbol call spells it. */
const PROJECT_LIBRARY_TYPE = '2';
/** The document type a project-local CBB block carries. */
const CBB_SYMBOL_TYPE = 17;
/** `itemType` of the schematic document a CBB block owns. */
const CBB_SCHEMATIC_ITEM_TYPE = 'CBB Schematic';
/** `EDMT_EditorDocumentType.SCHEMATIC_PAGE`. */
const SCHEMATIC_PAGE_TYPE = 1;
/** The one component type a placed block must report. */
const BLOCK_SYMBOL = 'block_symbol';
/** The pose this batch pins — no generic pose API is guessed at. */
const FIXED_ROTATION = 0;
const FIXED_MIRROR = false;
/** The project scope keyword 038Q16A added to `lib.cbb.search`. */
const PROJECT_SCOPE = 'project';
/** One page of the project catalogue; a full page means "may be truncated". */
const SEARCH_LIMIT = 100;

const POSE_ACCESSORS = ['PrimitiveId', 'ComponentType', 'X', 'Y', 'Rotation', 'Mirror'] as const;
const PIN_ACCESSORS = ['PinNumber', 'PinName', 'X', 'Y', 'Rotation', 'PinLength'] as const;

/** A short, JSON-safe description of a value — for error messages only. */
function describeValue(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return `an array of ${value.length}`;
  if (typeof value === 'object') return 'an object';
  if (typeof value === 'string') return `a string of ${value.length} chars`;
  return `a ${typeof value}`;
}

/** Read one member without letting an exotic object cost the call. */
function readMember(obj: any, key: string): { value?: any; error?: string } {
  try {
    return { value: obj?.[key] };
  } catch (error) {
    return { error: String((error as Error)?.message ?? error) };
  }
}

/** Await a value that may or may not be a promise (the API mixes both). */
async function settle<T>(value: T | Promise<T>): Promise<T> {
  return await value;
}

/** Params are an object or the call is refused; absent means "no arguments". */
function paramObject(params: unknown): Record<string, unknown> {
  if (params === undefined || params === null) return {};
  if (typeof params !== 'object' || Array.isArray(params)) {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_project_cbb params must be an object, got ${describeValue(params)}`,
    );
  }
  return params as Record<string, unknown>;
}

/** Refuse any key the action does not define, naming what it does accept. */
function assertAllowedKeys(input: Record<string, unknown>): void {
  const unknown = Object.keys(input).filter((key) => !PLACE_KEYS.includes(key as never));
  if (unknown.length) {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_project_cbb does not take ${unknown.join(', ')}; it accepts `
        + `${PLACE_KEYS.join(', ')}`,
      { unknown, allowed: [...PLACE_KEYS] },
    );
  }
}

/** A required, non-blank string parameter. */
function requiredText(value: unknown, name: string): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_project_cbb needs a non-empty ${name}, got ${describeValue(value)}`,
      { param: name },
    );
  }
  return value;
}

/** A finite numeric coordinate — no strings, no NaN, no Infinity. */
function finiteCoord(value: unknown, name: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_project_cbb ${name} must be a finite number, got ${describeValue(value)}`,
      { param: name },
    );
  }
  return value;
}

/** `rotation`: absent is the fixed 0; anything else but 0 is refused. */
function fixedRotation(value: unknown): number {
  if (value === undefined) return FIXED_ROTATION;
  if (value !== FIXED_ROTATION) {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_project_cbb rotation is fixed at ${FIXED_ROTATION} in this action — `
        + `a project CBB is placed upright, got ${describeValue(value)}`,
      { param: 'rotation', allowed: [FIXED_ROTATION], value },
    );
  }
  return FIXED_ROTATION;
}

/** `mirror`: absent is the fixed false; anything else but false is refused. */
function fixedMirror(value: unknown): boolean {
  if (value === undefined) return FIXED_MIRROR;
  if (value !== FIXED_MIRROR) {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_project_cbb mirror is fixed at ${String(FIXED_MIRROR)} in this action — `
        + `a project CBB is placed unmirrored, got ${describeValue(value)}`,
      { param: 'mirror', allowed: [FIXED_MIRROR], value },
    );
  }
  return FIXED_MIRROR;
}

/** The `eda.<name>` namespace object, or `NOT_IMPLEMENTED` naming the path. */
function hostNamespace(eda: Eda, name: string): any {
  const read = readMember(eda, name);
  const ns = read.value;
  if (read.error !== undefined || !ns || typeof ns !== 'object') {
    throw new ActionError(
      'NOT_IMPLEMENTED',
      `${name} is not available in this editor version (${read.error ?? 'absent'})`,
      { path: name },
    );
  }
  return ns;
}

/** One method of a host namespace, or `NOT_IMPLEMENTED` with the exact path. */
function hostMethod(ns: any, path: string): any {
  const name = path.slice(path.lastIndexOf('.') + 1);
  const read = readMember(ns, name);
  if (typeof read.value !== 'function') {
    throw new ActionError(
      'NOT_IMPLEMENTED',
      `${path} is not available (${read.error ?? 'not a function'})`,
      { path },
    );
  }
  return read.value;
}

/** One `getState_*` reading, guarded on both halves. */
async function getState(obj: any, name: string): Promise<unknown> {
  const read = readMember(obj, `getState_${name}`);
  if (typeof read.value !== 'function') return undefined;
  try {
    return await settle(read.value.call(obj));
  } catch {
    return undefined;
  }
}

/** A field of a host record: plain property first, then `getState_<Name>`. */
async function readField(obj: any, names: readonly string[]): Promise<unknown> {
  for (const name of names) {
    const plain = readMember(obj, name);
    if (plain.value !== undefined) return plain.value;
    const state = await getState(obj, name);
    if (state !== undefined) return state;
  }
  return undefined;
}

/**
 * The schematic document behind `schematicUuid`, checked against the request.
 *
 * The graph is the *source identity* of the block (which schematic, which CBB
 * symbol, which project) and the only thing that ties the name the caller used
 * to a document; a mismatch in any of the five fields is a refusal.
 */
async function checkedGraph(
  eda: Eda,
  expected: { schematicUuid: string; projectUuid: string; expectedName: string },
): Promise<Record<string, unknown>> {
  const ns = hostNamespace(eda, 'dmt_Schematic');
  const get = hostMethod(ns, SCHEMATIC_PATH);

  let graph: any;
  try {
    graph = await settle(get.call(ns, expected.schematicUuid));
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${SCHEMATIC_PATH}(${expected.schematicUuid}) threw: `
        + `${String((error as Error)?.message ?? error)}`,
      { schematicUuid: expected.schematicUuid },
    );
  }
  if (!graph || typeof graph !== 'object') {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${SCHEMATIC_PATH}(${expected.schematicUuid}) answered ${describeValue(graph)} — `
        + 'there is no schematic document to place from',
      { schematicUuid: expected.schematicUuid, found: false },
    );
  }

  const uuid = await readField(graph, ['uuid']);
  const parent = await readField(graph, ['parentProjectUuid']);
  const name = await readField(graph, ['name']);
  const itemType = await readField(graph, ['itemType']);
  const cbbSymbol = await readField(graph, ['cbbSymbol']);
  const symbolUuid = await readField(cbbSymbol, ['uuid']);
  const symbolType = await readField(cbbSymbol, ['type']);

  const wrong: string[] = [];
  if (uuid !== expected.schematicUuid) wrong.push(`uuid ${JSON.stringify(uuid ?? null)}`);
  if (parent !== expected.projectUuid) wrong.push(`parentProjectUuid ${JSON.stringify(parent ?? null)}`);
  if (name !== expected.expectedName) wrong.push(`name ${JSON.stringify(name ?? null)}`);
  if (itemType !== CBB_SCHEMATIC_ITEM_TYPE) wrong.push(`itemType ${JSON.stringify(itemType ?? null)}`);
  if (symbolType !== CBB_SYMBOL_TYPE) wrong.push(`cbbSymbol.type ${JSON.stringify(symbolType ?? null)}`);
  if (wrong.length) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${SCHEMATIC_PATH}(${expected.schematicUuid}) is not the requested CBB `
        + `schematic: ${wrong.join(', ')} (expected uuid ${expected.schematicUuid}, `
        + `parentProjectUuid ${expected.projectUuid}, name `
        + `${JSON.stringify(expected.expectedName)}, itemType `
        + `${JSON.stringify(CBB_SCHEMATIC_ITEM_TYPE)}, cbbSymbol.type ${CBB_SYMBOL_TYPE})`,
      {
        schematicUuid: expected.schematicUuid,
        observed: { uuid: uuid ?? null, parentProjectUuid: parent ?? null, name: name ?? null, itemType: itemType ?? null },
        wrong,
      },
    );
  }

  return {
    uuid,
    parentProjectUuid: parent,
    name,
    itemType,
    cbbSymbol: {
      uuid: symbolUuid ?? null,
      type: symbolType,
      name: await readField(cbbSymbol, ['name']) ?? null,
    },
  };
}

/**
 * One project-local symbol, read through `lib_Symbol.get(uuid, 'project')`.
 *
 * This read is what makes the name comparison honest: the search row's `name`
 * is an index field (upstream measured it can be an internal title), so the
 * resolution below matches `expectedName` against **this** answer.
 */
async function projectSymbol(
  eda: Eda, uuid: string, context: Record<string, unknown>,
): Promise<Record<string, any>> {
  const ns = hostNamespace(eda, SYMBOL_NAMESPACE);
  const get = hostMethod(ns, `${SYMBOL_NAMESPACE}.get`);
  let answer: unknown;
  try {
    answer = await settle(get.call(ns, uuid, PROJECT_SCOPE));
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') threw while resolving the project CBB: `
        + `${String((error as Error)?.message ?? error)}`,
      { ...context, uuid, scope: PROJECT_SCOPE },
    );
  }
  if (!answer || typeof answer !== 'object' || Array.isArray(answer)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') answered ${describeValue(answer)} instead of a `
        + 'symbol — the project CBB cannot be identified',
      { ...context, uuid, scope: PROJECT_SCOPE },
    );
  }
  const symbol = answer as Record<string, any>;
  if (symbol.uuid !== uuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') answered uuid `
        + `${JSON.stringify(symbol.uuid ?? null)} — a different symbol`,
      { ...context, uuid, answered: symbol.uuid ?? null, scope: PROJECT_SCOPE },
    );
  }
  return symbol;
}

/** The project uuid the editor has focused. */
async function focusedProjectUuid(eda: Eda): Promise<unknown> {
  const ns = hostNamespace(eda, 'dmt_Project');
  const get = hostMethod(ns, 'dmt_Project.getCurrentProjectInfo');
  let info: any;
  try {
    info = await settle(get.call(ns));
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `dmt_Project.getCurrentProjectInfo() threw: ${String((error as Error)?.message ?? error)}`,
      { path: 'dmt_Project.getCurrentProjectInfo' },
    );
  }
  return readField(info, ['uuid']);
}

/** The active document info, or `undefined` when the host has none. */
async function activeDocument(eda: Eda): Promise<any> {
  const ns = hostNamespace(eda, 'dmt_SelectControl');
  const get = hostMethod(ns, 'dmt_SelectControl.getCurrentDocumentInfo');
  try {
    return await settle(get.call(ns));
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `dmt_SelectControl.getCurrentDocumentInfo() threw: `
        + `${String((error as Error)?.message ?? error)}`,
      { path: 'dmt_SelectControl.getCurrentDocumentInfo' },
    );
  }
}

/** Why the editor is not on the requested project/page, or `null` when it is. */
async function contextProblem(
  eda: Eda, projectUuid: string, pageUuid: string,
): Promise<{ problem: string; detail: Record<string, unknown> } | null> {
  const focused = await focusedProjectUuid(eda);
  if (focused !== projectUuid) {
    return {
      problem: `the focused project is ${focused == null ? '(none)' : String(focused)}, `
        + `not ${projectUuid} — refusing to place a project CBB into another project`,
      detail: {
        guard: 'project',
        expected: projectUuid,
        actual: focused == null ? null : String(focused),
      },
    };
  }
  const document = await activeDocument(eda);
  const active = await readField(document, ['uuid']);
  const parent = await readField(document, ['parentProjectUuid', 'parentProject']);
  const type = await readField(document, ['documentType', 'type']);
  if (active !== pageUuid) {
    return {
      problem: `the focused document is ${active == null ? '(none)' : String(active)}, `
        + `not the requested page ${pageUuid} — refusing to place`,
      detail: { guard: 'page', expected: pageUuid, actual: active == null ? null : String(active) },
    };
  }
  if (parent !== projectUuid) {
    return {
      problem: `page ${pageUuid} reports parent project `
        + `${parent == null ? '(none)' : String(parent)}, not ${projectUuid}`,
      detail: { guard: 'page', expected: projectUuid, actual: parent == null ? null : String(parent) },
    };
  }
  if (type !== SCHEMATIC_PAGE_TYPE) {
    return {
      problem: `document ${pageUuid} is ${type == null ? 'of unknown type' : `type ${String(type)}`}, `
        + `not a schematic page (${SCHEMATIC_PAGE_TYPE}) — a block is placed on a page`,
      detail: { guard: 'page', expected: SCHEMATIC_PAGE_TYPE, actual: type ?? null },
    };
  }
  return null;
}

/** `contextProblem` as a refusal — the pre-write half. */
async function assertContext(eda: Eda, projectUuid: string, pageUuid: string): Promise<void> {
  const refused = await contextProblem(eda, projectUuid, pageUuid);
  if (refused) throw new ActionError('PAGE_MISMATCH', refused.problem, refused.detail);
}

/** One placed component's identity and pose, as the host reports them. */
type ComponentRow = {
  id: string | null;
  type: unknown;
  x: unknown;
  y: unknown;
  rotation: unknown;
  mirror: unknown;
};

/** Why a row cannot be part of a comparable inventory, or `null`. */
function rowProblem(row: ComponentRow): string | null {
  if (typeof row.id !== 'string' || row.id.trim() === '') return 'no PrimitiveId';
  if (typeof row.x !== 'number' || !Number.isFinite(row.x)) return 'no finite X';
  if (typeof row.y !== 'number' || !Number.isFinite(row.y)) return 'no finite Y';
  if (typeof row.rotation !== 'number' || !Number.isFinite(row.rotation)) return 'no finite Rotation';
  if (typeof row.mirror !== 'boolean') return 'no boolean Mirror';
  return null;
}

/** Every component on the page, with its geometry and its host object. */
async function inventory(
  getAll: any, ns: any,
): Promise<{ rows: ComponentRow[]; byId: Map<string, any> }> {
  let answer: unknown;
  try {
    answer = await settle(getAll.call(ns));
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `sch_PrimitiveComponent.getAll() threw: ${String((error as Error)?.message ?? error)}`,
      { path: 'sch_PrimitiveComponent.getAll', reason: 'inventory-unreadable' },
    );
  }
  if (!Array.isArray(answer)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `sch_PrimitiveComponent.getAll() answered ${describeValue(answer)} instead of an `
        + 'array — the page inventory is unknown, not empty',
      { path: 'sch_PrimitiveComponent.getAll', reason: 'inventory-unreadable' },
    );
  }
  const rows: ComponentRow[] = [];
  const byId = new Map<string, any>();
  const seen = new Map<string, number>();
  for (let index = 0; index < answer.length; index += 1) {
    const [id, type, x, y, rotation, mirror] = await Promise.all(
      POSE_ACCESSORS.map((accessor) => getState(answer[index], accessor)),
    );
    const row: ComponentRow = {
      id: typeof id === 'string' ? id : null,
      type,
      x,
      y,
      rotation,
      mirror,
    };
    const problem = rowProblem(row);
    if (problem) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `component ${index} ${row.id ? `(${row.id}) ` : ''}has ${problem} — the page `
          + 'inventory is incomplete, so a placement could not be compared against it',
        { index, id: row.id, problem, reason: 'inventory-incomplete' },
      );
    }
    const first = seen.get(row.id as string);
    if (first !== undefined) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `components ${first} and ${index} share the id ${row.id} — a duplicated id `
          + 'cannot be told apart by position',
        { id: row.id, indexes: [first, index], reason: 'inventory-duplicate-id' },
      );
    }
    seen.set(row.id as string, index);
    byId.set(row.id as string, answer[index]);
    rows.push(row);
  }
  return { rows, byId };
}

/** The comparable part of a row — what "unchanged" means for an old part. */
function geometryOf(row: ComponentRow): string {
  return JSON.stringify([row.id, row.type, row.x, row.y, row.rotation, row.mirror]);
}

/**
 * The placed block's ports, from `getAllPinsByPrimitiveId`.
 *
 * An array is mandatory (a non-array means the ports are *unknown*, never
 * "none"), an empty array is a real reading, and each field is left out when
 * the host does not expose its accessor.
 */
async function readPins(
  eda: Eda, primitiveId: string, problems: string[],
): Promise<Record<string, unknown>> {
  const nsRead = readMember(eda, COMPONENTS);
  const ns = nsRead.value;
  const fn = readMember(ns, 'getAllPinsByPrimitiveId');
  if (typeof fn.value !== 'function') {
    problems.push(
      `${PINS_PATH} is not available (${fn.error ?? 'not a function'}) — the block's `
        + 'ports cannot be read back',
    );
    return { source: PINS_PATH, readable: false, returned: null, pins: [] };
  }

  let answer: unknown;
  try {
    answer = await settle(fn.value.call(ns, primitiveId));
  } catch (error) {
    problems.push(
      `${PINS_PATH}(${primitiveId}) threw: ${String((error as Error)?.message ?? error)}`,
    );
    return { source: PINS_PATH, readable: false, returned: null, pins: [] };
  }
  if (!Array.isArray(answer)) {
    problems.push(
      `${PINS_PATH}(${primitiveId}) answered ${describeValue(answer)} instead of an `
        + 'array — the ports are unknown, not empty',
    );
    return { source: PINS_PATH, readable: false, returned: null, pins: [] };
  }

  const pins: Record<string, unknown>[] = [];
  for (let index = 0; index < answer.length; index += 1) {
    const pin = answer[index];
    if (!pin || typeof pin !== 'object') {
      problems.push(`${PINS_PATH} item ${index} is ${describeValue(pin)}, not a pin`);
      continue;
    }
    const row: Record<string, unknown> = {};
    for (const accessor of PIN_ACCESSORS) {
      const value = await getState(pin, accessor);
      if (value !== undefined) row[accessor] = value;
    }
    pins.push(row);
  }
  return { source: PINS_PATH, readable: true, returned: answer.length, pins };
}

/**
 * `sch.place_project_cbb` — one re-verified project-local CBB placement.
 *
 * Success is `verified: true, partial: false`; anything after the host call is
 * `partial: true, verified: false` with the `primitiveId`, the state actually
 * read and a `problems` list.
 */
export const schPlaceProjectCbb: ActionHandler = async (params, eda) => {
  const input = paramObject(params);
  assertAllowedKeys(input);

  const schematicUuid = requiredText(input.schematicUuid, 'schematicUuid');
  const expectedName = requiredText(input.expectedName, 'expectedName');
  const symbolUuid = requiredText(input.symbolUuid, 'symbolUuid');
  const projectUuid = requiredText(input.projectUuid, 'projectUuid');
  const pageUuid = requiredText(input.pageUuid, 'pageUuid');
  const x = finiteCoord(input.x, 'x');
  const y = finiteCoord(input.y, 'y');
  const rotation = fixedRotation(input.rotation);
  const mirror = fixedMirror(input.mirror);

  // --- 1. The schematic document, and the source identity it carries.
  const graph = await checkedGraph(eda, { schematicUuid, projectUuid, expectedName });

  // --- 2. Exactly one project-local symbol, named by the host's own readback.
  const found = await libCbbSearch({
    query: expectedName,
    libraryUuid: PROJECT_SCOPE,
    limit: SEARCH_LIMIT,
    page: 1,
  }, eda) as { count: number; items: Record<string, any>[] };
  if (found.count >= SEARCH_LIMIT) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib.cbb.search(${JSON.stringify(expectedName)}, 'project') answered a full page of `
        + `${found.count} — the catalogue may be truncated, so uniqueness cannot be decided`,
      { expectedName, count: found.count, limit: SEARCH_LIMIT },
    );
  }

  const matches: { uuid: string; name: string; sourceLibraryUuid: string | null }[] = [];
  for (const item of found.items) {
    const itemUuid = String(item.uuid);
    const symbol = await projectSymbol(eda, itemUuid, { expectedName });
    if (symbol.name === expectedName) {
      matches.push({
        uuid: itemUuid,
        name: symbol.name,
        sourceLibraryUuid: typeof item.sourceLibraryUuid === 'string'
          ? item.sourceLibraryUuid
          : null,
      });
    }
  }
  if (matches.length !== 1) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib.cbb.search(${JSON.stringify(expectedName)}, 'project') resolved to `
        + `${matches.length} project-local CBB symbol(s) named ${JSON.stringify(expectedName)} `
        + 'by lib_Symbol.get(uuid, \'project\') — exactly one is required, so no '
        + 'placement was attempted',
      { expectedName, candidates: matches, searched: found.count },
    );
  }
  const resolved = matches[0];
  if (symbolUuid !== resolved.uuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `expectedName ${JSON.stringify(expectedName)} resolves to the project-local symbol `
        + `${resolved.uuid}, but symbolUuid is ${JSON.stringify(symbolUuid)} — the `
        + 'request names two different blocks',
      { expectedName, resolvedUuid: resolved.uuid, symbolUuid },
    );
  }

  // --- 3. The focused project and page, verbatim.
  await assertContext(eda, projectUuid, pageUuid);

  // --- 4. The write path and the baseline.
  const components = hostNamespace(eda, COMPONENTS);
  const create = hostMethod(components, CREATE_PATH);
  const getAll = hostMethod(components, `${COMPONENTS}.getAll`);
  const before = (await inventory(getAll, components)).rows;

  // --- 5. The one write: the ordinary project-symbol call, fixed pose.
  let created: any;
  let createError: string | undefined;
  try {
    created = await settle(create.call(
      components,
      { libraryType: PROJECT_LIBRARY_TYPE, libraryUuid: projectUuid, uuid: symbolUuid },
      x,
      y,
      '',
      FIXED_ROTATION,
      FIXED_MIRROR,
      true,
      true,
    ));
  } catch (error) {
    createError = String((error as Error)?.message ?? error);
  }
  let primitiveId = typeof (await getState(created, 'PrimitiveId')) === 'string'
    ? await getState(created, 'PrimitiveId') as string
    : null;

  const problems: string[] = [];
  if (createError !== undefined) {
    problems.push(`${CREATE_PATH} threw: ${createError}`);
  }

  const answer: Record<string, unknown> = {
    schematicUuid,
    expectedName,
    symbolUuid,
    projectUuid,
    pageUuid,
    graph,
    resolution: {
      source: "lib.cbb.search(project) + lib_Symbol.get(project)",
      searched: found.count,
      resolvedUuid: resolved.uuid,
      sourceLibraryUuid: resolved.sourceLibraryUuid,
    },
    requested: { x, y, rotation, mirror },
    beforeCount: before.length,
    primitiveId,
    state: null,
    symbol: null,
    pins: null,
    preserved: null,
    verified: false,
    partial: true,
  };

  // --- 6. Read back; nothing below throws.
  const refused = await contextProblem(eda, projectUuid, pageUuid);
  if (refused) problems.push(`after the placement, ${refused.problem}`);

  let latest: { rows: ComponentRow[]; byId: Map<string, any> } | null = null;
  try {
    latest = await inventory(getAll, components);
  } catch (error) {
    problems.push(
      `the page could not be re-read after the placement: `
        + String((error as Error)?.message ?? error),
    );
  }

  if (latest) {
    const after = latest.rows;
    if (!primitiveId) {
      const appeared = after.filter((row) => !before.some((old) => old.id === row.id));
      if (appeared.length === 1) primitiveId = appeared[0].id;
      else if (appeared.length > 1) {
        problems.push(`${appeared.length} components appeared for one placement`);
      }
    }
    answer.primitiveId = primitiveId;

    if (!primitiveId) {
      problems.push(`${CREATE_PATH} returned no primitiveId and no single new component appeared`);
    } else if (before.some((row) => row.id === primitiveId)) {
      problems.push(`the returned primitiveId ${primitiveId} already belonged to an existing component`);
    }
    if (after.length !== before.length + 1) {
      problems.push(
        `the page holds ${after.length} components after the placement, not `
          + `${before.length + 1}`,
      );
    }
    const changed = before.filter((old) => !after.some((row) => geometryOf(row) === geometryOf(old)));
    answer.preserved = changed.length === 0;
    if (changed.length) {
      problems.push(
        `${changed.length} pre-existing component(s) changed geometry: `
          + `${changed.map((row) => row.id).join(', ')}`,
      );
    }

    const instance = primitiveId ? after.find((row) => row.id === primitiveId) : undefined;
    if (primitiveId && !instance) {
      problems.push(`primitiveId ${primitiveId} is not in the fresh inventory`);
    }
    if (instance) {
      const state = {
        id: instance.id,
        type: instance.type,
        x: instance.x,
        y: instance.y,
        rotation: instance.rotation,
        mirror: instance.mirror,
      };
      answer.state = state;
      if (state.type !== BLOCK_SYMBOL) {
        problems.push(
          `the placed component reports type ${JSON.stringify(state.type)}, not `
            + `${JSON.stringify(BLOCK_SYMBOL)}`,
        );
      }
      if (state.x !== x || state.y !== y || state.rotation !== FIXED_ROTATION
        || state.mirror !== FIXED_MIRROR) {
        problems.push(
          `the placed component's pose is ${JSON.stringify({
            x: state.x, y: state.y, rotation: state.rotation, mirror: state.mirror,
          })}, not the requested ${JSON.stringify({ x, y, rotation, mirror })}`,
        );
      }

      // The block's binding: `getState_Symbol()` must be the symbol we asked for.
      const hostInstance = latest.byId.get(primitiveId as string);
      const placedSymbol = hostInstance ? await getState(hostInstance, 'Symbol') : undefined;
      const placedSymbolUuid = await readField(placedSymbol, ['uuid', 'Uuid']);
      answer.symbol = placedSymbol === undefined || placedSymbol === null
        ? null
        : { uuid: placedSymbolUuid ?? null };
      if (placedSymbolUuid !== symbolUuid) {
        problems.push(
          `the placed component's symbol is `
            + `${placedSymbolUuid == null ? 'unreadable' : JSON.stringify(placedSymbolUuid)}, not `
            + `${JSON.stringify(symbolUuid)}`,
        );
      }

      answer.pins = await readPins(eda, primitiveId as string, problems);
    }
  }

  answer.problems = problems;
  answer.verified = problems.length === 0;
  answer.partial = problems.length > 0;
  if (problems.length) {
    answer.error = { message: problems.join('; '), problems };
  }
  return answer;
};
