import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useApprovalStore } from "@/store/approvalStore";

export function ApprovalBanner() {
  const pending = useApprovalStore((s) => s.pending);
  const fetchPending = useApprovalStore((s) => s.fetchPending);
  const approve = useApprovalStore((s) => s.approve);
  const reject = useApprovalStore((s) => s.reject);
  const navigate = useNavigate();

  useEffect(() => {
    fetchPending();
  }, [fetchPending]);

  if (pending.length === 0) return null;

  const first = pending[0]!;

  return (
    <div className="bg-orange-50 border-b border-orange-200 px-4 py-2 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-orange-600 font-medium text-sm">
          Approval needed:
        </span>
        <span className="text-sm text-gray-700">
          {first.tool_name} → {first.operation}
        </span>
        {pending.length > 1 && (
          <span className="text-xs text-gray-500">
            (+{pending.length - 1} more)
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => approve(first.id)}
          className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
        >
          Approve
        </button>
        <button
          onClick={() => reject(first.id)}
          className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
        >
          Reject
        </button>
        <button
          onClick={() => navigate("/approvals")}
          className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
        >
          View All
        </button>
      </div>
    </div>
  );
}
