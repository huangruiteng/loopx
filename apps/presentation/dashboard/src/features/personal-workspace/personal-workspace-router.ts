export type WorkspaceRouterActionKind =
  | "goal.create"
  | "todo.create"
  | "todo.update"
  | "agent.bind"
  | "heartbeat.bind"
  | "monitor.create";

export type WorkspaceRouterResult = {
  actionKind: WorkspaceRouterActionKind | null;
  confidence: number;
  missingFields: string[];
  normalizedParameters: Record<string, unknown>;
  route: "projection" | "typed_action" | "agent_chat" | "clarify";
};

export type WorkspaceRouterContext = {
  agents: Array<{ agentId: string; label: string }>;
  goalId: string | null;
  todos: Array<{ text: string; todoId: string }>;
};

function normalizedMessage(message: string) {
  return message.replace(/\s+/gu, " ").trim();
}

function negates(message: string, subject: RegExp) {
  const beforeSubject = new RegExp(
    `(?:不要|不需要|无需|禁止|别|暂不|do not\\b|don't\\b|without\\b).{0,10}(?:${subject.source})`,
    "iu",
  );
  const chineseAfter = new RegExp(`(?:${subject.source}).{0,10}(?:不要|不需要|无需|禁止|关闭)`, "iu");
  const explicitEnglishDisable = new RegExp(
    `disable\\b.{0,10}(?:${subject.source})|(?:turn|switch|set)\\b.{0,10}(?:${subject.source}).{0,10}\\boff\\b|(?:${subject.source})\\s+(?:is\\s+)?disabled\\b`,
    "iu",
  );
  return beforeSubject.test(message)
    || chineseAfter.test(message)
    || explicitEnglishDisable.test(message);
}

function managerProjectionIntent(message: string) {
  return /(我现在该做什么|下一步|哪些\s*Goal\s*在等我|需要我|谁在等我|Agent\s*在做什么|当前进度|总结(?:今天)?进展)/iu.test(message);
}

function heartbeatPreference(message: string): boolean | null {
  if (negates(message, /heartbeat|心跳/iu)) return false;
  if (/(heartbeat|心跳|每天推进|持续推进|daily progress)/iu.test(message)) return true;
  return null;
}

function executionIntent(message: string) {
  const asksForAdvice = /(怎么|如何|为什么|给.*建议|分析一下|解释|只读)/u.test(message);
  const asksForMutation = /(解决一下|修复一下|处理一下|执行一下|改一下|跑(?:一下)?测试|rebase|push|提交|推送)/iu.test(message);
  if (asksForAdvice) return false;
  return asksForMutation
    && /(帮我|请|给我|直接|现在|开始|bytedcli|codebase|git|rebase|push|提交|推送)/iu.test(message);
}

export function todoResumeWhenFromMessage(rawMessage: string) {
  const message = normalizedMessage(rawMessage).toLowerCase();
  const match = message.match(
    /(?:^|[\s，,；;：（(:]|到|至)(?<condition>todo_done:todo_[a-z0-9_-]{3,64}|pr_merged:(?:(?:[a-z0-9_.-]{1,80})\/(?:[a-z0-9_.-]{1,100}))?#[1-9][0-9]{0,8}|capacity_available:[a-z][a-z0-9_:-]{0,63})(?=$|[\s，,。；;）)])/iu,
  );
  return match?.groups?.condition ?? null;
}

export function routeWorkspaceInput(rawMessage: string, context: WorkspaceRouterContext): WorkspaceRouterResult {
  const message = normalizedMessage(rawMessage);
  const candidates: Array<{ actionKind: WorkspaceRouterActionKind; confidence: number; normalizedParameters: Record<string, unknown> }> = [];
  const agent = context.agents.find((candidate) => {
    const lower = message.toLowerCase();
    return lower.includes(candidate.agentId.toLowerCase()) || lower.includes(candidate.label.toLowerCase());
  });
  const todo = context.todos.find((candidate) => message.includes(candidate.todoId) || message.includes(candidate.text));
  const todoSubject = "todo|待办|任务";
  const referencesExistingTodo = /(刚刚|已经|已)(?:经)?\s*(新增|创建|添加)(?:的)?\s*(todo|待办|任务)/iu.test(message);
  const requestedHeartbeat = heartbeatPreference(message);
  const requestsHeartbeat = Boolean(context.goalId) && requestedHeartbeat === true;

  if (!context.goalId && !negates(message, /goal|目标/iu) && /(创建|新建|设置|create|start|set up).{0,24}(goal|目标)/iu.test(message)) {
    if (requestedHeartbeat === null) {
      return {
        actionKind: "goal.create",
        confidence: 0.97,
        missingFields: ["continuation_mode"],
        normalizedParameters: {},
        route: "clarify",
      };
    }
    candidates.push({
      actionKind: "goal.create",
      confidence: 0.97,
      normalizedParameters: {
        heartbeat_enabled: requestedHeartbeat,
      },
    });
  }
  if (context.goalId && requestsHeartbeat) {
    candidates.push({ actionKind: "heartbeat.bind", confidence: 0.96, normalizedParameters: { goal_id: context.goalId } });
  }
  if (context.goalId
    && !requestsHeartbeat
    && !negates(message, /定时|监控|监测|持续观察|scheduled check|monitor/iu)
    && /(定时|监控|监测|每.{0,8}(分钟|小时|天)|持续观察|scheduled check|monitor|every.{0,12}(minute|hour|day)|daily)/iu.test(message)) {
    candidates.push({ actionKind: "monitor.create", confidence: 0.94, normalizedParameters: { goal_id: context.goalId } });
  }
  if (context.goalId && agent && !negates(message, /绑定|负责|接管|管理/iu) && /((让|交给).{0,20}(管理|负责|接管).{0,8}(goal|目标)|(绑定).{0,12}(goal|目标)|(goal|目标).{0,12}(交给|绑定|负责|接管))/iu.test(message)) {
    candidates.push({ actionKind: "agent.bind", confidence: 0.96, normalizedParameters: { agent_id: agent.agentId, goal_id: context.goalId } });
  }
  if (context.goalId && !referencesExistingTodo && !negates(message, new RegExp(todoSubject, "iu"))
    && /(创建|新建|新增|添加|加一个|记一个).{0,16}(todo|待办|任务)|(todo|待办|任务).{0,12}(创建|新建|新增|添加)|(?:create|add)(?:\s+(?:a|an|new))?\s+(?:todo|task)|(?:todo|task).{0,12}(?:create|add)/iu.test(message)) {
    candidates.push({ actionKind: "todo.create", confidence: 0.94, normalizedParameters: { goal_id: context.goalId } });
  }
  if (context.goalId && executionIntent(message)) {
    candidates.push({ actionKind: "todo.create", confidence: 0.9, normalizedParameters: { goal_id: context.goalId, start_execution: true } });
  }
  if (context.goalId && todo) {
    const operation = !negates(message, /完成|做完|关闭/u) && /完成|做完|关闭/u.test(message) ? "complete"
      : !negates(message, /阻塞|卡住/u) && /阻塞|卡住/u.test(message) ? "block"
        : !negates(message, /暂缓|稍后|推迟/u) && /暂缓|稍后|推迟/u.test(message) ? "defer"
          : agent && !negates(message, /交给|分配给|改派/u) && /交给|分配给|改派/u.test(message) ? "reassign"
            : null;
    if (operation) {
      const resumeWhen = operation === "defer" ? todoResumeWhenFromMessage(message) : null;
      if (operation === "defer" && !resumeWhen) {
        return {
          actionKind: "todo.update",
          confidence: 0.97,
          missingFields: ["resume_when"],
          normalizedParameters: { goal_id: context.goalId, operation, todo_id: todo.todoId },
          route: "clarify",
        };
      }
      candidates.push({
        actionKind: "todo.update",
        confidence: 0.97,
        normalizedParameters: {
          goal_id: context.goalId,
          operation,
          ...(resumeWhen ? { resume_when: resumeWhen } : {}),
          todo_id: todo.todoId,
        },
      });
    }
  }
  const distinct = [...new Map(candidates.map((candidate) => [candidate.actionKind, candidate])).values()];
  if (distinct.length > 1) {
    return { actionKind: null, confidence: 0.4, missingFields: ["single_intent"], normalizedParameters: {}, route: "clarify" };
  }
  if (distinct.length === 1) {
    const candidate = distinct[0];
    return { ...candidate, missingFields: [], route: "typed_action" };
  }
  if (!context.goalId && managerProjectionIntent(message)) {
    return { actionKind: null, confidence: 0.98, missingFields: [], normalizedParameters: {}, route: "projection" };
  }
  return { actionKind: null, confidence: 0.75, missingFields: [], normalizedParameters: {}, route: "agent_chat" };
}
