# 任务书：604（shared）— V4 facts 证据元数据与坐标反证

## ① 前因后果

用户要求修 `outputs/hole570/TRIAGE.md`。G2 报告有三项：

- **G2-H1** 指称 `eprj3` 与 `v4facts` 对 y 取负两次。复核发现这两层不是同一种转换：`eprj3.transform_text` 把 V4 `yAxisDirection=up` 的文件坐标变成既有 V3 stored-y 形状；`schematic.page_y` 再把 stored-y 变成 canvas-y。`tests/test_038_eprj3.py::test_y_axis_up_reads_the_same_board_as_the_default_frame` 明确用成对的 up/down 文件证明二者必须得到同一模型与几何。原探针只删除 `up` marker、保留正 y，按现有格式合同会把该记录解释为另一种 down 输入，不再是同一电路，不能据此要求坐标不变。若按原 FIX 删除 `page_y` 或停止 eprj3 的 COMPONENT flip，正常 up 文件会整体反号。本批不得改这两个坐标行为，须补成对反证与准确注释，并把 H1 的“按原建议修复”记录为拒绝/证伪。
- **G2-H2** 是真实的证据漂移：旧 `boardwise.v4-facts/1` 产物无 generator、无 x/y，派生 `presentation_evidence` 时会被当成“工程无 pose”。需要新元数据与旧产物具名拒绝。
- **G2-H3** 是真实单位缺失：facts meta 应声明 page unit = 10 mil，不能靠读者从 A4 尺寸猜。

本批是 shared 证据合同集成批，与 grammar/绘制算法分开。只改 `v4facts` 证据边界，不改 parser、page_y、agent-adjusted 的几何算法或 CLI 形状。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批 602/603 的改动必须保留。
- `src/boardwise/engines/v4facts.py` SHA-256 `9e2a88aa2441115c49ccb477056b32b484d7f24f4575c5cbb1cce55dfec03ed0`。
- `src/boardwise/parsers/eprj3.py` 当前 `0f7a17eae8e43a3a5d11e2b821f468a2c3806dfea1f2ae6a997b04eabc47299f`，**本批不修改**。
- 当前 v4facts 217 行对 body y 调 `page_y`；106 起 read_v4_facts 返回的 meta 只来自容器；549–608 的 `presentation_evidence` 不验证旧 facts 的生成器或姿态覆盖。
- 既有坐标钉：`tests/test_v4_facts.py:344-356`、`tests/test_agentadjusted.py:318-341`、`tests/test_038_eprj3.py:202-220`；`evidence/556/parent-mutations.md` 已证明去掉 page_y 负号会有 4 红，仍须本批独立反证而非只引用旧绿。
- `src/boardwise/__init__.py` 有 `__version__="0.6.3"`，可用作 generator 版本，不 bump。
- 他人 `core/circuitsemantics.py`、563 文件、`tasks/review-line.md` 和临时文件禁触。开始先 cp 备份 v4facts 到 `.tmp_604/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/v4facts.py`（meta、legacy evidence 拒绝与相关注释/docstring）
- `tests/test_604_v4_facts_metadata.py`（新）
- 本任务书、`.tmp_604/`、`.tmp_pt_604/`、`evidence/604/`

禁止：`parsers/eprj3.py`、`parsers/schematic.py`、`agentadjusted.py`、CLI、core model/changeplan、connector/DSH、fixtures、历史证据、他人未提交内容。不得改 schema 名、page lock 坐标、网名/实例字段或输出几何；不得新增第二套 V4 读取器。既有断言不得删改宽、skip/xfail。

## ④ 交付物与验收

### A. 坐标反证（不接受原 H1 的伪复现）

新增成对 V4 工程（可用新测试内的最小 writer，不改 fixtures）：同一实例在 down 文件中 stored-y=-500、在 up 文件中 raw-y=+500 且带 marker；两者 `read_v4_facts` 的实例 canvas pose 都必须 `(x=300,y=500)`，并且 `collect_page_layout` 的 y 也一致。缺 marker 的 down 文件继续使用 -500→+500。不得采用“up 原值 +500 删 marker 后仍 +500”的断言，它混用了两种文件坐标。

测试应先证明现有生产在此项为绿，所以它不是 H1 的修复先红；报告必须明确“原 reproduced 经格式成对反证被推翻，生产坐标零改动”。随后去掉 `page_y` 负号或对 COMPONENT 禁用 eprj3 flip 的变异必须让成对断言红，cp+SHA 恢复；该变异在临时副本/本文件实施后立即恢复，不保留。

### B. H2/H3 先红与实现

1. 新 facts 的 `meta.generator` 包含 `boardwise.v4facts` 与当前包版本；`meta.instancesWithPose` 等于同时具有有限数值 x/y 的实例数（bool 不计数，缺轴不计）；`meta.units=="page-unit (10 mil)"`。无姿态实例仍保留 x/y absent，不得伪造 0。
2. 旧 facts（schema 相同、无 generator）调用 `presentation_evidence` 必须 `ValueError`，错误说明旧产物缺生成器/姿态口径，要求用当前 `draw v4-facts` 重生成；不得静默派生 0 姿态 evidence。新 facts 正常派生不变。若输入不是 v4-facts schema，沿用现有错误/行为，不扩大无关校验。
3. `presentation_evidence` 的 notes 改成准确的两段边界：V4 up→V3 stored 由 eprj3 完成，stored→canvas 由 page_y 完成一次；不能继续写容易误解的“v4facts 自己 exactly once”而不提前级。单位说明放入 facts meta，必要的话 evidence 加性携带同源 meta，但不改 work-order schema。
4. 先对未改生产跑 H2/H3 新测试，确认元数据与 legacy 拒绝用例红、正常 controls 绿。修后至少：

```bash
.venv/Scripts/python.exe -m pytest tests/test_604_v4_facts_metadata.py -q --basetemp=.tmp_pt_604/new
.venv/Scripts/python.exe -m pytest tests/test_604_v4_facts_metadata.py tests/test_v4_facts.py tests/test_v4_facts_cli.py tests/test_agentadjusted.py tests/test_038_eprj3.py tests/test_owner_rules.py tests/test_layer_rules.py -q --basetemp=.tmp_pt_604/neighborhood
```

### C. 变异与兼容矩阵

除 A 的坐标变异外，再做两项：① 删除 meta.generator/instancesWithPose 的生成；② 删除 legacy generator 拒绝（或 units）。每项目标测试必须先红，cp+SHA-256 恢复并复绿；总有效变异至少三项。保存原文与恢复 hash。

兼容矩阵：合成 `.eprj3` up/down 与旧/新 facts JSON 为覆盖；DesignModel/agent-adjusted 仅邻域；V3 `.epro2`、V4 真机、在线容器、多板+库、CBB 未覆盖。negative control：正常实例 pose/identity/net facts 不变；真正无姿态的新工程不被误报为旧文件，只在需要姿态的既有下游保持拒绝；多板选择不变。无新原理图、无真机/视觉声明。

## ⑤ 纪律与红线

零 git 写/移动/删除，禁止 rm/unlink；不跑全量，不接触 bridge/daemon/EDA，不部署/发布。pytest 独立 basetemp、单进程探针、命令带 timeout。变异只能 cp 备份恢复并 SHA-256 对照，禁 git checkout/restore。不得为迎合格旧探针修改正确坐标，不得伪造旧证据 generator，不通过改测试隐藏 H1 反证。shared 不再与算法批并行实施。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不再派代理。交卷 ≤2000 字，依次写：H1 反证与零坐标改动、H2/H3 先红与修后完整汇总、至少三项变异及恢复 hash、兼容矩阵/未覆盖项。证据落 `evidence/604/`。缺成对反证、先红或变异，只能写「停止/未完成」。

## 交卷记录（coder，2026-11-25）

完成。证据 `evidence/604/`（REPORT.md + prered/post 日志 + 4 份变异日志）。

- **H1 反证**：原 reproduced（删 marker 留 +500）混用两种文件坐标，被格式成对反证推翻；
  `eprj3.py` 与 `page_y` 零改动。新测试用同一电路的 down（存 -500）/ up（存 +500 带标记）
  成对断言 `read_v4_facts` pose `(300,500)` 与 `collect_page_layout` part y `500`，未改生产时即绿。
- **H2/H3 先红**：未改生产 `8 failed, 4 passed`（8 红为 meta/计数/legacy 拒绝/sourceMeta/notes）。
  修后：604 单文件 `12 passed`；指定邻域 7 文件 `144 passed`；额外消费者
  （540_cli_draw/review/shared、591、v4_islands）`60 passed`。
  实现：`meta.generator = "boardwise.v4facts 0.6.3"`、`meta.units = "page-unit (10 mil)"`、
  `meta.instancesWithPose`（排除 bool/非数值/非有限）；旧无 generator/instancesWithPose 的
  `boardwise.v4-facts/1` 在 `presentation_evidence` 抛具名 ValueError（含 `draw v4-facts`）；
  非该 schema 输入行为不变；evidence 加性 `sourceMeta`；notes 改写为 eprj3 up→stored 与
  page_y stored→canvas 两层。`tests/test_v4_facts.py` 的两条旧 note 子串断言未改，新 note 保留
  子串并补前级（同段 "two layers"）。
- **变异**（4 项，均先红；`cp .tmp_604/backup/v4facts.py.impl` 恢复 + sha256/cmp 一致，
  `10b371a0…e050ca`）：M1 去 `page_y` → 3 红；M2 删 generator/instancesWithPose 生成 → 6 红；
  M3 删 legacy 拒绝 → 3 红；M4 删 units → 2 红。恢复后 12 passed。
- 文件域：仅 `v4facts.py`（+84/-7）与新测试；`.tmp_604/`、`.tmp_pt_604/`、`evidence/604/`。
  零 git 写、零删除、未跑全量、未触真机/bridge/EDA、未碰 602/603 与他人改动。
- 未覆盖：V3 `.epro2`、V4 真机、在线容器、多板+库、CBB；多板选择仅邻域回归、无本批新断言。
