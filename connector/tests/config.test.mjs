import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEFAULT_URL,
  describeStoredToken,
  ensureConnectorConfig,
  forgetPairCode,
  randomToken,
  resolveConfig,
} from '../dist/esm/config.mjs';

function storage(entries = {}) {
  const written = [];
  return {
    written,
    getExtensionUserConfig: (key) => entries[key],
    setExtensionUserConfig: async (key, value) => {
      written.push([key, value]);
      return true;
    },
  };
}

test('falls back to the default url and reports a missing token', () => {
  const config = resolveConfig(storage());
  assert.equal(config.url, DEFAULT_URL);
  assert.equal(config.token, '');
  assert.equal(config.tokenSource, 'missing');
  assert.equal(config.autoConnect, true);
});

test('token resolution order: global beats storage beats url', () => {
  const store = storage({ token: 'from-storage', url: 'ws://127.0.0.1:9999/eda?token=from-url' });

  const fromUrl = resolveConfig(store);
  assert.equal(fromUrl.token, 'from-storage', 'storage wins over the url');

  globalThis.BOARDWISE_TOKEN = 'from-global';
  try {
    const fromGlobal = resolveConfig(store);
    assert.equal(fromGlobal.token, 'from-global');
    assert.equal(fromGlobal.tokenSource, 'global');
  } finally {
    delete globalThis.BOARDWISE_TOKEN;
  }
});

test('token in the url is read and then stripped from the socket url', () => {
  const config = resolveConfig(storage({ url: 'ws://127.0.0.1:61190/eda?token=abc123' }));
  assert.equal(config.token, 'abc123');
  assert.equal(config.tokenSource, 'url');
  assert.ok(!config.url.includes('token'), `url still carries the token: ${config.url}`);
});

test('auto-connect can be switched off explicitly', () => {
  assert.equal(resolveConfig(storage({ autoConnect: false })).autoConnect, false);
});


// --------------------------------------------------------------------------
// generated tokens (task 004c): nobody types a secret any more
// --------------------------------------------------------------------------


test('a token is generated and stored when the editor has none', async () => {
  const store = storage();
  forgetPairCode();
  const config = await ensureConnectorConfig(store);

  assert.equal(config.token.length, 64, 'a 32-byte secret as hex');
  assert.match(config.token, /^[0-9a-f]{64}$/);
  assert.equal(config.tokenSource, 'generated');
  // Persisted, or the next reload would generate a different one and re-pair.
  // One key, holding `"<source>:<hex>"` — deliberately not a token plus a
  // separate source key. 0.2.1 wrote two keys back to back and a real editor
  // ended up holding the source *without* the token (measured 2026-09-13 via
  // `About…`); no later load can repair a half-written pair, so there is no
  // longer a pair. See `config.ts`'s `STORAGE_KEYS.token`.
  assert.deepEqual(store.written[0], ['token', `webcrypto:${config.token}`]);
  // The pair code is the second write and a key of its own (549): a re-pair has
  // to be able to replace the code without touching the token.
  assert.equal(store.written.length, 2, `unexpected writes: ${JSON.stringify(store.written)}`);
  assert.deepEqual(store.written[1], ['pairCode', config.pairCode]);
  assert.equal(config.pairCodeSource, 'generated');
});

test('a host with no Web Crypto still pairs, and the provenance is recorded', async () => {
  // This is the real editor on 2026-09-13: bare `crypto` did not resolve, so
  // 0.2.0 produced no token at all and the connector sat idle. The fallback has
  // to work *and* be disclosed.
  const store = storage();
  forgetPairCode();
  const config = await ensureConnectorConfig(store, { crypto: undefined });

  assert.equal(config.token.length, 64);
  assert.equal(config.tokenSource, 'generated-weak');
  assert.equal(config.tokenNote, 'crypto=unavailable');
  // The *pair code*, however, has no fallback (549): without a CSPRNG there is
  // no code this window may offer, so nothing is minted and nothing is written.
  assert.equal(config.pairCode, '');
  assert.equal(config.pairCodeSource, 'missing');
  assert.match(config.pairCodeNote, /first pairing cannot be completed/);
  assert.deepEqual(store.written, [['token', `math:${config.token}`]]);
});

test('a weak token stays weak across a reload', async () => {
  // `About…` must not turn a `Math.random` token into an anonymous `storage`
  // one just because the process restarted.
  const weak = resolveConfig(storage({ token: `math:${'f'.repeat(64)}` }));
  assert.equal(weak.tokenSource, 'generated-weak');
  assert.match(weak.tokenNote, /Math\.random/);

  const strong = resolveConfig(storage({ token: `webcrypto:${'f'.repeat(64)}` }));
  assert.equal(strong.tokenSource, 'storage');
});

test('a 0.2.2 token, stored as bare hex, is still read', async () => {
  // 0.2.0–0.2.2 stored 64 hex characters with no provenance. Upgrading must not
  // silently re-pair the connector — the daemon would refuse a second pairing
  // and the user would have to run `bridge revoke` for a cosmetic change.
  const store = storage({ token: 'a'.repeat(64) });
  forgetPairCode();
  const config = await ensureConnectorConfig(store);

  assert.equal(config.token, 'a'.repeat(64));
  assert.equal(config.tokenSource, 'storage');
  // The legacy value decodes independently of the new key: adding a pair code
  // must not rewrite (or re-format) a token written by an older build.
  assert.deepEqual(store.written.map(([key]) => key), ['pairCode']);
});

test('About… describes what is stored without ever showing it', () => {
  const token = 'd'.repeat(64);
  assert.equal(describeStoredToken(undefined), 'unset');
  assert.equal(describeStoredToken(''), 'unset');
  assert.equal(describeStoredToken(`webcrypto:${token}`), 'webcrypto, 64 characters');
  assert.equal(describeStoredToken(`math:${token}`), 'math, 64 characters');
  // An old value has no source to name, so say that instead of guessing.
  assert.equal(describeStoredToken(token), 'legacy format, 64 characters');
  assert.ok(!describeStoredToken(`webcrypto:${token}`).includes(token));
});

test('nothing to generate from leaves the token missing, with a reason', async () => {
  const store = storage();
  forgetPairCode();
  const config = await ensureConnectorConfig(store, {
    crypto: undefined,
    mathRandom: undefined,
  });

  assert.equal(config.token, '');
  assert.equal(config.tokenSource, 'missing');
  assert.equal(config.tokenNote, 'crypto=unavailable', 'say why, not merely "no"');
  assert.equal(config.pairCode, '');
  assert.match(config.pairCodeNote, /no secure random source/);
  assert.deepEqual(store.written, [], 'nothing worth persisting');
});

test('an existing token is reused, never regenerated', async () => {
  const store = storage({ token: `webcrypto:${'a'.repeat(64)}` });
  forgetPairCode();
  const config = await ensureConnectorConfig(store);

  assert.equal(config.token, 'a'.repeat(64));
  assert.equal(config.tokenSource, 'storage');
  // A working pairing still gets a code for its *next* re-pair, but the token is
  // not touched: one key, one write, and never the other value's key.
  assert.deepEqual(store.written.map(([key]) => key), ['pairCode']);
});

test('an injected token wins over generation', async () => {
  globalThis.BOARDWISE_TOKEN = 'injected';
  try {
    const store = storage();
    forgetPairCode();
    const config = await ensureConnectorConfig(store);
    assert.equal(config.tokenSource, 'global');
    assert.deepEqual(store.written.map(([key]) => key), ['pairCode'], 'an injected token is not written down');
  } finally {
    delete globalThis.BOARDWISE_TOKEN;
  }
});

test('two generations differ, and are shaped like the daemon expects', () => {
  const first = randomToken();
  const second = randomToken();
  assert.match(first, /^[0-9a-f]{64}$/);
  assert.notEqual(first, second, 'a repeated token would not be a secret');
});

test('storage refusing to save does not lose this session', async () => {
  // A quota or permission failure must not stop the connector from connecting
  // now; it only means the next reload re-pairs.
  const store = storage();
  store.setExtensionUserConfig = async () => {
    throw new Error('storage is full');
  };
  forgetPairCode();
  const config = await ensureConnectorConfig(store);
  assert.equal(config.token.length, 64);
  assert.equal(config.tokenSource, 'generated');
  // The pair code survives the same failure, in-process and disclosed (549).
  assert.equal(config.pairCode.length, 8);
  assert.match(config.pairCodeNote, /storing the pair code threw/);
});

test('a refused write is reported, not silently swallowed', async () => {
  // `setExtensionUserConfig` returns a promise for a boolean. 0.2.x ignored the
  // value, so a refused write looked exactly like a good one until the next
  // reload — when the token was simply gone and the connector re-paired.
  const store = storage();
  store.setExtensionUserConfig = async () => false;
  forgetPairCode();
  const config = await ensureConnectorConfig(store);

  assert.equal(config.token.length, 64, 'still usable for this session');
  assert.match(config.tokenNote, /refused to store/, 'but the user is told');
  assert.equal(config.pairCode.length, 8, 'still shown, so the user can authorise it');
  assert.match(config.pairCodeNote, /refused to store the pair code/);
});

test('a generated token never appears in the resolved url', async () => {
  const config = await ensureConnectorConfig(storage());
  assert.ok(!config.url.includes(config.token), 'the url would be logged');
  assert.ok(!config.url.includes(config.pairCode), 'nor does the public code ride along');
});
