/**
 * #87⑤: `sch.readback` lifts `value` / `mpn` out of the attribute map.
 *
 * The defect: `sch.readback` summarised primitives through `snapshot`, which
 * folds `OtherProperty` into `{object: true}` and cuts the walk at 40 names. On
 * `test V4` P43 a live read answered 15 keys with **no** `value` and no `mpn`
 * anywhere at the top level (the part number sat inside `fields`), so a review
 * could not compare a value without exporting the archive.
 *
 * What is pinned here, all offline against a fake `eda`:
 *
 * 1. `value` comes from `OtherProperty['Value']` only, `mpn` prefers
 *    `ManufacturerId` and falls back to the attribute map — and `valueSource` /
 *    `mpnSource` say which channel answered, or `null` when none did.
 * 2. Blanks, an empty map, a missing key and a throwing getter all answer
 *    `null` — never `''`. A throwing getter still returns its row and is
 *    counted in `unreadable`.
 * 3. Numbers and booleans are stringified, because the host stores `Value: 100`
 *    and a review compares text.
 * 4. `pcb.readback` grows **no** key, even when the PCB primitive carries the
 *    same attributes — the lift is keyed on the document kind.
 * 5. The ordinary schematic path and the `PAGE_MISMATCH` refusal are unchanged
 *    (the guard's own file, `readback-page-guard.test.mjs`, owns the message).
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

const DOC_TYPE = { SCHEMATIC_PAGE: 1, PCB: 3 };

/** An editor object whose `getState_*` getters sit on the prototype. */
function primitive(state) {
  const proto = {};
  for (const [key, value] of Object.entries(state)) {
    proto[`getState_${key}`] = () => value;
  }
  return Object.create(proto);
}

/** A primitive whose named getter throws — the exotic-host shape. */
function throwingPrimitive(state, throwing) {
  const proto = {};
  for (const [key, value] of Object.entries(state)) {
    proto[`getState_${key}`] = () => value;
  }
  for (const key of throwing) {
    proto[`getState_${key}`] = () => {
      throw new Error(`${key} is unreadable`);
    };
  }
  return Object.create(proto);
}

/** A window focused on a schematic page, with one sch and one PCB namespace. */
function fakeWindow({ focus = 'sch', schItems, pcbItems } = {}) {
  const calls = { schGetAll: 0, pcbGetAll: 0 };
  const eda = {
    dmt_Schematic: {
      getCurrentSchematicPageInfo: async () => ({ uuid: 'page-1', name: 'P1.Schematic1' }),
    },
    dmt_Pcb: { getCurrentPcbInfo: async () => ({ uuid: 'pcb-1', name: 'PCB1' }) },
    dmt_EditorControl: {
      getSplitScreenTree: async () => ({
        id: 'root',
        tabs: [{ tabId: 't1', title: 'P1.Schematic1' }, { tabId: 't2', title: 'PCB1' }],
        children: [],
      }),
    },
    sch_PrimitiveComponent: {
      async getAll() {
        calls.schGetAll += 1;
        return schItems ?? [];
      },
    },
    pcb_PrimitiveComponent: {
      async getAll() {
        calls.pcbGetAll += 1;
        return pcbItems ?? [];
      },
    },
    dmt_SelectControl: {
      getCurrentDocumentInfo: async () => ({
        uuid: focus === 'pcb' ? 'pcb-1' : 'page-1',
        name: focus === 'pcb' ? 'pcb-1' : 'page-1',
        documentType: focus === 'pcb' ? DOC_TYPE.PCB : DOC_TYPE.SCHEMATIC_PAGE,
        tabId: 't1',
      }),
    },
  };
  return { eda, calls };
}

const call = (eda, action, params = {}) => buildHandlers(eda)[action](params);

/** One schematic row with a `Value` and nothing that looks like an MPN. */
const plainResistor = () => primitive({
  PrimitiveId: 's1',
  Designator: 'R15',
  Name: 'Resistor',
  OtherProperty: { Value: '10k' },
});

test('sch.readback lifts Value from OtherProperty and names its source', async () => {
  const { eda } = fakeWindow({ schItems: [plainResistor()] });

  const data = await call(eda, 'sch.readback');
  const [row] = data.components;

  assert.equal(row.value, '10k');
  assert.equal(row.valueSource, 'OtherProperty');
  assert.equal(row.mpn, null, 'no ManufacturerId and no part-number key: null, not a guess');
  assert.equal(row.mpnSource, null);
  assert.equal(row.designator, 'R15');
  assert.equal(row.net, null, 'an absent Net is still null (unchanged)');
  assert.ok(data.unreadable === undefined, 'a clean read reports no unreadable count');
});

test('sch.readback prefers ManufacturerId over the OtherProperty part number', async () => {
  const { eda } = fakeWindow({
    schItems: [primitive({
      PrimitiveId: 's2',
      Designator: 'C24',
      ManufacturerId: 'CL05B104KO5NNNC',
      OtherProperty: { Value: '100nF', 'Manufacturer Part': 'GRM155R71C104KA88D' },
    })],
  });

  const [row] = (await call(eda, 'sch.readback')).components;

  assert.equal(row.value, '100nF');
  assert.equal(row.mpn, 'CL05B104KO5NNNC', 'ManufacturerId wins when it answers');
  assert.equal(row.mpnSource, 'ManufacturerId');
});

test('sch.readback falls back to the OtherProperty part-number keys', async () => {
  const { eda } = fakeWindow({
    schItems: [
      primitive({
        PrimitiveId: 's3', Designator: 'U9',
        OtherProperty: { Value: 'LM358', 'Manufacturer Part': 'LM358DR' },
      }),
      primitive({
        PrimitiveId: 's4', Designator: 'U10',
        OtherProperty: { Value: 'NE555', ManufacturerPart: 'NE555P' },
      }),
      primitive({
        PrimitiveId: 's5', Designator: 'U11',
        OtherProperty: { Value: 'TL072', partNumber: 'TL072CP' },
      }),
    ],
  });

  const rows = (await call(eda, 'sch.readback')).components;

  assert.deepEqual(
    rows.map((row) => [row.designator, row.mpn, row.mpnSource]),
    [
      ['U9', 'LM358DR', 'OtherProperty'],
      ['U10', 'NE555P', 'OtherProperty'],
      ['U11', 'TL072CP', 'OtherProperty'],
    ],
    'each documented fallback key answers, and the source says so',
  );
});

test('an empty ManufacturerId falls through to the attribute map', async () => {
  const { eda } = fakeWindow({
    schItems: [primitive({
      PrimitiveId: 's6', Designator: 'R16',
      ManufacturerId: '   ',
      OtherProperty: { Value: '4k7', 'Manufacturer Part': 'RC0402FR-074K7L' },
    })],
  });

  const [row] = (await call(eda, 'sch.readback')).components;

  assert.equal(row.mpn, 'RC0402FR-074K7L', 'blank is not an answer: the fallback runs');
  assert.equal(row.mpnSource, 'OtherProperty');
});

test('numbers and booleans are stringified, blanks and missing keys are null', async () => {
  const { eda } = fakeWindow({
    schItems: [
      primitive({ PrimitiveId: 's7', Designator: 'R17', OtherProperty: { Value: 100 } }),
      primitive({ PrimitiveId: 's8', Designator: 'R18', OtherProperty: { Value: true } }),
      primitive({ PrimitiveId: 's9', Designator: 'R19', OtherProperty: { Value: '   ' } }),
      primitive({ PrimitiveId: 's10', Designator: 'R20', OtherProperty: {} }),
      primitive({ PrimitiveId: 's11', Designator: 'R21' }),
    ],
  });

  const rows = (await call(eda, 'sch.readback')).components;

  assert.deepEqual(
    rows.map((row) => [row.designator, row.value, row.valueSource]),
    [
      ['R17', '100', 'OtherProperty'],
      ['R18', 'true', 'OtherProperty'],
      ['R19', null, null],
      ['R20', null, null],
      ['R21', null, null],
    ],
    'a blank or absent attribute is null, never the empty string',
  );
  for (const row of rows) {
    assert.notEqual(row.value, '', 'null is not "" — a caller must be able to tell them apart');
  }
});

test('a throwing OtherProperty getter keeps the row and is counted unreadable', async () => {
  const { eda } = fakeWindow({
    schItems: [throwingPrimitive({
      PrimitiveId: 's12',
      Designator: 'R22',
      Name: 'Resistor',
      ManufacturerId: 'RC0402FR-074K7L',
    }, ['OtherProperty'])],
  });

  const data = await call(eda, 'sch.readback');
  const [row] = data.components;

  assert.equal(data.componentCount, 1, 'one broken attribute must not drop the part');
  assert.equal(row.designator, 'R22');
  assert.equal(row.value, null);
  assert.equal(row.valueSource, null);
  assert.equal(row.mpn, 'RC0402FR-074K7L', 'the other channel still answers');
  assert.equal(row.mpnSource, 'ManufacturerId');
  assert.equal(data.unreadable, 1, 'the failed read is counted, not swallowed');
  assert.match(data.reason, /getState_OtherProperty/);
});

test('a throwing ManufacturerId getter falls back instead of losing the part', async () => {
  const { eda } = fakeWindow({
    schItems: [throwingPrimitive({
      PrimitiveId: 's13',
      Designator: 'R23',
      OtherProperty: { Value: '1k', 'Manufacturer Part': 'RC0402FR-071KL' },
    }, ['ManufacturerId'])],
  });

  const data = await call(eda, 'sch.readback');
  const [row] = data.components;

  assert.equal(row.value, '1k');
  assert.equal(row.mpn, 'RC0402FR-071KL');
  assert.equal(row.mpnSource, 'OtherProperty');
  assert.equal(data.unreadable, 1);
  assert.match(data.reason, /getState_ManufacturerId/);
});

test('a net flag with no attributes reads as null value and null mpn', async () => {
  // A power/GND flag is a primitive with no `OtherProperty` and no
  // `ManufacturerId` at all — the shape a CBB-less page is full of.
  const { eda } = fakeWindow({
    schItems: [
      primitive({ PrimitiveId: 'f1', Designator: 'PWR1', Name: 'VCC', X: 10, Y: 20 }),
      primitive({ PrimitiveId: 'f2', Designator: 'GND1', Name: 'GND', X: 30, Y: 20 }),
    ],
  });

  const data = await call(eda, 'sch.readback');

  for (const row of data.components) {
    assert.equal(row.value, null);
    assert.equal(row.mpn, null);
    assert.equal(row.valueSource, null);
    assert.equal(row.mpnSource, null);
  }
  assert.equal(data.unreadable, undefined, 'an absent attribute is not an unreadable one');
});

test('pcb.readback grows no key, even when the primitive carries attributes', async () => {
  const pcbComponent = () => primitive({
    PrimitiveId: 'c1', Designator: 'U1', Name: 'CH340C',
    Footprint: 'SOP-16', Supplier: 'LCSC', SupplierId: 'C84681',
    Manufacturer: 'WCH', X: 100, Y: 200, Rotation: 90, Layer: 1,
    // The same channels the schematic lift reads — a PCB row must ignore them.
    ManufacturerId: 'CH340C',
    OtherProperty: { Value: 'CH340C' },
  });
  const { eda, calls } = fakeWindow({ focus: 'pcb', pcbItems: [pcbComponent()] });

  const data = await call(eda, 'pcb.readback');
  const [row] = data.components;

  for (const key of ['value', 'mpn', 'valueSource', 'mpnSource']) {
    assert.equal(key in row, false, `pcb.readback must not carry ${key}`);
  }
  assert.equal(row.designator, 'U1');
  assert.equal(row.layer, 1);
  assert.equal(calls.schGetAll, 0, 'a PCB read must not touch the schematic namespace');
  assert.equal(calls.pcbGetAll, 1);
});

test('the ordinary schematic path is unchanged: guard, net and fields still answer', async () => {
  const { eda, calls } = fakeWindow({
    schItems: [primitive({
      PrimitiveId: 's14', Designator: 'R24', Name: 'Resistor', Net: 'TX',
      X: 10, Y: 20, Rotation: 0,
      OtherProperty: { Value: '22R' },
    })],
  });

  const data = await call(eda, 'sch.readback');

  assert.equal(data.kind, 'sch');
  assert.equal(data.componentCount, 1);
  assert.equal(calls.schGetAll, 1);
  const [row] = data.components;
  assert.equal(row.net, 'TX');
  assert.equal(row.rotation, 0);
  // `fields.OtherProperty` is still the folded summary — the new keys are the
  // lift, not a replacement for the summary (a caller parsing `fields` today
  // keeps working).
  assert.deepEqual(row.fields.OtherProperty, { object: true });
  assert.equal(row.fields.Designator, 'R24');
  assert.equal(data.primitives.length, 0, 'primitives stay opt-in');
});

test('sch.readback on a PCB-focused window still refuses with PAGE_MISMATCH', async () => {
  const pcbComponent = () => primitive({ PrimitiveId: 'c1', Designator: 'U1', Layer: 1 });
  const { eda, calls } = fakeWindow({ focus: 'pcb', pcbItems: [pcbComponent()] });

  await assert.rejects(
    () => call(eda, 'sch.readback'),
    (error) => {
      assert.equal(error.name, 'ActionError');
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.match(error.message, /sch\.readback/);
      assert.match(error.message, /PCB \(pcb-1\)/);
      return true;
    },
  );
  assert.equal(calls.schGetAll, 0, 'a refused read must not touch the host namespace');
});
