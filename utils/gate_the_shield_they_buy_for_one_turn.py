"""Two-arm gate for "the shield they buy for one turn", isolated to THAT reading
and nothing else in the working tree.

THE RULE. Acerola's Mischief (`OP_EX_SHIELD_IDS`) is the fourth wall this agent
knows and the first one that is not on the board: "during your opponent's next
turn, prevent all damage from and effects of attacks done to that Pokemon by your
opponent's Pokemon ex". The protected body keeps no mark of it, so the only
evidence is the PLAY log of their turn -- and without that reading every
projection in the agent keeps quoting the printed damage while the engine logs
`value: 0` (user, episode 93163758 vs Comfey/Chandelure, seven turns, LOST at ONE
prize; `tests/test_the_shield_they_buy_for_one_turn_mutes_our_ex.py`).

WHAT THE ARMS DIFFER IN. `OP_EX_SHIELD_ROUTING` governs the WHOLE reading, model
included -- unlike its sibling `NZ_MUTE_ROUTING`, which only governs the routing
because the stadium behind it is legible from the observation and the damage
model can read it either way. Here there is nothing to fall back on: with the
flag off the agent simply does not know the card, which is the behaviour the
baseline arm has to reproduce.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
this working tree carries other work: the delta would answer "everything
uncommitted", not "this reading". Both arms here are the SAME tree loaded twice,
with the flag switched off in one of them.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. The population is thin by
construction: their list must carry the card, we must be at two prizes or fewer
for it to be legal at all, and the body it protects must be one our ex were
going to hit. On top of that the reference bot is a control, not the player who
built that lock. So:

  * run `--census` FIRST. If the bot never plays the card the honest report is
    the census plus the corpus audit, not a winrate -- and a self-play gate that
    reports "neutral" on a population of zero has measured nothing.
  * ALWAYS run `--control` at the same n. Both arms neutralised is the same code
    twice, so whatever separation it shows is that run's noise floor.
  * NEUTRAL DOES NOT ORDER A REVERT here: the change is a strict no-op wherever
    the card was never played -- `op_ex_shield_serial` stays None, every
    predicate answers False by its first guard -- which the unit tests pin and
    the frozen corpus confirms (0 flips over the fifty games; the 7 flips are
    all in the one episode this came from). It orders the MARK. A LOSS that
    clears the floor above orders the revert.

Usage:
    python utils/gate_the_shield_they_buy_for_one_turn.py --census
    python utils/gate_the_shield_they_buy_for_one_turn.py --games 1000
    python utils/gate_the_shield_they_buy_for_one_turn.py --games 1000 --control
"""

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# THE POPULATION IS THE LISTS THAT CARRY THE CARD, because everywhere else the
# shield is never pinned and both arms are the same agent. The three that do are
# the harvested Comfey/Chandelure lists; the rest are controls where the card is
# absent, and they are here to catch a change that leaks OUT of the matchup,
# which is the failure mode a no-op has.
DEFAULT_DECKS = (
    "deck/real_opponents/chandelure_1.csv",
    "deck/real_opponents/otro_comfey_1.csv",
    "deck/real_opponents_500/chandelure_2.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/marnie_grimmsnarl.csv",
)


def neutralise(agent_module):
    """Switch the reading off in `agent_module`, permanently, in place.

    It is the flag inside `ptcg.calc.damage` that has to be rebound, not a copy:
    `_shield_mutes_our_ex` reads it out of its own module globals, and every
    consumer -- the damage model itself, `_wall_mutes_our_ex`, the attack
    scorer -- calls that same function object. One assignment switches them all.

    The STICKY matchup flag is left alone on purpose: it is set from the logs
    whatever this flag says, and the discard ladder that reads it is part of the
    reading being measured.
    """
    agent_module._our_effective_damage.__globals__['OP_EX_SHIELD_ROUTING'] = False
    return agent_module


def _reading_of(agent_module):
    return agent_module._our_effective_damage.__globals__['OP_EX_SHIELD_ROUTING']


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked directly for the flag the run will compare against.
    """
    if candidate._our_effective_damage is base._our_effective_damage:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if _reading_of(base):
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if _reading_of(candidate) is bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, lectura={_reading_of(candidate)})")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la lectura'}, "
          f"baseline sin ella)\n", flush=True)


def census(games, decks, progress):
    """HOW OFTEN THE BOARD THE READING IS ABOUT ACTUALLY HAPPENS.

    Three numbers, and the gaps between them are the whole point:

      asked      every call to `_shield_mutes_our_ex` -- something priced a body
                 against the shield;
      pinned     the decisions taken with a shield actually up (their Supporter
                 seen in the logs and its turn still running);
      mute       the calls that came back True: the body being priced IS the one
                 they protected. That last line is the population -- everywhere
                 above it the two arms return the same number.

    A ZERO HERE IS A RESULT, not a failure of the gate. The reference bot
    pilots the list; whether it ever plays the Supporter is its business, and if
    it does not, this reading cannot be measured by self-play at all and the
    honest report is the corpus audit.
    """
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census")
    dmg = agent._our_effective_damage.__globals__
    plain = dmg['_shield_mutes_our_ex']
    counts = Counter()
    state = agent.AGENT_STATE

    def counted(op_pokemon):
        out = plain(op_pokemon)
        counts['asked'] += 1
        if state.op_ex_shield_serial is not None:
            counts['pinned'] += 1
        if out:
            counts['mute'] += 1
        return out

    dmg['_shield_mutes_our_ex'] = counted
    # The attack scorer imported the ORIGINAL object BY NAME, so its copy has to
    # be rebound too -- rebinding the definition alone counts nothing.
    #
    # AND IT IS NOT IN `sys.modules`. `load_agent` gives each arm its own `ptcg`
    # tree and then RETURNS the ambient one, so a scan there rebinds the copy
    # nobody plays with and the census reports a confident zero. It is reached
    # through the agent's own reference instead, and if it is missing this
    # raises rather than reporting that zero.
    _consumers = [agent.score_option.__globals__['attack'].__dict__]
    for _d in _consumers:
        if _d.get('_shield_mutes_our_ex') is not plain:
            raise SystemExit("el censo no alcanza a un consumidor: mediria cero")
        _d['_shield_mutes_our_ex'] = counted
    try:
        total_mute = 0
        for rel in decks:
            their = sp.read_deck(_ROOT / rel)
            counts.clear()
            sp.torneo(agent, OpponentBot(), games,
                      progress=progress or None, deck_base=their)
            asked, pinned, mute = counts['asked'], counts['pinned'], counts['mute']
            total_mute += mute
            print(f"{Path(rel).stem:42s} preguntado {asked:7d} "
                  f"({asked / games:7.2f}/partida)   escudo puesto {pinned:6d}   "
                  f"MUDO {mute:6d} ({mute / games:6.2f}/partida)", flush=True)
        print(f"\nCENSO DE DISPARO: {total_mute / (games * len(decks)):.2f} "
              f"lecturas mudas por partida de media.")
        if total_mute / (games * len(decks)) < 0.01:
            print("AVISO: el evento es RARO O NULO. Con una exposicion asi el "
                  "gate de self-play no puede resolver la diferencia por muchas "
                  "partidas que juegue; el informe honesto es este censo y la "
                  "auditoria del corpus, no un winrate.")
    finally:
        dmg['_shield_mutes_our_ex'] = plain
        for _d in _consumers:
            _d['_shield_mutes_our_ex'] = plain
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
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how often the board happens at all (run this first)")
    args = ap.parse_args(argv)

    decks = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))

    if args.census:
        return census(args.games, decks, args.progress)

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

    tot_c = tot_b = 0
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        c = sp.torneo(candidate, OpponentBot(), args.games,
                      progress=args.progress or None, deck_base=their)
        b = sp.torneo(base, OpponentBot(), args.games,
                      progress=args.progress or None, deck_base=their)
        cw, bw = c['candidate'], b['candidate']
        tot_c += cw
        tot_b += bw
        d, z, p = wilson_delta(cw, args.games, bw, args.games)
        # The PRIZE DIFFERENTIAL is the metric with resolution left once the
        # winrate saturates against the bot (docs/improving-the-agent.md), and
        # against a thin population it is the one that moves first.
        _cp = (c['premios_candidato'] - c['premios_base']) / max(1, c['partidas_con_premios'])
        _bp = (b['premios_candidato'] - b['premios_base']) / max(1, b['partidas_con_premios'])
        print(f"{Path(rel).stem:42s} con {cw:5d}/{args.games}  sin {bw:5d}/{args.games}  "
              f"delta {100 * d:+6.2f} pp  (z={z:+5.2f} p={p:.3f})   "
              f"premios {_cp:+.2f} vs {_bp:+.2f} ({_cp - _bp:+.2f})", flush=True)

    n = args.games * len(decks)
    d, z, p = wilson_delta(tot_c, n, tot_b, n)
    print(f"\nTOTAL  con {tot_c}/{n}  sin {tot_b}/{n}  "
          f"delta {100 * d:+.2f} pp  (z={z:+.2f} p={p:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
