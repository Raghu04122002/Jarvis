import { useState, useCallback, useEffect, type FormEvent, type KeyboardEvent } from "react";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { useProjectStore } from "@/store/projectStore";
import { useVoice } from "@/hooks/useVoice";

export function ChatInput() {
  const [text, setText] = useState("");
  const [showProjectPicker, setShowProjectPicker] = useState(false);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const sending = useChatStore((s) => s.sending);
  const activeProjectId = useChatStore((s) => s.activeProjectId);
  const setActiveProjectId = useChatStore((s) => s.setActiveProjectId);
  const readAloud = useSettingsStore((s) => s.readAloud);
  const projects = useProjectStore((s) => s.projects);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleMicFinal = useCallback(
    (finalText: string) => {
      setText("");
      sendMessage(finalText, readAloud ? (content) => speak(content) : undefined);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sendMessage, readAloud],
  );

  const { isSupported, listening, transcript, startListening, stopListening, speak } =
    useVoice(handleMicFinal);

  useEffect(() => {
    if (transcript) {
      setText(transcript);
    }
  }, [transcript]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    sendMessage(trimmed, readAloud ? (content) => speak(content) : undefined);
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const toggleMic = () => {
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const activeProject = projects.find((p) => p.id === activeProjectId);

  return (
    <div className="border-t border-gray-200">
      {/* Project context pill */}
      {activeProjectId && activeProject && (
        <div className="px-3 pt-2 flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full">
            📁 {activeProject.name}
            <button
              type="button"
              onClick={() => setActiveProjectId(null)}
              className="ml-0.5 text-blue-400 hover:text-blue-600"
            >
              ✕
            </button>
          </span>
        </div>
      )}

      {/* Project picker dropdown */}
      {showProjectPicker && (
        <div className="px-3 pt-2">
          <select
            value={activeProjectId ?? ""}
            onChange={(e) => {
              setActiveProjectId(e.target.value || null);
              setShowProjectPicker(false);
            }}
            className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:border-gray-500"
            autoFocus
            onBlur={() => setShowProjectPicker(false)}
          >
            <option value="">No project</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <form onSubmit={handleSubmit} className="p-3">
        <div className="flex items-end gap-2">
          {/* Project scope button */}
          <button
            type="button"
            onClick={() => setShowProjectPicker(!showProjectPicker)}
            title="Scope to project"
            className={`p-2 rounded-lg text-sm ${
              activeProjectId
                ? "bg-blue-100 text-blue-600"
                : "bg-gray-100 text-gray-500 hover:bg-gray-200"
            }`}
          >
            📁
          </button>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Jarvis anything..."
            rows={1}
            className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-gray-500"
            disabled={sending}
          />
          {isSupported && (
            <button
              type="button"
              onClick={toggleMic}
              className={`p-2 rounded-lg text-sm ${
                listening
                  ? "bg-red-100 text-red-600"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {listening ? "⏹" : "🎤"}
            </button>
          )}
          <button
            type="submit"
            disabled={sending || !text.trim()}
            className="px-4 py-2 bg-gray-800 text-white text-sm rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? "..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
