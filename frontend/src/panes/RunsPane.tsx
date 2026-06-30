import { useEffect, useState } from "react";
import { api, type Run } from "../api";

export default function RunsPane({ events }: { events: any[] }) {
  const [topic, setTopic] = useState("Reduce customer churn");
  const [objective, setObjective] = useState("Identify 3 actionable retention levers");
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<(Run & { agents: any[] }) | null>(null);

  const refresh = () => api.runs.list().then(setRuns).catch(() => setRuns([]));
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    api.runs
      .get(selected)
      .then((r) => !cancelled && setDetail(r))
      .catch(() => !cancelled && setDetail(null));
    return () => {
      cancelled = true;
    };
  }, [selected, events.length]);

  async function startRun(e: React.FormEvent) {
    e.preventDefault();
    await api.runs.create({ topic, objective });
    await refresh();
  }

  return (
    <div className="grid grid-cols-12 gap-4 h-full">
      <div className="col-span-5 bg-panel rounded p-3 flex flex-col">
        <form onSubmit={startRun} className="space-y-2">
          <label className="block text-xs uppercase text-slate-400">Topic</label>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
          />
          <label className="block text-xs uppercase text-slate-400">Objective</label>
          <textarea
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm h-16"
          />
          <button
            type="submit"
            className="bg-accent text-slate-900 font-semibold rounded px-3 py-1.5 text-sm hover:opacity-90"
          >
            ▶ Run
          </button>
        </form>

        <h2 className="mt-4 mb-2 text-sm uppercase text-slate-400">Recent runs</h2>
        <ul className="flex-1 overflow-y-auto divide-y divide-slate-800">
          {runs.map((r) => (
            <li
              key={r.id}
              onClick={() => setSelected(r.id)}
              className={
                "p-2 cursor-pointer text-sm flex justify-between items-center " +
                (selected === r.id ? "bg-slate-800" : "hover:bg-slate-800/40")
              }
            >
              <div>
                <div className="font-medium">{r.topic}</div>
                <div className="text-xs text-slate-400">{new Date(r.created_at + "Z").toLocaleString()}</div>
              </div>
              <span
                className={
                  "text-xs px-2 py-0.5 rounded " +
                  (r.status === "completed"
                    ? "bg-ok/30 text-ok"
                    : r.status === "failed"
                    ? "bg-bad/30 text-bad"
                    : r.status === "running"
                    ? "bg-warn/30 text-warn"
                    : "bg-slate-700 text-slate-200")
                }
              >
                {r.status}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="col-span-7 bg-panel rounded p-3 overflow-y-auto">
        {!detail && <p className="text-slate-400 text-sm">Select a run to inspect.</p>}
        {detail && (
          <RunInspector detail={detail} />
        )}
      </div>
    </div>
  );
}

function RunInspector({ detail }: { detail: Run & { agents: any[] } }) {
  return (
    <div className="space-y-3 text-sm">
      <header>
        <h2 className="text-base font-semibold">{detail.topic}</h2>
        <p className="text-slate-400 text-xs">status: {detail.status}</p>
      </header>
      <Section title="Plan">
        <ul className="list-disc ml-5">
          {(detail.config?.steps ?? []).map((s: string, i: number) => (
            <li key={i}>{s}</li>
          ))}
          {!detail.config?.steps?.length && (
            <li className="list-none italic text-slate-500">no steps captured</li>
          )}
        </ul>
      </Section>
      <Section title="Agents">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-slate-400">
              <th className="py-1">role</th>
              <th>state</th>
              <th>input</th>
              <th>output</th>
            </tr>
          </thead>
          <tbody>
            {detail.agents.map((a) => (
              <tr key={a.id} className="border-t border-slate-800 align-top">
                <td className="py-1 pr-2 font-medium">{a.role}</td>
                <td className="pr-2">{a.state}</td>
                <td className="pr-2 truncate max-w-xs">{a.input}</td>
                <td className="pr-2 truncate max-w-xs">{a.output}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
      <Section title="Report">
        <pre className="whitespace-pre-wrap text-xs bg-slate-900 p-2 rounded">
          {detail.config?.artifacts?.report ?? "(see agent rows for details)"}
        </pre>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-1">{title}</h3>
      {children}
    </section>
  );
}
