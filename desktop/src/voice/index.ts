import type { VoiceProvider } from "./types";
import { ElevenLabsProvider } from "./elevenLabsProvider";
import { WebSpeechProvider } from "./webSpeechProvider";

const providers: Record<string, () => VoiceProvider> = {
  webSpeech: () => new WebSpeechProvider(),
  elevenlabs: () => new ElevenLabsProvider(),
};

export function getVoiceProvider(name: string): VoiceProvider {
  const factory = providers[name];
  if (!factory) {
    return new WebSpeechProvider();
  }
  return factory();
}

export function getAvailableProviders(): string[] {
  return Object.keys(providers);
}

export type { VoiceProvider, VoiceTranscript } from "./types";
