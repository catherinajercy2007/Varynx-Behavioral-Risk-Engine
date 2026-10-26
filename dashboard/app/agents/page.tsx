"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_VARYNX_API_URL || "http://localhost:8000/api/v1";

interface AgentProfile {
  agent: {
    agent_id: string;
    owning_principal: string;
    scope_escalation_count: number;
    registered_at: string;
  };
  trust?: {
    current_score: number;
    level: string;
    history: Array<{ new_score: number; timestamp: string }>;
  };
  leases: Array<{ lease_id: string; state: string; capability: string }>;
}

function TrustBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    HIGH: "bg-green-100 text-green-800",
    ELEVATED: "bg-lime-100 text-lime-800",
    GUARDED: "bg-yellow-100 text-yellow-800",
    LOW: "bg-red-100 text-red-800",
    CRITICAL: "bg-red-900 text-white",
  };
  return (
    <span className={`px-2 py-1 rounded text-xs font-semibold ${colors[level] || "bg-gray-100"}`}>
      {level}
    </span>
  );
}

export default function AgentsPage() {
  const [agentId, setAgentId] = useState("");
  const [profile, setProfile] = useState<AgentProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadProfile() {
    if (!agentId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/agents/${encodeURIComponent(agentId)}/profile`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setProfile(data.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Agent Security Profiles</h1>

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="Enter agent_id"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && loadProfile()}
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={loadProfile}
          disabled={loading}
          className="bg-varynx-blue text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Load Profile"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
          {error}
        </div>
      )}

      {profile && (
        <div className="space-y-6">
          {/* Agent Identity */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">Agent Identity</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <dt className="text-gray-500">Agent ID</dt>
              <dd className="font-mono">{profile.agent.agent_id}</dd>
              <dt className="text-gray-500">Owner</dt>
              <dd>{profile.agent.owning_principal}</dd>
              <dt className="text-gray-500">Registered</dt>
              <dd>{new Date(profile.agent.registered_at).toLocaleString()}</dd>
              <dt className="text-gray-500">Scope Escalations</dt>
              <dd className={profile.agent.scope_escalation_count > 0 ? "text-red-600 font-semibold" : ""}>
                {profile.agent.scope_escalation_count}
              </dd>
            </dl>
          </div>

          {/* Trust State */}
          {profile.trust && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">Trust State</h2>
              <div className="flex items-center gap-4 mb-4">
                <div className="text-3xl font-bold">{profile.trust.current_score.toFixed(3)}</div>
                <TrustBadge level={profile.trust.level} />
              </div>
              <div className="text-sm text-gray-500">
                Score history: {profile.trust.history.length} entries
              </div>
              {/* Simple score history bar chart */}
              {profile.trust.history.length > 0 && (
                <div className="mt-3 flex items-end gap-1 h-12">
                  {profile.trust.history.slice(-20).map((h, i) => (
                    <div
                      key={i}
                      title={`${h.new_score.toFixed(3)} at ${h.timestamp}`}
                      className="flex-1 bg-blue-400 rounded-t"
                      style={{ height: `${Math.max(4, h.new_score * 48)}px` }}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Capability Leases */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">
              Capability Leases ({profile.leases.length})
            </h2>
            {profile.leases.length === 0 ? (
              <p className="text-gray-500 text-sm">No leases found.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="pb-2">Lease ID</th>
                    <th className="pb-2">Capability</th>
                    <th className="pb-2">State</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.leases.map((l) => (
                    <tr key={l.lease_id} className="border-b last:border-0">
                      <td className="py-2 font-mono text-xs">{l.lease_id.slice(0, 8)}...</td>
                      <td className="py-2">{l.capability}</td>
                      <td className="py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          l.state === "ACTIVE" ? "bg-green-100 text-green-800" :
                          l.state === "REVOKED" ? "bg-red-100 text-red-800" :
                          "bg-gray-100 text-gray-800"
                        }`}>{l.state}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}