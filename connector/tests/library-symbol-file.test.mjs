/**
 * 038Q3: `lib.symbol_file.get` — one library symbol's own file, read-only.
 *
 * Why this action exists, in one measurement: `lib.symbol.get` on a real symbol
 * (EDA 4.1.93, 2026-11-11) answered name + uuid + classification + otherProperty
 * and **no pins, no body geometry** (`outputs/review/038q3/ams1117.symbol.get.json`).
 * The container file is the remaining honest source for that geometry, so the
 * one host call that produces it is exposed — narrowly, and without pretending
 * to know what is inside.
 *
 * What this file pins, and why each one is here rather than left to the first
 * live run:
 *
 * 1. **The call shape** — exactly three positional arguments
 *    `(uuid, libraryUuid|undefined, fileType)`, with an omitted library sent as
 *    `undefined` rather than `''`. The host drops an argument it dislikes
 *    instead of rejecting, so a wrong shape settles as nothing at all.
 * 2. **Everything is refused before the host is called** — an unknown parameter,
 *    an array of uuids, an empty `libraryUuid`, a missing or foreign `fileType`.
 *    A silently ignored parameter is a call that does something other than what
 *    the caller asked for.
 * 3. **The bytes are whole or the call failed** — a missing method, a throwing
 *    parent, a host refusal, `undefined`/`null`, zero bytes and a `File` with no
 *    `arrayBuffer` are all errors. "An empty export is not a small one" is the
 *    rule `export.fab` learned, applied here before it can bite.
 * 4. **Observation is not verdict** — `isZip` reports two magic bytes and says
 *    so; the filename is cleaned but never read as an identity, and the request
 *    uuid is not echoed back as proof of what the container holds.
 * 5. **The old contracts do not move** — `lib.symbol.get` still answers
 *    `{uuid, libraryUuid, found, item}`, and the 025 archive refusal still
 *    carries its own two gates and nothing from this batch.
 *
 * Everything goes through the real `buildHandlers()` registry, so a handler that
 * exists but was never registered fails here too. All offline: what the real
 * host answers for this call is a question this file deliberately does not
 * claim to have answered.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

const ACTION = 'lib.symbol_file.get';
const SOURCE = 'sys_FileManager.getSymbolFileBySymbolUuid';
const SYMBOL_UUID = '06f50e10ab7d460599b3fe3ee8717a78';
const LIBRARY_UUID = '0819f05c4eef4c71ace90d822a990e87';

/** Bytes that start with the ZIP magic, plus a little payload. */
const ZIP_BYTES = [0x50, 0x4b, 0x03, 0x04, 9, 8, 7, 6];

/** Bytes that are not a ZIP — an elibz2 we refuse to name further. */
const PLAIN_BYTES = [0x7b, 0x22, 0x61];

/** A host `File` stand-in: only the members the action reads. */
function fileLike(bytes, { name = 'symbol.elibz2', type = 'application/zip' } = {}) {
  return {
    name,
    type,
    arrayBuffer: async () => new Uint8Array(bytes).buffer,
  };
}

/**
 * Writing / opening members that must never be reached from this read.
 *
 * A read that can open a document in the editor, import a project or change a
 * document source is a write wearing a read's name — the boundary is only real
 * if something trips when it is crossed.
 */
const FORBIDDEN = [
  'setDocumentSource',
  'importProject',
  'importProjectByProjectUuid',
  'deleteFile',
];

function fakeEda({ getSymbolFile, symbol = fileLike(ZIP_BYTES), fileManager } = {}) {
  const calls = { symbolFile: [], forbidden: [] };
  const ns = fileManager ?? {
    async getSymbolFileBySymbolUuid(...args) {
      calls.symbolFile.push(args);
      return getSymbolFile ? getSymbolFile(...args) : symbol;
    },
  };
  for (const name of FORBIDDEN) {
    ns[name] = (...args) => {
      calls.forbidden.push([name, args]);
      throw new Error(`sys_FileManager.${name} must never be reached by a read`);
    };
  }
  const eda = { sys_FileManager: ns };
  return { eda, calls };
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

const line = (error) => `${error.code}: ${error.message}`;

// --------------------------------------------------------------------------
// The successful read
// --------------------------------------------------------------------------

test('the action is registered and answers the declared shape, in order', async () => {
  const { eda } = fakeEda();
  const data = await run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' });

  assert.deepEqual(Object.keys(data), [
    'uuid',
    'libraryUuid',
    'fileType',
    'source',
    'apiStatus',
    'encoding',
    'name',
    'mime',
    'bytes',
    'data',
    'isZip',
  ]);
  assert.equal(data.uuid, SYMBOL_UUID);
  assert.equal(data.libraryUuid, null, 'an omitted library is reported as absent');
  assert.equal(data.fileType, 'elibz2');
  assert.equal(data.source, SOURCE);
  assert.equal(data.apiStatus, 'beta');
  assert.equal(data.encoding, 'base64');
  assert.equal(data.bytes, ZIP_BYTES.length);
  assert.equal(data.data, Buffer.from(ZIP_BYTES).toString('base64'), 'the bytes are whole');
  assert.equal(data.isZip, true);
});

test('the call sends exactly the three declared arguments, library omitted as undefined', async () => {
  const { eda, calls } = fakeEda();
  await run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' });

  // Declaration order is (symbolUuid, libraryUuid?, fileType?). A shorter call
  // would move fileType into the library slot, and the host would answer for a
  // library that does not exist rather than refuse.
  assert.deepEqual(calls.symbolFile, [[SYMBOL_UUID, undefined, 'elibz2']]);
  assert.equal(calls.symbolFile[0].length, 3, 'three arguments, not two');
});

test('an explicit library uuid is forwarded verbatim', async () => {
  const { eda, calls } = fakeEda();
  const data = await run(eda, ACTION, {
    uuid: SYMBOL_UUID,
    libraryUuid: LIBRARY_UUID,
    fileType: 'elibz2',
  });

  assert.deepEqual(calls.symbolFile, [[SYMBOL_UUID, LIBRARY_UUID, 'elibz2']]);
  assert.equal(data.libraryUuid, LIBRARY_UUID);
});

test('both container types are accepted and reported as asked', async () => {
  for (const fileType of ['elibz2', 'elibz']) {
    const { eda, calls } = fakeEda({
      getSymbolFile: async () => fileLike(PLAIN_BYTES, { name: `symbol.${fileType}` }),
    });
    const data = await run(eda, ACTION, {
      uuid: SYMBOL_UUID,
      libraryUuid: LIBRARY_UUID,
      fileType,
    });

    assert.equal(data.fileType, fileType);
    assert.deepEqual(calls.symbolFile, [[SYMBOL_UUID, LIBRARY_UUID, fileType]]);
  }
});

test('a non-ZIP header is reported as an observation, never as a format verdict', async () => {
  const { eda } = fakeEda({
    getSymbolFile: async () => fileLike(PLAIN_BYTES, { name: 'symbol.elibz2' }),
  });
  const data = await run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' });

  assert.equal(data.isZip, false);
  assert.equal(data.note, undefined, 'no elibz2 layout is claimed from two bytes');
  assert.equal(data.fileType, 'elibz2', 'the caller\'s fileType is what was asked for');
  assert.equal(data.bytes, PLAIN_BYTES.length);
});

test('the host file name is cleaned of path separators and never read as an identity', async () => {
  const { eda } = fakeEda({
    getSymbolFile: async () => fileLike(ZIP_BYTES, { name: '..\\..\\evil/elibz2.elibz2' }),
  });
  const data = await run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' });

  assert.equal(data.name, '.._.._evil_elibz2.elibz2');
  // The identity reported is the caller's request, in `uuid` — not a value
  // parsed out of the name, which is a host-side label with no contract.
  assert.equal(data.uuid, SYMBOL_UUID);
  assert.equal(data.identitySource, undefined, 'no identity is claimed from the file');
});

test('an untyped host file falls back to octet-stream, and the name may be empty', async () => {
  const { eda } = fakeEda({
    getSymbolFile: async () => fileLike(ZIP_BYTES, { name: '', type: '' }),
  });
  const data = await run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz' });

  assert.equal(data.mime, 'application/octet-stream');
  assert.equal(data.name, '');
});

test('reading a file reaches no writing member of sys_FileManager', async () => {
  const { eda, calls } = fakeEda();
  await run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' });
  assert.deepEqual(calls.forbidden, [], 'no write surface was touched');
});

// --------------------------------------------------------------------------
// Refused before the host is called
// --------------------------------------------------------------------------

const refusedBeforeHost = [
  ['an array of uuids', { uuid: [SYMBOL_UUID, 'other'], fileType: 'elibz2' }, /single non-empty string/],
  ['an empty uuid', { uuid: '   ', fileType: 'elibz2' }, /single non-empty string/],
  ['a non-string uuid', { uuid: 42, fileType: 'elibz2' }, /single non-empty string/],
  ['a missing uuid', { fileType: 'elibz2' }, /single non-empty string/],
  ['a missing fileType', { uuid: SYMBOL_UUID }, /needs fileType/],
  ['a foreign fileType', { uuid: SYMBOL_UUID, fileType: 'pdf' }, /needs fileType/],
  ['an empty libraryUuid', { uuid: SYMBOL_UUID, libraryUuid: '', fileType: 'elibz2' }, /neither omitted nor a library/],
  ['a non-string libraryUuid', { uuid: SYMBOL_UUID, libraryUuid: 7, fileType: 'elibz2' }, /libraryUuid must be a string/],
  ['an unknown parameter', { uuid: SYMBOL_UUID, fileType: 'elibz2', path: 'E:/x.elibz2' }, /does not take path/],
  ['the un-widened timeout', { uuid: SYMBOL_UUID, fileType: 'elibz2', timeoutMs: 5_000 }, /does not take timeoutMs/],
];

for (const [label, params, pattern] of refusedBeforeHost) {
  test(`${label} is refused before the host is asked`, async () => {
    const { eda, calls } = fakeEda();
    const error = await failure(run(eda, ACTION, params));

    assert.equal(error.code, 'BAD_REQUEST', line(error));
    assert.match(error.message, pattern);
    assert.deepEqual(calls.symbolFile, [], 'nothing was forwarded to the editor');
  });
}

test('params that are not an object are refused', async () => {
  const { eda, calls } = fakeEda();
  const error = await failure(run(eda, ACTION, ['uuid']));

  assert.equal(error.code, 'BAD_REQUEST');
  assert.match(error.message, /params must be an object/);
  assert.deepEqual(calls.symbolFile, []);
});

// --------------------------------------------------------------------------
// Unreadable host: missing, throwing, refusing, empty
// --------------------------------------------------------------------------

test('a missing method is NOT_IMPLEMENTED with the exact path', async () => {
  const absent = await failure(run({}, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' }));
  assert.equal(absent.code, 'NOT_IMPLEMENTED');
  assert.equal(absent.detail.path, SOURCE);
  assert.match(absent.message, /getSymbolFileBySymbolUuid/);

  const wrongType = await failure(
    run({ sys_FileManager: { getSymbolFileBySymbolUuid: 'nope' } }, ACTION, {
      uuid: SYMBOL_UUID,
      fileType: 'elibz2',
    }),
  );
  assert.equal(wrongType.code, 'NOT_IMPLEMENTED');
  assert.equal(wrongType.detail.path, SOURCE);
});

test('a throwing getter on the path is NOT_IMPLEMENTED, not INTERNAL', async () => {
  // The host hands out objects whose property reads throw (measured 2026-09-14),
  // so the lookup itself has to survive a trap — a raw throw would answer
  // INTERNAL and lose the method name the report needs.
  const trap = new Proxy({}, {
    get() {
      throw new TypeError('Cannot read properties of undefined (reading \'prototype\')');
    },
  });
  const error = await failure(run({ sys_FileManager: trap }, ACTION, {
    uuid: SYMBOL_UUID,
    fileType: 'elibz2',
  }));

  assert.equal(error.code, 'NOT_IMPLEMENTED', line(error));
  assert.equal(error.detail.path, SOURCE);
  assert.match(error.message, /prototype/);
});

test('a host refusal keeps the host words and names this call\'s gate only', async () => {
  const { eda } = fakeEda({
    getSymbolFile: async () => {
      throw new Error('no permission to download library');
    },
  });
  const error = await failure(run(eda, ACTION, {
    uuid: SYMBOL_UUID,
    libraryUuid: LIBRARY_UUID,
    fileType: 'elibz2',
  }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /no permission to download library/);
  assert.match(error.message, /not knowable from here/);
  assert.equal(error.detail.thrown, true);
  assert.equal(error.detail.errorMessage, 'no permission to download library');
  assert.match(error.detail.gate, /下载库/);
  assert.deepEqual(
    error.detail.permissions,
    [error.detail.gate],
    'this action carries its own one-element gate list',
  );
});

test('undefined, null and zero bytes are failures, never empty symbols', async () => {
  for (const answer of [undefined, null]) {
    const { eda } = fakeEda({ getSymbolFile: async () => answer });
    const error = await failure(run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' }));
    assert.equal(error.code, 'CONNECTOR_ERROR', line(error));
    assert.match(error.message, new RegExp(`returned ${answer}`));
    assert.equal(error.detail.empty, true);
  }

  const zero = fakeEda({ getSymbolFile: async () => fileLike([], { name: 'empty.elibz2' }) });
  const error = await failure(run(zero.eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /zero-byte/);
});

test('a File without arrayBuffer() is a failure naming the path', async () => {
  const { eda } = fakeEda({
    getSymbolFile: async () => ({ name: 'symbol.elibz2', type: 'application/zip' }),
  });
  const error = await failure(run(eda, ACTION, { uuid: SYMBOL_UUID, fileType: 'elibz2' }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /no arrayBuffer/);
  assert.equal(error.detail.path, SOURCE);
});

// --------------------------------------------------------------------------
// Negative controls: the older contracts do not move
// --------------------------------------------------------------------------

test('lib.symbol.get still answers metadata only', async () => {
  const eda = {
    lib_Symbol: {
      async get(uuid, libraryUuid) {
        assert.equal(uuid, SYMBOL_UUID);
        assert.equal(libraryUuid, undefined);
        return { uuid, name: 'AMS1117-3.3', classification: ['Power'] };
      },
    },
  };
  const data = await run(eda, 'lib.symbol.get', { uuid: SYMBOL_UUID });

  assert.deepEqual(Object.keys(data).slice(0, 4), ['uuid', 'libraryUuid', 'found', 'item']);
  assert.equal(data.found, true);
  assert.equal(data.bytes, undefined, 'the old action never carries bytes');
  assert.equal(data.data, undefined);
});

test('the 025 archive refusal still carries its own two gates, untouched', async () => {
  const eda = {
    sys_FileManager: {
      getDocumentFile: async () => {
        throw new Error('no permission to export document');
      },
    },
  };
  const error = await failure(run(eda, 'sys.get_document_file', {}));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.equal(error.detail.permissions.length, 2, 'the old array is still two gates');
  assert.ok(error.detail.permissions.some((gate) => gate.includes('文件导出')));
  assert.ok(error.detail.permissions.some((gate) => gate.includes('下载工程')));
  assert.ok(
    !error.detail.permissions.some((gate) => gate.includes('下载库')),
    'this batch appended nothing to the 025 gate list',
  );
  assert.ok(
    !error.message.includes('下载库'),
    'and the old refusal text was not rewritten either',
  );
});
