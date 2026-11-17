# 548P14：原共享轨道入口的有限回退

P13 用同一 Router 与同一真实墙集反证固定内端不可达并不等于共同轨不可达。
本批只在 `src/boardwise/engines/drawcompiler.py::_joint_route_group` 保留原内端优先、失败后试另一既有端点，
不添加中间目标、不扩大页框/路由阈值/预算、不跳过宿主供电脚。测试为 `tests/test_548p14_rail_entry.py`。
其他混合未提交文件、review/shared/bridge/CLI/Connector/DSH/Rust/fixtures 均不触碰，无 git 写或删除。

原源码先红3/1，新实现4 passed；邻域20 passed。父独立变异M1三红、M2一红并cp+SHA恢复，
恢复P14/owner/layer 28 passed。源码SHA `3e2f6d5045d2ee2aae25a924f04cb54014e0fa368687b6cc0232b7f56c049027`。
因果证据 `evidence/548P14/README.md`，父验收 `evidence/548P14/parent/acceptance.md`。

合成图 hard0、13脚连通，父视觉仍拒绝多余供电绕行；不称真实模块/整页完成。
下一步 P17 只读量未来组旧墙与最终几何，P15 已静态定位 native 标签收尾遗漏，待另批。
实现18次exec，父本恢复段约24次exec/协作工具调用；所有动态命令均单进程带timeout，未跑全量或真机。
