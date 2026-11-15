/**
 * `sch.place_cbb` — put one native reuse module (CBB / 复用模块) onto the
 * focused schematic page, and prove afterwards that exactly that module went
 * there (038Q15).
 *
 * The call is `sch_PrimitiveComponent.createCbbSymbol({libraryUuid, cbbUuid,
 * uuid}, x, y, rotation, mirror)` — declared `@beta`, and the sibling of
 * `SCH_PrimitiveComponent.create` the ordinary placement uses. A CBB placement
 * is a **block instance**, not a device: it carries its own identity
 * (`getState_Cbb` / `getState_CbbSymbol`) and it may have zero ports, so
 * "nothing was created" and "a block with no pins was created" look alike from
 * the outside. Everything below exists to tell those two apart.
 *
 * The order is the contract, and each step refuses before the write instead of
 * explaining itself afterwards:
 *
 * 1. **The module is whoever `lib_Cbb.get` says it is.** The caller's
 *    `uuid`/`libraryUuid` are re-read through `lib.cbb.get` (the 038Q14 action),
 *    and `expectedName` must equal the name that readback returns — a name the
 *    caller *remembers* is not an identity, and a module renamed since is a
 *    different thing to place.
 * 2. **Project and page are the caller's, verbatim.** `dmt_Project.
 *    getCurrentProjectInfo().uuid` and `dmt_SelectControl.
 *    getCurrentDocumentInfo()` (same uuid, same `parentProjectUuid`,
 *    `documentType === 1`) are both compared to the request. The host places
 *    onto whatever page is in front; there is no unguarded shape here.
 * 3. **The source symbol is verified when the host can read it, and only
 *    declared unverified when the caller says so.** This sample's
 *    `lib_Symbol.get` answers nothing (038Q15 §已核实的输入: `type 17` and the
 *    140×140 frame were proven from the source document instead). So an
 *    unreadable symbol is a refusal **unless** `allowUnverifiedSourceSymbol
 *    === true`, and the answer then carries `symbolVerification.mode:
 *    'unverified-source-symbol'` — the caller, not this action, is asserting
 *    that the uuid is backed by other evidence.
 * 4. **The page's components are read completely first.** Every row needs an
 *    id, finite x/y/rotation and a boolean mirror, and no id may repeat: an
 *    inventory that cannot be compared is not a baseline, and a placement
 *    without a baseline cannot prove what it added or what it left alone.
 * 5. **After the write, the same guards are re-run and the answer is read, not
 *    assumed.** Exactly one component is new and its id is unique; every
 *    earlier row is still present with identical geometry; the new primitive
 *    reports `block_symbol`, the requested pose, and the CBB/CBB-symbol
 *    identity that was asked for. Its ports are read through
 *    `getAllPinsByPrimitiveId` — an **array is required**, an empty one is a
 *    real reading (this sample has no pins), and a field the host does not
 *    expose is simply absent from the row, never invented.
 *
 * Anything that goes wrong **after** `createCbbSymbol` was called is reported
 * as `{partial: true, verified: false, primitiveId, state, problems}` — the
 * evidence travels with the failure. Throwing there would lose the one thing
 * the caller needs to decide whether a retry would stack a second block.
 *
 * `eda` and `ActionHandler` are type-only imports: `actions.ts` imports this
 * handler for its registry.
 */

import { ActionError } from './protocol';
import type { ActionHandler, Eda } from './actions';
import { libCbbGet } from './library-cbb';

/** Parameters `sch.place_cbb` accepts — anything else is refused by name. */
const PLACE_KEYS = [
  'uuid', 'libraryUuid', 'expectedName', 'symbolUuid', 'projectUuid',
  'pageUuid', 'x', 'y', 'rotation', 'mirror', 'allowUnverifiedSourceSymbol',
] as const;

/** Quarter turns only: the host stores a rotation, not an angle. */
const ROTATIONS = [0, 90, 180, 270] as const;

/** The one component type a placed CBB must report. */
const BLOCK_SYMBOL = 'block_symbol';

const SYMBOL_NAMESPACE = 'lib_Symbol';
const COMPONENTS = 'sch_PrimitiveComponent';
const CREATE_PATH = `${COMPONENTS}.createCbbSymbol`;
const PINS_PATH = `${COMPONENTS}.getAllPinsByPrimitiveId`;
/** The CBB symbol's document type (`type 17`, proven from the source document). */
const CBB_SYMBOL_TYPE = 17;
/** `EDMT_EditorDocumentType.SCHEMATIC_PAGE`. */
const SCHEMATIC_PAGE_TYPE = 1;
/** The accessors one placed component's identity/pose is read through. */
const POSE_ACCESSORS = ['PrimitiveId', 'ComponentType', 'X', 'Y', 'Rotation', 'Mirror'] as const;
/** The accessors one placed pin is read through — the type package's own names. */
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
      `sch.place_cbb params must be an object, got ${describeValue(params)}`,
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
      `sch.place_cbb does not take ${unknown.join(', ')}; it accepts ${PLACE_KEYS.join(', ')}`,
      { unknown, allowed: [...PLACE_KEYS] },
    );
  }
}

/** A required, non-blank string parameter. */
function requiredText(value: unknown, name: string): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_cbb needs a non-empty ${name}, got ${describeValue(value)}`,
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
      `sch.place_cbb ${name} must be a finite number, got ${describeValue(value)}`,
      { param: name },
    );
  }
  return value;
}

/** A quarter turn, as the host stores it. */
function quarterTurn(value: unknown): number {
  if (typeof value !== 'number' || !ROTATIONS.includes(value as never)) {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_cbb rotation must be one of ${ROTATIONS.join(', ')}, got ${describeValue(value)}`,
      { param: 'rotation', allowed: [...ROTATIONS] },
    );
  }
  return value;
}

/** A strict boolean — `'true'` is not a decision. */
function strictBoolean(value: unknown, name: string): boolean {
  if (typeof value !== 'boolean') {
    throw new ActionError(
      'BAD_REQUEST',
      `sch.place_cbb ${name} must be a boolean, got ${describeValue(value)}`,
      { param: name },
    );
  }
  return value;
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

/**
 * A field of a host record: the plain property the CBB/symbol objects were
 * measured to carry, falling back to the `getState_<Name>` accessor.
 */
async function readField(obj: any, names: readonly string[]): Promise<unknown> {
  for (const name of names) {
    const plain = readMember(obj, name);
    if (plain.value !== undefined) return plain.value;
    const state = await getState(obj, name);
    if (state !== undefined) return state;
  }
  return undefined;
}

/** The project uuid the editor has focused, or `undefined` when unreadable. */
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
      `dmt_SelectControl.getCurrentDocumentInfo() threw: ${String((error as Error)?.message ?? error)}`,
      { path: 'dmt_SelectControl.getCurrentDocumentInfo' },
    );
  }
}

/**
 * Why the editor is not on the requested project/page, or `null` when it is.
 *
 * Both halves are read on every call — before the write and again after it —
 * because a placement anchors to whatever is focused, and a focus that moved
 * between the two reads means the second reading describes another page.
 */
async function contextProblem(
  eda: Eda, projectUuid: string, pageUuid: string,
): Promise<{ problem: string; detail: Record<string, unknown> } | null> {
  const focused = await focusedProjectUuid(eda);
  if (focused !== projectUuid) {
    return {
      problem: `the focused project is ${focused == null ? '(none)' : String(focused)}, `
        + `not ${projectUuid} — refusing to place a CBB into another project`,
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
      detail: {
        guard: 'page', expected: pageUuid, actual: active == null ? null : String(active),
      },
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
        + `not a schematic page (${SCHEMATIC_PAGE_TYPE}) — a CBB is placed on a page`,
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

/** One component as read through `getState_*`. */
async function componentRow(item: any): Promise<ComponentRow> {
  const [id, type, x, y, rotation, mirror] = await Promise.all(
    POSE_ACCESSORS.map((accessor) => getState(item, accessor)),
  );
  return {
    id: typeof id === 'string' ? id : null,
    type,
    x,
    y,
    rotation,
    mirror,
  };
}

/** The comparable part of a row — what "unchanged" means for an old part. */
function geometryOf(row: ComponentRow): string {
  return JSON.stringify([row.id, row.type, row.x, row.y, row.rotation, row.mirror]);
}

/**
 * Every component on the page, with its geometry, or `CONNECTOR_ERROR`.
 *
 * The completeness rule is the baseline's whole point: an unreadable field or
 * a repeated id makes the before/after comparison meaningless, so the call is
 * refused here rather than producing a diff nobody can trust.
 */
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
    const row = await componentRow(answer[index]);
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

/**
 * The CBB symbol behind the requested module, from `lib_Symbol.get`.
 *
 * An unreadable symbol is refused unless the caller passed
 * `allowUnverifiedSourceSymbol: true` — the flag exists because this sample's
 * symbol is not in `lib_Symbol` at all (038Q15), not because the check is
 * optional. When the host *does* answer, `uuid` is the identity (it must be the
 * requested one) and `libraryUuid` / `type` / `cbbUuid` are checked **when the
 * record carries them**: a field the host omits is not evidence of anything.
 */
async function verifySymbol(
  eda: Eda,
  expected: { symbolUuid: string; libraryUuid: string; cbbUuid: string; allow: boolean },
): Promise<Record<string, unknown>> {
  const ns = hostNamespace(eda, SYMBOL_NAMESPACE);
  const get = hostMethod(ns, `${SYMBOL_NAMESPACE}.get`);

  let item: any;
  try {
    item = await settle(get.call(ns, expected.symbolUuid, expected.libraryUuid));
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${expected.symbolUuid}) threw: ${String((error as Error)?.message ?? error)}`,
      { symbolUuid: expected.symbolUuid, libraryUuid: expected.libraryUuid },
    );
  }

  if (item === undefined || item === null) {
    if (!expected.allow) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `lib_Symbol.get(${expected.symbolUuid}) found nothing, so the source symbol `
          + 'cannot be verified. Pass allowUnverifiedSourceSymbol:true only when the '
          + 'symbol\'s identity is backed by another host reading (the 038Q15 sample: '
          + 'the source document shows type 17 and a CBB? designator); a placement '
          + 'made that way is reported as unverified, never as verified',
        {
          symbolUuid: expected.symbolUuid,
          libraryUuid: expected.libraryUuid,
          readable: false,
          reason: 'source-symbol-unverified',
        },
      );
    }
    return {
      source: `${SYMBOL_NAMESPACE}.get`,
      readable: false,
      mode: 'unverified-source-symbol',
      allowedBy: 'allowUnverifiedSourceSymbol',
      checked: [],
    };
  }

  const answered = await readField(item, ['uuid']);
  if (answered !== expected.symbolUuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${expected.symbolUuid}) answered uuid `
        + `${answered == null ? '(none)' : JSON.stringify(answered)} — a different symbol`,
      { symbolUuid: expected.symbolUuid, answered: answered ?? null, reason: 'symbol-mismatch' },
    );
  }
  const library = await readField(item, ['libraryUuid']);
  if (library !== undefined && library !== expected.libraryUuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `symbol ${expected.symbolUuid} belongs to library ${String(library)}, not `
        + `${expected.libraryUuid}`,
      { symbolUuid: expected.symbolUuid, libraryUuid: library, reason: 'symbol-mismatch' },
    );
  }
  const type = await readField(item, ['type']);
  if (type !== undefined && Number(type) !== CBB_SYMBOL_TYPE) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `symbol ${expected.symbolUuid} is type ${String(type)}, not ${CBB_SYMBOL_TYPE} — `
        + 'only a CBB symbol document can be placed as a block',
      { symbolUuid: expected.symbolUuid, type, reason: 'symbol-mismatch' },
    );
  }
  const cbbUuid = await readField(item, ['cbbUuid']);
  if (cbbUuid !== undefined && cbbUuid !== expected.cbbUuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `symbol ${expected.symbolUuid} binds CBB ${String(cbbUuid)}, not `
        + `${expected.cbbUuid}`,
      { symbolUuid: expected.symbolUuid, cbbUuid, reason: 'symbol-mismatch' },
    );
  }
  return {
    source: `${SYMBOL_NAMESPACE}.get`,
    readable: true,
    mode: 'direct',
    checked: ['uuid', ...(library === undefined ? [] : ['libraryUuid']),
      ...(type === undefined ? [] : ['type']), ...(cbbUuid === undefined ? [] : ['cbbUuid'])],
  };
}

/**
 * The placed block's ports, from `getAllPinsByPrimitiveId`.
 *
 * An array is mandatory — a non-array means the ports are *unknown*, and an
 * unknown port list must not be reported as "no ports". An empty array is a
 * real reading (038Q15's sample has no pins). Each field is read through the
 * type package's accessor and simply left out when the host does not expose
 * it; nothing is filled in.
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
 * `sch.place_cbb` — one re-verified CBB placement onto a guarded page.
 *
 * Success is `verified: true, partial: false`; anything that happens after the
 * host call is answered as `partial: true, verified: false` with the
 * `primitiveId`, the state that was actually read and a `problems` list. No
 * retry, no rollback, no second write: the caller decides.
 */
export const schPlaceCbb: ActionHandler = async (params, eda) => {
  const input = paramObject(params);
  assertAllowedKeys(input);

  const uuid = requiredText(input.uuid, 'uuid');
  const libraryUuid = requiredText(input.libraryUuid, 'libraryUuid');
  const expectedName = requiredText(input.expectedName, 'expectedName');
  const symbolUuid = requiredText(input.symbolUuid, 'symbolUuid');
  const projectUuid = requiredText(input.projectUuid, 'projectUuid');
  const pageUuid = requiredText(input.pageUuid, 'pageUuid');
  const x = finiteCoord(input.x, 'x');
  const y = finiteCoord(input.y, 'y');
  const rotation = quarterTurn(input.rotation);
  const mirror = strictBoolean(input.mirror, 'mirror');
  const allowUnverified = input.allowUnverifiedSourceSymbol === undefined
    ? false
    : strictBoolean(input.allowUnverifiedSourceSymbol, 'allowUnverifiedSourceSymbol');

  // --- 1. The module, by exact readback (038Q14's own action).
  const identity = await libCbbGet({ uuid, libraryUuid }, eda) as {
    found: boolean;
    libraryUuid: string | null;
    cbb: { uuid?: string; libraryUuid?: string; name?: string } | null;
  };
  if (!identity.found) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) in library ${libraryUuid} found nothing — there is no `
        + 'module to place',
      { uuid, libraryUuid, found: false },
    );
  }
  if (identity.cbb?.name !== expectedName) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) answered name `
        + `${identity.cbb?.name == null ? '(none)' : JSON.stringify(identity.cbb.name)}, `
        + `not the expected ${JSON.stringify(expectedName)}`,
      { uuid, libraryUuid, expectedName, name: identity.cbb?.name ?? null },
    );
  }

  // --- 2. The focused project and page, verbatim.
  await assertContext(eda, projectUuid, pageUuid);

  // --- 3. The source symbol, verified or explicitly declared unverified.
  const symbolVerification = await verifySymbol(eda, {
    symbolUuid, libraryUuid, cbbUuid: uuid, allow: allowUnverified,
  });

  // --- 4. The write path and the baseline, both resolved before the write.
  const components = hostNamespace(eda, COMPONENTS);
  const create = hostMethod(components, CREATE_PATH);
  const getAll = hostMethod(components, `${COMPONENTS}.getAll`);
  const before = (await inventory(getAll, components)).rows;

  // --- 5. The one write.
  let created: any;
  let createError: string | undefined;
  try {
    created = await settle(create.call(components, {
      libraryUuid,
      cbbUuid: uuid,
      uuid: symbolUuid,
    }, x, y, rotation, mirror));
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
    uuid,
    libraryUuid,
    expectedName,
    symbolUuid,
    projectUuid,
    pageUuid,
    requested: { x, y, rotation, mirror },
    symbolVerification,
    beforeCount: before.length,
    primitiveId,
    state: null,
    cbb: null,
    cbbSymbol: null,
    pins: null,
    preserved: null,
    verified: false,
    partial: true,
  };

  // --- 6. Everything after the write is read back, and every failure keeps
  // its evidence: nothing below throws.
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
      // The call answered nothing usable; the diff is the only honest source
      // for "did a block land, and which one".
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
    const changed = before.filter((old) => !after.some(
      (row) => geometryOf(row) === geometryOf(old),
    ));
    answer.preserved = changed.length === 0;
    if (changed.length) {
      problems.push(
        `${changed.length} pre-existing component(s) changed geometry: `
          + `${changed.map((row) => row.id).join(', ')}`,
      );
    }

    const instance = primitiveId
      ? after.find((row) => row.id === primitiveId)
      : undefined;
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
      if (state.x !== x || state.y !== y || state.rotation !== rotation
        || state.mirror !== mirror) {
        problems.push(
          `the placed component's pose is ${JSON.stringify({
            x: state.x, y: state.y, rotation: state.rotation, mirror: state.mirror,
          })}, not the requested ${JSON.stringify({ x, y, rotation, mirror })}`,
        );
      }

      // Identity: the block must bind the module and the symbol that were asked
      // for. Those two accessors live on the host object, not on the geometry
      // row, so the object is taken from the same fresh inventory.
      const hostInstance = latest.byId.get(primitiveId as string);
      const placedCbb = hostInstance ? await getState(hostInstance, 'Cbb') : undefined;
      const cbbUuidField = await readField(placedCbb, ['uuid', 'Uuid']);
      const cbbLibraryField = await readField(placedCbb, ['libraryUuid', 'LibraryUuid']);
      const placedSymbol = hostInstance ? await getState(hostInstance, 'CbbSymbol') : undefined;
      const symbolUuidField = await readField(placedSymbol, ['uuid', 'Uuid']);
      const symbolCbbField = await readField(placedSymbol, ['cbbUuid', 'CbbUuid']);
      const symbolLibraryField = await readField(placedSymbol, ['libraryUuid', 'LibraryUuid']);
      answer.cbb = cbbUuidField === undefined && cbbLibraryField === undefined
        ? null
        : { uuid: cbbUuidField ?? null, libraryUuid: cbbLibraryField ?? null };
      answer.cbbSymbol = symbolUuidField === undefined && symbolCbbField === undefined
        && symbolLibraryField === undefined
        ? null
        : {
          uuid: symbolUuidField ?? null,
          cbbUuid: symbolCbbField ?? null,
          libraryUuid: symbolLibraryField ?? null,
        };
      if (cbbUuidField !== uuid) {
        problems.push(
          `the placed component's CBB is `
            + `${cbbUuidField == null ? 'unreadable' : JSON.stringify(cbbUuidField)}, not `
            + `${JSON.stringify(uuid)}`,
        );
      }
      if (cbbLibraryField !== libraryUuid) {
        problems.push(
          `the placed component's CBB library is `
            + `${cbbLibraryField == null ? 'unreadable' : JSON.stringify(cbbLibraryField)}, not `
            + `${JSON.stringify(libraryUuid)}`,
        );
      }
      if (symbolUuidField !== symbolUuid) {
        problems.push(
          `the placed component's CBB symbol is `
            + `${symbolUuidField == null ? 'unreadable' : JSON.stringify(symbolUuidField)}, not `
            + `${JSON.stringify(symbolUuid)}`,
        );
      }
      if (symbolCbbField !== uuid) {
        problems.push(
          `the placed component's CBB symbol binds CBB `
            + `${symbolCbbField == null ? 'unreadable' : JSON.stringify(symbolCbbField)}, not `
            + `${JSON.stringify(uuid)}`,
        );
      }
      if (symbolLibraryField !== undefined && symbolLibraryField !== libraryUuid) {
        problems.push(
          `the placed component's CBB symbol library is `
            + `${JSON.stringify(symbolLibraryField)}, not ${JSON.stringify(libraryUuid)}`,
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
