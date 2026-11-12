# 038Q12：CH340C 模块的显式电气脚位合同

日期：2026-11-12。接续 038Q9/Q10。目标是把 `block.ch340c_usb_serial` 的五个通配组
变成受管、可审计的物理脚成员，并绑定七个真实 symbolRef；不改上游样本，不做 PresentationSpec、
离线绘制或真机落图。

## 已测事实与边界

- 受管 book 已有本模块全部七个 device 的 candidate profile；不得重新逐颗采集或部署。
- CH340C/C84681：`1=GND, 2=TXD, 3=RXD, 4=V3, 5=D+, 6=D-, 7=NC., 8=OUT#,
  9=CTS#, 10=DSR#, 11=RI#, 12=DCD#, 13=DTR#, 14=RTS#, 15=R232, 16=VCC`。
  外部端口名继续叫 DTR/RTS，物理成员必须精确写 `U.DTR#`/`U.RTS#`，不是模糊匹配。
- Type-C/C9900012665：EP 是脚 8/9/10/11；GND 是两个复合脚号 `A1B12`、`B1A12`；
  VBUS 是 `A4B9`、`B4A9`。复合脚号是 profile 的原子键，不拆成 A1/B12 等假想脚。
- USBLC6/C2687116：`1/6=I/O1`、`3/4=I/O2`。同名不是内部短接证明；本合同要求这些
  物理脚都落到各自网络，不依赖器件内部连接。
- AMS1117 的 `U.VOUT*` 仍未裁，保持 unverified，不借本批展开或绑定。

## curation 合同

仅 `block.ch340c_usb_serial` 增加 `identityBinding: "book"` 及以下三个字段；其他资产不加：

```json
"pinGroups": {
  "D_ESD.I/O1*": ["D_ESD.1", "D_ESD.6"],
  "D_ESD.I/O2*": ["D_ESD.3", "D_ESD.4"],
  "J_USB.EP*": ["J_USB.8", "J_USB.9", "J_USB.10", "J_USB.11"],
  "J_USB.GND*": ["J_USB.A1B12", "J_USB.B1A12"],
  "J_USB.VBUS*": ["J_USB.A4B9", "J_USB.B4A9"]
},
"portPins": {
  "VBUS_5V": ["J_USB.A4B9", "J_USB.B4A9"]
},
"nc": ["U.7"]
```

- `pinGroups` 是逐组人工裁定，不是前缀展开算法。只在 bound block_template 上有效；
  key 必须逐字命中上游通配成员，value 非空、每项同 role 且精确解析到唯一物理脚。
  缺映射、额外映射、空组、跨 role、重复/跨网冲突、仍残留 `*` 全部 Err。
- `portPins` 解决上游 `ports.VBUS_5V.at=J_USB.VBUS` 对应两个同名物理脚的问题。
  每个显式脚都必须在 `port.VBUS_5V` 的 members 中；不得把 `J_USB.VBUS` 当成第三个脚，
  不得给 `port_pin_only` 端口另造成员。未声明该字段的端口仍由原来的 `at` 校验。
- `nc` 只收显式 no-connect；本批只有符号自身标作 `NC.` 的 U.7。OUT#/CTS#/DSR#/RI#/
  DCD#/R232 与 Type-C SBU1/2 没有连接声明，不等于 NC，列入 catalog `unstatedPins`。
- 三个字段若出现在未绑定资产或 role_topology 上必须拒绝，防止“写了但根本没生效”。

## 生成器硬约束

- 绑定后的每个 `role.pin` 必须全等命中**恰好一个** profile 物理脚；脚号优先不代表可忽略
  同名碰撞。重复脚名可存在于 profile，但作为成员/NC/端口落脚使用而未消歧时必须拒绝。
  每个 profile 内脚号必须唯一；复合脚号原样比较。
- 以解析后的 `(role, 脚号)` 统计 connected；同一物理脚用“脚号”和“脚名”两种写法跨网也
  必须抓住。`connected ∩ nc = ∅`，NC 不得落在内部网或 port_pin_only 网。
- bound 模块按 profile 逐脚对账：connected、nc、unstated 三类互斥并覆盖全部物理脚；
  `unstatedPins` 使用 `role.脚号`，不得把未声明脚伪造进 net 或 nc。其他未绑定模块读数不变。
- 七个 part 的 catalog/CircuitSpec `symbolRef` 一致且来自 book；CH340 `identityStatus=bound`、
  `unresolvedWildcards=[]`，但 `maturity=candidate`、`notForDrawCompile=true`、`draft=true`。
- DTR/RTS/TXD/RXD 保持既有 port_pin_only；方向/output/input 不变。VBUS_5V 是模块的
  5V 电源负载边界，连接 VBUS、U.VCC、C_VCC 与 D_ESD.VBUS，不是 U.V3，也不作 6M 波特率
  或硬件可用性声明；`part=J_USB`、direction=load 不变。
- 上游 `contracts/module-import/blocks/ch340c_usb_serial.json` 与其哈希保持不变；电气裁定只进
  curation。生成限制要说明“显式脚位映射不代表内部短接/ datasheet/compile/editor/hardware 验证”。

## 生成与文件域

- `contracts/module-import/curation.json`；Rust `module_import.rs` 及 core/必要 CLI 测试；
  新增 `tests/test_038q12_ch340c_electrical_contract.py`，更新 Q2/Q8/Q10 受影响的旧断言。
- 真实 CLI 在两个新临时目录生成并比对；仅复核复制 `catalog.json`、`manifest.json`、
  `circuits/ch340c_usb_serial.circuit.json`。其余三份 circuit、book、上游原件逐字节不变。
- 更新 `docs/rust-platform.md`、本任务书；收尾再更新 SCHEDULE/TASKMAP/handoff 的当前状态。
- 不改 `engines/grammar/**`，不做 PresentationSpec、draw compile/plan/apply，不重启 daemon、
  不热更 Connector、不碰真实工程、不做 git 写。

## 验收与负例

1. CH340 的七个 part 全部绑定真实 symbolRef；五组通配消失，上述 **12 个**显式物理成员逐脚
   落入正确网；A1B12/B1A12/A4B9/B4A9 原样保留，DTR#/RTS# 精确命中，U.7 是唯一 NC。
2. 全部 profile 脚按 connected/NC/unstated 对账；未用功能脚与 SBU 保持 unstated；
   6 个 openInterfaces、11 个 nets、7 个 parts 的既有结构不变，普通器件及其他三资产不变。
3. 至少覆盖：缺/多 pinGroup、空组、跨 role、未声明脚、重复脚名未消歧、复合脚被误拆、
   connected+NC、NC 落在端口网、通配组静默丢弃、portPins 未落在端口网、未绑定资产使用合同。
4. Rust fmt/clippy/module-import 测试、真实 CLI 幂等；Python Q12+Q10+Q2+Q8+邻域及 doc claims；
   `tools/check_symbol_book.py`。至少两处实现变异先红后 cp+SHA-256 恢复。
5. 本批不跑全量、不真机；完成只表示身份与电气脚位合同可机检，不表示可画、可投板或原生 CBB。

## 数据手册补证（2026-11-12，只读研究）

- WCH《CH340DS1》v3B（公开镜像
  `https://docs.sparkfun.com/SparkFun_RTK_Facet_mosaic/assets/component_documentation/CH340DS1.PDF`）
  p3 明写 TXD=`Transmit asynchronous data output`、RXD=`Receive asynchronous data input`；
  VCC 需外接 0.1µF，V3 在 VCC=5V 时接 0.1µF、VCC=3V3 时才接 VCC；SOP-16 脚 7 为
  `No Connection, do not connect`。p4 的 `Unused I/O pins of CH340 should be NC` 是悬空许可，
  不把上游未声明的功能脚自动变成 CircuitSpec 的显式 NC 决定。
- ST《USBLC6-2》DS4260 Rev 7（`https://www.st.com/resource/en/datasheet/usblc6-2.pdf`）
  §2.3 p5 要求 `the track from data lines to I/O pins ... must be as short as possible`，电特性也按
  任一 I/O 脚给钳位指标；没有找到“同名两脚内部短接”的明文，因此本合同不把同名当内部连通。
- Type-C 复合脚号按 profile 原子保存；没有取得 C9900012665 的厂商原始图纸，**EP 8/9/10/11
  与 GND 的关系仍只是上游样本的候选裁定，未获厂家 datasheet 证实**。这正是继续保留
  candidate/notForDrawCompile 的原因之一，不得把本批写成电气设计已认证。

## 实施与独立复验（2026-11-12）

- 子代理完成 curation、Rust 生成器、15 个 core 用例（含主代理复审补出的 portPins 不在端口网
  负例）和 11 个 Python 发布物用例；真实 CLI 两个新目录生成一致，只更新 catalog/manifest/
  CH340 circuit。book、上游原件和其他三份 circuit 哈希不变；CH340 circuit SHA-256 为
  `7483fbf864b7b62b220eca72a8b80a0ab5ddc6830312e5e6a8801301fe6d2de4`。
- 两处实现变异均已先红后 cp+SHA-256 恢复：取消脚名匹配（28 failed）、让 NC 泄漏进 unstated
  （1 failed）。恢复后 core 全绿。
- 主代理独立复验：Rust core **56 passed**，fmt/clippy 通过；Python Q12+Q10+Q2+Q8+Q11+
  doc-claims **125 passed**；book validator exit 0（19 profiles）；既有 CircuitSpec loader 读回
  **7 parts / 11 nets / 1 NC / 6 ports / 37 member 项**。子代理更大邻域为 **189 passed**。
- 未跑全量，零真机、零部署、零 git 写；CH340 仍 candidate/notForDrawCompile/draft。
  PresentationSpec 与绘制验收另批，EP 厂家依据和原生 `block_symbol` 样件仍未关闭。

## 提交前挖洞修复（2026-11-12）

- 两条新负例先在旧实现得到 **56 passed / 2 failed**：`portPins` 的未知 key 会被后续错误
  掩盖，两个 pinGroups 在同网重复认领同一物理脚会被静默去重。补上端口 key 对账和跨组
  物理脚唯一性后，主代理复跑 Rust core **58 passed**，fmt/clippy 通过；有效输入生成物不变。
- book 的 LF 与 catalog symbolRef 两处挖洞修复见 `tasks/038q8_symbol_book.md` 末节。
  修复后主代理 Python Q8+Q10+Q2+Q12+doc-claims **123 passed**，book validator exit 0。
