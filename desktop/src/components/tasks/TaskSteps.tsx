import type { TaskStep } from "@/api/types";
import { StatusDot } from "@/components/common/StatusDot";

export function TaskSteps({ steps }: { steps: TaskStep[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-gray-400">No steps yet</p>;
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700">Steps</h3>
      {steps.map((step) => (
        <div
          key={step.id}
          className="flex items-start gap-2 p-2 rounded bg-gray-50"
        >
          <StatusDot status={step.status} />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-800">{step.description}</p>
            {step.result && (
              <p className="text-xs text-gray-500 mt-1 truncate">
                {step.result}
              </p>
            )}
            {step.error && (
              <p className="text-xs text-red-500 mt-1">{step.error}</p>
            )}
          </div>
          <span className="text-xs text-gray-400 whitespace-nowrap">
            {step.status}
          </span>
        </div>
      ))}
    </div>
  );
}
