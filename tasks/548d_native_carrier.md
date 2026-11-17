# 548D3D-P1E：单run原生名字也必须落在自己的载体上

## 真实失败

P43规格：真实64脚MCU、localSeats、stubMin=40、textPlacement=native-attr。当前 `draw compile --page-box 0,0,1170,825` 一候选且机器检查空，但未绑 `draw plan` 拒绝六个名字：label anchor在40单位carrier终点，box在终点旁，native属性行不在x360..400或x130..170的既有run上。日志 `evidence/548D/host-binding/p43/plan-native-unbound.log`。

根因：`drawapply._native_carrier_cover`（约2324）只处理 `_native_split_nets` 中的label，单run被跳过；但 `native_carrier_problems`（约2533）明确Statement 1没有single-run exemption。后者已经点名P35同类缺陷。既有cover在长run能容纳名字时只做最小box平移，不改wire，正适合本次40单位carrier。

## 唯一缺口与验收

让 `_native_carrier_cover` 对所有 `_visible_native_label` 执行既有“row必须在carrier上”的修复，不再以split作为Statement 1的前置条件。保留split仅用于Statement 2的命名义务；已在run内/已有native_stub_rows的label不动；短run、碰撞、页框和foreign-wire规则不变。对P43这类长run应移动row进入既有40单位carrier，不增加/延长wire，不添加装饰文本，不绕过gate。

- 文件域：`src/boardwise/engines/drawapply.py`、`tests/test_543i_visible_labels.py`、`evidence/548D/host-binding/p43/apply-fix/`。
- 先加能识别旧缺陷的单run合同：可见native label在run终点外、run能容纳文字时cover后row在run内、wire点列不变、native_carrier_problems无该项；普通/非native及已在run内的行为不变。
- 跑该测试文件及native/label邻域，重跑P43未绑plan命令并保存日志；plan必须planned且六个native行有attributeMoves依据，不能仅把warning藏起来。
- 不真机、不改connector/drawcompiler/shared、不git写、不删除、不跑全量。主代理负责diff、变异、完整三关与P43。
