/**
 * 038Q6: `lib.footprint_file.get` — one library footprint's own file, read-only.
 *
 * Why this action exists, in one measurement: `lib.footprint.get` answers the
 * package name (`SOT-223-3_L6.5-W3.4-P2.30-LS7.0-BR` for AMS1117 / C6186) and
 * nothing about PAD geometry, so a pad number, layer or shape has no source. The
 * container file is the remaining honest place to look, and the one host call
 * that produces it is exposed here — narrowly, and without pretending to know
 * what is inside.
 *
 * What this file pins, and why each one is here rather than left to the first
 * live run:
 *
 * 1. **The call shape** — exactly three positional arguments
 *    `(uuid, libraryUuid|undefined, fileType)`, with an omitted library sent as
 *    `undefined` rather than `''`, and the **footprint** method and nothing else
 *    on the path. Q3 measured that the host drops an argument it dislikes
 *    instead of rejecting, so a wrong shape settles as nothing at all.
 * 2. **Everything is refused before the host is called** — an unknown parameter,
 *    an array of uuids, an empty `libraryUuid`, a missing or foreign `fileType`.
 * 3. **The bytes are whole or the call failed** — a missing method, a throwing
 *    parent, a host refusal, `undefined`/`null`, zero bytes and a `File` with no
 *    `arrayBuffer` are all errors.
 * 4. **Observation is not verdict** — `isZip` reports two magic bytes and says
 *    so; the file name is cleaned but never read as an identity, the request
 *    uuid is not echoed back as proof of the container's contents, and no PAD,
 *    manifest, docType or member name is claimed anywhere in the answer.
 * 5. **Sharing did not move Q3** — `lib.symbol_file.get` still reads its own
 *    method with its own gate and answers the same shape, `lib.footprint.get`
 *    still answers metadata only, and the 025 archive refusal still carries its
 *    own two gates. Neither action's failure ladder was copied: both go through
 *    one internal reader, which is why the cross-checks here fail if either
 *    action reaches for the other's method.
 *
 * Everything goes through the real `buildHandlers()` registry, so a handler that
 * exists but was never registered fails here too. All offline: what the real host
 * answers for this call — whether it produces a file at all, and what its PAD
 * records mean — is a question this file deliberately does not claim to have
 * answered.
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

const ACTION = 'lib.footprint_file.get';
const SYMBOL_ACTION = 'lib.symbol_file.get';
const PATH = 'sys_FileManager.getFootprintFileByFootprintUuid';
const SYMBOL_PATH = 'sys_FileManager.getSymbolFileBySymbolUuid';
/** The AMS1117 / C6186 footprint the next batch wants to open. */
const FOOTPRINT_UUID = '20c29e37a9b84b4197418483096f9c05';
const LIBRARY_UUID = '0819f05c4eef4c71ace90d822a990e87';

/** Bytes that start with the ZIP magic, plus a little payload. */
const ZIP_BYTES = [0x50, 0x4b, 0x03, 0x04, 9, 8, 7, 6];

/** Bytes that are not a ZIP — an elibz2 we refuse to name further. */
const PLAIN_BYTES = [0x7b, 0x22, 0x61];

/** A host `File` stand-in: only the members the action reads. */
function fileLike(bytes, { name = 'footprint.elibz2', type = 'application/zip' } = {}) {
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

function fakeEda({ getFootprintFile, footprint = fileLike(ZIP_BYTES) } = {}) {
  const calls = { footprintFile: [], symbolFile: [], forbidden: [] };
  const ns = {
    async getFootprintFileByFootprintUuid(...args) {
      calls.footprintFile.push(args);
      return getFootprintFile ? getFootprintFile(...args) : footprint;
    },
    async getSymbolFileBySymbolUuid(...args) {
      calls.symbolFile.push(args);
      return fileLike(ZIP_BYTES, { name: 'symbol.elibz2' });
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
  const data = await run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' });

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
  assert.equal(data.uuid, FOOTPRINT_UUID);
  assert.equal(data.libraryUuid, null, 'an omitted library is reported as absent');
  assert.equal(data.fileType, 'elibz2');
  assert.equal(data.source, PATH);
  assert.equal(data.apiStatus, 'beta');
  assert.equal(data.encoding, 'base64');
  assert.equal(data.bytes, ZIP_BYTES.length);
  assert.equal(data.data, Buffer.from(ZIP_BYTES).toString('base64'), 'the bytes are whole');
  assert.equal(data.isZip, true);
});

test('the call sends exactly the three declared arguments, library omitted as undefined', async () => {
  const { eda, calls } = fakeEda();
  await run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' });

  // Declaration order is (footprintUuid, libraryUuid?, fileType?). A shorter call
  // would move fileType into the library slot, and the host would answer for a
  // library that does not exist rather than refuse.
  assert.deepEqual(calls.footprintFile, [[FOOTPRINT_UUID, undefined, 'elibz2']]);
  assert.equal(calls.footprintFile[0].length, 3, 'three arguments, not two');
});

test('an explicit library uuid is forwarded verbatim', async () => {
  const { eda, calls } = fakeEda();
  const data = await run(eda, ACTION, {
    uuid: FOOTPRINT_UUID,
    libraryUuid: LIBRARY_UUID,
    fileType: 'elibz2',
  });

  assert.deepEqual(calls.footprintFile, [[FOOTPRINT_UUID, LIBRARY_UUID, 'elibz2']]);
  assert.equal(data.libraryUuid, LIBRARY_UUID);
});

test('both container types are accepted and reported as asked', async () => {
  for (const fileType of ['elibz2', 'elibz']) {
    const { eda, calls } = fakeEda({
      getFootprintFile: async () => fileLike(PLAIN_BYTES, { name: `footprint.${fileType}` }),
    });
    const data = await run(eda, ACTION, {
      uuid: FOOTPRINT_UUID,
      libraryUuid: LIBRARY_UUID,
      fileType,
    });

    assert.equal(data.fileType, fileType);
    assert.deepEqual(calls.footprintFile, [[FOOTPRINT_UUID, LIBRARY_UUID, fileType]]);
  }
});

test('a non-ZIP header is reported as an observation, never as a format verdict', async () => {
  const { eda } = fakeEda({
    getFootprintFile: async () => fileLike(PLAIN_BYTES, { name: 'footprint.elibz2' }),
  });
  const data = await run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' });

  assert.equal(data.isZip, false);
  assert.equal(data.note, undefined, 'no elibz2 layout is claimed from two bytes');
  assert.equal(data.fileType, 'elibz2', 'the caller\'s fileType is what was asked for');
  assert.equal(data.bytes, PLAIN_BYTES.length);
});

test('the host file name is cleaned of path separators and never read as an identity', async () => {
  const { eda } = fakeEda({
    getFootprintFile: async () => fileLike(ZIP_BYTES, { name: '..\\..\\evil/elibz2.elibz2' }),
  });
  const data = await run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' });

  assert.equal(data.name, '.._.._evil_elibz2.elibz2');
  // The identity reported is the caller's request, in `uuid` — not a value
  // parsed out of the name, which is a host-side label with no contract.
  assert.equal(data.uuid, FOOTPRINT_UUID);
  assert.equal(data.identitySource, undefined, 'no identity is claimed from the file');
});

test('an untyped host file falls back to octet-stream, and the name may be empty', async () => {
  const { eda } = fakeEda({
    getFootprintFile: async () => fileLike(ZIP_BYTES, { name: '', type: '' }),
  });
  const data = await run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz' });

  assert.equal(data.mime, 'application/octet-stream');
  assert.equal(data.name, '');
});

test('the answer claims nothing about pads, manifests or container members', async () => {
  const { eda } = fakeEda();
  const data = await run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' });

  // The next batch reads the file to find out what a PAD record is. Until then
  // the answer must not carry a decoded guess under any name.
  for (const key of ['pads', 'pad', 'padCount', 'manifest', 'members', 'docType', 'footprintName']) {
    assert.equal(data[key], undefined, `${key} must not be invented from the header`);
  }
});

test('reading a file reaches no writing member of sys_FileManager', async () => {
  const { eda, calls } = fakeEda();
  await run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' });
  assert.deepEqual(calls.forbidden, [], 'no write surface was touched');
});

// --------------------------------------------------------------------------
// Refused before the host is called
// --------------------------------------------------------------------------

const refusedBeforeHost = [
  ['an array of uuids', { uuid: [FOOTPRINT_UUID, 'other'], fileType: 'elibz2' }, /single non-empty string/],
  ['an empty uuid', { uuid: '   ', fileType: 'elibz2' }, /single non-empty string/],
  ['a non-string uuid', { uuid: 42, fileType: 'elibz2' }, /single non-empty string/],
  ['a missing uuid', { fileType: 'elibz2' }, /single non-empty string/],
  ['a missing fileType', { uuid: FOOTPRINT_UUID }, /needs fileType/],
  ['a foreign fileType', { uuid: FOOTPRINT_UUID, fileType: 'pdf' }, /needs fileType/],
  ['an empty libraryUuid', { uuid: FOOTPRINT_UUID, libraryUuid: '', fileType: 'elibz2' }, /neither omitted nor a library/],
  ['a non-string libraryUuid', { uuid: FOOTPRINT_UUID, libraryUuid: 7, fileType: 'elibz2' }, /libraryUuid must be a string/],
  ['an unknown parameter', { uuid: FOOTPRINT_UUID, fileType: 'elibz2', path: 'E:/x.elibz2' }, /does not take path/],
  ['the un-widened timeout', { uuid: FOOTPRINT_UUID, fileType: 'elibz2', timeoutMs: 5_000 }, /does not take timeoutMs/],
];

for (const [label, params, pattern] of refusedBeforeHost) {
  test(`${label} is refused before the host is asked`, async () => {
    const { eda, calls } = fakeEda();
    const error = await failure(run(eda, ACTION, params));

    assert.equal(error.code, 'BAD_REQUEST', line(error));
    assert.match(error.message, pattern);
    assert.deepEqual(calls.footprintFile, [], 'nothing was forwarded to the editor');
    assert.deepEqual(calls.symbolFile, [], 'and the shared reader did not reach the symbol path');
  });
}

test('params that are not an object are refused', async () => {
  const { eda, calls } = fakeEda();
  const error = await failure(run(eda, ACTION, ['uuid']));

  assert.equal(error.code, 'BAD_REQUEST');
  assert.match(error.message, /params must be an object/);
  assert.deepEqual(calls.footprintFile, []);
});

test('a refusal names this action and this noun, not the symbol read\'s', async () => {
  const { eda } = fakeEda();
  const error = await failure(run(eda, ACTION, { uuid: [FOOTPRINT_UUID], fileType: 'elibz2' }));

  assert.match(error.message, /^lib\.footprint_file\.get needs uuid/);
  assert.match(error.message, /one footprint per call/);
  assert.ok(!error.message.includes('symbol'), 'the shared reader keeps its nouns apart');
});

// --------------------------------------------------------------------------
// Unreadable host: missing, throwing, refusing, empty
// --------------------------------------------------------------------------

test('a missing method is NOT_IMPLEMENTED with the exact path', async () => {
  const absent = await failure(run({}, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' }));
  assert.equal(absent.code, 'NOT_IMPLEMENTED');
  assert.equal(absent.detail.path, PATH);
  assert.match(absent.message, /getFootprintFileByFootprintUuid/);

  const wrongType = await failure(
    run({ sys_FileManager: { getFootprintFileByFootprintUuid: 'nope' } }, ACTION, {
      uuid: FOOTPRINT_UUID,
      fileType: 'elibz2',
    }),
  );
  assert.equal(wrongType.code, 'NOT_IMPLEMENTED');
  assert.equal(wrongType.detail.path, PATH);

  // A host that has *only* the symbol method is still a missing footprint
  // method: the two actions must never fall through to each other.
  const symbolOnly = await failure(
    run({ sys_FileManager: { getSymbolFileBySymbolUuid: async () => fileLike(ZIP_BYTES) } }, ACTION, {
      uuid: FOOTPRINT_UUID,
      fileType: 'elibz2',
    }),
  );
  assert.equal(symbolOnly.code, 'NOT_IMPLEMENTED');
  assert.equal(symbolOnly.detail.path, PATH);
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
    uuid: FOOTPRINT_UUID,
    fileType: 'elibz2',
  }));

  assert.equal(error.code, 'NOT_IMPLEMENTED', line(error));
  assert.equal(error.detail.path, PATH);
  assert.match(error.message, /prototype/);
});

test('a host refusal keeps the host words and names this call\'s gate only', async () => {
  const { eda } = fakeEda({
    getFootprintFile: async () => {
      throw new Error('no permission to download library');
    },
  });
  const error = await failure(run(eda, ACTION, {
    uuid: FOOTPRINT_UUID,
    libraryUuid: LIBRARY_UUID,
    fileType: 'elibz2',
  }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /no permission to download library/);
  assert.match(error.message, /not knowable from here/);
  assert.equal(error.detail.thrown, true);
  assert.equal(error.detail.errorMessage, 'no permission to download library');
  assert.match(error.detail.gate, /下载库/);
  assert.match(error.detail.gate, /getFootprintFileByFootprintUuid/);
  assert.deepEqual(
    error.detail.permissions,
    [error.detail.gate],
    'this action carries its own one-element gate list',
  );
});

test('undefined, null and zero bytes are failures, never empty footprints', async () => {
  for (const answer of [undefined, null]) {
    const { eda } = fakeEda({ getFootprintFile: async () => answer });
    const error = await failure(run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' }));
    assert.equal(error.code, 'CONNECTOR_ERROR', line(error));
    assert.match(error.message, new RegExp(`returned ${answer}`));
    assert.match(error.message, /empty footprint/);
    assert.equal(error.detail.empty, true);
  }

  const zero = fakeEda({ getFootprintFile: async () => fileLike([], { name: 'empty.elibz2' }) });
  const error = await failure(run(zero.eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' }));
  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /zero-byte/);
  assert.equal(error.detail.path, PATH);
});

test('a File without arrayBuffer() is a failure naming the path', async () => {
  const { eda } = fakeEda({
    getFootprintFile: async () => ({ name: 'footprint.elibz2', type: 'application/zip' }),
  });
  const error = await failure(run(eda, ACTION, { uuid: FOOTPRINT_UUID, fileType: 'elibz2' }));

  assert.equal(error.code, 'CONNECTOR_ERROR');
  assert.match(error.message, /no arrayBuffer/);
  assert.equal(error.detail.path, PATH);
});

// --------------------------------------------------------------------------
// Negative controls: the shared reader did not move the older contracts
// --------------------------------------------------------------------------

test('lib.symbol_file.get still reads the symbol method with its own gate', async () => {
  const { eda, calls } = fakeEda();
  const data = await run(eda, SYMBOL_ACTION, { uuid: 'sym', fileType: 'elibz2' });

  assert.deepEqual(calls.symbolFile, [['sym', undefined, 'elibz2']]);
  assert.deepEqual(calls.footprintFile, [], 'the symbol read never touches the footprint path');
  assert.equal(data.source, SYMBOL_PATH);
  assert.equal(data.libraryUuid, null);
  assert.equal(data.encoding, 'base64');

  const refused = await failure(
    run({ sys_FileManager: { getFootprintFileByFootprintUuid: async () => fileLike(ZIP_BYTES) } },
      SYMBOL_ACTION, { uuid: 'sym', fileType: 'elibz2' }),
  );
  assert.equal(refused.code, 'NOT_IMPLEMENTED');
  assert.equal(refused.detail.path, SYMBOL_PATH);
});

test('lib.symbol_file.get still names its own action and its own noun', async () => {
  // The shared reader's noun is per-action data: the symbol read still says
  // "one symbol per call", and still names its own action in the same refusal.
  const { eda } = fakeEda();
  const error = await failure(run(eda, SYMBOL_ACTION, { uuid: [1], fileType: 'elibz2' }));
  assert.match(error.message, /^lib\.symbol_file\.get needs uuid/);
  assert.match(error.message, /one symbol per call/);
});

test('lib.footprint.get still answers metadata only', async () => {
  const eda = {
    lib_Footprint: {
      async get(uuid, libraryUuid) {
        assert.equal(uuid, FOOTPRINT_UUID);
        assert.equal(libraryUuid, undefined);
        return {
          uuid,
          name: 'SOT-223-3_L6.5-W3.4-P2.30-LS7.0-BR',
          pads: undefined,
        };
      },
    },
  };
  const data = await run(eda, 'lib.footprint.get', { uuid: FOOTPRINT_UUID });

  assert.deepEqual(Object.keys(data).slice(0, 4), ['uuid', 'libraryUuid', 'found', 'name']);
  assert.equal(data.found, true);
  assert.equal(data.name, 'SOT-223-3_L6.5-W3.4-P2.30-LS7.0-BR');
  assert.equal(data.bytes, undefined, 'the metadata action still carries no bytes');
  assert.equal(data.isZip, undefined);
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
});

test('the probe call allowlist did not grow', async () => {
  // `PROBE_CALL_ACTIONS` exists so a not-yet-restarted daemon can reach a
  // freshly registered action; this one rides the catalogue like every other.
  const source = readFileSync(new URL('../src/actions.ts', import.meta.url), 'utf8')
    .replace(/\r\n/g, '\n');
  const start = source.indexOf('const PROBE_CALL_ACTIONS');
  assert.ok(start > 0, 'the allowlist is gone — did actions.ts move?');
  const block = source.slice(start, source.indexOf('\n};', start));

  assert.ok(block.includes('sys.get_document_file'), 'the allowlist parse found the real block');
  assert.ok(!block.includes(ACTION), `${ACTION} must ride the catalogue, not the probe bypass`);
  assert.ok(!block.includes(SYMBOL_ACTION), 'and the 038Q3 action is unchanged too');
});
