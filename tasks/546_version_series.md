# 546：daemon / connector 同系列版本兼容

## 用户裁定

daemon 与 connector 以后只要求 **major.minor 系列同步**，补丁号分开。daemon 升到 0.6.2 时，
没有改动的 connector 不需要跟着升号；daemon 升到 0.7.0 时，connector 即使无改动也必须升 0.7.0。
DSH 插件与 boardwise 外部版本的同号策略不因本条改变。

## 公开合同

- 严格 `x.y.z` 数字版本：精确相等为 `match`，同 major.minor 为 `compatible`，跨系列或不可解析为
  `mismatch`；任一侧缺失仍为 `unknown`；离线仍为 `not-applicable`。
- 同系列双向兼容，不做方向白名单，不把 0.6.0↔0.6.2 或反向误判为失效。
- 兼容的依据是 protocol 主版本未变和加性动作，不表示动作全集相同。较新的动作仍需能力探测；
  旧补丁没有该动作时明确 `UNKNOWN_ACTION`，不得伪装支持。
- `environment.limitations` 的 `connector-version-compatible` 只影响 `attributeMoves`，
  不降级常规 live 审查证据。0.6.0 connector 可与 0.6.1 daemon 做既有动作；
  `sch.list_attributes` / `sch.move_attribute` 需要支持它们的 connector。
- doctor 与报告共用 `connector_versions_compatible`，不得出现两套判据。
- 版本发布纪律同步到 `docs/testing-doctrine.md`、`docs/roadmap.md`、`tasks/SCHEDULE.md`、
  `docs/bridge.md` 与 README；CLI doctor help 与 `contracts/cli/v1.json` 同步。

## 实测与变异

- 最终聚焦（含合同、DSH 同步、doctor、environment、guided doctor 与 review-read）：
  **457 passed / 3 skipped**；桥协议邻域 **153 passed**。
- 过程读数：doctor + environment + evidence/finalize **243 passed**；补充 **118 passed / 3 skipped**。
- 同系列多组合正反向均 compatible；跨系列、缺段、前后缀与非数字均 mismatch。
- 将系列比较变异为恒 False 后有 **15 failed / 91 passed**，随后以 `cp` 恢复并核对
  SHA-256 / `cmp` 一致，聚焦复跑恢复 243 passed。

## 边界

- 本批验证代码与报告合同，不把“同系列”解释成所有新动作均可用。
- 真实编辑器内 0.6.1 daemon + 0.6.0 connector 的混跑仍需用户测试确认；未以离线测试冒充真机通过。
- 0.7.0 及后续系列的强制同步规则只在本批文档中登记，届时不得擅自给无改动 connector 跳号。
