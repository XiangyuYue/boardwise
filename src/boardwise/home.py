"""The one boardwise home: ``BOARDWISE_HOME`` or ``~/.boardwise`` (598).

This module sits at the package root, below the layer roots, because two
consumers that must agree cannot import each other: ``core.config`` owns the
settings file under the home, and ``bridge.daemon`` owns the token, the audit
log and the daemon logs there, while the layer arrows forbid ``bridge`` from
importing ``core`` (and ``core`` must not import ``bridge``). 587 left the
bridge reading the variable through ``core.config``; the layer guard caught that
edge. The reader moved here and both sides import this one module instead.

It imports nothing from the package, deliberately — any in-package import would
re-create the arrow this module exists to remove, whichever way it ran.

Two rules the reader keeps from 586/587, both measured there:

* **read on every call, never cached** — 569-F-3 found one process whose settings
  sat under the new home while its token sat under the old one, because one
  consumer froze the value at import;
* **a value that cannot name one directory is refused** — a relative path moves
  with the working directory, and Windows silently strips a trailing dot or
  whitespace from a final component, so two spellings would mean one profile.
  ``\\\\?\\`` paths bypass that normalisation and are therefore accepted as
  written;
* **``~`` is expanded, nothing else is** — the user's home is a spelling that
  names one directory on its own terms, so ``~/bw`` is the user's ``bw`` and not
  a relative path. Only the leading ``~`` is resolved (615); a plain relative
  path stays refused, so this cannot re-open the drift 586 closed.

One class rule the reader also keeps: 586/587's contract is that *every*
consumer refuses an unusable home with the same named error, so the concrete
class lives here and ``core.config`` re-exports it (see :class:`ConfigError`).
"""

from __future__ import annotations

import os
from pathlib import Path


class BoardwiseHomeError(ValueError):
    """``BOARDWISE_HOME`` does not name one directory.

    The base of every refusal this module raises. A consumer that must not fail
    a call over the home — the bridge's audit log, whose promise is "logging must
    not break the request" — catches this shared name and not the settings
    module's, which it is not allowed to import.
    """


class ConfigError(BoardwiseHomeError):
    """The configuration's public error; an unusable home is one of its cases.

    Defined beside the reader rather than in ``core.config`` because the class
    has to be *one* class on both sides of the layer seam: the bridge may not
    import ``core.config``, and 587's contract is that a bad home is the same
    named error from every consumer. ``core.config`` re-exports this class as
    its ``ConfigError``, so ``boardwise.core.config.ConfigError`` is the same
    object it has always been for callers, ``except`` clauses and the CLI's
    exit-2 handlers.
    """


def boardwise_home() -> Path:
    """This call's boardwise home: ``BOARDWISE_HOME`` wins, else ``~/.boardwise``.

    An override is read literally, but only the spellings whose meaning cannot
    drift are accepted: a relative path would re-resolve against the current
    directory, and a final component ending in a dot or whitespace is silently
    stripped by Windows, so two environment values would name one directory.
    Both are configuration errors, raised here rather than misread later.

    ``~`` is the one spelling that is expanded (615): the user's home names one
    directory without being absolute, so ``~/bw`` is ``Path.home()/"bw"``.  The
    expansion happens before the absolute check and only for a leading ``~``;
    a path that cannot be expanded — an unknown ``~user``, no home in the
    environment — is the same named error, carrying the spelling as given,
    rather than a working-directory path or a bare ``RuntimeError``.
    """
    override = os.environ.get("BOARDWISE_HOME")
    if not override:
        return Path.home() / ".boardwise"
    try:
        home = Path(override).expanduser()
    except RuntimeError as exc:
        raise ConfigError(
            f"BOARDWISE_HOME={override!r}: '~' could not be expanded to a home "
            f"directory on this system ({exc}); give a full path"
        ) from exc
    if not home.is_absolute():
        raise ConfigError(
            f"BOARDWISE_HOME={override!r} is not an absolute path; a relative home "
            "would move with the working directory, so give a full path"
        )
    name = home.name
    # ``\\?\`` paths bypass Win32 name normalisation, so a trailing dot or space
    # there is a real, distinct name and must be accepted as written.
    if not override.startswith("\\\\?\\"):
        if name.endswith("."):
            raise ConfigError(
                f"BOARDWISE_HOME={override!r}: the last path component ends with a "
                "dot, which Windows strips silently — name the directory without it"
            )
        if name != name.rstrip():
            raise ConfigError(
                f"BOARDWISE_HOME={override!r}: the last path component ends with "
                "whitespace, which Windows strips silently — name the directory "
                "without it"
            )
    return home
