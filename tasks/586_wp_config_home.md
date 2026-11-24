# 任务书：586 / W-P(config) — 配置路径与写入诚实性

## ① 前因后果

hole568 总表的 569-F-1/2/4/6 已复现：`BOARDWISE_HOME` 不可用（父路径是文件、config.json 是目录、尾部空格、长路径等）时 `config set` 裸 traceback，且可能留下固定 `.tmp`；`config.json` 是目录时 `config get/show` 却 exit 0 印默认值；相对 HOME 随 `chdir` 改变而静默换家；Windows 尾随点被系统吞成另一个 HOME 的别名。原始证据在 `outputs/hole569/f/REPRO.md`。F-3（daemon 读取时点）和 F-5（parts 缓存）是不同文件域，另批处理；F-7 并发仍是 suspect，不在本批声称修复。

本批只修 `core/config.py` 及 CLI config 命令必要错误映射：非法/不可读配置必须具名拒绝，不能静默回默认或裸栈。相对 HOME 选择“具名拒绝”而非新增进程缓存，保证同一调用语义清楚。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 566–585 与他人改动。开工 hash：
- `src/boardwise/core/config.py` `75c5af262cdc1ddc992235ec0f9a6c93024020b8932c6b83c5c78c65a491a55c`
- `src/boardwise/cli.py` `d194d2b874a482161b006246b06847500d6f8e82ff610ff7be0eefebd468f98e`（含 581/584，必须保留）
`bridge/daemon.py`、`bridge/autostart.py`、`core/parts.py` 由别批负责，本批不碰。当前 `_cmd_config_get/set/show` 已捕获 `ConfigError`，但 `set_setting` 的 OSError 会逃逸；`boardwise_home()` 直接 `Path(override)`；`read_config()` 用 `not path.is_file(): return {}`。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/core/config.py`
- `src/boardwise/cli.py`（仅 config get/set/show 必要 OSError/ConfigError 映射，若核心包装足够则不改）
- `tests/test_586_config_home.py`（新建）
- `evidence/586/`、`.tmp_586/`、`.tmp_pt_586/`

禁止修改 daemon/autostart/parts、其他生产/测试、fixtures、前批证据和他人未提交 hunk；不 git 写、不删除、不跑全量、不接触 bridge/daemon/EDA。开工 cp 备份目标文件并记录 SHA-256；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. F-1：`set_setting` 的 mkdir/write/replace 等 OSError 必须包装为 ConfigError（含路径与原因），CLI `config set` exit 2、stderr 无 Traceback；目标为目录等失败不得留下本批新建的半成品临时文件。可沿现有原子写惯例改善临时文件生命周期，但不宣称解决 F-7 并发。
2. F-2：`config.json` 存在但不是普通文件（尤其目录）时 `read_config` 抛 ConfigError；不存在仍返回 `{}`。get/show 因此 exit 2，不印默认 on/off；坏 JSON 的既有话术保持。
3. F-4：相对 BOARDWISE_HOME 具名 ConfigError，不能随 cwd 漂移；绝对路径（含非 ASCII、空格、UNC/`\\?\` 形态）按原可用路径接受。不要引入 import-time 新缓存；`Path.home()` 默认行为不变。
4. F-6：HOME 末尾的 `.` 或空白在边界处具名拒绝，避免 Windows 别名与尾部空间崩溃；正常目录名内部点号/空格不受影响。对非法 HOME，get/set/show 都应是 exit 2 无栈。
5. 测试先在基线上先红，再运行：
   `.venv/Scripts/python.exe -m pytest tests/test_586_config_home.py tests/test_resources.py tests/test_039c_review_flow.py tests/test_doctor.py -q --basetemp=.tmp_pt_586`
   另按影响跑 `tests/test_537c_environment.py` 与必要的 config 现有测试；记录完整汇总和实际平台限制。
6. 至少两个因果变异（如恢复 `not is_file(): return {}`、去掉相对/尾部校验、去掉 OSError 包装）先红，cp+SHA 恢复；保存 CLI 原始读数、失败现场清单和差异到 `evidence/586/`。

兼容矩阵：配置 CLI 与 `core.resources` 等实际读者做正例；不存在配置、正常绝对 HOME、合法嵌套设置不变；V3/V4、容器、多板/CBB、daemon 真机未覆盖。negative control：缺失配置仍可默认，非法存在配置不得默认；相对 HOME 不得因 chdir 变成另一目录。

## ⑤ 纪律与红线

只改配置链，不改 daemon/parts/绘制算法，不把相对 HOME 静默解析成新约定，不删改宽断言，不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。禁止用 git restore/checkout 恢复混合工作树。

## ⑥ 预算与交卷格式

最多 35 步或 25 分钟。交卷 ≤1800 字，逐项报告 F-1/2/4/6、基线先红、修后命令完整汇总、两个变异及恢复 hash、合法路径兼容和未覆盖项；详细日志落 `evidence/586/`。有本批未解决红项不得写完成。
