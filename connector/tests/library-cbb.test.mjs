/**
 * 038Q1: the native CBB (复用模块) reads — `lib.cbb.search` and `lib.cbb.get`.
 *
 * The batch adds two read-only actions over the host's own reuse modules. What
 * this file pins, and why each one is here rather than left to the live run:
 *
 * 1. **The call shape** — exactly five arguments to `lib_Cbb.search`, in the
 *    official order, with `classification` as `undefined` and an omitted
 *    library as `undefined` (the host's system-library default). A shorter or
 *    reordered call would move `limit` into the classification slot and the
 *    page size would silently become "all".
 * 2. **An empty keyword is the inventory entry point** — `query` is forwarded
 *    verbatim, empty string included, and never trimmed or replaced.
 * 3. **An unreadable library is not an empty library** — a non-array answer, a
 *    page bigger than `limit`, a malformed item, a `get` that finds nothing and
 *    two answers that disagree about identity are all errors. Nothing is
 *    skipped, so `count: 0` only ever means "the host said nothing is here".
 * 4. **Identity is verified, not assumed** — every hit is re-read through
 *    `lib_Cbb.get` and must come back with the same uuid, a non-empty library
 *    uuid, and a library that matches both the caller's request and the item's
 *    own claim when one is present.
 * 5. **Only the reading half is reached** — every writing member of `lib_Cbb`
 *    (`create` / `delete` / `modify` / `copy` / `openProjectInEditor` /
 *    `openSymbolInEditor` / `getCbbFileByCbbUuid`) is a loud tripwire, and a
 *    successful page must leave it untouched.
 * 6. **038Q14's two reads** (`lib.cbb.personal`, `lib.cbb.export`) — a personal
 *    library uuid that is absent is an error rather than an empty string, and an
 *    export is refused before it fetches anything unless `lib_Cbb.get` has just
 *    confirmed the module *and* its library; afterwards the container has to be
 *    non-empty, at most 16 MiB, and its declared size has to match the bytes
 *    handed over. The payload is base64 of those bytes and nothing here
 *    unpacks, converts or renames them.
 *
 * Everything here goes through the real `buildHandlers()` registry, so a
 * handler that exists but was never registered fails these tests too. All
 * offline, against a fake `eda`; what the real host answers is a live question
 * this file deliberately does not claim to have answered.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

/** Writing / opening members of `lib_Cbb` — never reachable from these reads. */
const FORBIDDEN = [
  'create',
  'delete',
  'modify',
  'copy',
  'openProjectInEditor',
  'openSymbolInEditor',
  'getCbbFileByCbbUuid',
];

/** A fake `lib_Cbb` namespace that records every call it is given. */
function fakeLibCbb({ search, get } = {}) {
  const calls = { search: [], get: [], forbidden: [] };
  const ns = {
    async search(...args) {
      calls.search.push(args);
      return search ? search(...args) : [];
    },
    async get(...args) {
      calls.get.push(args);
      return get ? get(...args) : undefined;
    },
  };
  for (const name of FORBIDDEN) {
    ns[name] = (...args) => {
      calls.forbidden.push([name, args]);
      throw new Error(`lib_Cbb.${name} must never be reached by a read`);
    };
  }
  return { ns, calls };
}

/** A search hit, as `ILIB_CbbSearchItem` declares it. */
function hit(uuid, libraryUuid = 'lib-sys', extra = {}) {
  return {
    uuid,
    libraryUuid,
    name: `name-${uuid}`,
    ordinal: 1,
    updateTimestamp: 1700000000000,
    ascription: 'system',
    lastModifiedBy: 'someone',
    ...extra,
  };
}

/** A full module, as `ILIB_CbbItem` declares it. */
function cbbItem(uuid, libraryUuid = 'lib-sys', extra = {}) {
  return {
    uuid,
    libraryUuid,
    name: `name-${uuid}`,
    boards: [{ name: 'board-1', parentProjectUuid: 'proj-1' }],
    ...extra,
  };
}

/** Run one registered action by name, exactly as the daemon would. */
async function run(eda, action, params) {
  const handlers = buildHandlers(eda);
  assert.equal(typeof handlers[action], 'function', `${action} is not registered`);
  return handlers[action](params);
}

/** Reject with the ActionError; fail if the call unexpectedly succeeded. */
async function failure(promise) {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  assert.fail('expected the action to fail, but it answered');
}

/** The expressive single line of an ActionError, for messages in assertions. */
const line = (error) => `${error.code}: ${error.message}`;

// --------------------------------------------------------------------------
// lib.cbb.search — the call shape
// --------------------------------------------------------------------------

test('search sends exactly the official five arguments, with defaults', async () => {
  const { ns, calls } = fakeLibCbb({
    search: () => [hit('c1')],
    get: () => cbbItem('c1'),
  });
  const answer = await run({ lib_Cbb: ns }, 'lib.cbb.search', {});

  assert.equal(calls.search.length, 1);
  const args = calls.search[0];
  assert.equal(args.length, 5, 'the host signature has five parameters');
  assert.equal(args[0], '', 'an omitted query is the empty inventory keyword');
  assert.equal(args[1], undefined, 'no library uuid is invented — the host default applies');
  assert.equal(args[2], undefined, 'classification stays undefined = all');
  assert.equal(args[3], 20, 'limit defaults to 20');
  assert.equal(args[4], 1, 'page defaults to 1');

  assert.deepEqual(calls.get, [['c1', undefined]], 'the hit is re-read without a library');
  assert.deepEqual(answer, {
    query: '',
    libraryUuid: null,
    limit: 20,
    page: 1,
    count: 1,
    items: [
      {
        uuid: 'c1',
        name: 'name-c1',
        ordinal: 1,
        updateTimestamp: 1700000000000,
        ascription: 'system',
        lastModifiedBy: 'someone',
        libraryUuid: 'lib-sys',
        libraryIdentitySource: 'lib_Cbb.get',
      },
    ],
    source: 'lib_Cbb.search',
    apiStatus: 'beta',
  });
  assert.deepEqual(calls.forbidden, []);
});

test('search forwards query, library and page verbatim', async () => {
  const { ns, calls } = fakeLibCbb({
    search: () => [hit('c9', 'lib-user')],
    get: () => cbbItem('c9', 'lib-user'),
  });
  const answer = await run({ lib_Cbb: ns }, 'lib.cbb.search', {
    query: ' AMS1117 ',
    libraryUuid: 'lib-user',
    limit: 5,
    page: 3,
  });

  assert.deepEqual(calls.search[0], [' AMS1117 ', 'lib-user', undefined, 5, 3]);
  assert.deepEqual(calls.get, [['c9', 'lib-user']]);
  assert.equal(answer.query, ' AMS1117 ', 'the keyword is not trimmed for the caller');
  assert.equal(answer.libraryUuid, 'lib-user');
  assert.equal(answer.limit, 5);
  assert.equal(answer.page, 3);
  assert.equal(answer.count, 1);
  assert.equal(answer.items[0].libraryUuid, 'lib-user');
});

test('an empty page is an empty answer, not a failure', async () => {
  const { ns, calls } = fakeLibCbb({ search: () => [] });
  const answer = await run({ lib_Cbb: ns }, 'lib.cbb.search', { query: 'nothing-matches' });

  assert.equal(answer.count, 0);
  assert.deepEqual(answer.items, []);
  assert.equal(answer.query, 'nothing-matches');
  assert.equal(calls.get.length, 0, 'no hit means no identity to verify');
});

test('count is the page size, never a library total', async () => {
  const { ns } = fakeLibCbb({
    search: (query, libraryUuid, classification, limit) =>
      [hit('c1', 'lib-sys'), hit('c2', 'lib-sys')].slice(0, limit),
    get: (uuid) => cbbItem(uuid, 'lib-sys'),
  });
  const answer = await run({ lib_Cbb: ns }, 'lib.cbb.search', { limit: 2, page: 4 });

  assert.equal(answer.count, 2);
  assert.equal(answer.items.length, 2);
  assert.equal(answer.page, 4);
  assert.equal(answer.limit, 2);
});

// --------------------------------------------------------------------------
// lib.cbb.search — an unreadable library is not an empty one
// --------------------------------------------------------------------------

test('a non-array search answer is CONNECTOR_ERROR, not an empty library', async () => {
  for (const answerValue of [undefined, null, {}, 'no', 3]) {
    const { ns, calls } = fakeLibCbb({ search: () => answerValue });
    const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));
    assert.equal(error.code, 'CONNECTOR_ERROR', `answer ${JSON.stringify(answerValue)}`);
    assert.match(error.message, /unknown, not empty/);
    assert.equal(calls.get.length, 0);
  }
});

test('a page larger than limit is CONNECTOR_ERROR', async () => {
  const { ns } = fakeLibCbb({
    search: () => [hit('c1'), hit('c2'), hit('c3')],
    get: (uuid) => cbbItem(uuid),
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', { limit: 2 }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /3 items for limit 2/);
});

test('malformed search items are CONNECTOR_ERROR, never skipped', async () => {
  const cases = [
    [null, /is null, not a search item/],
    [[hit('c1')], /not a search item/],
    [{ name: 'no uuid' }, /has no uuid/],
    [{ uuid: '', name: 'empty uuid' }, /has no uuid/],
    [{ uuid: 'c1', name: 7 }, /has no name string/],
    [{ uuid: 'c1', name: 'x', libraryUuid: 5 }, /unusable libraryUuid|instead of an array|answered/],
  ];
  for (const [item, pattern] of cases) {
    const { ns, calls } = fakeLibCbb({
      search: () => [item],
      get: () => cbbItem('c1'),
    });
    const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(item));
    assert.match(error.message, pattern, JSON.stringify(item));
    assert.equal(calls.get.length, 0, `no unidentifiable hit is sent to get (${JSON.stringify(item)})`);
  }
});

test('a hit the host cannot read back is an error, not a silently dropped row', async () => {
  const { ns, calls } = fakeLibCbb({
    search: () => [hit('c1')],
    get: () => undefined,
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /c1/);
  assert.match(error.message, /found nothing/);
  assert.equal(error.detail.index, 0, 'the caller can tell which hit failed to verify');
  assert.equal(calls.get.length, 1);
});

test('get answering a different module is CONNECTOR_ERROR', async () => {
  const { ns } = fakeLibCbb({
    search: () => [hit('c1')],
    get: () => cbbItem('c2'),
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /a different module/);
  assert.equal(error.detail.requestedUuid, 'c1');
  assert.equal(error.detail.uuid, 'c2');
});

test('get answering without a libraryUuid is CONNECTOR_ERROR', async () => {
  const { ns } = fakeLibCbb({
    search: () => [hit('c1')],
    get: () => cbbItem('c1', ''),
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /without a libraryUuid/);
});

test('get disagreeing with the requested library is CONNECTOR_ERROR', async () => {
  const { ns } = fakeLibCbb({
    search: () => [hit('c1', 'lib-user')],
    get: () => cbbItem('c1', 'lib-sys'),
  });
  const error = await failure(
    run({ lib_Cbb: ns }, 'lib.cbb.search', { libraryUuid: 'lib-user' }),
  );
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /lib-sys/);
  assert.equal(error.detail.requestedLibraryUuid, 'lib-user');
});

test('a hit claiming another library than get reports is CONNECTOR_ERROR', async () => {
  const { ns } = fakeLibCbb({
    search: () => [hit('c1', 'lib-a')],
    get: () => cbbItem('c1', 'lib-b'),
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /claims library lib-a/);
  assert.equal(error.detail.searchLibraryUuid, 'lib-a');
  assert.equal(error.detail.getLibraryUuid, 'lib-b');
});

test('a host that throws is CONNECTOR_ERROR carrying the message', async () => {
  const { ns } = fakeLibCbb({
    search: () => {
      throw new Error('cbb index unavailable');
    },
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /cbb index unavailable/);
});

test('a get that throws during verification is CONNECTOR_ERROR', async () => {
  const { ns } = fakeLibCbb({
    search: () => [hit('c1')],
    get: () => {
      throw new Error('library locked');
    },
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', {}));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /verifying search item 0/);
  assert.match(error.message, /library locked/);
});

// --------------------------------------------------------------------------
// lib.cbb.search — parameters are refused, never rewritten
// --------------------------------------------------------------------------

test('illegal limit and page are BAD_REQUEST with no host call', async () => {
  const cases = [
    [{ limit: 0 }, /limit/],
    [{ limit: 101 }, /limit/],
    [{ limit: 1.5 }, /limit/],
    [{ limit: '20' }, /limit/],
    [{ limit: null }, /limit/],
    [{ page: 0 }, /page/],
    [{ page: -1 }, /page/],
    [{ page: 2.5 }, /page/],
    [{ page: '1' }, /page/],
  ];
  for (const [params, pattern] of cases) {
    const { ns, calls } = fakeLibCbb({ search: () => [] });
    const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', params));
    assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(params));
    assert.match(error.message, pattern);
    assert.equal(calls.search.length, 0, `nothing was searched for ${JSON.stringify(params)}`);
  }
});

test('a non-string query or libraryUuid is BAD_REQUEST', async () => {
  const cases = [
    [{ query: 5 }, /query must be a string/],
    [{ query: null }, /query must be a string/],
    [{ libraryUuid: 5 }, /libraryUuid must be a string/],
    [{ libraryUuid: '' }, /non-empty uuid/],
    [{ libraryUuid: '   ' }, /non-empty uuid/],
  ];
  for (const [params, pattern] of cases) {
    const { ns, calls } = fakeLibCbb({ search: () => [] });
    const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.search', params));
    assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(params));
    assert.match(error.message, pattern);
    assert.equal(calls.search.length, 0);
  }
});

test('an unknown search parameter is refused by name', async () => {
  const { ns, calls } = fakeLibCbb({ search: () => [] });
  const error = await failure(
    run({ lib_Cbb: ns }, 'lib.cbb.search', { keyword: 'AMS1117' }),
  );
  assert.equal(error.code, 'BAD_REQUEST');
  assert.match(error.message, /keyword/);
  assert.deepEqual(error.detail.allowed, ['query', 'libraryUuid', 'limit', 'page']);
  assert.equal(calls.search.length, 0);
});

// --------------------------------------------------------------------------
// lib.cbb.get
// --------------------------------------------------------------------------

test('get answers the module identity and its boards', async () => {
  const { ns, calls } = fakeLibCbb({ get: () => cbbItem('c1', 'lib-user') });
  const answer = await run({ lib_Cbb: ns }, 'lib.cbb.get', {
    uuid: 'c1',
    libraryUuid: 'lib-user',
  });

  assert.deepEqual(calls.get[0], ['c1', 'lib-user']);
  assert.equal(answer.uuid, 'c1');
  assert.equal(answer.libraryUuid, 'lib-user');
  assert.equal(answer.found, true);
  assert.equal(answer.source, 'lib_Cbb.get');
  assert.equal(answer.apiStatus, 'beta');
  assert.equal(Array.isArray(answer.cbb.boards), true);
  assert.deepEqual(answer.cbb.boards, [{ name: 'board-1', parentProjectUuid: 'proj-1' }]);
  assert.deepEqual(calls.forbidden, []);
});

test('get answers found:false for an unknown uuid', async () => {
  const { ns, calls } = fakeLibCbb({ get: () => undefined });
  const answer = await run({ lib_Cbb: ns }, 'lib.cbb.get', { uuid: 'nope' });

  assert.deepEqual(answer, {
    uuid: 'nope',
    libraryUuid: null,
    found: false,
    cbb: null,
    source: 'lib_Cbb.get',
    apiStatus: 'beta',
  });
  assert.deepEqual(calls.get[0], ['nope', undefined]);
});

test('get refuses a module that comes back as another uuid', async () => {
  const { ns } = fakeLibCbb({ get: () => cbbItem('c2') });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.get', { uuid: 'c1' }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /a different module/);
});

test('get refuses an empty libraryUuid or a non-array boards', async () => {
  const cases = [
    [{ libraryUuid: '' }, /without a libraryUuid/],
    [{ boards: undefined }, /boards/],
    [{ boards: 'none' }, /boards/],
  ];
  for (const [extra, pattern] of cases) {
    const { ns } = fakeLibCbb({ get: () => cbbItem('c1', 'lib-sys', extra) });
    const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.get', { uuid: 'c1' }));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(extra));
    assert.match(error.message, pattern);
  }
});

test('get refuses a library other than the one requested', async () => {
  const { ns } = fakeLibCbb({ get: () => cbbItem('c1', 'lib-sys') });
  const error = await failure(
    run({ lib_Cbb: ns }, 'lib.cbb.get', { uuid: 'c1', libraryUuid: 'lib-user' }),
  );
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /lib-sys/);
  assert.equal(error.detail.requestedLibraryUuid, 'lib-user');
});

test('get validates its own parameters', async () => {
  const cases = [
    [{}, /needs a non-empty uuid/],
    [{ uuid: '' }, /needs a non-empty uuid/],
    [{ uuid: '  ' }, /needs a non-empty uuid/],
    [{ uuid: 7 }, /needs a non-empty uuid/],
    [{ uuid: 'c1', libraryUuid: 7 }, /libraryUuid must be a string/],
    [{ uuid: 'c1', page: 1 }, /does not take page/],
  ];
  for (const [params, pattern] of cases) {
    const { ns, calls } = fakeLibCbb({ get: () => cbbItem('c1') });
    const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.get', params));
    assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(params));
    assert.match(error.message, pattern);
    assert.equal(calls.get.length, 0);
  }
});

test('get reports a host that throws', async () => {
  const { ns } = fakeLibCbb({
    get: () => {
      throw new Error('library service down');
    },
  });
  const error = await failure(run({ lib_Cbb: ns }, 'lib.cbb.get', { uuid: 'c1' }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /library service down/);
});

// --------------------------------------------------------------------------
// Missing API surface and the registration boundary
// --------------------------------------------------------------------------

test('a missing namespace or method is NOT_IMPLEMENTED with the exact path', async () => {
  const cases = [
    [{}, 'lib.cbb.search', 'lib_Cbb'],
    [{ lib_Cbb: {} }, 'lib.cbb.search', 'lib_Cbb.search'],
    [{ lib_Cbb: { search: () => [] } }, 'lib.cbb.search', 'lib_Cbb.get'],
    [{}, 'lib.cbb.get', 'lib_Cbb'],
    [{ lib_Cbb: {} }, 'lib.cbb.get', 'lib_Cbb.get'],
    [{ lib_Cbb: { get: 'not a function' } }, 'lib.cbb.get', 'lib_Cbb.get'],
  ];
  for (const [eda, action, path] of cases) {
    const error = await failure(run(eda, action, action === 'lib.cbb.get' ? { uuid: 'c1' } : {}));
    assert.equal(error.code, 'NOT_IMPLEMENTED', `${action} on ${JSON.stringify(eda)}`);
    assert.equal(error.detail.path, path);
    assert.match(error.message, new RegExp(path.replace('.', '\\.')));
  }
});

test('sys.probe call mode cannot dispatch either action', async () => {
  const { ns } = fakeLibCbb({ search: () => [] });
  for (const action of ['lib.cbb.search', 'lib.cbb.get']) {
    const error = await failure(
      run({ lib_Cbb: ns }, 'sys.probe', { call: { action, params: {} } }),
    );
    assert.equal(error.code, 'BAD_REQUEST', line(error));
    assert.match(error.message, /only dispatches/);
  }
});

// --------------------------------------------------------------------------
// 038Q14 — lib.cbb.personal: which library is this workspace's own?
// --------------------------------------------------------------------------

/** A fake `lib_LibrariesList` whose only working member is the personal read. */
function fakeLibrariesList({ personal } = {}) {
  const calls = { personal: [], forbidden: [] };
  const ns = {
    async getPersonalLibraryUuid(...args) {
      calls.personal.push(args);
      if (personal instanceof Error) throw personal;
      return typeof personal === 'function' ? personal(...args) : personal;
    },
  };
  for (const name of [
    'getSystemLibraryUuid',
    'getProjectLibraryUuid',
    'getFavoriteLibraryUuid',
    'getAllLibrariesList',
    'register',
  ]) {
    ns[name] = (...args) => {
      calls.forbidden.push([name, args]);
      throw new Error(`lib_LibrariesList.${name} must never be reached`);
    };
  }
  return { ns, calls };
}

/** A fake `sys_FileManager`: one working read, everything else a tripwire. */
function fakeFileManager({ cbbFile } = {}) {
  const calls = { cbbFile: [], forbidden: [] };
  const ns = {
    async getCbbFileByCbbUuid(...args) {
      calls.cbbFile.push(args);
      if (cbbFile instanceof Error) throw cbbFile;
      return typeof cbbFile === 'function' ? cbbFile(...args) : cbbFile;
    },
  };
  for (const name of [
    'getSymbolFileBySymbolUuid',
    'getFootprintFileByFootprintUuid',
    'getDocumentFile',
    'getProjectFile',
    'setDocumentSource',
    'saveFile',
    'importProjectFile',
  ]) {
    ns[name] = (...args) => {
      calls.forbidden.push([name, args]);
      throw new Error(`sys_FileManager.${name} must never be reached`);
    };
  }
  return { ns, calls };
}

/** A host `File` stand-in: a declared `size` plus `arrayBuffer()`. */
function fakeFile(bytes, overrides = {}) {
  return {
    name: 'exported-container.epro2',
    type: 'application/octet-stream',
    size: bytes.length,
    async arrayBuffer() {
      return bytes.slice().buffer;
    },
    ...overrides,
  };
}

const MIB = 1024 * 1024;

test('personal answers the workspace library uuid, with no arguments', async () => {
  const libraries = fakeLibrariesList({ personal: 'lib-user' });
  const answer = await run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.personal');

  assert.deepEqual(answer, {
    libraryUuid: 'lib-user',
    source: 'lib_LibrariesList.getPersonalLibraryUuid',
    apiStatus: 'public',
  });
  assert.deepEqual(libraries.calls.personal, [[]], 'the call takes no arguments');
  assert.deepEqual(libraries.calls.forbidden, []);
});

test('personal refuses every answer that is not a non-empty uuid', async () => {
  const cases = [
    [undefined, /no personal-library uuid was resolved/],
    [null, /no personal-library uuid was resolved/],
    ['', /empty string/],
    ['   ', /empty string/],
    [5, /instead of a library uuid/],
    [{ uuid: 'lib-user' }, /instead of a library uuid/],
    [['lib-user'], /instead of a library uuid/],
  ];
  for (const [answer, pattern] of cases) {
    const libraries = fakeLibrariesList({ personal: answer });
    const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.personal'));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(answer));
    assert.match(error.message, pattern, JSON.stringify(answer));
    assert.equal(error.detail.path, 'lib_LibrariesList.getPersonalLibraryUuid');
  }
});

test('an unresolved personal library is not diagnosed as a deployment fact', async () => {
  for (const answer of [undefined, null]) {
    const libraries = fakeLibrariesList({ personal: answer });
    const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.personal'));

    assert.equal(error.detail.reason, 'personal-library-unresolved');
    assert.match(error.message, /not a diagnosis/, 'the cause is not knowable from here');
    assert.match(error.message, /not\s+evidence that a library is empty/i);
    assert.doesNotMatch(
      error.message,
      /this workspace has no personal library|so there is no library/i,
      'a public build answering undefined is not proof of a private deployment',
    );
  }
});

test('personal reports a host that throws', async () => {
  const libraries = fakeLibrariesList({ personal: new Error('library service offline') });
  const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.personal'));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /library service offline/);
  assert.equal(error.detail.thrown, true);
});

test('personal is NOT_IMPLEMENTED when the namespace or method is absent', async () => {
  const cases = [
    [{}, 'lib_LibrariesList'],
    [{ lib_LibrariesList: {} }, 'lib_LibrariesList.getPersonalLibraryUuid'],
    [{ lib_LibrariesList: { getPersonalLibraryUuid: 'nope' } }, 'lib_LibrariesList.getPersonalLibraryUuid'],
  ];
  for (const [eda, path] of cases) {
    const error = await failure(run(eda, 'lib.cbb.personal'));
    assert.equal(error.code, 'NOT_IMPLEMENTED', JSON.stringify(eda));
    assert.equal(error.detail.path, path);
    assert.match(error.message, new RegExp(path.replace('.', '\\.')));
  }
});

test('personal takes no parameters at all', async () => {
  const libraries = fakeLibrariesList({ personal: 'lib-user' });
  for (const params of [{ libraryUuid: 'x' }, { uuid: 'c1' }]) {
    const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.personal', params));
    assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(params));
    assert.match(error.message, /takes no parameters/);
    assert.equal(libraries.calls.personal.length, 0);
  }
  const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.personal', 7));
  assert.equal(error.code, 'BAD_REQUEST');
  assert.match(error.message, /params must be an object/);
});

// --------------------------------------------------------------------------
// 038Q14 — lib.cbb.export: one module's own .epro2, identity first
// --------------------------------------------------------------------------

/**
 * The arguments the export must send — `fileName` is the **module's own name**
 * (`@jlceda/pro-api-types` index.d.ts:17087 documents that argument as
 * 复用模块名), so it is derived from the fake module, never hard-coded here.
 */
function exportProps(moduleName) {
  return { fileName: moduleName, fileType: 'epro2' };
}

/** An `eda` with a module `get` and a file manager that both answer. */
function exportHost({ cbb = (uuid) => cbbItem(uuid, 'lib-user'), file, order } = {}) {
  const lib = fakeLibCbb({
    get: (...args) => {
      if (order) order.push('get');
      return cbb(...args);
    },
  });
  const manager = fakeFileManager({
    cbbFile: (...args) => {
      if (order) order.push('file');
      return typeof file === 'function' ? file(...args) : file;
    },
  });
  return { eda: { lib_Cbb: lib.ns, sys_FileManager: manager.ns }, calls: { lib: lib.calls, manager: manager.calls } };
}

test('export hands back the container bytes as base64 after a verified identity', async () => {
  const bytes = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0x00, 0xff]);
  const order = [];
  const host = exportHost({ file: fakeFile(bytes), order });

  const answer = await run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' });

  assert.deepEqual(order, ['get', 'file'], 'the identity is read before a byte is fetched');
  assert.deepEqual(host.calls.lib.get, [['c1', 'lib-user']]);
  assert.deepEqual(
    host.calls.manager.cbbFile,
    [['c1', 'lib-user', exportProps('name-c1')]],
    'the host is handed the module\'s own name, not a name this side invented',
  );
  assert.deepEqual(host.calls.lib.forbidden, []);
  assert.deepEqual(host.calls.manager.forbidden, []);
  assert.deepEqual(answer, {
    uuid: 'c1',
    libraryUuid: 'lib-user',
    format: 'epro2',
    size: bytes.length,
    base64: Buffer.from(bytes).toString('base64'),
    source: 'sys_FileManager.getCbbFileByCbbUuid',
    apiStatus: 'beta',
  });
  assert.equal(answer.base64, 'UEsDBAD/', 'the bytes are not re-encoded');
  assert.deepEqual(
    new Uint8Array(Buffer.from(answer.base64, 'base64')),
    bytes,
    'the base64 is the bytes themselves',
  );
});

test('export refuses a module lib_Cbb.get cannot find, before fetching anything', async () => {
  const host = exportHost({ cbb: () => undefined, file: fakeFile(new Uint8Array([1])) });
  const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /cannot be attributed/);
  assert.equal(host.calls.manager.cbbFile.length, 0, 'unverified identity must not fetch bytes');
});

test('export forwards the module name verbatim, whitespace and all', async () => {
  const name = '  AMS1117 复用模块 (v2) ';
  const host = exportHost({
    cbb: () => cbbItem('c1', 'lib-user', { name }),
    file: fakeFile(new Uint8Array([1, 2, 3])),
  });
  const answer = await run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' });

  assert.equal(answer.uuid, 'c1');
  assert.deepEqual(
    host.calls.manager.cbbFile,
    [['c1', 'lib-user', exportProps(name)]],
    'the name is not trimmed, re-cased or replaced',
  );
});

test('export refuses a module with no usable name and never asks for a file', async () => {
  const cases = [
    [{ name: undefined }, /without a usable name/],
    [{ name: '' }, /without a usable name/],
    [{ name: '   ' }, /without a usable name/],
    [{ name: 7 }, /without a usable name/],
  ];
  for (const [extra, pattern] of cases) {
    const host = exportHost({
      cbb: () => cbbItem('c1', 'lib-user', extra),
      file: fakeFile(new Uint8Array([1])),
    });
    const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(extra));
    assert.match(error.message, pattern, JSON.stringify(extra));
    assert.match(error.message, /复用模块名/, 'the declaration is the reason, not a guess');
    assert.equal(host.calls.manager.cbbFile.length, 0, 'no name means no file call');
  }
});

test('export refuses a module whose library disagrees with the request', async () => {
  const host = exportHost({ cbb: () => cbbItem('c1', 'lib-sys'), file: fakeFile(new Uint8Array([1])) });
  const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /lib-sys/);
  assert.equal(error.detail.requestedLibraryUuid, 'lib-user');
  assert.equal(host.calls.manager.cbbFile.length, 0);
});

test('export refuses a module that comes back as another uuid', async () => {
  const host = exportHost({ cbb: () => cbbItem('c2', 'lib-user'), file: fakeFile(new Uint8Array([1])) });
  const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /a different module/);
  assert.equal(host.calls.manager.cbbFile.length, 0);
});

test('export refuses a zero-byte file', async () => {
  const host = exportHost({ file: fakeFile(new Uint8Array(0)) });
  const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /zero-byte/);
  assert.equal(error.detail.size, 0);
});

test('export refuses a file over 16 MiB without reading it', async () => {
  const host = exportHost({
    file: fakeFile(new Uint8Array(1), {
      size: 16 * MIB + 1,
      async arrayBuffer() {
        throw new Error('an over-sized file must not be read');
      },
    }),
  });
  const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /over the 16777216-byte \(16 MiB\) ceiling/);
  assert.equal(error.detail.size, 16 * MIB + 1);
  assert.equal(error.detail.maxBytes, 16 * MIB);
});

test('export accepts a file of exactly 16 MiB', async () => {
  const bytes = new Uint8Array(16 * MIB);
  const host = exportHost({ file: fakeFile(bytes) });
  const answer = await run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' });

  assert.equal(answer.size, 16 * MIB);
  assert.equal(answer.base64.length, 4 * Math.ceil(bytes.length / 3));
});

test('export refuses bytes whose length disagrees with the declared size', async () => {
  const host = exportHost({ file: fakeFile(new Uint8Array([1, 2]), { size: 4 }) });
  const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /handed over 2 bytes/);
  assert.equal(error.detail.size, 4);
  assert.equal(error.detail.readBytes, 2);
});

test('export refuses a declared size that is not a safe integer', async () => {
  for (const size of [undefined, null, '4', 1.5, Number.NaN, 2 ** 53]) {
    const host = exportHost({ file: fakeFile(new Uint8Array([1]), { size }) });
    const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));
    assert.equal(error.code, 'CONNECTOR_ERROR', String(size));
    assert.match(error.message, /safe integer/, String(size));
  }
});

test('export refuses a file object with no readable arrayBuffer()', async () => {
  const host = exportHost({ file: { size: 4 } });
  const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /no arrayBuffer\(\)/);
});

test('export reports an undefined, null or throwing host', async () => {
  for (const value of [undefined, null]) {
    const host = exportHost({ file: () => value });
    const error = await failure(run(host.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));
    assert.equal(error.code, 'CONNECTOR_ERROR', String(value));
    assert.match(error.message, /could not be fetched/);
    assert.equal(error.detail.empty, true);
  }

  const throwing = exportHost({
    file: () => {
      throw new Error('团队模块 下载模块 permission denied');
    },
  });
  const error = await failure(run(throwing.eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /permission denied/, 'the host\'s own words survive');
  assert.match(error.message, /团队模块 > 下载模块/, 'the documented gate is named as a check');
  assert.match(error.message, /rather than a diagnosis|Re-check the gate/);
  assert.doesNotMatch(
    error.message,
    /whether a permission is missing|permission is missing is not knowable|you lack/i,
    'a throw is not evidence that a grant is the cause',
  );
  assert.equal(error.detail.thrown, true);
  assert.equal(error.detail.path, 'sys_FileManager.getCbbFileByCbbUuid');
});

test('export is NOT_IMPLEMENTED when sys_FileManager or its method is absent', async () => {
  const cases = [
    [{}, 'sys_FileManager'],
    [{ sys_FileManager: {} }, 'sys_FileManager.getCbbFileByCbbUuid'],
    [{ sys_FileManager: { getCbbFileByCbbUuid: 1 } }, 'sys_FileManager.getCbbFileByCbbUuid'],
  ];
  for (const [extra, path] of cases) {
    const lib = fakeLibCbb({ get: () => cbbItem('c1', 'lib-user') });
    const eda = { lib_Cbb: lib.ns, ...extra };
    const error = await failure(run(eda, 'lib.cbb.export', { uuid: 'c1', libraryUuid: 'lib-user' }));
    assert.equal(error.code, 'NOT_IMPLEMENTED', JSON.stringify(extra));
    assert.equal(error.detail.path, path);
  }
});

test('export validates its own parameters without touching the host', async () => {
  const cases = [
    [{}, /needs a non-empty uuid/],
    [{ uuid: '' }, /needs a non-empty uuid/],
    [{ uuid: '  ' }, /needs a non-empty uuid/],
    [{ uuid: 7 }, /needs a non-empty uuid/],
    [{ uuid: ['c1'] }, /needs a non-empty uuid/],
    [{ uuid: 'c1' }, /needs a non-empty libraryUuid/],
    [{ uuid: 'c1', libraryUuid: '' }, /needs a non-empty libraryUuid/],
    [{ uuid: 'c1', libraryUuid: 5 }, /needs a non-empty libraryUuid/],
    [{ uuid: 'c1', libraryUuid: 'lib-user', fileType: 'epro' }, /does not take fileType/],
    [{ uuid: 'c1', libraryUuid: 'lib-user', password: 'x' }, /does not take password/],
  ];
  for (const [params, pattern] of cases) {
    const host = exportHost({ file: fakeFile(new Uint8Array([1])) });
    const error = await failure(run(host.eda, 'lib.cbb.export', params));
    assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(params));
    assert.match(error.message, pattern, JSON.stringify(params));
    assert.equal(host.calls.lib.get.length, 0, `nothing is read for ${JSON.stringify(params)}`);
    assert.equal(host.calls.manager.cbbFile.length, 0);
  }
  const error = await failure(run({}, 'lib.cbb.export', 'c1'));
  assert.equal(error.code, 'BAD_REQUEST');
  assert.match(error.message, /params must be an object/);
});

// --------------------------------------------------------------------------
// 038Q14 follow-up — lib.cbb.libraries: the workspace's *other* libraries
// --------------------------------------------------------------------------

/** The four special libraries the declaration says this list never contains. */
const SPECIAL_LIBRARY_READS = [
  'getSystemLibraryUuid',
  'getPersonalLibraryUuid',
  'getProjectLibraryUuid',
  'getFavoriteLibraryUuid',
];

/** A fake `lib_LibrariesList` whose only working member is the list read. */
function fakeLibraryList({ list } = {}) {
  const calls = { list: [], forbidden: [] };
  const ns = {
    async getAllLibrariesList(...args) {
      calls.list.push(args);
      if (list instanceof Error) throw list;
      return typeof list === 'function' ? list(...args) : list;
    },
  };
  for (const name of [...SPECIAL_LIBRARY_READS, 'register']) {
    ns[name] = (...args) => {
      calls.forbidden.push([name, args]);
      throw new Error(`lib_LibrariesList.${name} must never be reached`);
    };
  }
  return { ns, calls };
}

test('libraries answers the list with no arguments and no host extras', async () => {
  const libraries = fakeLibraryList({
    list: () => [
      { uuid: 'lib-team', name: 'team', description: 'host extra', type: 7 },
      { uuid: 'lib-other', name: 'other' },
    ],
  });
  const answer = await run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.libraries');

  assert.deepEqual(answer, {
    items: [
      { uuid: 'lib-team', name: 'team' },
      { uuid: 'lib-other', name: 'other' },
    ],
    count: 2,
    source: 'lib_LibrariesList.getAllLibrariesList',
    apiStatus: 'public',
  });
  assert.deepEqual(libraries.calls.list, [[]], 'the call takes no arguments');
  assert.deepEqual(libraries.calls.forbidden, [], 'the four special reads are not substitutes');
});

test('an empty list is a real reading, not a failure', async () => {
  const libraries = fakeLibraryList({ list: () => [] });
  const answer = await run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.libraries');

  assert.deepEqual(answer.items, []);
  assert.equal(answer.count, 0);
  assert.equal(answer.source, 'lib_LibrariesList.getAllLibrariesList');
});

test('a non-array answer is CONNECTOR_ERROR, never an empty list', async () => {
  for (const value of [undefined, null, {}, 'no', 3]) {
    const libraries = fakeLibraryList({ list: () => value });
    const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.libraries'));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(value));
    assert.match(error.message, /unknown, not empty/);
  }
});

test('malformed entries are CONNECTOR_ERROR, never skipped', async () => {
  const cases = [
    [null, /is null, not a library/],
    [[{ uuid: 'lib-a', name: 'a' }], /not a library/],
    [{ name: 'no uuid' }, /has no uuid/],
    [{ uuid: '', name: 'blank uuid' }, /has no uuid/],
    [{ uuid: '   ', name: 'spaces' }, /has no uuid/],
    [{ uuid: 'lib-a', name: 7 }, /has no name string/],
    [{ uuid: 'lib-a' }, /has no name string/],
  ];
  for (const [entry, pattern] of cases) {
    const libraries = fakeLibraryList({ list: () => [entry] });
    const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.libraries'));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(entry));
    assert.match(error.message, pattern, JSON.stringify(entry));
  }
});

test('a duplicated uuid is CONNECTOR_ERROR and names both positions', async () => {
  const libraries = fakeLibraryList({
    list: () => [
      { uuid: 'lib-a', name: 'first' },
      { uuid: 'lib-b', name: 'b' },
      { uuid: 'lib-a', name: 'again' },
    ],
  });
  const error = await failure(run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.libraries'));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /lists uuid lib-a twice/);
  assert.deepEqual(error.detail.indexes, [0, 2]);
});

test('libraries reports a throwing host and a missing API', async () => {
  const throwing = fakeLibraryList({ list: new Error('library index offline') });
  const error = await failure(run({ lib_LibrariesList: throwing.ns }, 'lib.cbb.libraries'));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /library index offline/);
  assert.equal(error.detail.thrown, true);

  const cases = [
    [{}, 'lib_LibrariesList'],
    [{ lib_LibrariesList: {} }, 'lib_LibrariesList.getAllLibrariesList'],
    [{ lib_LibrariesList: { getAllLibrariesList: 'nope' } }, 'lib_LibrariesList.getAllLibrariesList'],
  ];
  for (const [eda, path] of cases) {
    const missing = await failure(run(eda, 'lib.cbb.libraries'));
    assert.equal(missing.code, 'NOT_IMPLEMENTED', JSON.stringify(eda));
    assert.equal(missing.detail.path, path);
  }
});

test('libraries takes no parameters at all', async () => {
  const libraries = fakeLibraryList({ list: () => [] });
  const error = await failure(
    run({ lib_LibrariesList: libraries.ns }, 'lib.cbb.libraries', { uuid: 'lib-a' }),
  );
  assert.equal(error.code, 'BAD_REQUEST');
  assert.match(error.message, /takes no parameters/);
  assert.equal(libraries.calls.list.length, 0);
});

test('no 038Q14 read can be dispatched through sys.probe', async () => {
  for (const action of ['lib.cbb.personal', 'lib.cbb.libraries', 'lib.cbb.export']) {
    const error = await failure(
      run({}, 'sys.probe', { call: { action, params: {} } }),
    );
    assert.equal(error.code, 'BAD_REQUEST', line(error));
    assert.match(error.message, /only dispatches/);
  }
});

// --------------------------------------------------------------------------
// 038Q16 — the `'project'` scope: lib_Symbol.get verifies the local blocks
// --------------------------------------------------------------------------
//
// Measured 2026-11-15: `lib_Cbb.search('', 'project')` returns the project's own
// block (ca89…), but `lib_Cbb.get(ca89…, 'project')` is refused, so the old
// verification rejected a legitimate result. The project scope therefore reads
// each hit through `lib_Symbol.get(uuid, 'project')` and requires the same uuid,
// a name string, `type === 17` and `libraryType === '2'`. The normal-library
// path keeps `lib_Cbb.get` and its messages unchanged — these tests pin both
// halves, including that a project search never touches `lib_Cbb.get`.

/** A project-local CBB symbol, as `lib_Symbol.get(uuid, 'project')` answers it. */
function projectSymbol(uuid, extra = {}) {
  return {
    uuid,
    name: '晶振',
    type: 17,
    libraryType: '2',
    libraryUuid: '08be0000project-source',
    ...extra,
  };
}

/** A fake `lib_Symbol` whose only working member is `get`. */
function fakeLibSymbol({ get } = {}) {
  const calls = { get: [], forbidden: [] };
  const ns = {
    async get(...args) {
      calls.get.push(args);
      if (get instanceof Error) throw get;
      return typeof get === 'function' ? get(...args) : get;
    },
  };
  for (const name of ['create', 'modify', 'delete', 'copy', 'openInEditor']) {
    ns[name] = (...args) => {
      calls.forbidden.push([name, args]);
      throw new Error(`lib_Symbol.${name} must never be reached by a read`);
    };
  }
  return { ns, calls };
}

test('project scope verifies each hit through lib_Symbol.get and reports the scope', async () => {
  const lib = fakeLibCbb({ search: () => [hit('ca89fed3a434c5cb', 'project')] });
  const symbols = fakeLibSymbol({ get: () => projectSymbol('ca89fed3a434c5cb') });
  const calls = [];
  const answer = await run(
    { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
    'lib.cbb.search',
    { query: '', libraryUuid: 'project' },
  );

  assert.deepEqual(lib.calls.get, [], 'lib_Cbb.get is never called for the project scope');
  assert.deepEqual(symbols.calls.get, [['ca89fed3a434c5cb', 'project']]);
  assert.deepEqual(lib.calls.forbidden, []);
  assert.deepEqual(symbols.calls.forbidden, []);
  assert.equal(answer.libraryUuid, 'project', 'the caller\'s scope is echoed, not replaced');
  assert.equal(answer.count, 1);
  assert.deepEqual(answer.items[0], {
    uuid: 'ca89fed3a434c5cb',
    name: 'name-ca89fed3a434c5cb',
    ordinal: 1,
    updateTimestamp: 1700000000000,
    ascription: 'system',
    lastModifiedBy: 'someone',
    libraryUuid: 'project',
    sourceLibraryUuid: '08be0000project-source',
    libraryIdentitySource: 'lib_Symbol.get(project)',
  });
});

test('project scope keeps the search row metadata and validates the symbol name', async () => {
  const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
  const symbols = fakeLibSymbol({ get: () => projectSymbol('c1', { libraryUuid: undefined }) });
  const answer = await run(
    { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
    'lib.cbb.search',
    { libraryUuid: 'project' },
  );

  // The item's public metadata is still the search row's (038Q1's rule); the
  // symbol's `name` is a *check* (`typeof === 'string'`), not a replacement —
  // a caller that needs the authoritative display name reads the symbol itself.
  assert.equal(answer.items[0].name, 'name-c1');
  assert.equal(answer.items[0].libraryUuid, 'project');
  assert.equal('sourceLibraryUuid' in answer.items[0], false, 'absent means absent, not null');
  assert.equal(answer.items[0].libraryIdentitySource, 'lib_Symbol.get(project)');
});

test('a blank source library uuid is omitted rather than reported', async () => {
  for (const value of ['', '   ', 7]) {
    const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
    const symbols = fakeLibSymbol({ get: () => projectSymbol('c1', { libraryUuid: value }) });
    const answer = await run(
      { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
      'lib.cbb.search',
      { libraryUuid: 'project' },
    );
    assert.equal('sourceLibraryUuid' in answer.items[0], false, JSON.stringify(value));
  }
});

test('an empty project page is an empty answer, not a failure', async () => {
  const lib = fakeLibCbb({ search: () => [] });
  const symbols = fakeLibSymbol({});
  const answer = await run(
    { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
    'lib.cbb.search',
    { libraryUuid: 'project' },
  );

  assert.equal(answer.count, 0);
  assert.deepEqual(answer.items, []);
  assert.equal(answer.libraryUuid, 'project');
  assert.equal(symbols.calls.get.length, 0, 'no hit means no identity to verify');
});

test('project scope is NOT_IMPLEMENTED when lib_Symbol.get is absent', async () => {
  const cases = [
    [{ lib_Cbb: { search: async () => [] } }, 'lib_Symbol'],
    [{ lib_Cbb: { search: async () => [] }, lib_Symbol: {} }, 'lib_Symbol.get'],
    [
      { lib_Cbb: { search: async () => [] }, lib_Symbol: { get: 'nope' } },
      'lib_Symbol.get',
    ],
  ];
  for (const [eda, path] of cases) {
    const error = await failure(run(eda, 'lib.cbb.search', { libraryUuid: 'project' }));
    assert.equal(error.code, 'NOT_IMPLEMENTED', JSON.stringify(eda));
    assert.equal(error.detail.path, path);
  }
});

test('project scope still refuses a project library without lib_Cbb.search', async () => {
  const symbols = fakeLibSymbol({ get: () => projectSymbol('c1') });
  const error = await failure(run({ lib_Symbol: symbols.ns }, 'lib.cbb.search', {
    libraryUuid: 'project',
  }));
  assert.equal(error.code, 'NOT_IMPLEMENTED');
  assert.equal(error.detail.path, 'lib_Cbb');
  assert.equal(symbols.calls.get.length, 0);
});

test('a project hit the symbol read cannot find is an error, not a dropped row', async () => {
  const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
  const symbols = fakeLibSymbol({ get: () => undefined });
  const error = await failure(run(
    { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
    'lib.cbb.search',
    { libraryUuid: 'project' },
  ));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /lib_Symbol\.get\(c1, 'project'\) found nothing/);
  assert.equal(error.detail.index, 0);
  assert.equal(error.detail.scope, 'project');
  assert.equal(symbols.calls.get.length, 1, 'the hit was read, not skipped');
});

test('a project hit with the wrong type is refused', async () => {
  const cases = [
    [{ type: 0 }, /instead of 17/],
    [{ type: '17' }, /instead of 17/],
    [{ type: undefined }, /instead of 17/],
  ];
  for (const [extra, pattern] of cases) {
    const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
    const symbols = fakeLibSymbol({ get: () => projectSymbol('c1', extra) });
    const error = await failure(run(
      { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
      'lib.cbb.search',
      { libraryUuid: 'project' },
    ));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(extra));
    assert.match(error.message, pattern);
    assert.match(error.message, /not a project-local CBB symbol/);
  }
});

test('a project hit with the wrong libraryType is refused', async () => {
  const cases = [
    [{ libraryType: '1' }, /instead of "2"/],
    [{ libraryType: 2 }, /instead of "2"/],
    [{ libraryType: undefined }, /instead of "2"/],
  ];
  for (const [extra, pattern] of cases) {
    const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
    const symbols = fakeLibSymbol({ get: () => projectSymbol('c1', extra) });
    const error = await failure(run(
      { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
      'lib.cbb.search',
      { libraryUuid: 'project' },
    ));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(extra));
    assert.match(error.message, pattern);
    assert.match(error.message, /not in the project library/);
  }
});

test('a project hit answering another uuid or no name is refused', async () => {
  const cases = [
    [{ uuid: 'other' }, /a different symbol/],
    [{ name: 7 }, /without a name string/],
    [{ name: undefined }, /without a name string/],
  ];
  for (const [extra, pattern] of cases) {
    const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
    const symbols = fakeLibSymbol({ get: () => projectSymbol('c1', extra) });
    const error = await failure(run(
      { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
      'lib.cbb.search',
      { libraryUuid: 'project' },
    ));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(extra));
    assert.match(error.message, pattern);
  }
});

test('a project hit the symbol read answers as a non-object is refused', async () => {
  for (const value of ['x', 3, []]) {
    const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
    const symbols = fakeLibSymbol({ get: () => value });
    const error = await failure(run(
      { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
      'lib.cbb.search',
      { libraryUuid: 'project' },
    ));
    assert.equal(error.code, 'CONNECTOR_ERROR', JSON.stringify(value));
    assert.match(error.message, /instead of a symbol/);
  }
});

test('a malformed project hit is refused before the symbol read', async () => {
  const lib = fakeLibCbb({ search: () => [{ name: 'no uuid' }] });
  const symbols = fakeLibSymbol({ get: () => projectSymbol('c1') });
  const error = await failure(run(
    { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
    'lib.cbb.search',
    { libraryUuid: 'project' },
  ));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /has no uuid/);
  assert.equal(symbols.calls.get.length, 0, 'an unidentifiable hit never reaches lib_Symbol');
});

test('a throwing lib_Symbol.get is CONNECTOR_ERROR carrying the message', async () => {
  const lib = fakeLibCbb({ search: () => [hit('c1', 'project')] });
  const symbols = fakeLibSymbol({ get: new Error('symbol service down') });
  const error = await failure(run(
    { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
    'lib.cbb.search',
    { libraryUuid: 'project' },
  ));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /verifying search item 0/);
  assert.match(error.message, /symbol service down/);
});

test('a normal library search is unchanged and never reads lib_Symbol', async () => {
  const lib = fakeLibCbb({
    search: () => [hit('c1', 'lib-sys')],
    get: () => cbbItem('c1', 'lib-sys'),
  });
  const symbols = fakeLibSymbol({
    get: () => {
      throw new Error('lib_Symbol must not be reached for a normal library');
    },
  });
  const answer = await run(
    { lib_Cbb: lib.ns, lib_Symbol: symbols.ns },
    'lib.cbb.search',
    {},
  );

  assert.deepEqual(lib.calls.get, [['c1', undefined]], 'the old reader still verifies');
  assert.deepEqual(symbols.calls.get, [], 'lib_Symbol is not a fallback for other libraries');
  assert.equal(answer.items[0].libraryIdentitySource, 'lib_Cbb.get');
  assert.equal('sourceLibraryUuid' in answer.items[0], false);
});

test('the project branch does not relax the normal-library refusals', async () => {
  // Same fake as the pre-038Q16 suite: a `get` answering a blank library is still
  // fatal, because only the project scope changed readers.
  const lib = fakeLibCbb({
    search: () => [hit('c1', 'lib-sys')],
    get: () => cbbItem('c1', ''),
  });
  const error = await failure(run({ lib_Cbb: lib.ns }, 'lib.cbb.search', {}));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /without a libraryUuid/);
});
