# 任务书：598 — shared 根模块统一动态 HOME 并修复层级

## ① 前因后果

596 全量 `test_layer_rules::test_no_layer_imports_against_the_arrows` 新增失败：587 在 `bridge/daemon.py` 直接 `from ..core.config import ...`，违反 bridge 只允许自身的层级。`core` 也不能 import bridge，所以不能简单反向委托。需要让 core.config 与 bridge.daemon 共用一个无包内依赖的根模块，同时保留 586 的相对路径/尾随点空格校验和587的动态读取、显式home优先、audit never-raises。

本批只修层级与共享HOME实现，不改权限、写闸、绘制或其他行为。597 的9处测试隔离迁移已完成，真实audit SHA/mtime未变。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含所有前批改动。`bridge/daemon.py` 当前从 `..core.config` 导入 `ConfigError, boardwise_home as _config_home`；`core/config.py` 当前持有 `ConfigError` 和全部路径校验。`tests/test_layer_rules.py` 因这条 import 红；`tests/test_owner_rules.py` 当前要求164个生产模块都有owner，新增根模块必须登记并更新期望计数到165。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/home.py`（新：无包内import的动态HOME与 `BoardwiseHomeError`）
- `src/boardwise/core/config.py`（仅委托共享home、ConfigError继承关系，保留公开行为）
- `src/boardwise/bridge/daemon.py`（改为从包根home导入，audit捕获共享错误，更新旧注释）
- `contracts/module-owners.json`（登记 `home.py: shared`）
- `tests/test_owner_rules.py`（仅模块计数165与必要shared根模块断言）
- `tests/test_598_shared_home.py`（新建）
- `evidence/598/`、`.tmp_598/`、`.tmp_pt_598/`

禁止修改其它生产/测试、fixtures、前批证据和他人未提交改动；不git、不删除、不跑全量、不启动真实daemon/EDA。先cp备份所有目标文件并记录hash，变异只能cp+SHA恢复。

## ④ 交付物与验收

1. `home.py` 只依赖stdlib，提供动态 `boardwise_home()` 与 `BoardwiseHomeError`。保持：未设env默认 `Path.home()/.boardwise`；相对路径拒；普通绝对/UNC/非ASCII可；普通尾随点/空白拒；`\\?\` 形态按586兼容；不缓存。
2. `core.config.ConfigError` 继承 `BoardwiseHomeError`，`core.config.boardwise_home()` 委托共享实现，公开异常类型与文案不回归。daemon/autostart/token/audit默认路径全部用同一实现，显式home优先；`append_audit` 捕获共享错误保持never-raises，不再import core。
3. owner清单登记 shared根模块，owner/layer测试全绿；新测试证明 core与bridge读到同一家、显式home优先、共享异常可捕、无 core↔bridge import。
4. 运行：`tests/test_598_shared_home.py tests/test_587_daemon_home.py tests/test_586_config_home.py tests/test_157_auto_daemon.py tests/test_persistence.py tests/test_candidate_draw.py tests/test_187c_daemon_version.py tests/test_layer_rules.py tests/test_owner_rules.py -q --basetemp=.tmp_pt_598`，真实audit SHA/mtime前后一致。
5. 至少两个变异（恢复daemon→core import/相对HOME不拒/共享错误未捕）先红，cp+SHA恢复，保存import扫描、路径与异常读数到 `evidence/598/`。

shared兼容矩阵：config/resources与daemon/autostart两个消费者；合法绝对env路径不变，显式home不变，非法值统一错误；V3/V4、容器、多板/CBB、真实bridge/EDA未覆盖。

## ⑤ 纪律与红线

只在共享HOME及owner域修，不新增层级例外，不复制第二套路径校验，不改token/pairing/写闸，不删改宽断言、不skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。

## ⑥ 预算与交卷格式

最多30步或20分钟。交卷带层级前后结果、共享home行为、指定命令完整汇总、两个变异与恢复hash、真实audit前后、未覆盖项。
