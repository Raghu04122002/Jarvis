import { DEFAULT_BACKEND_URL } from "@/lib/constants";
import type { SSEEvent } from "./types";

export function connectSSE(
  onEvent: (event: SSEEvent) => void,
  onError: (error: Event) => void,
  onOpen: () => void,
  taskId?: string,
  backendUrl?: string,
): EventSource {
  const base = backendUrl ?? DEFAULT_BACKEND_URL;
  const params = taskId ? `?task_id=${taskId}` : "";
  const url = `${base}/events/stream${params}`;

  const source = new EventSource(url);

  source.onopen = onOpen;
  source.onerror = onError;

  // Listen for all event types from the backend
  const eventTypes = [
    "task_created",
    "task_updated",
    "task_state_changed",
    "task_step_started",
    "task_step_completed",
    "task_failed",
    "task_cancelled",
    "task_completed",
    "project_created",
    "project_updated",
    "project_deleted",
    "agent_execution_started",
    "agent_execution_completed",
    "tool_execution_started",
    "tool_execution_completed",
    "agent_fallback_triggered",
    "memory_created",
    "memory_updated",
    "memory_deleted",
    "approval_requested",
    "approval_approved",
    "approval_denied",
    "approval_expired",
  ];

  for (const type of eventTypes) {
    source.addEventListener(type, (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data as string) as SSEEvent;
        onEvent(data);
      } catch {
        // skip malformed events
      }
    });
  }

  return source;
}
