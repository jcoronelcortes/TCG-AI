"""Automatic autopsy of self-play LOSSES.

Phase 6 of the strategy improvement architecture. Self-play (phase 3) only
returns a winrate; the lost games were thrown away -- and they are exactly the
material new rules come from. This piece plays N games against
an opposing deck (the generic bot) or in a mirror, RECORDS the decision stream of the
losses and runs post-hoc DETECTORS over them that reuse the agent's own
calculators (main._attacker_base_damage / main._our_effective_damage):

  - letal_perdido: in a MAIN select there was an attack from the ACTIVE that knocked out
    the opposing active, and the turn closed without attacking (END/RETREAT). It is marked
    CRITICAL if that KO also took the prizes we were missing (we lost
    a game we had WON).
  - turno_esteril: a whole turn closed with END or with a 0-damage
    attack while holding >= 4 cards in hand (the class of step 61 vs Dragapult).

v2 (step 5 of the jul 2026 plan):
  - The recorded observation of a turno_esteril is that of the FIRST MAIN select of the
    turn (the complete menu: that is where the decision that lost the value is), not the
    one of the final END -- which sometimes only offered END and was irreproducible
    (findings p029/p043 vs iron_thorns). The close is kept in paso_cierre/
    eleccion_cierre; opciones_primer_main counts the legal non-END plays
    the menu offered (value left on the table).
  - Each loss is classified by MODE (clasificar_derrota): prizes /
    bench_out / deckout / unknown; the games that hit the step LIMIT
    are also autopsied (mode "limite"). The mode travels in every finding and
    the summary prints the distribution: against stall (crustle) it separates the
    deck-out losses from the prize ones without checking deckCount by hand.

Each finding is written as JSON with the complete OBSERVATION of the step (the
format of the tests/ fixtures) into registros/autopsia/ (git-ignored, transient
local data): ready to reproduce with main.agent(), turn into a
fixture or sweep with the StateBuilder.

Usage:
    python utils/autopsia.py --rival deck/rivales/cornerstone_cubchoo.csv --partidas 100
    python utils/autopsia.py --espejo --partidas 100
    python utils/autopsia.py --todos --partidas 60   # every deck in deck/rivales/
    python utils/autopsia.py --rival ... --partidas 400 --censo   # + a contrast

v3 (Aug 2026): `--censo`. The detectors only look at LOSSES and only emit on
the turns that already failed; that reproduces a failure, but it does not say what CAUSES it.
Without a control group, a trait that is frequent in the losses cannot be told apart from a
trait that is simply frequent -- two hypotheses fell exactly that way. `censo_de_turnos`
builds a compact row (with no observations) per turn of ALL the games,
wins included, and `resumen_censo` prints each trait as
loss% vs win% and their DIFFERENCE, which is the only thing that explains anything.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp
from cg.api import OptionType, SelectContext

MAX_STEPS = 3000
MIN_HAND_STERILE = 4
# The switching card of our own list: the same id that in main.py switches
# `has_switch_card` on (a free retreat without paying energy).
SWITCH_CARD = 1123


def play_recording(agente, rival, own_deck, opponent_deck, asiento):
    """Plays a game recording OUR decisions.

    It returns (result, decisions, final_obs) with the result in {"gana",
    "pierde", "limite", "forfeit"}, decisions = [{obs, eleccion, paso}] and
    final_obs = the last observation seen (terminal except on a forfeit/limit),
    so the MODE of the loss can be classified.
    """
    from cg import game

    sp._reset_si_aplica(agente)
    sp._reset_si_aplica(rival)
    decks = ((own_deck, opponent_deck) if asiento == 0
             else (opponent_deck, own_deck))
    obs, sd = game.battle_start(list(decks[0]), list(decks[1]))
    if obs is None:
        raise RuntimeError(f"battle_start fallo: {sd.errorType}")
    agentes = {asiento: agente, 1 - asiento: rival}
    decisiones, steps = [], 0
    try:
        while obs["current"]["result"] == -1 and steps < MAX_STEPS:
            yi = obs["current"]["yourIndex"]
            try:
                choice = agentes[yi].agent(obs)
            except Exception:
                return (("forfeit" if yi == asiento else "gana"),
                        decisiones, obs)
            if yi == asiento:
                decisiones.append({"obs": obs, "eleccion": list(choice),
                                   "paso": steps})
            obs = game.battle_select(choice)
            steps += 1
        if obs["current"]["result"] == -1:
            return "limite", decisiones, obs
        return (("gana" if obs["current"]["result"] == asiento
                 else "pierde"), decisiones, obs)
    finally:
        game.battle_finish()


def clasificar_derrota(obs_final, asiento, result):
    """Classifies HOW the game was lost by looking at the final observation.

    Modes: "premios" (the opponent completed their prizes), "bench_out" (we
    were left with no Pokemon in play while the opponent still had prizes pending), "deckout"
    (the deck at 0 with the opponent's prizes pending), "limite" (the game reached
    MAX_PASOS with no result) and "desconocido" (no clear signal). The order
    of the checks matters: bench_out and deckout are only declared if the
    opponent was STILL missing prizes (otherwise the dominant cause is "premios").
    """
    if result == "limite":
        return "limite"
    try:
        cur = obs_final["current"]
        yo = cur["players"][asiento]
        op = cur["players"][1 - asiento]
    except (KeyError, IndexError, TypeError):
        return "desconocido"
    # The convention of the rest of the file: a None entry in prize is a
    # prize that player has STILL to take.
    op_restantes = sum(1 for p in (op.get("prize") or []) if p is None)
    activos = [p for p in (yo.get("active") or []) if p]
    bench = [p for p in (yo.get("bench") or []) if p]
    if op_restantes > 0 and not activos and not bench:
        return "bench_out"
    if op_restantes > 0 and (yo.get("deckCount") or 0) <= 0:
        return "deckout"
    if op_restantes == 0:
        return "premios"
    return "desconocido"


# --------------------------------------------------------------------------
# Detectors. They receive the decisions of ONE lost game and return
# findings: {detector, paso, turno, detalle, obs, eleccion}.
# --------------------------------------------------------------------------

def _mi_lado(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]], cur["players"][1 - cur["yourIndex"]]


def _lethal_damage_to_active(m, obs):
    """The best damage from OUR active to the opposing active this step (or 0)."""
    yo, op = _mi_lado(obs)
    if not (yo.get("active") and yo["active"][0] and
            op.get("active") and op["active"][0]):
        return 0, None
    act, opa = yo["active"][0], op["active"][0]
    e = len(act.get("energies") or [])
    total_grass = 0
    for p in [yo["active"][0]] + list(yo.get("bench") or []):
        if p:
            total_grass += len(p.get("energies") or [])
    bench_n = sum(1 for b in (yo.get("bench") or []) if b)

    class _P:  # a minimal adapter for main's calculators
        def __init__(self, d):
            self.id = d["id"]
            self.hp = d.get("hp")
            self.energies = list(d.get("energies") or [])

            class _C:
                def __init__(self, dd):
                    self.id = dd["id"]
            self.energyCards = [_C(c) for c in (d.get("energyCards") or [])]
            self.tools = [_C(c) for c in (d.get("tools") or [])]

    a, o = _P(act), _P(opa)
    base = m._attacker_base_damage(a.id, o, e, grass_scale=total_grass,
                                   teal_self_energy=e, bench_count=bench_n)
    if base <= 0:
        return 0, o
    meganium = any(p and p["id"] == m.Meganium
                   for p in [yo["active"][0]] + list(yo.get("bench") or []))
    return m._our_effective_damage(a, o, base, meganium, False), o


def turn_census(m, decisiones):
    """A COMPACT row per turn of ours, for ALL games -- wins
    included.

    The detectors below only look at losses and only emit on the turns that
    already failed. That is enough to reproduce a specific failure, but not to
    decide WHAT causes it: without a control group, any pattern that is frequent in
    the losses looks like the cause even if it is just as frequent in the wins.
    Two hypotheses fell exactly that way (Aug 2026): "the Grass goes to the bench
    with the active stuck" turned out to be 15% of the cases, and the routing
    through Ripening Charge measured negative.

    The census does not keep observations -- only the traits that can be counted --
    so it fits for thousands of games and makes it possible to contrast
    `loss vs win` in the same batch. To reproduce a specific turn the
    detectors' `pasos_turno` are still there.

    Traits per turn: whether we attacked, the state of the ACTIVE (attack / retreat), whether
    there is a READY attacker waiting on the bench, the energy ammunition and how it closed.
    """
    filas = []
    per_turn = {}
    for d in decisiones:
        per_turn.setdefault(d["obs"]["current"]["turn"], []).append(d)

    for turn, ds in sorted(per_turn.items()):
        mains = [d for d in ds
                 if (d["obs"].get("select") or {}).get("context")
                 == int(SelectContext.MAIN)]
        if not mains:
            continue
        first, last = mains[0], mains[-1]
        yo, _ = _mi_lado(first["obs"])
        # The ONCE-PER-TURN resources are read from the LAST select, not from the
        # first: in the first one nothing has been played yet and they always come out
        # unspent in both groups (an empty trait). Here they measure what
        # really matters, what the turn left unused.
        cur = last["obs"]["current"]
        act = (yo.get("active") or [None])[0]
        hand = yo.get("hand") or []

        # Is the ACTIVE stuck? It neither reaches its attack cost nor can it pay
        # its retreat with the energy it already carries.
        atascado = can_attack = can_retreat = None
        if act is not None:
            req = m.ATTACK_ENERGY_REQ.get(act["id"])
            e = len(act["energies"])
            can_attack = None if req is None else (e * m._grass_mult() >= req)
            can_retreat = e >= m.RETREAT_COST.get(act["id"], 1)
            atascado = (can_attack is False) and not can_retreat

        # A REAL benched attacker that already reaches its cost: what the jam
        # leaves locked in behind it.
        ready_on_bench = sum(
            1 for b in (yo.get("bench") or [])
            if b["id"] in m.MAIN_ATTACKERS
            and len(b["energies"]) * m._grass_mult()
            >= (m.ATTACK_ENERGY_REQ.get(b["id"]) or 99))

        # Was there a WAY OUT of the jam? It is the question that decides the SHAPE of the
        # fix: if there was one and it was not taken, it is a SCORING problem; if there
        # was none, no scoring rule touches it and we have to go upstream
        # (which body gets promoted and with what retreat cost).
        # Three routes, the same ones the agent recognises:
        #   * the menu OFFERS a retreat (`can_switch`) in some select of the turn;
        #   * a switching card in hand (id 1123, the one that switches `has_switch_
        #     card` on);
        #   * the retreat becomes payable with the charge that STILL fits today.
        # The last one mirrors `_grass_unlocks_active_retreat`: `energies` already comes
        # in EFFECTIVE symbols and each new physical Grass provides `unidad`
        # (2 with Meganium in play through Wild Growth), so the deficit is measured
        # in CARDS.
        retreat_in_menu = any(
            int(o.get("type", -1)) == int(OptionType.RETREAT)
            for d in mains for o in d["obs"]["select"]["option"])
        switch_in_hand = any(c["id"] == SWITCH_CARD for c in hand)
        retreat_payable_today = False
        if act is not None and not can_retreat:
            campo = [act] + [b for b in (yo.get("bench") or []) if b]
            unit = 2 if any(b["id"] == m.Meganium for b in campo) else 1
            # Attachment routes that can leave a Grass ON THE ACTIVE today:
            # the manual one if it is still free, the Ripening Charge of each Hydrapple ex
            # (which charges anyone) and Teal Dance only if the ACTIVE is the Ogerpon.
            vias = (0 if cur.get("energyAttached") else 1)
            vias += sum(1 for b in campo if b["id"] == m.Hydrapple_ex)
            if act["id"] == m.Teal_Mask_Ogerpon_ex:
                vias += 1
            plantas = sum(1 for c in hand if c["id"] == m.Basic_Grass_Energy)
            missing = m.RETREAT_COST.get(act["id"], 1) - len(act["energies"])
            necesarias = -(-missing // unit)
            retreat_payable_today = 1 <= necesarias <= min(vias, plantas)
        escapatoria = bool(retreat_in_menu or switch_in_hand
                           or retreat_payable_today)

        closing_choice = None
        if last["eleccion"]:
            closing_choice = int(last["obs"]["select"]["option"][
                last["eleccion"][0]].get("type", -1))
        ataco = any(
            int(d["obs"]["select"]["option"][d["eleccion"][0]].get("type", -1))
            == int(OptionType.ATTACK)
            for d in mains if d["eleccion"])

        filas.append({
            "turno": turn,
            "selects": len(mains),
            "ataco": ataco,
            "cierre": closing_choice,
            "mano": len(hand),
            "opciones_no_end": sum(
                1 for o in first["obs"]["select"]["option"]
                if int(o.get("type", -1)) != int(OptionType.END)),
            "activo": None if act is None else act["id"],
            "activo_hp": None if act is None else act["hp"],
            "activo_energias": None if act is None else len(act["energies"]),
            "puede_atacar": can_attack,
            "puede_retirar": can_retreat,
            "atascado": atascado,
            "escapatoria": escapatoria,
            "retirada_en_menu": retreat_in_menu,
            "cambio_en_mano": switch_in_hand,
            "retirada_pagable_hoy": retreat_payable_today,
            "listos_banca": ready_on_bench,
            "plantas_mano": sum(1 for c in hand
                                if c["id"] == m.Basic_Grass_Energy),
            "adjunte_gastado": bool(cur.get("energyAttached")),
            "supporter_gastado": bool(cur.get("supporterPlayed")),
            "mis_premios": sum(1 for p in (yo.get("prize") or []) if p is None),
        })
    return filas


def detectar(m, decisiones):
    hallazgos = []

    # group decisions by our own turn
    per_turn = {}
    for d in decisiones:
        per_turn.setdefault(d["obs"]["current"]["turn"], []).append(d)

    for turn, ds in sorted(per_turn.items()):
        mains = [d for d in ds
                 if (d["obs"].get("select") or {}).get("context")
                 == int(SelectContext.MAIN)]
        if not mains:
            continue

        # --- letal_perdido: there was a step with a KO available from the active and the
        # turn closed without ATTACKING.
        ataco = any(
            int(d["obs"]["select"]["option"][d["eleccion"][0]].get("type", -1))
            == int(OptionType.ATTACK)
            for d in mains if d["eleccion"])
        if not ataco:
            for d in mains:
                opciones = d["obs"]["select"]["option"]
                if not any(int(o.get("type", -1)) == int(OptionType.ATTACK)
                           for o in opciones):
                    continue
                damage, opa = _lethal_damage_to_active(m, d["obs"])
                if opa is None or damage <= 0:
                    continue
                if damage >= (opa.hp or 0) > 0:
                    yo, _ = _mi_lado(d["obs"])
                    my_prizes = sum(1 for p in yo.get("prize") or []
                                      if p is None)
                    gana = m.prize_count(opa) >= my_prizes
                    hallazgos.append({
                        "detector": "letal_perdido",
                        "critico": bool(gana),
                        "turno": turn, "paso": d["paso"],
                        "detalle": (f"KO disponible ({damage} >= "
                                    f"{opa.hp}) y el turno cerro "
                                    f"sin atacar"),
                        "eleccion": d["eleccion"],
                        "observation": d["obs"],
                    })
                    break

        # --- turno_esteril: a close with END or a 0-damage attack with a fat hand.
        last = mains[-1]
        if not last["eleccion"]:
            continue
        opcion = last["obs"]["select"]["option"][last["eleccion"][0]]
        t = int(opcion.get("type", -1))
        yo, _ = _mi_lado(last["obs"])
        hand = len(yo.get("hand") or [])
        esteril = False
        if t == int(OptionType.END) and hand >= MIN_HAND_STERILE:
            esteril = True
        elif t == int(OptionType.ATTACK) and hand >= MIN_HAND_STERILE:
            atk = m.attack_table.get(opcion.get("attackId"))
            damage, _opa = _lethal_damage_to_active(m, last["obs"])
            if atk is not None and (atk.damage or 0) == 0 and damage == 0:
                esteril = True
        if esteril:
            # v2: the useful observation is that of the FIRST MAIN select of the turn
            # (the complete menu -- reproducible with main.agent() and sweepable with
            # the explorer); the final END sometimes only offered END. The
            # close is kept in paso_cierre/eleccion_cierre.
            first = mains[0]
            opciones_no_end = sum(
                1 for o in first["obs"]["select"]["option"]
                if int(o.get("type", -1)) != int(OptionType.END))
            hallazgos.append({
                "detector": "turno_esteril",
                "critico": False,
                "turno": turn, "paso": first["paso"],
                "detalle": (f"turno cerrado con "
                            f"{'END' if t == int(OptionType.END) else 'ataque de 0'}"
                            f" y {hand} cartas en mano"),
                "eleccion": first["eleccion"],
                "observation": first["obs"],
                "paso_cierre": last["paso"],
                "eleccion_cierre": last["eleccion"],
                "opciones_primer_main": opciones_no_end,
                # v2.1: the COMPLETE turn step by step (every MAIN select
                # with its observation and choice). Multi-step failures (the
                # plan of the first MAIN dies mid-turn: e.g. a positive Boss's
                # at the start and the close arrives with no gust) are only
                # diagnosed by reproducing the whole sequence.
                "pasos_turno": [
                    {"paso": d["paso"], "eleccion": d["eleccion"],
                     "observation": d["obs"]} for d in mains],
            })
    return hallazgos


def census_summary(censo, etiqueta):
    """LOSS vs WIN contrast over the turn census.

    Each trait is printed as its per-turn frequency in each group and the
    DIFFERENCE. What matters is the difference, not the level: a trait that appears
    in 40% of the turns of the losses and in 39% of those of the wins
    explains nothing, however striking it looks when reading a single game.
    """
    perd = [f for f in censo if f["resultado"] != "gana"]
    gana = [f for f in censo if f["resultado"] == "gana"]
    if not perd or not gana:
        print("  censo: hace falta al menos una victoria y una derrota")
        return
    rasgos = {
        "turno sin atacar": lambda f: not f["ataco"],
        "activo ATASCADO (ni ataca ni retira)": lambda f: f["atascado"] is True,
        "atascado + atacante listo en banca":
            lambda f: f["atascado"] is True and f["listos_banca"] >= 1,
        "atascado SIN escapatoria (no arreglable puntuando)":
            lambda f: f["atascado"] is True and not f.get("escapatoria"),
        "atascado CON escapatoria y no se tomo":
            lambda f: f["atascado"] is True and bool(f.get("escapatoria")),
        "sin atacante listo en ningun sitio":
            lambda f: f["listos_banca"] == 0 and f["puede_atacar"] is not True,
        "sin Plantas en la mano": lambda f: f["plantas_mano"] == 0,
        "adjunte del turno sin gastar": lambda f: not f["adjunte_gastado"],
        "supporter del turno sin gastar": lambda f: not f["supporter_gastado"],
        "cierre con END": lambda f: f["cierre"] == int(OptionType.END),
    }
    print(f"  censo [{etiqueta}]: {len(perd)} turnos en derrotas vs "
          f"{len(gana)} en victorias")
    print(f"    {'rasgo':40}{'derrota':>9}{'victoria':>10}{'dif':>8}")
    filas = []
    for name, f in rasgos.items():
        pp = 100 * sum(1 for x in perd if f(x)) / len(perd)
        pg = 100 * sum(1 for x in gana if f(x)) / len(gana)
        filas.append((pp - pg, name, pp, pg))
    for dif, name, pp, pg in sorted(filas, reverse=True):
        print(f"    {name:40}{pp:8.1f}%{pg:9.1f}%{dif:+8.1f}")
    # Jam streaks: a single stuck turn is noise; a long streak is
    # a whole game played from behind a wall of our own making.
    for group, name in ((perd, "derrotas"), (gana, "victorias")):
        rachas, actual, per_game = [], 0, None
        for f in group:
            if f["partida"] != per_game:
                if actual:
                    rachas.append(actual)
                actual, per_game = 0, f["partida"]
            if f["atascado"] is True:
                actual += 1
            else:
                if actual:
                    rachas.append(actual)
                actual = 0
        if actual:
            rachas.append(actual)
        largas = [r for r in rachas if r >= 3]
        print(f"    rachas de atasco en {name}: {len(rachas)} "
              f"(>=3 turnos seguidos: {len(largas)}, "
              f"max {max(rachas) if rachas else 0})")


def autopsia(opponent_csv, partidas, espejo=False, destino=None, censar=False):
    import main as m
    destino = destino or (_ROOT / "registros" / "autopsia")
    destino.mkdir(parents=True, exist_ok=True)

    agente = sp.load_agent(_ROOT / "main.py", "agente_autopsia")
    own_deck = sp.read_deck()
    if espejo:
        rival = sp.load_agent(_ROOT / "main.py", "rival_autopsia")
        opponent_deck, etiqueta = own_deck, "espejo"
    else:
        from bot_rival import BotRival
        rival = BotRival()
        opponent_deck = sp.read_deck(opponent_csv)
        etiqueta = Path(opponent_csv).stem

    marcador = Counter()
    modos = Counter()
    total_findings = []
    mode_per_game = {}
    censo = []
    for i in range(partidas):
        result, decisiones, obs_final = play_recording(
            agente, rival, own_deck, opponent_deck, asiento=i % 2)
        marcador[result] += 1
        # THE CENSUS: it is built from ALL the games, wins included. It is the
        # CONTROL group -- without it, a pattern that is frequent in the losses cannot be
        # told apart from a pattern that is simply frequent.
        if censar:
            for row in turn_census(m, decisiones):
                row["partida"] = i
                row["resultado"] = result
                censo.append(row)
        # v2: the games that hit the LIMIT are autopsied too (vs stall they are
        # the interesting failure mode), as well as losses and forfeits.
        if result not in ("pierde", "forfeit", "limite"):
            continue
        modo = clasificar_derrota(obs_final, asiento=i % 2,
                                  result=result)
        modos[modo] += 1
        mode_per_game[i] = modo
        for h in detectar(m, decisiones):
            h["partida"] = i
            h["rival"] = etiqueta
            h["resultado"] = result
            h["modo_derrota"] = modo
            total_findings.append(h)

    # persist: one file per game with its findings
    per_game = {}
    for h in total_findings:
        per_game.setdefault(h["partida"], []).append(h)
    for num, hs in per_game.items():
        path = destino / f"{etiqueta}_p{num:03d}.json"
        path.write_text(json.dumps(
            {"rival": etiqueta, "partida": num,
             "modo_derrota": mode_per_game.get(num, "desconocido"),
             "hallazgos": hs},
            ensure_ascii=False, indent=1))

    print(f"[{etiqueta}] {dict(marcador)}")
    if modos:
        print(f"  modo de derrota: {dict(modos.most_common())}")
    summary = Counter((h["detector"], h["critico"]) for h in total_findings)
    for (det, critico), n in summary.most_common():
        print(f"  {det}{' CRITICO' if critico else ''}: {n} "
              f"(en {len(per_game)} partidas perdidas)")
    if not total_findings:
        print("  sin hallazgos en las derrotas")
    if censar:
        (destino / f"{etiqueta}_censo.json").write_text(json.dumps(
            {"rival": etiqueta, "partidas": partidas, "turnos": censo},
            ensure_ascii=False))
        census_summary(censo, etiqueta)
    return total_findings


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rival", default=None, help="csv del mazo rival")
    ap.add_argument("--espejo", action="store_true")
    ap.add_argument("--todos", action="store_true",
                    help="autopsia contra todos los mazos de deck/rivales/")
    ap.add_argument("--partidas", type=int, default=100)
    ap.add_argument("--censo", action="store_true",
                    help="censo de turnos de TODAS las partidas (ganadas "
                         "incluidas) y contraste derrota-vs-victoria")
    args = ap.parse_args(argv)

    if args.todos:
        for path in sorted((_ROOT / "deck" / "rivales").glob("*.csv")):
            autopsia(path, args.partidas, censar=args.censo)
        return 0
    if args.espejo:
        autopsia(None, args.partidas, espejo=True, censar=args.censo)
        return 0
    if not args.rival:
        print("indica --rival, --espejo o --todos")
        return 1
    autopsia(args.rival, args.partidas, censar=args.censo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
