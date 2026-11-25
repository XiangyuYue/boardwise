# 任务书：620E — 620D 后 P126 最终重放证据刷新

## ① 前因后果

618/620A 已证明 P43/WiFi 能按 reconstructed-input 重放到原 geometry。620C/620D 随后把 pagecompiler 从证据中的 `b5ffebaf…` 改为最终 `7d94b448…`，所以 `evidence/548P126/PROVENANCE.md` 与 `replay/result.json` 再次过期。只刷新证据，不重开绘制算法；若几何不一致必须记 not-replayable。

## ② 当前树状态

HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`。602–620D 改动未提交，563/600R/review-line 等他人文件保留。drawcompiler `c5c6da702f9c1c83eaab665705c4a6a27e43bbb098c7496fabe6326a415f5b11`，placement `0674eb3842529fe280d06dc59c426f9eda7a1789cd0a1c35b86e89244596bb82`，pagecompiler `7d94b448f964faf710e28d6c48df69c19865fb80fed33a07ebec4309e4cbf95f`。620B/D 已父验，真实四候选不变。备份在 `.tmp_620e/backup/`。

## ③ 文件域与禁触清单

仅允许 `evidence/548P126/PROVENANCE.md`、`evidence/548P126/replay/{replay.log,result.json,p43.layout.json,wifi.layout.json}`、`evidence/620e/`、`.tmp_620e/`、`.tmp_pt_620e*/`、本任务书。禁止生产源码、测试、规格/输入、fixtures、原报告/原候选、其它证据、docs/tasks 路由、git、真机、部署。不得移动/删除文件。

## ④ 交付物与验收

运行 `.venv/Scripts/python.exe evidence/548P126/replay/replay.py`，P43/WiFi 均须 ok、geometryEqual、layersIdentical、pinTipsIdentical，declaredFeet=20/18、problems=[]。更新三份当前引擎 hash 和实测日志，保持 originalArgv preserved=false、输入与 geometry 不变。跑 `tests/test_618_p126_provenance.py tests/test_620a_replay_engine_current.py` 及必要 workspace/doc 邻域。两项证据变异：旧引擎 hash 必须让 620A 红；geometry 改一位必须让 618 红；均 cp+SHA/cmp 恢复并复绿。

## ⑤ 纪律与红线

零 git 写/移动/删除，禁 rm/unlink/checkout/restore，不全量（集成轮另跑）、不真机、不部署/发布。单进程、命令带 timeout，pytest 独立 basetemp。不得改输入/geometry/断言凑一致，不把 reconstructed-input 写成历史 argv 或视觉签收。

## ⑥ 预算与交卷格式

主代理执行证据刷新与复验，不派实现代理；最多 20 分钟。`evidence/620e/REPORT.md` 记录真实命令、两 case 读数、当前 hash、测试汇总、两项变异与恢复、未覆盖项。缺真实重放或不一致只能记停止/not-replayable。
