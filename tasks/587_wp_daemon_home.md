# 任务书：587 / W-P(daemon) — BOARDWISE_HOME 读取时点统一

## ① 前因后果

hole568 的 569-F-3 已复现：`core.config`/`resources` 每次调用读取 `BOARDWISE_HOME`，但 `bridge.daemon` 在导入期冻结常量，`bridge.autostart` 又引用该常量。同一进程改变环境后，配置落到 home_b，token/audit/log 却落 home_a，造成身份与审计分流。原始证据在 `outputs/hole569/f/REPRO.md` §H-569F-3。586 已修配置路径输入校验，本批只修 daemon/autostart 的动态 home 解析，不改配置、parts、权限或绘制算法，不启动 daemon。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 566–586 与他人改动。开工 hash：
- `src/boardwise/bridge/daemon.py` `22fd862630bccee7d9ee1230b630517014b08a739c3b45e2f733ad19baacca87`（含前批写闸改动，必须保留）
- `src/boardwise/bridge/autostart.py` `e6e53daad7946b0ee8b5692f48dc1403d3d26c7a67cf347ff5d670f10729d47a`
- `src/boardwise/core/config.py` 已修为 `64322fc3a7131513f74cab157ba5f031d236e7b7ac5de0f247f0178147a96e62`，本批不恢复。
现状：`daemon.BOARDWISE_HOME` 在约 286 行导入期赋值；`token_path`、`connector_token_path`、`audit_dir`、`BridgeDaemon.home` 默认值和 `autostart.log_dir/stamp_path` 都读它。需保留显式 `home=` 参数的优先级与旧调用形状。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/bridge/daemon.py`（仅动态 home 解析及必要调用点，保留公开兼容别名如确有需要）
- `src/boardwise/bridge/autostart.py`（仅 log/stamp 的 home 解析）
- `tests/test_587_daemon_home.py`（新建）
- `evidence/587/`、`.tmp_587/`、`.tmp_pt_587/`

禁止修改 config.py、parts.py、cli.py、其他生产/测试、fixtures、前批证据和他人未提交改动；不 git 写、不删除、不跑全量、不启动/连接 daemon 或 EDA。开工 cp 备份两个目标文件并记录 SHA-256；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. 环境在进程内从 home_a 改为 home_b 后，无显式 home 的 `token_path()`、`connector_token_path()`、`audit_dir()`、`autostart.log_dir()/stamp_path()` 以及新建 `BridgeDaemon` 的默认 home 全部与 `core.config.boardwise_home()` 一致；不得继续使用导入期 home_a。显式 `home=` 仍优先且不被环境覆盖。
2. 保留 `daemon.BOARDWISE_HOME` 的公开兼容方式或明确迁移所有读者；不能让旧 `from daemon import BOARDWISE_HOME` 的调用静默得到错误家。若保留常量只作历史默认，所有生产路径不得再读它；交卷列出兼容性依据。
3. 新测试先在基线上先红，再运行：
   `.venv/Scripts/python.exe -m pytest tests/test_587_daemon_home.py tests/test_157_auto_daemon.py tests/test_bridge.py tests/test_bridge_cli.py tests/test_537a_daemon_write_policy.py tests/test_586_config_home.py -q --basetemp=.tmp_pt_587`
   按实际影响补 `tests/test_549_pairing_authorization.py`、`tests/test_165_update_connector.py`，但不触发真实 daemon。完整汇总与任何环境限制如实记录。
4. 至少两个因果变异（恢复 token/home 默认读旧常量、恢复 autostart 读旧常量）先红，cp+SHA 恢复；保存动态环境读数、显式 home negative control 和命令到 `evidence/587/`。

shared 兼容矩阵：config/resources 与 daemon/autostart 两个消费者均覆盖；旧环境不变时路径不变，显式 home 不变；token/pairing/write guard 逻辑不变；V3/V4、容器、多板/CBB、真实 bridge/EDA 未覆盖，不声称。

## ⑤ 纪律与红线

只改 home 解析，不改认证、权限、写闸、日志内容或 daemon 生命周期，不新增全局可变缓存，不删改宽断言，不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。禁止用 git restore/checkout 恢复混合工作树。

## ⑥ 预算与交卷格式

最多 35 步或 25 分钟。交卷 ≤1800 字，报告 F-3、基线先红、修后命令完整汇总、两个变异与恢复 hash、显式 home/旧环境兼容和未覆盖项；详细日志落 `evidence/587/`。有本批未解决红项不得写完成。
