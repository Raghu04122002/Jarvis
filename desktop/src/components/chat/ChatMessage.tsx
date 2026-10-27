import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Pencil, RefreshCw } from "lucide-react";
import { useChatStore, type ChatMessage as ChatMsg } from "@/store/chatStore";
import { CopyButton, Markdown } from "@/components/common/Markdown";
import { RelativeTime } from "@/components/common/RelativeTime";
import { ToolCallList } from "./ToolCallList";

const actionBtn =
  "inline-flex items-center gap-1 rounded px-1.5 py-1 text-xs text-gray-500 hover:bg-gray-200 hover:text-gray-800 disabled:opacity-40 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-blue-500";

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1" aria-label="Jarvis is typing">
      {[0, 150, 300].map((d) => (
        <span
          key={d}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
          style={{ animationDelay: `${d}ms` }}
        />
      ))}
    </span>
  );
}

function UserMessage({ message }: { message: ChatMsg }) {
  const busy = useChatStore((s) => s.streamingId !== null);
  const editAndResend = useChatStore((s) => s.editAndResend);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing && ref.current) {
      ref.current.focus();
      ref.current.style.height = "auto";
      ref.current.style.height = `${ref.current.scrollHeight}px`;
    }
  }, [editing]);

  const submit = () => {
    setEditing(false);
    if (draft.trim() && draft.trim() !== message.content) void editAndResend(message.id, draft);
  };

  return (
    <div className="group mb-4 flex flex-col items-end">
      {editing ? (
        <div className="w-full max-w-[85%] rounded-2xl border border-blue-300 bg-white p-2">
          <textarea
            ref={ref}
            value={draft}
            aria-label="Edit message"
            onChange={(e) => {
              setDraft(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${e.target.scrollHeight}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              } else if (e.key === "Escape") {
                setEditing(false);
                setDraft(message.content);
              }
            }}
            className="w-full resize-none text-sm outline-none"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setEditing(false);
                setDraft(message.content);
              }}
              className="rounded px-3 py-1 text-xs text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={submit}
              className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700"
            >
              Send
            </button>
          </div>
        </div>
      ) : (
        <div className="max-w-[85%] rounded-2xl bg-gray-800 px-4 py-2 text-sm whitespace-pre-wrap text-white">
          {message.content}
        </div>
      )}
      <div className="mt-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        <RelativeTime iso={message.createdAt} className="mr-1 text-[11px] text-gray-400" />
        <CopyButton text={message.content} label="Copy message" />
        <button
          type="button"
          aria-label="Edit and resend"
          title="Edit and resend"
          disabled={busy}
          onClick={() => {
            setDraft(message.content);
            setEditing(true);
          }}
          className={actionBtn}
        >
          <Pencil size={14} />
        </button>
      </div>
    </div>
  );
}

function AssistantMessage({ message, isLast }: { message: ChatMsg; isLast: boolean }) {
  const busy = useChatStore((s) => s.streamingId !== null);
  const regenerate = useChatStore((s) => s.regenerate);
  const streaming = message.status === "streaming";
  const tools = message.toolCalls ?? [];

  return (
    <div className="group mb-4 flex flex-col items-start">
      <div
        className={`w-full rounded-2xl border px-4 py-3 text-gray-800 ${
          message.status === "error" ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"
        }`}
      >
        <ToolCallList calls={tools} />
        {message.content ? (
          <Markdown content={message.content} />
        ) : streaming ? (
          tools.some((t) => t.status === "running") ? null : <TypingDots />
        ) : (
          <p className="text-sm text-gray-400 italic">No response.</p>
        )}
        {message.status === "stopped" && (
          <p className="mt-2 text-xs text-gray-400 italic">Stopped.</p>
        )}
        {message.taskId && (
          <div className="mt-3 border-t border-gray-100 pt-2">
            <Link
              to={`/tasks/${message.taskId}`}
              className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline"
            >
              <ExternalLink size={12} />
              View task{message.taskTitle ? `: ${message.taskTitle}` : ""}
            </Link>
            {message.plan && message.plan.length > 0 && (
              <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-xs text-gray-600">
                {message.plan.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
      {!streaming && (
        <div className="mt-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
          <RelativeTime iso={message.createdAt} className="mr-1 text-[11px] text-gray-400" />
          {message.content && <CopyButton text={message.content} label="Copy message" />}
          {isLast && (
            <button
              type="button"
              aria-label="Regenerate response"
              title="Regenerate"
              disabled={busy}
              onClick={() => void regenerate(message.id)}
              className={actionBtn}
            >
              <RefreshCw size={14} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function ChatMessage({ message, isLast }: { message: ChatMsg; isLast: boolean }) {
  return message.role === "user" ? (
    <UserMessage message={message} />
  ) : (
    <AssistantMessage message={message} isLast={isLast} />
  );
}
