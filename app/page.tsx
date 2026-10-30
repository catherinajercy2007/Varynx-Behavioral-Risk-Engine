import Link from "next/link";

export default function DashboardHome() {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">Varynx Dashboard</h1>
      <p className="text-gray-600 mb-8">
        Cloud-Native Behavioral Risk Control Engine for Autonomous AI Agents
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Link href="/agents" className="block p-6 bg-white rounded-lg shadow hover:shadow-md transition">
          <h2 className="text-xl font-semibold mb-2">Agents</h2>
          <p className="text-gray-600 text-sm">View agent security profiles, trust scores, and session details.</p>
        </Link>

        <Link href="/audit" className="block p-6 bg-white rounded-lg shadow hover:shadow-md transition">
          <h2 className="text-xl font-semibold mb-2">Audit Log</h2>
          <p className="text-gray-600 text-sm">Browse tamper-evident audit records and verify hash-chain integrity.</p>
        </Link>

        <Link href="/evaluation" className="block p-6 bg-white rounded-lg shadow hover:shadow-md transition">
          <h2 className="text-xl font-semibold mb-2">Evaluation</h2>
          <p className="text-gray-600 text-sm">Run scenarios, view metrics, and compare against baselines.</p>
        </Link>

        <Link href="/bcse" className="block p-6 bg-white rounded-lg shadow hover:shadow-md transition border-l-4 border-yellow-400">
          <h2 className="text-xl font-semibold mb-2">BCSE</h2>
          <p className="text-gray-600 text-sm">Behavioral Counterfactual Security Evaluation — Phase 2 placeholder.</p>
          <span className="inline-block mt-2 text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Phase 2</span>
        </Link>
      </div>

      <div className="mt-8 p-4 bg-blue-50 rounded-lg text-sm text-blue-800">
        <strong>Phase 1 MVP.</strong> This dashboard connects to the Varynx REST API at{" "}
        <code className="bg-blue-100 px-1 rounded">{process.env.VARYNX_API_URL}</code>.
        The API must be running to load live data. BCSE counterfactual view requires Phase 2 engine.
      </div>
    </div>
  );
}