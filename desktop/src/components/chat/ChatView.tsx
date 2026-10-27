import { ChatHistory } from "./ChatHistory";
import { ChatInput } from "./ChatInput";

export function ChatView() {
  return (
    <div className="flex flex-col h-full">
      <ChatHistory />
      <ChatInput />
    </div>
  );
}
