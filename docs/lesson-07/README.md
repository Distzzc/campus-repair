# Lesson 07 交付与评审索引

日期：2026-11-02（Asia/Shanghai）。当前骨架的实施证据和未完成的课程验收如下。

| 交付项 | 证据/检查方法 | 当前结论 |
| --- | --- | --- |
| 规划、严格校验、能力/Scenario | [归档变更](../../openspec/changes/archive/2026-11-02-bootstrap-project-foundation/)、[主规约](../../openspec/specs/)、[归档记录](archive.md)、[26场景映射](../verification/scenario-matrix.md) | 四项主规约已同步；变更已归档，历史验证证据保留 |
| 实现与本地/容器运行 | [实施记录](../verification/implementation.md)、[本地pytest](../verification/pytest-local.txt)、[洁净本地](../verification/clean-local-results.json)、[容器结果](../verification/compose-results.json) | 自动化运行已执行，见原始证据 |
| 常驻规范及生效 | [AGENTS](../../AGENTS.md)、[六类规范](../standards/)、test_governance.py隔离代码变异检查 | 当前AST依赖/命名与文档检查已执行；真正新会话待验证 |
| 数据不入Git/镜像 | [真实上下文检查](../verification/context-results.json) | 本地原生Git与真实Docker夹具已执行 |
| 仓库地址可访问/教师权限 | 地址见README；教师本人访问或维护者核对协作者权限 | 待验证，不能代替教师身份访问 |
| 全历史密钥 | 按所有可获取refs扫描已提交blob及未提交内容，记录范围/工具/命中 | [本地规则扫描](../verification/secret-scan.json)0命中；最终提交及远端历史仍待审查，不凭.gitignore保证 |
| 骨架标签 | 在实现提交后创建明确骨架tag，记录commit和tag | 待用户授权提交/打标签；未将旧提交标为新骨架 |
| 组内peer review | [评审记录模板](peer-review.md) | 待另一位成员在自己的机器执行 |

这里归档课程交付索引和人工评审模板；详细运行记录按设计保留在docs/verification/并通过相对链接引用，不复制生成互相冲突的多份结果。

不能将自动化通过标为教师权限、真实新会话或另一人异机评审通过；最终交付需补足这些独立证据。
