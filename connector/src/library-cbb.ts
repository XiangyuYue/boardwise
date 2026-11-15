/**
 * Native CBB (复用模块) reads: `lib.cbb.search`, `lib.cbb.get`, and the 038Q14
 * reads `lib.cbb.personal`, `lib.cbb.libraries` (the workspace's *other*
 * libraries, as a list) and `lib.cbb.export` (one module's own container).
 *
 * The two actions exist so a caller can inventory the host's own reuse modules
 * **without writing anything**: an empty keyword is the documented way to walk
 * a library page by page, and every hit is confirmed by a second read before it
 * is reported. The point of that second read is identity, not decoration — a
 * search item and a get item are two separate host answers, and a bridge that
 * returned the search answer alone would be repeating whatever the index
 * claimed. So each search item is re-read through `lib_Cbb.get`: the same uuid
 * must come back, the module's library uuid must be a non-empty string, and it
 * must match both the caller's explicit library (when one was given) and the
 * item's own `libraryUuid` (when the host put one there).
 *
 * Three rules the module keeps on purpose:
 *
 * 1. **An unreadable library is not an empty one.** A non-array answer, an
 *    over-sized page, a malformed item, a `get` that finds nothing, or two
 *    answers that disagree about identity are all `CONNECTOR_ERROR`. Nothing
 *    is dropped and nothing is skipped; a caller that reads `count: 0` may
 *    conclude "this library has nothing", so that number has to mean it.
 * 2. **No parameter is rewritten into a default.** `query` is passed verbatim
 *    (empty string included — that is the inventory entry point), `limit` and
 *    `page` are integers or the call is refused, and `libraryUuid` is either
 *    the caller's own value or `undefined`. The system-library default belongs
 *    to the host, so an omitted library is passed as `undefined` rather than
 *    invented.
 * 3. **Only the reading half of `lib_Cbb` is ever touched.** `create` /
 *    `modify` / `delete` / `copy` / `openProjectInEditor` / `openSymbolInEditor`
 *    and `lib_Cbb.getCbbFileByCbbUuid` are never resolved, so a read cannot
 *    become a write by a typo. The container read 038Q14 adds goes through
 *    `sys_FileManager.getCbbFileByCbbUuid` instead — a different namespace, and
 *    the one the declaration puts that call in.
 *
 * 038Q14 adds the reads an archive needs: `lib.cbb.personal` (which library is
 * *this workspace's* personal one — `lib_LibrariesList.getPersonalLibraryUuid`),
 * `lib.cbb.libraries` (the other libraries, by name and uuid) and
 * `lib.cbb.export` (one module's own container, `sys_FileManager.
 * getCbbFileByCbbUuid`). Two rules those keep on purpose: the export re-reads
 * the module through `lib.cbb.get` **first**, because bytes without a verified
 * identity are bytes of an unknown module; and the container is handed back
 * whole and opaque — nothing is unpacked, no internal record format is guessed,
 * and neither the library nor the project is written. Every host answer that
 * cannot be described exactly (an *unresolved* personal library, a zero-byte or
 * oversized file, a declared size that the bytes do not match) is a
 * `CONNECTOR_ERROR` rather than a plausible-looking payload.
 *
 * The API shape is the official one from `@jlceda/pro-api-types`:
 * `search(key, libraryUuid?, classification?, itemsOfPage?, page?)` and
 * `get(cbbUuid, libraryUuid?)`, both `@beta`; `getPersonalLibraryUuid()`
 * (`@public`) and `getCbbFileByCbbUuid(cbbUuid, libraryUuid?, props?)`
 * (`@beta`). The five search arguments are always sent in that order —
 * `classification` stays `undefined` because this action has no classification
 * input and the host treats `undefined` as "all".
 *
 * `eda` and `ActionHandler` are imported **type-only** from `actions.ts`: that
 * module imports these handlers for its registry, so a value import here would
 * be a runtime cycle. `ActionError` is a value import from `protocol.ts`, which
 * imports nothing of ours.
 */

import { ActionError } from './protocol';
import type { ActionHandler, Eda } from './actions';

/** Parameters `lib.cbb.search` accepts — anything else is refused by name. */
const SEARCH_KEYS = ['query', 'libraryUuid', 'limit', 'page'] as const;
/** Parameters `lib.cbb.get` accepts. */
const GET_KEYS = ['uuid', 'libraryUuid'] as const;
/** Parameters `lib.cbb.export` accepts — both required, nothing else. */
const EXPORT_KEYS = ['uuid', 'libraryUuid'] as const;

/** Where a search item's library uuid came from, spelled out on every item. */
const LIBRARY_IDENTITY_SOURCE = 'lib_Cbb.get';

/** The namespace and method the personal library is read from. */
const LIBRARIES_LIST = 'lib_LibrariesList';
const PERSONAL_LIBRARY_METHOD = 'getPersonalLibraryUuid';
const PERSONAL_LIBRARY_SOURCE = `${LIBRARIES_LIST}.${PERSONAL_LIBRARY_METHOD}`;
/** The namespace and method the *other* libraries are listed through. */
const ALL_LIBRARIES_METHOD = 'getAllLibrariesList';
const ALL_LIBRARIES_SOURCE = `${LIBRARIES_LIST}.${ALL_LIBRARIES_METHOD}`;

/** The namespace and method one module's container is fetched from. */
const FILE_MANAGER = 'sys_FileManager';
const CBB_FILE_METHOD = 'getCbbFileByCbbUuid';
const CBB_FILE_SOURCE = `${FILE_MANAGER}.${CBB_FILE_METHOD}`;
/**
 * The container type the export asks for — fixed, because the caller asked for
 * an `.epro2` by calling *this* action.
 *
 * The **file name is not fixed here**: `getCbbFileByCbbUuid`'s `fileName` is
 * documented as 复用模块名 (`@jlceda/pro-api-types` index.d.ts:17087), i.e. the
 * module's own name, so the export passes the name `lib_Cbb.get` just read back
 * and refuses to fetch anything when that name is missing. A hard-coded name
 * would be a name the host does not know the module by.
 */
const CBB_FILE_TYPE = 'epro2';
/**
 * The ceiling on one export, and the reason it is a gate rather than a warning:
 * the bytes travel as one base64 string inside one WebSocket frame, so an
 * unbounded file is an unbounded allocation on both sides of the wire. 16 MiB
 * is the batch's stated limit; a module bigger than that is a caller's problem
 * to solve by a path this action does not have.
 */
const CBB_FILE_MAX_BYTES = 16 * 1024 * 1024;
/** The permission the declaration names for the export (团队模块 > 下载模块). */
const CBB_FILE_GATE = '团队模块 > 下载模块 — getCbbFileByCbbUuid';

/**
 * Read one member without letting an exotic object cost the call.
 *
 * The host hands out objects whose property reads can throw (see `readMember`
 * in `actions.ts`, where the same hazard was measured), so every lookup of a
 * namespace or a method goes through here instead of through `obj.name`.
 */
function readMember(obj: any, key: string): { value?: any; error?: string } {
  try {
    return { value: obj?.[key] };
  } catch (error) {
    return { error: String((error as Error)?.message ?? error) };
  }
}

/** A short, JSON-safe description of a value — for error messages only. */
function describeValue(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return `an array of ${value.length}`;
  if (typeof value === 'object') return 'an object';
  if (typeof value === 'string') return `a string of ${value.length} chars`;
  return `a ${typeof value}`;
}

/** Params are an object or the call is refused; absent means "no arguments". */
function paramObject(params: unknown, action: string): Record<string, unknown> {
  if (params === undefined || params === null) return {};
  if (typeof params !== 'object' || Array.isArray(params)) {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} params must be an object, got ${describeValue(params)}`,
    );
  }
  return params as Record<string, unknown>;
}

/**
 * Refuse any key the action does not define.
 *
 * A silently ignored parameter is a call that does something other than what
 * the caller asked for — the failure mode the whole contract is guarding
 * against, so unknown names are errors with the accepted list attached.
 */
function assertAllowedKeys(
  input: Record<string, unknown>,
  allowed: readonly string[],
  action: string,
): void {
  const unknown = Object.keys(input).filter((key) => !allowed.includes(key));
  if (unknown.length) {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} does not take ${unknown.join(', ')}; it accepts ${allowed.join(', ')}`,
      { unknown, allowed: [...allowed] },
    );
  }
}

/**
 * `libraryUuid`: omitted, or a non-empty uuid string.
 *
 * An empty string is refused rather than treated as "omitted": it is neither a
 * library nor an absence, and quietly falling back to the system library would
 * answer a question the caller did not ask.
 */
function optionalLibraryUuid(value: unknown, action: string): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== 'string') {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} libraryUuid must be a string, got ${describeValue(value)}`,
      { param: 'libraryUuid' },
    );
  }
  if (value.trim() === '') {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} libraryUuid must be a non-empty uuid when given — an empty `
        + 'string is neither omitted nor a library',
      { param: 'libraryUuid' },
    );
  }
  return value;
}

/** An integer parameter with an explicit default and a closed range. */
function integerParam(
  value: unknown,
  name: string,
  fallback: number,
  min: number,
  max: number,
  range: string,
  action: string,
): number {
  if (value === undefined) return fallback;
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} ${name} must be an integer in ${range}, got ${describeValue(value)}`,
      { param: name, type: typeof value },
    );
  }
  if (value < min || value > max) {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} ${name} must be in ${range}, got ${value}`,
      { param: name, value },
    );
  }
  return value;
}

/** The `eda.<name>` namespace object, or `NOT_IMPLEMENTED` naming the path. */
function hostNamespace(eda: Eda, name: string): any {
  const read = readMember(eda, name);
  const ns = read.value;
  if (read.error !== undefined || !ns || (typeof ns !== 'object' && typeof ns !== 'function')) {
    throw new ActionError(
      'NOT_IMPLEMENTED',
      `${name} is not available in this editor version (${read.error ?? 'absent'})`,
      { path: name },
    );
  }
  return ns;
}

/** One method of a host namespace, or `NOT_IMPLEMENTED` with the exact path. */
function hostMethod(ns: any, namespace: string, name: string): any {
  const read = readMember(ns, name);
  const fn = read.value;
  if (typeof fn !== 'function') {
    throw new ActionError(
      'NOT_IMPLEMENTED',
      `${namespace}.${name} is not available (${read.error ?? 'not a function'})`,
      { path: `${namespace}.${name}` },
    );
  }
  return fn;
}

/** The `lib_Cbb` namespace, or `NOT_IMPLEMENTED` naming the path. */
function cbbNamespace(eda: Eda): any {
  return hostNamespace(eda, 'lib_Cbb');
}

/** One method of `lib_Cbb`, or `NOT_IMPLEMENTED` with the exact path. */
function cbbMethod(ns: any, name: 'search' | 'get'): any {
  return hostMethod(ns, 'lib_Cbb', name);
}

/**
 * A required uuid parameter: one non-empty, non-blank string.
 *
 * An array is refused rather than fanned out — every one of these actions
 * answers about *one* thing, and a batch answer would make "which of these"
 * a question about position.
 */
function requiredUuid(value: unknown, name: string, action: string): string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} needs a non-empty ${name}, got ${describeValue(value)}`,
      { param: name },
    );
  }
  return value;
}

/**
 * Bytes as base64, and the one helper this module needs a copy of.
 *
 * `actions.ts` imports these handlers for its registry, so a value import back
 * into it would be a runtime cycle — hence the same chunked `btoa` written
 * here. The 8 KiB chunk is not decoration: `String.fromCharCode` has an
 * argument-count limit and a 16 MiB container must not meet it.
 */
function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  const chunk = 0x2000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

/**
 * Validate a `lib_Cbb.get` answer and return its verified identity.
 *
 * `get` answering nothing is a failure here, never a row to skip: the caller
 * asked about a uuid the search just produced, so "not found" means the two
 * host answers disagree — which is exactly the reading a silent skip would
 * destroy.
 */
function checkedCbb(
  answer: unknown,
  uuid: string,
  requestedLibraryUuid: string | undefined,
  context: Record<string, unknown>,
): { cbb: any; libraryUuid: string } {
  if (answer === undefined || answer === null) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) found nothing — a module the caller was told about `
        + 'cannot be read back, so its identity is unverified',
      { ...context, uuid, requestedLibraryUuid: requestedLibraryUuid ?? null },
    );
  }
  if (typeof answer !== 'object' || Array.isArray(answer)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) answered ${describeValue(answer)} instead of a module`,
      { ...context, uuid },
    );
  }
  const cbb = answer as Record<string, any>;

  const answeredUuid = typeof cbb.uuid === 'string' ? cbb.uuid : '';
  if (answeredUuid !== uuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) answered uuid ${JSON.stringify(answeredUuid || null)} — `
        + 'a different module, so the identity is unresolved',
      { ...context, requestedUuid: uuid, uuid: answeredUuid || null },
    );
  }

  const answeredLibrary = typeof cbb.libraryUuid === 'string' ? cbb.libraryUuid : '';
  if (!answeredLibrary) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) answered without a libraryUuid — the module's library `
        + 'cannot be verified',
      { ...context, uuid, libraryUuid: cbb.libraryUuid ?? null },
    );
  }
  if (requestedLibraryUuid !== undefined && answeredLibrary !== requestedLibraryUuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) answered library ${answeredLibrary}, but the call was `
        + `for library ${requestedLibraryUuid}`,
      {
        ...context,
        uuid,
        requestedLibraryUuid,
        libraryUuid: answeredLibrary,
      },
    );
  }
  if (!Array.isArray(cbb.boards)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) answered ${describeValue(cbb.boards)} for boards — the `
        + 'module metadata is incomplete',
      { ...context, uuid, libraryUuid: answeredLibrary },
    );
  }
  return { cbb, libraryUuid: answeredLibrary };
}

/** The public metadata of one get answer — documented fields, no host extras. */
function publicCbb(cbb: Record<string, any>): Record<string, unknown> {
  const out: Record<string, unknown> = {
    uuid: cbb.uuid,
    libraryUuid: cbb.libraryUuid,
    name: cbb.name,
    boards: cbb.boards,
  };
  if (cbb.classification !== undefined) out.classification = cbb.classification;
  if (cbb.description !== undefined) out.description = cbb.description;
  return out;
}

/** The public metadata of one search item, before the verified library joins it. */
function publicSearchItem(item: Record<string, any>): Record<string, unknown> {
  const out: Record<string, unknown> = { uuid: item.uuid, name: item.name };
  for (const key of [
    'classification',
    'description',
    'ordinal',
    'updateTimestamp',
    'ascription',
    'lastModifiedBy',
    'libraryUuid',
  ]) {
    if (item[key] !== undefined) out[key] = item[key];
  }
  return out;
}

/**
 * The `libraryUuid` value that means "the open project's own library".
 *
 * It is a scope keyword, not a uuid: `lib_Cbb.search` accepts it and returns the
 * project's local blocks, while `lib_Cbb.get` is the wrong reader for them
 * (measured 2026-11-15: `lib_Cbb.get(ca89…, 'project')` is refused even though
 * `lib_Symbol.get(ca89…, 'project')` answers the block). So the keyword selects
 * *which* reader verifies a hit — never a library uuid that gets substituted
 * for the caller's scope.
 */
const PROJECT_SCOPE = 'project';
/** Where a project-scoped hit's identity came from, spelled out on every item. */
const PROJECT_IDENTITY_SOURCE = 'lib_Symbol.get(project)';
/** The type a project-local CBB *symbol* carries (17 = block_symbol). */
const PROJECT_SYMBOL_TYPE = 17;
/** …and the `libraryType` it carries (`'2'` = the project's own library). */
const PROJECT_LIBRARY_TYPE = '2';

/** The `lib_Symbol` namespace, or `NOT_IMPLEMENTED` naming the path. */
function symbolNamespace(eda: Eda): any {
  return hostNamespace(eda, 'lib_Symbol');
}

/**
 * Validate a `lib_Symbol.get(uuid, 'project')` answer for one project-scoped hit.
 *
 * The project path needs its own reader and its own checks, and this is where
 * they live — `checkedCbb` is left exactly as it was, because the *other*
 * libraries' contract did not change and must not be relaxed by a project fix.
 * The four checks the batch requires are all here and none is optional: the same
 * uuid, a `name` string, `type === 17` and `libraryType === '2'`. A local block
 * symbol that fails one of them is a different thing wearing the same uuid, and
 * the caller would have no way to tell.
 *
 * `sourceLibraryUuid` is the *source* library the block came from, kept as a
 * separate field (如 `08be…`) — it describes provenance and is **not** the
 * caller's scope, so it is never written back into `libraryUuid`.
 */
function checkedProjectSymbol(
  answer: unknown,
  uuid: string,
  context: Record<string, unknown>,
): { symbol: any; sourceLibraryUuid?: string } {
  if (answer === undefined || answer === null) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') found nothing — a project-scoped hit the `
        + 'search returned cannot be read back, so its identity is unverified',
      { ...context, uuid, scope: PROJECT_SCOPE },
    );
  }
  if (typeof answer !== 'object' || Array.isArray(answer)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') answered ${describeValue(answer)} instead of a symbol`,
      { ...context, uuid, scope: PROJECT_SCOPE },
    );
  }
  const symbol = answer as Record<string, any>;

  const answeredUuid = typeof symbol.uuid === 'string' ? symbol.uuid : '';
  if (answeredUuid !== uuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') answered uuid `
        + `${JSON.stringify(answeredUuid || null)} — a different symbol, so the identity `
        + 'is unresolved',
      { ...context, requestedUuid: uuid, uuid: answeredUuid || null, scope: PROJECT_SCOPE },
    );
  }
  if (typeof symbol.name !== 'string') {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') answered without a name string — a project `
        + 'block cannot be identified by name',
      { ...context, uuid, name: symbol.name ?? null, scope: PROJECT_SCOPE },
    );
  }
  if (symbol.type !== PROJECT_SYMBOL_TYPE) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') answered type `
        + `${JSON.stringify(symbol.type ?? null)} instead of ${PROJECT_SYMBOL_TYPE} — this `
        + 'is not a project-local CBB symbol',
      { ...context, uuid, type: symbol.type ?? null, scope: PROJECT_SCOPE },
    );
  }
  if (symbol.libraryType !== PROJECT_LIBRARY_TYPE) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Symbol.get(${uuid}, 'project') answered libraryType `
        + `${JSON.stringify(symbol.libraryType ?? null)} instead of `
        + `${JSON.stringify(PROJECT_LIBRARY_TYPE)} — the symbol is not in the project library`,
      {
        ...context,
        uuid,
        libraryType: symbol.libraryType ?? null,
        scope: PROJECT_SCOPE,
      },
    );
  }

  const source = symbol.libraryUuid;
  const sourceLibraryUuid = typeof source === 'string' && source.trim() !== '' ? source : undefined;
  return { symbol, sourceLibraryUuid };
}

/**
 * `lib.cbb.search` — one page of native reuse modules, every hit verified.
 *
 * `itemsOfPage` and `page` are forwarded exactly, and the host's page is
 * returned as it came; `count` is that page's length, never a library total
 * this action never read.
 *
 * **Two readers, chosen by the scope the caller named (038Q16).** For a normal
 * library every hit is re-read through `lib_Cbb.get` exactly as before — same
 * calls, same checks, same messages. When `libraryUuid` is the scope keyword
 * `'project'`, `lib_Cbb.get` is not called at all (it refuses project-local
 * blocks — measured), and each hit is instead re-read through
 * `lib_Symbol.get(entry.uuid, 'project')`, which must answer the same uuid, a
 * `name` string, `type === 17` and `libraryType === '2'`. The item then reports
 * `libraryUuid: 'project'` (the caller's scope, unchanged), the host symbol's own
 * `libraryUuid` as `sourceLibraryUuid` when it has one, and
 * `libraryIdentitySource: 'lib_Symbol.get(project)'`. That source uuid is
 * provenance — it never replaces the scope.
 */
export const libCbbSearch: ActionHandler = async (params, eda) => {
  const action = 'lib.cbb.search';
  const input = paramObject(params, action);
  assertAllowedKeys(input, SEARCH_KEYS, action);

  // Empty string is legal and is not trimmed: it is the host's own "everything"
  // keyword, and any other keyword is the caller's to spell.
  const query = input.query === undefined ? '' : input.query;
  if (typeof query !== 'string') {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} query must be a string (an empty string inventories the library), `
        + `got ${describeValue(query)}`,
      { param: 'query', type: typeof query },
    );
  }
  const libraryUuid = optionalLibraryUuid(input.libraryUuid, action);
  const limit = integerParam(input.limit, 'limit', 20, 1, 100, '1..100', action);
  const page = integerParam(input.page, 'page', 1, 1, Number.MAX_SAFE_INTEGER, '>=1', action);
  const projectScope = libraryUuid === PROJECT_SCOPE;

  const ns = cbbNamespace(eda);
  const search = cbbMethod(ns, 'search');
  // Resolved before the search on purpose: a host without the reader this scope
  // needs cannot verify any hit, so the call is refused up front instead of
  // after a first page. A normal scope resolves `lib_Cbb.get`; the project scope
  // resolves `lib_Symbol.get` and leaves `lib_Cbb.get` untouched.
  const get = projectScope ? undefined : cbbMethod(ns, 'get');
  const symbolNs = projectScope ? symbolNamespace(eda) : undefined;
  const getSymbol = projectScope ? hostMethod(symbolNs, 'lib_Symbol', 'get') : undefined;

  let found: unknown;
  try {
    // Exactly five arguments, in the official order. `classification` is
    // `undefined` = all, and an omitted library stays `undefined` so the host
    // applies its own system-library default.
    found = await search.call(ns, query, libraryUuid, undefined, limit, page);
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.search(${JSON.stringify(query)}) threw: `
        + String((error as Error)?.message ?? error),
      { query, libraryUuid: libraryUuid ?? null, limit, page },
    );
  }

  if (!Array.isArray(found)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.search(${JSON.stringify(query)}) answered ${describeValue(found)} `
        + 'instead of an array — the library is unknown, not empty',
      { query, libraryUuid: libraryUuid ?? null, limit, page },
    );
  }
  if (found.length > limit) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.search(${JSON.stringify(query)}) answered ${found.length} items for `
        + `limit ${limit} — the page is bigger than the page size`,
      { query, libraryUuid: libraryUuid ?? null, limit, page, returned: found.length },
    );
  }

  const items: Record<string, unknown>[] = [];
  for (let index = 0; index < found.length; index += 1) {
    const item = found[index];
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `lib_Cbb.search item ${index} is ${describeValue(item)}, not a search item`,
        { query, limit, page, index },
      );
    }
    const row = item as Record<string, any>;
    const itemUuid = typeof row.uuid === 'string' ? row.uuid : '';
    if (!itemUuid) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `lib_Cbb.search item ${index} has no uuid — the hit cannot be identified`,
        { query, limit, page, index, uuid: row.uuid ?? null },
      );
    }
    if (typeof row.name !== 'string') {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `lib_Cbb.search item ${index} (${itemUuid}) has no name string`,
        { query, limit, page, index, uuid: itemUuid },
      );
    }

    if (projectScope) {
      // The project scope's own reader. `lib_Cbb.get` is never reached here, and
      // the entry's own `libraryUuid` is not compared: an index row for a local
      // block may carry the source library, while the scope the caller named is
      // 'project' and the symbol read is the authority on the rest.
      let answer: unknown;
      try {
        answer = await getSymbol!.call(symbolNs, itemUuid, libraryUuid);
      } catch (error) {
        throw new ActionError(
          'CONNECTOR_ERROR',
          `lib_Symbol.get(${itemUuid}, 'project') threw while verifying search item `
            + `${index}: ${String((error as Error)?.message ?? error)}`,
          { query, limit, page, index, uuid: itemUuid, scope: PROJECT_SCOPE },
        );
      }
      const verified = checkedProjectSymbol(answer, itemUuid, { query, index });
      const projected: Record<string, unknown> = {
        ...publicSearchItem(row),
        libraryUuid: PROJECT_SCOPE,
      };
      if (verified.sourceLibraryUuid !== undefined) {
        projected.sourceLibraryUuid = verified.sourceLibraryUuid;
      }
      projected.libraryIdentitySource = PROJECT_IDENTITY_SOURCE;
      items.push(projected);
      continue;
    }

    const itemLibrary = row.libraryUuid;
    if (itemLibrary !== undefined && (typeof itemLibrary !== 'string' || !itemLibrary.trim())) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `lib_Cbb.search item ${index} (${itemUuid}) carries an unusable libraryUuid `
          + `(${describeValue(itemLibrary)})`,
        { query, limit, page, index, uuid: itemUuid },
      );
    }

    let answer: unknown;
    try {
      answer = await get!.call(ns, itemUuid, libraryUuid);
    } catch (error) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `lib_Cbb.get(${itemUuid}) threw while verifying search item ${index}: `
          + String((error as Error)?.message ?? error),
        { query, limit, page, index, uuid: itemUuid },
      );
    }
    const verified = checkedCbb(answer, itemUuid, libraryUuid, {
      query,
      index,
    });
    if (itemLibrary !== undefined && itemLibrary !== verified.libraryUuid) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `lib_Cbb.search item ${index} (${itemUuid}) claims library ${itemLibrary}, `
          + `but lib_Cbb.get says ${verified.libraryUuid}`,
        {
          query,
          limit,
          page,
          index,
          uuid: itemUuid,
          searchLibraryUuid: itemLibrary,
          getLibraryUuid: verified.libraryUuid,
        },
      );
    }

    items.push({
      ...publicSearchItem(row),
      libraryUuid: verified.libraryUuid,
      libraryIdentitySource: LIBRARY_IDENTITY_SOURCE,
    });
  }

  return {
    query,
    libraryUuid: libraryUuid ?? null,
    limit,
    page,
    count: items.length,
    items,
    source: 'lib_Cbb.search',
    apiStatus: 'beta',
  };
};

/**
 * `lib.cbb.get` — one native reuse module's identity and `boards` metadata.
 *
 * Nothing is opened: the official `openProjectInEditor` / `openSymbolInEditor`
 * are never touched, so this action cannot move the editor's focus or discard
 * unsaved work. A uuid the host does not know is a normal answer
 * (`found: false`), not an error — but a uuid that comes back as *another*
 * module, or without a library, is.
 */
export const libCbbGet: ActionHandler = async (params, eda) => {
  const action = 'lib.cbb.get';
  const input = paramObject(params, action);
  assertAllowedKeys(input, GET_KEYS, action);

  const uuid = requiredUuid(input.uuid, 'uuid', action);
  const libraryUuid = optionalLibraryUuid(input.libraryUuid, action);

  const ns = cbbNamespace(eda);
  const get = cbbMethod(ns, 'get');

  let answer: unknown;
  try {
    // The second argument is always supplied; `undefined` is how the host is
    // told to use its own system-library default.
    answer = await get.call(ns, uuid, libraryUuid);
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) threw: ${String((error as Error)?.message ?? error)}`,
      { uuid, libraryUuid: libraryUuid ?? null },
    );
  }

  if (answer === undefined || answer === null) {
    return {
      uuid,
      libraryUuid: libraryUuid ?? null,
      found: false,
      cbb: null,
      source: 'lib_Cbb.get',
      apiStatus: 'beta',
    };
  }

  const verified = checkedCbb(answer, uuid, libraryUuid, {});
  return {
    uuid,
    libraryUuid: verified.libraryUuid,
    found: true,
    cbb: publicCbb(verified.cbb),
    source: 'lib_Cbb.get',
    apiStatus: 'beta',
  };
};

/**
 * `lib.cbb.personal` — the uuid of *this workspace's* personal library.
 *
 * The declaration (`lib_LibrariesList.getPersonalLibraryUuid`, `@public`) says
 * a private deployment always answers `undefined`; it does **not** say the
 * converse, so `undefined` from a public build is *unresolved*, not "no personal
 * library" and not a diagnosis. That distinction is the whole reason this action
 * exists rather than a caller probing for itself: the honest answer is
 * `CONNECTOR_ERROR` with `detail.reason: 'personal-library-unresolved'`, and an
 * unresolved uuid is never evidence that a library is empty. An absent
 * namespace/method is `NOT_IMPLEMENTED` with the exact path, and a blank or
 * non-string answer is refused with the same care.
 */
export const libCbbPersonal: ActionHandler = async (params, eda) => {
  const action = 'lib.cbb.personal';
  const input = paramObject(params, action);
  const unknownKeys = Object.keys(input);
  if (unknownKeys.length) {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} takes no parameters, got ${unknownKeys.join(', ')}`,
      { unknown: unknownKeys },
    );
  }

  const ns = hostNamespace(eda, LIBRARIES_LIST);
  const read = hostMethod(ns, LIBRARIES_LIST, PERSONAL_LIBRARY_METHOD);

  let answer: unknown;
  try {
    answer = await read.call(ns);
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${PERSONAL_LIBRARY_SOURCE}() threw: ${String((error as Error)?.message ?? error)}`,
      { path: PERSONAL_LIBRARY_SOURCE, thrown: true },
    );
  }

  if (answer === undefined || answer === null) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${PERSONAL_LIBRARY_SOURCE}() answered ${answer === null ? 'null' : 'undefined'} — `
        + 'no personal-library uuid was resolved in this workspace/session. The type '
        + 'declaration only says a *private deployment* always answers undefined, so '
        + 'this answer is not a diagnosis of the cause here (host state, workspace, '
        + 'sign-in and grants all remain possible); an unresolved uuid is also not '
        + 'evidence that a library is empty',
      { path: PERSONAL_LIBRARY_SOURCE, libraryUuid: null, reason: 'personal-library-unresolved' },
    );
  }
  if (typeof answer !== 'string') {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${PERSONAL_LIBRARY_SOURCE}() answered ${describeValue(answer)} instead of a `
        + 'library uuid',
      { path: PERSONAL_LIBRARY_SOURCE, libraryUuid: answer },
    );
  }
  if (answer.trim() === '') {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${PERSONAL_LIBRARY_SOURCE}() answered an empty string — a blank uuid is neither `
        + 'a library nor an absence, so the personal library is unresolved',
      { path: PERSONAL_LIBRARY_SOURCE, libraryUuid: answer },
    );
  }

  return {
    libraryUuid: answer,
    source: PERSONAL_LIBRARY_SOURCE,
    apiStatus: 'public',
  };
};

/**
 * `lib.cbb.libraries` — the library list *other than* the four special ones.
 *
 * The declaration (`lib_LibrariesList.getAllLibrariesList`, `@public`) also says
 * what the list is **not**: system, personal, project and favourite libraries
 * are excluded by design and have their own single-uuid reads. So this action is
 * a list of the caller's other libraries — it is not a substitute for
 * `lib.cbb.personal`, and reading it neither writes nor registers a library.
 *
 * The two rules that keep `count` meaningful:
 *
 * 1. **A non-array answer is unknown, not empty.** Empty is a real reading
 *    (`count: 0`, `items: []`) and is reported as such; a `undefined`, an object
 *    or a string is `CONNECTOR_ERROR`, because a caller that reads `0` will
 *    conclude the workspace has no libraries.
 * 2. **Identity is per item and unique.** Every item needs a non-blank `uuid`
 *    and a string `name`, and no uuid may appear twice — a duplicate would make
 *    "which library is that?" a question about position, and any later
 *    per-library read would answer about an unnamed one.
 */
export const libCbbLibraries: ActionHandler = async (params, eda) => {
  const action = 'lib.cbb.libraries';
  const input = paramObject(params, action);
  const unknownKeys = Object.keys(input);
  if (unknownKeys.length) {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} takes no parameters, got ${unknownKeys.join(', ')}`,
      { unknown: unknownKeys },
    );
  }

  const ns = hostNamespace(eda, LIBRARIES_LIST);
  const read = hostMethod(ns, LIBRARIES_LIST, ALL_LIBRARIES_METHOD);

  let answer: unknown;
  try {
    answer = await read.call(ns);
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${ALL_LIBRARIES_SOURCE}() threw: ${String((error as Error)?.message ?? error)}`,
      { path: ALL_LIBRARIES_SOURCE, thrown: true },
    );
  }

  if (!Array.isArray(answer)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${ALL_LIBRARIES_SOURCE}() answered ${describeValue(answer)} instead of an array — `
        + 'the library list is unknown, not empty',
      { path: ALL_LIBRARIES_SOURCE },
    );
  }

  const items: { uuid: string; name: string }[] = [];
  const seen = new Map<string, number>();
  for (let index = 0; index < answer.length; index += 1) {
    const row = answer[index];
    if (!row || typeof row !== 'object' || Array.isArray(row)) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `${ALL_LIBRARIES_SOURCE}() item ${index} is ${describeValue(row)}, not a library`,
        { path: ALL_LIBRARIES_SOURCE, index },
      );
    }
    const entry = row as Record<string, unknown>;
    const uuid = typeof entry.uuid === 'string' ? entry.uuid : '';
    if (uuid.trim() === '') {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `${ALL_LIBRARIES_SOURCE}() item ${index} has no uuid — the library cannot be named`,
        { path: ALL_LIBRARIES_SOURCE, index, uuid: entry.uuid ?? null },
      );
    }
    if (typeof entry.name !== 'string') {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `${ALL_LIBRARIES_SOURCE}() item ${index} (${uuid}) has no name string`,
        { path: ALL_LIBRARIES_SOURCE, index, uuid },
      );
    }
    const first = seen.get(uuid);
    if (first !== undefined) {
      throw new ActionError(
        'CONNECTOR_ERROR',
        `${ALL_LIBRARIES_SOURCE}() lists uuid ${uuid} twice (items ${first} and ${index}) — `
          + 'a duplicated library cannot be told apart by position',
        { path: ALL_LIBRARIES_SOURCE, uuid, indexes: [first, index] },
      );
    }
    seen.set(uuid, index);
    items.push({ uuid, name: entry.name });
  }

  return {
    items,
    count: items.length,
    source: ALL_LIBRARIES_SOURCE,
    apiStatus: 'public',
  };
};

/**
 * `lib.cbb.export` — one native reuse module's own `.epro2` container.
 *
 * Two steps, in this order and not the other way round:
 *
 * 1. **Identity first.** The module is re-read through `lib.cbb.get` with the
 *    caller's explicit uuid *and* library, so `uuid`, `libraryUuid`, `boards`
 *    and "it is in the library you named" are all confirmed by a second host
 *    answer before a single byte is fetched. Bytes without a verified identity
 *    are the bytes of a module nobody can name, and the caller would have no way
 *    to notice the difference. `found: false` is therefore an error here, not
 *    the normal answer it is for `lib.cbb.get`.
 * 2. **One declared call, and the name is the module's.** `getCbbFileByCbbUuid(
 *    uuid, libraryUuid, {fileName, fileType})`, where `fileType` is fixed
 *    (`epro2` — the container the caller asked this action for) and
 *    `fileName` is **the name `lib_Cbb.get` just returned**, passed verbatim:
 *    the declaration documents that argument as 复用模块名
 *    (`@jlceda/pro-api-types` index.d.ts:17087), so a hard-coded name would be
 *    a name the host does not know the module by. A module whose name is
 *    missing or blank is refused *before* the file call, because there is then
 *    no name to ask with.
 *
 * The payload is **opaque**: the bytes are returned whole as base64 and nothing
 * opens, unpacks, converts or interprets them, so no internal record format is
 * guessed here. Four host answers are refused rather than reported as a
 * smaller success: `undefined`/`null` (the declaration's own "数据获取失败"), a
 * declared `size` that is not a safe integer (an unreadable length cannot be
 * checked against the bytes), a zero-byte or over-16-MiB file, and an
 * `arrayBuffer()` whose length disagrees with the declared size — a file that
 * changed while it was being read is not the file that was identified.
 *
 * Nothing is written: no library entry, no project, no page, and the module is
 * never opened in the editor.
 */
export const libCbbExport: ActionHandler = async (params, eda) => {
  const action = 'lib.cbb.export';
  const input = paramObject(params, action);
  assertAllowedKeys(input, EXPORT_KEYS, action);

  const uuid = requiredUuid(input.uuid, 'uuid', action);
  const requestedLibrary = requiredUuid(input.libraryUuid, 'libraryUuid', action);

  // --- 1. Identity and the name, from a second host answer.
  const identity = (await libCbbGet({ uuid, libraryUuid: requestedLibrary }, eda)) as {
    found: boolean;
    libraryUuid: string | null;
    cbb: { name?: unknown } | null;
  };
  if (!identity.found || !identity.libraryUuid) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${action} refused: lib_Cbb.get(${uuid}) in library ${requestedLibrary} answered `
        + 'nothing, so the container cannot be attributed to a module',
      { uuid, libraryUuid: requestedLibrary, found: false },
    );
  }
  const libraryUuid = identity.libraryUuid;
  // The file name the host declares for this call **is** the module's own name.
  // A blank one is an error here, not something to fill in from a guess.
  const fileName = typeof identity.cbb?.name === 'string' ? identity.cbb.name : '';
  if (fileName.trim() === '') {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `lib_Cbb.get(${uuid}) answered without a usable name — the declaration documents `
        + "this call's fileName as 复用模块名 (the module's own name), so there is no name "
        + 'to ask the host for and no container can be fetched',
      { uuid, libraryUuid, name: identity.cbb?.name ?? null },
    );
  }

  // --- 2. The container.
  const fileManager = hostNamespace(eda, FILE_MANAGER);
  const fetchFile = hostMethod(fileManager, FILE_MANAGER, CBB_FILE_METHOD);

  let file: unknown;
  try {
    file = await fetchFile.call(fileManager, uuid, libraryUuid, {
      fileName,
      fileType: CBB_FILE_TYPE,
    });
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) threw ${String((error as Error)?.message ?? error)} — `
        + 'the host\'s own words are kept verbatim: the connector cannot see this '
        + "extension's grants, so the throw is a fact about this call rather than a "
        + 'diagnosis of why. Re-check the gate the type package documents for it '
        + `("${CBB_FILE_GATE}") before reading the message as a permission problem`,
      {
        uuid,
        libraryUuid,
        path: CBB_FILE_SOURCE,
        thrown: true,
        gate: CBB_FILE_GATE,
      },
    );
  }
  if (file === undefined || file === null) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) answered ${file === null ? 'null' : 'undefined'} — the `
        + 'declaration documents that as "the file data could not be fetched", so nothing '
        + 'was exported',
      { uuid, libraryUuid, path: CBB_FILE_SOURCE, empty: true },
    );
  }

  const declared = readMember(file, 'size');
  const size = declared.value;
  if (typeof size !== 'number' || !Number.isSafeInteger(size)) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) returned a file whose size is `
        + `${declared.error ?? describeValue(size)}, not a safe integer — an unreadable `
        + 'length cannot be checked against the bytes',
      { uuid, libraryUuid, path: CBB_FILE_SOURCE, size: size ?? null },
    );
  }
  if (size <= 0) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) returned a zero-byte file — an empty export is a `
        + 'failed export, not a small one',
      { uuid, libraryUuid, path: CBB_FILE_SOURCE, size },
    );
  }
  if (size > CBB_FILE_MAX_BYTES) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) returned ${size} bytes, over the ${CBB_FILE_MAX_BYTES}-byte `
        + `(${CBB_FILE_MAX_BYTES / (1024 * 1024)} MiB) ceiling this action carries`,
      { uuid, libraryUuid, path: CBB_FILE_SOURCE, size, maxBytes: CBB_FILE_MAX_BYTES },
    );
  }

  const arrayBuffer = readMember(file, 'arrayBuffer');
  if (typeof arrayBuffer.value !== 'function') {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) returned a file with no arrayBuffer() — its bytes `
        + 'cannot be read',
      { uuid, libraryUuid, path: CBB_FILE_SOURCE, observed: arrayBuffer.error ?? typeof file },
    );
  }
  let bytes: Uint8Array;
  try {
    bytes = new Uint8Array(await arrayBuffer.value.call(file));
  } catch (error) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) file bytes could not be read: `
        + `${String((error as Error)?.message ?? error)}`,
      { uuid, libraryUuid, path: CBB_FILE_SOURCE, thrown: true },
    );
  }
  if (bytes.byteLength !== size) {
    throw new ActionError(
      'CONNECTOR_ERROR',
      `${CBB_FILE_SOURCE}(${uuid}) handed over ${bytes.byteLength} bytes for a file it `
        + `declared as ${size} — the bytes changed while they were read, so this is not `
        + 'the container that was identified',
      {
        uuid,
        libraryUuid,
        path: CBB_FILE_SOURCE,
        size,
        readBytes: bytes.byteLength,
      },
    );
  }

  return {
    uuid,
    libraryUuid,
    format: CBB_FILE_TYPE,
    size,
    base64: bytesToBase64(bytes),
    source: CBB_FILE_SOURCE,
    apiStatus: 'beta',
  };
};
