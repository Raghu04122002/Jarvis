import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Bot, FolderGit2, GitBranch, MessageSquare, Trash2 } from "lucide-react";
import { useProjectStore } from "@/store/projectStore";
import { useChatStore } from "@/store/chatStore";
import { tasksApi } from "@/api/tasks";
import type { TaskSummary } from "@/api/types";
import { agentLabel } from "@/lib/taskStatus";
import { ConfirmDeleteDialog } from "@/components/common/ConfirmDeleteDialog";
import { RelativeTime } from "@/components/common/RelativeTime";
import { TaskCard } from "@/components/tasks/TaskCard";

export function ProjectDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const project = useProjectStore((s) => s.activeProject);
  const fetchProject = useProjectStore((s) => s.fetchProject);
  const deleteProject = useProjectStore((s) => s.deleteProject);
  const conversations = useChatStore((s) => s.conversations);
  const selectChat = useChatStore((s) => s.selectChat);
  const newChat = useChatStore((s) => s.newChat);
  const setActiveProjectId = useChatStore((s) => s.setActiveProjectId);
  const [tasks, setTasks] = useState<TaskSummary[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!id) return;
    setNotFound(false);
    setTasks(null);
    fetchProject(id).catch(() => setNotFound(true));
    tasksApi
      .list({ projectId: id, limit: 50 })
      .then(setTasks)
      .catch(() => setTasks([]));
  }, [id, fetchProject]);

  if (notFound) {
    return (
      <div className="mx-auto max-w-3xl p-6 text-center">
        <p className="text-sm text-gray-600">Project not found.</p>
        <Link to="/projects" className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline">Back to projects</Link>
      </div>
    );
  }
  if (!project || project.id !== id) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-6" aria-hidden>
        <div className="h-6 w-1/3 animate-pulse rounded bg-gray-200" />
        <div className="h-32 animate-pulse rounded-xl bg-gray-100" />
      </div>
    );
  }

  const chats = conversations.filter((c) => c.projectId === project.id);
  const chatHere = () => {
    newChat();
    setActiveProjectId(project.id);
    navigate("/");
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      <button
        type="button"
        onClick={() => navigate("/projects")}
        className="inline-flex items-center gap-1 rounded text-sm text-gray-500 hover:text-gray-800 focus-visible:outline-2 focus-visible:outline-blue-500"
      >
        <ArrowLeft size={14} aria-hidden /> Projects
      </button>

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-xl font-semibold text-gray-900">
            <FolderGit2 size={20} className="text-gray-400" aria-hidden /> {project.name}
          </h2>
          <p className="mt-1 font-mono text-xs text-gray-500">{project.local_path}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={chatHere}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            <MessageSquare size={14} aria-hidden /> Chat about this project
          </button>
          <button
            type="button"
            onClick={() => setConfirming(true)}
            aria-label={`Delete ${project.name}`}
            className="rounded-lg border border-gray-300 p-2 text-gray-500 hover:border-red-300 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </header>

      <dl className="grid grid-cols-2 gap-4 rounded-xl border border-gray-200 bg-white p-4 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-gray-500">Stack</dt>
          <dd className="mt-0.5 text-gray-800">{project.stack.length ? project.stack.join(", ") : "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Preferred agent</dt>
          <dd className="mt-0.5 inline-flex items-center gap-1 text-gray-800">
            <Bot size={13} aria-hidden /> {agentLabel(project.preferred_agent) ?? "Automatic"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Repository</dt>
          <dd className="mt-0.5 inline-flex items-center gap-1 truncate text-gray-800">
            <GitBranch size={13} aria-hidden /> {project.github_repo ?? "Local only"} ({project.default_branch})
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Added</dt>
          <dd className="mt-0.5 text-gray-800"><RelativeTime iso={project.created_at} /></dd>
        </div>
      </dl>

      {project.instructions && (
        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Instructions for agents</h3>
          <p className="whitespace-pre-wrap text-sm text-gray-700">{project.instructions}</p>
        </section>
      )}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-gray-700">Tasks {tasks && `(${tasks.length})`}</h3>
        {tasks === null ? (
          <div className="h-16 animate-pulse rounded-xl bg-gray-100" aria-hidden />
        ) : tasks.length === 0 ? (
          <p className="rounded-xl border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-500">
            No tasks have run in this project yet.
          </p>
        ) : (
          <div className="space-y-2">{tasks.map((t) => <TaskCard key={t.id} task={t} />)}</div>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-gray-700">Chats ({chats.length})</h3>
        {chats.length === 0 ? (
          <p className="rounded-xl border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-500">
            No chats scoped to this project yet.
          </p>
        ) : (
          <ul className="divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
            {chats.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => {
                    selectChat(c.id);
                    navigate("/");
                  }}
                  className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-sm hover:bg-gray-50"
                >
                  <span className="truncate text-gray-800">{c.title}</span>
                  <RelativeTime iso={c.updatedAt} className="shrink-0 text-xs text-gray-400" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {confirming && (
        <ConfirmDeleteDialog
          name={project.name}
          title={`Delete project “${project.name}”?`}
          description={<>Files on disk are not touched, and tasks keep their history.</>}
          onConfirm={async () => {
            await deleteProject(project.id);
            navigate("/projects");
          }}
          onClose={() => setConfirming(false)}
        />
      )}
    </div>
  );
}
