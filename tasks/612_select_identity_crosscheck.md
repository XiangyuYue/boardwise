# 任务书：612 — select 双词身份必须相互一致

## ① 前因后果

`outputs/hole570/d/REPRO.md` 的 **D8**：`select.resolve_identity` 用 C 号命中 `C8734`，返回项 MPN 为 `NE555DR`，但调用方同时声明 `STM32F103C8T6`，结果仍 `resolved=True/matched_by=lcsc`。反方向 MPN 命中、C 号矛盾却会拒绝，docstring 又声称两词必须一致。

本批只修 C 号命中后的 MPN 交叉核对，保持 C 号优先、精确命中唯一性、两个 UUID 必需和宿主大小写规则；不搜索真实库、不改 parts shelf 或 CLI。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批保留。
- `src/boardwise/engines/select.py` SHA-256 `a1828a23a609067af876e4daa485446feac92582db686e8f0bc338d764fca47b`。
- 605–707 行 resolve_identity：C 号命中后只检查 MPN→C 号分支（673–684），C 号分支没有 wanted_mpn 对照；`MPN_ITEM_KEYS` 与 `_item_value` 是现有身份尺。
- 现有注释“MPN 不比较，因为 host 自己命名”不能用来放行调用方明确给出的 MPN：这里只核对命中 item 自己明确携带的 MPN 字段；缺字段是否放行须与 MPN→C 分支的“carried 非空才拒”对称。
- 开始 cp 备份 select 到 `.tmp_612/backup/`。他人 563/review-line/router/临时文件禁触。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/select.py`（双词交叉核对与注释）
- `tests/test_612_select_identity_crosscheck.py`（新）
- 本任务书、`.tmp_612/`、`.tmp_pt_612/`、`evidence/612/`

禁止：CLI/parts shelf/rules/datasheet/bridge/connector/DSH、fixtures 和他人文件。不得放宽 UUID 要求、命中数量限制、搜索顺序或新增模糊 MPN 匹配；不调用真实库。既有测试不得删改宽。

## ④ 交付物与验收

1. 当 wanted_lcsc 与 wanted_mpn 都给且 lcsc 命中时，从 item 的 `MPN_ITEM_KEYS` 取实际非空值，与 wanted_mpn 按现有大小写/trim 规则比较；矛盾立即 `resolved=False`，reason 明确“LCSC hit carries <key>=<值>, not given MPN; refusing pair”。保留 candidates 证据，不能继续读 UUID 后 resolved=True。
2. item 没携带 MPN 时，沿用反向分支 carried 为空不猜的口径；精确一致通过；两词只给一个时行为完全不变；MPN 命中 C 号矛盾仍拒。不得把宿主 Ground-GND 这类与 MPN 无关的字段当 MPN。
3. 可把两个方向的交叉核对提成文件内小 helper，但不新生产子系统；错误文案保持与现有反向拒绝同形。
4. 先以 fake async client 跑未改生产：C 号命中/MPN 矛盾必须红（当前 resolved=True）；MPN 一致、缺 MPN、仅 C 号、仅 MPN 与反方向控制绿。

修后运行新测试、select/parts resolve 既有测试、187c/parts 邻域、owner/layer；不跑全量。至少两项变异：① 删除 lcsc→MPN 检查；② 把比较改成永远一致/只检查 item 是否存在。每项目标测试必须红，cp+SHA 恢复并复绿。

兼容矩阵：仅 fake `lib.device.search` 两个词与 UUID；真实库/在线/多板/CBB 未覆盖。negative control 为合法身份仍 resolved、缺字段不编造、搜索调用序不变。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机/真实库、不部署。pytest 独立 basetemp、单进程、命令 timeout。不得为通过旧测试忽略 wanted_mpn、任选一个命中、降低唯一性或模糊匹配。

## ⑥ 预算与交卷格式

一个 coder，最多 35 步或 25 分钟；不派下级。交卷 ≤1800字，含先红/修后汇总、双方向矩阵、两项变异与 SHA 恢复、未覆盖项。证据落 `evidence/612/`。缺反向控制或变异只能写「停止/未完成」。
