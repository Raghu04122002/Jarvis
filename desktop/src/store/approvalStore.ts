import { create } from "zustand";
import { approvalsApi } from "@/api/approvals";
import type { ApprovalSummary, SSEEvent } from "@/api/types";

interface ApprovalState {
  pending: ApprovalSummary[];
  history: ApprovalSummary[];
  loaded: boolean;
  error: string | null;
  deciding: Record<string, "approve" | "reject">;
  fetchPending: () => Promise<void>;
  fetchHistory: () => Promise<void>;
  approve: (id: string, reason?: string) => Promise<void>;
  reject: (id: string, reason?: string) => Promise<void>;
  handleEvent: (event: SSEEvent) => void;
}

export const useApprovalStore = create<ApprovalState>((set, get) => {
  const decide = async (id: string, kind: "approve" | "reject", reason?: string) => {
    set((s) => ({ deciding: { ...s.deciding, [id]: kind } }));
    try {
      const decision = { decided_by: "user", reason: reason || undefined };
      if (kind === "approve") await approvalsApi.approve(id, decision);
      else await approvalsApi.reject(id, decision);
      // Optimistically drop it from the pending list; the refresh confirms.
      set((s) => ({ pending: s.pending.filter((a) => a.id !== id) }));
      void get().fetchPending();
      void get().fetchHistory();
    } finally {
      set((s) => {
        const { [id]: _done, ...rest } = s.deciding;
        return { deciding: rest };
      });
    }
  };

  return {
    pending: [],
    history: [],
    loaded: false,
    error: null,
    deciding: {},
    fetchPending: async () => {
      try {
        const pending = await approvalsApi.list("pending");
        set({ pending, loaded: true, error: null });
      } catch (e) {
        set({ loaded: true, error: e instanceof Error ? e.message : "Couldn't load approvals" });
      }
    },
    fetchHistory: async () => {
      try {
        const all = await approvalsApi.list();
        set({ history: all.filter((a) => a.status !== "pending").slice(0, 20) });
      } catch {
        // History is secondary; the pending list reports errors.
      }
    },
    approve: (id, reason) => decide(id, "approve", reason),
    reject: (id, reason) => decide(id, "reject", reason),
    handleEvent: (event) => {
      if (event.type.startsWith("approval_")) {
        void get().fetchPending();
        void get().fetchHistory();
      }
    },
  };
});
