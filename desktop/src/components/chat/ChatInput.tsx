import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { ArrowUp, Folder, Mic, Square, X } from "lucide-react";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { useProjectStore } from "@/store/projectStore";
import { useVoice } from "@/hooks/useVoice";

export interface ChatInputHandle {
  focus: () => void;
  setText: (text: string) => void;
}

const MAX_HEIGHT = 200;

export const ChatInput = forwardRef<ChatInputHandle>(function ChatInput(_props, ref) {
  const [text, setText] = useState("");
  const [showProjectPicker, setShowProjectPicker] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const stop = useChatStore((s) => s.stop);
  const streaming = useChatStore((s) => s.streamingId !== null);
  const activeProjectId = useChatStore((s) => s.activeProjectId);
  const setActiveProjectId = useChatStore((s) => s.setActiveProjectId);
  const readAloud = useSettingsStore((s) => s.readAloud);
  const projects = useProjectStore((s) => s.projects);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
    setText: (t: string) => {
      setText(t);
      textareaRef.current?.focus();
    },
  }));

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  // Auto-grow up to MAX_HEIGHT, then scroll.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  }, [text]);

  const handleMicFinal = useCallback(
    (finalText: string) => {
      setText("");
      void sendMessage(finalText, readAloud ? (content) => speak(content) : undefined);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sendMessage, readAloud],
  );

  const { isSupported, listening, transcript, startListening, stopListening, speak } =
    useVoice(handleMicFinal);

  useEffect(() => {
    if (transcript) setText(transcript);
  }, [transcript]);

  const canSend = text.trim().length > 0 && !streaming;

  const submit = () => {
    if (!canSend) return;
    void sendMessage(text.trim(), readAloud ? (content) => speak(content) : undefined);
    setText("");
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    } else if (e.key === "Escape" && streaming) {
      e.preventDefault();
      stop();
    }
  };

  const activeProject = projects.find((p) => p.id === activeProjectId);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4">
      {showProjectPicker && (
        <div className="mb-2">
          <select
            value={activeProjectId ?? ""}
            aria-label="Project scope"
            onChange={(e) => {
              setActiveProjectId(e.target.value || null);
              setShowProjectPicker(false);
              textareaRef.current?.focus();
            }}
            className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
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

      <form
        onSubmit={handleSubmit}
        className="rounded-2xl border border-gray-300 bg-white shadow-sm focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100"
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Jarvis anything…"
          aria-label="Message Jarvis"
          rows={1}
          className="block w-full resize-none bg-transparent px-4 pt-3 pb-1 text-sm outline-none placeholder:text-gray-400"
        />
        <div className="flex items-center gap-2 px-2 pb-2">
          {activeProject ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 py-0.5 pr-1 pl-2 text-xs text-blue-700">
              <Folder size={12} />
              <button
                type="button"
                onClick={() => setShowProjectPicker((v) => !v)}
                className="max-w-[12rem] truncate hover:underline"
                title="Change project"
              >
                {activeProject.name}
              </button>
              <button
                type="button"
                onClick={() => setActiveProjectId(null)}
                aria-label={`Remove project ${activeProject.name}`}
                className="rounded-full p-0.5 text-blue-400 hover:bg-blue-100 hover:text-blue-700"
              >
                <X size={12} />
              </button>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setShowProjectPicker((v) => !v)}
              aria-label="Scope to a project"
              title="Scope to a project"
              className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-800 focus-visible:outline-2 focus-visible:outline-blue-500"
            >
              <Folder size={14} />
              Project
            </button>
          )}

          <span className="flex-1" />

          {isSupported && (
            <button
              type="button"
              onClick={() => (listening ? stopListening() : startListening())}
              aria-label={listening ? "Stop listening" : "Speak a message"}
              title={listening ? "Stop listening" : "Speak a message"}
              className={`rounded-full p-2 focus-visible:outline-2 focus-visible:outline-blue-500 ${
                listening ? "bg-red-100 text-red-600" : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              <Mic size={16} />
            </button>
          )}

          {streaming ? (
            <button
              type="button"
              onClick={stop}
              aria-label="Stop generating (Esc)"
              title="Stop (Esc)"
              className="rounded-full bg-gray-800 p-2 text-white hover:bg-gray-700 focus-visible:outline-2 focus-visible:outline-blue-500"
            >
              <Square size={16} fill="currentColor" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send message"
              title="Send (Enter)"
              className={`rounded-full p-2 transition-colors focus-visible:outline-2 focus-visible:outline-blue-500 ${
                canSend
                  ? "bg-blue-600 text-white hover:bg-blue-700"
                  : "cursor-not-allowed bg-gray-100 text-gray-400"
              }`}
            >
              <ArrowUp size={16} />
            </button>
          )}
        </div>
      </form>
      <p className="mt-1.5 text-center text-[11px] text-gray-400">
        Enter to send · Shift+Enter for a new line
      </p>
    </div>
  );
});
