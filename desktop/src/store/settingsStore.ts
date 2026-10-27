import { create } from "zustand";
import { DEFAULT_BACKEND_URL } from "@/lib/constants";
import { applyTheme, type Theme } from "@/lib/theme";

function storedTheme(): Theme {
  const v = localStorage.getItem("jarvis_theme");
  return v === "light" || v === "dark" ? v : "system";
}

interface SettingsState {
  backendUrl: string;
  voiceEnabled: boolean;
  voiceProvider: string;
  readAloud: boolean;
  theme: Theme;
  setBackendUrl: (url: string) => void;
  setVoiceEnabled: (enabled: boolean) => void;
  setVoiceProvider: (provider: string) => void;
  setReadAloud: (enabled: boolean) => void;
  setTheme: (theme: Theme) => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  backendUrl:
    localStorage.getItem("jarvis_backend_url") ?? DEFAULT_BACKEND_URL,
  voiceEnabled: localStorage.getItem("jarvis_voice_enabled") === "true",
  voiceProvider: localStorage.getItem("jarvis_voice_provider") ?? "webSpeech",
  readAloud: localStorage.getItem("jarvis_read_aloud") === "true",
  theme: storedTheme(),

  setBackendUrl: (url) => {
    localStorage.setItem("jarvis_backend_url", url);
    set({ backendUrl: url });
  },
  setVoiceEnabled: (enabled) => {
    localStorage.setItem("jarvis_voice_enabled", String(enabled));
    set({ voiceEnabled: enabled });
  },
  setVoiceProvider: (provider) => {
    localStorage.setItem("jarvis_voice_provider", provider);
    set({ voiceProvider: provider });
  },
  setReadAloud: (enabled) => {
    localStorage.setItem("jarvis_read_aloud", String(enabled));
    set({ readAloud: enabled });
  },
  setTheme: (theme) => {
    localStorage.setItem("jarvis_theme", theme);
    applyTheme(theme);
    set({ theme });
  },
}));
