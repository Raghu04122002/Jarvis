import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useEventStore } from "@/store/eventStore";
import type { SSEEvent } from "@/api/types";

const str = (v: unknown): string => (typeof v === "string" ? v : "");

/**
 * Toasts for the things worth interrupting for: a task finishing or failing,
 * an approval request, and the backend connection dropping or coming back.
 */
export function useNotifications(): void {
  const navigate = useNavigate();

  useEffect(() => {
    const seen = new Set<string>();

    const onEvent = (e: SSEEvent) => {
      const key = `${e.type}:${e.task_id}:${e.timestamp}`;
      if (seen.has(key)) return;
      seen.add(key);

      const title = str(e.data.title) || "Task";
      const open = { label: "View", onClick: () => navigate(`/tasks/${e.task_id}`) };
      switch (e.type) {
        case "task_completed":
          toast.success(`Task finished: ${title}`, { action: open });
          break;
        case "task_failed":
          toast.error(`Task failed: ${title}`, {
            description: str(e.data.error) || undefined,
            action: open,
            duration: 10_000,
          });
          break;
        case "approval_requested":
          toast.warning("Approval needed", {
            description: [str(e.data.tool_name), str(e.data.operation)].filter(Boolean).join(" → ") || undefined,
            action: { label: "Review", onClick: () => navigate("/approvals") },
            duration: Infinity,
          });
          break;
      }
    };

    // Listen to new events only — the store keeps history we've already shown.
    let lastHead = useEventStore.getState().events[0];
    let wasConnected = useEventStore.getState().connected;
    let everConnected = wasConnected;

    return useEventStore.subscribe((s) => {
      if (s.events[0] !== lastHead) {
        const fresh: SSEEvent[] = [];
        for (const ev of s.events) {
          if (ev === lastHead) break;
          fresh.push(ev);
        }
        lastHead = s.events[0];
        fresh.reverse().forEach(onEvent);
      }

      if (s.connected !== wasConnected) {
        wasConnected = s.connected;
        if (!s.connected && everConnected) {
          toast.error("Connection to Jarvis lost", {
            id: "connection",
            description: "Retrying in the background…",
            duration: Infinity,
          });
        } else if (s.connected) {
          if (everConnected) toast.success("Connection restored", { id: "connection", duration: 3000 });
          everConnected = true;
        }
      }
    });
  }, [navigate]);
}
