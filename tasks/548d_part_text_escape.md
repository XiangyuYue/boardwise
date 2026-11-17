# 548D3D-H4：本件文字避让本件水平引脚逃逸带

## 基线与唯一缺口

- 开工生产哈希：`drawcompiler.py=c8e483fcfc4aafba3e55655b8711d9ce05ddc70057baf9ffe3501b104ddeba26`，`placement.py=326d96e9ffa265077538fceb4ba385e0406f78927b904e33178440595da9c4a8`。
- 31 条跨侧/host-binding/flag-seat 聚焦测试已于当前工作树复跑通过。
- 冻结输入：`evidence/548D/host-binding/live-reference/circuit_hostbound.json`、`profiles_hostbound.json`，不改电气归属或符号库。
- `evidence/548D/host-binding/h3/compile_real64.py` 当前因 U1.48 无合法旗位拒绝；pin48 的真实 tip 在 `(65,-45)`，水平逃逸段穿过本件 `U1` 文字 `(73,-47.5,88,-38.5)`。完整坐标见 `h3/pin48-geometry.md`。

## 完成条件

只在 `_part_texts` 的文字决策中，让当前 part 的位号/型号避开当前 part 水平引脚的外向首段逃逸区；逃逸方向和位姿必须读真实 profile/pose，长度消费现有 `FLAG_LEAD`，不得新增实例常数。不得把逃逸带塞进 `_seat_first_text_inputs` 的全局 occupied（已实测造成 26 条回归），不得改旗位梯子、页框、near/reach、排名或硬闸。

不改变未启用 `serviceLayout.localSeats=true`、或有 `panelGroups` 的页面行为；真实库声明文字锚点的契约需保持，若确需调整必须先报告证据。完成后真实 64 脚输入须产生 `ok=True` 候选，逐脚、readability、grammar 无硬错误，生成 SVG/JSON；如仍有新拒因，如实停在下一红，不能放宽验收。

## 文件域与禁止事项

- 实现域：`src/boardwise/engines/drawcompiler.py`。
- 新合同测试域：`tests/test_548d_part_text_escape.py`。
- 证据域：`evidence/548D/host-binding/h4/`（可复用 h3 脚本，不覆盖 h3 证据）。
- 不动 `placement.py`、公共 schema、CH34 输入、参考坐标、userLocks、P42 和其他 agent 的 shared/connector 改动。
- 不跑全量、不做真机写、不删除页或文件、不做 git 写。pytest 用 `-n 0` 和独立 `.tmp_pt_548dh_h4_*`。

## 复验

主代理抽 diff、重跑 31 条及新测试、CH34/文法邻域，执行至少两项独立源码变异并 cp+SHA-256 恢复，亲看真实 64 脚渲染；离线三关过后才另行安排 P43 真机。
