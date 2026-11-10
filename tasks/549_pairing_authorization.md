# 任务书：549 首次配对显式授权（已随 0.6.1 正式版发布）

> 状态：**已随 0.6.1 正式版发布**（tag 与 Release `targetCommitish` 均为 `9ffeb3b`，`prerelease=false`、latest）；本地实现、离线验收及 4.1.93 真机/回滚验收完成；4.1.71 仍只有模拟证据。红队裁定变化、离线读数与真机验收见 §5、§7。

## 1. 问题与证据

0.6.1 的 pairing-write 只豁免 `https://client`。EDA 4.1.71 / Connector 0.6.2 上报 `https://pro.lceda.cn` 时，无配对记录会在写记录前得到 `UNAUTHENTICATED`，反复重连仍为零记录。`.tmp_workspace_cleanup/pairing-origin-simulation/simulation-report.json` 已用真实 daemon + loopback WebSocket 复现；有效旧 token 可在该 Origin 重连，无 Origin 且无活动窗口时旧记录会被静默替换。

本批不是给 `pro.lceda.cn` 加白名单，而是取消“Origin + TOFU 即可写配对”的授权模型。EDA 4.1.71 没有安装包，协议模拟可以覆盖 Origin，但不能宣称其 `eda.*` API 兼容已验。

## 2. 已裁定的流程

- Connector 用 Web Crypto CSPRNG 生成 8 字符公开配对编号（32 字符无歧义字母表，UI 可显示 `XXXX-XXXX`），hello 以可选 `pairCode` 上报。编号不是 token，可以在 Connector About/日志中显示；token 永不显示。Math.random/none 不得生成首次授权编号，省略字段并明确报错。
- 编号在 Connector 重连时保持稳定，存独立的 `pairCode` 配置键，不塞进 token 键。显式 re-pair 时换新编号。
- 新 CLI：`boardwise bridge pair <CODE>`。它使用既有 CLI token 调用 daemon-owned `pair.authorize`，不得增加无认证 HTTP 面或持久化授权文件。授权只存在 daemon 内存，daemon 重启即失效。
- daemon 规范化编号（大写、去连字符/空白）后保存一条 grant：编号、单调时钟 5 分钟到期、授权时的配对指纹、失败尝试数。后一次显式授权覆盖前一次并各自审计。
- 已配对且 token 相同：直接放行，不看 Origin/grant。
- 已配对且 token 不同且有活动窗口：拒绝，不顶掉活连接。
- 其余首次/重配：只有 grant 匹配、未过期、记录指纹未变才可写；错码、过期、已消费、指纹变化均拒绝。旧 Connector 无 `pairCode` 时不得静默 TOFU；消息要求升级。有效旧配对重连不受此限制。
- 错误尝试只进服务端审计，不销毁 grant（红队推翻了原“10 次作废”方案，避免未认证 socket 反复取消用户授权）。成功写记录后再消费 grant；写失败保留 grant 供 5 分钟内重试。`_authenticate_connector` 的同步检查+写入没有 await，同一事件循环内不交错；本批不引入跨进程锁。
- `pair.authorize` 只允许 ROLE_CLI。响应不返回 token 或完整配对编号。审计记录授权和配对结果，配对审计带 `authorizedBy`，不记录 token。
- 复用 `UNAUTHENTICATED`，detail/message 给出 `pairCodeRequired` 和原因；不新增协议大版本、不修改 MIN_CONNECTOR_VERSION。新 Connector 配旧 daemon 时不得声称首次授权已受支持。
- `bridge revoke` 仍删除记录；grant 的记录指纹变化会作废旧授权。re-pair 文案不再只建议 revoke，应指导用户使用新编号执行 `bridge pair`。

## 3. 分批文件域

1. daemon + protocol + Python 协议测试：`src/boardwise/bridge/daemon.py`、`protocol.py`、`tests/test_bridge.py`、新增聚焦测试；需要时 `tests/test_action_catalogue.py`。
2. CLI：`src/boardwise/cli.py`、`commands/shared.py`、`tests/test_bridge_cli.py` 及必要合同测试。保留这些文件中 546 的未提交改动。
3. Connector：`connector/src/{random,config,transport,index}.ts` 与 connector tests。不得改 daemon/CLI。
4. 审核与文档：聚焦攻击负例、CLI 合同生成器、`docs/bridge.md`、README/任务台账（仅在实现实际覆盖时更新）。版本号、发布件、Release、真机部署另行批准。

## 4. 必过负例与不变量

- `https://pro.lceda.cn` 未授权首配拒绝且零记录；授权后成功；错码、过期、重用、错误角色均失败。
- 两条不同编号只授权一条时，只有获授权 Connector 可写；重复授权只有最新编号有效。
- grant 后 revoke/记录变化使旧 grant 失效；daemon 重启后旧 grant 失效。
- 有效旧配对在两种 Origin 都可重连；无编号旧 Connector 不得再自动首配或静默换配。
- 编号可公开显示，token 不出现在 UI、审计或报告；CSPRNG 不可用失败关闭。
- 既有测试需要首配时必须通过测试自己的显式授权 helper，不得给生产代码加测试后门。
- 先跑聚焦测试，再跑 bridge/CLI/connector 邻域和合同检查。全量、Rust、真机验收在本批完成后单独安排，不伪称已完成。

## 5. 红队裁定变化与当前状态（2026-11-10，文档子代理交卷）

**裁定变化 1：错误尝试不再作废 grant。** 本任务书 §2 原写"最多 10 次错误尝试后作废 grant"，
红队已推翻：失败计数无法绑定到对端（端口是自由的，一个页面可以自己开一条），任何未认证的本地
socket 都能用 10 次错码取消用户自己的授权——把守卫变成攻击面。现行实现：错码只**拒绝本次握手**
并把次数记在 grant 上，只进服务端审计（`pairCodeFailures`）；不许销毁、削弱或消费授权。真正的
边界是 grant 自身的形状：8 符号 × 32 字母表、一个编号、5 分钟、一次配对。未认证 `detail` 只允许
`pairCodeRequired` + `reason`，指纹与次数一律不出线（`_close` 的 allowlist 兜底）。

**裁定变化 2：Origin 只诊断、不再授权。** 旧实现豁免 `https://client`，#57 的 Origin 闸因此拒绝了
上报 `https://pro.lceda.cn` 的真实 EDA 4.1.71。现实现里配对写只认 CLI 铸的 grant；Origin 仍记录在
`connect` 审计行、仍被 `doctor` 读，但不参与授权判断（`check_origin` 恒放行，仍属 004d）。

**实现要点（549，已随 0.6.1 正式版发布；定稿时为工作树）：** 覆盖 daemon/protocol/CLI/Connector 四块，
`pair.authorize` 为 daemon-owned、`risk=write`、`design_write=false`、仅 CLI role；Connector 侧
Web Crypto only（无 `Math.random`，零/恒定随机失败关闭），编号独立 `pairCode` 键，重连稳定、
re-pair 换新编号，`hello.data.pairCodeUsed === true` 才轮换。记录写盘改为同目录临时文件 +
`os.replace`，成功后才消费 grant。

**最终读数（2026-11-10 收尾）：** 主代理独立 Python 聚焦 **455 passed / 3 skipped**；Connector
**608 passed** + `npm run typecheck`；DSH **137 passed / 1 skipped** + typecheck/build；Rust
`fmt`/`clippy`/`test` **111 passed / 4 ignored**；`python -m tools.cli_contract` 一致。**全量 Python
一轮**：**10611 passed / 25 skipped / 1 xfailed / 23 failed / 5 errors**（27:15）——**不是全绿，
也不把这 23+5 全算作既有基线**：其中 `test_537a_daemon_write_policy` 两条是 549 新动作未登记
非 design-write 例外（`pair.authorize` 现为第四个 `design_write=False` 例外，`risk=write` 不变），
补登记后由 `tests/test_537a_daemon_write_policy.py + tests/test_549_pairing_authorization.py +
tests/test_bridge_cli.py` 聚焦 **126 passed** 关闭；另有 4 处 549 测试把审计写到仓库根，已改
`tmp_path`、残留走回收站；其余失败为既有货架数据、绘制线在途改动与已知 MSYS 环境错误。
**未跑第二轮全量。** 红队两轮：7 条已修，后续 3 条非阻断项亦已修，最终无已知阻断项。测试临时
目录清理 24 个进回收站，日志与证据保留。`docs/bridge.md` §4 的 `pair.authorize` 行与 hello 的
`pairCode` 参数（`contract-drift.test.mjs` 比对 `ACTIONS` ↔ 文档表）已补；两处过期 HELP 文案
（`protocol.py` summary、`shared.py` pair description）已改正并重生成 `contracts/cli/v1.json`。

**状态：已随 0.6.1 正式版发布**（tag 与 Release `targetCommitish` 均为 `9ffeb3b`，`prerelease=false`、latest）；本地实现、离线验收及 4.1.93 真机/回滚验收完成，4.1.71 仍只有模拟证据。（真机读数见 §7）

**未做/未验（发布后仍成立）：** 生产环境升级（真机验收后已回滚到原 0.6.0 Connector）、4.1.71 真机、
整板验收；4.1.71 只有模拟 Origin 证据（无安装包），朋友那台真实候选跑通不是本实现的验收；
新版 daemon 与 Connector 必须同步部署，不能用内嵌旧 Connector 的 `update-connector` 冒充安全包；
`connected` 不等于 `checkup` 通过（空模型仍 `incomplete`）。

## 6. 真机验收任务边界（2026-11-10，岳批准）

- 目标逐字为 **`test V4`**，projectUuid `1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`，EDA 4.1.93；验收前 `doc.list` 已核对项目与页面。另一窗口 `ROBOT ctrl FOC` 是禁地，不寻址、不更新、不写。
- 允许：构建并记录 bundle/eext 哈希；对目标实例 `update-connector --no-reload`；由用户通过宿主菜单重新求值扩展；停止旧 daemon 后用独立 `BOARDWISE_HOME` 启动新 daemon；在独立目录执行首次授权、重连、只读 `sys.probe` / `doc.list` / `sch.netlist` / `checkup`；最后回滚 Connector 和 daemon。
- 禁止：任何工程内容、属性、页面或 PCB 写入；读取/复制生产 token；用生产 `BOARDWISE_HOME` 做首次授权；把 connected 写成 checkup 通过；把 4.1.93 的结果外推成 4.1.71 已验。
- 回滚材料：v0.6.0 官方 eext 与其 `dist/index.js`，v0.6.1 原 daemon EXE。生产配对目录保持原位，只做运行进程切换。验收产物放 `outputs/review/549_real/`，部署日志放 `.tmp_workspace_cleanup/549-real/`。

## 7. 真机验收结果（2026-11-10，EDA 4.1.93 `test V4`）

以 `outputs/review/549_real/ACCEPTANCE.md` 为准，摘要：

- **首次授权成立**：新 Connector 以 `update-connector --no-reload` 写入、用户经宿主菜单激活（不刷新页面）；
  独立 `BOARDWISE_HOME` 下 `bridge pair EQE5-W2YC` 成功，审计 `authorizedBy=pair.authorize`，编号只留掩码 `EQ****YC`。
- **读取成立**：`sys.probe` 报 4.1.93、检查的 API 均存在；`doc.list` 返回 9 文档 / 5 原理图页 / 2 PCB；
  `checkup --project "test V4"` 取到真实模型 **77 components / 225 nets**（Board1 66/205、Board2 11/20）。
- **exit 1 不是连接失败**：是目标工程自身 **85 项 ERROR**（77 条 `pcb-footprint-consistency`、7 条位号重复、
  1 条宿主 Import Changes），`completion=incomplete`——不得据此称板子干净或可投板。
- **重启后旧配对自愈**：隔离 daemon 重启后未再 `bridge pair`，旧 token 于 19:41:02 自动重连、`doc.list` 完整；
  审计 `pair-authorize=1 / pairing=1 / re-pairing=0`。
- **回滚成立**：原 0.6.0 bundle 以 `--no-reload` 写回，最终 Connector **0.6.0** / daemon **0.6.1**、两窗口
  connected、paired fingerprint `8b82a227` 不变；临时对齐的 package/extension 元数据逐字节恢复。
  原 daemon EXE 首次启动报 `Could not create temporary directory` 是临时目录不可写，改用既有可写目录后恢复，
  与配对无关。
- **仍未覆盖**：4.1.71 只有模拟 Origin 证据，4.1.93 的结果不得外推为 4.1.71 全功能兼容；发布时生产环境
  仍是原 0.6.0 Connector（真机验收后已回滚），本次不处理工程 findings、未做整板验收。
- **发布（2026-11-10）**：已随 0.6.1 正式版发布——main `47713c2`/`8ad625e`/`9ffeb3b`，tag 与 Release
  `targetCommitish` 均为 `9ffeb3b`，`prerelease=false` 且 latest；内嵌 Connector bundle
  `418c7a023b44d5d5cbc659c8d0e3e26fe8eaca17b2a3b4df4acd4cfac89e05dc`。
