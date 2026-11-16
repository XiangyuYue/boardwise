/**
 * 087F1: `export.render` on a **confirmed PCB** — the viewport branch (#87②).
 *
 * The defect this pins: since it was written, `export.render` had one backend,
 * `sch_ManufactureData.getExportDocumentFile`, a *schematic* document export. On
 * a PCB it does not fail — on EDA 4.1.93 it hangs until the caller gives up, and
 * `engines/liveevidence` recorded exactly that 60 s timeout before it stopped
 * taking PCB images. The fix routes a *confirmed* PCB to the one channel the
 * 087f probe measured (`dmt_EditorControl.getCurrentRenderedAreaImage` after
 * `zoomToAllPrimitives`), and the tests below are written so that they fail on
 * the old code: the first one asserts the schematic export was never called.
 *
 * The negative controls are the point of the batch, not decoration:
 *   - PCB + png: `getExportDocumentFile` called **0 times**, and the answer is
 *     marked `channel`/`evidenceGrade` = viewport with a freshness note;
 *   - PCB + svg / pdf / selection / project: refused by name, no data, no
 *     selection call, no schematic export;
 *   - missing / zero-byte / fake-PNG / timed-out captures: each its own named
 *     error, no `data` field, and the blob's `type` never taken as truth;
 *   - a `pageUuid` naming a PCB while a page is in front still branches;
 *   - an unknown target keeps the *old* path (the schematic export is called).
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import { createFacade } from '../dist/esm/facade.mjs';
import * as connector from '../dist/esm/index.mjs';

/** A real 1x1 PNG — signature included, so the check under test is satisfied. */
const PNG_1X1 = Buffer.from(
  '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    + '0000000a49444154789c6300010000050001',
  'hex',
);

const PCB_1 = '847fb91471c76cab';
const PCB_2 = '523016c3df10ea8d';
const PAGE_1 = '797f20b8a217b331';

function blobOf(buffer, type = 'image/png') {
  return {
    type,
    async arrayBuffer() {
      return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
    },
  };
}

/**
 * A host with both surfaces: the schematic export the old code used, and the
 * canvas capture the PCB branch needs. Everything is recorded, because most
 * assertions here are about what was **not** called.
 */
function host(overrides = {}) {
  const state = {
    // `test V4` in miniature: one schematic page plus two PCBs.
    documents: [
      { uuid: PAGE_1, name: 'P43', type: 'page' },
      { uuid: PCB_1, name: 'PCB1', type: 'pcb' },
      { uuid: PCB_2, name: 'PCB2', type: 'pcb' },
    ],
    activeDocument: PAGE_1,
    // `EDMT_EditorDocumentType`: 1 = SCHEMATIC_PAGE, 3 = PCB.
    activeType: 1,
    editorCalls: [],
    mfgCalls: [],
    captureCalls: [],
    zoomCalls: 0,
    selectCalls: [],
    capture: () => blobOf(PNG_1X1),
    ...(overrides.state ?? {}),
  };

  const typeOf = (uuid) => {
    const row = state.documents.find((doc) => doc.uuid === uuid);
    if (!row) return 5; // an unnamed document kind: PROJECT
    return row.type === 'pcb' ? 3 : 1;
  };

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
    sys_Environment: { getEditorCurrentVersion: () => '4.1.93' },
    sys_Storage: {
      getExtensionUserConfig: () => undefined,
      setExtensionUserConfig: async () => true,
    },
    sys_Dialog: { showInformationMessage() {} },

    // The schematic document export — every PCB assertion below is partly about
    // this namespace staying unused.
    sch_ManufactureData: {
      async getExportDocumentFile(fileName, fileType, typeParams, object) {
        state.mfgCalls.push({ fileName, fileType, typeParams, object });
        return blobOf(PNG_1X1);
      },
    },

    sch_SelectControl: {
      async doSelectPrimitives(ids) {
        state.selectCalls.push([...ids]);
        return true;
      },
    },

    dmt_Schematic: {
      async getCurrentSchematicPageInfo() {
        const row = state.documents.find((doc) => doc.uuid === state.activeDocument);
        return row && row.type !== 'pcb' ? { uuid: row.uuid } : undefined;
      },
      async getAllSchematicsInfo() {
        return state.documents
          .filter((doc) => doc.type === 'schematic')
          .map(({ uuid, name }) => ({ uuid, name }));
      },
      async getAllSchematicPagesInfo() {
        return state.documents
          .filter((doc) => doc.type === 'page')
          .map(({ uuid, name }) => ({ uuid, name, parentSchematicUuid: 'sch-1' }));
      },
    },

    dmt_Pcb: {
      async getAllPcbsInfo() {
        state.pcbListCalls = (state.pcbListCalls ?? 0) + 1;
        return state.documents
          .filter((doc) => doc.type === 'pcb')
          .map(({ uuid, name }) => ({ uuid, name }));
      },
    },

    dmt_SelectControl: {
      async getCurrentDocumentInfo() {
        state.editorCalls.push(['getCurrentDocumentInfo']);
        if (!state.activeDocument) return undefined;
        const uuid = state.activeDocument;
        return {
          uuid,
          documentType: state.activeType,
          tabId: `tab-${uuid}`,
          parentProjectUuid: 'proj-1',
        };
      },
    },

    dmt_EditorControl: {
      async openDocument(uuid) {
        state.editorCalls.push(['openDocument', uuid]);
        return `tab-${uuid}`;
      },
      async activateDocument(tabId) {
        state.editorCalls.push(['activateDocument', tabId]);
        if (state.activateIsLying) return true; // claims success, does not switch
        const uuid = tabId.replace(/^tab-/, '');
        state.activeDocument = uuid;
        // `activateAsSchematic` models the readback drift the confirmation read
        // exists for: the tab switches, the kind it reports does not match the
        // kind `doc.list` gave for that uuid.
        state.activeType = state.activateAsSchematic ? 1 : typeOf(uuid);
        return true;
      },
      async zoomToAllPrimitives() {
        state.zoomCalls += 1;
        state.editorCalls.push(['zoomToAllPrimitives']);
        return true;
      },
      async getCurrentRenderedAreaImage(...args) {
        state.captureCalls.push(args);
        state.editorCalls.push(['getCurrentRenderedAreaImage', ...args]);
        return state.capture();
      },
    },

    __state: state,
  };
  for (const [key, value] of Object.entries(overrides.namespaces ?? {})) {
    if (value === null) delete hostObject[key];
    else hostObject[key] = value;
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

/** A host whose front document is a PCB — the ordinary case for this batch. */
function pcbHost(overrides = {}) {
  return host({
    ...overrides,
    state: { activeDocument: PCB_1, activeType: 3, ...(overrides.state ?? {}) },
  });
}

// --------------------------------------------------------------------------
// the branch itself
// --------------------------------------------------------------------------

test('export.render on a PCB captures the viewport and never calls the schematic export', async (t) => {
  const h = pcbHost();
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, true, JSON.stringify(frame.error ?? {}));
  assert.deepEqual(h.__state.mfgCalls, [],
    'sch_ManufactureData.getExportDocumentFile must be called 0 times on a PCB');
  // The channel is named, so a consumer can tell a viewport from a document render.
  assert.equal(frame.data.channel, 'viewport');
  assert.equal(frame.data.evidenceGrade, 'viewport');
  assert.equal(frame.data.format, 'image/png');
  assert.equal(frame.data.encoding, 'base64');
  assert.equal(frame.data.scope, 'page');
  assert.equal(frame.data.bytes, PNG_1X1.byteLength);
  assert.match(frame.data.data, /^iVBOR/, 'PNG magic in base64');
  assert.equal(frame.data.activatedPageUuid, PCB_1);
  assert.equal(frame.data.activated, true);
  assert.match(frame.data.note, /NOT a document render/);
  assert.match(frame.data.note, /freshness/);
  assert.equal('bboxes' in frame.data, false, 'a capture is not geometry');
  // Activation before capture, and the zoom that frames the whole board.
  assert.deepEqual(
    h.__state.editorCalls.filter(([name]) => name !== 'getCurrentDocumentInfo'),
    [
      ['openDocument', PCB_1],
      ['activateDocument', `tab-${PCB_1}`],
      ['zoomToAllPrimitives'],
      ['getCurrentRenderedAreaImage', `tab-${PCB_1}`],
    ],
  );
});

test('export.render passes the activated tab id to the capture and zooms first', async (t) => {
  const h = pcbHost();
  withEda(t, h);
  await connector.activate();

  await call(h, 'export.render', { pageUuid: PCB_2 });

  assert.equal(h.__state.zoomCalls, 1, 'zoomToAllPrimitives runs once, before the capture');
  assert.deepEqual(h.__state.captureCalls, [[`tab-${PCB_2}`]],
    'the tab id the activation produced is what the capture is asked for');
});

test('a pageUuid naming a PCB branches even when a schematic page is in front', async (t) => {
  // The `doc.list` half of "confirmed target": the uuid's own row says pcb.
  const h = host();
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', { pageUuid: PCB_2, format: 'png' });

  assert.equal(frame.ok, true, JSON.stringify(frame.error ?? {}));
  assert.equal(frame.data.channel, 'viewport');
  assert.equal(frame.data.activatedPageUuid, PCB_2);
  assert.deepEqual(h.__state.mfgCalls, []);
  assert.ok(h.__state.pcbListCalls >= 1, 'the kind came from the doc.list read');
});

test('export.render refuses a page it cannot confirm as the active PCB, and captures nothing', async (t) => {
  // Two ways to be unconfirmed, and the batch needs both: the activation itself
  // can fail to bring the page in front (033/034's refusal, from `doc.open`), and
  // — the case only this branch can see — the page can come to the front while
  // the kind it reports is not the kind `doc.list` gave. Either way a capture
  // taken now would be a picture of an unconfirmed document.
  const lies = pcbHost({ state: { activateIsLying: true } });
  lies.__state.activeDocument = PAGE_1;
  withEda(t, lies);
  await connector.activate();

  const notActive = await call(lies, 'export.render', { pageUuid: PCB_1 });
  assert.equal(notActive.ok, false);
  assert.equal(notActive.error.code, 'CONNECTOR_ERROR');
  assert.match(notActive.error.message, /The export was NOT attempted/);
  assert.deepEqual(lies.__state.captureCalls, []);

  const drifts = pcbHost({ state: { activateAsSchematic: true } });
  withEda(t, drifts);
  await connector.activate();

  const frame = await call(drifts, 'export.render', { pageUuid: PCB_1 });
  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /could not confirm PCB/);
  assert.match(frame.error.message, /No capture was taken/);
  assert.deepEqual(drifts.__state.captureCalls, [], 'a picture of an unconfirmed page is not evidence');
  assert.deepEqual(drifts.__state.mfgCalls, []);
});

// --------------------------------------------------------------------------
// named refusals: the four requests the viewport channel cannot answer
// --------------------------------------------------------------------------

for (const format of ['svg', 'pdf']) {
  test(`export.render on a PCB refuses format=${format} by name`, async (t) => {
    const h = pcbHost();
    withEda(t, h);
    await connector.activate();

    const frame = await call(h, 'export.render', { format });

    assert.equal(frame.ok, false);
    assert.equal(frame.error.code, 'NOT_IMPLEMENTED');
    assert.match(frame.error.message, new RegExp(`format=${format}`));
    assert.match(frame.error.message, /only format=png/);
    assert.match(frame.error.message, /No export was attempted/);
    assert.equal(frame.data, undefined, 'a refusal has no data');
    assert.deepEqual(h.__state.mfgCalls, [], 'and does not fall back to the hanging channel');
    assert.deepEqual(h.__state.captureCalls, []);
  });
}

for (const scope of ['selection', 'project']) {
  test(`export.render on a PCB refuses scope=${scope} by name`, async (t) => {
    const h = pcbHost();
    withEda(t, h);
    await connector.activate();

    const frame = await call(h, 'export.render', {
      scope,
      ...(scope === 'selection' ? { ids: ['p1'] } : {}),
    });

    assert.equal(frame.ok, false);
    assert.equal(frame.error.code, 'NOT_IMPLEMENTED');
    assert.match(frame.error.message, new RegExp(`scope=${scope}`));
    assert.match(frame.error.message, /only scope=page/);
    assert.equal(frame.data, undefined);
    assert.deepEqual(h.__state.selectCalls, [], 'the PCB never selects primitives');
    assert.deepEqual(h.__state.mfgCalls, []);
    assert.deepEqual(h.__state.captureCalls, []);
  });
}

test('export.render still rejects an unknown format on a PCB as BAD_REQUEST', async (t) => {
  // The vocabulary check is the caller's error, not a missing capability.
  const h = pcbHost();
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', { format: 'bmp' });

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'BAD_REQUEST');
  assert.match(frame.error.message, /format/);
  assert.deepEqual(h.__state.captureCalls, [], 'no host call on a rejected param');
});

// --------------------------------------------------------------------------
// negative controls: what a *bad* capture must not become an image
// --------------------------------------------------------------------------

test('a PCB capture that returns no blob is a named failure, not an empty board', async (t) => {
  const h = pcbHost({ state: { capture: () => undefined } });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /returned no image/);
  assert.equal(frame.data, undefined);
  assert.deepEqual(h.__state.mfgCalls, []);
});

test('a zero-byte PCB capture is reported as bytes: 0', async (t) => {
  // Never "an empty board": 087f's PCB2 was an empty *board* and still came
  // back as 93840 bytes of grid and frame.
  const h = pcbHost({ state: { capture: () => blobOf(Buffer.alloc(0)) } });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /empty \(0 bytes\)/);
  assert.equal(frame.error.detail.bytes, 0);
  assert.equal(frame.data, undefined);
});

test('a fake PNG is refused on its signature, not on blob.type', async (t) => {
  // The blob *claims* image/png; the bytes are a JSON error page. `blob.type` is
  // a claim, so it is never what the check reads — and it is quoted back in the
  // message so the lie is visible.
  const h = pcbHost({
    state: {
      capture: () => blobOf(Buffer.from('{"error":"no canvas"}', 'utf8'), 'image/png'),
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /is not a PNG/);
  assert.match(frame.error.message, /blob\.type said "image\/png"/);
  assert.match(frame.error.message, /7b 22 65 72/, 'the bytes actually seen are named');
  assert.equal(frame.error.detail.blobType, 'image/png');
  assert.equal(frame.data, undefined, 'the bytes are not passed on as an image');
});

test('a truncated PNG header is refused too', async (t) => {
  const h = pcbHost({ state: { capture: () => blobOf(Buffer.from('89504e47', 'hex')) } });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /is not a PNG/);
});

test('a PCB capture that never settles answers TIMEOUT and captures nothing usable', async (t) => {
  const h = pcbHost({ state: { capture: () => new Promise(() => {}) } });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', { timeoutMs: 1_000 });

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'TIMEOUT');
  assert.match(frame.error.message, /within 1 s/, 'the clamped deadline is what the text says');
  assert.match(frame.error.message, /treat the picture as absent/);
  assert.match(frame.error.message, /do NOT fall back/, 'the hanging channel is named as forbidden');
  assert.equal(frame.data, undefined);
  assert.equal(frame.error.detail.path, 'dmt_EditorControl.getCurrentRenderedAreaImage');
  assert.equal(frame.error.detail.pageUuid, PCB_1);
  assert.deepEqual(h.__state.mfgCalls, []);
});

test('a PCB capture whose arrayBuffer throws is a named read failure', async (t) => {
  const h = pcbHost({
    state: {
      capture: () => ({
        type: 'image/png',
        async arrayBuffer() {
          throw new Error('blob detached');
        },
      }),
    },
  });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'CONNECTOR_ERROR');
  assert.match(frame.error.message, /could not be read: blob detached/);
  assert.equal(frame.data, undefined);
});

// --------------------------------------------------------------------------
// missing host capabilities
// --------------------------------------------------------------------------

test('a PCB without zoomToAllPrimitives is NOT_IMPLEMENTED and captures nothing', async (t) => {
  const h = pcbHost();
  delete h.dmt_EditorControl.zoomToAllPrimitives;
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'NOT_IMPLEMENTED');
  assert.match(frame.error.message, /zoomToAllPrimitives/);
  assert.equal(frame.error.detail.path, 'dmt_EditorControl.zoomToAllPrimitives');
  assert.deepEqual(h.__state.captureCalls, []);
});

test('a PCB without getCurrentRenderedAreaImage is NOT_IMPLEMENTED', async (t) => {
  const h = pcbHost();
  delete h.dmt_EditorControl.getCurrentRenderedAreaImage;
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'NOT_IMPLEMENTED');
  assert.match(frame.error.message, /getCurrentRenderedAreaImage/);
  assert.deepEqual(h.__state.mfgCalls, [], 'the schematic export is not a fallback here');
});

// --------------------------------------------------------------------------
// the old path is untouched: unknown targets, and schematic targets
// --------------------------------------------------------------------------

test('an unknown target keeps the old path instead of guessing PCB', async (t) => {
  // A uuid that is in no document list and is not the active document: nothing
  // confirmed its kind, so the action must not route it anywhere new.
  const h = host();
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', { pageUuid: 'not-in-this-project' });

  assert.equal(frame.ok, true, JSON.stringify(frame.error ?? {}));
  assert.equal(h.__state.mfgCalls.length, 1, 'the schematic export still answers an unknown target');
  assert.equal(frame.data.channel, 'document', 'and the answer claims the document channel only');
  assert.deepEqual(h.__state.captureCalls, []);
});

test('an unnamed document type keeps the old path', async (t) => {
  // 5 = PROJECT / a symbol editor: a document, but not one this action can name.
  const h = host({ state: { activeDocument: 'doc-weird', activeType: 5 } });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, true, JSON.stringify(frame.error ?? {}));
  assert.equal(h.__state.mfgCalls.length, 1);
  assert.deepEqual(h.__state.captureCalls, []);
});

test('a schematic page still exports through the document render, unchanged', async (t) => {
  // The reverse consumer: CLI / draw / checkup call this on schematic pages and
  // depend on the object literals, the file type and the answer's shape.
  const h = host();
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', { pageUuid: PAGE_1, format: 'png' });

  assert.equal(frame.ok, true, JSON.stringify(frame.error ?? {}));
  assert.equal(h.__state.mfgCalls.length, 1);
  assert.equal(h.__state.mfgCalls[0].fileType, 'PNG');
  assert.equal(h.__state.mfgCalls[0].object, 'Current Page');
  assert.deepEqual(h.__state.mfgCalls[0].typeParams, { theme: 'Default', lineWidth: 'Default' });
  assert.equal(frame.data.format, 'image/png');
  assert.equal(frame.data.activatedPageUuid, PAGE_1);
  // #87②'s one addition to this path: the channel is named, so a consumer can
  // tell a document render from the PCB viewport without guessing. Every other
  // field is exactly what it was, and `evidenceGrade` is *not* added — the
  // document render is the grade the acceptance image has always had.
  assert.equal(frame.data.channel, 'document');
  assert.equal(frame.data.evidenceGrade, undefined);
  assert.deepEqual(h.__state.captureCalls, []);
});

test('the three schematic scopes still pass their real object literals', async (t) => {
  const h = host();
  withEda(t, h);
  await connector.activate();

  await call(h, 'export.render', { pageUuid: PAGE_1 });
  await call(h, 'export.render', { pageUuid: PAGE_1, scope: 'project' });
  await call(h, 'export.render', { pageUuid: PAGE_1, scope: 'selection', ids: ['p1', 'p2'] });

  assert.deepEqual(
    h.__state.mfgCalls.map((mfgCall) => mfgCall.object),
    ['Current Page', 'Project', 'Current Page Selected Items'],
  );
  assert.deepEqual(h.__state.selectCalls, [['p1', 'p2']], 'the schematic selection is unchanged');
  assert.deepEqual(h.__state.captureCalls, []);
});

// --------------------------------------------------------------------------
// the order the two paths ask their questions in (main-review pin, 2026-11-16)
// --------------------------------------------------------------------------

test('a schematic host without getExportDocumentFile still answers NOT_IMPLEMENTED for a bad format', async (t) => {
  // The schematic path's error precedence is **frozen**: it probes the host
  // capability first and reads the caller's parameters second, so a host that
  // has no `getExportDocumentFile` says NOT_IMPLEMENTED even when `format` is
  // nonsense. Hoisting the vocabulary check above the probe (the first cut of
  // this batch did) silently rewrote that answer to BAD_REQUEST.
  const h = host({ namespaces: { sch_ManufactureData: {} } });
  withEda(t, h);
  await connector.activate();

  const frame = await call(h, 'export.render', { format: 'bmp' });

  assert.equal(frame.ok, false);
  assert.equal(frame.error.code, 'NOT_IMPLEMENTED');
  assert.match(frame.error.message, /getExportDocumentFile/);
  assert.doesNotMatch(frame.error.message, /params\.format/);
  assert.equal(frame.error.detail.path, 'sch_ManufactureData.getExportDocumentFile');
});

test('a PCB renders through the viewport when the editor has no sch_ManufactureData at all', async (t) => {
  // The mirror image, and the reason the ordering has to branch rather than be
  // global: a PCB needs nothing from the schematic export namespace, so its
  // absence must not stop a PCB capture. (The PCB namespace probe would be the
  // wrong question to ask here — it is the *schematic* host API.)
  const h = pcbHost({ namespaces: { sch_ManufactureData: null } });
  withEda(t, h);
  await connector.activate();

  assert.equal('sch_ManufactureData' in h, false, 'the fake really has no such namespace');

  const frame = await call(h, 'export.render', {});

  assert.equal(frame.ok, true, JSON.stringify(frame.error ?? {}));
  assert.equal(frame.data.channel, 'viewport');
  assert.equal(frame.data.evidenceGrade, 'viewport');
  assert.equal(frame.data.format, 'image/png');
  assert.equal(frame.data.activatedPageUuid, PCB_1);
  assert.ok(frame.data.bytes > 0);
  assert.match(frame.data.data, /^iVBOR/);
});
