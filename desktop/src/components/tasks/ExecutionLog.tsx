import type { AgentExecution } from "@/api/types";
import { agentLabel } from "@/lib/taskStatus";
import { RelativeTime } from "@/components/common/RelativeTime";
import { TaskStatusBadge } from "./TaskStatusBadge";

function Log({ label, text, tone, open }: { label: string; text: string; tone: "out" | "err"; open?: boolean }) {
  return (
    <details className="mt-2" open={open}>
      <summary className={`cursor-pointer text-xs ${tone === "err" ? "text-red-600" : "text-gray-600"}`}>
        {label} <span className="text-gray-400">({text.split("\n").length} lines)</span>
      </summary>
      <pre
        className={`mt-1 max-h-80 overflow-auto rounded-lg bg-gray-900 p-3 text-xs ${
          tone === "err" ? "text-red-300" : "text-gray-100"
        }`}
      >
        {text}
      </pre>
    </details>
  );
}

export function ExecutionLog({ executions }: { executions: AgentExecution[] }) {
  if (executions.length === 0) {
    return <p className="text-sm text-gray-500">No agent has run this task yet.</p>;
  }

  return (
    <div className="space-y-3">
      {executions.map((exec, i) => (
        <div key={exec.id} className="rounded-lg border border-gray-200 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-gray-800">
              {agentLabel(exec.agent_name)}
              <span className="ml-2 text-xs font-normal text-gray-400">Attempt {executions.length - i}</span>
            </span>
            <TaskStatusBadge status={exec.status} />
          </div>
          <p className="mt-1 text-xs text-gray-500">
            {exec.started_at && <RelativeTime iso={exec.started_at} />}
            {exec.duration_ms != null && <> · {(exec.duration_ms / 1000).toFixed(1)}s</>}
            {exec.exit_code != null && <> · exit code {exec.exit_code}</>}
          </p>
          {exec.error && <p className="mt-1 text-xs text-red-600">{exec.error}</p>}
          {exec.stdout && <Log label="Output" text={exec.stdout} tone="out" open={i === 0} />}
          {exec.stderr && <Log label="Errors" text={exec.stderr} tone="err" />}
        </div>
      ))}
    </div>
  );
}
