# 任务书：581 / W-N — 页框有限性与资源上界

## ① 前因后果

当前主任务是用户指定的 `outputs/hole568/TRIAGE.md`。总表 569G-03 实测 `--page-box 0,0,nan,826` 仍 exit 0、产出带 `NaN` 的 SVG/JSON；569G-04 实测 `inf`、`1e9`、`1e308` 页框在 20–45 秒内不返回。根因是 `src/boardwise/cli.py:_draw_page_box` 用比较运算判序但没有 `isfinite` 或尺寸上界，`src/boardwise/core/symbolprofile.py:check_box` 同样接受 NaN/Inf。原报告与复现矩阵在 `outputs/hole569/g/REPRO.md`、`outputs/hole569/g/matrix.md`。

本批只修这两条 reproduced，不处理 suspect，不顺手拿别的 568 洞。前批 580 SVG 已收口；工作树仍有 566–579 及他人未提交改动，绝不能恢复整文件到 HEAD。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`。开工时：
- `src/boardwise/cli.py` SHA-256 `66a1412b08c411bd3567da51f5cc1187fa07d466072a7be7458dba0d4aead677`，含前批未提交改动，必须保留；
- `src/boardwise/core/symbolprofile.py` SHA-256 `efc31cbe00b44759be7811d80ac421b8f4d60cdb6714a4592cb5c65ca70c103f`；
- 相关 `layoutplan.py`/`pagelayoutplan.py`/`changeplan.py` 由后续 W-S 处理，本批不改。
现有 `_draw_page_box` 在约 11648–11680 行，`check_box` 在约 1181–1207 行。正常基准页框为 `(0,0,1170,825)`，另有 `(0,0,1655,1170)` 和小至 `(0,0,240,300)` 的合法测试。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/cli.py`（仅 `_draw_page_box` 及必要的局部常量）
- `src/boardwise/core/symbolprofile.py`（仅 `check_box` 的有限性校验）
- `tests/test_581_page_box.py`（新建）
- `evidence/581/`、`.tmp_581/`、`.tmp_pt_581/`

禁止改其他生产/测试文件、fixtures、前批证据和他人未提交 hunk；不做 git 写、不删除、不跑全量、不接触 bridge/daemon/EDA。先 `cp` 备份两个生产文件并记录 hash；变异恢复只能 cp+SHA-256，禁用 git checkout/restore。

## ④ 交付物与验收

1. `_draw_page_box` 对 NaN、+/-Inf、反向盒、过小盒、超过明确上界的有限巨盒具名抛 `_DrawInputError`，不得进入编译。上界采用每边 `100000` canvas units（含边界），并在错误文案中说明是防资源耗尽的上界；`100000.1` 和 `1e9` 必须快速拒绝。正常 `1170x825`、`1655x1170`、`240x300` 以及负坐标合法页框保持接受。不要修改既有最小尺寸 100 的口径。
2. `check_box` 对所有调用者拒绝非有限坐标，保留原有的盒顺序/空值/类型语义；不得给普通文本盒或 keep-out 擅自加页面尺寸上界。
3. 新回归至少覆盖：CLI 入口函数 NaN/Inf/1e9/1e308、边界与正常值、`check_box` 的 NaN/Inf 与正常盒；必要的话用一个离线 CLI 冒烟证明 NaN 不再生成候选，但不调用 bridge。
4. 先运行新增测试对基线，保留先红原文；修后运行：
   `.venv/Scripts/python.exe -m pytest tests/test_581_page_box.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_053a_specs.py -q --basetemp=.tmp_pt_581`
   若某既有文件含前批已知基线红，必须逐名披露并用更窄正/负控证明本批无新增，不能写成全绿。
5. 至少两个独立因果变异（去掉有限性、去掉上界）先红，cp 恢复并核对两个生产文件 SHA-256。保存命令、完整汇总和差异到 `evidence/581/`。

兼容矩阵：普通模块/页文档离线输入均覆盖；正常 SymbolProfile 盒和 LayoutPlan 所复用的 `check_box` 做正例；V3/V4、容器、多板/CBB、真机不覆盖且不声称。negative control：合法页框/合法盒的返回值及既有测试不得改变，非法输入不得产生候选文件。

## ⑤ 纪律与红线

不新增第二套页框解析器，不改编译预算/搜索范围来凑过，不放宽断言，不 skip/xfail，不改前批测试。只做本批两个缺口；命令带超时、探针单进程；不跑全量、不真机、不部署、不发布。发现上界与既有合法合同冲突时停止并交证据，不自行扩大文件域。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤2000 字，逐项列出 569G-03/04、基线先红、修后命令与完整汇总、两个变异及恢复 hash、兼容矩阵和未覆盖项。详细日志落 `evidence/581/`；有任何未解决本批红项不得写完成。
