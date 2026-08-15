"""How often the agent defers to an Item that the turn's lock has taken away.

THE BOARD IT COMES FROM (user, episode 93229766 turn 14 vs Budew/Dragapult,
LOST; drawn out in `tests/test_the_locked_item_is_not_the_better_play.py`): a
Chikorita active with no energy and a retreat cost of one -- it can neither
attack nor step aside -- two Teal Mask Ogerpon ex holding the turn's energy on
the bench where they cannot be reached, and a nine-card hand of which five are
Items under Budew's Itchy Pollen. The only playable card was the Meowth ex, and
the Meowth branch of `play.py` vetoed it in order to "play the Bug Catching Set
first". The Set could not be played. The turn ended with END.

WHAT IS BEING COUNTED. The candidate arm drives the game; a NEUTRALISED copy of
the same tree is asked for its own choice on the same observation, exactly as
`utils/shadow.py` does, so both see the identical stream of frames and their
tracking evolves together. Per one of OUR decisions:

    ours        decisions the agent took (the denominator)
    locked      ...taken with Items unplayable this turn (`itchy_pollen_active`
                from ANY of its sources: Budew, Galvantula ex, or an opposing
                active that locks Items)
    claimed     ...and a Bug Catching Set in hand with something left in the
                deck for it to find: the boards where the old flag CLAIMED a
                card the engine would not accept. This is the population the
                sentence is about, and it is the number to read
    flip        ...where the neutralised copy would have chosen something ELSE.
                These are the boards where the reading changes a decision at all
    unlocked    ...and the flip is exactly this rule's sentence: the baseline
                ends the turn (or plays something else) and the candidate puts a
                body down instead. A flip that is not is a knock-on -- a turn
                that goes differently once one option moves -- and worth telling
                apart

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won:
the winrate question has its own two-arm gate with a `--control` row at the same
N (`utils/gate_an_item_under_a_lock_is_not_playable.py`).

⚠️ THE CRITERION, written before this file was run and not moved afterwards.
`claimed` at or above **0.05 per game** -- one board in twenty games -- since an
item lock is a common opening line against us and a Bug Catching Set is four of
our sixty. Below that the correction is real but too rare to defend on
frequency, and it stands or falls on the value being ILLEGAL rather than merely
worse ([[politica-neutro-se-revierte-salvo-valor-ilegal]]): a flag that reports
a card as playable when the engine will refuse it is a wrong reading of the
board, not a preference. `flip` is expected to be a small fraction of `claimed`
-- most locked boards have something else to do -- and a `flip` far ABOVE
`claimed` would mean the change is reshaping turns it never spoke about, which
is the failure this column exists to catch.

Usage:
    python utils/census_an_item_under_a_lock_is_not_playable.py --games 200
    python utils/census_an_item_under_a_lock_is_not_playable.py --games 200 \
        --opponent deck/real_opponents/dragapult_1.csv
"""

import argparse
import copy
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests", _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp                                              # noqa: E402
from cg.api import CardType, EnergyType, OptionType                # noqa: E402
from gate_an_item_under_a_lock_is_not_playable import arm          # noqa: E402
from ptcg.cards.ids import Basic_Grass_Energy, Bug_Catching_Set    # noqa: E402

DEFAULT_OPPONENT = "deck/real_opponents/dragapult_1.csv"

#: The opposing attacks and actives that take Items off the table, mirrored from
#: `itchy_pollen_active` in main.py. Read from the driver at run time rather
#: than copied, so this column cannot drift away from the flag it describes.
_LOCK_ATTRS = ("Budew", "Galvantula_ex", "OP_ITEM_LOCK_ACTIVE_IDS",
               "FULGURITE_ATTACK_ID")


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _item_lock(driver, obs):
    """Are Items unplayable this turn? The same three sources main.py collects.

    Rebuilt here from the RAW observation instead of calling the agent's own
    helper: a column that restates the belief cannot contradict it, and the
    point of a census is to be able to.
    """
    for attr in _LOCK_ATTRS:
        if not hasattr(driver, attr):
            raise SystemExit(f"el driver no expone {attr}: el censo mide otra cosa")
    cur = obs["current"]
    seat = cur["yourIndex"]
    for log in (obs.get("logs") or []):
        if log.get("type") != 15 or log.get("playerIndex") == seat:
            continue
        if log.get("cardId") == driver.Budew:
            return True
        if (log.get("cardId") == driver.Galvantula_ex
                and log.get("attackId") == driver.FULGURITE_ATTACK_ID):
            return True
    op = cur["players"][1 - seat]
    active = (op.get("active") or [None])[0]
    return bool(active and active.get("id") in driver.OP_ITEM_LOCK_ACTIVE_IDS)


def _bcs_would_claim(driver, obs):
    """Would the OLD flag have called the Bug Catching Set playable here?

    The Set in hand, and something left in the deck it could find: a Basic {G}
    Energy or a Grass Pokemon. The deck side is the agent's belief -- there is
    no other source for it -- but the hand side is read from the observation.
    """
    hand = _mine(obs).get("hand") or []
    if not any(c.get("id") == Bug_Catching_Set for c in hand):
        return False
    for cid, states in driver.AGENT_STATE.ACTIVE_CARDS_IN_DECK.items():
        if states[driver.ZONE_DECK] <= 0:
            continue
        if cid == Basic_Grass_Energy:
            return True
        data = driver.card_table.get(cid)
        if (data is not None and data.cardType == CardType.POKEMON
                and data.energyType == EnergyType.GRASS):
            return True
    return False


def _is_play(obs, choice):
    """Does this choice put a card down from hand?"""
    if not choice:
        return False
    options = (obs.get("select") or {}).get("option") or []
    if choice[0] >= len(options):
        return False
    return options[choice[0]].get("type") == int(OptionType.PLAY)


def _is_end(obs, choice):
    if not choice:
        return False
    options = (obs.get("select") or {}).get("option") or []
    if choice[0] >= len(options):
        return False
    return options[choice[0]].get("type") == int(OptionType.END)


def census_game(driver, shadow, deck0, deck1, counts, max_steps=3000):
    """One game driven by `driver`, with `shadow` asked on every frame."""
    from cg import game

    for mod in (driver, shadow):
        sp._reset_si_aplica(mod)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: {sd.errorType}")
    steps = 0
    while obs["current"]["result"] == -1 and steps < max_steps:
        choice = driver.agent(obs)
        mirror = shadow.agent(copy.deepcopy(obs))
        counts['ours'] += 1
        locked = _item_lock(driver, obs)
        if locked:
            counts['locked'] += 1
            if _bcs_would_claim(driver, obs):
                counts['claimed'] += 1
        if list(mirror) != list(choice):
            counts['flip'] += 1
            if locked and _is_end(obs, mirror) and _is_play(obs, choice):
                counts['unlocked'] += 1
        obs = game.battle_select(choice)
        steps += 1
    return obs["current"]["result"]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    ap.add_argument("--progress", type=int, default=50)
    args = ap.parse_args(argv)

    driver = arm("census_candidate", True)
    shadow = arm("census_baseline", False)

    own = sp.read_deck()
    theirs = sp.read_deck(_ROOT / args.opponent)

    counts = Counter()
    for i in range(args.games):
        # The seat alternates so the census is not a reading of one half of the
        # game (docs/improving-the-agent.md).
        d0, d1 = (own, theirs) if i % 2 == 0 else (theirs, own)
        census_game(driver, shadow, d0, d1, counts)
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i + 1}/{args.games}", flush=True)

    n = args.games or 1
    print(f"\n{args.games} partidas contra {Path(args.opponent).stem}")
    for key in ("ours", "locked", "claimed", "flip", "unlocked"):
        print(f"  {key:9s} {counts[key]:6d}   {counts[key] / n:7.3f} por partida")
    print("\nCriterio (escrito ANTES): claimed >= 0.05 por partida.")
    print(f"  claimed = {counts['claimed'] / n:.3f} -> "
          f"{'CUMPLE' if counts['claimed'] / n >= 0.05 else 'NO CUMPLE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
