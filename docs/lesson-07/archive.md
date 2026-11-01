# 首条变更归档记录

日期：2026-11-02（Asia/Shanghai）。用户明确选择“立即同步主规约后归档”。

- 变更：bootstrap-project-foundation；schema：spec-driven。
- 归档路径：`openspec/changes/archive/2026-11-02-bootstrap-project-foundation/`。
- 完整保留proposal、design、四份delta spec、tasks及.openspec.yaml；20项任务全部完成，无未完成产物或任务警告。
- 同步新增主规约：application-foundation（3需求/8场景）、engineering-governance（4/4）、health-observability（4/8）、reproducible-runtime（4/6），合计15需求、26场景。
- 同步只添加主规约标题并将ADDED Requirements转换为Requirements；Purpose、每条需求和Scenario原文保持一致。逐文件核对后才移动归档目录。
- README与课程索引更新归档引用；治理测试改为读取四项主规约，避免依赖活动变更目录。

归档前四项主规约严格校验通过，变更严格校验通过。归档后四项主规约及归档任务检查均严格校验通过（issues=[]），63项pytest全部通过。校验及回归原始结果见 `docs/verification/archive-validation.json`、`docs/verification/archive-tasks-validation.json`、`docs/verification/archive-pytest.txt`。

原planning、config-docs和implementation记录为当时阶段的历史证据，保留其原始结果；本记录补充后续归档动作，不将“此前未归档”改写成当时已归档。没有提交、推送或创建Git标签。教师权限、真正新会话实验、另一位组员异机peer review仍待验证，归档不代表这些课程验收完成。
