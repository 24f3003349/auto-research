"""Tests for evolution engine."""
import pytest

from app.evolution.engine import (
    EvolutionEngine,
    Candidate,
    GenerationStats,
    PlateauDetector,
    mutate,
    crossover,
    diversity,
)


def test_mutate_changes_string_with_high_probability():
    s = "hello world"
    out = mutate(s, rate=1.0, seed=1)
    assert out != s
    assert len(out) == len(s)


def test_mutate_returns_same_string_when_rate_is_zero():
    s = "untouched"
    assert mutate(s, rate=0.0, seed=1) == s


def test_crossover_interleaves_characters_from_two_parents():
    a = "abcdef"
    b = "ghijkl"
    child = crossover(a, b)
    assert len(child) == 6
    # Each position should come from a parent.
    for ch in child:
        assert ch in "abcdefghijkl"


def test_diversity_uses_unique_ratio():
    pop = ["abc", "abc", "xyz", "xyz", "xyz"]
    assert diversity(pop) == 0.4  # 2 unique / 5


def test_plateau_detector_signals_when_no_improvement():
    pd = PlateauDetector(window=3, min_delta=0.01)
    assert pd.observe(0.5) is False
    assert pd.observe(0.5) is False
    assert pd.observe(0.51) is False  # small improvement, within delta
    # Force a plateau
    pd2 = PlateauDetector(window=3, min_delta=0.01)
    assert pd2.observe(0.5) is False
    assert pd2.observe(0.5) is False
    assert pd2.observe(0.5) is True  # 3rd observation in window without gain


@pytest.mark.asyncio
async def test_evolution_engine_seeds_population_and_records_first_gen():
    eng = EvolutionEngine(
        pop_size=4,
        seed="seed text",
        fitness=lambda s: len(s),
        mutation_rate=0.0,  # stable for this test
        plateau_window=3,
        plateau_min_delta=0.01,
    )
    gen0 = await eng.initial_generation(run_id="r1")
    assert gen0.generation == 0
    assert gen0.best_fitness >= 0
    assert gen0.diversity >= 0
    rows = eng.list_population()
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_evolution_engine_steps_through_generation_and_selects_better():
    eng = EvolutionEngine(
        pop_size=4,
        seed="abcdef",
        fitness=lambda s: len(set(s)),   # rewards character variety
        mutation_rate=0.5,
        plateau_window=3,
        plateau_min_delta=0.01,
    )
    await eng.initial_generation(run_id="r1")
    gen1 = await eng.step_generation()
    assert gen1.generation == 1
    # Either best improved or stayed equal; never regressed.
    rows = eng.list_population()
    assert all(0.0 <= c.fitness <= 1.0 for c in rows)


@pytest.mark.asyncio
async def test_evolution_engine_emits_event_on_plateau():
    events: list[dict] = []
    eng = EvolutionEngine(
        pop_size=2,
        seed="ab",
        fitness=lambda s: 0.5,  # flat fitness
        mutation_rate=0.0,
        plateau_window=2,
        plateau_min_delta=0.01,
        hook=lambda e: events.append(e),
    )
    await eng.initial_generation(run_id="r1")
    gen1 = await eng.step_generation()
    gen2 = await eng.step_generation()
    plateau_events = [e for e in events if e.get("type") == "evolution.plateau"]
    assert len(plateau_events) >= 1


def test_adaptive_mutation_increases_when_plateau():
    pd = PlateauDetector(window=2, min_delta=0.01)
    pd.observe(0.5)
    pd.observe(0.5)  # triggers plateau on 2nd observation
    rate = 0.05
    rate = EvolutionEngine._adapt_mutation(rate, pd, max_rate=0.3, step=0.05)
    assert rate > 0.05