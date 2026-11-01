# 534B — CH343 V4 六岛布局（worktree 实验）

日期：2026-11-01 · 分支 `534b-layout` · worktree `E:/boardwise-wt-layout`
授权：岳「拉个 worktree 去改，token 预算无限大胆试错」

## 目标

把 CH343 从“五岛/电源岛沉底”改成：
CC 并入 USB、去耦按服务脚拆成卫星岛贴 U2、LED 独立、H1 独立；
标签优先直跑，地/电源旗标按簇就近；不再靠人工坐标硬凑。

## 结果（V4 Board2 P2 `dc46ef64fc7385ec`）

- 6 岛：`usb_c` / `v3_cap` / `ch343` / `vcc_cap` / `hdr` / `led`
- 11 器件、54 段计划线、43 个宿主 wire、16 旗标
- `draw apply` exit 0；`outOfScope.items=0`；`{saved:true}`，`saved_unverified`
- `draw lint` **0 ERROR / 1 WARN**（D+ 可逆脚同线双标签）
- 独立逐脚：**17 网 / 58 脚 / 55 连通 / 3 NC PASS**
- H2 `Name` 改为 `2x5P`，不再显示长 MPN

证据：`evidence/534b/report.md`、`render_final.png`、`apply.json`、`plan.json`、
`lint.json`、`netlist.json`、`connectivity.json`、`SHA256SUMS`。

## 编译器变更

1. `PresentationSpec.moduleOrder`：显式页面摆放顺序（必须是 modules 的排列），
   不冒充信号 flow；未写时不改变旧页。
2. `PresentationSpec.moduleColumns`：固定网格列数；未写时仍 1..N 自动搜索。
3. `pagecompiler._placement_orders` / `_variants` 读取这两个字段。
4. `ch343_uart_v4.library.json`：C0603/C0805/R0603/LED 增加 90/180/270 pose；
   声明 pose，不是逐角度实测文字行，只按本页 apply/lint 结果使用。
5. 保留 534A 的 lint end-anchor 修复与 `labelPolicy.stub` 能力。

## 未关闭

- C7/C8 是卫星岛 frame 相邻（间距约 80 单位），不是同一岛内部贴脚；
  还没到 Board2 P1 的“电容贴 U2 左右”程度。
- 页面仍有大片空区，H2/LED 偏下；布局紧凑度不是最优。
- S-21 标签名称行仍有贴 2 单位下限的软项。
- native netlabel 仍不可用；`saved_unverified`；未做 checkup/PCB。
- 未提交、未合并；worktree 内实验交付。

## 测试

- schema/compiler/page 聚焦：**220 passed / 3 skipped**
- 全量 Python（主树、worktree 代码）：**8829 passed / 25 skipped / 2 failed**
  - 两条均为既有环境红：`pytest-slots` ACL、MSYS `0xC0000022`
  - 没有本批回归
