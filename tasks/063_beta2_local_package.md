# 0.6.3 beta 2 本地打包与当前工作树提交

用户2026-11-18明确授权：“打包一个0.6.3（beta 2）给我”；随后授权“当前的修复和未提交内容也提交了吧”。本任务包括本地三件套构建、必要集成元数据修复、验收与一次Git提交；不包含push/GitHub Release或用户环境安装。

## 输入与版本

- 起点main `75347ab53068a5efe3c1cbce454474dff113e6d9`，混合未提交源代码/测试/文档按用户要求合入，临时日志/工程容器/ignored证据不入库。
- CLI/Python项目/根npm与DSH外部版本统一`0.6.3-beta.2`（合法PEP440，规范metadata为`0.6.3b2`）；connector维持0.6.2，同0.6系列兼容。
- 本地包包含本次A/B/C修复及现有待提交源码；P48为已完成参考，不重画药箱、不重启P145、不做eprj2开发。

## 独立文件域

1. 元数据子批：版本声明与lock根元数据、owner清单及精确扫描计数、官方生成CLI快照、DSH安装示例版本。不得修改业务判定或削弱断言；备份+SHA，先聚焦基线/负控。
2. 构建子批：新建`.tmp_release_063b2*/`和`outputs/releases/0.6.3-beta.2/`，复用现有esbuild/PyInstaller spec/npm pack，避开现有构建脚本直删。所有既存产物保留，不进行移动/删除。
3. 根审阅当前diff与待提交文件；生产、文档、版本集成完毕后显式路径暂存，执行仓库保密闸和commit-msg闸，一次提交；不add临时lock/debug日志/容器。

## 集成验收与影响面

无新算法/shared公开模型/schema变更。已知派生钉：CLI命令树/错误码合同、owner/layer和模块精确计数、版本/DSH lib同步、桥目录/connector动作能力、replay/move-block合同、V4 facts/adapter及普通carrier原闸。先补齐已知元数据，再启动全量，禁止靠全量侦察已知漂移。

- 全量pytest：`C:/Python314/python.exe -m pytest tests/ -q -n 4 --dist loadfile --basetemp=.tmp_pt_063b2_r5 --durations=50 --durations-min=1.0 --junitxml=.tmp_perf_pytest/junit-063b2-r5.xml`。采用已验证basePython+仓库site-packages，UTF-8及Git usr/bin完整PATH。用户2026-11-19明确指出近期全量近40分钟，无需卡30分钟，故硬超时改90分钟；临时外部插件实时落失败详情，不改测试断言。先后有CLI崩溃主动中断、30分钟超时、35分钟完整8红；修复本批因果后聚焦65 passed。第四次临时目录含`verified`触发bridge全输出关键字断言假红，212.8秒主动停止；第五次使用中性批号r5，根已说明复跑原因。其他红披露归属，不重复陪跑。
- 随后串行connector tests/typecheck、DSH typecheck/tests/build、根tsc及Rust fmt/clippy/test；构建可能直删的脚本采用保持相同配置的无删除适配，不改变产品源码或测试断言。
- 使用当前三件套构建最终exe/eext/tgz，跑打包后版本/doctor/保存候选plan、隔离端口daemon状态与停止、安装skill输出到隔离目录验证；不安装全局/修改用户DSH。
- 真实EDA仅允许既有已授权`test V4/P48`只读冒烟：先status+doc.list身份逐字核对，目标缺失则不自行替换；不改任何工程。无需本任务重新绘制P48。旧daemon/connector仅能证明现有页只读结果，不能冒充新三件套激活验收。
- 原发布件保密扫描覆盖exe压缩流及三件套；校验包内版本/文件、写SHA256。构建成功与普通用户端到端稳定绘图分开披露，不能把beta包标为已完成P48效果普适化。

## 交付与停止线

交本地zip与三件套、版本/源文件指纹、真实验收日志及限制，更新PROGRESS/handoff。子批分别≤40步/25分钟，长进程受控并定期汇报；无证据失败两轮停扩项。不会以beta名义豁免红项或伪称发布绿。用户已授权本地包与提交，未授权push、公开发布、全局安装、真机写入或清理。

## 最终验收（2026-11-19）

- 中性r5全量 **11756 passed,22 skipped,2 xfailed in2086.45s(34:46)**，exit0；connector846 passed，DSH193 passed/1 skipped，typecheck/build与Rust fmt/clippy/test通过（177 passed/4 ignored）。完整日志、JUnit与每次失败/中断原始证据见`evidence/release-063-beta2/`。
- 本批新红全部修复：owner三处精确计数157；普通carrier按既有root成员数>1收窄，四项旧回归恢复且跨岛接线保留；完整PATH解决hooks测试缺chmod。父独立聚焦65 passed，退root资格4failed3passed、禁carrier2failed3passed、owner退154三红，copy+SHA恢复，旧断言/指纹无放宽。
- 最终exe位于`outputs/releases/0.6.3-beta.2/verified/`，版本0.6.3-beta.2、隔离端口54383自动daemon/doctor及双端skill同步通过；无connector预期exit1如实保留。打包DSH调用最终exe保存候选计划ok=true；所有发布件与解包正文保密检查通过。
- 用户最后明确“提交后不要推送，我让本地DSH跑一遍看看效果”。只做本地提交，不push/tag/公开发版；最终commit写入包manifest与证据。实际DSH端到端/新三件套现场激活待用户试跑，原P48不重画。
