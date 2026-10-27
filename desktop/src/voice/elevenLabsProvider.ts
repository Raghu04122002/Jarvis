import type { VoiceProvider, VoiceTranscript } from "./types";
import { WebSpeechProvider } from "./webSpeechProvider";
import { synthesize } from "@/api/voice";

export class ElevenLabsProvider implements VoiceProvider {
  readonly name = "elevenlabs";
  private webSpeech = new WebSpeechProvider();
  private _isSpeaking = false;
  private currentAudio: HTMLAudioElement | null = null;

  get isSupported(): boolean {
    return this.webSpeech.isSupported;
  }

  startListening(onTranscript: (t: VoiceTranscript) => void): void {
    this.webSpeech.startListening(onTranscript);
  }

  stopListening(): void {
    this.webSpeech.stopListening();
  }

  isListening(): boolean {
    return this.webSpeech.isListening();
  }

  async speak(text: string): Promise<void> {
    try {
      const audioBuffer = await synthesize(text);
      const blob = new Blob([audioBuffer], { type: "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      this.currentAudio = audio;
      this._isSpeaking = true;

      return new Promise<void>((resolve) => {
        audio.onended = () => {
          this._isSpeaking = false;
          this.currentAudio = null;
          URL.revokeObjectURL(url);
          resolve();
        };
        audio.onerror = () => {
          this._isSpeaking = false;
          this.currentAudio = null;
          URL.revokeObjectURL(url);
          resolve();
        };
        audio.play();
      });
    } catch {
      // Fall back to browser TTS if backend fails
      return this.webSpeech.speak(text);
    }
  }

  stopSpeaking(): void {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this._isSpeaking = false;
    this.webSpeech.stopSpeaking();
  }

  isSpeaking(): boolean {
    return this._isSpeaking;
  }
}
