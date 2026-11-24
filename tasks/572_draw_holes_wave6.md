# 任务书：572 — 绘制线挖洞第六批（批量差分 + 未审面，只读）

- 批号 **572**　日期 2026-11-24　（第五批回来后再开，本文件先备好）
- 承接 565/566/567/568/569/570/571。本批两个主题：**全量电路差分**（用仓库自带电路批量跑编译，找统计意义上的假绿/假拒）与**最后几块未审面**。
- 只挖不修；每条带 `FIX:` 一行；开工记 HEAD + 被审文件 sha256（树在动）。

## ① 前因

- 前五批多为「单点复现」：手工构造一个输入、看一处行为。仓库里 `blocklib/modules/circuits/*.json` 有成套真实电路，**从没被批量跑过**——「ok=True 但图明显不合规」或「拒因点名错东西」只有批量差分能统计出来。
- 未审面还剩：`connector/src/actions.ts` 全量（566-D 只看守卫）、`engines/draw.py`（77 KB）、`core/pintable.py` + `engines/pintable_check.py`、`commands/draw.py` 命令链、`svgpreview` 剩余部分。

## ② 八缝

| 缝 | 地盘 | 只查这些 | 探针 | 报告 |
|---|---|---|---|---|
| **572-A 批量编译差分** | `blocklib/modules/circuits/*.json` + 对应 `blocklib/specs/*.presentation.json` + `blocklib/symbols/profiles.json` | 对**全部**可用三元组跑 `draw compile`（每条带 timeout 60 s，单进程串行）：① `ok=True` 的样本里，用独立 oracle 查「盒出页 / 盒进标题栏 / 未连通网」各几例；② `ok=False` 的样本里，拒因是否点名真实原因（抽 5 条人工核）；③ 两次同输入是否同指纹 | `.tmp_hole572/a/` | `outputs/hole572/a/` |
| **572-B connector 全量** | `connector/src/actions.ts`（约 7000 行，含 446 行 NC writer） | 除 566-D 已查的守卫外：① 写动作的**回读**是否齐全（哪些只回布尔）；② 批量/循环写的部分成功语义；③ 错误码与 `docs/bridge.md` 一致；④ 有没有「静默降级」（旧宿主不支持时假装成功） | `.tmp_hole572/b/` | `outputs/hole572/b/` |
| **572-C `engines/draw.py`** | 77 KB，未被任何一批审过 | 入口函数与错误处理：输入→输出的契约、退出码、异常吞没、与 `cli.py` 的重复判断（两处口径不同即洞） | `.tmp_hole572/c/` | `outputs/hole572/c/` |
| **572-D pintable** | `core/pintable.py` + `engines/pintable_check.py` | 引脚表解析/校验：单位、脚名归一、缺脚/多脚、同名脚、`pintable check` 的退出码与话术 | `.tmp_hole572/d/` | `outputs/hole572/d/` |
| **572-E `commands/draw.py` 命令链** | 命令注册与分派 | 每个子命令的参数→函数→返回值链是否完整（参数丢失/返回值被丢/异常被吞）；与 `cli.py` 同名逻辑是否两份 | `.tmp_hole572/e/` | `outputs/hole572/e/` |
| **572-F svgpreview 剩余** | `engines/svgpreview.py` 除字体/控制字符/载体之外的部分 | 坐标变换、layer 顺序、旋转/镜像绘制、空页/超大页、缩放 | `.tmp_hole572/f/` | `outputs/hole572/f/` |
| **572-G 属性与文字落图链** | `drawapply` 的 `attributeMoves` / `wire_name_row` / `text metrics` 交叉 | 属性移动是否记账（570-D 已钉 census 盲）、文字载体在属性移动后是否失效、位号/值行与原生 ATTR 的一致性 | `.tmp_hole572/g/` | `outputs/hole572/g/` |
| **572-H 回归网对拍** | `tests/` 里所有 draw 相关断言 vs 生产函数实际行为 | 抽 20 条测试断言，逐条问「把被测函数的一个关键分支改坏，这条断言会不会红」——用桩插件（**不改测试文件**）实测；产出「空转断言」清单 | `.tmp_hole572/h/` | `outputs/hole572/h/` |

## ③ 交付与纪律

同 571 §④–§⑥：六栏 + `FIX:` 一行 + `holes.json`（`boardwise.hole572/1`）；只读、零 git 写、不删、不碰真机、探针 `.tmp_hole572/<seam>/`、报告 `outputs/hole572/<seam>/`；每缝 ≤25 步或 ≤20 分钟；正文 ≤1200 字。

**572-A 额外**：批量跑必须单进程串行、每条命令带 timeout、总时长控制；失败样本与成功样本**都要留原始 stdout**，不许只留汇总。
