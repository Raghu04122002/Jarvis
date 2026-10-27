import { create } from "zustand";
import { connectSSE } from "@/api/events";
import type { SSEEvent } from "@/api/types";

const MAX_EVENTS = 200;

interface EventState {
  events: SSEEvent[];
  connected: boolean;
  source: EventSource | null;
  connect: (backendUrl: string) => void;
  disconnect: () => void;
  addEvent: (event: SSEEvent) => void;
  clearEvents: () => void;
}

export const useEventStore = create<EventState>((set, get) => ({
  events: [],
  connected: false,
  source: null,

  connect: (backendUrl) => {
    const existing = get().source;
    if (existing) {
      existing.close();
    }

    const source = connectSSE(
      (event) => {
        get().addEvent(event);
      },
      () => {
        set({ connected: false });
      },
      () => {
        set({ connected: true });
      },
      undefined,
      backendUrl,
    );

    set({ source });
  },

  disconnect: () => {
    const source = get().source;
    if (source) {
      source.close();
    }
    set({ source: null, connected: false });
  },

  addEvent: (event) => {
    set((s) => {
      const events = [event, ...s.events].slice(0, MAX_EVENTS);
      return { events };
    });
  },

  clearEvents: () => set({ events: [] }),
}));
