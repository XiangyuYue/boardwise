# 038Q13A：CH340 离线试点暴露的呈现缺口

日期：2026-11-12。来源：038Q13 首候选的主代理视觉拒收。本文只分派缺口，不授权修改
grammar、落图或解除 notForDrawCompile。

**状态：搁置（岳 2026-11-12 裁）。** 下列归属与验收锚仅作恢复时的证据，不继续 CBB 绘制
相关开发，不 plan/apply。

## 已证事实

- 真实页编译 4 候选，hard=0，11/11 网逐成员及网名一致，U.7 保持 NC；主代理 Python
  Q13+Q12=24 passed。证据 `outputs/review/038q13/{compile,verification,negatives}.json`。
- 主代理亲看 `cand1.svg` 后仍拒收：D± 的自动 net id 约45字符且每网五处重复，文本互相
  覆盖；`min_text_gap=0.0`，另有一条四弯导线。VBUS/GND 没有真实旗标，GND 在 usb 岛退化
  为 `port.GND` 标签；D_ESD 未绑定、落在自由货架。机器合法不等于人能读。

## 缺口归属与顺序

1. **CBB 下一批：内部网的语义命名**。`auto:D_ESD...|U.D-` 是成员拼出的机器 id，不应直接
   成为人类标签。由 module-import 的 curation 显式裁定内部网 id（USB_D+/USB_D-/V3/CC1/CC2
   等），保持 members/NC/端口和生成哈希合同，禁止在绘制器里按位号或长字符串特判。先消除
   CBB 自己制造的不可读名字，再重跑 Q13；这不是已暂缓的“网表语义函数层”。
2. **绘制线：多脚 ESD 绑定与可逆短载体**。`ic-periphery` 不绑定 D_ESD；给 D± 声明
   `localLabelObligations` 又以 `layout-unsat` 拒绝，D_ESD.1 的短直载体所有候选落点都碰
   邻脚。需要通用的多脚保护器件角色/服务座位与标签布局，不得用手摆坐标掩盖。
3. **绘制线既有旗标缺口**：受管 book 没有 PWR/GND 旗标族，`port.VBUS_5V` 报无电源旗，
   usb 的 GND attachment 失败退为标签；与 `tasks/038q11a_buck_grammar_gap.md` 的旗标/net id
   对齐是同一平台问题，不在 CBB 批伪造旗标。

## 验收锚

- CBB 命名后 11/11 网成员、NC、四负例继续保持，标签不再出现 `auto:` 长串；普通模块读数不变。
- ESD 一眼能看出保护哪对数据线、CC 电阻各回各的 CC 脚，D± 不出现 U 形回环或标签互压。
- VBUS/GND 使用真实旗标；文本不互压，UART/DTR/RTS 边界可读。
- 三项未过前，CH340 只保留离线候选，不 plan/apply、不端给用户、不晋升。
