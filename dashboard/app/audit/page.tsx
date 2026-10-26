"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_VARYNX_API_URL || "http://localhost:8000/api/v1";

interface AuditRecord {
  record_id: string;
  timestamp: string;
  record_type: string;
  source_entity_id: string;
  agent_id?: string;
  correlation_id?: string;
  payload: Record<string, unknown>;
}

export default function AuditPage() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [violations, setViolations] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterAgent, setFilterAgent] = useState("");

  async function loadAudit() {
    setLoading(true);
    setError(null);
    try {
      const params = filterAgent ? `?agent_id=${encodeURIComponent(filterAgent)}&limit=100` : "?limit=100";
      const res = await fetch(`${API}/audit${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRecords(data.data.records || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load audit records");
    } finally {
      setLoading(false);
    }
  }

  async function verifyChain() {
    try {
      const res = await fetch(`${API}/audit/verify`);
      const data = await res.json();
      setChainValid(data.data.chain_valid);
      setViolations(data.data.violations || []);
    } catch (e) {
      setError("Failed to verify chain");
    }
  }

  const RECORD_TYPE_COLORS: Record<string, string> = {
    EVENT_INGESTED: "bg-blue-100 text-blue-800",
    EVIDENCE_PRODUCED: "bg-purple-100 text-purple-800",
    TRUST_UPDATED: "bg-yellow-100 text-yellow-800",
    RESPONSE_RECOMMENDED: "bg-orange-100 text-orange-800",
    ENFORCEMENT_APPLIED: "bg-red-100 text-red-800",
    LEASE_STATE_CHANGED: "bg-teal-100 text-teal-800",
    SESSION_CREATED: "bg-green-100 text-green-800",
    SESSION_TERMINATED: "bg-gray-100 text-gray-800",
  };

  return (
    <div className="max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Audit Log</h1>

      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="Filter by agent_id (optional)"
          value={filterAgent}
          onChange={(e) => setFilterAgent(e.target.value)}
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={loadAudit}
          disabled={loading}
          className="bg-varynx-blue text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Load Records"}
        </button>
        <button
          onClick={verifyChain}
          className="border border-gray-300 px-4 py-2 rounded text-sm hover:bg-gray-50"
        >
          Verify Chain
        </button>
      </div>

      {chainValid !== null && (
        <div className={`p-3 rounded mb-4 text-sm ${chainValid ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
          Hash chain: {chainValid ? "VALID" : "INTEGRITY VIOLATION"}
          {violations.length > 0 && <ul className="mt-1 list-disc ml-4">{violations.map((v, i) => <li key={i}>{v}</li>)}</ul>}
        </div>
      )}

      {error && <div className="bg-red-50 text-red-700 p-3 rounded mb-4 text-sm">{error}</div>}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-3 text-gray-500 font-medium">Timestamp</th>
              <th className="text-left p-3 text-gray-500 font-medium">Type</th>
              <th className="text-left p-3 text-gray-500 font-medium">Agent</th>
              <th className="text-left p-3 text-gray-500 font-medium">Entity ID</th>
              <th className="text-left p-3 text-gray-500 font-medium">Correlation</th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 ? (
              <tr><td colSpan={5} className="p-6 text-center text-gray-400">No records. Click "Load Records" to fetch.</td></tr>
            ) : records.map((r) => (
              <tr key={r.record_id} className="border-t hover:bg-gray-50">
                <td className="p-3 text-xs text-gray-500">{new Date(r.timestamp).toLocaleString()}</td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${RECORD_TYPE_COLORS[r.record_type] || "bg-gray-100"}`}>
                    {r.record_type}
                  </span>
                </td>
                <td className="p-3 font-mono text-xs">{r.agent_id || "—"}</td>
                <td className="p-3 font-mono text-xs">{r.source_entity_id.slice(0, 12)}...</td>
                <td className="p-3 font-mono text-xs">{r.correlation_id ? r.correlation_id.slice(0, 8) + "..." : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {records.length > 0 && <p className="text-xs text-gray-400 mt-2">{records.length} records shown</p>}
    </div>
  );
}