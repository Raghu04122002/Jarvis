import type { AgentExecution } from "@/api/types";
import { TaskStatusBadge } from "./TaskStatusBadge";

export function ExecutionLog({
  executions,
}: {
  executions: AgentExecution[];
}) {
  if (executions.length === 0) {
    return <p className="text-sm text-gray-400">No executions yet</p>;
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">
        Agent Executions
      </h3>
      {executions.map((exec) => (
        <div key={exec.id} className="border border-gray-200 rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-800">
              {exec.agent_name}
            </span>
            <TaskStatusBadge status={exec.status} />
          </div>
          {exec.duration_ms != null && (
            <p className="text-xs text-gray-500 mb-1">
              Duration: {(exec.duration_ms / 1000).toFixed(1)}s
            </p>
          )}
          {exec.stdout && (
            <details className="mt-2">
              <summary className="text-xs text-gray-500 cursor-pointer">
                stdout
              </summary>
              <pre className="mt-1 text-xs bg-gray-900 text-green-400 p-2 rounded overflow-x-auto max-h-60">
                {exec.stdout}
              </pre>
            </details>
          )}
          {exec.stderr && (
            <details className="mt-2">
              <summary className="text-xs text-red-500 cursor-pointer">
                stderr
              </summary>
              <pre className="mt-1 text-xs bg-gray-900 text-red-400 p-2 rounded overflow-x-auto max-h-60">
                {exec.stderr}
              </pre>
            </details>
          )}
          {exec.error && (
            <p className="text-xs text-red-500 mt-1">{exec.error}</p>
          )}
        </div>
      ))}
    </div>
  );
}
