import { create } from "zustand";
import { tasksApi } from "@/api/tasks";
import type { ChatResponse } from "@/api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  taskId?: string;
  plan?: string[];
  timestamp: string;
}

interface ChatState {
  messages: ChatMessage[];
  sending: boolean;
  activeProjectId: string | null;
  setActiveProjectId: (id: string | null) => void;
  sendMessage: (text: string, onReply?: (content: string) => void) => Promise<void>;
  clearMessages: () => void;
}

let messageCounter = 0;

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  sending: false,
  activeProjectId: null,

  setActiveProjectId: (id) => set({ activeProjectId: id }),

  sendMessage: async (text: string, onReply?: (content: string) => void) => {
    const userMsg: ChatMessage = {
      id: `msg-${++messageCounter}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    set((s) => ({ messages: [...s.messages, userMsg], sending: true }));

    try {
      const resp: ChatResponse = await tasksApi.chat({
        message: text,
        project_id: get().activeProjectId ?? undefined,
      });

      const assistantMsg: ChatMessage = {
        id: `msg-${++messageCounter}`,
        role: "assistant",
        content: resp.answer || resp.message,
        taskId: resp.task_id,
        plan: resp.plan,
        timestamp: new Date().toISOString(),
      };

      set((s) => ({ messages: [...s.messages, assistantMsg], sending: false }));

      if (onReply && assistantMsg.content) {
        onReply(assistantMsg.content);
      }
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: `msg-${++messageCounter}`,
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
        timestamp: new Date().toISOString(),
      };

      set((s) => ({ messages: [...s.messages, errorMsg], sending: false }));
    }
  },

  clearMessages: () => set({ messages: [] }),
}));
