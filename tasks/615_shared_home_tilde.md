# 任务书：615（shared）— BOARDWISE_HOME 的 `~/…` 统一展开

## ① 前因后果

`outputs/hole570/d/REPRO.md` 的 **D10** 最初实测 `BOARDWISE_HOME="~/bw"` 会在 CWD 建字面 `~`，空串时 config 与 daemon 不一致。76e0806 已经过 586/587/598：`src/boardwise/home.py` 是唯一动态读取点，空串 `if not override` 已统一回默认，普通相对路径按新合同具名拒绝，不再自动绝对化。因此不能照旧 FIX 把任意相对路径变成 CWD 下绝对路径，这会恢复已知漂移。

剩余缺口是 `~/bw`：`Path(override)` 在 is_absolute 前没有 expanduser，所以合法的用户家目录写法被当相对路径拒绝（旧版则建错目录）。本批只让 `~` 展开为当前用户家目录，并保持空串、普通相对路径、尾点/空格、扩展 Windows 前缀和动态读取合同。

## ② 当前树状态

- HEAD/origin `76e08060ded403793bc6fb0eb64b38f9e140c765`；前批全部保留。
- `src/boardwise/home.py` SHA-256 `74d4328ad6fec007bc7337e03f0054e2afcb181295b345174e98336ddae2a728`，59–92 行是唯一实现，stdlib-only，owner=shared。
- `core.config.boardwise_home` 委托它；`bridge.daemon.boardwise_home` 也委托它，`BOARDWISE_HOME` 通过 PEP562 动态读；`autostart`/resources 消费 daemon/config。
- 当前空串返回 `Path.home()/'.boardwise'`；相对 `data/bw` 抛 ConfigError；末组件尾点/空格拒绝；`\\?\` 前缀例外。
- 真实 HOME/audit/config 不得读写；测试一律 monkeypatch.setenv 到 tmp_path，禁止旧式 `monkeypatch.setattr(...BOARDWISE_HOME...)`。开始 cp 备份 home.py 到 `.tmp_615/backup/`。他人 563/review-line/router/临时文件禁触。

## ③ 文件域与禁触清单

允许修改/新建仅：
- `src/boardwise/home.py`（`~` 展开与 docstring）
- `tests/test_615_home_tilde.py`（新）
- 本任务书、`.tmp_615/`、`.tmp_pt_615/`、`evidence/615/`

禁止：core.config、daemon/autostart/resources、CLI、connector/DSH、真实用户目录、fixtures 和他人文件。不得把普通相对路径合法化、缓存 env、修改 ConfigError 继承或创建目录，不新增另一个 HOME 读取器。既有测试不得删改宽。

## ④ 交付物与验收

1. 在绝对性检查前 `Path(override).expanduser()`：`~/bw` 返回 `Path.home()/"bw"` 且 absolute，字符串不再含未展开的 `~`；`~` 本身同理。展开失败（例如无法解析的 `~user`）转成 ConfigError 并给原名，不能落 CWD 或裸 RuntimeError。不要调用 mkdir/resolve 访问真实盘。
2. 空串/未设仍默认 `.boardwise`；`data/bw` 仍 ConfigError；合法绝对路径逐字返回；尾点/空格、`\\?\` 例外不变。每次调用读 env，运行中更换 BOARDWISE_HOME/HOME 生效。
3. 至少验证两个实际消费者：`core.config.boardwise_home()` 与 `bridge.daemon.boardwise_home()`（及动态 `daemon.BOARDWISE_HOME`）对同一 env 返回同一路径；`config_path()` 位于其下。不得真正实例化/启动 daemon。
4. 先对未改生产跑 `~/bw` 与两消费者用例必须红；空串/default、相对拒绝、绝对路径和尾点控制绿。

修后运行新测试、586/587/598 对应测试（先 Glob 核名）、config/autostart/resources、owner/layer；不全量。至少两项变异：① 删除 expanduser；② 把所有相对路径都自动绝对化（必须被相对拒绝测试打红）。每项 cp+SHA 恢复并复绿；测试 env 全用 setenv。

兼容矩阵：config 与 daemon 两个 shared 消费者，另 autostart/resources 邻域；离线/在线只覆盖路径解析，不启动桥。V3/V4、容器、多板/CBB 未覆盖。negative control 为空/default、相对拒绝、尾点、动态 HOME、真实用户目录零写入。

## ⑤ 纪律与红线

零 git 写/移动/删除；禁 rm/unlink 和 git checkout/restore；不全量、不真机、不部署、不启动 daemon。pytest 独立 basetemp、单进程、命令 timeout。不得读取/改写真实 config/token/audit，不能用 `monkeypatch.setattr` 固定 HOME 常量，不为旧报告恢复 CWD 相对路径。

## ⑥ 预算与交卷格式

一个 coder，最多 35 步或 25 分钟；不派下级。交卷 ≤1800字，含先红/修后汇总、两消费者路径、两项变异与 SHA 恢复、兼容矩阵和未覆盖项。证据落 `evidence/615/`。有真实 HOME 写入风险或未解决红项只能停止。
