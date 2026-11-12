# 038Q9：剩余 13 个器件身份的集中采集

日期：2026-11-12。调整此前逐模块、逐窗口的拆分方式：按**采集窗口与交付层**分批，
不再为每颗器件重复部署。覆盖当前 catalog 与 `blocklib/symbols/index.json` 差集的全部 13 个身份。

## 批次原则

1. **Q9a 一次正式环境只读会话**：用同一脚本、同一目标实例，串行读完剩余身份的
   device/symbol/footprint 元数据，输出逐颗原始响应和总表。不得逐颗手工复制命令。
2. **Q9b 一次候选部署**：另获岳明确批准后，只重启/热更一次，在同一候选会话读取全部真实
   symbol 文件，随后一次回滚。不得恢复一次后再为下一颗重新部署。
3. **离线并行收口**：最多两个互不重叠文件域的子代理解析/校验；主代理负责身份裁定、
   关键 diff 和独立复验。真实 profile 统一经 `tools/check_symbol_book.py` 准入，不逐颗改 catalog。
4. 身份层完成后，模块生成合同、通配脚、PresentationSpec 与编译另按交付层推进，不再按器件排队。

## 当前差集（由脚本实算，不手维护）

- SY8089 block 3 个：C250183、C25744、C26980。
- SY8089 live 6 个：C167206、C14663、C1653、C25803、C2960862、C25804。
- CH340C 4 个：C84681、C2687116、C9900012665、C25905。

catalog 共 19 个唯一 device UUID，book 已覆盖 6 个，差集必须为 13；多一颗少一颗都停止。
相同 deviceUuid 的多个 role 只采集一次，但保留全部 role 映射。

## 身份与文件合同

- Q9a 逐颗核对 found/deviceUuid/libraryUuid/lcsc/mpn/association；独立 symbol/footprint
  响应与 association 对齐。失败按颗记录，不用搜索替换，不因缺失继续伪造 profile。
- Q9b 仅当 symbol UUID/library 明确后读取 elibz2；同 UUID 只读一次，不同 UUID 即使同名、
  同封装或同 MPN 家族也分别处理。严格 base64、容器身份、reader、profile hash 与确定性复跑。
- CH340C 的复杂符号、通配脚、未声明引脚只采集事实，不在本批展开或推断电气连接。
- 原始证据在 `outputs/review/038q9/`，一次性脚本在 `.tmp_038q9/`；原始容器不入库。

## 验收与边界

- Q9a 总表必须列出 13/13 成功或明确失败项、每个 symbol/footprint UUID 和差异；主代理复核汇总。
- Q9b 全部成功后才统一更新 book；部分成功只保留证据，不把未读件写成完成。
- 两次解析产物逐字节一致，`tools/check_symbol_book.py` 与 Q8/Q2/文档邻域通过。
- 不改 CircuitSpec、模块 catalog/notForDrawCompile，不做通配脚展开、draw compile/apply、
  原生 block_symbol、V3/elibz 或硬件兼容声明。
- 真机只读，除获批的热更/回滚外不写工程；任何 git 写、发布、部署仍逐次经岳批准。

## Q9a 与采集准备验收（2026-11-12）

- 同一实例、同一脚本串行完成 39 次只读调用，用时约 56 秒；原始 39 份响应齐全。
  首轮汇总 6/13 是采集器把“省略 library 时顶层 null”误判为失败；修正后要求 item.libraryUuid
  非空、顶层若存在须与 item 一致、association 同库，**没有放宽身份校验，也没有重新采集**。
- 修正后 13/13、overallPassed=true；主代理两次 `--check-only` 均一致，采集器测试 **31 passed**。
  总表 `outputs/review/038q9/identity-summary.json`，SHA-256
  `001498763d93cb40fb6532fd71fa1789680edcb9ef77e51bc7c0e140ca72ee1d`。
- Q9b 文件/profile 集中采集器已备好，覆盖 13 个独立 symbol UUID，一次候选会话全部读取；
  fake/合成测试 **21 passed**，parse-only 不发起子进程，任何失败都不会写成整体通过。
- 下一步仅需**一次** daemon 重启与仅 `test V4` 热更，不是 13 次部署。获批后采集、统一解析、
  一次回滚，再进入 book 统一准入；不逐颗修改 catalog 或解除 notForDrawCompile。

## Q9b 与 book 准入验收（2026-11-12，岳已批准本次集中部署）

- 第一次热更在目标窗重连前返回 INSTANCE_STALE，未发生写入；等待目标上线并重取状态后，
  第二次 verified。候选实例 `inst-025920320-567n6hxc` 经 `doc.list` 确认 `test V4` / P41，
  同一候选会话读取 13 份公开符号并生成 profile，约 9.4 秒完成；13/13、overallPassed=true。
- 正式 Connector 0.6.0 一次回滚 verified；当前目标实例 `inst-030035529-hq99k1gc`，三窗均
  0.6.0、当前页 P41、配对指纹 `8b82a227`，listener 为正式 exe，daemon 任务
  `bash-3k72sbqi` 保持运行。没有写原理图或 PCB。
- book 已从 6 份统一准入到 **19/19 个唯一 device 身份**。`profiles.json` SHA-256
  `b6d5e9f1376255291228f15eb6ac265715c7ab88a113d6138afdb69c49c23241`；`index.json`
  SHA-256 `cc86aa226de58f5404339d1b8b3a890e99e4ea981e29c0afaee7627228d76873`。
  `tools/check_symbol_book.py` exit 0，主代理组合 **97 passed**，Q8 自身 **39 passed**。
  新增13份无重复脚号、无 shared tip；生成器两次运行逐字节一致。
- CH340C 的真实脚名是 DTR#/RTS#；Type-C 有 EP 脚8–11及 A1B12/B4A9 等复合编号。
  这些只作为采集事实保留，通配脚/未声明脚不自动展开，AMS 的 VOUT 未决项不变。
- 未改 catalog/CircuitSpec/notForDrawCompile，未跑全量、未提交。完整证据：
  `outputs/review/038q9/ACCEPTANCE.md`、`file-profile-summary.json`、`book-admission.json`。
- 下一交付层是模块生成合同与首个无通配脚试点，不再按器件拆分；CH340/AMS 的电气未决项
  不得借“19个身份已齐”跳过。
