import { apiFetch } from "./client";
import type { ActivityEvent } from "./types";

export interface ActivityParams {
  types?: string[];
  taskId?: string;
  /** ISO timestamp: only events older than this (for "Load more"). */
  before?: string;
  limit?: number;
}

export const activityApi = {
  list(params: ActivityParams = {}): Promise<ActivityEvent[]> {
    const qs = new URLSearchParams();
    for (const t of params.types ?? []) qs.append("type", t);
    if (params.taskId) qs.set("task_id", params.taskId);
    if (params.before) qs.set("before", params.before);
    qs.set("limit", String(params.limit ?? 100));
    return apiFetch(`/activity?${qs.toString()}`);
  },
};
