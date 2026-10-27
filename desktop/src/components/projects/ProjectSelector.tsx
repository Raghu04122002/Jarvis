import { useEffect } from "react";
import { useProjectStore } from "@/store/projectStore";
import { useChatStore } from "@/store/chatStore";

export function ProjectSelector() {
  const projects = useProjectStore((s) => s.projects);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const activeProjectId = useChatStore((s) => s.activeProjectId);
  const setActiveProjectId = useChatStore((s) => s.setActiveProjectId);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return (
    <select
      value={activeProjectId ?? ""}
      onChange={(e) => setActiveProjectId(e.target.value || null)}
      className="w-full bg-gray-800 text-gray-200 text-sm rounded px-2 py-1 border border-gray-600 focus:outline-none"
    >
      <option value="">No project</option>
      {projects.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  );
}
