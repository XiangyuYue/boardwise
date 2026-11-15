/**
 * 038Q15: `sch.place_cbb` — a native reuse module (CBB) placed as a block.
 *
 * Everything here is offline, against the real `buildHandlers()` registry with a
 * fake `eda`. What the fake is *for*, case by case: the module/project/page
 * guards must refuse with **zero writes**, the single host call must carry the
 * declaration's exact argument shape, and every post-placement reading —
 * `block_symbol`, pose, CBB/CBB-symbol identity, the component diff and the pin
 * array — must be able to say "no" without the handler throwing the evidence
 * away.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

const CBB = {
  uuid: 'cbb-晶振-uuid',
  libraryUuid: 'lib-personal-uuid',
  name: '晶振',
};
const SYMBOL = 'cbb-symbol-uuid';
const PROJECT = 'project-uuid';
const PAGE = 'page-uuid';

/** A placed component as the host hands it back: `getState_*` accessors. */
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
  if (extras.cbb !== undefined) obj.getState_Cbb = () => extras.cbb;
  if (extras.cbbSymbol !== undefined) obj.getState_CbbSymbol = () => extras.cbbSymbol;
  return obj;
}

/** The block a successful placement lands, bound to `CBB` and `SYMBOL`. */
function placedBlock(id, { x, y, rotation, mirror }) {
  return part(id, { type: 'block_symbol', x, y, rotation, mirror }, {
    cbb: { uuid: CBB.uuid, libraryUuid: CBB.libraryUuid },
    cbbSymbol: { uuid: SYMBOL, cbbUuid: CBB.uuid, libraryUuid: CBB.libraryUuid },
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
 * A host with one focused page and a native CBB.
 *
 * Knobs: `components` (the page as it stands), `cbbAnswer` (`null` = the module
 * cannot be read back), `symbol` (`lib_Symbol.get`'s answer; `undefined` is the
 * 038Q15 sample), `pins`, `noCreate` / `noPins` (the two APIs the connector must
 * survive without), `onCreate` (what the placement actually lands) and the
 * project/page identity the editor reports.
 */
function makeHost(options = {}) {
  const state = {
    components: (options.components ?? []).slice(),
    createCalls: [],
    getAllCalls: 0,
    focusedProject: options.focusedProject ?? PROJECT,
    focusedPage: options.focusedPage ?? PAGE,
    documentType: options.documentType ?? 1,
  };

  const eda = {
    lib_Cbb: {
      get: async (uuid, libraryUuid) => {
        if (options.cbbAnswer === null) return undefined;
        return options.cbbAnswer
          ?? { uuid, libraryUuid, name: CBB.name, boards: [] };
      },
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
    lib_Symbol: {
      get: async () => ('symbol' in options ? options.symbol : undefined),
    },
    sch_PrimitiveComponent: {
      getAll: async () => {
        state.getAllCalls += 1;
        return state.components.slice();
      },
    },
  };

  if (!options.noCreate) {
    eda.sch_PrimitiveComponent.createCbbSymbol = async (ref, x, y, rotation, mirror) => {
      state.createCalls.push({ ref, x, y, rotation, mirror });
      const made = options.onCreate
        ? options.onCreate({ ref, x, y, rotation, mirror, state })
        : placedBlock('new-block', { x, y, rotation, mirror });
      if (made) state.components.push(made);
      return made;
    };
  }
  if (!options.noPins) {
    eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId = async () => options.pins ?? [];
  }
  return { eda, state };
}

/** The request every case starts from: one 90° block and nothing else. */
const REQUEST = {
  uuid: CBB.uuid,
  libraryUuid: CBB.libraryUuid,
  expectedName: CBB.name,
  symbolUuid: SYMBOL,
  projectUuid: PROJECT,
  pageUuid: PAGE,
  x: 120,
  y: 80,
  rotation: 90,
  mirror: false,
  // The 038Q15 sample's symbol is not readable through `lib_Symbol`, so every
  // case but the refusal one carries the caller's explicit allowance.
  allowUnverifiedSourceSymbol: true,
};

/** The same request with the allowance *omitted* — the shape that refuses. */
const { allowUnverifiedSourceSymbol: _omit, ...REQUEST_WITHOUT_ALLOWANCE } = REQUEST;

function handler(eda) {
  const bound = buildHandlers(eda)['sch.place_cbb'];
  assert.equal(typeof bound, 'function', 'sch.place_cbb is not in buildHandlers');
  return bound;
}

async function call(options, params = {}) {
  const { eda, state } = makeHost(options);
  const result = await handler(eda)({ ...REQUEST, ...params });
  return { result, state };
}

test('a verified empty-port placement: one block, nothing else touched', async () => {
  const existing = part('r1', { type: 'part', x: 10, y: 20, rotation: 0, mirror: false });
  const { result, state } = await call({ components: [existing] });

  assert.equal(state.createCalls.length, 1);
  assert.deepEqual(state.createCalls[0], {
    ref: { libraryUuid: CBB.libraryUuid, cbbUuid: CBB.uuid, uuid: SYMBOL },
    x: 120,
    y: 80,
    rotation: 90,
    mirror: false,
  });

  assert.equal(result.verified, true);
  assert.equal(result.partial, false);
  assert.equal(result.primitiveId, 'new-block');
  assert.equal(result.beforeCount, 1);
  assert.equal(result.preserved, true);
  assert.deepEqual(result.state, {
    id: 'new-block', type: 'block_symbol', x: 120, y: 80, rotation: 90, mirror: false,
  });
  assert.deepEqual(result.cbb, { uuid: CBB.uuid, libraryUuid: CBB.libraryUuid });
  assert.deepEqual(result.cbbSymbol, {
    uuid: SYMBOL, cbbUuid: CBB.uuid, libraryUuid: CBB.libraryUuid,
  });
  // The empty array is the *measured* reading for this sample, not a stub.
  assert.deepEqual(result.pins, {
    source: 'sch_PrimitiveComponent.getAllPinsByPrimitiveId',
    readable: true,
    returned: 0,
    pins: [],
  });
  assert.deepEqual(result.symbolVerification, {
    source: 'lib_Symbol.get',
    readable: false,
    mode: 'unverified-source-symbol',
    allowedBy: 'allowUnverifiedSourceSymbol',
    checked: [],
  });
});

test('a block with ports reports every pin the host can read', async () => {
  const { result } = await call({
    pins: [
      pin({ number: '1', name: 'XI', x: 30, y: 40 }),
      pin({ number: '2', name: 'XO', x: 30, y: 60, rotation: 0, length: 15 }),
    ],
  });

  assert.equal(result.verified, true);
  assert.equal(result.pins.readable, true);
  assert.equal(result.pins.returned, 2);
  assert.deepEqual(result.pins.pins, [
    { PinNumber: '1', PinName: 'XI', X: 30, Y: 40, Rotation: 180, PinLength: 20 },
    { PinNumber: '2', PinName: 'XO', X: 30, Y: 60, Rotation: 0, PinLength: 15 },
  ]);
});

test('a readable source symbol is verified field by field', async () => {
  const { result } = await call({
    symbol: {
      uuid: SYMBOL, libraryUuid: CBB.libraryUuid, type: 17, cbbUuid: CBB.uuid,
    },
  });
  assert.equal(result.verified, true);
  assert.equal(result.symbolVerification.readable, true);
  assert.equal(result.symbolVerification.mode, 'direct');
  assert.deepEqual(result.symbolVerification.checked, ['uuid', 'libraryUuid', 'type', 'cbbUuid']);
});

test('an unreadable symbol is refused with zero writes unless the caller allows it', async () => {
  const refused = makeHost({});
  await assert.rejects(
    () => handler(refused.eda)(REQUEST_WITHOUT_ALLOWANCE),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /allowUnverifiedSourceSymbol/);
      return true;
    },
  );
  assert.equal(refused.state.getAllCalls, 0, 'the refusal must happen before any page read');
  assert.equal(refused.state.createCalls.length, 0);

  // The same host, with the caller's own evidence asserted for it.
  const allowed = await call({}, { allowUnverifiedSourceSymbol: true });
  assert.equal(allowed.result.verified, true);
  assert.equal(allowed.result.symbolVerification.mode, 'unverified-source-symbol');
});

test('a source symbol that contradicts the request is refused with zero writes', async () => {
  const { eda, state } = makeHost({ symbol: { uuid: SYMBOL, type: 15 } });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /type 15/);
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a module whose readback name differs is refused with zero writes', async () => {
  const { eda, state } = makeHost({
    cbbAnswer: { uuid: CBB.uuid, libraryUuid: CBB.libraryUuid, name: '别的模块', boards: [] },
  });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /expected/);
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a module the library cannot read back is refused with zero writes', async () => {
  const { eda, state } = makeHost({ cbbAnswer: null });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /found nothing/);
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
      assert.equal(error.detail.actual, 'another-page');
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
  assert.equal(state.getAllCalls, 0);
});

test('a project that is not the requested one is PAGE_MISMATCH (guard: project)', async () => {
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

test('a document that is not a schematic page is refused', async () => {
  const { eda, state } = makeHost({ documentType: 3 });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.match(error.message, /schematic page/);
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a host without createCbbSymbol is NOT_IMPLEMENTED, not a silent miss', async () => {
  const { eda, state } = makeHost({ noCreate: true });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'NOT_IMPLEMENTED');
      assert.equal(error.detail.path, 'sch_PrimitiveComponent.createCbbSymbol');
      return true;
    },
  );
  assert.equal(state.getAllCalls, 0);
});

test('a duplicated id in the baseline refuses the write', async () => {
  const dup = part('same-id', { x: 1, y: 2 });
  const { eda, state } = makeHost({ components: [dup, part('same-id', { x: 3, y: 4 })] });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.equal(error.detail.reason, 'inventory-duplicate-id');
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('an incomplete baseline (no boolean mirror) refuses the write', async () => {
  const broken = part('broken', { x: 1, y: 2 });
  delete broken.getState_Mirror;
  const { eda, state } = makeHost({ components: [broken] });
  await assert.rejects(
    () => handler(eda)(REQUEST),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.equal(error.detail.reason, 'inventory-incomplete');
      return true;
    },
  );
  assert.equal(state.createCalls.length, 0);
});

test('a pre-existing component whose geometry moved is partial, never verified', async () => {
  const existing = part('r1', { type: 'part', x: 10, y: 20, rotation: 0, mirror: false });
  const { result } = await call({
    components: [existing],
    onCreate: ({ x, y, rotation, mirror, state }) => {
      // The host "helpfully" snapped the old part while placing the block.
      state.components[0].__geometry.x = 11;
      return placedBlock('new-block', { x, y, rotation, mirror });
    },
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.equal(result.preserved, false);
  assert.equal(result.primitiveId, 'new-block', 'the id is kept as evidence');
  assert.match(result.error.message, /changed geometry/);
});

test('a component that is not a block_symbol is partial, never verified', async () => {
  const { result } = await call({
    onCreate: ({ x, y, rotation, mirror }) => part('new-block', {
      type: 'part', x, y, rotation, mirror,
    }, {
      cbb: { uuid: CBB.uuid, libraryUuid: CBB.libraryUuid },
      cbbSymbol: { uuid: SYMBOL, cbbUuid: CBB.uuid, libraryUuid: CBB.libraryUuid },
    }),
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.match(result.error.message, /block_symbol/);
  assert.equal(result.state.type, 'part');
});

test('a block bound to another module is partial, with the actual identity reported', async () => {
  const { result } = await call({
    onCreate: ({ x, y, rotation, mirror }) => part('new-block', {
      type: 'block_symbol', x, y, rotation, mirror,
    }, {
      cbb: { uuid: 'another-cbb', libraryUuid: CBB.libraryUuid },
      cbbSymbol: { uuid: SYMBOL, cbbUuid: 'another-cbb', libraryUuid: CBB.libraryUuid },
    }),
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.deepEqual(result.cbb, { uuid: 'another-cbb', libraryUuid: CBB.libraryUuid });
  assert.match(result.error.message, /CBB is/);
});

test('a placement that changed the pose is partial, with the actual pose reported', async () => {
  const { result } = await call({
    onCreate: ({ x, y, rotation, mirror }) => placedBlock('new-block', {
      x, y, rotation: rotation + 90, mirror,
    }),
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.equal(result.state.rotation, 180);
  assert.match(result.error.message, /pose/);
});

test('an unreadable pin list is partial: unknown ports are not empty ports', async () => {
  const { result } = await call({ noPins: true });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.equal(result.pins.readable, false);
  assert.equal(result.pins.returned, null);
  assert.equal(result.primitiveId, 'new-block');
});

test('a create call that throws keeps the id-less evidence and says so', async () => {
  const { result } = await call({
    onCreate: () => { throw new Error('host said no'); },
  });
  assert.equal(result.verified, false);
  assert.equal(result.partial, true);
  assert.equal(result.primitiveId, null);
  assert.match(result.error.message, /createCbbSymbol threw: host said no/);
});

test('the parameter contract is closed and typed', async () => {
  const { eda } = makeHost({});
  for (const [patch, pattern] of [
    [{ rotation: 45 }, /rotation/],
    [{ rotation: '90' }, /rotation/],
    [{ x: Number.POSITIVE_INFINITY }, /x must be a finite number/],
    [{ y: '80' }, /y must be a finite number/],
    [{ mirror: 'false' }, /mirror/],
    [{ allowUnverifiedSourceSymbol: 'yes' }, /allowUnverifiedSourceSymbol/],
    [{ uuid: '' }, /uuid/],
    [{ width: 1 }, /does not take width/],
  ]) {
    await assert.rejects(
      () => handler(eda)({ ...REQUEST, ...patch }),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST');
        assert.match(error.message, pattern);
        return true;
      },
      `expected a refusal for ${JSON.stringify(patch)}`,
    );
  }
});
