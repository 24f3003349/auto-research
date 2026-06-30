export default function LiveStrip({ events }: { events: any[] }) {
  const last = events.slice().reverse().slice(0, 30);
  return (
    <div className="bg-panel rounded p-3 h-full">
      <h3 className="text-xs uppercase text-slate-400 mb-2">Live events</h3>
      <ul className="space-y-1 text-xs overflow-y-auto max-h-[80vh]">
        {last.map((e, i) => (
          <li key={i} className="font-mono">
            <span className="text-slate-500">{e.type}</span>
            {e.agent && <span className="ml-1 text-accent">{e.agent}</span>}
            {e.run_id && <span className="ml-1 text-slate-300">→ {e.run_id}</span>}
            {e.score !== undefined && (
              <span className="ml-1 text-ok">score={e.score.toFixed ? e.score.toFixed(2) : e.score}</span>
            )}
            {e.detail && <span className="ml-1 text-slate-300">"{e.detail}"</span>}
          </li>
        ))}
        {last.length === 0 && (
          <li className="text-slate-500">(no events yet — start a run)</li>
        )}
      </ul>
    </div>
  );
}
