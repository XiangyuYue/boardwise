# 038Q11A：绘制线缺口——Buck 主回路与电源/地旗标

日期：2026-11-12。来源：038Q11 的 SY8089 block 离线试点。**owner=绘制线**；CBB 只提供
真实身份、网表、PresentationSpec 与负证据，不在 CBB 批里修改 grammar。

**状态：搁置（岳 2026-11-12 裁）。** 保留已有证据，不继续 CBB 绘制相关开发，不 plan/apply。

## 已证事实

- 038Q10 已给 SY8089 block 的七个 part 绑定真实 symbolRef；identityStatus=bound，
  但 catalog/notForDrawCompile 仍为 true。
- `blocklib/specs/sy8089_buck_3v3.presentation.json` 使用现有 `ic-periphery`，没有 userLocks、
  像素坐标或位号特判。真实 `draw compile` exit 0、3 candidates、3 候选 hard=0，
  `outputs/review/038q11/verification.json` 的 6/6 网逐脚相等。
- **主代理已亲看 `cand1.svg`，视觉拒收**。机器合法不等于可读，更不能交付。

## 两个根因

1. `ic-periphery` 只绑定 U/core、port.VIN/rail、port.GND/gnd、C_IN、R_FBB；
   **C_HF/C_OUT/L/R_FBT 全部未绑定**且不报 stray。电感与输出反馈因此落在自由货架，
   首候选虽 crossings=0，仍不形成可读的 Buck 主回路。首候选另有 bends=10、
   unaligned_part_pairs=14，不能拿软指标掩盖语义缺口。
2. VIN/3V3 都报 `power net drawn without a power flag`；GND 退化为 `port.GND` 网络标签，
   没有地旗。受管 book 当前只有 19 个器件符号，没有 PWR/地旗族；flag 的 net id 命名与
   `port.*` 对齐也必须单独裁定，不能简单把 `port.` 字符串拼进符号名。

## 必须同时满足的验收

- U.LX→L.1→L.2→3V3 是明确主回路；L 不得接到 VIN。
- R_FBT/R_FBB 形成 3V3→FB→GND 分压，FB 回到 U.5；C_OUT/C_HF 在输出，C_IN 在输入。
- EN 是独立边界标签，不与 VIN 合并；VIN/3V3/GND 均为真实旗标，禁网络标签替代。
- 逐脚继续 6/6、0 短路、0 悬空；四个 negative control 不被放宽。
- 主代理或岳渲染后逐区视觉复核，能一眼说明 Buck 的输入、开关节点、电感、输出和反馈。
- 未通过前不得 draw plan/apply，不得把 catalog/notForDrawCompile 改 false，不得端给用户。

## 负证据与约束

- 候选与编译：`outputs/review/038q11/cand{1,2,3}.svg`、`compile.json`、`verification.json`。
- L 错接 VIN、EN 并 VIN、删 R_FBT、删 C_OUT 的反例已经执行；机器接受 L 错接时，
  源网对账能抓到，说明现有 ok=True 不能代替拓扑验收。
- 本任务不要求新建几百行 Buck 专用语法。可评估 rail 集合、输出侧绑定和语义约束的最小
  组合，但任何改动必须归绘制线，并保持既有 CH34/反激/分压/LDO 的零移动基线。
