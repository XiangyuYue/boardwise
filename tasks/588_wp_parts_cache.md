# 任务书：588 / W-P(parts) — 保存失败不得污染内存货架

## ① 前因后果

hole568 的 569-F-5 已复现：`core.parts._PARTS_MEMO` 按内容摘要缓存并直接交出共享可变 `PartLibrary`；`parts add` 在该对象上 append 后调用非原子 `save_parts`，保存失败后同进程下一读仍看到磁盘没有的条目（disk=1 / memory=2）。原始探针为 `outputs/hole569/f/probes/f6_parts_failed_save.py`。F-7 的真实并发交错仍是 suspect，本批不声称解决并发锁。

本批只修 parts 的写者/缓存一致性。必须保留 perf-02A 的内容摘要 memo 和“多次读取只解析一次”的性能合同；不能靠禁用缓存或全量重读掩盖。可以更新 `tests/test_perf02a_memoization.py` 中“每个读者必须拿到同一个可变对象”的过时断言，但要保留并证明解析次数不增加。

## ② 当前树状态

HEAD `f5083286de06b1d1b698a91e51da18463be4f4de`，混合工作树含 566–587 与他人改动。`src/boardwise/core/parts.py` 开工 SHA-256 `9b7d66ec03dc9e3f8b6883bd9e49f0e2d7575026059a0a6a024c3caf2a45a25d`。`cli.py` 当前 `d194d2b874a482161b006246b06847500d6f8e82ff610ff7be0eefebd468f98e`，其中 parts add 在约 18655 行执行 `write_library.parts.append(...)` 后 `save_parts`。`core/parts.py:1781–1827` 是 memo 与 writer。现有 `tests/test_perf02a_memoization.py:99–109` 钉同一对象 identity，需以新隔离合同替换而保留 parse_counter。

## ③ 文件域与禁触清单

允许修改/新建：
- `src/boardwise/core/parts.py`（memo 返回值隔离/不可变快照与原子保存，按最小方案）
- `src/boardwise/cli.py`（仅 parts 写者入口如确需 copy-on-write；保留前批所有 hunk）
- `tests/test_588_parts_cache.py`（新建）
- `tests/test_perf02a_memoization.py`（仅更新共享可变对象的旧合同，保留性能断言）
- `evidence/588/`、`.tmp_588/`、`.tmp_pt_588/`

禁止修改 config/daemon/changeplan、其他生产/测试、fixtures、前批证据和他人未提交改动；不 git 写、不删除、不跑全量、不接触 bridge/EDA。开工 cp 备份目标文件并记录 SHA-256；变异只能 cp+SHA 恢复。

## ④ 交付物与验收

1. 复现并修复“load → append → save 失败 → 下一读”：磁盘仍只有原条目时，下一次 `load_parts` 不得出现幽灵条目，缓存不得被写者的原地修改污染。写者必须 copy-on-write 或 memo 返回隔离/不可变快照；成功后新摘要仍触发重读。
2. 保留 `parse_counter` 证明同一路径同一内容重复读只解析一次；读者得到的数据相等，但不能通过共享可变对象互相污染。若返回深拷贝，记录其性能合同影响并避免无意义重复解析。
3. `save_parts` 采用仓内既有原子写惯例，写失败保留旧文件、清理自己创建的临时文件并抛具名 PartError/OSError（按现有调用方可处理类型）；成功写出的 JSON 字节/排序与旧实现一致。不要宣称解决 F-7 并发锁。
4. 新测试先在基线先红，再运行：
   `.venv/Scripts/python.exe -m pytest tests/test_588_parts_cache.py tests/test_perf02a_memoization.py tests/test_039_parts_toolchain.py tests/test_039c_review_flow.py tests/test_191b_shelf_merge.py tests/test_527_parts_classify.py -q --basetemp=.tmp_pt_588`
   另跑 `tests/test_owner_rules.py` 和 `tests/test_038x_shelf_resolution.py`，记录完整汇总。
5. 至少两个因果变异（恢复共享可变写入/恢复非原子保存）先红，cp+SHA 恢复；保存失败前后磁盘/内存读数、parse_counter、成功路径 diff 到 `evidence/588/`。

shared 兼容矩阵：review 规则读者与 parts add 写者两个消费者均覆盖；同一文件重写、用户/内置架合并、缺失 shelf、成功 add 不变；V3/V4、容器、多板/CBB、真机未覆盖。negative control：保存失败不得增加条目，保存成功必须增加且可读；memo 不得让旧字节覆盖新字节。

## ⑤ 纪律与红线

只在 parts 缓存/写者链修，不改器件分类、事实闸、review verdict、配置或绘制算法，不删除缓存，不删改宽断言，不 skip/xfail。探针单进程、命令带超时；不跑全量、不真机、不部署、不发布。禁止用 git restore/checkout 恢复混合工作树。

## ⑥ 预算与交卷格式

最多 40 步或 30 分钟。交卷 ≤1800 字，报告 F-5、基线先红、修后命令完整汇总、两个变异与恢复 hash、parse/兼容/未覆盖项；详细日志落 `evidence/588/`。有本批未解决红项不得写完成。
