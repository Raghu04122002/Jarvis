export interface VoiceTranscript {
  text: string;
  isFinal: boolean;
  confidence: number;
}

export interface VoiceProvider {
  readonly name: string;
  readonly isSupported: boolean;
  startListening(onTranscript: (t: VoiceTranscript) => void): void;
  stopListening(): void;
  isListening(): boolean;
  speak(text: string): Promise<void>;
  stopSpeaking(): void;
  isSpeaking(): boolean;
}
