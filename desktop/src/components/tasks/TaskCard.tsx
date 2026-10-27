import { Link } from "react-router-dom";
import type { TaskSummary } from "@/api/types";
import { TaskStatusBadge } from "./TaskStatusBadge";
import { formatRelativeTime } from "@/lib/formatters";

export function TaskCard({ task }: { task: TaskSummary }) {
  return (
    <Link
      to={`/tasks/${task.id}`}
      className="block p-4 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-gray-800 truncate flex-1">
          {task.title}
        </h3>
        <TaskStatusBadge status={task.status} />
      </div>
      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
        <span>{task.priority}</span>
        <span>{formatRelativeTime(task.created_at)}</span>
      </div>
    </Link>
  );
}
