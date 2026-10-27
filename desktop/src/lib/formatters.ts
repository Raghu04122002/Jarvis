export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatRelativeTime(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));

  if (diffSec < 45) return "just now";
  if (diffSec < 3600) return `${Math.max(1, Math.round(diffSec / 60))}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 7 * 86400) return `${Math.floor(diffSec / 86400)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "text-green-600";
    case "failed":
    case "error":
      return "text-red-600";
    case "running":
    case "in_progress":
      return "text-blue-600";
    case "pending":
    case "planning":
      return "text-yellow-600";
    case "cancelled":
      return "text-gray-500";
    case "awaiting_approval":
      return "text-orange-600";
    default:
      return "text-gray-600";
  }
}

export function statusBgColor(status: string): string {
  switch (status) {
    case "completed":
    case "approved":
      return "bg-green-100 text-green-800";
    case "failed":
    case "denied":
    case "error":
      return "bg-red-100 text-red-800";
    case "running":
    case "in_progress":
    case "verifying":
      return "bg-blue-100 text-blue-800";
    case "pending":
    case "planning":
      return "bg-yellow-100 text-yellow-800";
    case "cancelled":
      return "bg-gray-100 text-gray-600";
    case "awaiting_approval":
    case "waiting_for_approval":
      return "bg-orange-100 text-orange-800";
    default:
      return "bg-gray-100 text-gray-600";
  }
}
