import type { SSEEvent } from "@/api/types";
import { formatRelativeTime } from "@/lib/formatters";
import { StatusDot } from "@/components/common/StatusDot";

export function ActivityItem({ event }: { event: SSEEvent }) {
  const status = event.type.includes("completed")
    ? "completed"
    : event.type.includes("failed")
      ? "failed"
      : event.type.includes("started") || event.type.includes("running")
        ? "running"
        : "pending";

  return (
    <div className="flex items-start gap-2 p-2 hover:bg-gray-50 rounded">
      <StatusDot status={status} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-800">
          <span className="font-medium">{event.type.replace(/_/g, " ")}</span>
        </p>
        <p className="text-xs text-gray-500 truncate">
          Task: {event.task_id}
        </p>
      </div>
      <span className="text-xs text-gray-400 whitespace-nowrap">
        {formatRelativeTime(event.timestamp)}
      </span>
    </div>
  );
}
