const API_URL = process.env.NEXT_PUBLIC_VARYNX_API_URL || "http://localhost:8000/api/v1";

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || `HTTP ${res.status}: ${path}`);
  }
  const data = await res.json();
  return data.data as T;
}

export async function getHealth() {
  return fetchAPI<{ status: string; storage: Record<string, number> }>("/health");
}

export async function getAgentProfile(agentId: string) {
  return fetchAPI<{ agent: Record<string, unknown>; trust: Record<string, unknown> | null; leases: unknown[] }>(
    `/agents/${encodeURIComponent(agentId)}/profile`
  );
}

export async function getAuditRecords(params?: { agent_id?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (params?.agent_id) q.set("agent_id", params.agent_id);
  if (params?.limit) q.set("limit", String(params.limit));
  return fetchAPI<{ count: number; records: unknown[] }>(`/audit?${q}`);
}