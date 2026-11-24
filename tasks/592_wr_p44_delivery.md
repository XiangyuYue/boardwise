# 任务书：592 / W-R3 — P44 交付状态与四项读数

## ① 前因后果

hole568-D6 证明 `boardwise-draw` §5B 要求“每条绘图交付必须打印 P44 四条，缺一条只能交未验收”，但真实 compile exit 0 / ok=True 时 P1–P4 一项也不印，成功 payload 也没有交付验收状态。590 已增加 route/provenance，但那仍只说明来源与封签，不是质量或视觉通过。

本批把“候选编译成功”与“交付验收”分开：保留 compile `ok` 的既有含义；为单模块与 page compile JSON 增加 `delivery` 对象，包含 `ok/status/route/visualReview` 和完整 P1–P4。没有功能关系/视觉证据时，delivery 必须 `ok=false,status=unverified`，不得编造通过。P3 的实际路径/Manhattan 差与 P4 的器件原点二维跨度从产物独立计算并打印，P1/P2 的语义证据不足明确列出，不能拿旗标/距离计数冒充视觉结论。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`cli.py` 当前含 581/584/590/591 全部 hunk；单模块 compile 在 `_cmd_draw_compile`，page compile 在 `_cmd_draw_compile_page`，候选 LayoutPlan 可从 `result.candidates`/`result.pages` 读取。`docs/draw.md` §Baseline 已说明 P1–P4 的语义、P44 参考距离 50/95/70/205/165、跨度265×25以及“数值只作诊断”。本批不重写那些语义，不另造质量阈值。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/cli.py`（仅 delivery/P44 派生与单模块/page compile输出）
- `tests/test_592_delivery_p44.py`（新建）
- `tests/test_054_draw_cli.py`、`tests/test_057_draw_page_cli.py`（仅直接被新字段/打印影响的断言）
- `docs/draw.md`（仅 delivery与P44机器读数说明）
- `evidence/592/`、`.tmp_592/`、`.tmp_pt_592/`

禁止修改 LayoutPlan/PageLayoutPlan、ChangePlan、agentadjusted、其他生产/测试、fixtures、前批证据和他人未提交改动；不 git、不删除、不跑全量、不接触 bridge/EDA。开工 cp 备份目标文件并记录 SHA-256；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. 新增一个复用的 delivery 派生 helper，输入实际 LayoutPlan 与 route，输出 `ok:false,status:"unverified",route,visualReview:"required",p44` 四项；只有未来有真实证据才能改变状态，本批不允许自动判 pass。compile `ok` 不变，delivery 不得被称为视觉通过。
2. P1/P2 明确为 `status:"unverified"`，给出功能宿主脚分组/旗域成员需要语义与视觉复核的原因及可获得的计数（若提供，必须注明不能证明关系）；不得从几何近邻猜功能归属。
3. P3 对每条实际 segment 计算折线总长按各子边 Manhattan 之和、端点 Manhattan 距离与 excess=路径−直达；输出逐网/逐段明细及最大 excess。几何只作诊断，必要的避障不能据此判 gratuitous，因此验收状态仍 unverified。
4. P4 从 plan.parts 原点计算二维 span `[maxX-minX,maxY-minY]`，空件为 `[0,0]`；不把跨度当通用通过阈值。P1–P4 四项一项不能缺，console 在成功 compile 时分别打印四行，页级和模块级一致。
5. 单模块/page compile JSON 都带 delivery；stdout 包含 P44-P1…P44-P4 与 `delivery: UNVERIFIED`。零候选不伪造成品；已有 recovery 结构不变。
6. 新测试：真实 compile 两路、独立重算 P3/P4、四行打印、delivery.ok=false/status、route、无缺失项、旧 `ok` 与几何不变；先红后修，运行：
   `.venv/Scripts/python.exe -m pytest tests/test_592_delivery_p44.py tests/test_590_plan_provenance.py tests/test_054_draw_cli.py tests/test_057_draw_page_cli.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_592`
   保存真实 JSON/stdout和独立差分到 `evidence/592/`。
7. 至少两个因果变异（漏一项P44、P3/P4计算错、delivery默认pass）先红，cp+SHA恢复；交原始汇总、真实读数和未覆盖项。

兼容要求：compile `ok`、候选几何、route/provenance、CLI退出码与旧字段不变；delivery只加性披露，不宣称自动视觉/人工验收。V3/V4、容器、多板/CBB、真机未覆盖。

## ⑤ 纪律与红线

只在现有 compile 输出链加派生，不新增第二套质量评分器，不把几何指标当视觉结论，不把 P44 参考坐标/阈值套到所有页，不删改宽断言、不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。禁止用 git restore/checkout 恢复混合工作树。

## ⑥ 预算与交卷格式

最多 35 步或 25 分钟。交卷 ≤1800 字，报告 D6、基线先红、修后完整汇总、两个变异与恢复 hash、P1–P4实际读数、compile/delivery口径、未覆盖项；详细日志落 `evidence/592/`。有本批未解决红项不得写完成。
