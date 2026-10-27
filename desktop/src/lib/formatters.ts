export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString();
}

export function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffSec = Math.floor((now - then) / 1000);

  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
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
      return "bg-green-100 text-green-800";
    case "failed":
    case "error":
      return "bg-red-100 text-red-800";
    case "running":
    case "in_progress":
      return "bg-blue-100 text-blue-800";
    case "pending":
    case "planning":
      return "bg-yellow-100 text-yellow-800";
    case "cancelled":
      return "bg-gray-100 text-gray-600";
    case "awaiting_approval":
      return "bg-orange-100 text-orange-800";
    default:
      return "bg-gray-100 text-gray-600";
  }
}
