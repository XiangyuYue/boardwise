# 548K：名字桩下限同源 + 单脚标签网先预留（机制批）

日期：2026-11-14。owner：绘制线。基线 HEAD `f23b801`（工作树混合未提交）。
证据：`evidence/548K/README.md`。**图未签收**，不宣布 548J/548D 完成。

## 1. 一个缺口

548J 十二跳把三条合法路径全部卡死在同一句话上：`draw plan` 报
`net <X>: the label at (…) has no free name stub`。实测根因不是"没地方放"，是两层不同源：

1. **长度不同源**：编译期 `_reserve_label_stubs` 承诺 `LABEL_LANE_STEPS = 2` 格 = 10 单位；
   交付侧 `drawapply._label_stub_candidates` 按 `labelPolicy.stubMin`（本例 40）找桩。
   中间 30 单位无人预留，路由自由占用。
2. **顺序不同源**：名字桩带在旗标引线与宿主支路**之后**才排。探针原文：`ESP_TXD cells=9
   accepted=False`，而 `3V3` 的旗标引线先拿到 cells=40–45（其中一条就在模块右列引脚的
   escape 列 x=250），路由又沿 x=255 画了宿主支路竖线。等标签轮到，四面已被占完。

## 2. 改法（只 `engines/drawcompiler.py`，两处，均为既有机制的复用）

- 新增 `_stated_stub_floor(presentation)`：读 `labelPolicy.stubMin`，缺省 0。
- `_reserve_label_stubs`：`reach = max(LABEL_LANE_STEPS*grid, 下限)`，`_service_layout_page`
  除外（那条通路已由 `_seat_first_port_columns` 消费同一键）。
- `_lead_lane_reservations`：`stubMin` 阳性时，把**单脚** label 网并入既有 `local_first`
  两趟机制（534 r15 同一理由：声明的载体先预留）。

不新增键、不新增规划器、不调 GAP/页框/`max_nodes`、不动 `pack_frames`、不动 service 页。

## 3. 验收口径（机器部分已过，视觉部分判废）

- 默认关闭：删掉 `stubMin` 一键的同一页面，改动前后 geometry **逐字节相同**
  （`367dbdc9…`）。
- 两项独立变异（M2 只反向顺序 hunk → plan 恢复拒绝；M3 只反向长度 hunk → 16 线/弯桩回退）。
  恢复点 `drawcompiler.py = 6351A85E…`，三次 cp+sha256 还原均 MATCH。
- 因果项回归 `tests/test_548k_stub_lane.py`：正常树 2 passed，M4/M4b（顺序 hunk → `if False:`）
  **2 failed**，两次都 cp 还原 MATCH。
- 收口聚焦 14 文件 **297 passed / 1 skipped**；Rust 线 fmt/clippy/test 全过。
- **完整四线（2026-11-14，岳授权）**：pytest 全量 **8 failed / 11042 passed / 22 skipped /
  1 xfailed / 1 warning（27:00）**；connector **740 passed** + typecheck；dsh-plugin
  typecheck + **137 passed / 1 skipped** + build；Rust fmt/clippy/test 全过。
  8 条红经 M5/M6 两次反向变异归因：**6 条为本批造成**（534x×2 属顺序 hunk；534/543c/548c4/548c6
  属长度 hunk），1 条既有 panel 路由次数、1 条既有 Windows 环境红。
- **548K-R 收口（已落）**：不改他人金标准；两处行为收进显式开关
  `labelPolicy.stubLaneReserve: true`（默认不写 = 逐字节旧行为，`false` 等价不写，只在 true 时
  序列化，非布尔具名拒绝）。文件域四个：`core/presentationspec.py`、`engines/drawcompiler.py`、
  `tests/test_548k_stub_lane.py`、`docs/draw.md`。
  - 主代理独立复验 **63 passed**（534x 整文件 + 四条指名 + 两个 548K 测试 + doc claims）。
  - 校准 WiFi 件三态：不写开关 → 几何 `f4f1c58c00ee…`（与 548J §16 记录逐字相同）+ `draw plan`
    拒绝；写开关 → `draw plan ok=True`（6 件/17 线/7 旗），几何 `81557467…`，parts/labels/segs/flags
    与开门前那版逐项相同；去掉门控 → 6 条老金标准红。
  - 三种变异：放开 reach 门控 4 红、union 关死 2 红、两处全放开 7 红，均 cp+sha256 还原。
- **视觉：判废。** 校准 WiFi 件能建计划（6 件/17 线/7 旗/7 分区/17-18 脚连通），
  但编译器自述 `ESP_EN/ESP_RST: wired route not found; labelled instead`，画成两截裸名长桩
  （200/80 单位）+ 三条名字行贴边；强令成线则 `[wire-through-body]` 0 候选。

## 4. 边界（不做什么）

不落画布、不真机、不 git 写、不宣称 548J-B1 复活、不宣称 548D 自动整页、不宣称 548E/547G。
P44 人工页/P42/P43/Board2/P45 未动。`userLocks`/参考坐标/缩字/降 `stubMin` 一律不用。

## 5. 下一批

1. 本批缺口：回归测试（`tests/test_548k_stub_floor.py`），并要求在 M2 变异下先红。
2. 批次2 主目标：`wired route not found` —— 两脚网在旗标图形与标签盒之间没有合法走廊。
   只在既有 `_flag_pin_lead` / 预留 / 路由同一决策链里补，不新建规划器。
