"""625A — `core/blocks.py` 装载器：证据台账、端口唯一性、身份与几何的松闸。

来源 `outputs/hole625/a/REPRO.md`（625A-01…07）。缝 A 的结论先写在前面，因为它决定
这一批修什么、不修什么：

* 8 条洞里有 **5 条是「装载期该拒却放行」**（证据引用、reference 路径、端口唯一性、
  重复脚号、绝对模板、身份空白），本批逐条加闸；
* **625A-04（空网导线）是复核否决**：出货规格 `ch340g_usb_uart` 的四个模板里有 35 段
  导线本来就没有网名（10/13/11/1），加闸等于当场拒掉被审过的真板；模板里的导线是
  **画线**，电气归属由它连着的脚和旗标给出；
* **625A-02 的存在性不在装载器**：绝对路径与目录在这里拒，文件「在不在」归
  `declared-input-exists`（`validate --spec` 的 sources 闸，产品闸，默认就跑）——装载器拿不到运行时的语料。

所有用例都建在出货模板 `blocklib/blocks/power_ams1117_3v3.json` 上（拷进 tmp 再改一处），
这样符号 offsets、端口、几何都是真数据，闸的位置也落在真文件的形状上。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boardwise.core.blocks import BlockError, load_board_spec

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "blocklib" / "blocks" / "power_ams1117_3v3.json"
SHIPPING_SPECS = ROOT / "blocklib" / "specs"


def _stage(tmp_path: Path, *, duplicate_pin: bool = False, wire_without_net: bool = False) -> str:
    """Copy the shipping template into ``tmp_path``, optionally bending one field."""
    body = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    if duplicate_pin:
        body["components"][0]["pins"].append(dict(body["components"][0]["pins"][0]))
    if wire_without_net:
        body["geometry"]["wires"][0]["net"] = ""
    (tmp_path / "t.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    return "t.json"


def _block(block_id: str, template: str, at: tuple[float, float] = (0.0, 0.0)) -> dict:
    return {"id": block_id, "template": template, "at": [at[0], at[1]]}


def _spec(
    tmp_path: Path,
    *,
    blocks: list[dict] | None = None,
    connections: list[dict] | None = None,
    references: list[dict] | None = None,
    param_evidence: dict | None = None,
    params: dict | None = None,
) -> Path:
    body = {
        "kind": "boardwise-board-spec",
        "version": 1,
        "name": "625a",
        "description": "",
        "provenance": {"kind": "textbook", "source": "625", "note": ""},
        "sheet": {"attrs": {}, "origin": [0.0, 0.0]},
        "blocks": blocks if blocks is not None else [_block("pwr", "t.json")],
        "connections": connections if connections is not None else [],
        "params": params or {},
    }
    if references is not None:
        body["references"] = references
    if param_evidence is not None:
        body["param_evidence"] = param_evidence
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------- 625A-01


@pytest.mark.parametrize("carrier", ["param_evidence", "block", "connection"])
def test_evidence_that_cites_an_undeclared_reference_is_refused(tmp_path: Path, carrier: str) -> None:
    """一条证据 id 是**引用**，必须解析到已声明的 reference。

    修前（REPRO §625A-01）：`param_evidence` / `blocks[].evidence` /
    `connections[].evidence` 三处引用 `NOPE-REF` 全部 `LOADED`——真正查它的只有
    opt-in 的 `validate --benchmark`，而产品默认路径故意不带 benchmark。
    """
    _stage(tmp_path)
    references = [{"id": "ds", "kind": "datasheet", "path": "d.pdf"}]
    kwargs: dict = {"references": references}
    if carrier == "param_evidence":
        kwargs["params"] = {"pwr.c_in_value": "10uF"}
        kwargs["param_evidence"] = {"pwr.c_in_value": ["NOPE-REF"]}
    elif carrier == "block":
        kwargs["blocks"] = [{"id": "pwr", "template": "t.json", "at": [0.0, 0.0],
                             "evidence": ["NOPE-REF"]}]
    else:
        kwargs["blocks"] = [_block("pwr", "t.json"), _block("pwr2", "t.json", (100.0, 0.0))]
        kwargs["connections"] = [{"net": "NET_A",
                                  "ports": [["pwr", "GND"], ["pwr2", "GND"]],
                                  "evidence": ["NOPE-REF"]}]
    with pytest.raises(BlockError, match="not a declared reference"):
        load_board_spec(_spec(tmp_path, **kwargs))


def test_a_declared_reference_still_carries_its_evidence(tmp_path: Path) -> None:
    """加闸的对照：引用已声明的 `ds` 照常装载（出货规格就是这个形状）。"""
    _stage(tmp_path)
    spec = load_board_spec(
        _spec(
            tmp_path,
            references=[{"id": "ds", "kind": "datasheet", "path": "d.pdf"}],
            params={"pwr.c_in_value": "10uF"},
            param_evidence={"pwr.c_in_value": ["ds"]},
        )
    )
    assert spec.param_evidence["pwr.c_in_value"] == ["ds"]


# ---------------------------------------------------------------- 625A-02


def test_a_reference_path_may_not_be_absolute(tmp_path: Path) -> None:
    """绝对路径的引文搬不动 spec 就废了。修前 `C:/Windows/win.ini` 照样 LOADED。"""
    _stage(tmp_path)
    with pytest.raises(BlockError, match="absolute path"):
        load_board_spec(
            _spec(tmp_path, references=[{"id": "ds", "kind": "datasheet", "path": str(TEMPLATE)}])
        )


def test_a_reference_path_may_not_be_a_directory(tmp_path: Path) -> None:
    """修前 `path: "../../"` 也能装载；目录不是能读出一页东西的地方。"""
    _stage(tmp_path)
    with pytest.raises(BlockError, match="is a directory"):
        load_board_spec(
            _spec(tmp_path, references=[{"id": "intent", "kind": "intent", "path": "../"}])
        )


def test_a_missing_reference_path_is_the_benchmarks_question_not_the_loaders(tmp_path: Path) -> None:
    """**文档化的边界**：文件「在不在」不在这里问。

    装载器只有 spec 文件本身，没有运行时的语料；`declared-input-exists` 在
    `declared-input-exists` 里按本次运行真有的语料回答——它是 `validate --spec` 的 sources 闸，
    产品闸，默认就跑（625A-02 原文允许这个口径）。
    这里把边界钉住，免得下一个人以为「不存在的 path 也能装载」是漏。
    """
    _stage(tmp_path)
    spec = load_board_spec(
        _spec(tmp_path, references=[{"id": "ds", "kind": "datasheet", "path": "no/such/file.pdf"}])
    )
    assert spec.references[0].path == "no/such/file.pdf"


# ---------------------------------------------------------------- 625A-03


def test_one_port_on_two_nets_is_refused_at_load(tmp_path: Path) -> None:
    """一个端口只能在一个网上：两个网就是短路。

    修前装载放行，唯一拦截在 `assemble`，文案却指向「同一个 block 出现两次」。
    """
    _stage(tmp_path)
    blocks = [_block("pwr", "t.json"), _block("pwr2", "t.json", (100.0, 0.0))]
    connections = [
        {"net": "NET_A", "ports": [["pwr", "GND"], ["pwr2", "GND"]]},
        {"net": "NET_B", "ports": [["pwr", "GND"], ["pwr2", "VCC"]]},
    ]
    with pytest.raises(BlockError, match=r"port pwr\.GND is already on net 'NET_A'"):
        load_board_spec(_spec(tmp_path, blocks=blocks, connections=connections))


def test_the_same_port_twice_in_one_connection_is_refused(tmp_path: Path) -> None:
    """同一条连接里把同一端口写两遍：修前按「两个端口」计数并放行。"""
    _stage(tmp_path)
    blocks = [_block("pwr", "t.json"), _block("pwr2", "t.json", (100.0, 0.0))]
    connections = [
        {"net": "NET_A", "ports": [["pwr", "GND"], ["pwr2", "GND"], ["pwr", "GND"]]}
    ]
    with pytest.raises(BlockError, match=r"port pwr\.GND is already on net 'NET_A'"):
        load_board_spec(_spec(tmp_path, blocks=blocks, connections=connections))


# ---------------------------------------------------------------- 625A-04（复核否决）


def test_a_template_wire_may_carry_no_net_and_the_shipped_library_does(tmp_path: Path) -> None:
    """**不改**：空网导线是模板的画线，出货规格里有 35 段。

    `ch340g_usb_uart` 的四个模板分别是 10 / 13 / 11 / 1 段无网导线——加「net 非空」
    这道闸等于当场拒掉一块被审过的真板。电气归属由导线连着的脚与旗标给出，不是由
    导线自己声明的。
    """
    _stage(tmp_path, wire_without_net=True)
    spec = load_board_spec(_spec(tmp_path))
    assert spec.blocks[0].template.wires[0].net == ""

    shipped = load_board_spec(SHIPPING_SPECS / "ch340g_usb_uart.json")
    empty = sum(1 for block in shipped.blocks for wire in block.template.wires if not wire.net)
    assert empty == 35, f"the shipped library's witness moved: {empty} wires carry no net"


# ---------------------------------------------------------------- 625A-05


def test_two_pins_with_the_same_number_are_refused(tmp_path: Path) -> None:
    """同脚两个名字/两个网：修前得到两条 pin 记录，下游按遍历顺序覆盖。"""
    _stage(tmp_path, duplicate_pin=True)
    with pytest.raises(BlockError, match="already declared on this part"):
        load_board_spec(_spec(tmp_path))


# ---------------------------------------------------------------- 625A-06（复核否决）


def test_a_spec_kept_outside_the_library_may_name_its_blocks_absolutely(tmp_path: Path) -> None:
    """**不改**：绝对模板路径是「spec 不在库里、指回图书馆」的合法写法。

    裁量证据在仓库自己手里：`tests/test_spec_cli.py` 的 `variant` fixture 就是
    「a copy that lives elsewhere must say where they are」，它把模板路径绝对化之后
    才把 spec 写进 tmp。拒掉绝对路径等于拒掉这条工作流；而可搬迁性承诺说的是
    **跟自己的 blocks 一起搬** 的 spec，那种 spec 里模板仍是相对名（23 份出货规格
    全部如此）。
    """
    spec = load_board_spec(_spec(tmp_path, blocks=[_block("pwr", str(TEMPLATE))]))
    assert Path(spec.blocks[0].template_path).is_absolute()


# ---------------------------------------------------------------- 625A-07


def test_a_block_id_may_not_carry_surrounding_whitespace(tmp_path: Path) -> None:
    """身份字段逐字比较：`"  pwr  "` 曾经被 strip 成 `pwr`，文件里和内存里不是一个串。"""
    _stage(tmp_path)
    with pytest.raises(BlockError, match="whitespace in identity"):
        load_board_spec(_spec(tmp_path, blocks=[{"id": "  pwr  ", "template": "t.json",
                                                 "at": [0.0, 0.0]}]))


def test_a_port_role_may_not_carry_surrounding_whitespace(tmp_path: Path) -> None:
    _stage(tmp_path)
    blocks = [_block("pwr", "t.json"), _block("pwr2", "t.json", (100.0, 0.0))]
    connections = [{"net": "NET_A", "ports": [["pwr", " GND "], ["pwr2", "GND"]]}]
    with pytest.raises(BlockError, match="whitespace in identity"):
        load_board_spec(_spec(tmp_path, blocks=blocks, connections=connections))


def test_a_reference_id_may_not_carry_surrounding_whitespace(tmp_path: Path) -> None:
    _stage(tmp_path)
    with pytest.raises(BlockError, match="whitespace in identity"):
        load_board_spec(
            _spec(tmp_path, references=[{"id": " ds ", "kind": "datasheet", "path": "d.pdf"}])
        )


# ---------------------------------------------------------------- 625A-08


def test_the_two_presentations_without_a_library_circuit_are_documented() -> None:
    """出货库里两份 presentation 没有配对 circuit，缺在哪儿写在库的 README 里。

    不搬历史 drafts 进来是有理由的：`.tmp_038q12_main_gen/circuits/` 里那两个
    circuit 是 `"draft": true`，并且带 `"provenance": "ai_asserted"` 的 NC——库是策展
    过的输入，不能把没人签过的草稿当成可复跑的证据。这条闸钉住「声明」本身，免得
    README 悄悄过期、下一个人又以为文件只是忘了提交。
    """
    readme = (SHIPPING_SPECS / "README.md").read_text(encoding="utf-8")
    for stem in ("ch340c_usb_serial", "sy8089_buck_3v3"):
        assert (SHIPPING_SPECS / f"{stem}.presentation.json").is_file(), stem
        assert not (SHIPPING_SPECS / f"{stem}.circuit.json").exists(), stem
        assert stem in readme, f"{stem} is not disclosed in blocklib/specs/README.md"
