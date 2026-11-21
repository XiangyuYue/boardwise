/**
 * `sch.set_pin_no_connected` — the one native NC write (044).
 *
 * The F1/STM32G431 rebuild needs real NoConnected crosses, and no bridge action
 * could write the flag. This fake host models the three things the write must not
 * trust:
 *
 * 1. an id is not an identity — the **parent's own pin list** has to contain
 *    it, with the stated pin number and (when given) the stated old value;
 * 2. `modify`'s answer is not evidence — a fresh parent-pin read decides
 *    `applied`, so a host that accepts and stores nothing (or answers
 *    `undefined`) is never reported as success.
 * 3. V4.1.100 measured a noConnected-only modify re-deriving the pin position:
 *    R pin2 (520,500) became (520,-500) and the NC cross rendered off-page.
 *    The fake host therefore flips y when x/y are omitted, and every successful
 *    test asserts the write carries the current coordinates and the pin stays
 *    where it was.
 *
 * Every test goes through the production dispatch path (facade + activate +
 * wire frames), so the response shape is what the daemon sees.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { createFacade } from '../dist/esm/facade.mjs';
import * as connector from '../dist/esm/index.mjs';

const PAGE = 'page-1';
const COMPONENT = 'comp-u1';

/** A placed component pin as the host exposes it (`ISCH_PrimitiveComponentPin`). */
function pinObject(pin, { withCoordinates = true } = {}) {
  const view = {
    getState_PrimitiveId: () => pin.id,
    getState_PinNumber: () => pin.number,
    getState_NoConnected: () => pin.noConnected,
  };
  if (withCoordinates) {
    view.getState_X = () => pin.x;
    view.getState_Y = () => pin.y;
  }
  return view;
}

/**
 * A host holding one component and its pins.
 *
 * `honour: false` models a host that accepts `modify` and stores nothing;
 * `throwModify` throws before storing; `eraseOnModify` stores `undefined` into
 * the flag (the "undefined is not success" case); `withoutModify` removes the
 * write namespace entirely.
 */
function host({
  initial = [
    { id: 'p1', number: '1', noConnected: true, x: 480, y: 500 },
    { id: 'p2', number: '2', noConnected: false, x: 520, y: 500 },
  ],
  currentPage = PAGE,
  honour = true,
  throwModify = false,
  eraseOnModify = false,
  withoutModify = false,
  dropCoordinates = false,
  recomputeOnModify = false,
} = {}) {
  const pins = initial.map((pin) => ({ ...pin }));
  const modifyCalls = [];
  const hostObject = {
    sys_WebSocket: {
      register(_id, _uri, onMessage) { hostObject.__onMessage = onMessage; },
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
      async getCurrentSchematicPageInfo() { return { uuid: currentPage }; },
    },
    sch_PrimitiveComponent: {
      async get(primitiveId) {
        return primitiveId === COMPONENT
          ? { getState_PrimitiveId: () => primitiveId }
          : undefined;
      },
      async getAllPinsByPrimitiveId(primitiveId) {
        // An unknown parent answers an empty list: the action must treat that
        // as NOT_FOUND, never as "a component with no pins took the write".
        return primitiveId === COMPONENT
          ? pins.map((pin) => pinObject(pin, { withCoordinates: !dropCoordinates }))
          : [];
      },
    },
    __pins: pins,
    __modifyCalls: modifyCalls,
  };
  if (!withoutModify) {
    hostObject.sch_PrimitivePin = {
      async modify(primitiveId, property) {
        modifyCalls.push({ id: primitiveId, property });
        if (throwModify) throw new Error('host refused the pin write');
        if (!honour) return { getState_PrimitiveId: () => primitiveId };
        const pin = pins.find((candidate) => candidate.id === primitiveId);
        if (!pin) return undefined;
        if (Object.prototype.hasOwnProperty.call(property, 'noConnected')) {
          pin.noConnected = eraseOnModify ? undefined : property.noConnected;
        }
        if (recomputeOnModify) {
          // A host that re-derives the position even when x/y are supplied.
          pin.y = -pin.y;
        } else if (typeof property.x === 'number' && typeof property.y === 'number') {
          pin.x = property.x;
          pin.y = property.y;
        } else {
          // V4.1.100: a noConnected-only modify re-derives the pin position.
          pin.y = -pin.y;
        }
        return pinObject(pin);
      },
    };
  } else {
    hostObject.sch_PrimitivePin = {};
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
    await waitFor(() => (hostObject.__sent ?? []).some((frame) => frame.id === id)),
    `no response frame for ${action}`,
  );
  return (hostObject.__sent ?? []).find((frame) => frame.id === id);
}

/** The request every happy-path test starts from, with overrides. */
function request(overrides = {}) {
  return {
    pageUuid: PAGE,
    parentPrimitiveId: COMPONENT,
    primitiveId: 'p2',
    expectedPinNumber: '2',
    noConnected: true,
    ...overrides,
  };
}

async function ready(t, options) {
  const h = host(options);
  withEda(t, h);
  await connector.activate();
  await connector.activate();
  return h;
}

test('sets true on the named second pin, not the first', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({ expectedNoConnected: false }));

  assert.equal(frame.ok, true, JSON.stringify(frame));
  assert.equal(frame.data.pageUuid, PAGE);
  assert.equal(frame.data.parentPrimitiveId, COMPONENT);
  assert.equal(frame.data.primitiveId, 'p2');
  assert.equal(frame.data.pinNumber, '2');
  assert.equal(frame.data.before, false);
  assert.equal(frame.data.requested, true);
  assert.equal(frame.data.after, true);
  assert.equal(frame.data.applied, true);
  assert.deepEqual(frame.data.mismatched, []);
  assert.deepEqual(frame.data.coordinatesBefore, { x: 520, y: 500 });
  assert.deepEqual(frame.data.coordinatesAfter, { x: 520, y: 500 });

  const p2 = h.__pins.find((pin) => pin.id === 'p2');
  assert.equal(p2.noConnected, true);
  assert.equal(p2.x, 520, 'x was repeated unchanged');
  assert.equal(p2.y, 500, 'y was repeated unchanged (a noConnected-only modify flips it)');
  assert.equal(h.__pins.find((pin) => pin.id === 'p1').noConnected, true, 'p1 was not touched');
  assert.equal(h.__pins.find((pin) => pin.id === 'p1').y, 500, 'p1 position was not touched');
  assert.equal(h.__modifyCalls.length, 1);
  assert.deepEqual(h.__modifyCalls[0], {
    id: 'p2', property: { noConnected: true, x: 520, y: 500 },
  });
});

test('a host that moves the pin while applying NC is not success', async (t) => {
  // The lead's second reading: checking only the flag reported an off-page NC
  // cross as success. Both coordinates are part of the after-read now.
  const h = await ready(t, { recomputeOnModify: true });
  const frame = await call(h, 'sch.set_pin_no_connected', request());

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.applied, false);
  assert.equal(frame.error.detail.after, true, 'the flag itself did take');
  assert.deepEqual(frame.error.detail.coordinatesBefore, { x: 520, y: 500 });
  assert.deepEqual(frame.error.detail.coordinatesAfter, { x: 520, y: -500 });
  assert.deepEqual(frame.error.detail.mismatched, [
    { field: 'y', expected: 500, actual: -500 },
  ]);
  assert.equal(h.__pins.find((pin) => pin.id === 'p2').y, -500);
});

test('sets false as a real request (false is not "no argument")', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({
    primitiveId: 'p1',
    expectedPinNumber: '1',
    noConnected: false,
    expectedNoConnected: true,
  }));

  assert.equal(frame.ok, true, JSON.stringify(frame));
  assert.equal(frame.data.before, true);
  assert.equal(frame.data.requested, false);
  assert.equal(frame.data.after, false);
  assert.equal(frame.data.applied, true);
  assert.deepEqual(h.__modifyCalls, [{
    id: 'p1', property: { noConnected: false, x: 480, y: 500 },
  }]);
  assert.equal(h.__pins.find((pin) => pin.id === 'p1').y, 500, 'the coordinate is preserved');
});

test('refuses when the pin coordinates cannot be read, before any write', async (t) => {
  const h = await ready(t, { dropCoordinates: true });
  const frame = await call(h, 'sch.set_pin_no_connected', request());

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /getState_X unavailable/);
  assert.match(frame.error.message, /getState_Y unavailable/);
  assert.deepEqual(h.__modifyCalls, [], 'without the current coordinates there is no safe write');
});

test('refuses a page that is not the focused one, before any write', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({ pageUuid: 'other-page' }));

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'PAGE_MISMATCH');
  assert.deepEqual(h.__modifyCalls, []);
});

test('refuses an unknown parent component', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({ parentPrimitiveId: 'comp-ghost' }));

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'NOT_FOUND');
  assert.match(frame.error.message, /comp-ghost/);
  assert.deepEqual(h.__modifyCalls, []);
});

test('refuses a pin id the parent does not own', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({ primitiveId: 'p99' }));

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'NOT_FOUND');
  assert.match(frame.error.message, /not a pin of component/);
  assert.deepEqual(h.__modifyCalls, []);
});

test('refuses a pin whose number is not the expected one', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({ expectedPinNumber: '22' }));

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /pinNumber: expected "22", found "2"/);
  assert.deepEqual(h.__modifyCalls, [], 'a stale identity means zero writes');
});

test('refuses when the old NoConnected is not what the caller expected', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({ expectedNoConnected: true }));

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /noConnected: expected true, found false/);
  assert.deepEqual(h.__modifyCalls, [], 'the pre-write state did not match, so nothing moved');
});

test('a flag that is not a strict boolean is refused', async (t) => {
  const h = await ready(t);
  for (const bad of ['true', 1, 0, null]) {
    const frame = await call(h, 'sch.set_pin_no_connected', request({ noConnected: bad }));
    assert.equal(frame.ok, false, `noConnected=${JSON.stringify(bad)} must be refused`);
    assert.equal(frame.error.code, 'BAD_REQUEST');
  }
  const expectedBad = await call(h, 'sch.set_pin_no_connected', request({
    expectedNoConnected: 'false',
  }));
  assert.equal(expectedBad.ok, false);
  assert.equal(expectedBad.error.code, 'BAD_REQUEST');
  assert.deepEqual(h.__modifyCalls, []);
});

test('coordinates and other properties are refused by name', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.set_pin_no_connected', request({ x: 10, net: 'GND' }));

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'BAD_REQUEST');
  assert.match(frame.error.message, /refusing x, net/);
  assert.deepEqual(h.__modifyCalls, []);
});

test('a host without sch_PrimitivePin.modify is refused, never a fake success', async (t) => {
  const h = await ready(t, { withoutModify: true });
  const frame = await call(h, 'sch.set_pin_no_connected', request());

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'NOT_IMPLEMENTED');
  assert.match(frame.error.message, /sch_PrimitivePin\.modify/);
  assert.equal(frame.data, undefined);
  assert.deepEqual(h.__modifyCalls, []);
});

test('modify throwing without changing the pin is not success', async (t) => {
  const h = await ready(t, { throwModify: true });
  const frame = await call(h, 'sch.set_pin_no_connected', request());

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.applied, false, 'a throw must never imply applied');
  assert.equal(frame.error.detail.after, false);
  assert.equal(frame.error.detail.mismatched.length, 1);
  assert.match(frame.error.detail.modifyError, /host refused the pin write/);
  assert.equal(h.__pins.find((pin) => pin.id === 'p2').noConnected, false);
});

test('a host that accepts and stores nothing reports applied false', async (t) => {
  const h = await ready(t, { honour: false });
  const frame = await call(h, 'sch.set_pin_no_connected', request());

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.applied, false);
  assert.equal(frame.error.detail.before, false);
  assert.equal(frame.error.detail.after, false);
  assert.deepEqual(frame.error.detail.mismatched, [
    { field: 'noConnected', expected: true, actual: false },
  ]);
  assert.equal(h.__pins.find((pin) => pin.id === 'p2').noConnected, false);
});

test('an undefined read-back is never treated as success', async (t) => {
  const h = await ready(t, { eraseOnModify: true });
  const frame = await call(h, 'sch.set_pin_no_connected', request());

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.equal(frame.error.detail.applied, false);
  assert.equal(frame.error.detail.after, null);
  assert.match(frame.error.detail.mismatched[0].error, /unreadable after the write/);
});

test('sch.component_pins still reads the same parent list and writes nothing', async (t) => {
  const h = await ready(t);
  const frame = await call(h, 'sch.component_pins', { primitiveId: COMPONENT });

  assert.equal(frame.ok, true, JSON.stringify(frame));
  assert.equal(frame.data.primitiveId, COMPONENT);
  assert.equal(frame.data.returned, 2);
  assert.deepEqual(frame.data.pins.map((pin) => pin.PinNumber), ['1', '2']);
  assert.deepEqual(frame.data.pins.map((pin) => pin.NoConnected), [true, false]);
  assert.deepEqual(h.__modifyCalls, [], 'the read action must never touch the host write path');
});
