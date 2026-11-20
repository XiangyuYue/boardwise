# 087F：#87② PCB `export.render` 宿主能力与实现验收

> 状态：**已落 `3d4a0d5`（origin/main）**；test V4 在线验收完成（2026-11-16），未发布。
> 提交状态由 557 于 2026-11-19 校正；V3 / 生产非空板未覆盖与 #87 Issue 待提出人复验的边界不变，不因已落而关单。

日期：2026-11-16。前置：HEAD `504e766` 的 `exportRender` 固定调用 `sch_ManufactureData.getExportDocumentFile`；官方类型包没有 PCB 文档出图成员，`engines/liveevidence.py` 已记录 V4 PCB 60 s 超时后停用。不能用 geometry 或已知缓存帧冒充 render。本任务先做只读能力探针，再决定实现，不预设视口通道可接受。

## 1. 探针身份与动作

唯一工程：`test V4`，projectUuid `1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`。开始活动页 P43=`797f20b8a217b331`；现有 PCB1=`847fb91471c76cab`、PCB2=`523016c3df10ea8d`。另一窗口和一切真实工程禁碰。

只允许 `bridge status`、指定工程的 `doc.list`/`document.current`、在上述三个文档间 `doc.open`、现有 `export.screenshot {fit:true}`。不得重试已知会冻结的 PCB `export.render`，不创建/保存/修改设计，不热更，不调用其它工程。结束必须恢复 P43 并复核。

## 2. 能力判据

1. 分别取得 PCB1/PCB2 PNG，记录字节数、SHA-256 和 PNG 签名；空数据、非 PNG、异常都保留原文。
2. 两板内容不同而图像哈希相同，或任一为缓存/空白/错误页，即判定 `export.screenshot` 不能作为本批 PCB 视觉证据；停止该通道，不靠延时重试洗白。
3. 只有哈希不同且主代理逐张目检确认图像确实对应当前 PCB，才可把 `getCurrentRenderedAreaImage` 设计为 **viewport 级**候选；它仍不是 document render，不得直接改 SOP 的“document render 优先”结论。
4. 本探针不关闭 #87②。后续实现须另写公开合同：PCB+PNG 不再调用 sch 文档导出，channel/evidenceGrade 明示，svg/pdf 与 selection/project 具名拒绝，sch 旧路径逐字不变，伪 PNG/空图/超时 negative controls 齐全。

## 3. 证据与纪律

原始 JSON 放 `.tmp_087f/`，解码 PNG 与结论放 `outputs/review/087f/`。不修改生产代码、fixtures、绘制线或真实工程；零 git 写、零 push、零删除。若探针不成立，交付可复现失败边界与最小后续动作，不宣称 #87② 已修。

## 4. 只读能力探针结果（2026-11-16）

- PCB1 PNG：196673 B，SHA-256 `e6ffb7dd3b12d169d6d3409fd901b5a421217d2fa4975ba8919aee7f3dea4cda`；PCB2 PNG：93840 B，SHA-256 `80f97c9805523661d2e3580e101b4194d9ec7b7d9a83a4bb8dd7dec7eb27a742`。两者 PNG 签名均正确，哈希不同。
- 主代理已逐张目检 `outputs/review/087f/pcb1.png`、`pcb2.png`：PCB1 显示其实际板框，PCB2 为只有坐标网格的空板，分别对应当前两块骨架板，不是同帧缓存或错误页。
- 本结果只证明 EDA 4.1.93 + 当前 Connector 上 `export.screenshot`/`getCurrentRenderedAreaImage` 可提供 **viewport 级** PCB 位图候选；不等于 document render，不外推 V3、非空生产板、selection/project 或 SVG/PDF。
- 已恢复 P43=`797f20b8a217b331` 并由指定工程 `doc.list` 复核。没有设计写、保存、热更或真实工程调用。下一步可按 §2④ 实现离线 PCB 分支；真机候选验收仍需另批热更授权。
