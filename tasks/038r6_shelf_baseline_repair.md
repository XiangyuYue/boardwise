# 038R6：正式货架候选数据清理

日期：2026-11-11。只处理非绘制线的 12 条货架失败，不改测试期望，不改规则。

## 已核实事实

- `HEAD:blocklib/parts.json` 为 109 项；当前为 110 项。唯一新增 key 是 `candidate.jer1206f1r030`（C46634438），唯一变化既有 key 是 `ic.stm32g431rbt6`。
- 候选件 deviceUuid/libraryUuid/footprint_name/datasheetPdfUrl 全空，facts_trust=candidate；全仓除 parts.json 没有 JER1206F1R030/C46634438 来源引用。它不是可核验、可驱动规则的正式货架条目。
- STM32 在 HEAD 中已有 `category=ic.mcu` 和既有 curated note；当前只在 facts/facts_trust/notes 增加了未经人工核验的自动提取候选 facts，category 本身没有变化。候选 facts 不能留在正式货架里冒充已核验事实。
- `parts.json` / `parts.json.tmp` 的 mtime 都在 2026-11-06，当前没有证据表明有活跃写入。禁止覆盖其他未提交数据。

## 裁定

- 原始当前文件先备份到 `.tmp_038r6/parts.before.json`，候选件与 STM32 候选 facts 的完整对象也留在 `.tmp_038r6/`，不是物理删除数据。
- 用正式 `load_parts` / `save_parts` 写回：移除 `candidate.jer1206f1r030`；仅把 `ic.stm32g431rbt6` 恢复为 HEAD 中同一对象（保留其已 curated 的 category/identity，去除未核验 facts/trust/附注）。`git show` 只读，不使用 git checkout/restore。
- 其他条目保持现状。写后应与 HEAD 的 109 项语义一致；若出现额外差异，停止并查明，不扩大恢复范围。
- 不改任何测试、阈值、category/facts 规则、fixtures、bridge/Connector/DSH/Rust、绘制线；零 git 写、零删除、零真机。

## 验收

- 一个 coder，最多 25 步/20 分钟。先做备份与结构化前后对比，再写正式 API。
- 只跑这 12 个既有失败（独立 `--basetemp=.tmp_pt_038r6`）：
  - parts_library 两个地址/未核验字段检查；
  - harvest 的 fresh-harvest 和 datasheet-link 两个；
  - 039 parts toolchain 的 real-shelf round-trip；
  - 176 sampling-bias 的 category evidence；
  - 527d2 的 legacy byte-identical round-trip；
  - rehome 的 candidate-free 与 positive-control 两个；
  - facts_library 的 109 项；
  - 191b 的 109 entries；
  - harvest_verify 的无参数 --check。
- 必须实际得到 12 passed，且 `git diff -- blocklib/parts.json` 为空或能逐项解释剩余差异；不能改测试数字求绿。
- 报告备份路径、结构化读数、测试计数和最终 diff。若 12 项不全绿，主代理复核，不宣称清理完成。


## 主代理验收（2026-11-11）

- 主代理独立运行原 12 个失败：**12 passed**。
- 正式 API 写回后 `git diff -- blocklib/parts.json` 为 0 行；候选数据完整备份在 `.tmp_038r6/`，未物理删除。
- 没有改测试、规则或绘制线。证据 `outputs/review/038r6/ACCEPTANCE.md`。
