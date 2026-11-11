/**
 * Native CBB (复用模块) reads: `lib.cbb.search` and `lib.cbb.get`.
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
 *    and `getCbbFileByCbbUuid` are never resolved, so a read cannot become a
 *    write by a typo.
 *
 * The API shape is the official one from `@jlceda/pro-api-types`:
 * `search(key, libraryUuid?, classification?, itemsOfPage?, page?)` and
 * `get(cbbUuid, libraryUuid?)`, both `@beta`. The five search arguments are
 * always sent in that order — `classification` stays `undefined` because this
 * action has no classification input and the host treats `undefined` as "all".
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

/** Where a search item's library uuid came from, spelled out on every item. */
const LIBRARY_IDENTITY_SOURCE = 'lib_Cbb.get';

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

/** The `lib_Cbb` namespace, or `NOT_IMPLEMENTED` naming the path. */
function cbbNamespace(eda: Eda): any {
  const read = readMember(eda, 'lib_Cbb');
  const ns = read.value;
  if (read.error !== undefined || !ns || (typeof ns !== 'object' && typeof ns !== 'function')) {
    throw new ActionError(
      'NOT_IMPLEMENTED',
      `lib_Cbb is not available in this editor version (${read.error ?? 'absent'})`,
      { path: 'lib_Cbb' },
    );
  }
  return ns;
}

/** One method of `lib_Cbb`, or `NOT_IMPLEMENTED` with the exact path. */
function cbbMethod(ns: any, name: 'search' | 'get'): any {
  const read = readMember(ns, name);
  const fn = read.value;
  if (typeof fn !== 'function') {
    throw new ActionError(
      'NOT_IMPLEMENTED',
      `lib_Cbb.${name} is not available (${read.error ?? 'not a function'})`,
      { path: `lib_Cbb.${name}` },
    );
  }
  return fn;
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
 * `lib.cbb.search` — one page of native reuse modules, every hit verified.
 *
 * `itemsOfPage` and `page` are forwarded exactly, and the host's page is
 * returned as it came; `count` is that page's length, never a library total
 * this action never read.
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

  const ns = cbbNamespace(eda);
  const search = cbbMethod(ns, 'search');
  // Resolved before the search on purpose: a host without `get` cannot verify
  // any hit, so the call is refused up front instead of after a first page.
  const get = cbbMethod(ns, 'get');

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
      answer = await get.call(ns, itemUuid, libraryUuid);
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

  const uuid = input.uuid;
  if (typeof uuid !== 'string' || uuid.trim() === '') {
    throw new ActionError(
      'BAD_REQUEST',
      `${action} needs a non-empty uuid, got ${describeValue(uuid)}`,
      { param: 'uuid' },
    );
  }
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
