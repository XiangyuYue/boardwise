# 任务书：585 / W-P(shared) — ChangePlan.dump 写口合同

## ① 前因后果

584 已在 CLI 入口预检 draw 的输出路径，主代理复跑 `162 passed`，但 hole569-G-05 明确指出 `src/boardwise/core/changeplan.py:1215` 是第二个独立写手：直接调用 `ChangePlan.dump` 时，缺失父目录或目标是目录仍会裸 `FileNotFoundError`/`PermissionError`。只修 CLI 不能闭合该洞。本批只修这个 shared 写口，保留 583 的闭合 reader 与所有前批 hunk，不改 CLI 或其他业务逻辑。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 566–584 与他人改动。`src/boardwise/core/changeplan.py` 当前 SHA-256 `ffbd8f08df3a400fad6fe138d65ab652e5657fd8c3254e17b94abe8e725f21f1`，`src/boardwise/cli.py` 当前 `d194d2b874a482161b006246b06847500d6f8e82ff610ff7be0eefebd468f98e`，本批不改。合法 `outputs/016_plan_r1.json` 与 draw-module 计划是兼容样本。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/core/changeplan.py`（仅 `ChangePlan.dump` 及必要的局部写口辅助）
- `tests/test_585_changeplan_dump.py`（新建）
- `evidence/585/`、`.tmp_585/`、`.tmp_pt_585/`

禁止修改 CLI、其他生产/测试、fixtures、前批证据和他人未提交改动；不 git 写、不删除、不跑全量、不接触 bridge/EDA。开工 cp 备份并记录 SHA-256；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. `ChangePlan.dump` 对父目录不存在、父路径为文件、目标为目录、写入 OSError 具名包装为 `ChangePlanError`，包含目标路径和原因，不泄漏 traceback 给调用方；合法既有目录/文件路径的 JSON 内容、返回形状（None）不变。
2. 在任何实际写入前完成可判定目标检查；尽量复用仓内已有的原子写惯例，不能让失败留下半截 JSON。临时文件清理必须遵循生产代码既有安全方式，不执行仓库文件删除操作。
3. 真实旧计划 load→dump 仍逐字节一致；583 的 172 份合法文档等价性不得受影响。
4. 新增测试先在基线上先红：每类坏目标都断言 `ChangePlanError` 而非 OSError，且无目标半成品；合法样本不变。
5. 修后运行：
   `.venv/Scripts/python.exe -m pytest tests/test_585_changeplan_dump.py tests/test_583_changeplan_schema.py tests/test_584_draw_cli_outputs.py tests/test_016_edit_cli.py tests/test_054_drawapply.py tests/test_054_draw_cli.py -q --basetemp=.tmp_pt_585`
   另跑 `tests/test_owner_rules.py`，记录完整汇总。
6. 至少两个因果变异（去掉目标预检/恢复裸 write_text）先红，cp+SHA 恢复；保存命令、汇总、合法 diff、半成品清单到 `evidence/585/`。

shared 兼容矩阵：review/edit 与 draw-module 两个消费者均覆盖；CLI 已预检和直接 dump 两条入口都覆盖；V3/V4、容器、多板/CBB、真机未覆盖，不声称。

## ⑤ 纪律与红线

只在原 dump 写口修，不新增平行 writer，不改计划字段、几何、退出码或 CLI，不自动创建被 CLI 明确拒绝的父目录来制造两种口径，不删改宽断言、不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。

## ⑥ 预算与交卷格式

最多 30 步或 20 分钟。交卷 ≤1500 字，报告坏目标四类、基线先红、修后完整汇总、两个变异与恢复 hash、两个消费者兼容证据和未覆盖项；详细日志落 `evidence/585/`。有本批未解决红项不得写完成。
