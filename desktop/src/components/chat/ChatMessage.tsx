import { useNavigate } from "react-router-dom";
import type { ChatMessage as ChatMsg } from "@/store/chatStore";
import { useTaskStore } from "@/store/taskStore";
import { formatRelativeTime } from "@/lib/formatters";

export function ChatMessage({ message }: { message: ChatMsg }) {
  const navigate = useNavigate();
  const dispatchTask = useTaskStore((s) => s.dispatchTask);
  const isUser = message.role === "user";

  const handleDispatch = async () => {
    if (message.taskId) {
      await dispatchTask(message.taskId);
    }
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[75%] rounded-lg px-4 py-2 ${
          isUser
            ? "bg-gray-800 text-white"
            : "bg-white border border-gray-200 text-gray-800"
        }`}
      >
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>

        {message.plan && message.plan.length > 0 && (
          <div className="mt-2 border-t border-gray-200 pt-2">
            <p className="text-xs font-semibold text-gray-500 mb-1">Plan:</p>
            <ol className="text-xs text-gray-600 list-decimal pl-4 space-y-0.5">
              {message.plan.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
            <div className="mt-2 flex gap-2">
              <button
                onClick={handleDispatch}
                className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
              >
                Start
              </button>
              {message.taskId && (
                <button
                  onClick={() => navigate(`/tasks/${message.taskId}`)}
                  className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                >
                  View Task
                </button>
              )}
            </div>
          </div>
        )}

        <span className="text-[10px] text-gray-400 mt-1 block">
          {formatRelativeTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
