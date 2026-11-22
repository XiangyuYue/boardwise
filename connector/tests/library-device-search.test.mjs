/**
 * Contract tests for `lib.device.search`'s answer size (549 follow-up).
 *
 * The host's search answers its whole candidate set and the exact hit is not
 * always near the front — measured on test V4 Board2 P5, `C1590` /
 * `CL10B104KA8NNNC` is the **9th of 10** rows. The action's own default `limit`
 * was 8, so every caller that omitted `limit` lost that row. These tests drive
 * the production dispatch path (fake host → real facade → real handler) and pin
 * three things at the wire boundary:
 *
 * 1. no `limit` → the whole 10-row candidate set is shown, target included;
 * 2. an explicit `limit: 8` still truncates to 8 (the behaviour callers rely on
 *    is unchanged), and `shown` says 8;
 * 3. both answers report the host's real candidate count as `returned`, so a
 *    truncation can never be mistaken for a short candidate set.
 *
 * The regression is causal: setting the default back to 8 makes test 1 fail
 * (`shown` 8, target absent) while test 2 stays green.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { createFacade } from '../dist/esm/facade.mjs';
import * as connector from '../dist/esm/index.mjs';

const TARGET_INDEX = 8;

/** The ten rows the host holds for `C1590`: eight decoys, the target, one more. */
function libraryRows() {
  const decoys = Array.from({ length: 8 }, (_, index) => ({
    uuid: `dev-decoy-${index}`,
    libraryUuid: 'lib-decoys',
    supplierId: `C99000${index}`,
    name: `DECOY-${index}`,
    footprintName: '0603',
  }));
  return [
    ...decoys,
    {
      uuid: 'dev-c1590',
      libraryUuid: 'lib-c1590',
      supplierId: 'C1590',
      manufacturerId: 'CL10B104KA8NNNC',
      name: 'CL10B104KA8NNNC',
      footprintName: '0402',
      otherProperty: {
        'Supplier Part': 'C1590',
        'Manufacturer Part': 'CL10B104KA8NNNC',
      },
    },
    {
      uuid: 'dev-decoy-9',
      libraryUuid: 'lib-decoys',
      supplierId: 'C990009',
      name: 'DECOY-9',
      footprintName: '0603',
    },
  ];
}

/**
 * A host with just enough surface for the extension to activate, plus the
 * `lib_Device.search` the action under test calls. Every search is recorded so
 * the assertions can check what reached the host, not only what came back.
 */
function edaHost() {
  const searches = [];
  const host = {
    sys_WebSocket: {
      register(_id, _uri, onMessage) {
        host.__onMessage = onMessage;
      },
      send(_id, data) {
        host.__sent = host.__sent ?? [];
        host.__sent.push(JSON.parse(data));
      },
      close() {},
    },
    sys_Log: { add() {} },
    sys_Message: { showToastMessage() {} },
    sys_Environment: { getEditorCurrentVersion: () => '4.1.93' },
    sys_Storage: {
      getExtensionUserConfig: () => undefined,
      setExtensionUserConfig: async () => true,
    },
    sys_Dialog: { showInformationMessage() {} },
    lib_Device: {
      async search(keyword) {
        searches.push(keyword);
        return libraryRows().map((row) => ({ ...row }));
      },
    },
    __searches: searches,
  };
  return host;
}

function withEda(t, host) {
  connector.__setFacadeForTests(createFacade(host));
  t.after(() => {
    connector.deactivate();
    connector.__setFacadeForTests(undefined);
  });
}

/** Poll for a predicate; never a fixed sleep (Node clamps short timers). */
async function waitFor(predicate, timeoutMs = 2000) {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() > deadline) return false;
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
  return true;
}

async function call(host, action, params = {}) {
  const id = `req-${Math.random().toString(36).slice(2, 8)}`;
  void host.__onMessage({ data: JSON.stringify({ id, action, params }) });
  assert.ok(
    await waitFor(() => (host.__sent ?? []).some((frame) => frame.id === id)),
    `no response frame for ${action}`,
  );
  return (host.__sent ?? []).find((frame) => frame.id === id);
}

/** Start one activated session against a fresh host and answer one search. */
async function search(t, params) {
  const host = edaHost();
  withEda(t, host);
  await connector.activate();
  const frame = await call(host, 'lib.device.search', params);
  assert.equal(frame.ok, true, frame.error?.message);
  // The keyword must reach `lib_Device.search` untouched — this batch changes
  // only the answer size, never how a search is matched.
  assert.deepEqual(host.__searches, [params.keyword]);
  return frame.data;
}

test('no limit shows the whole candidate set, including the ninth row', async (t) => {
  const data = await search(t, { keyword: 'C1590' });

  assert.equal(data.keyword, 'C1590');
  // The host held ten rows; the default must not be the tightest page size.
  assert.equal(data.returned, 10);
  assert.equal(data.shown, 10);
  assert.equal(data.items.length, 10);

  // The exact hit is the 9th row — the one a default of 8 cut away.
  const target = data.items[TARGET_INDEX];
  assert.equal(target.supplierId, 'C1590');
  assert.equal(target.name, 'CL10B104KA8NNNC');
  assert.equal(target.otherProperty['Manufacturer Part'], 'CL10B104KA8NNNC');
  assert.equal(target.footprintName, '0402');
  assert.equal(target.uuid, 'dev-c1590');
  assert.equal(target.libraryUuid, 'lib-c1590');

  // The earlier rows are still the same rows, in the host's own order.
  assert.equal(data.items[0].supplierId, 'C990000');
  assert.equal(data.items[9].supplierId, 'C990009');
  assert.equal(data.items[9].name, 'DECOY-9');
  assert.equal(data.readErrors, undefined);
});

test('an explicit limit of 8 still truncates, and the answer says so', async (t) => {
  const data = await search(t, { keyword: 'C1590', limit: 8 });

  assert.equal(data.returned, 10, 'returned is the host count, never the page size');
  assert.equal(data.shown, 8);
  assert.equal(data.items.length, 8);
  assert.deepEqual(
    data.items.map((item) => item.supplierId),
    ['C990000', 'C990001', 'C990002', 'C990003', 'C990004', 'C990005', 'C990006', 'C990007'],
  );
  // The target is genuinely outside this answer: explicit truncation is real,
  // not a wider default wearing an 8.
  assert.equal(
    data.items.some((item) => item.supplierId === 'C1590'),
    false,
  );
});

test('an explicit limit wider than the candidate set shows every row', async (t) => {
  const data = await search(t, { keyword: 'C1590', limit: 64 });

  assert.equal(data.returned, 10);
  assert.equal(data.shown, 10);
  assert.equal(data.items[TARGET_INDEX].supplierId, 'C1590');
});
