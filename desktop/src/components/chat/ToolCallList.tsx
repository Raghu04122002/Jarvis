import { useState } from "react";
import { AlertCircle, Check, ChevronRight, Loader2 } from "lucide-react";
import type { ToolCall } from "@/api/types";

function ToolCallItem({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);
  const args = Object.entries(call.args ?? {})
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return (
    <li className="rounded-md border border-gray-200 bg-gray-50 text-xs">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-gray-600 hover:text-gray-900 focus-visible:outline-2 focus-visible:outline-blue-500"
      >
        <ChevronRight size={14} className={`shrink-0 transition-transform ${open ? "rotate-90" : ""}`} />
        {call.status === "running" ? (
          <Loader2 size={14} className="shrink-0 animate-spin text-blue-500" aria-label="Running" />
        ) : call.status === "error" ? (
          <AlertCircle size={14} className="shrink-0 text-red-500" aria-label="Failed" />
        ) : (
          <Check size={14} className="shrink-0 text-green-600" aria-label="Done" />
        )}
        <span className="font-medium">{call.label || call.name}</span>
        {args && <span className="truncate text-gray-400">{args}</span>}
      </button>
      {open && (
        <pre className="max-h-64 overflow-auto border-t border-gray-200 px-2.5 py-2 whitespace-pre-wrap text-gray-700">
          {call.status === "running" ? "Running…" : call.output || "(no output)"}
        </pre>
      )}
    </li>
  );
}

export function ToolCallList({ calls }: { calls: ToolCall[] }) {
  if (calls.length === 0) return null;
  return (
    <ul className="mb-2 space-y-1" aria-label="Steps Jarvis took">
      {calls.map((c) => (
        <ToolCallItem key={c.id} call={c} />
      ))}
    </ul>
  );
}
