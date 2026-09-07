import { routeWorkspaceInput } from "../src/features/personal-workspace/personal-workspace-router.js";

function equal(actual: unknown, expected: unknown, label: string) {
  if (actual !== expected) throw new Error(`${label}: expected ${String(expected)}, received ${String(actual)}`);
}

function ok(value: unknown, label: string) {
  if (!value) throw new Error(label);
}

const goalContext = {
  agents: [{ agentId: "codex", label: "Codex" }],
  goalId: "demo-goal",
  todos: [{ text: "整理验收材料", todoId: "todo-1" }],
};

equal(routeWorkspaceInput("我现在该做什么？只读回答，不要修改状态", { ...goalContext, goalId: null }).route, "projection", "manager projection");
equal(routeWorkspaceInput("不要设置 Heartbeat，只回答当前进度", goalContext).route, "agent_chat", "negated heartbeat");
equal(routeWorkspaceInput("每天推进这个 Goal，设置 heartbeat", goalContext).actionKind, "heartbeat.bind", "heartbeat outranks generic daily monitor");
equal(routeWorkspaceInput("Set up a Heartbeat for this Goal with daily progress", goalContext).actionKind, "heartbeat.bind", "English heartbeat");
equal(routeWorkspaceInput("Turn Heartbeat off", goalContext).route, "agent_chat", "explicit English heartbeat disable stays in chat");
equal(routeWorkspaceInput("Add a scheduled check every 2 hours", goalContext).actionKind, "monitor.create", "English monitor");
equal(routeWorkspaceInput("Add a monitor for off hours", goalContext).actionKind, "monitor.create", "off hours is a valid monitor target");
equal(routeWorkspaceInput("Create a scheduled check for off-hours deployment alerts", goalContext).actionKind, "monitor.create", "hyphenated off-hours is a valid scheduled-check target");
equal(routeWorkspaceInput("Turn monitor off", goalContext).route, "agent_chat", "explicit English monitor disable stays in chat");
equal(routeWorkspaceInput("创建一个 Todo：整理发布说明", goalContext).actionKind, "todo.create", "todo create");
equal(
  routeWorkspaceInput("做一次只读分析：判断刚刚新增的 Todo 是否与当前 Goal 一致。不要修改状态。", goalContext).route,
  "agent_chat",
  "existing todo read-only analysis",
);
equal(routeWorkspaceInput("把 todo-1 标记完成", goalContext).actionKind, "todo.update", "todo update");
const deferMissingCondition = routeWorkspaceInput("把 todo-1 暂缓", goalContext);
equal(deferMissingCondition.route, "clarify", "todo defer without condition clarifies");
equal(deferMissingCondition.missingFields.join(","), "resume_when", "todo defer names missing resume condition");
const deferUntilPr = routeWorkspaceInput("把 todo-1 暂缓到pr_merged:huangruiteng/loopx#3399", goalContext);
equal(deferUntilPr.route, "typed_action", "todo defer with condition routes to typed action");
equal(deferUntilPr.normalizedParameters.resume_when, "pr_merged:huangruiteng/loopx#3399", "todo defer preserves supported condition");
equal(routeWorkspaceInput("帮我修复 MR 冲突，跑测试，然后 push", goalContext).actionKind, "todo.create", "execution task");
equal(routeWorkspaceInput("创建任务并设置 Heartbeat", goalContext).route, "clarify", "compound intent");
equal(routeWorkspaceInput("创建任务并设置 Heartbeat", goalContext).missingFields.join(","), "single_intent", "compound missing field");
equal(routeWorkspaceInput("Create a task and set up a Heartbeat", goalContext).route, "clarify", "English compound intent");
equal(routeWorkspaceInput("解释一下现在的状态", goalContext).route, "agent_chat", "goal chat");
equal(routeWorkspaceInput("请问怎么解决一下这个问题？", goalContext).route, "agent_chat", "advice question stays in chat");
equal(routeWorkspaceInput("请不要部署到生产环境", goalContext).route, "agent_chat", "negated deployment does not trigger gate");
equal(routeWorkspaceInput("请只回复：合并后真实回复已收到", goalContext).route, "agent_chat", "descriptive merge phrase stays in chat");
equal(routeWorkspaceInput("请分析：合并 PR #123 后会有什么风险", goalContext).route, "agent_chat", "protected action discussion stays in chat");
equal(routeWorkspaceInput("请合并 PR #123", goalContext).route, "agent_chat", "protected merge intent is interpreted by the Agent");
equal(routeWorkspaceInput("请合并", goalContext).route, "agent_chat", "targetless protected intent is clarified by the Agent");
equal(routeWorkspaceInput("请把 PR #456 合并", goalContext).route, "agent_chat", "object-first merge reaches semantic interpretation");
equal(routeWorkspaceInput("请发布 v1.2.3", goalContext).route, "agent_chat", "release intent reaches semantic interpretation");
equal(routeWorkspaceInput("现在部署到生产环境", goalContext).route, "agent_chat", "deployment intent reaches semantic interpretation");
equal(routeWorkspaceInput("请删除 todo_demo_123", goalContext).route, "agent_chat", "delete intent reaches semantic interpretation");
equal(routeWorkspaceInput("批准付款 100 元", goalContext).route, "agent_chat", "payment intent reaches semantic interpretation");
equal(routeWorkspaceInput("请部署服务", goalContext).route, "agent_chat", "generic deployment target is clarified by the Agent");
equal(routeWorkspaceInput("发布完成后请只回复结果", goalContext).route, "agent_chat", "descriptive release phrase stays in chat");
equal(routeWorkspaceInput("整理验收材料还没有完成，不要关闭", goalContext).route, "agent_chat", "negated complete does not update todo");

const createGoal = routeWorkspaceInput("创建 Goal：整理每周复盘", { ...goalContext, goalId: null });
equal(createGoal.route, "clarify", "Goal creation asks for an explicit continuation mode");
equal(createGoal.missingFields.join(","), "continuation_mode", "Goal clarification names the missing continuation mode");
const createEnglishGoal = routeWorkspaceInput("Create a long-term Goal: prepare my weekly review", { ...goalContext, goalId: null });
equal(createEnglishGoal.route, "clarify", "English Goal creation asks for an explicit continuation mode");
equal(createEnglishGoal.missingFields.join(","), "continuation_mode", "English Goal clarification names the missing continuation mode");
equal(routeWorkspaceInput("Create a Goal: off track delivery recovery", { ...goalContext, goalId: null }).actionKind, "goal.create", "off track is not a Goal-disable command");
const oneShotGoal = routeWorkspaceInput("Create a Goal without Heartbeat", { ...goalContext, goalId: null });
equal(oneShotGoal.route, "typed_action", "an explicit one-shot Goal remains actionable");
equal(oneShotGoal.actionKind, "goal.create", "an explicit one-shot Goal keeps the Goal action");
equal(oneShotGoal.normalizedParameters.heartbeat_enabled, false, "English Goal can explicitly omit Heartbeat");
const continuousGoal = routeWorkspaceInput("Create a Goal with a daily Heartbeat", { ...goalContext, goalId: null });
equal(continuousGoal.route, "typed_action", "an explicit continuous Goal remains actionable");
equal(continuousGoal.actionKind, "goal.create", "an explicit continuous Goal keeps the Goal action");
equal(continuousGoal.normalizedParameters.heartbeat_enabled, true, "an explicit continuous Goal enables Heartbeat");
ok(continuousGoal.confidence >= 0.9, "explicit Goal confidence");

console.log("personal workspace router smoke passed");
