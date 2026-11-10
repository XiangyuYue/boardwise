/**
 * Where the connector's own token comes from — and being honest about it.
 *
 * 0.2.0 assumed `crypto.getRandomValues` was reachable from an extension the way
 * a browser page reaches it. On 2026-09-13 a real editor said otherwise: `About…`
 * reported `token: NONE — this editor cannot generate one`, so the bare `crypto`
 * identifier did not resolve in the extension's realm. That is the *third* time
 * this extension has been bitten by assuming a host global is where the docs say
 * it is (see `facade.ts`), and the first time the failure was invisible: the old
 * `randomToken()` caught everything and returned `''`, so the only symptom was a
 * connector that sat idle.
 *
 * This module exists so the assumption is *checkable* instead of implicit:
 *
 * - it reads the global defensively (`typeof` / `try` below),
 * - it always reports which source produced the token, in words a user can read
 *   in the log panel, and
 * - it never hands back a token without saying how it got it.
 *
 * Fallback policy, and why it is not a silent downgrade: if Web Crypto is absent
 * we fall back to `Math.random`. That is a real weakening — the output is not a
 * CSPRNG — but it is bounded by the threat model in `docs/bridge.md` §9. The
 * token guards a loopback socket, the same OS user can read the token file
 * anyway, and an attacker who can read neither file (another OS user, or a web
 * page abusing the Origin hole that 004c only *measures*) cannot observe this
 * process's outputs, so the PRNG seed is not recoverable in practice. A user who
 * dislikes the trade-off can see it in `About…` and in the log panel and decide
 * — which is the opposite of the silent `?? someGlobal` failure that cost two
 * hardware sessions.
 *
 * **The pair code gets no fallback at all (549).** `generatePairCode` is a
 * separate function with a stricter policy than `generateToken`: it uses Web
 * Crypto or it fails, because a pair code authorises a pairing and a guessable
 * one would authorise the wrong connector. That is why the two values are not
 * one function with a flag.
 */

export type RandomSource =
  /** The platform CSPRNG. The only source we would call strong. */
  | 'webcrypto'
  /** `Math.random` — works everywhere, is not cryptographic. Disclosed. */
  | 'math'
  /** Nothing usable: no token can be produced. */
  | 'none';

export type GeneratedToken = {
  /** 64 lowercase hex characters, or `''` when no source was usable. */
  token: string;
  source: RandomSource;
  /** One readable line about the host, e.g. `crypto=unavailable`. Never a token. */
  detail: string;
};

/** The slice of Web Crypto we rely on. */
type CryptoLike = { getRandomValues?: (array: Uint8Array) => unknown };

/**
 * Injectable host surface, so the whole chain is testable without an editor.
 *
 * Use `'crypto' in host` to tell "not injected" from "injected as undefined":
 * a test must be able to say *this host has no crypto* explicitly.
 */
export type RandomHost = {
  /** Defaults to the ambient global. */
  crypto?: unknown;
  /** Defaults to `Math.random`. Injected by tests to prove the fallback ran. */
  mathRandom?: () => number;
};

const BYTES = 32;

function bytesToHex(bytes: Uint8Array): string {
  let out = '';
  for (const byte of bytes) out += byte.toString(16).padStart(2, '0');
  return out;
}

/**
 * The ambient `crypto`, or `undefined`.
 *
 * The bare identifier is deliberate. `globalThis.crypto` is the spelling that
 * *looks* right, and it is exactly the one that turned out to be `undefined` for
 * `eda`; the bare form covers both a real platform global and a host-bound
 * context global, and degrades to `undefined` rather than throwing when neither
 * exists. `tests/source-guard.test.mjs` forbids the `globalThis.crypto` spelling
 * anywhere in `src/`.
 */
function hostCrypto(): unknown {
  try {
    return crypto;
  } catch {
    return undefined;
  }
}

function hostMathRandom(): (() => number) | undefined {
  try {
    return typeof Math?.random === 'function' ? Math.random : undefined;
  } catch {
    return undefined;
  }
}

/** Pull the crypto object out of an injected host, or read the ambient one. */
function pickCrypto(host: RandomHost): unknown {
  return 'crypto' in host ? host.crypto : hostCrypto();
}

/** Bytes the usability probe asks for. One is enough to prove the call works. */
const PROBE_BYTES = 1;

/**
 * What the host offers, in words. Safe to display: it never contains a token, so
 * it can go straight into the log panel and the `About…` box.
 *
 * It **calls** `getRandomValues` rather than believing `typeof`. That matters,
 * and 0.2.1 is the evidence: it reported `crypto=ok` on a realm where the token
 * still never appeared, which sent the investigation down the wrong path for a
 * whole round trip. A sandbox can perfectly well expose a function that throws
 * the moment it is invoked, and `typeof rng === 'function'` cannot see that.
 */
export function describeRandomHost(cryptoGlobal: unknown): string {
  if (cryptoGlobal === undefined || cryptoGlobal === null) return 'crypto=unavailable';

  const type = typeof cryptoGlobal;
  if (type !== 'object' && type !== 'function') return `crypto=${type}`;

  const rng = (cryptoGlobal as CryptoLike).getRandomValues;
  if (typeof rng !== 'function') return `crypto=${type}, getRandomValues=${typeof rng}`;

  try {
    rng.call(cryptoGlobal, new Uint8Array(PROBE_BYTES));
    return 'crypto=ok';
  } catch (error) {
    return `crypto=getRandomValues threw ${errorName(error)}`;
  }
}

/** `TypeError` for an `Error`, else the type — never a full message. */
function errorName(error: unknown): string {
  if (error && typeof error === 'object' && 'name' in error) {
    return String((error as { name: unknown }).name);
  }
  return typeof error;
}

/**
 * Describe a host's random surface.
 *
 * For `About…`, which may be opened before any connect attempt — i.e. before
 * anything has tried to generate a token, so there is no `tokenNote` to show.
 * Takes the host explicitly (defaulting to this realm) so the box can be tested
 * against a stand-in without Web Crypto — the configuration that actually broke.
 */
export function describeRandom(host: RandomHost = {}): string {
  return describeRandomHost(pickCrypto(host));
}

/**
 * The ambient host, packaged for injection.
 *
 * `index.ts` never reaches for `crypto` itself: it takes this from the facade and
 * hands it to `ensureConnectorConfig`. That is what lets the test suite drive the
 * *no-Web-Crypto* path end to end — the exact path a real editor took on
 * 2026-09-13, and the one 0.2.0 shipped without any test for.
 */
export function ambientRandomHost(): RandomHost {
  return { crypto: hostCrypto() };
}

/**
 * Produce a fresh token, and say where it came from.
 *
 * Order: Web Crypto, then `Math.random`, then nothing. The middle step is the
 * one that makes this work on the real editor today; `source: 'math'` is the
 * caller's cue to warn the user.
 */
export function generateToken(host: RandomHost = {}): GeneratedToken {
  const cryptoGlobal = pickCrypto(host);
  const detail = describeRandomHost(cryptoGlobal);

  const rng = (cryptoGlobal as CryptoLike | undefined)?.getRandomValues;
  if (typeof rng === 'function') {
    try {
      const bytes = new Uint8Array(BYTES);
      rng.call(cryptoGlobal, bytes);
      return { token: bytesToHex(bytes), source: 'webcrypto', detail };
    } catch {
      // `detail` already records that the call threw and why; fall through to the
      // fallback rather than losing the connector to an unhandled error.
    }
  }

  const mathRandom = 'mathRandom' in host ? host.mathRandom : hostMathRandom();
  if (typeof mathRandom === 'function') {
    const bytes = new Uint8Array(BYTES);
    for (let i = 0; i < BYTES; i += 1) {
      bytes[i] = Math.floor(mathRandom() * 256) & 0xff;
    }
    return { token: bytesToHex(bytes), source: 'math', detail };
  }

  return { token: '', source: 'none', detail };
}

// --------------------------------------------------------------------------
// the public pair code (549)
// --------------------------------------------------------------------------

/**
 * The characters a pair code is built from: Crockford base32 — the ten digits
 * and the upper-case letters without `I`, `L`, `O` and `U`, the four a human
 * reads back wrong. The daemon keeps the same list
 * (`bridge/daemon.py`'s `PAIR_CODE_ALPHABET`) so a code read off the editor
 * screen can be typed into `boardwise bridge pair` without a translation table.
 */
export const PAIR_CODE_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

/** Eight characters, i.e. 40 bits: ~1.1e12 codes, shown as two groups of four. */
export const PAIR_CODE_LENGTH = 8;

/**
 * `ABCD1234` → `ABCD-1234`, for display only.
 *
 * The hyphen is a reading aid, never part of the code: the daemon strips it (and
 * spaces, and the case) before comparing, so displaying the groups and sending
 * the bare form cannot disagree. A value that is not a code at all is returned
 * untouched rather than sliced into a shape it does not have.
 */
export function formatPairCode(code: string): string {
  const text = typeof code === 'string' ? code : '';
  if (text.length !== PAIR_CODE_LENGTH) return text;
  return `${text.slice(0, 4)}-${text.slice(4)}`;
}

export type GeneratedPairCode = {
  /** Eight characters from {@link PAIR_CODE_ALPHABET}, or `''` when there is no CSPRNG. */
  pairCode: string;
  /** `webcrypto` only. There is deliberately no weak source for this value. */
  source: 'webcrypto' | 'none';
  /** One readable line about the host, e.g. `crypto=unavailable`. Never a secret. */
  detail: string;
};

/**
 * Mint the public code that authorises this connector's **first** pairing (549).
 *
 * Two decisions are load-bearing here, and both are about what this value is
 * *for*:
 *
 * **Web Crypto or nothing.** `generateToken` above may fall back to
 * `Math.random`, and that trade-off is defensible for the token (see this
 * file's docstring). It is not defensible for the pair code: the code is what
 * convinces the daemon to write the pairing record, so it is the one secret the
 * user types *into a command*, and it is shown on screen while a grant is live.
 * A predictable code would let anyone who can guess it pair their own connector.
 * So this function never touches `Math.random`, and when the platform CSPRNG is
 * missing or throws it answers `''` — the caller omits the field from `hello`
 * and tells the user plainly that a first pairing is impossible on this host,
 * instead of minting something weak and calling it authorised.
 *
 * **Uniform without rejection sampling.** Each character needs 5 bits, and 256
 * is an exact multiple of 32, so `byte & 31` is uniform — no modulo bias, and no
 * variable-length loop that could read more bytes than it needs. The bytes come
 * from one `getRandomValues` call, which is also what makes the source provable
 * in a test.
 *
 * **Output that cannot be random is not accepted either.** "The function exists
 * and did not throw" is not the same claim as "the buffer holds entropy": a
 * sandbox can hand back a stub that fills nothing (leaving the buffer's zeros)
 * or fills one repeated value, and either would mint `00000000`/`ZZZZZZZZ` —
 * eight characters a guesser gets in one try. Eight identical bytes from a real
 * CSPRNG has probability 2^-56, so refusing the shape costs nothing honest and
 * closes the stubbed-host hole. Same policy as the missing-CSPRNG branch: `''`,
 * and the detail names what the host actually did.
 */
export function generatePairCode(host: RandomHost = {}): GeneratedPairCode {
  const cryptoGlobal = pickCrypto(host);
  const detail = describeRandomHost(cryptoGlobal);
  const rng = (cryptoGlobal as CryptoLike | undefined)?.getRandomValues;
  if (typeof rng !== 'function') return { pairCode: '', source: 'none', detail };

  try {
    const bytes = new Uint8Array(PAIR_CODE_LENGTH);
    rng.call(cryptoGlobal, bytes);
    const first = bytes[0];
    let constant = true;
    let zero = true;
    for (const byte of bytes) {
      if (byte !== first) constant = false;
      if (byte !== 0) zero = false;
    }
    // Checked before the alphabet is applied: `00000000` is a code, and this is
    // the one place that can tell it apart from a real draw of eight zero bytes.
    if (zero) return { pairCode: '', source: 'none', detail: `${detail}, getRandomValues=zeros` };
    if (constant) {
      return { pairCode: '', source: 'none', detail: `${detail}, getRandomValues=constant` };
    }
    let pairCode = '';
    for (const byte of bytes) pairCode += PAIR_CODE_ALPHABET[byte & 31];
    return { pairCode, source: 'webcrypto', detail };
  } catch {
    // `detail` already records that the call threw and why. Fail closed: there
    // is no weaker source to fall back to for this value.
    return { pairCode: '', source: 'none', detail };
  }
}
