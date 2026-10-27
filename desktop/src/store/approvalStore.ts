import { create } from "zustand";
import { approvalsApi } from "@/api/approvals";
import type { ApprovalSummary, SSEEvent } from "@/api/types";

interface ApprovalState {
  pending: ApprovalSummary[];
  loading: boolean;
  fetchPending: () => Promise<void>;
  approve: (id: string, reason?: string) => Promise<void>;
  reject: (id: string, reason?: string) => Promise<void>;
  handleEvent: (event: SSEEvent) => void;
}

export const useApprovalStore = create<ApprovalState>((set, get) => ({
  pending: [],
  loading: false,

  fetchPending: async () => {
    set({ loading: true });
    try {
      const pending = await approvalsApi.list("pending");
      set({ pending, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  approve: async (id, reason) => {
    await approvalsApi.approve(id, { reason });
    get().fetchPending();
  },

  reject: async (id, reason) => {
    await approvalsApi.reject(id, { reason });
    get().fetchPending();
  },

  handleEvent: (event) => {
    if (event.type.startsWith("approval_")) {
      get().fetchPending();
    }
  },
}));
