import { useEffect } from "react";
import { useEventStore } from "@/store/eventStore";
import { useTaskStore } from "@/store/taskStore";
import { useApprovalStore } from "@/store/approvalStore";
import type { SSEEvent } from "@/api/types";

export function useSSE(backendUrl: string) {
  const connect = useEventStore((s) => s.connect);
  const disconnect = useEventStore((s) => s.disconnect);

  useEffect(() => {
    // Override addEvent to also route events to task/approval stores
    const originalAddEvent = useEventStore.getState().addEvent;
    useEventStore.setState({
      addEvent: (event: SSEEvent) => {
        originalAddEvent(event);
        useTaskStore.getState().handleEvent(event);
        useApprovalStore.getState().handleEvent(event);
      },
    });

    connect(backendUrl);

    return () => {
      disconnect();
      useEventStore.setState({ addEvent: originalAddEvent });
    };
  }, [backendUrl, connect, disconnect]);
}
