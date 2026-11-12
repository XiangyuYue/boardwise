# 038Q13：CH340C block 的离线编译与视觉试点

日期：2026-11-12。依赖 038Q12 的真实身份与显式脚位。只做 PresentationSpec、离线编译、
逐脚回验、负例和视觉自审；不改绘制语法，不申请落图，不解除 notForDrawCompile。

## 呈现结构

新增 `blocklib/specs/ch340c_usb_serial.presentation.json`，复用 `ic-periphery` 与
`blocklib/specs/ch340_uart_543g.presentation.json` 已验收的**通用结构**，不复制其器件身份：

- `usb` 岛：J_USB（core）、R_CC1、R_CC2、D_ESD。USB-C 可逆 D±、CC 下拉和 ESD 靠近接口。
- `serial` 岛：U（core）、C_VCC、C_V3。两颗 100nF 分别服务 VCC 与 V3；CH340C 不需要
  CH340G 的晶振岛，不得虚构晶振。
- `flow: usb → serial`，两个模块；`portRoles` 只用真实 net id：TXD=output、RXD=input、
  DTR/RTS=output、VBUS_5V=load。GND 由 net class/gnd side 表达，不伪造 portRoles.gnd。
- D± 两条真实 auto net 可声明 localLabelObligations：可逆连接器脚和 ESD 脚各自用短直
  载体，禁 U 形回环线、禁为了紧凑把不同网拉成母线；其他局部网不逐脚打标签。
- 只用通用 PresentationSpec 字段。禁止 userLocks/像素坐标/partTexts 位号特判，禁止改
  `engines/grammar/**` 或为了出图放宽 gate。若现有文法不能绑定多脚 ESD/接口，如实记缺口。

## 三关与负例

1. 真实 `draw compile` 使用 Q12 CircuitSpec、上述 PresentationSpec 和受管 profiles；页级编译
   给 `--page-box 0,0,1170,825`，产物写 `outputs/review/038q13/`。记录 ok/candidates/failures/
   rejected/hard violations，不把 ok 当视觉通过。
2. 用现有 readability/derive_netlist 与 number-first canonical pin 对全部 **11 网**逐成员对账，
   另核 U.7 保持 NC；记录 missing/extra/shorts/unplaceable/NC 错误。七个 part 必须真实放置，
   未绑定货架件必须点名。
3. 渲染首候选，主代理亲看：USB-C/CC/ESD、D± 可逆对、VBUS 与 V3 去耦、UART/DTR/RTS 边界、
   GND/电源旗是否清楚；看不懂、关键件乱摆、文本互压或标签/导线互压即拒，不端给用户。

负例至少在内存副本覆盖：D+ 与 D- 对调、U.V3 错并 VBUS、删 R_CC1、把 U.7 接到 GND。
真实输入不动；每个负例必须被机器闸、源网对账或 NC 对账明确抓住，不能靠人工一句“错了”。

## 文件域与纪律

- PresentationSpec、新增 `tests/test_038q13_ch340c_offline_pilot.py`；
- `outputs/review/038q13/`、`.tmp_038q13/`、本任务书及必要 SCHEDULE/TASKMAP/handoff 收尾。
- 不改 module-import/curation/book/catalog/Rust/grammar/其他绘制文件；不改 Q12 已验收生成物。
- 零真机、零部署、零 git 写、零 plan/apply；测试用 `--basetemp=.tmp_pt_038q13`，暂不跑全量。
- 子代理最多40步/30分钟，先交机器与逐脚证据；视觉裁定必须由主代理看图后另写，子代理不得
  自称视觉通过。机器不过也要交回最小证据和具体缺口，不扩成绘制算法研发。

## 实施与主代理视觉裁定（2026-11-12）

- PresentationSpec 落地为 usb（J_USB/R_CC1/R_CC2/D_ESD）→ serial（U/C_VCC/C_V3）两岛，
  无晶振、无锁、无坐标、无 partTexts。两列最小宽度1930.75超出页框，故 moduleColumns=1；
  gndClustering 会把 serial 地网拆成两个节点，未声明。真实 CLI 得 **4 candidates / 0 failures /
  0 rejected**，四候选 hard=0。
- 四候选均 **11/11** 网逐成员与网名一致，七 part 全部放置，U.7 无导线、无标签、独占节点；
  D_ESD 是 ic-periphery 未绑定件。D±对调由名字对账抓住，V3并VBUS由源网对账抓住，删R_CC1
  由 facts-missing 抓住，U.7接GND由 CircuitSpec/NC对账抓住。证据在
  `outputs/review/038q13/{compile,verification,negatives}.json`。
- 主代理独立复跑 Q13+Q12 **24 passed**，并通过本地只读 HTTP 亲看 `cand1.svg`：**视觉拒收**。
  D± 长自动 net id 每网重复五次且互相压字（min_text_gap=0.0）；VBUS/GND 无旗标，GND 退化
  为标签；D_ESD 自由摆放，另有一条四弯导线。不能拿 hard=0 或11/11代替视觉验收。
- 不 plan/apply、不端给用户、不晋升，预览服务与浏览器 tab 已关闭。后续按
  `tasks/038q13a_ch340_presentation_gaps.md`：先由 CBB 给内部网语义命名，再由绘制线解决多脚
  ESD/短载体与旗标平台缺口；本批未改 grammar，未跑全量，零真机、零部署、零 git 写。
