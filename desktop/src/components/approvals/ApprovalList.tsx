import { useEffect, useState } from "react";
import { useApprovalStore } from "@/store/approvalStore";
import { approvalsApi } from "@/api/approvals";
import type { ApprovalRequestFull } from "@/api/types";
import { ApprovalDialog } from "./ApprovalDialog";
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge";
import { formatRelativeTime } from "@/lib/formatters";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";

export function ApprovalList() {
  const pending = useApprovalStore((s) => s.pending);
  const loading = useApprovalStore((s) => s.loading);
  const fetchPending = useApprovalStore((s) => s.fetchPending);
  const [selected, setSelected] = useState<ApprovalRequestFull | null>(null);

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  const openDetail = async (id: string) => {
    const full = await approvalsApi.get(id);
    setSelected(full);
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">
        Pending Approvals
      </h2>

      {loading && pending.length === 0 ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : pending.length === 0 ? (
        <p className="text-gray-400 text-center py-12">
          No pending approvals
        </p>
      ) : (
        <div className="space-y-2">
          {pending.map((item) => (
            <button
              key={item.id}
              onClick={() => openDetail(item.id)}
              className="w-full text-left p-4 bg-white border border-gray-200 rounded-lg hover:border-orange-300 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-gray-800">
                    {item.tool_name}
                  </span>
                  <span className="text-sm text-gray-500 ml-2">
                    {item.operation}
                  </span>
                </div>
                <TaskStatusBadge status={item.status} />
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Task: {item.task_id} · {formatRelativeTime(item.created_at)}
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <ApprovalDialog
          approval={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
