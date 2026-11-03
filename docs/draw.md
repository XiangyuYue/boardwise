# Drawing with boardwise (`boardwise draw`)

Two flows share this command family:

- **The drawing compiler (053–074, the main line).** You state circuit intent —
  a `CircuitSpec` (what the circuit is) plus a `PresentationSpec` (how a human
  should read it) — and `draw compile` turns it into ranked `LayoutPlan`s
  offline, behind an independent readability gate; `draw plan` / `draw apply`
  land one into the open editor, and `draw discard` takes it back off.
  Grammars today: voltage divider, RC low-pass, LDO; several modules compose
  onto one page. See **The compiled page** below and `docs/architecture.md`;
  the drawing rules it enforces are `docs/schematic-conventions.md` R6–R10.
- **The golden replay (006/006b, this document's original flow).** Redraws a
  golden board — currently the CH340 USB-UART schematic — on a **blank page of
  the open EasyEDA Pro project**, and diffs what the editor actually
  understood against the golden netlist, pin by pin. Zero differences is the
  definition of "drawn correctly"; since 006b the drawing also has to be
  *readable*, which is why the layout is replayed rather than solved.

This page is the operator manual: what the flow does, what must be measured on
the machine before it can be trusted, and the step-by-step verification
checklist. Protocol details of the actions live in `docs/bridge.md` (the
catalogue is also rendered by `boardwise bridge --help`).

## The flow (006b: layout is data)

```
golden .epro2 ──build_schematic_model──▶ DesignModel   (connectivity, 005)
              └─collect_page_layout────▶ PageLayout    (the human's geometry)
              └─collect_symbol_bodies──▶ bodies        (measured drawn extents)
                    │
                    ▼ engines.replay (pure)
  sch.geometry ─▶ measured sheet frame  ─┐
                    │                    │
                    ▼                    ▼
                ActionPlan  (placements with rotation/mirror, wires, flags, labels)
                    │  self-check: 5 hard constraints + annotation lint
                    │  gate: print plan, human confirms (--yes skips)
                    ▼
   sch.doc.new ─ sch.place_component × N (rotation verbatim)
              ─ sch.doc.save ─ sch.netlist ─▶ core.verify (F2 PLACEMENT GATE)
                   │                              │
                   │                       unmappable part? ──▶ STOP (no wire)
                   ▼                              │
              sch.place_wire ─ sch.place_power (rails) / sch.place_netlabel (signals)
                    │
                    ▼ candidate model (the verified readback is reused)
   sch.netlist (preferred) ─▶ parse  ── otherwise ──▶ sch.geometry ─▶ parse
                    │
                    ▼ core.compare (005 + F4 identity maps)
        per-pin diff + `boardwise lint` table + `export.render` acceptance image
```

**The placement gate (revision 4).** The replay copies the golden's wire
endpoints on the assumption that the library resolves to *the same symbol*. In
round 4 it did not — a 0402 became a 0603, a 470 Ω part became a 1 kΩ one, and
USB1's pins were renumbered — and every replayed endpoint missed its pin, so
the whole page was 51 differences with no drawing error behind them. Since
0.3.8 the flow therefore reads the page back **after placement and before any
wire**, maps each part's pins to the golden's (by number, else by **name** —
`core/verify.py`), and:

* **refuses to draw** when a part cannot be mapped (fail fast: a broken page
  costs nothing but a refusal);
* **remaps the comparison** for a part whose numbering drifted with the library
  (`compare_models(..., pin_maps=...)`), so a renumbered part is compared
  pin-for-pin instead of reporting every pin as a difference;
* **continues unverified** when the netlist export returns nothing — *not
  knowing* is deliberately kept distinct from *knowing it is broken*.

**Honest limit.** There is no API that returns a *placed* symbol's pin
geometry (`sch_PrimitivePin.getAll()` is empty on a schematic page, a
component's `Symbol` state is an empty object, `lib_Symbol.get` is metadata
only, and the geometry dump's `pins` is empty). Endpoints are therefore still
replayed at the **golden** pin tip: exactly right when a redraw kept the pad
positions (only the numbering moved), and caught by the gate when the mapping
cannot be built at all. See `tasks/006b-schematic-readability.md` §I-3.

**The decision that fixed 006.** The 006 solver's output was judged
"completely unusable" (wires crossing parts, no zoning, off the frame). The
answer was not a better solver: the golden `.epro2` already holds a human's
placement — every COMPONENT's `x/y/rotation/mirror`, every WIRE's segments,
every visible net-label anchor — so the default plan **copies it** onto the new
page, inheriting zoning, orientation and spacing. The generic solver in
`engines/layout.py` stays as the fallback for boards with no reference
geometry, and `boardwise draw --solver` forces it.

## Coordinate contract (rewritten by task 010c, 2026-09-18)

| Space | Convention |
|---|---|
| editor canvas | **y up**, x right — measured by a two-marker test, GUI-confirmed |
| `.epru` page as stored | **y down** — measured: `stored_y = -canvas_y` on 35 of 42 parts |
| our file space = canvas | **y up**, x right |

**One negation, at one boundary.** The parser negates the stored y as it hands its
result over (`parsers/schematic.py::_page_y` / `_page_box`); everything past that
point — replay, layout, the candidate builders, the plan — is canvas space and
negates nothing. The earlier revision of this table had the canvas and the file
labels the wrong way round, which is what made hand-authored geometry come out
vertically mirrored while the golden replay stayed self-consistent (two
negations cancelling). `engines/generate.py::canvas_pin_offsets` survives as the
named checkpoint for that boundary and is now an identity.

Pin offsets rotate **counter-clockwise** — the file's own convention, restored in
`core/geometry.py::transform_point` — and then mirror across the vertical axis;
the instance origin is added last. (The **order** of those two is a measurement
too, not a formality: 189A2 pinned it against a real board's wire endpoints and
corrected `transform_point`, which had been mirroring first. 0°/180° cannot tell
the two apart, which is why only a mirrored 90°/270° part could expose it.) Note that the *editor API* turns clockwise, so
`engines/draw.py::_editor_rotation` negates the angle when it hands it over: the
file's angle and the API's angle are opposite, and the two ends of that pair must
be changed together (010c's appendix B moved one and broke the golden). The page
offset is snapped to a 5-unit lattice so pin tips keep the grid the wire endpoints
share.

A replay is therefore byte-exact apart from one integer page translation — and
the self-check proves it: a replayed part's rotated pin tip must land on a
replayed wire (`test_replay.py::test_every_replayed_pin_tip_lands_on_its_own_wire`).

## The sheet frame is measured, never assumed

- **Frame**: the focused page's sheet primitive bbox, via `getPrimitivesBBox`
  (the sheet's `getState_*` fields carry an anchor, not an extent, so
  `Width`/`Height` would have to be *trusted* from the file — they are used only
  as a provenance-tagged fallback, and when neither is available the replay
  **refuses** instead of inventing an A4).
- **Title block**: carved from that bbox by the A-series-landscape ratio the
  reference implementation also uses (0.6 x 0.24, bottom-right), cross-checked
  against a rendered page. It is a *keep-out*, and it is deliberately
  conservative (larger than the real block).
- **Offset**: centred in the drawable area, then shifted left/above the title
  block if centring would land on it, then clamped inside the frame. Every
  deviation is a `note` in the gate output — a silent clamp is a lie about what
  the picture will look like.

## Names: labels for signals, flags for rails

xianyuyijinban's rule: **signal nets are named with net labels; I/O ports are banned**
(`sch.place_netport` stays in the catalogue for the solver's last resort, but
the replay never emits one). Power/ground rails keep the standard flag drawing.

`sch.place_netlabel` is **timeout-bounded and self-reporting**:

- the call races an 8 s deadline (`timeoutMs` may shorten it, 200..30000 ms);
- when it does not settle, the handler **reads the attribute list back** before
  failing, and says in the error whether a `NET` attribute for that name
  appeared anyway. The reference lesson: a timed-out call may well have created
  the marker, and a blind retry stacks duplicates;
- the result or the error always carries `elapsedMs` and `landedAnyway`.

**Measured 2026-09-14 on 3.2.186.b52e3e87** (see
`tasks/006b-netlabel-finding.md`): the call hung for 6963 ms against a 6000 ms
bound and **nothing landed** (`landedAnyway: false`, `matches: 0`). The cause is
in the type package, not the host: `createNetLabel` is documented **"ADD since
EDA v4"** and this host is the v3.2 line — so it is not flaky here, it is a call
that can never settle. The timeout is what turns that into a reportable failure
instead of a dead action slot.

The type package has **no path for a *connectivity-bearing* signal-net name**:
`createNetFlag` accepts only `Power / Ground / AnalogGround / ProtectGround`, and
`sch_PrimitiveNetLabel` is not a namespace on this host. The only visible form
the package offers is `sch_PrimitiveText` — a decoration with no connectivity.

## Naming strategies (006b revision 3; default changed by 134, 2026-10-08)

xianyuyijinban's rule is fixed: **signal nets are named with a visible label, never an
I/O port**; power and ground keep their flags. What varies is *how* the visible
name is realised, and — since 134 — *whether* one is placed at all.

**Why this stopped being a cosmetic choice.** In EasyEDA Pro a net label is
equivalent to a network port: drawing one **creates an electrical connection**.
So labelling every signal net was not "a bit busy", it was burying implicit
connections all over the page *and* masking routing mistakes. An engineer's
complaint that the AI-drawn flyback came back as a screenful of network
identifiers smeared over parts and wires is precisely this.

| Strategy | Wire carries the net? | Signal name primitive | Status |
|---|---|---|---|
| `wire` | yes (`WireStep.net`) | none | **verified** — measured 2026-09-14: the editor's netlister honours the wire's own net attribute (3 resistors + a wire tagged `PROBE_WIRE_NET` → `R1.2/R2.2/R3.1 → PROBE_WIRE_NET` in `getNetlistFile`) |
| `auto` | yes (`WireStep.net`) | only on long or cross-page nets | **default** (134) — see below |
| `text` | yes | `sch.place_text` (`sch_PrimitiveText`), one per signal net | was the 006b default; visible but decorative, and every report line says so |
| `label` | yes | `sch.place_netlabel` (`createNetLabel`) | **dormant** — documented *v4*, never settles on 3.2.186; kept behind its timeout |
| `none` | no | none | for a bare-connectivity run |

### `auto`: a name only where a name is the only way to read the net

A signal net is named on either of two grounds (岳裁 2026-10-08，长距离/跨页才打):

1. **long distance** — its routed wire runs past `LONG_NET_LABEL_UNITS`
   (1500 canvas units ≈ 38 mm at 1 unit = 1 mil). The threshold answers *how
   far can a reader follow a net*, not how tidy the page looks: past roughly a
   third of an A4 landscape sheet a net has to be traced, and tracing is what a
   name saves. It is a **house rule pending confirmation of the exact number** —
   one named constant in `engines/generate.py`, so moving it moves the policy
   for every page at once. Measured on the CH340G golden board the longest
   signal net runs 1395 units, i.e. *just under* the threshold, so that page
   now carries rail flags only.
2. **cross page** — the net's members sit on more than one sheet
   (`DesignModel.unproven_nets`; an empty page tuple counts too, because it
   means "seen twice, page ids unavailable" — issue #19).

Everything else is read off its wires, as a schematic is meant to be read. The
**wire still carries the net name** under `auto`: the ruling removes the visible
decoration, never the electrical name (measured 2026-09-14 — the editor's own
netlister reads the wire's net attribute).

### Where a placed label is allowed to land

Every label that *is* placed goes through `layout.clear_label_point`, which
walks the on-wire candidates of *that* net — never off it, because a name off
its wire is a floating marker rather than a name — and scores each by the
clearance its predicted text box has from every foreign component box, every
foreign wire, and every name already placed. When nothing along the route
clears the bar, the plan records that in `notes` instead of dropping a label
somewhere it reads as a smudge: a nameless net is legible, an unreadable one is
worse than either.

**Power/ground flags go through the same search, and that is 173/A's fix.** The
sentence above used to be true of signal names only: under `auto` a rail's flag
was pinned to the router's own candidate (`route.attach`) without the search
ever looking at it, and 163a/E3 caught the consequence on the golden page — the
`+5V` flag's anchor sat on another net's wire, 5 units from the electrical
anchor, which is the `LABEL_ON_FOREIGN_WIRE` reading (a short to a reader). The
two are one search now, with one difference in the bar: a signal name may refuse
a placement the search cannot clear (`LABEL_CLEARANCE`, 20 units — a
readability preference), while a rail's flag is *the* naming of that net, so it
is placed at the cleanest point the search finds under `margin=0.0` — it may
never land on a foreign wire, a body, or another name, but it is never dropped
in exchange for a preference (`naming_steps_for` in `engines/generate.py` is the
whole of that policy).

`boardwise draw --naming <strategy>` and `boardwise lint --naming <strategy>`
select it; an unknown value falls back to the default **and the fallback is
reported**, never silent. The gate printout and the acceptance report both name
the strategy, and any strategy that draws a text name carries an explicit
"(decorative, NOT native net labels)" disclaimer.

The golden replay lints clean (**0 violations**) under all five strategies. That
is a deliberate invariant, not a coincidence: the human's wire ends where the
human's label sits, so the validator's legal terminals include the golden
page's flag / label anchors regardless of whether the current strategy draws a
name there. Deriving them from the plan's naming steps alone made the two
strategies that draw no name report ten phantom `ENDPOINT_NOT_TERMINAL` rows.
On the replay path `auto` decides **whether** a golden label is drawn; the
human's own anchor still decides **where**, because a replay that moved the
human's labels would not be a replay.

## Two design sources (008a added the second)

| Source | Flag | The design comes from | The diff answers |
|---|---|---|---|
| golden replay | `--from <golden.epro2>` | the golden page's own layout (006b) | "did we draw what the golden has?" |
| **assembly** | `--spec <board spec>` | block templates + a spec (`docs/blocks.md`) | "did we draw what the **specification** says?" |

With `--spec` the spec first passes the **product validation gates**
(009-M0 P0, `docs/validate_spec.md`: sources, levels, power tree, and pin
budget when a table is given) before anything is assembled — a refused spec
draws nothing, the bridge is never opened, and the report's `spec sha256:`
prefix binds the verdict to the exact bytes that were checked (nothing is
cached; an edited spec is re-judged on the next run).

With `--spec`, `--golden` turns on the **double check** that runs before a
single bridge call: `compare` the assembled spec netlist against the golden
(fixture plus its correction sidecar). A mismatch aborts the run, so a wrong
specification cannot mutate a project. `boardwise lint --spec …` and
`boardwise compare --spec …` are the same two checks without an editor.

`compare` applies a corrections sidecar **only when `--overrides` names one**
(its task-005 contract is a raw file-against-file comparison); `draw` keeps
defaulting to the sidecar beside the fixture, as it always has.

## The acceptance image is a document render

`export.render` calls `sch_ManufactureData.getExportDocumentFile(fileName,
fileType, typeParams, object)` — a *document* render. `export.screenshot`
(`getCurrentRenderedAreaImage`) returns **cached frames** on this host (the
reference measured two byte-identical captures across different board states),
so it stays available as a diagnostic of the viewport and is never evidence.
`format: png|svg|pdf` (default png) selects the render type — svg is the
vector, zoomable option — and `scope: page|selection|project` (default page)
selects what is rendered; `scope: 'selection'` requires `ids` and selects the
primitives first. A multi-page project can come back as a zip; the action
reports `format: 'zip'` rather than saving an archive with a `.png` name.

**Ported 2026-09-18** from the reference's live-verified `schematicExportImage`
(reference issue #166). Before that, this action targeted `getPngFile`, which
answers `NOT_IMPLEMENTED` on this host even though the package marks it *added
in v3.2.183* and the host reports 3.2.186. One trap the type package cannot
warn about: the `object` argument must be the literal strings `'Current
Page' | 'Current Page Selected Items' | 'Project'` — the values the `.d.ts`
declares make the host promise never settle (a stuck 1% toast), which is why
the connector races the call against a 30 s deadline and its timeout error
says to reload the document to clear the toast.

## Offline lint (self-produced detail)

`boardwise lint --from <golden.epro2> [--plan replay|solver] [--json]` runs the
whole plan — layout, routing, naming — with **no bridge and no editor**, and
prints one row per violation plus a tally:

| Code | Meaning |
|---|---|
| `BOX_OVERLAP` | two parts' measured drawn extents intersect |
| `OUT_OF_SHEET` | a part's box leaves the measured frame |
| `PLACEMENT_ON_TITLE_BLOCK` | a part's box enters the title block |
| `WIRE_THROUGH_BOX` | a wire's interior crosses a part's box |
| `NON_MANHATTAN` | a diagonal segment |
| `WIRE_OUT_OF_SHEET` / `WIRE_ON_TITLE_BLOCK` | a wire endpoint outside / on the block |
| `ENDPOINT_NOT_TERMINAL` | a wire end that is neither a pin tip, a junction, an annotated end, nor a short overhang |
| `CROSS_NET_SHORT` | one net's endpoint lands on another net's wire (the editor junction-dots it) |
| `WIRE_TOO_CLOSE` | two nets' wires running **alongside** each other closer than `WIRE_CLEARANCE` (136) |
| `SEPARATION_GIVEN_UP` | a net that only routed after the retry dropped the router's wire-separation preference (136) |
| `LABEL_FLOATS` | a flag / label not on any of its own wires |
| `LABEL_ON_COMPONENT` | an annotation box overlaps a foreign part |
| `LABEL_OVERLAP` | two annotation boxes intersect |
| `LABEL_ON_TITLE_BLOCK` | an annotation inside the title block |
| `LABEL_ON_FOREIGN_WIRE` | an annotation box touches **another** net's wire — a name drawn across a stranger's wire reads as a connection that is not there (163a) |
| `WIRE_OVERLAP` | two nets' wires coincide (gap ≤ 0) — a true short, unlike the advisory `WIRE_TOO_CLOSE` (163a) |
| `PINS_UNPLACED` | netlist-connected pins no wire reaches — the page would not equal the netlist (163a) |

`LABEL_ON_FOREIGN_WIRE` has **two paths, one ruler** (168). The solver / terminal
check (`layout.annotation_anchor_violations`) keeps it **blocking**: a generated
page is ours to fix, so a name pressed on a stranger's wire must not be drawn. The
**replay** path measures the same defect on the **glyph boxes the replayed page
really draws** (`layout.annotation_foreign_wire_contacts`), but a replayed page is
the human's own, so there it is an **INFO observation** written into
`plan.notes` ("INFO (observation, not a refusal) — [LABEL_ON_FOREIGN_WIRE] …") and
printed by `boardwise lint` / `draw plan`. It is deliberately *not* an entry in
`plan.violations`: that list is the gate, and an observation must not be in it.

`boardwise draw` runs the same lint as part of its self-check and **refuses to
execute** when anything fails — the whole point is that the burden of proof
moved from the reviewer's eyes to the generator.

Parts are bounded by their **measured drawn geometry** (`collect_symbol_bodies`:
the symbol's `RECT`/`POLY`/`CIRCLE` records), not by their pin extents. This is
not cosmetic: with a pin-extent box inflated by 20 units, the human's own
decoupling capacitors register as 19 overlapping pairs, and the wires reaching
their IC register as 25 crossings. With the drawn extent and zero pad, the
human's board lints clean — which is the calibration that makes the lint
trustworthy at all.

## Machine probe (006b additions)

Prerequisites: connector **0.4.2** sideloaded, daemon restarted (the action
catalogue grew — a stale daemon answers `UNKNOWN_ACTION`), editor open on the
project to draw into.

```bash
# 0a. what does the editor's API actually expose? (read-only, always first)
#     NAMED reads — immune to the exotic host objects that killed the first
#     enumeration run with "reading 'prototype'". `checks: true` verifies the
#     type package's declared surface for the namespaces the roadmap uses; the
#     table is generated by tools/api_names.py into connector/src/api-names.ts.
PYTHONPATH=src python -m boardwise.cli bridge call --action sys.probe \
    --params '{"checks": true}'
#   -> checks: {<ns>: {present, checked, missing, status: {member: typeof},
#                      arity: {member: fn.length for the functions}, notes?}}
#   `status` uses the language's own vocabulary — function / object / undefined —
#   plus `threw: …` and `namespace-absent`, so "undeclared" and "the read itself
#   failed" stay distinguishable. `arity` is the declared `fn.length`, reported
#   for the members that are functions — a hint, not a verdict (a wrapper loses
#   the real arity). A method the package marks `ADD since EDA v…` that reads
#   back `undefined` gets a `notes` entry carrying the contradiction.
#   Exit is 0 whether or not names are missing — an answer is the product.
#   Looking for: getExportDocumentFile on sch_ManufactureData (the render path
#   since 0.4.2), and the page/tab switch on dmt_EditorControl / dmt_Schematic.

# 0b. enumerate when you need a name nobody predicted (predictive, but it can
#     fail on a hostile object; one bad level costs one `errors` line, not the call)
PYTHONPATH=src python -m boardwise.cli bridge call --action sys.probe \
    --params '{"namespaces":["sch_ManufactureData","dmt_EditorControl","dmt_Schematic"]}'
#   -> namespaces: {<ns>: {present, ownNames, functions, data, errors?}}

# 1. the measured frame (sheet bbox + which namespaces exist)
PYTHONPATH=src python -m boardwise.cli bridge call --action sch.geometry > frame.json

# 2. does the wire's own net name stick? (this is the `wire` strategy's basis)
PYTHONPATH=src python -m boardwise.cli bridge call --action sch.doc.new
PYTHONPATH=src python -m boardwise.cli bridge call --action sch.place_wire \
    --params '{"points": [[0, 100], [200, 100]], "net": "PROBE_NET"}'
PYTHONPATH=src python -m boardwise.cli bridge call --action sch.geometry

# 3. the net-label probe: bounded, and it reads back what landed
PYTHONPATH=src python -m boardwise.cli bridge call --action sch.place_netlabel \
    --params '{"x": 200, "y": 100, "net": "PROBE_NET", "timeoutMs": 8000}'
#   outcome ok / elapsedMs / landedAnyway       -> the label path works
#   TIMEOUT + landedAnyway true                 -> it landed; the API just never answers
#   TIMEOUT + landedAnyway false                -> no label path on this host

# 3b. the decorative text fallback (the `text` strategy uses this; the `auto`
#     default only places one when a net is long or cross-page)
PYTHONPATH=src python -m boardwise.cli bridge call --action sch.place_text \
    --params '{"content": "PROBE_NET", "x": 200, "y": 80}'

# 3c. placement: a first library resolution can exceed 30 s and STILL land.
#     The action reads the page back and says so — never retry on TIMEOUT.
PYTHONPATH=src python -m boardwise.cli bridge call --action sch.place_component \
    --params '{"lcsc": "C14267", "x": 300, "y": 300, "designator": "U9"}'
#   ok                     -> {uuid, device, resolvedBy, elapsedMs}
#   TIMEOUT landedAnyway   -> true: it is on the page, do NOT resend
#                            false: nothing appeared; `near` lists what is close by

# 4. the acceptance render (format png|svg|pdf, scope page|selection|project;
#    selection needs ids; svg is the zoomable option for the readability gate)
PYTHONPATH=src python -m boardwise.cli bridge call --action export.render
PYTHONPATH=src python -m boardwise.cli bridge call --action export.render \
    --params '{"format": "svg", "scope": "page"}'
```

## Acceptance (three gates, all three required)

1. **`compare` per-pin: 0 differences** — the existing 005 referee, printed by
   the draw report (`no differences — designs match`).
2. **Self-produced lint: 0 violations** — printed before and after the run;
   `boardwise lint` reproduces it offline.
3. **xianyuyijinban reads the `export.render` image** and judges it readable — the
   human gate the solver failed. The viewport screenshot is not evidence.

Verification steps:

1. Stop anything on 61190 that is not the current daemon (`netstat -ano |
   grep 61190`), then `boardwise bridge start`.
2. Sideload connector **0.4.2**, restart the editor, open the **test** project,
   `boardwise bridge status` must say `connector: connected`.
3. `boardwise lint --from tests/fixtures/ch340_golden.epro2` → `0 violations`.
   (Offline, no editor — do this first.) Repeat for
   `--naming auto|wire|text|label|none`: all five must be 0, because the
   human's geometry does not depend on our naming policy.
   **Task 008a adds the assembled path**, also offline:
   `boardwise lint --spec blocklib/specs/ch340g_usb_uart.json` → 0 violations,
   and `boardwise compare --spec blocklib/specs/ch340g_usb_uart.json --golden
   tests/fixtures/ch340_golden.epro2 --overrides
   tests/fixtures/ch340_golden.overrides.json` → `no differences`.
4. Create a fresh page **after asking xianyuyijinban** (new rule: never create a page
   unprompted), then `boardwise draw --from tests/fixtures/ch340_golden.epro2
   --render out.png` (default `auto` strategy — signal nets are named only
   when long or cross-page) — or, for the 008a acceptance,
   `boardwise draw --spec blocklib/specs/ch340g_usb_uart.json --golden
   tests/fixtures/ch340_golden.epro2 --render out.png`. Do **not** draw into
   P1 — the
   probes above left primitives on it. Read the gate output: plan source
   `golden replay`, the measured frame, the offset note, 17 placements with
   their rotations, the naming line, 45 wires.
   In `--spec` mode the report opens with the assembly (each block, where it
   went, every port and connection) and with the double check's verdict.
   If the netlist export fails and the flow falls back to geometry, the report
   prints a **page census** (`page census (netlist failed): <type>=<n>, …`) —
   that is what tells "a net-port poisoned the exporter" apart from "our parser
   is wrong". Report the census; do not guess.
5. The report prints the candidate source, the **placement check** line, failed
   actions, then the per-pin diff. Read the placement check first:

   ```
   placement check: 17 parts, 0 drifted with the library version, 0 unmappable
   ```

   `0 unmappable` is the pass mark — anything else means the flow **stopped
   before drawing a single wire** and printed why (`✗ unmappable parts …`).
   A non-zero **drifted** count is not a failure: it means the library redrew
   those symbols, the diff is being compared by pin name, and the wire
   endpoints stay at the golden pin tips (see the honest limit above).
   If the netlist export failed and the flow fell back to geometry, the report
   prints a **page census** (`page census (netlist failed): <type>=<n>, …`) —
   that is what tells "a net-port poisoned the exporter" apart from "our parser
   is wrong". Report the census; do not guess.
6. The diff below it: **0 differences** is the pass mark.
7. Open `out.png` and read it as a schematic: zoning inherited from the golden,
   wires orthogonal, every rail flagged, every signal name on its wire. The
   `text` strategy's names are decorative — if the readability gate rejects
   disguised text, flip to `--naming wire` and re-run: zero rework, the wire
   already carries the net.

## Persistence: the facts about a write (M0-P0d, extended 2026-09-18)

"The write API said ok", "the editor's page is right" and "the file kept it" are
different facts. The report names which one it established, and prints the state
with its qualifier attached:

| state | established by | meaning |
|---|---|---|
| `not_placed` | zero write attempts acknowledged | the page was never touched |
| `unknown` | the run stopped with writes acknowledged or unanswered | what is on the page **cannot be stated** |
| `placed` | the netlist compare | written, and the editor's own readback agrees. **Not saved** |
| `saved_unverified` | a `sch.doc.save` that answered ok | the editor accepted a save; nothing checked the disk |
| `saved_verified` | a close-and-reopen in which the snapshot's content is all still present (content added afterwards is reported as extras, not failed) | the content reached the file |

`unknown` is not a weaker rung on the ladder — it is the statement that the
ladder cannot be climbed. It exists because of a measured defect: killing the
daemon mid-draw left **five parts on the page** while the report said "nothing
was written". A reader who believed that would redraw onto a page that already
had them, ending with two sets of parts on one sheet. So the one state that
asserts an *absence* requires positive evidence of the absence: zero write
attempts acknowledged **and** zero unanswered.

Two properties are structural, not oversights:

* **`draw` tops out at `saved_unverified`.** `saved_verified` needs a reopen, and
  the bridge cannot perform one: `doc.open` is a `read` that moves the focused tab
  without reloading it from disk, and there is no close-project action in the
  catalogue. The report therefore says "NOT verified on disk" out loud rather than
  borrowing the word "saved" for a state it never reached.
* **A failed write is not "nothing happened", in either of its two shapes.** A
  **timeout** means the daemon stopped waiting without telling the editor to
  cancel; a **disconnect** means the answer never arrived because the connection
  died in flight. Both leave the outcome unknown, so every write the flow issues
  goes through a timeout-aware wrapper: on either failure it reads the page back
  (`sch.geometry`), reports what it saw — or that it **could not look**, which is
  not the same as "it is empty" — and never re-issues the call, because a retry
  after a write that landed is a duplicate part. Transport deaths are normalised
  into `BridgeError(DISCONNECTED)` by the layer that owns the transport:
  `bridge/client.py` when the daemon connection dies, and `bridge/daemon.py`
  when the editor's window closes while the call is already on the wire (#43 —
  reporting that second case as `CONNECTOR_ERROR` is what used to make an
  in-flight write read as `not_placed`).

The exit code for an unknown outcome is **3** ("cannot say"), distinct from 2
("nothing was executed"), and it **outranks both 0 and 1**: "the diff happened to
match" and "the diff differed" are claims about a page whose contents we are no
longer sure of.

The third state is reachable only through a human step, and
`boardwise persistence` turns that step's result into an exit code —
see `docs/persistence-baseline.md` for the four-scenario checklist.

## Known limits (006b scope)

- The replay reproduces the golden's *drawing*, so it inherits the golden's own
  quirks (a 4-unit overhang past one VCC junction, unlabelled local nets). The
  lint's tolerances are documented next to the codes; nothing is silently
  "fixed" away, because a replay that edits the source is no longer evidence.
- The title block is a ratio-derived keep-out, not a measured rectangle: the
  API exposes no title-block bbox. It is conservative, and a violation inside it
  is reported with that provenance.
- Annotation marker boxes are predictions (flag glyph = measured symbol body +
  a text band; labels = 6 units per character). The reference implementation's
  rule applies: generation and checking must use the same ruler, which they do.
- Rotation is replayed verbatim; a host that applies `rotation` differently from
  the file would show up immediately as a per-pin diff (and as a failed pin-tip
  invariant in the self-check).
- No PCB anything (task 007). The generic solver remains for boards without
  reference geometry, and is still "legal but ugly" by design.

## The compiled page (057: `draw compile|plan|apply` on a page, `draw discard`)

054 landed one compiled module; 056 compiled several modules into one page
offline; 057 lands that page. There is **no new landing command and no new
flag** — the three `draw` commands take a page on the same flags:

| input | `draw compile` | `draw plan` | `draw apply` |
|---|---|---|---|
| a presentation with ≥2 modules, a `flow`, a module `grammarRef` or a page lock | page compiler; `candN.page.json` + framed `candN.svg`; `--page-box` required | the chosen page's `plan` field → the same `draw-module` plan; `<plan>.page.json` written beside it | — |
| a page document (`kind=boardwise-page-layout-plan`) | — | — | as `--layout` (digests its `plan`), or as the positional (needs `--circuit/--presentation/--profiles` and `--page`/`--new-page`; the plan is built at apply time) |

**A non-empty page** (`draw plan --page`): every primitive already on the page
(part, wire segment, flag, net label — parts and labels at their `bboxIds`-measured
extent, anything unmeasured at an assumed ±50 box the notes name) becomes a
keep-out, and the arrangement moves off them as a rigid body
(`PageCompileBudget.relocate_around_keepouts`; nothing is squeezed). A page the
census fills is `presentation-poor`, the keep-out named by what it is ("existing
R5 c-17"). After the landing, **every primitive that was on the page before is
compared field by field** (designator, value, LCSC, net, origin, pose; a wire's
point list; a label's net, text and pose) — one changed item is exit 2 and no save
(`range.outOfScope`). This applies to every `draw apply`, single module or page.
The C5 digest behind all of this counts every section a `sch.geometry` dump is
contracted to carry (`components`/`wires`/`pins`/`netlabels`) plus the parts the
designator set deliberately drops (`R5?`): a kind the census does not count is a
change no guard can see.

**Page locks**: a `userLocks[]` entry with `"scope": "page"` (x, y only — the pose
is the module's) pins the part to that page point in every candidate: the
module's origin is `P − L(generation)`. A lock point off the page, two locks in
one module that disagree, a locked frame off the page / on a keep-out / on
another locked frame are `presentation-poor` naming the lock(s). A module lock
and a page lock may sit on the same part.

**Shared nets (G4)**: a net that spans modules is named at each end (label or
flag); this host cannot place a net label, so a label whose point no planned wire
reaches becomes a 10-unit **named stub** (declared in the plan's downgrades) —
otherwise the pin sits on an unnamed net and the two modules' same-named nets
never merge in the editor's project-wide netlist. The apply report's
`verification.nets` lists every net's live name(s), `crossModule` and `oneNet`;
findings may only shrink, judged by identity (`rule|severity|designator|pins|named
nets`), never by count. 145d: a **single-module** plan stakes the same stub for a
net that has a name and **no conductor at all** (a one-pin net like the flyback's
`GATE`/`VFB_NF`), because the editor's netlist otherwise holds neither the name
nor the pin — the label's downgrade used to state "the name is on the wire" over a
plan that drew no wire.

**Wire ends and vertices (145d)**: the canvas leg asks that **both ends of every
planned wire be vertices of the page's own wiring for that net**. The host merges
collinear wires and keeps a node only where a run ends or something else attaches
(pit 32), so the plan is built to state only points the page will hold: a run
another wire of the same net already covers is **not drawn** (it adds no
conductor), and the wire a flag attaches **inside** of is cut in two at that point
(two wires, one net, connected). Measured on 145c's landed page: the flag's own
anchor `(280,785)` survived the host's merge while the bare run end `(280,760)`,
lying on the same rail, did not.

**`draw discard <plan.json|page.json>`** takes one landed drawing back off its
page, and only that: a part is the plan's by designator + position + value (the
LCSC number for a pre-055 plan), a flag by net + point, a wire by net and *every*
point lying on the plan's own wiring (a primitive the host merged with somebody
else's wire, pit 32, is never deleted). One mismatch refuses the whole batch
(exit 4, nothing deleted). Lines go first, then flags, then parts (≤30 ids per
call, a split is reported); the page is read back — targets gone, everything else
unchanged. A second run answers `nothing_to_discard` (exit 0). `--save` saves; a
timeout is read back and never retried (exit 3). A page document is discarded
with `--circuit/--presentation/--profiles`, its parts found by position, prefix
and value.

Offline evidence: `tools/057_scenarios.py` (writes `outputs/057_offline/`); the
real-machine steps for E1–E7 are `tools/057_live_runbook.md`.

### Service interval for a uniquely served shunt (543B)

`serviceLayout` is an optional top-level PresentationSpec object; it is **not
written when absent**, so every document compiled before 543B keeps its bytes,
digest and drawing. It carries one key:

```json
"serviceLayout": {"pinGap": 30}
```

`pinGap` is a positive, finite number of canvas units. When stated, the compiler
asks the read-only decoupling analysis (`engines/layoutroles.py`, 543A) about each
two-terminal **shunt** branch and uses `pinGap` as the distance between that
shunt's service pin and the host pin it serves, instead of the branch ladder's
first rung. The interval is fixed, not a rung: the ladder's per-branch index does
not add to it. The side, pose and wire are still constructed from the symbols,
the net partition and the relations; the key states a distance, never a
coordinate.

It is consumed only when the relation is `served`, the host is the branch's
owner, the served net is the branch's own shared net, the service pin is the
branch's own shared pin, and the host has **exactly one** pin on that net. An
ambiguous host, several hosts or several equivalent host pins are left to the
ordinary ladder — the key is not a licence to guess. The normal readability and
lint gates still run unchanged.

### Service channels, paired labels and final-plan bounds (543C–543F)

These are all opt-in behaviours; a document that states neither `serviceLayout`
nor the corresponding native text options keeps its previous drawing. The
current validation case is the CH343 page specified in
`evidence/543d2/effective.presentation.json`, with regression coverage in
`tests/test_543c_service_channels.py`, `test_543d_label_layout.py`,
`test_543d2_usb_pair.py`, `test_543e2_service_siblings.py` and
`test_543f2_changeplan_bounds.py`.

- **Agent owns semantic islands.** Merging the two core decoupling capacitors
  into the CH343 island and splitting the CC pull-downs into their own island
  are PresentationSpec decisions, not automatic island inference. The compiler
  consumes that intent and regenerates every coordinate and conductor.
- **Service channels are hard reservations.** On an island with a uniquely
  served shunt, the return pad/lane and the measured label boxes are reserved
  before routing; labels also avoid the promised ground-flag seats. A later
  shunt on the same host pin may take a perpendicular seat at the same
  `pinGap`, but if no legal seat exists the compiler returns `layout-unsat`
  instead of sharing an origin and reporting a false pass.
- **Native labels follow the declared reading side.** With both
  `serviceLayout` and `textPlacement: native-attr`, local label pins must leave
  toward the module's stated side. Duplicate names remain on their wires and
  keep their net, but only one is visible; page ports prefer that visible name.
  The CH343 case therefore has D+/D− to the right of the mirrored USB
  connector and to the left of the CH343, with straight landing stubs.
- **Bounds apply to the final ChangePlan, not only the LayoutPlan.**
  `drawapply.module_plan(..., page_box=...)` rejects every stub candidate whose
  segment endpoint leaves the sheet and tries the next direction/length; if no
  candidate fits, the label is refused by name. `draw plan` supplies the actual
  page box (and the page-document path supplies `page.page_box`). Passing no
  `page_box` preserves the previous behaviour. This covers stubs generated only
  while the final ChangePlan is built, which is where the P30 `x=-5` defect had
  escaped the LayoutPlan-only check.

The first P31 landing has `draw lint` **0E/0W/0I** and independent per-pin
**55/55 connections + 3/3 NC**, but its CC1 carrier makes the host print CC1
vertically. It is therefore an experiment, not a completed replacement for
P29. A generic second topology, the second same-pin decoupling layout, and
close/reopen persistence remain unverified. Evidence: `evidence/543f2/`.

## Flag and naming rules on compiled pages (060–074)

After 057 landed pages, xianyuyijinban ruled five drawing conventions on the
live renders; they are compile-time hard constraints, written up as R6–R10 in
`docs/schematic-conventions.md`. The visible consequences on any compiled page:

- capacitors hang on their owning pin's physical side (input cap by the input
  pin, output cap by the output pin — even when the symbol duplicates the pin
  on the far face);
- same-role pins on opposite faces of a body join **by name** (a short stub
  with a flag or label each), never by a wire across the part;
- every power net carries at least one flag, flags are always vertical
  (0°/180°), and a wire on a flagged net carries no text name of its own;
- a flag lead never crosses a foreign net's conductor — the compiler rejects
  such a candidate outright and reports `layout-unsat` rather than shipping a
  crossing.

The apply report's `verification.nets` and the readability evidence are what
prove these held; the renders under `evidence/074/` show the before/after.


## 落图 SOP（自 SKILL.md §3.3 迁入，2026-10-06 减重 124）

053 阶段 B 的编译器离线算出**画法**（`LayoutPlan`：器件+姿态+折线+旗标+文字 bbox，
`engines/drawcompiler.py`），054 把一张画法落进编辑器的一页。三条命令：

```bash
boardwise draw compile --circuit C.json --presentation P.json --profiles LIB.json \
    --page-box 0,0,1170,825 --out outputs/054_x/previews      # 离线：ranked 表 + 四分类 + SVG
boardwise draw plan    --circuit … --presentation … --profiles … --page-box … \
    --page <uuid> --project test --lcsc R1=C25744 --out plan.json   # 一候选 → ChangePlan
boardwise draw apply   plan.json --project test \
    --circuit … --presentation … --profiles … --layout <cand1.layout.json> \
    --render render.png --json apply.json                     # 真机：守卫 → 落图 → 回读 → 保存 → 出图
```

同族另外两条，别漏：**`boardwise draw lint --page …` 是落图之后的机器闸**（只读：九条几何
谓词——压线/重叠/出界/同名导线段等，111 起；真机快照或 `--snapshot` 捕获件都吃。
P1 的 48E/20W/21I 验收基线就是它量的——**画完一页先过它再交付**。
**168 的严重度口径**：人手页/既有页只观察提醒——L8 横放旗标（90/270）报 INFO，
不进退出码（`FLAG_VERTICAL_ROTATIONS` 仍是 {0,180}，横放仍要报；非直角斜置如 45°
仍是 ERROR）；生成器产出的页不受影响，它的旗标朝向闸在 `draw apply` 的⑮核对，
不在这条只读谓词上）；
**`boardwise draw propose`**（109 A4，纯离线）把一份 DesignIntent 合同提成
PresentationSpec 草稿（模块清单 + flow + 角色），是「意图 → 画法」这条链的入口，
compile/plan 的 `--intent PATH` 消费同一份合同（见下）。

**支路顺序的三个来源（095 A4 起）**：`power-entry` 画法里「哪条支路贴入口」按
`PresentationSpec.modules[].branchOrder` > **DesignIntent 合同** > 位号序 读；后两者都
没说话时与 088/088b 逐字节一致。合同侧读 `decisions[subject=<支路>]` 的 prose 或
`blocks[].kind`（写明 `tvs`/`clamp`·`钳位`/`泄放` 才算），原文 + 出处 + provenance 进
绑定 evidence，`ai_asserted` 照走但标注草稿。**声明与合同不一致 → `circuit-invalid` 拒绝、
两个来源的原文并列**（谁错人裁，不会自动二选一）。`draw compile` / `draw plan` 用
`--intent PATH` 把合同交给编译（`dc.compile(..., intent=…)`）；**只认显式路径**——编译发生在
读工程之前，用户级默认落点 `<home>/design-intent/<projectUuid>.json` 那时还没有 uuid；
页级（057）路径本批不读合同，给了 `--intent` 会明说没读。

**落图前必须先有"实测符号库"**（本批最关键的一条工序，C1/C2 都是这么过的）：
编辑器**不提供**库符号几何的读接口（`lib.symbol.get` 明说 no geometry），所以
`--profiles` 的那份库要**先在真机上量**——在临时页上放一颗真器件（`sch.place_component
--params '{"lcsc":"C25744","x":400,"y":300}'`），读 `sch.component_pins`（引脚偏移 + PinLength）
和 `sch.geometry --params '{"bboxIds":[<id>]}'`（实测外框 = body），删掉这颗探针件，
再把量到的数字写成 `SymbolProfile`（`source` 里写清量法与出处）。
实测：C25744（0402 10k）引脚 ±20、body ±10.5×±4.5；C1525（0402 100n）引脚 ±20、body ±10.5×±8.5。
拿**竖排 ±50** 这类没量过的 profile 去落图，引脚回读必然点名不符（C6 现场）。

**apply 的执行序**（`_draw_apply_flow`）：① 页（`--page` 或 `--new-page`；plan 未绑页又没给页 → exit 5；
**plan 已绑页或已给 `--page` 时再给 `--new-page` → 显式拒 exit 5**，绝不静默落在绑定页上——143d）
→ ② 守卫（双 spec 摘要 + 布局摘要 + 库几何表 + 页身份；**显式** `--expect-census` 也在这关）
→ ③ 探针（plan 自己的 postconditions，双证齐全 = `already_applied` exit 0 零写入）
→ ④ 页既不是 plan 成品也不是 plan 基线 → `canvas_changed` exit 4 零写入
→ ⑤ 位号池（页面 ∪ 工程导出）→ ⑥ 放件 → ⑦ **写 Value**（055 起：plan 用 `valueKey` 逐件
声明，无 key/无值**不写不报**；`sch.set_component_attribute` 既有通道零新增）
→ ⑧ **引脚回读**（容差半格，同一把 geometry 读同时做值回读；引脚不符、值写不进/回读不符
**都在拉线前**停住 exit 3）→ ⑨ 走线（`net` 承载网名）→ ⑩ 旗标（180：**地旗**按库符号
`Ground-<net>` 走 `sch.place_component`，库无同名符号或**电源旗**回落 `sch.place_power`；
回落与「两族同形」写 plan notes，不拦、不改严重度）→ ⑪ 双证回读
（活网表按**本 plan 自己的引脚**判分区；页面外同名同网只报 `sharedWithOutsidePins`）
→ ⑫ 范围（无删除 → 导出新鲜）+ findings 分级拦（ERROR 必拦 / WARN 需 `--force` / INFO 只报告）
→ ⑬ 保存（`saved_unverified`，要 `saved_verified` 得走 `boardwise persistence` 的关闭重开）
→ ⑭ `export.render` 出图（`already_applied` 也出图：图是证据不是写）
→ ⑮ **旗标朝向核对**（坑 42 的手法、坑 43 的事实）：出图时一并要 `format=svg`，解
`c_partid="netflag"` 组逐颗读"连接点 → 字形往哪边伸"，与 plan 里每颗旗标的 `rotation`
对表；GND 与 PWR-* 两家自然姿态相反，离线预览画的是统一约定盒、看不出这个差
（照抄姿势与判据见 `outputs/064_railflag/`）。

退出码：**0** 落图并被双证确认（或 already_applied 零写入）/ **2** 承诺的效果不在（写被拒、
保存被拒、range/旗标数不对、findings 仍被拦：ERROR 有、或 WARN 有而未给 `--force`）/ **3** 页状态不可陈述或回读不符（超时、拔 daemon、
引脚/值回读不符、postconditions 不满足——**在拉线前**停）/ **4** 守卫拒绝（摘要 stale、库几何变了、
页不是 plan 的、画布被动过、位号被占、半成品件在页上）/ **5** plan 或输入不可用。

幂等与 stale：`draw apply` 同 plan 再跑 → `already_applied` 零写入（C4）；手工动过画布再跑 →
exit 4 零写入（C5）；库几何不符 → exit 4 零写入（C6，写前那条腿用 `--profiles` 的库文档，
编辑器侧那条腿只能靠放完后的引脚回读，所以它是 exit 3 且件已放）。

**053R：`attributeMoves`（可选，公开计划的一部分）**。plan 的 `change` 里可以带一个**可选**数组，
声明「哪几行属性文字要挪到哪里」，每一行是 `{"moveVersion": 1, "owner": ..., "role": ..., "to": {...}}`：

- **空态就是旧行为**：没有 `attributeMoves` 键（空列表也不写这个键）时，plan 的字节、apply 的动作序
  （不调 `sch.list_attributes` / `sys.probe` / `sch.move_attribute`）、CLI 参数、退出码和报告字段
  全部与 053R 之前一致；报告里也不会出现 `attributeMoves` 段。
- **行级版本只认 1**。`owner` 只许 `{"kind": "part", "specId": <本 plan 放置的 specId>}`
  或 `{"kind": "wire", "index": <draw_wires 的非负下标>}`；`role` 只许 part 的
  `reference`/`value` 与 wire 的 `net`；`to` 只许 `x`/`y`/`rotation`/`alignMode` 至少一项，
  数值有限、`alignMode` 1..9。**任意 `primitiveId`、key/value 改写、可见性、字体、颜色或额外键
  一律在读计划时按名拒绝**，不会转发给宿主，也不会被当成"没写"悄悄放过。
  每行**必须显式写 `moveVersion`**：缺失即读计划时拒绝（053R 的行内必填合同，parser 不替行补 1）。
  只有程序里构造 `PlanAttributeMove` 时该字段默认 1，序列化输出仍照写 1。
- **053U：`moveVersion: 2` 才许 `to.valueVisible`**（严格 bool），且只许 wire 的 `net` 行——
  这是"保留 NET、隐藏多余同名文字"的唯一入口：只改那一枚 ATTR 的 `ValueVisible=false`，
  **不清空导线 net、不删 ATTR、不跨脚拉线**，宿主 netlist 必须逐字节不变。它可以单独构成
  一次隐藏（`to` 只有 `valueVisible` 也算"至少一项"）。part 的可见性、非 bool、未知版本、
  版本 1 里出现的 `valueVisible` 一律读计划时拒绝。隐藏完成的幂等探针核对该行
  `valueVisible=false` + 父级/net 不变（**不再**要求它可见）；显示仍要求可见。旧版本
  计划的行、序列化字节与 apply 调用序不变。
- **apply 怎么定位**：父级取这一趟**实际放置**返回的 id（part 的 primitiveId、线段的
  `sch.place_wire` uuid），目标文字从页面自己的属性表解析——part `reference` 用页面回读的
  **实际位号**，part `value` 只认父级下**唯一**有坐标且可见的 `Name` 行，wire `net` 认父级下
  `key=Name` 且值等于该 wire 网名的唯一行。候选缺失、多候选、调用失败或回读不符 → **停**（exit 3），
  现场保留、不清理、不回退折线、**不保存**。
- **只有非空 moves 才做写前能力检查**（`sch.list_attributes` + `sys.probe` 查
  `sch_PrimitiveAttribute.modify`），宿主缺 API 在**器件写入之前** exit 4；检查只证明 API 面，
  不冒充移动成功。空 moves 一次多余调用都不发。
- **幂等**：带 moves 的 plan 再跑时，`already_applied` 之前先读**整页 ATTR**逐行核对
  role/内容/可见性和 `to` 声明的字段；同一条 move 多候选、两条 move 共用同一行、`readErrors`
  非空、坐标/姿态不符都**不算**已到位——文字没挪过去的页面不会被当成"已完成"而跳过移动。
  这一步**只读**，探针本身从不移动文字。
- **053R 时这批不生成它**：`attributeMoves` 最初由一次性合成计划提供，compiler/readability/label
  stub 当时未改，也不决定布局；P22 的合成计划是一次性探针，不是自动布局能力。053S 起由显式
  规格开关生成，规则见下节。

**053S：`textPlacement`（可选顶层开关）——编译器生成 `attributeMoves`**。唯一的非缺省值是
`"native-attr"`；**不写这个键 = 与 053S 之前逐字节相同**（spec 不写 `textPlacement`，plan 没有
`attributeMoves` 键，apply 不调 `sch.list_attributes` / `sys.probe` / `sch.move_attribute`）。
未知值、非字符串、把坐标塞进这个键一律在读 spec 时按名拒绝；pagecompiler 切模块时把它原样
传给每个模块的子 spec。它要求宿主/connector 具备 ATTR 能力（053R 的写前检查），没有能力时在
写任何器件**之前** exit 4，不会静默退回旧画法。

开启后编译器自动生成三类移动（不启用就一个都没有）：

- **器件文字**：`layout.texts` 的 `reference` / `value` 以 `LayoutText.x/y` 为目标（缺省用 bbox
  中心），只写 x/y，不发明 rotation / alignMode。`partTexts` 指定侧的器件即使符号声明了自然
  锚点也走编译器的候选侧阶梯——015S 的声明因此在画布上真正生效；文档没点名的器件仍沿用自然
  锚点，不生成"挪到原地"的空移动。
- **网名**：最终 wires 稳定**之后**（`_drop_covered_runs` / `_cut_at_flag_attachments` 已跑过），
  按 `LayoutLabel` 的 anchor/net 找 `is_label_wire` 的承载线，生成 `role=net`、目标为 label
  bbox 中心的移动。下标取**落地计划里的最终下标**，不拿 layout 的陈旧下标。
- **歧义不猜**：一个 label 找不到承载线、有两根承载线，或两个 label 落在同一根线上，`draw plan`
  以 `DrawPlanError` 明确报 native 标签歧义并拒绝出计划——不挑第一枚、不额外调用
  `createNetLabel`。本批不去重连续多段同名、不禁弯、不改旗标；CH343 这类页面若撞歧义就是
  **不落图**，所以本批不宣称 CH343 已完成。
- 数值目标与移动后的回读核对仍走 053R 的 apply 合同（唯一可见 `Name` 行、坐标/姿态逐行核对、
  不到位的页面不算 `already_applied`）。

**053T：一条连续导线只印一个网名、native 只走直桩、文字按真实盒子建模**。`textPlacement` 不变，
`native-attr` 开启后行为收紧，不开时旧 candidates / labels / plan 逐字节不变：

- **连续段只留一个名**：`LayoutLabel` 多了可选 `textMode`（缺省不序列化、不进 geometry digest）。
  编译在 readability 与 geometry hash **之前**按现有 segments 的同网连通分量筛标签：共享端点、
  或一段的顶点落在另一段上（T 接）算连续，连续的只留第一个名；**同网不等于连续**——断开的同网
  各留一个（Type-C 的可逆脚就是这种），本批绝不为了合并而加线。053V 起再由可见性 pass 把这些
  断开的同名收敛成"一枚显示、其余隐藏"（见下节）。
- **被省略的标签必须本来就有导体**：anchor 不在本网任何导线上的标签原样保留；旗标覆盖的网名
  不走该筛选，也不产生 attr 移动。
- **native 短桩只走直线**：候选阶梯里折线（099f 三折、r19 四折、r23 near stagger）在 `text_mode`
  为 native 时整段不提供；四向直桩全被挡就照旧拒绝，不借折线通过。名字行、owner/其它文字
  碰撞与 `nameCarriers` 都按**保留标签自己的 bbox**（ATTR 打印的位置）量，不按导线中点盒。
- **readability 读真实盒子**：native 标签的名字行取 label bbox（水平 ATTR），不再额外造一个
  导线中点的幽灵 Name 行，也不再用导线方向判竖排；旧 labels / `_named_wire_rows` 行为不变。
- **降级文案**：native 页面的 downgrade 说"wire 承载网名 + ATTR 移字到哪里"，不再声称当前 V4
  的 ATTR 不可用（029 只描述旧宿主）。
- 页面路径要把 `textMode` 一起搬到页坐标（`pagecompiler` 的两处标签拷贝），否则 native 页面会
  静默退回旧画法。
- 实测边界（`evidence/534t/`）：CH343 v45（v44 布局 + `native-attr`）页级 compile 出 4 个候选、
  `legality=0/findings=0`；`draw plan` 在 D- 的两个可逆脚名字行相距 8.5（L5 的 20 下限）处
  **拒绝出计划**，四处候选一致。那是 USB 回环/旗标那批的活，本批不修、不落画布。

**053V：每个模块视图每网只显示一个名，重复名用 `valueVisible: false` 隐藏**。053T 只合并
**连续**段；断开的同网（Type-C 可逆脚）各留一个名，因此仍可能有两行相距 8.5（L5 下限 20）。
053U 已实测：导线 net 不动、只把该行 `Name` 的 `valueVisible` 写 false，宿主 netlist **逐字节不变**。
本批把两件事接起来，`textPlacement: native-attr` 下的行为再收紧一层；不开开关仍逐字节不变：

- **每模块视图每网一枚显示名**：`LayoutLabel.text_mode` 新增 `"native-hidden"`。053T 的物理连通
  去重照旧先跑；之后在同一次模块编译视图内，把该网其余（**不连续**）标签标为 `native-hidden`。
  相关标签仍留在 plan 里——导线继续带该网名、同一名字跨岛仍按名合并——**不清 net、不删标签、
  不跨可逆脚补线**，只是不印字。
- **显示项怎么选**：取 **label bbox 中心离该承载段离开的 pin 更远**的那一枚（即更长更清楚的桩），
  同距离按原顺序（`max` 取第一个），因此 5 单位短桩不会挤掉长桩的名；判定是量出来的，不是猜的。
  pin 由 plan 自己的线段读出：承载段起点是 pin，标签 anchor 是远端，所以取该段离 anchor 最远的
  端点。
- **隐藏项的形状**：`native-hidden` 生成 **version 2**、`owner.kind="wire"`、`role="net"` 的
  `to = {"valueVisible": false}`（无 pose——行留在宿主原地，只改可见性）；显示项仍 version 1、
  移到 label bbox 中心。两种行的 wire 下标都取落地计划的**最终**下标，一 label 一线，重复候选
  照旧拒绝（native 标签歧义）。
- **隐藏项不是墨**：不产生文字盒、不算 `nameCarriers`、不参与 owner/其它文字碰撞；readability
  不再为它造默认中点的幽灵 Name 行、不拿导线方向判竖排、`_text_boxes` 不把它的 bbox 当文字障碍。
  **导线净空与直桩规则照查**（承载段仍要直、仍要过 `_label_stub_candidates` 的净空阶梯）。
- **降级文案**：隐藏标签的 downgrade 说"wire 承载网名 + ATTR 的 `valueVisible: false` 隐藏
  （本模块视图只印一次）"，不说 V4 的 ATTR 不可用（029 只描述旧宿主）。
- **边界**：旗标网维持原例外（旗标名字，不产生 attr 移动）；anchor 不在本网任何导线上的标签不被
  本 pass 挑动。未写 `textPlacement` 的规格仍无 `textMode`、无 `attributeMoves`，plan 与 geometry
  digest 逐字节不变；`pagecompiler` 继续把两种 `textMode` 一起搬到页坐标。

**LDO（C3）现场有两条真机事实，照坑 33/34 走**：真机 AMS1117 符号的 VIN/VOUT/GND 全在**同一侧**
（外加一颗重复 VOUT），`ldo` 文法的默认"in 左 out 右"**无合法姿态**——要么按坑 33 用
`sidePreferences`（这是一个**说明**"下面那条输出支路"，不是"输出在下方"），要么换一颗符号；
另有坑 34：本仓库 facts 要求 AMS1117 输出 ≥22µF（053 场景值 055 起已同步为 22µF），拿 100n
输出落图 `decap-required-caps` 会涨 finding、`draw apply` 按 036 规矩**拒绝保存**（图落好了、没落盘）。

**057：一页多模块（页文档）与 `draw discard`——不加命令、不加旗标，同三条命令**：

- **什么算"页"**：PresentationSpec 有 ≥2 个 `modules[]`、或写了 `flow`、或某模块自带 `grammarRef`、
  或有页级锁（`pagecompiler.wants_page`）→ 走页级编译；恰一个模块（054 夹具那种）走原单模块路径，输出一字不变。
  页级 `draw compile` **必须给 `--page-box`**，产物是 `candN.page.json`（`kind=boardwise-page-layout-plan`）+
  带模块虚线框的 `candN.svg`。
- **`draw plan`（页）**：页级编译后把选中候选的 `plan` 字段交给同一个 `module_plan`，产出的仍是
  `draw-module` plan（layoutSha256 = 页文档 `plan` 的几何哈希），旁边写 `<plan>.page.json`。带 `--page`
  时读页面 census，**每个既有图元（件/线/旗标/网标，件与网标用 `bboxIds` 实测外框，没量到的用原点 ±50 假定框
  并在 notes 里点名）转 keepout**，模块组整体平移避开；
  未编号器件（编辑器自己的 `R5?`）没有位号可点名，只进 census 计数、不进组件集；
  全被占 → `presentation-poor` 点名"existing R5 …"。页文档里的跨模块标签在本机放不了（坑 9），**没有线
  到达的标签点会补一段 10 单位具名短线**（downgrades 里写明），否则两边同名网在工程级网表里合不起来。
- **`draw apply`**：`--layout` 可给页文档；位置参数也可直接给页文档（需 `--circuit/--presentation/--profiles`
  + `--page`/`--new-page`），运行时现建 plan 再走原流程；页文档的"过期守卫" = 它的模块框对页面现状的
  keepout 规则（压到既有图元 → exit 4 零写入）；要"页面任何变动都拒"用 `draw plan --page` 产的 plan
  （census 摘要精确）或 `--expect-census`。**所有落图**新增范围外逐项对比：落图前已在页上的每个图元
  （位号/值/LCSC/网/坐标/姿态/线点；网标另比 网名/文字/坐标/角度）必须原样，改了一件 → exit 2 不保存（`range.outOfScope`）。
  报告 `verification.nets` 逐网列出编辑器网表回读名，跨模块网标 `crossModule`、`oneNet`（G4）。
  findings 按身份分级拦（`rule|severity|位号|脚|命名网` 的**第二段**就是严重度）：ERROR 必拦、
  WARN 需 `--force`、INFO 只报告（#55 裁决 B）；仍不按计数。
- **页级锁**：`userLocks[]` 加 `"scope": "page"`（不写 rotation；位姿归模块）→ 该件在每个候选都落在
  页坐标 P（origin = P − 模块内坐标，逐代次不同是对的）；锁点出页 / 两把锁矛盾 / 锁住的框出页、压
  keepout、与另一锁住的框冲突 → `presentation-poor` 点名锁。模块锁（默认 scope）与页锁可同件共存。
- **`draw discard <plan.json|page.json>`**：只删该 plan 自己画的东西。件按**位号 + 坐标 + 值**（无 valueKey
  的旧 plan 用 LCSC）核身份，旗标按网 + 点，线要求**每个点都在 plan 的线上**（被宿主并进别人线的 primitive
  不删，坑 32）；**任何一件不符整批拒删**（exit 4，零删除）。先线、再旗标、后件（每相每次 ≤30 id，分批
  会写进报告）；删后回读：目标全无 + 范围外逐项不变。第二遍 = `nothing_to_discard` exit 0。`--save` 才保存；
  超时/断连先回读、不重试（exit 3）。页文档需 `--circuit/--presentation/--profiles`，按坐标 + 前缀 + 值找件。
- **已知缺口（057 离线实测，`tools/057_scenarios.py`）**：CH340G 核心/晶振/USB 侧**没有文法**（只有
  divider/RC/LDO），页级编译对这三组报 `facts-missing`；金样板上的 RT9013（VIN/GND/EN 同在左侧）在 `ldo`
  文法下 48 种 sidePreferences **全部无合法姿态**——坑 33 的"改输入侧"对它无效。真机 E1–E7 的操作清单见
  `tools/057_live_runbook.md`。
- **074：旗引线不得穿越别网导体**（岳裁「必须改」，命令面一字未增）。069 落下的 pin2 3V3 旗引线
  「横 50 + 竖拐 25」的**竖拐**子线段与 5V0 横轨在 (60,740) 垂直交叉、无 junction 圆点——电气双岛正确，
  但第一眼读成「旗挂在 5V0 轨上」。尺子：候选引线的**每个子线段**与别网导体（`router.edges` +
  已落件引脚）做**严格内部**相交——共享端点、T 型衔接（端点落线 = 有意的 junction）、共线重叠都**不算**；
  只硬化**旗引线/stub 段**（069① 远脚 stub、`_rail_flag` 沿轨段、竖拐 jog），**普通信号布线穿越不硬化**
  （crossings 仍是软指标）。硬拒后按既有梯子升级（距离档 → 逃逸方向 → 三折/两段引线 → 向无轨方向垂挂）；
  梯子穷尽 → `layout-unsat`，报**哪段穿哪条导体 + 交叉点 + 建议动作**，**不许静默产出穿越图、不许假
  junction**（安全阀：`layout-unsat` 是契约内的合法答复，不是 bug）。
- **175/B-1：普通布线的穿越是一条*价*，不是一堵墙**（岳裁 2026-10-12「宁可多绕也不穿干线」）。
  `router.CROSS_COST` 从 2.0（两步——比绕行便宜得多）提到 **120 步（600 单位）**：一次垂直穿越比
  120 步以内的绕行都贵，而它仍是**有限价**——原理图图论上不保证平面，硬拒会把「拥挤的页」变成
  `NET_UNROUTABLE`（画不出的板），所以穿越仍留作最后手段（一折快路与搜索同价：折腿穿别网导线的
  肘不再直接返回，交搜索按同一价决定）。实测：150 落地页的 `COMP` 引线由**穿 `SEC_12V` 干线两次**
  降到一次（第 175 批前该走线出自一折快路，因此单提常量对它无效）；`FB_SENSE` 的穿越从 120 起
  被绕开。另见 `docs/draw.md` 的旗引线一节（074）——**普通信号布线穿越不硬化**这条未变。


- **053W：旗标外形压线是硬检查，native 页按网格避让**。新增硬 kind
  `flag-body-on-wire`（`readability._check_flag_body_on_wire`）：用 `flag_glyph_box`
  实测的旗标外形，按 `FLAG_BODY_CLEARANCE = 5.0` 测导线与它的**净距**，报旗标 net、
  `symbolRef`、位置与 box、被穿 wire 的下标与 net，以及实测 gap。**净距内贴边也报**；
  唯一豁免是从 anchor 向 glyph 反方向离开的正常引线，其余各点仍满足净距。
  **未知 profile/body 不测量、不假装零碰撞**；**同网主干穿过也报**
  （`drawcompiler._flag_room` 本来就是这条规则）。
  该检查在 readability 门里只对 **native 页**启用（`textPlacement == "native-attr"`）；未写
  该键的旧规格保持旧布局与旧判定，`flag-body-on-wire` 不出现。要专项审计任意 `LayoutPlan`
  仍可直接调 `_check_flag_body_on_wire`（053AD：净距 5 是 native 文本模型的排版约束，
  不是对所有旧图纸的追溯判定）。
- **native 的修复在整页拼装之后、readability 之前**（`pagecompiler._relocate_native_flags`，
  只读 `textPlacement == "native-attr"`）：按**最近网格距离**（1..20 步，5 单位/步）、
  固定方向顺序（上、下、左、右）尝试移位；保留 `symbolRef`、net 与**竖直姿态**（不旋转）。
  原 anchor 到候选用**同网直线**连接：旧 anchor 是既有 lead 末端且共线就**延长**该 lead
  （不共线则在该 lead 上追加一段折），没有 lead 才新增两点段——不留悬空、不跨异网。
  候选外形须避开全部导线、器件、文字、其它旗标外形与页界；被移动旗标所属 module 的
  frame 同步扩张且不得与邻框重叠，该 module 的 flag port 锚点同步。plan notes 逐条记
  原位置、候选、距离/步数与 lead 变化。**找不到合法位置即整页失败**（`layout-unsat`），
  不回落压线、不删旗标、不清 net。非 native 规格（未写 `textPlacement`）一个旗标都不动，
  旧图字节不变。
- **053W续（净距 5）**：内部交叉**不是**判据。`flag-body-on-wire` 改成按
  `FLAG_BODY_CLEARANCE = 5.0`（与 `drawcompiler.FLAG_CLEARANCE` 同值同义）测
  **净距**，violation 报实测 gap；边/角接触、2 单位开外的run 一律报，唯一豁免是同网、
  端点落在 anchor、第一步背离 glyph、其余各点仍 ≥5 的自身 lead。同网主干不豁免。
  `pagecompiler` 的碰撞识别与候选复检调同一个 `readability._flag_body_offence`。
  实测：P20 旧计划 GND 旗标被自己的 GND 主干擦过 **1.0 单位**，「0 内部交叉」把这条盖住了。
- **053W续二（模块梯子与整页净距统一）**：模块级旗标梯子
  （`drawcompiler._rail_flag_seat` / `_flag_pin_lead` 的 `fits`）在算出候选 glyph 后，
  对 `router.edges` 与 `router.own_edges` 调**同一个** `readability._flag_body_offence`
  （`drawcompiler._flag_wire_ruler`），原有 solids/page/blocked/lead 净空照旧；非 native
  规格该尺子恒放行，字节不变。同时 `_seat_wire_flags` 为 native 页预留的墙由「只有 glyph」
  改成 `_flag_box(margin=FLAG_CLEARANCE)`——路由器的 1 单位 epsilon 会让导线贴着墙走，
  只留 glyph 的墙就是把旗标交给门禁去判 1 单位。**两处都用同一个常量、同一套语义，
  不是第二把尺子**。不写 `textPlacement` 的规格两处都不变。
- **v45 恢复 4 个合法候选**（`.tmp_534w`/`evidence/534w/offline_v45_ladder.json`）：
  修复前同一输入 0 候选，`usb_c` 的 `R1.2` GND 梯子全被旧 room 判死；修复后四个候选
  `_check_flag_body_on_wire` 全为 0 条，**每个旗标对非引线导线的最小净距 6.0**，
  无需整页移位（plan 无 `053W:` note）。真机 test V4 的空白 P26 `9b729f3ad67a20d6` 上
  `draw plan --page-box 0,0,1170,825` = exit 0 / planned / candidate 0，P26 依旧空白、**未 apply**。
- 053W 早期结论「v45 四候选 0 内部交叉、避障是惰性的」只对**内部交叉**成立；净距 5 之下
  同一批布局是被模块梯子自己的 room 模型选出来的，所以续二必须把两把尺子合成一把。
- **053Z：native 名字必须住在自己的载体上（`native-label-off-carrier`）**。
  `textPlacement: native-attr` 下主机把网名印在 label 的 box 上（`_native_attribute_moves`
  的目标就是 box 中心），所以 box 离自己的引线多远，名字就印在多远。新增硬 kind
  `native-label-off-carrier`（`readability.NATIVE_LABEL_CARRIER_LIMIT = 10`，一个 10 单位网格）：
  对每个 `textMode: "native"` 的可见 label，载体 = 其 anchor 所在的导线（同网优先，其次本页无名
  引线）或 tip 就是 anchor 的引脚线，退路是同网任意一段；**量的是文字盒到 polyline 的最近距**
  （`_box_run_gap`，不是 anchor，也不是 lineGroup）。P27 实测 `CTS=40`、`RI=55` 必须复现
  （`tests/test_534z_label_carriers.py`）；`native-hidden` 不印字不检，非 native 路径字节不变。
  盒心在 anchor 的行/列上（一条直桩到得了）且距离 ≤10 才算合格——页编译器原本就按轴摆放，
  所以 v46 四个候选仍 0 条。
- **053Z：native 候选盒重选（`pagecompiler._native_label_seat`）**。`_add_label(native=True)`
  不再走 `_label_box`，改按固定梯子 `_NATIVE_LABEL_SEATS = (1, 2)`（贴锚点一格 + 第二列）
  四方向试位：盒尺寸与水平阅读不变（`font_text_box`）、盒心在 anchor 的行/列（直桩到得了）、
  距每个**异网**导线 ≥10、直桩本身不跨异网导线；无合法位置返回 `layout-unsat`，**不回退到
  离岸短桩**。该选择发生在整页 `_reseat_native_labels`（`_assemble` 内、flag 迁移之后、
  readability 与 geometry hash 之前），因此 `_native_attribute_moves` 的目标、直桩终点与
  gate 量的是**同一个 box**。非 native 的 `_label_box` 分支一行未改。
- **H1 长型号**：v47 = v46 + `partTexts.H1 = "right"`（`.tmp_534z/v47.presentation.json`），
  不带任何 `localLabelObligations`（053Y 证明它会改契约且不可编译）。离线几何核对长型号
  值框与 x=140 地旗引线（`140,450 → 140,425`）不相交。
- **053Z 真机（未通过，现场保留）**：新页 P28 `ea468a6523625fa0`（工程 `test V4`，
  census 0/0/0 起）apply 成功（11 器件 / 52 导线 / 16 旗标，live+canvas ok，保存，
  `evidence/534z/p28.png`），独立逐脚 **55/55 连接 + 3/3 NC = 58/58**；但 `draw lint`
  **2E/2W/3I**：`L1` H1 长型号被 net DSR 导线穿过 77 单位、`L2` 该文字与 `RI` 盒重叠 7.1×7.0，
  `L5` 仍报 `RXD`/`DSR` 各被印了第二个名字（`CTS`/`RI`）；且页面网表里 `CC1/CC2/V3` 落成
  `$9N4/$9N13/$9N14` 自动名。**0E 未达成**，P28 保留待修，P20/P27/参考页与 Board2 P1 未动、
  未删任何页。缺的那一块写在这里：模块自带的标签（`PAGE_PORT_LABEL` 的 `if labels:` 分支）
  在页面上**没有落地它的直桩**，所以 box 离引线 28–68 单位、属性行照 box 印到邻线上——
  下一批要么让整页为这些标签补直桩导线，要么把它们的 box 收到载体旁≤10。
- **053X：页间标签也必须是 native**。`pagecompiler._port` 复用的模块标签
  （`PAGE_PORT_LABEL` 的 `if labels:` 分支，`_native_text_mode`）与新造的标签
  （`_add_label(..., native=…)`）在 `textPlacement: native-attr` 下都写
  `textMode: "native"`；已有 `native-hidden` **不改可见**，非 native 规格一个字节都不动。
  没有这个标记时跨岛 `V3`/`RTS` 等名是空 `textMode`：readability 继续按导线中点建行
  （旧中点幽灵），`drawcompiler` 也按"沿导线印名"排版，竖直载体就印成折线/竖排。
  回归 `tests/test_534x_page_native_layout.py`（9 项）；v46（C3/C4 并入 `ch343`，
  `C3=(-70,0)`/`C4=(70,0)` 芯片外侧）离线 4 候选、16 旗、`flag-body-on-wire` 0 条，
  真机 P27 `fcbf0ddbe79dc94d` 已 apply（11 件/52 线/16 旗）。
