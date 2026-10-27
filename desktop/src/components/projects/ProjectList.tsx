import { useEffect, useState } from "react";
import { useProjectStore } from "@/store/projectStore";
import { ProjectForm } from "./ProjectForm";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { formatRelativeTime } from "@/lib/formatters";

export function ProjectList() {
  const projects = useProjectStore((s) => s.projects);
  const loading = useProjectStore((s) => s.loading);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const deleteProject = useProjectStore((s) => s.deleteProject);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-800">Projects</h2>
        <button
          onClick={() => setShowForm(true)}
          className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded hover:bg-gray-700"
        >
          New Project
        </button>
      </div>

      {showForm && (
        <div className="mb-4">
          <ProjectForm onClose={() => setShowForm(false)} />
        </div>
      )}

      {loading && projects.length === 0 ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : projects.length === 0 ? (
        <p className="text-gray-400 text-center py-12">No projects yet</p>
      ) : (
        <div className="space-y-2">
          {projects.map((project) => (
            <div
              key={project.id}
              className="p-4 bg-white border border-gray-200 rounded-lg"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-800">
                    {project.name}
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {project.local_path}
                  </p>
                  {project.stack.length > 0 && (
                    <div className="flex gap-1 mt-1">
                      {project.stack.map((s) => (
                        <span
                          key={s}
                          className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">
                    {formatRelativeTime(project.created_at)}
                  </span>
                  <button
                    onClick={() => deleteProject(project.id)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
