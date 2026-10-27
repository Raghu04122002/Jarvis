import { create } from "zustand";
import { persist } from "zustand/middleware";
import { streamChat } from "@/api/chatStream";
import type { ChatStreamEvent, ChatTurn, ToolCall } from "@/api/types";

export type MessageStatus = "streaming" | "done" | "error" | "stopped";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Real creation time (ISO, UTC). Persisted, so it survives reloads. */
  createdAt: string;
  status?: MessageStatus;
  toolCalls?: ToolCall[];
  taskId?: string;
  taskTitle?: string;
  plan?: string[];
}

export interface Conversation {
  id: string;
  title: string;
  /** True once the user renamed it; stops auto-titling. */
  titleEdited?: boolean;
  /** Project the chat was last scoped to, if any. */
  projectId?: string | null;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

interface ChatState {
  conversations: Conversation[];
  activeId: string | null;
  /** Conversation currently streaming a reply, if any. */
  streamingId: string | null;
  activeProjectId: string | null;

  setActiveProjectId: (id: string | null) => void;
  newChat: () => void;
  selectChat: (id: string) => void;
  renameChat: (id: string, title: string) => void;
  deleteChat: (id: string) => void;
  sendMessage: (text: string, onReply?: (content: string) => void) => Promise<void>;
  stop: () => void;
  regenerate: (assistantMessageId: string) => Promise<void>;
  editAndResend: (userMessageId: string, text: string) => Promise<void>;
}

const MAX_HISTORY = 20;
const MAX_TURN_CHARS = 20000;

let abortController: AbortController | null = null;

const uid = (p: string) =>
  `${p}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const now = () => new Date().toISOString();

/** Short title from the first user message: first ~6 words, max 48 chars. */
export function autoTitle(text: string): string {
  const clean = text.replace(/\s+/g, " ").trim().replace(/[?!.]+$/, "");
  const words = clean.split(" ").slice(0, 6).join(" ");
  const t = words.length > 48 ? `${words.slice(0, 47)}…` : words;
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "New chat";
}

function historyFrom(messages: ChatMessage[]): ChatTurn[] {
  return messages
    .filter((m) => m.content.trim() && (m.role === "user" || m.status === "done"))
    .slice(-MAX_HISTORY)
    .map((m) => ({ role: m.role, content: m.content.slice(0, MAX_TURN_CHARS) }));
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => {
      const updateConv = (id: string, fn: (c: Conversation) => Conversation) =>
        set((s) => ({
          conversations: s.conversations.map((c) => (c.id === id ? fn(c) : c)),
        }));

      const updateMsg = (
        convId: string,
        msgId: string,
        fn: (m: ChatMessage) => ChatMessage,
      ) =>
        updateConv(convId, (c) => ({
          ...c,
          messages: c.messages.map((m) => (m.id === msgId ? fn(m) : m)),
        }));

      /** Replace the conversation's messages with prior + user, then stream a reply. */
      const runTurn = async (
        convId: string,
        prior: ChatMessage[],
        userMsg: ChatMessage,
        onReply?: (content: string) => void,
      ) => {
        if (get().streamingId) return;
        const assistant: ChatMessage = {
          id: uid("msg"),
          role: "assistant",
          content: "",
          createdAt: now(),
          status: "streaming",
          toolCalls: [],
        };
        updateConv(convId, (c) => ({
          ...c,
          title:
            !c.titleEdited && prior.length === 0 ? autoTitle(userMsg.content) : c.title,
          updatedAt: now(),
          messages: [...prior, userMsg, assistant],
        }));
        set({ streamingId: convId });

        const controller = new AbortController();
        abortController = controller;
        let finalContent = "";

        const onEvent = (ev: ChatStreamEvent) => {
          switch (ev.type) {
            case "token":
              updateMsg(convId, assistant.id, (m) => ({
                ...m,
                content: m.content + ev.text,
              }));
              break;
            case "tool_start":
              updateMsg(convId, assistant.id, (m) => ({
                ...m,
                toolCalls: [
                  ...(m.toolCalls ?? []),
                  {
                    id: ev.id,
                    name: ev.name,
                    label: ev.label,
                    args: ev.args,
                    status: "running",
                    output: "",
                  },
                ],
              }));
              break;
            case "tool_end":
              updateMsg(convId, assistant.id, (m) => ({
                ...m,
                toolCalls: (m.toolCalls ?? []).map((t) =>
                  t.id === ev.id
                    ? { ...t, status: ev.ok ? "done" : "error", output: ev.output }
                    : t,
                ),
              }));
              break;
            case "task_created":
              updateMsg(convId, assistant.id, (m) => ({
                ...m,
                taskId: ev.task_id,
                taskTitle: ev.title,
              }));
              break;
            case "done": {
              const r = ev.response;
              // The server's final answer is authoritative (e.g. unverified
              // links stripped), so it replaces the streamed text.
              finalContent = r.answer || r.message;
              updateMsg(convId, assistant.id, (m) => ({
                ...m,
                content: finalContent,
                status: r.status === "error" ? "error" : "done",
                taskId: r.task_id ?? m.taskId,
                plan: r.plan && r.plan.length > 0 ? r.plan : undefined,
                toolCalls: r.tool_calls?.length ? r.tool_calls : m.toolCalls,
              }));
              break;
            }
            case "error":
              updateMsg(convId, assistant.id, (m) => ({
                ...m,
                content: m.content ? `${m.content}\n\n${ev.message}` : ev.message,
                status: "error",
              }));
              break;
          }
        };

        try {
          await streamChat(
            {
              message: userMsg.content,
              project_id: get().activeProjectId ?? undefined,
              history: historyFrom(prior),
              conversation_id: convId,
            },
            onEvent,
            controller.signal,
          );
          // Stream closed without a done/error event.
          updateMsg(convId, assistant.id, (m) =>
            m.status === "streaming"
              ? { ...m, status: m.content ? "done" : "error", content: m.content || "No response." }
              : m,
          );
        } catch (err) {
          const aborted = controller.signal.aborted;
          updateMsg(convId, assistant.id, (m) => ({
            ...m,
            status: aborted ? "stopped" : "error",
            content: aborted
              ? m.content
              : `${m.content ? `${m.content}\n\n` : ""}Couldn't reach Jarvis: ${
                  err instanceof Error ? err.message : "unknown error"
                }`,
          }));
        } finally {
          if (abortController === controller) abortController = null;
          set({ streamingId: null });
          updateConv(convId, (c) => ({ ...c, updatedAt: now() }));
        }
        if (onReply && finalContent) onReply(finalContent);
      };

      return {
        conversations: [],
        activeId: null,
        streamingId: null,
        activeProjectId: null,

        setActiveProjectId: (id) => set({ activeProjectId: id }),

        newChat: () => {
          const active = get().conversations.find((c) => c.id === get().activeId);
          // Don't stack up empty chats.
          if (active && active.messages.length === 0) return;
          const conv: Conversation = {
            id: uid("chat"),
            title: "New chat",
            createdAt: now(),
            updatedAt: now(),
            messages: [],
          };
          set((s) => ({ conversations: [conv, ...s.conversations], activeId: conv.id }));
        },

        selectChat: (id) => set({ activeId: id }),

        renameChat: (id, title) => {
          const t = title.trim();
          if (!t) return;
          updateConv(id, (c) => ({ ...c, title: t, titleEdited: true }));
        },

        deleteChat: (id) => {
          if (get().streamingId === id) get().stop();
          set((s) => {
            const conversations = s.conversations.filter((c) => c.id !== id);
            return {
              conversations,
              activeId: s.activeId === id ? (conversations[0]?.id ?? null) : s.activeId,
            };
          });
        },

        sendMessage: async (text, onReply) => {
          const content = text.trim();
          if (!content || get().streamingId) return;
          let convId = get().activeId;
          if (!convId || !get().conversations.some((c) => c.id === convId)) {
            const conv: Conversation = {
              id: uid("chat"),
              title: "New chat",
              createdAt: now(),
              updatedAt: now(),
              messages: [],
            };
            set((s) => ({ conversations: [conv, ...s.conversations], activeId: conv.id }));
            convId = conv.id;
          }
          const scope = get().activeProjectId;
          if (scope) updateConv(convId, (c) => ({ ...c, projectId: scope }));
          const conv = get().conversations.find((c) => c.id === convId)!;
          const userMsg: ChatMessage = {
            id: uid("msg"),
            role: "user",
            content,
            createdAt: now(),
            status: "done",
          };
          await runTurn(convId, conv.messages, userMsg, onReply);
        },

        stop: () => abortController?.abort(),

        regenerate: async (assistantMessageId) => {
          const convId = get().activeId;
          const conv = get().conversations.find((c) => c.id === convId);
          if (!conv || get().streamingId) return;
          const i = conv.messages.findIndex((m) => m.id === assistantMessageId);
          const userMsg = conv.messages[i - 1];
          if (i < 1 || userMsg?.role !== "user") return;
          await runTurn(conv.id, conv.messages.slice(0, i - 1), userMsg);
        },

        editAndResend: async (userMessageId, text) => {
          const content = text.trim();
          const convId = get().activeId;
          const conv = get().conversations.find((c) => c.id === convId);
          if (!conv || !content || get().streamingId) return;
          const i = conv.messages.findIndex((m) => m.id === userMessageId);
          const original = conv.messages[i];
          if (!original || original.role !== "user") return;
          const userMsg: ChatMessage = {
            ...original,
            content,
            createdAt: now(),
          };
          await runTurn(conv.id, conv.messages.slice(0, i), userMsg);
        },
      };
    },
    {
      name: "jarvis-chats",
      version: 1,
      partialize: (s) => ({
        conversations: s.conversations,
        activeId: s.activeId,
        activeProjectId: s.activeProjectId,
      }),
      // A reload mid-stream leaves a half-written reply; mark it stopped.
      merge: (persisted, current) => {
        const p = (persisted ?? {}) as Partial<ChatState>;
        return {
          ...current,
          ...p,
          conversations: (p.conversations ?? []).map((c) => ({
            ...c,
            messages: c.messages.map((m) =>
              m.status === "streaming" ? { ...m, status: "stopped" as const } : m,
            ),
          })),
        };
      },
    },
  ),
);

export function useActiveConversation(): Conversation | undefined {
  return useChatStore((s) => s.conversations.find((c) => c.id === s.activeId));
}
