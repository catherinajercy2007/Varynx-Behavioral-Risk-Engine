"use client";
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_VARYNX_API_URL || "http://localhost:8000/api/v1";

interface EvalResult {
  run_id: string;
  scenario: string;
  events_processed: number;
  metrics: { precision: number; recall: number; f1_score: number };
  errors: Array<{ event_index: number; error: string }>;
  elapsed_seconds: number;
}

export default function EvaluationPage() {
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState<EvalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadScenarios() {
    const res = await fetch(`${API}/evaluate/scenarios`);
    const data = await res.json();
    setScenarios(data.data.scenarios || []);
  }

  async function runEvaluation() {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/evaluate/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_name: selected, seed: 42 }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.message || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(data.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Evaluation</h1>

      <div className="bg-yellow-50 border border-yellow-200 p-4 rounded mb-6 text-sm text-yellow-800">
        <strong>Research Integrity:</strong> All metrics are derived from pipeline outputs on
        scenario inputs. No results are pre-claimed. BCSE (H3) and predictive trajectory (H4)
        evaluations require Phase 2 components.
      </div>

      <div className="flex gap-3 mb-6">
        <button
          onClick={loadScenarios}
          className="border border-gray-300 px-4 py-2 rounded text-sm hover:bg-gray-50"
        >
          Load Scenarios
        </button>
      </div>

      {scenarios.length > 0 && (
        <div className="flex gap-3 mb-6">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="flex-1 border rounded px-3 py-2 text-sm"
          >
            <option value="">Select scenario...</option>
            {scenarios.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button
            onClick={runEvaluation}
            disabled={loading || !selected}
            className="bg-varynx-blue text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Running..." : "Run"}
          </button>
        </div>
      )}

      {error && <div className="bg-red-50 text-red-700 p-3 rounded mb-4 text-sm">{error}</div>}

      {result && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Results: {result.scenario}</h2>
          <dl className="grid grid-cols-2 gap-3 text-sm mb-4">
            <dt className="text-gray-500">Events Processed</dt>
            <dd>{result.events_processed}</dd>
            <dt className="text-gray-500">Precision</dt>
            <dd>{result.metrics.precision.toFixed(4)}</dd>
            <dt className="text-gray-500">Recall</dt>
            <dd>{result.metrics.recall.toFixed(4)}</dd>
            <dt className="text-gray-500">F1 Score</dt>
            <dd className="font-semibold">{result.metrics.f1_score.toFixed(4)}</dd>
            <dt className="text-gray-500">Elapsed</dt>
            <dd>{result.elapsed_seconds.toFixed(3)}s</dd>
            <dt className="text-gray-500">Errors</dt>
            <dd className={result.errors.length > 0 ? "text-red-600" : ""}>{result.errors.length}</dd>
          </dl>
          <p className="text-xs text-gray-400">
            Run ID: {result.run_id} &bull; Seed: 42 &bull; Phase 1 in-memory pipeline
          </p>
        </div>
      )}
    </div>
  );
}