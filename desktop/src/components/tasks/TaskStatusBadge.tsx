import { statusBgColor } from "@/lib/formatters";
import { STATUS_LABEL } from "@/lib/taskStatus";
import type { TaskStatus } from "@/api/types";

export function TaskStatusBadge({ status }: { status: string }) {
  const label = STATUS_LABEL[status as TaskStatus] ?? status.replace(/_/g, " ");
  return (
    <span
      className={`inline-block shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${statusBgColor(status)}`}
    >
      {label}
    </span>
  );
}
