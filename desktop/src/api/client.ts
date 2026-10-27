import { DEFAULT_BACKEND_URL } from "@/lib/constants";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export function getBaseUrl(): string {
  return (
    localStorage.getItem("jarvis_backend_url") ?? DEFAULT_BACKEND_URL
  );
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const resp = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new ApiError(
      resp.status,
      (body as { detail?: string }).detail ?? resp.statusText,
    );
  }

  return resp.json() as Promise<T>;
}
