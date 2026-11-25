# 565g — drawlint 的 L12/轨名四条洞（S2-H3/H4/H5/H6）

- 批号 **565g**　日期 2026-11-25　owner：绘制线/审查尺　状态：**待派**
- 来源：`outputs/hole565/TRIAGE.md` §1 的 565g 组；2026-11-25 主代理重放 `outputs/hole565/s2/probes/probe_s2.py all` 确认**四条全部仍复现**
- 文件域：`src/boardwise/engines/drawlint.py`、新建 `tests/test_565g_lint_holes.py`、`evidence/565g/`

## ① 前因后果

565 挖洞在 L12（网表语义闸）与轨名判据上审出四条同族缺口：**认不出脚名形态**（A/K、1.1/1.2）、**网名大小写两套身份**、**轨名词表缺 AGENTS 点名的 HVDC/SEC_12V**、**旗标旁 20u 内的真实冲突被整条丢弃**。前两条会同时造假结果与漏报，后两条是纯漏报。

2026-11-25 主代理重放原探针的原文（子代理开工必须自己复跑，不许直接引用）：

```
h3: [h3-named-A/K] findings: none            (应报 L12-two-pin-same-net)
    [h3-three-pin-cap-short] findings: none  (两脚同网 + 多余一脚)
    [h3-1.1/1.2] findings: none
    [h3-numeric-1/2] ERROR L12-two-pin-same-net   (会报)
h4: [h4-flag-gnd-vs-net-GND] ERROR L12-ground-flag-absent-from-netlist  (误报)
    [h4-two-pin-GND+gnd] findings: none                                   (漏报)
h5: _rail_kind('HVDC')=''  _rail_kind('SEC_12V')=''   (AGENTS 绘图红线点名的电源网)
h6: [h6-near-flag] findings: none      (旗标旁 +5V/GND 冲突消失)
    [h6-flag-far] ERROR L5-wire-rail-conflict  (旗标移远即重现)
```

## ② 当前树状态

- HEAD **`76e08060ded403793bc6fb0eb64b38f9e140c765`**，工作树混合未提交；`src/boardwise/engines/drawlint.py` 属已提交面（`git status` 无该文件改动），本批是它 2026-11-25 首改。
- 开工前必须：`cp src/boardwise/engines/drawlint.py .tmp_565g/backup/drawlint.py` 并记 SHA-256（主代理派工时给读数）。
- 相关位置（当前文件）：
  - `_RAIL_SUPPLY_RE` 1750-1752；`_rail_kind` 1765-1782
  - `_is_flag_own_name` 1785-1802（**只看距离 `hypot <= L5_FLAG_OWN_NAME_GAP`，从不比对文字**）
  - `check_rail_without_flag` 1903-1949（已 `upper()` 归一）
  - `check_netlist_electrical` 1972 起：两脚门 1993-1995（`len(pins)==2 and all(_numeric_pin_name(...))` + `nets = {pin.net ...}` 大小写敏感）、`by_net` 2008-2011（大小写敏感）、`netlist_nets` 2031-2036（`net in netlist_nets` 大小写敏感）
- 聚焦基线（派工时由主代理实测填入）：`tests/test_565g_lint_holes.py`（新建）先红；相邻既有 L12 用例见 `tests/` 里 `drawlint`/`lint` 相关文件，子代理用 `--basetemp=.tmp_pt_565g` 跑点名的几个文件，**不跑全量**。

## ③ 文件域与禁触清单

**唯一允许修改/新建：**

| 路径 | 允许 |
|---|---|
| `src/boardwise/engines/drawlint.py` | 改（只改 L12 判据与轨名判据区） |
| `tests/test_565g_lint_holes.py` | 新建 |
| `evidence/565g/REPORT.md` | 新建 |
| `.tmp_565g/**` | 自己的临时目录 |

**禁触：** `core/circuitsemantics.py`、`core/netlist.py`（565b 在途）、`cli.py`、`engines/svgpreview.py`、`core/presentationspec.py`、`commands/draw.py`、`tests/fixtures/`、任何既有测试文件的断言（若既有 L12 断言因本批合法变红，停下报告，不许放宽）。

## ④ 交付物与验收（先红后绿，逐洞）

新建 `tests/test_565g_lint_holes.py`，先从探针形状造 Sheet/Netlist 夹具（可直接抄 `outputs/hole565/s2/probes/probe_s2.py` 的 builder），**先全部红**（失败原文存 `evidence/565g/RED.txt`），再改判据。父级裁决的期望行为：

| 洞 | 父级裁决 | 先红断言 |
|---|---|---|
| **S2-H3** | ① `len(pins) == 2` 且两脚同一非空网 → ERROR，**不再要求脚名是数字**（A/K、`1.1/1.2` 都报）；② ≥3 脚但**全部脚名是数字**（钝件/无源件的形态）且任意两脚同非空网 → ERROR（“两脚电容多一脚”）；③ 命名脚（VDD/GND/PB0…）的多脚器件**不进**两脚门，`L12-ground-supply-pin-short` 维持原判据（否则每个多电源脚 IC 都会误报） | A/K 同网、3 脚钝件同网、`1.1/1.2` 同网三条当前 findings 为空 |
| **S2-H4** | 网身份在 L12 内统一 `strip().upper()` 归一：`nets` 集合、`by_net` 分组、`netlist_nets` 成员判定三处；**报错文案保留原始拼写**。页面 flag 侧已有归一，L12 必须与之同口径 | `gnd` 旗 + `GND` 网表当前误报；`GND`+`gnd` 两脚同件当前漏报 |
| **S2-H5** | 轨名词表补 `HVDC` 与 `SEC_\d+V\d*`（AGENTS 绘图红线点名的电源网），`_rail_kind('HVDC')=='Power'`、`('SEC_12V')=='Power'`；`L11-rail-without-flag` 对它们照 GND/+3V3 判 | 两条 `_rail_kind` 当前为 `''`；HVDC 无旗当前无 finding |
| **S2-H6** | 豁免**只**给「距离 ≤ `L5_FLAG_OWN_NAME_GAP` **且** 文字 strip+upper 等于该 flag 的 net」的盒；文字不同的真实冲突（+5V 在 GND 旗旁）必须报 `L5-wire-rail-conflict`。距离只作次级界，不再单独成立 | `h6-near-flag` 当前 findings 为空；`h6-flag-far` 已报是反证，修后必须仍报 |

**验收读数：**

```
.venv\Scripts\python.exe -m pytest tests/test_565g_lint_holes.py -q --basetemp=.tmp_pt_565g
.venv\Scripts\python.exe -m pytest tests/test_565g_lint_holes.py <相邻既有 lint 测试文件> -q --basetemp=.tmp_pt_565g
.venv\Scripts\python.exe outputs\hole565\s2\probes\probe_s2.py all
```

- 先红 ≥4 failed；后绿全 passed；`probe_s2.py` 重放要逐条对照 ① 的原文（h3 三个反例转阳性、h4 误报消失且漏报转阳性、h5 两条 kind 为 Power、h6 近旗转阳性且远旗仍阳性）。
- **逐洞变异**：把每条因果行失效（H3 恢复 `all(_numeric_pin_name…)`；H4 把某处归一改回原样；H5 去掉 HVDC 分支；H6 去掉文字相等条件），点 named 用例先红，再用 `.tmp_565g/sub-backup/` 的 `cp` 备份 + SHA-256 还原复绿。四次读数写进报告。禁用 git 恢复。

## ⑤ 纪律与红线

1. 零 git 写（只读 status/diff 可以）；零删除（禁 `rm`/`Remove-Item`，临时文件留 `.tmp_565g/`）。
2. 不跑全量 pytest、不 `-n auto`、不碰 bridge/EDA、不联网。
3. 不改 `core/netlist.py`/`core/circuitsemantics.py`（565b 在途）；不新建第二套轨名/脚名子系统；扩词表只加点名两项，不顺手扩其它名字。
4. 不得用放宽既有断言、skip/xfail、改夹具的方式凑绿；不得把「不可复现」写成「已修」。
5. 交卷时有红项或无读数，写「停止/未验收」。

## ⑥ 预算与交卷格式

- 上限 **40 步 / 30 分钟**，先到先停。
- `evidence/565g/REPORT.md`：开工哈希、先红原文、逐洞修复点（文件:行）、四次变异读数、后绿原文、`probe_s2.py` 前后对照、未做项。
- 最终回复 ≤2000 字：结论 + 关键读数 + 证据路径 + 需要主代理裁决的事。
