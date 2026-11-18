/**
 * 550B: `sys.probe {instances: […]}` — the closed, read-only instance probe.
 *
 * Why this exists: the static `sys.probe` check reports
 * `pcb_PrimitivePad.getConnectedPrimitives`, `Line/Arc.getEntireTrack` and
 * `Line/Via/Arc.getAdjacentPrimitives` as `undefined` on the 4.1.100 host — but
 * the type package declares all three on `IPCB_*` **instances**, never on the
 * manager namespace, so the static reading is not evidence about instances.
 * Measuring it needs a real instance, and `pcb.readback` / `pcb.geometry` only
 * answer JSON summaries: nothing in the connector could reach an instance.
 *
 * What is pinned here, all offline against a fake `eda`:
 *
 * 1. **The page guard runs before any `get()`.** Not a PCB, or a focus that
 *    cannot be *proven* to be a PCB, is `PAGE_MISMATCH` — and no `get` is
 *    called at all, because a get on the wrong page answers another document's
 *    primitives.
 * 2. **Each failure keeps its own name**: a missing manager / `get`
 *    (`unavailable`), an id this page does not hold (`not-found`), an instance
 *    without the method (`absent`), a host that threw or answered a non-array
 *    (`error`). "No candidates" is never written as "no such method", and a
 *    non-array answer is never reported as an empty connection list.
 * 3. **The parameters each method takes are the ones passed**, including the
 *    declared defaults (`onlyCentreConnection` true, `includeVias` false).
 * 4. `count` keeps the host's own array length while `ids` respects `limit`, and
 *    a truncated or unnameable answer says so instead of shrinking silently.
 * 5. The contract is **closed**: unknown keys, illegal kind/method
 *    combinations, mixed modes and out-of-range `limit` are `BAD_REQUEST`
 *    before the host is touched.
 * 6. Only reads happen — the recorded call log contains no write verb.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

/** `EDMT_EditorDocumentType` values, as the type package declares them. */
const DOC_TYPE = { SCHEMATIC_PAGE: 1, PCB: 3 };

/**
 * Editor objects are class instances: `getState_*` sits on the prototype, so a
 * fake that puts the getter on the object does not exercise the same read.
 */
function primitive(state) {
  const proto = {};
  for (const [key, value] of Object.entries(state)) {
    proto[`getState_${key}`] = () => value;
  }
  return Object.create(proto);
}

/** An instance whose methods live on its prototype, like the host's. */
function instanceOf(methods) {
  const proto = {};
  for (const [name, fn] of Object.entries(methods)) proto[name] = fn;
  return Object.create(proto);
}

/**
 * Record every function call made on a fake host object, so "read-only" is a
 * measurement rather than a claim about the source.
 */
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

/** The names no probe may ever produce: every write verb the API has. */
const WRITE_CALL = /^(create|modify|delete|deletePrimitive|reset|done|setState_|set)/;

function assertReadOnly(calls) {
  const writes = calls.filter((call) => WRITE_CALL.test(call.name));
  assert.deepEqual(writes, [], 'a read probe must never reach a write method');
}

/**
 * One component whose `getAllPins()` answers `pins` — the only door to a
 * component pad (`IPCB_PrimitiveComponentPad`) on the measured host.
 */
function componentWith(pins) {
  return instanceOf({ getAllPins: async () => pins });
}

/** A component whose pins cannot be listed, one shape per `kind`. */
function brokenComponent(kind) {
  if (kind === 'missing') return instanceOf({});
  if (kind === 'throws') {
    return instanceOf({
      getAllPins() {
        throw new Error('getAllPins: component not resolved');
      },
    });
  }
  return instanceOf({ getAllPins: async () => null });
}

/** A component pad: what `getConnectedPrimitives` is really declared on. */
function componentPad(id, methods) {
  const proto = { getState_PrimitiveId: () => id, ...methods };
  return Object.create(proto);
}

/**
 * One window with a focused PCB and the four PCB primitive managers.
 *
 * `managers` lets a test leave one out (a build that lacks the namespace) or
 * replace a manager wholesale. Every `get()` is recorded in `calls.gets`, so a
 * refusal can be checked as "the host was not touched".
 */
function fakeEditor({
  focus = 'pcb',
  managers = {},
  connected = {},
  extra = {},
  components,
} = {}) {
  const calls = { gets: [], all: [], componentListings: 0 };
  const activeUuid = focus === 'pcb' ? 'pcb-1' : 'page-1';
  const activeType = focus === 'pcb' ? DOC_TYPE.PCB : DOC_TYPE.SCHEMATIC_PAGE;

  const manager = (name, get) => recording({
    async get(primitiveId) {
      calls.gets.push({ manager: name, primitiveId });
      return get(primitiveId);
    },
  }, calls.all);

  const eda = {
    sys_Environment: { getEditorCurrentVersion: () => '4.1.100' },
    dmt_Pcb: { getCurrentPcbInfo: async () => ({ uuid: 'pcb-1', name: 'PCB1' }) },
    dmt_Schematic: {
      getCurrentSchematicPageInfo: async () => ({ uuid: 'page-1', name: 'P1.Schematic1' }),
    },
    pcb_PrimitivePad: manager('pcb_PrimitivePad', connected.pad ?? (() => undefined)),
    pcb_PrimitiveLine: manager('pcb_PrimitiveLine', connected.line ?? (() => undefined)),
    pcb_PrimitiveArc: manager('pcb_PrimitiveArc', connected.arc ?? (() => undefined)),
    pcb_PrimitiveVia: manager('pcb_PrimitiveVia', connected.via ?? (() => undefined)),
    ...extra,
  };
  // The component namespace only exists when a test asks for it: `components`
  // is the list `getAll()` answers, or a function so a test can count calls.
  if (components !== undefined) {
    eda.pcb_PrimitiveComponent = recording({
      async getAll() {
        calls.componentListings += 1;
        if (typeof components === 'function') return components();
        return components.map((component) => recording(component, calls.all));
      },
    }, calls.all);
  }
  for (const [name, value] of Object.entries(managers)) {
    if (value === null) delete eda[name];
    else eda[name] = value;
  }
  if (focus !== 'none') {
    eda.dmt_SelectControl = {
      getCurrentDocumentInfo: async () => ({
        uuid: activeUuid,
        name: activeUuid,
        documentType: activeType,
        tabId: focus === 'pcb' ? 't2' : 't1',
      }),
    };
  }
  return { eda, calls };
}

const probe = (eda, params) => buildHandlers(eda)['sys.probe'](params);

// --------------------------------------------------------------------------
// the page guard: before any get
// --------------------------------------------------------------------------

test('a schematic in front is refused with PAGE_MISMATCH and no get at all', async () => {
  const { eda, calls } = fakeEditor({ focus: 'sch' });
  await assert.rejects(
    () => probe(eda, { instances: [{ kind: 'pad', primitiveId: 'p1', method: 'connected' }] }),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.match(error.message, /focused document is/);
      return true;
    },
  );
  assert.deepEqual(calls.gets, [], 'the guard must run before the first get()');
});

test('a focus that cannot be proven to be a PCB is refused, not guessed', async () => {
  // Only the per-kind fallbacks answer: they can say "a PCB exists", never
  // "the PCB is in front", and the probe never switches the tab itself.
  const { eda, calls } = fakeEditor({ focus: 'none' });
  await assert.rejects(
    () => probe(eda, { instances: [{ kind: 'via', primitiveId: 'v1', method: 'adjacent' }] }),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.match(error.message, /heuristically/);
      return true;
    },
  );
  assert.deepEqual(calls.gets, []);
});

test('no focused document at all is also PAGE_MISMATCH, with no get', async () => {
  const { eda, calls } = fakeEditor({ focus: 'none' });
  delete eda.dmt_Pcb;
  delete eda.dmt_Schematic;
  await assert.rejects(
    () => probe(eda, { instances: [{ kind: 'pad', primitiveId: 'p1', method: 'connected' }] }),
    (error) => {
      assert.equal(error.code, 'PAGE_MISMATCH');
      assert.match(error.message, /no active document/);
      return true;
    },
  );
  assert.deepEqual(calls.gets, []);
});

// --------------------------------------------------------------------------
// per-item truth: unavailable / not-found / absent are three different facts
// --------------------------------------------------------------------------

test('a missing manager, a missing id and a missing method are three statuses', async () => {
  const { eda, calls } = fakeEditor({
    managers: { pcb_PrimitiveLine: null },
    connected: {
      // the pad exists but has no getConnectedPrimitives on this build
      pad: () => instanceOf({}),
      // the via id is simply not on this page
      via: () => undefined,
    },
    // A complete component walk that finds nothing: the only shape in which a
    // negative answer is allowed to stay `absent`.
    components: [componentWith([componentPad('other-pad', {})])],
  });
  const data = await probe(eda, {
    instances: [
      { kind: 'pad', primitiveId: 'pad-1', method: 'connected' },
      { kind: 'line', primitiveId: 'line-1', method: 'adjacent' },
      { kind: 'via', primitiveId: 'via-1', method: 'adjacent' },
    ],
  });

  assert.deepEqual(data.instances.map((row) => row.status), ['absent', 'unavailable', 'not-found']);
  // "the method is not there" and "the primitive is not there" must never be
  // the same reading — and neither may borrow the empty-connection shape.
  for (const row of data.instances) {
    assert.equal('call' in row, false, `${row.status} is not a call: ${JSON.stringify(row)}`);
    assert.equal(typeof row.error, 'string');
  }
  assert.match(data.instances[0].error, /not a function on the base pad instance/);
  assert.match(data.instances[0].error, /complete 1-component walk found no ComponentPad/);
  assert.equal(data.instances[0].resolution, 'component');
  assert.deepEqual(data.instances[0].componentFallback, {
    components: 1, matches: 0, readErrors: [], truncated: false,
  });
  assert.match(data.instances[1].error, /pcb_PrimitiveLine is not available/);
  assert.match(data.instances[2].error, /no such primitive on this page/);
  // The absent-method row is reported *after* a get: the id was resolved first.
  assert.deepEqual(calls.gets.map((entry) => entry.primitiveId), ['pad-1', 'via-1']);
  assert.equal(calls.gets.some((entry) => entry.manager === 'pcb_PrimitiveLine'), false);
  assert.equal(calls.componentListings, 1, 'the walk ran once, for the pad row only');
  assertReadOnly(calls.all);
});

// --------------------------------------------------------------------------
// the bounded ComponentPad fallback (measured: the base pad has no method)
// --------------------------------------------------------------------------

test('a direct pad method enumerates no components at all', async () => {
  const connectedCalls = [];
  const { eda, calls } = fakeEditor({
    connected: {
      pad: () => instanceOf({
        getConnectedPrimitives(onlyCentre) {
          connectedCalls.push([onlyCentre]);
          return [primitive({ PrimitiveId: 'l1' })];
        },
      }),
    },
    components: () => {
      throw new Error('getAll must not be reached when the base pad answers');
    },
  });
  const data = await probe(eda, {
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  assert.equal(data.instances[0].status, 'function');
  assert.equal(data.instances[0].resolution, 'direct');
  assert.equal('componentFallback' in data.instances[0], false);
  assert.deepEqual(connectedCalls, [[true]]);
  assert.equal(calls.componentListings, 0, 'zero component enumeration on the direct path');
  assert.deepEqual(data.instances[0].call.ids, ['l1']);
  assertReadOnly(calls.all);
});

test('a unique ComponentPad answers the call, with the requested parameter', async () => {
  const seen = [];
  const pad = componentPad('pad-1', {
    getConnectedPrimitives(onlyCentre) {
      seen.push([onlyCentre]);
      return [primitive({ PrimitiveId: 'line-9' }), primitive({ PrimitiveId: 'via-3' })];
    },
  });
  const { eda, calls } = fakeEditor({
    connected: { pad: () => instanceOf({}) },
    components: [componentWith([componentPad('other', {})]), componentWith([pad])],
  });
  const data = await probe(eda, {
    instances: [{
      kind: 'pad', primitiveId: 'pad-1', method: 'connected', onlyCentreConnection: false,
    }],
  });
  const row = data.instances[0];
  assert.equal(row.status, 'function');
  assert.equal(row.resolution, 'component');
  assert.deepEqual(row.componentFallback, {
    components: 2, matches: 1, readErrors: [], truncated: false,
  });
  assert.deepEqual(row.call, { ok: true, count: 2, ids: ['line-9', 'via-3'], truncated: false });
  assert.deepEqual(seen, [[false]], 'the ComponentPad got the parameter the caller asked for');
  assert.equal(calls.componentListings, 1);
  assertReadOnly(calls.all);
});

test('two ComponentPads answering the same id are ambiguous, never the first', async () => {
  const callsMade = [];
  const pad = () => componentPad('pad-1', {
    getConnectedPrimitives() {
      callsMade.push('called');
      return [];
    },
  });
  const { eda } = fakeEditor({
    connected: { pad: () => instanceOf({}) },
    components: [componentWith([pad()]), componentWith([pad()])],
  });
  const data = await probe(eda, {
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  const row = data.instances[0];
  assert.equal(row.status, 'error');
  assert.equal(row.resolution, 'component');
  assert.match(row.error, /2 component pads answer getState_PrimitiveId "pad-1" — ambiguous/);
  assert.equal(row.componentFallback.matches, 2);
  assert.deepEqual(callsMade, [], 'nothing is called on either candidate');
});

test('a component read failure forbids a negative answer', async () => {
  for (const kind of ['throws', 'non-array', 'missing']) {
    const { eda } = fakeEditor({
      connected: { pad: () => instanceOf({}) },
      components: [componentWith([componentPad('other', {})]), brokenComponent(kind)],
    });
    const data = await probe(eda, {
      instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
    });
    const row = data.instances[0];
    assert.notEqual(row.status, 'absent', `${kind}: an incomplete walk cannot claim "no method"`);
    assert.equal(row.status, 'error', kind);
    assert.equal(row.resolution, 'component');
    assert.match(row.error, /the scan did not complete/, kind);
    assert.equal(row.componentFallback.readErrors.length, 1, kind);
    assert.equal(row.componentFallback.components, 2, 'the walk continued past the bad component');
    assert.equal(row.componentFallback.matches, 0, kind);
  }
});

test('a unique ComponentPad without the method is absent, but only if the walk completed', async () => {
  const clean = await probe(
    fakeEditor({
      connected: { pad: () => instanceOf({}) },
      components: [componentWith([componentPad('pad-1', {})])],
    }).eda,
    { instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }] },
  );
  assert.equal(clean.instances[0].status, 'absent');
  assert.match(clean.instances[0].error, /neither does the unique ComponentPad/);

  // The same negative, now with one unreadable component in the walk: refused.
  const gapped = await probe(
    fakeEditor({
      connected: { pad: () => instanceOf({}) },
      components: [componentWith([componentPad('pad-1', {})]), brokenComponent('throws')],
    }).eda,
    { instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }] },
  );
  assert.equal(gapped.instances[0].status, 'error');
  assert.match(gapped.instances[0].error, /does not expose getConnectedPrimitives .* did not complete/);
});

test('more than 512 components: the scan is disclosed as truncated', async () => {
  const many = (padIndex) => Array.from({ length: 600 }, (_, index) => componentWith(
    padIndex === index ? [componentPad('pad-1', {
      getConnectedPrimitives: async () => [primitive({ PrimitiveId: 'near' })],
    })] : [],
  ));

  // The match is inside the cap: the positive path still answers, and says so.
  const inside = await probe(fakeEditor({ connected: { pad: () => instanceOf({}) }, components: many(5) }).eda, {
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  const row = inside.instances[0];
  assert.equal(row.status, 'function');
  assert.equal(row.resolution, 'component');
  assert.equal(row.componentFallback.truncated, true);
  assert.equal(row.componentFallback.components, 512);
  assert.deepEqual(row.call.ids, ['near']);

  // The match is beyond the cap: no negative claim may be made.
  const beyond = await probe(fakeEditor({ connected: { pad: () => instanceOf({}) }, components: many(550) }).eda, {
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  const missing = beyond.instances[0];
  assert.equal(missing.status, 'error');
  assert.equal(missing.componentFallback.truncated, true);
  assert.equal(missing.componentFallback.matches, 0);
  assert.match(missing.error, /only the first 512 components were inspected/);
});

test('a component namespace that cannot be read says unavailable, not absent', async () => {
  const { eda } = fakeEditor({
    connected: { pad: () => instanceOf({}) },
    components: [componentWith([])],
  });
  delete eda.pcb_PrimitiveComponent;
  const noNamespace = await probe(eda, {
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  assert.equal(noNamespace.instances[0].status, 'unavailable');
  assert.match(noNamespace.instances[0].error, /pcb_PrimitiveComponent is not available/);

  const noGetAll = await probe(
    fakeEditor({
      connected: { pad: () => instanceOf({}) },
      managers: { pcb_PrimitiveComponent: { getAllPinsByPrimitiveId: async () => [] } },
    }).eda,
    { instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }] },
  );
  assert.equal(noGetAll.instances[0].status, 'unavailable');
  assert.match(noGetAll.instances[0].error, /pcb_PrimitiveComponent\.getAll is not a function/);
});

test('the fallback reads ids only, and never a write method', async () => {
  const { eda, calls } = fakeEditor({
    connected: { pad: () => instanceOf({}) },
    components: [componentWith([componentPad('pad-1', {
      getConnectedPrimitives: async () => [primitive({ PrimitiveId: 'a' })],
    })])],
  });
  await probe(eda, { instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }] });
  // Every call the fallback made goes through the recorder: the manager, then
  // the component it read pins from. `getConnectedPrimitives` and
  // `getState_PrimitiveId` live on objects the fake cannot wrap from here, so
  // their use is proven by the answer itself (`ids: ['a']` means the id was
  // read off the returned primitive).
  assert.deepEqual(
    [...new Set(calls.all.map((entry) => entry.name))].sort(),
    ['get', 'getAll', 'getAllPins'],
  );
  assertReadOnly(calls.all);
});

test('line, arc and via rows carry no fallback keys', async () => {
  const { eda } = fakeEditor({
    connected: {
      line: () => instanceOf({ getEntireTrack: async () => [], getAdjacentPrimitives: async () => [] }),
      via: () => instanceOf({ getAdjacentPrimitives: async () => [] }),
      arc: () => instanceOf({ getEntireTrack: async () => [] }),
    },
  });
  const data = await probe(eda, {
    instances: [
      { kind: 'line', primitiveId: 'l1', method: 'entireTrack' },
      { kind: 'line', primitiveId: 'l1', method: 'adjacent' },
      { kind: 'via', primitiveId: 'v1', method: 'adjacent' },
      { kind: 'arc', primitiveId: 'a1', method: 'entireTrack' },
    ],
  });
  for (const row of data.instances) {
    assert.equal('resolution' in row, false, JSON.stringify(row));
    assert.equal('componentFallback' in row, false, JSON.stringify(row));
  }
});

test('a manager whose get is not a function is unavailable, and nothing is called', async () => {
  const { eda, calls } = fakeEditor({
    managers: { pcb_PrimitiveArc: { getAll: async () => [] } },
  });
  const data = await probe(eda, {
    instances: [{ kind: 'arc', primitiveId: 'arc-1', method: 'entireTrack' }],
  });
  assert.equal(data.instances[0].status, 'unavailable');
  assert.match(data.instances[0].error, /pcb_PrimitiveArc\.get is not a function/);
  assert.deepEqual(calls.gets, []);
});

// --------------------------------------------------------------------------
// the positive paths, with their own parameters
// --------------------------------------------------------------------------

test('the three methods are called with the parameters their own table allows', async () => {
  const seen = [];
  // Two builders, because arity is part of the answer: a method that takes the
  // boolean has `length === 1`, `getAdjacentPrimitives()` has 0.
  const answer = (name, ids) => function (takesOneParameter) {
    void takesOneParameter;
    seen.push({ name, args: [...arguments] });
    return ids.map((id) => primitive({ PrimitiveId: id }));
  };
  const noArgs = (name, ids) => function () {
    seen.push({ name, args: [] });
    return ids.map((id) => primitive({ PrimitiveId: id }));
  };
  const { eda, calls } = fakeEditor({
    connected: {
      pad: () => instanceOf({
        getConnectedPrimitives: answer('pad.connected', ['l1', 'l2']),
      }),
      line: () => instanceOf({
        getEntireTrack: answer('line.entireTrack', ['a', 'b']),
        getAdjacentPrimitives: noArgs('line.adjacent', ['x']),
      }),
      arc: () => instanceOf({
        getEntireTrack: answer('arc.entireTrack', []),
      }),
      via: () => instanceOf({
        getAdjacentPrimitives: noArgs('via.adjacent', ['y']),
      }),
    },
  });

  // Four items, the contract's own cap: the pad's two parameter shapes and the
  // line's two `includeVias` shapes.
  const data = await probe(eda, {
    instances: [
      // declared defaults: onlyCentreConnection true, includeVias false
      { kind: 'pad', primitiveId: 'pad-1', method: 'connected' },
      { kind: 'pad', primitiveId: 'pad-2', method: 'connected', onlyCentreConnection: false },
      { kind: 'line', primitiveId: 'line-1', method: 'entireTrack' },
      { kind: 'line', primitiveId: 'line-1', method: 'entireTrack', includeVias: true },
    ],
  });
  // `adjacent` is the third method and takes no argument at all.
  const adjacent = await probe(eda, {
    instances: [
      { kind: 'line', primitiveId: 'line-1', method: 'adjacent' },
      { kind: 'via', primitiveId: 'via-1', method: 'adjacent' },
      { kind: 'arc', primitiveId: 'arc-1', method: 'entireTrack' },
    ],
  });

  assert.deepEqual(data.page, { uuid: 'pcb-1', type: 'pcb' });
  assert.equal(data.readOnly, true);
  assert.equal(data.version, '4.1.100');
  assert.deepEqual(
    data.instances.map((row) => row.status),
    ['function', 'function', 'function', 'function'],
  );
  assert.deepEqual(adjacent.instances.map((row) => row.status), ['function', 'function', 'function']);
  assert.deepEqual(seen, [
    { name: 'pad.connected', args: [true] },
    { name: 'pad.connected', args: [false] },
    { name: 'line.entireTrack', args: [false] },
    { name: 'line.entireTrack', args: [true] },
    { name: 'line.adjacent', args: [] },
    { name: 'via.adjacent', args: [] },
    { name: 'arc.entireTrack', args: [false] },
  ]);
  assert.deepEqual(data.instances[0].call, { ok: true, count: 2, ids: ['l1', 'l2'], truncated: false });
  assert.deepEqual(data.instances[2].call, { ok: true, count: 2, ids: ['a', 'b'], truncated: false });
  // A real empty answer is an ok call with count 0 — never an error, never absent.
  assert.deepEqual(adjacent.instances[2].call, { ok: true, count: 0, ids: [], truncated: false });
  assert.deepEqual(calls.gets.map((entry) => entry.primitiveId), [
    'pad-1', 'pad-2', 'line-1', 'line-1', 'line-1', 'via-1', 'arc-1',
  ]);
  // `arity` is reported so "present but answers nothing" has a shape.
  assert.equal(data.instances[0].arity, 1);
  assert.equal(adjacent.instances[0].arity, 0);
  assertReadOnly(calls.all);
  // An `adjacent` row carries no optional parameter key and no truncation.
  assert.deepEqual(Object.keys(adjacent.instances[0]), ['kind', 'primitiveId', 'method', 'status', 'arity', 'call']);
});

// --------------------------------------------------------------------------
// failures that are answers
// --------------------------------------------------------------------------

test('a throwing method is that item\'s error, and the next item still answers', async () => {
  const { eda, calls } = fakeEditor({
    connected: {
      pad: () => instanceOf({
        getConnectedPrimitives(onlyCentreConnection) {
          assert.equal(onlyCentreConnection, true);
          throw new TypeError('Cannot read properties of null (reading \'map\')');
        },
      }),
      via: () => instanceOf({
        getAdjacentPrimitives: async () => [primitive({ PrimitiveId: 'l9' })],
      }),
    },
  });
  const data = await probe(eda, {
    instances: [
      { kind: 'pad', primitiveId: 'pad-1', method: 'connected' },
      { kind: 'via', primitiveId: 'via-1', method: 'adjacent' },
    ],
  });
  assert.equal(data.instances[0].status, 'error');
  assert.equal(data.instances[0].call.ok, false);
  assert.match(data.instances[0].call.error, /^getConnectedPrimitives\(\) threw TypeError: Cannot read properties of null/);
  assert.equal(data.instances[0].arity, 1, 'the method existed; its arity survives the throw');
  assert.equal(data.instances[1].status, 'function');
  assert.deepEqual(data.instances[1].call.ids, ['l9']);
  assertReadOnly(calls.all);
});

test('a get that throws is an error on that item, not a missing primitive', async () => {
  const { eda } = fakeEditor({
    connected: {
      pad: () => {
        throw new Error('get_primitive_by_id: engine not ready');
      },
    },
  });
  const data = await probe(eda, {
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  assert.equal(data.instances[0].status, 'error');
  assert.match(data.instances[0].error, /pcb_PrimitivePad\.get\("pad-1"\) threw Error: get_primitive_by_id/);
  assert.equal('call' in data.instances[0], false, 'nothing was called on the primitive');
});

test('a non-array answer is an error, not an empty connection list', async () => {
  for (const [label, value] of [
    ['null', null],
    ['undefined', undefined],
    ['an object', { 0: 'x' }],
    ['a boolean', true],
    ['a string', 'none'],
  ]) {
    const { eda } = fakeEditor({
      connected: { pad: () => instanceOf({ getConnectedPrimitives: async () => value }) },
    });
    const data = await probe(eda, {
      instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
    });
    const row = data.instances[0];
    assert.equal(row.status, 'error', label);
    assert.equal(row.call.ok, false, label);
    assert.match(row.call.error, /not an array/, label);
    assert.notDeepEqual(
      row.call,
      { ok: true, count: 0, ids: [], truncated: false },
      `${label} must not be readable as "connected to nothing"`,
    );
  }
});

// --------------------------------------------------------------------------
// count vs ids: the 5000-primitive case, and limit
// --------------------------------------------------------------------------

test('5000 primitives: count is the host\'s length, ids stop at limit', async () => {
  const many = Array.from({ length: 5000 }, (_, index) => primitive({ PrimitiveId: `p${index}` }));
  const { eda } = fakeEditor({
    connected: { pad: () => instanceOf({ getConnectedPrimitives: async () => many }) },
  });

  const byDefault = await probe(eda, {
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  assert.equal(byDefault.instances[0].call.count, 5000);
  assert.equal(byDefault.instances[0].call.ids.length, 32, 'the default limit is 32');
  assert.equal(byDefault.instances[0].call.truncated, true);

  const explicit = await probe(eda, {
    limit: 5,
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  assert.equal(explicit.instances[0].call.count, 5000);
  assert.deepEqual(explicit.instances[0].call.ids, ['p0', 'p1', 'p2', 'p3', 'p4']);
  assert.equal(explicit.instances[0].call.truncated, true);

  const wide = await probe(eda, {
    limit: 64,
    instances: [{ kind: 'pad', primitiveId: 'pad-1', method: 'connected' }],
  });
  assert.equal(wide.instances[0].call.ids.length, 64);
  assert.equal(wide.instances[0].call.truncated, true);

  // limit larger than the answer: nothing is held back, so truncated is false.
  const few = await probe(eda, {
    limit: 64,
    instances: [{ kind: 'via', primitiveId: 'via-1', method: 'adjacent' }],
  });
  // (via answers `undefined` here, which is not-found — the limit is not at fault)
  assert.equal(few.instances[0].status, 'not-found');
});

test('a primitive whose id will not read is counted, not dropped', async () => {
  const noGetter = Object.create({});
  const throwing = Object.create({
    getState_PrimitiveId() {
      throw new TypeError('exotic primitive');
    },
  });
  const { eda } = fakeEditor({
    connected: {
      line: () => instanceOf({
        getEntireTrack: async () => [
          primitive({ PrimitiveId: 'ok-1' }),
          noGetter,
          throwing,
          primitive({ PrimitiveId: '' }),
        ],
      }),
    },
  });
  const data = await probe(eda, {
    instances: [{ kind: 'line', primitiveId: 'line-1', method: 'entireTrack' }],
  });
  const row = data.instances[0];
  assert.equal(row.status, 'function');
  assert.equal(row.call.count, 4, 'the host answered four');
  assert.deepEqual(row.call.ids, ['ok-1'], 'only the ids that really read back');
  assert.equal(row.call.unreadable, 3, 'three entries were counted as unnameable');
  assert.equal(row.call.truncated, false);
});

// --------------------------------------------------------------------------
// the contract is closed
// --------------------------------------------------------------------------

test('illegal kind, method, key and mode combinations are all BAD_REQUEST', async () => {
  const { eda, calls } = fakeEditor();
  const pad = (patch = {}) => ({ kind: 'pad', primitiveId: 'p1', method: 'connected', ...patch });
  const rejects = [
    [pad({ kind: 'component' }), /kind must be one of pad \| line \| arc \| via/],
    [pad({ kind: 'Pad' }), /kind must be one of/],
    [pad({ method: 'getConnectedPrimitives' }), /method for a pad must be connected/],
    [{ kind: 'via', primitiveId: 'v1', method: 'connected' }, /method for a via must be adjacent/],
    [{ kind: 'line', primitiveId: 'l1', method: 'connected' }, /method for a line must be entireTrack \| adjacent/],
    [pad({ primitiveId: '  ' }), /primitiveId must be a non-empty string/],
    [pad({ primitiveId: 42 }), /primitiveId must be a non-empty string/],
    [pad({ action: 'pcb.delete_primitives' }), /the allowed keys are/],
    [pad({ includeVias: true }), /calls connected, which accepts onlyCentreConnection/],
    [{ kind: 'line', primitiveId: 'l1', method: 'entireTrack', onlyCentreConnection: true },
      /calls entireTrack, which accepts includeVias/],
    [{ kind: 'via', primitiveId: 'v1', method: 'adjacent', includeVias: true },
      /calls adjacent, which accepts no optional key/],
    [pad({ onlyCentreConnection: 'yes' }), /onlyCentreConnection must be a boolean/],
    [{ kind: 'line', primitiveId: 'l1', method: 'entireTrack', includeVias: 1 },
      /includeVias must be a boolean/],
    ['pad', /must be an object/],
    [null, /must be an object/],
  ];
  for (const [entry, pattern] of rejects) {
    await assert.rejects(() => probe(eda, { instances: [entry] }), (error) => {
      assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(entry));
      assert.match(error.message, pattern, JSON.stringify(entry));
      return true;
    }, JSON.stringify(entry));
  }
  assert.deepEqual(calls.gets, [], 'nothing reaches the host when the request is malformed');
});

test('the instances array itself is bounded and typed', async () => {
  const { eda, calls } = fakeEditor();
  const item = { kind: 'pad', primitiveId: 'p1', method: 'connected' };
  const cases = [
    [{ instances: [] }, /takes 1\.\.4 items/],
    [{ instances: [item, item, item, item, item] }, /takes 1\.\.4 items/],
    [{ instances: item }, /must be an array/],
    [{ instances: 'pad' }, /must be an array/],
  ];
  for (const [params, pattern] of cases) {
    await assert.rejects(() => probe(eda, params), (error) => {
      assert.equal(error.code, 'BAD_REQUEST');
      assert.match(error.message, pattern);
      return true;
    });
  }
  assert.deepEqual(calls.gets, []);
});

test('limit is meaningful only with instances, and only inside 1..64', async () => {
  const { eda } = fakeEditor();
  const item = { kind: 'pad', primitiveId: 'p1', method: 'connected' };
  for (const limit of [0, 65, -1, 1.5, '32', null, true]) {
    await assert.rejects(() => probe(eda, { limit, instances: [item] }), (error) => {
      assert.equal(error.code, 'BAD_REQUEST', `limit ${JSON.stringify(limit)}`);
      assert.match(error.message, /params\.limit must be an integer 1\.\.64/);
      return true;
    });
  }
  await assert.rejects(() => probe(eda, { limit: 5 }), (error) => {
    assert.equal(error.code, 'BAD_REQUEST');
    assert.match(error.message, /only means something together with params\.instances/);
    return true;
  });
});

test('instances cannot be mixed with any other probe mode', async () => {
  const { eda, calls } = fakeEditor();
  const instances = [{ kind: 'pad', primitiveId: 'p1', method: 'connected' }];
  const mixed = [
    { realm: true },
    { call: { action: 'sys.identity' } },
    { checks: true },
    { checks: { sys_Log: ['add'] } },
    { namespace: 'sys_Log' },
    { namespaces: ['sys_Log'] },
    { functionsOnly: true },
  ];
  for (const extra of mixed) {
    await assert.rejects(() => probe(eda, { ...extra, instances }), (error) => {
      assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(extra));
      assert.match(error.message, /is a mode of its own/);
      return true;
    }, JSON.stringify(extra));
  }
  assert.deepEqual(calls.gets, []);
});

// --------------------------------------------------------------------------
// the old modes are untouched
// --------------------------------------------------------------------------

test('omitting instances leaves every existing mode as it was', async () => {
  const { eda, calls } = fakeEditor({
    extra: {
      sys_Log: { add() {}, sort: async () => [] },
      sch_ManufactureData: { getPngFile() {}, getNetlistFile() {} },
    },
  });

  const enumerated = await probe(eda, { namespace: 'sys_Log' });
  assert.deepEqual(enumerated.namespaces.sys_Log.functions, ['add', 'sort']);
  assert.equal('instances' in enumerated, false);
  assert.equal('page' in enumerated, false);

  const checks = await probe(eda, { checks: { sys_Log: ['add', 'missingOne'] } });
  assert.deepEqual(checks.checks.sys_Log.status, { add: 'function', missingOne: 'undefined' });

  // 025's `call` mode still dispatches its closed allowlist (and only that).
  const call = await probe(eda, { call: { action: 'sys.log_read' } });
  assert.equal(call.call.action, 'sys.log_read');
  assert.equal('instances' in call, false);

  const realm = await probe(eda, { realm: true });
  assert.ok(realm.realm.kinds);

  const bare = await probe(eda, {});
  assert.deepEqual(Object.keys(bare).sort(), ['connector', 'namespaces', 'topLevel', 'version']);

  assert.deepEqual(calls.gets, [], 'none of the old modes resolves a primitive');
  assertReadOnly(calls.all);
});
