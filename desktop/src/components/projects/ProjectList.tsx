import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FolderGit2, MoreHorizontal, Plus, Trash2 } from "lucide-react";
import { useProjectStore } from "@/store/projectStore";
import type { ProjectSummary } from "@/api/types";
import { ConfirmDeleteDialog } from "@/components/common/ConfirmDeleteDialog";
import { RelativeTime } from "@/components/common/RelativeTime";
import { ProjectForm } from "./ProjectForm";

function RowMenu({ onDelete, label }: { onDelete: () => void; label: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={`More actions for ${label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          e.preventDefault();
          setOpen((o) => !o);
        }}
        className="rounded-md p-1.5 text-gray-400 opacity-0 transition-opacity hover:bg-gray-100 hover:text-gray-700 focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-blue-500 group-hover:opacity-100 aria-expanded:opacity-100"
      >
        <MoreHorizontal size={16} />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-10 mt-1 w-36 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
          <button
            type="button"
            role="menuitem"
            onClick={(e) => {
              e.preventDefault();
              setOpen(false);
              onDelete();
            }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-red-600 hover:bg-red-50"
          >
            <Trash2 size={14} aria-hidden /> Delete…
          </button>
        </div>
      )}
    </div>
  );
}

export function ProjectList() {
  const projects = useProjectStore((s) => s.projects);
  const loading = useProjectStore((s) => s.loading);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const deleteProject = useProjectStore((s) => s.deleteProject);
  const [showForm, setShowForm] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [toDelete, setToDelete] = useState<ProjectSummary | null>(null);

  useEffect(() => {
    void fetchProjects().finally(() => setLoaded(true));
  }, [fetchProjects]);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Projects</h2>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        >
          <Plus size={15} aria-hidden /> {showForm ? "Close" : "New project"}
        </button>
      </div>

      {showForm && (
        <div className="mb-4">
          <ProjectForm onClose={() => setShowForm(false)} />
        </div>
      )}

      {!loaded && loading ? (
        <div className="space-y-2" aria-hidden>
          {[0, 1, 2].map((i) => <div key={i} className="h-[72px] animate-pulse rounded-xl bg-gray-100" />)}
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center rounded-xl border border-dashed border-gray-300 px-6 py-12 text-center">
          <FolderGit2 size={26} className="text-gray-400" aria-hidden />
          <p className="mt-2 text-sm font-medium text-gray-800">No projects yet</p>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            Register a folder on your machine so Jarvis knows where to run coding agents. You can then scope a chat to it.
          </p>
          {!showForm && (
            <button type="button" onClick={() => setShowForm(true)} className="mt-3 text-sm font-medium text-blue-600 hover:underline">
              Add your first project
            </button>
          )}
        </div>
      ) : (
        <ul className="space-y-2">
          {projects.map((p) => (
            <li key={p.id} className="group relative">
              <Link
                to={`/projects/${p.id}`}
                className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 pr-12 hover:border-gray-300 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-blue-500"
              >
                <FolderGit2 size={18} className="shrink-0 text-gray-400" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-900">{p.name}</p>
                  <p className="truncate font-mono text-xs text-gray-500">{p.local_path}</p>
                  {p.stack.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {p.stack.map((s) => (
                        <span key={s} className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-600">{s}</span>
                      ))}
                    </div>
                  )}
                </div>
                <RelativeTime iso={p.created_at} className="shrink-0 text-xs text-gray-400" />
              </Link>
              <div className="absolute right-2 top-1/2 -translate-y-1/2">
                <RowMenu label={p.name} onDelete={() => setToDelete(p)} />
              </div>
            </li>
          ))}
        </ul>
      )}

      {toDelete && (
        <ConfirmDeleteDialog
          name={toDelete.name}
          title={`Delete project “${toDelete.name}”?`}
          description={
            <>
              This removes the project from Jarvis. Files in <code className="font-mono">{toDelete.local_path}</code> are
              not touched, and existing tasks keep their history.
            </>
          }
          onConfirm={() => deleteProject(toDelete.id)}
          onClose={() => setToDelete(null)}
        />
      )}
    </div>
  );
}
