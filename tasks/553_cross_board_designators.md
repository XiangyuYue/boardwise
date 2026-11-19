# 553：跨板共用位号不再作为缺陷（review 小批，工作树完成，未提交）

## 背景与裁决

岳 2026-11-19 明确：跨板共用位号不算问题，以后不要报错。此前 `DuplicateDesignators` 把 `cross_board_designators` 逐项升为 ERROR，导致一个双板工程仅因两板各自存在 C1/U1 等就产生 18 条 ERROR。

本批只改 review 规则的判决，不改解析事实：

- `BoardModel.cross_board_designators` 和 `ProjectModel.multi_board_designators()` 原样保留，供按板寻址、BOM、报告与消费者识别项目级歧义。
- `conn-duplicate-designators` 不再遍历 cross-board 事实，不再产生对应 Finding/Outcome。
- 同板同页重复、同板跨页重复仍是 ERROR；552 的合法多单元合并不是本批改动对象。
- 无 finding 时 OK 文案只声称本板位号唯一，不再声称全工程唯一。规则标题同步收窄。
- 无 CLI/DSH/schema/connector 变化，无版本 bump。

## 当前树与文件域

552 已在工作树修改 `schematic.py` 和若干旧测试，必须原样保留。主仓还有其他绘制线未提交改动，禁止触碰。

只允许：

- `src/boardwise/rules/connectivity.py`
- 新增 `tests/test_553_cross_board_designators.py`
- `tests/test_040_page_scope.py`、`tests/test_040b_boards.py` 中仍描述旧跨板 ERROR 的因果 hunks
- `tasks/553_cross_board_designators.md`、`evidence/553/`、`.tmp_553/`、`.tmp_pt_553*`

禁止改 `schematic.py`、`core/model.py`、552 新测试、fixtures/reviewsets、绘制线及任何他人未提交文件。若其他测试需要改，先报告，不越域。

## 验收与负对照

- 新测试先证明旧规则对纯跨板同名产生 ERROR，再证明修后为零；模型事实和项目级 repeated/ambiguity 读数不变。
- 同一合成模型同时含同页、跨页、跨板三类时，只前两类产生 ERROR；跨板事实原样存在。
- 既有双板归档的跨板同名不再报，但 DCDC 同页复制、注入 R24 跨页复制继续 ERROR。
- 聚焦运行 553、552、040、040b、049、105、107；独立 `--basetemp=.tmp_pt_553_*`，不跑全量。
- 至少一个因果变异：恢复 cross-board 遍历或让同板重号也不报，相应测试必须红；`cp` 恢复并核对 SHA-256。证明同板负对照不是只检查总数而被跨板移除掩盖。

## 纪律与交卷

先备份本批既有文件到 `.tmp_553/backup/`。零 git 写、零 `rm/unlink`、零全量、零真实工程写、零发布，不删改宽负对照。

最多 15 步或 15 分钟。交卷 ≤1200 字：实际 diff、测试命令和汇总原文、变异红与恢复哈希、跨板事实保留读数、未覆盖项。出现 552 或其他线的既有红项要分开披露，不陪跑、不掩藏。
