import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, X } from "lucide-react";
import { useTaskStore } from "@/store/taskStore";
import {
  EMPTY_STATE,
  TASK_FILTERS,
  matchesFilter,
  type TaskFilter,
} from "@/lib/taskStatus";
import { TaskCard } from "./TaskCard";

function SkeletonRows() {
  return (
    <div className="space-y-2" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="h-[68px] animate-pulse rounded-xl border border-gray-200 bg-gray-100" />
      ))}
    </div>
  );
}

export function TaskListView() {
  const tasks = useTaskStore((s) => s.tasks);
  const loaded = useTaskStore((s) => s.loaded);
  const error = useTaskStore((s) => s.error);
  const query = useTaskStore((s) => s.query);
  const setQuery = useTaskStore((s) => s.setQuery);
  const fetchTasks = useTaskStore((s) => s.fetchTasks);
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [draft, setDraft] = useState(query);

  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  // Debounce the search box so we don't hit the API on every keystroke.
  useEffect(() => {
    if (draft === query) return;
    const t = setTimeout(() => setQuery(draft), 250);
    return () => clearTimeout(t);
  }, [draft, query, setQuery]);

  const counts = useMemo(() => {
    const c = {} as Record<TaskFilter, number>;
    for (const f of TASK_FILTERS) c[f.id] = tasks.filter((t) => matchesFilter(t.status, f.id)).length;
    return c;
  }, [tasks]);
  const visible = tasks.filter((t) => matchesFilter(t.status, filter));

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-900">Tasks</h2>
        <label className="relative w-full sm:w-72">
          <span className="sr-only">Search tasks</span>
          <Search size={15} className="pointer-events-none absolute left-2.5 top-2.5 text-gray-400" aria-hidden />
          <input
            type="search"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Search tasks"
            className="w-full rounded-lg border border-gray-300 bg-white py-1.5 pl-8 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
          {draft && (
            <button
              type="button"
              onClick={() => setDraft("")}
              aria-label="Clear search"
              className="absolute right-2 top-2 rounded p-0.5 text-gray-400 hover:text-gray-600 focus-visible:outline-2 focus-visible:outline-blue-500"
            >
              <X size={14} />
            </button>
          )}
        </label>
      </div>

      <div role="tablist" aria-label="Filter tasks by status" className="mb-4 flex gap-1 overflow-x-auto border-b border-gray-200">
        {TASK_FILTERS.map((f) => {
          const active = f.id === filter;
          return (
            <button
              key={f.id}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() => setFilter(f.id)}
              className={`-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-blue-500 ${
                active
                  ? "border-blue-600 font-medium text-blue-700"
                  : "border-transparent text-gray-500 hover:text-gray-800"
              }`}
            >
              {f.label}
              <span className={`rounded-full px-1.5 text-xs ${active ? "bg-blue-100" : "bg-gray-100"}`}>
                {counts[f.id]}
              </span>
            </button>
          );
        })}
      </div>

      {error && (
        <div role="alert" className="mb-3 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <span>Couldn't load tasks: {error}</span>
          <button type="button" onClick={() => void fetchTasks()} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      {!loaded ? (
        <SkeletonRows />
      ) : visible.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 px-6 py-12 text-center">
          <p className="text-sm text-gray-600">
            {query ? `No tasks match “${query}”.` : EMPTY_STATE[filter]}
          </p>
          {!query && filter === "all" && (
            <Link to="/" className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline">
              Go to Chat
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {visible.map((task) => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
      )}
    </div>
  );
}
