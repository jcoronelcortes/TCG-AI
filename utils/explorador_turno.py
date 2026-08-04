"""Exhaustive TURN explorer: it finds the best line of our
actions and compares it with the one the agent chooses.

Phase 7 of the strategy improvement architecture. It generalises the "walkers"
of the tests (the Myriad combo, the Ogerpon pivot): given a state (an observation),
it enumerates ALL the legal sequences of our actions in the turn with a
transition model of its own, evaluates the final state of each one and returns
the dominant line. If the agent's line ends up dominated, there is a
new scenario there with the correct play already computed.

LIMITS of the model (v1, documented on purpose):
  - OUR turn only (the opponent's hidden information makes it impossible to branch the
    real simulator). No draws: the Teal Dance draw / the hand refills
    (Lillie's) are not modelled because their outcome is chance.
  - Modelled actions: the manual attachment, Teal Dance, Ripening Charge, retreat
    +promotion, evolution, Night Stretcher (recovering Grass), Boss's Orders
    (a gust), Forest of Vitality, the ACTIVE's attack (via main's own
    calculators) and ending the turn.
  - The damage uses main._attacker_base_damage/_our_effective_damage: exact for
    our main attackers; the chip attacks that are not modelled count as 0.

Evaluation (lexicographic): winning > prizes taken > damage dealt >
energy attached + bodies played + evolutions. A sterile turn loses
against any line that develops.

Usage:
    python utils/explorador_turno.py --demo                # the Myriad combo
    python utils/explorador_turno.py --hallazgo registros/autopsia/X.json
    python utils/explorador_turno.py --autopsia registros/autopsia/ --max 20
"""

import argparse
import copy
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import main as m
from cg.api import OptionType

MAX_NODOS = 30000


# --------------------------------------------------------------------------
# State utilities (over the observation dict, like the walkers)
# --------------------------------------------------------------------------

def _yo(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _op(obs):
    cur = obs["current"]
    return cur["players"][1 - cur["yourIndex"]]


def _pokes(j):
    activos = [p for p in (j.get("active") or []) if p]
    return activos + [p for p in (j.get("bench") or []) if p]


def _firma(obs):
    """State signature used to deduplicate transpositions."""
    def pk_sig(p):
        return (p["id"], len(p.get("energies") or []), p.get("hp"))
    yo, op = _yo(obs), _op(obs)
    cur = obs["current"]
    return (
        tuple(pk_sig(p) for p in (yo.get("active") or []) if p),
        tuple(sorted(pk_sig(p) for p in (yo.get("bench") or []) if p)),
        tuple(sorted(c["id"] for c in (yo.get("hand") or []))),
        tuple(sorted(c["id"] for c in (yo.get("discard") or []))),
        tuple(pk_sig(p) for p in (op.get("active") or []) if p),
        tuple(sorted(pk_sig(p) for p in (op.get("bench") or []) if p)),
        cur.get("energyAttached"), cur.get("retreated"),
        cur.get("supporterPlayed"), cur.get("stadiumPlayed"),
        tuple(s["id"] for s in (cur.get("stadium") or [])),
        tuple(sorted(obs.get("_td_usadas", ()))),
        tuple(sorted(obs.get("_rc_usadas", ()))),
    )


class _P:
    """dict->object adapter for main's calculators."""

    def __init__(self, d):
        self.id = d["id"]
        self.hp = d.get("hp")
        self.maxHp = d.get("maxHp")
        self.energies = list(d.get("energies") or [])

        class _C:
            def __init__(self, dd):
                self.id = dd["id"]
        self.energyCards = [_C(c) for c in (d.get("energyCards") or [])]
        self.tools = [_C(c) for c in (d.get("tools") or [])]


def _meganium_en_juego(obs):
    return any(p["id"] == m.Meganium for p in _pokes(_yo(obs)))


def _forest_en_juego(obs):
    return any(s["id"] == m.Forest_of_Vitality
               for s in (obs["current"].get("stadium") or []))


def _lock_habilidades_ex(obs):
    """The abilities of our EX Pokemon are cancelled (step 6 of the jul
    2026 plan): an Iron Thorns ex as the opposing ACTIVE (Initialization) or Team Rocket's
    Watchtower as the stadium. Without this the explorer proposed illegal lines
    (TEAL DANCE x3 against an active Iron Thorns ex, finding p029) and contaminated
    the judgement of the autopsies precisely in the weakest matchup."""
    op = _op(obs)
    act = (op.get("active") or [None])[0]
    if act and act.get("id") == m.Iron_Thorns_ex:
        return True
    return any(s["id"] == m.Team_Rockets_Watchtower
               for s in (obs["current"].get("stadium") or []))


def _dano_activo(obs):
    """(effective_damage, target_dict) of our active's attack."""
    yo, op = _yo(obs), _op(obs)
    if not (yo.get("active") and yo["active"][0]
            and op.get("active") and op["active"][0]):
        return 0, None
    act, opa = yo["active"][0], op["active"][0]
    e = len(act.get("energies") or [])
    total_grass = sum(len(p.get("energies") or []) for p in _pokes(yo))
    bench_n = len([p for p in (yo.get("bench") or []) if p])
    a, o = _P(act), _P(opa)
    base = m._attacker_base_damage(a.id, o, e, grass_scale=total_grass,
                                   teal_self_energy=e, bench_count=bench_n)
    if base <= 0:
        return 0, opa
    return m._our_effective_damage(a, o, base, _meganium_en_juego(obs),
                                   False), opa


# --------------------------------------------------------------------------
# Enumerating and applying actions. An action is (label, apply)
# where apply(obs) -> a new obs (deepcopy) or None if it is terminal.
# --------------------------------------------------------------------------

def _quitar_de_mano(yo, card_id):
    i = next(i for i, c in enumerate(yo["hand"]) if c["id"] == card_id)
    card = yo["hand"][i]
    yo["hand"] = [c for j, c in enumerate(yo["hand"]) if j != i]
    yo["handCount"] = len(yo["hand"])
    return card


def _adjunta(p, card):
    p["energies"] = list(p.get("energies") or []) + [1]
    p["energyCards"] = list(p.get("energyCards") or []) + [card]


def _slots(yo):
    out = []
    if yo.get("active") and yo["active"][0]:
        out.append(("activo", yo["active"][0]))
    for k, bp in enumerate(yo.get("bench") or []):
        if bp:
            out.append((f"banca{k}", bp))
    return out


def _menu_real(obs):
    """(types, play_ids) of the simulator's REAL menu at the ROOT node, or
    (None, None) if it does not apply (step 6b of the jul 2026 plan). It is only consulted with
    `_respetar_menu` (autopsy findings: their first MAIN select carries the
    complete menu and already reflects ability locks, item blocks -- Budew
    --, impossible retreats, etc.); the SYNTHETIC scenarios (--demo,
    StateBuilder) build partial menus on purpose and are not filtered.
    The SIMULATED nodes (after the first transition) are not either: there the
    recorded menu no longer describes the state."""
    if not obs.get("_respetar_menu") or obs.get("_simulado"):
        return None, None
    opts = (obs.get("select") or {}).get("option") or []
    if not opts:
        return None, None
    tipos = {int(o.get("type", -1)) for o in opts}
    hand = _yo(obs).get("hand") or []
    play_ids = set()
    for o in opts:
        if (int(o.get("type", -1)) == int(OptionType.PLAY)
                and o.get("index") is not None and o["index"] < len(hand)):
            play_ids.add(hand[o["index"]]["id"])
    return tipos, play_ids


def acciones_legales(obs):
    yo, op = _yo(obs), _op(obs)
    cur = obs["current"]
    acciones = []
    mano_ids = [c["id"] for c in (yo.get("hand") or [])]
    grass_en_mano = m.Basic_Grass_Energy in mano_ids
    forest = _forest_en_juego(obs)

    # Legality filter through the real menu (the root node of findings only).
    _tipos_menu, _play_ids_menu = _menu_real(obs)

    def _permitido(tipo):
        return _tipos_menu is None or int(tipo) in _tipos_menu

    def _play_ok(cid):
        return _play_ids_menu is None or cid in _play_ids_menu

    # manual attachment
    if (grass_en_mano and not cur.get("energyAttached")
            and _permitido(OptionType.ATTACH)):
        for name, p in _slots(yo):
            def ap(obs, _n=name):
                o2 = copy.deepcopy(obs)
                y2 = _yo(o2)
                card = _quitar_de_mano(y2, m.Basic_Grass_Energy)
                tgt = dict(_slots(y2))[_n]
                _adjunta(tgt, card)
                o2["current"]["energyAttached"] = True
                return o2
            acciones.append((f"ATTACH->{m.card_table[p['id']].name}", ap))

    # Teal Dance (one per Ogerpon per turn; the draw is not modelled).
    # An EX ability: cancelled under _lock_habilidades_ex.
    if (grass_en_mano and not _lock_habilidades_ex(obs)
            and _permitido(OptionType.ABILITY)):
        for name, p in _slots(yo):
            if (p["id"] == m.Teal_Mask_Ogerpon_ex
                    and p["serial"] not in obs.get("_td_usadas", ())):
                def ap(obs, _n=name, _s=p["serial"]):
                    o2 = copy.deepcopy(obs)
                    y2 = _yo(o2)
                    card = _quitar_de_mano(y2, m.Basic_Grass_Energy)
                    _adjunta(dict(_slots(y2))[_n], card)
                    o2["_td_usadas"] = tuple(obs.get("_td_usadas", ())) + (_s,)
                    return o2
                acciones.append(("TEAL DANCE", ap))

    # Ripening Charge (Hydrapple ex: it attaches 1 Grass from hand to anyone).
    # An EX ability: cancelled under _lock_habilidades_ex.
    if (grass_en_mano and not _lock_habilidades_ex(obs)
            and _permitido(OptionType.ABILITY)):
        for _, hyd in _slots(yo):
            if (hyd["id"] == m.Hydrapple_ex
                    and hyd["serial"] not in obs.get("_rc_usadas", ())):
                for name, p in _slots(yo):
                    def ap(obs, _n=name, _s=hyd["serial"]):
                        o2 = copy.deepcopy(obs)
                        y2 = _yo(o2)
                        card = _quitar_de_mano(y2, m.Basic_Grass_Energy)
                        _adjunta(dict(_slots(y2))[_n], card)
                        o2["_rc_usadas"] = tuple(
                            obs.get("_rc_usadas", ())) + (_s,)
                        return o2
                    acciones.append(
                        (f"RIPENING->{m.card_table[p['id']].name}", ap))
                break

    # evolution (hand -> a pre-evolution in play; Forest allows it the same turn)
    for cid in set(mano_ids) if _permitido(OptionType.EVOLVE) else ():
        data = m.card_table.get(cid)
        if not data or not (data.stage1 or data.stage2):
            continue
        for name, p in _slots(yo):
            pdata = m.card_table.get(p["id"])
            if not pdata or data.evolvesFrom != pdata.name:
                continue
            if p.get("appearThisTurn") and not forest:
                continue
            def ap(obs, _cid=cid, _n=name):
                o2 = copy.deepcopy(obs)
                y2 = _yo(o2)
                card = _quitar_de_mano(y2, _cid)
                tgt = dict(_slots(y2))[_n]
                previo = {k: tgt[k] for k in tgt}
                tgt["preEvolution"] = (list(tgt.get("preEvolution") or [])
                                       + [{"id": previo["id"],
                                           "playerIndex": card["playerIndex"],
                                           "serial": previo["serial"]}])
                dano_actual = (previo.get("maxHp") or 0) - (previo.get("hp") or 0)
                nueva = m.card_table[_cid]
                tgt["id"] = _cid
                tgt["serial"] = card["serial"]
                tgt["maxHp"] = nueva.hp
                tgt["hp"] = max(1, nueva.hp - dano_actual)
                tgt["appearThisTurn"] = True
                o2["_evoluciones"] = obs.get("_evoluciones", 0) + 1
                return o2
            acciones.append(
                (f"EVOLVE {data.name}<-{pdata.name}", ap))

    # retreat + promotion (the cost in effective energies, v1)
    act = yo["active"][0] if yo.get("active") and yo["active"][0] else None
    if (act is not None and not cur.get("retreated")
            and _permitido(OptionType.RETREAT)):
        cost = m.card_table[act["id"]].retreatCost
        if len(act.get("energies") or []) >= cost:
            for k, bp in enumerate(yo.get("bench") or []):
                if not bp:
                    continue
                def ap(obs, _k=k, _coste=cost):
                    o2 = copy.deepcopy(obs)
                    y2 = _yo(o2)
                    a2 = y2["active"][0]
                    for _ in range(_coste):
                        if a2["energyCards"]:
                            y2["discard"] = (list(y2["discard"])
                                             + [a2["energyCards"].pop()])
                        a2["energies"] = a2["energies"][:-1]
                    nuevo = y2["bench"][_k]
                    y2["active"] = [nuevo]
                    y2["bench"] = [b for i, b in enumerate(y2["bench"])
                                   if i != _k] + [a2]
                    o2["current"]["retreated"] = True
                    return o2
                acciones.append(
                    (f"RETREAT->{m.card_table[bp['id']].name}", ap))

    # Night Stretcher: recovering a Grass from the discard (v1: energy only)
    if (m.Night_Stretcher in mano_ids and _play_ok(m.Night_Stretcher)
            and any(c["id"] == m.Basic_Grass_Energy
                    for c in (yo.get("discard") or []))):
        def ap(obs):
            o2 = copy.deepcopy(obs)
            y2 = _yo(o2)
            ns = _quitar_de_mano(y2, m.Night_Stretcher)
            y2["discard"] = list(y2["discard"]) + [ns]
            i = next(i for i, c in enumerate(y2["discard"])
                     if c["id"] == m.Basic_Grass_Energy)
            card = y2["discard"][i]
            y2["discard"] = [c for j, c in enumerate(y2["discard"]) if j != i]
            y2["hand"] = list(y2["hand"]) + [card]
            y2["handCount"] = len(y2["hand"])
            return o2
        acciones.append(("NS->PLANTA", ap))

    # Boss's Orders: bringing up a target from the opposing bench
    if (m.Boss_Orders in mano_ids and not cur.get("supporterPlayed")
            and _play_ok(m.Boss_Orders)
            and any(b for b in (op.get("bench") or []))):
        for k, bp in enumerate(op.get("bench") or []):
            if not bp:
                continue
            def ap(obs, _k=k):
                o2 = copy.deepcopy(obs)
                y2, p2 = _yo(o2), _op(o2)
                boss = _quitar_de_mano(y2, m.Boss_Orders)
                y2["discard"] = list(y2["discard"]) + [boss]
                objetivo = p2["bench"][_k]
                anterior = p2["active"][0]
                p2["active"] = [objetivo]
                p2["bench"] = [b for i, b in enumerate(p2["bench"])
                               if i != _k] + [anterior]
                o2["current"]["supporterPlayed"] = True
                return o2
            acciones.append(
                (f"BOSS->{m.card_table[bp['id']].name}", ap))

    # Forest of Vitality
    if (m.Forest_of_Vitality in mano_ids and not forest
            and _play_ok(m.Forest_of_Vitality)
            and not cur.get("stadiumPlayed")):
        def ap(obs):
            o2 = copy.deepcopy(obs)
            y2 = _yo(o2)
            card = _quitar_de_mano(y2, m.Forest_of_Vitality)
            o2["current"]["stadium"] = [card]
            o2["current"]["stadiumPlayed"] = True
            return o2
        acciones.append(("FOREST", ap))

    # the active's attack (terminal). At the root node the real menu rules: if the
    # simulator did not offer ATTACK (not enough energy, a condition), the
    # model does not invent it; after any transition the model decides
    # again (a simulated attachment can enable the attack).
    damage, opa = _dano_activo(obs)
    if damage > 0 and _permitido(OptionType.ATTACK):
        acciones.append(("ATTACK", None))
    acciones.append(("END", None))
    return acciones


def evaluar_terminal(obs, ataca):
    """A lexicographic tuple: (wins, prizes, damage, development)."""
    yo = _yo(obs)
    prizes, damage = 0, 0
    gana = False
    if ataca:
        damage, opa = _dano_activo(obs)
        if opa is not None and damage >= (opa.get("hp") or 0) > 0:
            prizes = m.prize_count(_P(opa))
            faltan = sum(1 for p in (yo.get("prize") or []) if p is None)
            gana = prizes >= faltan
            damage = opa["hp"]
    energy = sum(len(p.get("energies") or []) for p in _pokes(yo))
    desarrollo = (len(_pokes(yo)) * 10 + energy
                  + obs.get("_evoluciones", 0) * 5)
    return (int(gana), prizes, damage, desarrollo)


def explorar(obs, max_nodos=MAX_NODOS, respetar_menu=False):
    """Returns (best_score, best_line) by exploring the complete turn.

    With `respetar_menu` (step 6b), the ROOT node only generates actions whose
    type appears in the observation's real menu (see _menu_real): for
    autopsy findings, where the simulator's menu already reflects locks and
    blocks the v1 model does not know about. The synthetic scenarios (--demo)
    do not switch it on: their menus are partial on purpose."""
    inicial = copy.deepcopy(obs)
    inicial.setdefault("_evoluciones", 0)
    if respetar_menu:
        inicial["_respetar_menu"] = True
    best = [None, None]
    vistos = set()
    nodos = [0]

    def dfs(estado, line):
        if nodos[0] >= max_nodos:
            return
        nodos[0] += 1
        for etiqueta, apply in acciones_legales(estado):
            if apply is None:  # terminal: ATTACK or END
                p = evaluar_terminal(estado, etiqueta == "ATTACK")
                if best[0] is None or p > best[0]:
                    best[0], best[1] = p, line + [etiqueta]
                continue
            sig = estado_sig = None
            nuevo = apply(estado)
            # After the first transition the state is SIMULATED: the recorded
            # menu no longer describes it and legality goes back to the model.
            nuevo["_simulado"] = True
            estado_sig = _firma(nuevo)
            if estado_sig in vistos:
                continue
            vistos.add(estado_sig)
            dfs(nuevo, line + [etiqueta])

    dfs(inicial, [])
    return best[0], best[1], nodos[0]


def comparar_hallazgo(ruta, indice=0, max_nodos=MAX_NODOS):
    data = json.loads(Path(ruta).read_text())
    h = data["hallazgos"][indice]
    obs = h["observation"]
    # A real autopsy finding: the simulator's menu rules at the root node.
    puntaje, line, nodos = explorar(obs, max_nodos, respetar_menu=True)
    print(f"{Path(ruta).name} [{h['detector']} turno {h['turno']}]")
    print(f"  agente en la partida: {h['detalle']}")
    print(f"  mejor linea del explorador ({nodos} nodos): "
          f"{' -> '.join(line)}")
    print(f"  evaluacion (gana, premios, dano, desarrollo): {puntaje}")
    return puntaje, line


def demo_combo_myriad():
    """The explorer must rediscover the combo of registro_012 step 227."""
    from state_builder import Escenario, pk, G
    import golden_corpus as gc
    gc.reset_agente(m)
    obs = (Escenario(turn=12, paso=227, tac=1, premios_propios=2)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G] * 4, fisicas=4))
           .mi_banca(pk(m.Applin))
           .mi_mano(m.Basic_Grass_Energy, m.Boss_Orders)
           .op_activo(pk(271, hp=120, max_hp=120))          # Kilowattrel
           .op_banca(pk(269, hp=280, max_hp=280,
                        energias=[G, G, G, G]))             # Bellibolt ex
           .op_zonas(mano=5, mazo=30, prizes=3)
           .menu_teal_dance()
           .construir())
    puntaje, line, nodos = explorar(obs)
    print("demo combo Myriad (registro_012 paso 227):")
    print(f"  mejor linea ({nodos} nodos): {' -> '.join(line)}")
    print(f"  evaluacion: {puntaje}")
    esperado = puntaje[0] == 1 and puntaje[1] == 2
    print(f"  {'OK: encuentra la linea GANADORA de 2 premios' if esperado else 'FALLO'}")
    return 0 if esperado else 1


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--hallazgo", default=None)
    ap.add_argument("--indice", type=int, default=0)
    ap.add_argument("--autopsia", default=None,
                    help="directorio de hallazgos de utils/autopsia.py")
    ap.add_argument("--max", type=int, default=10,
                    help="con --autopsia: numero maximo de hallazgos")
    args = ap.parse_args(argv)

    if args.demo:
        return demo_combo_myriad()
    if args.hallazgo:
        comparar_hallazgo(args.hallazgo, args.indice)
        return 0
    if args.autopsia:
        rutas = sorted(Path(args.autopsia).glob("*.json"))[:args.max]
        for ruta in rutas:
            comparar_hallazgo(ruta)
            print()
        return 0
    print("indica --demo, --hallazgo o --autopsia")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
