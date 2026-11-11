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
