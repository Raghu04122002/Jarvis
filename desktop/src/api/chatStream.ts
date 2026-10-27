import { ApiError, getBaseUrl } from "./client";
import type { ChatRequest, ChatStreamEvent } from "./types";

/**
 * POST /chat/stream and call `onEvent` for each Server-Sent Event.
 * Resolves when the stream ends; rejects on network/HTTP errors or abort.
 */
export async function streamChat(
  req: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${getBaseUrl()}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
  if (!resp.ok || !resp.body) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    const detail = (body as { detail?: unknown }).detail;
    throw new ApiError(
      resp.status,
      typeof detail === "string" ? detail : resp.statusText || "Request failed",
    );
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const data = raw
        .split("\n")
        .filter((l) => l.startsWith("data: "))
        .map((l) => l.slice(6))
        .join("\n");
      if (!data) continue;
      try {
        onEvent(JSON.parse(data) as ChatStreamEvent);
      } catch {
        // ignore malformed event
      }
    }
  }
}
