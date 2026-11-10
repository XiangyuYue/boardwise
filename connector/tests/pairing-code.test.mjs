/**
 * 549 — the connector's public pair code, and the handshake that offers it.
 *
 * The daemon used to trust whoever arrived first with an `https://client` Origin.
 * EDA 4.1.71 reports `https://pro.lceda.cn` instead, so a real editor could not
 * pair at all, and the Origin header was never a trust boundary in the first
 * place. It is now an **explicit authorisation**: the connector shows an 8-
 * character public code, the user runs `boardwise bridge pair <CODE>` on the
 * daemon host, and the daemon accepts a pairing write only while that grant
 * matches the code the handshake carries.
 *
 * What that makes load-bearing on this side, and what this file pins:
 *
 * 1. the code comes from the platform CSPRNG or not at all (no `Math.random`,
 *    no silent downgrade) — a guessable code would authorise the wrong connector;
 * 2. it lives under its own storage key, stable across reconnects, replaced by an
 *    explicit re-pair, and still stable in-process when the store refuses it;
 * 3. `hello` carries it optionally — absent when there is none, never a blank
 *    string, and never required to *re*connect with a token that already pairs;
 * 4. the refusal guidance names `boardwise bridge pair`, not `bridge revoke`,
 *    while a daemon that predates the field keeps the advice it can act on.
 *
 * Nothing here is a claim about the real editor: the code path is exercised
 * against stand-in hosts, and `https://pro.lceda.cn` has not been re-measured.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

import {
  PAIR_CODE_ALPHABET,
  PAIR_CODE_LENGTH,
  formatPairCode,
  generatePairCode,
} from '../dist/esm/random.mjs';
import {
  ensureConnectorConfig,
  forgetPairCode,
  normalisePairCode,
  resolveConfig,
} from '../dist/esm/config.mjs';
import { createFacade } from '../dist/esm/facade.mjs';
import * as connector from '../dist/esm/index.mjs';
import { Transport } from '../dist/esm/transport.mjs';

const CODE_SHAPE = new RegExp(`^[${PAIR_CODE_ALPHABET}]{${PAIR_CODE_LENGTH}}$`);

/**
 * A stand-in Web Crypto that fills the buffer deterministically — with a
 * *different* value in every slot.
 *
 * Varying on purpose: `generatePairCode` now rejects a constant fill (see the
 * "identical bytes" test below), because a source that hands back one repeated
 * value cannot be a CSPRNG and would mint a code a guesser finds first try. A
 * fixture that filled a constant would be testing the rejection path in every
 * other test.
 */
function fakeCrypto(seed, calls = []) {
  return {
    getRandomValues: (array) => {
      calls.push(array.length);
      for (let i = 0; i < array.length; i += 1) array[i] = (seed + i) & 0xff;
      return array;
    },
  };
}

/** A storage backed by a plain object, recording every write. */
function storage(entries = {}) {
  const written = [];
  return {
    written,
    entries,
    getExtensionUserConfig: (key) => entries[key],
    setExtensionUserConfig: async (key, value) => {
      entries[key] = value;
      written.push([key, value]);
      return true;
    },
  };
}

// --------------------------------------------------------------------------
// minting: Web Crypto or nothing
// --------------------------------------------------------------------------

test('the pair code is eight characters from the unambiguous alphabet', () => {
  const calls = [];
  const generated = generatePairCode({ crypto: fakeCrypto(0x1b, calls) });

  assert.equal(generated.source, 'webcrypto');
  assert.equal(generated.pairCode.length, PAIR_CODE_LENGTH);
  assert.match(generated.pairCode, CODE_SHAPE);
  // Two calls: `describeRandomHost` probes with one byte, the mint draws eight.
  assert.deepEqual(calls, [1, PAIR_CODE_LENGTH], 'one probe, one draw — no retry loop');
});

test('the alphabet drops the four characters a human reads back wrong', () => {
  assert.equal(PAIR_CODE_ALPHABET.length, 32, 'five bits per character, no modulo bias');
  assert.equal(new Set(PAIR_CODE_ALPHABET).size, PAIR_CODE_ALPHABET.length);
  for (const ambiguous of ['I', 'L', 'O', 'U']) {
    assert.ok(
      !PAIR_CODE_ALPHABET.includes(ambiguous),
      `${ambiguous} is read back wrong and must not be in the alphabet`,
    );
  }
});

test('each byte contributes exactly five bits, with no rejection sampling', () => {
  // 256 is a multiple of 32, so `byte & 31` is uniform. Both ends of the byte
  // range are pinned here: a modulo would still land on them, but a retry loop
  // or a 6-bit mask would not produce these exact characters.
  assert.equal(
    generatePairCode({ crypto: fakeCrypto(0x00) }).pairCode,
    '01234567',
    'the low end of the range, one per slot',
  );
  assert.equal(
    generatePairCode({ crypto: fakeCrypto(0xff) }).pairCode,
    `Z${PAIR_CODE_ALPHABET[0]}${PAIR_CODE_ALPHABET[1]}${PAIR_CODE_ALPHABET[2]}`
      + `${PAIR_CODE_ALPHABET[3]}${PAIR_CODE_ALPHABET[4]}${PAIR_CODE_ALPHABET[5]}`
      + `${PAIR_CODE_ALPHABET[6]}`,
    '0xff & 31 = 31, and the range wraps on the next slot',
  );
  assert.equal(
    generatePairCode({ crypto: fakeCrypto(0x21) }).pairCode,
    '12345678',
    '0x21 & 31 = 1: five bits kept, the upper three dropped',
  );
});

test('a getRandomValues that yields no entropy is refused, not turned into a code', () => {
  // Three shapes of "the call worked, the bytes are not random". Each one would
  // otherwise mint a code that is identical every time — an authorisation anyone
  // who has read this file can reproduce.
  const silent = {
    // The real stub shape: returns its argument, writes nothing, and the buffer
    // keeps the zeros `new Uint8Array` starts with.
    getRandomValues: (array) => array,
  };
  const zeroed = generatePairCode({ crypto: silent });
  assert.equal(zeroed.pairCode, '', 'an unfilled buffer is not eight zero characters');
  assert.equal(zeroed.source, 'none');
  assert.match(zeroed.detail, /getRandomValues=zeros/);

  const allZero = generatePairCode({
    crypto: { getRandomValues: (array) => { array.fill(0); return array; } },
  });
  assert.equal(allZero.pairCode, '');
  assert.equal(allZero.source, 'none');
  assert.match(allZero.detail, /getRandomValues=zeros/);

  const constant = generatePairCode({
    crypto: { getRandomValues: (array) => { array.fill(0xff); return array; } },
  });
  assert.equal(constant.pairCode, '', 'eight identical bytes is not a draw');
  assert.equal(constant.source, 'none');
  assert.match(constant.detail, /getRandomValues=constant/);

  // And nothing weaker is consulted on the way out: the fallback does not exist
  // for this value, so a refusal here has to stay a refusal.
  const refused = generatePairCode({
    crypto: silent,
    mathRandom: () => {
      throw new Error('the pair code must never come from Math.random');
    },
  });
  assert.equal(refused.pairCode, '');
});

test('display groups the code as two fours; the bare form is what is sent', () => {
  assert.equal(formatPairCode('ABCD1234'), 'ABCD-1234');
  // The daemon normalises the same separators, so the two forms are one code.
  assert.equal(normalisePairCode('ABCD-1234'), 'ABCD1234');
  assert.equal(normalisePairCode(' abcd 1234 '), 'ABCD1234');
  assert.equal(normalisePairCode('abcd_1234'), 'ABCD1234');
  // Unicode whitespace too: a code pasted out of a web page carries U+00A0
  // between the groups, and the daemon folds the same (str.isspace) — a
  // narrower set here would make the editor show a code the CLI refuses.
  assert.equal(normalisePairCode('abcd\u00a01234'), 'ABCD1234');
  assert.equal(normalisePairCode('\u3000ABCD-1234\u00a0'), 'ABCD1234');
  // Not a code at all: handed back untouched rather than sliced into a shape.
  assert.equal(formatPairCode('ABC'), 'ABC');
  assert.equal(normalisePairCode('ABC'), '');
  assert.equal(normalisePairCode('ABCD123I'), '', 'I is not in the alphabet');
  assert.equal(normalisePairCode(undefined), '');
  assert.equal(normalisePairCode(12345678), '');
});

test('no CSPRNG means no pair code, and Math.random is never consulted', () => {
  // The fallback is what makes the *token* work on the real editor; for the pair
  // code it would be a security downgrade dressed as availability. The
  // `mathRandom` here throws, so a fallback would be visible as an exception.
  const generated = generatePairCode({
    crypto: undefined,
    mathRandom: () => {
      throw new Error('the pair code must never come from Math.random');
    },
  });

  assert.equal(generated.pairCode, '');
  assert.equal(generated.source, 'none');
  assert.equal(generated.detail, 'crypto=unavailable');
});

test('a getRandomValues that throws fails closed instead of weakening', () => {
  const generated = generatePairCode({
    crypto: {
      getRandomValues: () => {
        throw new TypeError('not allowed in this realm');
      },
    },
    mathRandom: () => 0.5,
  });

  assert.equal(generated.pairCode, '', 'a throwing CSPRNG is "no source", not "weak source"');
  assert.equal(generated.source, 'none');
  assert.match(generated.detail, /threw TypeError/);
});

test('two minted codes differ, and none of them leaks the host diagnosis', () => {
  const first = generatePairCode();
  const second = generatePairCode();
  assert.notEqual(first.pairCode, second.pairCode, 'a repeated code is not an authorisation');
  assert.match(first.detail, /^crypto=/, 'the diagnosis names the host, not a guess');
  assert.ok(
    !first.detail.includes(first.pairCode),
    'the diagnosis goes into the log panel; it must not carry the code',
  );
});

// --------------------------------------------------------------------------
// storage: its own key, stable, replaced only by an explicit re-pair
// --------------------------------------------------------------------------

test('the pair code is stored under its own key, beside an untouched legacy token', async () => {
  forgetPairCode();
  const store = storage({ token: 'c'.repeat(64) }); // a 0.2.2 bare-hex token

  const config = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x07) });

  assert.match(config.pairCode, CODE_SHAPE);
  assert.equal(config.pairCodeSource, 'generated');
  assert.deepEqual(store.written, [['pairCode', config.pairCode]]);
  // The old token still decodes, value and view: adding a key must not disturb
  // the format an earlier build wrote.
  assert.equal(config.token, 'c'.repeat(64));
  assert.equal(resolveConfig(store).token, 'c'.repeat(64));
});

test('a reload reads the stored code back, and does not write again', async () => {
  forgetPairCode();
  const store = storage();
  const first = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x12) });

  // Same process: the resolver answers from the store, so the About box and the
  // `hello` frame agree no matter which one is asked.
  const fromStore = resolveConfig(store);
  assert.equal(fromStore.pairCode, first.pairCode);
  assert.equal(fromStore.pairCodeSource, 'storage');

  // A reconnect (or a reload of the extension) must reuse it: a code that moved
  // on every attempt would invalidate the grant between reading it and pairing.
  const writesBefore = store.written.length;
  const again = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x99) });
  assert.equal(again.pairCode, first.pairCode);
  assert.equal(store.written.length, writesBefore, 'nothing to rewrite');
});

test('a hand-typed or hyphenated stored value is folded to the one spelling', async () => {
  const store = storage({ pairCode: 'abcd-1234' });
  const config = resolveConfig(store);
  assert.equal(config.pairCode, 'ABCD1234');
  assert.equal(config.pairCodeSource, 'storage');

  // A stored value that is not a code is treated as absent, never as valid —
  // so the answer must come from nothing at all, which is why the in-process
  // copy is cleared first.
  forgetPairCode();
  assert.equal(resolveConfig(storage({ pairCode: 'nope' })).pairCode, '');
  assert.equal(resolveConfig(storage({ pairCode: 'IIIIIIII' })).pairCode, '');
});

test('a store that refuses the code still leaves this process with one, and says so', async () => {
  forgetPairCode();
  const store = storage();
  store.setExtensionUserConfig = async () => false;

  const config = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x05) });
  assert.match(config.pairCode, CODE_SHAPE, 'shown anyway: the user has to be able to authorise it');
  assert.match(config.pairCodeNote, /refused to store the pair code/);

  // Stable for the rest of the process — the whole reason the code is cached.
  const later = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x2a) });
  assert.equal(later.pairCode, config.pairCode);
  // ...and `resolveConfig`, which is what the About box reads, sees the same one.
  const box = resolveConfig(store);
  assert.equal(box.pairCode, config.pairCode);
  assert.match(box.pairCodeNote, /refused to store the pair code/);
});

test('a store that throws is the same story: stable in-process, disclosed', async () => {
  forgetPairCode();
  const store = storage();
  store.setExtensionUserConfig = async () => {
    throw new Error('storage is full');
  };

  const config = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x31) });
  assert.match(config.pairCode, CODE_SHAPE);
  assert.match(config.pairCodeNote, /storing the pair code threw/);
  assert.equal((await ensureConnectorConfig(store, { crypto: fakeCrypto(0x32) })).pairCode, config.pairCode);
});

test('no CSPRNG: the code is absent and the config says a first pairing cannot be completed', async () => {
  forgetPairCode();
  const store = storage();
  const config = await ensureConnectorConfig(store, { crypto: undefined });

  assert.equal(config.pairCode, '');
  assert.equal(config.pairCodeSource, 'missing');
  assert.match(config.pairCodeNote, /no secure random source/);
  assert.match(config.pairCodeNote, /first pairing cannot be completed/);
  assert.match(config.pairCodeNote, /crypto=unavailable/, 'and the host detail, not just a verdict');
  // The token still exists (its own, weaker fallback): an existing pairing has
  // to keep reconnecting on a host with no CSPRNG.
  assert.equal(config.token.length, 64);
});

test('an explicit re-pair replaces both values, and only then', async () => {
  forgetPairCode();
  const store = storage();
  const first = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x0f) });

  // What `rePair` does: clear both keys, forget the in-process code, mint again.
  await store.setExtensionUserConfig('token', '');
  await store.setExtensionUserConfig('pairCode', '');
  forgetPairCode();
  const second = await ensureConnectorConfig(store, { crypto: fakeCrypto(0x10) });

  assert.notEqual(second.pairCode, first.pairCode, 'a re-pair has to change the code');
  assert.notEqual(second.token, first.token, 'and the token with it');
  assert.equal(store.entries.pairCode, second.pairCode);
  assert.equal(resolveConfig(store).pairCode, second.pairCode);
});

// --------------------------------------------------------------------------
// the wire: `hello.pairCode` is optional in both directions
// --------------------------------------------------------------------------

class FakeSocket {
  constructor() {
    this.registered = [];
    this.sent = [];
    this.closed = [];
  }

  register(id, uri, onMessage, onConnected) {
    this.registered.push({ id, uri });
    this.onMessage = onMessage;
    this.onConnected = onConnected;
  }

  send(id, data) {
    this.sent.push({ id, frame: JSON.parse(data) });
  }

  close(id) {
    this.closed.push(id);
  }

  connect() {
    this.onConnected?.();
  }

  async deliver(frame) {
    await this.onMessage?.({ data: JSON.stringify(frame) });
    // The hello a banner triggers is not on the wire the moment `deliver`
    // returns: it first reads this window's project (021 §2.3), so it goes out a
    // few microtasks later. One macrotask turn drains that chain.
    await new Promise((resolve) => setImmediate(resolve));
  }

  lastFrame() {
    return this.sent[this.sent.length - 1]?.frame;
  }

  frame(action) {
    return this.sent.find((entry) => entry.frame.action === action)?.frame;
  }

  /** Every frame of one kind, oldest first — a reconnect sends a second hello. */
  frames(action) {
    return this.sent.filter((entry) => entry.frame.action === action).map((entry) => entry.frame);
  }
}

function makeTransport(socket, overrides = {}) {
  return new Transport({
    url: 'ws://127.0.0.1:61190/eda',
    token: 'tok',
    socket,
    minBackoffMs: 5,
    maxBackoffMs: 20,
    heartbeatMs: 50,
    onRequest: async () => ({}),
    ...overrides,
  });
}

test('hello carries the pair code, and omits the field when there is none', async () => {
  const withCode = new FakeSocket();
  const transport = makeTransport(withCode, { pairCode: 'ABCD1234' });
  await transport.start();
  withCode.connect();
  assert.equal(withCode.lastFrame().params.pairCode, 'ABCD1234');
  transport.stop();

  // No code (no CSPRNG): the field is absent, not empty. A blank string would be
  // a code that happens to be blank; absence is the fact.
  const bare = new FakeSocket();
  const without = makeTransport(bare);
  await without.start();
  bare.connect();
  assert.equal('pairCode' in bare.lastFrame().params, false);
  without.stop();
});

test('a configured code never stops a reconnect that already holds the token', async () => {
  // The daemon lets a connector presenting the paired token straight through
  // (549), whatever the grant says — so the transport must not gate `hello` on
  // the code, and an *empty* value must not become a refusal here either.
  const socket = new FakeSocket();
  const transport = makeTransport(socket, { pairCode: '' });
  await transport.start();
  socket.connect();

  const hello = socket.lastFrame();
  assert.equal(hello.action, 'hello');
  assert.equal(hello.params.token, 'tok');
  assert.equal('pairCode' in hello.params, false);
  transport.stop();
});

test('the daemon\'s refusal detail reaches the caller', async () => {
  const socket = new FakeSocket();
  const refusals = [];
  const transport = makeTransport(socket, {
    onHandshakeRefused: (refusal) => refusals.push(refusal),
  });
  await transport.start();
  socket.connect();

  await socket.deliver({
    id: null,
    ok: false,
    error: {
      code: 'UNAUTHENTICATED',
      message: 'no pairing authorisation is active',
      detail: { pairCodeRequired: true, reason: 'no-grant' },
    },
  });

  assert.equal(refusals.length, 1, 'a refusal is reported, never dropped');
  assert.equal(refusals[0].code, 'UNAUTHENTICATED');
  assert.deepEqual(refusals[0].detail, { pairCodeRequired: true, reason: 'no-grant' });
  assert.equal(transport.state, 'stopped', 'and the socket is not retried into a loop');
});

test('a refusal with no detail leaves the field absent, not invented', async () => {
  const socket = new FakeSocket();
  const refusals = [];
  const transport = makeTransport(socket, {
    onHandshakeRefused: (refusal) => refusals.push(refusal),
  });
  await transport.start();
  socket.connect();

  await socket.deliver({
    id: null,
    ok: false,
    error: { code: 'UNAUTHENTICATED', message: 'bad or missing token' },
  });

  // A daemon that predates 549 looks exactly like this, and the caller has to be
  // able to tell it apart from `pairCodeRequired`.
  assert.equal('detail' in refusals[0], false);
});

// --------------------------------------------------------------------------
// the extension wiring: About…, re-pair, and the guidance a user acts on
// --------------------------------------------------------------------------

const BANNER = {
  event: 'banner',
  data: { server: 'boardwise', protocol: '1.0', expect: 'hello' },
};

function fakeHost(stored = {}, random) {
  const socket = new FakeSocket();
  const logs = [];
  const toasts = [];
  const dialogs = [];
  const written = [];
  const host = {
    sys_WebSocket: socket,
    sys_Log: { add: (line) => logs.push(line) },
    sys_Message: { showToastMessage: (message) => toasts.push(message) },
    sys_Environment: { getEditorCurrentVersion: () => '3.2.149.88089769' },
    ...(random ? { random } : {}),
    sys_Storage: {
      getExtensionUserConfig: (key) => stored[key],
      setExtensionUserConfig: async (key, value) => {
        stored[key] = value;
        written.push([key, value]);
        return true;
      },
    },
    sys_Dialog: {
      showInformationMessage: (message, title) => dialogs.push({ message, title }),
    },
  };
  return { host, socket, logs, toasts, dialogs, written, stored };
}

function withHost(t, stored = {}, random) {
  const parts = fakeHost(stored, random);
  connector.__setFacadeForTests(createFacade(parts.host));
  t.after(() => {
    connector.deactivate();
    connector.__setFacadeForTests(undefined);
  });
  return parts;
}

test('the hello that answers the banner carries the same code About… shows', async (t) => {
  const { socket, dialogs } = withHost(t);
  await connector.activate();
  await socket.deliver(BANNER);

  const hello = socket.frame('hello');
  assert.ok(hello, 'the banner must still trigger hello');
  assert.match(hello.params.pairCode, CODE_SHAPE, 'the public code goes out with the handshake');

  connector.about();
  const text = dialogs.at(-1).message;
  assert.match(text, new RegExp(`pair code: ${hello.params.pairCode.slice(0, 4)}-`));
  assert.ok(
    text.includes(`bridge pair ${formatPairCode(hello.params.pairCode)}`),
    `the box has to name the command that authorises the code: ${text}`,
  );
  // The token is still never displayed — not even a prefix of it.
  assert.ok(!text.includes(hello.params.token), `the box leaked the token: ${text}`);
  assert.ok(!text.includes(hello.params.token.slice(0, 16)), 'nor a prefix of it');
});

test('About… says a first pairing is impossible when the host has no CSPRNG', async (t) => {
  const { socket, logs, dialogs } = withHost(t, {}, { crypto: undefined });
  await connector.activate();
  await socket.deliver(BANNER);

  assert.equal('pairCode' in socket.frame('hello').params, false, 'no field to offer');

  connector.about();
  const text = dialogs.at(-1).message;
  assert.match(text, /pair code: NONE — no secure random source/);
  assert.match(text, /first pairing cannot be completed/);
  // Said in the log too, and said as *not* a network fault: the token still
  // works, so a silent absence would read as "the daemon is down".
  assert.ok(
    logs.some((line) => /no pair code — no secure random source/.test(line)),
    `the log panel must say it: ${JSON.stringify(logs)}`,
  );
  assert.ok(
    logs.some((line) => /not a connection failure/.test(line)),
    'and must not let it be read as one',
  );
});

test('a pairing refusal points at `bridge pair` with our code, not at `revoke`', async (t) => {
  const { socket, logs, dialogs } = withHost(t);
  await connector.activate();
  await socket.deliver(BANNER);
  const code = formatPairCode(socket.frame('hello').params.pairCode);

  await socket.deliver({
    id: null,
    ok: false,
    error: {
      code: 'UNAUTHENTICATED',
      message: 'no pairing authorisation is active',
      detail: { pairCodeRequired: true, reason: 'no-grant' },
    },
  });

  const status = connector.getStatus();
  assert.equal(status.paired, false);
  assert.equal(status.refusedCode, 'UNAUTHENTICATED');
  assert.equal(status.refusedPairCodeReason, 'no-grant');
  assert.match(status.lastError, new RegExp(`boardwise bridge pair ${code}`));
  assert.doesNotMatch(status.lastError, /revoke/, 'revoke does not authorise anything (549)');

  connector.about();
  const text = dialogs.at(-1).message;
  assert.match(text, /REFUSED — the daemon needs an explicit authorisation/);
  assert.ok(logs.some((line) => line.includes(`boardwise bridge pair ${code}`)));
});

test('a `code-missing` refusal is reported as this host\'s limit, not a network fault', async (t) => {
  const { socket, dialogs } = withHost(t, {}, { crypto: undefined });
  await connector.activate();
  await socket.deliver(BANNER);

  await socket.deliver({
    id: null,
    ok: false,
    error: {
      code: 'UNAUTHENTICATED',
      message: 'this connector sent no pairCode, so it cannot be authorised',
      detail: { pairCodeRequired: true, reason: 'code-missing' },
    },
  });

  const status = connector.getStatus();
  assert.equal(status.refusedPairCodeReason, 'code-missing');
  assert.match(status.lastError, /no pair code/);
  assert.match(status.lastError, /not a network fault/);
  assert.match(status.lastError, /existing pairing still reconnects/);

  connector.about();
  assert.match(dialogs.at(-1).message, /pair code: NONE — no secure random source/);
});

test('a refusal from a pre-549 daemon keeps the advice that daemon understands', async (t) => {
  const { socket, dialogs } = withHost(t);
  await connector.activate();
  await socket.deliver(BANNER);

  await socket.deliver({
    id: null,
    ok: false,
    error: { code: 'UNAUTHENTICATED', message: 'bad or missing token' },
  });

  const status = connector.getStatus();
  assert.equal(status.refusedPairCodeReason, undefined, 'no field was sent, so none is claimed');
  assert.match(status.lastError, /bridge revoke/);
  assert.match(
    status.lastError,
    /predates explicit pairing/,
    'and it must not describe `bridge pair` as supported there',
  );

  connector.about();
  assert.match(dialogs.at(-1).message, /run "boardwise bridge revoke"/);
});

test('another refusal code is not turned into pairing advice', async (t) => {
  const { socket } = withHost(t);
  await connector.activate();
  await socket.deliver(BANNER);

  await socket.deliver({
    id: 'hello',
    ok: false,
    error: { code: 'VERSION_MISMATCH', message: 'connector speaks 2.0, daemon speaks 1.0' },
  });

  const status = connector.getStatus();
  assert.equal(status.refusedCode, 'VERSION_MISMATCH');
  assert.equal(status.refusedPairCodeReason, undefined);
  // A version skew is answered by updating a build, never by pairing or revoking.
  assert.doesNotMatch(status.lastError, /bridge pair|bridge revoke/);
});

test('re-pair announces a new code and the command that authorises it', async (t) => {
  const { socket, toasts, written, stored } = withHost(t);
  await connector.activate();
  await socket.deliver(BANNER);
  const firstHello = socket.frames('hello').at(-1).params;
  const before = firstHello.pairCode;

  await connector.rePair();
  // The re-pair's own reconnect greets on the new socket; the banner is what the
  // daemon speaks first, so deliver it and read the *newest* hello.
  await socket.deliver(BANNER);
  const afterHello = socket.frames('hello').at(-1).params;

  const after = afterHello.pairCode;
  assert.ok(after, 'a re-pair mints the code before it reconnects — it has to be shown first');
  assert.notEqual(after, before, 'an explicit re-pair replaces the code');
  assert.equal(stored.pairCode, after, 'and stores the new one under its own key');
  assert.notEqual(afterHello.token, firstHello.token, 'the token is replaced with it');
  assert.equal(stored.token, `webcrypto:${afterHello.token}`);
  // minted on the first connect, cleared by the re-pair, minted again.
  assert.deepEqual(
    written.filter(([key]) => key === 'pairCode').map(([, value]) => value),
    [before, '', after],
  );

  const announcement = toasts.find((line) => /new pair code/.test(line)) ?? '';
  assert.match(announcement, new RegExp(`new pair code ${formatPairCode(after)}`));
  assert.match(announcement, new RegExp(`boardwise bridge pair ${formatPairCode(after)}`));
  assert.doesNotMatch(announcement, /revoke/, 'the old wording is retired');
});

// --------------------------------------------------------------------------
// rotation: a spent code is replaced, an unspent one is left alone (549)
// --------------------------------------------------------------------------

/** The `hello` answer the daemon sends, as the fields this module reads. */
function helloAnswer(data = {}) {
  return {
    id: 'hello',
    ok: true,
    data: { paired: true, fingerprint: 'abc123', ...data },
  };
}

test('a pairing write retires the code; an ordinary reconnect leaves it alone', async (t) => {
  const { socket, stored, logs, dialogs } = withHost(t);
  await connector.activate();
  await socket.deliver(BANNER);
  const before = socket.frame('hello').params.pairCode;
  assert.match(before, CODE_SHAPE);

  // 1) The daemon accepted the token this window already had: its early return
  // never consults a grant, so the code it carried was not spent. `false` here is
  // the whole reason the field exists — rotating on every reconnect would
  // invalidate the user's authorisation between reading the code and pairing.
  const noneBefore = connector.__pairCodeRotationForTests();
  await socket.deliver(helloAnswer({ pairCodeUsed: false }));
  assert.equal(
    connector.__pairCodeRotationForTests(),
    noneBefore,
    'no rotation was started: nothing was spent',
  );
  assert.equal(stored.pairCode, before, 'and therefore nothing to rewrite');

  // 2) `true`: this handshake is what wrote the pairing record.
  await socket.deliver(helloAnswer({ pairCodeUsed: true }));
  const rotation = connector.__pairCodeRotationForTests();
  assert.ok(rotation, 'a spent code is rotated');
  await rotation;

  const after = stored.pairCode;
  assert.match(after, CODE_SHAPE);
  assert.notEqual(after, before, 'the code that authorised the pairing is retired');

  // The new code has to be *visible*: it is what the next pairing is authorised
  // with, and the user types it. Same line, same command, as a first mint.
  const shown = formatPairCode(after);
  assert.ok(
    logs.some((line) => line.includes(`new pair code ${shown}`)
      && line.includes(`boardwise bridge pair ${shown}`)),
    `the log panel must offer the new code: ${JSON.stringify(logs)}`,
  );

  // ...and About… agrees with it, because both read the same resolver — the box
  // must never show a code the next `hello` will not carry.
  connector.about();
  const text = dialogs.at(-1).message;
  assert.ok(text.includes(shown), `the box shows the current code: ${text}`);
  assert.ok(
    text.includes(`bridge pair ${shown}`),
    'and the one command that authorises it',
  );

  // A second reconnect with the same answer `false` still changes nothing.
  const settled = connector.__pairCodeRotationForTests();
  await socket.deliver(helloAnswer({ pairCodeUsed: false }));
  assert.equal(connector.__pairCodeRotationForTests(), settled, 'no second rotation');
  assert.equal(stored.pairCode, after);
});

test('a daemon that predates `pairCodeUsed` never triggers a rotation', async (t) => {
  const { socket, stored, written } = withHost(t);
  await connector.activate();
  await socket.deliver(BANNER);
  const before = socket.frame('hello').params.pairCode;

  // No field at all — the shape a 0.6.1 daemon sends. Absence of a claim is not
  // a claim: reading it as "the code was spent" would rotate on every handshake
  // against an older daemon, and reading it as "authorised" would tell the user
  // this pairing was explicitly allowed when nobody said so.
  const noneBefore = connector.__pairCodeRotationForTests();
  await socket.deliver(helloAnswer());
  assert.equal(connector.__pairCodeRotationForTests(), noneBefore, 'no rotation');
  assert.equal(stored.pairCode, before);
  assert.deepEqual(
    written.filter(([key]) => key === 'pairCode').map(([, value]) => value),
    [before],
    'one write ever: the first mint',
  );
});

test('a rotation the store refuses keeps a stable new code in this process, and says so', async (t) => {
  const parts = withHost(t);
  const { socket, stored, logs } = parts;
  await connector.activate();
  await socket.deliver(BANNER);
  const before = socket.frame('hello').params.pairCode;

  // The store now refuses every write: the code cannot be persisted. The pairing
  // that was just established is untouched — this path never touches the token.
  parts.host.sys_Storage.setExtensionUserConfig = async () => false;
  await socket.deliver(helloAnswer({ pairCodeUsed: true }));
  const rotation = connector.__pairCodeRotationForTests();
  assert.ok(rotation);
  await rotation;

  assert.equal(stored.pairCode, before, 'the store still holds the spent code');
  const box = resolveConfig(parts.host.sys_Storage);
  assert.match(box.pairCode, CODE_SHAPE);
  assert.notEqual(box.pairCode, before, 'but this process moved on to the new one');
  assert.match(box.pairCodeNote, /refused to store the pair code/);
  assert.ok(
    logs.some((line) => line.includes('the new pair code is not stored')),
    `the log panel must disclose it: ${JSON.stringify(logs)}`,
  );

  // Stable: asking twice in a row cannot mint a third code, or the user would be
  // reading one code while the next `hello` carried another.
  assert.equal(resolveConfig(parts.host.sys_Storage).pairCode, box.pairCode);
});

test('a rotation with no CSPRNG keeps the pairing and says what it could not do', async (t) => {
  // A host surface whose `getRandomValues` went away between the mint and the
  // pairing (a reload into a hardened realm is the realistic version). The
  // facade holds that object, so mutating it is what the next call sees.
  const parts = withHost(t, {}, { crypto: undefined });
  const { socket, stored, logs } = parts;
  // A code from before, as if this window had paired fine and then lost its
  // CSPRNG: the point is what a rotation does when it cannot mint.
  stored.pairCode = 'ABCD1234';
  await connector.activate();
  await socket.deliver(BANNER);

  await socket.deliver(helloAnswer({ pairCodeUsed: true }));
  const rotation = connector.__pairCodeRotationForTests();
  assert.ok(rotation, 'the answer still starts a rotation');
  await rotation;

  assert.equal(stored.pairCode, 'ABCD1234', 'a mint that could not happen writes nothing');
  assert.equal(resolveConfig(parts.host.sys_Storage).pairCode, 'ABCD1234');
  assert.ok(
    logs.some((line) => /no replacement pair code could be minted/.test(line)),
    `the panel must say what could not happen: ${JSON.stringify(logs)}`,
  );
  assert.ok(
    logs.some((line) => /the pairing itself is fine/.test(line)),
    'and must not let it read as a broken pairing',
  );
  assert.ok(
    !logs.some((line) => /rotation failed/.test(line)),
    'a host limit is not an exception',
  );
});

// --------------------------------------------------------------------------
// re-pair vs a store that answers late — or not at all (549 review)
// --------------------------------------------------------------------------

/**
 * Hang **one** pair-code write, then behave normally.
 *
 * One-shot on purpose: what is under test is the *wait*, not a dead store. The
 * re-pair's own writes (the clears and the fresh mint) have to go through, or
 * the test would only prove that a broken host breaks everything — a true and
 * useless statement. `release` hands the hung call its answer, and the value is
 * stored at *that* moment, which is what a store resolving a queued write late
 * looks like from here.
 */
function hangNextPairCodeWrite(parts) {
  const store = parts.host.sys_Storage;
  const real = store.setExtensionUserConfig;
  const control = { armed: true, release: undefined, settled: false };
  store.setExtensionUserConfig = (key, value) => {
    if (!control.armed || key !== 'pairCode') return real.call(store, key, value);
    control.armed = false;
    return new Promise((resolve) => {
      control.release = () => {
        control.settled = true;
        parts.stored[key] = value;
        parts.written.push([key, value]);
        resolve(true);
      };
    });
  };
  control.finished = () => control.settled;
  return control;
}

test('a rotation the store never answers cannot stall a re-pair', async (t) => {
  const parts = withHost(t);
  const { socket, stored, logs } = parts;
  await connector.activate();
  await socket.deliver(BANNER);
  const before = socket.frame('hello').params.pairCode;

  // The host accepted the rotation's write and will never answer it: an editor
  // that queues the call and forgets. Before the bounded wait this test hung
  // here — no new code, no reconnect, nothing in the panel, exactly what a user
  // clicking Re-pair would see as a dead menu item.
  const hung = hangNextPairCodeWrite(parts);
  await socket.deliver(helloAnswer({ pairCodeUsed: true }));
  const pending = connector.__pairCodeRotationForTests();
  assert.ok(pending, 'the answer started a rotation');

  const started = Date.now();
  await connector.rePair();
  const waited = Date.now() - started;
  assert.ok(waited < 10_000, `the re-pair waited ${waited} ms on a store that never answers`);
  assert.equal(hung.finished(), false, 'the hung write really is still outstanding');

  assert.ok(
    logs.some((line) => /did not finish within/.test(line)),
    `the panel has to say the wait was given up on: ${JSON.stringify(logs)}`,
  );
  assert.match(
    logs.find((line) => /did not finish within/.test(line)) ?? '',
    /cannot replace it/,
    'and that the new code is the one to authorise',
  );

  // The re-pair completed its real work regardless: new code, stored, on the wire.
  await socket.deliver(BANNER);
  const after = socket.frames('hello').at(-1).params.pairCode;
  assert.ok(after, 'a re-pair still mints a code after giving up on the rotation');
  assert.notEqual(after, before, 'and it is a different code');
  assert.equal(stored.pairCode, after, 'stored under its own key');
});

test('a rotation that answers after the re-pair gave up cannot put its code back', async (t) => {
  const parts = withHost(t);
  const { socket, stored, logs, written } = parts;
  await connector.activate();
  await socket.deliver(BANNER);
  const before = socket.frame('hello').params.pairCode;

  const hung = hangNextPairCodeWrite(parts);
  await socket.deliver(helloAnswer({ pairCodeUsed: true }));
  const pending = connector.__pairCodeRotationForTests();
  assert.ok(pending);

  // The re-pair gives up on the rotation, clears both keys, mints and stores its
  // own code — the code the user is told to authorise.
  await connector.rePair();
  const fresh = stored.pairCode;
  assert.match(fresh, CODE_SHAPE);
  assert.notEqual(fresh, before);
  assert.ok(typeof hung.release === 'function', 'the write is still hung, about to answer');

  // Now the host answers the *old* write. A store that resolves late writes
  // late, so this lands after the re-pair's own value — the classic lost-update
  // shape, and the one that would leave a reload showing a spent code.
  hung.release();
  await pending;

  assert.equal(
    stored.pairCode,
    fresh,
    'the late write must not become the stored code',
  );
  assert.equal(resolveConfig(parts.host.sys_Storage).pairCode, fresh, 'and About… agrees');
  assert.equal(
    written.filter(([key]) => key === 'pairCode').at(-1)[1],
    fresh,
    'the last write to the store is the current code, not the superseded one',
  );
  assert.ok(
    logs.some((line) => /replaced by a re-pair/.test(line)),
    `the rotation must not announce a code it did not keep: ${JSON.stringify(logs)}`,
  );
  assert.ok(
    !logs.some((line) => /so the code it spent is retired/.test(line)),
    'and must not print the superseded code as the new one',
  );
});
