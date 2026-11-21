/**
 * 562A: `pcb.path_probe` — multi-hop adjacency evidence for one copper walk.
 *
 * Why this exists: 559's `pcb.connection_probe` answers only the **direct**
 * question ("do both ends name the same typed primitive"), because 559B
 * measured `getEntireTrack(true)` returning ids of other, offline-disconnected
 * copper components and rejected it. The 562 contract asks the next question —
 * "what does the host say each piece of copper is adjacent to" — so a Python
 * side can walk several hops and decide. This action is the collector only.
 *
 * What is pinned here, all offline against a fake host:
 *
 * 1. **The 550B page guard runs before the first read**, and the request is the
 *    closed `{from, to}` pair of `REF.PAD` strings.
 * 2. **Both ends are resolved by one bounded component scan**, and each end's
 *    `getConnectedPrimitives(false)` is called exactly once.
 * 3. **Every hop is traceable**: each edge names one method, one `callIndex`
 *    (the global order of the direct/adjacent invocation) and one `hostOrder`
 *    (the position inside that answer), and the fake's own call log is the
 *    arbiter — `log[edge.callIndex]` must be the call the edge claims.
 * 4. **Both directions are recorded separately.** A→B and B→A are two edges
 *    with two different `callIndex` values; a one-way answer stays one-way and
 *    the Connector never turns it into a verdict either way.
 * 5. **Classification is explicit**: `Pad`→`Via` is `unknown:pad-via-contact`,
 *    `Arc` is `unknown:arc-unverified`, poured copper is
 *    `ignored:pour-excluded`, `Polyline`/`Region` are
 *    `unknown:unsupported-adjacent-type`, an intermediate pad is
 *    `unknown:intermediate-pad-unsupported`, a missing net is
 *    `unknown:net-missing` (never expanded) and another net is
 *    `ignored:other-net` (never traversed).
 * 6. **Failures and caps are disclosed, not swallowed**: a non-array answer, a
 *    missing/throwing adjacency method, an unreadable id/type, a manager that
 *    hands back a different primitive, a per-call truncation and the vertex
 *    budget all appear in `unknown`/`errors`/`frontier`/`coverage`.
 * 7. **No verdict, ever**: no `verdict`, `path`, `hopCount`, `viaCount` or
 *    `sharedIds` in the answer; `getEntireTrack` is trapped and never called;
 *    no write verb is reached.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildHandlers } from '../dist/esm/actions.mjs';

/** `EDMT_EditorDocumentType` values, as the type package declares them. */
const DOC_TYPE = { SCHEMATIC_PAGE: 1, PCB: 3 };

/** `EPCB_PrimitiveType` spellings used below, from `@jlceda/pro-api-types`. */
const PRIM = {
  LINE: 'Line',
  ARC: 'Arc',
  VIA: 'Via',
  FILL: 'Fill',
  POUR: 'Pour',
  POLYLINE: 'Polyline',
  REGION: 'Region',
  PAD: 'Pad',
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
 * One fake editor: a component namespace, the two copper managers, and a log of
 * every direct/adjacent call with the ids each answered.
 *
 * The log is the point. `callIndex` is only evidence if it can be checked
 * against the call that actually happened, so the fixtures append an entry
 * **at invocation time** and the assertions look the index up.
 */
function makeWorld() {
  const log = [];
  const entire = [];
  const calls = { all: [], listings: 0 };
  const specs = new Map();
  const built = new Map();

  function define(spec) {
    specs.set(spec.id, spec);
    return spec;
  }

  function instanceFor(spec) {
    const methods = {
      getState_PrimitiveId: () => (spec.answerId === undefined ? spec.id : spec.answerId),
      getState_PrimitiveType: () => (spec.answerType === undefined ? spec.type : spec.answerType),
      getState_Net: () => spec.net,
      getState_Layer: () => (spec.layer === undefined ? 1 : spec.layer),
      getEntireTrack: (includeVias) => {
        entire.push({ id: spec.id, includeVias });
        throw new Error(`getEntireTrack must never be called on ${spec.type} ${spec.id} (559B/562)`);
      },
    };
    if (spec.noAdjacent !== true) {
      methods.getAdjacentPrimitives = () => {
        const ids = spec.adjacentIds ?? [];
        log.push({ method: 'getAdjacentPrimitives', ownerId: spec.id, type: spec.type, ids });
        if (spec.adjacentThrows !== undefined) throw spec.adjacentThrows;
        if (spec.adjacentValue !== undefined) return spec.adjacentValue;
        return ids.map((childId) => instanceOfId(childId)).filter((entry) => entry !== undefined);
      };
    }
    return instanceOf(methods);
  }

  function instanceOfId(id) {
    if (built.has(id)) return built.get(id);
    const spec = specs.get(id);
    if (!spec) return undefined;
    const made = recording(spec.custom ?? instanceFor(spec), calls.all);
    built.set(id, made);
    return made;
  }

  function pad({
    id,
    padNumber = '1',
    net,
    type = PRIM.COMPONENT_PAD,
    layer = 1,
    connectionIds = [],
    connectionsValue,
    connectionsThrows,
    extra = {},
  }) {
    const methods = {
      getState_PrimitiveId: () => id,
      getState_PrimitiveType: () => type,
      getState_PadNumber: () => padNumber,
      getState_Layer: () => layer,
      ...(net === undefined ? {} : { getState_Net: () => net }),
      getConnectedPrimitives(onlyCentre) {
        log.push({ method: 'getConnectedPrimitives', ownerId: id, ids: connectionIds });
        if (connectionsThrows !== undefined) throw connectionsThrows;
        if (connectionsValue !== undefined) return connectionsValue;
        return connectionIds.map((childId) => instanceOfId(childId)).filter((entry) => entry !== undefined);
      },
      ...extra,
    };
    const made = recording(instanceOf(methods), calls.all);
    built.set(id, made);
    specs.set(id, { id, type, net, isPad: true });
    return made;
  }

  function component(designator, pins) {
    return instanceOf({
      getState_Designator: () => designator,
      getAllPins: async () => pins,
    });
  }

  function editor({ designs = [], focus = 'pcb', managers = true } = {}) {
    const eda = {
      dmt_Pcb: { getCurrentPcbInfo: async () => ({ uuid: 'pcb-1', name: 'PCB1' }) },
      dmt_Schematic: {
        getCurrentSchematicPageInfo: async () => ({ uuid: 'page-1', name: 'P1.Schematic1' }),
      },
      pcb_PrimitiveComponent: recording({
        async getAll() {
          calls.listings += 1;
          return designs.map((entry) => recording(entry, calls.all));
        },
      }, calls.all),
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
    if (managers) {
      eda.pcb_PrimitiveLine = recording({
        async get(id) {
          const spec = specs.get(id);
          if (spec === undefined || spec.type !== PRIM.LINE) return undefined;
          return instanceOfId(id);
        },
      }, calls.all);
      eda.pcb_PrimitiveVia = recording({
        async get(id) {
          const spec = specs.get(id);
          if (spec === undefined || spec.type !== PRIM.VIA) return undefined;
          return instanceOfId(id);
        },
      }, calls.all);
    }
    return eda;
  }

  return { log, entire, calls, define, pad, component, editor, instanceOfId };
}

const probe = (eda, params) => buildHandlers(eda)['pcb.path_probe'](params);

/** No verdict-shaped key may appear anywhere in the answer. */
const FORBIDDEN = ['verdict', 'path', 'hops', 'hopCount', 'viaCount', 'sharedIds', 'connected'];

function assertNoVerdict(data) {
  for (const key of FORBIDDEN) {
    assert.equal(key in data, false, `${key} must not be in the answer`);
  }
  for (const end of [data.from, data.to]) {
    for (const key of FORBIDDEN) {
      assert.equal(key in end, false, `${key} must not be in an end`);
    }
  }
}

/**
 * Every edge must be locatable: `log[callIndex]` is the call it claims, and the
 * answered id at `hostOrder` is the edge's `to`.
 */
function assertTraceable(log, edges) {
  for (const edge of edges) {
    const call = log[edge.callIndex];
    assert.ok(call, `edge ${edge.from.type} ${edge.from.primitiveId}→${edge.to.type} `
      + `${edge.to.primitiveId} names callIndex ${edge.callIndex}, which no host call answers`);
    assert.equal(call.method, edge.method, 'the edge names the method that produced it');
    assert.equal(call.ownerId, edge.from.primitiveId, 'the call belongs to the edge\'s source');
    assert.equal(call.ids[edge.hostOrder], edge.to.primitiveId,
      'hostOrder is the position inside that very answer');
  }
}

// --------------------------------------------------------------------------
// 1. the page guard and the closed request, both before any read
// --------------------------------------------------------------------------

test('a schematic in front is refused with PAGE_MISMATCH and zero reads', async () => {
  const w = makeWorld();
  const eda = w.editor({
    focus: 'sch',
    designs: [w.component('R1', [w.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1' })])],
  });
  await assert.rejects(() => probe(eda, { from: 'R1.1', to: 'C2.2' }), (error) => {
    assert.equal(error.code, 'PAGE_MISMATCH');
    assert.match(error.message, /focused document is/);
    return true;
  });
  assert.equal(w.calls.listings, 0, 'the guard runs before the component scan');
  assert.deepEqual(w.calls.all, [], 'no component, pin or primitive is read');
  assert.deepEqual(w.log, [], 'no direct or adjacent call is made');
});

test('no focused document at all is PAGE_MISMATCH, with zero reads', async () => {
  const w = makeWorld();
  const eda = w.editor({ focus: 'none' });
  delete eda.dmt_Pcb;
  delete eda.dmt_Schematic;
  await assert.rejects(() => probe(eda, { from: 'R1.1', to: 'C2.2' }), (error) => {
    assert.equal(error.code, 'PAGE_MISMATCH');
    assert.match(error.message, /no active document/);
    return true;
  });
  assert.equal(w.calls.listings, 0);
  assert.deepEqual(w.log, []);
});

test('malformed ends and unknown keys are BAD_REQUEST before the host is touched', async () => {
  const w = makeWorld();
  const eda = w.editor({ designs: [] });
  const cases = [
    [{ from: 'R1.1' }, /params\.to must be a "REF\.PAD" string/],
    [{ to: 'C2.2' }, /params\.from must be a "REF\.PAD" string/],
    [{ from: 'R1.1', to: 'C2.2', hops: 4 }, /the allowed keys are from, to/],
    [{ from: 'R1', to: 'C2.2' }, /must be "REF\.PAD"/],
    [{ from: 'R1.1', to: 7 }, /must be a "REF\.PAD" string/],
  ];
  for (const [params, pattern] of cases) {
    await assert.rejects(() => probe(eda, params), (error) => {
      assert.equal(error.code, 'BAD_REQUEST', JSON.stringify(params));
      assert.match(error.message, pattern, JSON.stringify(params));
      return true;
    }, JSON.stringify(params));
  }
  assert.equal(w.calls.listings, 0);
  assert.deepEqual(w.log, []);
});

// --------------------------------------------------------------------------
// 2. the multi-hop happy path: one scan, two directions, traceable hops
// --------------------------------------------------------------------------

test('three lines and a via: both directions of every adjacency are recorded', async () => {
  const w = makeWorld();
  w.define({ id: 'ln1', type: PRIM.LINE, net: 'N1', adjacentIds: ['ln2'] });
  // Deliberately host-reversed: the Via comes first in the answer, so a
  // connector that followed host order would record via1 before ln1.
  w.define({ id: 'ln2', type: PRIM.LINE, net: 'N1', adjacentIds: ['via1', 'ln1'] });
  w.define({ id: 'via1', type: PRIM.VIA, net: 'N1', adjacentIds: ['ln2', 'ln3'] });
  w.define({ id: 'ln3', type: PRIM.LINE, net: 'N1', adjacentIds: ['p-c2-2', 'via1'] });
  const fromPad = w.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1', connectionIds: ['ln1'] });
  const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: ['ln3'] });
  const eda = w.editor({
    designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])],
  });

  const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });

  assert.equal(w.calls.listings, 1, 'one component scan answers both ends');
  assert.deepEqual(data.page, { uuid: 'pcb-1', type: 'pcb' });
  assert.equal(data.readOnly, true);
  // The answer is exactly the 562A contract's key set: host evidence, no verdict.
  assert.deepEqual(Object.keys(data).sort(), [
    'coverage', 'edges', 'errors', 'from', 'frontier', 'ignored', 'nodes', 'page',
    'readOnly', 'seeds', 'to', 'unknown',
  ]);

  // The two ends keep 559's readout: one direct call each, typed items.
  assert.equal(data.from.status, 'resolved');
  assert.deepEqual(data.from.pad, {
    primitiveId: 'p-r1-1', padNumber: '1', net: 'N1', type: 'ComponentPad',
  });
  assert.deepEqual(data.from.direct, {
    ok: true, count: 1, ids: ['ln1'], truncated: false, items: [{ primitiveId: 'ln1', type: 'Line' }],
  });
  assert.deepEqual(data.to.direct.items, [{ primitiveId: 'ln3', type: 'Line' }]);
  const directCalls = w.log.filter((call) => call.method === 'getConnectedPrimitives');
  assert.equal(directCalls.length, 2, 'each end is asked exactly once');

  // Vertices: the two endpoint pads plus every Line/Via the walk reached.
  assert.deepEqual(data.nodes, [
    { primitiveId: 'p-c2-2', type: 'ComponentPad', net: 'N1', layer: 1 },
    { primitiveId: 'p-r1-1', type: 'ComponentPad', net: 'N1', layer: 1 },
    { primitiveId: 'ln1', type: 'Line', net: 'N1', layer: 1 },
    { primitiveId: 'ln2', type: 'Line', net: 'N1', layer: 1 },
    { primitiveId: 'ln3', type: 'Line', net: 'N1', layer: 1 },
    { primitiveId: 'via1', type: 'Via', net: 'N1', layer: 1 },
  ]);
  // Only direct Lines are seeds — a Via is reached through adjacency, never
  // seeded — and **both** ends seed: the walk must be able to expand the far
  // side's copper too, or its reciprocal answers would never be collected.
  assert.deepEqual(data.seeds, [
    { primitiveId: 'ln1', type: 'Line' },
    { primitiveId: 'ln3', type: 'Line' },
  ]);
  assert.deepEqual(data.frontier, []);

  // Hops, in the order the walk made them, each pinned to one host call.
  assert.deepEqual(data.edges.map((edge) => [
    edge.callIndex, edge.hostOrder, edge.method, edge.kind,
    edge.from.primitiveId, edge.to.primitiveId,
  ]), [
    [0, 0, 'getConnectedPrimitives', 'pad-direct', 'p-r1-1', 'ln1'],
    [1, 0, 'getConnectedPrimitives', 'pad-direct', 'p-c2-2', 'ln3'],
    [2, 0, 'getAdjacentPrimitives', 'adjacent', 'ln1', 'ln2'],
    // ln2 answered [via1, ln1]; candidates are processed in (type, id) order,
    // so ln1 comes first while hostOrder keeps the host's own position.
    [3, 1, 'getAdjacentPrimitives', 'adjacent', 'ln2', 'ln1'],
    [3, 0, 'getAdjacentPrimitives', 'adjacent', 'ln2', 'via1'],
    [4, 0, 'getAdjacentPrimitives', 'adjacent-to-endpoint-pad', 'ln3', 'p-c2-2'],
    [4, 1, 'getAdjacentPrimitives', 'adjacent', 'ln3', 'via1'],
    [5, 0, 'getAdjacentPrimitives', 'adjacent', 'via1', 'ln2'],
    [5, 1, 'getAdjacentPrimitives', 'adjacent', 'via1', 'ln3'],
  ]);
  assertTraceable(w.log, data.edges);

  // Both directions exist as two separate edges with two separate calls: the
  // reciprocity rule belongs to Python, so the Connector keeps neither more nor
  // less than what the host said.
  const ln1ToLn2 = data.edges.filter((edge) => edge.from.primitiveId === 'ln1' && edge.to.primitiveId === 'ln2');
  const ln2ToLn1 = data.edges.filter((edge) => edge.from.primitiveId === 'ln2' && edge.to.primitiveId === 'ln1');
  assert.equal(ln1ToLn2.length, 1);
  assert.equal(ln2ToLn1.length, 1);
  assert.notEqual(ln1ToLn2[0].callIndex, ln2ToLn1[0].callIndex, 'each direction cites its own call');

  assert.deepEqual(data.errors, []);
  assert.deepEqual(data.unknown, []);
  assert.deepEqual(data.ignored, []);
  assert.equal(data.coverage.scan.components, 2);
  assert.equal(data.coverage.scan.complete, true);
  assert.equal(data.coverage.direct.reported.from, 1);
  assert.equal(data.coverage.adjacent.calls, 4, 'ln1, ln2, ln3 and the via were each expanded once');
  assert.equal(data.coverage.nodes.count, 6);
  assert.equal(data.coverage.edges.count, 9);
  assert.deepEqual(data.coverage.nets, { from: 'N1', to: 'N1', same: true });
  assert.equal(data.coverage.budget.exhausted, null);
  assert.equal(data.coverage.complete, true, 'nothing was withheld in this fixture');

  // getEntireTrack is trapped on every copper instance and must stay untouched.
  assert.deepEqual(w.entire, [], 'getEntireTrack is never called');
  assertNoVerdict(data);
  assertReadOnly(w.calls.all);
});

test('a one-way adjacency stays one-way evidence, never a verdict', async () => {
  const w = makeWorld();
  // ln1 names ln2; ln2 names nobody — the reverse direction does not exist.
  w.define({ id: 'ln1', type: PRIM.LINE, net: 'N1', adjacentIds: ['ln2'] });
  w.define({ id: 'ln2', type: PRIM.LINE, net: 'N1', adjacentIds: [] });
  const fromPad = w.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1', connectionIds: ['ln1'] });
  const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
  const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });

  const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });

  const forward = data.edges.filter((edge) => edge.from.primitiveId === 'ln1' && edge.to.primitiveId === 'ln2');
  const backward = data.edges.filter((edge) => edge.from.primitiveId === 'ln2' && edge.to.primitiveId === 'ln1');
  assert.equal(forward.length, 1, 'the host\'s one-way answer is kept');
  assert.equal(backward.length, 0, 'and no reciprocal edge is invented');
  assert.deepEqual(data.to.direct.ids, [], 'the other end answered nothing');
  assert.deepEqual(data.unknown, [], 'a one-way answer is evidence, not an unknown');
  assertNoVerdict(data);
  assertReadOnly(w.calls.all);
});

// --------------------------------------------------------------------------
// 3. classification: what may be a vertex, what is unknown, what is ignored
// --------------------------------------------------------------------------

test('pad-via, arc, pour, polyline, intermediate pad, missing net and other net are each classified', async () => {
  const w = makeWorld();
  w.define({ id: 'ln-ok', type: PRIM.LINE, net: 'N1', adjacentIds: [] });
  w.define({ id: 'via-x', type: PRIM.VIA, net: 'N1', adjacentIds: [] });
  w.define({ id: 'arc-1', type: PRIM.ARC, net: 'N1', adjacentIds: [] });
  w.define({ id: 'fill-1', type: PRIM.FILL, net: 'N1' });
  w.define({ id: 'pour-1', type: PRIM.POUR, net: 'N1' });
  w.define({ id: 'poly-1', type: PRIM.POLYLINE, net: 'N1' });
  w.define({ id: 'region-1', type: PRIM.REGION, net: 'N1' });
  w.define({ id: 'p-other-1', type: PRIM.COMPONENT_PAD, net: 'N1' });
  w.define({ id: 'ln-nonet', type: PRIM.LINE, net: undefined, adjacentIds: [] });
  w.define({ id: 'ln-othernet', type: PRIM.LINE, net: 'N2', adjacentIds: [] });
  const fromPad = w.pad({
    id: 'p-r1-1',
    padNumber: '1',
    net: 'N1',
    connectionIds: ['ln-ok', 'via-x', 'arc-1', 'fill-1', 'pour-1', 'poly-1', 'region-1', 'p-other-1', 'ln-nonet', 'ln-othernet'],
  });
  const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
  const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });

  const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });

  const codes = data.unknown.map((entry) => `${entry.code}:${entry.to ? entry.to.primitiveId : ''}`).sort();
  assert.deepEqual(codes, [
    // Pad→Via direct contact is not a claim this batch may make, and the via is
    // not seeded either (§4.7).
    'arc-unverified:arc-1',
    'intermediate-pad-unsupported:p-other-1',
    'net-missing:ln-nonet',
    'pad-via-contact:via-x',
    'unsupported-adjacent-type:poly-1',
    'unsupported-adjacent-type:region-1',
  ]);
  assert.deepEqual(
    data.ignored.map((entry) => `${entry.code}:${entry.to ? entry.to.primitiveId : ''}`).sort(),
    ['other-net:ln-othernet', 'pour-excluded:fill-1', 'pour-excluded:pour-1'],
  );

  // Only the same-net Line became a vertex, an edge and a seed.
  assert.deepEqual(data.nodes.map((node) => `${node.type} ${node.primitiveId}`), [
    'ComponentPad p-c2-2', 'ComponentPad p-r1-1', 'Line ln-ok',
  ]);
  assert.deepEqual(data.seeds, [{ primitiveId: 'ln-ok', type: 'Line' }]);
  assert.deepEqual(data.edges.map((edge) => edge.to.primitiveId), ['ln-ok']);

  // Nothing outside the proof set was expanded: exactly one manager get() ran.
  const gets = w.calls.all.filter((call) => call.name === 'get');
  assert.equal(gets.length, 1, 'only the accepted Line was fetched from a manager');
  assert.deepEqual(w.entire, [], 'getEntireTrack is never called');
  assert.equal(data.coverage.complete, false, 'unknowns forbid "nothing was withheld"');
  assertReadOnly(w.calls.all);
});

// --------------------------------------------------------------------------
// 4. read failures: disclosed, never expanded, never guessed at
// --------------------------------------------------------------------------

test('unreadable candidates are disclosed in host order and never expanded', async () => {
  const w = makeWorld();
  w.define({ id: 'ln-ok', type: PRIM.LINE, net: 'N1', adjacentIds: [] });
  const noId = recording(instanceOf({
    getState_PrimitiveType: () => PRIM.LINE,
  }), w.calls.all);
  const noType = recording(instanceOf({
    getState_PrimitiveId: () => 'ln-notype',
  }), w.calls.all);
  const fromPad = w.pad({
    id: 'p-r1-1',
    padNumber: '1',
    net: 'N1',
    connectionsValue: [noId, noType, 42, w.instanceOfId('ln-ok')],
    connectionIds: [],
  });
  const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
  const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });

  const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });

  assert.deepEqual(data.unknown.map((entry) => [entry.hostOrder, entry.code]), [
    [0, 'primitive-id-unreadable'],
    [1, 'primitive-type-unknown'],
    [2, 'entry-not-an-instance'],
  ]);
  assert.equal(data.from.direct.unreadable, 3, 'the readout counts what it could not name');
  assert.deepEqual(data.from.direct.items, [{ primitiveId: 'ln-ok', type: 'Line' }]);
  assert.equal(data.coverage.complete, false);
  assertReadOnly(w.calls.all);
});

test('a non-array, a missing method and a throwing method are disclosed and not expanded', async () => {
  const scenarios = [
    {
      name: 'non-array',
      spec: { id: 'ln-x', type: PRIM.LINE, net: 'N1', adjacentValue: 'not-an-array' },
      code: 'adjacent-not-array',
    },
    {
      name: 'missing',
      spec: { id: 'ln-x', type: PRIM.LINE, net: 'N1', noAdjacent: true },
      code: 'adjacent-missing',
    },
    {
      name: 'throws',
      spec: { id: 'ln-x', type: PRIM.LINE, net: 'N1', adjacentThrows: new Error('host said no') },
      code: 'adjacent-error',
    },
  ];
  for (const scenario of scenarios) {
    const w = makeWorld();
    w.define(scenario.spec);
    const fromPad = w.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1', connectionIds: ['ln-x'] });
    const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
    const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });

    const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });

    assert.deepEqual(
      data.unknown.filter((entry) => !entry.to).map((entry) => entry.code),
      [scenario.code],
      scenario.name,
    );
    assert.equal(data.errors.length, 1, `${scenario.name}: the failure text is in errors[]`);
    // Not expanded, so it stays in the frontier instead of vanishing.
    assert.deepEqual(data.frontier, [{ primitiveId: 'ln-x', type: 'Line' }], scenario.name);
    assert.equal(data.coverage.complete, false, scenario.name);
    assertReadOnly(w.calls.all);
  }
});

test('a manager that answers a different primitive, or is missing, does not expand', async () => {
  // (a) the pad advertises ln-m but get('ln-m') answers a different id, so the
  // instance cannot be trusted for one neighbour read → instance-mismatch.
  const w = makeWorld();
  const advertised = recording(instanceOf({
    getState_PrimitiveId: () => 'ln-m',
    getState_PrimitiveType: () => PRIM.LINE,
    getState_Net: () => 'N1',
    getState_Layer: () => 1,
  }), w.calls.all);
  w.define({ id: 'ln-m', type: PRIM.LINE, net: 'N1', answerId: 'ln-other', adjacentIds: [] });
  const fromPad = w.pad({
    id: 'p-r1-1', padNumber: '1', net: 'N1', connectionsValue: [advertised], connectionIds: [],
  });
  const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
  const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });
  const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });
  assert.deepEqual(data.unknown.filter((entry) => !entry.to).map((entry) => entry.code), ['instance-mismatch']);
  assert.equal(w.log.filter((call) => call.method === 'getAdjacentPrimitives').length, 0,
    'a mismatched instance has no neighbours read');
  assert.deepEqual(data.frontier, [{ primitiveId: 'ln-m', type: 'Line' }]);

  // (b) the manager namespace is absent entirely.
  const w2 = makeWorld();
  w2.define({ id: 'ln-n', type: PRIM.LINE, net: 'N1', adjacentIds: [] });
  const p1 = w2.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1', connectionIds: ['ln-n'] });
  const p2 = w2.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
  const eda2 = w2.editor({ designs: [w2.component('R1', [p1]), w2.component('C2', [p2])], managers: false });
  const data2 = await probe(eda2, { from: 'R1.1', to: 'C2.2' });
  assert.deepEqual(data2.unknown.filter((entry) => !entry.to).map((entry) => entry.code), ['manager-unavailable']);
  assert.equal(data2.errors.length, 1);
  assert.deepEqual(data2.frontier, [{ primitiveId: 'ln-n', type: 'Line' }]);
  assert.equal(data2.coverage.complete, false);
});

// --------------------------------------------------------------------------
// 5. caps: per call, and a whole-graph budget
// --------------------------------------------------------------------------

test('an answer longer than 64 candidates is truncated and disclosed', async () => {
  const w = makeWorld();
  const ids = Array.from({ length: 65 }, (_, index) => `ln${String(index + 1).padStart(2, '0')}`);
  for (const id of ids) w.define({ id, type: PRIM.LINE, net: 'N1', adjacentIds: [] });
  const fromPad = w.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1', connectionIds: ids });
  const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
  const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });

  const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });

  assert.equal(data.from.direct.count, 65, 'the honest count is kept');
  assert.equal(data.from.direct.truncated, true);
  assert.equal(data.from.direct.items.length, 64);
  const truncation = data.unknown.filter((entry) => entry.code === 'per-call-truncated');
  assert.equal(truncation.length, 1);
  assert.equal(truncation[0].kept, 64);
  assert.equal(truncation[0].reported, 65);
  assert.equal(data.coverage.direct.truncated.from, true);
  assert.equal(data.coverage.perCallTruncated, 1);
  assert.equal(data.seeds.length, 64);
  assert.equal(data.coverage.complete, false, 'a truncated answer forbids "complete"');
  assertReadOnly(w.calls.all);
});

test('the vertex budget stops the walk and leaves the unexpanded nodes in the frontier', async () => {
  const w = makeWorld();
  const first = Array.from({ length: 64 }, (_, index) => `ln${String(index + 1).padStart(2, '0')}`);
  for (const id of first) {
    const children = Array.from({ length: 64 }, (_, index) => `${id}-${String(index + 1).padStart(2, '0')}`);
    for (const child of children) w.define({ id: child, type: PRIM.LINE, net: 'N1', adjacentIds: [] });
    w.define({ id, type: PRIM.LINE, net: 'N1', adjacentIds: children });
  }
  const fromPad = w.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1', connectionIds: first });
  const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: [] });
  const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });

  const data = await probe(eda, { from: 'R1.1', to: 'C2.2' });

  assert.equal(data.coverage.nodes.cap, 512);
  assert.equal(data.coverage.nodes.count, 512, 'the graph stops at the vertex cap');
  assert.equal(data.nodes.length, 512);
  assert.equal(data.coverage.nodes.truncated, true);
  assert.equal(data.coverage.budget.exhausted, 'vertices');
  const budget = data.unknown.filter((entry) => entry.code === 'budget-exhausted');
  assert.equal(budget.length, 1);
  assert.equal(budget[0].budget, 'vertices');
  assert.ok(data.frontier.length > 0, 'what was not expanded is disclosed, not dropped');
  assert.equal(data.coverage.frontier, data.frontier.length);
  assert.equal(data.coverage.complete, false);
  assert.equal(data.coverage.adjacent.calls < 512, true, 'the vertex cap was hit before the call cap');
  assertReadOnly(w.calls.all);
});

// --------------------------------------------------------------------------
// 6. determinism
// --------------------------------------------------------------------------

test('the same input answers identically twice, wall clock aside', async () => {
  const build = () => {
    const w = makeWorld();
    w.define({ id: 'ln1', type: PRIM.LINE, net: 'N1', adjacentIds: ['ln2', 'via1'] });
    w.define({ id: 'ln2', type: PRIM.LINE, net: 'N1', adjacentIds: ['ln1', 'p-c2-2'] });
    w.define({ id: 'via1', type: PRIM.VIA, net: 'N1', adjacentIds: ['ln1'] });
    const fromPad = w.pad({ id: 'p-r1-1', padNumber: '1', net: 'N1', connectionIds: ['ln1'] });
    const toPad = w.pad({ id: 'p-c2-2', padNumber: '2', net: 'N1', connectionIds: ['ln2'] });
    const eda = w.editor({ designs: [w.component('R1', [fromPad]), w.component('C2', [toPad])] });
    return { w, eda };
  };
  const first = await probe(build().eda, { from: 'R1.1', to: 'C2.2' });
  const second = await probe(build().eda, { from: 'R1.1', to: 'C2.2' });
  // The elapsed time is a measurement, not structure; everything else must match.
  delete first.coverage.budget.elapsedMs;
  delete second.coverage.budget.elapsedMs;
  assert.deepEqual(second, first);
  assert.deepEqual(JSON.stringify(second), JSON.stringify(first));
});
