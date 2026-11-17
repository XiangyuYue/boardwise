/**
 * 551: `pcb.net_class.list` — the persisted net classes and the net rules.
 *
 * The question this action answers is 「which nets are grouped, and what do the
 * net rules say」 — a different question from `pcb.drc_ruleset`'s 「which rule
 * set is this board checked against」, which is why it is its own action rather
 * than two more keys on that deliberately narrow read.
 *
 * What is pinned here, one test per way the answer can be wrong:
 *
 * 1. **The call set** — `getAllNetClasses` and `getNetRules`, in that order,
 *    and nothing else. The class carries
 *    `createNetClass` / `deleteNetClass` / `modifyNetClassName` /
 *    `addNetToNetClass` / `removeNetFromNetClass` and the whole pad-pair /
 *    differential-pair / equal-length family; the fake installs a tripwire for
 *    each and every one of them.
 * 2. **「读不到」is not 「没有」** — an absent member, a throwing member and an
 *    unserialisable value each leave `null` (never `[]`) plus a named row in
 *    `missing`/`unreadable`, and `count` is `null` unless `classes` was really
 *    read.
 * 3. **The two reads are independent** — `classes: []` beside a non-empty
 *    `netRules` is a state, not a contradiction, and a missing `getNetRules`
 *    does not damage the classes that were read.
 * 4. **The focus discipline is `pcb.drc_ruleset`'s** — a non-PCB focus is
 *    refused with `PAGE_MISMATCH`, the focused document is named, **no
 *    `doc.open`** is issued and no net-class member is called. `active: null` is
 *    not evidence that a PCB is in front.
 * 5. **Sanitising only removes what JSON cannot carry** — a `Date` keeps its
 *    instant, a cycle becomes `(cycle)`, a function disappears, and the answer
 *    still round-trips through `JSON.stringify`.
 *
 * All offline, against a fake `eda`. What the host really returns for
 * `getAllNetClasses()` is a live question (the type package declares
 * `{name, nets, color}` and no widths at all); nothing here invents a field the
 * host has not been measured to send.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

/** Every write in the net-class neighbourhood, kept as a tripwire. */
const FORBIDDEN_WRITES = [
  'createNetClass',
  'deleteNetClass',
  'modifyNetClassName',
  'renameNetClass',
  'addNetToNetClass',
  'removeNetFromNetClass',
  'createDifferentialPair',
  'deleteDifferentialPair',
  'modifyDifferentialPairName',
  'createEqualLengthNetGroup',
  'deleteEqualLengthNetGroup',
  'addNetToEqualLengthNetGroup',
  'removeNetFromEqualLengthNetGroup',
  'saveRuleConfiguration',
  'overwriteCurrentRuleConfiguration',
  'overwriteNetRules',
  'overwriteNetByNetRules',
  'overwriteRegionRules',
  'createRuleConfiguration',
  'deleteRuleConfiguration',
  'renameRuleConfiguration',
  'setAsDefault',
  'startRealTimeDrc',
  'stopRealTimeDrc',
];

/** Two real-looking classes, in the shape `IPCB_NetClassItem` declares. */
function classes() {
  return [
    { name: 'PWR', nets: ['+5V', '+3V3'], color: { r: 255, g: 128, b: 0, alpha: 1 } },
    { name: 'DIFF', nets: ['USB_DP', 'USB_DM'], color: null },
  ];
}

/** Net-rule records, in the shape the config consumer already reads (`type`/`name`). */
function netRules() {
  return [
    { type: 'netClass', name: 'PWR', trackWidth: { min: 0.25, max: 1.0 } },
    { type: 'netClass', name: 'DIFF', trackWidth: { min: 0.15, max: 0.2 } },
  ];
}

function fakeEda(overrides = {}) {
  const calls = { reads: [], writes: [], opened: [] };
  const drc = {
    getAllNetClasses: async () => {
      calls.reads.push('getAllNetClasses');
      return classes();
    },
    getNetRules: async () => {
      calls.reads.push('getNetRules');
      return netRules();
    },
  };
  for (const name of FORBIDDEN_WRITES) {
    drc[name] = async (...args) => {
      calls.writes.push([name, args]);
      throw new Error(`forbidden write reached the host: ${name}`);
    };
  }
  const eda = {
    dmt_SelectControl: {
      getCurrentDocumentInfo: async () => ({ uuid: '5dc38976c1fa45ce', name: 'PCB1', documentType: 3 }),
    },
    dmt_EditorControl: {
      // Any `doc.open` at all is a failure of the page discipline.
      openDocument: async (...args) => {
        calls.opened.push(args);
        throw new Error('doc.open was issued');
      },
    },
    pcb_Drc: drc,
    ...overrides,
  };
  return { eda, calls };
}

const read = (eda, params = {}) => buildHandlers(eda)['pcb.net_class.list'](params);

test('reads exactly getAllNetClasses and getNetRules, and reports both verbatim', async () => {
  const { eda, calls } = fakeEda();
  const report = await read(eda);

  assert.deepEqual(
    calls.reads,
    ['getAllNetClasses', 'getNetRules'],
    'the call order is the answer\'s own key order',
  );
  assert.deepEqual(calls.writes, [], 'no write member may be reached');
  assert.deepEqual(calls.opened, [], 'the action never opens a document');

  assert.equal(report.source, 'pcb_Drc');
  assert.equal(report.readOnly, true);
  assert.deepEqual(report.page, { uuid: '5dc38976c1fa45ce', type: 'pcb' });
  assert.equal(report.count, 2);
  assert.deepEqual(report.classes, classes());
  assert.deepEqual(report.netRules, netRules());
  assert.deepEqual(report.missing, []);
  assert.deepEqual(report.unreadable, []);
  assert.deepEqual(
    report.reads.map((entry) => [entry.key, entry.read]),
    [['classes', true], ['netRules', true]],
  );
  assert.ok(report.reads.every((entry) => entry.path.startsWith('pcb_Drc.')));
  assert.ok(typeof report.elapsedMs === 'number');
  assert.ok(report.jsonChars > 0);
});

test('a non-PCB focus is PAGE_MISMATCH: no read, no doc.open, document named', async () => {
  const { eda, calls } = fakeEda({
    dmt_SelectControl: {
      getCurrentDocumentInfo: async () => ({ uuid: 'b4298962367251c8', name: 'P1', documentType: 1 }),
    },
  });
  await assert.rejects(() => read(eda), (error) => {
    assert.equal(error.code, 'PAGE_MISMATCH');
    assert.match(error.message, /b4298962367251c8 \(page\)/);
    assert.match(error.message, /doc\.open/);
    return true;
  });
  assert.deepEqual(calls.reads, [], 'a refused call must not touch the host at all');
  assert.deepEqual(calls.opened, [], 'the caller opens the board, not this action');
});

test('an absent/null focus is not treated as a confirmed PCB', async () => {
  const { eda, calls } = fakeEda({
    dmt_SelectControl: { getCurrentDocumentInfo: async () => null },
  });
  await assert.rejects(() => read(eda), (error) => {
    assert.equal(error.code, 'PAGE_MISMATCH');
    return true;
  });
  assert.deepEqual(calls.reads, []);
});

test('getAllNetClasses missing: classes=null and missing names the member (never [])', async () => {
  const { eda, calls } = fakeEda();
  delete eda.pcb_Drc.getAllNetClasses;
  const report = await read(eda);

  assert.equal(report.classes, null, '「this build has no reader」 must not read as 「no classes」');
  assert.equal(report.count, null, 'a count out of a failed read would be a fabricated fact');
  assert.deepEqual(report.missing, ['pcb_Drc.getAllNetClasses']);
  assert.deepEqual(
    report.reads.map((entry) => entry.read),
    [false, true],
  );
  // The other read is untouched by the first one's gap.
  assert.deepEqual(report.netRules, netRules());
  assert.ok(report.notes.some((note) => note.includes('getAllNetClasses')));
  assert.deepEqual(calls.writes, []);
});

test('getAllNetClasses throwing: classes=null and unreadable carries the host text', async () => {
  const { eda } = fakeEda();
  eda.pcb_Drc.getAllNetClasses = async () => {
    throw new Error('host said no');
  };
  const report = await read(eda);

  assert.equal(report.classes, null);
  assert.equal(report.count, null);
  assert.deepEqual(report.missing, []);
  assert.ok(
    report.unreadable.some((row) => row.includes('pcb_Drc.getAllNetClasses') && row.includes('host said no')),
  );
});

test('getNetRules missing: netRules=null by name, and the classes read is not damaged', async () => {
  const { eda } = fakeEda();
  delete eda.pcb_Drc.getNetRules;
  const report = await read(eda);

  assert.deepEqual(report.classes, classes());
  assert.equal(report.count, 2);
  assert.equal(report.netRules, null);
  assert.deepEqual(report.missing, ['pcb_Drc.getNetRules']);
  assert.ok(report.notes.some((note) => note.includes('getNetRules')));
});

test('classes=[] beside non-empty netRules: both reported as read, count is a real 0', async () => {
  const { eda } = fakeEda();
  eda.pcb_Drc.getAllNetClasses = async () => [];
  const report = await read(eda);

  assert.deepEqual(report.classes, [], 'an empty array the host really returned is []');
  assert.equal(report.count, 0, 'a real zero is a fact; a failed read was the thing with no count');
  assert.deepEqual(report.netRules, netRules());
  assert.deepEqual(report.missing, []);
  assert.deepEqual(report.unreadable, []);
});

test('both members missing is an outright CONNECTOR_ERROR, not an empty board answer', async () => {
  const { eda } = fakeEda();
  delete eda.pcb_Drc.getAllNetClasses;
  delete eda.pcb_Drc.getNetRules;
  await assert.rejects(() => read(eda), (error) => {
    assert.equal(error.code, 'CONNECTOR_ERROR');
    assert.match(error.message, /neither of the two net-class reads answered/);
    assert.match(error.message, /5dc38976c1fa45ce \(pcb\)/);
    return true;
  });
});

test('maxChars keeps the rule-set bounds and rejects anything outside them', async () => {
  const { eda } = fakeEda();
  await assert.rejects(() => read(eda, { maxChars: 999 }), (error) => {
    assert.equal(error.code, 'BAD_REQUEST');
    assert.match(error.message, /between 1000 and 4000000/);
    return true;
  });
  await assert.rejects(() => read(eda, { maxChars: 4_000_001 }), (error) => {
    assert.equal(error.code, 'BAD_REQUEST');
    return true;
  });
  const ok = await read(eda, { maxChars: 1_000 });
  assert.ok(ok.jsonChars > 0);
});

test('sanitising removes only what JSON cannot carry, and the answer round-trips', async () => {
  const cyclic = { name: 'PWR', nets: ['+5V'], updatedAt: new Date(1_700_000_000_000), width: Number.NaN };
  cyclic.self = cyclic;
  const { eda } = fakeEda();
  // The same object, not a spread copy: a cycle one level deeper would still be
  // cut, but then the assertion below would be pinning the wrong depth.
  eda.pcb_Drc.getAllNetClasses = async () => [cyclic];
  const report = await read(eda);

  const roundTripped = JSON.parse(JSON.stringify(report));
  assert.equal(roundTripped.classes[0].self, '(cycle)');
  assert.equal(
    roundTripped.classes[0].updatedAt,
    new Date(1_700_000_000_000).toISOString(),
    'a Date keeps the instant the host holds rather than becoming {}',
  );
  assert.equal(roundTripped.classes[0].width, null, 'NaN cannot survive JSON, and must not pretend to');
  assert.ok(
    report.unreadable.some((row) => row.includes('pcb_Drc.getAllNetClasses') && row.includes('sanitised')),
  );
});

test('a host that answers undefined writes null with the key present', async () => {
  const { eda } = fakeEda();
  eda.pcb_Drc.getNetRules = async () => undefined;
  const report = await read(eda);

  assert.equal(report.netRules, null);
  assert.deepEqual(
    report.reads.map((entry) => [entry.key, entry.read]),
    [['classes', true], ['netRules', true]],
    'a read that answered nothing is still a read that was attempted',
  );
  assert.deepEqual(report.unreadable, [], 'answering nothing is not a serialisation failure');
  assert.equal(report.count, 2);
});

test('the build declares the capability, so an older connector cannot claim it', async () => {
  // The capability is a fact about this **bundle**: a caller that does not see
  // the key is talking to an older connector, and the daemon catalogue is a
  // load-time constant that cannot be used to infer whether the connector has
  // the action. Declared here rather than inferred from a live dispatch.
  const { eda } = fakeEda();
  const handlers = buildHandlers(eda);
  assert.ok('pcb.net_class.list' in handlers);
  assert.equal(typeof handlers['pcb.net_class.list'], 'function');

  const status = await handlers['sys.connector_status']({});
  assert.equal(status.capabilities.pcbNetClassList, true);
  assert.equal(status.capabilities.pcbRenderViewport, true, 'the older flag is unchanged');
});
