# 548P 侦察任务书（只侦察，不改代码）

> 工作区 `E:\boardwise-wt-548o`（分支 `drawing-548o`，HEAD `f23b801`，`drawcompiler.py` =
> `05139E85…5EA3E`，即 548K/L/M/N2 之后的状态）。
> **本任务不写一行业务代码**：产出是一份"接缝报告"，主代理据此派实现单。

## 为什么要侦察

548N2 → 548O 连续两轮都没修好同一张页：第一次卡在 `J2.GND has no clear upright hang`，
第二次把这一句消掉，拒因搬到 `segments[13] 'ESP_RXD' lands on parts[J2]`；把页框翻倍也落在
同一处。三条独立路径指向同一个事实：这一岛在 1170×825 的页上只占 **370 × 45**
（31.6% 宽 × 5.5% 高，`whitespace_ratio=0.991`），六件本体全挤在宿主本体那一行里。

前两轮我的毛病是**猜层**：以为缺"预留"，其实缺"行"。这次先钉准再动手。

## 必须回答的六个问题（每条都要给文件名 + 行号 + 原文）

1. **谁决定行/带**：`_joint_seat_group`（≈28854）里兄弟支路落在哪一行、哪一列，是哪个函数/
   哪个循环算出来的？把决策点原文贴出来。
2. **为什么现在只能一行**：阻挡"宿主上方/下方再来一行"的**具体判断**是哪几个（越具体越好：
   某个 `taken` 列表、某个 `for` 的上界、某个只沿一条轴展开的候选生成器）。
3. **548C6 的二维座位轮到底做什么**（`tests/test_548c6_two_dimensional_seats.py` +
   其对应实现）：它的"一行一个兄弟支路"是怎么排的？行只往一侧长，还是两侧都能长？
   能不能承载这一岛？
4. **548L 的门控**：≈24913 是 `_stub_lane_reserved(...) and not _service_layout_page(...)`。
   若把 `not _service_layout_page(...)` 去掉，**两组件页**（`evidence/548M/presentation.rail.json`）
   的几何会不会变（`317E7FD773E76A66`）？请实测并给读数；再单独测"只把门控换成
   '这条网是不是双脚正交 wire'、不看 548K 开关"的后果。
5. **三种最小改动**：给出三条互斥方案，每条写清（a）改哪几处、（b）预测 P4 读数
   （零件原点 y 跨度）、（c）预测对 93 个邻域测试的影响、（d）最可能的新拒因是什么。
   至少一条方案必须"只让既有二维座位轮在宿主两侧选行"，不新增规划器。
6. **别处有没有已经能用的东西**：`_service_group_side_tokens*`、`_reserve_open_ports`、
   `_shift_flags`(548O 已撤回，补丁在 `.tmp_548o_over/548o-wrong-layer.patch` 可读) 里
   有没有现成机制可以直接复用？

## 允许做的事

- 只读代码、只读测试、只跑**单个**编译/探针（`C:\Python314\python.exe` + `PYTHONPATH`
  见下），产物落 `E:\boardwise\.tmp_548o_over\recon\`。
- 允许改**你自己的临时副本**（`E:\boardwise\.tmp_548o_over\recon\drawcompiler_probe.py`），
  用它在内存里试"去掉某个判断会怎样"；**不许改** `E:\boardwise-wt-548o\src` 与主仓任何文件。

```powershell
cd E:\boardwise-wt-548o
$env:PYTHONPATH = "E:\boardwise-wt-548o\src;E:\boardwise\.venv\Lib\site-packages"
$env:TEMP = "E:\boardwise\.tmp_548o_pt"; $env:TMP = $env:TEMP
$py = "C:\Python314\python.exe"
& $py -X utf8 -c "from boardwise.cli import main; main()" draw compile `
  --circuit evidence/548J/wifi-canvas/calibrated-wifi-island.circuit.json `
  --presentation evidence/548M/presentation.rail.json `
  --profiles evidence/548J/wifi-canvas/calibrated.library.json `
  --page-box 0,0,1170,825 --out E:\boardwise\.tmp_548o_over\recon\out `
  --json E:\boardwise\.tmp_548o_over\recon\out.json
```

> 注意：`E:\boardwise\.venv\Scripts\python.exe` **不能写** `E:\boardwise-wt-*`（会
> `PermissionError`/`WinError 5`），所以用上面的系统解释器写法。

## 禁区

- 不 git 任何写操作；不删任何文件；不跑全量 pytest；不碰真机/bridge/daemon；
- 不改 `E:\boardwise\**`（岳的混合未提交现场）；
- 不改 8 个 548 继承测试、不改 `presentationspec.py`、不加契约字段；
- 不扩页框、不调 `GAP`/`near`/`max_nodes`/间距梯子来"让它过"。

## 交付格式（≤2000 字，超出落文件）

```text
1. 谁决定行/带：<函数>（<行号>）… 原文摘录
2. 为什么只能一行：①②③ 具体判断 + 行号
3. 548C6 二维轮：现在怎么排、能不能承载、缺什么
4. 548L 门控实测：两组件几何 <sha>（去排除前 / 后）；只换门控的后果
5. 三种最小改动：方案 A/B/C，各含 (a)(b)(c)(d)
6. 可复用机制：…
7. 你建议选哪条，为什么（一句话）
```

## 预算

25 分钟 / 25 步，先到先停。交不回完整报告就交回"已钉准的部分 + 卡在哪"。
