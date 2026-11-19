# 552：多单元器件身份与真实网表修复（shared 小批，工作树完成，未提交）

## 1. 前因后果

2026-11-19 的 DSH 审查把同一颗双单元运放的 `.1/.2` 两个符号当成两颗同位号器件，产生 4 条同页重号 ERROR，并进一步造成 17 个网的 `truncated-by-duplicate-designator`、19 条规则 withheld。原始图明确显示 `U15.1/U15.2`；既有归档中的两个 COMPONENT 具有相同非空 `Unique ID`、相同非空 `Device`，但 `partId` 分别为 `<device>.1/.2`。

第二个根因是 `_commit_symbol` 丢弃 `PIN.partId`，把同一 SYMBOL 的所有单元引脚合成一个集合；随后 `components.setdefault(designator, component)` 只保留第一个 placement，第二单元的真实网络被丢弃。只删掉 ERROR 会留下错误网表，禁止这样修。

跨板同名是另一项独立裁决：岳 2026-11-19 明确「跨板共用位号以后不要报错」。它只在后续 review 规则小批取消跨板 finding，保留 `cross_board_designators` 事实与同板/同页重号 ERROR，不在本 shared 批改 verdict。

## 2. 当前树与基线

- 主仓 `E:/boardwise`，HEAD `9f73ede`，混合工作树；绘制线和他人的未提交改动均不属于本批。
- 本批开始前 `src/boardwise/parsers/schematic.py` SHA-256：`d64463100b99c34bbb819334f1beab6be8dbf5cd7bd1e0b0c379cad4a87c2a8d`。
- `rules/connectivity.py` 本批不动，SHA-256：`e3e9846ac4932308c108984ba4a3d2da574941dd5bcd3aff8e81bd771a965d58`。
- 改前实测：`test_040_page_scope.py test_040b_boards.py test_105_b4b_designator_membership.py test_107_dup_net_unproven.py` = **92 passed, 55.53s**。
- 既有归档只读，不新增真实工程夹具，不修改 `tests/fixtures/` 或 `reviewsets/`。

## 3. 公开合同

1. SYMBOL 的旧 `pins` 全集保留给既有消费者；另记录 `PIN.partId → 本单元引脚`。实例 `partId` 精确命中时只用该单元的引脚；旧格式缺 `partId` 或不能精确命中时保持旧全集回退，不猜单元。
2. 同一板内、同一位号的两个 placement 仅在以下证据全部成立时才是一颗物理器件的多个单元：
   - 两者 `Unique ID` 非空且相同；
   - 两者 `Device` 非空且相同；
   - 两者 `partId` 不同。
   不得按 MPN、Value、封装、标题或坐标猜同一件。
3. 合法单元的引脚全部进入同一个根 Component 与相应 Net；不得再因这些合法单元产生 `duplicate_designators`、`cross_page_designators` 或 `truncated-by-duplicate-designator`。
4. 若合法身份候选在不同单元声明同一引脚号，只有该引脚解析到同一网络时才可合并；网络冲突或一有一无则保留旧重号/未证实处理，不伪造唯一网表。
5. 同一 `partId` 被复制，即使 `Unique ID` 也相同，仍是重号；不同 `Unique ID`、不同 `Device` 也仍是重号。既有 DCDC 复制件与注入的跨页 R24 是负对照。
6. 回退是恢复本批前的 `schematic.py`；无 schema/CLI/DSH/connector 新面，无版本迁移。

## 4. 文件域与禁触

允许：

- `src/boardwise/parsers/schematic.py`
- 新增 `tests/test_552_multi_unit_designators.py`
- 仅因正确新读数需要更新的 `tests/test_040_page_scope.py`、`test_040b_boards.py`、`test_049_parser_defects.py`、`test_105_b4b_designator_membership.py`、`test_107_dup_net_unproven.py`
- `evidence/552/` 与 `.tmp_552/`、`.tmp_pt_552*`

禁止：`core/model.py`、`rules/connectivity.py`、`cli.py`、`engines/v4facts.py`、`tests/test_v4_facts.py`、所有绘制线文件、fixtures/reviewsets、既有证据目录。不得清理或覆盖他人工作树内容。

## 5. 验证与兼容矩阵

| 维度 | 本批证据 | 不得声称 |
|---|---|---|
| V3 `.epro2` | 既有双板归档：四个双单元器件完整；另一既有归档两个双单元器件完整 | 不用旧错误网表数字反推新正确答案 |
| V4 `.eprj3` | 合成 `partId` 单元钉；真机宿主网表若另取则只读交叉验证 | 合成绿不等于全部 V4 库兼容 |
| 在线/离线 | 本批离线；在线只读另列证据 | 离线通过不冒充 DSH 已部署 |
| 单/多板 | 单元只在 BoardModel 内合并；跨板同名事实不改 | 重复 PCB 双审、分歧库串板不在本批变化范围 |
| 普通器件/CBB | 普通多单元器件；无 partId 的普通件旧回退 | CBB 未覆盖，不得借本批宣称恢复 |
| 负对照 | DCDC 复制件、R24 跨页复制、缺 Unique ID/Device、引脚冲突 | 不得把真重号静默合并 |

必须先写会失败的新测试，再实现。聚焦测试至少：552、040、040b、049、105、107、038L/038 符号差分、owner/layer；其他派生红项只报告，不越文件域修。每个 pytest 用独立 `--basetemp=.tmp_pt_552_<用途>`，不跑全量。

至少两次因果变异：① 让实例忽略单元引脚子集，新真实网表断言必须红；② 让物理身份判断忽略不同 partId，同 partId 负对照必须红。变异后一律 `cp` 备份恢复并核对 SHA-256，禁 `git checkout/restore`。

## 6. 纪律与交卷

- 实施前把本批所有既有文件备份到 `.tmp_552/backup/`；记录备份哈希。
- 零 git 写、零 `rm/unlink`、零发布、零真实工程写；不得改宽旧断言、skip/xfail、调阈值凑绿。
- 一个 coder，最多 40 步或 30 分钟；只跑指定聚焦测试。
- 交卷 ≤2000 字：实际 diff、测试命令与汇总原文、两个变异红→恢复哈希、正确网表读数、未覆盖维度。
- 若需要改 `core/model.py`、扩 CLI、改 fixtures 或触碰他人未提交文件才能继续，立即停止并交回最小下一步，不自行扩域。
