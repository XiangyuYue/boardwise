"""555 A: `parts hunt` 的两条新入口 —— 活工程（``--live``）与报告过滤（``--from-report``）。

The properties are asserted as counterfactuals, exactly as 520 does: not "the
report says one part" but "the catalog was asked about one C-number"; not "the
run was offline" but "the outbound recorder saw nothing". A test that only read
the report would pass on an implementation that had already dialled.

No test touches a network or an editor. The two seams are the ones the 520 suite
already patches — `_fetch_url` / `_pdf_text` / `urllib_product_fetcher` for the
network, `_load_model_online` for the live ladder — so the *pipeline* under test
is the real one, not a second copy of it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise import cli
from boardwise.core.model import Component, DesignModel
from boardwise.engines import hunt

#: The page dump 520's narrow extractor turns into facts (one pin row + one spec row).
MARKED = """<<<page 1>>>
Table 5-1 Pin Functions
VCC 3 Supply 3.3V supply voltage
<<<page 4>>>
8.3 Recommended Operating Conditions
Supply voltage, VCC 3 3.6 V
"""


class FakeNetwork:
    """Every seam the run can dial through, recording what it saw."""

    def __init__(self) -> None:
        self.detail_calls: list[str] = []
        self.download_calls: list[str] = []
        self.extract_calls: list[Path] = []

    def fetch_detail(self, product_code: str) -> dict:
        self.detail_calls.append(product_code)
        return {
            "code": 200,
            "result": {
                "pdfUrl": f"https://example.invalid/{product_code}.pdf",
                "productModel": "X",
            },
        }

    def download(self, url: str) -> "hunt.Download":
        self.download_calls.append(url)
        return hunt.Download(
            ok=True, payload=b"%PDF-1.4 fake body", content_type="application/pdf", status=200
        )

    def pdf_text(self, path: Path) -> tuple[str, str]:
        self.extract_calls.append(Path(path))
        return MARKED, "stub extractor"


@pytest.fixture()
def network(monkeypatch) -> FakeNetwork:
    fake = FakeNetwork()
    monkeypatch.setattr(cli, "urllib_product_fetcher", fake.fetch_detail, raising=False)
    monkeypatch.setattr(cli, "_fetch_url", fake.download)
    monkeypatch.setattr(cli, "_pdf_text", fake.pdf_text)
    return fake


def component(designator: str, *, lcsc: str = "", mpn: str = "") -> Component:
    return Component(uid=f"u-{designator}", designator=designator, lcsc_part=lcsc, mpn=mpn)


def board_model(*components: Component) -> DesignModel:
    return DesignModel(components={part.designator: part for part in components})


def live_ladder(monkeypatch, model: DesignModel, *, tier: str = "project-file", seen=None):
    """Stand in for `_load_model_online`; record the routing args it was handed."""

    def fake(args, *, notes, attempts, **_kwargs):
        if seen is not None:
            seen["project"] = getattr(args, "project", "")
            seen["instance"] = getattr(args, "instance", "")
            seen["live"] = getattr(args, "live", False)
        attempts.append({"tier": tier, "ok": True})
        notes.append("stub live ladder")
        return (
            model,
            None,
            tier,
            {"project": {"friendlyName": "ds555-fixture", "name": "ds555"}, "file": None},
            None,
        )

    monkeypatch.setattr(cli, "_load_model_online", fake)


def offline_model(monkeypatch, model: DesignModel) -> None:
    monkeypatch.setattr(cli, "_load_model", lambda *a, **k: (model, None))


def report(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        json.dumps({"version": "/7", "needs_datasheet": rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def hunt_report(out: Path) -> dict:
    return json.loads((out / "hunt-report.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# §1 --live: the editor is read through the ladder the other commands use
# --------------------------------------------------------------------------


def test_live_project_file_hunt_names_its_source_and_reads_one_c_number(
    tmp_path, network, monkeypatch
):
    model = board_model(component("U1", lcsc="C2977777"))
    live_ladder(monkeypatch, model, tier="project-file")
    code = cli.main(
        ["parts", "hunt", "--live", "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 0
    assert network.detail_calls == ["C2977777"]
    report_body = hunt_report(tmp_path / "out")
    assert report_body["board"]["source"]["tier"] == "project-file"
    assert report_body["board"]["source"]["project"] == "ds555-fixture"
    assert "live:" in report_body["board"]["file"]
    assert report_body["parts"][0]["outcome"] == hunt.EXTRACTED


def test_live_per_page_tier_is_accepted(tmp_path, network, monkeypatch):
    live_ladder(monkeypatch, board_model(component("U1", lcsc="C2977777")), tier="per-page")
    code = cli.main(
        ["parts", "hunt", "--live", "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 0
    assert hunt_report(tmp_path / "out")["board"]["source"]["tier"] == "per-page"
    assert network.detail_calls == ["C2977777"]


def test_live_netlist_tier_is_refused_rather_than_hunted_as_anonymous(
    tmp_path, network, monkeypatch, capsys
):
    """A netlist model has no MPN and no C-number: hunting it would write 40 rows
    of `no-identity` about parts that *do* have identity in the editor."""
    live_ladder(monkeypatch, board_model(component("U1")), tier="netlist")
    code = cli.main(
        ["parts", "hunt", "--live", "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 3
    assert network.detail_calls == [], "no outbound call on a refused tier"
    assert not (tmp_path / "out" / "hunt-report.json").exists(), "no half report"
    stderr = capsys.readouterr().err
    assert "netlist" in stderr and "身份" in stderr


def test_live_with_no_reachable_state_is_three(tmp_path, network, monkeypatch):
    monkeypatch.setattr(cli, "_load_model_online", lambda *a, **k: None)
    code = cli.main(
        ["parts", "hunt", "--live", "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 3
    assert network.detail_calls == []


def test_live_passes_the_named_window_through(tmp_path, network, monkeypatch):
    seen: dict = {}
    live_ladder(monkeypatch, board_model(component("U1", lcsc="C2977777")), seen=seen)
    code = cli.main(
        [
            "parts", "hunt", "--live", "--project", "ds555-fixture",
            "--instance", "win-7", "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert seen == {"project": "ds555-fixture", "instance": "win-7", "live": True}


# --------------------------------------------------------------------------
# §2 the flag combinations: each refusal is a sentence, not a silent choice
# --------------------------------------------------------------------------


def test_a_file_and_live_together_are_refused(tmp_path, network, monkeypatch):
    def never(*_a, **_k):  # pragma: no cover - the point is that it is not called
        raise AssertionError("a contradictory request must not read anything")

    monkeypatch.setattr(cli, "_load_model_online", never)
    monkeypatch.setattr(cli, "_load_model", never)
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--live",
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 2
    assert not (tmp_path / "out" / "hunt-report.json").exists()


def test_no_input_at_all_is_two(tmp_path, network, monkeypatch):
    code = cli.main(["parts", "hunt", "--out", str(tmp_path / "out"), "--no-cache"])
    assert code == 2


def test_project_or_instance_without_live_is_two(tmp_path, network, monkeypatch, capsys):
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"),
            "--project", "ds555-fixture", "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 2
    assert "--live" in capsys.readouterr().err


def test_live_with_offline_is_two(tmp_path, network, monkeypatch, capsys):
    """"read the editor" and "not one outbound call" are two different answers."""
    code = cli.main(
        ["parts", "hunt", "--live", "--offline", "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 2
    assert "--offline" in capsys.readouterr().err


# --------------------------------------------------------------------------
# §3 --from-report: only what checkup said it was missing
# --------------------------------------------------------------------------


def three_c_numbers(monkeypatch) -> FakeNetwork:
    offline_model(
        monkeypatch,
        board_model(
            component("U1", lcsc="C1111111"),
            component("U2", lcsc="C2222222"),
            component("U3", lcsc="C3333333"),
        ),
    )
    return None


def test_from_report_addresses_only_the_named_parts(tmp_path, network, monkeypatch):
    three_c_numbers(monkeypatch)
    path = report(tmp_path / "report.json", [{"part": "U2", "pins": [], "trigger": "facts"}])
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert network.detail_calls == ["C2222222"], "the other two C-numbers never left"
    body = hunt_report(tmp_path / "out")
    assert [part["designator"] for part in body["parts"]] == ["U2"]
    assert any("--from-report" in note for note in body["notes"])


def test_from_report_reads_the_reports_own_designator_key(tmp_path, network, monkeypatch):
    """The report's worklist rows carry the designator under `part`; a caller
    that writes `designator` (the seeding section's own spelling) must work too."""
    three_c_numbers(monkeypatch)
    path = report(tmp_path / "report.json", [{"designator": "U3"}])
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert network.detail_calls == ["C3333333"]


def test_from_report_empty_worklist_is_a_zero_part_report(tmp_path, network, monkeypatch):
    three_c_numbers(monkeypatch)
    path = report(tmp_path / "report.json", [])
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert network.detail_calls == [], "an empty worklist asks nobody anything"
    body = hunt_report(tmp_path / "out")
    assert body["parts"] == []
    assert body["board"]["parts"] == 0


def test_a_report_without_the_key_is_refused_not_read_as_all_parts(
    tmp_path, network, monkeypatch, capsys
):
    three_c_numbers(monkeypatch)
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"version": "/7"}), encoding="utf-8")
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 2
    assert network.detail_calls == []
    assert "needs_datasheet" in capsys.readouterr().err


def test_a_report_of_the_wrong_shape_is_two(tmp_path, network, monkeypatch):
    three_c_numbers(monkeypatch)
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"needs_datasheet": "U1,U2"}), encoding="utf-8")
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 2
    assert network.detail_calls == []


def test_a_report_naming_a_part_this_board_does_not_have_is_two(
    tmp_path, network, monkeypatch, capsys
):
    three_c_numbers(monkeypatch)
    path = report(tmp_path / "report.json", [{"part": "U2"}, {"part": "U404"}])
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 2
    assert network.detail_calls == [], "refused before anything is dialled"
    assert "U404" in capsys.readouterr().err


def test_a_report_file_that_is_not_json_is_two(tmp_path, network, monkeypatch):
    three_c_numbers(monkeypatch)
    path = tmp_path / "report.json"
    path.write_text("not json", encoding="utf-8")
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 2


def test_limit_applies_after_the_report_filter(tmp_path, network, monkeypatch):
    """`--limit 1` over a filtered worklist takes the *first selected* part, not
    the first part of the board (which the report may not have named at all)."""
    three_c_numbers(monkeypatch)
    path = report(tmp_path / "report.json", [{"part": "U2"}, {"part": "U3"}])
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--from-report", str(path),
            "--limit", "1", "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert network.detail_calls == ["C2222222"]
    assert [part["designator"] for part in hunt_report(tmp_path / "out")["parts"]] == ["U2"]


def test_from_report_and_live_compose(tmp_path, network, monkeypatch):
    live_ladder(
        monkeypatch,
        board_model(component("U1", lcsc="C1111111"), component("U2", lcsc="C2222222")),
    )
    path = report(tmp_path / "report.json", [{"part": "U2"}])
    code = cli.main(
        [
            "parts", "hunt", "--live", "--from-report", str(path),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert network.detail_calls == ["C2222222"]
    body = hunt_report(tmp_path / "out")
    assert body["board"]["source"]["tier"] == "project-file"
    assert [part["designator"] for part in body["parts"]] == ["U2"]


# --------------------------------------------------------------------------
# §4 the offline shape is untouched
# --------------------------------------------------------------------------


def test_an_offline_report_keeps_its_old_board_shape(tmp_path, network, monkeypatch):
    three_c_numbers(monkeypatch)
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"),
            "--out", str(tmp_path / "out"), "--offline", "--no-cache",
        ]
    )
    assert code == 0
    assert network.detail_calls == []
    board = hunt_report(tmp_path / "out")["board"]
    assert set(board) == {"file", "title", "boards", "parts", "offline", "out", "cache"}
    assert board["offline"] is True
    assert board["file"] == str(tmp_path / "b.epro2")


# --------------------------------------------------------------------------
# §5 one designator, two boards, two different parts
# --------------------------------------------------------------------------
#
# Measured on a real board pair 2026-11-19: a checkup report folded 23 unreviewed
# placements into 15 designators, and `U1` is an MCU on 控制板 and a different part
# on 驱动板. Taking the first board's `U1` addressed 15 parts and silently left the
# other identity out — and, worse, an answer keyed by designator would have hung
# one part's datasheet on the other. These tests are about *placements*, not names.


def two_boards(*, same: bool) -> DesignModel:
    """控制板/驱动板, each with a `U1` — the same part, or two different ones."""
    from boardwise.core.model import BoardModel, BoardRef, ProjectModel

    control = Component(
        uid="c1", designator="U1", lcsc_part="C1111111", mpn="CTRL-MCU", manufacturer="Elm"
    )
    driver = (
        Component(
            uid="d1", designator="U1", lcsc_part="C1111111", mpn="CTRL-MCU",
            manufacturer="Elm",
        )
        if same
        else Component(
            uid="d1", designator="U1", lcsc_part="C2222222", mpn="DRV-GATE",
            manufacturer="Oak",
        )
    )
    return ProjectModel(
        boards=[
            BoardModel(
                board=BoardRef(uuid="b-control", title="控制板"),
                components={"U1": control},
            ),
            BoardModel(
                board=BoardRef(uuid="b-driver", title="驱动板"),
                components={"U1": driver},
            ),
        ]
    )


def test_the_same_designator_with_two_identities_is_two_rows_and_two_lookups(
    tmp_path, network, monkeypatch
):
    """"one designator = one part" is a per-board fact, not a project one."""
    offline_model(monkeypatch, two_boards(same=False))
    code = cli.main(
        ["parts", "hunt", "--file", str(tmp_path / "b.epro2"),
         "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 0
    assert network.detail_calls == ["C1111111", "C2222222"], (
        "both identities are addressed, each with its own C-number"
    )
    parts = hunt_report(tmp_path / "out")["parts"]
    assert [part["designator"] for part in parts] == ["U1", "U1"]
    assert [part["identity"]["lcsc"] for part in parts] == ["C1111111", "C2222222"]
    assert [part["outcome"] for part in parts] == [hunt.EXTRACTED, hunt.EXTRACTED]
    assert any("不同器件" in note for note in hunt_report(tmp_path / "out")["notes"])


def test_the_same_designator_with_the_same_identity_stays_one_row(
    tmp_path, network, monkeypatch
):
    """Dedupe is kept where it is true: same part, two placements, one datasheet."""
    offline_model(monkeypatch, two_boards(same=True))
    code = cli.main(
        ["parts", "hunt", "--file", str(tmp_path / "b.epro2"),
         "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 0
    assert network.detail_calls == ["C1111111"], "one identity, one lookup"
    body = hunt_report(tmp_path / "out")
    assert [part["designator"] for part in body["parts"]] == ["U1"]
    assert any("只寻了一次" in note for note in body["notes"])


def test_a_designator_answer_that_fits_two_parts_is_refused_not_guessed(
    tmp_path, network, monkeypatch
):
    """The answer names only `U1`; two different parts answer to it. Guessing is
    how one part's PDF lands on another part's row."""
    offline_model(monkeypatch, two_boards(same=False))
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps([{"designator": "U1", "url": "https://example.invalid/u1.pdf"}]),
        encoding="utf-8",
    )
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--apply", str(answers),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert "https://example.invalid/u1.pdf" not in network.download_calls, (
        "the ambiguous answer's PDF is hung on neither part"
    )
    body = hunt_report(tmp_path / "out")
    effective = [part for part in body["parts"] if part["channel"] != ""]
    assert [part["url"] for part in effective] == [
        "https://example.invalid/C1111111.pdf",
        "https://example.invalid/C2222222.pdf",
    ], "each part kept the address its own C-number resolved to"
    assert body["counts"].get(hunt.UNKNOWN_DESIGNATOR) == 1
    # Both real parts were still addressed normally — the refusal costs nothing else.
    assert [part["identity"]["lcsc"] for part in effective] == ["C1111111", "C2222222"]


def test_an_mpn_answer_lands_on_the_identity_it_names(tmp_path, network, monkeypatch):
    """The caller's way out of the ambiguity: address the part, not the name."""
    offline_model(monkeypatch, two_boards(same=False))
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps([{"mpn": "DRV-GATE", "url": "https://example.invalid/drv.pdf"}]),
        encoding="utf-8",
    )
    code = cli.main(
        [
            "parts", "hunt", "--file", str(tmp_path / "b.epro2"), "--apply", str(answers),
            "--out", str(tmp_path / "out"), "--no-cache",
        ]
    )
    assert code == 0
    assert network.download_calls.count("https://example.invalid/drv.pdf") == 1, (
        "exactly one download, for the part the answer named"
    )
    assert "https://example.invalid/C2222222.pdf" not in network.download_calls, (
        "the named part took the handed-in address instead of asking the catalog"
    )
    body = hunt_report(tmp_path / "out")
    effective = [part for part in body["parts"] if part["channel"] != ""]
    landed = [
        part for part in effective
        if part["url"] == "https://example.invalid/drv.pdf"
    ]
    assert len(landed) == 1, "the handed-in address lands on exactly one part"
    assert landed[0]["identity"]["mpn"] == "DRV-GATE"
    assert landed[0]["outcome"] == hunt.EXTRACTED


def test_the_label_is_the_part_on_its_own_board(tmp_path, network, monkeypatch):
    """Two rows, one name: each carries the maker/MPN of the part it addressed."""
    offline_model(monkeypatch, two_boards(same=False))
    code = cli.main(
        ["parts", "hunt", "--file", str(tmp_path / "b.epro2"),
         "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 0
    by_identity = {
        part["identity"]["lcsc"]: part["facts"]["supply_pins"][0]["provenance"]
        for part in hunt_report(tmp_path / "out")["parts"]
    }
    assert "Elm CTRL-MCU" in by_identity["C1111111"]
    assert "Oak DRV-GATE" in by_identity["C2222222"]
    assert "Oak" not in by_identity["C1111111"], "控制板's row is not labelled with 驱动板's part"
    assert "Elm" not in by_identity["C2222222"], "驱动板's row is not labelled with 控制板's part"


# --------------------------------------------------------------------------
# §6 the candidate sidecars of two parts under one designator
# --------------------------------------------------------------------------
#
# `<designator>.candidate.json` is a filename a curator hands to
# `parts add --facts`. Once two placements share a designator (see §5), that name
# is not unique and the second identity's file silently replaced the first's.


def sidecars(out: Path) -> dict[str, dict]:
    directory = out / "candidates"
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.candidate.json"))
    }


def test_two_identities_under_one_designator_keep_two_sidecars(
    tmp_path, network, monkeypatch
):
    offline_model(monkeypatch, two_boards(same=False))
    code = cli.main(
        ["parts", "hunt", "--file", str(tmp_path / "b.epro2"),
         "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 0
    files = sidecars(tmp_path / "out")
    assert sorted(files) == [
        "U1.C1111111.candidate.json",
        "U1.C2222222.candidate.json",
    ], f"the identity is in the name: got {sorted(files)}"
    by_identity = {body["identity"]["lcsc"]: body for body in files.values()}
    assert set(by_identity) == {"C1111111", "C2222222"}
    # …and each file holds its own part's facts, labelled with its own maker.
    assert "Elm CTRL-MCU" in by_identity["C1111111"]["label"]
    assert "Oak DRV-GATE" in by_identity["C2222222"]["label"]
    assert by_identity["C1111111"]["facts"]["supply_pins"]
    assert by_identity["C2222222"]["facts"]["supply_pins"]


def test_a_unique_designator_keeps_the_old_sidecar_name(tmp_path, network, monkeypatch):
    """Nothing about a board that places one part per name may change."""
    offline_model(monkeypatch, board_model(component("U1", lcsc="C2977777")))
    code = cli.main(
        ["parts", "hunt", "--file", str(tmp_path / "b.epro2"),
         "--out", str(tmp_path / "out"), "--no-cache"]
    )
    assert code == 0
    assert list(sidecars(tmp_path / "out")) == ["U1.candidate.json"]
