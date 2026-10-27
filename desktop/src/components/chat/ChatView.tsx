import { useEffect, useRef, useState } from "react";
import { PanelLeftClose, PanelLeftOpen, SquarePen } from "lucide-react";
import { useActiveConversation, useChatStore } from "@/store/chatStore";
import { ChatHistory } from "./ChatHistory";
import { ChatInput, type ChatInputHandle } from "./ChatInput";
import { ConversationList } from "./ConversationList";

const PANEL_KEY = "jarvis_chat_panel_open";

export function ChatView() {
  const [panelOpen, setPanelOpen] = useState(
    () => localStorage.getItem(PANEL_KEY) !== "false",
  );
  const newChat = useChatStore((s) => s.newChat);
  const stop = useChatStore((s) => s.stop);
  const conv = useActiveConversation();
  const inputRef = useRef<ChatInputHandle>(null);

  useEffect(() => {
    localStorage.setItem(PANEL_KEY, String(panelOpen));
  }, [panelOpen]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [conv?.id]);

  // Cmd/Ctrl+K: new chat · "/": focus composer · Esc: stop generating.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        newChat();
        inputRef.current?.focus();
      } else if (e.key === "/" && !typing) {
        e.preventDefault();
        inputRef.current?.focus();
      } else if (e.key === "Escape" && !typing) {
        stop();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [newChat, stop]);

  return (
    <div className="flex h-full">
      {panelOpen && (
        <aside
          className="flex w-60 shrink-0 flex-col border-r border-gray-200 bg-gray-50"
          aria-label="Chat history"
        >
          <div className="flex items-center justify-between p-2">
            <button
              type="button"
              onClick={() => setPanelOpen(false)}
              aria-label="Hide chat history"
              title="Hide chat history"
              className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-200 hover:text-gray-800 focus-visible:outline-2 focus-visible:outline-blue-500"
            >
              <PanelLeftClose size={18} />
            </button>
            <button
              type="button"
              onClick={() => {
                newChat();
                inputRef.current?.focus();
              }}
              aria-label="New chat (⌘K)"
              title="New chat (⌘K)"
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-200 focus-visible:outline-2 focus-visible:outline-blue-500"
            >
              <SquarePen size={16} />
              New chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            <ConversationList />
          </div>
        </aside>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-11 shrink-0 items-center gap-1 px-2">
          {!panelOpen && (
            <>
              <button
                type="button"
                onClick={() => setPanelOpen(true)}
                aria-label="Show chat history"
                title="Show chat history"
                className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800 focus-visible:outline-2 focus-visible:outline-blue-500"
              >
                <PanelLeftOpen size={18} />
              </button>
              <button
                type="button"
                onClick={() => {
                  newChat();
                  inputRef.current?.focus();
                }}
                aria-label="New chat (⌘K)"
                title="New chat (⌘K)"
                className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-800 focus-visible:outline-2 focus-visible:outline-blue-500"
              >
                <SquarePen size={18} />
              </button>
            </>
          )}
          <h2 className="truncate px-1 text-sm font-medium text-gray-700">
            {conv && conv.messages.length > 0 ? conv.title : ""}
          </h2>
        </div>
        <ChatHistory onPickStarter={(p) => inputRef.current?.setText(p)} />
        <ChatInput ref={inputRef} />
      </div>
    </div>
  );
}
