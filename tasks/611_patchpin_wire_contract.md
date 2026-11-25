# 任务书：611 — patch-pin 导线坐标完整性与过针网过滤

## ① 前因后果

`outputs/hole570/d/REPRO.md` 的 **D9** 有两个同函数域问题：`patchpin.wire_segments` 对奇数长度 `Line=[0,0,100,0,200]` 静默丢末坐标；`wires_through_pin` 没有 net 参数，VCC 穿身线会被 GND 的排查当成证据。当前 CLI 在 range_report 调用它时已有 `after_net`，却没传入。

本批只修 D9，不动 `wire_endpoints_on_pin` 的其它判定、addcomponent 几何、shared 模型或宿主行为。奇数坐标必须具名拒绝，不能猜最后一个数属于 x 还是 y。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批全部保留。
- `src/boardwise/engines/patchpin.py` SHA-256 `c823d7b75b5ba4f5efa0dddcaae1c7db0c3ae1bf764d5d6c612b3c2a491239a8`。
- wire_segments 98–133 行用 `range(0,len(coords)-1,2)` 静默截断；wires_through_pin 319–330 无过滤；`wire_endpoints_on_pin` 303–316 已有可选 net 的相同风格。
- `src/boardwise/cli.py` 30463–30471 同时计算 endpoint 与 through，endpoint 已传 after_net、through 未传；after_net 空必须保持原不过滤行为。
- 开始分别 cp 备份 patchpin 与 cli 到 `.tmp_611/backup/`，记录 SHA，保留其中所有前批 hunk。他人 563/review-line/router/临时文件禁触。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/engines/patchpin.py`（奇数坐标拒绝、可选 net 过滤及注释）
- `src/boardwise/cli.py`（仅 wires_through_pin 调用补 after_net 与必要注释）
- `tests/test_611_patchpin_wire_contract.py`（新）
- 本任务书、`.tmp_611/`、`.tmp_pt_611/`、`evidence/611/`

禁止：addcomponent/changeplan/shared parser/connector/DSH、其它 CLI 段、fixtures 和他人文件。不得把奇数坐标补 0、丢点或取前两个；不得改变 after_net 为空时的报告语义，不顺手修任何 suspect。既有断言不得删改宽。

## ④ 交付物与验收

1. `wire_segments` 遇扁平 Line/Points/points 奇数坐标立即 `ValueError`，错误点名 wire index/primitive id 与坐标数量，不能返回部分段。空线/非 dict 的既有行为不变，偶数扁平与 nested points 保持逐点一致；非有限坐标仍按既有 `_number`/拒绝合同处理，不扩展范围。
2. `wires_through_pin(geometry,pin_at,net="")` 增加可选过滤：net 非空只收该网；空 net 保持旧行为。VCC 穿身线在 net=GND 时返回 []，net=VCC/空时返回原 id；端点排除、T 型判定不变。
3. CLI 唯一调用点传 `after_net`，并通过 monkeypatch/局部入口测试证明 GND patch 不会让 VCC 过针线进入该网的报告；after_net="" 时传空并保持未过滤。
4. 先对未改生产运行：奇数线仍不抛（测试应红）、跨网仍被返回（红）、CLI 未传 net（红）；偶数与默认控制绿。

修后运行新测试、035 patchpin 全部邻域、029 addcomponent、036、相关 CLI edit 测试、owner/layer；不跑全量。至少两项变异：① 恢复奇数静默截断；② 删除 net 过滤或 CLI 转发。每项对应测试必须红，cp+SHA 恢复并复绿。

兼容矩阵：geometry dict + CLI range report 离线 fake；默认空网兼容旧调用。真机/V3/V4、多板/CBB 未覆盖；negative control 为偶数几何与空网报告逐字段不变。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署。pytest 独立 basetemp、命令 timeout、单进程。不得吞 ValueError、改输入 Line 长度凑过、默认选第一网或改其它 patchpin 规则；cli.py 的大量前批内容必须原样保留。

## ⑥ 预算与交卷格式

一个 coder，最多 35 步或 25 分钟；不派下级。交卷 ≤1800字，含先红/修后完整汇总、奇数拒绝原文、跨网与空网读数、两项变异及 SHA 恢复、未覆盖项。证据落 `evidence/611/`。缺 CLI 转发或变异只能写「停止/未完成」。
