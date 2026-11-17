# 548P135 — 完图重选的同网名称行距过滤

> 状态：**机制通过 / 整页未通过**。同网行距与预留重选已验收，证据 `evidence/548P135/README.md`。
> 当前首拒转为C3.2固定地旗房间，下一批见 `tasks/548p136_ground_terminal_room.md`。

## 已有事实

- P133完图重选34/34被rowGap拒绝，已回退；P134证明主比较对象是不同net的LCD_SDA。
- 原 `_local_label_candidate` 只比较同网rows，重选却对所有前序网络rows做L5_DUPLICATE_NET_GAP。
- 实验改为 `row_of[:index]` + 同net且非None过滤后，LCD_SCK/LED1/LED2均重选成功，
  首拒转为C3.2固定地旗房间冲突。

生产基线：drawcompiler `2bb3fceaea0f60ae4b5b7bb8d54c6340b2fe8871231151ede4c9490122cd85d3`，
placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
输入 `evidence/548P125/circuit.full.g3c.pinmap.json` +
`evidence/548P126/full.presentation.service-feedback.json`，库P59。

## 实现范围

只修改重选时的row-gap比较：使用 `row_of[:index]`，按 `nets[item_index] == nets[index]`
且item非None过滤，与原 `_local_label_candidate` 的同网尺一致。
不得恢复P133整段未验收实现、统一拉长、改stubMin/GAP/reach/预算/页框、豁免同网重复名称行。

## 验收与负控

1. 新测试先在基线红：异网近行不得被误拒；同网近行仍必须拒绝。
2. 真实MCU不再报LCD_SCK `no free name box for run to (-105,-25)`，LCD_SCK/LED1/LED2能重选；
   记录C3.2固定地旗首拒，不宣称整页通过。
3. 两项变异：恢复跨网比较复现LCD_SCK拒绝；错误放宽同网比较让负例变绿。Copy-Item+SHA恢复。
4. P43/WiFi geometry不变，P103/P116/P117/P118/P124/P126聚焦无新增红；独立basetemp、`-n 4 --dist loadfile`。
5. 只有ok=True才逐脚/渲染/视觉；否则交机制通过/页面未通过。
6. 子代理20分钟/40步，主代理独立复核；不默认全量、真机、apply或Git写。
