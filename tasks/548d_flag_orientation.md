# 548D3D-H5：旗位候选保持已验证的引线/字形方向

## 实测起点

H4 已把真实 64 脚 MCU 推进过 U1.48 的文字拒绝，当前 `drawcompiler=038db465ce549ba87bd2444c6014d96ff1b76ae055f59bc8297833258a534d3c`，主代理复跑新7+原31=38 passed。新红为 U1.16 的3V3与U1.15的GND每组仅一个候选且节点冲突。

`_seat_first_net_jobs` 在 `_seat_first_seat_alternates` 已按库字形、lead方向和真实碰撞选位后，又调用 `_flag_rotation_away`（drawcompiler.py:12495-12503）。该函数按“离pad更远”重新翻转rotation，但没有重新跑 `_flag_room` / lead方向尺；pool的 `_seat_first_candidate_seats` 却不做这次翻转。两处可能对同一候选使用不同字形，且最终翻转可能把已通过检查的座位变成冲突/逆向。先用真实输入逐项记录翻转前后rotation、lead、glyph和碰撞，验证或推翻这个根因，不靠猜。

## 唯一缺口与完成条件

统一候选枚举、pool、最终回放对“锚点+引线+旋转+真实盒”的消费。旗保持竖直，电源/地由库glyph kind和rotation共同读；水平脚先水平逃逸、末端短竖段接旗，末段方向与字形一致。不得把仅离pad更远当作合法方向，不能翻转到碰撞或未验证的一侧。优先保留 `_rail_flag_seat` 已验证的答案；若确需另一朝向，必须在同一完整合法性尺下生成该候选。

仅调整 seat-first 的 localSeats 路径，未启用serviceLayout或有panelGroups的旧行为不变。不改常量、搜索上限、near/reach、排名、硬闸、参考坐标、电气归属、库profile或P42。真实64脚 compile 必须 ok=True 才继续逐脚/readability/grammar/SVG；若根因假设被推翻，交回具体实测拒因，不顺手扩到别的算法。

## 文件域

- `src/boardwise/engines/drawcompiler.py`
- 新测试 `tests/test_548d_flag_orientation.py`
- `evidence/548D/host-binding/h5/`（复制real64脚本，不改h3/h4证据）

不改placement/shared/connector/other agent文件，不做git写、真机写、删除或全量。聚焦pytest `-n 0`、独立basetemp；最多40步或30分钟。主代理负责diff、38+新测试与邻域复验、至少两项变异、视觉及后续P43。
