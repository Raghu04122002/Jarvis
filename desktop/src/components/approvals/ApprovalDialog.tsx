import { useState } from "react";
import type { ApprovalRequestFull } from "@/api/types";
import { useApprovalStore } from "@/store/approvalStore";
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge";

export function ApprovalDialog({
  approval,
  onClose,
}: {
  approval: ApprovalRequestFull;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const approve = useApprovalStore((s) => s.approve);
  const reject = useApprovalStore((s) => s.reject);

  const handleApprove = async () => {
    await approve(approval.id, reason || undefined);
    onClose();
  };

  const handleReject = async () => {
    await reject(approval.id, reason || undefined);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-lg max-w-md w-full p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">Approval Required</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        <div className="space-y-2 mb-4">
          <div className="flex justify-between">
            <span className="text-sm text-gray-500">Tool</span>
            <span className="text-sm font-medium">{approval.tool_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-gray-500">Operation</span>
            <span className="text-sm font-medium">{approval.operation}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-gray-500">Risk</span>
            <TaskStatusBadge status={approval.risk_level} />
          </div>
          {approval.description && (
            <p className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
              {approval.description}
            </p>
          )}
        </div>

        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason (optional)"
          rows={2}
          className="w-full border border-gray-300 rounded p-2 text-sm mb-3 focus:outline-none focus:border-gray-500"
        />

        <div className="flex gap-2 justify-end">
          <button
            onClick={handleReject}
            className="px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700"
          >
            Reject
          </button>
          <button
            onClick={handleApprove}
            className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
