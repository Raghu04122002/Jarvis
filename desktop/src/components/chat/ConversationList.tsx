import { useEffect, useRef, useState } from "react";
import { Check, MessageSquare, Pencil, Trash2, X } from "lucide-react";
import { useChatStore, type Conversation } from "@/store/chatStore";
import { RelativeTime } from "@/components/common/RelativeTime";

function Row({ conv, active }: { conv: Conversation; active: boolean }) {
  const selectChat = useChatStore((s) => s.selectChat);
  const renameChat = useChatStore((s) => s.renameChat);
  const deleteChat = useChatStore((s) => s.deleteChat);
  const streaming = useChatStore((s) => s.streamingId === conv.id);
  const [mode, setMode] = useState<"view" | "rename" | "confirm">("view");
  const [draft, setDraft] = useState(conv.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (mode === "rename") inputRef.current?.select();
  }, [mode]);

  const saveRename = () => {
    renameChat(conv.id, draft);
    setMode("view");
  };

  if (mode === "rename") {
    return (
      <li className="flex items-center gap-1 rounded-lg bg-white px-2 py-1.5 ring-1 ring-blue-300">
        <input
          ref={inputRef}
          value={draft}
          aria-label="Chat name"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") saveRename();
            if (e.key === "Escape") setMode("view");
          }}
          onBlur={saveRename}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
      </li>
    );
  }

  if (mode === "confirm") {
    return (
      <li className="flex items-center gap-1 rounded-lg bg-red-50 px-2 py-1.5 text-sm">
        <span className="flex-1 truncate text-red-700">Delete this chat?</span>
        <button
          type="button"
          aria-label="Confirm delete"
          onClick={() => deleteChat(conv.id)}
          className="rounded p-1 text-red-600 hover:bg-red-100"
          autoFocus
        >
          <Check size={14} />
        </button>
        <button
          type="button"
          aria-label="Cancel delete"
          onClick={() => setMode("view")}
          className="rounded p-1 text-gray-500 hover:bg-gray-200"
        >
          <X size={14} />
        </button>
      </li>
    );
  }

  return (
    <li
      className={`group relative flex items-center rounded-lg ${
        active ? "bg-gray-200" : "hover:bg-gray-100"
      }`}
    >
      <button
        type="button"
        onClick={() => selectChat(conv.id)}
        aria-current={active ? "true" : undefined}
        className="min-w-0 flex-1 px-2 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-blue-500"
      >
        <span className="flex items-center gap-1.5 truncate text-sm text-gray-800">
          {streaming && (
            <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-blue-500" />
          )}
          <span className="truncate">{conv.title}</span>
        </span>
        <RelativeTime iso={conv.updatedAt} className="text-[11px] text-gray-400" />
      </button>
      <div className="absolute right-1 hidden items-center gap-0.5 group-focus-within:flex group-hover:flex">
        <button
          type="button"
          aria-label={`Rename ${conv.title}`}
          title="Rename"
          onClick={() => {
            setDraft(conv.title);
            setMode("rename");
          }}
          className="rounded p-1 text-gray-500 hover:bg-gray-300 hover:text-gray-800"
        >
          <Pencil size={13} />
        </button>
        <button
          type="button"
          aria-label={`Delete ${conv.title}`}
          title="Delete"
          onClick={() => setMode("confirm")}
          className="rounded p-1 text-gray-500 hover:bg-gray-300 hover:text-red-600"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </li>
  );
}

export function ConversationList() {
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeId);
  const sorted = [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

  if (sorted.length === 0) {
    return (
      <div className="flex flex-col items-center px-4 py-8 text-center text-xs text-gray-400">
        <MessageSquare size={20} className="mb-2" />
        Your chats appear here.
      </div>
    );
  }

  return (
    <ul className="space-y-0.5 p-2" aria-label="Past chats">
      {sorted.map((c) => (
        <Row key={c.id} conv={c} active={c.id === activeId} />
      ))}
    </ul>
  );
}
