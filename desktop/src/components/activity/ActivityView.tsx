import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity as ActivityIcon } from "lucide-react";
import { activityApi } from "@/api/activity";
import { useEventStore } from "@/store/eventStore";
import { ACTIVITY_GROUPS, type ActivityGroup } from "@/lib/activity";
import { ActivityItem, type FeedEvent } from "./ActivityItem";

const PAGE = 50;
const liveKey = (e: { type: string; task_id: string | null; timestamp: string }) =>
  `${e.type}|${e.task_id ?? ""}|${e.timestamp}`;

export function ActivityView() {
  const [group, setGroup] = useState<ActivityGroup>("all");
  const [saved, setSaved] = useState<FeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const live = useEventStore((s) => s.events);
  const connected = useEventStore((s) => s.connected);
  const types = ACTIVITY_GROUPS.find((g) => g.id === group)!.types;

  const load = useCallback(
    async (before?: string) => {
      const rows = await activityApi.list({ types, before, limit: PAGE });
      setHasMore(rows.length === PAGE);
      return rows.map<FeedEvent>((r) => ({ ...r, key: liveKey(r) }));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [group],
  );

  useEffect(() => {
    let stale = false;
    setLoading(true);
    setError(null);
    load()
      .then((rows) => !stale && setSaved(rows))
      .catch((e) => !stale && setError(e instanceof Error ? e.message : "Couldn't load activity"))
      .finally(() => !stale && setLoading(false));
    return () => {
      stale = true;
    };
  }, [load]);

  const loadMore = async () => {
    const oldest = saved[saved.length - 1];
    if (!oldest) return;
    setLoadingMore(true);
    try {
      const rows = await load(oldest.timestamp);
      setSaved((s) => [...s, ...rows]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load more");
    } finally {
      setLoadingMore(false);
    }
  };

  // Live events arrive before they're persisted, so merge and de-duplicate.
  const feed = useMemo(() => {
    const seen = new Set(saved.map((e) => e.key));
    const fresh = live
      .filter((e) => types.length === 0 || types.includes(e.type))
      .map<FeedEvent>((e) => ({ ...e, task_id: e.task_id || null, key: liveKey({ ...e, task_id: e.task_id || null }) }))
      .filter((e) => !seen.has(e.key));
    return [...fresh, ...saved].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [live, saved, types]);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Activity</h2>
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <span className={`h-2 w-2 rounded-full ${connected ? "animate-pulse bg-green-500" : "bg-red-500"}`} aria-hidden />
          {connected ? "Live" : "Not connected to backend"}
        </span>
      </div>

      <div role="tablist" aria-label="Filter activity" className="mb-4 flex flex-wrap gap-1.5">
        {ACTIVITY_GROUPS.map((g) => (
          <button
            key={g.id}
            type="button"
            role="tab"
            aria-selected={g.id === group}
            onClick={() => setGroup(g.id)}
            className={`rounded-full px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-blue-500 ${
              g.id === group ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {g.label}
          </button>
        ))}
      </div>

      {error && (
        <p role="alert" className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {loading ? (
        <div className="space-y-2" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-12 animate-pulse rounded-lg bg-gray-100" />)}
        </div>
      ) : feed.length === 0 ? (
        <div className="flex flex-col items-center rounded-xl border border-dashed border-gray-300 px-6 py-12 text-center">
          <ActivityIcon size={26} className="text-gray-400" aria-hidden />
          <p className="mt-2 text-sm font-medium text-gray-800">No activity yet</p>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            Everything Jarvis does (tasks created, agents starting and finishing, approvals, chat answers) is
            recorded here and kept across restarts.
          </p>
        </div>
      ) : (
        <>
          <ul className="divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
            {feed.map((e) => <ActivityItem key={e.key} event={e} />)}
          </ul>
          {hasMore && (
            <div className="mt-3 text-center">
              <button
                type="button"
                disabled={loadingMore}
                onClick={() => void loadMore()}
                className="rounded-lg border border-gray-300 bg-white px-4 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {loadingMore ? "Loading…" : "Load older"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
