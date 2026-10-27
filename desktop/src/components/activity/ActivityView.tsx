import { useEventStore } from "@/store/eventStore";
import { ActivityItem } from "./ActivityItem";

export function ActivityView() {
  const events = useEventStore((s) => s.events);
  const connected = useEventStore((s) => s.connected);
  const clearEvents = useEventStore((s) => s.clearEvents);

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-800">Activity</h2>
          <span
            className={`h-2 w-2 rounded-full ${
              connected ? "bg-green-500 animate-pulse" : "bg-red-500"
            }`}
          />
        </div>
        <button
          onClick={clearEvents}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Clear
        </button>
      </div>

      {events.length === 0 ? (
        <p className="text-gray-400 text-center py-12">
          {connected
            ? "Waiting for events..."
            : "Not connected to backend"}
        </p>
      ) : (
        <div className="space-y-1">
          {events.map((event, i) => (
            <ActivityItem key={`${event.timestamp}-${i}`} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
