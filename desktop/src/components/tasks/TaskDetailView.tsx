import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTaskStore } from "@/store/taskStore";
import { TaskStatusBadge } from "./TaskStatusBadge";
import { TaskSteps } from "./TaskSteps";
import { ExecutionLog } from "./ExecutionLog";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { formatDate } from "@/lib/formatters";

export function TaskDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const task = useTaskStore((s) => s.currentTask);
  const steps = useTaskStore((s) => s.steps);
  const executions = useTaskStore((s) => s.executions);
  const loading = useTaskStore((s) => s.loading);
  const fetchTask = useTaskStore((s) => s.fetchTask);
  const fetchSteps = useTaskStore((s) => s.fetchSteps);
  const fetchExecutions = useTaskStore((s) => s.fetchExecutions);
  const cancelTask = useTaskStore((s) => s.cancelTask);
  const retryTask = useTaskStore((s) => s.retryTask);
  const dispatchTask = useTaskStore((s) => s.dispatchTask);

  useEffect(() => {
    if (id) {
      fetchTask(id);
      fetchSteps(id);
      fetchExecutions(id);
    }
  }, [id, fetchTask, fetchSteps, fetchExecutions]);

  if (loading && !task) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="p-6 text-center text-gray-400">Task not found</div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate("/tasks")}
        className="text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        ← Back to tasks
      </button>

      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-4">
        <div className="flex items-start justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-800">{task.title}</h2>
          <TaskStatusBadge status={task.status} />
        </div>

        <p className="text-sm text-gray-600 mb-3">{task.request}</p>

        {task.description && (
          <p className="text-sm text-gray-500 mb-3">{task.description}</p>
        )}

        <div className="flex gap-4 text-xs text-gray-400 mb-4">
          <span>Priority: {task.priority}</span>
          <span>Created: {formatDate(task.created_at)}</span>
          {task.started_at && <span>Started: {formatDate(task.started_at)}</span>}
          {task.completed_at && (
            <span>Completed: {formatDate(task.completed_at)}</span>
          )}
        </div>

        {task.plan.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-1">Plan</h3>
            <ol className="text-sm text-gray-600 list-decimal pl-5 space-y-0.5">
              {task.plan.map((step, i) => (
                <li
                  key={i}
                  className={
                    task.current_step === i ? "font-semibold text-blue-600" : ""
                  }
                >
                  {step}
                </li>
              ))}
            </ol>
          </div>
        )}

        {task.result && (
          <div className="bg-green-50 border border-green-200 rounded p-3 mb-4">
            <h3 className="text-xs font-semibold text-green-700 mb-1">
              Result
            </h3>
            <p className="text-sm text-green-800 whitespace-pre-wrap">
              {task.result}
            </p>
          </div>
        )}

        {task.error && (
          <div className="bg-red-50 border border-red-200 rounded p-3 mb-4">
            <h3 className="text-xs font-semibold text-red-700 mb-1">Error</h3>
            <p className="text-sm text-red-800">{task.error}</p>
          </div>
        )}

        <div className="flex gap-2">
          {task.status === "planning" && (
            <button
              onClick={() => dispatchTask(task.id)}
              className="px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700"
            >
              Start Execution
            </button>
          )}
          {["running", "planning", "waiting_for_approval"].includes(
            task.status,
          ) && (
            <button
              onClick={() => cancelTask(task.id)}
              className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700"
            >
              Cancel
            </button>
          )}
          {task.status === "failed" && (
            <button
              onClick={() => retryTask(task.id)}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Retry
            </button>
          )}
        </div>
      </div>

      <div className="space-y-4">
        <TaskSteps steps={steps} />
        <ExecutionLog executions={executions} />
      </div>
    </div>
  );
}
