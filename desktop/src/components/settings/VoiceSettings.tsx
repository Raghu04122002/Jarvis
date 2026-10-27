import { useSettingsStore } from "@/store/settingsStore";
import { getAvailableProviders } from "@/voice";

const providerLabels: Record<string, string> = {
  webSpeech: "Browser (Web Speech API)",
  elevenlabs: "ElevenLabs (Premium TTS)",
};

export function VoiceSettings() {
  const voiceEnabled = useSettingsStore((s) => s.voiceEnabled);
  const voiceProvider = useSettingsStore((s) => s.voiceProvider);
  const readAloud = useSettingsStore((s) => s.readAloud);
  const setVoiceEnabled = useSettingsStore((s) => s.setVoiceEnabled);
  const setVoiceProvider = useSettingsStore((s) => s.setVoiceProvider);
  const setReadAloud = useSettingsStore((s) => s.setReadAloud);

  const providers = getAvailableProviders();

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-700">Voice</h3>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={voiceEnabled}
          onChange={(e) => setVoiceEnabled(e.target.checked)}
          className="rounded"
        />
        <span className="text-sm text-gray-700">Enable voice input</span>
      </label>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={readAloud}
          onChange={(e) => setReadAloud(e.target.checked)}
          className="rounded"
        />
        <span className="text-sm text-gray-700">Read responses aloud</span>
      </label>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Provider
        </label>
        <select
          value={voiceProvider}
          onChange={(e) => setVoiceProvider(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-gray-500"
        >
          {providers.map((p) => (
            <option key={p} value={p}>
              {providerLabels[p] ?? p}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
