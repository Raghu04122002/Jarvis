import { apiFetch } from "./client";
import type {
  ApprovalDecision,
  ApprovalRequestFull,
  ApprovalSummary,
} from "./types";

export const approvalsApi = {
  list(status?: string): Promise<ApprovalSummary[]> {
    const params = status ? `?status=${status}` : "";
    return apiFetch(`/approvals${params}`);
  },

  get(id: string): Promise<ApprovalRequestFull> {
    return apiFetch(`/approvals/${id}`);
  },

  approve(id: string, decision?: ApprovalDecision): Promise<ApprovalRequestFull> {
    return apiFetch(`/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify(decision ?? {}),
    });
  },

  reject(id: string, decision?: ApprovalDecision): Promise<ApprovalRequestFull> {
    return apiFetch(`/approvals/${id}/deny`, {
      method: "POST",
      body: JSON.stringify(decision ?? {}),
    });
  },
};
