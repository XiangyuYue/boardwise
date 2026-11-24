# 任务书：583 / W-S(shared) — ChangePlan 闭合载入合同

## ① 前因后果

hole568 总表的 569-E-01…08 中，582 已完成 LayoutPlan/PageLayoutPlan 的 E-02…E-07。剩余 shared `ChangePlan` 实锤：E-01 顶层/source/target/change 未知键被接受且 dump 静默丢弃；E-03 非 UTF-8 load 泄漏 UnicodeDecodeError；E-04 `planVersion: true` 与 `1.0` 因 Python 相等比较被当成 v1（缺省已经拒绝，不得改变）；E-08 把 LayoutPlan/PageLayoutPlan 误喂给 ChangePlan 时只报 `change/target ... got NoneType`，不指出真实文档身份。原始证据在 `outputs/hole569/e/REPRO.md` §E-01/E-03/E-04/E-08。

这是 shared 公开合同，按 `tasks/shared-platform.md` 单独集成，不夹带绘制算法、CLI 写口或配置修复。合法旧 edit/review 与 draw-module 计划的字段、执行语义和退出码必须不变。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含前批 566–582 与他人改动。`src/boardwise/core/changeplan.py` 开工 SHA-256 `b0d7ae37f17bfbcd6a40b5ba25bdff9a8674018c748811f909aa34d0d6b25711`，含前批 attributeMoves 等未提交改动，不能整文件恢复 HEAD。582 的 `layoutplan.py`/`pagelayoutplan.py` 已修，`symbolprofile.py` 的 581 有限性闸已修，本批均不碰。`outputs/016_plan_r1.json` 是合法 ChangePlan 样本；`outputs/054_drawcompile/` 提供误喂身份样本。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/core/changeplan.py`
- `tests/test_583_changeplan_schema.py`（新建）
- `evidence/583/`、`.tmp_583/`、`.tmp_pt_583/`

禁止修改 cli.py、layoutplan.py、pagelayoutplan.py、symbolprofile.py、其他生产/测试、fixtures、前批证据和他人未提交改动。不做 git 写、不删除、不跑全量、不接触 bridge/EDA。开工先 cp 备份并记录 hash；变异只能 cp+SHA-256 恢复。

## ④ 交付物与验收

1. E-01：在 `ChangePlan.from_jsonable` 对顶层、source、target、change 做闭合键校验，未知键具名拒绝，不得接受后丢弃。必须从现有 `to_jsonable` 与各 kind reader 导出完整合法键集合，覆盖所有 SUPPORTED_KINDS 以及 attributeMoves、draw/page、insert、move 等可选字段；不能用一个会误杀合法字段的窄白名单。若不同 kind 的合法键不同，按 kind 校验；至少保证真实旧计划逐一字段可往返。
2. E-03：`ChangePlan.load` 捕 UnicodeDecodeError 并包装成 ChangePlanError，含路径与 not UTF-8；坏 JSON、目录、缺失文件仍保持原话术/错误类型。
3. E-04：`planVersion` 仍必须存在，且 `type(version) is int` 并等于 1；True/1.0/字符串/未来版本具名拒绝，不改变缺省拒绝。
4. E-08：在读取 source/target/change 前识别带有 `boardwise-layout-plan` 或 `boardwise-page-layout-plan` kind 的误喂文档，ChangePlanError 明确说“这是 X，不是 ChangePlan/可执行编辑计划”；普通缺字段/未知文档仍按闭合 schema 给出有用错误，不泄露 traceback。
5. 新测试先在基线上取得各缺陷先红；修后运行：
   `.venv/Scripts/python.exe -m pytest tests/test_583_changeplan_schema.py tests/test_016_edit_cli.py tests/test_054_drawapply.py tests/test_054_draw_cli.py tests/test_534r_attribute_moves.py tests/test_534v_label_visibility.py tests/test_037_moveblock.py tests/test_036_subcircuit.py tests/test_029a_addcomponent.py -q --basetemp=.tmp_pt_583`
   另跑 `tests/test_owner_rules.py` 与必要的真实样本 round-trip 探针。完整汇总与任何既有红逐名记录。
6. 至少两个独立因果变异（闭合键/版本类型/UTF-8/身份各选代表）先红，cp+SHA 恢复；保存原始命令、汇总、合法样本 diff 和证据。

shared 兼容矩阵：review/edit 的 component-value/patch-pin/add/insert/move 与 draw-module 旧计划均覆盖；attributeMoves v1/v2 与无可选键旧计划做 negative control；V3/V4、容器、多板/CBB、真机未覆盖且不声称。重复 PCB 双审、分歧库串板不属于本批改动，不得借本批宣称验证。

## ⑤ 纪律与红线

只在原 ChangePlan loader 内实现，不新增第二套 schema/reader，不改执行逻辑、几何、verdict 或 CLI，不删改宽既有断言，不 skip/xfail。不得为了省事只校验顶层而漏掉嵌套层，也不得接受未知键后继续。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。发现合法字段无法从现有读者确定时停止并列证据，不擅自放行。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤2000 字，逐项报告 E-01/E-03/E-04/E-08、基线先红、修后命令完整汇总、两个变异及恢复 hash、两个消费者的兼容证据、未覆盖项。详细日志落 `evidence/583/`；任何本批未解决红项不得写完成。
