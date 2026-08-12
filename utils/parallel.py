"""Playing games on every core instead of one.

Phase A of `docs/engine-source-plan-2026-08-12.md`. `selfplay.py` and
`matchup_matrix.py` were entirely sequential on a 12-core machine; this is the
pool they now drive.

Two measurements decided its shape, both taken 12 August 2026:

* **Processes, not threads.** With the agent driving, the harness does 1 710
  steps/s; with a trivial policy the engine alone does 11 281. The agent is
  ~85 % of wall time and it is pure Python, so the GIL binds and threads buy
  nothing. Measured with processes: 12.5 games/s at 1 worker, 62.9 at 6 (5.0x),
  74.4 at 10 (5.95x) on 6 performance cores.
* **The engine allows it.** Two battles run concurrently in one process with
  distinct pointers (see `cg/battle.py`); the one-battle-at-a-time limit was
  `Battle.battle_ptr`, a Python global.

The expensive part of a worker is its SETUP -- `GameInitialize()`, importing
`cg`, and loading two independent agent instances costs about 0.3 s -- so a
worker is initialised once and then drains many jobs. Handing out one game per
task would spend more time starting workers than playing.

**Determinism of the OUTPUT, separately from the engine.** Results come back in
job order, never completion order, so a run is reproducible as a list even when
the engine is unseeded. With `--seeds` (phase B) the games themselves are
reproducible too.
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Per-worker state, built once by `_init_worker`.
_W = {}


def default_jobs():
    """Performance cores, which is what the 5.95x plateau was measured at.

    `os.cpu_count()` reports 12 on this machine but only 6 are performance
    cores; oversubscribing past them bought 0.95x more for 67 % more processes.
    """
    try:
        n = len(os.sched_getaffinity(0))
    except AttributeError:
        n = os.cpu_count() or 1
    if sys.platform == "darwin":
        try:
            import subprocess
            out = subprocess.run(["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                                 capture_output=True, text=True)
            if out.returncode == 0 and out.stdout.strip():
                n = int(out.stdout.strip())
        except Exception:
            pass
    return max(1, n)


# --------------------------------------------------------------------------
# Agent specs: what a worker should build. Must be picklable, so they are
# tuples of plain data -- never a loaded module.
# --------------------------------------------------------------------------

def spec_file(path):
    """The agent in a working-tree file (e.g. main.py)."""
    return ("file", str(path))


def spec_tree(root, name):
    """The agent of an already-exported git tree.

    The tree is exported ONCE in the parent (`selfplay.checkout_tree`) and its
    path passed down. Letting each worker run its own `git archive` would repeat
    the export per core for an identical result.
    """
    return ("tree", str(root), name)


def spec_bot(first_choice="first"):
    """The generic opposing bot.

    `first_choice="second"` makes it DECLINE the first turn; the default
    reproduces every figure on record (the matrix has only ever measured the
    going-second half -- see `matchup_matrix.medir`).
    """
    return ("bot", first_choice)


def _build_agent(spec, name):
    import selfplay
    kind = spec[0]
    if kind == "file":
        return selfplay.load_agent(spec[1], name)
    if kind == "tree":
        root = Path(spec[1])
        return selfplay.load_agent(root / "main.py", name, root=root)
    if kind == "bot":
        from opponent_bot import OpponentBot
        return OpponentBot(first_choice=spec[1])
    raise ValueError(f"unknown agent spec: {spec!r}")


def _init_worker(cand_spec, base_spec):
    os.chdir(_ROOT)  # main.py reads deck.csv relative to the cwd
    for p in (str(_ROOT), str(_ROOT / "tests"), str(_ROOT / "utils")):
        if p not in sys.path:
            sys.path.insert(0, p)
    _W["cand"] = _build_agent(cand_spec, "agente_candidato")
    _W["base"] = _build_agent(base_spec, "agente_base")


def _play_job(job):
    """Plays one game. Returns (index, tag, seat, result) so order is restorable."""
    import selfplay
    i, tag, candidate_seat, deck_cand, deck_base, seed = job
    if candidate_seat == 0:
        p0, p1, d0, d1 = _W["cand"], _W["base"], deck_cand, deck_base
    else:
        p0, p1, d0, d1 = _W["base"], _W["cand"], deck_base, deck_cand
    try:
        r = selfplay.play_game(p0, p1, deck0=d0, deck1=d1, seed=seed)
    except Exception as e:  # a crash in one game must not kill the run
        r = {"result": f"error_p{candidate_seat}", "ganador": 1 - candidate_seat,
             "pasos": 0, "primer_jugador": -1, "premios_tomados": [None, None],
             "excepcion": f"{type(e).__name__}: {e}"[:200]}
    return i, tag, candidate_seat, r


def build_jobs(games, deck_cand=None, deck_base=None, seeds=None, tag=None,
               start=0):
    """The job list: seat alternates, and each job carries its own seed.

    Seat alternation is by INDEX WITHIN THE MATCHUP, so the split is identical
    whatever order the jobs finish in -- the candidate is seat 0 on even
    indices, exactly as the sequential harness did. The same holds for the
    seed, which is why two arms handed the same `seeds` replay the same games.
    """
    jobs = []
    for i in range(games):
        seed = None if seeds is None else seeds[i % len(seeds)]
        jobs.append((start + i, tag, i % 2, deck_cand, deck_base, seed))
    return jobs


def build_matchup_jobs(matchups, seeds=None):
    """One flat job list across EVERY matchup.

    `matchups` is [(tag, opponent_deck, games), ...]. Flattening matters: a pool
    per matchup would pay worker startup 87 times and, worse, idle its cores at
    each matchup's tail while the slowest game finished. One pool over the whole
    matrix keeps every core busy until the last game of the last deck.
    """
    jobs = []
    for tag, deck_base, games in matchups:
        jobs += build_jobs(games, None, deck_base, seeds, tag=tag,
                           start=len(jobs))
    return jobs


def group_by_tag(results):
    """[(tag, seat, result)] -> {tag: [(seat, result), ...]}, order preserved."""
    out = {}
    for tag, seat, r in results:
        out.setdefault(tag, []).append((seat, r))
    return out


def run_jobs(jobs, cand_spec, base_spec, jobs_n=None, progress=None,
             chunk=None):
    """Runs the job list and returns [(tag, candidate_seat, result), ...] IN ORDER.

    `jobs_n=1` runs in this process, without a pool. That is not just an
    optimisation: it is what makes `--jobs 1` a genuine control for the
    acceptance test, since a difference between 1 and N cannot then be blamed on
    the pool being absent.
    """
    jobs_n = jobs_n or default_jobs()
    total = len(jobs)
    out = []

    if jobs_n <= 1:
        _init_worker(cand_spec, base_spec)
        for job in jobs:
            out.append(_play_job(job))
            if progress and len(out) % progress == 0:
                print(f"  ... {len(out)}/{total}", flush=True)
    else:
        import multiprocessing as mp
        # `fork` keeps the parent's sys.path and cwd, and is what macOS needs
        # here: `spawn` would re-import main.py in every worker anyway, but
        # loses the exported git tree path resolution the specs rely on.
        ctx = mp.get_context("fork")
        # Long chunks amortise worker startup; short ones keep the cores fed at
        # the tail. One chunk per core per quarter of the run is the compromise.
        chunk = chunk or max(1, total // (jobs_n * 4))
        with ctx.Pool(jobs_n, initializer=_init_worker,
                      initargs=(cand_spec, base_spec)) as pool:
            for r in pool.imap_unordered(_play_job, jobs, chunksize=chunk):
                out.append(r)
                if progress and len(out) % progress == 0:
                    print(f"  ... {len(out)}/{total}", flush=True)

    out.sort(key=lambda t: t[0])  # job order, never completion order
    return [(tag, seat, r) for _, tag, seat, r in out]
