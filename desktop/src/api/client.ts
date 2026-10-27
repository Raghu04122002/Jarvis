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

/** FastAPI errors carry `detail` as a string, or a list of validation errors (422). */
function detailText(body: unknown): string | undefined {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) =>
        [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "),
      )
      .join("; ");
  }
  return undefined;
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
    throw new ApiError(resp.status, detailText(body) ?? resp.statusText);
  }

  // 204 No Content (e.g. DELETE) has no body to parse.
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}
