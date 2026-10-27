import { useEventStore } from "@/store/eventStore";

export function ConnectionStatus() {
  const connected = useEventStore((s) => s.connected);

  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`h-2 w-2 rounded-full ${
          connected ? "bg-green-500" : "bg-red-500"
        }`}
      />
      <span className="text-xs text-gray-500">
        {connected ? "Connected" : "Disconnected"}
      </span>
    </div>
  );
}
