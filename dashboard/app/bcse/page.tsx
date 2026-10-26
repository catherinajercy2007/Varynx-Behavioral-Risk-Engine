export default function BCSeCounterfactualPage() {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">BCSE Counterfactual View</h1>

      <div className="bg-yellow-50 border-l-4 border-yellow-400 p-6 rounded-lg mb-6">
        <div className="flex items-center gap-3 mb-3">
          <span className="bg-yellow-400 text-yellow-900 px-3 py-1 rounded-full text-sm font-bold">
            Phase 2 Placeholder
          </span>
        </div>
        <p className="text-yellow-800 text-sm leading-relaxed">
          The BCSE Counterfactual View is a Phase 2 deliverable. It will display the full output
          of the Behavioral Counterfactual Security Evaluation engine, including:
        </p>
        <ul className="list-disc ml-6 mt-3 text-sm text-yellow-800 space-y-1">
          <li>Policy simulation across multiple alternative policy configurations</li>
          <li>Consequence projections per policy (projected risk level, uncertainty score)</li>
          <li>Divergence scoring between active and counterfactual policies</li>
          <li>Confidence intervals derived from evidence density and history depth</li>
          <li>Natural-language rationale citing specific Evidence Record IDs</li>
        </ul>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold mb-3">Phase 1 Stub API (Available Now)</h2>
        <p className="text-sm text-gray-600 mb-4">
          The Phase 1 BCSE stub is available at{" "}
          <code className="bg-gray-100 px-1 rounded">POST /api/v1/bcse/evaluate</code>.
          It returns <code className="bg-gray-100 px-1 rounded">is_stub: true</code> with a
          single active consequence projection and no counterfactuals.
        </p>
        <div className="bg-gray-50 p-4 rounded text-xs font-mono text-gray-700">
          {`{
  "bcse_id": "uuid",
  "is_stub": true,
  "low_history_warning": false,
  "divergence_score": 0.0,
  "active_consequence": {
    "risk_level": "LOW",
    "uncertainty_score": 0.5,
    "is_projected": true
  },
  "counterfactual_consequences": []
}`}
        </div>
      </div>

      <div className="bg-blue-50 rounded-lg p-4 text-sm text-blue-800">
        <strong>Research Integrity Note:</strong> BCSE outputs are probabilistic estimates,
        not security verdicts. The Phase 2 engine does not predict attacker behavior with
        certainty and must not be represented as a definitive security decision system.
        See REQ-007 and docs/research_methodology.md for full limitations.
      </div>
    </div>
  );
}