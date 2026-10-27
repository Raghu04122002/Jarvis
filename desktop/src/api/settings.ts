import { apiFetch } from "./client";

export type AIProvider = "anthropic" | "ollama";
export type SearchProvider = "auto" | "ollama" | "tavily" | "brave" | "none";
export type KeyName = "anthropic" | "ollama" | "tavily" | "brave";

export interface KeyStatus {
  set: boolean;
  /** Last 4 characters only — the backend never returns a full key. */
  hint: string;
  source: "settings" | "config" | "none";
}

export interface ToolSetting {
  name: string;
  label: string;
  description: string;
  enabled: boolean;
}

export interface ServerSettings {
  provider: AIProvider;
  model: string;
  ollama_model: string;
  ollama_think: string;
  web_search_provider: string;
  web_search_connected: boolean;
  keys: Record<KeyName, KeyStatus>;
  tools: ToolSetting[];
  persona: string;
  ai_available: boolean;
}

export interface SettingsPatch {
  provider?: AIProvider;
  model?: string;
  ollama_model?: string;
  ollama_think?: string;
  web_search_provider?: SearchProvider;
  /** A non-empty value sets a key; "" clears the saved one. */
  keys?: Partial<Record<KeyName, string>>;
  disabled_tools?: string[];
  persona?: string;
}

export interface CheckResult {
  ok: boolean;
  detail: string;
  latency_ms: number | null;
}

export interface ConnectionTest {
  provider: AIProvider;
  model: string;
  ai: CheckResult;
  web_search: CheckResult | null;
}

export const settingsApi = {
  get: () => apiFetch<ServerSettings>("/settings"),
  update: (patch: SettingsPatch) =>
    apiFetch<ServerSettings>("/settings", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  test: () => apiFetch<ConnectionTest>("/settings/test", { method: "POST" }),
};
