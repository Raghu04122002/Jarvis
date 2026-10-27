import { Link } from "react-router-dom";
import { RelativeTime } from "@/components/common/RelativeTime";
import { describeEvent, type Tone } from "@/lib/activity";

const DOT: Record<Tone, string> = {
  ok: "bg-green-500",
  bad: "bg-red-500",
  busy: "bg-blue-500",
  warn: "bg-amber-500",
  info: "bg-gray-400",
};

export interface FeedEvent {
  key: string;
  type: string;
  task_id: string | null;
  data: Record<string, unknown>;
  timestamp: string;
}

export function ActivityItem({ event }: { event: FeedEvent }) {
  const { text, tone } = describeEvent(event.type, event.data);
  return (
    <li className="flex items-start gap-3 px-4 py-2.5">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[tone]}`} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm text-gray-800">{text}</p>
        <p className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-gray-400">
          <span className="font-mono">{event.type}</span>
          {event.task_id && (
            <Link to={`/tasks/${event.task_id}`} className="font-mono text-blue-600 hover:underline">
              {event.task_id}
            </Link>
          )}
        </p>
      </div>
      <RelativeTime iso={event.timestamp} className="shrink-0 text-xs text-gray-400" />
    </li>
  );
}
