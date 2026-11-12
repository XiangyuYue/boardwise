# 038Q7：SY8089 双身份核对与 SymbolProfile

日期：2026-11-12。接续 038Q6，只处理 SY8089 两种上游身份；不扩到 CH340C，
不改模块生成物、不进入绘制。分两小批：Q7a 正式环境只读身份/变体核对，Q7b 真实符号文件。

## 两个待核身份

| 来源 | LCSC | 上游 MPN | device UUID | 上游封装 |
|---|---|---|---|---|
| block | C479074 | SY8089A1AAC | `00111ae499794742b81a699a4ff88fc8` | TSOT-23-5 |
| live topology | C78988 | SY8089AAAC | `8cfd65b3cdf844cdadfefd57318dcba1` | SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR |

系统库 UUID：`0819f05c4eef4c71ace90d822a990e87`。上游 pin map 仅供对拍：
1=EN、2=GND、3=LX、4=IN、5=FB；不能在真实 profile 之前当作本仓已核事实。

## Q7a：正式环境只读核对

- 只在 `test V4` 当前实例使用既有 `lib.device.get` / `lib.symbol.get` / `lib.footprint.get`。
- 逐字段核对 device UUID、LCSC、MPN、manufacturer、datasheet、symbol/footprint association、
  封装名称和符号标题；找不到或矛盾即停止该身份，不用搜索结果替代。
- 重点回答：两种身份是否共用 symbol/footprint UUID、封装是否只是标题差异、资料是否指向同一
  datasheet。**相似 MPN 不证明可互换，相同封装标题不证明相同符号，两个 C 号不证明不同 die。**
- 原始响应和比较写 `outputs/review/038q7/`，不得修改 catalog/CircuitSpec/notForDrawCompile。

## Q7b：真实 elibz2 与 profile（另获部署批准后）

- 仅当 Q7a 身份明确后，另获岳明确批准本次 daemon 重启和仅 `test V4` 热更，使用已有
  `lib.symbol_file.get` 读取真实符号文件；完成后恢复正式环境。038Q6 的批准不沿用。
- 若两种身份共用同一 symbol UUID，只读取一份并明确共享依据；不同则分别读取，禁止按
  SOT-23-5/TSOT-23-5 封装名或相似 MPN 合并 profile。
- 复用 `load_elibz2_symbol`，核对 5 脚号码/名称/tip/body/source/hash；与上游 pin map 对拍，
  差异原样保留。遇到新容器/body 形状另开 shared/parser 小批，不猜几何。
- datasheet 只用于对应真实 MPN/封装的引脚与变体证据；不把别家 SY8089 或同名经验代入。

## 验收与边界

- Q7a 的原始响应必须可重放校验；Q7b 两次解析产物逐字节一致，主代理独立复跑。
- 负控：两个身份不得因标题合并；datasheet 变体差异不得被“都是 SY8089”吞掉；
  任一 pin map 不一致不得晋升模块。
- 零生产代码预期；若确需实现/解析变更，另立任务书。未获部署批准前不读取新文件。
- 本批完成不等于 SY8089 模块齐备：电感、电阻、电容身份与电气事实仍需另批；
  不解除 candidate/unverified/notForDrawCompile，不做 draw compile/apply。

## Q7a 验收（2026-11-12）

- 正式环境只读六次调用完成，两个 device UUID、MPN、LCSC、manufacturer、symbol/footprint
  association 与独立响应三向一致。校验 **204/204**，主代理复跑两次产物哈希稳定。
- C479074：symbol=`f88e34d680e646e38a7b77e29201ff30`，
  footprint=`50772b8efd884647ad64a05add7fa273`；C78988：symbol=
  `ef98186cdedd4b58bd8e66a11ff8b5be`，footprint=`124f07aad233471aaaadd3ad027839dc`。
  两组身份不得合并，可互换性未证实（不是证伪）。
- 电气目录差异：输入范围 2.5–5.5V vs 2.7–5.5V、开关频率 1.5MHz vs 1MHz、
  温度范围 −40…125℃ vs −40…85℃、静态电流 50µA vs 55µA、Features 不同；
  datasheet 文档 URL 也不同。不能因“都是 SY8089”吞掉变体差异。
- 原始证据与汇总：`outputs/review/038q7/`、`identity-summary.json`、`Q7A-ACCEPTANCE.md`。
  上游 pin map 仍未核；Q7b 必须另获本次 daemon 重启和仅 `test V4` 热更批准。

## Q7b 验收（2026-11-12，岳已批准本次部署）

- 候选 bundle SHA-256 `ba78d505cb1a38c049204699e101a21a1f4fd71de94699eda4576876a6491b34`，
  仅 `test V4` 热更并 verified；新实例经 `doc.list` 确认 P41 后完成两次只读符号文件调用。
- C479074 archive SHA-256 `36f627dfa671d0e2adc512c8576afda78b864eee24477a1d109ca92efdadab1a`，
  profile SHA-256 `2e7a80352261817a05ffa10fa501df4be00e323245c4f6030a6f70bfc01e4cc1`；
  C78988 archive `8b4b61760502ae4284303401fc9b0402c9c55971266a0e8f4af5be30f1e5925e`，
  profile `e7909022a37f978f5678388cf3b61167df783c356101035d1d99ca737e58be26`。
- 两份均为 1=EN、2=GND、3=LX、4=IN、5=FB，脚号集合和脚名与上游完全一致；没有为求匹配改数据。
  body 分别为 (-25,-20,25,20) 与 (-30,-22,30,22)，tip x 与 geometry hash 不同，来源独立。
  身份/几何不合并，可互换性仍未证实。
- 主代理两次运行采集脚本，stdout 与产物哈希逐字节一致；Q4 reader **37 passed**。
  原始证据：`outputs/review/038q7/profile-summary.json`、`ACCEPTANCE.md`。
- 正式 Connector 0.6.0 回滚 verified；目标实例 `inst-010531564-evtedrb1`，三窗均 0.6.0、
  当前页 P41、配对指纹 `8b82a227`，listener 为正式 exe，daemon 任务 `bash-t8o3s62h` 保持运行。
- 零生产代码变化、未改 catalog/notForDrawCompile、未写工程、未跑全量、未提交。
  下一步先建立受管 profile 落盘合同，再采集 SY8089 外围，避免证据只散落在 outputs。
