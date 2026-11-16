# 541R5：DSH 桌面部署验收与供应链阻断记录

日期：2026-11-16。前置：541R3/I/R4 已在隔离 DSH 0.2.2-rc.3 真实 Session 验收，但桌面 profile 未部署。岳允许在本机完成全量回归与真实桌面验收。

## 本次操作与结果

- `npm pack` 生成当前 boardwise-dsh 0.6.1，随后先执行 `tools/dsh_plugin_install.mjs --dry-run`，再尝试安装到 `D:/dsh-home/profiles/desktop`。
- 安装脚本自动备份到 `D:/dsh-home/profiles/_backup_boardwise-dsh_20261116-224916`。
- `pnpm install` 被上游供应链策略拒绝：`ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION`，既有 `@eddyskywalker/dsh-chatgpt-subscription@0.75.2` 的发布时间晚于当前 minimumReleaseAge cutoff。未放宽策略、未清理锁文件、未改其它依赖版本。
- 已从备份恢复 `package.json` 与 `pnpm-lock.yaml`，恢复前后 SHA-256 完全一致：manifest `196d65e19a154be25fb2603f9ce4a59ab7b6b48e662b15888f384316c4c35cf3`，lock `6d4a037c3858a13cfc1d6f8bcbb698ac1b04890fa6b8c9fa35e6105575deb847`。
- 已安装 `boardwise-dsh` 仍没有 `lib/review-stage-gate.js`，即旧版未变；桌面新闸未加载，不能记为通过。

## 后续允许路径

1. 等既有依赖进入上游允许发布时间窗口后，重新 dry-run 并安装；或上游提供与该供应链策略兼容的正式安装路径。
2. 安装后必须由实际桌面进程重启加载，再验工具与两个 listener、显式 out、initial/partial、跨目录欠账、预算与 tool-gap。
3. 不得通过替换 `node_modules`、关闭/放宽供应链检查或修改无关依赖来绕过阻断。

本任务只记录部署事实，不修改生产代码、不提交、不推送。隔离实载证据仍有效，但桌面验收保持未完成。
