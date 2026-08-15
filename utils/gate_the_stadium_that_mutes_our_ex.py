"""Two-arm gate for "Neutralization Zone is a wall, and the wall is the missing
Rule Box", isolated to THAT reading and nothing else in the working tree.

THE RULE. Neutralization Zone (id 1247, ACE SPEC) prevents all damage done to
Pokemon WITHOUT a Rule Box by attacks from the opponent's ex/V. With their whole
board Rule-Box-less, every ex of OURS -- Hydrapple ex, both Teal Mask Ogerpon ex,
Fezandipiti ex, Meowth ex -- is mute, and the only bodies that can still take a
prize are our non-ex: Meganium, Tapu Bulu, Dipplin, Pinsir.

`_our_effective_damage` has always known this (`neutralization_zone and my_is_ex
and not _op_has_rule_box -> 0`). The ENERGY ROUTING did not, and that is the
defect: the damage model answered the question correctly every time it was
asked, and nobody asked it before spending the turn's only Grass.

THE BOARD IT COMES FROM (user, `records/registro_010_pasos_070_hasta_080` step
70, episode 93142685, vs a Mesprit/Uxie/Azelf deck). Their five bodies, all 70
HP, none with a Rule Box; our active Hydrapple ex covering Syrup Storm's cost
and doing zero with it; on the bench a Meganium at ZERO energy, whose Solar Beam
(140, and Wild Growth doubles every Grass so TWO cards arm it) knocks out
anything they have. The turn's only Grass went to a benched Ogerpon ex via Teal
Dance -- 31300, the `_active_hydra_ready` rung, whose sentence is "the active
covers its cost, so the surplus goes to the bench": true of the cost and false
of the board.

WHAT THE READING CHANGES, and it is two halves of one turn:

  * the Teal Dance ladder gains the THIRD wall. The rung that already demotes
    the dance to 7500 against Crustle and Cornerstone ("the last Grass belongs
    to the body that can still hit the wall") now also fires under the stadium,
    with the WIDEST creditor list of the three -- this wall filters by Rule Box,
    not by our abilities, so every non-ex of ours is owed, Meganium included;
  * the bench half of the stadium's own energy bands stops being development.
    Their ACTIVE halves were already priced as the attackers of the matchup
    (23200/23000/15000); the bench halves sat at 600/400/380/300 and lost the
    Grass twice over -- to the mute active ex, and to the 7000 cap an attachment
    takes when it yields to a Teal Dance. They are promoted by a fixed 22000
    while the front is mute, which preserves their order and keeps the whole
    bench below every active band.

BOTH HALVES ARE ONE TURN and there is no measuring them apart: with only the
first, the Grass goes to the mute active ex instead of the mute benched one.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
the working tree normally carries other work: the delta then answers
"everything uncommitted", not "this reading". Here both arms are the SAME tree
loaded twice, with `NZ_MUTE_ROUTING` switched off in one of them.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. This is a rule of the game the
model was reading only half of, and it is a STRICT NO-OP on every board where
the stadium is not in play or their active carries a Rule Box -- which the unit
tests pin and the frozen corpus confirms (0 flips in 50 games, none of which
reaches this board). So NEUTRAL DOES NOT ORDER A REVERT here: it orders the
mark. A LOSS that clears the noise floor does order the revert.

ALWAYS RUN `--control` AT THE SAME N. Both arms neutralised is the same code
twice, so whatever separation it shows is that run's noise floor. A delta that
does not clear it is not a delta.

WHAT IT MEASURED (14 August 2026, n=1000 per list, 8 lists, 8 000 games/arm):

    --census   3.10 - 10.75 mute readings per game on the five lists that get
               the card down; EXACTLY 0 on the three where it never lands.
               The board is common, not a corner.
    --games    TOTAL +0.05 pp (7800/8000 vs 7796/8000). Prize differential on
               the exposed lists +0.06 / +0.03 / +0.10 / -0.06 / +0.18.
    --control  TOTAL +0.44 pp (z=+1.72, p=0.085), and one list separates by
               +2.10 pp at p=0.005 WITH THE SAME CODE IN BOTH ARMS.

So the reading is NEUTRAL, and it is neutral by a wide margin: its delta is an
order of magnitude inside the floor its own control run shows. The winrate
against the reference bot is saturated in this half of the field (95-99 %) and
cannot resolve it -- which is what `utils/oracle_the_stadium_that_mutes_our_ex.py`
was written for, and that grader came back SPLIT (3 boards for, 3 against, net
+16 pp / +0.68 margin over six), on proxy opponent lists that cover only 36-39 %
of the board and that -- unlike the real all-non-ex opponent -- carry ex of their
own, which favours the baseline arm by construction.

NEUTRAL DOES NOT ORDER A REVERT HERE, it orders the MARK: the routing was
contradicting a damage model that had the rule right all along, and the change
is a no-op wherever the stadium is absent or their front carries a Rule Box.
A LOSS that clears the floor above does order the revert.

Usage:
    python utils/gate_the_stadium_that_mutes_our_ex.py --census
    python utils/gate_the_stadium_that_mutes_our_ex.py --games 1000
    python utils/gate_the_stadium_that_mutes_our_ex.py --games 1000 --control
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

# THE POPULATION IS THE DECKS THAT CARRY THE STADIUM, because everywhere else
# `_nz_mutes_our_ex` is False by its first guard and both arms are the same
# agent. Neutralization Zone is an ACE SPEC (one copy, and the deck may never
# draw it), so the exposure is thin by construction -- which is what the census
# is for. The last two are controls where the card is absent: they are here to
# catch a change that leaks OUT of the matchup, the failure mode a no-op has.
DEFAULT_DECKS = (
    "deck/real_opponents/otro_comfey_1.csv",
    "deck/real_opponents/otro_bramblin_1.csv",
    "deck/real_opponents_500/chandelure_1.csv",
    "deck/real_opponents_500/otro_team_rocket_s_murkrow_1.csv",
    "deck/opponents/comfey_yveltal_nz.csv",
    "deck/opponents/crustle_great_tusk_nz.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/marnie_grimmsnarl.csv",
)


def neutralise(agent_module):
    """Switch the reading off in `agent_module`, permanently, in place.

    It is the flag inside `ptcg.calc.damage` that has to be rebound, not a copy:
    `_nz_mutes_our_ex` reads it out of its own module globals, and the two
    consumers (`ptcg/turn/options/ability.py`, `ptcg/turn/energy.py`) call that
    same function object. One assignment switches both halves.
    """
    dmg = agent_module._our_effective_damage.__globals__
    dmg['NZ_MUTE_ROUTING'] = False
    return agent_module


def _reading_of(agent_module):
    return agent_module._our_effective_damage.__globals__['NZ_MUTE_ROUTING']


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked directly for the flag the net will compare against.
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

    Two numbers, and the gap between them is the whole point:

      asked      every call to `_nz_mutes_our_ex` -- the routing consulted it;
      mute       the calls that came back True, i.e. the stadium was up AND the
                 body in front had no Rule Box. That is the population.

    The corpus flips six decisions and all six are the same game, so the
    exposure has to be measured where the boards come from: self-play against
    the decks that carry the card.
    """
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census")
    dmg = agent._our_effective_damage.__globals__
    plain = dmg['_nz_mutes_our_ex']
    counts = Counter()

    def counted(op_active, neutralization_zone):
        out = plain(op_active, neutralization_zone)
        counts['asked'] += 1
        if neutralization_zone:
            counts['stadium'] += 1
        if out:
            counts['mute'] += 1
        return out

    dmg['_nz_mutes_our_ex'] = counted
    # The two consumers imported the ORIGINAL object BY NAME, so the copies the
    # ability ladder and the energy router hold have to be rebound too --
    # rebinding the definition alone counts nothing (the same trap the
    # `_op_hp_for_our_ko` census documents next door).
    #
    # AND THEY ARE NOT IN `sys.modules`. `load_agent` gives each arm its own
    # `ptcg` tree and then RETURNS the ambient one to `sys.modules`, so a scan
    # there rebinds the copy nobody plays with and the census reports a
    # confident zero -- an instrument that measures nothing while looking like
    # it measured. They are reached through the agent's own references instead,
    # and if either is missing this raises rather than reporting that zero.
    _consumers = [
        agent.score_option.__globals__['ability'].__dict__,
        agent._energy_score_base_impl.__globals__,
    ]
    for _d in _consumers:
        if _d.get('_nz_mutes_our_ex') is not plain:
            raise SystemExit("el censo no alcanza a un consumidor: mediria cero")
        _d['_nz_mutes_our_ex'] = counted
    try:
        total_mute = 0
        for rel in decks:
            their = sp.read_deck(_ROOT / rel)
            counts.clear()
            sp.torneo(agent, OpponentBot(), games,
                      progress=progress or None, deck_base=their)
            asked, stadium, mute = counts['asked'], counts['stadium'], counts['mute']
            total_mute += mute
            print(f"{Path(rel).stem:42s} preguntado {asked:7d} "
                  f"({asked / games:7.2f}/partida)   estadio {stadium:6d}   "
                  f"MUDO {mute:6d} ({mute / games:6.2f}/partida)", flush=True)
        print(f"\nCENSO DE DISPARO: {total_mute / (games * len(decks)):.2f} "
              f"lecturas mudas por partida de media.")
        if total_mute / (games * len(decks)) < 0.01:
            print("AVISO: el evento es RARO. Con una exposicion asi el gate de "
                  "self-play puede no resolver la diferencia por muchas partidas "
                  "que juegue; el informe honesto es este censo, no un winrate.")
    finally:
        dmg['_nz_mutes_our_ex'] = plain
        for _d in _consumers:
            _d['_nz_mutes_our_ex'] = plain
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
