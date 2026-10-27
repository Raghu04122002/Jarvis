import { useCallback, useEffect, useRef, useState } from "react";
import { getVoiceProvider } from "@/voice";
import type { VoiceProvider, VoiceTranscript } from "@/voice";
import { useSettingsStore } from "@/store/settingsStore";

export function useVoice(onFinal?: (text: string) => void) {
  const voiceProvider = useSettingsStore((s) => s.voiceProvider);
  const voiceEnabled = useSettingsStore((s) => s.voiceEnabled);
  const providerRef = useRef<VoiceProvider | null>(null);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    const provider = getVoiceProvider(voiceProvider);
    providerRef.current = provider;
    setIsSupported(provider.isSupported);
    return () => {
      provider.stopListening();
      provider.stopSpeaking();
    };
  }, [voiceProvider]);

  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const startListening = useCallback(() => {
    if (!providerRef.current || !voiceEnabled) return;
    setTranscript("");
    providerRef.current.startListening((t: VoiceTranscript) => {
      setTranscript(t.text);
      if (t.isFinal) {
        setListening(false);
        if (t.text.trim() && onFinalRef.current) {
          onFinalRef.current(t.text.trim());
        }
      }
    });
    setListening(true);
  }, [voiceEnabled]);

  const stopListening = useCallback(() => {
    providerRef.current?.stopListening();
    setListening(false);
  }, []);

  const speak = useCallback(async (text: string) => {
    if (!providerRef.current) return;
    await providerRef.current.speak(text);
  }, []);

  const stopSpeaking = useCallback(() => {
    providerRef.current?.stopSpeaking();
  }, []);

  return {
    isSupported: isSupported && voiceEnabled,
    listening,
    transcript,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
  };
}
