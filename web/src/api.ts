import type {
  BatchParseRequest,
  BatchResponse,
  CleanupOutputsResponse,
  OutputListResponse,
  ParseRequest,
  ParseResponse,
} from "./types";

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

async function fetchJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (data && typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      const body = await response.text();
      if (body) {
        message = body;
      }
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function parseSingle(payload: ParseRequest): Promise<ParseResponse> {
  return fetchJson<ParseResponse>(`${API_BASE}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function parseBatch(
  payload: BatchParseRequest
): Promise<BatchResponse> {
  return fetchJson<BatchResponse>(`${API_BASE}/parse/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchOutputs(
  limit = 50
): Promise<OutputListResponse> {
  return fetchJson<OutputListResponse>(`${API_BASE}/outputs?limit=${limit}`);
}

const encodePath = (value: string) =>
  value
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");

export async function fetchOutputFile(relativePath: string): Promise<unknown> {
  const encodedPath = encodePath(relativePath);
  return fetchJson(`${API_BASE}/outputs/${encodedPath}`);
}

export async function deleteOutput(relativePath: string): Promise<void> {
  const encodedPath = encodePath(relativePath);
  await fetchJson(`${API_BASE}/outputs/${encodedPath}`, { method: "DELETE" });
}

export async function cleanupOutputs(
  retentionSeconds: number
): Promise<CleanupOutputsResponse> {
  return fetchJson<CleanupOutputsResponse>(`${API_BASE}/outputs/cleanup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ retention_seconds: retentionSeconds }),
  });
}
