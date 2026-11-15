# 038Q18：块端口未展开的 unproven 证据与 N1–N3

日期：2026-11-15。前置：038Q17 块实例识别；真实带 PIN 块已放置并接线。
本批是 shared parser + 既有 unproven 通道小批，不新增全局规则、不改 verdict/exit code/绘制。

## 真实基线

`.tmp_038q_native/pins-p47-baseline-project.epro2`，SHA-256
`8c563bcee081bd602e81a8480c0d931271c24ab36dbe61cf7893af2e63a6968a`。
P47=`14e0eec8ff7ccc8d`：

- 块 `10a78dbe099533d2`（CBB2），本地 symbol=ca89…，PIN 1 在 (380,370)，经正交导线 NRST 到 U10.7。
- 宿主 EasyEDA 网表没有 CBB 组件/端口，U10.7=NRST；离线 `Net.pins` 只有 U10.7。
- 旧 `arch-nrst-closure` 对 U10.7 报 **单成员网 WARN**（N1 误报）；U2.7 无网，仍应 WARN（N2）。
- 其他 U9/J5 行是既有对照，不得借本批修改。
- 几何/记录/宿主网表分析：`.tmp_038q_native/pins-connected-analysis.md`。

另一个实际样例 `.tmp_038q_native/pins-connected-project.epro2`：BLOCK_SIG=R1.1，R2.1 真悬空；
当前没有通用单脚网规则，不能用不存在的规则冒充 N2。

## 公开合同

新增 unproven reason `TRUNCATED_BY_BLOCK_PORT`，含义：**原生块端口没有展开成普通 Net.pins 成员**。
在 `_fill_board_model` 中复用现有 symbol pin + `_transform_point` + WIRE point_index/UnionFind/labels：
若一个已识别块端口与导线端点重合，则该 cluster 的 net membership 不完整，写入：

- `model.unproven_nets[name]`：并集该块所在 page uuid；
- `model.unproven_reasons[name]`：新 reason + 可定位的块/端口/页 detail；若已有 duplicate-designator
  reason，保留原 code 并追加 detail，不覆盖旧证据。

块本身仍不成为 Component/Net 成员。只在真实导线端点命中时标记；无导线、空端口、未识别候选不标记。
NC 与普通 pin 同规则跳过。旋转/镜像必须走同一 transform，不复制第二份坐标算法。

`rules/unproven.py` 的 `RefusedNet.truncated` 和 `TRUNCATION_PHRASES` 吸收新 reason，使现有
`unproven_outcome`、coverage/refusal 计数认识它。不是新开一条静默豁免；普通无块输入的 maps 和 findings
必须逐字不变。

## N1 / N2 / N3 完成判据

- **N1**：U10.7 已接块 PIN，旧单成员 WARN 消失，转为既有 unproven UNKNOWN/测量披露，
  明确“块端口未展开”，不得再写“网上只有它自己”。
- **N2**：U2.7 普通真悬空仍产生同一 arch-nrst-closure VIOLATION，不能因工程含块而豁免。
- **N3**：不含 CBB 实例的对照输入，解析模型与 findings 逐字不变；自动网号不得因本批新增 UF 节点而漂移。
  实现不得向 UF 添加块节点，只在 labels 完成后读已有 wire root。

同时保留：普通组件/nets、块三锚识别、手填位号不分流为普通件、同 uuid first-wins、source 未决。

## 文件域

- `src/boardwise/core/model.py`（一个 reason 与注释）、`src/boardwise/rules/unproven.py`、
  `src/boardwise/parsers/schematic.py`、`tests/test_038q18_block_port_unproven.py`、
  `docs/v3-v4-boundary.md`、本任务书。不得改 archclosure 的业务阈值、绘制、CLI/DSH schema、connector。
- 测试可用匿名合成流，真实容器只在本机 `.tmp_038q_native/` 对拍，不进 fixtures。

## 验收

1. 先保存旧实现基线：真实 P47 U10/U2 warning 原文；无块对照 findings 原文。
2. 新实现后真实 P47：U10 不再出现悬空文案、unproven reason 可读；U2/U9/J5 及其他普通行不变。
3. 无块对照 findings 逐字不变；普通 components/nets/pin_wires 与 Q17 一致。
4. 合成负例：块无导线、空端口、NC、旋转/镜像、多块同网、已有 duplicate reason 不覆盖。
5. 聚焦 pytest `--basetemp=.tmp_pt_038q18`；至少两变异（漏块 unproven、误豁免普通悬空）
   先红后 cp+SHA-256 恢复。零 git 写、零直删、零真机写。

未覆盖：V3、嵌套块、非端点接触、块内部展开网表、未识别候选的端口推断、完整 CBB 电气兼容。

## 实际结果（2026-11-15，工作树，未提交）

新 reason `TRUNCATED_BY_BLOCK_PORT`（`core/model.py`）已纳入 `RefusedNet.truncated` 与
`TRUNCATION_PHRASES`（因而也进 `REFUSAL_SENTENCES` / `is_unproven_refusal`）。`schematic.py` 在
`labels` 定稿后调用 `_block_port_net_hits()`：已识别块的端口按**同一** `_transform_point`（位姿/旋转/镜像）
定位，查既有 `point_index`（只含 WIRE 端点）→ 取 `uf.find` 的既有 root → `labels` 得网名；
未向 UF 加节点。命中的网写 `unproven_nets`（并集页）与 `unproven_reasons`（新 reason + 块/端口/页 detail）；
已有 duplicate reason 保留原 code 并追加 detail。无导线、空端口、NC、未识别候选均不标。

真实读数（`.tmp_038q_native/q18-review-check.json`，旧实现以 `cp` 备份模块同进程对拍）：

| 容器 | findings 前 | findings 后 | 模型差异 |
|---|---|---|---|
| `pins-p47-baseline-project.epro2`（`8c563bce…`） | 0E/3W/7I | 0E/**2W**/8I | 仅 unproven 新增，`nets`/`components`/`pin_wires` 逐字相同 |
| `test-v4-cbb-project.epro2` 无块对照（`8ad4558f…`） | 0E/1W/7I | 同一份 JSON（`findings_identical: true`） | 零差异 |
| `q46-project.epro2`（块 0 端口） | — | — | 零差异、`unproven={}` |

P47 两块两块端口都命中导线：`BLOCK_SIG`（块 CBB1 端口 1，页 `2ee0dc01f7e63dfe`）与
`NRST`（块 CBB2 端口 1，页 `14e0eec8ff7ccc8d`）各标 `truncated-by-block-port`。
**N1**：`arch-nrst-closure` 的 U10 pin7 行由 WARN「单成员网/网上只有它自己」变为 INFO
「net 'NRST' may have members missing from it (… block 'CBB2' port '1' on page '14e0eec8…')」。
**N2**：U2 pin7（`NET125`）、U9 pin7（`NET178`）仍是同一 WARN，J5 pin7 仍 INFO——P47 前后
findings 集合只差 U10 一行。**N3**：无块对照 JSON 逐字相同；14 份夹具 before/after 模型逐字相同、
0 块实例；合成对照（加块 vs 不加块）`nets`/`pin_wires` 完全一致，自动 `NETn` 无位移。

聚焦 pytest：`tests/test_038q18_block_port_unproven.py` 13 passed；连同 Q17、107、093、138、
189a2、072、040b、041、doc_claims 合计 294 passed（`--basetemp=.tmp_pt_038q18`）。
两变异先红后 `cp`+SHA-256 还原（`c00246c6…` 字节一致）：「不标块 unproven」8 failed；
「误豁免普通单成员网」9 failed。

未覆盖：V3、嵌套块、非端点接触（端口在导线中段不标）、块内部展开网表、未识别候选的端口推断、
完整 CBB 电气兼容；`pins-connected-project.epro2` 的 `BLOCK_SIG` 同样被标（该容器同批实测，未单独做规则行证据）。

### 独立挖洞 4 项修复（同日）

1. `unproven_message` 收尾按 gap 分派：block-only 用 `a native CBB block's ports are not expanded
   into this netlist`，duplicate+block 用合并句，107/welded 文案逐字不变。真实 P47 的 U10 行以块端口句收尾，
   不再出现 “a placement the model did not keep may be the part this judgement needs”。
2. `cli.py` 的 `unprovenNets.note` 把两种 truncation 分开：block 只写原生块端口未展开/成员不完整
   （并明说不是位号重复），107 句只列自己的网名；只有 107 的板 note 与旧文本逐字相同
   （Q18 测试走真实 `checkup --file` 的 `report.json` 断言）。
3. 进 `unproven_nets` 的网名一定在 `model.nets` 里：只有块端口的有名导线以 `Net(name, pins=[])` 存在，
   在自动网名定死之后补，`NETn` 不位移（两块对拍 + 变体对照 + `unproven ⊆ nets` 断言）。
4. 块 hit 键加 `primitive_id`，detail 形如 `block 'CBB1' (primitive 'blk1') port '1' on page …`，
   两个同名实例是两个事实（`port '1'` 计 2 次、两个 primitive id 都在）。

真实复核：P47 `checkup --file` 的 `unprovenNets` = `BLOCK_SIG`/`NRST`，reason 均
`truncated-by-block-port`，note 只有块端口句；`unproven_not_in_nets` 为空、无空网；findings 仍 0E/2W/8I，
无块对照仍逐字相同。聚焦：Q18 单文件 22 passed；Q18+Q17+107+coverage+checkup CLI+doc_claims 251 passed。
变异先红后恢复：block 文案改回 107 尾巴 2 红、unproven 网不进 `model.nets` 2 红（两文件 `cmp` 字节一致）。

### 全量唯一归属本批的失败：rules 摘要重钉（同日）

`tests/test_126a_pcb_review_plumbing.py::test_the_rulebody_digest_covers_the_pcb_subpackage`
红在钉值上：本批有意改 `rules/unproven.py`（`rules/` 顶层直接文件），旧值 626e16ef/d2ff8ae4 过期。
在当前工作树按上方同一配方实测：**direct `d345bfc0`、recursive `2b62613f`**（非手填，命令见测试注释）。
官方 `tools.build_differential_fixtures` 重生成 `contracts/differential`，净 diff 三项、来源分开写：
①`rulebody` d2ff8ae4→2b62613f（manifest 与 report 两处，**038Q18** 本批）；
②`source.parseStats.unknown_types` `{TABLE:1,UNIVERSAL:1}`→`{}`（**038Q17** 把 TABLE/UNIVERSAL 登记为
已知记录后的真实解析读数；上一批落码未重生成合同，这次按生成器读数落盘，不是无关漂移，也没有任何测试
把它故意钉成未知——`grep -rn unknown_types tests/test_540c_*.py` 零命中，规则侧只有
`tests/test_162b_epru_truth.py` 的「已知类型不得出现在 unknown_types」正向断言）；③`toolVersion` /
`environment.expectedConnectorVersion` 0.6.0→0.6.1 与两批均无关，成对恢复为 0.6.0；另加
`manifest.inputs` 该输入的哈希随字节重算（`8597f0ce…`）。测试 docstring 分开记 ①②③，断言改为新值。
行为锚：`tests/test_038q18_block_port_unproven.py` 22 条与 `tests/test_107_dup_net_unproven.py` 未改仍绿。

### 第三轮全量：三处 PRE_EXISTING 输入哈希钉同步（同日）

`test_038m_device_differential.py`、`test_038n_footprint_differential.py`、
`test_038t_footprint_declared.py` 三处 `PRE_EXISTING["review-report-projection"]` 仍钉旧
`9457f6d0…`。全仓 grep `9457f6d0`：只有这三个测试文件（另命中
`tasks/038r5_contract_test_alignment.md` 一条**历史记录**，记的是 038R5 当时的合法值，
不在本批文件域、也不是活钉，未改）。逐处核对：三处都指向同一份生成输入
`contracts/differential/inputs/review-report.json`，其当前官方生成字节 SHA-256 为
`8597f0ce9ea9cadf0259842def71a4e81324e0c9de8f5765c0d273db48f81618`（变化来自 038Q17 的
`unknown_types={}` 与 038Q18 的 `rulebody=2b62613f`，见上一节）。只改这一项哈希与邻近说明
（说明里写清两次重生成、两个成因），案例 ID、顺序、其他行哈希、`kind`/`input` 一概不动。

### 最终全量（第三轮）

**11226 passed / 26 skipped / 3 xfailed / 3 failed / 1 warning**（27m27s，
`.tmp_038q_native/q18-final3-pytest.log`）。本批的 126a 与 038M/N/T 失败全部清零；
剩余三红为绘制线未提交的 548D panel_base、548K stub_floor、548P service_rows，不由本批修改，
不称全量全绿。Connector 774 passed + typecheck；DSH 137 passed / 1 skipped + typecheck/build；
Rust 177 passed / 4 ignored + fmt/clippy/test。证据：`evidence/038q18/live-report.md`。
