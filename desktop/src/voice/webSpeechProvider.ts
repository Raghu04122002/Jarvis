import type { VoiceProvider, VoiceTranscript } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SpeechRecognitionClass = (window as any).SpeechRecognition ??
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).webkitSpeechRecognition;

export class WebSpeechProvider implements VoiceProvider {
  readonly name = "webSpeech";

  get isSupported(): boolean {
    return !!SpeechRecognitionClass && !!window.speechSynthesis;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private recognition: any = null;
  private _isListening = false;
  private _isSpeaking = false;

  startListening(onTranscript: (t: VoiceTranscript) => void): void {
    if (!this.isSupported || this._isListening) return;

    this.recognition = new SpeechRecognitionClass();
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.lang = "en-US";

    this.recognition.onresult = (event: { results: ArrayLike<{ isFinal: boolean; 0: { transcript: string; confidence: number } }> }) => {
      const last = event.results[event.results.length - 1];
      if (!last) return;
      onTranscript({
        text: last[0].transcript,
        isFinal: last.isFinal,
        confidence: last[0].confidence,
      });
    };

    this.recognition.onerror = () => {
      this._isListening = false;
    };

    this.recognition.onend = () => {
      this._isListening = false;
    };

    this.recognition.start();
    this._isListening = true;
  }

  stopListening(): void {
    if (this.recognition) {
      this.recognition.stop();
      this.recognition = null;
    }
    this._isListening = false;
  }

  isListening(): boolean {
    return this._isListening;
  }

  async speak(text: string): Promise<void> {
    if (!this.isSupported) return;

    return new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      this._isSpeaking = true;
      utterance.onend = () => {
        this._isSpeaking = false;
        resolve();
      };
      utterance.onerror = () => {
        this._isSpeaking = false;
        resolve();
      };
      window.speechSynthesis.speak(utterance);
    });
  }

  stopSpeaking(): void {
    window.speechSynthesis.cancel();
    this._isSpeaking = false;
  }

  isSpeaking(): boolean {
    return this._isSpeaking;
  }
}
