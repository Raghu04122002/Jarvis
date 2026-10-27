import { useEffect, useState, type ReactNode } from "react";
import { CheckCircle2, KeyRound, Loader2, Monitor, Moon, Plug, Sun, XCircle } from "lucide-react";
import {
  settingsApi,
  type AIProvider,
  type ConnectionTest,
  type KeyName,
  type ServerSettings,
  type SettingsPatch,
} from "@/api/settings";
import { useSettingsStore } from "@/store/settingsStore";
import type { Theme } from "@/lib/theme";
import { VoiceSettings } from "./VoiceSettings";
import { ConnectionStatus } from "./ConnectionStatus";

const KEY_LABELS: Record<KeyName, string> = {
  anthropic: "Anthropic API key",
  ollama: "Ollama API key",
  tavily: "Tavily API key (web search)",
  brave: "Brave Search API key",
};

const OLLAMA_MODELS = ["gpt-oss:20b", "gpt-oss:120b", "glm-5.3-flash", "gemma4:31b"];

const field =
  "w-full rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";
const primaryBtn =
  "inline-flex items-center gap-1.5 rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-blue-500";

function Card({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {description && <p className="mt-0.5 text-xs text-gray-500">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function errorText(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

export function SettingsView() {
  const [server, setServer] = useState<ServerSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = () => {
    setLoadError(null);
    settingsApi.get().then(setServer).catch((e) => setLoadError(errorText(e)));
  };
  useEffect(load, []);

  const save = async (patch: SettingsPatch): Promise<boolean> => {
    setSaving(true);
    setSaveError(null);
    try {
      setServer(await settingsApi.update(patch));
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1500);
      return true;
    } catch (e) {
      setSaveError(errorText(e));
      return false;
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-5 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Settings</h2>
        <span aria-live="polite" className="text-xs text-gray-500">
          {saving ? "Saving…" : saved ? "Saved" : ""}
        </span>
      </div>

      {saveError && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Couldn't save: {saveError}
        </p>
      )}

      {loadError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <p>Couldn't load settings from the backend: {loadError}</p>
          <button type="button" onClick={load} className="mt-2 font-medium underline">
            Retry
          </button>
        </div>
      ) : !server ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading settings">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-gray-100" />
          ))}
        </div>
      ) : (
        <>
          <ModelCard server={server} onSave={save} />
          <KeysCard server={server} onSave={save} />
          <ToolsCard server={server} onSave={save} />
          <PersonaCard server={server} onSave={save} />
        </>
      )}

      <AppearanceCard />

      <Card title="Backend connection" description="Where the desktop app finds the Jarvis server.">
        <BackendUrl />
      </Card>

      <Card title="Voice">
        <VoiceSettings />
      </Card>
    </div>
  );
}

type SaveFn = (patch: SettingsPatch) => Promise<boolean>;

function ModelCard({ server, onSave }: { server: ServerSettings; onSave: SaveFn }) {
  const [provider, setProvider] = useState<AIProvider>(server.provider);
  const [model, setModel] = useState(server.provider === "ollama" ? server.ollama_model : server.model);
  const [think, setThink] = useState(server.ollama_think);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<ConnectionTest | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const switchProvider = (p: AIProvider) => {
    setProvider(p);
    setModel(p === "ollama" ? server.ollama_model : server.model);
  };

  const dirty =
    provider !== server.provider ||
    model !== (provider === "ollama" ? server.ollama_model : server.model) ||
    (provider === "ollama" && think !== server.ollama_think);

  const apply = () =>
    onSave(
      provider === "ollama"
        ? { provider, ollama_model: model.trim(), ollama_think: think }
        : { provider, model: model.trim() },
    );

  const test = async () => {
    setTesting(true);
    setResult(null);
    setTestError(null);
    try {
      if (dirty && !(await apply())) return;
      setResult(await settingsApi.test());
    } catch (e) {
      setTestError(errorText(e));
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card title="AI model" description="The model that answers chat, plans tasks and reviews agent work.">
      <div role="radiogroup" aria-label="Provider" className="grid grid-cols-2 gap-2">
        {(["ollama", "anthropic"] as const).map((p) => (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={provider === p}
            onClick={() => switchProvider(p)}
            className={`rounded-lg border px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-blue-500 ${
              provider === p ? "border-blue-500 bg-blue-50 text-gray-900" : "border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            <span className="block font-medium">{p === "ollama" ? "Ollama" : "Anthropic"}</span>
            <span className="block text-xs text-gray-500">
              {p === "ollama" ? "Cloud or local models" : "Claude via API key"}
            </span>
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-600">Model</span>
          <input
            className={field}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            list={provider === "ollama" ? "ollama-models" : undefined}
            spellCheck={false}
          />
          <datalist id="ollama-models">
            {OLLAMA_MODELS.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </label>
        {provider === "ollama" && (
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-gray-600">Reasoning effort</span>
            <select className={field} value={think} onChange={(e) => setThink(e.target.value)}>
              <option value="">Model default</option>
              <option value="low">Low (fastest, uses least quota)</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className={primaryBtn} disabled={!dirty || !model.trim()} onClick={() => void apply()}>
          Save model
        </button>
        <button
          type="button"
          onClick={() => void test()}
          disabled={testing}
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-blue-500"
        >
          {testing ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Plug size={14} aria-hidden />}
          Test connection
        </button>
        {!server.ai_available && (
          <span className="text-xs text-amber-700">No API key for this provider yet.</span>
        )}
      </div>

      <div aria-live="polite">
        {testError && <p className="text-sm text-red-700">Test failed: {testError}</p>}
        {result && (
          <ul className="space-y-1 text-sm">
            <CheckLine label={`${result.provider} · ${result.model}`} check={result.ai} />
            {result.web_search && <CheckLine label="Web search" check={result.web_search} />}
          </ul>
        )}
      </div>
    </Card>
  );
}

function CheckLine({ label, check }: { label: string; check: ConnectionTest["ai"] }) {
  return (
    <li className="flex items-start gap-2">
      {check.ok ? (
        <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-green-600" aria-label="OK" />
      ) : (
        <XCircle size={16} className="mt-0.5 shrink-0 text-red-600" aria-label="Failed" />
      )}
      <span className="text-gray-700">
        <span className="font-medium">{label}</span> — {check.detail}
        {check.latency_ms != null && <span className="text-gray-400"> ({check.latency_ms} ms)</span>}
      </span>
    </li>
  );
}

function KeysCard({ server, onSave }: { server: ServerSettings; onSave: SaveFn }) {
  const [editing, setEditing] = useState<KeyName | null>(null);
  const [value, setValue] = useState("");

  const submit = async (name: KeyName, v: string) => {
    if (await onSave({ keys: { [name]: v } })) {
      setEditing(null);
      setValue("");
    }
  };

  return (
    <Card
      title="API keys"
      description="Stored on this machine only (data/settings.json, owner-readable). Keys are never shown again after saving."
    >
      <ul className="divide-y divide-gray-100">
        {(Object.keys(KEY_LABELS) as KeyName[]).map((name) => {
          const status = server.keys[name];
          return (
            <li key={name} className="py-2.5">
              <div className="flex items-center gap-3">
                <KeyRound size={15} className="shrink-0 text-gray-400" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-800">{KEY_LABELS[name]}</p>
                  <p className="text-xs text-gray-500">
                    {status?.set ? (
                      <>
                        <span className="font-mono">••••{status.hint}</span>
                        {status.source === "config" && " · from .env / environment"}
                      </>
                    ) : (
                      "Not set"
                    )}
                  </p>
                </div>
                {editing !== name && (
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(name);
                        setValue("");
                      }}
                      className="rounded-md px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-blue-500"
                    >
                      {status?.set ? "Replace" : "Add"}
                    </button>
                    {status?.source === "settings" && (
                      <button
                        type="button"
                        onClick={() => void submit(name, "")}
                        className="rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-blue-500"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                )}
              </div>
              {editing === name && (
                <form
                  className="mt-2 flex gap-2 pl-7"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (value.trim()) void submit(name, value.trim());
                  }}
                >
                  <input
                    type="password"
                    autoFocus
                    autoComplete="off"
                    aria-label={KEY_LABELS[name]}
                    placeholder="Paste key"
                    className={field}
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Escape" && setEditing(null)}
                  />
                  <button type="submit" className={primaryBtn} disabled={!value.trim()}>
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(null)}
                    className="rounded-lg px-2 text-sm text-gray-600 hover:bg-gray-100"
                  >
                    Cancel
                  </button>
                </form>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function ToolsCard({ server, onSave }: { server: ServerSettings; onSave: SaveFn }) {
  const toggle = (name: string, enabled: boolean) => {
    const disabled = server.tools.filter((t) => (t.name === name ? !enabled : !t.enabled)).map((t) => t.name);
    void onSave({ disabled_tools: disabled });
  };
  return (
    <Card title="Tools" description="What the chat model may use. Disabled tools are hidden from the model entirely.">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-gray-500">Web search:</span>
        <select
          aria-label="Web search provider"
          className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs text-gray-800"
          value={server.web_search_provider}
          onChange={(e) => void onSave({ web_search_provider: e.target.value as SettingsPatch["web_search_provider"] })}
        >
          <option value="auto">Auto</option>
          <option value="ollama">Ollama</option>
          <option value="tavily">Tavily</option>
          <option value="brave">Brave</option>
          <option value="none">Off</option>
        </select>
        <span className={server.web_search_connected ? "text-green-700" : "text-gray-500"}>
          {server.web_search_connected ? "connected" : "not connected (needs a key)"}
        </span>
      </div>
      <ul className="divide-y divide-gray-100">
        {server.tools.map((t) => (
          <li key={t.name} className="flex items-center gap-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="text-sm text-gray-800">
                {t.label} <code className="ml-1 text-xs text-gray-400">{t.name}</code>
              </p>
              <p className="text-xs text-gray-500">{t.description}</p>
            </div>
            <Switch label={`Enable ${t.label}`} checked={t.enabled} onChange={(v) => toggle(t.name, v)} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Switch({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 shrink-0 rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 ${
        checked ? "bg-blue-600" : "bg-gray-300"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-4" : ""
        }`}
      />
    </button>
  );
}

function PersonaCard({ server, onSave }: { server: ServerSettings; onSave: SaveFn }) {
  const [persona, setPersona] = useState(server.persona);
  return (
    <Card
      title="Persona"
      description="Extra instructions added to Jarvis's system prompt (tone, focus, preferences). They can't override the honesty rules."
    >
      <textarea
        aria-label="Persona instructions"
        rows={4}
        maxLength={4000}
        className={`${field} resize-y`}
        placeholder="e.g. Answer like a senior engineer. Prefer TypeScript examples."
        value={persona}
        onChange={(e) => setPersona(e.target.value)}
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">{persona.length}/4000</span>
        <button
          type="button"
          className={primaryBtn}
          disabled={persona === server.persona}
          onClick={() => void onSave({ persona })}
        >
          Save persona
        </button>
      </div>
    </Card>
  );
}

function AppearanceCard() {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const options: { value: Theme; label: string; icon: typeof Sun }[] = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ];
  return (
    <Card title="Appearance">
      <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-lg border border-gray-200 p-0.5">
        {options.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={theme === value}
            onClick={() => setTheme(value)}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-blue-500 ${
              theme === value ? "bg-gray-100 font-medium text-gray-900" : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <Icon size={14} aria-hidden />
            {label}
          </button>
        ))}
      </div>
    </Card>
  );
}

function BackendUrl() {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const setBackendUrl = useSettingsStore((s) => s.setBackendUrl);
  const [url, setUrl] = useState(backendUrl);
  return (
    <>
      <ConnectionStatus />
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setBackendUrl(url.trim());
        }}
      >
        <input aria-label="Backend URL" className={field} value={url} onChange={(e) => setUrl(e.target.value)} />
        <button type="submit" className={primaryBtn} disabled={!url.trim() || url.trim() === backendUrl}>
          Save
        </button>
      </form>
    </>
  );
}
