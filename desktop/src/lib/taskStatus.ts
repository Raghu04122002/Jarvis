import type { TaskStatus } from "@/api/types";

/** Tabs on the Tasks page; each groups one or more backend statuses. */
export type TaskFilter = "all" | "running" | "planning" | "completed" | "failed";

export const TASK_FILTERS: { id: TaskFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "running", label: "Running" },
  { id: "planning", label: "Planning" },
  { id: "completed", label: "Completed" },
  { id: "failed", label: "Failed" },
];

const GROUPS: Record<Exclude<TaskFilter, "all">, TaskStatus[]> = {
  running: ["running", "verifying", "waiting_for_approval"],
  planning: ["created", "planning"],
  completed: ["completed"],
  failed: ["failed", "cancelled"],
};

export function matchesFilter(status: TaskStatus, filter: TaskFilter): boolean {
  return filter === "all" || GROUPS[filter].includes(status);
}

/** Tasks that are still doing (or about to do) work and can be cancelled. */
export function isActive(status: TaskStatus): boolean {
  return ["created", "planning", "waiting_for_approval", "running", "verifying"].includes(
    status,
  );
}

export const STATUS_LABEL: Record<TaskStatus, string> = {
  created: "Created",
  planning: "Planning",
  waiting_for_approval: "Needs approval",
  running: "Running",
  verifying: "Verifying",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const AGENT_LABEL: Record<string, string> = {
  claude_code: "Claude Code",
  antigravity: "Antigravity",
};

export function agentLabel(name: string | null | undefined): string | null {
  if (!name) return null;
  return AGENT_LABEL[name] ?? name;
}

export const EMPTY_STATE: Record<TaskFilter, string> = {
  all: "No tasks yet. Ask Jarvis to do something in Chat, like “add a dark mode toggle to the settings page”, and it will show up here.",
  running: "Nothing is running right now.",
  planning: "No tasks are waiting to start.",
  completed: "No completed tasks yet.",
  failed: "No failed or cancelled tasks. Nice.",
};
