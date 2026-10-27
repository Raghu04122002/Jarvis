import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { useApprovalStore } from "@/store/approvalStore";
import type { ApprovalSummary, RiskLevel } from "@/api/types";
import { RelativeTime } from "@/components/common/RelativeTime";
import { TaskStatusBadge } from "@/components/tasks/TaskStatusBadge";

const RISK_STYLE: Record<RiskLevel, string> = {
  safe: "bg-green-100 text-green-800",
  requires_approval: "bg-amber-100 text-amber-800",
  blocked: "bg-red-100 text-red-800",
};
const RISK_LABEL: Record<RiskLevel, string> = {
  safe: "Low risk",
  requires_approval: "Needs review",
  blocked: "High risk",
};

function ApprovalCard({ item }: { item: ApprovalSummary }) {
  const risk: RiskLevel = item.risk_level ?? "requires_approval";
  const approve = useApprovalStore((s) => s.approve);
  const reject = useApprovalStore((s) => s.reject);
  const deciding = useApprovalStore((s) => s.deciding[item.id]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const act = async (fn: typeof approve) => {
    setError(null);
    try {
      await fn(item.id, reason.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't record the decision");
    }
  };

  return (
    <li className="rounded-xl border border-amber-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900">
            {item.tool_name} <span className="font-normal text-gray-500">→</span>{" "}
            <code className="rounded bg-gray-100 px-1 text-[13px]">{item.operation}</code>
          </p>
          {item.description && <p className="mt-1 text-sm text-gray-700">{item.description}</p>}
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${RISK_STYLE[risk]}`}>
          {RISK_LABEL[risk]}
        </span>
      </div>
      <p className="mt-2 text-xs text-gray-500">
        Requested <RelativeTime iso={item.created_at} />
        {item.task_id && (
          <>
            {" · for task "}
            <Link to={`/tasks/${item.task_id}`} className="font-mono text-blue-600 hover:underline">
              {item.task_id}
            </Link>
          </>
        )}
        {item.expires_at && (
          <>
            {" · expires "}
            <RelativeTime iso={item.expires_at} />
          </>
        )}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Note (optional)"
          aria-label={`Note for ${item.tool_name} ${item.operation}`}
          className="min-w-0 flex-1 rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
        />
        <button
          type="button"
          disabled={!!deciding}
          onClick={() => void act(reject)}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-blue-500"
        >
          <X size={14} aria-hidden /> {deciding === "reject" ? "Rejecting…" : "Reject"}
        </button>
        <button
          type="button"
          disabled={!!deciding}
          onClick={() => void act(approve)}
          className="inline-flex items-center gap-1 rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-blue-500"
        >
          <Check size={14} aria-hidden /> {deciding === "approve" ? "Approving…" : "Approve"}
        </button>
      </div>
      {error && <p role="alert" className="mt-2 text-xs text-red-600">{error}</p>}
    </li>
  );
}

export function ApprovalList() {
  const { pending, history, loaded, error, fetchPending, fetchHistory } = useApprovalStore();

  useEffect(() => {
    void fetchPending();
    void fetchHistory();
  }, [fetchPending, fetchHistory]);

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Approvals</h2>
        <p className="mt-1 text-sm text-gray-500">
          Agents pause here before risky actions such as deleting files, pushing code or running unknown commands.
        </p>
      </div>

      {error && (
        <div role="alert" className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <span>Couldn't load approvals: {error}</span>
          <button type="button" onClick={() => void fetchPending()} className="font-medium underline">Retry</button>
        </div>
      )}

      {!loaded ? (
        <div className="space-y-2" aria-hidden>
          {[0, 1].map((i) => <div key={i} className="h-32 animate-pulse rounded-xl bg-gray-100" />)}
        </div>
      ) : pending.length === 0 ? (
        <div className="flex flex-col items-center rounded-xl border border-dashed border-gray-300 px-6 py-12 text-center">
          <ShieldCheck size={28} className="text-green-500" aria-hidden />
          <p className="mt-2 text-sm font-medium text-gray-800">Nothing needs your approval</p>
          <p className="mt-1 max-w-sm text-sm text-gray-500">
            When an agent wants to do something risky, it will stop and wait here, and the sidebar will show a badge.
          </p>
        </div>
      ) : (
        <section aria-labelledby="pending-h">
          <h3 id="pending-h" className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-amber-700">
            <ShieldAlert size={15} aria-hidden /> Waiting for you ({pending.length})
          </h3>
          <ul className="space-y-3">
            {pending.map((a) => <ApprovalCard key={a.id} item={a} />)}
          </ul>
        </section>
      )}

      {history.length > 0 && (
        <section aria-labelledby="history-h">
          <h3 id="history-h" className="mb-2 text-sm font-semibold text-gray-700">Recent decisions</h3>
          <ul className="divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
            {history.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                <span className="min-w-0 truncate text-gray-700">
                  {a.tool_name} → <code className="text-[13px]">{a.operation}</code>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <RelativeTime iso={a.created_at} className="text-xs text-gray-400" />
                  <TaskStatusBadge status={a.status} />
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
