import { useEffect, useRef } from "react";
import { CheckSquare, FolderGit2, ListTodo, Newspaper } from "lucide-react";
import { useActiveConversation } from "@/store/chatStore";
import { ChatMessage } from "./ChatMessage";

const STARTERS = [
  {
    icon: Newspaper,
    title: "Today's headlines",
    prompt: "What are today's top news headlines?",
  },
  {
    icon: ListTodo,
    title: "Check my tasks",
    prompt: "Which of my tasks are running or failed?",
  },
  {
    icon: FolderGit2,
    title: "My projects",
    prompt: "List my registered projects.",
  },
  {
    icon: CheckSquare,
    title: "Hand off coding work",
    prompt: "Add a dark mode toggle to the settings page",
  },
];

function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4">
      <h2 className="text-2xl font-semibold text-gray-800">What can I help with?</h2>
      <p className="mt-2 max-w-md text-center text-sm text-gray-500">
        Ask questions, search the web, or check on your tasks and projects. Real work, like
        code changes, becomes a task that a coding agent carries out.
      </p>
      <div className="mt-6 grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
        {STARTERS.map(({ icon: Icon, title, prompt }) => (
          <button
            key={title}
            type="button"
            onClick={() => onPick(prompt)}
            className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white p-3 text-left hover:border-gray-300 hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-blue-500"
          >
            <Icon size={18} className="mt-0.5 shrink-0 text-gray-500" />
            <span>
              <span className="block text-sm font-medium text-gray-800">{title}</span>
              <span className="block text-xs text-gray-500">{prompt}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function ChatHistory({ onPickStarter }: { onPickStarter: (prompt: string) => void }) {
  const conv = useActiveConversation();
  const messages = conv?.messages ?? [];
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const last = messages[messages.length - 1];

  // Stay pinned to the bottom while streaming unless the user scrolled up.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedRef.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, last?.content, last?.toolCalls?.length]);

  useEffect(() => {
    pinnedRef.current = true;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [conv?.id]);

  if (messages.length === 0) return <EmptyState onPick={onPickStarter} />;

  return (
    <div
      ref={scrollRef}
      onScroll={(e) => {
        const el = e.currentTarget;
        pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      }}
      className="flex-1 overflow-y-auto"
    >
      <div className="mx-auto max-w-3xl px-4 py-6">
        {messages.map((msg, i) => (
          <ChatMessage key={msg.id} message={msg} isLast={i === messages.length - 1} />
        ))}
      </div>
    </div>
  );
}
