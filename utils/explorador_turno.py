"""Explorador exhaustivo de TURNO: encuentra la mejor linea de nuestras
acciones y la compara con la que elige el agente.

Fase 7 de la arquitectura de mejora de estrategia. Generaliza los "walkers"
de los tests (combo Myriad, pivote Ogerpon): dado un estado (observacion),
enumera TODAS las secuencias legales de nuestras acciones en el turno con un
modelo de transiciones propio, evalua el estado final de cada una y devuelve
la linea dominante. Si la linea del agente queda dominada, ahi hay un
escenario nuevo con la jugada correcta ya calculada.

LIMITES del modelo (v1, documentados a proposito):
  - Solo NUESTRO turno (la informacion oculta del rival impide bifurcar el
    simulador real). Sin robos: el robo de Teal Dance / los refrescos de mano
    (Lillie's) no se modelan porque su resultado es azar.
  - Acciones modeladas: adjunte manual, Teal Dance, Ripening Charge, retirada
    +promocion, evolucion, Night Stretcher (recuperar Planta), Boss's Orders
    (gusteo), Forest of Vitality, ataque del ACTIVO (via las calculadoras del
    propio main) y fin de turno.
  - El dano usa main._attacker_base_damage/_our_effective_damage: exacto para
    nuestros atacantes principales; los ataques de chip no modelados valen 0.

Evaluacion (lexicografica): ganar > premios tomados > dano infligido >
energia adjuntada + cuerpos bajados + evoluciones. Un turno esteril pierde
contra cualquier linea que desarrolle.

Uso:
    python utils/explorador_turno.py --demo                # combo Myriad
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
# Utilidades de estado (sobre el dict de observacion, como los walkers)
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
    """Firma del estado para deduplicar transposiciones."""
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
    """Adaptador dict->objeto para las calculadoras de main."""

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
    """Las habilidades de nuestros Pokemon EX estan anuladas (paso 6 plan jul
    2026): Iron Thorns ex en el ACTIVO rival (Initialization) o Team Rocket's
    Watchtower como estadio. Sin esto el explorador proponia lineas ilegales
    (TEAL DANCE x3 contra Iron Thorns ex activo, hallazgo p029) y contaminaba
    el juicio de las autopsias justo en el matchup mas debil."""
    op = _op(obs)
    act = (op.get("active") or [None])[0]
    if act and act.get("id") == m.Iron_Thorns_ex:
        return True
    return any(s["id"] == m.Team_Rockets_Watchtower
               for s in (obs["current"].get("stadium") or []))


def _dano_activo(obs):
    """(dano_efectivo, objetivo_dict) del ataque de nuestro activo."""
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
# Enumeracion y aplicacion de acciones. Una accion es (etiqueta, aplicar)
# donde aplicar(obs) -> obs nuevo (deepcopy) o None si es terminal.
# --------------------------------------------------------------------------

def _quitar_de_mano(yo, card_id):
    i = next(i for i, c in enumerate(yo["hand"]) if c["id"] == card_id)
    carta = yo["hand"][i]
    yo["hand"] = [c for j, c in enumerate(yo["hand"]) if j != i]
    yo["handCount"] = len(yo["hand"])
    return carta


def _adjunta(p, carta):
    p["energies"] = list(p.get("energies") or []) + [1]
    p["energyCards"] = list(p.get("energyCards") or []) + [carta]


def _slots(yo):
    out = []
    if yo.get("active") and yo["active"][0]:
        out.append(("activo", yo["active"][0]))
    for k, bp in enumerate(yo.get("bench") or []):
        if bp:
            out.append((f"banca{k}", bp))
    return out


def _menu_real(obs):
    """(tipos, play_ids) del menu REAL del simulador en el nodo RAIZ, o
    (None, None) si no aplica (paso 6b plan jul 2026). Solo se consulta con
    `_respetar_menu` (hallazgos de autopsia: su primer select MAIN trae el
    menu completo y ya refleja locks de habilidad, bloqueos de item -- Budew
    --, retiradas imposibles, etc.); los escenarios SINTETICOS (--demo,
    StateBuilder) construyen menus parciales a proposito y no se filtran.
    Los nodos SIMULADOS (tras la primera transicion) tampoco: ahi el menu
    grabado ya no describe el estado."""
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

    # Filtro de legalidad por el menu real (solo nodo raiz de hallazgos).
    _tipos_menu, _play_ids_menu = _menu_real(obs)

    def _permitido(tipo):
        return _tipos_menu is None or int(tipo) in _tipos_menu

    def _play_ok(cid):
        return _play_ids_menu is None or cid in _play_ids_menu

    # adjunte manual
    if (grass_en_mano and not cur.get("energyAttached")
            and _permitido(OptionType.ATTACH)):
        for nombre, p in _slots(yo):
            def ap(obs, _n=nombre):
                o2 = copy.deepcopy(obs)
                y2 = _yo(o2)
                carta = _quitar_de_mano(y2, m.Basic_Grass_Energy)
                tgt = dict(_slots(y2))[_n]
                _adjunta(tgt, carta)
                o2["current"]["energyAttached"] = True
                return o2
            acciones.append((f"ATTACH->{m.card_table[p['id']].name}", ap))

    # Teal Dance (una por Ogerpon por turno; el robo no se modela).
    # Habilidad de un EX: anulada bajo _lock_habilidades_ex.
    if (grass_en_mano and not _lock_habilidades_ex(obs)
            and _permitido(OptionType.ABILITY)):
        for nombre, p in _slots(yo):
            if (p["id"] == m.Teal_Mask_Ogerpon_ex
                    and p["serial"] not in obs.get("_td_usadas", ())):
                def ap(obs, _n=nombre, _s=p["serial"]):
                    o2 = copy.deepcopy(obs)
                    y2 = _yo(o2)
                    carta = _quitar_de_mano(y2, m.Basic_Grass_Energy)
                    _adjunta(dict(_slots(y2))[_n], carta)
                    o2["_td_usadas"] = tuple(obs.get("_td_usadas", ())) + (_s,)
                    return o2
                acciones.append(("TEAL DANCE", ap))

    # Ripening Charge (Hydrapple ex: adjunta 1 Planta de la mano a cualquiera).
    # Habilidad de un EX: anulada bajo _lock_habilidades_ex.
    if (grass_en_mano and not _lock_habilidades_ex(obs)
            and _permitido(OptionType.ABILITY)):
        for _, hyd in _slots(yo):
            if (hyd["id"] == m.Hydrapple_ex
                    and hyd["serial"] not in obs.get("_rc_usadas", ())):
                for nombre, p in _slots(yo):
                    def ap(obs, _n=nombre, _s=hyd["serial"]):
                        o2 = copy.deepcopy(obs)
                        y2 = _yo(o2)
                        carta = _quitar_de_mano(y2, m.Basic_Grass_Energy)
                        _adjunta(dict(_slots(y2))[_n], carta)
                        o2["_rc_usadas"] = tuple(
                            obs.get("_rc_usadas", ())) + (_s,)
                        return o2
                    acciones.append(
                        (f"RIPENING->{m.card_table[p['id']].name}", ap))
                break

    # evolucion (mano -> pre-evo en juego; Forest permite el mismo turno)
    for cid in set(mano_ids) if _permitido(OptionType.EVOLVE) else ():
        data = m.card_table.get(cid)
        if not data or not (data.stage1 or data.stage2):
            continue
        for nombre, p in _slots(yo):
            pdata = m.card_table.get(p["id"])
            if not pdata or data.evolvesFrom != pdata.name:
                continue
            if p.get("appearThisTurn") and not forest:
                continue
            def ap(obs, _cid=cid, _n=nombre):
                o2 = copy.deepcopy(obs)
                y2 = _yo(o2)
                carta = _quitar_de_mano(y2, _cid)
                tgt = dict(_slots(y2))[_n]
                previo = {k: tgt[k] for k in tgt}
                tgt["preEvolution"] = (list(tgt.get("preEvolution") or [])
                                       + [{"id": previo["id"],
                                           "playerIndex": carta["playerIndex"],
                                           "serial": previo["serial"]}])
                dano_actual = (previo.get("maxHp") or 0) - (previo.get("hp") or 0)
                nueva = m.card_table[_cid]
                tgt["id"] = _cid
                tgt["serial"] = carta["serial"]
                tgt["maxHp"] = nueva.hp
                tgt["hp"] = max(1, nueva.hp - dano_actual)
                tgt["appearThisTurn"] = True
                o2["_evoluciones"] = obs.get("_evoluciones", 0) + 1
                return o2
            acciones.append(
                (f"EVOLVE {data.name}<-{pdata.name}", ap))

    # retirada + promocion (coste en energias efectivas, v1)
    act = yo["active"][0] if yo.get("active") and yo["active"][0] else None
    if (act is not None and not cur.get("retreated")
            and _permitido(OptionType.RETREAT)):
        coste = m.card_table[act["id"]].retreatCost
        if len(act.get("energies") or []) >= coste:
            for k, bp in enumerate(yo.get("bench") or []):
                if not bp:
                    continue
                def ap(obs, _k=k, _coste=coste):
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

    # Night Stretcher: recuperar una Planta del descarte (v1: solo energia)
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
            carta = y2["discard"][i]
            y2["discard"] = [c for j, c in enumerate(y2["discard"]) if j != i]
            y2["hand"] = list(y2["hand"]) + [carta]
            y2["handCount"] = len(y2["hand"])
            return o2
        acciones.append(("NS->PLANTA", ap))

    # Boss's Orders: subir un objetivo de la banca rival
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
            carta = _quitar_de_mano(y2, m.Forest_of_Vitality)
            o2["current"]["stadium"] = [carta]
            o2["current"]["stadiumPlayed"] = True
            return o2
        acciones.append(("FOREST", ap))

    # ataque del activo (terminal). En el nodo raiz el menu real manda: si el
    # simulador no ofrecio ATTACK (energia insuficiente, condicion), el
    # modelo no lo inventa; tras cualquier transicion vuelve a decidir el
    # modelo (un adjunte simulado puede habilitar el ataque).
    dano, opa = _dano_activo(obs)
    if dano > 0 and _permitido(OptionType.ATTACK):
        acciones.append(("ATTACK", None))
    acciones.append(("END", None))
    return acciones


def evaluar_terminal(obs, ataca):
    """Tupla lexicografica: (gana, premios, dano, desarrollo)."""
    yo = _yo(obs)
    premios, dano = 0, 0
    gana = False
    if ataca:
        dano, opa = _dano_activo(obs)
        if opa is not None and dano >= (opa.get("hp") or 0) > 0:
            premios = m.prize_count(_P(opa))
            faltan = sum(1 for p in (yo.get("prize") or []) if p is None)
            gana = premios >= faltan
            dano = opa["hp"]
    energia = sum(len(p.get("energies") or []) for p in _pokes(yo))
    desarrollo = (len(_pokes(yo)) * 10 + energia
                  + obs.get("_evoluciones", 0) * 5)
    return (int(gana), premios, dano, desarrollo)


def explorar(obs, max_nodos=MAX_NODOS, respetar_menu=False):
    """Devuelve (mejor_puntaje, mejor_linea) explorando el turno completo.

    Con `respetar_menu` (paso 6b), el nodo RAIZ solo genera acciones cuyo
    tipo aparece en el menu real de la observacion (ver _menu_real): para
    hallazgos de autopsia, donde el menu del simulador ya refleja locks y
    bloqueos que el modelo v1 no conoce. Los escenarios sinteticos (--demo)
    no lo activan: sus menus son parciales a proposito."""
    inicial = copy.deepcopy(obs)
    inicial.setdefault("_evoluciones", 0)
    if respetar_menu:
        inicial["_respetar_menu"] = True
    mejor = [None, None]
    vistos = set()
    nodos = [0]

    def dfs(estado, linea):
        if nodos[0] >= max_nodos:
            return
        nodos[0] += 1
        for etiqueta, aplicar in acciones_legales(estado):
            if aplicar is None:  # terminal: ATTACK o END
                p = evaluar_terminal(estado, etiqueta == "ATTACK")
                if mejor[0] is None or p > mejor[0]:
                    mejor[0], mejor[1] = p, linea + [etiqueta]
                continue
            sig = estado_sig = None
            nuevo = aplicar(estado)
            # Tras la primera transicion el estado es SIMULADO: el menu
            # grabado ya no lo describe y la legalidad vuelve al modelo.
            nuevo["_simulado"] = True
            estado_sig = _firma(nuevo)
            if estado_sig in vistos:
                continue
            vistos.add(estado_sig)
            dfs(nuevo, linea + [etiqueta])

    dfs(inicial, [])
    return mejor[0], mejor[1], nodos[0]


def comparar_hallazgo(ruta, indice=0, max_nodos=MAX_NODOS):
    data = json.loads(Path(ruta).read_text())
    h = data["hallazgos"][indice]
    obs = h["observation"]
    # Hallazgo real de autopsia: el menu del simulador manda en el nodo raiz.
    puntaje, linea, nodos = explorar(obs, max_nodos, respetar_menu=True)
    print(f"{Path(ruta).name} [{h['detector']} turno {h['turno']}]")
    print(f"  agente en la partida: {h['detalle']}")
    print(f"  mejor linea del explorador ({nodos} nodos): "
          f"{' -> '.join(linea)}")
    print(f"  evaluacion (gana, premios, dano, desarrollo): {puntaje}")
    return puntaje, linea


def demo_combo_myriad():
    """El explorador debe redescubrir el combo del registro_012 paso 227."""
    from state_builder import Escenario, pk, G
    import golden_corpus as gc
    gc.reset_agente(m)
    obs = (Escenario(turno=12, paso=227, tac=1, premios_propios=2)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G] * 4, fisicas=4))
           .mi_banca(pk(m.Applin))
           .mi_mano(m.Basic_Grass_Energy, m.Boss_Orders)
           .op_activo(pk(271, hp=120, max_hp=120))          # Kilowattrel
           .op_banca(pk(269, hp=280, max_hp=280,
                        energias=[G, G, G, G]))             # Bellibolt ex
           .op_zonas(mano=5, mazo=30, premios=3)
           .menu_teal_dance()
           .construir())
    puntaje, linea, nodos = explorar(obs)
    print("demo combo Myriad (registro_012 paso 227):")
    print(f"  mejor linea ({nodos} nodos): {' -> '.join(linea)}")
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
