# 电路语义投影（`boardwise.circuitSemantics/1`）

> 563B。状态：563A/B 聚焦验收完成（246 passed）；最终闭环修复、测试与本文档仍在工作树，未提交。
> 任务书：[`tasks/563_netlist_semantics.md`](../tasks/563_netlist_semantics.md)。
> 上游读取与实例身份：563A 的 [`src/boardwise/core/netlist.py`](../src/boardwise/core/netlist.py)。

这份文档只描述**已实现**的投影，不描述计划中的电路理解。它是一份
**拓扑事实的投影**：网表说了什么就记什么，能派生的只有
`two_pin` / `parallel` / `series` 三条，其余全部落进 `unknowns`。

## 1. 入口

```python
from boardwise.core.circuitsemantics import (
    SCHEMA, SCHEMA_HEADER, SemanticProgram,
    compile_semantics, verify_semantics, roundtrip_members,
)
```

| 名字 | 语义 |
|---|---|
| `compile_semantics(view: NetlistView) -> SemanticProgram` | 纯函数，无 I/O、无 bridge、无文件。同一 view 编译两次结果逐字节一致 |
| `SemanticProgram.as_dict()` | 整个程序的**深拷贝**；改它不影响已编译的程序 |
| `SemanticProgram.to_c()` | 确定性类 C 文本投影，首行 `// boardwise.circuitSemantics/1` |
| `verify_semantics(view, program)` | 重新编译并**整体**对拍；被改过的程序返回 `False`，不抛模糊异常 |
| `roundtrip_members(view, program)` | 只对拍原始逐脚/逐网事实（`parts`/`pins`/`nets`/`unconnected`） |

`program` 可以是 `SemanticProgram`，也可以是普通 dict（例如 `program.as_dict()`
被改过之后）。类型不对、结构不认、字段被删，一律 `False`。

## 2. 结构

```text
schema       "boardwise.circuitSemantics/1"
parts[]      {designator, source_id, pin_count}       —— 每个实例一条，同名实例不合并
pins[]       {designator, number, source_id, pin_key, name, net}
nets[]       {name, members:[{designator, number, source_id, pin_key}]}
unconnected[]{designator, number, source_id, pin_key} —— 空网引脚（NC），不是错误
relations    {two_pin[], parallel[], series[]}
unknowns[]   {kind: ambiguous_designator|unproven_net|cycle, ...}
```

`parts`/`pins`/`nets`/`unconnected` 是**回验底座**：不是给人看的摘要。

- 同名实例（重复位号、跨页同名）各占一条 `parts`，脚上带自己的
  `source_id`/`pin_key`；同一实例里同号不同 `pin_key` 的两脚仍是两脚。
- `net.members` 保留来源顺序与重复实例，也保留 `model.nets` 里**模型已无法解析**
  的成员（`source_id=""`、`pin_key=""`）——那是模型的事实，不编造、不删除。
  这类成员不进 `pins`（没有可寻址的脚），但 `nets` 照样列。
- `unconnected` 只列空网脚。**有名字的单脚网不是 NC**，它是意图，进 `nets`。
- 引脚 `name` 只写文档**拼出来的**名字；文档没拼就写 `""`，不借脚号充名。

## 3. 派生：只有三条

### `two_pin(part, pins=[...])`

唯一位号（不在 `ambiguous_designators()`）且**恰好两脚**的器件。每条记录两端脚的
`number`/`pin_key`/`name`/`net`。**不表示方向、不推断电阻/电容/二极管类型**；
一端空网也照样是两脚器件（空网留在记录里，由下面的派生拒绝它）。

### `parallel(parts, between)`

至少两个合格的 `two_pin`，其两个**非空、不同、且非 unproven** 的网组成同一个
无序对。一组一条。`between` 里的两个网只做规范化排序，**不是方向**。

### `series(parts, nets)`

合格 `two_pin` 通过「**只含两个不同器件引脚**、属于两个不同合格器件、且非 unproven」
的内部网串成**极大简单链**。链的端网不能是这种二度网；链里不重复器件、不重复网。

`nets` = `[起点端网, *内部网, 终点端网]`，所以 **`len(nets) == len(parts) + 1`**：
只看 `series` 就能读出整条链从哪里起、到哪里终。端网**可以是空字符串**（那一端悬空），
空端网原样保留，不为了过滤空网而丢掉端点。`nets` 顺序是拓扑顺序，不是电压/信号流；
正逆两向按器件身份取规范向（小的在前），规范化时 `parts` 与完整 `nets` **同步反转**。

三条拒绝规则，逐条都有反例测试：

1. **MID 上多一脚即不是链节**：三脚网不是二度网，R1–MID–R2 不成立。
2. **两器件两端同网（或两端都悬空）不是链**：那是并联/悬空对，`parallel` 或
   `unconnected` 已经说过；两元链若两端落在同一个网，成链就是重复叙述。
3. **链端落在 unproven 网上的链不发**：端点靠「同名焊接」而来就不是证过的端点。
4. **两端网相同即闭环，不是链**：`parts >= 3` 且两个端网是同一个非空网时，候选链
   两端落在同一网上——三者成环，第三个引脚只是让该网不再是二度网，不能把环变成串联；
   且链「不可重复网」，重复端网本身就不合法。此时不发 `series`，改记 `unknown` 的
   `cycle`：`parts` 沿候选链，`nets` = 内部网 + 闭合的那个端网，`len(nets)==len(parts)`
   且每个网不重复。两器件两端同网仍只由 `parallel` 说一次，不多记 cycle。

## 4. `unknowns`

| kind | 含义 | 作用 |
|---|---|---|
| `ambiguous_designator` | 该名字对不上唯一实例（重复位号 / 同名校页） | 该名字不进 `two_pin`/`parallel`/`series`，原始脚网全保留 |
| `unproven_net` | `model.unproven_nets` 声明的网（附带 pages） | 该网不做任何派生 |
| `cycle` | ≥3 个 `two_pin` 组成的纯环，或两端同网的候选闭环（`parts` 环绕顺序、`nets` 每器件一条，`len(nets)==len(parts)`） | 不硬选起点发 `series` |

两个器件两端同网的那种「2 元环」就是并联，由 `parallel` 说一次，不重复记成环。

## 5. `to_c()` 文本

```text
// boardwise.circuitSemantics/1
part("R1", "r1", pins=2);
pin("R1", "1", "r1", "1", "1", "A");
net("A", ["R1.1@r1#1", "R3.1@r3#1"]);
unconnected("R5.1@r5#1");
two_pin("R1@r1", ["1#1:A", "2#2:MID"]);
parallel(["R3@r3", "R4@r4"], ["A", "B"]);
series(["R1@r1", "R2@r2"], ["A", "MID", "B"]);
unknown("ambiguous_designator", "U15");
unknown("unproven_net", "VCC", ["page-a"]);
unknown("cycle", ["R1@r1", "R3@r3", "R2@r2"], ["N3", "N2", "N1"]);
```

`two_pin` 的脚 token 是 `脚号#pin_key:net`（`pin_key` 为空则省掉 `#`），所以同一
`source` 里同脚号不同 key 的两脚在文本里仍是两条（`1#1:A` 与 `1#2:B`）；`source` 在
part token 里。其余脚 token 是 `位号.脚号@source_id#pin_key`（空字段省略）。所有字符串字面量用
`json.dumps(..., ensure_ascii=True)` 转义：含引号、反斜杠、换行的网名不能伪造一行
新语句，非 ASCII 字符转成 `\uXXXX`，所以同一程序的字节在任何编码下都一样。

**本批不提供 C 解析器**：文本是给人/外部工具读的投影，不是第二套输入格式。

## 6. 明确不做

- 不从网名或形状推断 `decap` / `filter` / `driver` / `opamp` / `power_path` /
  地电源功能 / 信号方向 / 跨板同名相连。后续语义必须另立证据合同。
- 不做 CBB 内部展开、不做多板合流、不做 041 的 S3/S4。
- 不加 CLI / bridge 动作 / Connector / DSH 工具 / Rust 主流程；不改
  finding/severity/verdict、布局、网表成员或报告。
- 不改 563A 的读取与查询语义（`core/netlist.py` 本批零改动）。

## 7. 自检

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest \
  tests/test_563_circuit_semantics.py tests/test_563_netlist_view.py \
  tests/test_owner_rules.py tests/test_layer_rules.py \
  -q -n 4 --dist loadfile --basetemp=.tmp_pt_563b
```

覆盖：同名实例不合并、同号不同 `pin_key` 不丢、MID 三脚不产串联、只有一端相同不并联、
unproven 不派生、重复位号原样保留但不派生、单脚命名网 ≠ NC、纯环记 unknown、
删 unknown/relation/NC 即验证失败、`to_c` 字节一致且带关键关系。
每条 `series` 都断言 `len(nets) == len(parts) + 1` 且端网完整（含 `""` 端网），
链与并联并存时两条关系各自出现一次，`two_pin` 文本里同号不同 `pin_key` 两脚都在。
