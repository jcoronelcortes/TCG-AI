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
    python utils/selfplay.py --partidas 100
        # mirror: main.py vs main.py (a sanity check: winrate ~50%)
    python utils/selfplay.py --partidas 200 --base HEAD~1
        # candidate (the working tree's main.py) vs baseline (a git ref)
    python utils/selfplay.py --partidas 200 --base HEAD --candidato otra.py
    python utils/selfplay.py --partidas 200 --rival deck/rivales/crustle.csv
        # candidate vs the generic BOT piloting an opposing deck (a matchup)
    python utils/selfplay.py --partidas 200 --rival ... --base HEAD~1
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

from golden_corpus import reset_agente  # a mirror of the tests' reset

MAX_STEPS = 3000


def load_agent(path, name):
    """Loads an independent instance of an agent module.

    INDEPENDENT INCLUDES ITS OWN `ptcg/` TREE. Since wave 3 of the refactor the
    state that persists between turns lives in `ptcg.estado.agente.ESTADO`, not in
    main.py's globals. If `ptcg` is left in sys.modules, the two instances
    import the SAME singleton and overwrite each other's state: the matchup stops
    measuring anything and sombra.py reports phantom flips (58 in 20 games the first
    time it happened). By clearing `ptcg*` before each load, each main.py builds
    its own tree; the modules already loaded keep their direct references,
    so the previous instance goes on working with its own.

    `cg` is NOT touched: `cg/sim.py` calls `GameInitialize()` when imported and
    doing that twice ABORTS the interpreter.
    """
    def _ramas_ptcg():
        return [k for k in sys.modules if k == "ptcg" or k.startswith("ptcg.")]

    previos = {k: sys.modules[k] for k in _ramas_ptcg()}
    for k in previos:
        del sys.modules[k]
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        # And the ambient tree is RETURNED to sys.modules. The instance just
        # created already keeps direct references to its own, so it keeps its
        # own ESTADO; but if the process were left without the original tree,
        # any later `from ptcg... import` would create a SECOND copy
        # of the package -- and whoever patched there would not affect the agent that was
        # already loaded (it happened: it contaminated tests/test_xerosic_*).
        for k in _ramas_ptcg():
            del sys.modules[k]
        sys.modules.update(previos)
    return mod


def load_agent_from_git(ref, name):
    """Loads the main.py version of a git ref (the baseline)."""
    fuente = subprocess.run(
        ["git", "show", f"{ref}:main.py"], cwd=_ROOT, capture_output=True,
        text=True, check=True).stdout
    with tempfile.NamedTemporaryFile(
            "w", suffix=".py", prefix=f"main_{name}_",
            delete=False) as f:
        f.write(fuente)
        path = f.name
    return load_agent(path, name)


def read_deck(path=None):
    csv = Path(path or _ROOT / "deck.csv").read_text().split("\n")
    return [int(csv[i]) for i in range(60)]


def _reset_si_aplica(mod):
    # The opposing bot has no tracking; only the main.py instances do.
    if hasattr(mod, "_init_cards_tracking"):
        reset_agente(mod)


def _prizes_left(obs):
    """Prizes each seat has LEFT, or None if they cannot be read."""
    try:
        jugadores = obs["current"]["players"]
        return [len(jugadores[i].get("prize") or []) for i in (0, 1)]
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


def play_game(agente_p0, agente_p1, deck0=None, deck1=None,
                  max_steps=MAX_STEPS):
    """Plays a complete game. Returns a dict with the outcome.

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
    from cg import game

    deck = read_deck()
    deck0 = deck0 or deck
    deck1 = deck1 or deck
    _reset_si_aplica(agente_p0)
    _reset_si_aplica(agente_p1)

    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(
            f"battle_start fallo: errorPlayer={sd.errorPlayer} "
            f"errorType={sd.errorType}")
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
    agentes = {0: agente_p0, 1: agente_p1}
    steps = 0
    first_player = -1
    try:
        while obs["current"]["result"] == -1 and steps < max_steps:
            yi = obs["current"]["yourIndex"]
            if first_player == -1:
                first_player = obs["current"]["firstPlayer"]
            try:
                choice = agentes[yi].agent(obs)
                obs = game.battle_select(choice)
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
        game.battle_finish()


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


def torneo(candidato, base, partidas, progreso=None,
           deck_candidato=None, deck_base=None):
    """Pits the candidate against the base alternating seats. Returns stats.

    deck_candidato/deck_base: lists of 60 ids; by default, deck.csv.
    Each deck travels with its agent when the seat changes.
    """
    stats = {
        "partidas": partidas, "candidato": 0, "base": 0, "limites": 0,
        "errores_candidato": 0, "errores_base": 0,
        "cand_j0": [0, 0], "cand_j1": [0, 0],  # [wins, played]
        "cand_primero": [0, 0], "cand_segundo": [0, 0],
        "pasos_totales": 0,
        # The RESOLUTION metric: the winrate is saturated against the bot, the
        # prizes are not. They are accumulated per AGENT (not per seat), because the
        # candidate alternates seats on every game.
        "premios_candidato": 0, "premios_base": 0, "partidas_con_premios": 0,
    }
    for i in range(partidas):
        asiento_cand = i % 2
        if asiento_cand == 0:
            p0, p1, d0, d1 = candidato, base, deck_candidato, deck_base
        else:
            p0, p1, d0, d1 = base, candidato, deck_base, deck_candidato
        r = play_game(p0, p1, deck0=d0, deck1=d1)
        stats["pasos_totales"] += r["pasos"]
        prizes = r.get("premios_tomados") or [None, None]
        if prizes[0] is not None and prizes[1] is not None:
            stats["premios_candidato"] += prizes[asiento_cand]
            stats["premios_base"] += prizes[1 - asiento_cand]
            stats["partidas_con_premios"] += 1
        if isinstance(r["result"], str) and r["result"].startswith("error"):
            asiento_err = int(r["result"][-1])
            if asiento_err == asiento_cand:
                stats["errores_candidato"] += 1
            else:
                stats["errores_base"] += 1
        if r["ganador"] is None:
            stats["limites"] += 1
        else:
            gano_cand = (r["ganador"] == asiento_cand)
            stats["candidato" if gano_cand else "base"] += 1
            seat = stats["cand_j0"] if asiento_cand == 0 else stats["cand_j1"]
            seat[1] += 1
            seat[0] += int(gano_cand)
            if r["primer_jugador"] == asiento_cand:
                stats["cand_primero"][1] += 1
                stats["cand_primero"][0] += int(gano_cand)
            elif r["primer_jugador"] == 1 - asiento_cand:
                stats["cand_segundo"][1] += 1
                stats["cand_segundo"][0] += int(gano_cand)
        if progreso and (i + 1) % progreso == 0:
            print(f"  ... {i + 1}/{partidas} "
                  f"({stats['candidato']}-{stats['base']})", flush=True)
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
    dec = stats["candidato"] + stats["base"]
    lo, hi = wilson_95(stats["candidato"], dec) if dec else (0, 1)
    lines = [
        f"Self-play: candidato={etiqueta_cand}  vs  base={etiqueta_base}",
        f"Partidas: {stats['partidas']}  (decididas {dec}, "
        f"limite {stats['limites']})",
        f"Marcador: candidato {stats['candidato']} - {stats['base']} base",
        f"Winrate candidato: {_pct(stats['candidato'], dec)} "
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
    ap.add_argument("--partidas", type=int, default=100)
    ap.add_argument("--base", default=None,
                    help="ref de git para el baseline (p.ej. HEAD~1); "
                         "sin --base: espejo main.py vs main.py")
    ap.add_argument("--candidato", default="main.py",
                    help="ruta del agente candidato (default: main.py)")
    ap.add_argument("--progreso", type=int, default=20,
                    help="imprime marcador cada N partidas (0 = nunca)")
    ap.add_argument("--rival", default=None,
                    help="csv de mazo rival: el oponente pasa a ser el BOT "
                         "generico pilotando ese mazo (modo matchup)")
    args = ap.parse_args(argv)

    cand_path = _ROOT / args.candidato
    candidato = load_agent(cand_path, "agente_candidato")

    if args.opponent:
        from opponent_bot import BotRival
        opponent_deck = read_deck(_ROOT / args.opponent)
        bot = BotRival()
        stats = torneo(candidato, bot, args.partidas,
                       progreso=args.progreso or None,
                       deck_base=opponent_deck)
        print(informe(stats, args.candidato, f"bot+{args.opponent}"))
        if args.base:
            base = load_agent_from_git(args.base, "agente_base")
            stats_base = torneo(base, bot, args.partidas,
                                progreso=args.progreso or None,
                                deck_base=opponent_deck)
            print()
            print(informe(stats_base, f"{args.base} (git)",
                          f"bot+{args.opponent}"))
            dec_c = stats["candidato"] + stats["base"]
            dec_b = stats_base["candidato"] + stats_base["base"]
            wr_c = stats["candidato"] / dec_c if dec_c else 0
            wr_b = stats_base["candidato"] / dec_b if dec_b else 0
            print(f"\nDELTA de matchup (candidato - {args.base}): "
                  f"{100 * (wr_c - wr_b):+.1f} puntos "
                  f"({100 * wr_c:.1f}% vs {100 * wr_b:.1f}%)")
        return 0

    if args.base:
        base = load_agent_from_git(args.base, "agente_base")
        etiqueta_base = f"{args.base} (git)"
    else:
        base = load_agent(cand_path, "agente_base_espejo")
        etiqueta_base = f"{args.candidato} (espejo)"

    stats = torneo(candidato, base, args.partidas,
                   progreso=args.progreso or None)
    print(informe(stats, args.candidato, etiqueta_base))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
