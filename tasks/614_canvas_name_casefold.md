# 任务书：614 — 画布文件名按大小写不敏感盘去重

## ① 前因后果

`outputs/hole570/d/REPRO.md` 的 **D5**：`unique_canvas_name("boarda.svg",...,used={"BoardA.svg"})` 返回 `boarda.svg`，Windows 上与已有 `BoardA.svg` 是同一文件，第二块板静默覆盖第一块，而报告有两个 canvas_images 条目。当前函数只在精确字符串碰撞时加后缀。

本批只修文件名碰撞比较，统一 casefold 防止大小写变体撞名；不改 SVG 内容、板名、uuid 后缀规则、输出目录或报告字段。保留 POSIX 上更保守也不会丢文件的同一规则。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批保留。
- `src/boardwise/engines/canvasrender.py` SHA-256 `e3750a7b23b06a9971ca113c4bc7fc63a62120c211e13162bfc9589cf46e353b`。
- unique_canvas_name 363–385 行；调用方在返回后将 name 加进 used，故本函数只读 used、候选循环也必须用同一折叠尺。
- 开始 cp 备份 canvasrender 到 `.tmp_614/backup/`。他人 563/review-line/router/临时文件禁触。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/canvasrender.py`（unique_canvas_name 碰撞比较与注释）
- `tests/test_614_canvas_name_casefold.py`（新）
- 本任务书、`.tmp_614/`、`.tmp_pt_614/`、`evidence/614/`

禁止：其它 render/CLI/report/shared/connector/DSH、fixtures 和他人文件。不得改输出文件内容、后缀格式或命名去重用途，不做真实板导出。既有断言不得删改宽。

## ④ 交付物与验收

1. 将 used 与 candidate 都按 `casefold()` 比较：首个名字无碰撞保持原样；BoardA/boarda 碰撞必须生成不同文件名的 `boarda-<key后6位>.svg`；该候选若与 used 中另一大小写变体碰撞，ordinal 继续递增，不能循环返回同名。
2. 保留扩展名与 key 后六位，空 key 的 `-2/-3` 规则；Unicode 字母大小写按 Python casefold，不只 ASCII lower。
3. 先对未改生产运行大小写碰撞与二次碰撞用例，必须红；无碰撞、精确碰撞旧后缀、空 key 控制绿。可在 tmp_path 真写两个返回名，证明不会只留一个文件（无需真实板）。

修后运行新测试、canvasrender/checkup canvas 邻域、owner/layer；不跑全量。至少两项变异：① 仅初次比较 casefold、while 不折叠；② 完全恢复精确比较。每项对应测试必须红，cp+SHA 恢复并复绿。

兼容矩阵：纯命名函数与 Windows tmp_path 文件写；真实 EDA/多板/CBB 未覆盖。negative control 为无碰撞文件名、正常精确碰撞后缀、SVG/报告内容不变。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、命令 timeout、单进程。不得用删除旧文件验证覆盖，不修改板标题或 uuid，不用额外依赖探测文件系统。

## ⑥ 预算与交卷格式

一个 coder，最多 30 步或 20 分钟；不派下级。交卷 ≤1500字，含先红/修后汇总、两个返回值与实际文件数、两项变异与 SHA 恢复、未覆盖项。证据落 `evidence/614/`。缺二次碰撞或变异只能写「停止/未完成」。
