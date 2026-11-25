# 任务书：620A — 617C 后刷新 P126 重放引擎证据

## ① 前因后果

618 已证明 P43/WiFi 以 reconstructed-input 重放到原 geometry，父级 5 passed。617C 随后把 drawcompiler 从 `9ded2eb3…` 改为 `c5c6da70…`，所以 `evidence/548P126/PROVENANCE.md` 和 `replay/result.json` 的 engineSha256 已过期。主代理已在最终 c5c6da70 上重跑 `tests/test_618_p126_provenance.py`，**5 passed in 86.67s**，几何仍一致。

本批只做证据刷新：用当前最终源码再跑 replay.py，更新引擎 hash 与实测读数，不重写历史 argv、原报告或候选，不重开绘制算法。若重放不再一致，状态改 not-replayable，不能沿用旧成功。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；602–619 改动保留。
- 当前 drawcompiler SHA `c5c6da702f9c1c83eaab665705c4a6a27e43bbb098c7496fabe6326a415f5b11`；placement `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`；pagecompiler `5370289d0fb84e0efc3811c98d65db131d37eb1a55853bcf978614e9c4dbb827`。
- `evidence/548P126/PROVENANCE.md` 和 `replay/result.json` 仍写 607 的 `9ded2eb3…`，需实测更新；原 geometry 不得改。
- 主代理 refresh 测试 `.tmp_pt_617c_replay_refresh` 已 5 passed。617C 的独立视觉复核在另一上下文进行，本批不写视觉结论。
- 他人 563/review-line/router/201f 与临时文件禁触。开始 cp 备份 PROVENANCE 与 result 到 `.tmp_620a/backup/`。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `evidence/548P126/PROVENANCE.md`（当前引擎 hash、日期/实测日志指向）
- `evidence/548P126/replay/{replay.log,result.json,p43.layout.json,wifi.layout.json}`（由真实重放更新）
- `evidence/620a/`（新报告与日志）
- `.tmp_620a/`、`.tmp_pt_620a/`、本任务书

禁止：src/tests/contracts/docs/原报告/原候选/历史 outputs/其它证据、他人文件。不得改 geometry/输入/规格/budget/seed，不得改 `tests/test_618_p126_provenance.py` 来掩盖失败，不重跑全量、不真机。

## ④ 交付物与验收

1. 运行 `.venv/Scripts/python.exe evidence/548P126/replay/replay.py`，单进程，记录完整日志。两个 case 必须 `ok=true`、`geometryEqual=true`、`layersIdentical=true`、`pinTipsIdentical=true`，P43 declaredFeet=20、WiFi=18，problems=[]；否则按失败状态更新，不宣称 replayable。
2. 用当前三份引擎文件的实际 SHA-256 更新 result 和 PROVENANCE；原始 argv 仍 `preserved=false`，分类仍是 reconstructed-input。原报告/原候选 hash 保持不动。
3. 运行 `tests/test_618_p126_provenance.py` 和必要 doc-claims/workspace 测试，保存完整汇总。若 617C 的最终邻域 543h3b 红出现，不把它写成新红或本批修复。
4. 至少两项文档变异：① engine hash 改回 9ded2eb3（如果测试有当前 hash 钉则必须红；若无，补一个轻量一致性钉，不修改生产）；② geometry 改一位，已有测试必须红。cp+SHA 恢复并复绿。若需新增测试钉，仅允许 `tests/test_620a_replay_engine_current.py`，并把它加入文件域后记录；不得改 618 既有断言。

兼容矩阵：P43/WiFi 两条离线 replay；完整 30 件页、真机、V3/V4、多板/CBB 未覆盖。negative control 为原 geometry 不变、原 argv 未保留、历史文件不改。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。探针单进程、命令 timeout。不得用旧 result 冒充当前重放，不通过改输入/引擎或断言凑一致，不修改其他文档路由。

## ⑥ 预算与交卷格式

一个 coder，最多 30 步或 25 分钟（含一次约 2 分钟重放）；不派下级。交卷 ≤1500字，含真实命令与两 case 读数、当前引擎 hash、测试汇总、两项变异与 SHA 恢复、未覆盖项。证据落 `evidence/620a/`。缺真实重放或不一致只能写「停止/not-replayable」。
