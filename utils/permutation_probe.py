"""Does the agent choose a PLAY, or a position in the menu?

THE PROPERTY. The observation hands the agent a list of legal options and it
returns indexes into that list. Every rule in the project is written as a score
attached to an option, so shuffling the list must not change WHAT gets played --
only which index carries it. That is a metamorphic property: it needs no expected
answer, so it can be checked on boards nobody has ever looked at.

WHAT IT CATCHES that nothing else does. A rule that reaches for `option[0]`, a
tie broken by position instead of by the board, a scan that stops at the first
match of a kind rather than the best one. None of those shows up as a red test or
a crash -- the agent plays on, slightly worse, on a fraction of boards that
depends on the order the simulator happened to emit.

HOW IT RUNS. Two independent instances of the agent, the shadow harness's recipe:
the driver sees the real observations and its choices advance the game; the
shadow sees the same observation with its option list PERMUTED, and both choices
are translated back into what they mean before being compared. Both instances
therefore see the same stream and their card tracking stays aligned.

EQUIVALENCE, not identity. Two copies of the same card in hand are the same play,
so the comparison is on the DESCRIPTION of the option (`describe_option`), not on
its index. And face-down prizes are excluded outright: they are chosen blind, so
every choice among them is the same choice and a difference there is noise.

Usage:
    python utils/permutation_probe.py                 # 40 mirror games
    python utils/permutation_probe.py --games 200 --seed 7
    python utils/permutation_probe.py --records       # over records/ instead
    python utils/permutation_probe.py --games 150 --dump log/ties --kinds ABILITY,ATTACH

THE COUNT IS NOT THE DELIVERABLE. A percentage says how often the order decides;
it does not say WHICH board, and a board nobody can reopen is not a finding. With
`--dump` every divergence is written out whole -- the observation included -- so
it can be replayed, turned into a fixture and pinned. `--kinds` narrows the dump
to one class of tie (the names of the option kinds that tied, comma separated),
because the interesting classes are a handful and the rest are copies of a card.
"""

import argparse
import copy
import json
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cg.api import AreaType, OptionType  # noqa: E402

import selfplay as sp  # noqa: E402
from golden_corpus import our_index, record_files, reset_agent  # noqa: E402

# The one context where a difference means nothing: the cards are FACE DOWN, so
# every choice among them is the same choice.
BLIND_AREAS = {int(AreaType.PRIZE)}


def meaning(m, obs, index):
    """What option `index` MEANS, with every index resolved to a card.

    The comparison cannot be on the option itself. Two copies of the same Energy
    in hand are two options and one play, and the whole point of a permutation
    is that the indexes move. So each option is reduced to the card it acts on,
    through the agent's own `get_card` -- the same resolution the agent uses, so
    an area this probe cannot read is an area the agent cannot read either.
    """
    options = (obs.get("select") or {}).get("option") or []
    if index >= len(options):
        return f"?{index}"
    option = options[index]
    kind = option.get("type")
    observation = m.to_observation_class(obs)
    mine = observation.current.yourIndex

    def card(area, idx, player):
        try:
            got = m.get_card(observation, AreaType(area), idx, player)
        except (ValueError, IndexError, AttributeError, TypeError):
            return None
        return getattr(got, 'id', None)

    if kind == int(OptionType.ATTACK):
        return f"ATTACK:{option.get('attackId')}"
    if kind == int(OptionType.PLAY):
        return f"PLAY:{card(int(AreaType.HAND), option.get('index'), mine)}"
    if kind == int(OptionType.ATTACH):
        target = card(option.get('inPlayArea'), option.get('inPlayIndex', 0), mine)
        source = card(option.get('area'), option.get('index'), mine)
        return f"ATTACH:{source}->{target}"
    if kind == int(OptionType.ABILITY):
        return f"ABILITY:{card(option.get('area'), option.get('index', 0), mine)}"
    if kind in (int(OptionType.CARD), int(OptionType.TOOL_CARD),
                int(OptionType.ENERGY_CARD), int(OptionType.DISCARD),
                int(OptionType.EVOLVE)):
        owner = option.get('playerIndex', mine)
        return (f"{OptionType(kind).name}:"
                f"{card(option.get('area'), option.get('index'), owner)}")
    return OptionType(kind).name if kind in {int(o) for o in OptionType} else str(kind)


def _is_blind(select):
    options = select.get("option") or []
    return bool(options) and all(o.get("area") in BLIND_AREAS for o in options)


def _permuted(obs, rng):
    options = obs["select"]["option"]
    order = list(range(len(options)))
    rng.shuffle(order)
    twin = copy.deepcopy(obs)
    twin["select"]["option"] = [options[i] for i in order]
    return twin


def kinds_of(divergence):
    """The set of option kinds that tied, as the summary groups them."""
    return tuple(sorted({str(x).split(":")[0] for x in
                         (divergence["chose"] + divergence["chose_permuted"])}))


def compare(driver, shadow, obs, rng, keep_board=False):
    """(choice the driver makes, divergence or None)."""
    choice = driver.agent(obs)
    select = obs.get("select") or {}
    if not select.get("option") or _is_blind(select):
        shadow.agent(copy.deepcopy(obs))       # keep its tracking aligned
        return choice, None
    twin = _permuted(obs, rng)
    twin_choice = shadow.agent(twin)
    meant = [meaning(driver, obs, i) for i in choice]
    twin_meant = [meaning(shadow, twin, i) for i in twin_choice]
    if sorted(meant) == sorted(twin_meant):
        return choice, None
    bad = {
        "turn": (obs.get("current") or {}).get("turn"),
        "context": select.get("context"),
        "n_options": len(select["option"]),
        "chose": meant,
        "chose_permuted": twin_meant,
    }
    if keep_board:
        # A copy, because the caller hands this same dict back to the simulator
        # and the next `battle_select` is free to mutate it.
        bad["observation"] = copy.deepcopy(obs)
    return choice, bad


def over_games(games, seed, keep_board=False):
    from cg import game

    driver = sp.load_agent(str(_ROOT / "main.py"), "perm_driver")
    shadow = sp.load_agent(str(_ROOT / "main.py"), "perm_shadow")
    rng = random.Random(seed)
    deck = sp.read_deck()
    seen, divergences = 0, []
    for game_no in range(games):
        sp._reset_si_aplica(driver)
        sp._reset_si_aplica(shadow)
        obs, _sd = game.battle_start(list(deck), list(deck))
        if obs is None:
            continue
        steps = 0
        try:
            while obs and obs["current"]["result"] == -1 and steps < 3000:
                choice, bad = compare(driver, shadow, obs, rng, keep_board)
                seen += 1
                if bad:
                    divergences.append({**bad, "game": game_no, "step": steps})
                obs = game.battle_select(choice)
                steps += 1
        finally:
            game.battle_finish()
    return seen, divergences


def over_records(seed, keep_board=False):
    driver = sp.load_agent(str(_ROOT / "main.py"), "perm_driver")
    shadow = sp.load_agent(str(_ROOT / "main.py"), "perm_shadow")
    rng = random.Random(seed)
    seen, divergences = 0, []
    for path in record_files():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        ours = our_index(data)
        reset_agent(driver)
        reset_agent(shadow)
        for step in data.get("steps", []):
            for item in step:
                obs = item.get("observation") or {}
                current = obs.get("current") or {}
                if (item.get("status") != "ACTIVE" or not obs.get("select")
                        or current.get("yourIndex") != ours):
                    continue
                _choice, bad = compare(driver, shadow, obs, rng, keep_board)
                seen += 1
                if bad:
                    divergences.append({**bad, "record": path.name})
    return seen, divergences


def dump(divergences, directory, wanted_kinds=None):
    """Write one JSON per divergence, board included. Returns how many."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for n, d in enumerate(divergences):
        if wanted_kinds is not None and set(kinds_of(d)) != wanted_kinds:
            continue
        name = (f"tie_{n:03d}_t{d.get('turn')}_c{d.get('context')}"
                f"_{'-'.join(kinds_of(d))}.json")
        (out / name).write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        written += 1
    return written


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--records", action="store_true",
                        help="replay records/ instead of playing games")
    parser.add_argument("--dump",
                        help="directory to write each diverging board to")
    parser.add_argument("--kinds",
                        help="dump only this class of tie, e.g. ABILITY,ATTACH")
    args = parser.parse_args(argv)

    wanted = ({k.strip().upper() for k in args.kinds.split(",")}
              if args.kinds else None)
    if args.records:
        seen, divergences = over_records(args.seed, keep_board=bool(args.dump))
        source = f"{len(record_files())} records"
    else:
        seen, divergences = over_games(args.games, args.seed,
                                       keep_board=bool(args.dump))
        source = f"{args.games} games"

    print(f"decisions compared: {seen}  ({source})")
    print(f"order-dependent    : {len(divergences)}"
          f"  ({100 * len(divergences) / max(1, seen):.2f}%)")

    # The useful summary is not the list, it is WHICH KINDS tie. A tie between
    # two copies of a card is nothing; a tie between attacking and benching a
    # body is a rule that was never written.
    from collections import Counter
    by_class = Counter()
    for d in divergences:
        by_class[(d.get("context"), kinds_of(d))] += 1
    if by_class:
        print("\nties, by context and by the kinds that tie:")
        for (context, kinds), n in by_class.most_common():
            print(f"  context {context:>2}  {' vs '.join(kinds):40s} {n:4d}")
    for d in divergences[:10]:
        print(f"  turn {d.get('turn')} context {d.get('context')} "
              f"({d['n_options']} options): {d['chose']} vs {d['chose_permuted']}")
    if args.dump:
        written = dump(divergences, args.dump, wanted)
        print(f"\nboards written: {written} -> {args.dump}")
    return 1 if divergences else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
