"""Two-arm gate for "the seat the SETUP gave did not spend the ability",
isolated to THAT reading and nothing else in the working tree.

The rule: a body that reached play WITHOUT BEING PLAYED -- the starting active
the setup deals into the active spot, and anything an effect puts down straight
from the deck -- never fired a come-into-play ability. The engine says which is
which: a card played from hand is a PLAY log, the setup is a MOVE_CARD, and the
two never land on the same serial. `AGENT_STATE._in_play_without_a_play` is that
set, and `_meowth_ld_free` is the one reading that consumes it: before it, a
Meowth ex dealt into the active spot carried `appearThisTurn` on turn 1 like
everything else the setup puts down, and the whole Last-Ditch engine read that
as "the turn's ability is already spent".

WHY NOT `selfplay.py --base HEAD`: the same reason the other gates give -- the
git baseline carries every other uncommitted change, so the delta would answer
"the working tree", not "this reading". Both arms here are the SAME tree loaded
twice, with the memory switched off in one of them.

NOTHING ON DISK IS REWRITTEN. The neutralisation happens on the loaded module
objects (the arm's own `AgentState` class), so this is safe to leave running
while other files are edited.

READ THE CENSUS FIRST (`--census`). It drives the candidate and asks the
neutralised arm for its choice on the SAME observation (the `utils/shadow.py`
harness), so it counts the decisions the reading really changes, on games that
are not the corpus. It is the ceiling of any winrate effect.

Usage:
    python utils/gate_the_setup_seat_did_not_spend_the_ability.py --census
    python utils/gate_the_setup_seat_did_not_spend_the_ability.py --games 1500
    python utils/gate_the_setup_seat_did_not_spend_the_ability.py --games 1500 --control
"""

import argparse
import copy
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# The reading is about OUR OWN opening, not about a matchup: whoever is on the
# other side of the table, the setup deals our starting active the same way. So
# the arms are played against a spread and no deck here should show zero.
SPREAD_DECKS = (
    "deck/opponents/dragapult.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/crustle_kangaskhan.csv",
)


class _Blind(set):
    """A set that forgets: the state the agent had before this reading."""

    def add(self, item):
        pass


def neutralise(agent_module):
    """Switch the memory off in `agent_module`, permanently, in place.

    It is the arm's OWN `AgentState` class that has to be patched, not just the
    live instance: `reset()` runs at the start of every game and would install a
    fresh, remembering set for game 2 onwards.
    """
    state_cls = type(agent_module.AGENT_STATE)
    if not getattr(state_cls, "_gate_blinded", False):
        _original_reset = state_cls.reset

        def reset(self):
            _original_reset(self)
            self._in_play_without_a_play = _Blind()

        state_cls.reset = reset
        state_cls._gate_blinded = True
    agent_module.AGENT_STATE._in_play_without_a_play = _Blind()
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent."""

    def remembers(agent):
        agent.AGENT_STATE.reset()
        agent.AGENT_STATE._in_play_without_a_play.add(-1)
        return -1 in agent.AGENT_STATE._in_play_without_a_play

    if candidate.agent is base.agent:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if remembers(candidate) is bool(control):
        raise SystemExit("el brazo candidato no lleva la regla que dice llevar")
    if remembers(base):
        raise SystemExit("el brazo baseline lleva la regla: no hay nada que medir")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la regla'}, "
          f"baseline sin ella)\n", flush=True)


def _asked(agent_module, obs):
    """Is this a decision where the two arms READ THE BOARD DIFFERENTLY?

    That is the population the flips are drawn from: a Meowth ex in play that
    carries `appearThisTurn` and got its seat without being played. The
    candidate calls its Last-Ditch free there and the neutralised arm calls it
    spent; every other board they read identically.
    """
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    seated = agent_module.AGENT_STATE._in_play_without_a_play
    for body in list(mine.get("active") or []) + list(mine.get("bench") or []):
        if (body and body.get("id") == agent_module.Meowth_ex
                and body.get("appearThisTurn")
                and body.get("serial") in seated):
            return True
    return False


def _census_game(candidate, base, deck, their_deck, seed, lib):
    """One seeded game driven by the candidate, with the base SHADOWING it.

    Both arms see the same stream of observations, so their beliefs evolve the
    same way and the only difference left is the reading under test. Returns
    (divergences, asked, our_decisions).
    """
    from cg.battle import Battle
    from opponent_bot import OpponentBot

    rival = OpponentBot()
    sp._reset_si_aplica(candidate)
    sp._reset_si_aplica(base)
    battle = Battle(list(deck), list(their_deck), seed=seed, lib=lib)
    obs = battle.obs
    diverged, asked, ours, steps = [], 0, 0, 0
    try:
        while obs["current"]["result"] == -1 and steps < 3000:
            seat = obs["current"]["yourIndex"]
            if seat == 0:
                choice = candidate.agent(obs)
                shadow = base.agent(copy.deepcopy(obs))
                ours += 1
                asked += 1 if _asked(candidate, obs) else 0
                if list(shadow) != list(choice):
                    diverged.append((obs["current"]["turn"],
                                     (obs.get("select") or {}).get("context"),
                                     list(shadow), list(choice)))
            else:
                choice = rival.agent(obs)
            obs = battle.select(choice)
            steps += 1
    finally:
        battle.finish()
    return diverged, asked, ours


def census(games, decks, progress):
    """HOW MANY of our decisions the reading changes, on fresh games."""
    import local_engine

    lib = local_engine.load()
    deck = sp.read_deck()
    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    provenance(candidate, base, control=False)

    total_div = total_asked = total_dec = total_games = 0
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        div = asked = dec = touched = seats = 0
        for i in range(games):
            d, a, n = _census_game(candidate, base, deck, their, seed=1 + i,
                                   lib=lib)
            div += len(d)
            asked += a
            dec += n
            seats += 1 if a else 0
            touched += 1 if d else 0
            if d and touched <= 3:
                for turn, ctx, before, after in d:
                    print(f"    seed {1 + i} turno {turn} ctx {ctx}: "
                          f"{before} -> {after}")
            if progress and (i + 1) % progress == 0:
                print(f"  ... {i + 1}/{games}", flush=True)
        total_div += div
        total_asked += asked
        total_dec += dec
        total_games += games
        print(f"{Path(rel).stem:30s} lectura distinta en {asked:4d} decisiones "
              f"({seats}/{games} partidas, {100 * seats / games:.1f}%)   "
              f"CAMBIA {div:3d} de {dec:6d} ({100 * div / max(dec, 1):.2f}%)   "
              f"partidas tocadas {touched}/{games} "
              f"({100 * touched / games:.1f}%)", flush=True)

    per_game = total_div / max(total_games, 1)
    print(f"\nCENSO DE DISPARO: {total_asked / max(total_games, 1):.2f} decisiones "
          f"por partida se LEEN distinto y {per_game:.2f} CAMBIAN "
          f"({total_div} de {total_dec} decisiones nuestras).")
    if per_game < 0.01:
        print("AVISO: el evento es RARO. Con una exposicion asi el gate de "
              "self-play puede no resolver la diferencia por muchas partidas "
              "que juegue; el informe honesto es este censo, no un winrate.")
    return 0


def wilson_delta(w1, n1, w2, n2):
    """Two-proportion z test. It ASSUMES independent Bernoulli, which the bot
    does not honour -- so read the p it prints as an optimistic bound."""
    if not n1 or not n2:
        return 0.0, 0.0, 1.0
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) or 1e-9
    z = (p1 - p2) / se
    return p1 - p2, z, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=1500)
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas. "
                         "Omitted: the spread in SPREAD_DECKS")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how many decisions the reading changes (run this first)")
    args = ap.parse_args(argv)

    decks = (args.opponent.split(",") if args.opponent else list(SPREAD_DECKS))

    if args.census:
        return census(args.games, decks, args.progress)

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

    label_c = "con la regla" + (" (NEUTRALIZADO: control)" if args.control else "")
    totals = [0, 0, 0, 0]                      # wins_c, n_c, wins_b, n_b
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        name = Path(rel).stem
        rows = []
        for agent in (candidate, base):
            st = sp.torneo(agent, OpponentBot(), args.games,
                           progress=args.progress or None, deck_base=their)
            rows.append((st["candidate"], st["candidate"] + st["base"], st))
        (wc, nc, stc), (wb, nb, stb) = rows
        totals[0] += wc; totals[1] += nc; totals[2] += wb; totals[3] += nb
        d, z, p = wilson_delta(wc, nc, wb, nb)
        print(f"{name:30s} {label_c} {100 * wc / nc:5.2f}%   sin ella "
              f"{100 * wb / nb:5.2f}%   delta {100 * d:+5.2f} pts  z={z:5.2f} p={p:.3f}   "
              f"premios {sp.prizes_per_game(stc)[0]:.2f} vs {sp.prizes_per_game(stb)[0]:.2f}   "
              f"forfeits {stc['errores_candidato']}/{stb['errores_candidato']}",
              flush=True)

    d, z, p = wilson_delta(*totals)
    print(f"\nAGREGADO ({totals[1]} partidas por brazo)  "
          f"{100 * totals[0] / totals[1]:.2f}% vs {100 * totals[2] / totals[3]:.2f}%   "
          f"DELTA {100 * d:+.2f} pts  z={z:.2f}  p={p:.3f} (cota optimista)")
    if args.control:
        print("Esto es el SUELO DE RUIDO: mismo codigo en los dos brazos. "
              "Un delta real tiene que superarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
