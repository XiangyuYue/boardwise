# 任务书：590 / W-R1 — 计划来源与陈旧重封检测

## ① 前因后果

hole568 的 568-D-1/2/3 已复现：手改 LayoutPlan 坐标后只重算 `geometrySha256`，载入仍是 `verdict=pass` 且 notes 与编译器产物逐字相同；`reference-replay` 在 src/tests/contracts/dsh-plugin 零机读表示；成功 compile JSON 没有 route/provenance/mode，只有失败 recovery 常量 route=agent-adjusted。原证据在 `outputs/hole568/d/REPRO.md`。

本批建立兼容的来源合同：`automatic` / `reference-replay` / `agent-adjusted` 三值可机读；新编译产物声明 automatic 并携带与几何绑定的 provenance digest，旧文档缺 route 时按 reference-replay 解释且保持 load→dump 原字节。**provenance digest 只检测“几何改了但来源封签没更新”的陈旧重封，不是密钥签名，也不能阻止刻意重算所有公开哈希。** 文档和交卷必须明确此边界，不能用另一个可编辑字段冒充作者身份公证。

D4（work order 下游消费）与 D6（P44 交付状态）在下一批，不在本批扩域。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 566–589B 与他人改动。`layoutplan.py` 已由 582 加严格 kind/version/有限数，`pagelayoutplan.py` 同；`cli.py` 已由 581/584 加页框和输出预检。开工请以实际 SHA-256 记录，禁止整文件恢复。`outputs/054_drawcompile/` 旧 layout/page 文档是兼容样本；568-D 的手改+重封探针在 `outputs/hole568/d/probes/`。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/core/layoutplan.py`
- `src/boardwise/core/pagelayoutplan.py`
- `src/boardwise/cli.py`（仅 compile 成功 JSON 的 route/provenance/mode 附加字段及必要 helper）
- `tests/test_590_plan_provenance.py`（新建）
- `tests/test_053a_specs.py`、`tests/test_054_draw_cli.py`、`tests/test_057_draw_page_cli.py`（仅限被新输出合同直接影响且有证据的断言）
- `docs/draw.md`（仅新来源合同与边界说明）
- `evidence/590/`、`.tmp_590/`、`.tmp_pt_590/`

禁止修改 ChangePlan、agentadjusted、其他生产/测试、fixtures、前批证据和他人未提交 hunk；不 git、不删除、不跑全量、不接触 bridge/EDA。开工 cp 备份所有目标文件并记录 hash；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. 增加封闭 route 词表 `automatic|reference-replay|agent-adjusted` 与校验。LayoutPlan 新直接构造默认 automatic；`from_dict` 缺 route 的旧文档解释为 reference-replay，且记住“未声明”以保持 load→dump 原字节。显式 reference-replay/agent-adjusted 可读写，非法 route 具名拒绝。
2. automatic 文档必须带 `provenanceSha256`。它由版本化域名、route 与当前 `geometry_sha256()` 计算；from_dict 重算并拒绝缺失/不匹配。手改新 automatic JSON 后只更新 `geometrySha256` 必须因 provenance 陈旧而拒。旧文档缺 route/provenance 仍可读，但其机读 route 不是 automatic。PageLayoutPlan 采用同样三值与页几何 digest，避免只改模块 frame 就绕过。
3. `to_jsonable` 对新 automatic 写 route+provenance；对显式 reference-replay/agent-adjusted 写 route；对旧缺 route 文档不新增键，保持真实旧样本字节。geometrySha256 的既有算法与几何不变。文档明确“自洽/陈旧检测，不是不可伪造的作者证明”。
4. 单模块与 page compile 成功 JSON 增加 `route:"automatic"`、`mode:"automatic"` 与 `provenance` 对象（至少包含 mode 和 `attestation:"self-consistency-only"`），零候选 recovery 仍走 agent-adjusted，不把失败说成自动成品。保持旧字段和候选几何。
5. 真实旧样本 load→dump 字节不变；新 automatic roundtrip 通过；手改+只重算 geometry 的 D1 场景必拒；显式 reference-replay/agent-adjusted 可序列化/读取，非法 route/缺 provenance/错 provenance 必拒。
6. 新测试先在基线先红；修后运行：
   `.venv/Scripts/python.exe -m pytest tests/test_590_plan_provenance.py tests/test_053a_specs.py tests/test_582_draw_plan_schema.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_draw_plan_saved_page.py tests/test_056_pagecompiler.py -q --basetemp=.tmp_pt_590`
   另跑 `tests/test_doc_claims.py` 与必要的真实编译/旧样本差分，完整记录所有红绿。
7. 至少两个因果变异（去掉 provenance 校验、旧文档误判 automatic、成功 payload 不写字段）先红，cp+SHA 恢复；保存 D1 原始拒绝、三种 route、旧文档 diff 和真实 CLI JSON 到 `evidence/590/`。

兼容要求：旧 LayoutPlan/PageLayoutPlan 可读且字节不变；新字段不进入几何 digest，不改变既有几何；compile `ok` 仍只表示有合法候选，不能表示视觉/交付验收。V3/V4、容器、多板/CBB、真机未覆盖。

## ⑤ 纪律与红线

只在现有 plan/compile 链添加来源与派生校验，不新增平行签名/构建子系统，不改几何、verdict 或旧文档默认身份为 automatic，不用 HMAC/硬编码密钥制造安全假象，不删改宽断言、不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。若旧样本需要改字节，停止并交证据，不擅自扩大迁移。

## ⑥ 预算与交卷格式

最多 45 步或 35 分钟。交卷 ≤2000 字，逐项报告 D1/D2/D3、基线先红、修后完整汇总、两个变异与恢复 hash、旧文档字节差、三种 route、边界和未覆盖项；详细日志落 `evidence/590/`。有本批未解决红项不得写完成。
