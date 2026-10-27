import { create } from "zustand";
import type {
  CreateScheduledTaskRequest,
  ScheduledTask,
  ScheduledTaskStatus,
  ScheduledTaskSummary,
  UpdateScheduledTaskRequest,
} from "../api/types";
import {
  cancelSchedule,
  createSchedule,
  getSchedule,
  listSchedules,
  pauseSchedule,
  resumeSchedule,
  updateSchedule,
} from "../api/schedules";

interface ScheduleState {
  schedules: ScheduledTaskSummary[];
  selectedSchedule: ScheduledTask | null;
  loading: boolean;
  error: string | null;

  fetchSchedules: (status?: ScheduledTaskStatus) => Promise<void>;
  fetchSchedule: (id: string) => Promise<void>;
  addSchedule: (request: CreateScheduledTaskRequest) => Promise<ScheduledTask>;
  editSchedule: (
    id: string,
    request: UpdateScheduledTaskRequest
  ) => Promise<void>;
  pause: (id: string) => Promise<void>;
  resume: (id: string) => Promise<void>;
  cancel: (id: string) => Promise<void>;

  handleSSEEvent: (event: { type: string; data: Record<string, unknown> }) => void;
}

export const useScheduleStore = create<ScheduleState>((set, get) => ({
  schedules: [],
  selectedSchedule: null,
  loading: false,
  error: null,

  fetchSchedules: async (status) => {
    set({ loading: true, error: null });
    try {
      const schedules = await listSchedules(status);
      set({ schedules, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  fetchSchedule: async (id) => {
    set({ loading: true, error: null });
    try {
      const schedule = await getSchedule(id);
      set({ selectedSchedule: schedule, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  addSchedule: async (request) => {
    const schedule = await createSchedule(request);
    await get().fetchSchedules();
    return schedule;
  },

  editSchedule: async (id, request) => {
    await updateSchedule(id, request);
    await get().fetchSchedules();
    if (get().selectedSchedule?.id === id) {
      await get().fetchSchedule(id);
    }
  },

  pause: async (id) => {
    await pauseSchedule(id);
    await get().fetchSchedules();
    if (get().selectedSchedule?.id === id) {
      await get().fetchSchedule(id);
    }
  },

  resume: async (id) => {
    await resumeSchedule(id);
    await get().fetchSchedules();
    if (get().selectedSchedule?.id === id) {
      await get().fetchSchedule(id);
    }
  },

  cancel: async (id) => {
    await cancelSchedule(id);
    await get().fetchSchedules();
    if (get().selectedSchedule?.id === id) {
      await get().fetchSchedule(id);
    }
  },

  handleSSEEvent: (event) => {
    const scheduleEvents = [
      "schedule_created",
      "schedule_updated",
      "schedule_paused",
      "schedule_resumed",
      "schedule_cancelled",
      "schedule_triggered",
      "schedule_failed",
    ];
    if (scheduleEvents.includes(event.type)) {
      get().fetchSchedules();
    }
  },
}));
