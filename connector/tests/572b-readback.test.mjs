/**
 * 572B contract tests: five write actions whose "success" was the host's word.
 *
 * Batch 572 read the connector as a black box and found one family of the same
 * mistake in five shapes (see `outputs/hole572/TRIAGE.md` §1/§3 and
 * `outputs/hole572/b/REPRO.md`):
 *
 * - **572B-1** `sch.place_text` / `sch.place_wire` never read the primitive back,
 *   so success was only "the host returned an object".
 * - **572B-2** `sch.place_power` answered `{uuid: null}` as a success with no
 *   net/coordinate readback — a flag nobody had verified.
 * - **572B-3** `sch.doc.save` was the only bare boolean: any truthy answer
 *   counted as saved, and the project state was never read.
 * - **572B-4** `sch.place_netlabel` wrote "nothing appeared" — a *definite
 *   negative* — when the attribute API could not be read at all. That is the
 *   dangerous direction, because a netlabel retry stacks a second label on one
 *   that may well have landed (the action's own comment says so).
 * - **572B-5** a synchronous throw from `createNetLabel` was reported as
 *   `TIMEOUT`, a code `docs/bridge.md:934` reserves for "did not answer in
 *   time" — i.e. the retryable bucket. A permission refusal is not retryable.
 *
 * The through-line is the repo's own rule (`docs/bridge.md`, `pcb.net_class.list`):
 * **"could not read" is never "there are none"**. So every readback here is
 * three-valued — `true` / `false` / `null` — and the tests pin all three, because
 * the whole bug is that two of them used to be the same value.
 *
 * Mutation check that must fail (the point of the whole file, recorded for the
 * main agent): make `netAttributeLanded` return `landed: false` on a missing
 * `getAll` again, or drop `landed: null` from `schPlacePower`'s no-PrimitiveId
 * branch — the corresponding test must go red, not stay green.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { createFacade } from '../dist/esm/facade.mjs';
import * as connector from '../dist/esm/index.mjs';

/**
 * Editor primitives expose `getState_*` on their **prototype** (that is how
 * `deepDump` finds them), so the fakes are class instances, not object literals.
 */
class FakePrimitive {
  constructor(fields) {
    this.fields = fields;
  }
}
for (const name of ['PrimitiveId', 'ComponentType', 'X', 'Y', 'Net', 'Line', 'PointArr', 'Key', 'Value']) {
  Object.defineProperty(FakePrimitive.prototype, `getState_${name}`, {
    value: function () {
      return this.fields[name];
    },
  });
}

function primitive(idOrFields, extra = {}) {
  const fields = typeof idOrFields === 'string' ? { PrimitiveId: idOrFields } : idOrFields;
  return new FakePrimitive({ ...fields, ...extra });
}

/** Minimal host: only the namespaces these five actions touch. */
function host(overrides = {}) {
  const state = {};
  const hostObject = {
    sys_WebSocket: {
      register(_id, _uri, onMessage) {
        hostObject.__onMessage = onMessage;
      },
      send(_id, data) {
        hostObject.__sent = hostObject.__sent ?? [];
        hostObject.__sent.push(JSON.parse(data));
      },
      close() {},
    },
    sys_Log: { add() {} },
    sys_Message: { showToastMessage() {} },
    sys_Environment: { getEditorCurrentVersion: () => '3.2.186' },
    sys_Storage: {
      getExtensionUserConfig: () => undefined,
      setExtensionUserConfig: async () => true,
    },
    sys_Dialog: { showInformationMessage() {} },

    dmt_Schematic: {
      async getCurrentSchematicPageInfo() {
        return { uuid: 'page-1' };
      },
    },

    sch_Document: {
      async save() {
        return true;
      },
    },

    __state: state,
  };
  for (const [key, value] of Object.entries(overrides)) {
    if (value === null) delete hostObject[key];
    else hostObject[key] = typeof value === 'function' ? value(hostObject) : value;
  }
  return hostObject;
}

function withEda(t, hostObject) {
  connector.__setFacadeForTests(createFacade(hostObject));
  t.after(() => {
    connector.deactivate();
    connector.__setFacadeForTests(undefined);
  });
}

async function waitFor(predicate, timeoutMs = 2000) {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() > deadline) return false;
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
  return true;
}

async function call(hostObject, action, params = {}) {
  const id = `req-${Math.random().toString(36).slice(2, 8)}`;
  void hostObject.__onMessage({ data: JSON.stringify({ id, action, params }) });
  assert.ok(
    await waitFor(() => (hostObject.__sent ?? []).some((f) => f.id === id)),
    `no response frame for ${action}`,
  );
  return (hostObject.__sent ?? []).find((f) => f.id === id);
}

// --------------------------------------------------------------------------
// 572B-4: sch.place_netlabel — a read that did not happen is not a negative
// --------------------------------------------------------------------------

test('572B-4: a missing attribute API makes landedAnyway null, not false', async (t) => {
  // The host has no `getAll`. Old behaviour: `landedAnyway: false` plus
  // "nothing appeared" — a confident negative built out of a missing capability,
  // which invites a retry that stacks a duplicate label.
  const h = host({
    sch_PrimitiveAttribute: {
      createNetLabel: () => new Promise(() => {}), // hangs, like #191
      // getAll deliberately absent
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_netlabel', {
    x: 10, y: 20, net: 'TX', pageUuid: 'page-1', timeoutMs: 250,
  });
  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'TIMEOUT', 'the call really did not settle');
  assert.equal(
    frame.error.detail.landedAnyway,
    null,
    'an unreadable readback is UNKNOWN — never the definite `false`',
  );
  assert.equal(frame.error.detail.matches, 0);
  assert.match(frame.error.detail.readbackBasis, /UNKNOWN/);
  assert.ok(frame.error.detail.readError, 'the reason the read could not be taken is kept');
  assert.match(frame.error.message, /readback unavailable/);
  assert.match(frame.error.message, /UNKNOWN/);
  assert.doesNotMatch(
    frame.error.message,
    /nothing for TX appeared/,
    'the old lie: "nothing appeared" when nothing was read',
  );
});

test('572B-4: a throwing getAll is also unknown, not "nothing appeared"', async (t) => {
  const h = host({
    sch_PrimitiveAttribute: {
      createNetLabel: () => new Promise(() => {}),
      getAll() {
        throw new Error('permission denied reading attributes');
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_netlabel', {
    x: 10, y: 20, net: 'TX', pageUuid: 'page-1', timeoutMs: 250,
  });
  assert.equal(frame.ok, false);
  assert.equal(frame.error.detail.landedAnyway, null);
  assert.match(frame.error.detail.readError, /permission denied/);
  assert.doesNotMatch(frame.error.message, /nothing for TX appeared/);
});

test('572B-4: a read that really found nothing is still a hard false', async (t) => {
  // The other direction matters just as much: the fix must not turn every
  // readback into `null`, or "it did not land" becomes unstateable.
  const h = host({
    sch_PrimitiveAttribute: {
      createNetLabel: () => new Promise(() => {}),
      async getAll() {
        return [];
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_netlabel', {
    x: 10, y: 20, net: 'TX', pageUuid: 'page-1', timeoutMs: 250,
  });
  assert.equal(frame.error.code, 'TIMEOUT');
  assert.equal(frame.error.detail.landedAnyway, false);
  assert.match(frame.error.message, /the call is unusable/);
});

test('572B-4: a label found by readback is true and says do NOT retry', async (t) => {
  const h = host({
    sch_PrimitiveAttribute: {
      createNetLabel: () => new Promise(() => {}),
      async getAll() {
        return [primitive({ PrimitiveId: 'attr-1', Key: 'NET', Value: 'TX', X: 10, Y: 20 })];
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_netlabel', {
    x: 10, y: 20, net: 'TX', pageUuid: 'page-1', timeoutMs: 250,
  });
  assert.equal(frame.error.detail.landedAnyway, true);
  assert.equal(frame.error.detail.matches, 1);
  assert.match(frame.error.message, /do NOT retry/);
});

// --------------------------------------------------------------------------
// 572B-5: a synchronous throw is CONNECTOR_ERROR; only a real timeout is TIMEOUT
// --------------------------------------------------------------------------

test('572B-5: a synchronous throw from createNetLabel is CONNECTOR_ERROR', async (t) => {
  const h = host({
    sch_PrimitiveAttribute: {
      createNetLabel() {
        throw new Error('no permission to place labels');
      },
      async getAll() {
        return [];
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_netlabel', {
    x: 5, y: 6, net: 'RX', pageUuid: 'page-1', timeoutMs: 250,
  });
  assert.equal(frame.ok, false);
  assert.equal(
    frame.error.code,
    'CONNECTOR_ERROR',
    'a refusal is a definite answer, not "the connector did not answer in time"',
  );
  assert.match(frame.error.message, /threw instead of answering/);
  assert.match(frame.error.message, /no permission to place labels/, 'the host’s own words survive');
  assert.match(frame.error.detail.hostFailure, /no permission to place labels/);
});

test('572B-5: a host that hangs still answers TIMEOUT', async (t) => {
  const h = host({
    sch_PrimitiveAttribute: {
      createNetLabel: () => new Promise(() => {}),
      async getAll() {
        return [];
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_netlabel', {
    x: 5, y: 6, net: 'RX', pageUuid: 'page-1', timeoutMs: 250,
  });
  assert.equal(frame.error.code, 'TIMEOUT', 'the retryable case keeps its retryable code');
  assert.match(frame.error.message, /did not settle within 250 ms/);
  assert.equal(
    frame.error.detail.hostFailure,
    undefined,
    'a timeout carries no host failure — the host never spoke',
  );
});

// --------------------------------------------------------------------------
// 572B-1a: sch.place_text reads its own anchor back
// --------------------------------------------------------------------------

test('572B-1: place_text reports where the text really is', async (t) => {
  const h = host({
    sch_PrimitiveText: {
      async create() {
        return primitive('text-1');
      },
      async get(uuid) {
        assert.equal(uuid, 'text-1');
        return primitive({ PrimitiveId: 'text-1', X: 120, Y: 240 });
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_text', {
    x: 120, y: 240, content: 'RX', pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true, JSON.stringify(frame));
  assert.equal(frame.data.uuid, 'text-1');
  assert.equal(frame.data.content, 'RX');
  assert.equal(frame.data.decorative, true, 'the old field keeps its old meaning');
  assert.equal(frame.data.landed, true);
  assert.deepEqual(frame.data.readback.placed, { x: 120, y: 240 });
});

test('572B-1: place_text is not a success when the read-back disagrees', async (t) => {
  const h = host({
    sch_PrimitiveText: {
      async create() {
        return primitive('text-1');
      },
      async get() {
        return primitive({ PrimitiveId: 'text-1', X: 220, Y: 240 }); // 100 off in x
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_text', {
    x: 120, y: 240, content: 'RX', pageUuid: 'page-1',
  });
  assert.equal(frame.ok, false, 'a host object is not a placement');
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.landed, false);
  assert.equal(frame.error.detail.readbackMismatch, true);
  assert.match(frame.error.message, /read-back puts it at \(220, 240\)/);
});

test('572B-1: place_text without a get answers landed null, never true', async (t) => {
  // The 006b fake host, and possibly a real older host, has no `get`. That is a
  // missing capability: the text may well be on the page, but nothing here read
  // it, so the honest value is `null`.
  const h = host({
    sch_PrimitiveText: {
      async create() {
        return primitive('text-1');
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_text', {
    x: 1, y: 2, content: 'RX', pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true, 'old callers still get their uuid/content');
  assert.equal(frame.data.landed, null);
  assert.match(frame.data.readback.readError, /get is not available/);
  assert.match(frame.data.readback.basis, /UNKNOWN/);
});

// --------------------------------------------------------------------------
// 572B-1b: sch.place_wire reads its polyline back
// --------------------------------------------------------------------------

test('572B-1: place_wire reads the polyline under the field the live host uses (Line)', async (t) => {
  // Measured on EDA 4.1.100 (2026-11-26, evidence/u14/REPORT.md 2.2): a wire
  // primitive exposes PrimitiveType/PrimitiveId/Line/Net and nothing called
  // PointArr/Points/PointArray/Polyline, so this is the shape the readback meets
  // in the editor. It used to answer `landed: null` here — a re-read wire whose
  // geometry was readable, reported as UNKNOWN.
  const h = host({
    sch_PrimitiveWire: {
      async create() {
        return primitive('wire-1');
      },
      async get() {
        return primitive({ PrimitiveId: 'wire-1', Line: [0, 0, 10, 0] });
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_wire', {
    points: [[0, 0], [10, 0]], net: 'GND', pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true, JSON.stringify(frame));
  assert.equal(frame.data.landed, true, 'the live field name must reach the comparison');
  assert.deepEqual(frame.data.readback.points, [0, 0, 10, 0]);
  assert.equal(frame.data.readback.maxDelta, 0);
});

test('572B-1: place_wire reports the polyline it read back', async (t) => {
  const h = host({
    sch_PrimitiveWire: {
      async create() {
        return primitive('wire-1');
      },
      async get() {
        return primitive({ PrimitiveId: 'wire-1', PointArr: [0, 0, 10, 0] });
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_wire', {
    points: [[0, 0], [10, 0]], net: 'GND', pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true, JSON.stringify(frame));
  assert.equal(frame.data.uuid, 'wire-1');
  assert.deepEqual(frame.data.points, [[0, 0], [10, 0]], 'the old echo keeps its shape');
  assert.equal(frame.data.landed, true);
  assert.deepEqual(frame.data.readback.points, [0, 0, 10, 0]);
  assert.equal(frame.data.readback.maxDelta, 0);
});

test('572B-1: place_wire fails when the read-back polyline is elsewhere', async (t) => {
  const h = host({
    sch_PrimitiveWire: {
      async create() {
        return primitive('wire-1');
      },
      async get() {
        return primitive({ PrimitiveId: 'wire-1', PointArr: [100, 0, 110, 0] });
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_wire', {
    points: [[0, 0], [10, 0]], pageUuid: 'page-1',
  });
  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.landed, false);
  assert.equal(frame.error.detail.readbackMismatch, true);
  assert.equal(frame.error.detail.readback.maxDelta, 100);
});

test('572B-1: place_wire without a get answers landed null', async (t) => {
  const h = host({
    sch_PrimitiveWire: {
      async create() {
        return primitive('wire-1');
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_wire', {
    points: [[0, 0], [10, 0]], pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true);
  assert.equal(frame.data.landed, null);
  assert.match(frame.data.readback.readError, /get is not available/);
});

test('572B-1: place_wire with an unreadable polyline answers landed null', async (t) => {
  const h = host({
    sch_PrimitiveWire: {
      async create() {
        return primitive('wire-1');
      },
      async get() {
        return primitive('wire-1'); // no PointArr/Points at all
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_wire', {
    points: [[0, 0], [10, 0]], pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true);
  assert.equal(frame.data.landed, null);
  assert.match(frame.data.readback.basis, /no readable polyline/);
});

// --------------------------------------------------------------------------
// 572B-2: sch.place_power — no PrimitiveId means unverified, not placed
// --------------------------------------------------------------------------

test('572B-2: place_power without a PrimitiveId is explicitly unverified', async (t) => {
  const h = host({
    sch_PrimitiveComponent: {
      async createNetFlag() {
        return {}; // no PrimitiveId
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_power', {
    kind: 'Ground', net: 'GND', x: 5, y: 6, pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true, 'the old shape `{uuid: null}` is still a success');
  assert.equal(frame.data.uuid, null);
  assert.equal(frame.data.landed, null, 'nothing verified it, so nothing claims it landed');
  assert.equal(frame.data.unverified, true);
  assert.deepEqual(frame.data.readback, { net: 'GND', x: 5, y: 6, verified: false });
  assert.match(frame.data.basis, /UNVERIFIED/);
});

test('572B-2: place_power without a get is unverified, not landed', async (t) => {
  const h = host({
    sch_PrimitiveComponent: {
      async createNetFlag() {
        return primitive('flag-1');
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_power', {
    kind: 'Ground', net: 'GND', x: 5, y: 6, pageUuid: 'page-1',
  });
  assert.equal(frame.data.uuid, 'flag-1');
  assert.equal(frame.data.landed, null);
  assert.equal(frame.data.unverified, true);
  assert.equal(frame.data.readback.verified, false);
  assert.match(frame.data.readback.why ?? frame.data.readError ?? '', /get is not available/);
});

test('572B-2: place_power verifies net and position from a fresh read', async (t) => {
  const h = host({
    sch_PrimitiveComponent: {
      async createNetFlag() {
        return primitive('flag-1');
      },
      async get(uuid) {
        assert.equal(uuid, 'flag-1');
        return primitive({ PrimitiveId: 'flag-1', Net: 'GND', X: 5, Y: 6 });
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_power', {
    kind: 'Ground', net: 'GND', x: 5, y: 6, pageUuid: 'page-1',
  });
  assert.equal(frame.ok, true, JSON.stringify(frame));
  assert.equal(frame.data.landed, true);
  assert.equal(frame.data.readback.verified, true);
  assert.deepEqual(frame.data.readback.net, 'GND');
});

test('572B-2: place_power fails when the flag carries another net', async (t) => {
  const h = host({
    sch_PrimitiveComponent: {
      async createNetFlag() {
        return primitive('flag-1');
      },
      async get() {
        return primitive({ PrimitiveId: 'flag-1', Net: 'VCC', X: 5, Y: 6 });
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_power', {
    kind: 'Ground', net: 'GND', x: 5, y: 6, pageUuid: 'page-1',
  });
  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.landed, false);
  assert.equal(frame.error.detail.readbackMismatch, true);
  assert.match(frame.error.message, /"VCC" ≠ "GND"/);
});

test('572B-2: place_power fails when the flag landed somewhere else', async (t) => {
  const h = host({
    sch_PrimitiveComponent: {
      async createNetFlag() {
        return primitive('flag-1');
      },
      async get() {
        return primitive({ PrimitiveId: 'flag-1', Net: 'GND', X: 105, Y: 6 });
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.place_power', {
    kind: 'Ground', net: 'GND', x: 5, y: 6, pageUuid: 'page-1',
  });
  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.readback.maxDelta, 100);
});

// --------------------------------------------------------------------------
// 572B-3: sch.doc.save — a strict boolean, or an honest "unknown"
// --------------------------------------------------------------------------

test('572B-3: a truthy non-boolean answer is unknown, not saved', async (t) => {
  const h = host({
    sch_Document: {
      async save() {
        return {}; // the probe's exact lie: `{}` used to read as `{saved: true}`
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.doc.save', {});
  assert.equal(frame.ok, true, 'the action still answers — the caller decides');
  assert.equal(frame.data.saved, 'unknown', 'only a strict `true` may say saved');
  assert.notEqual(frame.data.saved, true);
  assert.equal(frame.data.savedVerified, false);
  assert.match(frame.data.hostAnswer, /^object/);
  assert.equal(frame.data.stateReadback, 'unavailable', 'no dmt_Project, so no state either');
  assert.match(frame.data.basis, /did not answer a boolean/);
});

test('572B-3: a string answer is unknown too', async (t) => {
  const h = host({
    sch_Document: {
      async save() {
        return 'ok';
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.doc.save', {});
  assert.equal(frame.data.saved, 'unknown');
  assert.equal(frame.data.hostAnswer, 'string "ok"');
});

test('572B-3: a strict true still reads as saved', async (t) => {
  const h = host({});
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.doc.save', {});
  assert.equal(frame.data.saved, true);
  assert.equal(frame.data.hostAnswer, true);
  assert.equal(frame.data.stateReadback, 'unavailable');
  assert.equal(
    frame.data.savedVerified,
    false,
    'a host word with no project state to confirm it is not "verified"',
  );
});

test('572B-3: the project state box confirms a save when the host carries it', async (t) => {
  const h = host({
    dmt_Project: {
      async getCurrentProjectInfo() {
        return { name: 'test', saved: true, dirty: false };
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.doc.save', {});
  assert.equal(frame.data.saved, true);
  assert.equal(frame.data.savedVerified, true);
  assert.deepEqual(frame.data.stateReadback, { available: true, saved: true, dirty: false });
});

test('572B-3: a dirty project box leaves savedVerified false', async (t) => {
  const h = host({
    dmt_Project: {
      async getCurrentProjectInfo() {
        return { saved: false, dirty: true };
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.doc.save', {});
  assert.equal(frame.data.saved, true, 'the host still said true');
  assert.equal(frame.data.savedVerified, false, 'but the project says it is dirty');
});

test('572B-3: a strict false is still an error, with saved:false in the detail', async (t) => {
  const h = host({
    sch_Document: {
      async save() {
        return false;
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.doc.save', {});
  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.saved, false);
});

test('572B-3: a save that throws is unknown and says so', async (t) => {
  const h = host({
    sch_Document: {
      save() {
        throw new Error('project is read-only');
      },
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'sch.doc.save', {});
  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.saved, 'unknown');
  assert.match(frame.error.message, /project is read-only/);
});
