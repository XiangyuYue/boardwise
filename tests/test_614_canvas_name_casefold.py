"""614 — `unique_canvas_name` compares names the way a Windows disk does.

570-D5 (``outputs/hole570/d/REPRO.md``): on this machine ``BoardA.svg`` and
``boarda.svg`` are **one file**.  ``write_canvases`` used a case-sensitive
``name not in used``, so a second board whose title only differs in case was
handed a name the first board already owned: the second render silently
overwrote the first while ``canvas_images[]`` kept two rows.

The rule now: ``used`` and the candidate are both compared after
``str.casefold()``, so the collision-free first name, the six-digit key suffix,
the empty-key ``-2``/``-3`` ordinals, and the second-order collision all keep
their old shape — they just cannot be reached by a case variant any more.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from boardwise.core.geometry import BoardGeometry, PadGeometry
from boardwise.engines.canvasrender import unique_canvas_name, write_canvases


# ---------------------------------------------------------------------------
# 1. the hole: a case variant is the same name on a case-insensitive disk
# ---------------------------------------------------------------------------


def test_a_case_variant_cannot_reuse_the_taken_name():
    got = unique_canvas_name("boarda.svg", "ab812f", {"BoardA.svg"})
    assert got != "boarda.svg", "boarda.svg 与 BoardA.svg 在 Windows 上是同一个文件"
    assert got.casefold() != "boarda.svg", got
    assert got == "boarda-ab812f.svg", "撞名规则不变：key 后六位做后缀"


def test_the_first_name_still_keeps_its_own_case():
    # The taken name is not rewritten; only the newcomer moves aside.
    used = {"BoardA.svg"}
    assert unique_canvas_name("BoardA.svg", "012345", used) != "BoardA.svg"
    assert unique_canvas_name("other.svg", "012345", used) == "other.svg"


def test_a_case_variant_with_no_key_uses_the_ordinal_form():
    got = unique_canvas_name("boarda.svg", "", {"BoardA.svg"})
    assert got == "boarda-2.svg", got
    assert got.casefold() not in {"boarda.svg"}


def test_a_second_order_case_collision_keeps_counting():
    # The keyed candidate itself is taken by another case variant: the ordinal
    # has to advance instead of returning a name that folds onto ``used``.
    used = {"BoardA.svg", "boarda-AB812F.svg"}
    got = unique_canvas_name("boarda.svg", "xx-ab812f", used)
    folded = {name.casefold() for name in used}
    assert got.casefold() not in folded, f"{got} 仍与 used 折叠同名"
    assert got == "boarda-ab812f-3.svg", got


def test_unicode_case_variants_fold_too():
    # Unicode, not ASCII lower(): '' and 'SS' are the same word.
    assert "Straße".casefold() == "STRASSE".casefold()
    used = {"STRASSE.svg"}
    got = unique_canvas_name("Straße.svg", "abcdef", used)
    assert got == "Straße-abcdef.svg", got
    assert got.casefold() not in {name.casefold() for name in used}


# ---------------------------------------------------------------------------
# 2. the same rule on a real directory: two files, not one overwritten
# ---------------------------------------------------------------------------


def test_two_case_variant_names_leave_two_files(tmp_path: Path):
    used: set[str] = set()
    first = unique_canvas_name("boarda.svg", "aaaaaa", used)
    used.add(first)
    second = unique_canvas_name("BoardA.svg", "bbbbbb", used)
    used.add(second)
    (tmp_path / first).write_text("body-of-first", encoding="utf-8", newline="\n")
    (tmp_path / second).write_text("body-of-second", encoding="utf-8", newline="\n")

    on_disk = sorted(path.name for path in tmp_path.glob("*.svg"))
    assert len(on_disk) == 2, f"两个名字在大小写不敏感盘上落成了一个文件：{on_disk}"
    assert (tmp_path / first).read_text(encoding="utf-8") == "body-of-first"
    assert (tmp_path / second).read_text(encoding="utf-8") == "body-of-second"


def _pad(pid: str, comp: str, x: float = 0.0, y: float = 0.0) -> PadGeometry:
    return PadGeometry(id=pid, component=comp, x=x, y=y, width=40.0, height=20.0,
                       footprint_layer_id=1)


def _board(*pads: PadGeometry) -> BoardGeometry:
    board = BoardGeometry()
    board.pads = list(pads)
    return board


def test_write_canvases_splits_case_variant_titles(tmp_path: Path):
    images = write_canvases(
        [("BoardA", _board(_pad("a", "U1"))),
         ("boarda", _board(_pad("b", "U2"), _pad("c", "U2", 500, 500)))],
        out_dir=tmp_path,
        keys=["ab812fb7-0000-4000-8000-000000000001",
              "3e2ff784-0000-4000-8000-000000000002"],
    )
    files = [image["file"] for image in images]
    assert len({name.casefold() for name in files}) == 2, files
    assert files[0] == "canvas-BoardA.svg"
    assert files[1] == "canvas-boarda-000002.svg"
    on_disk = sorted(path.name for path in tmp_path.glob("*.svg"))
    assert on_disk == sorted(files), "canvas_images[].file 与盘上的文件必须一一对应"
    for name in files:
        ET.fromstring((tmp_path / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 3. the negative control: collision-free, exact collisions and keys unchanged
# ---------------------------------------------------------------------------


def test_a_free_name_is_returned_untouched():
    assert unique_canvas_name("canvas-A.svg", "abcdef", {"canvas-B.svg"}) == "canvas-A.svg"
    assert unique_canvas_name("canvas-主板_A.svg", "", set()) == "canvas-主板_A.svg"


def test_an_exact_collision_keeps_the_old_suffix():
    assert unique_canvas_name("A.svg", "123456", {"A.svg"}) == "A-123456.svg"
    assert unique_canvas_name("A.svg", "", {"A.svg"}) == "A-2.svg"
    assert unique_canvas_name("A.svg", "", {"A.svg", "A-2.svg"}) == "A-3.svg"
    assert unique_canvas_name(
        "A.svg", "123456", {"A.svg", "A-123456.svg"},
    ) == "A-123456-3.svg"


def test_the_extension_is_preserved():
    assert unique_canvas_name("noext", "", {"noext"}) == "noext-2"
    assert unique_canvas_name(
        "canvas-Power_Board.png", "0c0ffe", {"canvas-Power_Board.png"},
    ) == "canvas-Power_Board-0c0ffe.png"
