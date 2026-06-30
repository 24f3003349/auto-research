import { useState } from "react";
import { api, type EvoRunResponse } from "../api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export default function EvolutionPane() {
  const [seed, setSeed] = useState("Concise, friendly, accurate.");
  const [generations, setGenerations] = useState(8);
  const [popSize, setPopSize] = useState(6);
  const [mutationRate, setMutationRate] = useState(0.1);
  const [fitnessKind, setFitnessKind] = useState("diversity");
  const [result, setResult] = useState<EvoRunResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.evolution.run({
        seed,
        generations,
        pop_size: popSize,
        mutation_rate: mutationRate,
        fitness_kind: fitnessKind,
      });
      setResult(r);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-12 gap-4 h-full">
      <div className="col-span-3 bg-panel rounded p-3">
        <form onSubmit={run} className="space-y-2 text-sm">
          <label className="block text-xs uppercase text-slate-400">Seed prompt</label>
          <textarea
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 h-20"
          />
          <label className="block text-xs uppercase text-slate-400">Generations</label>
          <input
            type="number"
            min={1}
            max={50}
            value={generations}
            onChange={(e) => setGenerations(+e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1"
          />
          <label className="block text-xs uppercase text-slate-400">Population</label>
          <input
            type="number"
            min={2}
            max={32}
            value={popSize}
            onChange={(e) => setPopSize(+e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1"
          />
          <label className="block text-xs uppercase text-slate-400">Mutation rate</label>
          <input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={mutationRate}
            onChange={(e) => setMutationRate(+e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1"
          />
          <label className="block text-xs uppercase text-slate-400">Fitness</label>
          <select
            value={fitnessKind}
            onChange={(e) => setFitnessKind(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1"
          >
            <option value="length">length (more = better)</option>
            <option value="diversity">diversity (unique chars)</option>
            <option value="fixed">fixed 0.5 (for stress test)</option>
          </select>
          <button
            disabled={busy}
            className="bg-accent text-slate-900 font-semibold rounded px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {busy ? "Running…" : "Evolve"}
          </button>
        </form>
      </div>

      <div className="col-span-9 bg-panel rounded p-3 overflow-y-auto">
        {!result && <p className="text-slate-400 text-sm">Run an evolution to see results.</p>}
        {result && (
          <div className="space-y-4">
            <header className="text-sm">
              <h2 className="font-semibold">Run {result.run_id}</h2>
              <p className="text-xs text-slate-400">
                Final mutation rate: {result.mutation_rate.toFixed(3)} ·
                Generations: {result.generations.length}
              </p>
            </header>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.generations}>
                  <CartesianGrid stroke="#1f2937" />
                  <XAxis dataKey="generation" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="best_fitness" stroke="#7dd3fc" />
                  <Line type="monotone" dataKey="mean_fitness" stroke="#86efac" />
                  <Line type="monotone" dataKey="diversity" stroke="#fde68a" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <section>
              <h3 className="text-xs uppercase text-slate-400 mb-1">Top candidates (last gen)</h3>
              <ol className="text-sm space-y-1">
                {[...result.population]
                  .filter((c) => c.generation === result.generations[result.generations.length - 1].generation)
                  .sort((a, b) => b.fitness - a.fitness)
                  .slice(0, 8)
                  .map((c) => (
                    <li key={c.id} className="flex justify-between border-b border-slate-800 py-1">
                      <span className="font-mono text-xs truncate mr-3">{c.candidate}</span>
                      <span className="text-accent">{c.fitness.toFixed(2)}</span>
                    </li>
                  ))}
              </ol>
            </section>
            {result.generations.some((g) => g.plateau) && (
              <section className="text-warn text-xs">
                ⚠ Plateau detected — adaptive mutation applied to break the stall.
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
