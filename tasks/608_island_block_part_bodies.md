# 任务书：608 — IslandBlock bbox 纳入真实器件体

## ① 前因后果

`outputs/hole570/b2/REPRO.md` 的 **570-B2-2** 实测 `IslandBlock.bbox()` 自称覆盖“everything the block draws”，但 parts 只贡献 `(part.x,part.y)` 退化点。power_entry 4 件中 3 个姿态后的体盒在 block bbox 外，packer 的 keep-out 和 `_page_floor` 看不见器件体。flyback 19 件体盒当前都在 bbox 内，因此它应当成为几何不变对照，不能借修 bbox 改它。

本批只修 B2-2，不与 607 的标题栏派生混批。复用 `layout_island` 已经算出的 `pose_box(profile.body,…)`，不把引脚/文字额外扩张混进器件体，也不另写姿态变换。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；保留前批全部改动。
- `src/boardwise/engines/islandlayout.py` 开工 SHA-256 `cafac48c03cefe0e70829da261708a6e613a5cb23644f92037741202355d1a5f`。
- `IslandBlock` 在 2180 起，`power_boxes` 已有“库存 extents 随块平移”的既有模式；`translated` 2254–2334 必须同步；`bbox` 2352–2353 当前只加锚点。
- `layout_island` 2906–2917 已分别构造 `_part_box` extents 和真正的 `pose_box(body)` obstacles；ring 内每个 body=None 已被排除。构造函数 2920 可把这份体盒加性存入 block，不必重算/新引依赖。
- 原始 oracle 显示 flyback body 出框 0、power_entry 出框 3；输出 `outputs/hole570/b2/readings/oracle_rerun.json` 与探针只读。他人 563/review-line/临时文件禁触。开始 cp 备份 islandlayout 到 `.tmp_608/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/islandlayout.py`（`part_boxes` 加性字段、平移、bbox、构造与相关注释）
- `tests/test_608_island_part_boxes.py`（新）
- 本任务书、`.tmp_608/`、`.tmp_pt_608/`、`evidence/608/`

禁止：drawcompiler/pagecompiler/placement/readability/CLI/shared/connector/DSH、fixtures、607 的 hunk（若尚未开始）、既有测试及他人文件。不得用 `_part_box` 的针尖总框替代实际 body，不能修改姿态、岛内布局、gap、页框、keepout 或候选排名。既有测试若因合法 packer 变化而红，先交独立几何证据，不擅自重钉。

## ④ 交付物与验收

### 实现与先红

1. `IslandBlock` 新增 `part_boxes: list[Box]` 默认空列表，顺序与 block.parts 对应（或另存可核对的同等结构）；`layout_island` 填入当前姿态后的 profile.body 盒，body=None 的处理必须与 parts 对齐，不能错位。`translated` 对每盒施加同一 dx/dy，不重算姿态；`bbox()` 纳入这些盒，`PackedPage.bbox()` 自动得到真实并集。
2. 新测试先对未改生产运行：power_entry 每个有 body 的器件，其 `pose_box` 必须被所属 block.bbox 包含，基线至少 3 个不满足；平移后每个体盒仍被包含且位移一致。flyback 19 件均包含作为控制。
3. 用原始独立 oracle 重算 flyback 与 power_entry，记录每块 bodies_outside_block_bbox；不能只调用新 `block.bbox()` 自证，要独立从 LayoutPart/profile 复算。
4. 合法性变化：power_entry packer 的 floor/columns 若改变，记录前后 block/page bbox、keepout_conflicts 和最终 plan 的独立页框/标题栏检查；不能把退化点仍当安全。flyback 的 blocks/plan geometry 应保持不变（若 607 已改标题入口，分开说明其影响，不混归因）。
5. 无 profile.body 的老 block/手工构造保持 bbox 旧行为，空 block 仍 `(0,0,0,0)`；power_boxes/texts/labels/segments 覆盖不回归。

修后运行新测试、530A/520M/岛布局与标题栏邻域、power_entry/flyback 相关测试、owner/layer；文件名先 Glob 核实，不跑全量。任何新红逐名报告并做因果分析。

至少两项变异：① bbox 不并 part_boxes（或构造不存）；② translated 忘记平移 part_boxes。每项对应测试必须红，cp+SHA 恢复并复绿。另用 flyback 对照证明不是“改所有几何”。

兼容矩阵：离线 island block/page packer 两个层次；无 body/旧构造负控。真机/V3/V4、多板/CBB 未覆盖；只有几何机器检查，不自动获得视觉签收。若产生新候选渲染，必须交 SVG/PNG 路径供主代理亲看，不能只报数。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得放大页框或改岛声明/布局凑绿，不新增第二套 packer，不把器件体仍写成锚点，不修改 fixtures 和他人文件。两轮同拒无新证据即停。

## ⑥ 预算与交卷格式

一个 coder，最多 40 步或 30 分钟；不派下级。交卷 ≤2000字，含先红 3 件证据、修后 oracle/平移计数、flyback 对照、完整测试汇总、两项变异与 SHA 恢复、候选/渲染路径和未覆盖项。证据落 `evidence/608/`。有未解释新红或缺变异只能写「停止/未完成」。
