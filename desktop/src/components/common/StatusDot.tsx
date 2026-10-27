const colors: Record<string, string> = {
  completed: "bg-green-500",
  failed: "bg-red-500",
  error: "bg-red-500",
  running: "bg-blue-500 animate-pulse",
  in_progress: "bg-blue-500 animate-pulse",
  pending: "bg-yellow-500",
  planning: "bg-yellow-500",
  cancelled: "bg-gray-400",
  awaiting_approval: "bg-orange-500 animate-pulse",
  waiting_for_approval: "bg-orange-500 animate-pulse",
  created: "bg-gray-400",
};

export function StatusDot({ status }: { status: string }) {
  const color = colors[status] ?? "bg-gray-400";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} />;
}
