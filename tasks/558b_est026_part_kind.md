# 558B：EST026 连接器声明的 shared 小批

## 1. 前因后果

558 的真实重算证明：机械件和大多数连接器已按义务分类，但 EST026 三行仍为 `ic-facts` 和七键。原因是原理图侧只有 U 位号、`EST026` 与“插件”，没有货架 category 或封装词可让 `classify_part` 读成 connector。公开目录把它列为 Through Hole Quick Connects/Disconnects；主代理对 C52878 扫描图的视觉复核确认标题为“6.3端子(双脚内固定式)技术图纸”。这些只支持**品类识别**，不支持身份或 IC facts 签核，边界见 `evidence/558/est026-visual.json`。

## 2. 最小 shared 裁决

在现有 `core/partkind.py` 的 `CONNECTOR_WORDS` 增加精确族词 `EST026`，与既有 `MX1.25`/`XT60` 同一机制；不得加 `EST` 前缀，不得修改 IC 优先级、脚地板、设计器兜底或其他词。这样 `classify_part` 在同一声明来源下返回 connector，558 的 `datasheet_obligation` 自然转 `connector-pinout`，不需要写货架或在 checkup 复制第二份判型。

这是 shared 独立批，不能与 559 的 protocol/CLI 集成并行；先等当前 shared 锁释放。两个实际消费者必须同时验证：

- checkup：真实 `.tmp_555` 只读重算，EST026 三行 `connector-pinout`、`missingFacts=[]`、`pinoutSource=none`，不列七键，仍在 unreviewed/needs，verdict 不变。
- 规则：合成的 U 位号 EST026 二脚端子不再被 DecouplingPerIC 当 IC；普通 IC 和其他被动件基线不变。

## 3. 文件域与禁触

仅 `src/boardwise/core/partkind.py` 的精确词、新 `tests/test_558b_est026_part_kind.py`（或并入558测试）、`.tmp_558b/`、`.tmp_pt_558b/`、`evidence/558/`。不改 checkup.py、绘制线、bridge/CLI、fixtures、货架/facts trust、真实工程。先 cp 备份 partkind.py 并记 SHA。零 Git 写、零 rm/unlink、零全量、零真机、零部署发布。

## 4. Negative controls 与验收

- 新测试在加词前必须红：`classify_part(EST026).kind != connector`；加词后 connector，且 `EST` 不加词时不得命中任意 EST 开头 IC。
- 一个普通三脚 IC 仍走 ic-facts；U 位号 330k 电阻与既有 `test_190_part_kind.py` 不回归。
- `tests/test_558_datasheet_obligations.py`、`test_190_part_kind.py`、`test_558b_est026_part_kind.py`、owner/layer/doc-claims 聚焦通过。
- 真实重算比较总 unreviewed 不变、机器待签三份不变、verdict incomplete 不变；EST026 不再要七键，身份仍只是 catalog-associated，不写 facts。
- 主代理独立变异移除精确词，合成与真实分类均回落并转红，cp+SHA 恢复。

## 5. 交卷

一个 coder，≤20 步/15 分钟，≤1200 字。实际命令→汇总→前后计数、SHA 与未覆盖项。不得把品类证据写成厂家身份已确认或脚表已取得。

## 实际完成（560 收尾时补记）

- `core/partkind.py` 精确族词已落工作树；EST026 三行由 `ic-facts` 转 `connector-pinout`——不靠给货架补 C52878、不改 `is_c_number` 语义、不动 tests/fixtures。
- 父移除该族词 → **3 failed**，cp+SHA 恢复后聚焦 **68 passed**；新 10 例与修复后子集 109 passed 见 `evidence/558/558b-marked-seed-fix.md`。
- 真实重算 needs 仍 15→11、`verdict=incomplete` 不变；身份判类变化不等于身份已证实。
- 状态：**工作树完成、未提交未推送**。
