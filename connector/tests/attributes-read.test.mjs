/**
 * 053P: `sch.list_attributes` — the attribute namespace read as data.
 *
 * The gap this action closes: `createNetLabel` answered `undefined` while two
 * V3 texts appeared in the render, and no read in the catalogue could say
 * whether those texts are `ISCH_PrimitiveAttribute` objects (i.e. addressable
 * through `parentPrimitiveId`) or decoration the canvas drew on its own. A
 * picture cannot answer that; the attribute namespace can.
 *
 * What is pinned here, all offline against a fake `eda`:
 *
 * 1. **`pageUuid` is required and checked first.** `guardPage` treats a missing
 *    uuid as "interactive probe, no guard", which is exactly wrong for a page
 *    read, so the emptiness check has to happen in this handler — and it has
 *    to happen *before* any host call.
 * 2. **The parent is forwarded as one argument, or not at all.** `getAll(p)`
 *    with the id, bare `getAll()` without it — never `getAll(undefined)`.
 * 3. **Every declared field is read by calling its getter**, and a field the
 *    host cannot hand over is named in `readErrors` with its attribute's id
 *    rather than silently appearing as `null`.
 * 4. **"Unknown" is never reported as "empty".** A missing namespace or
 *    `getAll` is `NOT_IMPLEMENTED` with the path; a non-array answer is
 *    `CONNECTOR_ERROR`. Only a real `[]` is a zero-attribute page.
 * 5. **Read-only.** The namespace's write surface (`createNetLabel` / `modify`
 *    / `delete`) is present in the fake and must never be called.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

const PAGE = 'page-1';

/** Which `getState_*` accessors the primitive exposes, and what they answer. */
function attribute(fields, { missing = [], throwing = [] } = {}) {
  const proto = {};
  for (const [key, value] of Object.entries(fields)) {
    if (missing.includes(key)) continue;
    if (throwing.includes(key)) {
      Object.defineProperty(proto, `getState_${key}`, {
        value() {
          throw new Error(`${key} is unreadable on this host`);
        },
      });
      continue;
    }
    proto[`getState_${key}`] = () => value;
  }
  return Object.create(proto);
}

/** Every field the type package declares, so a test can drop exactly one. */
const FULL_FIELDS = {
  PrimitiveId: '157f86e71e6e601b',
  ParentPrimitiveId: '826fcdf4abadc39b',
  Key: 'NET',
  Value: 'V3',
  X: 420,
  Y: 300,
  Rotation: 0,
  AlignMode: 2,
  FillColor: '#000000',
  KeyVisible: true,
  ValueVisible: true,
};

const V3_END = attribute(FULL_FIELDS);

/**
 * A window focused on `PAGE`, with a `sch_PrimitiveAttribute` namespace whose
 * `getAll` is recorded (arguments included) and whose write surface throws if
 * it is ever reached.
 */
function fakeWindow({ focus = PAGE, items = [V3_END], getAll } = {}) {
  const calls = { getAll: [], writeCalls: 0 };
  const namespace = {
    async getAll(...args) {
      calls.getAll.push(args);
      if (getAll) return getAll(...args);
      return items;
    },
    createNetLabel() {
      calls.writeCalls += 1;
      throw new Error('sch.list_attributes must never create a net label');
    },
    modify() {
      calls.writeCalls += 1;
      throw new Error('sch.list_attributes must never modify an attribute');
    },
    delete() {
      calls.writeCalls += 1;
      throw new Error('sch.list_attributes must never delete an attribute');
    },
  };
  const eda = {
    dmt_Schematic: { getCurrentSchematicPageInfo: async () => ({ uuid: focus }) },
    sch_PrimitiveAttribute: namespace,
    // Present so a wrong fallback would be visible rather than absent: the
    // attribute read must not be answered out of the net-label namespace.
    sch_PrimitiveNetLabel: {
      getAll: async () => {
        throw new Error('the net-label namespace must not be read');
      },
    },
  };
  return { eda, calls };
}

const call = (eda, params = {}) =>
  buildHandlers(eda)['sch.list_attributes']({ pageUuid: PAGE, ...params });

test('missing pageUuid is refused before any host call', async () => {
  const { eda, calls } = fakeWindow();
  for (const params of [{}, { pageUuid: '' }, { pageUuid: '   ' }, { pageUuid: 123 }]) {
    await assert.rejects(
      () => buildHandlers(eda)['sch.list_attributes'](params),
      (error) => {
        assert.equal(error.name, 'ActionError');
        assert.equal(error.code, 'BAD_REQUEST');
        assert.match(error.message, /pageUuid/);
        return true;
      },
    );
  }
  assert.deepEqual(calls.getAll, [], 'a refused request must not have read the page');
});

test('a pageUuid that is not the focused page is refused, and nothing is read', async () => {
  const { eda, calls } = fakeWindow({ focus: 'some-other-page' });
  await assert.rejects(
    () => call(eda, { pageUuid: PAGE }),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.match(error.message, /some-other-page/);
      assert.match(error.message, new RegExp(PAGE));
      return true;
    },
  );
  assert.deepEqual(calls.getAll, []);
});

test('every declared field is read back under its wire name', async () => {
  const { eda, calls } = fakeWindow();
  const data = await call(eda);

  assert.equal(data.pageUuid, PAGE);
  assert.equal(data.parentPrimitiveId, null);
  assert.equal(data.count, 1);
  assert.deepEqual(data.attributes, [{
    primitiveId: '157f86e71e6e601b',
    parentPrimitiveId: '826fcdf4abadc39b',
    key: 'NET',
    value: 'V3',
    x: 420,
    y: 300,
    rotation: 0,
    alignMode: 2,
    fillColor: '#000000',
    keyVisible: true,
    valueVisible: true,
  }]);
  assert.deepEqual(data.readErrors, [], 'a clean read must report no read errors');
  assert.equal(calls.writeCalls, 0);
});

test('no parent means the bare getAll(), a parent is forwarded as one argument', async () => {
  const bare = fakeWindow();
  await call(bare.eda);
  assert.deepEqual(bare.calls.getAll, [[]], 'getAll() must be called with no arguments');

  const scoped = fakeWindow();
  const data = await call(scoped.eda, { parentPrimitiveId: '826fcdf4abadc39b' });
  assert.deepEqual(scoped.calls.getAll, [['826fcdf4abadc39b']]);
  assert.equal(data.parentPrimitiveId, '826fcdf4abadc39b');
});

test('a present but empty or non-string parent is refused', async () => {
  const { eda, calls } = fakeWindow();
  for (const parentPrimitiveId of ['', '   ', 7, { id: 'x' }, true]) {
    await assert.rejects(
      () => call(eda, { parentPrimitiveId }),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST');
        assert.match(error.message, /parentPrimitiveId/);
        return true;
      },
    );
  }
  assert.deepEqual(calls.getAll, []);
});

test('a missing namespace or getAll is NOT_IMPLEMENTED, naming the path', async () => {
  const noNamespace = { dmt_Schematic: fakeWindow().eda.dmt_Schematic };
  await assert.rejects(
    () => call(noNamespace),
    (error) => {
      assert.equal(error.code, 'NOT_IMPLEMENTED');
      assert.match(error.message, /sch_PrimitiveAttribute/);
      return true;
    },
  );

  const noGetAll = fakeWindow();
  noGetAll.eda.sch_PrimitiveAttribute = { createNetLabel() {} };
  await assert.rejects(
    () => call(noGetAll.eda),
    (error) => {
      assert.equal(error.code, 'NOT_IMPLEMENTED');
      assert.match(error.message, /sch_PrimitiveAttribute\.getAll/);
      return true;
    },
  );
});

test('a non-array answer is an error, never an empty page', async () => {
  for (const answer of [undefined, null, { items: [] }, 'none']) {
    const { eda } = fakeWindow({ getAll: () => answer });
    await assert.rejects(
      () => call(eda),
      (error) => {
        assert.equal(error.code, 'CONNECTOR_ERROR');
        assert.match(error.message, /unknown, not empty/);
        return true;
      },
    );
  }
});

test('getAll throwing is reported with the call and the parent', async () => {
  const { eda } = fakeWindow({
    getAll: () => {
      throw new Error('host exploded');
    },
  });
  await assert.rejects(
    () => call(eda, { parentPrimitiveId: 'wire-1' }),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /host exploded/);
      assert.equal(error.detail.parentPrimitiveId, 'wire-1');
      return true;
    },
  );
});

test('an empty array is a real zero-attribute reading', async () => {
  const { eda } = fakeWindow({ items: [] });
  const data = await call(eda);
  assert.equal(data.count, 0);
  assert.deepEqual(data.attributes, []);
  assert.deepEqual(data.readErrors, []);
});

test('a field that throws is named with its attribute id, never filled in as null', async () => {
  const broken = attribute(
    {
      PrimitiveId: 'attr-1',
      ParentPrimitiveId: 'wire-1',
      Key: 'NET',
      Value: 'V3',
      X: 10,
      Y: 20,
      Rotation: 0,
      AlignMode: 2,
      FillColor: '#ff0000',
      KeyVisible: true,
      ValueVisible: true,
    },
    { throwing: ['FillColor'] },
  );
  const { eda } = fakeWindow({ items: [broken] });
  const data = await call(eda);

  assert.equal(data.count, 1);
  assert.equal('fillColor' in data.attributes[0], false, 'an unread field must not appear');
  assert.equal(data.attributes[0].value, 'V3', 'the other fields are still read');
  assert.equal(data.readErrors.length, 1);
  assert.match(data.readErrors[0], /^attr-1: /);
  assert.match(data.readErrors[0], /getState_FillColor/);
  assert.match(data.readErrors[0], /unreadable on this host/);
});

test('a field the host does not have is a read error too, not a null', async () => {
  const older = attribute(FULL_FIELDS, { missing: ['KeyVisible', 'ValueVisible'] });
  const { eda } = fakeWindow({ items: [older] });
  const data = await call(eda);

  assert.equal('keyVisible' in data.attributes[0], false);
  const named = data.readErrors.filter((line) => line.startsWith(`${FULL_FIELDS.PrimitiveId}: `));
  assert.equal(named.length, 2);
  assert.ok(named.some((line) => /getState_KeyVisible/.test(line)));
  assert.ok(named.some((line) => /getState_ValueVisible/.test(line)));
  assert.ok(named.every((line) => /not present/.test(line)));
});

test('an attribute whose own id is unreadable is reported by its position', async () => {
  const anonymous = attribute(FULL_FIELDS, { missing: ['PrimitiveId'] });
  const { eda } = fakeWindow({ items: [anonymous] });
  const data = await call(eda);

  assert.equal('primitiveId' in data.attributes[0], false);
  assert.equal(data.readErrors.length, 1);
  assert.match(data.readErrors[0], /^attribute\[0\]: /);
});
