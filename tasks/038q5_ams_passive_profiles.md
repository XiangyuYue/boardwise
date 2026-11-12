# 038Q5：AMS1117 三个电容的真实身份与 SymbolProfile

日期：2026-11-12。接续 038Q4，只完成 AMS1117 试点的三个电容；不扩展到 SY8089、CH340C，
不进入原生 `block_symbol` 的阶段 A，也不进入绘制编译。

## 范围与输入

| role | LCSC | 预期 MPN | 上游 device UUID | 预期封装 |
|---|---|---|---|---|
| C_BYP | C1525 | CL05B104KO5NNNC | `87bb635d0b2f489a9f60e7cd225beb3c` | C0402 |
| C_IN | C440198 | GRM21BR61H106KE43L | `6e5726223dd84f70bc3b626fc7d1f72c` | C0805 |
| C_OUT | C45783 | CL21A226MAQNNNE | `159c3da60be9490abf4e97599788a0d5` | C0805 |

系统库 UUID：`0819f05c4eef4c71ace90d822a990e87`。这些上游字段是待核声明，不是已核身份。

## 两个小批，部署授权不沿用

### Q5a：正式环境只读身份核对（当前可做）

- 在 `test V4` 的当前实例上调用既有只读 `lib.device.get`，逐颗核对 device UUID、LCSC、
  MPN、封装与 `association.symbol`；再读 `lib.symbol.get` 核对 symbol UUID、library 和标题。
- 只读，不重启 daemon、不热更 Connector、不写工程。找不到或字段矛盾就停止该颗，不以搜索
  结果替换请求身份，不按封装猜符号。
- 记录三个独立响应和一份脱机汇总到 `outputs/review/038q5/`。允许封装相同的两颗电容解析
  到不同符号；只有真实 symbol UUID 相同才允许共用后续文件/profile。

### Q5b：真实 elibz2 与 profile（另获部署批准后）

- 需要载入 038Q3 的 `lib.symbol_file.get`：另获岳明确批准后，才可重启 daemon 并仅热更
  `test V4`。038Q3 的批准不沿用；其他两个窗口不动，完成后恢复正式环境。
- 按 Q5a 的真实 symbol UUID/library 读取 `elibz2`，保存原文件、SHA-256 和身份响应到
  `outputs/review/038q5/`。每颗都用 `load_elibz2_symbol` 独立解析，输出候选 SymbolProfile。
- 若出现当前 reader 不支持的容器/body 形状，停止并另开 shared/parser 小批；不猜 ELLIPSE、
  ARC、PIN 方向或文本几何，不放宽容器校验。

## 对拍与 negative control

1. 请求 device UUID 与响应身份不一致、MPN/LCSC 不符、symbol association 缺失：不得生成 profile。
2. 两颗 0805 不得因封装相同而自动共用 profile；symbol UUID 相同才可共享同一文件读取结果。
3. C45783 的新 profile 与 `blocklib/specs/flyback_uc3845.library.json` 的既有 `C0805`
   实测引脚做只读对拍。差异必须保留并解释，不覆盖旧实测，不用“同族规则”抹平。
4. 每个新 profile 必须来自真实容器哈希，二次解析 JSON 与 geometry hash 一致；脚号、脚名、
   tip、body 必须来自文件，不能由 MPN/封装补猜。

## 明确不做

- 不改 `blocklib/modules/catalog.json`、CircuitSpec、PresentationSpec，不解除
  `candidate/unverified/notForDrawCompile`。
- 不展开 AMS1117 `U.VOUT*`，不断言第 4 脚焊盘存在；封装与焊盘核验另批。
- 不改规则、CLI、bridge/Connector/DSH/Rust/绘制算法；不碰真实工程，不执行 draw compile/apply。
- 不宣称原生 CBB、V3/elibz、多符号容器或硬件兼容完成。

## 验收与文件域

- 本任务书；`outputs/review/038q5/`（真实证据与候选 profile）；`.tmp_038q5/`（一次性探针）。
- Q5a 主代理核对三份原始身份响应；Q5b 主代理独立重算容器/profile 哈希并检查逐脚几何。
- 零生产代码变化时不跑全量 pytest；运行 Q4 reader/profile 邻域和实际采集脚本即为本批验证。
  若确需 parser 改动，另立 shared 任务书、补测试与两处变异，不能夹进本采集批。
- 任何 git 写、部署、daemon 重启、Connector 热更、发布仍逐次经岳明确批准。

## Q5a 验收（2026-11-12）

- 正式 daemon/Connector 未重启、未热更；仅在 `test V4` 当前实例完成六次只读调用。
  三颗 device UUID、MPN、LCSC、library 与 symbol association 全部命中，原始响应在
  `outputs/review/038q5/`。没有写工程，也没有使用搜索结果替换身份。
- 真实 symbol UUID：C1525=`5d54ad1e3ff64cdb9e7c9f449679d79f`；
  C440198=`2e54d9f6ef024fd6a073cb020500c9e8`；
  C45783=`a945ad0780e84529829fad9eef7941b6`。
- C440198/C45783 的 footprint UUID 同为 `ccb32feceadc4298b406326a506ce8e7`，但 symbol
  UUID 不同，证明“同封装共用 profile”不成立；三颗必须分别读取真实文件。
- 离线校验脚本 `.tmp_038q5/validate_identity.py` 由子代理实现，主代理独立复跑两次均为
  **59/59 checks passed**；summary SHA-256 两次均为
  `e628d83cf77dd0f3dcd43b580a4f806438a353c33f3105fa42df83156f5c1cfe`。
  汇总与验收：`outputs/review/038q5/identity-summary.json`、`Q5A-ACCEPTANCE.md`。
- Q5a 未采集 elibz2、未生成 profile、未改 catalog。Q5b 仍需岳明确批准本次 daemon 重启
  和仅 `test V4` 热更，批准后才可继续。

## Q5b 验收（2026-11-12，岳已批准本次部署）

- 候选 bundle SHA-256 `6a71c808061b5059adf03a5152adefb99c273ba29ed71aab3c9bf42d731cd199`。
  热更后另一旧窗口重连报 0.6.0，使命令报 mismatch；没有盲目重试。新候选实例经 `doc.list`
  逐字确认 `test V4` / P41 后，才进行三次只读文件调用。没有写原理图或 PCB。
- 三份真实 elibz2 均通过严格 base64/身份/容器校验，并由现有 `load_elibz2_symbol` 独立解析。
  归档 SHA-256：C1525=`396c40ceaa9fd16f84bb2324e0aea3aee0ce43c7794ee0a113188932f263efd2`；
  C440198=`83d18ee62326704840c0a7e2354948d662480727c59bd21039b523098673a4ec`；
  C45783=`4a371cc61d8da136294a3d7594e2266bb4e760dc644f59249456dad7ff857a43`。
- 三份候选 profile 均为 1=(-20,0,left)、2=(20,0,right)、body=(-10,-8,10,8)，但 symbol
  UUID、归档和 geometry hash 各自独立，没有按相同几何或封装合并来源。profile SHA-256 分别为
  `0a143a8843f2b0aa4b5021f75b627007952743e68e60c46a1183566f86f11496`、
  `99725839d4fb3472bcf41351f50555cfe3235458a76e7185ab801d6f36ca27e9`、
  `34d6f70d048409dcd654a61ae01430336b90e8dbd73610a45e764664c2756a0b`。
- C45783 与旧 C0805 实测的脚号、名称、tip、direction 一致；body 从旧“两脚内端”下界
  `[-10,0,10,0]` 到新文件 POLY `[-10,-8,10,8]`，pin length 仍因 reader 未暴露而为 null。
  差异原样记录，旧实测未改。见 `c0805-comparison.json`。
- 子代理实现一次性采集脚本；主代理连跑两次，stdout 与产物哈希逐字节一致。Q4 reader 邻域
  **37 passed**。零生产代码变化，未跑全量，未改 catalog，四模块继续 notForDrawCompile。
- 正式 Connector 0.6.0 回滚已 verified；正式 daemon exe 为
  `.tmp_038q1/rollback/v061/boardwise.exe`，三窗均 0.6.0、配对指纹 `8b82a227`、目标 P41 一致。
  当前目标实例 `inst-163945808-nioq97aq`，正式 daemon 后台任务 `bash-hja4xpl6` 保持运行。
- 完整证据与部署记录：`outputs/review/038q5/ACCEPTANCE.md`、`profile-summary.json`、
  `final-bridge-status.txt`、`final-listener-process.txt`。

## 下一小批建议

先裁 AMS1117 `U.VOUT*` 的展开及第 4 脚焊盘证据，并单独确定 profile 的受管落盘合同；
未完成前不晋升模块。SY8089、CH340C 不在本批自动接续，原生 CBB 样件也仍独立排期。
