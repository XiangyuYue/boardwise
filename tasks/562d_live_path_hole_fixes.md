# 562D：多跳图对抗审查三处小修（全量结束后执行）

## 1. 前因与边界

只读对抗审查发现两处确定性判错和一处写文件异常逃逸，详见 `evidence/562c/adversarial-review.md`。必须等当前全量 Python 结束后再改源码，避免磁盘变异与全量交叉。

本批只修：

1. `core/livepath.py`：`Pad` 端点 pad-direct 尚未收齐就检查相邻端点配对，产生伪 non-reciprocal；改为两遍扫描。
2. `core/livepath.py`：`adjacent.calls == cap` 且 frontier 完整时不应当作截断；计数仅在 `calls > cap` 时额外判截断，真正 budget/frontier 缺口不变。
3. `pcb_path.py`：JSON 写入同时捕获 `OSError` 与 `ValueError`，孤立代理字符写失败也具名退 3、披露残留、不打印 verdict。

跨层邻接不在本批改规则，归 562C 真机语义探针。

## 2. 文件域与禁触

仅 `src/boardwise/core/livepath.py`、`src/boardwise/pcb_path.py`、`tests/test_562_live_path.py`、`tests/test_562_live_path_cli.py`、`.tmp_562d/`、`evidence/562d/`、`tasks/562d_live_path_hole_fixes.md`。不得改 connector、559/550、绘制线、协议、DSH、真实工程。先 cp 备份并记 SHA，零 Git 写、零删除、零全量 pytest（聚焦后再由主代理决定最终复跑）。

## 3. 必加负例

- `type="Pad"` 的 reciprocal Line↔endpoint + pad-direct：CONNECTED，不能有伪 non-reciprocal，partial=false；ComponentPad 旧例不变。
- `calls=512/cap=512/frontier=[]` 且其他干净：NOT_PROVEN；`calls>cap` 或真正 budget/frontier 缺口仍 INDETERMINATE。
- `write_json_atomically` 收到孤立代理字符：返回 leftover+错误而非抛出；CLI 写失败退 3、stdout 空、披露残留、不打印 verdict、不 unlink。

## 4. 验收

运行：

```bash
.venv/Scripts/python.exe -m pytest tests/test_562_live_path.py tests/test_562_live_path_cli.py -q --basetemp=.tmp_pt_562d
```

主代理至少两项变异：恢复单遍配对检查、恢复 `>= cap`，必须先红后 cp+SHA 恢复。子代理 ≤25 步/20 分钟，交卷 ≤1200 字，真实读数和未覆盖项。跨层语义没有真机证据前不得新增 cross-layer 生产规则。


## 5. 实际完成与父代理验收

- `_build_hops` 已改两遍扫描，Pad 与 ComponentPad 完整互证均不再产生伪 `non-reciprocal-adjacency`；调用计数仅在 `calls > cap` 时额外判截断；JSON 写入捕获 `OSError + ValueError`。
- 主代理独立 **85 passed**；恢复单遍实现 → **1 failed / 2 passed / 46 deselected**，恢复 `>= cap` → **1 failed / 1 passed / 47 deselected**，均 cp+SHA 恢复并复跑 **85 passed**。证据 `evidence/562d/562d-hole-fixes.md`、`evidence/562d/parent-validation.md`。
- 全量前另补第三个命令模块的 161 owner 计数；跨层语义仍未改生产规则，归 562C 真机探针。状态：工作树完成、未提交未推送、未做真机/DSH。
