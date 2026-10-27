import { afterEach, describe, expect, it, vi } from "vitest";

// Node test env has no localStorage; chatStore persists to it and the API
// client reads the backend URL from it.
const mem = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => void mem.set(k, v),
  removeItem: (k: string) => void mem.delete(k),
  clear: () => mem.clear(),
  key: (i: number) => [...mem.keys()][i] ?? null,
  get length() {
    return mem.size;
  },
});
import { streamChat } from "@/api/chatStream";
import type { ChatStreamEvent } from "@/api/types";
import { formatRelativeTime } from "@/lib/formatters";
import { autoTitle } from "@/store/chatStore";

function sseResponse(chunks: string[]): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      chunks.forEach((ch) => c.enqueue(enc.encode(ch)));
      c.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => vi.restoreAllMocks());

describe("streamChat", () => {
  it("parses events split across chunks", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse([
        'data: {"type":"token","text":"Hel"}\n\ndata: {"type":"tok',
        'en","text":"lo"}\n\n',
        'data: {"type":"done","response":{"title":"t","status":"answered","message":"m","answer":"Hello"}}\n\n',
      ]),
    );
    const events: ChatStreamEvent[] = [];
    await streamChat({ message: "hi" }, (e) => events.push(e));
    expect(events.map((e) => e.type)).toEqual(["token", "token", "done"]);
    expect(events[1]).toEqual({ type: "token", text: "lo" });
  });

  it("throws ApiError with the server detail on HTTP errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "bad request" }), { status: 422 }),
    );
    await expect(streamChat({ message: "" }, () => {})).rejects.toThrow("bad request");
  });
});

describe("autoTitle", () => {
  it("uses the first words, capitalised, without trailing punctuation", () => {
    expect(autoTitle("what are today's top news headlines in the world?")).toBe(
      "What are today's top news headlines",
    );
    expect(autoTitle("   ")).toBe("New chat");
  });
});

describe("formatRelativeTime", () => {
  const now = Date.parse("2026-10-27T12:00:00Z");
  it.each([
    ["2026-10-27T11:59:40Z", "just now"],
    ["2026-10-27T11:58:00Z", "2m ago"],
    ["2026-10-27T09:00:00Z", "3h ago"],
    ["2026-10-25T12:00:00Z", "2d ago"],
  ])("%s → %s", (iso, expected) => {
    expect(formatRelativeTime(iso, now)).toBe(expected);
  });
  it("never shows negative times for clock skew", () => {
    expect(formatRelativeTime("2026-10-27T12:01:00Z", now)).toBe("just now");
  });
});
