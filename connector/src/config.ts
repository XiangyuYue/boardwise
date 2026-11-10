/**
 * Connector configuration and where the token comes from.
 *
 * An editor extension cannot read `~/.boardwise/token` — it has no way to learn
 * the OS home directory, and `sys_FileSystem` only exposes dialogs and the
 * extension's own folder. Asking the user to copy a 64-hex secret into a dialog
 * ("Set token…") was the worst part of v0, so as of 0.2.0 the connector
 * **generates its own random token** and the daemon trusts it on first use
 * (`docs/bridge.md` §3.4). Nobody types anything.
 *
 * Resolution order for the token:
 *
 * 1. `BOARDWISE_TOKEN` on `globalThis` — lets a wrapper inject it for testing.
 * 2. `token` in extension user config — generated on first activation, or
 *    cleared by "Re-pair on next connect".
 * 3. `?token=` on the configured URL — convenient for a one-off session.
 * 4. nothing — {@link ensureConnectorConfig} generates one before we connect.
 *
 * Since 0.2.1 the generation itself is honest about its source: `random.ts`
 * reports whether it used Web Crypto or had to fall back to `Math.random`, and
 * that source is persisted beside the token so `About…` can still say so after a
 * reload. See `random.ts` and `docs/bridge.md` §9.
 *
 * Since 549 this module also owns the **public pair code** a first pairing needs
 * (`STORAGE_KEYS.pairCode`): minted from Web Crypto only, stored under its own
 * key so a re-pair can replace it without touching the token, and displayed by
 * the panel so the user can run `boardwise bridge pair <CODE>`.
 */

import {
  generatePairCode,
  generateToken,
  PAIR_CODE_ALPHABET,
  PAIR_CODE_LENGTH,
  type RandomHost,
} from './random';

/**
 * Where the daemon listens by default.
 *
 * The `/eda` path is there to match the known-working `easyeda-agent`
 * connector, which dials `ws://127.0.0.1:<port>/eda`. Our daemon ignores the
 * path entirely (measured — see `docs/bridge.md` §12), so this is not
 * load-bearing; it is simply the spelling that has been observed to work on a
 * real editor, and matching it removes one variable when something does not
 * connect. The CLI dials the identical URL via `bridge.client.uri_for`.
 */
export const DEFAULT_URL = 'ws://127.0.0.1:61190/eda';

export const STORAGE_KEYS = {
  url: 'url',
  /**
   * The connector's secret, encoded as `"<source>:<64 hex>"` — **one key, one
   * write, on purpose**.
   *
   * 0.2.1 stored the token and its source as two keys written back to back, and
   * a real editor ended up holding `token.source` without `token` (measured
   * 2026-09-13, via `About…`: `storage: readable (token.source=webcrypto)`
   * beside `token: NONE`). Whatever the host does with two adjacent calls, no
   * later load can repair a half-written pair — so there is no longer a pair.
   * `rePair` clears this same single key, which is why it cannot leave residue.
   */
  token: 'token',
  /**
   * The **public** pair code for the next first pairing (549) — its own key, on
   * purpose.
   *
   * It is not a secret and not the token: it is shown in the panel and typed
   * into `boardwise bridge pair`, and the daemon keeps the grant it authorises
   * in its own memory for five minutes. Storing it beside the token would make
   * two different lifetimes share one value — the token must survive `bridge
   * revoke`-free reconnects, while a re-pair must mint a *new* code — so the two
   * live under separate keys and `rePair` clears both. Keeping it out of
   * `token`'s value also means the 0.2.x–0.6.x stored-token formats (see
   * {@link STORED_TOKEN}) still decode untouched.
   */
  pairCode: 'pairCode',
  autoConnect: 'autoConnect',
} as const;

/** `"webcrypto:<64 hex>"` / `"math:<64 hex>"`. */
const STORED_TOKEN = /^(webcrypto|math):([0-9a-f]{64})$/;

type TokenSource = 'webcrypto' | 'math';

/** Read a stored value as a token plus its provenance. */
function decodeStoredToken(raw: string): { token: string; source: TokenSource | '' } {
  const match = STORED_TOKEN.exec(raw);
  // A bare hex string is a 0.2.0–0.2.2 value, written before the source was
  // recorded; accept it rather than making the user re-pair.
  if (!match) return { token: raw, source: '' };
  return { token: match[2], source: match[1] as TokenSource };
}

function encodeStoredToken(token: string, source: TokenSource): string {
  return `${source}:${token}`;
}

/**
 * A display-only summary of a stored value. Never the value itself: `About…` and
 * the log panel are both user-visible and exportable.
 */
export function describeStoredToken(raw: unknown): string {
  if (raw === undefined || raw === null || raw === '') return 'unset';
  const text = String(raw);
  const match = STORED_TOKEN.exec(text);
  if (match) return `${match[1]}, ${match[2].length} characters`;
  return `legacy format, ${text.length} characters`;
}

export type StorageLike = {
  getExtensionUserConfig(key: string): unknown;
  setExtensionUserConfig(key: string, value: unknown): Promise<boolean>;
};

/**
 * The one spelling of a pair code this connector uses, mirroring the daemon's
 * own `normalise_pair_code`: upper case, separators dropped, and a length and
 * alphabet check that turns anything else into `''` (which never matches a
 * grant, rather than becoming a wildcard).
 *
 * Here rather than only at the input, because the same fold has to apply to a
 * value read back from storage, to a value typed by a user, and to a value
 * compared in the About box. `PAIR_CODE_ALPHABET` is `random.ts`'s — the module
 * that mints the code owns its alphabet.
 */
export function normalisePairCode(raw: unknown): string {
  if (typeof raw !== 'string') return '';
  const text = raw.toUpperCase().replace(/[-_\s]/g, '');
  if (text.length !== PAIR_CODE_LENGTH) return '';
  for (const char of text) {
    if (!PAIR_CODE_ALPHABET.includes(char)) return '';
  }
  return text;
}

/**
 * What a host with no CSPRNG has to be told, in the words the log panel and the
 * About box use (549).
 *
 * Stated as its own constant because the whole point is that this is **not** a
 * network symptom: a connector that cannot mint a pair code can still connect
 * with an existing token, but it can never complete a *first* pairing — the
 * daemon has nothing to match, and no amount of reconnecting changes that.
 */
export const PAIR_CODE_UNAVAILABLE =
  'no secure random source, so this editor cannot mint a pair code and the first '
  + 'pairing cannot be completed from this window';

/**
 * The pair code this *process* is using, when it exists but could not be
 * persisted (549).
 *
 * Stability is the requirement: the code shown in the panel is the one the user
 * types into `boardwise bridge pair`, and the daemon pins the grant to it. A
 * connector that re-minted a code on every reconnect would invalidate the
 * user's authorisation between the moment they read the code and the moment the
 * editor finished reconnecting. So a code is minted **once per process** and
 * reused, whether or not the store accepted it — and when the store refused, the
 * `note` says so instead of the box quietly showing a code that a reload will
 * lose.
 */
let sessionPairCode: {
  code: string;
  note: string;
  /**
   * Set by {@link rotatePairCode} only (549). A rotated code outranks whatever
   * the store still holds, because the rotation happened *because* the daemon
   * consumed the previous code: if the write below it failed, the stored value
   * is a spent authorisation, and showing the user that one would be worse than
   * showing nothing. An ordinary mint leaves this unset, so a stored value keeps
   * the precedence it has always had.
   */
  supersedesStored?: boolean;
} | undefined;

/**
 * Which pair-code intent is current, counted up on every mint and every reset.
 *
 * A code is not just a value, it is a *decision made at a moment*: the rotation
 * a `hello` starts decides "this spent code is retired", and a later explicit
 * re-pair decides "no, everything is replaced". The two write the same storage
 * key, and the host store may answer the older call *after* the newer one — an
 * editor that queues a call and resolves it late is the shape this exists for.
 * So each intent takes a number, an async path re-reads it after every await,
 * and one that finds its number gone knows its value lost: no code that the user
 * has already been told about may be replaced by a code the process stopped
 * using. Only the *latest* intent may land in the store.
 */
let pairCodeGeneration = 0;

/**
 * Forget this process's pair code, so the next mint is a new one.
 *
 * Called by `rePair` — an explicit re-pair has to produce a *new* code, because
 * the old one may still be sitting in a daemon grant — and by the test-only
 * facade teardown, so one test's code cannot bleed into the next. An ordinary
 * reconnect never reaches it: that is what keeps the code stable.
 *
 * It also retires any mint or rotation still in flight (see
 * {@link pairCodeGeneration}): after a re-pair, a write that has not answered yet
 * belongs to a code nobody is using, and it must not resurrect it.
 */
export function forgetPairCode(): void {
  sessionPairCode = undefined;
  pairCodeGeneration += 1;
}

export type ResolvedConfig = {
  url: string;
  token: string;
  /**
   * Where the token came from. `generated` is the normal path since 0.2.0:
   * {@link ensureConnectorConfig} invented it a moment ago and stored it.
   * `generated-weak` is the same thing via the `Math.random` fallback — a
   * connector that works, at a provenance the user is entitled to be told about.
   */
  tokenSource: 'global' | 'storage' | 'url' | 'generated' | 'generated-weak' | 'missing';
  /**
   * Diagnostics about the token's origin, safe to display (e.g.
   * `crypto=unavailable`). Present when we had to hunt for a source.
   */
  tokenNote?: string;
  /**
   * The public 8-character pair code this window offers for a first pairing
   * (549), or `''` when no CSPRNG could mint one. Safe to display: it is the
   * value the user reads out and types into `boardwise bridge pair`.
   */
  pairCode: string;
  /** `storage` (read back), `generated` (minted by this process), `missing`. */
  pairCodeSource: 'storage' | 'generated' | 'missing';
  /**
   * Why there is no usable pair code, or why the one we have is not persisted.
   * Safe to display; never the token.
   */
  pairCodeNote?: string;
  autoConnect: boolean;
};

function fromUrl(url: string): string {
  const match = /[?&]token=([^&]+)/.exec(url);
  return match ? decodeURIComponent(match[1]) : '';
}

export function resolveConfig(storage?: StorageLike): ResolvedConfig {
  const injected = (globalThis as { BOARDWISE_TOKEN?: string }).BOARDWISE_TOKEN;
  const storedUrl = String(storage?.getExtensionUserConfig(STORAGE_KEYS.url) ?? '');
  const url = storedUrl || DEFAULT_URL;

  const stored = decodeStoredToken(
    String(storage?.getExtensionUserConfig(STORAGE_KEYS.token) ?? ''),
  );
  const urlToken = fromUrl(url);

  let token = '';
  let tokenSource: ResolvedConfig['tokenSource'] = 'missing';
  if (injected) {
    token = injected;
    tokenSource = 'global';
  } else if (stored.token) {
    token = stored.token;
    // A token born of the weak fallback stays labelled that way for the rest of
    // its life, so `About…` never launders it into an anonymous `storage` token.
    tokenSource = stored.source === 'math' ? 'generated-weak' : 'storage';
  } else if (urlToken) {
    token = urlToken;
    tokenSource = 'url';
  }

  // The socket URL itself must not carry the token once it has been read.
  const cleanUrl = url.replace(/([?&])token=[^&]*&?/, '$1').replace(/[?&]$/, '');
  const autoConnect = storage?.getExtensionUserConfig(STORAGE_KEYS.autoConnect) !== false;

  // The pair code: the stored value first — it is the one that survives a
  // reload — then whatever this process already minted. Reading the session copy
  // here (and not only in `ensureConnectorConfig`) is what keeps `About…` and
  // the `hello` frame describing the same code after a storage failure.
  //
  // The one exception is a code this process *rotated* (549): it was minted
  // because the daemon had just spent the previous one, so the value in the
  // store is dead even when the new one could not be written over it.
  const storedPairCode = normalisePairCode(
    storage?.getExtensionUserConfig(STORAGE_KEYS.pairCode),
  );
  const session = sessionPairCode;
  const sessionWins = session !== undefined
    && (session.supersedesStored === true || !storedPairCode);
  const pairCode = sessionWins ? session.code : storedPairCode;
  const pairCodeSource: ResolvedConfig['pairCodeSource'] = sessionWins
    ? 'generated'
    : storedPairCode
      ? 'storage'
      : 'missing';

  return {
    url: cleanUrl || DEFAULT_URL,
    token,
    tokenSource,
    // Carry the provenance forward so `About…` can be honest after a reload,
    // not just at the moment of generation.
    ...(tokenSource === 'generated-weak'
      ? { tokenNote: 'the stored token was generated with Math.random (not a CSPRNG)' }
      : {}),
    pairCode,
    pairCodeSource,
    ...(sessionWins && session.note ? { pairCodeNote: session.note } : {}),
    autoConnect,
  };
}

export const DEFAULT_PORT = 61190;

/** Port from `BOARDWISE_PORT`, mirroring the daemon's own resolution. */
export function portFromEnvironment(): number {
  const raw = (globalThis as { BOARDWISE_PORT?: string | number }).BOARDWISE_PORT;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_PORT;
}

/**
 * A fresh 32-byte secret as 64 hex characters — the same shape the daemon uses.
 *
 * A thin wrapper over {@link generateToken}, kept because its callers only want
 * the string. The *source* lives there because a caller that cannot say how it
 * got a token is precisely the mistake 0.2.1 exists to fix.
 */
export function randomToken(host?: RandomHost): string {
  return generateToken(host).token;
}

/**
 * The config, with a token and a pair code guaranteed to exist where the host
 * allows it.
 *
 * Called once per connect. Generates and persists a token the first time, so
 * the zero-configuration flow is: install the extension, restart the editor,
 * done. Writes to storage before returning, because a token that only lives in
 * this process would be regenerated on every reload — which would re-pair the
 * connector each restart and make the pairing record meaningless.
 *
 * Since 549 it also ensures the **public pair code** the daemon's
 * `pair.authorize` grant has to match. That half has a stricter policy than the
 * token's (see `random.ts`): Web Crypto or nothing, and a code that could not be
 * persisted is still reused for the rest of this process, because a code that
 * changed on every reconnect would invalidate the user's authorisation between
 * reading the code and the editor finishing its next attempt.
 */
export async function ensureConnectorConfig(
  storage?: StorageLike,
  host?: RandomHost,
): Promise<ResolvedConfig> {
  const withToken = await ensureToken(storage, host);
  return ensurePairCode(withToken, storage, host);
}

async function ensureToken(
  storage?: StorageLike,
  host?: RandomHost,
): Promise<ResolvedConfig> {
  const current = resolveConfig(storage);
  if (current.token) return current;

  const generated = generateToken(host);
  if (!generated.token) {
    // Nothing usable on this host. Return the *diagnosis*, not a bare failure:
    // the caller puts `tokenNote` in the log panel, so the user sees
    // `crypto=unavailable` instead of a connector that sits silently idle.
    return { ...current, tokenNote: generated.detail };
  }

  let note = generated.detail;
  try {
    // One key, one call. See STORAGE_KEYS.token for why this is not two.
    const wrote = await storage?.setExtensionUserConfig(
      STORAGE_KEYS.token,
      encodeStoredToken(generated.token, generated.source === 'math' ? 'math' : 'webcrypto'),
    );
    // The method returns a boolean and may resolve `false`. 0.2.x ignored it, so
    // a refused write was indistinguishable from a good one until the next
    // reload — when the token was simply gone. Say so instead.
    if (storage && wrote === false) {
      note = `${note}; the editor refused to store the token (setExtensionUserConfig returned false)`;
    }
  } catch {
    // Storage refused (quota, permissions). The token still works for this
    // session; it is the *next* restart that will re-pair. Not worth failing —
    // but it is worth reporting.
    note = `${note}; storing the token threw`;
  }
  return {
    ...current,
    token: generated.token,
    tokenSource: generated.source === 'math' ? 'generated-weak' : 'generated',
    tokenNote: note,
  };
}

/**
 * Make sure this window has a pair code, and that the user can see it.
 *
 * Three outcomes, each of which the caller must be able to tell apart:
 *
 * - a code already exists (stored, or minted earlier in this process) — nothing
 *   is written and nothing changes, which is what makes reconnects stable;
 * - a code was minted and stored — the normal first-pairing path;
 * - no code could be minted (no CSPRNG) — `pairCode` stays `''` and
 *   {@link PAIR_CODE_UNAVAILABLE} explains that a *first* pairing is impossible
 *   on this host. An existing token still connects: only the first pairing needs
 *   the code.
 *
 * A storage failure never loses the code: it is kept for this process (see
 * `sessionPairCode`) and the `pairCodeNote` says it will not survive a reload,
 * rather than the box showing a number a restart will silently change.
 */
async function ensurePairCode(
  current: ResolvedConfig,
  storage: StorageLike | undefined,
  host: RandomHost | undefined,
): Promise<ResolvedConfig> {
  if (current.pairCode) return current;

  const generated = generatePairCode(host);
  if (!generated.pairCode) {
    return {
      ...current,
      pairCode: '',
      pairCodeSource: 'missing',
      pairCodeNote: `${PAIR_CODE_UNAVAILABLE} (${generated.detail})`,
    };
  }

  sessionPairCode = { code: generated.pairCode, note: '' };
  // A mint is a new intent: anything older still under way (a rotation whose
  // write never answered, then a re-pair) must not land over this value.
  const generation = ++pairCodeGeneration;
  let note = '';
  try {
    // Its own key, one write — the same rule the token follows, and the same
    // reason: two adjacent writes can be left half-done by the host.
    const wrote = await storage?.setExtensionUserConfig(
      STORAGE_KEYS.pairCode,
      generated.pairCode,
    );
    if (storage && wrote === false) {
      note = 'the editor refused to store the pair code (setExtensionUserConfig returned false)';
    }
  } catch {
    note = 'storing the pair code threw';
  }
  if (note && generation === pairCodeGeneration) {
    sessionPairCode = { code: generated.pairCode, note };
  }

  return {
    ...current,
    pairCode: generated.pairCode,
    pairCodeSource: 'generated',
    ...(note ? { pairCodeNote: note } : {}),
  };
}

/** What a rotation produced — and what it could not do, in words. */
export type RotatedPairCode = {
  /** The new code, or `''` when this host could not mint one. */
  pairCode: string;
  /** Why there is no new code at all (`crypto=unavailable`, …); omitted on success. */
  detail?: string;
  /** Non-empty when the new code could not be persisted. */
  note?: string;
  /**
   * A re-pair replaced this rotation's code while the store was answering it:
   * the rotation's own value was never kept, so a caller must not announce it.
   */
  superseded?: boolean;
};

/**
 * Put the current code back after a superseded rotation's write has landed.
 *
 * Last thing that happens on the losing side of a race, and the reason the race
 * is only cosmetically lost: the store may well have accepted the *older* code
 * after the newer one was written (a host that resolves its queue in order but
 * late). Rewriting the winner is what makes "the newest code wins" true in
 * storage as well as in memory — otherwise a reload would show the user the code
 * of a pairing that is already done with.
 *
 * Best effort and never throws: the caller is a rotation nobody is waiting for
 * any more, and an exception here would be an unhandled rejection in the editor.
 */
async function restoreCurrentPairCode(
  storage: StorageLike | undefined,
  code: string,
): Promise<void> {
  try {
    await storage?.setExtensionUserConfig(STORAGE_KEYS.pairCode, code);
  } catch {
    /* the store refused the correction too; the in-process value still wins */
  }
}

/**
 * Mint the **next** public code, after the daemon has written a pairing record
 * with the current one (549).
 *
 * Called from the `hello` handler when the answer says `pairCodeUsed: true`, and
 * the reason is the whole point of that field: a code authorises exactly one
 * pairing write, so leaving it on screen after it has been spent would hand
 * every later reader — a saved log line, a screenshot, anyone watching the
 * panel — a working authorisation for a pairing that is not theirs. The next
 * pairing needs a code nobody has seen.
 *
 * Two things must survive a failure here, and they are different failures:
 *
 * - **The pairing that just succeeded must not be disturbed.** This function
 *   only touches the code, never the token, and it never throws: a rotation that
 *   could not happen leaves a connected, paired window connected and paired, and
 *   says what it could not do instead.
 * - **The new code must be stable for this process even when the store refuses
 *   it.** `sessionPairCode` is set *before* the write, and marked as superseding
 *   the stored value, so `About…` and the next `hello` show the new code rather
 *   than the spent one for the rest of this process; `note` says the code will
 *   not survive a reload.
 *
 * A third case sits between the two: **the rotation was superseded while it
 * awaited the store** (an explicit re-pair got there first, see
 * {@link pairCodeGeneration}). Then this code is not the one anybody is using,
 * and the write that has just answered may have landed after the re-pair's own —
 * so the current code is written back and the caller is told the rotation was
 * superseded rather than shown a value it must not announce.
 */
export async function rotatePairCode(
  storage: StorageLike | undefined,
  host: RandomHost | undefined,
): Promise<RotatedPairCode> {
  const generated = generatePairCode(host);
  if (!generated.pairCode) {
    // No CSPRNG. Nothing is cleared and nothing is claimed: the pairing record is
    // untouched, and a first pairing was already impossible on this host.
    return { pairCode: '', detail: generated.detail };
  }

  sessionPairCode = { code: generated.pairCode, note: '', supersedesStored: true };
  const generation = ++pairCodeGeneration;
  let note = '';
  try {
    const wrote = await storage?.setExtensionUserConfig(
      STORAGE_KEYS.pairCode,
      generated.pairCode,
    );
    if (storage && wrote === false) {
      note = 'the editor refused to store the pair code (setExtensionUserConfig returned false)';
    }
  } catch {
    note = 'storing the pair code threw';
  }

  if (generation !== pairCodeGeneration) {
    // A newer intent exists (a re-pair forgot this code and minted its own while
    // this write was in the host's queue). Whatever the store now holds, it must
    // end up describing the newest code, so put it back when there is one.
    if (sessionPairCode) await restoreCurrentPairCode(storage, sessionPairCode.code);
    return { pairCode: generated.pairCode, superseded: true };
  }

  if (note) sessionPairCode = { code: generated.pairCode, note, supersedesStored: true };

  return note ? { pairCode: generated.pairCode, note } : { pairCode: generated.pairCode };
}
