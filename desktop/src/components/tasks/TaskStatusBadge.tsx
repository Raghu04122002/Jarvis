import { statusBgColor } from "@/lib/formatters";

export function TaskStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${statusBgColor(status)}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
