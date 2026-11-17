# 548P136 — C3.2 固定地旗房间与 GND 分配

> 状态：**冲突已证实，offset未解决，生产未改**。证据 `evidence/548P136/README.md`。
> 当前正常生产首阻前移到service:C2，下一批见 `tasks/548p137_c2_service_seat.md`。

## 当前首拒

生产SHA：drawcompiler `6614fc046b0d8544979f4698cb3eb3c34d75666d8c307f22c40f36fa06da6edc`，
placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
输入 `evidence/548P125/circuit.full.g3c.pinmap.json` +
`evidence/548P126/full.presentation.service-feedback.json`，库P59。

主代理 `reviewed-downstream.log`：
- C3.2固定service-terminal at `(-205,65)` 被leg `(-205,95)→(-205,65)`
  穿过 `(-301,84)-(-94,86)` 的器件/文字；
- C3.2在最终文字场景无assignment、被丢弃，U1.15亦无完整座，GND不完整。
不能移动固定terminal或扩reach/GAP/预算/页框来掩盖。

## 唯一问题

C3.2的固定地旗房间为何被占据，现有serviceLayout/service terminal/host channel/label墙中
哪一项先决定了冲突？先捕获terminal seat、引线、占用盒和对应producer，区分：
1. 固定seat本身位置非法；
2. host channel/label与seat不一致；
3. GND分配器没有合法替代（只能具名拒绝）。

只读侦察先行，若需修复只限draw线必要文件和一个新测试，不新建builder/router。
P43/WiFi geometry必须不变，P135标签回退不得重开。

## 完成条件

- 新测试基线先红，至少两项变异先红并Copy-Item+SHA恢复；不能只断言helper被调用。
- 真实MCU首拒与C3.2逐项对照；只有ok=True才逐脚/渲染/视觉，否则交下一首拒。
- 子代理20分钟/40步，主代理独立复核；不默认全量、真机、apply或Git写。
