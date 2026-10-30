"use client";

import { useState } from "react";

const DEFAULT_ALTERNATIVES = [
  {
    policy_id: "permissive",
    label: "Permissive (high thresholds)",
    overrides: { restrict_threshold: 0.8, suspend_threshold: 0.9 },
  },
  {
    policy_id: "strict",
    label: "Strict (low thresholds)",
    overrides: { restrict_threshold: 0.1, suspend_threshold: 0.3 },
  },
];

export default function BCSeCounterfactualPage() {
  const [agentId, setAgentId] = useState("agent-bcse-demo");
  const [resource, setResource] = useState("/data/sensitive.csv");
  const [useAlts, setUseAlts] = useState(true);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function runEval() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body: any = {
        agent_id: agentId,
        proposed_action_type: "READ",
        proposed_resource_scope: resource,
        session_id: "00000000-0000-0000-0000-000000000001",
        capability_requested: "read:files",
      };
      if (useAlts) body.alternative_policies = DEFAULT_ALTERNATIVES;
      const apiKey = process.env.NEXT_PUBLIC_VARYNX_API_KEY;
      const apiBase = process.env.NEXT_PUBLIC_VARYNX_API_URL || "http://localhost:8000/api/v1";
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey) headers["X-API-Key"] = apiKey;
      const res = await fetch(`${apiBase}/bcse/evaluate`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(`API error ${res.status}: ${json?.detail || JSON.stringify(json)}`);
      } else {
        setResult(json?.data ?? json);
      }
    } catch (e: any) {
      setError(e?.message ?? "Network error — is the Varynx API running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">BCSE Counterfactual Analysis</h1>

      {/* Input form */}
      <div className="bg-white rounded-lg shadow p-6 mb-4 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Agent ID</label>
          <input
            className="border rounded px-3 py-2 w-full text-sm font-mono"
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Proposed Resource Scope</label>
          <input
            className="border rounded px-3 py-2 w-full text-sm font-mono"
            value={resource}
            onChange={(e) => setResource(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="use-alts"
            checked={useAlts}
            onChange={(e) => setUseAlts(e.target.checked)}
          />
          <label htmlFor="use-alts" className="text-sm">
            Include alternative policies (enables Phase 2 — <code>is_stub: false</code>)
          </label>
        </div>
        <button
          onClick={runEval}
          disabled={loading}
          className="bg-indigo-600 text-white px-6 py-2 rounded hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
        >
          {loading ? "Evaluating…" : "Run BCSE Evaluation"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded mb-4 text-sm text-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Summary banner */}
          <div className={`rounded-lg p-4 flex gap-4 items-center ${result.is_stub ? "bg-yellow-50 border border-yellow-300" : "bg-green-50 border border-green-300"}`}>
            <span className={`px-3 py-1 rounded-full text-xs font-bold ${result.is_stub ? "bg-yellow-400 text-yellow-900" : "bg-green-500 text-white"}`}>
              {result.is_stub ? "Phase 1 Stub" : "Phase 2 Full"}
            </span>
            <div className="text-sm">
              <span className="font-medium">is_stub:</span>{" "}
              <code>{String(result.is_stub)}</code>
              {"  |  "}
              <span className="font-medium">divergence_score:</span>{" "}
              <code>{result.divergence_score?.toFixed(4)}</code>
              {"  |  "}
              <span className="font-medium">low_history_warning:</span>{" "}
              <code>{String(result.low_history_warning)}</code>
            </div>
          </div>

          {/* Active consequence */}
          {result.active_consequence && (
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-semibold mb-2 text-sm">Active Policy Consequence</h2>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <dt className="text-gray-500">Projected response</dt>
                <dd className="font-mono">{result.active_consequence.projected_response}</dd>
                <dt className="text-gray-500">Risk level</dt>
                <dd className="font-mono">{result.active_consequence.risk_level}</dd>
                <dt className="text-gray-500">Confidence</dt>
                <dd className="font-mono">{result.active_consequence.confidence}</dd>
                <dt className="text-gray-500">Uncertainty</dt>
                <dd className="font-mono">{result.active_consequence.uncertainty_score}</dd>
              </dl>
              <p className="text-xs text-gray-500 mt-2 italic">{result.active_consequence.rationale}</p>
            </div>
          )}

          {/* Counterfactuals */}
          {result.counterfactual_consequences?.length > 0 && (
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="font-semibold mb-3 text-sm">
                Counterfactual Consequences ({result.counterfactual_consequences.length})
              </h2>
              <div className="space-y-3">
                {result.counterfactual_consequences.map((cf: any, i: number) => (
                  <div key={i} className="border rounded p-3 text-xs">
                    <p className="font-medium mb-1">{cf.policy_id}</p>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                      <dt className="text-gray-500">Projected response</dt>
                      <dd className="font-mono">{cf.projected_response}</dd>
                      <dt className="text-gray-500">Risk level</dt>
                      <dd className="font-mono">{cf.risk_level}</dd>
                      <dt className="text-gray-500">Confidence</dt>
                      <dd className="font-mono">{cf.confidence}</dd>
                    </dl>
                    <p className="text-gray-500 mt-1 italic">{cf.rationale?.slice(0, 120)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw JSON */}
          <details className="bg-gray-50 rounded p-3 text-xs">
            <summary className="cursor-pointer font-medium text-gray-600 mb-1">Raw JSON response</summary>
            <pre className="overflow-x-auto mt-2">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}

      <div className="bg-blue-50 rounded-lg p-4 text-xs text-blue-800 mt-4">
        <strong>Research note:</strong> BCSE outputs are probabilistic estimates, not security
        verdicts. Check the box above to enable alternative policies and trigger Phase 2 analysis
        (<code>is_stub: false</code>). See REQ-007 and docs/research_methodology.md.
      </div>
    </div>
  );
}