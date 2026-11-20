# 087F3：#87②⑤ 文档、热更与真实在线验收

> 状态：**已落 `3d4a0d5`（origin/main）**；test V4 在线验收完成（2026-11-16），未发布。
> 提交状态由 557 于 2026-11-19 校正；V3 / 生产非空板未覆盖与 #87 Issue 待提出人复验的边界不变，不因已落而关单。

日期：2026-11-16。前置：087E、087F1、087F2 的离线实现与主代理复核完成。当前旧 connector 的 P43 readback 无 value/mpn，`capabilities` 缺键；PCB viewport 探针已证两块板图像真实不同。此任务分“候选在线验收”和“证据成立后文档”两段，热更必须另获岳当次批准，不自动执行。

## 1. 在线身份与边界

唯一工程 `test V4`，projectUuid `1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`。开始/恢复页 P43=`797f20b8a217b331`。允许只读导航：P44=`6fb7a1f1f245008e`、P45=`22d51b7d8e39974b`、P46=`7ed7ae8281e5a6a8`、P47=`678f22680140b828`、Board2 P1=`30560d9c0a52a6d2`、第三页 P1=`fac384d9f1c7c56b`；PCB1=`847fb91471c76cab`、PCB2=`523016c3df10ea8d`、第三板=`9c1812e046fdb36f`。不得路由另一窗口或任何真实工程。

热更仅限该 test V4 窗口，先备份当前可回滚包，不 bump/release。只读动作包括 doc.list/current/open、sys.connector_status、sch.readback、sys.get_document_source、export.render、review-evidence/checkup。不得修改设计、保存、删除、创建页/板、autofix。结束恢复 P43 并复核。

## 2. #87⑤ 在线判据

- P43 `sch.readback` 的 C24/R15/U9 必须与公开 source 事前基线一致：C24 `100nF/CC0603KRX7R9BB104`、R15 `10k/0603WAF1002T5E`、U9 `STM32G431/STM32G431RBT6`；valueSource=OtherProperty，mpn 与来源如实记录。
- 电源/netflag 的 value/mpn 应为 null；旧字段/fields.OtherProperty 折叠形状不变。`sys.get_document_source` 再次只读对照，不以归档替代在线 readback。

## 3. #87② 在线判据

- `sys.connector_status.capabilities.pcbRenderViewport=true`；旧基线缺键已留。
- PCB1/PCB2 `export.render png/page` 均返回 channel=evidenceGrade=viewport、真实 PNG、activated uuid 正确；SVG 具名拒绝且不再走 schematic export。主代理逐张目检，确认图像与板一致。
- 全新目录跑在线 checkup（默认上述全部页/板），记录 `live-evidence.json` 与 report 的 pcbImage status/steps/artifacts/errors。全部页/板才允许讨论全覆盖 ok；若只选子集，coverage 必须 missing。checkup/completion 不是板级通过，骨架板缺资料/空模型如实保留。
- 无 PCB 文档、旧 connector 缺 flag、错误 grade 的 fake negative controls 不得被真机结果覆盖掉。

## 4. 证据成立后的文档

更新 `docs/review-sop.md` 的 #87② 段、`docs/pits.md` 坑23、必要的两份 SKILL 与 `tests/test_doc_claims.py`：保留 schematic-only API 60.01 s 历史边界，同时写明新 connector 的 viewport 分支、能力旗帜、旧 connector 零 render 调用、PNG≠视觉通过、V3/生产板未覆盖。不得再把“当前没有 PCB 图像通道”写成绝对事实，也不得把 viewport 改称 document render。

`tests/test_doc_claims.py` 同时含绘制线 hunk，只许编辑 #87② 必要段。测试须钉住新旧两态和 viewport/geometry 区别，而不是只跟着新文案改字符串。跑 doc-claims、537C 与 action 聚焦，不跑全量。

证据放 `outputs/review/087f3/`，临时 `.tmp_087f3/`。零 git 写、零 push/comment/close、零删除；热更和后续发布各自另行批准。

## 5. 候选与回滚准备（未热更）

- 候选 `connector/boardwise-connector-0.6.1.eext` 已由 `npm run package` 构建，SHA-256=`2ac0bb05eaccf66391abe49980e27145db75d910e0f719d0732b9d0caee26d0e`；connector 全量 **809 passed** + typecheck。
- 当前 test V4 运行 connector 0.6.0；已从 GitHub v0.6.0 下载回滚包到 `.tmp_087f3/rollback/boardwise-connector-0.6.0.eext`，SHA-256=`2c662f2c1efdc9c8c4dc3edae59fb52380761b2b46de9301d6dce7c2cde19cbc`。
- 已向岳说明建议仅对 test V4 使用 `--no-reload`，待当次明确批准后才写入；尚未执行热更、未刷新页面、未改另一窗口。离线证据不得被这段准备写成在线已验。

## 6. 文档阶段结果（热更前）

- 文档子代理已更新 `docs/review-sop.md` 的 PCB 目视段、`docs/pits.md` 坑23、两份 SKILL 与 `tests/test_doc_claims.py`：保留 60.01 s schematic-only 历史边界，新增工作树候选、能力旗标、旧 connector 零 render、viewport≠document render、PNG≠视觉通过与未覆盖项。
- 主代理修正“探针图未核”为实际目检结论：PCB1 图对应板框、PCB2 图对应空板；仍不把这写成新分支热更后已验。两副本 `cmp` 一致。
- 主代理联合复验：doc-claims + live_capture + review_evidence_cli + evidence_coverage **186 passed**，basetemp `.tmp_pt_087f3_main`。
- 截止本段，岳尚未明确批准热更；`update-connector` 未执行，#87②⑤ 在线验收与 Issue 核销仍未完成。

## 7. 岳批准后的不刷新写入（2026-11-16）

- 岳明确回复“批准”后，先以 `bridge status` 复核 `inst-015320415-gqzhsc3h` 仍指向 `test V4` 及既定 projectUuid，再执行 `bridge update-connector --instance inst-015320415-gqzhsc3h --no-reload`。
- 实际 exit 0：423024 bytes 从 `connector/dist/index.js` 写入，版本记录 0.6.0→0.6.1；返回 **written, NOT activated**。未派发 reload，未保存编辑不会因此丢失，未寻址或写入另一窗口。日志 `.tmp_087f3/update-no-reload.log`。
- 当前只能称“候选已写入存储”，不能称新分支已运行。下一步等岳在 test V4 点一次 Boardwise 扩展菜单激活，再重新核 instance/project、capabilities 和在线读数。

## 8. 真实在线验收结果（2026-11-16）

### 激活与 #87⑤

- 岳点一次 Boardwise 菜单后，新 instance=`inst-121517427-g280bz4e`，test V4 运行 connector **0.6.1**，`capabilities.pcbRenderViewport=true`；P43 焦点与 projectUuid 均复核一致。
- P43 `sch.readback`：C24 `100nF / CC0603KRX7R9BB104`、R15 `10k / 0603WAF1002T5E`、U9 `STM32G431 / STM32G431RBT6`，三件均 `valueSource=OtherProperty`、`mpnSource=ManufacturerId`，primitiveId 与事前基线一致，`fields.OtherProperty={object:true}` 不变；11 个 netflag 的 value/mpn 全为 null，componentCount=15，无 unreadable/problems。
- 当前公开 source 为 102274 字符、323 记录、truncated=false；逐件 ATTR Value/Manufacturer Part 与 readback 完全相同。源流哈希与事前不同，因此没有拿“哈希不同”当内容差异，已按 ATTR 实际值核对。证据 `.tmp_087f3/p43-readback-new.json`、`p43-document-source-new.json`。

### #87② 直接 render

- PCB1：196764 B，SHA-256=`5300e566b4986655205bb4484c2b6c35cda06d789d8f97042e069111f51d878a`；PCB2：93676 B，SHA-256=`6c1a51744bda7bf912738eb91ca6d8b7c2d825bae2a6418c44a6d40183d8818c`。均为真实 PNG、`channel=evidenceGrade=viewport`、activated uuid 正确。PCB1 SVG exit 1 / NOT_IMPLEMENTED，明确“不支持 PCB 文档导出，未尝试”。
- 主代理已目检 `outputs/review/087f3/pcb1.png`、`pcb2.png`：分别对应实际板框与空板，不是缓存错板。

### 全文档 review-evidence

- 全新目录在线 checkup exit 1，工程仍有 26 ERROR、缺手册/分诊与 boardsEmpty；这不是板级通过。随后默认全部页/板 `review-evidence` **exit 0**：`capture.ok=true`、`identity.verifiedAgainstReport=true`、`focusRestore=restored(originalUuid=P43)`。
- `live-evidence.json` bytes=182276，SHA-256=`dd0c57cd5083b29e9a3816ea6cc130ff8f94f6022719c87ea9226678ff03a514`。`pcbImage.status=ok`，三块 PCB 均有 viewport PNG artifact 与成功 step；`livePcb.status=ok`（3 块 readback+geometry）。报告 schema 已为 `boardwise.checkup/7`。
- 第三板图 bytes=93750，SHA-256=`aa3826a13ad08ea14268253e2ee1dbe1c2cf3073bb6cbea1624100d85f216298`，主代理目检为预期的空板网格。delivery 仍 partial，只因 datasheets=unavailable；没有把它改写成整板通过。
- 最终 P43 恢复，未修改/保存设计，未路由另一窗口。V3、生产非空板、SVG/PDF 与多板并发未覆盖。

## 9. 定稿文档与联合复验

- 文档已从“候选/未在线验收”改为“工作树实现、test V4 已在线验收、未发布”：SOP 标题为“PCB 目视复核：几何与 viewport 两级证据”，坑23与 `_PCB_VISUAL_MARKER` 同步；历史 60.01 s 边界、旧 connector 零 render、PNG≠视觉通过和 V3/生产板未覆盖均保留。
- 主代理最终联合复验 **186 passed**（doc-claims + live_capture + review_evidence_cli + evidence_coverage），两 SKILL 副本 `cmp` 一致，diff-check 通过。文档测试继续回源码核 capabilities/channel/grade，并禁止“工作树候选/未在线验收/已上线”等过期或越界措辞。
- 截止本段，#87②⑤ 实现与 test V4 在线验收均完成，**未发布**；该实现已在 `3d4a0d5`（`origin/main`）。SOP 与坑23 仍写作“工作树实现”，属同批历史措辞，另批校正。Issue 只准备复验说明，未经岳批准不评论、不关单。
