import { useState, type FormEvent } from "react";
import { useProjectStore } from "@/store/projectStore";

export function ProjectForm({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [stack, setStack] = useState("");
  const createProject = useProjectStore((s) => s.createProject);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !localPath.trim()) return;
    setSubmitting(true);
    try {
      await createProject({
        name: name.trim(),
        local_path: localPath.trim(),
        stack: stack
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white border border-gray-200 rounded-lg p-4 space-y-3"
    >
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Name
        </label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-gray-500"
          required
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Local Path
        </label>
        <input
          value={localPath}
          onChange={(e) => setLocalPath(e.target.value)}
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-gray-500"
          required
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Stack (comma separated)
        </label>
        <input
          value={stack}
          onChange={(e) => setStack(e.target.value)}
          placeholder="python, fastapi, react"
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-gray-500"
        />
      </div>
      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded hover:bg-gray-700 disabled:opacity-50"
        >
          Create
        </button>
      </div>
    </form>
  );
}
