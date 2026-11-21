# 562B1：Python 纯图投影 `core/livepath.py`

## 1. 前因后果

562A 已提供 `pcb.path_probe` 的真实证据形状：`from/to/nodes/edges/seeds/frontier/coverage/unknown/ignored/errors`。主代理复核 52 passed，Arc 与预算变异均先红后恢复。现在只实现 Python 纯函数：端点校验、双向邻接 proof、确定性 BFS、三态和 `boardwise.pcbLivePath/1`。本批不接 bridge/CLI/protocol/DSH，不做真机。

## 2. 当前树与文件域

HEAD `0b21342`，混合工作树。只允许新 `src/boardwise/core/livepath.py`、新 `tests/test_562_live_path.py`、`.tmp_562b1/`、`evidence/562b1/`、`tasks/562b1_live_path_projection.md`。不得改 connector、assembly、protocol、owners、合同快照、550/559、绘制线、fixtures、真实工程。先阅读 562 总合同、562A 源码输出与 `connector/tests/pcb-path-probe.test.mjs` 主夹具。零 Git 写、零删除、零全量 pytest。

## 3. 纯函数输入与输出

实现 `project_live_path(payload: Mapping[str, Any], *, source: Mapping[str,Any]|None=None) -> LivePathResult`，不读文件/bridge/EDA。结果 dataclass 提供 `as_dict()` 与 `to_json(indent=None)`，canonical `sort_keys=True`、`allow_nan=False`。

输出固定键：`schema=boardwise.pcbLivePath/1 / verdict / source / query / path / hops / hopCount / viaCount / unknown / ignored / errors / coverage / scope`。

- `query.from/to` 保留 designator/pad/primitiveId/type/net；`path[]` 为有序 `{primitiveId,type,net}`；`hops[]` 为有序 `{from,to,kind,evidence[]}`。
- 每个 evidence 保留原 directed edge 的 `{from,to,method,kind,callIndex,hostOrder}`。`hopCount=len(hops)`，`viaCount` 数 path 的 Via。
- `coverage.partial` 在有 unknown/errors/frontier/截断或未完整遍历时为 true；完整负向只有 `coverage.complete=true` 且无缺口才可能 NOT_PROVEN。
- `scope` 明确支持 Line/Via、双向邻接、端点 direct；排除 Arc（未验证）、Pad↔Via、铺铜/PLANE、未知类型、net-name-only、DRC/线长/阻抗。

## 4. 端点与 proof 规则

1. 两端必须 `status=resolved`、pad id/type/net 完整、`direct.ok=true`，同一非空 net、不同 pad id；扫描/readErrors/直接调用失败均 INDETERMINATE。两端 coverage.nets 不一致不得 CONNECTED。
2. 节点键 `(type,primitiveId)`；net 必须一致。边引用缺失节点、身份不一致、非法 from/to 都要 `unknown`，不得进 proof。
3. `pad-direct`：只允许查询端点↔Line，作为无向直接证据；Arc→`arc-unverified`，Via→`pad-via-contact`，中间 Pad/其他类型→unknown。
4. `pad-direct-other-pad`：只允许两个查询端点，作无向直接证据。
5. `adjacent`：Line/Via 之间，**只有存在反向 directed edge** 才成为无向 proof。两边都须 `method=getAdjacentPrimitives`、id/type/net 一致；单向写 `unknown:non-reciprocal-adjacency`。hop.evidence 同时保存正反向两条。
6. `adjacent-to-endpoint-pad`：Line→查询端点 Pad 必须与对应 `pad-direct` 配对；Via→Pad 记 `pad-via-contact`。缺配对记 `unknown:non-reciprocal-adjacency`。
7. Connector 的 unknown/errors/ignored 原样保留；Python 追加的 unknown 也带 code/from/to 等可定位字段。重复边可 ignored:duplicate-edge，但不得丢第一条证据。

## 5. BFS、三态与确定性

- 从 from 起 BFS，合法边按无向处理，邻居按 `(type,primitiveId)` 排序；返回最短跳数路径。`hops.evidence` 保留证据原方向，不伪造成 path 方向的宿主调用。
- 找到目标即 CONNECTED；无关 unknown 不推翻已证路径，但 coverage.partial=true。
- 找不到时，只有可达合法图已穷尽且 unknown/errors 为空、无 per-call/vertex/edge/time 截断、frontier 为空、端点与 coverage 完整才 NOT_PROVEN；否则 INDETERMINATE。NOT_PROVEN 不是开路。
- 同一 payload 两次投影除 source 外必须字节一致；不能依赖 edges 原顺序。

## 6. Negative controls 与验收

新测试至少覆盖：

1. direct Pad→Line 正例、两根 Line 的双向邻接正例、Line→Via→Line 正例、Pad→对方 Pad 正例。
2. 单向邻接不能 CONNECTED；补反向即最短路径；缺反向时负向 INDETERMINATE。
3. 异网/缺 net/同 pad/端点未解析/直接调用失败/节点缺失/身份不符全部拒绝或 INDETERMINATE，不能产生 proof。
4. Pad↔Via、Arc、铺铜、Polyline、intermediate Pad 不进入路径，各自 unknown/ignored 分类正确。
5. per-call 截断、frontier 非空、coverage.complete=false、Python 发现单向证据都压否定；预算未知与完整负例区分。
6. 无关 unknown 不推翻正路径但 partial=true；`coverage.complete` 单字段不能放行 NOT_PROVEN。
7. 最短路径、hop 证据含正反向 callIndex/hostOrder、viaCount/hopCount 一致、两次输出字节相同。

运行 `.venv/Scripts/python.exe -m pytest tests/test_562_live_path.py -q --basetemp=.tmp_pt_562b1`。主代理随后做“允许单向邻接成 proof”和“截断仍放行 NOT_PROVEN”两项变异先红后 cp+SHA 恢复。子代理 ≤40 步/30 分钟，交卷 ≤2000 字，真实测试汇总、未覆盖项；只能写工作树完成，未接 CLI/真机。


## 7. 实际完成与父代理验收

- `project_live_path` 与 `LivePathResult` 已落地，输出 `boardwise.pcbLivePath/1`，只接受端点 direct、Line/Via 双向邻接与相邻端点配对证据；BFS 最短路径和 hop 证据均确定。
- 主代理独立 **46 passed**；允许单向 proof 变异 **2 failed / 44 passed**，截断放行负向变异 **16 failed / 30 passed**，均 cp+SHA 恢复并复跑 **46 passed**。证据 `evidence/562b1/562b1-pure-projection.md`、`evidence/562b1/parent-validation.md`。
- 状态：纯投影完成、未提交未推送；CLI 由 562B2 接管，真机/DSH 不在本批。
