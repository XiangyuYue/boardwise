/**
 * 559: `pcb.connection_probe` — host evidence for one pad-to-pad connection.
 *
 * Why this exists: 550B measured that EDA 4.1.100 answers
 * `getConnectedPrimitives` on `IPCB_PrimitiveComponentPad` and
 * `getEntireTrack` on `IPCB_PrimitiveLine`/`IPCB_PrimitiveArc`, but
 * `sys.probe {instances: […]}` only reports **ids for primitives the caller
 * already names**. A caller holding two `REF.PAD` ends — the way a schematic
 * caller thinks — had no action that resolved them and collected what the host
 * says connects them.
 *
 * What is pinned here, all offline against a fake host:
 *
 * 1. **The 550B page guard runs before the first read.** A schematic, no focus,
 *    or a focus only the per-kind fallback can vouch for is `PAGE_MISMATCH` with
 *    zero component and zero primitive reads.
 * 2. **One bounded scan resolves both ends** (≤512 components), matching a
 *    component's `getState_Designator` **and** the pad's `getState_PadNumber`
 *    together. No match, several matches, and an incomplete scan are three
 *    different answers and none of them is an endpoint.
 * 3. **`getConnectedPrimitives(false)` is typed, and nothing is followed**: the
 *    action never calls `getEntireTrack` (559B measured it returning ids of
 *    other, offline-disconnected copper components), so `Line`/`Arc` stay typed
 *    direct items and `Via`/`Fill`/`Pour`/`Polyline` plus any unreadable type
 *    are `unknown`.
 * 4. **Every gap is disclosed** — a truncated scan, a failed component/pin
 *    read, an unnameable id, a missing method, a throw, a non-array — and the
 *    one remaining cap (16 direct per end) is reported rather than applied
 *    silently. There is no `coverage.ids`: its id budget belonged to the removed
 *    track walk.
 * 5. **The action computes no verdict**: no `verdict`, no `path`, no
 *    `sharedIds` anywhere in the answer, and no `tracks[]` either.
 * 6. Only reads happen — the recorded call log contains no write verb.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

/** `EDMT_EditorDocumentType` values, as the type package declares them. */
const DOC_TYPE = { SCHEMATIC_PAGE: 1, PCB: 3 };

/** `EPCB_PrimitiveType` spellings used below, from `@jlceda/pro-api-types`. */
const PRIMITIVE_TYPE = {
  LINE: 'Line',
  ARC: 'Arc',
  VIA: 'Via',
  FILL: 'Fill',
  POUR: 'Pour',
  POLYLINE: 'Polyline',
  COMPONENT_PAD: 'ComponentPad',
};

/** An instance whose methods live on its prototype, like the host's. */
function instanceOf(methods) {
  const proto = {};
  for (const [name, fn] of Object.entries(methods)) proto[name] = fn;
  return Object.create(proto);
}

/** Record every function call made through one fake host object. */
function recording(target, calls) {
  return new Proxy(target, {
    get(obj, prop) {
      const value = obj[prop];
      if (typeof value !== 'function') return value;
      return (...args) => {
        calls.push({ name: String(prop), args });
        return value.apply(obj, args);
      };
    },
  });
}

/** The names no read may ever produce: every write verb the API has. */
const WRITE_CALL = /^(create|modify|delete|deletePrimitive|reset|done|setState_|set)/;

function assertReadOnly(calls) {
  const writes = calls.filter((call) => WRITE_CALL.test(call.name));
  assert.deepEqual(writes, [], 'a read probe must never reach a write method');
}

/**
 * A component pad (`IPCB_PrimitiveComponentPad`): its id, its pad number, its
 * net and its type are the public fields the probe reads.
 */
function pad({
  id = 'pad-id',
  padNumber = '1',
  net = undefined,
  type = PRIMITIVE_TYPE.COMPONENT_PAD,
  extra = {},
  methods = {},
} = {}) {
  return instanceOf({
    getState_PrimitiveId: () => id,
    getState_PadNumber: () => padNumber,
    getState_PrimitiveType: () => type,
    ...(net === undefined ? {} : { getState_Net: () => net }),
    ...extra,
    ...methods,
  });
}

/** A component: its designator and its `getAllPins()` answer. */
function component({ designator, pads = [], pins } = {}) {
  const methods = { getAllPins: pins ?? (async () => pads) };
  if (designator !== undefined) methods.getState_Designator = () => designator;
  return instanceOf(methods);
}

/**
 * One window with a focused PCB and `components` behind
 * `pcb_PrimitiveComponent.getAll()`.
 *
 * `calls.listings` counts `getAll()` (the scan) and `calls.all` records every
 * call made through the manager and each component — two separate
 * measurements, because "one scan" and "no write verb" are different claims.
 */
function fakeEditor({ focus = 'pcb', components = [], manager, extra = {} } = {}) {
  const calls = { all: [], listings: 0 };
  const eda = {
    dmt_Pcb: { getCurrentPcbInfo: async () => ({ uuid: 'pcb-1', name: 'PCB1' }) },
    dmt_Schematic: {
      getCurrentSchematicPageInfo: async () => ({ uuid: 'page-1', name: 'P1.Schematic1' }),
    },
    ...extra,
  };
  if (focus !== 'none') {
    const isPcb = focus === 'pcb';
    eda.dmt_SelectControl = {
      getCurrentDocumentInfo: async () => ({
        uuid: isPcb ? 'pcb-1' : 'page-1',
        name: isPcb ? 'pcb-1' : 'page-1',
        documentType: isPcb ? DOC_TYPE.PCB : DOC_TYPE.SCHEMATIC_PAGE,
        tabId: isPcb ? 't2' : 't1',
      }),
    };
  }
  if (manager !== null) {
    eda.pcb_PrimitiveComponent = recording(manager ?? {
      async getAll() {
        calls.listings += 1;
        return components.map((entry) => recording(entry, calls.all));
      },
    }, calls.all);
  }
  return { eda, calls };
}

const probe = (eda, params) => buildHandlers(eda)['pcb.connection_probe'](params);

/** A directly connected primitive; `entireTrack` is a trap that must never fire. */
function connectedPrimitive(type, id, calls) {
  return instanceOf({
    getState_PrimitiveId: () => id,
    getState_PrimitiveType: () => type,
    getEntireTrack: (includeVias) => {
      calls.push({ id, type, includeVias });
      throw new Error(`getEntireTrack must not be called on ${type} ${id} (559B is direct-only)`);
    },
  });
}

// --------------------------------------------------------------------------
// the page guard: before any component or primitive read
// --------------------------------------------------------------------------

test('a schematic in front is refused with PAGE_MISMATCH and zero reads', async () => {
  const { eda, calls } = fakeEditor({
    focus: 'sch',
    components: [component({ designator: 'R1', pads: [pad({ padNumber: '1' })] })],
  });
  await assert.rejects(() => probe(eda, { from: 'R1.1', to: 'C4.2' }), (error) => {
    assert.equal(error.code, 'PAGE_MISMATCH');
    assert.match(error.message, /focused document is/);
    return true;
  });
  assert.equal(calls.listings, 0, 'the guard must run before the component scan');
  assert.deepEqual(calls.all, [], 'no component or primitive is read');
});

test('no focused document at all is PAGE_MISMATCH, with zero reads', async () => {
  const { eda, calls } = fakeEditor({ focus: 'none' });
  delete eda.dmt_Pcb;
  delete eda.dmt_Schematic;
  await assert.rejects(() => probe(eda, { from: 'R1.1', to: 'C4.2' }), (error) => {
    assert.equal(error.code, 'PAGE_MISMATCH');
    assert.match(error.message, /no active document/);
    return true;
  });
  assert.equal(calls.listings, 0);
  assert.deepEqual(calls.all, []);
});

test('a focus that cannot be proven to be a PCB is refused, not guessed', async () => {
  // Only the per-kind fallbacks answer: they can say "a PCB exists", never
  // "the PCB is in front", and this action never switches the tab itself.
  const { eda, calls } = fakeEditor({ focus: 'none', components: [] });
  await assert.rejects(() => probe(eda, { from: 'R1.1', to: 'C4.2' }), (error) => {
    assert.equal(error.code, 'PAGE_MISMATCH');
    assert.match(error.message, /heuristically/);
    return true;
  });
  assert.equal(calls.listings, 0);
  assert.deepEqual(calls.all, []);
});

// --------------------------------------------------------------------------
// the contract is closed: two REF.PAD strings, nothing else
// --------------------------------------------------------------------------

test('unknown keys, missing ends and malformed REF.PAD are all BAD_REQUEST', async () => {
  const { eda, calls } = fakeEditor({ components: [] });
  const cases = [
    [{ from: 'R1.1' }, /params\.to must be a "REF\.PAD" string/],
    [{ to: 'C4.2' }, /params\.from must be a "REF\.PAD" string/],
    [{ from: 'R1.1', to: 'C4.2', limit: 8 }, /the allowed keys are from, to/],
    [{ from: 'R1.1', to: 'C4.2', project: 'x' }, /the allowed keys are from, to/],
    [{ from: 'R1', to: 'C4.2' }, /must be "REF\.PAD"/],
    [{ from: 'R1.1', to: '.2' }, /must be "REF\.PAD"/],
    [{ from: 'R1.1', to: 42 }, /must be a "REF\.PAD" string/],
    [{ from: ['R1.1'], to: 'C4.2' }, /must be a "REF\.PAD" string/],
  ];
  for (const [params, pattern] of cases) {
    await assert.rejects(() => probe(eda, params), (error) => {
      assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(params));
      assert.match(error.message, pattern, JSON.stringify(params));
      return true;
    }, JSON.stringify(params));
  }
  assert.equal(calls.listings, 0, 'nothing reaches the host when the request is malformed');
  assert.deepEqual(calls.all, []);
});

// --------------------------------------------------------------------------
// the happy path: one scan, typed direct answer, tracks for Line/Arc only
// --------------------------------------------------------------------------

test('both ends resolve in one scan and no getEntireTrack call is ever made', async () => {
  const entire = [];
  const fromPad = pad({
    id: 'p-r1-3',
    padNumber: '3',
    net: 'N1',
    methods: {
      getConnectedPrimitives(onlyCentre) {
        assert.equal(onlyCentre, false, 'the measured call is getConnectedPrimitives(false)');
        return [
          connectedPrimitive(PRIMITIVE_TYPE.LINE, 't1', entire),
          connectedPrimitive(PRIMITIVE_TYPE.VIA, 'v1', entire),
        ];
      },
    },
  });
  const toPad = pad({
    id: 'p-c4-2',
    padNumber: '2',
    net: 'N1',
    methods: {
      getConnectedPrimitives: () => [
        connectedPrimitive(PRIMITIVE_TYPE.ARC, 'a1', entire),
      ],
    },
  });
  const { eda, calls } = fakeEditor({
    components: [
      component({ designator: 'R7', pads: [pad({ id: 'p-r7-1', padNumber: '1' })] }),
      component({ designator: 'R1', pads: [pad({ id: 'p-r1-1', padNumber: '1' }), fromPad] }),
      component({ designator: 'C4', pads: [toPad] }),
    ],
  });

  const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });

  assert.equal(calls.listings, 1, 'one component scan answers both ends');
  assert.deepEqual(data.page, { uuid: 'pcb-1', type: 'pcb' });
  assert.equal(data.readOnly, true);

  assert.deepEqual(data.from.ref, { designator: 'R1', pad: '3' });
  assert.equal(data.from.status, 'resolved');
  assert.deepEqual(data.from.pad, {
    primitiveId: 'p-r1-3', padNumber: '3', net: 'N1', type: 'ComponentPad',
  });
  assert.deepEqual(data.from.resolution.candidates, ['p-r1-3']);
  assert.equal(data.from.resolution.matches, 1);
  assert.equal(data.from.resolution.complete, true);

  assert.deepEqual(data.from.direct, {
    ok: true,
    count: 2,
    ids: ['t1', 'v1'],
    truncated: false,
    items: [
      { primitiveId: 't1', type: 'Line' },
      { primitiveId: 'v1', type: 'Via' },
    ],
  });
  assert.deepEqual(data.to.direct.items, [{ primitiveId: 'a1', type: 'Arc' }]);

  // 559B: the entire-track read is gone, so a happy path makes zero of them.
  assert.deepEqual(entire, [], 'getEntireTrack is never called');
  assert.equal('tracks' in data.from, false, 'no tracks[] in an end');
  assert.equal('tracks' in data.to, false, 'no tracks[] in an end');
  assert.equal('ids' in data.coverage, false, 'no coverage.ids: its budget left with the track walk');
  // The via was seen, named and not followed — no fabricated path through it.
  assert.deepEqual(data.unknown, [
    { end: 'from', reason: 'not-a-track', primitiveId: 'v1', type: 'Via' },
  ]);
  assert.deepEqual(data.errors, []);
  assert.equal(data.coverage.scan.complete, true);
  assert.equal(data.coverage.unknown, 1);
  assert.equal(data.coverage.complete, false, 'an unknown item forbids "nothing was withheld"');
  assertReadOnly(calls.all);

  // No verdict, no path, no sharedIds: the intersection is offline work.
  for (const key of ['verdict', 'path', 'sharedIds', 'status', 'connected']) {
    assert.equal(key in data, false, `${key} must not be in the answer`);
  }
  for (const end of [data.from, data.to]) {
    for (const key of ['verdict', 'path', 'sharedIds']) {
      assert.equal(key in end, false, `${key} must not be in an end`);
    }
  }
});

test('a complete scan with no matching component pad is absent, and says so', async () => {
  const { eda } = fakeEditor({
    components: [component({ designator: 'R1', pads: [pad({ id: 'p-r1-1', padNumber: '1' })] })],
  });
  const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });
  assert.equal(data.from.status, 'absent');
  assert.equal(data.from.pad, null);
  assert.equal(data.from.direct, null);
  assert.match(data.from.error, /complete 1-component walk found no component pad for R1\.3/);
  assert.equal(data.coverage.scan.complete, true);
  assert.equal(data.coverage.complete, false);
});

// --------------------------------------------------------------------------
// identity: ambiguity, truncation and read gaps never become an endpoint
// --------------------------------------------------------------------------

test('two component pads answering the same REF.PAD are ambiguous, never the first', async () => {
  const called = [];
  const candidate = () => pad({
    id: 'p-dup',
    padNumber: '3',
    methods: {
      getConnectedPrimitives: () => {
        called.push('called');
        return [];
      },
    },
  });
  const { eda } = fakeEditor({
    components: [
      component({ designator: 'R1', pads: [candidate()] }),
      component({ designator: 'R1', pads: [candidate()] }),
    ],
  });
  const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });
  assert.equal(data.from.status, 'ambiguous');
  assert.equal(data.from.pad, null);
  assert.equal(data.from.direct, null);
  assert.equal(data.from.resolution.matches, 2);
  assert.deepEqual(data.from.resolution.candidates, ['p-dup']);
  assert.match(data.from.error, /2 component pads answer R1\.3 .* taking the first match would be a guess/);
  assert.deepEqual(called, [], 'nothing is called on either candidate');
});

test('more than 512 components: the scan is disclosed and cannot answer "no"', async () => {
  const many = (targetIndex) => Array.from({ length: 600 }, (_, index) => (
    index === targetIndex
      ? component({
        designator: 'R1',
        pads: [pad({
          id: 'p-r1-3',
          padNumber: '3',
          methods: { getConnectedPrimitives: () => [] },
        })],
      })
      : component({ designator: `X${index}`, pads: [] })
  ));

  // Inside the cap: the endpoint resolves, and the truncation is still on the record.
  const inside = await probe(
    fakeEditor({ components: many(5) }).eda,
    { from: 'R1.3', to: 'C4.2' },
  );
  assert.equal(inside.from.status, 'resolved');
  assert.equal(inside.from.resolution.truncated, true);
  assert.equal(inside.from.resolution.complete, false);
  assert.equal(inside.coverage.scan.components, 512);
  assert.equal(inside.coverage.scan.truncated, true);
  assert.deepEqual(inside.from.direct.ids, []);

  // Beyond the cap: no negative claim may be made.
  const beyond = await probe(
    fakeEditor({ components: many(550) }).eda,
    { from: 'R1.3', to: 'C4.2' },
  );
  assert.equal(beyond.from.status, 'incomplete');
  assert.equal(beyond.from.pad, null);
  assert.match(beyond.from.error, /only the first 512 components were inspected/);
  assert.equal(beyond.coverage.complete, false);
});

test('a component read failure forbids an absent answer', async () => {
  // `getAllPins` throws, `getAllPins` answers a non-array, `getAllPins` is
  // missing, and a component whose Designator will not read: four gaps.
  for (const [label, broken] of [
    ['throws', instanceOf({ getState_Designator: () => 'R1', getAllPins() { throw new Error('pins: not resolved'); } })],
    ['non-array', instanceOf({ getState_Designator: () => 'R1', getAllPins: async () => null })],
    ['missing', instanceOf({ getState_Designator: () => 'R1' })],
  ]) {
    const { eda } = fakeEditor({
      components: [component({ designator: 'R9', pads: [] }), broken],
    });
    const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });
    assert.equal(data.from.status, 'incomplete', label);
    assert.equal(data.from.pad, null, label);
    assert.notEqual(data.from.status, 'absent', label);
    assert.equal(data.from.resolution.readErrors.length, 1, label);
    assert.match(data.from.error, /the walk did not complete/, label);
  }

  // A component whose designator will not read could be the target.
  const unreadable = await probe(
    fakeEditor({ components: [instanceOf({ getAllPins: async () => [] })] }).eda,
    { from: 'R1.3', to: 'C4.2' },
  );
  assert.equal(unreadable.from.status, 'incomplete');
  assert.match(unreadable.from.resolution.readErrors[0], /Designator read undefined/);
});

test('a component namespace that cannot be read says unavailable, not absent', async () => {
  const noNamespace = await probe(
    fakeEditor({ manager: null }).eda,
    { from: 'R1.3', to: 'C4.2' },
  );
  assert.equal(noNamespace.from.status, 'unavailable');
  assert.match(noNamespace.from.error, /pcb_PrimitiveComponent is not available/);

  const noGetAll = await probe(
    fakeEditor({ manager: { getAllPinsByPrimitiveId: async () => [] } }).eda,
    { from: 'R1.3', to: 'C4.2' },
  );
  assert.equal(noGetAll.from.status, 'unavailable');
  assert.match(noGetAll.from.error, /pcb_PrimitiveComponent\.getAll is not a function/);
});

// --------------------------------------------------------------------------
// the direct call: absent / error / non-array are three different facts
// --------------------------------------------------------------------------

test('a missing method, a throw and a non-array answer are named, not read as []', async () => {
  const cases = [
    ['absent', pad({ id: 'p1', padNumber: '3' }), /is not a function on the ComponentPad resolved for R1\.3/],
    ['throws', pad({
      id: 'p1',
      padNumber: '3',
      methods: {
        getConnectedPrimitives() {
          throw new TypeError('Cannot read properties of null (reading \'map\')');
        },
      },
    }), /^getConnectedPrimitives\(false\) threw TypeError: Cannot read properties of null/],
    ['non-array', pad({
      id: 'p1', padNumber: '3', methods: { getConnectedPrimitives: async () => null },
    }), /not an array/],
  ];
  for (const [label, padInstance, pattern] of cases) {
    const { eda } = fakeEditor({
      components: [component({ designator: 'R1', pads: [padInstance] })],
    });
    const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });
    assert.equal(data.from.status, 'resolved', `${label}: the pad identity is still proven`);
    assert.equal(data.from.direct.ok, false, label);
    assert.match(data.from.direct.error, pattern, label);
    assert.equal('ids' in data.from.direct, false, `${label} must not look like an empty list`);
    assert.equal('tracks' in data.from, false, `${label} carries no tracks[]`);
    assert.equal(data.coverage.complete, false, label);
    assert.ok(data.errors.length >= 1, label);
  }
});

// --------------------------------------------------------------------------
// caps: disclosed, never silent
// --------------------------------------------------------------------------

test('16 direct primitives are a cap, not a silent cut, and nothing is walked', async () => {
  const entire = [];
  const direct = Array.from({ length: 20 }, (_, index) => connectedPrimitive(
    PRIMITIVE_TYPE.LINE,
    `l${String(index).padStart(2, '0')}`,
    entire,
  ));
  const { eda } = fakeEditor({
    components: [component({
      designator: 'R1',
      pads: [pad({ id: 'p1', padNumber: '3', methods: { getConnectedPrimitives: () => direct } })],
    })],
  });
  const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });

  assert.equal(data.from.direct.count, 20);
  assert.equal(data.from.direct.items.length, 16);
  assert.equal(data.from.direct.truncated, true);
  assert.equal(data.coverage.direct.perEnd, 16);
  assert.equal(data.coverage.direct.reported.from, 16);
  assert.equal(data.coverage.direct.truncated.from, true);
  assert.equal(data.coverage.complete, false);
  assert.deepEqual(entire, [], 'no id budget, no entire-track read');
  assert.equal('tracks' in data.from, false);
  assert.equal('ids' in data.coverage, false);
});

test('a primitive whose id will not read is counted and disclosed, not dropped', async () => {
  const noId = Object.create({ getState_PrimitiveType: () => PRIMITIVE_TYPE.LINE });
  const { eda } = fakeEditor({
    components: [component({
      designator: 'R1',
      pads: [pad({
        id: 'p1',
        padNumber: '3',
        methods: {
          getConnectedPrimitives: () => [
            connectedPrimitive(PRIMITIVE_TYPE.LINE, 'l1', []),
            noId,
            connectedPrimitive(PRIMITIVE_TYPE.FILL, 'f1', []),
          ],
        },
      })],
    })],
  });
  const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });
  assert.equal(data.from.direct.count, 3);
  assert.equal(data.from.direct.unreadable, 1);
  assert.deepEqual(data.from.direct.ids, ['f1', 'l1']);
  assert.deepEqual(data.from.direct.items, [
    { primitiveId: 'l1', type: 'Line' },
    { primitiveId: 'f1', type: 'Fill' },
  ]);
  assert.deepEqual(data.unknown.map((entry) => entry.reason), ['primitive-id-unreadable', 'not-a-track']);
  assert.equal('tracks' in data.from, false, 'the Line is a typed item, not a walked track');
});

test('a type outside the declared set is unknown and is not followed', async () => {
  const exotic = instanceOf({
    getState_PrimitiveId: () => 'x1',
    getState_PrimitiveType: () => 'SomethingNew',
    getEntireTrack: () => {
      throw new Error('must not be called');
    },
  });
  const noType = instanceOf({
    getState_PrimitiveId: () => 'x2',
    getEntireTrack: () => {
      throw new Error('must not be called');
    },
  });
  const { eda } = fakeEditor({
    components: [component({
      designator: 'R1',
      pads: [pad({
        id: 'p1', padNumber: '3', methods: { getConnectedPrimitives: () => [exotic, noType] },
      })],
    })],
  });
  const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });
  assert.equal('tracks' in data.from, false);
  assert.deepEqual(data.from.direct.items, []);
  assert.deepEqual(data.unknown, [
    { end: 'from', reason: 'primitive-type-unknown', primitiveId: 'x1', type: 'SomethingNew' },
    { end: 'from', reason: 'primitive-type-unknown', primitiveId: 'x2', type: null },
  ]);
  assert.equal(data.coverage.complete, false);
});

test('via, fill, pour and polyline are named and never followed', async () => {
  const called = [];
  const types = [
    PRIMITIVE_TYPE.VIA,
    PRIMITIVE_TYPE.FILL,
    PRIMITIVE_TYPE.POUR,
    PRIMITIVE_TYPE.POLYLINE,
  ];
  const { eda } = fakeEditor({
    components: [component({
      designator: 'R1',
      pads: [pad({
        id: 'p1',
        padNumber: '3',
        methods: {
          getConnectedPrimitives: () => types.map((type, index) => (
            connectedPrimitive(type, `n${index}`, called)
          )),
        },
      })],
    })],
  });
  const data = await probe(eda, { from: 'R1.3', to: 'C4.2' });
  assert.deepEqual(data.from.direct.items.map((item) => item.type), types);
  assert.equal('tracks' in data.from, false, 'no end carries a track list');
  assert.deepEqual(called, [], 'getEntireTrack is never called, for any type');
  assert.deepEqual(
    data.unknown.map((entry) => [entry.reason, entry.type]),
    types.map((type) => ['not-a-track', type]),
  );
  assert.equal(data.coverage.complete, false, 'a known-but-unfollowed type still forbids "nothing withheld"');
});
