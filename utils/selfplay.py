"""Self-play harness: complete agent-vs-agent games with the simulator.

Phase 3 of the strategy improvement architecture: the gate that measures what
no unit test can measure — whether a rule change WINS MORE GAMES.

It loads TWO independent instances of main.py (via importlib, each with
its own tracking globals) and pits them against each other with cg.game
(battle_start/battle_select). The simulator's internal randomness (shuffles, coin
flips) cannot be seeded through the API, so the variance is handled with N games and
SEAT ALTERNATION (the candidate plays half of them as player 0 and
half as player 1).

Usage:
    python utils/selfplay.py --games 100
        # mirror: main.py vs main.py (a sanity check: winrate ~50%)
    python utils/selfplay.py --games 200 --base HEAD~1
        # candidate (the working tree's main.py) vs baseline (a git ref)
    python utils/selfplay.py --games 200 --base HEAD --candidate otra.py
    python utils/selfplay.py --games 200 --opponent deck/opponents/crustle.csv
        # candidate vs the generic BOT piloting an opposing deck (a matchup)
    python utils/selfplay.py --games 200 --opponent ... --base HEAD~1
        # matchup DIFFERENTIAL: candidate-vs-bot and base-vs-bot; the delta
        # between the two winrates is the signal (the bot's absolute level is not)

Output: the score, the candidate's winrate with a 95% Wilson interval, the split
by seat and errors/limits. A game where an agent raises an exception or
returns an invalid choice counts as a LOSS for that agent (a forfeit).
"""

import argparse
import importlib.util
import math
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_TESTS = _ROOT / "tests"
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))
_UTILS = _ROOT / "utils"
if str(_UTILS) not in sys.path:
    sys.path.insert(0, str(_UTILS))

import parallel  # noqa: E402  (needs _UTILS on the path first)
from golden_corpus import reset_agent  # a mirror of the tests' reset

MAX_STEPS = 3000

# Exported git trees, keyed by (ref, name): see `checkout_tree`.
_TREE_CACHE = {}


def load_agent(path, name, root=None):
    """Loads an independent instance of an agent module.

    INDEPENDENT INCLUDES ITS OWN `ptcg/` TREE. Since wave 3 of the refactor the
    state that persists between turns lives in `ptcg.estado.agente.ESTADO`, not in
    main.py's globals. If `ptcg` is left in sys.modules, the two instances
    import the SAME singleton and overwrite each other's state: the matchup stops
    measuring anything and sombra.py reports phantom flips (58 in 20 games the first
    time it happened). By clearing `ptcg*` before each load, each main.py builds
    its own tree; the modules already loaded keep their direct references,
    so the previous instance goes on working with its own.

    `root`, when given, is the directory those `from ptcg... import` lines are
    resolved against -- see `load_agent_from_git`, which is where it matters. It
    is prepended to `sys.path` only while this module executes; the 39 imports
    main.py opens with all run in that window, and rule R4 of
    `utils/lint_architecture.py` (no lazy import of our own package) is what
    guarantees there is no later one to catch the wrong tree.

    `cg` is NOT touched: `cg/sim.py` calls `GameInitialize()` when imported and
    doing that twice ABORTS the interpreter. It stays in sys.modules, so both
    agents keep playing inside the SAME simulator -- which is the point.
    """
    def _ramas_ptcg():
        return [k for k in sys.modules if k == "ptcg" or k.startswith("ptcg.")]

    previos = {k: sys.modules[k] for k in _ramas_ptcg()}
    for k in previos:
        del sys.modules[k]
    if root is not None:
        sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if root is not None:
            try:
                sys.path.remove(str(root))
            except ValueError:
                pass
        # And the ambient tree is RETURNED to sys.modules. The instance just
        # created already keeps direct references to its own, so it keeps its
        # own AGENT_STATE; but if the process were left without the original tree,
        # any later `from ptcg... import` would create a SECOND copy
        # of the package -- and whoever patched there would not affect the agent that was
        # already loaded (it happened: it contaminated tests/test_xerosic_*).
        for k in _ramas_ptcg():
            del sys.modules[k]
        sys.modules.update(previos)
    return mod


def checkout_tree(ref, name):
    """Materialises the WHOLE tree of a git ref and returns its root.

    Cached per (ref, name) for the life of the process, so the baseline is
    exported once however many times it is loaded.
    """
    key = (ref, name)
    cached = _TREE_CACHE.get(key)
    if cached is not None:
        return cached
    root = Path(tempfile.mkdtemp(prefix=f"tree_{name}_"))
    archive = subprocess.run(["git", "archive", "--format=tar", ref],
                             cwd=_ROOT, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(root)], input=archive, check=True)
    _TREE_CACHE[key] = root
    return root


def load_agent_from_git(ref, name):
    """Loads the agent of a git ref -- main.py AND the `ptcg/` package it imports.

    IT USED TO LOAD ONLY main.py, AND THAT MADE THE GATE BLIND TO MOST OF THE
    AGENT (user, August 2026, measured). The baseline was written to a temporary
    file and imported from there, but its `from ptcg... import` lines resolved
    through `sys.path` to the WORKING TREE -- so candidate and baseline shared
    every module object under `ptcg`:

        baseline resolves ptcg.turn.options.card to .../ptcg/turn/options/card.py
        SAME MODULE OBJECT as working tree: True

    That was harmless while main.py WAS the agent. After the refactor it is
    11 328 lines against 26 571 in `ptcg/`, and every rule now lives in the
    package: a change there measured EXACTLY ZERO difference, by construction,
    in both `selfplay.py` and `utils/matchup_matrix.py` -- the two heavy gates
    that decide whether a rule is kept or reverted.

    Exporting the whole tree fixes it. What is deliberately NOT taken from the
    ref is the DECK: main.py reads `deck.csv` relative to the process's working
    directory, so both sides pilot the same 60 cards. Comparing two rule sets on
    two different decks would not be a comparison.
    """
    root = checkout_tree(ref, name)
    return load_agent(root / "main.py", name, root=root)


def parse_seeds(text):
    """'500' -> [1..500]; '3,7,11' -> [3, 7, 11]; None/'' -> None.

    Seed 0 is rejected rather than accepted: the engine reads 0 as "roll one",
    so it would play an UNSEEDED game while the report claimed a seeded one.
    """
    if not text:
        return None
    if "," in text:
        seeds = [int(s) for s in text.split(",") if s.strip()]
    else:
        seeds = list(range(1, int(text) + 1))
    if not seeds or any(not 0 < s < 2 ** 32 for s in seeds):
        raise ValueError("seeds must be in 1..2**32-1")
    return seeds


def read_deck(path=None):
    csv = Path(path or _ROOT / "deck.csv").read_text().split("\n")
    return [int(csv[i]) for i in range(60)]


def _reset_si_aplica(mod):
    # The opposing bot has no tracking; only the main.py instances do.
    if hasattr(mod, "_init_cards_tracking"):
        reset_agent(mod)


def _prizes_left(obs):
    """Prizes each seat has LEFT, or None if they cannot be read."""
    try:
        players = obs["current"]["players"]
        return [len(players[i].get("prize") or []) for i in (0, 1)]
    except (KeyError, IndexError, TypeError):
        return None


def _prizes_taken(pico, final):
    """Prizes TAKEN by each seat = how far its OWN pile has gone down.

    Each player draws from THEIR pile when knocking out, so a seat's prize
    counter measures what THEY have taken, not what has been taken from them.
    Verified against the simulator: in 20 of 25 games the winner ends with
    their own pile at 0 and in none with the opponent's at 0 (the other 5 were
    won by bench-out or deckout, without exhausting the prizes).

    `pico` is the MAXIMUM number of prizes seen during the game, not the reading of
    `battle_start`: there the deal has not happened yet and both piles are
    0, which made the differential come out identically 0 in ALL matchups.
    Since the pile can only go down, its peak IS the initial deal, and it also
    saves hard-coding the 6.

    It returns [None, None] if it could not be read, so the aggregate can
    tell "0 prizes" apart from "not measured".
    """
    if not pico or not final or max(pico) <= 0:
        return [None, None]
    return [max(0, pico[i] - final[i]) for i in (0, 1)]


def play_game(agent_p0, agent_p1, deck0=None, deck1=None,
                  max_steps=MAX_STEPS, seed=None, lib=None):
    """Plays a complete game. Returns a dict with the outcome.

    Since phase A it drives `cg.battle.Battle` -- a battle that owns its own
    engine pointer -- instead of the module-global one in `cg/game.py`. Inside a
    worker the games are still sequential, so the global would have worked; the
    handle is what lets a `seed` exist at all, and what stops a future caller
    from assuming there is only ever one battle.

    `seed`, when given, requires an engine exporting `BattleStartSeeded` (the
    local build, see `utils/local_engine.py`). Same seed and same decisions ->
    the same game, which is what makes a paired comparison possible.

    result: 0/1 (the winner), "limite" (the step cap) or "error_pX" (the agent
    in seat X raised an exception or chose an invalid option -> it loses).

    `premios_tomados`: [p0, p1], the prizes each seat took. It is the
    harness's RESOLUTION metric: the winrate against the generic bot is
    saturated (>93% weighted) and cannot arbitrate a change, but the prizes
    do grade it -- against Marnie the three reference games were lost
    BY ONE PRIZE, and that magnitude disappears when collapsed into won/lost.
    Careful: a game can be won without taking all 6 (bench-out, deckout), so
    the prize differential is NOT a disguised winrate: it measures something else.
    """
    from cg.battle import Battle

    if seed is not None and lib is None:
        # A seed is meaningless on the shipped engine, which ignores it. Resolve
        # the local build here rather than at the call site, so every caller
        # that asks for a seed gets a genuinely reproducible game or an error --
        # never an unseeded game silently reported as seeded.
        import local_engine
        lib = local_engine.load()

    deck = read_deck()
    deck0 = deck0 or deck
    deck1 = deck1 or deck
    _reset_si_aplica(agent_p0)
    _reset_si_aplica(agent_p1)

    battle = Battle(list(deck0), list(deck1), seed=seed, lib=lib)
    obs = battle.obs
    # The prize peak per seat. In `battle_start` the piles are still 0
    # (they have not been dealt), so the initial value is discovered as we go.
    peak_prizes = [0, 0]

    def _watch_prizes():
        actual = _prizes_left(obs)
        if actual:
            for i in (0, 1):
                if actual[i] > peak_prizes[i]:
                    peak_prizes[i] = actual[i]
        return actual

    _watch_prizes()
    agentes = {0: agent_p0, 1: agent_p1}
    steps = 0
    first_player = -1
    try:
        while obs["current"]["result"] == -1 and steps < max_steps:
            yi = obs["current"]["yourIndex"]
            if first_player == -1:
                first_player = obs["current"]["firstPlayer"]
            try:
                choice = agentes[yi].agent(obs)
                obs = battle.select(choice)
            except Exception:
                return {"result": f"error_p{yi}", "ganador": 1 - yi,
                        "pasos": steps, "primer_jugador": first_player,
                        "premios_tomados": _prizes_taken(
                            peak_prizes, _prizes_left(obs))}
            _watch_prizes()
            steps += 1
        prizes = _prizes_taken(peak_prizes, _prizes_left(obs))
        if obs["current"]["result"] == -1:
            return {"result": "limite", "ganador": None, "pasos": steps,
                    "primer_jugador": first_player,
                    "premios_tomados": prizes}
        winner = obs["current"]["result"]
        return {"result": winner, "ganador": winner, "pasos": steps,
                "primer_jugador": obs["current"]["firstPlayer"]
                if first_player == -1 else first_player,
                "premios_tomados": prizes}
    finally:
        battle.finish()


def wilson_95(victorias, n):
    """95% Wilson interval for a proportion."""
    if n == 0:
        return (0.0, 1.0)
    z = 1.959963984540054
    p = victorias / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    delta = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - delta), min(1.0, centro + delta))


def new_stats(games):
    """The empty accumulator. One shape, so sequential and parallel agree."""
    return {
        "games": games, "candidate": 0, "base": 0, "limites": 0,
        "errores_candidato": 0, "errores_base": 0,
        "cand_j0": [0, 0], "cand_j1": [0, 0],  # [wins, played]
        "cand_primero": [0, 0], "cand_segundo": [0, 0],
        "pasos_totales": 0,
        # The RESOLUTION metric: the winrate is saturated against the bot, the
        # prizes are not. They are accumulated per AGENT (not per seat), because the
        # candidate alternates seats on every game.
        "premios_candidato": 0, "premios_base": 0, "partidas_con_premios": 0,
    }


def accumulate(stats, r, candidate_seat):
    """Folds ONE game result into the accumulator.

    Extracted so the sequential and the parallel tournament share it verbatim.
    When `--jobs 1` and `--jobs 6` disagree the cause cannot be the bookkeeping,
    which is exactly what phase A's acceptance test needs to be able to assume.
    """
    stats["pasos_totales"] += r["pasos"]
    prizes = r.get("premios_tomados") or [None, None]
    if prizes[0] is not None and prizes[1] is not None:
        stats["premios_candidato"] += prizes[candidate_seat]
        stats["premios_base"] += prizes[1 - candidate_seat]
        stats["partidas_con_premios"] += 1
    if isinstance(r["result"], str) and r["result"].startswith("error"):
        asiento_err = int(r["result"][-1])
        if asiento_err == candidate_seat:
            stats["errores_candidato"] += 1
        else:
            stats["errores_base"] += 1
    if r["ganador"] is None:
        stats["limites"] += 1
    else:
        gano_cand = (r["ganador"] == candidate_seat)
        stats["candidate" if gano_cand else "base"] += 1
        seat = stats["cand_j0"] if candidate_seat == 0 else stats["cand_j1"]
        seat[1] += 1
        seat[0] += int(gano_cand)
        if r["primer_jugador"] == candidate_seat:
            stats["cand_primero"][1] += 1
            stats["cand_primero"][0] += int(gano_cand)
        elif r["primer_jugador"] == 1 - candidate_seat:
            stats["cand_segundo"][1] += 1
            stats["cand_segundo"][0] += int(gano_cand)
    return stats


def torneo(candidate, base, games, progress=None,
           deck_candidate=None, deck_base=None, seeds=None):
    """Pits the candidate against the base alternating seats. Returns stats.

    deck_candidato/deck_base: lists of 60 ids; by default, deck.csv.
    Each deck travels with its agent when the seat changes.

    This is the IN-PROCESS tournament, kept because it takes agents that are
    already loaded -- which the pool cannot, since a loaded module does not
    pickle. `torneo_paralelo` is the one the command line drives.
    """
    stats = new_stats(games)
    for i in range(games):
        candidate_seat = i % 2
        if candidate_seat == 0:
            p0, p1, d0, d1 = candidate, base, deck_candidate, deck_base
        else:
            p0, p1, d0, d1 = base, candidate, deck_base, deck_candidate
        seed = None if seeds is None else seeds[i % len(seeds)]
        r = play_game(p0, p1, deck0=d0, deck1=d1, seed=seed)
        accumulate(stats, r, candidate_seat)
        if progress and (i + 1) % progress == 0:
            print(f"  ... {i + 1}/{games} "
                  f"({stats['candidate']}-{stats['base']})", flush=True)
    return stats


def torneo_paralelo(cand_spec, base_spec, games, jobs=None, progress=None,
                    deck_candidate=None, deck_base=None, seeds=None):
    """The same tournament, spread over processes. Same stats, same shape.

    Agents arrive as SPECS (see `utils/parallel.py`), not as loaded modules: a
    module object cannot be pickled to a worker, and loading it once per worker
    is what makes the pool worth having anyway.
    """
    import parallel
    jobs_list = parallel.build_jobs(games, deck_candidate, deck_base, seeds)
    results = parallel.run_jobs(jobs_list, cand_spec, base_spec,
                                jobs_n=jobs, progress=progress)
    stats = new_stats(games)
    for _tag, candidate_seat, r in results:
        accumulate(stats, r, candidate_seat)
    return stats


def _pct(v, n):
    return f"{100 * v / n:.1f}%" if n else "n/a"


def prizes_per_game(stats):
    """(prizes/game of the candidate, of the base, the differential). None if there are none."""
    n = stats.get("partidas_con_premios") or 0
    if not n:
        return (None, None, None)
    pc = stats["premios_candidato"] / n
    pb = stats["premios_base"] / n
    return (pc, pb, pc - pb)


def informe(stats, etiqueta_cand, etiqueta_base):
    dec = stats["candidate"] + stats["base"]
    lo, hi = wilson_95(stats["candidate"], dec) if dec else (0, 1)
    lines = [
        f"Self-play: candidato={etiqueta_cand}  vs  base={etiqueta_base}",
        f"Partidas: {stats['games']}  (decididas {dec}, "
        f"limite {stats['limites']})",
        f"Marcador: candidato {stats['candidate']} - {stats['base']} base",
        f"Winrate candidato: {_pct(stats['candidate'], dec)} "
        f"[IC95 {100 * lo:.1f}%-{100 * hi:.1f}%]",
        f"  como J0: {_pct(*stats['cand_j0'])} "
        f"({stats['cand_j0'][0]}/{stats['cand_j0'][1]})   "
        f"como J1: {_pct(*stats['cand_j1'])} "
        f"({stats['cand_j1'][0]}/{stats['cand_j1'][1]})",
        f"  saliendo primero: {_pct(*stats['cand_primero'])} "
        f"({stats['cand_primero'][0]}/{stats['cand_primero'][1]})   "
        f"segundo: {_pct(*stats['cand_segundo'])} "
        f"({stats['cand_segundo'][0]}/{stats['cand_segundo'][1]})",
        f"Errores (forfeit): candidato {stats['errores_candidato']}, "
        f"base {stats['errores_base']}",
        f"Pasos totales: {stats['pasos_totales']}",
    ]
    pc, pb, dif = prizes_per_game(stats)
    if pc is not None:
        lines.append(
            f"Premios/partida: candidato {pc:.2f} - {pb:.2f} base  "
            f"(diferencial {dif:+.2f})")
        lines.append(
            "  el winrate se satura contra el bot; el diferencial de premios "
            "gradua y detecta cambios que el marcador no ve")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--base", default=None,
                    help="git ref for the baseline (e.g. HEAD~1); without"
                         "                         --base: mirror, main.py"
                         "                         vs main.py")
    ap.add_argument("--candidate", default="main.py",
                    help="path to the candidate agent (default: main.py)")
    ap.add_argument("--progress", type=int, default=20,
                    help="print the score every N games (0 = never)")
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck: the opponent becomes the"
                         "                         GENERIC bot piloting it"
                         "                         (matchup mode)")
    ap.add_argument("--jobs", type=int, default=None,
                    help="worker processes (default: performance cores). "
                         "--jobs 1 runs in-process, and is the control for the "
                         "parallel path")
    ap.add_argument("--seeds", default=None,
                    help="engine seeds: 'N' for 1..N, or a comma list. Needs "
                         "the local engine (utils/local_engine.py); makes the "
                         "two arms replay the SAME games")
    args = ap.parse_args(argv)

    seeds = parse_seeds(args.seeds)
    if seeds:
        # Fail here, not 400 games in, if the engine cannot honour a seed.
        import local_engine
        local_engine.load()

    cand_spec = parallel.spec_file(_ROOT / args.candidate)

    def _base_spec(ref):
        return parallel.spec_tree(checkout_tree(ref, "agente_base"),
                                  "agente_base")

    if args.opponent:
        opponent_deck = read_deck(_ROOT / args.opponent)
        stats = torneo_paralelo(cand_spec, parallel.spec_bot(), args.games,
                                jobs=args.jobs,
                                progress=args.progress or None,
                                deck_base=opponent_deck, seeds=seeds)
        print(informe(stats, args.candidate, f"bot+{args.opponent}"))
        if args.base:
            stats_base = torneo_paralelo(
                _base_spec(args.base), parallel.spec_bot(), args.games,
                jobs=args.jobs, progress=args.progress or None,
                deck_base=opponent_deck, seeds=seeds)
            print()
            print(informe(stats_base, f"{args.base} (git)",
                          f"bot+{args.opponent}"))
            dec_c = stats["candidate"] + stats["base"]
            dec_b = stats_base["candidate"] + stats_base["base"]
            wr_c = stats["candidate"] / dec_c if dec_c else 0
            wr_b = stats_base["candidate"] / dec_b if dec_b else 0
            print(f"\nMatchup DELTA (candidate - {args.base}): "
                  f"{100 * (wr_c - wr_b):+.1f} points "
                  f"({100 * wr_c:.1f}% vs {100 * wr_b:.1f}%)")
        return 0

    if args.base:
        base_spec = _base_spec(args.base)
        etiqueta_base = f"{args.base} (git)"
    else:
        base_spec = parallel.spec_file(_ROOT / args.candidate)
        etiqueta_base = f"{args.candidate} (espejo)"

    stats = torneo_paralelo(cand_spec, base_spec, args.games, jobs=args.jobs,
                            progress=args.progress or None, seeds=seeds)
    print(informe(stats, args.candidate, etiqueta_base))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
