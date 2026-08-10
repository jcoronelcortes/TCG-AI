"""Radar of COLLISIONS between matchup rules.

The matchup matrix (phase 8) says WHICH matchup goes worse; the autopsy (phase 6)
says a game was lost. Neither of them finds the class of failure
that gave the project's biggest measured jump (+5.4 in cornerstone_cubchoo): a
veto from ONE matchup that kills the play another matchup REQUIRES. The meta decks are
mixed (Cornerstone+Cubchoo, Crustle+Kangaskhan...), so two `op_is_*_deck`
flags coexist and their rules step on each other.

How that one was found: comparing the SAME scenario in two sibling
matchups. Against Crustle, "a wall in front + a ready attacker on the bench + a legal
retreat" was resolved by bringing the attacker up 82-100% of the time; against
Cornerstone+Cubchoo, 13.7%. That asymmetry IS the bug.

This piece generalises that method: it defines canonical, deck-agnostic SITUATIONS
that are read from the observation (without touching main.py) and measures, per opposing deck, how
often we RESOLVE them. A resolution rate that collapses in one deck and
not in the others is a collision candidate, and the deck where it collapses says which
flag to look at.

What it does NOT do: decide whether it is a bug. It only points at where to look; the confirmation
is still capturing the menu and tracing the score (`sys.settrace` over `agent`,
filtering changes of `frame.f_locals['score']`).

Usage:
    python utils/collision_radar.py --games 100
    python utils/collision_radar.py --games 200 --only cornerstone_cubchoo,crustle_kangaskhan
    python utils/collision_radar.py --opponents deck/real_opponents --games 400

The default folder is still `deck/opponents/`, the 19 synthetic decks the method
was built on, because a canonical situation needs a deck whose engine is known.
`--opponents` points it at any other folder -- `deck/real_opponents/` above --
which is what turns the radar from "the sibling matchups disagree" into "THIS
real list is where the situation collapses". Auxiliary CSVs in that folder
(`pesos.csv`) are skipped rather than read as a deck and crashed on, which
otherwise happens AFTER every good matchup has already been played.
"""

import argparse
import collections
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp
import autopsy as au
from cg.api import OptionType


def _act(player):
    a = player.get("active") or []
    return a[0] if a and a[0] else None


def _menu_types(obs):
    return {o.get("type") for o in obs["select"]["option"]}


# --------------------------------------------------------------------------
# SITUATIONS. Each one receives the menus of ONE of our turns and returns
# (applies, resolved). They are read from the observation: no main.py internals,
# so the radar does not inherit the same biases it is auditing.
# --------------------------------------------------------------------------

def _s_pivot_to_wall(m, menus):
    """The active canNOT damage the opposing active (immunity) and on the bench there is a
    body that CAN and is charged. Resolved = the turn ends with a body
    that does damage in the active spot."""
    aplica = False
    for d in menus:
        cur = d["obs"]["current"]
        yo = cur["players"][cur["yourIndex"]]
        op = cur["players"][1 - cur["yourIndex"]]
        act, oact = _act(yo), _act(op)
        if act is None or oact is None:
            continue
        ex_imm = oact["id"] in m.EX_IMMUNE_IDS
        ab_imm = oact["id"] in m.ABILITY_IMMUNE_IDS
        if not (ex_imm or ab_imm):
            continue
        bloqueado = ((ex_imm and act["id"] in m.OUR_EX_IDS)
                     or (ab_imm and act["id"] in m.OUR_ABILITY_IDS))
        if not bloqueado:
            continue
        relief = any(
            b and _hits_the_wall(m, b, ex_imm, ab_imm)
            and m._can_attack_eff(b["id"], len(b["energies"]))
            and _real_threat(m, b, oact, yo)
            for b in (yo.get("bench") or []))
        if relief and int(OptionType.RETREAT) in _menu_types(d["obs"]):
            aplica = True
            break
    if not aplica:
        return False, False
    # Resolved = at SOME point of the turn the relief reaches the active spot (or attacks
    # from it). Looking only at the last menu is not enough: if the relief knocks out the wall,
    # the opponent promotes and the final state no longer describes the play.
    for d in menus:
        cur = d["obs"]["current"]
        yo = cur["players"][cur["yourIndex"]]
        op = cur["players"][1 - cur["yourIndex"]]
        act, oact = _act(yo), _act(op)
        if act is None or oact is None:
            continue
        ex_imm = oact["id"] in m.EX_IMMUNE_IDS
        ab_imm = oact["id"] in m.ABILITY_IMMUNE_IDS
        if _hits_the_wall(m, act, ex_imm, ab_imm):
            return True, True
    return True, False


class _P:
    """A minimal dict -> object adapter for main's calculators (the same
    pattern as `autopsia._dano_letal_activo`)."""

    def __init__(self, d):
        self.id = d["id"]
        self.hp = d.get("hp")
        self.energies = list(d.get("energies") or [])

        class _C:
            def __init__(self, dd):
                self.id = dd["id"]

        self.energyCards = [_C(c) for c in (d.get("energyCards") or [])]
        self.tools = [_C(c) for c in (d.get("tools") or [])]


def _real_threat(m, relief, wall, yo, threshold=0.25):
    """Does the relief really threaten the wall, or does it only chip it?

    A pivot costs the turn and the retreat energy: it only pays off if the
    body that comes up bites. Without this filter the radar counted as "we should
    pivot" the turns whose only relief was a Dipplin (20 x bench) against
    a wall of 170-210 HP -- the agent was right to decline, and the resolution
    rate collapsed without there being any failure (crustle came out at 55% and 96.8%
    of the "unresolved" cases had a Dipplin as their only relief). It is the same
    trap that already forced filtering by `MAIN_ATTACKERS`, one level up.

    Threshold: take away >= 25% of the wall's CURRENT HP (a 4-turn clock or
    better).
    """
    bodies = [p for p in (yo.get("active") or []) + (yo.get("bench") or []) if p]
    total_grass = sum(len(p.get("energies") or []) for p in bodies)
    bench = sum(1 for b in (yo.get("bench") or []) if b)
    e = len(relief.get("energies") or [])
    a, o = _P(relief), _P(wall)
    try:
        base = m._attacker_base_damage(a.id, o, e, grass_scale=total_grass,
                                       teal_self_energy=e, bench_count=bench)
        meg = any(p["id"] == m.Meganium for p in bodies)
        dmg = m._our_effective_damage(a, o, base, meg, False)
    except Exception:
        return True          # when in doubt, do not filter: better a false positive
    return dmg >= threshold * max(1, wall.get("hp") or 1)


def _hits_the_wall(m, pk, ex_imm, ab_imm):
    """Is this body a REAL relief against the wall?

    `MAIN_ATTACKERS` is required -- the CURATED list of bodies we really
    attack with --, not any card with an attack. Without that filter, an Applin
    with 1 energy (20 damage to a 210 HP wall) counted as a valid relief: the
    situation fired constantly, the agent was right to ignore it and the
    resolution rate collapsed without there being any failure at all. That bias made
    the radar INSENSITIVE to the fix used to validate it (1.9% -> 1.1%, without
    moving, when the fix is worth +5.4 measured points).
    """
    if pk["id"] not in m.MAIN_ATTACKERS:
        return False
    if ex_imm and pk["id"] in m.OUR_EX_IDS:
        return False
    if ab_imm and pk["id"] in m.OUR_ABILITY_IDS:
        return False
    return True


def _s_supporter_unplayed(m, menus):
    """A free Supporter slot and at least one in hand. Resolved = it is played."""
    cur0 = menus[0]["obs"]["current"]
    yo0 = cur0["players"][cur0["yourIndex"]]
    if cur0["supporterPlayed"]:
        return False, False
    if not any(h["id"] in m._SUPP_PLAY_IDS for h in (yo0.get("hand") or [])):
        return False, False
    ult = menus[-1]["obs"]["current"]
    return True, bool(ult["supporterPlayed"])


def _s_energy_unattached(m, menus):
    """The turn's attachment is free and there is Grass in hand. Resolved = it ends up on the field
    (through the manual attachment or a charging ability)."""
    cur0 = menus[0]["obs"]["current"]
    yo0 = cur0["players"][cur0["yourIndex"]]
    if cur0["energyAttached"]:
        return False, False
    if not any(h["id"] == m.Basic_Grass_Energy for h in (yo0.get("hand") or [])):
        return False, False
    total0 = sum(len(p["energies"]) for p in
                 (yo0.get("active") or []) + (yo0.get("bench") or []) if p)
    ult = menus[-1]["obs"]["current"]
    yo_f = ult["players"][ult["yourIndex"]]
    total_f = sum(len(p["energies"]) for p in
                  (yo_f.get("active") or []) + (yo_f.get("bench") or []) if p)
    return True, (ult["energyAttached"] or total_f > total0)


def _s_turn_not_sterile(m, menus):
    """The menu offered plays that are NOT END. Resolved = we make one of them."""
    hubo_opcion = any(t not in (int(OptionType.END),) for d in menus
                      for t in _menu_types(d["obs"]))
    if not hubo_opcion:
        return False, False
    hizo = any(d["obs"]["select"]["option"][d["eleccion"][0]].get("type")
               != int(OptionType.END)
               for d in menus if d["eleccion"])
    return True, hizo


def _s_remata_si_puede(m, menus):
    """The ACTIVE knocks out the opposing active THIS turn. Resolved = we attack.

    It is the most basic play there is, so its rate has to come out high in
    ALL decks: if it comes out low in all of them, the detector is wrong (not the agent).
    It serves as a sanity check on the radar itself."""
    aplica = False
    for d in menus:
        cur = d["obs"]["current"]
        yo = cur["players"][cur["yourIndex"]]
        op = cur["players"][1 - cur["yourIndex"]]
        a, o = _act(yo), _act(op)
        if a is None or o is None:
            continue
        if int(OptionType.ATTACK) not in _menu_types(d["obs"]):
            continue
        if not m._can_attack_eff(a["id"], len(a["energies"])):
            continue
        if _damage(m, a, o, yo) >= (o.get("hp") or 10 ** 6):
            aplica = True
            break
    if not aplica:
        return False, False
    ataco = any(d["obs"]["select"]["option"][d["eleccion"][0]].get("type")
                == int(OptionType.ATTACK)
                for d in menus if d["eleccion"])
    return True, ataco


def _s_evoluciona_si_puede(m, menus):
    """An evolution in hand with its pre-evolution IN PLAY and LEGALLY evolvable.
    Resolved = the evolution ends up on the field.

    The `appearThisTurn` filter is not cosmetic: a pre-evolution played this very
    turn canNOT evolve (except with a Forest of Vitality in play, which allows it).
    Without that filter the situation fired constantly over
    ILLEGAL plays and the rate came out at 40-58% in ALL decks -- the symptom
    of a broken detector, not of an agent that gets distracted."""
    cur0 = menus[0]["obs"]["current"]
    yo0 = cur0["players"][cur0["yourIndex"]]
    forest = any(s.get("id") == m.Forest_of_Vitality
                 for s in (cur0.get("stadium") or []))
    in_play = {p["id"] for p in
                (yo0.get("active") or []) + (yo0.get("bench") or [])
                if p and (forest or not p.get("appearThisTurn"))}
    hand = {h["id"] for h in (yo0.get("hand") or [])}
    target = set()
    for line in m.EVO_LINES:
        for pre, evo in zip(line, line[1:]):
            if evo in hand and pre in in_play and evo not in in_play:
                target.add(evo)
    if not target:
        return False, False
    ult = menus[-1]["obs"]["current"]
    yo_f = ult["players"][ult["yourIndex"]]
    final = {p["id"] for p in
             (yo_f.get("active") or []) + (yo_f.get("bench") or []) if p}
    return True, bool(target & final)


def _damage(m, attacker, target, yo):
    bodies = [p for p in (yo.get("active") or []) + (yo.get("bench") or []) if p]
    e = len(attacker.get("energies") or [])
    a, o = _P(attacker), _P(target)
    try:
        base = m._attacker_base_damage(
            a.id, o, e, grass_scale=sum(len(p.get("energies") or [])
                                        for p in bodies),
            teal_self_energy=e,
            bench_count=sum(1 for b in (yo.get("bench") or []) if b))
        meg = any(p["id"] == m.Meganium for p in bodies)
        return m._our_effective_damage(a, o, base, meg, False)
    except Exception:
        return 0


# `_s_evoluciona_si_puede` is NOT included: measured in 3 decks it gives 33-61% -- low in
# ALL of them --, even after filtering out the pre-evolutions that appeared this turn (which
# cannot evolve without Forest). Evolving is genuinely DISCRETIONARY: the
# agent rightly declines often (keeping a 1-prize Dipplin, not
# building an ex Stage 2 against a wall that makes it useless...). A situation
# whose rate is low in every deck does not tell policy from failure: it only
# adds noise and false positives. The function is kept in case somebody
# refines it, but out of the table.
SITUACIONES = (
    ("pivote_al_muro", _s_pivot_to_wall),
    # A SANITY CHECK, not a detector: it comes out at 100% in every deck measured
    # (when the active knocks out, we always attack). Its value is being the canary
    # of the radar's own damage arithmetic -- if one day it drops below 100%,
    # either the agent broke or `_damage` broke.
    ("remata_si_puede", _s_remata_si_puede),
    ("juega_supporter", _s_supporter_unplayed),
    ("pone_energia", _s_energy_unattached),
    ("turno_productivo", _s_turn_not_sterile),
)


def radar(agent_state, opponent_deck, games):
    from opponent_bot import OpponentBot
    cnt = collections.defaultdict(lambda: [0, 0])   # name -> [applies, resolved]
    for i in range(games):
        _res, dec, _fin = au.play_recording(
            agent_state, OpponentBot(), agent_state.my_deck, opponent_deck, i % 2)
        turns = collections.defaultdict(list)
        for d in dec:
            turns[d["obs"]["current"]["turn"]].append(d)
        for _t, menus in turns.items():
            if not menus:
                continue
            for name, fn in SITUACIONES:
                try:
                    aplica, resuelta = fn(agent_state, menus)
                except Exception:
                    continue
                if aplica:
                    cnt[name][0] += 1
                    cnt[name][1] += int(resuelta)
    return cnt


def is_deck(path):
    """Is the CSV a list of 60 ids and not something else?

    `deck/real_opponents/` also carries `pesos.csv`. Without this filter the
    radar reads it as a deck and blows up AFTER having played every good
    matchup, which is the expensive place to fail.
    """
    try:
        lines = [x for x in path.read_text(encoding="utf-8-sig").split() if x.strip()]
    except (OSError, UnicodeDecodeError):
        return False
    if len(lines) != 60:
        return False
    return all(x.lstrip("-").isdigit() for x in lines)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--candidate", default="main.py")
    ap.add_argument("--only", default=None,
                    help="comma-separated list of decks")
    ap.add_argument("--opponents", default=str(_ROOT / "deck" / "opponents"),
                    help="folder of opposing decks (default: deck/opponents, "
                         "the 19 synthetic ones; deck/real_opponents points it "
                         "at the real leaderboard lists)")
    args = ap.parse_args(argv)

    agent_state = sp.load_agent(_ROOT / args.candidate, "agente_radar")
    carpeta = Path(args.opponents)
    if not carpeta.is_absolute():
        carpeta = _ROOT / carpeta
    if not carpeta.is_dir():
        print(f"ERROR: there is no {carpeta}", file=sys.stderr)
        return 2
    todos = sorted(carpeta.glob("*.csv"))
    decks = [p for p in todos if is_deck(p)]
    omitidos = [p.name for p in todos if p not in decks]
    if omitidos:
        print(f"(not decks, skipped: {', '.join(omitidos)})")
    if args.only:
        querer = {s.strip() for s in args.only.split(",")}
        decks = [p for p in decks if p.stem in querer]
    if not decks:
        print(f"ERROR: no deck to measure in {carpeta}", file=sys.stderr)
        return 2

    rows = {}
    for path in decks:
        deck = sp.read_deck(path)
        rows[path.stem] = radar(agent_state, deck, args.games)
        print(f"  {path.stem}: hecho", flush=True)

    names = [n for n, _ in SITUACIONES]
    width = max(len(k) for k in rows) if rows else 10
    print(f"\n=== COLLISION RADAR (n={args.games}/deck) ===")
    print("RESOLUTION rate per situation; (n) = how often the situation applies")
    print(f"{'deck':<{width}} " + "  ".join(f"{n:>18}" for n in names))
    for deck_name, cnt in sorted(rows.items()):
        celdas = []
        for n in names:
            ap_, ok = cnt[n]
            celdas.append(f"{100*ok/ap_:5.1f}% (n={ap_:4d})" if ap_ else
                          f"{'-':>18}")
        print(f"{deck_name:<{width}} " + "  ".join(f"{c:>18}" for c in celdas))

    # It flags outliers: a situation that in one deck is resolved much worse than
    # the MEDIAN of the rest is a collision candidate.
    print("\n--- candidates (resolution well below the median) ---")
    hubo = False
    for n in names:
        tasas = {mz: (c[n][1] / c[n][0]) for mz, c in rows.items()
                 if c[n][0] >= 10}
        if len(tasas) < 3:
            continue
        order = sorted(tasas.values())
        mediana = order[len(order) // 2]
        for mz, t in sorted(tasas.items(), key=lambda x: x[1]):
            if t < mediana - 0.25:
                hubo = True
                print(f"  {n:<18} {mz:<22} {100*t:5.1f}%  "
                      f"(mediana {100*mediana:5.1f}%)")
    if not hubo:
        print("  none: every situation resolves "
              "evenly across decks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
