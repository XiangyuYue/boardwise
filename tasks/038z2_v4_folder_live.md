# 038Z2：test V4 真实 eprj3 多文件与在线/离线差分

日期：2026-11-16，宿主 **4.1.100**。前置：038Z1 只证明三 PCB 骨架的 `.epro2` 语义一致，真实 eprj3 文件夹、多文件守卫与非空多板仍未覆盖。本批只读真实文件夹 `E:/LC Project/test V4/test V4.eprj3`，不改设计。

## 身份与边界

- 工程 `test V4`，projectUuid `1ea6af15c2b1bd8132b46a0648d4e149ced21066c4a6650bbffd40dc5e286a5b`，活动 P43=`797f20b8a217b331`。
- 文件夹实测：3 个 `pcb/*.epcb2`、7 个 `sch/**/*.esch2`、3 个 BOARD；三块 PCB 文件各只有一份 PCB 文档，无 FOOTPRINT/DEVICE/SYMBOL 库副本。
- 只允许只读该工程目录、运行离线 `checkup --file "E:/LC Project/test V4"` 和在线 `checkup --project "test V4"`，以及 doc.list/status。不得复制真实容器入仓库/fixtures/blocklib，不修改/保存设计，不路由其它工程。

## 完成条件

1. 离线、在线分别用全新输出目录，记录真实 exit/schema/conclusion/coverage。
2. 对拍逐板 title/boardUuid/components/copperLayers/checksRun/findings、crossView、archivePcb、schema。格式不同（文件夹 vs `.epro2`）只做语义差分，不称同字节对拍。
3. 真实多文件路径必须走过 3 个 `.epcb2` 的合流；重复 PCB、分歧库和相同库副本三种 guard 是否实际触发按文件事实记录，未触发不得写成已验证。
4. 现有合成多文件测试只作补充负例，不替代真实证据。生产缺陷另开小批，不在验收中顺手修。

证据 `outputs/review/038z2/`，临时 `.tmp_038z2/`。零 git 写、零删除、零全量。

## 实际结果（2026-11-16，EDA 4.1.100）

- 真实文件夹离线 exit **1**，在线 exit **1**，schema 均 `boardwise.checkup/7`。`pcb_review.boards` 三板完整字段逐字一致；各 35 checks，findings 22/20/9，components=0，copperLayers=2/0/0。`pcbReviewMissing=false`，archivePcb 均 ok 且 errors 一致。
- 两侧自有 findings 各 **60 条**，完整多重集一致；仅 `param-rc-cutoff` 的 C25/C26 组合在 index 3–8 顺序不同，已记录为排序差，不是电气差异。证据 `outputs/review/038z2/differential.json`。
- 真实输入确实走过 3 个 `.epcb2` 的合流路径；三块文件各只有一份 PCB 文档，没有 FOOTPRINT/DEVICE/SYMBOL 库副本，因此重复 PCB、分歧库与相同库副本三种 guard **未在真实样本上触发**，不能写成真实负例已完成。
- 合成补充 `test_038p1_eprj3_multi_guards.py + test_038p_eprj3_multi_pcb.py`：**17 passed**。它只支持既有 guard 负例，不冒充真实库副本证据。
- 本批未修改生产代码或设计，未复制真实容器入库。NC/缺省 yAxisDirection/非空多板分别由 038Z3/Z4 记录未覆盖。
