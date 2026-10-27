import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Bot, FolderGit2, MessageSquare, Play, RotateCcw, Square } from "lucide-react";
import { useTaskStore } from "@/store/taskStore";
import { useChatStore } from "@/store/chatStore";
import { useProjectStore } from "@/store/projectStore";
import { Markdown } from "@/components/common/Markdown";
import { RelativeTime } from "@/components/common/RelativeTime";
import { agentLabel, isActive } from "@/lib/taskStatus";
import { TaskStatusBadge } from "./TaskStatusBadge";
import { TaskSteps } from "./TaskSteps";
import { ExecutionLog } from "./ExecutionLog";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-700">{title}</h3>
      {children}
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6" aria-hidden>
      <div className="h-6 w-1/3 animate-pulse rounded bg-gray-200" />
      <div className="h-28 animate-pulse rounded-xl bg-gray-100" />
      <div className="h-40 animate-pulse rounded-xl bg-gray-100" />
    </div>
  );
}

export function TaskDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const task = useTaskStore((s) => s.currentTask);
  const steps = useTaskStore((s) => s.steps);
  const executions = useTaskStore((s) => s.executions);
  const loading = useTaskStore((s) => s.loading);
  const error = useTaskStore((s) => s.error);
  const fetchTask = useTaskStore((s) => s.fetchTask);
  const fetchSteps = useTaskStore((s) => s.fetchSteps);
  const fetchExecutions = useTaskStore((s) => s.fetchExecutions);
  const cancelTask = useTaskStore((s) => s.cancelTask);
  const retryTask = useTaskStore((s) => s.retryTask);
  const dispatchTask = useTaskStore((s) => s.dispatchTask);
  const conversations = useChatStore((s) => s.conversations);
  const selectChat = useChatStore((s) => s.selectChat);
  const projects = useProjectStore((s) => s.projects);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const [busy, setBusy] = useState<null | "cancel" | "retry" | "start">(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    void fetchTask(id);
    void fetchSteps(id);
    void fetchExecutions(id);
  }, [id, fetchTask, fetchSteps, fetchExecutions]);

  useEffect(() => {
    if (projects.length === 0) void fetchProjects();
  }, [projects.length, fetchProjects]);

  const run = async (kind: "cancel" | "retry" | "start", fn: () => Promise<void>) => {
    setBusy(kind);
    setActionError(null);
    try {
      await fn();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(null);
    }
  };

  if (!task || task.id !== id) {
    if (loading) return <DetailSkeleton />;
    return (
      <div className="mx-auto max-w-4xl p-6 text-center">
        <p className="text-sm text-gray-600">{error ? `Couldn't load this task: ${error}` : "Task not found."}</p>
        <Link to="/tasks" className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline">
          Back to tasks
        </Link>
      </div>
    );
  }

  const agent = agentLabel(task.metadata.agent_name);
  const conversation = conversations.find((c) => c.id === task.metadata.conversation_id);
  const project = projects.find((p) => p.id === task.project_id);
  const canStart = task.status === "planning" || task.status === "created";

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <button
        type="button"
        onClick={() => navigate("/tasks")}
        className="inline-flex items-center gap-1 rounded text-sm text-gray-500 hover:text-gray-800 focus-visible:outline-2 focus-visible:outline-blue-500"
      >
        <ArrowLeft size={14} aria-hidden /> Tasks
      </button>

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold text-gray-900">{task.title}</h2>
            <TaskStatusBadge status={task.status} />
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
            <span className="font-mono">{task.id}</span>
            {agent && (
              <span className="inline-flex items-center gap-1" title={task.metadata.agent_reason}>
                <Bot size={12} aria-hidden /> {agent}
              </span>
            )}
            {project && (
              <Link to={`/projects/${project.id}`} className="inline-flex items-center gap-1 hover:text-blue-600">
                <FolderGit2 size={12} aria-hidden /> {project.name}
              </Link>
            )}
            {conversation && (
              <button
                type="button"
                onClick={() => {
                  selectChat(conversation.id);
                  navigate("/");
                }}
                className="inline-flex items-center gap-1 hover:text-blue-600"
              >
                <MessageSquare size={12} aria-hidden /> {conversation.title}
              </button>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {canStart && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void run("start", () => dispatchTask(task.id))}
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <Play size={14} aria-hidden /> {busy === "start" ? "Starting…" : "Start now"}
            </button>
          )}
          {task.status === "failed" && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void run("retry", () => retryTask(task.id))}
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <RotateCcw size={14} aria-hidden /> {busy === "retry" ? "Retrying…" : "Retry"}
            </button>
          )}
          {isActive(task.status) && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void run("cancel", () => cancelTask(task.id))}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <Square size={13} aria-hidden /> {busy === "cancel" ? "Cancelling…" : "Cancel"}
            </button>
          )}
        </div>
      </header>

      {actionError && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {actionError}
        </p>
      )}

      {task.status === "failed" && task.error && (
        <div role="alert" className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-600" aria-hidden />
          <div className="min-w-0">
            <p className="text-sm font-medium text-red-800">This task failed</p>
            <pre className="mt-1 whitespace-pre-wrap break-words font-sans text-sm text-red-700">{task.error}</pre>
          </div>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-3 rounded-xl border border-gray-200 bg-white p-4 text-sm sm:grid-cols-4">
        {(
          [
            ["Created", task.created_at],
            ["Started", task.started_at],
            ["Finished", task.completed_at],
            ["Updated", task.updated_at],
          ] as const
        ).map(([label, iso]) => (
          <div key={label}>
            <dt className="text-xs text-gray-500">{label}</dt>
            <dd className="text-gray-800">{iso ? <RelativeTime iso={iso} /> : "—"}</dd>
          </div>
        ))}
      </dl>

      <Section title="Request">
        <p className="whitespace-pre-wrap text-sm text-gray-800">{task.request}</p>
      </Section>

      {task.result && (
        <Section title="Result">
          <Markdown content={task.result} />
        </Section>
      )}

      <Section title="Steps">
        <TaskSteps steps={steps} plan={task.plan} />
      </Section>

      <Section title="Agent runs & logs">
        <ExecutionLog executions={executions} />
      </Section>
    </div>
  );
}
