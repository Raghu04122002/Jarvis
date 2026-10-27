import { Link } from "react-router-dom";
import { Bot } from "lucide-react";
import type { TaskSummary } from "@/api/types";
import { RelativeTime } from "@/components/common/RelativeTime";
import { agentLabel } from "@/lib/taskStatus";
import { TaskStatusBadge } from "./TaskStatusBadge";

export function TaskCard({ task }: { task: TaskSummary }) {
  const agent = agentLabel(task.agent_name);
  const failed = task.status === "failed";
  return (
    <Link
      to={`/tasks/${task.id}`}
      className="block rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm transition-colors hover:border-gray-300 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-blue-500"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 flex-1 truncate text-sm font-medium text-gray-900">
          {task.title}
        </h3>
        <TaskStatusBadge status={task.status} />
      </div>
      {failed && task.error && (
        <p className="mt-1 line-clamp-1 text-xs text-red-600">{task.error}</p>
      )}
      <div className="mt-1.5 flex items-center gap-3 text-xs text-gray-500">
        <span className="font-mono text-gray-400">{task.id}</span>
        {agent && (
          <span className="inline-flex items-center gap-1">
            <Bot size={12} aria-hidden />
            {agent}
          </span>
        )}
        {/* Priority only matters when it differs from the default. */}
        {task.priority !== "normal" && (
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">
            {task.priority}
          </span>
        )}
        <RelativeTime iso={task.created_at} className="ml-auto" />
      </div>
    </Link>
  );
}
