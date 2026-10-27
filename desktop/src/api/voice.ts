import { DEFAULT_BACKEND_URL } from "@/lib/constants";

function getBaseUrl(): string {
  return localStorage.getItem("jarvis_backend_url") ?? DEFAULT_BACKEND_URL;
}

export interface TranscribeResult {
  text: string;
}

export interface VoiceChatResult {
  audio: ArrayBuffer;
  transcript: string;
}

export async function transcribe(audioBlob: Blob): Promise<TranscribeResult> {
  const form = new FormData();
  form.append("audio", audioBlob, "audio.webm");

  const resp = await fetch(`${getBaseUrl()}/voice/transcribe`, {
    method: "POST",
    body: form,
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error((body as { detail?: string }).detail ?? resp.statusText);
  }

  return resp.json() as Promise<TranscribeResult>;
}

export async function synthesize(text: string): Promise<ArrayBuffer> {
  const resp = await fetch(`${getBaseUrl()}/voice/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error((body as { detail?: string }).detail ?? resp.statusText);
  }

  return resp.arrayBuffer();
}

export async function voiceChat(audioBlob: Blob): Promise<VoiceChatResult> {
  const form = new FormData();
  form.append("audio", audioBlob, "audio.webm");

  const resp = await fetch(`${getBaseUrl()}/voice/chat`, {
    method: "POST",
    body: form,
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error((body as { detail?: string }).detail ?? resp.statusText);
  }

  const transcript = resp.headers.get("X-Transcript") ?? "";
  const audio = await resp.arrayBuffer();

  return { audio, transcript };
}
