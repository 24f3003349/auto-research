"""Evolution Lab.

Evolves string-typed candidates (prompts, heuristics, strategy snippets).
A candidate's fitness is delegated to a pluggable FitnessFunc — in practice
this is the evaluator agent. Includes plateau detection, adaptive mutation,
diversity bonus, and an event hook for UI streaming.
"""
from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.storage.db import Database


FitnessFunc = Callable[[str], float]
HookFunc = Callable[[dict], None]


# ----- pure helpers (deterministic given seed) -----


def mutate(s: str, rate: float, seed: int | None = None) -> str:
    rng = random.Random(seed) if seed is not None else random
    if rate <= 0:
        return s
    alphabet = string.ascii_letters + " .,"
    chars = list(s)
    for i in range(len(chars)):
        if rng.random() < rate:
            chars[i] = rng.choice(alphabet)
    return "".join(chars)


def crossover(a: str, b: str) -> str:
    if not a or not b:
        return a or b
    n = max(len(a), len(b))
    aa = a.ljust(n, "-")
    bb = b.ljust(n, "-")
    rng = random.Random()
    return "".join(aa[i] if rng.random() < 0.5 else bb[i] for i in range(n)).rstrip("-")


def diversity(population: list[str]) -> float:
    if not population:
        return 0.0
    return len({p for p in population}) / len(population)


# ----- candidate + generation records -----


@dataclass
class Candidate:
    id: str
    candidate: str
    fitness: float
    generation: int
    parent_id: str | None
    metadata: dict = field(default_factory=dict)


@dataclass
class GenerationStats:
    generation: int
    best_fitness: float
    mean_fitness: float
    diversity: float
    plateau: bool

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ----- plateau detector -----


class PlateauDetector:
    """Tracks best-fitness trend; signals once improvement stalls."""

    def __init__(self, window: int = 5, min_delta: float = 0.01):
        self.window = max(2, window)
        self.min_delta = min_delta
        self._history: list[float] = []
        self._triggered = False

    def observe(self, best: float) -> bool:
        self._history.append(best)
        if len(self._history) < self.window:
            return False
        recent = self._history[-self.window :]
        spread = max(recent) - min(recent)
        stalled = spread < self.min_delta
        if stalled and not self._triggered:
            self._triggered = True
            return True
        # If improvement resumes, reset trigger.
        if spread >= self.min_delta:
            self._triggered = False
        return False

    def recent(self) -> list[float]:
        return list(self._history[-self.window :])


# ----- evolution engine -----


class EvolutionEngine:
    def __init__(
        self,
        pop_size: int = 8,
        seed: str = "seed",
        fitness: FitnessFunc | None = None,
        mutation_rate: float = 0.05,
        plateau_window: int = 5,
        plateau_min_delta: float = 0.01,
        diversity_bonus: float = 0.0,
        db: Database | None = None,
        hook: HookFunc | None = None,
        max_mutation_rate: float = 0.3,
    ):
        self.pop_size = pop_size
        self.seed = seed
        self.mutation_rate = mutation_rate
        self.max_mutation_rate = max_mutation_rate
        self.diversity_bonus = diversity_bonus
        self.hook = hook or (lambda e: None)
        self.db = db
        self._fitness_fn = fitness or (lambda s: 0.5)
        self._detector = PlateauDetector(plateau_window, plateau_min_delta)
        self._generation = 0
        self._memory: list[Candidate] = []  # fallback when db is None
        self._memory_counter = 0

    # ----- public API -----

    async def initial_generation(self, run_id: str) -> GenerationStats:
        rng = random.Random()
        seeds = []
        for _ in range(self.pop_size):
            variant = mutate(self.seed, rate=0.3, seed=rng.randint(0, 1_000_000))
            seeds.append(variant)
        stats = self._evaluate_and_persist(run_id, 0, seeds, parents=None)
        self._emit("evolution.generation", run_id=run_id, **stats.to_dict())
        return stats

    async def step_generation(self, run_id: str | None = None) -> GenerationStats:
        run_id = run_id or "evolve"
        self._generation += 1
        gens = self._detector.recent()
        # If fitness plateaued, inject one random immigrant.
        inject_immigrant = bool(gens) and (
            max(gens) - min(gens) < self._detector.min_delta
        )
        pop_now = self._current_population_texts()
        next_pop: list[tuple[str, str | None]] = []  # (text, parent_id)
        # Elitism: keep top 2 candidates.
        ranked = sorted(
            zip(pop_now, self._current_population_ids()),
            key=lambda kv: self._safe_fitness(kv[0]),
            reverse=True,
        )
        elites = ranked[:2]
        for text, cid in elites:
            next_pop.append((text, cid))

        # Mutate / crossover the rest.
        rng = random.Random()
        while len(next_pop) < self.pop_size:
            parents = [t for t, _ in ranked] if ranked else [self.seed]
            a = rng.choice(parents)
            b = rng.choice(parents)
            child_text = crossover(a, b)
            child_text = mutate(child_text, rate=self.mutation_rate)
            parent_id = ranked[0][1] if ranked else None
            next_pop.append((child_text, parent_id))

        if inject_immigrant and len(next_pop) > 0:
            immigrant = mutate(
                self.seed, rate=0.5, seed=rng.randint(0, 1_000_000)
            )
            next_pop[-1] = (immigrant, None)

        stats = self._evaluate_and_persist(
            run_id, self._generation, [t for t, _ in next_pop],
            parents=[p for _, p in next_pop],
        )
        plateau_now = self._detector.observe(stats.best_fitness)
        if plateau_now:
            stats.plateau = True
            # adaptive mutation
            self.mutation_rate = self._adapt_mutation(
                self.mutation_rate, self._detector,
                max_rate=self.max_mutation_rate,
            )
            self._emit(
                "evolution.plateau",
                run_id=run_id,
                generation=stats.generation,
                mutation_rate=self.mutation_rate,
            )
        self._emit(
            "evolution.generation",
            run_id=run_id,
            **stats.to_dict(),
            mutation_rate=self.mutation_rate,
        )
        return stats

    def list_population(self) -> list[Candidate]:
        if self.db is None:
            return self._in_memory_population()
        rows = self.db.fetchall(
            "SELECT id, candidate, fitness, generation, parent_id, metadata "
            "FROM evolution_population ORDER BY created_at ASC"
        )
        out: list[Candidate] = []
        for r in rows:
            meta_raw = r[5]
            meta = json_loads_safe(meta_raw)
            out.append(
                Candidate(
                    id=r[0], candidate=r[1], fitness=r[2],
                    generation=r[3], parent_id=r[4], metadata=meta,
                )
            )
        return out

    # ----- helpers -----

    @staticmethod
    def _adapt_mutation(
        rate: float, det: PlateauDetector, *, max_rate: float, step: float = 0.05
    ) -> float:
        return min(max_rate, rate + step)

    def _evaluate_and_persist(
        self,
        run_id: str,
        generation: int,
        texts: list[str],
        parents: list[str | None] | None,
    ) -> GenerationStats:
        evaluated: list[tuple[str, float, str | None]] = []
        for i, text in enumerate(texts):
            try:
                f = float(self._safe_fitness(text))
            except Exception:
                f = 0.0
            parent = parents[i] if parents else None
            evaluated.append((text, f, parent))
        for text, f, parent in evaluated:
            self._persist_candidate(run_id, generation, text, f, parent)
        best = max(f for _, f, _ in evaluated) if evaluated else 0.0
        mean = sum(f for _, f, _ in evaluated) / max(1, len(evaluated))
        div = diversity([t for t, _, _ in evaluated])
        plateau = bool(
            self._detector.recent()
            and max(self._detector.recent()) - min(self._detector.recent())
            < self._detector.min_delta
        )
        return GenerationStats(
            generation=generation,
            best_fitness=best,
            mean_fitness=mean,
            diversity=div,
            plateau=plateau,
        )

    def _safe_fitness(self, text: str) -> float:
        f = float(self._fitness_fn(text))
        return min(1.0, max(0.0, f))

    def _emit(self, type_: str, **detail) -> None:
        try:
            self.hook({"type": type_, **detail})
        except Exception:
            pass

    def _persist_candidate(
        self, run_id: str, generation: int, text: str,
        fitness: float, parent_id: str | None,
    ) -> None:
        self._memory_counter += 1
        cid = f"cand_{self._memory_counter:04d}"
        cand = Candidate(
            id=cid, candidate=text, fitness=fitness,
            generation=generation, parent_id=parent_id,
            metadata={"run_id": run_id},
        )
        self._memory.append(cand)
        if self.db is None:
            return
        cid_db = f"cand_{uuid.uuid4().hex[:10]}"
        cand.id = cid_db
        self.db.execute(
            "INSERT INTO evolution_population "
            "(id, candidate, fitness, generation, parent_id, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cid_db, text, fitness, generation, parent_id, run_id),
        )
        self.db.execute(
            "INSERT INTO evolution_generations "
            "(run_id, generation, best_fitness, mean_fitness, diversity, plateau) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (run_id, generation, fitness, fitness, 0.0),
        )

    def _current_population_texts(self) -> list[str]:
        if self.db is None:
            return [c.candidate for c in self._in_memory_population()]
        rows = self.db.fetchall(
            "SELECT candidate FROM evolution_population "
            "WHERE generation = (SELECT MAX(generation) FROM evolution_population)"
        )
        return [r[0] for r in rows]

    def _current_population_ids(self) -> list[str]:
        if self.db is None:
            return [c.id for c in self._in_memory_population()]
        rows = self.db.fetchall(
            "SELECT id FROM evolution_population "
            "WHERE generation = (SELECT MAX(generation) FROM evolution_population)"
            " ORDER BY created_at ASC"
        )
        return [r[0] for r in rows]

    def _in_memory_population(self) -> list[Candidate]:
        return list(self._memory)

def json_loads_safe(s):
    import json

    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


def llm_fitness_for_prompts(evaluator) -> FitnessFunc:
    """Adapt the agent harness's evaluator into a FitnessFunc.

    Usage:
        fitness = llm_fitness_for_prompts(
            lambda prompt: agent_evaluate(prompt, "improve clarity", provider)
        )
    """

    def fn(prompt: str) -> float:
        try:
            return float(evaluator(prompt))
        except Exception:
            return 0.0

    return fn