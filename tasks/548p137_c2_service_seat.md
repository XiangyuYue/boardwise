# 548P137 — C2 服务支路保留区与宿主线

> 状态：**C2最终首拒已修复 / 完整整图未通过**。证据 `evidence/548P137/README.md`。
> 真实 `_place` 已 `placed=True`、5/5服务落座；完整候选首拒前移为3V3联合座位，下一批见 `tasks/548p138_joint_3v3_seat.md`。

## 当前首阻

修复后生产SHA：drawcompiler `324a4db6f6265d10ac66170a92039b6b80c63437443fd402b80c347cba451be6`，
placement `f550f6eafa3d45b3c23a104925c3a9fa1c2d02f8424068bd31dfe8dba9859d60`。
输入 `evidence/548P125/circuit.full.g3c.pinmap.json` +
`evidence/548P126/full.presentation.service-feedback.json`，库P59。

基线的正常生产首先失败于 panel service:C2，但完整侦察证明后续已有 C2=1 的5/5方案；
根因是 `_service_seats_in_flag_room` 在无下游通过时返回首个失败方案。已只增加首个完整服务
答案快照，未扩reach/GAP/预算/页框，未移动C3.2。修复后 `_place` 通过，完整候选首拒为
3V3 `share:chain` / `share:part:U1` 联合座位。

## 唯一问题

C2的保留房间和宿主线具体与哪一个支路对象互斥？先捕获：
1. C2实际宿主脚、候选origin/host_path/flag room；
2. C1/C3/BZ1已落座房间和引线；
3. 现有branchOrder/host反馈/offset为什么没有合法组合，是否必须先改服务归属或通道预留，
   而不是继续换档。

只读侦察先行，若需修复只限draw线必要文件和一个新测试，不新建builder/router。
P43/WiFi geometry必须不变，P126/P135成果不得重开。

## 完成条件

- 新测试基线先红，至少两项变异先红并恢复；不能只断言helper被调用。
- 真实C2逐项对照；只有ok=True才逐脚/渲染/视觉，否则交下一首拒。
- 子代理20分钟/40步，主代理独立复核；不默认全量、真机、apply或Git写。

## 实测交卷

- 新测试基线 `1 failed, 2 passed`；修复后 `3 passed`；M1/M2均 `1 failed, 2 passed`，Copy-Item+SHA恢复。
- P137/P126/P135/P43聚焦 `17 passed in 61.20s`；文档/工作区 `67 passed in 8.63s`；
  资产终扫 `290 checks / 25 indexLinks / 20 worktreeEntries / errors=[]`。
- 服务邻域 `53 passed, 3 failed`，三红为旧WiFi冻结输入的ESP_TXD/J2关系且
  `serviceSeatsStated=False`，已单列披露。
- 修复前后真实服务记录均42次、6次完整5/5；修复后 `_place` 返回 `placed=True`、`failure=None`。
- 完整 `_build_candidate` 仍 `built=False`，首拒为3V3联合座位；无整图候选，未做逐脚/渲染/视觉。
- P43 geometry `a9201cfb85d8878391713a143a1199c9a9bb0e6e1a33404f0a038edcfea3d48e`、
  P118 WiFi geometry `a6232436e8e7f78d6168f353944a8cb0c76b5068684e5865b018149e92be5fda` 均不变。
