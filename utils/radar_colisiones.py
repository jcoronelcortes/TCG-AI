"""Radar de COLISIONES entre reglas de matchup.

La matriz de matchups (fase 8) dice QUE matchup va peor; la autopsia (fase 6)
dice que se perdio una partida. Ninguna de las dos encuentra la clase de fallo
que dio el mayor salto medido del proyecto (+5.4 en cornerstone_cubchoo): un
veto de UN matchup que mata la jugada que otro matchup EXIGE. Los mazos meta son
mixtos (Cornerstone+Cubchoo, Crustle+Kangaskhan...), asi que dos banderas
`op_is_*_deck` conviven y sus reglas se pisan.

Como se encontro aquella: comparando el MISMO escenario en dos matchups
hermanos. Contra Crustle, "muro delante + atacante listo en banca + retirada
legal" se resolvia subiendo al atacante el 82-100% de las veces; contra
Cornerstone+Cubchoo, el 13.7%. Esa asimetria ES el bug.

Esta pieza generaliza ese metodo: define SITUACIONES canonicas y deck-agnosticas
que se leen de la observacion (sin tocar main.py) y mide, por mazo rival, con
que frecuencia las RESOLVEMOS. Una tasa de resolucion que se hunde en un mazo y
no en los demas es un candidato a colision, y el mazo donde se hunde dice que
bandera mirar.

Lo que NO hace: decidir si es un bug. Solo senala donde mirar; la confirmacion
sigue siendo capturar el menu y trazar el score (`sys.settrace` sobre `agent`,
filtrando cambios de `frame.f_locals['score']`).

Uso:
    python utils/radar_colisiones.py --partidas 100
    python utils/radar_colisiones.py --partidas 200 --solo cornerstone_cubchoo,crustle_kangaskhan
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
import autopsia as au
from cg.api import OptionType


def _act(jugador):
    a = jugador.get("active") or []
    return a[0] if a and a[0] else None


def _tipos_del_menu(obs):
    return {o.get("type") for o in obs["select"]["option"]}


# --------------------------------------------------------------------------
# SITUACIONES. Cada una recibe los menus de UN turno nuestro y devuelve
# (aplica, resuelta). Se leen de la observacion: nada de internals de main.py,
# para que el radar no herede los mismos sesgos que esta auditando.
# --------------------------------------------------------------------------

def _s_pivote_al_muro(m, menus):
    """El activo NO puede danar al activo rival (inmunidad) y en la banca hay un
    cuerpo que SI puede y esta cargado. Resuelta = el turno acaba con un cuerpo
    que si dana en el activo."""
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
        relevo = any(
            b and _pega_al_muro(m, b, ex_imm, ab_imm)
            and m._can_attack_eff(b["id"], len(b["energies"]))
            and _amenaza_real(m, b, oact, yo)
            for b in (yo.get("bench") or []))
        if relevo and int(OptionType.RETREAT) in _tipos_del_menu(d["obs"]):
            aplica = True
            break
    if not aplica:
        return False, False
    # Resuelta = en ALGUN momento del turno el relevo llega al activo (o ataca
    # desde el). Mirar solo el ultimo menu no basta: si el relevo noquea al muro,
    # el rival promueve y el estado final ya no describe la jugada.
    for d in menus:
        cur = d["obs"]["current"]
        yo = cur["players"][cur["yourIndex"]]
        op = cur["players"][1 - cur["yourIndex"]]
        act, oact = _act(yo), _act(op)
        if act is None or oact is None:
            continue
        ex_imm = oact["id"] in m.EX_IMMUNE_IDS
        ab_imm = oact["id"] in m.ABILITY_IMMUNE_IDS
        if _pega_al_muro(m, act, ex_imm, ab_imm):
            return True, True
    return True, False


class _P:
    """Adaptador minimo dict -> objeto para las calculadoras de main (mismo
    patron que `autopsia._dano_letal_activo`)."""

    def __init__(self, d):
        self.id = d["id"]
        self.hp = d.get("hp")
        self.energies = list(d.get("energies") or [])

        class _C:
            def __init__(self, dd):
                self.id = dd["id"]

        self.energyCards = [_C(c) for c in (d.get("energyCards") or [])]
        self.tools = [_C(c) for c in (d.get("tools") or [])]


def _amenaza_real(m, relevo, muro, yo, umbral=0.25):
    """¿El relevo amenaza al muro de verdad, o solo lo gotea?

    Un pivote cuesta el turno y la energia de retirada: solo compensa si el
    cuerpo que sube muerde. Sin este filtro el radar contaba como "deberiamos
    pivotar" los turnos cuyo unico relevo era un Dipplin (20 x banca) frente a
    un muro de 170-210 PV -- el agente hacia bien en declinar, y la tasa de
    resolucion se hundia sin que hubiera fallo (crustle salia al 55% y el 96.8%
    de los casos "no resueltos" tenian Dipplin como unico relevo). Es la misma
    trampa que ya obligo a filtrar por `MAIN_ATTACKERS`, un nivel mas arriba.

    Umbral: quitar >= 25% de la vida ACTUAL del muro (reloj de 4 turnos o
    mejor).
    """
    cuerpos = [p for p in (yo.get("active") or []) + (yo.get("bench") or []) if p]
    total_grass = sum(len(p.get("energies") or []) for p in cuerpos)
    banca = sum(1 for b in (yo.get("bench") or []) if b)
    e = len(relevo.get("energies") or [])
    a, o = _P(relevo), _P(muro)
    try:
        base = m._attacker_base_damage(a.id, o, e, grass_scale=total_grass,
                                       teal_self_energy=e, bench_count=banca)
        meg = any(p["id"] == m.Meganium for p in cuerpos)
        dmg = m._our_effective_damage(a, o, base, meg, False)
    except Exception:
        return True          # ante la duda, no filtrar: mejor falso positivo
    return dmg >= umbral * max(1, muro.get("hp") or 1)


def _pega_al_muro(m, pk, ex_imm, ab_imm):
    """¿Este cuerpo es un relevo REAL contra el muro?

    Se exige `MAIN_ATTACKERS` -- la lista CURADA de cuerpos con los que de
    verdad atacamos --, no cualquier carta con ataque. Sin ese filtro, un Applin
    con 1 energia (20 de dano a un muro de 210) contaba como relevo valido: la
    situacion disparaba constantemente, el agente hacia bien en ignorarla y la
    tasa de resolucion se hundia sin que hubiera ningun fallo. Ese sesgo hacia
    el radar INSENSIBLE al fix que se uso para validarlo (1.9% -> 1.1%, sin
    moverse, cuando el fix vale +5.4 puntos medidos).
    """
    if pk["id"] not in m.MAIN_ATTACKERS:
        return False
    if ex_imm and pk["id"] in m.OUR_EX_IDS:
        return False
    if ab_imm and pk["id"] in m.OUR_ABILITY_IDS:
        return False
    return True


def _s_supporter_sin_jugar(m, menus):
    """Hueco de Supporter libre y al menos uno en mano. Resuelta = se juega."""
    cur0 = menus[0]["obs"]["current"]
    yo0 = cur0["players"][cur0["yourIndex"]]
    if cur0["supporterPlayed"]:
        return False, False
    if not any(h["id"] in m._SUPP_PLAY_IDS for h in (yo0.get("hand") or [])):
        return False, False
    ult = menus[-1]["obs"]["current"]
    return True, bool(ult["supporterPlayed"])


def _s_energia_sin_adjuntar(m, menus):
    """Adjunte del turno libre y Planta en mano. Resuelta = se pone en el campo
    (por adjunte manual o por habilidad de carga)."""
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


def _s_turno_no_esteril(m, menus):
    """El menu ofrecia jugadas que NO son END. Resuelta = hacemos alguna."""
    hubo_opcion = any(t not in (int(OptionType.END),) for d in menus
                      for t in _tipos_del_menu(d["obs"]))
    if not hubo_opcion:
        return False, False
    hizo = any(d["obs"]["select"]["option"][d["eleccion"][0]].get("type")
               != int(OptionType.END)
               for d in menus if d["eleccion"])
    return True, hizo


def _s_remata_si_puede(m, menus):
    """El ACTIVO noquea al activo rival ESTE turno. Resuelta = atacamos.

    Es la jugada mas basica que existe, asi que su tasa tiene que salir alta en
    TODOS los mazos: si sale baja en todos, el detector esta mal (no el agente).
    Sirve de control de cordura del propio radar."""
    aplica = False
    for d in menus:
        cur = d["obs"]["current"]
        yo = cur["players"][cur["yourIndex"]]
        op = cur["players"][1 - cur["yourIndex"]]
        a, o = _act(yo), _act(op)
        if a is None or o is None:
            continue
        if int(OptionType.ATTACK) not in _tipos_del_menu(d["obs"]):
            continue
        if not m._can_attack_eff(a["id"], len(a["energies"])):
            continue
        if _dano(m, a, o, yo) >= (o.get("hp") or 10 ** 6):
            aplica = True
            break
    if not aplica:
        return False, False
    ataco = any(d["obs"]["select"]["option"][d["eleccion"][0]].get("type")
                == int(OptionType.ATTACK)
                for d in menus if d["eleccion"])
    return True, ataco


def _s_evoluciona_si_puede(m, menus):
    """Evolucion en mano con su pre-evo EN JUEGO y LEGALMENTE evolucionable.
    Resuelta = la evolucion acaba en el campo.

    El filtro `appearThisTurn` no es cosmetico: una pre-evo bajada este mismo
    turno NO puede evolucionar (salvo con Forest of Vitality en juego, que lo
    permite). Sin ese filtro la situacion disparaba constantemente sobre
    jugadas ILEGALES y la tasa salia al 40-58% en TODOS los mazos -- el sintoma
    de un detector roto, no de un agente que se despista."""
    cur0 = menus[0]["obs"]["current"]
    yo0 = cur0["players"][cur0["yourIndex"]]
    forest = any(s.get("id") == m.Forest_of_Vitality
                 for s in (cur0.get("stadium") or []))
    en_juego = {p["id"] for p in
                (yo0.get("active") or []) + (yo0.get("bench") or [])
                if p and (forest or not p.get("appearThisTurn"))}
    mano = {h["id"] for h in (yo0.get("hand") or [])}
    objetivo = set()
    for linea in m.EVO_LINES:
        for pre, evo in zip(linea, linea[1:]):
            if evo in mano and pre in en_juego and evo not in en_juego:
                objetivo.add(evo)
    if not objetivo:
        return False, False
    ult = menus[-1]["obs"]["current"]
    yo_f = ult["players"][ult["yourIndex"]]
    final = {p["id"] for p in
             (yo_f.get("active") or []) + (yo_f.get("bench") or []) if p}
    return True, bool(objetivo & final)


def _dano(m, atacante, objetivo, yo):
    cuerpos = [p for p in (yo.get("active") or []) + (yo.get("bench") or []) if p]
    e = len(atacante.get("energies") or [])
    a, o = _P(atacante), _P(objetivo)
    try:
        base = m._attacker_base_damage(
            a.id, o, e, grass_scale=sum(len(p.get("energies") or [])
                                        for p in cuerpos),
            teal_self_energy=e,
            bench_count=sum(1 for b in (yo.get("bench") or []) if b))
        meg = any(p["id"] == m.Meganium for p in cuerpos)
        return m._our_effective_damage(a, o, base, meg, False)
    except Exception:
        return 0


# `_s_evoluciona_si_puede` NO se envia: medida en 3 mazos da 33-61% -- baja en
# TODOS --, incluso tras filtrar las pre-evos que aparecieron este turno (que no
# pueden evolucionar sin Forest). Evolucionar es genuinamente DISCRECIONAL: el
# agente declina con razon a menudo (conservar un Dipplin de 1 premio, no
# construir una Etapa 2 ex contra un muro que la inmuniza...). Una situacion
# cuya tasa es baja en todos los mazos no distingue politica de fallo: solo
# aporta ruido y falsos positivos. Se conserva la funcion por si alguien la
# afina, pero fuera de la tabla.
SITUACIONES = (
    ("pivote_al_muro", _s_pivote_al_muro),
    # CONTROL DE CORDURA, no detector: sale 100% en todos los mazos medidos
    # (cuando el activo noquea, atacamos siempre). Su valor es ser el canario
    # de la aritmetica de dano del propio radar -- si algun dia baja del 100%,
    # o se rompio el agente o se rompio `_dano`.
    ("remata_si_puede", _s_remata_si_puede),
    ("juega_supporter", _s_supporter_sin_jugar),
    ("pone_energia", _s_energia_sin_adjuntar),
    ("turno_productivo", _s_turno_no_esteril),
)


def radar(agente, deck_rival, partidas):
    from bot_rival import BotRival
    cnt = collections.defaultdict(lambda: [0, 0])   # nombre -> [aplica, resuelta]
    for i in range(partidas):
        _res, dec, _fin = au.jugar_grabando(
            agente, BotRival(), agente.my_deck, deck_rival, i % 2)
        turnos = collections.defaultdict(list)
        for d in dec:
            turnos[d["obs"]["current"]["turn"]].append(d)
        for _t, menus in turnos.items():
            if not menus:
                continue
            for nombre, fn in SITUACIONES:
                try:
                    aplica, resuelta = fn(agente, menus)
                except Exception:
                    continue
                if aplica:
                    cnt[nombre][0] += 1
                    cnt[nombre][1] += int(resuelta)
    return cnt


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partidas", type=int, default=100)
    ap.add_argument("--candidato", default="main.py")
    ap.add_argument("--solo", default=None,
                    help="lista de mazos separada por comas")
    args = ap.parse_args(argv)

    agente = sp.cargar_agente(_ROOT / args.candidato, "agente_radar")
    mazos = sorted((_ROOT / "deck" / "rivales").glob("*.csv"))
    if args.solo:
        querer = {s.strip() for s in args.solo.split(",")}
        mazos = [p for p in mazos if p.stem in querer]

    filas = {}
    for ruta in mazos:
        deck = sp.leer_deck(ruta)
        filas[ruta.stem] = radar(agente, deck, args.partidas)
        print(f"  {ruta.stem}: hecho", flush=True)

    nombres = [n for n, _ in SITUACIONES]
    ancho = max(len(k) for k in filas) if filas else 10
    print(f"\n=== RADAR DE COLISIONES (n={args.partidas}/mazo) ===")
    print("tasa de RESOLUCION por situacion; (n) = veces que la situacion aplica")
    print(f"{'mazo':<{ancho}} " + "  ".join(f"{n:>18}" for n in nombres))
    for mazo, cnt in sorted(filas.items()):
        celdas = []
        for n in nombres:
            ap_, ok = cnt[n]
            celdas.append(f"{100*ok/ap_:5.1f}% (n={ap_:4d})" if ap_ else
                          f"{'-':>18}")
        print(f"{mazo:<{ancho}} " + "  ".join(f"{c:>18}" for c in celdas))

    # Senala outliers: una situacion que en un mazo se resuelve mucho peor que
    # la MEDIANA del resto es candidata a colision.
    print("\n--- candidatos (resolucion muy por debajo de la mediana) ---")
    hubo = False
    for n in nombres:
        tasas = {mz: (c[n][1] / c[n][0]) for mz, c in filas.items()
                 if c[n][0] >= 10}
        if len(tasas) < 3:
            continue
        orden = sorted(tasas.values())
        mediana = orden[len(orden) // 2]
        for mz, t in sorted(tasas.items(), key=lambda x: x[1]):
            if t < mediana - 0.25:
                hubo = True
                print(f"  {n:<18} {mz:<22} {100*t:5.1f}%  "
                      f"(mediana {100*mediana:5.1f}%)")
    if not hubo:
        print("  ninguno: todas las situaciones se resuelven de forma "
              "homogenea entre mazos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
