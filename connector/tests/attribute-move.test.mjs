/**
 * 053Q: `sch.move_attribute` — the constrained attribute move.
 *
 * The gap: 053P could **read** an attribute and nothing could place one, so a
 * net name that is an attribute (R900's `Designator`, the wire's two `V3` texts)
 * could be seen and not moved. This action moves one attribute's text position,
 * and only after proving which attribute it is.
 *
 * What is pinned here:
 *
 * 1. **Everything that identifies the attribute is required**, and an id that is
 *    not on the page, or whose parent / key / value differ from what the caller
 *    said, is refused **before any write**. `expectedValue` may be `''` but must
 *    be a string — the API's `Name` value `={Value}` is compared literally.
 * 2. **The write surface is a closed allowlist.** `x`/`y`/`rotation` are finite
 *    numbers, `alignMode` a declared `ESCH_PrimitiveTextAlignMode` (1..9),
 *    `valueVisible` (053U) a strict boolean, at least one of the five; any other
 *    parameter (`key`, `value`, `keyVisible`, font, colour, an unknown name) is
 *    refused and never reaches `modify`.
 * 3. **`applied` comes from a fresh `get(primitiveId)`**, not from `modify`'s
 *    return value: `modify` may answer `undefined` and land anyway, and a move
 *    that did not take has to come back as an error listing `mismatched`.
 *
 * All offline, against a fake `eda`; nothing here touches an editor.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

const PAGE = 'page-1';
const ATTR = 'attr-1';
const PARENT = 'wire-1';

const BASE = {
  PrimitiveId: ATTR,
  ParentPrimitiveId: PARENT,
  Key: 'Name',
  Value: 'V3',
  X: 370,
  Y: 300,
  Rotation: 0,
  AlignMode: 2,
  ValueVisible: true,
};

/** An editor primitive whose `getState_*` getters sit on the prototype. */
class FakeAttribute {
  constructor(fields) {
    this.fields = { ...fields };
  }
}

for (const name of [
  'PrimitiveId', 'ParentPrimitiveId', 'Key', 'Value', 'X', 'Y', 'Rotation',
  'AlignMode', 'ValueVisible',
]) {
  Object.defineProperty(FakeAttribute.prototype, `getState_${name}`, {
    value() {
      return this.fields[name];
    },
  });
}

/**
 * A window focused on `PAGE` with one attribute, and a recorder for every host
 * call. The default `modify` behaves like the measured host: it moves the text
 * and answers `undefined`.
 */
function fakeWindow({
  focus = PAGE,
  attributes = [new FakeAttribute(BASE)],
  modifyImpl,
  getImpl,
  omit = [],
  noValueVisiblePort = false,
} = {}) {
  const calls = { getAll: [], modify: [], get: [] };
  const findAll = (id) => attributes.filter((a) => a.fields.PrimitiveId === id)[0];
  if (noValueVisiblePort) {
    // A host that can list attributes but cannot hand `ValueVisible` back: the
    // accessor is absent, which is an error, not a null field.
    for (const attribute of attributes) {
      Object.defineProperty(attribute, 'getState_ValueVisible', { value: undefined });
    }
  }
  const namespace = {
    async getAll(...args) {
      calls.getAll.push(args);
      return attributes;
    },
    async modify(id, property) {
      calls.modify.push([id, property]);
      if (modifyImpl) return modifyImpl(id, property, attributes);
      const target = findAll(id);
      if (!target) return undefined;
      for (const [key, value] of Object.entries(property)) {
        const state = {
          x: 'X', y: 'Y', rotation: 'Rotation', alignMode: 'AlignMode',
          valueVisible: 'ValueVisible',
        }[key];
        target.fields[state] = value;
      }
      return undefined;
    },
    async get(...args) {
      calls.get.push(args);
      if (getImpl) return getImpl(args[0], attributes);
      return findAll(args[0]);
    },
  };
  for (const name of omit) delete namespace[name];
  const eda = {
    dmt_Schematic: { getCurrentSchematicPageInfo: async () => ({ uuid: focus }) },
    sch_PrimitiveAttribute: namespace,
  };
  return { eda, calls };
}

const params = (extra = {}) => ({
  pageUuid: PAGE,
  primitiveId: ATTR,
  parentPrimitiveId: PARENT,
  expectedKey: 'Name',
  expectedValue: 'V3',
  ...extra,
});

const call = (eda, extra = {}) => buildHandlers(eda)['sch.move_attribute'](params(extra));

test('every identity parameter is required, and a refusal writes nothing', async () => {
  const cases = [
    { pageUuid: undefined },
    { pageUuid: '' },
    { primitiveId: undefined },
    { primitiveId: 42 },
    { parentPrimitiveId: '' },
    { expectedKey: '' },
    { expectedKey: 7 },
    { expectedValue: undefined },
    { expectedValue: 3 },
    { expectedValue: null },
  ];
  for (const override of cases) {
    const { eda, calls } = fakeWindow();
    const input = params({ x: 1 });
    for (const [key, value] of Object.entries(override)) {
      if (value === undefined) delete input[key];
      else input[key] = value;
    }
    await assert.rejects(
      () => buildHandlers(eda)['sch.move_attribute'](input),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(input));
        return true;
      },
    );
    assert.deepEqual(calls.modify, [], 'a refused call must not write');
  }
});

test('an empty expectedValue is legal; the comparison is a string comparison', async () => {
  const empty = new FakeAttribute({ ...BASE, Key: 'Color', Value: '' });
  const { eda, calls } = fakeWindow({ attributes: [empty] });
  const data = await call(eda, {
    expectedKey: 'Color', expectedValue: '', x: 10, y: 20,
  });
  assert.equal(data.applied, true);
  assert.equal(data.before.value, '');
  assert.equal(calls.modify.length, 1);
});

test('key / value / keyVisible / font / colour / unknown params are refused, not forwarded', async () => {
  const forbidden = [
    { key: 'NET' }, { value: 'V2' }, { keyVisible: false },
    { fontSize: 12 }, { color: '#ff0000' }, { fillColor: '#00ff00' }, { bold: true },
    { fontName: 'Arial' }, { anything: 1 },
  ];
  for (const extra of forbidden) {
    const { eda, calls } = fakeWindow();
    await assert.rejects(
      () => call(eda, { x: 1, ...extra }),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST');
        assert.match(error.message, /refusing/);
        return true;
      },
    );
    assert.deepEqual(calls.modify, []);
  }
});

test('at least one pose field is required', async () => {
  const { eda, calls } = fakeWindow();
  await assert.rejects(
    () => call(eda),
    (error) => {
      assert.equal(error.code, 'BAD_REQUEST');
      assert.match(error.message, /at least one/);
      return true;
    },
  );
  assert.deepEqual(calls.getAll, []);
});

test('x / y / rotation must be finite numbers, alignMode a declared value', async () => {
  for (const bad of [{ x: '10' }, { y: null }, { x: NaN }, { y: Infinity }, { rotation: '90' }]) {
    const { eda, calls } = fakeWindow();
    await assert.rejects(
      () => call(eda, bad),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(bad));
        return true;
      },
    );
    assert.deepEqual(calls.modify, []);
  }
  for (const alignMode of [0, 10, 2.5, '2', true]) {
    const { eda, calls } = fakeWindow();
    await assert.rejects(
      () => call(eda, { alignMode }),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST', String(alignMode));
        return true;
      },
    );
    assert.deepEqual(calls.modify, []);
  }
  const ok = fakeWindow();
  await call(ok.eda, { alignMode: 9 });
  assert.deepEqual(ok.calls.modify[0][1], { alignMode: 9 });
});

test('a page that is not in front is refused and nothing is read', async () => {
  const { eda, calls } = fakeWindow({ focus: 'other-page' });
  await assert.rejects(
    () => call(eda, { x: 1 }),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      return true;
    },
  );
  assert.deepEqual(calls.getAll, []);
  assert.deepEqual(calls.modify, []);
});

test('an id that is not on the page is NOT_FOUND and nothing is written', async () => {
  const { eda, calls } = fakeWindow();
  await assert.rejects(
    () => call(eda, { primitiveId: 'not-here', x: 1 }),
    (error) => {
      assert.equal(error.code, 'NOT_FOUND');
      assert.match(error.message, /nothing was written/);
      return true;
    },
  );
  assert.deepEqual(calls.modify, []);
});

test('a parent, key or value mismatch is an error, with zero writes', async () => {
  const cases = [
    { parentPrimitiveId: 'wire-2', field: 'parentPrimitiveId' },
    { expectedKey: 'NET', field: 'key' },
    { expectedValue: 'V4', field: 'value' },
  ];
  for (const { field, ...override } of cases) {
    const { eda, calls } = fakeWindow();
    await assert.rejects(
      () => call(eda, { x: 1, ...override }),
      (error) => {
        assert.equal(error.code, 'CONNECTOR_ERROR');
        assert.match(error.message, /nothing was written/);
        const named = error.detail.mismatched.map((m) => m.field);
        assert.deepEqual(named, [field]);
        assert.ok(error.detail.before, 'the answer must show what was actually read');
        return true;
      },
    );
    assert.deepEqual(calls.modify, [], `${field} mismatch must not write`);
  }
});

test('a confirmed move reports before / requested / after and applied', async () => {
  const { eda, calls } = fakeWindow();
  const data = await call(eda, { x: 280, y: 335 });

  assert.equal(data.pageUuid, PAGE);
  assert.equal(data.primitiveId, ATTR);
  assert.equal(data.parentPrimitiveId, PARENT);
  assert.equal(data.key, 'Name');
  assert.equal(data.value, 'V3');
  assert.deepEqual(data.before, {
    primitiveId: ATTR,
    parentPrimitiveId: PARENT,
    key: 'Name',
    value: 'V3',
    x: 370,
    y: 300,
    rotation: 0,
    alignMode: 2,
  });
  assert.deepEqual(data.requested, { x: 280, y: 335 });
  assert.deepEqual(data.after, { x: 280, y: 335 });
  assert.equal(data.applied, true);
  assert.deepEqual(data.mismatched, []);
  assert.equal(data.returned, null, 'the measured host answers undefined');

  // The write carries exactly the whitelisted fields, on the page's own list.
  assert.deepEqual(calls.getAll, [[]]);
  assert.deepEqual(calls.get, [[ATTR]]);
  assert.equal(calls.modify.length, 1);
  assert.equal(calls.modify[0][0], ATTR);
  assert.deepEqual(calls.modify[0][1], { x: 280, y: 335 });
});

test('modify answering undefined but landing is reported as applied, not as a failure', async () => {
  // The default fake does exactly this; the note has to say how it was decided.
  const { eda } = fakeWindow();
  const data = await call(eda, { x: 370, y: 320 });
  assert.equal(data.applied, true);
  assert.equal(data.returned, null);
  assert.match(data.note, /fresh get\(\)/);
});

test('a modify that returns an object still needs the read-back', async () => {
  const { eda } = fakeWindow({
    modifyImpl: (id, property, attributes) => {
      const target = attributes[0];
      target.fields.X = property.x;
      return { getState_PrimitiveId: () => id };
    },
  });
  const data = await call(eda, { x: 1 });
  assert.equal(data.applied, true);
  assert.equal(data.returned, 'object');
});

test('a move that did not take is an error listing the mismatched field', async () => {
  const noop = fakeWindow({ modifyImpl: () => undefined });
  await assert.rejects(
    () => call(noop.eda, { x: 999 }),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.match(error.message, /did not take the requested move/);
      assert.equal(error.detail.applied, false);
      assert.deepEqual(error.detail.mismatched, [{ field: 'x', expected: 999, actual: 370 }]);
      return true;
    },
  );
  assert.equal(noop.calls.modify.length, 1, 'the write was attempted exactly once — no retry');
});

test('a read-back that throws is a mismatch with the reason, never a pass', async () => {
  const broken = fakeWindow({
    getImpl: () => {
      throw new Error('get exploded');
    },
  });
  await assert.rejects(
    () => call(broken.eda, { x: 5 }),
    (error) => {
      assert.equal(error.detail.applied, false);
      assert.equal(error.detail.mismatched.length, 1);
      assert.match(error.detail.mismatched[0].error, /get exploded/);
      return true;
    },
  );
});

test('a host without getAll / modify / get is NOT_IMPLEMENTED and writes nothing', async () => {
  for (const member of ['getAll', 'modify', 'get']) {
    const { eda, calls } = fakeWindow({ omit: [member] });
    await assert.rejects(
      () => call(eda, { x: 1 }),
      (error) => {
        assert.equal(error.code, 'NOT_IMPLEMENTED');
        assert.match(error.message, new RegExp(member));
        return true;
      },
    );
    assert.deepEqual(calls.modify, []);
  }
});

test('only the requested pose fields are ever sent', async () => {
  const one = fakeWindow();
  await call(one.eda, { rotation: 90 });
  assert.deepEqual(one.calls.modify[0][1], { rotation: 90 });

  const all = fakeWindow();
  await call(all.eda, { x: 1, y: 2, rotation: 3, alignMode: 5 });
  assert.deepEqual(Object.keys(all.calls.modify[0][1]).sort(), ['alignMode', 'rotation', 'x', 'y']);
});

// --------------------------------------------------------------------------
// 053U: ValueVisible — hide one duplicated net name, keep everything else
// --------------------------------------------------------------------------

test('valueVisible=false alone hides one ATTR, and nothing else is sent', async () => {
  const { eda, calls } = fakeWindow();
  const data = await call(eda, { valueVisible: false });

  assert.equal(data.applied, true);
  assert.deepEqual(data.requested, { valueVisible: false });
  assert.deepEqual(data.after, { valueVisible: false });
  assert.equal(data.before.valueVisible, true);
  // The write carries the ONE requested field: no net, no key, no position, no
  // deletion path exists in this action at all.
  assert.deepEqual(calls.modify, [[ATTR, { valueVisible: false }]]);
  assert.deepEqual(calls.getAll, [[]]);
});

test('valueVisible=true is a display request and reads back visible', async () => {
  const hidden = new FakeAttribute({ ...BASE, ValueVisible: false });
  const { eda, calls } = fakeWindow({ attributes: [hidden] });
  const data = await call(eda, { valueVisible: true });
  assert.equal(data.applied, true);
  assert.deepEqual(data.after, { valueVisible: true });
  assert.deepEqual(calls.modify, [[ATTR, { valueVisible: true }]]);
});

test('valueVisible combines with pose fields in one modify', async () => {
  const { eda, calls } = fakeWindow();
  const data = await call(eda, { x: 420, y: 300, valueVisible: false });
  assert.equal(data.applied, true);
  assert.deepEqual(calls.modify, [[ATTR, { x: 420, y: 300, valueVisible: false }]]);
  assert.deepEqual(Object.keys(data.after).sort(), ['valueVisible', 'x', 'y']);
});

test('a non-boolean valueVisible is BAD_REQUEST with zero writes', async () => {
  for (const bad of ['false', 0, 1, null, undefined]) {
    const { eda, calls } = fakeWindow();
    await assert.rejects(
      () => call(eda, { valueVisible: bad }),
      (error) => {
        assert.equal(error.code, 'BAD_REQUEST', String(bad));
        assert.match(error.message, /valueVisible must be a boolean/);
        return true;
      },
    );
    assert.deepEqual(calls.modify, [], `${String(bad)} must not write`);
    assert.deepEqual(calls.getAll, [], 'a type refusal happens before the page is read');
  }
});

test('a hide is refused before the write when ValueVisible cannot be read back', async () => {
  const { eda, calls } = fakeWindow({ noValueVisiblePort: true });
  await assert.rejects(
    () => call(eda, { valueVisible: false }),
    (error) => {
      assert.equal(error.code, 'NOT_IMPLEMENTED');
      assert.match(error.message, /nothing was written/);
      assert.match(error.message, /getState_ValueVisible/);
      return true;
    },
  );
  assert.deepEqual(calls.modify, [], 'a hide nobody can confirm is never sent');
});

test('a pose-only call still works on a host without the ValueVisible port', async () => {
  // Old behaviour is unchanged: 053Q never needed that accessor.
  const { eda, calls } = fakeWindow({ noValueVisiblePort: true });
  const data = await call(eda, { x: 10 });
  assert.equal(data.applied, true);
  assert.equal('valueVisible' in data.before, false);
  assert.deepEqual(calls.modify, [[ATTR, { x: 10 }]]);
});

test('identity guards still refuse a hide on the wrong attribute', async () => {
  const { eda, calls } = fakeWindow();
  await assert.rejects(
    () => call(eda, { valueVisible: false, expectedValue: 'V2' }),
    (error) => {
      assert.equal(error.code, 'CONNECTOR_ERROR');
      assert.equal(error.detail.mismatched[0].field, 'value');
      return true;
    },
  );
  assert.deepEqual(calls.modify, []);
});
