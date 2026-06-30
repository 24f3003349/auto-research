import { useEffect, useState } from "react";
import { api, newEventStream, type Run } from "./api";
import RunsPane from "./panes/RunsPane";
import WikiPane from "./panes/WikiPane";
import EvolutionPane from "./panes/EvolutionPane";
import LiveStrip from "./panes/LiveStrip";

type Tab = "runs" | "wiki" | "evolution";

export default function App() {
  const [tab, setTab] = useState<Tab>("runs");
  const [provider, setProvider] = useState<string>("");
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    api.health().then((h) => setProvider(h.provider)).catch(() => setProvider("offline"));
    const ws = newEventStream((e) => setEvents((prev) => [...prev.slice(-99), e]));
    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="px-6 py-3 border-b border-slate-700 flex items-center justify-between bg-panel">
        <div>
          <h1 className="text-lg font-semibold">Auto-Research Cockpit</h1>
          <p className="text-xs text-slate-400">
            provider: {provider || "..."}
          </p>
        </div>
        <nav className="flex gap-1">
          {(["runs", "wiki", "evolution"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={
                "px-3 py-1.5 rounded text-sm " +
                (tab === t
                  ? "bg-accent text-slate-900 font-semibold"
                  : "bg-slate-800 text-slate-200 hover:bg-slate-700")
              }
            >
              {t === "runs" ? "Research Runs" : t === "wiki" ? "LLM Wiki" : "Evolution Lab"}
            </button>
          ))}
        </nav>
      </header>

      <main className="flex-1 p-4 grid grid-cols-12 gap-4">
        {tab === "runs" && (
          <>
            <section className="col-span-9"><RunsPane events={events} /></section>
            <aside className="col-span-3"><LiveStrip events={events} /></aside>
          </>
        )}
        {tab === "wiki" && (
          <section className="col-span-12"><WikiPane /></section>
        )}
        {tab === "evolution" && (
          <section className="col-span-12"><EvolutionPane /></section>
        )}
      </main>
    </div>
  );
}
