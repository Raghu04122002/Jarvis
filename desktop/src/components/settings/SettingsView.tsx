import { useState } from "react";
import { useSettingsStore } from "@/store/settingsStore";
import { VoiceSettings } from "./VoiceSettings";
import { ConnectionStatus } from "./ConnectionStatus";

export function SettingsView() {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const setBackendUrl = useSettingsStore((s) => s.setBackendUrl);
  const [urlInput, setUrlInput] = useState(backendUrl);

  const handleSaveUrl = () => {
    setBackendUrl(urlInput.trim());
  };

  return (
    <div className="p-6 max-w-xl mx-auto space-y-6">
      <h2 className="text-lg font-semibold text-gray-800">Settings</h2>

      <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">
            Connection
          </h3>
          <div className="mb-2">
            <ConnectionStatus />
          </div>
          <div className="flex gap-2">
            <input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-gray-500"
            />
            <button
              onClick={handleSaveUrl}
              className="px-3 py-1.5 text-sm bg-gray-800 text-white rounded hover:bg-gray-700"
            >
              Save
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <VoiceSettings />
      </div>
    </div>
  );
}
