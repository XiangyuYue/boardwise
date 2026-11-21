# 562B2：`pcb path` CLI、协议与 shared 集成

## 1. 前因后果

562A Connector 已能提供图证据，562B1 `core/livepath.py` 已完成纯 BFS/三态，主代理独立 46 passed，单向和截断变异分别 2 红、16 红后恢复。现在把纯函数接到公开在线命令，关闭 Connector contract-drift 的 `inRegistryOnly=['pcb.path_probe']`。本批不做 DSH、不做真机、不改 559 direct-only。

## 2. 当前树状态与 shared 锁

HEAD `0b21342`，混合工作树。`bridge/protocol.py`、`docs/bridge.md`、`tests/test_537a_daemon_write_policy.py` 等有其他 owner 未提交 hunks，只能追加/修改本批指定行，不能格式化或还原。shared 按 `tasks/shared-platform.md` 串行，绘制线不动。

## 3. 文件域

- 新 `src/boardwise/pcb_path.py`、新 `tests/test_562_live_path_cli.py`；
- `src/boardwise/commands/assembly.py` 仅 `path` parser 与 dispatch；
- `src/boardwise/bridge/protocol.py` 仅 `pcb.path_probe` action；
- `contracts/module-owners.json`、`contracts/cli/v1.json`（官方生成）；
- `tests/test_owner_rules.py`、`tests/test_540_cli_shared.py`、`tests/test_540_cli_review.py` 仅新模块与 161 计数；
- `tests/test_537a_daemon_write_policy.py` 仅 `NOT_DESIGN_WRITES` 块新增本 action；
- `tests/test_doc_claims.py` 仅 pcb 子命令集合加 `path`；
- `docs/bridge.md`、`docs/review-sop.md` 仅新命令段；
- `.tmp_562b2/`、`evidence/562b2/`、`tasks/562b2_live_path_cli.md`。

禁改 `core/livepath.py`（B1 已验收，若发现缺口先交回主代理）、connector、550/559、绘制线、fixtures、真实工程、DSH、版本文件。先 cp 备份所有将改既有文件并记 SHA。零 Git 写、零删除、零真机、零全量 pytest。

## 4. 公开合同

### Adapter

`pcb_path.py` 复用 559 的 `PROBE_ACTION/PROBE_PARAMS`、版本读取和短桥接路由，新增 `PATH_ACTION='pcb.path_probe'`：

1. 先 `sys.probe {namespaces:[]}`，失败按 559 `source.versions.missing/error` 披露，不伪造版本、不影响 verdict；
2. 再 `pcb.path_probe {from,to}`，异常是 refusal：stderr 一行、stdout 空、exit 3；
3. 用 `project_live_path` 投影并写 source.versions；exit 0/2/3 与三态一致。

CLI：

`boardwise pcb path --from REF.PAD --to REF.PAD [--project P] [--instance I] [--port N] [--json PATH]`

- 无 FILE/live/board，不自动切页。无 `--json` 时 stdout 一份 `boardwise.pcbLivePath/1`；有 `--json` 时同一 JSON 写 PATH、stdout 为空。
- JSON 写入须同目录临时文件 + `os.replace` 原子替换，父目录可创建；失败具名退 3 且不打印 verdict，残留临时文件路径如实披露，禁止 unlink/rm 清理。
- protocol action `risk=read`、`design_write=False`、params 仅 from/to，summary/returns 必须描述 nodes/edges/seeds/frontier/coverage 和“无 verdict、无 entireTrack”。
- assembly `path` 注册在 `connection` 后，`dispatch_pcb` 新增分支；旧 gate/net-path/connection 不变。

### Owners/合同

`core/livepath.py=shared`、`pcb_path.py=assembly`，模块总数 **161**。`contracts/module-owners.json` note 与 owners 同步；`contracts/cli/v1.json` 只能由 `PYTHONPATH=. .venv/Scripts/python.exe tools/cli_contract.py --write` 生成。`tests/test_doc_claims.py` 的 pcb 子命令集合变 `{gate,net-path,connection,path}`，docstring 同步。

## 5. 测试与 negative controls

新 CLI 测试复用 B1 payload 和 559 FakeBridge 范式，至少钉住：

- parser 全参/缺参/非法位置参数；`--live`、board 等不存在；
- action 顺序、封闭 params、project/instance/port 路由；
- CONNECTED/NOT_PROVEN/INDETERMINATE 的退出码与 stdout schema；
- 版本读取失败仍返回实测 verdict，missing/error 完整；
- path action 失败时 stderr+空 stdout+exit 3；
- 不带 `--json` 输出 JSON；带 `--json` 文件完整、stdout 为空；写失败退 3 且不打印 verdict、不 unlink 清理；
- protocol 目录、owner/layer、559/550 邻域与 Connector contract-drift 不再出现 `inRegistryOnly`。

运行：

```bash
.venv/Scripts/python.exe -m pytest tests/test_562_live_path.py tests/test_562_live_path_cli.py tests/test_559_pcb_connection.py tests/test_559_pcb_connection_cli.py tests/test_550_pcb_net_path.py tests/test_540c_contracts.py tests/test_540_cli_shared.py tests/test_540_cli_review.py tests/test_537a_daemon_write_policy.py tests/test_action_catalogue.py tests/test_owner_rules.py tests/test_layer_rules.py tests/test_doc_claims.py -q --basetemp=.tmp_pt_562b2
cd connector && npm test && npm run typecheck
```

主代理随后做两项独立变异（CLI 用错 action、JSON 写失败仍打印 verdict）先红后 cp+SHA 恢复。子代理 ≤40 步/30 分钟，交卷 ≤2000 字，真实命令→汇总、未覆盖项；只能写工作树完成，未真机、未 DSH。

## 6. 兼容矩阵与边界

- V4 fake/协议：本批覆盖；V3 未覆盖。
- 在线 CLI fake：覆盖；真机归后续 562C，不提前声称。
- `.epro2/.eprj2/.eprj3`：本批不改 parser，未覆盖；重复 PCB 双审与分歧库串板仍不验证。
- 单板焦点：覆盖；多板不自动选择；普通 ComponentPad，CBB 内部未覆盖。
- 559 direct-only 与 550 离线 net-path 的源码/输出必须不变。


## 7. 实际完成与父代理验收

- `pcb path`、protocol action、assembly dispatch、owners=161 与官方 CLI 合同均已接入；`--json PATH` 原子写入且 stdout 为空，写失败不打印 verdict、不删除残留。Connector 全量 **876 passed / 0 failed**，合同漂移关闭。
- 主代理收紧 assembly 的 Pad→Line 文案并重生成合同，十三文件聚焦 **376 passed in 23.83s**。父变异用错 action **16 failed / 18 passed**，JSON 写失败仍打印 verdict **1 failed / 33 passed**，均 cp+SHA 恢复并复跑 **34 passed**。证据 `evidence/562b2/handoff.md`、`evidence/562b2/parent-validation.md`。
- 状态：CLI/shared 实现完成、未提交未推送；真机由 562C 执行，DSH 明确不做。
