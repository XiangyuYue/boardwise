# 548D3D-F1：同模块独立分压链族

## 实测缺口

`evidence/548D/full-page/semantic-split/`：真实KEY/LED分岛后MCU框443≤546，LED用 `voltage-divider` 可电气闭合且6/6逐脚正确，但 `_result` 只消费 `chains[0]`。第二支R3/D2自由横排、无抽头标签，与R2/D1竖排不一致，视觉判废。LED框276，整页三列宽差41.5；成对同类布局是最小通用缺口，不允许只调页框/间距。

## 完成条件

在 `voltage-divider` 中支持同一模块内**互不重叠的独立链族**：每条链都产生upper/lower/tap/in/gnd绑定、几何约束和DIRECT_WIRE/VISIBLE_TAP义务，不得只画第一条。选择必须确定：共享tap的备选路径或共用arm的链不是另一条独立链；共同power/gnd不意味着重复绑定，共享in/gnd角色去重。

为保持旧页面，只有显式 `textPlacement=native-attr` 且存在 `serviceLayout` 时启用多链消费（与既有pair-reading的两个显式声明同级，但不导入drawcompiler私有函数）；缺省/单链保持原结果。若证明需要公共helper/shared合同，先交锁，不夹改。

真实LED规格以 `derived.led-vdiv.portinput.presentation.json` 为底，LED1_K/LED2_K作为**进入LED指示岛的输入**（portRoles=input；相对于MCU它们仍是输出），seriesBranches为空。新增native-attr用于真实属性行，其它键不改。R2/D1与R3/D2必须同向、同节距/同阅读规则，LED1_A/LED2_A各自可见，6/6逐脚连通；无跨岛长导线，主代理视觉后才签。

## 文件域与验收

- `src/boardwise/engines/grammar/voltage_divider.py`
- 新 `tests/test_548d_divider_families.py`
- `evidence/548D/full-page/divider-families/`

测试：双独立链都有约束/逐脚/同类一致、共享tap或arm不得误选多条、缺省单链不变、既有CH343/电源分压邻域不红。真实LED SVG/JSON和全页frame/packer读数分别记录；整页若仍差尺寸，给下一真实阻塞，不宣称整页通过。

不真机、不git写、不删除、不改电气、页框、near/reach、排名或硬闸。主代理负责diff、变异、视觉与全量。≤40步或30分钟。

## F1A 实测后的触发更正

F1实现证明双链LED成立（236×216.5、6/6、四件同向、两个抽头），但全局native-attr使bmp280/wifi的既有pair-reading失候选。不得为LED让其它岛退化，也不为此引入模块级native-attr公共合同。

多链启用改为**`serviceLayout`存在且`labelPolicy.stubMin>0`**（真实页已有pinGap30+stubMin40），表示作者显式要求端口短桩和同类布局；不再要求native-attr。LED规格去掉textPlacement，保留其他全部语义。缺省、stubMin=0、只写serviceLayout、单链及电源分压保持旧结果。测试相应改为native-attr不启用的负例和stubMin启用的正例，真实整页应在无native-attr下重新测量。这个更正只动grammar谓词/测试/派生规格和证据，不扩shared。
