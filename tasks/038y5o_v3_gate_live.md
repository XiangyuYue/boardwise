# 038Y5O：V3 `test` 的 `pcb gate` 在线只读验收

日期：2026-11-16。前置：038Y5L/M/N 只覆盖 test V4。岳已打开 V3 `test`，本批验证 V3 宿主路径与天然 GREEN，不修改设计。

## 身份与边界

- friendlyName：`test`
- projectUuid：`ea80fff642fa86cdc95882ab0201b0bb7ee6d966412a8958fec3ff95fa13f489`
- 开始为 Start Page（active=null），完成后用 `doc.focus {tabId:"tab_page1"}` 恢复。
- 现有 PCB1=`5dc38976c1fa45ce`、PCB2=`443698e98668b58b`。

只允许 bridge status、指定工程的 doc.list/document.current、在上述两块 PCB 与 Start Page 间 doc.open/doc.focus、`boardwise pcb gate --project "test" --out <全新目录>`，以及必要的 sys.probe 只读版本检查。禁止设计写入、保存、autofix、创建/删除页板、复用输出目录、热更或路由其它工程。

先跑 PCB1；若宿主 DRC 非清洁，保留 RED 后可按同一授权检查 PCB2。DRC 清洁后必须证明新鲜 checkup 真跑；只有 checkup 结论允许时才记 GREEN，INCOMPLETE/RED 不冒充通过。证据 `outputs/review/038y5o/`，零 git 写、零删除、零全量。

## 实际结果（2026-11-16）

- `sys.probe`：宿主 **4.1.100**、connector 0.6.1。本次是 V3 `.eprj2` 工程路径验证，**不是 3.2.x 宿主验收**。
- PCB1=`5dc38976c1fa45ce`：严格 DRC `checked=true / errors=1 / items=1 / truncated=false`，gate RED / exit 2，checkup 未运行。
- PCB2=`443698e98668b58b`：同样 errors=1 / items=1 / truncated=false，gate RED / exit 2，checkup 未运行。
- 两块现有板均非天然 DRC 清洁，因此没有 GREEN，也未补出 V3 的 checkup 路径。未修改设计或隐瞒 DRC。
- 已用 `doc.focus(tab_page1)` 恢复 Start Page，doc.list 确认 active=null。证据 `outputs/review/038y5o/`。
- 后续需要一块天然 DRC 清洁的授权测试板；若要求 V3 宿主兼容，还需 3.2.x 环境，不能以 4.1.100 替代。

## 环境裁定（岳，2026-11-16）

岳确认身边设备均已升级到 V4，不再有 3.2.x 环境。V3 宿主验收转为等待其他用户反馈，不再列为本机必做项；本机已有 `.eprj2` 读数保留，但不得写成 V3 宿主已验证。
