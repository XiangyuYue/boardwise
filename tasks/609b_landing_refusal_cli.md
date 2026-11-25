# 任务书：609B — LandingRefused 接入 edit plan 的具名拒绝

## ① 前因后果

609 为 D3 新增 `LandingRefused(ValueError)`，使 `landing_spot` 不再返回 NaN/Inf。执行者交卷时发现 `cli.py:27774` 只 catch `LadderExhausted`，所以带 NaN 锚点的真实 add-component plan 会以新异常裸栈。这是本批引入的集成缺口，不能留作“以后再说”，也不应回退有限性守卫。

本批只做 CLI 错误映射：把 `LandingRefused` 纳入现有具名 exit 5 通道，保持 `LadderExhausted` 文案与行为；不扩大成捕获所有 ValueError，不改 addcomponent 的几何实现。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–611 改动保留。
- `src/boardwise/engines/addcomponent.py` 当前 SHA `e323c5a8b25a6e87b890698d5d0f657268f8a0c18a071b4038a55cfb49c595c3`，本批不改。
- `src/boardwise/cli.py` 当前 SHA `41621bbc56b0dae719804e021de558a9b0b20fb8cd0a0e4b9bc7a202f771268f`，含 611 的唯一 patch-pin hunk，必须保留。
- 27772–27780：真实 `addcomponent.landing_spot(...)` 仅 `except addcomponent.LadderExhausted` 后 exit 5。
- 他人 563/review-line/router/201f 与临时文件禁触。开始 cp 备份 cli.py 到 `.tmp_609b/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/cli.py`（仅 LandingRefused 的局部捕获与错误文案）
- `tests/test_609b_landing_refusal_cli.py`（新）
- 本任务书、`.tmp_609b/`、`.tmp_pt_609b/`、`evidence/609b/`

禁止：addcomponent/patchpin/select/moveblock/canvasrender/shared/connector/DSH、fixtures、其它 CLI 段及他人文件。不得改返回码、自动补落点、捕获宽 ValueError 或隐藏 traceback 之外的真正错误；既有断言不得删改宽。

## ④ 交付物与验收

1. 用真实 `cli.main(edit plan --add-component …)` 与 fake bridge，但**不 mock landing_spot**：让 geometry 的锚器件携带 NaN X/Y，使 609 的真实 `landing_spot` 抛 `LandingRefused`。必须 exit 5，stderr 明指 landing/origin/有限坐标，无 Traceback，无计划 JSON 或任何写动作。
2. 正常 LadderExhausted 仍使用原 exit 5/原文；合法落点 plan 不变。可另测 grid=0 直接 helper 只作补充，不替代真实 CLI。
3. 先对当前生产运行新测试，复现 LandingRefused 裸栈（记录 red）；修后新测试与 609/029a/035/edit 邻域通过，保存完整汇总。若测试参数与旧 add-component 不同，以 `tests/test_029a_addcomponent.py` 的真实调用为准，不构造假命令。
4. 至少两项变异：① except 去掉 LandingRefused，真实 CLI 用例红；② 把异常映射改成返回 0/成功，文件与 exit 断言红。每项 cp+SHA 恢复并复绿。父级会独立检查不是捕获宽 ValueError。

兼容矩阵：add-component 的真实 CLI + fake bridge 只读；无 daemon/EDA/真实工程。V3/V4、多板/CBB 未覆盖。negative control 为合法 plan、LadderExhausted 和未知异常不伪装成功。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得回退 609 的 isfinite，不修改测试输入让 NaN 消失，不用 broad except 吞掉其他程序错误。

## ⑥ 预算与交卷格式

一个 coder，最多 25 步或 20 分钟；不派下级。交卷 ≤1500字，含先红裸栈、修后 exit/stderr/产物清单、邻域汇总、两项变异与 SHA 恢复、未覆盖项。证据落 `evidence/609b/`。缺真实 CLI 或变异只能写「停止/未完成」。
