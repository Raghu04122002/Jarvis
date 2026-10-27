/** Human-readable descriptions and filter groups for activity events. */

export type ActivityGroup = "all" | "tasks" | "agents" | "approvals" | "chat" | "projects";

export const ACTIVITY_GROUPS: { id: ActivityGroup; label: string; types: string[] }[] = [
  { id: "all", label: "All", types: [] },
  {
    id: "tasks",
    label: "Tasks",
    types: ["task_created", "task_updated", "task_state_changed", "task_completed", "task_failed", "task_cancelled", "task_reviewed"],
  },
  {
    id: "agents",
    label: "Agents",
    types: ["agent_execution_started", "agent_execution_completed", "agent_execution_failed", "agent_fallback_triggered"],
  },
  { id: "approvals", label: "Approvals", types: ["approval_requested", "approval_approved", "approval_denied", "approval_expired"] },
  { id: "chat", label: "Chat", types: ["query_answered"] },
  { id: "projects", label: "Projects", types: ["project_created", "project_updated", "project_deleted"] },
];

export type Tone = "ok" | "bad" | "busy" | "warn" | "info";

const str = (v: unknown): string | undefined => (typeof v === "string" && v ? v : undefined);

const AGENT: Record<string, string> = { claude_code: "Claude Code", antigravity: "Antigravity" };
const agent = (v: unknown) => (str(v) ? (AGENT[str(v)!] ?? str(v)) : "An agent");

/** One plain-English line describing an event, plus a colour tone. */
export function describeEvent(type: string, data: Record<string, unknown>): { text: string; tone: Tone } {
  const title = str(data.title);
  const q = title ? ` “${title}”` : "";
  switch (type) {
    case "task_created":
      return { text: `Task created${q}`, tone: "info" };
    case "task_state_changed":
      return { text: `Task moved to ${str(data.to)?.replace(/_/g, " ") ?? "a new state"}`, tone: "busy" };
    case "task_completed":
      return { text: `Task finished${q}`, tone: "ok" };
    case "task_failed":
      return { text: `Task failed${str(data.error) ? `: ${str(data.error)}` : ""}`, tone: "bad" };
    case "task_cancelled":
      return { text: "Task cancelled", tone: "warn" };
    case "task_reviewed":
      return {
        text: `Reviewer ${data.done ? "accepted" : "sent back"} the work${str(data.summary) ? ` — ${str(data.summary)}` : ""}`,
        tone: data.done ? "ok" : "warn",
      };
    case "agent_execution_started":
      return { text: `${agent(data.agent_name)} started working`, tone: "busy" };
    case "agent_execution_completed":
      return { text: `${agent(data.agent_name)} finished`, tone: "ok" };
    case "agent_execution_failed":
      return { text: `${agent(data.agent_name)} failed`, tone: "bad" };
    case "agent_fallback_triggered":
      return { text: `${agent(data.primary_agent)} couldn't start; falling back to ${agent(data.fallback_agent)}`, tone: "warn" };
    case "approval_requested":
      return { text: `Approval requested for ${str(data.tool_name) ?? "a tool"} → ${str(data.operation) ?? "action"}`, tone: "warn" };
    case "approval_approved":
      return { text: "Approval granted", tone: "ok" };
    case "approval_denied":
      return { text: "Approval denied", tone: "bad" };
    case "approval_expired":
      return { text: "Approval request expired", tone: "warn" };
    case "query_answered":
      return { text: `Answered in chat${str(data.message) ? `: “${str(data.message)!.slice(0, 80)}”` : ""}`, tone: "info" };
    default:
      return { text: type.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()), tone: "info" };
  }
}
