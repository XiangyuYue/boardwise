/**
 * 038Q16B: `sch.place_project_cbb` — a project-local CBB block.
 *
 * Offline, against the real `buildHandlers()` registry with a fake `eda`. The
 * fake pins the three things a second placement path can get wrong: the
 * **graph** identity (`getSchematicInfo`), the **name resolution** (search rows
 * are index fields, `lib_Symbol.get(project)` is the authority, and the answer
 * must be unique), and the **project-symbol call** itself
 * (`create({libraryType:'2', libraryUuid: projectUuid, uuid}, x, y, '', 0,
 * false, true, true)`). Every post-placement reading must be able to say "no"
 * without losing the `primitiveId`/`state` evidence.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

const NAME = '晶振';
const LOCAL_SYMBOL = 'ca89fed3a434c5cb';
const SOURCE_LIBRARY = '08be6a96fc064a03b488fd9d5a25ccea';
const SCHEMATIC = 'cbb-schematic-uuid';
const PROJECT = 'project-uuid';
const PAGE = 'page-uuid';

/** A placed component as the host hands it back. */
function part(id, geometry, extras = {}) {
  const g = { type: 'part', x: 0, y: 0, rotation: 0, mirror: false, ...geometry };
  const obj = {
    __geometry: g,
    getState_PrimitiveId: () => id,
    getState_ComponentType: () => g.type,
    getState_X: () => g.x,
    getState_Y: () => g.y,
    getState_Rotation: () => g.rotation,
    getState_Mirror: () => g.mirror,
  };
  if (extras.symbol !== undefined) obj.getState_Symbol = () => extras.symbol;
  return obj;
}

/** The block a successful placement lands. */
function placedBlock(id, { x, y, uuid = LOCAL_SYMBOL }) {
  return part(id, { type: 'block_symbol', x, y, rotation: 0, mirror: false }, {
    symbol: { uuid },
  });
}

/** A pin as `getAllPinsByPrimitiveId` hands it back. */
function pin({ number, name, x, y, rotation = 180, length = 20 }) {
  return {
    getState_PinNumber: () => number,
    getState_PinName: () => name,
    getState_X: () => x,
    getState_Y: () => y,
    getState_Rotation: () => rotation,
    getState_PinLength: () => length,
  };
}

/**
 * A host with one focused page, one project-local CBB schematic and a symbol
 * catalogue. `rows` are the search's index rows (`name` may be an internal
 * title on purpose); `symbols` is what `lib_Symbol.get(uuid, 'project')` answers
 * per uuid. `lib_Cbb.get` **throws if it is ever called** — the project scope
 * must not reach it.
 */
function makeHost(options = {}) {
  const state = {
    components: (options.components ?? []).slice(),
    createCalls: [],
    searchCalls: [],
    getAllCalls: 0,
    focusedProject: options.focusedProject ?? PROJECT,
    focusedPage: options.focusedPage ?? PAGE,
    documentType: options.documentType ?? 1,
  };

  const graph = 'graph' in options ? options.graph : {
    uuid: SCHEMATIC,
    parentProjectUuid: PROJECT,
    name: NAME,
    itemType: 'CBB Schematic',
    cbbSymbol: { uuid: LOCAL_SYMBOL, type: 17, name: NAME },
  };

  const symbols = options.symbols ?? {
    [LOCAL_SYMBOL]: {
      uuid: LOCAL_SYMBOL, name: NAME, type: 17, libraryType: '2', libraryUuid: SOURCE_LIBRARY,
    },
  };
  const rows = options.rows ?? [{ uuid: LOCAL_SYMBOL, name: 'crystal_internal_title' }];

  const eda = {
    lib_Cbb: {
      get: () => {
        throw new Error('lib_Cbb.get must never be called for a project-local block');
      },
      search: async (query, libraryUuid, _classification, limit, page) => {
        state.searchCalls.push({ query, libraryUuid, limit, page });
        return rows;
      },
    },
    lib_Symbol: {
      get: async (uuid) => symbols[uuid],
    },
    dmt_Schematic: {
      getSchematicInfo: async () => graph,
    },
    dmt_Project: {
      getCurrentProjectInfo: () => ({ uuid: state.focusedProject }),
    },
    dmt_SelectControl: {
      getCurrentDocumentInfo: () => ({
        uuid: state.focusedPage,
        parentProjectUuid: state.focusedProject,
        documentType: state.documentType,
      }),
    },
    sch_PrimitiveComponent: {
      getAll: async () => {
        state.getAllCalls += 1;
        return state.components.slice();
      },
    },
  };

  if (!options.noCreate) {
    eda.sch_PrimitiveComponent.create = async (...args) => {
      state.createCalls.push(args);
      const [ref, x, y, , rotation, mirror] = args;
      const made = options.onCreate
        ? options.onCreate({ ref, x, y, rotation, mirror, state })
        : placedBlock('new-block', { x, y });
      if (made) state.components.push(made);
      return made;
    };
  }
  if (!options.noPins) {
    eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId = async () => options.pins ?? [];
  }
  return { eda, state };
}

const REQUEST = {
  schematicUuid: SCHEMATIC,
  expectedName: NAME,
  symbolUuid: LOCAL_SYMBOL,
  projectUuid: PROJECT,
  pageUuid: PAGE,
  x: 130,
  y: 90,
  rotation: 0,
  mirror: false,
};

function handler(eda) {
  const bound = buildHandlers(eda)['sch.place_project_cbb'];
  assert.equal(typeof bound, 'function', 'sch.place_project_cbb is not in buildHandlers');
  return bound;
}

async function call(options, params = {}) {
  const { eda, state } = makeHost(options);
  const result = await handler(eda)({ ...REQUEST, ...params });
  return { result, state };
}

test('a verified empty-port placement: one project symbol, fixed pose', async () => {
  const existing = part('r1', { type: 'part', x: 10, y: 20 });
  const { result, state } = await call({ components: [existing] });

  // The name was resolved from `lib_Symbol.get(project)`, not from the row's
  // internal title — but the search itself was asked for the display name.
  assert.deepEqual(state.searchCalls, [{
    query: NAME, libraryUuid: 'project', limit: 100, page: 1,
  }]);
  assert.equal(state.createCalls.length, 1);
  const [ref, x, y, designator, rotation, mirror, lock, auto] = state.createCalls[0];
  assert.deepEqual(ref, { libraryType: '2', libraryUuid: PROJECT, uuid: LOCAL_SYMBOL });
  assert.deepEqual(
    { x, y, designator, rotation, mirror, lock, auto },
    { x: 130, y: 90, designator: '', rotation: 0, mirror: false, lock: true, auto: true },
  );

  assert.equal(result.verified, true);
  assert.equal(result.partial, false);
  assert.equal(result.primitiveId, 'new-block');
  assert.equal(result.beforeCount, 1);
  assert.equal(result.preserved, true);
  assert.equal(result.graph.itemType, 'CBB Schematic');
  assert.equal(result.graph.cbbSymbol.uuid, LOCAL_SYMBOL);
  assert.equal(result.graph.cbbSymbol.type, 17);
  assert.equal(result.resolution.resolvedUuid, LOCAL_SYMBOL);
  assert.equal(result.resolution.sourceLibraryUuid, SOURCE_LIBRARY);
  assert.deepEqual(result.state, {
    id: 'new-block', type: 'block_symbol', x: 130, y: 90, rotation: 0, mirror: false,
  });
  assert.deepEqual(result.symbol, { uuid: LOCAL_SYMBOL });
  assert.deepEqual(result.pins, {
    source: 'sch_PrimitiveComponent.getAllPinsByPrimitiveId',
    readable: true,
    returned: 0,
    pins: [],
  });
});

test('a block with ports reports every pin the host can read', async () => {
  const { result } = await call({
    pins: [pin({ number: '1', name: 'XI', x: 30, y: 40 })],
  });
  assert.equal(result.verified, true);
  assert.equal(result.pins.returned, 1);
  assert.deepEqual(result.pins.pins, [
    { PinNumber: '1', PinName: 'XI', X: 30, Y: 40, Rotation: 180, PinLength: 20 },
  ]);
});

test('a graph that is not the requested CBB schematic is refused, zero writes', async () => {
  const { eda, state } = makeHost({
    graph: {
      uuid: SCHEMATIC,
      parentProjectUuid: PROJECT,
      name: NAME,
      itemType: 'Schematic',
      cbbSymbol: { uuid: LOCAL_SYMBOL, type: 17 },
    },
  });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /itemType/);
      return true;
    },
  );
  assert.equal(state.searchCalls.length, 0, 'the graph is proved before any search');
  assert.equal(state.createCalls.length, 0);
});

test('a graph whose cbbSymbol is not type 17 is refused', async () => {
  const { eda, state } = makeHost({
    graph: {
      uuid: SCHEMATIC,
      parentProjectUuid: PROJECT,
      name: NAME,
      itemType: 'CBB Schematic',
      cbbSymbol: { uuid: LOCAL_SYMBOL, type: 16 },
    },
  });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /cbbSymbol\.type/);
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a graph from another project is refused', async () => {
  const { eda, state } = makeHost({
    graph: {
      uuid: SCHEMATIC,
      parentProjectUuid: 'another-project',
      name: NAME,
      itemType: 'CBB Schematic',
      cbbSymbol: { uuid: LOCAL_SYMBOL, type: 17 },
    },
  });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /parentProjectUuid/);
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a name that resolves to two local symbols is refused, zero writes', async () => {
  const { eda, state } = makeHost({
    rows: [{ uuid: LOCAL_SYMBOL, name: 'internal-a' }, { uuid: 'second-local', name: 'internal-b' }],
    symbols: {
      [LOCAL_SYMBOL]: { uuid: LOCAL_SYMBOL, name: NAME, type: 17, libraryType: '2' },
      'second-local': { uuid: 'second-local', name: NAME, type: 17, libraryType: '2' },
    },
  });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.equal(error.detail.candidates.length, 2);
      assert.match(error.message, /exactly one is required/);
      return true;
    },
  );
  assert.equal(state.getAllCalls, 0, 'the refusal happens before the page is read');
  assert.equal(state.createCalls.length, 0);
});

test('a name that resolves to nothing is refused, zero writes', async () => {
  const { eda, state } = makeHost({
    rows: [{ uuid: 'other', name: 'other-title' }],
    symbols: { other: { uuid: 'other', name: '别的模块', type: 17, libraryType: '2' } },
  });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.equal(error.detail.candidates.length, 0);
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a symbolUuid that is not the resolved local uuid is refused', async () => {
  const { eda, state } = makeHost({});
  await assert.rejects(
    () => handler(eda)({ ...REQUEST, symbolUuid: 'some-other-symbol' }),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.equal(error.detail.resolvedUuid, LOCAL_SYMBOL);
      assert.match(error.message, /two different blocks/);
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a page that is not the requested one is PAGE_MISMATCH, before any write', async () => {
  const { eda, state } = makeHost({ focusedPage: 'another-page' });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.equal(error.detail.guard, 'page');
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a project that is not the focused one is PAGE_MISMATCH (guard: project)', async () => {
  const { eda, state } = makeHost({ focusedProject: 'another-project' });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.equal(error.detail.guard, 'project');
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a component that is not a block_symbol is partial, never verified', async () => {
  const { result } = await call({
    onCreate: ({ x, y }) => part('new-block', { type: 'part', x, y }, {
      symbol: { uuid: LOCAL_SYMBOL },
    }),
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.match(result.error.message, /block_symbol/);
  assert.equal(result.state.type, 'part');
});

test('a block bound to another symbol is partial, with the actual binding', async () => {
  const { result } = await call({
    onCreate: ({ x, y }) => placedBlock('new-block', { x, y, uuid: 'another-symbol' }),
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.deepEqual(result.symbol, { uuid: 'another-symbol' });
  assert.match(result.error.message, /symbol is/);
});

test('a pre-existing component whose geometry moved is partial, never verified', async () => {
  const existing = part('r1', { type: 'part', x: 10, y: 20 });
  const { result } = await call({
    components: [existing],
    onCreate: ({ x, y, state }) => {
      state.components[0].__geometry.x = 11;
      return placedBlock('new-block', { x, y });
    },
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.equal(result.preserved, false);
  assert.equal(result.primitiveId, 'new-block');
  assert.match(result.error.message, /changed geometry/);
});

test('an unreadable pin list is partial: unknown ports are not empty ports', async () => {
  const { result } = await call({ noPins: true });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.equal(result.pins.readable, false);
  assert.equal(result.pins.returned, null);
});

test('a host without sch_PrimitiveComponent.create is NOT_IMPLEMENTED, zero writes', async () => {
  const { eda, state } = makeHost({ noCreate: true });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'NOT_IMPLEMENTED');
      assert.equal(error.detail.path, 'sch_PrimitiveComponent.create');
      return true;
    },
  );
  assert.equal(state.getAllCalls, 0, 'a missing create is detected before the baseline read');
});

test('a host without lib_Symbol.get is NOT_IMPLEMENTED before the search', async () => {
  const { eda, state } = makeHost({});
  delete eda.lib_Symbol;
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'NOT_IMPLEMENTED');
      assert.equal(error.detail.path, 'lib_Symbol');
      return true;
    },
  );
  assert.equal(state.searchCalls.length, 0);
});

test('a create call that throws keeps the id-less evidence and says so', async () => {
  const { result } = await call({ onCreate: () => { throw new Error('host said no'); } });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.equal(result.primitiveId, null);
  assert.match(result.error.message, /sch_PrimitiveComponent\.create threw: host said no/);
});

test('rotation and mirror are fixed at 0/false in this action', async () => {
  const { eda } = makeHost({});
  for (const patch of [{ rotation: 90 }, { rotation: 180 }, { mirror: true }]) {
    await assert.rejects(
      () => handler(eda)({ ...REQUEST, ...patch }),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST');
        assert.match(error.message, /fixed at/);
        return true;
      },
      `expected a refusal for ${JSON.stringify(patch)}`,
    );
  }
  // …and an omitted pair is the fixed pose, not "whatever the host does".
  const { result } = await call({}, { rotation: undefined, mirror: undefined });
  assert.equal(result.verified, true);
  assert.deepEqual(result.requested, { x: 130, y: 90, rotation: 0, mirror: false });
});

test('the parameter contract is closed and typed', async () => {
  const { eda } = makeHost({});
  for (const [patch, pattern] of [
    [{ x: Number.NaN }, /x must be a finite number/],
    [{ y: '90' }, /y must be a finite number/],
    [{ expectedName: '' }, /expectedName/],
    [{ uuid: 'library-uuid' }, /does not take uuid/],
  ]) {
    await assert.rejects(
      () => handler(eda)({ ...REQUEST, ...patch }),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST');
        assert.match(error.message, pattern);
        return true;
      },
    );
  }
});
