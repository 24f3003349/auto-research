export type Run = {
  id: string;
  topic: string;
  objective: string | null;
  constraints: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  config: any;
};

export type Agent = {
  id: string;
  run_id: string;
  role: string;
  state: string;
  input: string | null;
  output: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type WikiPage = {
  id: string;
  title: string;
  body: string;
  tags: string[];
  source: string | null;
  run_id: string | null;
  created_at: string;
  updated_at: string;
};

const base = "/api";

async function asJson<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`http ${r.status}: ${await r.text()}`);
  return (await r.json()) as T;
}

export const api = {
  health: () => fetch(`${base}/health`).then(asJson<{ status: string; provider: string }>),

  runs: {
    list: () => fetch(`${base}/runs`).then(asJson<Run[]>),
    create: (body: { topic: string; objective?: string }) =>
      fetch(`${base}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(asJson<{ id: string; job_id: string }>),
    get: (id: string) => fetch(`${base}/runs/${id}`).then(asJson<Run & { agents: Agent[] }>),
  },

  wiki: {
    list: () => fetch(`${base}/wiki/pages`).then(asJson<WikiPage[]>),
    search: (q: string) =>
      fetch(`${base}/wiki/search?q=${encodeURIComponent(q)}`).then(asJson<WikiPage[]>),
    create: (body: { title: string; body: string; tags?: string[] }) =>
      fetch(`${base}/wiki/pages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(asJson<WikiPage>),
    get: (id: string) => fetch(`${base}/wiki/pages/${id}`).then(asJson<WikiPage & { backlinks: WikiPage[] }>),
  },

  evolution: {
    run: (body: {
      seed: string;
      pop_size: number;
      generations: number;
      mutation_rate: number;
      fitness_kind: string;
    }) =>
      fetch(`${base}/evolution/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(asJson<EvoRunResponse>),
  },
};

export type EvoRunResponse = {
  run_id: string;
  mutation_rate: number;
  generations: Array<{
    generation: number;
    best_fitness: number;
    mean_fitness: number;
    diversity: number;
    plateau: boolean;
  }>;
  population: Array<{
    id: string;
    candidate: string;
    fitness: number;
    generation: number;
    parent_id: string | null;
  }>;
  events: any[];
};

export function newEventStream(onEvent: (e: any) => void): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
  ws.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data));
    } catch {
      // ignore
    }
  };
  return ws;
}
