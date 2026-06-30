import { useEffect, useState } from "react";
import { api, type WikiPage } from "../api";

export default function WikiPane() {
  const [q, setQ] = useState("");
  const [pages, setPages] = useState<WikiPage[]>([]);
  const [selected, setSelected] = useState<WikiPage | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newBody, setNewBody] = useState("");
  const [newTags, setNewTags] = useState("");

  const refresh = (query = "") => {
    if (query.trim()) api.wiki.search(query).then(setPages).catch(() => setPages([]));
    else api.wiki.list().then(setPages).catch(() => setPages([]));
  };
  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const t = setTimeout(() => refresh(q), 200);
    return () => clearTimeout(t);
  }, [q]);

  async function createPage(e: React.FormEvent) {
    e.preventDefault();
    await api.wiki.create({
      title: newTitle || "Untitled",
      body: newBody,
      tags: newTags.split(",").map((s) => s.trim()).filter(Boolean),
    });
    setNewTitle("");
    setNewBody("");
    setNewTags("");
    refresh(q);
  }

  return (
    <div className="grid grid-cols-12 gap-4 h-full">
      <div className="col-span-4 bg-panel rounded p-3 flex flex-col">
        <input
          placeholder="Search wiki (title, body, tags)…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm mb-3"
        />
        <ul className="flex-1 overflow-y-auto divide-y divide-slate-800">
          {pages.map((p) => (
            <li
              key={p.id}
              onClick={() => setSelected(p)}
              className={
                "p-2 cursor-pointer text-sm " +
                (selected?.id === p.id ? "bg-slate-800" : "hover:bg-slate-800/40")
              }
            >
              <div className="font-medium">{p.title}</div>
              <div className="text-xs text-slate-400 truncate">
                {p.body.slice(0, 80)}
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {p.tags.map((t) => (
                  <span key={t} className="text-[10px] bg-slate-700 px-1.5 py-0.5 rounded">
                    {t}
                  </span>
                ))}
              </div>
            </li>
          ))}
        </ul>

        <form onSubmit={createPage} className="mt-3 space-y-1">
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="New page title"
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs"
          />
          <textarea
            value={newBody}
            onChange={(e) => setNewBody(e.target.value)}
            placeholder="Body (markdown)"
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs h-20"
          />
          <input
            value={newTags}
            onChange={(e) => setNewTags(e.target.value)}
            placeholder="tags, comma-separated"
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs"
          />
          <button className="bg-accent text-slate-900 font-semibold rounded px-3 py-1 text-xs">
            + Add page
          </button>
        </form>
      </div>

      <div className="col-span-8 bg-panel rounded p-4 overflow-y-auto">
        {!selected && <p className="text-slate-400 text-sm">Pick a page to read it.</p>}
        {selected && (
          <article className="prose prose-invert max-w-none text-sm">
            <h2 className="text-lg font-semibold">{selected.title}</h2>
            <div className="text-xs text-slate-400 mb-3">
              {selected.source ? `source: ${selected.source}` : ""}
              {selected.run_id ? ` · run: ${selected.run_id}` : ""}
            </div>
            <pre className="whitespace-pre-wrap font-sans">{selected.body}</pre>
            <Backlinks title={selected.title} currentId={selected.id} />
          </article>
        )}
      </div>
    </div>
  );
}

function Backlinks({ title, currentId }: { title: string; currentId: string }) {
  const [items, setItems] = useState<WikiPage[]>([]);
  useEffect(() => {
    api.wiki.search(title).then(setItems).catch(() => setItems([]));
  }, [title]);
  const found = items.filter((p) => p.id !== currentId && p.body.includes(`[[${title}]]`));
  if (!found.length) return null;
  return (
    <section className="mt-6">
      <h3 className="text-xs uppercase text-slate-400">Backlinks</h3>
      <ul className="text-sm list-disc ml-5">
        {found.map((p) => (
          <li key={p.id}>{p.title}</li>
        ))}
      </ul>
    </section>
  );
}
