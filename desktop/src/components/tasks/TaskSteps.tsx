import type { TaskStep } from "@/api/types";
import { StatusDot } from "@/components/common/StatusDot";

export function TaskSteps({ steps, plan = [] }: { steps: TaskStep[]; plan?: string[] }) {
  if (steps.length === 0) {
    if (plan.length === 0) return <p className="text-sm text-gray-500">No steps were planned for this task.</p>;
    return (
      <ol className="list-decimal space-y-1 pl-5 text-sm text-gray-700">
        {plan.map((p, i) => (
          <li key={i}>{p}</li>
        ))}
      </ol>
    );
  }

  return (
    <ol className="space-y-1.5">
      {steps.map((step) => (
        <li key={step.id} className="flex items-start gap-2.5 rounded-lg bg-gray-50 px-3 py-2">
          <span className="mt-1.5">
            <StatusDot status={step.status} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm text-gray-800">{step.description}</p>
            {step.result && <p className="mt-0.5 line-clamp-2 text-xs text-gray-500">{step.result}</p>}
            {step.error && <p className="mt-0.5 text-xs text-red-600">{step.error}</p>}
          </div>
          <span className="whitespace-nowrap text-xs capitalize text-gray-400">{step.status}</span>
        </li>
      ))}
    </ol>
  );
}
