# 548D3D-H6：相邻脚旗位的独立备选枚举

## 已证实根因

H4 解决本件文字挡出线后，真实64脚仍有3V3/GND相邻脚冲突。H5只读实验证明：648次 `_flag_rotation_away` 在真实页0次翻转，不是字形翻转问题；冲突是U1.16与U1.15的水平逃逸后在同一x列的短竖段重叠。`_seat_first_seat_alternates` 把第一条答案的整条lead加入 `blocked_now` 且作为墙体，下一次更长水平档必穿自己的旧竖段，所以每组只返回一个候选。证据 `evidence/548D/host-binding/h5/findings.md` §3。

## 完成条件

备选必须是**同一原始障碍场景下各自合法**的候选，不能把上一个备选的引线当成本次页面的真实障碍；最终两两不重叠由 `_seat_first_joint` 的occupancy/lanes负责。仍须防止返回重复答案：保留已答案的anchor/glyph排斥或使用等价且不自杀的档位游标。第一条必须与旧 `_rail_flag_seat` 相同，不得改单旗默认图、旗形/引线形状族、长度梯、常量、搜索上限、排名、near/reach或硬闸。只在 `_seat_first_seat_alternates` 已启用的localSeats多候选分支改变枚举；localSeats=false和panel路径不变。

先写/跑一个最小相邻VDD/GND几何探针，证明旧实现单候选且新实现至少存在不同逃逸列的合法备选；再跑真实64脚本。若成功必须输出逐脚、readability、grammar和SVG/JSON；若失败记录下一真实拒因，不扩域。

## 文件域与验收

- `src/boardwise/engines/drawcompiler.py`
- `tests/test_548d_flag_orientation.py`（可修正H5中过弱/空转的断言，不能放宽原合同）
- `evidence/548D/host-binding/h6/`

不改H4测试、placement、shared/connector、P42、参考坐标或电气输入；不真机、不git写、不删除、不跑全量。聚焦含H4/H5与旧31共42条，`-n 0`独立basetemp；加CH34/文法邻域。主代理负责diff、复验、≥2变异、视觉及P43。≤40模型步骤或30分钟。
