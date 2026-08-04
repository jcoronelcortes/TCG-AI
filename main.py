

import os
import sys
from collections import defaultdict
from dataclasses import dataclass, replace as _dc_replace
from math import comb as _comb
from typing import NamedTuple

from cg.api import AreaType, CardType, EnergyType, Observation, SelectContext, OptionType, Card, Pokemon, SpecialConditionType, LogType, all_card_data, all_attack, to_observation_class

# Constantes de carta (IDs, grupos y tablas). Extraidas en la Ola 1 del
# refactor; ver docs/main-refactor-arquitectura.md. Va ARRIBA a proposito:
# en el contenedor de Kaggle el directorio del agente solo esta en sys.path
# mientras se ejecuta este modulo, asi que un import diferido no resolveria.
from ptcg.estado.agente import ESTADO, EstadoAgente  # noqa: F401
from ptcg.cartas.costes import ATTACK_ENERGY_REQ_BASE  # noqa: F401
from ptcg.cartas.grupos import *  # noqa: F401,F403
from ptcg.cartas.ids import *  # noqa: F401,F403
from ptcg.cartas.lineas import *  # noqa: F401,F403
from ptcg.cartas.tablas import *  # noqa: F401,F403
from ptcg.motor.contexto import *  # noqa: F401,F403
from ptcg.motor.plan import *  # noqa: F401,F403
from ptcg.motor.reglas import *  # noqa: F401,F403
from ptcg.estado.claves import *  # noqa: F401,F403
from ptcg.estado.logs import *  # noqa: F401,F403
from ptcg.estado.tracking import *  # noqa: F401,F403
from ptcg.calculo.carta import *  # noqa: F401,F403
from ptcg.calculo.dano import *  # noqa: F401,F403
from ptcg.calculo.energia import *  # noqa: F401,F403
from ptcg.calculo.planta import *  # noqa: F401,F403
from ptcg.calculo.probabilidad import *  # noqa: F401,F403
from ptcg.calculo.rival import *  # noqa: F401,F403
from ptcg.calculo.tablero import *  # noqa: F401,F403
from ptcg.decision.boss_orders import *  # noqa: F401,F403
from ptcg.decision.bug_catching_set import *  # noqa: F401,F403
from ptcg.decision.disrupcion import *  # noqa: F401,F403
from ptcg.decision.estadios import *  # noqa: F401,F403
from ptcg.decision.meowth import *  # noqa: F401,F403
from ptcg.decision.night_stretcher import *  # noqa: F401,F403
from ptcg.decision.poke_pad import *  # noqa: F401,F403
from ptcg.decision.supporters import *  # noqa: F401,F403
from ptcg.decision.ultra_ball import *  # noqa: F401,F403
from ptcg.cartas.puntuacion import *  # noqa: F401,F403
from ptcg.motor.depuracion import *  # noqa: F401,F403
from ptcg.turno.ctx import TurnoCtx  # noqa: F401
from ptcg.turno.finalize import finalizar  # noqa: F401
from ptcg.turno.ctx_puntuacion import PuntuacionCtx  # noqa: F401
from ptcg.turno.puntuacion import puntuar_opcion, _SALTAR  # noqa: F401
from ptcg.turno.supporters import evaluate_supporters as _evaluate_supporters_impl  # noqa: F401
from ptcg.turno.supporters_ctx import CtxEvaluateSupporters  # noqa: F401
from ptcg.turno.energia import _energy_score_base as _energy_score_base_impl  # noqa: F401
from ptcg.turno.energia_ctx import CtxEnergyScoreBase  # noqa: F401

# =============================================================================
# Puente de compatibilidad: `main.<campo de estado>` <-> `ESTADO.<campo>`
# -----------------------------------------------------------------------------
# El estado que persiste entre turnos vive en `ESTADO` (ptcg/estado/agente.py),
# pero la suite lo fija y lo lee como atributo de `main` en ~1.285 sitios. Sin
# este puente esas escrituras irian a un atributo muerto: los tests SEGUIRIAN
# PASANDO mientras el agente lee un estado que nadie actualiza -- justo el fallo
# silencioso que la Ola 3 existe para eliminar.
#
# Reescribir la suite a la vez que se cambia lo que la suite vigila es la peor
# forma de hacer este paso. El puente permite migrar el estado con el arnes
# intacto; retirarlo (y actualizar los tests) es una limpieza posterior, con el
# refactor ya verde.
#
# En el contenedor de Kaggle NO se instala: alli main.py se ejecuta con exec()
# sobre un dict vacio, asi que no hay objeto-modulo y `__name__` ni existe. La
# submission corre el camino puro `ESTADO.x`, que es el que prueba
# tests/test_submission.py (carga con el cargador real, no con `import`).
# =============================================================================
_ESTADO_CAMPOS = frozenset(vars(EstadoAgente()))
_mod = sys.modules.get(globals().get('__name__') or '')
if _mod is not None:
    class _MainConEstado(type(_mod)):
        def __getattr__(self, nombre):
            if nombre in _ESTADO_CAMPOS:
                return getattr(ESTADO, nombre)
            raise AttributeError(nombre)

        def __setattr__(self, nombre, valor):
            if nombre in _ESTADO_CAMPOS:
                setattr(ESTADO, nombre, valor)
            else:
                super().__setattr__(nombre, valor)

    _mod.__class__ = _MainConEstado


# =============================================================================
# CONVENCIONES DEL AGENTE (leer antes de tocar puntuaciones o energia)
# -----------------------------------------------------------------------------
# ENERGIA:
#   * `len(pokemon.energies)` YA es la energia EFECTIVA. La observacion aplica
#     Wild Growth de Meganium duplicando cada energia basica de Planta FISICA,
#     asi que NUNCA hay que volver a multiplicar por 2. Por eso `_grass_mult()`
#     devuelve 1. Comparar `len(energies)` directamente con ATTACK_ENERGY_REQ.
#   * `_grass_attach_unit()` = energia EFECTIVA que aporta adjuntar UNA Planta
#     basica: 2 si Meganium esta en juego, 1 si no.
#   * Las energias del RIVAL en nuestra observacion NO estan dobladas.
#
# PUNTUACION:
#   * `agent(obs)` puntua cada opcion; se juega la de mayor valor.
#   * Requisitos de energia para atacar: ATTACK_ENERGY_REQ (fuente unica).
#   * Dano base de nuestros atacantes: _attacker_base_damage(...) (fuente unica).
#     Debilidad/resistencia/inmunidad se aplican aparte en _our_effective_damage.
#
# TIPOS DE OPCION (OptionType, valores numericos en el log):
#   7 = PLAY (jugar carta de la mano)   13 = ATTACK
#   12 = PASS                           14 = END TURN        3 = seleccion objetivo
# =============================================================================


file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r") as file:
    csv = file.read().split("\n")
my_deck = []
for i in range(60):
    my_deck.append(int(csv[i]))

















try:
    _ID_AUDIT_MISMATCHES = _validate_id_constants()
except Exception:
    _ID_AUDIT_MISMATCHES = []







# =============================================================================
# MOTOR DE REGLAS (fase 4): reglas con NOMBRE y TRAZA.
#
# Problema que resuelve: el scoring inline entierra cada regla como un if con
# numeros magicos; cuando dos reglas colisionan (p.ej. un clamp que pisa un
# score alto), encontrar la culpable exige instrumentar a mano. Aqui cada
# regla es un objeto con nombre; el resolver deja una traza legible de que
# regla fijo el score y que ajustes lo transformaron (visible con PTCG_DEBUG).
#
# Semantica IDENTICA al codigo que reemplaza:
#   - _ReglaFija: cadena if/elif -> gana la PRIMERA cuyo `cuando` es True.
#   - _Ajuste: transformaciones secuenciales posteriores (clamps, topes).
# Bloques migrados: fetch de Ultra Ball (11 ramas), Night Stretcher (12),
# _score_boss_orders_play. Cero cambio de comportamiento en cada migracion
# (suite + corpus dorado + invariantes + self-play).
# =============================================================================






























# =============================================================================
# CADENAS EVOLUTIVAS DERIVADAS DEL MAZO (deck-agnostico)
# -----------------------------------------------------------------------------
# `EVO_LINES` esta escrita a mano para ESTE mazo. El motor de Grand Tree (ver
# `_gt_*`) tiene que funcionar con CUALQUIER deck.csv, asi que deriva las
# cadenas Basico -> Fase 1 -> Fase 2 leyendo `CardData.evolvesFrom` (que es el
# NOMBRE de la pre-evolucion, no un id) de las cartas que realmente estan en el
# mazo. Se calcula UNA vez al importar el modulo.
# =============================================================================

_CARD_NAME = {cid: (c.name or "") for cid, c in card_table.items()}

for _cbn in card_table.values():
    _CARD_BY_NAME.setdefault(_cbn.name or "", _cbn)










for _epn in card_table.values():
    _epn_pre = getattr(_epn, 'evolvesFrom', None)
    if _epn_pre:
        _EVOLUCIONES_POR_NOMBRE.setdefault(_epn_pre, []).append(_epn)








_EVO_POR_NOMBRE, _CADENAS_MAZO = _construir_cadenas_de_mazo(my_deck)

# Pokemon que REALMENTE estan en deck.csv. Sirve para distinguir "cuerpo que la
# configuracion curada (ATTACK_ENERGY_REQ / MAIN_ATTACKERS / topes por carta)
# conoce y excluye a proposito" de "cuerpo que simplemente no conoce". Lo
# primero debe seguir excluido; lo segundo puede resolverse con el dato de
# carta. Ver `_ns_umbral_energia_util`.
_DECK_POKEMON_IDS = frozenset(
    cid for cid in set(my_deck)
    if (card_table.get(cid) is not None
        and card_table[cid].cardType == CardType.POKEMON))

# Basicos del mazo que ABREN una cadena (tienen al menos una Fase 1 en el mazo).
_GT_BASICOS_CON_CADENA = frozenset(b for b, _s1, _s2 in _CADENAS_MAZO)










def _gt_planes(my_state, cartas_en_mazo, field_counts, our_first_turn,
               veta_etapa_ex=False, activo_condenado=False):
    """Todos los planes de Grand Tree EJECUTABLES ahora, de mejor a peor.

    Un plan es ejecutable si el Basico esta en juego, NO salio este turno
    (`appearThisTurn`), no estamos en nuestro primer turno, y su Fase 1 sigue
    en el mazo. La Fase 2 se anade solo si tambien queda en el mazo y el
    matchup no la desaconseja.
    """
    if our_first_turn:
        return []
    planes = []
    for area, idx, pkmn in _gt_slots_propios(my_state):
        if not isinstance(pkmn, Pokemon) or getattr(pkmn, 'appearThisTurn', False):
            continue
        data = card_table.get(pkmn.id)
        if data is None or not data.basic:
            continue
        energia = len(getattr(pkmn, 'energies', None) or [])
        for basico, s1, s2 in _CADENAS_MAZO:
            if basico != pkmn.id:
                continue
            if cartas_en_mazo.get(s1, {}).get(ESTADO_MAZO, 0) <= 0:
                continue
            s2_ok = bool(s2) and cartas_en_mazo.get(s2, {}).get(ESTADO_MAZO, 0) > 0
            if s2_ok and veta_etapa_ex:
                s2_data = card_table.get(s2)
                if s2_data is not None and (s2_data.ex or s2_data.megaEx):
                    s2_ok = False
            final = s2 if s2_ok else s1
            valor = _gt_valor_cuerpo(final) + energia
            if s2_ok:
                valor += GT_VALOR_ETAPA2
            if field_counts.get(final, 0) == 0:
                valor += GT_VALOR_DIVERSIFICAR
            if (activo_condenado and area == AreaType.ACTIVE
                    and _gt_premios_de(final) > _gt_premios_de(basico)):
                # El activo esta condenado: convertirlo en un cuerpo de MAS
                # premios antes de que lo noqueen regala la diferencia. No es
                # un veto (si es el unico plan, sigue valiendo la pena por los
                # PV), solo cede el turno a cualquier Basico de BANCA.
                valor -= GT_PENAL_ACTIVO_CONDENADO
            planes.append(_GrandTreePlan(
                area=area, index=idx, serial=getattr(pkmn, 'serial', -1),
                basic_id=basico, stage1_id=s1,
                stage2_id=(s2 if s2_ok else 0), valor=valor))
    planes.sort(key=lambda p: (-p.valor, int(p.area), p.index))
    return planes


def _gt_score_seleccion(o, card, plan, planes, my_state, field_counts):
    """Puntua UNA opcion de las sub-selecciones que abre la habilidad de Grand
    Tree (`select.effect.id == Grand_Tree`). El simulador las emite en llamadas
    posteriores a `agent()` y con contextos distintos segun el paso, asi que
    aqui no se discrimina por `context` sino por DONDE esta la carta:

      * area ACTIVE/BENCH -> "que Pokemon MIO evoluciona": manda el serial del
        plan; si no aparece (p.ej. el plan se recalculo tras el paso 1), se cae
        al ranking de planes y, en ultimo termino, a preferir un Basico con
        cadena disponible.
      * cualquier otra area (DECK / LOOKING) -> "que carta traigo": la Fase 2
        del plan primero, luego la Fase 1, y de fondo un criterio deck-agnostico
        (cualquier evolucion cuya pre-evolucion este en juego, valorada por
        `_gt_valor_cuerpo` y con bono si aun no tenemos ese cuerpo).

    Nunca devuelve un veto: estas selecciones suelen ser obligatorias una vez
    activada la habilidad, y quedarse sin opcion valida seria peor que elegir
    la menos mala.
    """
    cid = getattr(card, 'id', 0)

    if o.area in (AreaType.ACTIVE, AreaType.BENCH):
        serial = getattr(card, 'serial', None)
        for pos, p in enumerate(planes):
            if serial is not None and serial == p.serial:
                # El orden de `planes` YA es el orden de preferencia.
                return 10000 - pos
        data = card_table.get(cid)
        if data is not None and data.basic and cid in _GT_BASICOS_CON_CADENA:
            return 100
        return 1

    if plan is not None and plan.stage2_id and cid == plan.stage2_id:
        return 10000
    if plan is not None and cid == plan.stage1_id:
        return 9000

    data = card_table.get(cid)
    if data is not None and data.cardType == CardType.POKEMON:
        pre = getattr(data, 'evolvesFrom', None)
        if pre and any(_CARD_NAME.get(getattr(p, 'id', 0)) == pre
                       for _a, _i, p in _gt_slots_propios(my_state)):
            return (1000 + _gt_valor_cuerpo(cid)
                    + (500 if field_counts.get(cid, 0) == 0 else 0))
    return 1


def _gt_basicos_deseados(cartas_en_mazo, field_counts, veta_etapa_ex=False):
    """Basicos que, PUESTOS EN JUEGO, abren una cadena de Grand Tree para el
    proximo turno, ordenados por el valor del cuerpo al que llegan. Alimenta el
    fetch (mazo / descarte) y la bajada desde la mano."""
    ranking = {}
    for basico, s1, s2 in _CADENAS_MAZO:
        if cartas_en_mazo.get(s1, {}).get(ESTADO_MAZO, 0) <= 0:
            continue
        s2_ok = bool(s2) and cartas_en_mazo.get(s2, {}).get(ESTADO_MAZO, 0) > 0
        if s2_ok and veta_etapa_ex:
            s2_data = card_table.get(s2)
            if s2_data is not None and (s2_data.ex or s2_data.megaEx):
                s2_ok = False
        final = s2 if s2_ok else s1
        valor = _gt_valor_cuerpo(final) + (GT_VALOR_ETAPA2 if s2_ok else 0)
        if field_counts.get(final, 0) == 0:
            valor += GT_VALOR_DIVERSIFICAR
        if valor > ranking.get(basico, -1):
            ranking[basico] = valor
    return ranking














# Coste BASE, inmutable. `ATTACK_ENERGY_REQ` es la "fuente unica de verdad" que
# leen ~50 sitios, asi que el impuesto de Nighttime Mine se aplica ajustando ese
# diccionario UNA VEZ por llamada a agent() (ver `_aplicar_impuesto_tera`) en vez
# de tocar los 50 puntos de lectura. Se recalcula SIEMPRE desde esta base, de
# modo que el valor no se acumula entre llamadas ni entre partidas.



# Atacantes principales evaluados en los bloques de listo-para-atacar.
MAIN_ATTACKERS = (
    Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
    Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir,
)










# --- PESCA DE REMATE: el ataque que hoy solo depende del ROBO ---------------
# `_plan_de_planta` responde "cuantas Plantas NUEVAS de la MANO desbloquean un
# ataque hoy". Cuando esas Plantas NO estan en la mano sino en el MAZO y
# tenemos un refresco jugable (Lillie's roba 6/8), la pregunta correcta ya no
# es booleana sino PROBABILISTICA: ¿con que probabilidad el robo trae las
# cartas que faltan, y lo que desbloquean vale mas que el otro uso del hueco de
# Supporter? Estas dos piezas son la fuente unica de esa respuesta.









# =============================================================================
# VENTANA DEL KO: "Fuera de Combate DURANTE EL ULTIMO TURNO DE TU RIVAL"
# -----------------------------------------------------------------------------
# `ko_last_turn` no significa "perdimos un cuerpo": significa EXACTAMENTE la
# clausula que comparten Flip the Script (Fezandipiti ex) y Unfair Stamp --
# "si alguno de tus Pokemon quedo Fuera de Combate durante el ULTIMO TURNO DE TU
# RIVAL". Todos sus consumidores puntuan una de esas dos cartas.
#
# El detector viejo lo infiere de que el rival COBRO UN PREMIO (`op_prize` baja).
# Eso es un KO nuestro, si -- pero no dice CUANDO. Y hay un hueco de turno en el
# que un KO no cuenta: la ventana ENTRE TURNOS (despues del TURN_END del rival y
# antes del TURN_START nuestro), donde disparan los efectos "entre turnos" como
# Freezing Shroud (Froslass: 1 contador a cada Pokemon CON HABILIDAD). Ese KO no
# ocurre "durante el turno del rival": ocurre en tierra de nadie.
#
# Medido en el episodio 88914948 (registro_008 paso 74, vs Marnie/Grimmsnarl con
# doble Froslass + doble Munkidori), PERDIDA:
#
#   TURN_END(rival) -> 14 contadores de Freezing Shroud (x2 Froslass) -> muere
#   nuestro Dipplin -> el rival cobra premio -> TURN_START(nuestro)
#
# El motor NO ofrecio Unfair Stamp en el menu (lo teniamos en mano) ni la
# habilidad tras bajar el cuerpo: para el juego NO hubo KO "durante el ultimo
# turno del rival". El agente, con `ko_last_turn=True`, bajo Fezandipiti ex a la
# banca a cobrar un robo de 3 que no existia: regalo un cuerpo de 2 premios y
# el ultimo hueco de banca a cambio de nada.
#
# El corte NO es "ataque vs habilidad" (el mismo episodio lo refuta): en el
# registro_011 paso 105 Munkidori MOVIO 3 contadores con Adrena-Brain y mato a
# nuestro Ogerpon ex DENTRO del turno rival -- y ahi el motor SI ofrecio el
# Sello el turno siguiente. Lo que decide es la VENTANA, no la fuente del dano.
#
# De ahi estos marcadores, que se alimentan de los TURN_START / TURN_END de los
# logs (el flujo de logs es contiguo entre lotes, asi que la ventana se arrastra
# de una llamada a la siguiente) y solo pueden REBAJAR `ko_last_turn`: sin
# evidencia positiva se conserva el comportamiento anterior.
_TURNO_LOG_DESCONOCIDO = -1



# Ajuste terminal de PROMOCION (ver "SUPERVIVENCIA AL PROMOVER"). El condenado
# baja lo bastante como para ceder ante cualquier superviviente real (el caso
# medido: Ogerpon cargado 4557 -> -1443, por debajo del Hydrapple ex a 259).
PROMO_DOOMED_PENALTY = 6000
# Sin supervivientes, cada premio extra que regalamos cuesta esto.
PROMO_PRIZE_PENALTY = 1500
# El que NOQUEA al activo rival se promueve por encima de cualquiera que no lo
# haga, tanque incluido (user). Por encima del score maximo de las ramas de
# promocion (9500 = `_promote_setup_ko_attacker`) para que sea una GARANTIA y no
# dependa de que el noqueador saque mas base que el tanque: `_ko_prefer_basic_general`
# da 8500+ a un basico de 1 premio y el muro resistente 6100, asi que un
# noqueador a ~4500 podia perder. Entre varios noqueadores decide el score base.
PROMO_KO_BONUS = 20000
# MATCH POINT: al rival le basta con noquear este cuerpo para llevarse el ultimo
# premio. No es un mal intercambio, es perder la partida -> veto, no
# penalizacion. Va por DEBAJO de SCORE_NEVER (-10000) a proposito: otros vetos
# de promocion usan ese valor exacto (p.ej. "la linea Meganium no va al activo")
# y un empate a -10000 dejaria el desempate al azar del orden de opciones, justo
# entre el cuerpo que aguanta y el que nos hace perder.
PROMO_MATCH_POINT_VETO = -30000







def _init_cartas_tracking():
    ESTADO.CARTAS_ACTIVAS_EN_MAZO = {}
    ESTADO._cartas_first_scan_done = False
    ESTADO._cartas_prizes_identified = False
    for card_id in my_deck:
        if card_id not in ESTADO.CARTAS_ACTIVAS_EN_MAZO:
            ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id] = {
                ESTADO_MAZO: 0,
                ESTADO_BANCA: 0,
                ESTADO_MANO: 0,
                ESTADO_PREMIO: 0,
                ESTADO_DESCARTE: 0,
            }
        ESTADO.CARTAS_ACTIVAS_EN_MAZO[card_id][ESTADO_MAZO] += 1

    # Los marcadores de la ventana del KO abarcan DOS turnos (ver
    # `_rastrear_ventana_de_ko`), asi que no los limpia el reset por turno de
    # `agent()`. Se limpian aqui, que es el gancho de PARTIDA NUEVA: lo llama
    # `_update_cartas_tracking` cuando el contador de turno vuelve a 1 (el
    # harness de self-play encadena miles de episodios en el mismo proceso) y
    # tambien los reseteos de los tests. Sin esto, un KO entre turnos del
    # episodio anterior rebajaria un `ko_last_turn` legitimo del siguiente.
    _reset_ventana_de_ko()


def _reset_ventana_de_ko():
    """Borra el rastro de ventana de los KO propios (partida nueva)."""
    ESTADO._log_turno_en_curso = _TURNO_LOG_DESCONOCIDO
    ESTADO._ko_propio_en_turno_rival = -99
    ESTADO._ko_propio_fuera_del_turno_rival = -99


_init_cartas_tracking()









# --- AUTO-DANO DEL PROPIO ATAQUE (Wood Hammer y compania) -------------------
# Muchos ataques se hacen dano A SI MISMOS ("This Pokemon also does 30 damage to
# itself"). Ese dato NO vive en ningun campo de `Attack`: solo en su TEXTO, asi
# que se parsea una vez por attackId y se cachea. Deck-agnostico: cubre los ~49
# ataques con auto-dano de la base, no solo el Wood Hammer de nuestro Tapu Bulu.
#
# Tres familias, y solo la PRIMERA es dano seguro:
#   * OBLIGATORIO fijo -- "This Pokemon also does 30 damage to itself." -> 30.
#   * OPCIONAL -- "You may do 30 more damage. If you do, this Pokemon also does
#     30 damage to itself." / "You may have this Pokemon also do 60 damage to
#     itself..." -> 0: la decision es NUESTRA, no se asume el auto-dano.
#   * AZAR -- "Flip 2 coins. If both of them are tails, this Pokemon also does
#     90 damage to itself." -> 0 en el calculo CIERTO; el peor caso se obtiene
#     con `incierto=True` (lo que consultan los frenos prudentes).
# Y una escala: "...10 damage to itself for each damage counter on it"
# (Vanguard Punch), que se resuelve con el dano ya recibido por el atacante.
import re as _re_autodano

# `do` sin la -s cubre la forma opcional "You may have this Pokemon also DO 60
# damage to itself..." (Voltaic Fist), que si no quedaba sin clasificar.
_RE_AUTODANO = _re_autodano.compile(
    r"do(?:es)?\s+(\d+)\s+damage\s+to\s+itself", _re_autodano.IGNORECASE)
_RE_AUTODANO_ESCALA = _re_autodano.compile(
    r"to\s+itself\s+for\s+each\s+damage\s+counter", _re_autodano.IGNORECASE)
_AUTODANO_CACHE: dict = {}


def _autodano_spec(attack_id):
    """(n, opcional, azar, por_contador) del auto-dano del ataque; None si no lo
    tiene. El "You may" y el "Flip 2 coins" que condicionan el auto-dano viven a
    menudo en la oracion ANTERIOR, asi que el contexto abarca las dos."""
    if attack_id in _AUTODANO_CACHE:
        return _AUTODANO_CACHE[attack_id]
    spec = None
    _atk = attack_table.get(attack_id)
    texto = (getattr(_atk, 'text', None) or '') if _atk is not None else ''
    _m = _RE_AUTODANO.search(texto)
    if _m is not None:
        _ini = texto.rfind('.', 0, _m.start()) + 1
        _fin = texto.find('.', _m.end())
        _frase = texto[_ini:_fin if _fin != -1 else len(texto)]
        _prev = texto[texto.rfind('.', 0, max(0, _ini - 1)) + 1:_ini]
        _ctx = (_prev + ' ' + _frase).lower()
        spec = (int(_m.group(1)),
                'you may' in _ctx,
                any(_w in _ctx for _w in ('flip', 'coin', 'heads', 'tails')),
                bool(_RE_AUTODANO_ESCALA.search(_frase)))
    _AUTODANO_CACHE[attack_id] = spec
    return spec


def _attack_self_damage(attack_id, attacker=None, incierto=False):
    """Auto-dano que el ataque `attack_id` inflige a su PROPIO portador.

    Devuelve el dano CIERTO: 0 si es opcional (lo decidimos nosotros) o si
    depende de una moneda. Con `incierto=True` devuelve el PEOR caso."""
    spec = _autodano_spec(attack_id)
    if spec is None:
        return 0
    _n, _opcional, _azar, _por_contador = spec
    if _opcional:
        return 0
    if _azar and not incierto:
        return 0
    if _por_contador:
        if attacker is None:
            return 0
        _cont = max(0, ((attacker.maxHp or 0) - (attacker.hp or 0)) // 10)
        return _n * _cont
    return _n


def _self_damage_of_pokemon(pokemon, incierto=False):
    """Auto-dano del ataque que `pokemon` usaria HOY: el PEOR de entre los
    ataques cuyo coste de energia puede pagar ya.

    Los frenos de remate suicida se calculan ANTES del bucle de opciones, donde
    todavia no se conoce el attackId elegido; tomar el maximo es el lado seguro,
    porque su unica consecuencia es DEJAR de reclamar una victoria absoluta (el
    agente vuelve a la puntuacion normal), nunca reclamar una que no existe.
    `len(energies)` ya es energia EFECTIVA y `Attack.energies` es la lista de
    unidades del coste, asi que se comparan directamente."""
    if pokemon is None:
        return 0
    _data = card_table.get(pokemon.id)
    if _data is None or not getattr(_data, 'attacks', None):
        return 0
    _disp = len(pokemon.energies)
    _peor = 0
    for _aid in _data.attacks:
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        if len(getattr(_atk, 'energies', []) or []) > _disp:
            continue  # no puede pagar ese ataque
        _peor = max(_peor, _attack_self_damage(_aid, pokemon, incierto))
    return _peor


def _self_ko_by_own_attack(pokemon, incierto=False):
    """True si el auto-dano del ataque de `pokemon` lo NOQUEA a el mismo."""
    if pokemon is None:
        return False
    _auto = _self_damage_of_pokemon(pokemon, incierto)
    return _auto > 0 and _auto >= (pokemon.hp or 0)











# =============================================================================
# ATAQUES QUE ELIGEN OBJETIVO (SNIPE): el activo rival NO es siempre el mejor
# -----------------------------------------------------------------------------
# Cruel Arrow (Fezandipiti ex) hace 100 fijos a UNO CUALQUIERA de los Pokemon
# del rival, activo o banca ("no apliques Debilidad y Resistencia a los Pokemon
# en Banca"). Todo el resto del scorer mide el ataque del ACTIVO contra el
# ACTIVO rival, asi que con un muro delante daba el turno por esteril: en
# registro_004 paso 54 (vs Alakazam) el Fezandipiti ex activo, con 4 energias
# efectivas, no llegaba al Alakazam de 140 PV y el agente lo RETIRO para subir
# un Ogerpon que ni siquiera podia atacar -- teniendo un Kadabra de 80 PV
# noqueable en la banca rival.
#
# Estas cuatro piezas son la fuente UNICA de verdad del snipe y las comparten
# el planificador (que decide si atacar o retirar) y la seleccion real del
# objetivo en el menu de DAMAGE, que por tanto no pueden discrepar.
SNIPE_ANY_TARGET_IDS = frozenset({Fezandipiti_ex})






def _snipe_best_target(attacker, op_state, effective_energy, meganium_active,
                       neutral_zone, bench_count=0, grass_scale=0):
    """(objetivo, dano_efectivo, es_ko) del MEJOR Pokemon rival para el ataque
    del `attacker`, cuando ese ataque puede apuntar tambien a la banca.

    Devuelve (None, 0, False) si el atacante no es un snipe o no llega al coste
    de su ataque. El dano sale de `_our_effective_damage`, que ya aplica la
    inmunidad a ex (Crustle), Neutralization Zone, Sturdy/Resolute Heart y el
    salto de debilidad/resistencia propio de Fezandipiti (dano fijo)."""
    if attacker is None or attacker.id not in SNIPE_ANY_TARGET_IDS:
        return None, 0, False
    best, best_dmg, best_score = None, 0, 0
    for tgt in _snipe_targets(op_state):
        base = _attacker_base_damage(
            attacker.id, tgt, effective_energy,
            grass_scale=grass_scale, teal_self_energy=effective_energy,
            bench_count=bench_count)
        if base <= 0:
            continue  # el atacante no llega al coste de su ataque
        dmg = _our_effective_damage(attacker, tgt, base, meganium_active,
                                    neutral_zone)
        sc = _snipe_target_score(dmg, tgt)
        if best is None or sc > best_score:
            best, best_dmg, best_score = tgt, dmg, sc
    if best is None:
        return None, 0, False
    return best, best_dmg, (best_dmg > 0 and best_dmg >= (best.hp or 0))






import os as _os_dbg





def _rastrear_ventana_de_ko(logs, my_index, turno):
    """Clasifica NUESTROS KO por la ventana de turno en que ocurrieron.

    Recorre el lote de logs manteniendo el turno en curso (`TURN_START` /
    `TURN_END`) y, cada vez que un Pokemon NUESTRO sale de Activo/Banca al
    descarte, anota el `state.turn` en el marcador que toca:

      * dentro del turno del RIVAL  -> `_ko_propio_en_turno_rival`
        (es el KO que habilita Flip the Script y Unfair Stamp; da igual que lo
        haya hecho un ataque o una habilidad que mueve contadores)
      * ENTRE TURNOS o en NUESTRO turno -> `_ko_propio_fuera_del_turno_rival`
        (no habilita nada: Freezing Shroud y compania matan en tierra de nadie,
        y un auto-KO de retroceso ocurre en nuestro propio turno)

    El estado del turno se ARRASTRA entre llamadas: los lotes de logs son
    contiguos, asi que el `TURN_END` del rival puede haber llegado en la
    observacion anterior (una seleccion forzada durante su turno) y el KO en la
    siguiente. Mientras no hayamos visto ningun marcador de turno el estado es
    `_TURNO_LOG_DESCONOCIDO` y NO se clasifica nada: sin evidencia no se rebaja.
    """

    for log in logs or ():
        _tipo = getattr(log, 'type', None)

        if _tipo == LogType.TURN_START:
            ESTADO._log_turno_en_curso = getattr(log, 'playerIndex', None)
            continue

        if _tipo == LogType.TURN_END:
            ESTADO._log_turno_en_curso = None
            continue

        if _tipo != LogType.MOVE_CARD:
            continue
        if getattr(log, 'playerIndex', None) != my_index:
            continue
        if getattr(log, 'fromArea', None) not in (AreaType.ACTIVE, AreaType.BENCH):
            continue
        if getattr(log, 'toArea', None) != AreaType.DISCARD:
            continue
        # Solo cuerpos: las energias/tools adjuntas salen con fromArea
        # ENERGY/TOOL y la pre-evolucion con PRE_EVOLUTION, pero el filtro
        # explicito evita depender de eso.
        _data_ko = card_table.get(getattr(log, 'cardId', 0))
        if _data_ko is None or not getattr(_data_ko, 'hp', 0):
            continue

        if ESTADO._log_turno_en_curso == _TURNO_LOG_DESCONOCIDO:
            continue
        if ESTADO._log_turno_en_curso == 1 - my_index:
            ESTADO._ko_propio_en_turno_rival = turno
        else:
            ESTADO._ko_propio_fuera_del_turno_rival = turno




def _update_cartas_tracking(obs, my_index, my_state):

    if obs.current.turn == 1 and ESTADO._cartas_last_turn > 1:
        _init_cartas_tracking()
        ESTADO.op_is_crustle_deck = False
        ESTADO.op_is_cornerstone_deck = False
        ESTADO.op_has_mega_kangaskhan = False
    ESTADO._cartas_last_turn = obs.current.turn

    if not ESTADO._cartas_first_scan_done and obs.current is not None:

        _first_turn_scan(my_state)
    else:

        _process_logs(obs, my_index)

        _sync_from_state(my_state)

    _identify_prizes(obs, my_state)































_REGLAS_BOSS_PLAY = [
    _ReglaFija("supporter_ya_jugado",
               lambda c: c.state.supporterPlayed,
               lambda c: SCORE_VETO),
    # Con Unfair Stamp jugable (nos noquearon), el Sello va primero. Solo si el
    # Sello se va a jugar DE VERDAD (`_stamp_pendiente`): si su regla de carta
    # lo veta, el Boss's no le cede el turno a nadie.
    _ReglaFija("cede_a_unfair_stamp",
               _stamp_pendiente,
               lambda c: SCORE_VETO),
    # Regla (user): vs Alakazam con Dunsparce activo rival y nuestro activo
    # SIN ataque, NO gustear: despejaria el muro y les daria via libre;
    # conviene mantener trabado a Dunsparce.
    _ReglaFija("no_despejar_muro_dunsparce",
               lambda c: (c.op_is_alakazam_deck and c.op_active_is_dunsparce
                          and c.active_cant_attack),
               lambda c: SCORE_VETO),
    # Gusteo GANADOR: el ACTIVO noquea a un objetivo de banca y GANA la
    # partida. Debe superar CUALQUIER retirada/pivote (~6500-6600); antes se
    # puntuaba win_via_bench (5600) y el agente RETIRABA en vez de rematar
    # (user, registro 019 paso 190 vs Dragapult, GANADA).
    _ReglaFija("gusteo_ganador",
               lambda c: c.win_via_boss_gust,
               lambda c: BOSS_SCORE_WIN_NOW + c.supporter_boost),
    # MATCH POINT AL ACTIVO (user, registro_010 paso 144 vs Marnie's Grimmsnarl
    # ex, PERDIDA): el ACTIVO rival ya vale los premios que nos faltan y un
    # cuerpo de BANCA lo remata tras una retirada pagable. La partida se cierra
    # retirando -- sin gastar el Supporter y sin cambiar el activo rival, que es
    # justo el cuerpo que queremos noquear. Gustear cualquier otra cosa cambia
    # el objetivo por uno de MENOS premios y tira el turno ganador: VETO.
    # Cede a `gusteo_ganador` (arriba): ese remate ya gana con el activo actual,
    # sin pagar la retirada.
    _ReglaFija("remate_ganador_al_activo_tras_retirar",
               lambda c: (c.win_ko_active_via_promote
                          and not c.win_via_boss_gust),
               lambda c: SCORE_VETO),
    # MURO INMUNE A EX PRIMERO (user, registro_006 paso 47 vs Crustle,
    # PERDIDA): con Crustle/Sylveon de ACTIVO rival y nuestro activo capaz de
    # NOQUEARLO este turno, NO se juega Boss's. Gustear cambia el activo rival:
    # el muro se va a la banca sano y el turno se gasta en otro cuerpo, cuando
    # la unica cosa que nuestro mazo (todo ex: Ogerpon, Hydrapple, Meowth,
    # Fezandipiti) no puede hacer despues es tocar a ese muro. En el registro
    # el gusteo cobro 2 premios del Ogerpon ex de su banca (`gusteo_2_premios`,
    # 6800) y dejo vivo al Crustle. Excepciones: los gusteos que GANAN la
    # partida ya (`win_via_boss_gust` / `boss_win_via_bench`) siguen mandando.
    # Solo aplica a Crustle/Sylveon (`EX_IMMUNE_IDS`): un muro de Habilidad
    # (Cornerstone) se resuelve al contrario, gusteandolo.
    _ReglaFija("rematar_muro_inmune_antes_de_gustear",
               lambda c: (c.ex_immune_wall_ko_ready
                          and not c.win_via_boss_gust
                          and not c.boss_win_via_bench),
               lambda c: SCORE_VETO),
    # Gusteo de 2 PREMIOS (user, registro_008 paso 119 vs TR Mewtwo ex,
    # GANADA): el activo ya noquea al activo rival (1 premio) pero un ex de
    # banca noqueable da 2; `gust_2prize_via_boss` ya exige KO, >= 2 premios,
    # > premios del activo y no trade-down. Bajo WIN_NOW, sobre pivotes.
    _ReglaFija("gusteo_2_premios",
               lambda c: c.gust_2prize_via_boss,
               lambda c: BOSS_SCORE_GUST_2PRIZE + c.supporter_boost),
    # PESCA DE REMATE (user, registro_004 paso 49 vs Marnie, PERDIDA): sin
    # ningun ataque posible este turno, el hueco de Supporter vale mas pescando
    # con Lillie's la energia que desbloquea un KO de premios (ver
    # `_pesca_de_remate`) que gusteando. El gusteo, ademas, cambia el activo
    # rival justo cuando ese activo ES el objetivo del remate que se pesca.
    # Va tras los remates SEGUROS (gusteo ganador, 2 premios, match point), que
    # `_pesca_remate_valida` ya se exceptua.
    _ReglaFija("cede_a_pesca_de_remate",
               lambda c: (_pesca_remate_valida(c)
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _ReglaFija("primer_turno_cede_a_lillie",
               _boss_first_turn_cede,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _ReglaFija("gusteo_vacio_cede_a_lillie",
               _boss_empty_gust,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _ReglaFija("sin_atacante_banca_cede_a_lillie",
               _boss_cede_dig,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _ReglaFija("muro_inmune",
               lambda c: ((c.op_has_ability_immune_active
                           or c.op_has_ex_immune_active)
                          and _boss_val_de(c) >= 900),
               lambda c: BOSS_SCORE_WALL_GUST + c.supporter_boost),
    _ReglaFija("dodge_redirect",
               lambda c: c.boss_dodge_redirect,
               lambda c: BOSS_SCORE_DODGE_REDIRECT + c.supporter_boost),
    _ReglaFija("win_via_bench",
               lambda c: c.boss_win_via_bench,
               lambda c: BOSS_SCORE_WIN_VIA_BENCH + c.supporter_boost),
    # Cortar la linea Alakazam: gustear+noquear su pre-evo de banca cuando
    # el activo rival esta fuera de la linea (muro). Registro 010, paso 64.
    _ReglaFija("cortar_linea_alakazam",
               lambda c: c.boss_deny_alakazam_line,
               lambda c: BOSS_SCORE_PRIZE_RANK_BASE + c.supporter_boost),
    # Prioridad entre copias de la misma amenaza (user, registro_007 paso 80
    # vs Archaludon): el activo rival (Hero's Cape + 3 energias) domina a su
    # copia debil de banca -> ATACAR al activo y GUARDAR el Boss's. Corta
    # las ramas de valor bajo/medio; los remates ya retornaron antes.
    _ReglaFija("amenaza_activa_domina",
               lambda c: c.boss_active_threat_dominates,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    # Des-lockear las habilidades gusteando un no-locker (ver el docstring
    # de _boss_unlock_gust). Tras los remates y las cesiones a Lillie's;
    # sobre low_value/defensivo/sin_valor, que era donde moria (-1).
    _ReglaFija("gusteo_deslockea_habilidades",
               _boss_unlock_gust,
               lambda c: BOSS_SCORE_UNLOCK_GUST + c.supporter_boost),
    # Los dos VETOS del gusteo SIN PROPOSITO (ver sus docstrings). Van aqui, con
    # todos los motivos de premio/muro/lock ya resueltos por arriba, y por
    # encima de las tres ramas que no exigen KO ni amenaza: `gusteo_low_value`,
    # `gusteo_defensivo` y sobre todo la reserva `valor_del_supporter`, que es
    # la que jugaba el Boss's del registro_002 paso 20 (2400 + 200*1.4 = 2680).
    # Ambas condiciones se exceptuan a si mismas con `_boss_motivo_con_premio`,
    # asi que `gusteo_por_prize_rank` (exige KO) y `gusteo_defensivo` (exige el
    # remate rival) siguen alcanzables por debajo.
    _ReglaFija("no_regalar_linea_alakazam",
               _boss_regala_linea_alakazam,
               lambda c: SCORE_VETO),
    _ReglaFija("gusteo_sin_proposito",
               _boss_gusteo_sin_proposito,
               lambda c: SCORE_VETO),
    _ReglaFija("gusteo_low_value",
               lambda c: c.boss_low_value_gust,
               lambda c: BOSS_SCORE_LOW_VALUE_GUST + c.supporter_boost),
    _ReglaFija("gusteo_por_prize_rank",
               lambda c: c.boss_prize_rank >= 1,
               lambda c: (BOSS_SCORE_PRIZE_RANK_BASE
                          + (8 - c.boss_prize_rank) * 20
                          + c.supporter_boost)),
    _ReglaFija("gusteo_defensivo",
               lambda c: c.boss_defensive_gust,
               lambda c: BOSS_SCORE_DEFENSIVE_GUST + c.supporter_boost),
    _ReglaFija("sin_valor",
               lambda c: _boss_val_de(c) <= 0,
               lambda c: SCORE_VETO),
    # Fallback: valor generico del supporter.
    _ReglaFija("valor_del_supporter",
               lambda c: True,
               lambda c: (SCORE_SUPPORTER_VALUE_BASE
                          + int(_boss_val_de(c) * 1.4)
                          + c.supporter_boost)),
]

def _score_boss_orders_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Boss's Orders (id 1182). Cuerpo migrado al MOTOR
    DE REGLAS (fase 4): las reglas y sus comentarios estrategicos viven en
    _REGLAS_BOSS_PLAY; PTCG_DEBUG imprime la traza."""
    return _resolver_con_traza("boss->play", _REGLAS_BOSS_PLAY, [], ctx,
                               defecto=0)



































# Umbral de "energia todavia util sobre el ACTIVO", por familia de cuerpo.
# Antes esto era una cadena de `if act.id == ...` dentro de
# `_ns_activo_no_llega_al_coste`; extraerlo a tablas permite anadir el fallback
# deck-agnostico sin tocar ninguna de las decisiones ya medidas.
#
# LINEA MEGANIUM: manda el coste de RETIRADA, no el de ataque. Es una decision
# de ESTRATEGIA, no un dato de carta: a estos cuerpos no los queremos atacando
# (Chikorita nunca usa Growl, Meganium es el motor Wild Growth), los queremos
# pudiendo pivotar. Por eso Meganium corta en 2 (retirada) y no en 4 (Solar
# Beam). Ver [[retirar-chikorita-para-linea-meganium]].
_NS_UMBRAL_POR_RETIRADA = frozenset({Chikorita, Bayleef, Meganium})
# ATACANTES cuyo umbral es su coste de ataque (fuente: ATTACK_ENERGY_REQ).
# Fezandipiti ex y Meowth ex quedan FUERA a proposito: son cuerpos de utilidad
# (Cruel Arrow cuesta 3, Last-Ditch Catch no ataca), y regar una sola energia
# hacia ellos no hace progresar ningun plan. Cuando el activo es uno de ellos y
# hay un rematador en banca, la jugada correcta no es cargarlos sino RETIRARLOS
# -- eso lo cubren `_ns_e_retirada_letal` / `_ns_e_retirada_chip`.
_NS_UMBRAL_POR_ATAQUE = frozenset({Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
                                   Tapu_Bulu, Pinsir})


def _ns_umbral_energia_util(card_id):
    """Energia a partir de la cual una Planta mas sobre el ACTIVO deja de
    aportar. `None` = recuperar energia para ese cuerpo no aporta nada.

    Tres niveles, de mas especifico a mas general:
      1. tablas CURADAS del mazo actual (`_NS_UMBRAL_POR_RETIRADA` /
         `_NS_UMBRAL_POR_ATAQUE`): codifican estrategia medida, mandan siempre;
      2. resto de Pokemon de deck.csv (`_DECK_POKEMON_IDS`) -> `None`: la
         configuracion los conoce y los excluye A PROPOSITO (Meowth ex,
         Fezandipiti ex); derivarlos del dato de carta desharia esa decision;
      3. cualquier otro cuerpo -> `_coste_de_ataque_min`, derivado del dato de
         carta. Es la rama DECK-AGNOSTICA: con otro deck.csv la funcion deja de
         devolver `False` a ciegas y razona con el coste real del ataque.
    """
    if card_id in _NS_UMBRAL_POR_RETIRADA:
        return RETREAT_COST.get(card_id, 1)
    if card_id in _NS_UMBRAL_POR_ATAQUE:
        return ESTADO.ATTACK_ENERGY_REQ.get(card_id)
    if card_id in _DECK_POKEMON_IDS:
        return None
    return _coste_de_ataque_min(card_id)


def _ns_activo_no_llega_al_coste(w):
    """El ACTIVO todavia no alcanza su umbral de energia util
    (`_ns_umbral_energia_util`) ni por energia EFECTIVA ni por cartas FISICAS.

    Se comprueban las dos porque con Meganium en juego `len(energies)` viene
    duplicado por Wild Growth: el tope efectivo evita atacar de menos y el
    fisico evita amontonar cartas de energia que ya no hacen falta.
    """
    act = _active_of(w.my_state)
    if act is None:
        return False
    umbral = _ns_umbral_energia_util(act.id)
    if umbral is None:
        return False
    e, eff = len(act.energies), len(act.energies) * _grass_mult()
    return eff < umbral and e < umbral


def _ns_e_activo_necesita(w):
    """Energia del descarte para el ACTIVO que aun no llega a su coste de
    ataque (o de retirada, para la linea Meganium) y no esta al tope."""
    return (_ns_energia_util_sin_planta(w)
            and not w.state.energyAttached
            and _ns_activo_no_llega_al_coste(w))


def _ns_e_activo_por_debajo_del_coste(w):
    """Como `_ns_e_activo_necesita` pero admitiendo tambien la carga por
    HABILIDAD cuando el adjunte manual del turno ya se gasto."""
    return (_ns_energia_util_sin_planta(w)
            and _ns_activo_no_llega_al_coste(w)
            and _ns_ruta_de_carga_hasta_el_activo(w))

















_ESC_NS_RECUPERACION = [
    # Combos completos (recuperar la pieza + evolucionar la linea entera).
    _E("applin_combo_completo",
       lambda w: (Applin in w.basics and w.hand_counts.get(Dipplin, 0) >= 1
                  and w.hand_counts.get(Hydrapple_ex, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 980),
    _E("dipplin_combo_completo",
       lambda w: (Dipplin in w.evos and w.hand_counts.get(Applin, 0) >= 1
                  and w.hand_counts.get(Hydrapple_ex, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 970),
    _E("applin_con_dipplin_mano",
       lambda w: (Applin in w.basics and w.hand_counts.get(Dipplin, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 900),
    _E("dipplin_con_applin_mano",
       lambda w: (Dipplin in w.evos and w.hand_counts.get(Applin, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 880),
    _E("hydra_con_applin_campo",
       lambda w: (Hydrapple_ex in w.evos
                  and w.field_counts.get(Applin, 0) >= 1
                  and w.hand_counts.get(Dipplin, 0) >= 1
                  and w.forest_in_play), 960),
    _E("hydra_dipplin_evolucionable",
       lambda w: (Hydrapple_ex in w.evos
                  and w.evolvable.get(Dipplin, 0) >= 1), 950),
    _E("chikorita_combo_completo",
       lambda w: (Chikorita in w.basics and not w.meganium_in_play
                  and w.hand_counts.get(Bayleef, 0) >= 1
                  and w.hand_counts.get(Meganium, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 990),
    _E("bayleef_combo_completo",
       lambda w: (Bayleef in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Chikorita, 0) >= 1
                  and w.hand_counts.get(Meganium, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 985),
    _E("chikorita_con_bayleef_mano",
       lambda w: (Chikorita in w.basics and not w.meganium_in_play
                  and w.hand_counts.get(Bayleef, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 920),
    _E("bayleef_con_chikorita_mano",
       lambda w: (Bayleef in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Chikorita, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 910),
    _E("meganium_con_chikorita_campo",
       lambda w: (Meganium in w.evos and not w.meganium_in_play
                  and w.field_counts.get(Chikorita, 0) >= 1
                  and w.hand_counts.get(Bayleef, 0) >= 1
                  and w.forest_in_play), 975),
    _E("meganium_bayleef_evolucionable",
       lambda w: (Meganium in w.evos and not w.meganium_in_play
                  and w.evolvable.get(Bayleef, 0) >= 1), 970),
    # Arrancar lineas desde cero.
    _E("applin_arrancar_linea",
       lambda w: (Applin in w.basics and not w.has_hydrapple
                  and (w.field_counts.get(Applin, 0)
                       + w.field_counts.get(Dipplin, 0)) == 0
                  and w.bench_count < 5), 700),
    _E("chikorita_arrancar_linea",
       lambda w: (Chikorita in w.basics and not w.meganium_in_play
                  and (w.field_counts.get(Chikorita, 0)
                       + w.field_counts.get(Bayleef, 0)
                       + w.field_counts.get(Meganium, 0)) == 0
                  and w.bench_count < 5), 750),
    # Evolucion directa de una pre-evo YA en juego (valor segun Forest).
    _E("dipplin_applin_evolucionable",
       lambda w: (Dipplin in w.evos and not w.has_hydrapple
                  and w.hand_counts.get(Dipplin, 0) == 0
                  and w.evolvable.get(Applin, 0) >= 1),
       lambda w: 880 if w.forest_in_play else 750),
    _E("bayleef_chikorita_evolucionable",
       lambda w: (Bayleef in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Bayleef, 0) == 0
                  and w.evolvable.get(Chikorita, 0) >= 1),
       lambda w: 900 if w.forest_in_play else 780),
    _E("meganium_directo",
       lambda w: (Meganium in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Meganium, 0) == 0
                  and w.evolvable.get(Bayleef, 0) >= 1),
       lambda w: 970 if w.forest_in_play else 900),
    _E("hydra_directo",
       lambda w: (Hydrapple_ex in w.evos and not w.has_hydrapple
                  and w.hand_counts.get(Hydrapple_ex, 0) == 0
                  and w.evolvable.get(Dipplin, 0) >= 1),
       lambda w: 960 if w.forest_in_play else 950),
    # Futuro con Forest (la evolucion esta en mano o en el mazo).
    _E("applin_futuro_con_forest",
       lambda w: (w.forest_in_play and w.bench_count < 5
                  and Applin in w.basics
                  and (w.field_counts.get(Applin, 0)
                       + w.field_counts.get(Dipplin, 0)
                       + w.field_counts.get(Hydrapple_ex, 0)) == 0
                  and not w.has_hydrapple
                  and (w.hand_counts.get(Dipplin, 0) >= 1
                       or w.cartas_en_mazo.get(
                           Dipplin, {}).get(ESTADO_MAZO, 0) > 0)), 870),
    _E("chikorita_futuro_con_forest",
       lambda w: (w.forest_in_play and w.bench_count < 5
                  and Chikorita in w.basics
                  and (w.field_counts.get(Chikorita, 0)
                       + w.field_counts.get(Bayleef, 0)
                       + w.field_counts.get(Meganium, 0)) == 0
                  and not w.meganium_in_play
                  and (w.hand_counts.get(Bayleef, 0) >= 1
                       or w.cartas_en_mazo.get(
                           Bayleef, {}).get(ESTADO_MAZO, 0) > 0)), 890),
    # Cuerpos de valor puntual.
    _E("tapu_vs_crustle",
       lambda w: (Tapu_Bulu in w.basics
                  and w.field_counts.get(Tapu_Bulu, 0) == 0
                  and w.op_is_crustle_deck and w.bench_count < 5), 850),
    _E("fez_tras_ko",
       lambda w: (Fezandipiti_ex in w.basics
                  and w.field_counts.get(Fezandipiti_ex, 0) == 0
                  and w.ko_last_turn and w.bench_count < 5), 840),
    _E("ogerpon_con_energia_mano",
       lambda w: (Teal_Mask_Ogerpon_ex in w.basics
                  and w.hand_counts.get(Basic_Grass_Energy, 0) >= 1
                  and w.bench_count <= 3), 820),
    # Recuperar Meowth ex para el motor de refresco (Last-Ditch ->
    # Lillie's). Registro 006, paso 51 vs Alakazam.
    _E("meowth_motor_refresco",
       lambda w: (Meowth_ex in w.basics and not w.meowth_ability_lock
                  and w.field_counts.get(Meowth_ex, 0) == 0
                  and w.bench_count < 5 and not w.state.supporterPlayed
                  and w.best_supp_in_hand_val < 500
                  and w.best_supp_in_mazo_val >= 400), 830),
    # Energia del descarte.
    _E("energia_activo_necesita", _ns_e_activo_necesita, 860),
    _E("energia_hydra_ripening",
       lambda w: (_ns_energia_util_sin_planta(w) and w.my_state.active
                  and w.my_state.active[0] is not None
                  and w.my_state.active[0].id == Hydrapple_ex
                  and len(w.my_state.active[0].energies)
                      * _grass_mult() < 2), 860),
    _E("energia_syrup_letal", _ns_e_syrup_letal, 950),
    # Mismo tier que el remate con el activo: el premio de hoy manda.
    _E("energia_remate_con_el_activo", _ns_e_remate_con_el_activo, 950),
    _E("energia_remate_via_promocion", _ns_e_remate_via_promocion, 950),
    # LA PLANTA QUE PAGA LA RETIRADA (user, registro_021 turno 21): activo
    # bloqueado sin energia + atacante de banca LISTO que remata, y la unica
    # copia de Planta esta en el DESCARTE. `_ns_e_remate_via_promocion` NO cubre
    # este caso -- exige `len(act.energies) >= coste`, es decir que la retirada
    # YA se pueda pagar --, y `_ns_e_activo_necesita` tampoco: pasa por
    # `_ns_activo_no_llega_al_coste`, una tabla por carta que devuelve False
    # para todo lo que no sea de la linea Meganium/Hydrapple/Ogerpon/Tapu/Pinsir
    # (Fezandipiti ex, Meowth ex y cualquier cuerpo de otro mazo caen fuera).
    # Sin estos dos escenarios el ARGMAX daba 0 -> SCORE_VETO -> END con el
    # remate en la mesa. Tier 950 (letal) = el resto de remates: el premio de
    # hoy manda. Tier 860 (chip) = misma banda que `energia_activo_necesita`.
    _E("energia_retirada_letal", _ns_e_retirada_letal, 950),
    _E("energia_retirada_chip", _ns_e_retirada_chip, 860),
    _E("energia_teal_dance",
       lambda w: (_ns_energia_util_sin_planta(w)
                  and w.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
                  and _ns_hay_ogerpon_teal(w)), 800),
    _E("energia_activo_sin_teal",
       lambda w: (_ns_energia_util_sin_planta(w)
                  and w.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
                  and not _ns_hay_ogerpon_teal(w)
                  and not w.state.energyAttached
                  and w.active_needs_energy), 860),
    _E("energia_linea_mega_activa",
       lambda w: (w.mega_line_active and _ns_energia_util_sin_planta(w)
                  and not w.state.energyAttached), 950),
]



_ESC_NS_CRUSTLE = [
    # vs Crustle/Cornerstone SOLO se consideran recuperaciones de la
    # whitelist no-ex (el bloque original REEMPLAZA el acumulador).
    _E("basico_whitelist",
       lambda w: (w.bench_count < 5
                  and any(b in w.basics
                          for b in _ns_crustle_basicos_permitidos(w))), 900),
    _E("dipplin_con_applin",
       lambda w: (Dipplin in _ns_crustle_evos_permitidas(w)
                  and Dipplin in w.evos and not w.has_hydrapple
                  and (w.field_counts.get(Applin, 0) >= 1
                       or w.hand_counts.get(Applin, 0) >= 1)), 880),
    _E("bayleef_con_chikorita",
       lambda w: (Bayleef in _ns_crustle_evos_permitidas(w)
                  and Bayleef in w.evos and not w.meganium_in_play
                  and (w.field_counts.get(Chikorita, 0) >= 1
                       or w.hand_counts.get(Chikorita, 0) >= 1)), 880),
    _E("meganium_con_bayleef",
       lambda w: (Meganium in _ns_crustle_evos_permitidas(w)
                  and Meganium in w.evos and not w.meganium_in_play
                  and (w.field_counts.get(Bayleef, 0) >= 1
                       or w.hand_counts.get(Bayleef, 0) >= 1)), 900),
    _E("energia_dipplin_activo_cero",
       lambda w: (_ns_energia_util_sin_planta(w)
                  and not w.state.energyAttached
                  and w.my_state.active
                  and w.my_state.active[0] is not None
                  and w.my_state.active[0].id == Dipplin
                  and len(w.my_state.active[0].energies) == 0), 900),
    # Recuperar Hydrapple ex para el KO al Kangaskhan (op_kang_ko_target).
    _E("hydra_para_kang_ko",
       lambda w: (w.op_kang_ko_target and Hydrapple_ex in w.evos
                  and not w.has_hydrapple
                  and (w.field_counts.get(Dipplin, 0) >= 1
                       or w.hand_counts.get(Dipplin, 0) >= 1)), 960),
    # Cargar un atacante de banca antes de refrescar con Lillie's.
    _E("energia_cargar_banca", _ns_e_cargar_banca_crustle, 850),
]

def _ns_banca_llena_guardar(w, ns_score):
    """Corte de banca llena (como UB/Poke Pad) con excepciones: energia
    util o una pre-evo en juego cuya evolucion este en el descarte."""
    if w.bench_count < 5 or ns_score <= 0:
        return False
    energia_util = _ns_energia_util_sin_planta(w) and not w.state.energyAttached
    if (_ns_energia_util_sin_planta(w) and w.my_state.active
            and w.my_state.active[0] is not None
            and w.my_state.active[0].id == Hydrapple_ex
            and len(w.my_state.active[0].energies) * _grass_mult() < 2):
        energia_util = True
    # La energia recuperada NO deja de ser util porque el adjunte MANUAL del
    # turno ya se haya gastado: Teal Dance y Ripening Charge son HABILIDADES y
    # pueden ponerla igualmente en el campo (user, registro_006 paso 68 vs Mega
    # Abomasnow ex, PERDIDA). Alli, con la banca llena y `energyAttached`, este
    # corte vetaba la Night Stretcher que habilitaba el remate: Syrup Storm
    # 30+30x10 = 330 contra 350 PV, y la Planta del descarte (via Teal Dance en
    # un Ogerpon de banca) lo subia a 390. Se exige que quede ruta de carga
    # real (`_ns_ruta_de_carga_abierta`) para no recuperar una Planta muerta.
    if not energia_util:
        if _ns_e_syrup_letal(w) and _ns_ruta_de_carga_abierta(w):
            energia_util = True
        elif _ns_e_remate_con_el_activo(w):
            energia_util = True
        elif _ns_e_remate_via_promocion(w):
            energia_util = True
        elif _ns_e_activo_por_debajo_del_coste(w):
            energia_util = True
        elif _ns_e_activo_paga_retirada(w):
            energia_util = True
    algo_que_evolucionar = w.evolve_possible_in_play or (
        (w.field_counts.get(Chikorita, 0) >= 1 and Bayleef in w.evos) or
        (w.field_counts.get(Bayleef, 0) >= 1 and Meganium in w.evos) or
        (w.field_counts.get(Applin, 0) >= 1 and Dipplin in w.evos) or
        (w.field_counts.get(Dipplin, 0) >= 1 and Hydrapple_ex in w.evos))
    return not algo_que_evolucionar and not energia_util

_AJUSTES_NS_PLAY = [
    _Ajuste("banca_llena_guardar",
            lambda w, s: _ns_banca_llena_guardar(w, s),
            lambda w, s: SCORE_VETO),
    # Rescate anti-Kangaskhan: recuperar el Hydrapple ex que noquea al
    # Mega Kangaskhan ex proyectado (op_kang_ko_target) domina todo.
    _Ajuste("rescate_hydra_anti_kang",
            lambda w, s: (w.op_kang_ko_target and Hydrapple_ex in w.evos
                          and not w.has_hydrapple
                          and (w.field_counts.get(Dipplin, 0) >= 1
                               or w.hand_counts.get(Dipplin, 0) >= 1)),
            lambda w, s: 34000),
]

def _score_night_stretcher_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Night Stretcher (recupera Pokemon o Energia del
    descarte). Cuerpo migrado al MOTOR DE REGLAS (fase 4) con el modo ARGMAX
    (_resolver_max): ~30 escenarios de recuperacion compiten y el mejor se
    mapea a tiers de score; vs Crustle/Cornerstone compite SOLO la lista de
    whitelist (el original reemplaza el acumulador)."""
    w = _CtxNSPlay(ctx)
    if ctx.op_is_crustle_deck or ctx.op_is_cornerstone_deck:
        mejor, traza_max = _resolver_max(_ESC_NS_CRUSTLE, w)
    else:
        mejor, traza_max = _resolver_max(_ESC_NS_RECUPERACION, w)
    if mejor >= 900:
        base = 11800
    elif mejor >= 800:
        base = 11000
    elif mejor >= 700:
        base = 10400
    elif mejor > 0:
        base = 9800
    else:
        base = SCORE_VETO
    score, traza = _resolver_reglas([], _AJUSTES_NS_PLAY, w, defecto=base)
    if os.environ.get("PTCG_DEBUG"):
        print("[reglas ns->play]", traza_max, "|", " | ".join(traza))
    return score






_REGLAS_FOREST_PLAY = [
    _ReglaFija("t1_saliendo_primeros",
               lambda c: c.we_go_first and c.state.turn == 1,
               lambda c: SCORE_VETO),
    # Copia REDUNDANTE de Forest en el primer turno saliendo segundos
    # (autopsia cornerstone_cubchoo p004, plan jul 2026): con >=2 Forest en la
    # MANO y una cadena evolutiva a la que Forest le sirve (Applin/Chikorita
    # con su evolucion disponible), guardarlas todas es sobre-conservador. Se
    # juega una aunque el rival no tenga estadio: el mazo lleva 4 copias, la
    # extra es peso muerto y si el estadio sobrevive la cadena dispara el
    # proximo turno. El gate `_fv_cadena_evolutiva` evita gastarla en manos
    # sin linea (medicion vs comfey: sin el gate el matchup bajaba ~10pts).
    # El veto de abajo sigue cubriendo el caso de copia UNICA.
    _ReglaFija("t1_segundos_copia_redundante",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and c.stadium_id == 0
                          and c.hand_counts.get(Forest_of_Vitality, 0) >= 2
                          and _fv_cadena_evolutiva(c)),
               lambda c: 12000),
    # vs CRUSTLE: EL ESTADIO ANTES DE LA LILLIE'S (regla del user).
    # El veto general de estadio en NUESTRO primer turno existe para no regalar
    # el Forest a un rival que lo reemplace acto seguido. El mazo Crustle no
    # juega estadio (o lleva una o dos copias sueltas), asi que ese riesgo no
    # existe: el Forest se queda en mesa. Y Lillie's Determination BARAJA LA
    # MANO ENTERA en el mazo, asi que conservar el estadio "para mas adelante"
    # con una Lillie's en la misma mano es PERDERLO. Saliendo SEGUNDOS (turno 2)
    # con estadio + Lillie's y el Supporter aun sin jugar se baja primero el
    # estadio -- el tier de orden `_TIER_STADIUM` (50) ya lo antepone al
    # Supporter (tier 0) -- y despues se refresca la mano.
    # Solo vs Crustle: contra el resto de matchups sigue mandando el veto. Se
    # mira la LINEA en el tablero (`_op_juega_crustle`) y no el flag
    # `op_is_crustle_deck`, que tambien se enciende con Sylveon/Eevee: esos
    # comparten la inmunidad a ex, pero no la ausencia de estadio, que es lo
    # unico que justifica adelantar el nuestro.
    _ReglaFija("t1_segundos_crustle_estadio_antes_de_lillie",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and _op_juega_crustle(c.op_state)
                          and c.stadium_id == 0
                          and not c.state.supporterPlayed
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: 12000),
    _ReglaFija("t1_segundos_sin_estadio_rival",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and c.stadium_id == 0),
               lambda c: SCORE_VETO),
    _ReglaFija("t1_segundos_reemplaza_estadio",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and c.stadium_id != 0
                          and c.stadium_id != Forest_of_Vitality),
               lambda c: 15000),
    _ReglaFija("forest_ya_en_juego",
               lambda c: c.stadium_id == Forest_of_Vitality,
               lambda c: SCORE_VETO),
    # PRIMERO LA HABILIDAD DE GRAND TREE, DESPUES EL REEMPLAZO (regla del user).
    # Con Grand Tree en mesa y una Forest of Vitality en la mano, jugar el
    # Forest AHORA tira a la basura una cadena evolutiva GRATIS (Basico ->
    # Fase 1 -> Fase 2 sacada del mazo). El estadio del rival no se va a ningun
    # sitio: se usa la habilidad y en el MISMO turno, ya sin la opcion ABILITY
    # en el menu, esta regla deja de disparar y el Forest se juega con su score
    # normal (`reemplazar_estadio_rival`, 15000).
    #
    # Mismo mecanismo que "Teal Dance precede al adjunte manual": vetar la
    # jugada mientras la habilidad siga OFRECIDA en el menu, en vez de intentar
    # ordenar dos acciones dentro de una sola llamada a `agent()`.
    # `grand_tree_ability_pending` ya exige que haya un plan ejecutable, asi
    # que un Grand Tree inutil (sin Basico evolucionable, o con la cadena
    # agotada en el mazo) NO retiene el Forest.
    _ReglaFija("esperar_habilidad_grand_tree",
               lambda c: c.grand_tree_ability_pending,
               lambda c: SCORE_VETO),
    # Neutralization Zone anula el DANO de nuestros ex a Pokemon de 1
    # premio: removerla es lo mas urgente (29000 con linea grass en campo).
    _ReglaFija("anular_neutralization_zone",
               lambda c: c.neutralization_zone_active,
               _v_fv_neutralization),
    # Team Rocket's Watchtower APAGA el motor Meowth (anula Last-Ditch).
    # Con el motor VIVO, reemplazarla es prioritario: 27000, bajo la
    # Neutralization Zone y sobre la cadena evolutiva (21900-22000).
    # (auditoria julio 2026, sugerencia 3)
    _ReglaFija("reactivar_motor_meowth_vs_watchtower",
               lambda c: (c.watchtower_in_play
                          and c.field_counts.get(Meowth_ex, 0) < 2
                          and (c.hand_counts.get(Meowth_ex, 0) >= 1
                               or c.cartas_en_mazo.get(
                                   Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0)),
               lambda c: 27000),
    # Festival Grounds ENCIENDE Festival Lead: su Dipplin repite el ataque en
    # cuanto nos noquea el activo, que es como se cierran las partidas contra
    # ese mazo (log 88971843). Reemplazarlo apaga el doble ataque de raiz, asi
    # que va por delante de la cadena evolutiva (21900-22000): la cadena se
    # cobra el proximo turno, el doble ataque nos mata en este. Queda por
    # debajo del motor Meowth (27000), que ademas es irreversible.
    # NO MEDIDO en self-play: el BotRival generico no sabe pilotar el mazo
    # Festival Lead (98.9% en ambos brazos), asi que el gate no tiene senal.
    _ReglaFija("apagar_festival_lead",
               lambda c: c.festival_lead_hostil,
               lambda c: 26000),
    _ReglaFija("habilita_cadena_evolutiva",
               _fv_cadena_evolutiva,
               _v_fv_cadena),
    _ReglaFija("reemplazar_estadio_rival",
               lambda c: c.stadium_id != 0,
               lambda c: 15000),
    _ReglaFija("desarrollo_temprano",
               lambda c: c.state.turn <= 4,
               _v_fv_temprano),
]

def _score_forest_of_vitality_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Forest of Vitality (estadio que permite evolucionar
    el mismo turno). Cuerpo migrado al MOTOR DE REGLAS (fase 4)."""
    return _resolver_con_traza("forest->play", _REGLAS_FOREST_PLAY, [],
                               ctx, defecto=8000)






































def _ub_meowth_para_manana(ctx) -> bool:
    """Cavar HOY el Meowth ex que se jugara MAÑANA, porque mañana no hay Items.

    UNICA excepcion a "la Ultra Ball solo se juega por un Pokemon que vayamos a
    JUGAR este turno" (`_ub_cavar_meowth_se_juega`), y la simetrica de la que ya
    tenia la red de rescate del turno esteril: con el bloqueo de Items encima
    (`_bloqueo_de_items_inminente`) la Ultra Ball no es un recurso que se guarda,
    es un recurso que CADUCA.

    Escenario que la motiva (user, registro_002 paso 17 vs Dragapult, PERDIDA --
    episodio 89079426, turno 2 saliendo segundos):

        NOSOTROS                                  RIVAL
        activo Chikorita 70, 1 energia            activo **Budew 30**
        banca  Fezandipiti ex 210, 0 energias     banca  Dreepy x2, Munkidori 1 en.
        mano   Planta x3, Boss's x2, **Ultra Ball**, Meganium, Forest
        (Lillie's Determination YA jugada este turno)

    El agente **atacaba con el Chikorita** y cerraba el turno con la Ultra Ball
    en la mano. Al turno siguiente el *Itchy Pollen* del Budew la mataba: la
    unica carta que podia rehacer la partida se quedo de adorno hasta el final.

    El tablero era el peor posible -- Fezandipiti ex a 3 energias de atacar
    (una por turno) y un Meganium en la mano sin Bayleef debajo:
    `_sin_atacante_para_manana`. La linea correcta es cavar el Meowth ex AHORA y
    bajarlo el turno que viene (los Pokemon y las habilidades NO los bloquea el
    Itchy Pollen), donde su *Last-Ditch Catch* trae una Lillie's Determination
    -- un Supporter, tambien jugable bajo el bloqueo.

    Por que no se baja el Meowth ex hoy mismo (razon del user): el Supporter del
    turno ya esta gastado, asi que su habilidad no produciria nada y el cuerpo
    solo REGALARIA dos premios en el turno rival. En la mano no cuesta nada.

    Guardas: sin Lillie's/Meowth ya en mano (no hay nada que buscar), sin Meowth
    en juego (el motor ya esta montado; un segundo cuerpo son 2 premios por
    cero), con ambas piezas vivas en el mazo, hueco de banca para mañana y la
    habilidad sin apagar (Watchtower / Iron Thorns)."""
    if not ctx.item_lock_incoming or ctx.itchy_pollen_active:
        return False
    if ctx.meowth_ability_lock or ctx.bench_count >= 5:
        return False
    _h, _f, _cartas = ctx.hand_counts, ctx.field_counts, ctx.cartas_en_mazo
    if (_h.get(Meowth_ex, 0) >= 1 or _h.get(Lillie_Determination, 0) >= 1
            or _f.get(Meowth_ex, 0) >= 1):
        return False
    if (_cartas.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) <= 0
            or _cartas.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) <= 0):
        return False
    return _sin_atacante_para_manana(ctx.my_state, _h, _f)


def _ub_target_score(ctx, _ubf) -> int:
    """Fase D de Ultra Ball (ruta NO cancelada): valora el mejor objetivo de
    busqueda y mapea a tiers de ub_score, con penalizaciones por descartes y
    posible deferral del Supporter. Cuerpo verbatim (Paso 2 del plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    my_prize = ctx.my_prize
    op_prize = ctx.op_prize
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    ko_last_turn = ctx.ko_last_turn
    watchtower_in_play = ctx.meowth_ability_lock
    itchy_pollen_active = ctx.itchy_pollen_active
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_is_cornerstone_deck = ctx.op_is_cornerstone_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    _mega_line_active = ctx.mega_line_active
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _best_supp_in_hand_val = ctx.best_supp_in_hand_val
    _best_supp_in_mazo_val = ctx.best_supp_in_mazo_val
    _win_via_boss_gust = ctx.win_via_boss_gust
    _gust_2prize_via_boss = ctx.gust_2prize_via_boss
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line
    _ub_evolve_needs_search = _ubf.evolve_needs_search
    _ub_evolve_now_search = _ubf.evolve_now_search
    _ub_developed_attacker_board = _ubf.developed_attacker_board
    hand_size = _ubf.hand_size
    ub_score = 10000

    _ub_hand_play_options, _ub_supporters_in_hand = _count_hand_play_options(
        hand_counts, field_counts, bench_count, state.energyAttached)
    _ub_hand_is_weak = (_ub_hand_play_options <= 1 and hand_size <= 4)
    _ub_has_energy_for_teal = hand_counts.get(Basic_Grass_Energy, 0) >= 1

    ub_best_target = _eval_ub_best_target(
        field_counts, hand_counts, meganium_in_play, has_hydrapple,
        forest_in_play, op_has_ex_immune_active, op_has_ex_immune_bench,
        op_prize, bench_count, state, ko_last_turn,
        _best_supp_in_mazo_val, _ub_supporters_in_hand, _ub_hand_is_weak,
        _ub_has_energy_for_teal, we_go_first,
        _best_supp_in_hand_val,
        op_is_crustle_deck, op_is_cornerstone_deck,
        budew_on_op_field and budew_op_index == 0,
        watchtower_in_play,
        op_hand_count=ctx.op_hand_count)

    # Cadena UB -> Meowth ex -> Last-Ditch Catch -> Supporter. `field_counts < 2`
    # NO bastaba: con UN Meowth ex ya en juego la rama PLAY veta el segundo
    # cuerpo, asi que la Ultra Ball cavaba una carta que luego no se jugaba
    # (registro_004 paso 35). Ver `_ub_cavar_meowth_se_juega`.
    if (not _stamp_pendiente(ctx) and
            hand_counts.get(Meowth_ex, 0) == 0 and
            hand_counts.get(Lillie_Determination, 0) == 0 and
            not state.supporterPlayed and
            _ub_cavar_meowth_se_juega(ctx) and
            bench_count < 5 and
            CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):

        if _ub_hand_is_weak or _mega_line_active:
            ub_best_target = max(ub_best_target, 950)
        elif _best_supp_in_mazo_val >= 600:
            ub_best_target = max(ub_best_target, 850)

    # La MISMA cadena, un turno desplazada: con el bloqueo de Items encima el
    # Meowth ex se cava HOY aunque solo pueda bajarse MAÑANA (ver
    # `_ub_meowth_para_manana`). Es la unica rama que no exige que el objetivo
    # se use este turno, porque es la unica en la que guardar la Ultra Ball
    # equivale a tirarla.
    if _ub_meowth_para_manana(ctx):
        ub_best_target = max(ub_best_target, 1100)

    if ub_best_target == 0:
        # NINGUN objetivo que valga la pena en el mazo: la Ultra Ball no aporta
        # nada. SCORE_CANCEL (no SCORE_VETO) por el mismo motivo que las ramas
        # de abajo: con el resto del turno tambien vetado, el desempate por
        # INDICE del menu la jugaba igual en vez de atacar.
        ub_score = SCORE_CANCEL
    else:

        _ub_ns_in_hand = (hand_counts.get(Night_Stretcher, 0) >= 1)

        _ub_meowth_chain = (
            ub_best_target >= 850 and
            not state.supporterPlayed and
            CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
        safe_discards = 0
        for cid, cnt in hand_counts.items():
            if cid == Ultra_Ball:
                continue
            for _ in range(cnt):

                if cid == Basic_Grass_Energy:
                    safe_discards += 1

                elif cid in (Chikorita, Applin, Tapu_Bulu):
                    if field_counts.get(cid, 0) >= 1:
                        safe_discards += 1
                    elif CARTAS_ACTIVAS_EN_MAZO.get(cid, {}).get(ESTADO_MAZO, 0) >= 1:
                        safe_discards += 1
                    elif _ub_ns_in_hand:
                        safe_discards += 1

                elif cid == Forest_of_Vitality and (forest_in_play or cnt > 1):
                    safe_discards += 1
                elif cid == Meganium and meganium_in_play:
                    safe_discards += 1
                elif cid == Bayleef and meganium_in_play:
                    safe_discards += 1
                elif cid == Hydrapple_ex and has_hydrapple and cnt > 1:
                    safe_discards += 1
                elif cid == Meowth_ex and field_counts.get(Meowth_ex, 0) >= 1:
                    safe_discards += 1
                elif cid == Fezandipiti_ex and (field_counts.get(Fezandipiti_ex, 0) >= 1 or not ko_last_turn):
                    safe_discards += 1
                elif cid == Night_Stretcher and cnt > 1:
                    safe_discards += 1
                elif cid == Lanas_Aid and cnt > 1:
                    safe_discards += 1
                elif cid == Lillie_Determination and cnt > 1:
                    safe_discards += 1

                elif cid == Lanas_Aid and cnt == 1 and _ub_meowth_chain:
                    safe_discards += 1

                elif cid == Dipplin:
                    if cnt > 1:
                        safe_discards += 1
                    elif field_counts.get(Applin, 0) == 0:
                        safe_discards += 1

        if (_ub_developed_attacker_board and
                ub_best_target < 800 and
                not _ub_evolve_needs_search):
            # Board ya desarrollado con atacante listo:
            # no gastar Ultra Ball + descartes en un
            # objetivo de desarrollo de bajo valor.
            #
            # SCORE_CANCEL, no SCORE_VETO (user, registro_006 paso 101 vs Mega
            # Lucario ex, PERDIDA): con TODAS las jugadas del turno vetadas
            # (ataque = -1 por defecto) el desempate del argmax es por INDICE
            # del menu, y la Ultra Ball -que aparece antes que el ataque- se
            # jugaba pese a estar vetada aqui mismo. -100 la deja por debajo
            # del piso de veto para que el turno lo cierre el ATAQUE. Es el
            # mismo motivo por el que la salvaguarda de banca llena de
            # `_ub_terminal_overrides` ya usaba SCORE_CANCEL.
            ub_score = SCORE_CANCEL
        elif ub_best_target < 300 and safe_discards < 2:
            ub_score = SCORE_CANCEL
        elif ub_best_target < 250:
            ub_score = SCORE_CANCEL
        elif bench_count >= 5 and not _evolve_possible_in_play:
            # Banca LLENA + NINGUN Pokemon en juego que
            # evolucionar: la Ultra Ball solo llevaria la
            # carta a la MANO (no se puede banquear nada)
            # y no habilita ninguna evolucion, asi que no
            # aporta nada este turno. Se cancela para
            # GUARDAR el recurso para cuando derriben un
            # Pokemon (banca con hueco) o haya algo que
            # evolucionar.
            ub_score = SCORE_VETO
        else:

            if ub_best_target >= 900:
                ub_score = 12500
            elif ub_best_target >= 700:
                ub_score = 12000
            elif ub_best_target >= 500:
                ub_score = 11200
            elif ub_best_target >= 300:
                ub_score = 10500
            else:
                ub_score = 10000

            if safe_discards < 2:
                ub_score -= 600
            elif safe_discards < 3:
                ub_score -= 250

            if _ub_hand_is_weak and ub_best_target >= 650:
                ub_score += 500

            if hand_counts.get(Lillie_Determination, 0) >= 1 and not state.supporterPlayed:
                _ub_enables_evo = (ub_best_target >= 800)
                # Con exactamente 6 premios restantes
                # Lillie's Determination roba 8 cartas:
                # ese refuerzo masivo tiene prioridad,
                # asi que se pospone Ultra Ball aunque
                # habilite una evolucion, para jugar
                # primero Lillie's.
                # EXCEPCION: si la Ultra Ball habilita una
                # evolucion que se puede COMPLETAR este
                # turno (`_ub_evolve_now_search`: pre-evo en
                # mesa evolucionable ya por Forest o por
                # estar desde el inicio del turno, y la
                # pieza en el mazo), NO se degrada: primero
                # se desarrolla la linea de evolucion y
                # Lillie's se juega despues, para no barajar
                # al mazo unas Ultra Ball que este turno
                # habilitaban evoluciones.
                _lillie_draws_8 = (my_prize == 6)
                if ((hand_size < 4 or not _ub_enables_evo
                        or _lillie_draws_8)
                        and not _ub_evolve_now_search):
                    ub_score = 4500

            # No quemar Lillie's Determination como coste
            # de Ultra Ball cuando eso nos dejaria sin mano.
            # Si al pagar el coste (descartar 2 cartas) no
            # quedan al menos 2 cartas distintas de la
            # Lillie's, jugar Ultra Ball obliga a descartar
            # la Lillie's y nos quedamos practicamente sin
            # mano. En ese caso se cancela, salvo que la
            # busqueda sirva para cerrar la partida (tomar
            # los premios que faltan, es decir muy pocos
            # premios restantes).
            if hand_counts.get(Lillie_Determination, 0) >= 1:
                _ub_non_lillie_discardable = 0
                for _ub_lid, _ub_lcnt in hand_counts.items():
                    if _ub_lid in (Ultra_Ball, Lillie_Determination):
                        continue
                    _ub_non_lillie_discardable += _ub_lcnt
                _ub_lillie_forced_discard = (
                    _ub_non_lillie_discardable < 2)
                _ub_winning_search = (
                    my_prize <= 2 or
                    _win_via_boss_gust or
                    _gust_2prize_via_boss)
                if (_ub_lillie_forced_discard
                        and not _ub_winning_search):
                    ub_score = SCORE_VETO

    return ub_score


def _ub_score_before_overrides(ctx, _ubf) -> int:
    """Fases B+C+D de _score_ultra_ball_play: cortes duros tempranos, vetos por
    coste de descarte y valoracion de objetivo. Devuelve ub_score ANTES de los
    overrides terminales (Fase E). Cuerpo verbatim (Paso 2 del plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    my_prize = ctx.my_prize
    op_prize = ctx.op_prize
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    ko_last_turn = ctx.ko_last_turn
    watchtower_in_play = ctx.meowth_ability_lock
    itchy_pollen_active = ctx.itchy_pollen_active
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_is_cornerstone_deck = ctx.op_is_cornerstone_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    _mega_line_active = ctx.mega_line_active
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _best_supp_in_hand_val = ctx.best_supp_in_hand_val
    _best_supp_in_mazo_val = ctx.best_supp_in_mazo_val
    _win_via_boss_gust = ctx.win_via_boss_gust
    _gust_2prize_via_boss = ctx.gust_2prize_via_boss
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line
    _ub_evolve_needs_search = _ubf.evolve_needs_search
    _ub_evolve_now_search = _ubf.evolve_now_search
    _ub_developed_attacker_board = _ubf.developed_attacker_board
    hand_size = _ubf.hand_size
    ub_score = 10000

    if hand_size < 3:
        ub_score = SCORE_VETO
    elif bench_count >= 5 and not _ub_evolve_needs_search:
        # SALVAGUARDA temprana (corte duro): con la banca LLENA
        # y NINGUN Pokemon en juego que se pueda evolucionar CON UNA
        # BUSQUEDA (la pieza de evolucion falta en mano y esta en el
        # mazo), la Ultra Ball no puede banquear nada nuevo y solo
        # llevaria una carta REDUNDANTE a la mano (p.ej. un 2o
        # Meganium cuando ya hay uno en juego), pagando ademas el
        # coste de descartar 2 cartas utiles. Tampoco cuenta si la
        # evolucion YA esta en la mano (esa linea evoluciona sin
        # Ultra Ball). No aporta NADA este turno, asi que se cancela
        # SIEMPRE para guardar el recurso hasta que derriben un
        # Pokemon (hueco en banca) o haya una evolucion que buscar.
        # Independiente de como quede ub_best_target.
        # Se usa un valor CLARAMENTE por debajo del piso de veto (-1) para que,
        # en un turno donde el resto de jugadas tambien esten vetadas (ataque /
        # retirada = -1 y END muy negativo), el argmax NO caiga por defecto en
        # jugar esta Ultra Ball inutil (indice 0). Asi se prefiere atacar / pasar
        # antes que malgastar la Ultra Ball + 2 descartes (user, registro 006
        # paso 72 vs Hops, PERDIDA: banca llena, buscaba un Hydrapple ex que no
        # quedaba en el mazo).
        ub_score = SCORE_CANCEL
    else:

        _ub_cancel_for_stamp = _ub_cancel_stamp(ctx)
        _ub_cancel_for_fez = _ub_cancel_fez(ctx)
        _ub_cancel_for_lillie = _ub_cancel_lillie(ctx)
        _ub_cancel_for_meowth = _ub_cancel_meowth(ctx)
        _ub_cancel_for_xerosic = _ub_cancel_xerosic(ctx)
        if (_ub_cancel_for_stamp or _ub_cancel_for_fez
                or _ub_cancel_for_lillie or _ub_cancel_for_meowth
                or _ub_cancel_for_xerosic):
            ub_score = SCORE_VETO

        if not _ub_cancel_for_meowth and not _ub_cancel_for_stamp and not _ub_cancel_for_fez and not _ub_cancel_for_lillie and not _ub_cancel_for_xerosic:
            ub_score = _ub_target_score(ctx, _ubf)
    return ub_score




def _score_ultra_ball_play(ctx) -> int:
    """Puntua la jugada de Ultra Ball. Orquestador (Paso 2 del plan): compone las
    3 fases ya aisladas. Fase A `_ub_derive_flags` (contexto derivado) -> Fases
    B+C+D `_ub_score_before_overrides` (cortes duros, vetos por coste, valoracion
    de objetivo) -> Fase E `_ub_terminal_overrides` (overrides terminales, SIEMPRE
    al final). Ver docs/main-refactor-ultra-ball-plan.md."""
    # Estrategia vs Comfey (user, registro_005): la Ultra Ball SOLO sirve para
    # buscar Teal Mask Ogerpon ex, y el maximo es 2 en juego. Si ya tenemos 2, la
    # Ultra Ball es inutil -> CANCELAR (por debajo del piso de veto -1 para que el
    # agente ATAQUE/PASE en vez de malgastar la carta y sus 2 descartes).
    if (ctx.op_is_comfey_deck
            and ctx.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2):
        return SCORE_CANCEL
    # Motor UB->Meowth->Lillie's sobre el tier de energia (ver helper): 31450
    # gana al adjunte manual (~31410) y a Ripening Charge sin pivote (30000),
    # y queda BAJO los pivotes de habilidad con KO/retirada (31500-31600).
    # Arma `_ub_engine_pivot_turn` para que el FETCH de esta UB elija Meowth.
    if _ub_engine_refresh_pivot(ctx):
        ESTADO._ub_engine_pivot_turn = True
        return 31450
    # vs Alakazam con la mano rival gorda (Powerful Hand): montar el cap de
    # Xerosic via Ultra Ball -> Meowth ex -> Last-Ditch -> Xerosic (user,
    # registro_008 paso 75, GANADA suboptima: el agente jugaba Lillie's
    # -refresco redundante con Hydrapple ex cargado + 3 atacantes de banca- en
    # vez de cavar la disrupcion). Prioridad de disrupcion en la banda Xerosic
    # (5950): sobre el ataque (que cerraria el turno sin capar Powerful Hand) y
    # sobre Lillie's (que ademas gasta el Supporter del turno), bajo los remates
    # ganadores y el gusteo de 2 premios. Solo cuando hay que CAVAR Meowth (no
    # en mano). Arma `_ub_engine_pivot_turn` para que el FETCH elija Meowth ex y
    # continue la cadena (su Last-Ditch busca Xerosic por `xerosic_alakazam`).
    if (_alakazam_dig_xerosic_engine(ctx)
            and ctx.hand_counts.get(Meowth_ex, 0) == 0):
        ESTADO._ub_engine_pivot_turn = True
        return 5950
    _ubf = _ub_derive_flags(ctx)
    ub_score = _ub_score_before_overrides(ctx, _ubf)
    ub_score = _ub_terminal_overrides(
        ctx, ub_score, _ubf.survival_mode, _ubf.hand_size, _ubf.first_action_turn)
    return ub_score


class _CtxLillie:
    """Wrapper del DecisionContext para las reglas de Lillie's Determination:
    precomputa los derivados que el bloque original calculaba al inicio
    (atacantes ex listos, lineas de evolucion pendientes/evolucionables,
    Hydrapple activo cargado, guarda del Boss's vs Hop's) y delega el resto
    de campos en el ctx via __getattr__."""

    def __init__(self, ctx):
        self.c = ctx
        my_state = ctx.my_state
        hand_counts = ctx.hand_counts
        field_counts = ctx.field_counts
        meganium_in_play = ctx.meganium_in_play
        has_hydrapple = ctx.has_hydrapple
        forest_in_play = ctx.forest_in_play
        _field_at_turn_start = ctx.field_at_turn_start

        self.hand_len = len(my_state.hand or [])

        _ready_ex_attackers = 0
        _lillie_my_pkmn = (
            [my_state.active[0]] if (my_state.active and my_state.active[0] is not None) else [])
        _lillie_my_pkmn += [bp for bp in my_state.bench if bp is not None]
        for _exp in _lillie_my_pkmn:
            _exp_eff = len(_exp.energies) * _grass_mult()
            if _exp.id == Hydrapple_ex and _exp_eff >= 2:
                _ready_ex_attackers += 1
            elif _exp.id == Teal_Mask_Ogerpon_ex and _exp_eff >= 3:
                _ready_ex_attackers += 1
            elif _exp.id == Fezandipiti_ex and _exp_eff >= 3:
                _ready_ex_attackers += 1
        self.ready_ex_attackers = _ready_ex_attackers

        # Piezas de evolucion en mano cuya pre-evolucion YA esta en juego
        # (activo o banca): si barajamos la mano con Lillie's Determination
        # las devolveriamos al mazo y perderiamos la linea de evolucion.
        # Detectamos esa situacion para NO jugar Lillie's hasta completar las
        # evoluciones disponibles.
        _lillie_pending_evo = False
        if not meganium_in_play:
            if (hand_counts.get(Bayleef, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1):
                _lillie_pending_evo = True
            if (hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Bayleef, 0) >= 1):
                _lillie_pending_evo = True
            if (forest_in_play and
                    hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1 and
                    hand_counts.get(Bayleef, 0) >= 1):
                _lillie_pending_evo = True
        if not has_hydrapple:
            if (hand_counts.get(Dipplin, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1):
                _lillie_pending_evo = True
            if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Dipplin, 0) >= 1):
                _lillie_pending_evo = True
            if (forest_in_play and
                    hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1 and
                    hand_counts.get(Dipplin, 0) >= 1):
                _lillie_pending_evo = True
        self.pending_evo = _lillie_pending_evo

        # Linea de evolucion "con HUECO" que Ultra Ball puede completar (user,
        # registro_004 paso 47 vs Alakazam, PERDIDA): tenemos el BASICO en
        # juego y el STAGE-2 en la MANO, pero falta la STAGE-1 intermedia
        # (Bayleef / Dipplin), que esta en el MAZO y se puede BUSCAR con Ultra
        # Ball. Lillie's Determination BARAJA toda la mano al mazo, perdiendo el
        # Stage-2 (Meganium / Hydrapple ex) y la propia Ultra Ball: lo correcto
        # es jugar PRIMERO la Ultra Ball para traer la pieza intermedia y montar
        # la linea (Chikorita->Bayleef->Meganium), y solo despues refrescar. A
        # diferencia de `pending_evo` (evolucion DIRECTA ya en mano), aqui la
        # pieza intermedia falta pero es buscable. Deck-agnostico.
        _lillie_ub_gapped_line = False
        if hand_counts.get(Ultra_Ball, 0) >= 1:
            if (not meganium_in_play
                    and hand_counts.get(Meganium, 0) >= 1
                    and field_counts.get(Chikorita, 0) >= 1
                    and hand_counts.get(Bayleef, 0) == 0
                    and field_counts.get(Bayleef, 0) == 0
                    and ctx.cartas_en_mazo.get(
                        Bayleef, {}).get(ESTADO_MAZO, 0) >= 1):
                _lillie_ub_gapped_line = True
            if (not has_hydrapple
                    and hand_counts.get(Hydrapple_ex, 0) >= 1
                    and field_counts.get(Applin, 0) >= 1
                    and hand_counts.get(Dipplin, 0) == 0
                    and field_counts.get(Dipplin, 0) == 0
                    and ctx.cartas_en_mazo.get(
                        Dipplin, {}).get(ESTADO_MAZO, 0) >= 1):
                _lillie_ub_gapped_line = True
        # ROMPER EL BLOQUEO MUTUO Lillie's <-> Ultra Ball (user, registro_010
        # paso 116 vs Dragapult, PERDIDA). Las dos cartas pueden estar
        # cediendose el paso a la vez:
        #   * esta regla dice "no juegues Lillie's, que barajaria la Ultra Ball
        #     con la que voy a montar la linea";
        #   * y `_ub_cancel_lillie` dice "no juegues la Ultra Ball, que su coste
        #     de descartar 2 se llevaria la Lillie's".
        # Cuando las dos disparan a la vez no se juega NINGUNA de las dos y el
        # Supporter del turno se muere en la mano: en aquel paso la mano era
        # {Ultra Ball x3, Hydrapple ex, Lillie's} y el turno se cerro atacando.
        # La deferencia solo tiene sentido si la Ultra Ball se puede jugar por
        # algo que NO sea esta misma Lillie's, asi que se cede el paso salvo en
        # ese caso circular. Es el mismo fallo -- y la misma forma de romperlo
        # -- que en el par Sello<->Supporter (`_sello_merece_jugarse`: "se cedia
        # el paso a una carta que ya no se iba a jugar").
        #
        # Deliberadamente NO se consulta el score completo de la Ultra Ball: los
        # otros vetos por COSTE son de ESTE INSTANTE y se levantan solos dentro
        # del turno. En el registro_004 paso 47 (el caso que creo esta regla) la
        # Ultra Ball esta en -1 por `_ub_cancel_meowth` -- su coste se llevaria
        # el Meowth ex --, pero el agente baja el Meowth PRIMERO y despues la
        # Ultra Ball ya es jugable: alli guardar la Lillie's es correcto y un
        # gate por score la habria tirado.
        #
        # Y solo se rompe si esta Lillie's es el UNICO Supporter de la mano, que
        # es cuando el bloqueo cuesta algo: con OTRO Supporter en mano el hueco
        # del turno se usa igual, asi que vetar la Lillie's no desperdicia nada
        # y ademas conserva la linea. Es la diferencia entre los dos escenarios:
        # en el paso 116 la mano era {Ultra Ball x3, Hydrapple ex, Lillie's} --
        # sin Supporter de repuesto -- y en el paso 49 vs Marnie hay un Boss's
        # Orders al lado, que es el que se juega.
        _otro_supporter_en_mano = any(
            hand_counts.get(_sid, 0) >= 1
            for _sid in _SUPP_PLAY_IDS if _sid != Lillie_Determination)
        if (_lillie_ub_gapped_line and _ub_cancel_lillie(ctx)
                and not _otro_supporter_en_mano
                and not ctx.state.supporterPlayed):
            _lillie_ub_gapped_line = False
        self.ub_gapped_line = _lillie_ub_gapped_line

        # Podemos EVOLUCIONAR realmente una de esas lineas ESTE turno? Solo
        # cuenta si la pre-evolucion esta AHORA en juego (field_counts) y
        # ademas puede evolucionar ya: o estaba en juego al inicio del turno
        # (_field_at_turn_start, no salio este turno) o hay Forest of
        # Vitality (permite evolucionar el mismo turno). Evita el falso
        # positivo de contar como evolucionable un Pokemon que YA evoluciono
        # este turno.
        _lillie_evolve_now = False
        if not meganium_in_play:
            if (hand_counts.get(Bayleef, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Chikorita, 0) >= 1)):
                _lillie_evolve_now = True
            if (hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Bayleef, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Bayleef, 0) >= 1)):
                _lillie_evolve_now = True
        if not has_hydrapple:
            if (hand_counts.get(Dipplin, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Applin, 0) >= 1)):
                _lillie_evolve_now = True
            if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Dipplin, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Dipplin, 0) >= 1)):
                _lillie_evolve_now = True
        self.evolve_now = _lillie_evolve_now

        # Hydrapple ex CARGADO en el activo (>=2 de Planta efectiva, listo
        # para Syrup Storm): jugar Lillie's Determination tiene prioridad
        # sobre Boss's Orders. Barajar la mano y robar 6-8 busca mas Pokemon
        # y energia para potenciar Syrup Storm (que escala con la energia
        # Planta en juego); Hydrapple conserva su energia (Lillie's solo
        # baraja la MANO) y ataca igual despues.
        self.hydra_active_charged = (
            my_state.active and my_state.active[0] is not None
            and my_state.active[0].id == Hydrapple_ex
            and len(my_state.active[0].energies) * _grass_mult() >= 2)

        # Regla (user, registro 008 paso 84 vs Hops): Boss's Orders es una
        # carta CLAVE vs Hops (permite gustear y noquear a un Hops Phantump /
        # Trevenant que saque CARA y noquee a nuestro activo). Lillie's
        # Determination baraja TODA la mano al mazo (incluido el Boss's), asi
        # que vs Hops, con Boss's en mano, solo se juega Lillie's si el
        # ACTIVO es el UNICO atacante disponible (necesitamos cavar por mas
        # recursos). Con >= 2 atacantes LISTOS (activo + banca) NO se juega
        # Lillie's: se guarda el Boss's en la mano para la respuesta. Si no
        # hay Boss's en mano, Lillie's se puede jugar con normalidad.
        # Generalizacion (user, registro_007 p78 vs Archaludon, GANADA):
        # ademas de vs Hops, GUARDAR el Boss's (vetar Lillie's) cuando el
        # rival tiene en la banca una PRE-EVOLUCION AMENAZA que podemos
        # gustear y NOQUEAR (Duraludon -> Archaludon ex: el atacante real del
        # mazo) y tenemos >= 2 atacantes listos. Lillie's barajaria el Boss's
        # al mazo; con atacantes de sobra no hace falta cavar, y la prioridad
        # es remover el atacante con Boss's. `_boss_ko_threat_preevo` NO se
        # anula por `_active_attack_sufficient`, asi que aplica aunque el
        # activo pudiera atacar al activo rival (p.ej. un Cinderace poco
        # peligroso).
        # ACTIVO CONDENADO SIN RELEVO (user, registro_004 t4 vs Mega Lucario,
        # PERDIDA): guardar el Boss's presupone que habra un turno siguiente
        # con tablero. Si el activo muere seguro el proximo turno
        # (`active_ko_likely` heuristico o `active_doomed_real`, el remate
        # rival leido de attack_table) y NO hay atacante de banca listo, no
        # hay a quien pasarle el relevo: reservar el Boss's condena el turno.
        # Ahi manda CAVAR con Lillie's (roba 6, u 8 con 6 premios) para
        # encontrar atacante/energia. Mismo criterio que `_boss_cede_dig`.
        _lillie_condenado_sin_relevo = (
            (ctx.active_ko_likely or ctx.active_doomed_real)
            and not ctx.has_ready_bench_attacker)
        _hop_keep_boss = False
        if ((ctx.op_is_hop_deck or ctx.boss_ko_threat_preevo)
                and hand_counts.get(Boss_Orders, 0) >= 1
                and not ctx.boss_win_via_bench
                and not _lillie_condenado_sin_relevo):
            _lillie_ready_attackers = 0
            for _lra in _lillie_my_pkmn:
                # Solo ATACANTES REALES (MAIN_ATTACKERS). El conteo por
                # ATTACK_ENERGY_REQ a secas contaba como "atacante listo" a un
                # Chikorita con 1 energia (Growl: 0 de dano) o a un Applin, y
                # con eso el veto se disparaba con un solo atacante de verdad
                # (user, registro_004 t4 vs Mega Lucario, PERDIDA: Ogerpon ex
                # + Chikorita recien bajado = "2 atacantes" -> se guardaba el
                # Boss's y se perdia el refresco). Es el mismo criterio de
                # `has_ready_bench_attacker`.
                if _lra.id not in MAIN_ATTACKERS:
                    continue
                if _can_attack_eff(_lra.id, len(_lra.energies) * _grass_mult()):
                    _lillie_ready_attackers += 1
            if _lillie_ready_attackers >= 2:
                _hop_keep_boss = True
        self.hop_keep_boss = _hop_keep_boss

        # Rama final (mano > 6): version AMPLIA de las lineas pendientes /
        # evolucionables del bloque original (condiciones transcritas fieles;
        # difieren sutilmente de pending_evo/evolve_now de arriba).
        _has_pending_evolutions = False
        if (hand_counts.get(Bayleef, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                not meganium_in_play):
            _has_pending_evolutions = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Bayleef, 0) >= 1 and
                not meganium_in_play):
            _has_pending_evolutions = True
        if (hand_counts.get(Dipplin, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                not has_hydrapple):
            _has_pending_evolutions = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Dipplin, 0) >= 1 and
                not has_hydrapple):
            _has_pending_evolutions = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                forest_in_play and not meganium_in_play and
                hand_counts.get(Bayleef, 0) >= 1):
            _has_pending_evolutions = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                forest_in_play and not has_hydrapple and
                hand_counts.get(Dipplin, 0) >= 1):
            _has_pending_evolutions = True
        self.pending_evo_amplia = _has_pending_evolutions

        # NO usa `_evolvable_counts`: MEDIDO Y REVERTIDO (nota de alcance alli).
        _evolvable_now = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts
        _can_evolve_now = False
        if (hand_counts.get(Bayleef, 0) >= 1 and
                _evolvable_now.get(Chikorita, 0) >= 1 and
                not meganium_in_play):
            _can_evolve_now = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                _evolvable_now.get(Bayleef, 0) >= 1 and
                not meganium_in_play):
            _can_evolve_now = True
        if (hand_counts.get(Dipplin, 0) >= 1 and
                _evolvable_now.get(Applin, 0) >= 1 and
                not has_hydrapple):
            _can_evolve_now = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                _evolvable_now.get(Dipplin, 0) >= 1 and
                not has_hydrapple):
            _can_evolve_now = True
        if forest_in_play:
            if (hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1 and
                    not meganium_in_play and
                    hand_counts.get(Bayleef, 0) >= 1):
                _can_evolve_now = True
            if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1 and
                    not has_hydrapple and
                    hand_counts.get(Dipplin, 0) >= 1):
                _can_evolve_now = True
        self.evolve_now_amplia = _can_evolve_now

    def __getattr__(self, nombre):
        return getattr(self.c, nombre)


_REGLAS_LILLIE_PLAY = [
    # Estrategia vs Comfey (user, registro_005): Lillie's Determination SOLO
    # se juega si tenemos 10 o MAS cartas en la mano. Baraja la mano al mazo,
    # lo que nos DEVUELVE cartas al deck (evita deckearnos por Flower Shower
    # y esquiva el descarte de Xerosic's Machinations). Con menos de 10
    # cartas NO se juega. Con >=10 se deja pasar al scoring normal (positivo).
    _ReglaFija("comfey_mano_corta",
               lambda c: c.op_is_comfey_deck and c.hand_len < 10,
               lambda c: SCORE_VETO),
    # Guardar el Boss's vs Hops / pre-evo amenaza (comentario en _CtxLillie).
    _ReglaFija("hop_guarda_boss",
               lambda c: c.hop_keep_boss,
               lambda c: SCORE_VETO),
    _ReglaFija("mano_gorda_turnos_1_2",
               lambda c: (not c.op_is_comfey_deck
                          and c.state.turn <= 2 and c.hand_len >= 10
                          and not c.our_first_turn),
               lambda c: SCORE_VETO),
    # FRENO DE DECK-OUT (autopsia crustle_kangaskhan jul 2026): en partidas
    # largas vs muro+curacion el motor de robo quema 8-15 cartas por turno y
    # hubo deck-outs REALES (mazo 0 en t20-22). Lillie's baraja la mano al
    # mazo y roba 6: su delta de mazo es (mano - 6). Con el mazo CRITICO
    # (<=10) se veta solo en la franja donde ademas es un refresco de lujo:
    # mano 4-6 (neta negativa/cero y aun hay jugadas). Con mano <=3 (atasco
    # real) sigue siendo la salida; con mano >=7 DEVUELVE cartas al mazo
    # (anti-deck-out) y tambien pasa. Vs Comfey gobierna su propia regla.
    _ReglaFija("freno_deckout_mazo_critico",
               lambda c: (not c.op_is_comfey_deck
                          and getattr(c.my_state, 'deckCount', 60) <= 10
                          and 4 <= c.hand_len < 7),
               lambda c: SCORE_VETO),
    _ReglaFija("supporter_ya_jugado",
               lambda c: c.state.supporterPlayed,
               lambda c: SCORE_VETO),
    # EXCEPCION (user): con Unfair Stamp en mano normalmente se prefiere
    # jugar el Stamp (draw 5 + disrupcion) sobre Lillie's; PERO si el rival
    # tiene 3 o menos cartas en la mano la disrupcion aporta poco y se
    # prefiere Lillie's, asi que este veto solo aplica con la mano rival > 3.
    _ReglaFija("cede_a_unfair_stamp",
               lambda c: (_stamp_pendiente(c)
                          and c.op_hand_count > 3),
               lambda c: SCORE_VETO),
    # Guard (sugerencia 3 anti-Alakazam): Lillie's BARAJARIA el Xerosic que
    # tenemos en mano y ya NO queda forma de re-buscarlo (sin Meowth en mano
    # ni en mazo, o con los 2 Meowth ya en juego y su Last-Ditch gastado).
    # Con la mano rival >= 4 y creciendo, perder el unico acceso al cap de
    # Powerful Hand justo antes de su pico es irrecuperable. Con mano rival
    # >= 6 la escalera ya garantiza Xerosic (6000+) > Lillie's (5800); este
    # veto cubre el hueco 4-5. Si el Xerosic aun es re-buscable, Lillie's
    # sigue su curso normal (decision de diseno previa: Meowth lo re-busca).
    # Con la 2a copia en el mazo (julio 2026) el veto tampoco aplica:
    # barajar la de la mano no pierde el acceso (quedan copias robables).
    _ReglaFija("no_barajar_ultimo_xerosic",
               lambda c: (c.op_is_alakazam_deck
                          and c.hand_counts.get(Xerosic_Machinations, 0) >= 1
                          and c.op_hand_count >= 4
                          and c.cartas_en_mazo.get(
                              Xerosic_Machinations, {}).get(ESTADO_MAZO, 0) == 0
                          and c.hand_counts.get(Meowth_ex, 0) == 0
                          and (c.field_counts.get(Meowth_ex, 0) >= 2
                               or c.cartas_en_mazo.get(
                                   Meowth_ex, {}).get(ESTADO_MAZO, 0) == 0)),
               lambda c: SCORE_VETO),
    _ReglaFija("alakazam_stamp_dos_ex_listos",
               lambda c: (c.op_is_alakazam_deck and
                          c.hand_counts.get(Unfair_Stamp, 0) >= 1 and
                          _sello_merece_jugarse(c.op_hand_count,
                                                c.my_hand_len) and
                          c.ready_ex_attackers >= 2 and
                          c.op_hand_count > 3),
               lambda c: SCORE_VETO),
    # vs Alakazam con la mano rival grande (Powerful Hand): si podemos MONTAR el
    # cap de Xerosic ESTE turno -- Ultra Ball -> Meowth ex -> Last-Ditch busca
    # Xerosic -> jugar Xerosic -- y ya tenemos un atacante LISTO, NO gastar el
    # Supporter del turno en Lillie's (refresco redundante que ademas baraja la
    # Ultra Ball y el Boss's). Reservarlo para Xerosic, que capa el dano de
    # Powerful Hand (20 x carta de su mano). El guard de atacante-listo
    # (Hydrapple ex cargado o un ex de banca listo) evita sacrificar el refresco
    # cuando el tablero es pobre y de verdad hace falta cavar. Va DESPUES de
    # `no_barajar_ultimo_xerosic` (Xerosic ya en mano) y ANTES de
    # `hydra_cargado_sobre_boss` (5800), que era quien jugaba Lillie's aqui.
    # Ver `_alakazam_dig_xerosic_engine`.
    _ReglaFija("alakazam_reserva_supporter_para_xerosic",
               lambda c: (_alakazam_dig_xerosic_engine(c)
                          and (c.hydra_active_charged
                               or c.ready_ex_attackers >= 1)),
               lambda c: SCORE_VETO),
    # Regla (user, log 86025936 paso 11): en NUESTRO primer turno SIEMPRE se
    # juega Lillie's Determination si esta en la mano, por encima de Boss's
    # Orders. Se ignora el veto de mano >= 10 y el veto por prioridad de
    # Boss's. La capa de orden de jugada mantiene Lillie's (tier 0, score
    # 5000) DESPUES de los desarrollos/items de mayor score, asi que se
    # baraja la mano al final del turno.
    _ReglaFija("primer_turno_siempre",
               lambda c: c.our_first_turn,
               lambda c: 5000),
    # PESCA DE REMATE (user, registro_004 paso 49 vs Marnie, PERDIDA): el turno
    # no tiene NINGUN ataque posible -- Teal Mask Ogerpon ex activo con 1 de las
    # 3 energias de Myriad, banca sin cargar y CERO Plantas en mano-- pero el
    # robo de Lillie's (OCHO cartas con los 6 premios intactos) puede traer las
    # 2 que faltan: 10 Plantas vivas en 42 cartas = 63%. Con ellas Myriad pega
    # 360 al Marnie's Grimmsnarl ex (debilidad Planta) y cobra DOS premios.
    # Aqui el refresco NO es "cavar por si acaso": es la unica linea que ataca
    # este turno, asi que ANULA los vetos de orden de mas abajo (la Ultra Ball
    # que completa linea, la cesion a un gusteo ejecutable). Va DESPUES de todos
    # los vetos duros de arriba (Supporter gastado, Sello pendiente, freno de
    # deck-out, guards de Xerosic): esos siguen mandando.
    #
    # El gusteo que se le cede es ademas ACTIVAMENTE malo aqui: Myriad Leaf
    # Shower escala con la energia de AMBOS activos, asi que cambiar un
    # Grimmsnarl ex con 2 energias y debilidad Planta por un Snorunt pelado
    # DEGRADA el remate justo el turno en que se pesca.
    _ReglaFija("pescar_energia_para_remate",
               _pesca_remate_valida,
               lambda c: LILLIE_SCORE_PESCA_REMATE + c.supporter_boost),
    # Prioridad Lillie's > Boss's con Hydrapple ex cargado en el activo.
    # Puntua por ENCIMA del maximo de Boss's que no gana la partida (~5600);
    # se exceptua `_boss_win_via_bench` (gustada letal a la banca) para no
    # perder un remate. EXCEPCION (user, log 86343257 paso 99, PERDIDA vs
    # Hop): si el activo rival es INMUNE por esquiva (Splashing Dodge con
    # cara -> `_boss_dodge_redirect`) NO se puede atacar al activo este
    # turno, asi que potenciar Syrup Storm con Lillie's es inutil; se cede la
    # prioridad a Boss's Orders (5500) para gustear y noquear un objetivo de
    # banca.
    _ReglaFija("hydra_cargado_sobre_boss",
               lambda c: (c.hydra_active_charged and not c.pending_evo
                          and not c.boss_win_via_bench
                          and not (c.boss_dodge_redirect
                                   and c.hand_counts.get(Boss_Orders, 0) >= 1)),
               lambda c: 5800 + c.supporter_boost),
    # No vetar Lillie's cuando el gusteo por `_boss_prize_rank` NO es
    # ejecutable este turno (activo no puede atacar y sin atacante de banca
    # listo). Los remates ejecutables (win_via_bench / dodge) si siguen
    # vetando Lillie's. ADEMAS (user, registro_005 vs Dragapult): un gusteo
    # de DESARROLLO (prize_rank, cortar la linea rival) NO veta Lillie's si
    # ademas del activo NO tenemos un atacante REAL de banca listo
    # (`has_ready_bench_attacker`, que nunca cuenta un Applin); sin segundo
    # atacante conviene CAVAR con Lillie's. Se exceptua la pre-evo AMENAZA
    # (`boss_ko_threat_preevo`, p.ej. Duraludon), que sigue teniendo
    # prioridad de gusteo.
    _ReglaFija("cede_a_boss_ejecutable",
               lambda c: (not c.boss_low_value_gust and
                          c.hand_counts.get(Boss_Orders, 0) >= 1 and
                          ((c.boss_prize_rank >= 1
                            and not c.active_cant_attack
                            and (c.has_ready_bench_attacker
                                 or (c.boss_ko_threat_preevo
                                     # activo CONDENADO sin relevo: el KO de
                                     # premios no veta el refresco (esp. la
                                     # simetria con _boss_cede_dig).
                                     #
                                     # ASIMETRIA CONOCIDA, MEDIDA Y MANTENIDA
                                     # (user, registro_006 paso 78 vs Archaludon
                                     # ex): `_boss_cede_dig` consulta
                                     # `active_ko_likely OR active_doomed_real`
                                     # -- se le anadio el segundo porque el
                                     # primero es CIEGO (`_op_best_damage_vs`
                                     # devuelve siempre 0) -- y esta regla mira
                                     # SOLO `active_ko_likely`. En la ventana
                                     # exacta (sin atacante de banca listo,
                                     # pre-evo AMENAZA gusteable, activo
                                     # condenado solo segun attack_table) las dos
                                     # reglas se ceden el turno la una a la otra
                                     # -- Lillie's a -1 por "Boss's es
                                     # ejecutable" y Boss's a 20 por "cede a
                                     # Lillie's" -- y el slot de Supporter se
                                     # pierde entero.
                                     #
                                     # Cerrar la asimetria (anadir aqui
                                     # `or c.active_doomed_real`) SE MIDIO:
                                     # -0.39 puntos con n=7000 por rama en 4
                                     # matchups (archaludon -0.5, crustle -0.7,
                                     # alakazam -0.5, dragapult +0.3; p=0.40).
                                     # Mecanismo probable del signo: Lillie's
                                     # BARAJA la mano en el mazo, asi que en el
                                     # paso 78 cambiaba un Boss's Orders vivo (y
                                     # el Bayleef de la linea Meganium) por 8
                                     # cartas al azar con el activo muriendose
                                     # igual. Se revierte y se documenta; el
                                     # turno perdido lo rescata ahora el veto de
                                     # ORDEN diferible de Flip the Script, que
                                     # al no haber bloqueador jugable cobra el
                                     # robo de 3 en vez de cerrar atacando.
                                     and not c.active_ko_likely)))
                           or c.boss_win_via_bench or c.boss_dodge_redirect)),
               lambda c: SCORE_VETO),
    _ReglaFija("ogerpon_jugable_primero",
               lambda c: (c.hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
                          c.hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                          c.bench_count < 5),
               lambda c: 4500),
    # Ultra Ball completa la linea de evolucion antes de refrescar (user,
    # registro_004 paso 47 vs Alakazam, PERDIDA): con el basico en juego + el
    # Stage-2 en mano pero la Stage-1 intermedia buscable en el mazo
    # (`ub_gapped_line`), NO se juega Lillie's -- barajaria el Stage-2 y la
    # Ultra Ball. Se conserva la mano para jugar la Ultra Ball (traer Bayleef /
    # Dipplin) y montar la linea; una vez la pieza intermedia esta en juego, el
    # veto `linea_pendiente` (evolucion directa) toma el relevo. Gate hand_len
    # > 4 (con mano minima el valor de robar 6-8 gana) y turn > 2.
    _ReglaFija("ultra_ball_completa_linea",
               lambda c: (c.ub_gapped_line and c.state.turn > 2
                          and c.hand_len > 4),
               lambda c: SCORE_VETO),
    # Tenemos en mano la evolucion (Bayleef/Meganium/Dipplin/Hydrapple ex) de
    # un Pokemon que ya esta en juego. Primero se completan esas evoluciones
    # (que puntuan ~31000-35000) y se juegan los items; Lillie's
    # Determination se pospone para cuando no quede nada mas que evolucionar.
    # Si la pre-evolucion esta en el activo y todavia no se puede evolucionar
    # este turno (se difiere hasta banquearla), se conserva igualmente para
    # NO descartar las piezas al barajar la mano. Corrige el caso en que se
    # jugaba Lillie's con Bayleef+Meganium en mano y se perdia la linea.
    # EXCEPCION 1: con 4 o menos cartas en mano en total, el valor de robar
    # (Lillie's roba 6-8) supera el de conservar la linea, asi que NO se veta
    # y se juega Lillie's.
    # EXCEPCION 2: si NO podemos evolucionar la linea ESTE turno
    # (`_lillie_evolve_now` False, p.ej. Bayleef recien evolucionado sin
    # Forest) Y vamos a ATACAR este turno, NO se veta: atacar dejaria la
    # Lillie's varada en la mano; mejor jugarla ahora (robar 6-8) antes del
    # ataque. "Atacar este turno" incluye tanto el activo actual
    # (`can_attack`) como noquear al activo rival RETIRANDO y promoviendo un
    # atacante de banca listo (`_bdg_retreat_ko`). Solo se conserva la linea
    # si de verdad podemos evolucionarla ya (evolucionar primero) o si NO
    # vamos a cerrar el turno atacando (se guarda para el proximo turno).
    # (user, log 86345042 paso 44, vs Mega Lucario, GANADA): con Hydrapple ex
    # en mano + Dipplin en banca y un atacante de banca que ya noquea al
    # Riolu activo (retirar+promover), el juego jugaba Boss's Orders en un
    # gusteo sin premio en vez de refrescar; ahora `_bdg_retreat_ko`
    # desbloquea Lillie's para buscar mas recursos (p.ej. el Estadio) antes
    # de atacar.
    # EXCEPCION 3 (user, registro 003 paso 36 vs Archaludon ex, GANADA): si
    # NO podemos evolucionar la linea ESTE turno (`_lillie_evolve_now` False)
    # hemos entrado a esta rama por el disyuntor `not (can_attack or
    # _bdg_retreat_ko)`, es decir, el turno seria MUERTO (no evolucionamos,
    # no atacamos, no retiramos-para-noquear). En ese caso conservar unas
    # piezas que igualmente no bajaremos hoy es peor que refrescar: Lillie's
    # roba 6 (u 8 con 6 premios) y abre nuevas opciones de energia/atacante.
    # Solo se mantiene el veto (conservar la linea) cuando SI podemos
    # evolucionar ya (`_lillie_evolve_now`): ahi se evoluciona primero y se
    # difiere Lillie's para no barajar las piezas restantes.
    _ReglaFija("linea_pendiente",
               lambda c: (c.pending_evo and c.state.turn > 2
                          and c.hand_len > 4
                          and (c.evolve_now
                               or not (c.can_attack or c.bdg_retreat_ko))),
               lambda c: 5000 if not c.evolve_now else SCORE_VETO),
    _ReglaFija("refresco_mano_corta",
               lambda c: c.hand_len <= 6,
               lambda c: 5000),
    # Rama final del original (mano > 6): score 5000 salvo que haya piezas
    # pendientes SIN salida este turno. Transcrita fiel aunque su veto exige
    # `hand_len < 7` y esta rama solo se alcanza con mano > 6: es inalcanzable
    # (sub-rama muerta del original, se conserva por fidelidad).
    _ReglaFija("conserva_piezas_sin_salida",
               lambda c: (c.pending_evo_amplia
                          and not c.evolve_now_amplia
                          and c.state.turn > 2
                          and not (c.hand_counts.get(Lanas_Aid, 0) >= 1
                                   and not c.state.supporterPlayed)
                          and c.hand_len < 7),
               lambda c: SCORE_VETO),
    _ReglaFija("refresco_generico",
               lambda c: True,
               lambda c: 5000),
]


def _score_lillie_determination_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Lillie's Determination (baraja la mano y roba 6/8).
    Cuerpo migrado al MOTOR DE REGLAS (fase 4): los derivados viven en
    _CtxLillie y las reglas (con sus comentarios estrategicos) en
    _REGLAS_LILLIE_PLAY; PTCG_DEBUG imprime la traza."""
    return _resolver_con_traza("lillie->play", _REGLAS_LILLIE_PLAY, [],
                               _CtxLillie(ctx), defecto=0)











def _supp_play_score(ctx: DecisionContext, sid: int) -> int:
    """Score REAL de JUGAR el Supporter `sid` con el tablero de `ctx`."""
    if sid == Boss_Orders:
        return _score_boss_orders_play(ctx)
    if sid == Xerosic_Machinations:
        return _score_xerosic_play(ctx)
    if sid == Lillie_Determination:
        return _score_lillie_determination_play(ctx)
    if sid == Dawn:
        return _score_dawn_play(ctx)
    if sid == Lanas_Aid:
        return _score_lanas_aid_play(ctx, 0)
    return 0


def _mejor_supporter_de_mano(ctx: DecisionContext, hand_counts=None):
    """(id, score) del Supporter de la MANO que se llevaria el turno.

    `hand_counts` permite evaluar una mano HIPOTETICA (p.ej. la de despues de
    resolver una busqueda) sin tocar el ctx del turno. Devuelve (None, 0) si
    ningun Supporter de la mano es jugable."""
    _hc = ctx.hand_counts if hand_counts is None else hand_counts
    mejor_id, mejor = None, 0
    for _sid in _SUPP_PLAY_IDS:
        if _hc.get(_sid, 0) < 1:
            continue
        _val = _supp_play_score(ctx, _sid)
        if _val > mejor:
            mejor_id, mejor = _sid, _val
    return mejor_id, mejor


# --- Reglas del fetch de Ultra Ball -> Hydrapple ex -------------------------




_REGLAS_UB_HYDRAPPLE = [
    # Evolucionar el Dipplin activo Y atacar este turno vale mas que el
    # refill de Fezandipiti (1050): prioridad maxima del fetch.
    _ReglaFija("dipplin_evo_ataca",
               lambda c: c.dipplin_evo_atk,
               lambda c: 1200),
    _ReglaFija("dipplin_evolucionable",
               lambda c: c.evolvable.get(Dipplin, 0) >= 1,
               lambda c: 980),
    _ReglaFija("applin_evolucionable_full_linea",
               lambda c: (c.evolvable.get(Applin, 0) >= 1
                          and (ESTADO.forest_in_play
                               or c.hand.get(Forest_of_Vitality, 0) >= 1)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 900),
    _ReglaFija("applin_evolucionable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: 180),
    _ReglaFija("applin_en_campo",
               lambda c: c.campo.get(Applin, 0) >= 1,
               lambda c: 130),
]

_AJUSTES_UB_HYDRAPPLE = [
    _Ajuste("preparar_hydra_prox_turno",
            lambda c, s: (c.campo.get(Dipplin, 0) >= 1 and s < 860
                          and _uh_preparar_hydra_prox_turno(c)),
            lambda c, s: 860),
    # Contra mazos con INMUNIDAD A EX (p.ej. Crustle), Hydrapple ex es un
    # atacante ex que no puede danarlos: carta muerta, cede ante la linea
    # Meganium o los atacantes no-ex. EXCEPCION `evo_doomed_hittable`: si
    # evoluciona al Dipplin activo condenado y el activo rival NO es
    # inmune (Kangaskhan ex), el clamp no aplica (pivote de evolucion y
    # supervivencia: 80 PV -> 330 PV).
    _Ajuste("clamp_ex_muerto_vs_crustle",
            lambda c, s: (not (c.dipplin_evo_atk
                               and not c.op_ex_immune_active)
                          and (ESTADO.op_is_crustle_deck
                               or c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
            lambda c, s: min(s, 40)),
    # Hydrapple ex quedaria muerto este turno (no ataca) y el motor de
    # refresco Meowth ex -> Lillie's esta disponible: cede la busqueda a
    # Meowth ex (1000), que rehace la mano.
    _Ajuste("cede_a_meowth_refresco",
            lambda c, s: c.hydra_dead_prefer_meowth,
            lambda c, s: min(s, 150)),
]

# --- Reglas del fetch de Ultra Ball -> Meowth ex ----------------------------






_REGLAS_UB_MEOWTH = [
    # PRIMER TURNO: la Ultra Ball solo cava Meowth ex para traer Lillie's
    # Determination (user, log 88461779 vs Alakazam, PERDIDA). Si la Lillie's
    # YA esta en la mano no hay nada que buscar (y el veto de jugar Meowth la
    # dejaria muerta en la mano); si NO queda ninguna en el mazo, el fetch de
    # Last-Ditch no traeria el refresco que justifica el gasto. En ambos casos
    # la Ultra Ball busca otra cosa (una linea de evolucion, un atacante). Va
    # PRIMERO: ni el motor de pivote ni el de Boss's vs Crustle levantan esta
    # regla en el primer turno.
    _ReglaFija("primer_turno_solo_para_lillie",
               lambda c: (_um_es_primer_turno(c)
                          and (c.hand.get(Lillie_Determination, 0) >= 1
                               or c.lillie_in_mazo <= 0)),
               lambda c: 10),
    # Team Rocket's Watchtower anula la habilidad de Meowth ex (Pokemon
    # incoloro): no buscarlo con la Ultra Ball.
    _ReglaFija("watchtower_anula_habilidad",
               lambda c: c.watchtower,
               lambda c: 10),
    # BLOQUEO DE ITEMS MAÑANA: la Ultra Ball se jugo EXACTAMENTE para cavar este
    # cuerpo (`_ub_meowth_para_manana`, registro_002 paso 17 vs Dragapult), asi
    # que el fetch tiene que completar la compra. Va POR ENCIMA de
    # `last_ditch_no_produce`: es cierto que hoy la habilidad no produce nada --
    # ese es el punto, el Meowth ex se baja MAÑANA, cuando ya no habra Items
    # para buscarlo y el hueco de Supporter vuelva a estar libre.
    _ReglaFija("bloqueo_de_items_manana",
               lambda c: c.meowth_manana,
               lambda c: 1250),
    # LA LAST-DITCH TIENE QUE PODER PRODUCIR ALGO ESTE TURNO (user,
    # registro_006 pasos 98-104 vs Mega Lucario ex, PERDIDA). Meowth ex vale
    # EXCLUSIVAMENTE por su Last-Ditch Catch -> Supporter; el cuerpo en si es
    # un regalo de 2 premios. Hay dos formas de que la habilidad no produzca
    # nada, y ninguna se comprobaba aqui:
    #   1) `supporter_played`: el Supporter del turno YA se jugo, asi que el
    #      que traiga el fetch se queda muerto en la mano (y la rama PLAY veta
    #      el Meowth por [[no-meowth-si-supporter-ya-jugado]]).
    #   2) `not ld_free`: algun Meowth ex en juego APARECIO ESTE TURNO, asi que
    #      la unica Last-Ditch del turno ya se gasto (ver `_meowth_ld_free` y
    #      `_ub_cavar_meowth_se_juega`).
    # En aquel turno 6 habiamos jugado Lillie's y aun asi la Ultra Ball trajo
    # Meowth ex (1000, ganando a Chikorita/Meganium/Bayleef); el agente encadeno
    # una SEGUNDA Ultra Ball para cavar el otro Meowth ex y termino atacando
    # igual, 4 cartas de mano (Forest, Xerosic, Dipplin, Lana's) por dos cuerpos
    # muertos. Va con los vetos de "la habilidad no funciona" (Watchtower) y por
    # encima de los motores de pivote, que de todas formas exigen el Supporter
    # libre (`_ub_engine_refresh_pivot` / `_alakazam_dig_xerosic_engine`).
    _ReglaFija("last_ditch_no_produce",
               lambda c: c.supporter_played or not c.ld_free,
               lambda c: 10),
    # Con Lillie's YA en mano el fetch de Meowth ex es redundante (su unico
    # proposito es buscar Lillie's); mejor una evolucion util. EXCEPCION:
    # vs Crustle, Meowth ex trae Boss's Orders (gust), no refresco. (user,
    # log 86339167 paso 23, PERDIDA vs Mega Starmie)
    _ReglaFija("lillie_ya_en_mano_redundante",
               lambda c: (c.hand.get(Lillie_Determination, 0) >= 1
                          and not _um_boss_engine_vs_crustle(c)
                          and not ESTADO._ub_engine_pivot_turn),
               lambda c: 10),
    # Motor UB->Meowth->Lillie's (registro_008 paso 58 vs Archaludon,
    # PERDIDA): la Ultra Ball se jugo POR el pivote; el fetch DEBE
    # completar la cadena. Sobre desarrollo (1000-1250) y evoluciones.
    _ReglaFija("engine_pivot_turn",
               lambda c: ESTADO._ub_engine_pivot_turn,
               lambda c: 1300),
    # Unico Pokemon en juego + sin Basico jugable + sin Lillie's en mano:
    # bajar Meowth, buscar Lillie's y refrescar.
    _ReglaFija("develop_unico_pokemon",
               lambda c: c.prefer_meowth_develop,
               lambda c: 1250),
    # La unica evolucion grande (Hydrapple ex sobre Dipplin) quedaria
    # muerta este turno: refrescar con Meowth/Lillie's abre mas opciones.
    _ReglaFija("hydra_muerto_prefiere_meowth",
               lambda c: c.hydra_dead_prefer_meowth,
               lambda c: 1000),
    # La linea Meganium no aporta este turno y no hay atacante listo.
    _ReglaFija("meganium_muerto_prefiere_meowth",
               lambda c: c.mega_dead_prefer_meowth,
               lambda c: 1000),
    # Sin atacante USABLE este turno (ni activo que ataque ni banca
    # subible): el refresco supera a una evolucion sin ataque. >1000 para
    # ganar a un Meganium jugable. (registro_004 paso 29 vs Mega Starmie)
    _ReglaFija("sin_atacante_prefiere_meowth",
               lambda c: c.no_attacker_prefer_meowth,
               lambda c: 1250),
    _ReglaFija("t1_saliendo_segundos",
               lambda c: c.t1_going_second_meowth,
               lambda c: 1200),
    _ReglaFija("t1_saliendo_primeros_no",
               lambda c: c.turno == 1 and ESTADO.we_go_first,
               lambda c: 10),
    _ReglaFija("ya_dos_meowth_en_juego",
               lambda c: c.campo.get(Meowth_ex, 0) >= 2,
               lambda c: 10),
    _ReglaFija("un_meowth_y_activo_ataca",
               lambda c: (c.campo.get(Meowth_ex, 0) >= 1
                          and not c.active_cant_attack),
               lambda c: 10),
    _ReglaFija("banca_llena",
               lambda c: c.bench_count >= 5,
               lambda c: 10),
    # Se cumple una condicion que privilegia a Dipplin: Meowth cede.
    _ReglaFija("cede_a_dipplin_prioritario",
               lambda c: c.dipplin_priority,
               lambda c: 10),
    _ReglaFija("linea_mega_activa_con_lillie",
               lambda c: c.mega_line_active and c.lillie_in_mazo > 0,
               lambda c: 1150),
    _ReglaFija("vs_dragapult_con_lillie",
               lambda c: c.dragapult and c.lillie_in_mazo > 0,
               lambda c: 985),
    _ReglaFija("motor_boss_vs_crustle",
               _um_boss_engine_vs_crustle,
               lambda c: 1100),
    # Sin condicion que privilegie a Dipplin: Meowth ex tiene PRIORIDAD
    # para refrescar (buscar Lillie's), sin importar la mano.
    _ReglaFija("lillie_en_mazo_refresco",
               lambda c: c.lillie_in_mazo > 0,
               lambda c: 1000),
    # Otro supporter en el mazo: refrescar igualmente.
    _ReglaFija("otro_supporter_en_mazo",
               lambda c: c.any_supp_in_mazo,
               lambda c: 850),
]

# --- Reglas del fetch de Ultra Ball: ramas restantes ------------------------
# Ctx COMPARTIDO por las ramas Ogerpon/Meganium/Bayleef/Dipplin/Chikorita/
# Applin/Tapu/Pinsir/Fezandipiti. Los globals por turno (meganium_in_play,
# forest_in_play, op_is_crustle_deck, op_is_cornerstone_deck, ko_last_turn,
# CARTAS_ACTIVAS_EN_MAZO) se leen al vuelo desde los lambdas (agent() los
# declara `global`).





_REGLAS_UB_OGERPON = [
    # Cede la busqueda a Meowth ex (refresco de mano): solo se traeria
    # Ogerpon ex aqui si YA tuvieramos Lillie's en la mano.
    _ReglaFija("cede_a_meowth_develop",
               lambda c: c.prefer_meowth_develop,
               lambda c: 200),
    _ReglaFija("t1_segundos_necesita_ogerpon",
               lambda c: c.t1_going_second_need_ogerpon,
               lambda c: 1050),
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_ogerpon_t1_primeros),
    _ReglaFija("ya_dos_ogerpon",
               lambda c: c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 2,
               lambda c: 350 if (c.has_energy_for_teal
                                 and c.bench_count < 5) else 15),
    _ReglaFija("energia_para_teal_dance",
               lambda c: c.has_energy_for_teal and c.bench_count < 5,
               _v_ub_ogerpon_teal),
    _ReglaFija("primer_ogerpon_banca_corta",
               lambda c: (c.campo.get(Teal_Mask_Ogerpon_ex, 0) == 0
                          and c.bench_count <= 2),
               lambda c: 300),
]

_REGLAS_UB_MEGANIUM = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 25),
    # vs Cornerstone: Wild Growth duplica cada Planta y baja el coste de
    # Tapu Bulu -- el UNICO atacante que dana a Cornerstone -- de 4 Plantas
    # fisicas a 2. Con la linea ya iniciada en juego, completarla es la
    # busqueda prioritaria aunque Meganium en si no pueda danarlo.
    _ReglaFija("linea_mega_habilita_tapu_vs_cornerstone",
               lambda c: (ESTADO.op_is_cornerstone_deck
                          and (c.campo.get(Chikorita, 0) >= 1
                               or c.campo.get(Bayleef, 0) >= 1)),
               lambda c: 1050),
    _ReglaFija("bayleef_evolucionable",
               lambda c: c.evolvable.get(Bayleef, 0) >= 1,
               lambda c: 1000),
    _ReglaFija("cadena_chikorita_completa",
               lambda c: (c.evolvable.get(Chikorita, 0) >= 1
                          and _forest_disponible(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 950),
    _ReglaFija("chikorita_evolucionable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 200),
    _ReglaFija("chikorita_en_campo",
               lambda c: c.campo.get(Chikorita, 0) >= 1,
               lambda c: 150),
]

_REGLAS_UB_BAYLEEF = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 20),
    _ReglaFija("bayleef_ya_en_campo",
               lambda c: c.campo.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # Ya hay un Bayleef EN LA MANO: buscar otro es redundante (uno basta
    # para la unica Chikorita); no malgastar la UB ni su descarte.
    _ReglaFija("bayleef_ya_en_mano",
               lambda c: c.hand.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # vs Cornerstone, Bayleef es el paso intermedio hacia Meganium (que
    # duplica la Planta y deja a Tapu Bulu atacando con 2 fisicas) y ademas
    # es uno de los dos cuerpos SIN habilidad que si le hacen dano.
    _ReglaFija("linea_mega_vs_cornerstone",
               lambda c: (ESTADO.op_is_cornerstone_deck
                          and c.campo.get(Chikorita, 0) >= 1),
               lambda c: 1000),
    _ReglaFija("chikorita_evolucionable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 950 if (c.hand.get(Meganium, 0) >= 1
                                 and ESTADO.forest_in_play) else 850),
    _ReglaFija("chikorita_en_campo",
               lambda c: c.campo.get(Chikorita, 0) >= 1,
               lambda c: 200),
]

_REGLAS_UB_DIPPLIN = [
    _ReglaFija("hydrapple_ya_en_juego",
               lambda c: c.has_hydrapple,
               lambda c: 20),
    _ReglaFija("dipplin_ya_en_campo",
               lambda c: c.campo.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Mismo criterio que Bayleef: duplicado redundante.
    _ReglaFija("dipplin_ya_en_mano",
               lambda c: c.hand.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Solo se privilegia a Dipplin con _dipplin_priority; si no, Meowth ex
    # refresca mejor y Dipplin baja para no robarle la busqueda.
    _ReglaFija("applin_evolucionable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: ((920 if (c.hand.get(Hydrapple_ex, 0) >= 1
                                   and ESTADO.forest_in_play) else 800)
                          if c.dipplin_priority else 150)),
    _ReglaFija("applin_en_campo",
               lambda c: c.campo.get(Applin, 0) >= 1,
               lambda c: 200),
    _ReglaFija("rival_anti_ex",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 600 if c.evolvable.get(Applin, 0) >= 1 else 150),
]



_REGLAS_UB_CHIKORITA = [
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_chikorita_t1),
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 30),
    _ReglaFija("linea_meganium_ya_iniciada",
               lambda c: (c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0)) > 0,
               lambda c: 150),
    _ReglaFija("arrancar_linea_meganium",
               lambda c: True,
               _v_ub_chikorita_arrancar),
]



_REGLAS_UB_APPLIN = [
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_applin_t1),
    _ReglaFija("hydrapple_ya_en_juego",
               lambda c: c.has_hydrapple,
               lambda c: 25),
    _ReglaFija("linea_hydra_ya_iniciada",
               lambda c: (c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0)
                          + c.campo.get(Hydrapple_ex, 0)) > 0,
               lambda c: 120),
    _ReglaFija("arrancar_linea_hydra",
               lambda c: True,
               _v_ub_applin_arrancar),
]

_REGLAS_UB_TAPU = [
    _ReglaFija("tapu_ya_en_campo",
               lambda c: c.campo.get(Tapu_Bulu, 0) >= 1,
               lambda c: 15),
    # Atacante no-ex contra rivales inmunes a ex, con Meganium duplicando
    # su energia; mejor aun si Hydrapple ex ya cubre el rol ex.
    _ReglaFija("anti_ex_con_meganium",
               lambda c: (ESTADO.meganium_in_play
                          and (c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
               lambda c: 850 if c.has_hydrapple else 750),
]

_REGLAS_UB_PINSIR = [
    _ReglaFija("anti_ex",
               lambda c: (c.campo.get(Pinsir, 0) == 0
                          and (ESTADO.op_is_crustle_deck
                               or ESTADO.op_is_cornerstone_deck)),
               lambda c: 900),
]

_REGLAS_UB_FEZ = [
    # Refill tras KO con Flip the Script (Fezandipiti ex de banca roba 3 al
    # noquearnos). Es buena busqueda SI ya tenemos un atacante usable o si el
    # motor Meowth ex -> Last-Ditch -> Lillie's NO esta disponible. Pero si NO
    # hay atacante usable y AUN queda Meowth ex + Lillie's en el mazo (motor de
    # refresco intacto, `no_attacker_prefer_meowth`), es preferible traer Meowth
    # ex: bajarlo busca Lillie's y rehace TODA la mano (hasta 8 cartas), abriendo
    # muchas mas opciones que el robo de 3 de Fezandipiti (user). Fez cede y su
    # rama cae al defecto (10); Meowth ex (`sin_atacante_prefiere_meowth`=1250 u
    # otras ramas de refresco) gana la busqueda. Deck-agnostico.
    _ReglaFija("refill_tras_ko",
               lambda c: (c.campo.get(Fezandipiti_ex, 0) == 0
                          and ESTADO.ko_last_turn and c.bench_count < 5
                          and not c.no_attacker_prefer_meowth),
               lambda c: 1050),
]

# --- Reglas de la recuperacion de Night Stretcher ---------------------------
# Un solo ctx para las 12 ramas. `evolvable_ns` replica la foto de inicio de
# turno del bloque original (_field_at_turn_start si no hay Forest). Los
# post-ajustes transversales (bonus por copias agotadas/premiadas y el veto
# de whitelist vs Crustle/Cornerstone) se quedan inline: aplican a todas las
# cartas por igual.




def _sin_atacante_para_manana(my_state, hand_counts, field_counts) -> bool:
    """True si NINGUN cuerpo nuestro llegara a atacar el turno QUE VIENE.

    Mira un turno MAS ALLA que `_sin_ataque_hoy`: sobre los cuerpos que YA estan
    en juego cuenta el adjunte del proximo turno (una Planta mas, en unidades
    EFECTIVAS) y las evoluciones que la mano puede completar sobre una pre-evo
    en mesa (la evolucion hereda la energia del cuerpo). No cuenta los Basicos
    de la mano: un Tapu Bulu recien bajado necesita 4 energias, no una.

    Solo cuentan los `MAIN_ATTACKERS` -- un Chikorita que pega 10 no es "empezar
    a atacar", y confundirlos es justo lo que hizo perder el turno del
    registro_002 paso 17 vs Dragapult.

    CONSERVADORA por diseño: ante la duda devuelve False ("si tenemos atacante"),
    porque quien la consulta la usa para justificar gastar recursos."""
    unidad = _grass_attach_unit()
    for _cuerpo in ((my_state.active or []) + (my_state.bench or [])):
        if _cuerpo is None or _cuerpo.id not in MAIN_ATTACKERS:
            continue
        if _can_attack_eff(_cuerpo.id, len(_cuerpo.energies) + unidad):
            return False
    for _pre, _evo in ((Applin, Dipplin), (Dipplin, Hydrapple_ex),
                       (Chikorita, Bayleef), (Bayleef, Meganium)):
        if (hand_counts.get(_evo, 0) >= 1
                and field_counts.get(_pre, 0) >= 1
                and _evo in MAIN_ATTACKERS):
            return False
    return True





_REGLAS_NS_GRASS = [
    # La Planta que REMATA (Syrup Storm letal ESTE turno) gana a cualquier otra
    # recuperacion, incluidas las evoluciones (registro_006 paso 68 vs Mega
    # Abomasnow ex): un premio hoy vale mas que desarrollo para manana.
    _ReglaFija("planta_remata_syrup_storm",
               lambda c: c.grass_enables_syrup_ko,
               lambda c: 1400),
    # Hydrapple ex ACTIVO sin ataque: cargarlo con Ripening Charge GANA
    # sobre cualquier otro objetivo de recuperacion.
    _ReglaFija("hydrapple_activo_ripening",
               lambda c: c.act_hyd_ripen,
               lambda c: 1300),
    _ReglaFija("cargar_banca_vs_crustle",
               lambda c: c.ns_bench_charge,
               lambda c: 950),
    _ReglaFija("activo_necesita_energia",
               lambda c: (c.active_needs_energy
                          and c.hand.get(Basic_Grass_Energy, 0) == 0
                          and not c.energy_attached),
               lambda c: 900),
    _ReglaFija("ogerpon_teal_habilita",
               lambda c: c.act_og_can_teal_attack,
               lambda c: 900),
    _ReglaFija("sin_planta_en_mano",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) == 0,
               _v_ns_grass_sin_planta),
    _ReglaFija("hydra_con_pocas_planta",
               lambda c: c.has_hydrapple and c.total_grass < 4,
               lambda c: 450),
    _ReglaFija("exceso_planta_en_mano",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) >= 3,
               lambda c: 100),
]

# --- Motor de ROBO en un turno muerto ---------------------------------------
# (user, registro_008 paso 67 vs Alakazam, PERDIDA). Con el turno MUERTO en
# ataque (`turno_muerto`) y la mano seca (`mano_agotada`), la recuperacion tiene
# que traer el cuerpo que REHACE LA MANO, no desarrollo:
#   1º Meowth ex   -> al bajarlo, Last-Ditch Catch busca un Supporter del mazo
#                     (Lillie's Determination rehace la mano ENTERA).
#   2º Fezandipiti ex -> Flip the Script roba 3, pero SOLO si nos noquearon un
#                     Pokemon en el turno anterior; si no, su habilidad no
#                     existe y el cuerpo de 2 premios es un regalo.
# En el registro se recupero un Meganium (990 por `bayleef_evolucionable`) sobre
# el Meowth ex que acababan de noquearnos: el Meganium no tenia energia, no
# atacaba, y nos quedamos con 0 cartas en mano y sin atacante. Los scores van
# por encima de TODO el desarrollo (990 + 200 del bonus por ultima copia = 1190)
# y por debajo de la energia que produce un ataque HOY (1300/1400), que nunca
# coexiste con `turno_muerto`. Deck-agnostico: el turno muerto se mide sobre
# `ATTACK_ENERGY_REQ`, no sobre una lista de matchups.





_REGLAS_NS_FEZ = [
    # Segunda opcion del motor: cede al Meowth ex (1250), que rehace la mano
    # entera via Lillie's en vez de robar 3. Se respeta el veto vs Lucario
    # (golpea banca: un ex de 2 premios ahi es un premio regalado).
    _ReglaFija("motor_de_robo_turno_muerto",
               lambda c: (c.turno_muerto and c.mano_agotada
                          and not c.op_is_lucario
                          and _ns_motor_fez_vivo(c)),
               lambda c: 1200),
    _ReglaFija("refill_tras_ko",
               lambda c: (c.campo.get(Fezandipiti_ex, 0) == 0
                          and ESTADO.ko_last_turn and c.bench_count < 5),
               lambda c: 850),
    # vs Lucario (golpea banca): Fez solo como cuerpo de emergencia con
    # banca vacia; si no, vetado.
    _ReglaFija("vs_lucario",
               lambda c: c.op_is_lucario,
               lambda c: (200 if (c.campo.get(Fezandipiti_ex, 0) == 0
                                  and c.bench_count == 0) else SCORE_VETO)),
    _ReglaFija("primer_fez",
               lambda c: c.campo.get(Fezandipiti_ex, 0) == 0,
               lambda c: 200),
]


_REGLAS_NS_CHIKORITA = [
    _ReglaFija("arrancar_linea_meganium",
               lambda c: (not ESTADO.meganium_in_play
                          and (c.campo.get(Chikorita, 0)
                               + c.campo.get(Bayleef, 0)
                               + c.campo.get(Meganium, 0)) == 0),
               _v_ns_chikorita_arrancar),
]


_REGLAS_NS_APPLIN = [
    _ReglaFija("hydrapple_ya_en_juego",
               lambda c: c.has_hydrapple,
               lambda c: 35),
    _ReglaFija("arrancar_linea_hydra",
               lambda c: (c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0)
                          + c.campo.get(Hydrapple_ex, 0)) == 0,
               _v_ns_applin_arrancar),
    _ReglaFija("banca_corta",
               lambda c: c.bench_count <= 1,
               lambda c: 350),
]


_REGLAS_NS_OGERPON = [
    _ReglaFija("menos_de_dos_ogerpon",
               lambda c: c.campo.get(Teal_Mask_Ogerpon_ex, 0) < 2,
               _v_ns_ogerpon_pocos),
    # 3er Ogerpon como acelerador de Syrup Storm (Teal Dance suma Grass).
    _ReglaFija("tercer_ogerpon_para_syrup",
               lambda c: (c.bench_count < 5
                          and c.hand.get(Basic_Grass_Energy, 0) >= 1
                          and c.campo.get(Hydrapple_ex, 0) >= 1),
               lambda c: 500),
]

_REGLAS_NS_TAPU = [
    # vs Dragapult con el tablero hecho no se puede BAJAR: no se recupera.
    _ReglaFija("dragapult_no_lo_baja",
               lambda c: c.dragapult_no_tapu,
               lambda c: SCORE_VETO),
    _ReglaFija("tapu_ya_en_campo",
               lambda c: c.campo.get(Tapu_Bulu, 0) >= 1,
               lambda c: 15),
    _ReglaFija("anti_ex_con_meganium",
               lambda c: (ESTADO.meganium_in_play
                          and (c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
               lambda c: 800 if c.has_hydrapple else 700),
    _ReglaFija("anti_ex",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 350),
]

_REGLAS_NS_PINSIR = [
    _ReglaFija("anti_ex",
               lambda c: (c.campo.get(Pinsir, 0) == 0
                          and (ESTADO.op_is_crustle_deck
                               or ESTADO.op_is_cornerstone_deck)),
               lambda c: 850),
]


_REGLAS_NS_MEOWTH = [
    _ReglaFija("t1_saliendo_primeros_no",
               lambda c: c.turno == 1 and ESTADO.we_go_first,
               lambda c: 10),
    # Primera opcion del motor de robo en un turno muerto: gana a TODO el
    # desarrollo (ver el bloque de comentarios sobre _ns_motor_meowth_vivo).
    _ReglaFija("motor_de_robo_turno_muerto",
               lambda c: (c.turno_muerto and c.mano_agotada
                          and _ns_motor_meowth_vivo(c)),
               lambda c: 1250),
    # Recuperar Meowth ex para bajarlo y que Last-Ditch busque un Supporter
    # del mazo que supere lo que hay en mano.
    _ReglaFija("fetch_supporter_del_mazo",
               lambda c: (not c.watchtower
                          and c.campo.get(Meowth_ex, 0) == 0
                          and c.bench_count < 5
                          and not c.supporter_played
                          and c.best_supp_hand_val < 500
                          and c.best_supp_mazo_val >= 400),
               _v_ns_meowth_fetch),
]

_REGLAS_NS_HYDRAPPLE = [
    # Rescate del Dipplin condenado por el snipe: gana a la energia (<=950) y a
    # todo el desarrollo. Ver `ns_evo_saves_doomed` en `_ctx_ns_fetch`.
    _ReglaFija("salvar_dipplin_condenado_snipe",
               lambda c: c.ns_evo_saves_doomed,
               lambda c: 1200),
    _ReglaFija("dipplin_evolucionable",
               lambda c: (c.evolvable_ns.get(Dipplin, 0) >= 1
                          and not c.has_hydrapple),
               lambda c: 980),
    _ReglaFija("cadena_applin_dipplin_mano",
               lambda c: (c.campo.get(Applin, 0) >= 1
                          and c.hand.get(Dipplin, 0) >= 1
                          and ESTADO.forest_in_play and not c.has_hydrapple),
               lambda c: 960),
]

_REGLAS_NS_MEGANIUM = [
    _ReglaFija("bayleef_evolucionable",
               lambda c: (c.evolvable_ns.get(Bayleef, 0) >= 1
                          and not ESTADO.meganium_in_play),
               lambda c: 990),
    _ReglaFija("cadena_chikorita_bayleef_mano",
               lambda c: (c.campo.get(Chikorita, 0) >= 1
                          and c.hand.get(Bayleef, 0) >= 1
                          and ESTADO.forest_in_play and not ESTADO.meganium_in_play),
               lambda c: 975),
]

_REGLAS_NS_DIPPLIN = [
    _ReglaFija("combo_applin_hydra_en_mano",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and c.hand.get(Hydrapple_ex, 0) >= 1
                          and ESTADO.forest_in_play and c.bench_count < 5),
               lambda c: 970),
    _ReglaFija("applin_en_mano_con_forest",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and ESTADO.forest_in_play and c.bench_count < 5),
               lambda c: 880),
    _ReglaFija("applin_evolucionable",
               lambda c: (c.evolvable_ns.get(Applin, 0) >= 1
                          and not c.has_hydrapple),
               lambda c: 850),
]

# --- Reglas del fetch TO_HAND de Bug Catching Set ---------------------------
# Dispatch por TABLA (mismo patron que el fetch de Night Stretcher): reutiliza
# _CtxNS (hand/campo/bench/flags); los globals por turno (meganium_in_play,
# forest_in_play, ko_last_turn, op_is_crustle_deck, op_is_cornerstone_deck) se
# leen al vuelo desde los lambdas. El bonus por copias premiadas se conserva
# inline en el call site (post-ajuste transversal).

_REGLAS_BCS_CHIKORITA = [
    # Arrancar la linea de Meganium desde cero; con Forest y la evolucion en
    # mano, el rush de evolucion sube la prioridad.
    _ReglaFija("linea_desde_cero_rush",
               lambda c: (not ESTADO.meganium_in_play
                          and c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0) == 0
                          and ESTADO.forest_in_play
                          and (c.hand.get(Bayleef, 0) >= 1
                               or c.hand.get(Meganium, 0) >= 1)),
               lambda c: 950),
    _ReglaFija("linea_desde_cero",
               lambda c: (not ESTADO.meganium_in_play
                          and c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0) == 0),
               lambda c: 800),
]

_REGLAS_BCS_BAYLEEF = [
    _ReglaFija("evo_inmediata_rush",
               lambda c: (not ESTADO.meganium_in_play
                          and c.campo.get(Chikorita, 0) >= 1
                          and ESTADO.forest_in_play
                          and c.hand.get(Meganium, 0) >= 1),
               lambda c: 950),
    _ReglaFija("evo_inmediata",
               lambda c: (not ESTADO.meganium_in_play
                          and c.campo.get(Chikorita, 0) >= 1),
               lambda c: 850),
    _ReglaFija("chikorita_en_mano",
               lambda c: (not ESTADO.meganium_in_play
                          and c.hand.get(Chikorita, 0) >= 1),
               lambda c: 700),
    _ReglaFija("sin_linea_en_juego",
               lambda c: not ESTADO.meganium_in_play,
               lambda c: 400),
]

_REGLAS_BCS_MEGANIUM = [
    _ReglaFija("evo_inmediata",
               lambda c: (not ESTADO.meganium_in_play
                          and c.campo.get(Bayleef, 0) >= 1),
               lambda c: 1000),
    _ReglaFija("rush_desde_chikorita",
               lambda c: (not ESTADO.meganium_in_play
                          and c.campo.get(Chikorita, 0) >= 1
                          and ESTADO.forest_in_play),
               lambda c: 900),
    _ReglaFija("sin_linea_en_juego",
               lambda c: not ESTADO.meganium_in_play,
               lambda c: 500),
]

_REGLAS_BCS_APPLIN = [
    _ReglaFija("linea_desde_cero_rush",
               lambda c: (not c.has_hydrapple
                          and c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0)
                          + c.campo.get(Hydrapple_ex, 0) == 0
                          and ESTADO.forest_in_play
                          and (c.hand.get(Dipplin, 0) >= 1
                               or c.hand.get(Hydrapple_ex, 0) >= 1)),
               lambda c: 850),
    _ReglaFija("linea_desde_cero",
               lambda c: (not c.has_hydrapple
                          and c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0)
                          + c.campo.get(Hydrapple_ex, 0) == 0),
               lambda c: 700),
    _ReglaFija("sin_hydrapple",
               lambda c: not c.has_hydrapple,
               lambda c: 200),
]

_REGLAS_BCS_DIPPLIN = [
    _ReglaFija("evo_inmediata_rush",
               lambda c: (not c.has_hydrapple
                          and c.campo.get(Applin, 0) >= 1
                          and ESTADO.forest_in_play
                          and c.hand.get(Hydrapple_ex, 0) >= 1),
               lambda c: 900),
    _ReglaFija("evo_inmediata",
               lambda c: (not c.has_hydrapple
                          and c.campo.get(Applin, 0) >= 1),
               lambda c: 800),
    _ReglaFija("applin_en_mano",
               lambda c: (not c.has_hydrapple
                          and c.hand.get(Applin, 0) >= 1),
               lambda c: 650),
    # Atacante no-ex util contra los muros con proteccion-ex.
    _ReglaFija("vs_muro_anti_ex",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 600),
    _ReglaFija("sin_hydrapple",
               lambda c: not c.has_hydrapple,
               lambda c: 350),
]

_REGLAS_BCS_HYDRAPPLE = [
    _ReglaFija("evo_inmediata",
               lambda c: (not c.has_hydrapple
                          and c.campo.get(Dipplin, 0) >= 1),
               lambda c: 950),
    _ReglaFija("rush_desde_applin",
               lambda c: (not c.has_hydrapple
                          and c.campo.get(Applin, 0) >= 1
                          and ESTADO.forest_in_play),
               lambda c: 850),
    _ReglaFija("sin_hydrapple",
               lambda c: not c.has_hydrapple,
               lambda c: 400),
]

_REGLAS_BCS_OGERPON = [
    # Hasta 2 Ogerpon en juego; con la banca corta, +100 (cuerpo temprano).
    _ReglaFija("menos_de_dos",
               lambda c: c.campo.get(Teal_Mask_Ogerpon_ex, 0) < 2,
               lambda c: 700 if c.bench_count <= 2 else 600),
    # 3er Ogerpon como acelerador de Syrup Storm (Teal Dance suma Grass).
    _ReglaFija("acelerador_syrup",
               lambda c: (c.bench_count < 5 and
                          c.hand.get(Basic_Grass_Energy, 0) >= 1 and
                          c.campo.get(Hydrapple_ex, 0) >= 1),
               lambda c: 550),
]

_REGLAS_BCS_TAPU = [
    # vs Dragapult con el tablero hecho no se puede BAJAR: no se busca.
    _ReglaFija("dragapult_no_lo_baja",
               lambda c: c.dragapult_no_tapu,
               lambda c: SCORE_VETO),
    _ReglaFija("anti_muro_con_meganium_e_hydra",
               lambda c: (c.campo.get(Tapu_Bulu, 0) == 0
                          and ESTADO.meganium_in_play
                          and (c.op_ex_immune_active or c.op_ex_immune_bench)
                          and c.has_hydrapple),
               lambda c: 700),
    _ReglaFija("anti_muro_con_meganium",
               lambda c: (c.campo.get(Tapu_Bulu, 0) == 0
                          and ESTADO.meganium_in_play
                          and (c.op_ex_immune_active or c.op_ex_immune_bench)),
               lambda c: 600),
    _ReglaFija("primer_tapu",
               lambda c: c.campo.get(Tapu_Bulu, 0) == 0,
               lambda c: 50),
]

_REGLAS_BCS_PINSIR = [
    _ReglaFija("anti_muro",
               lambda c: (c.campo.get(Pinsir, 0) == 0 and
                          (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck)),
               lambda c: 750),
]

_REGLAS_BCS_MEOWTH = [
    # Motor de Supporters: solo si Last-Ditch va a rendir (sin Watchtower,
    # Supporter libre, la mano floja y un Supporter valioso en el mazo).
    _ReglaFija("motor_supporter",
               lambda c: (not c.watchtower and
                          c.campo.get(Meowth_ex, 0) == 0
                          and not c.supporter_played and
                          c.best_supp_hand_val < 500
                          and c.best_supp_mazo_val >= 400),
               lambda c: min(500, c.best_supp_mazo_val - 100)),
]

_REGLAS_BCS_FEZ = [
    _ReglaFija("lucario_responde",
               lambda c: (c.op_is_lucario
                          and c.campo.get(Fezandipiti_ex, 0) == 0 and
                          (ESTADO.ko_last_turn or c.bench_count == 0)),
               lambda c: 650),
    # vs Mega Lucario, fuera del arranque/respuesta se RESERVA (debil a Lucha).
    _ReglaFija("lucario_reserva",
               lambda c: c.op_is_lucario,
               lambda c: SCORE_VETO),
    _ReglaFija("tras_ko",
               lambda c: (c.campo.get(Fezandipiti_ex, 0) == 0
                          and ESTADO.ko_last_turn),
               lambda c: 650),
]

_REGLAS_BCS_GRASS = [
    _ReglaFija("sobran_plantas",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) >= 3,
               lambda c: 150),
    _ReglaFija("sin_planta_y_sin_adjunte",
               lambda c: (c.hand.get(Basic_Grass_Energy, 0) == 0
                          and not c.energy_attached),
               lambda c: 650),
    _ReglaFija("sin_planta",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) == 0,
               lambda c: 550),
    _ReglaFija("con_hydrapple",
               lambda c: c.has_hydrapple,
               lambda c: 400),
]

_TABLA_BCS_FETCH = {
    Chikorita: ("bcs->chikorita", _REGLAS_BCS_CHIKORITA, 50),
    Bayleef: ("bcs->bayleef", _REGLAS_BCS_BAYLEEF, 30),
    Meganium: ("bcs->meganium", _REGLAS_BCS_MEGANIUM, 20),
    Applin: ("bcs->applin", _REGLAS_BCS_APPLIN, 40),
    Dipplin: ("bcs->dipplin", _REGLAS_BCS_DIPPLIN, 30),
    Hydrapple_ex: ("bcs->hydrapple", _REGLAS_BCS_HYDRAPPLE, 25),
    Teal_Mask_Ogerpon_ex: ("bcs->ogerpon", _REGLAS_BCS_OGERPON, 20),
    Tapu_Bulu: ("bcs->tapu", _REGLAS_BCS_TAPU, 20),
    Pinsir: ("bcs->pinsir", _REGLAS_BCS_PINSIR, 20),
    Meowth_ex: ("bcs->meowth", _REGLAS_BCS_MEOWTH, 15),
    Fezandipiti_ex: ("bcs->fez", _REGLAS_BCS_FEZ, 10),
    Basic_Grass_Energy: ("bcs->grass", _REGLAS_BCS_GRASS, 350),
}

# --- Reglas del fetch TO_HAND de Poke Pad -----------------------------------
# Poke Pad busca un Pokemon NO Rule-Box (basico o evolucion) hacia la MANO.
# Tres modos del bloque original, aplanados en una sola cadena (la primera
# regla que aplica gana, como el if/elif anidado): (1) PRIMER TURNO: asegurar
# los basicos de las dos lineas; (2) EVO DIRECTA (`has_evo`): traer la
# SIGUIENTE evolucion de un Pokemon que YA esta en el tablero ACTUAL —
# deliberadamente NO la foto de inicio de turno (_field_at_turn_start): esa
# foto ignora un Bayleef recien evolucionado y nos haria buscar un 2o Bayleef
# redundante en vez del Meganium que SI completa la linea; (3) FALLBACK:
# completar lineas desde la mano aunque la pre-evo no este en juego.



_REGLAS_PP_FETCH = [
    # (1) Primer turno: bajar los basicos de ambas lineas antes que nada.
    _ReglaFija("t1_applin",
               lambda c: (c.first_turn and c.card_id == Applin
                          and not c.have_applin),
               lambda c: 2000),
    _ReglaFija("t1_chikorita",
               lambda c: (c.first_turn and c.card_id == Chikorita
                          and not c.have_chik),
               lambda c: 1900),
    _ReglaFija("t1_otro",
               lambda c: c.first_turn,
               lambda c: 10),
    # (2) Evolucion directa de un Pokemon del tablero actual.
    _ReglaFija("evo_meganium",
               lambda c: (c.has_evo and c.card_id == Meganium
                          and not ESTADO.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0
                          and c.campo.get(Bayleef, 0) >= 1),
               lambda c: 1000),
    _ReglaFija("evo_meganium_rush",
               lambda c: (c.has_evo and c.card_id == Meganium
                          and not ESTADO.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0
                          and ESTADO.forest_in_play
                          and c.campo.get(Chikorita, 0) >= 1
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 900),
    _ReglaFija("evo_bayleef_rush",
               lambda c: (c.has_evo and c.card_id == Bayleef
                          and not ESTADO.meganium_in_play
                          and c.hand.get(Bayleef, 0) == 0
                          and c.campo.get(Chikorita, 0) >= 1
                          and ESTADO.forest_in_play
                          and c.hand.get(Meganium, 0) >= 1),
               lambda c: 950),
    _ReglaFija("evo_bayleef",
               lambda c: (c.has_evo and c.card_id == Bayleef
                          and not ESTADO.meganium_in_play
                          and c.hand.get(Bayleef, 0) == 0
                          and c.campo.get(Chikorita, 0) >= 1),
               lambda c: 850),
    _ReglaFija("evo_dipplin_rush",
               lambda c: (c.has_evo and c.card_id == Dipplin
                          and c.hand.get(Dipplin, 0) == 0
                          and c.campo.get(Applin, 0) >= 1
                          and ESTADO.forest_in_play
                          and c.hand.get(Hydrapple_ex, 0) >= 1),
               lambda c: 920),
    _ReglaFija("evo_dipplin",
               lambda c: (c.has_evo and c.card_id == Dipplin
                          and c.hand.get(Dipplin, 0) == 0
                          and c.campo.get(Applin, 0) >= 1),
               lambda c: 800),
    _ReglaFija("evo_otro",
               lambda c: c.has_evo,
               lambda c: 10),
    # (3) Fallback: completar lineas desde la mano.
    _ReglaFija("fb_bayleef",
               lambda c: (c.card_id == Bayleef and not ESTADO.meganium_in_play
                          and c.have_chik and not c.have_bay),
               lambda c: 850),
    _ReglaFija("fb_dipplin",
               lambda c: (c.card_id == Dipplin and c.have_applin
                          and not c.have_dipplin),
               lambda c: 800),
    _ReglaFija("fb_meganium",
               lambda c: (c.card_id == Meganium and not ESTADO.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0 and c.have_bay),
               lambda c: 700),
    _ReglaFija("fb_chikorita",
               lambda c: (c.card_id == Chikorita and not ESTADO.meganium_in_play
                          and c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0) < 1
                          and c.hand.get(Chikorita, 0) < 1
                          and c.bench_count < 5),
               lambda c: 800),
    _ReglaFija("fb_applin",
               lambda c: c.card_id == Applin and c.bench_count < 5,
               lambda c: 650),
]

# --- Reglas del fetch de Supporter de Meowth ex (Last-Ditch Catch) ----------
# Solo puntua Supporters (_MEOWTH_FETCH_SUPPS); el resto de candidatos
# conserva el 50 base del call site. Los dos ajustes del else original
# (bonus Boss's vs Crustle, cap de Dawn sin Forest) viven en el valor del
# catch-all (_v_meowth_fetch_valor), fiel a la reasignacion secuencial.






_REGLAS_MEOWTH_FETCH = [
    # PRIMER TURNO = SOLO LILLIE'S (user, log 88461779 paso 16 vs Alakazam,
    # PERDIDA). En NUESTRO primer turno el unico motivo por el que se baja un
    # Meowth ex es traer Lillie's Determination: el turno 1 no ataca, no
    # evoluciona y (yendo primeros) ni siquiera ofrece jugar Supporters, asi
    # que lo unico que decide la partida es cuanta MANO tendremos el turno 2.
    # Cualquier otro Supporter que traiga el Last-Ditch se queda muerto en la
    # mano -- y si el turno 2 jugamos la propia Lillie's, ademas se BARAJA.
    # En aquella partida el fetch trajo un Xerosic's Machinations (rama
    # `xerosic_alakazam`: mano rival >= 6 + atacante fuerte) teniendo cuatro
    # Lillie's en el mazo: se gasto la Ultra Ball, el Meowth ex (cuerpo de 2
    # premios en banca) y el turno entero para NO desarrollar nada.
    # Va PRIMERO en la cadena: ninguna rama de matchup (Xerosic, Boss's,
    # Dawn...) puede secuestrar el fetch del primer turno. Deck-agnostico: si
    # el mazo no tiene Lillie's alcanzable (`lillie_alcanzable`), la regla no
    # degrada a nadie y decide la escalera normal.
    _ReglaFija("primer_turno_solo_lillie",
               lambda c: (c.first_turn
                          and c.card_id == Lillie_Determination),
               lambda c: 1400),
    _ReglaFija("primer_turno_resto_cede_a_lillie",
               lambda c: c.first_turn and c.lillie_alcanzable,
               lambda c: min(c.sv, 40)),
    # COPIA REDUNDANTE (user, registro_010 paso 118 vs Alakazam, GANADA con
    # error): solo se juega UN Supporter por turno, asi que traer una 2a copia
    # de uno que YA esta en la mano no aporta absolutamente nada -- se gasto el
    # Meowth ex (un cuerpo de 2 premios en banca) para duplicar una carta. En
    # aquel turno el fetch trajo un segundo Xerosic's Machinations teniendo uno
    # en mano, en vez del Boss's Orders que era justo lo que el motor que bajo
    # el Meowth queria. Va PRIMERO en la cadena: ninguna otra rama debe poder
    # rescatar un duplicado. 40 (no veto) porque el prompt exige elegir una
    # carta: si TODOS los candidatos fueran duplicados hay que quedarse con
    # alguno. Deck-agnostico.
    _ReglaFija("copia_ya_en_mano",
               lambda c: (c.hand.get(c.card_id, 0) >= 1
                          and not c.first_turn),
               lambda c: 40),
    # Remate ganador / 2 premios via Boss's Orders del MAZO.
    _ReglaFija("boss_ganador",
               lambda c: ((c.win_via_boss or c.gust2_via_boss)
                          and c.card_id == Boss_Orders),
               lambda c: 1300),
    # Gusteo de VALOR (deny-evo) via motor Meowth (plan motor Meowth, mejora
    # A): el Boss's del MAZO corta la pre-evo ENERGIZADA del atacante ex
    # rival. 1280: bajo el remate ganador (1300), sobre Lillie's de
    # refresco/desarrollo (1200-1250) -- con la amenaza en banca, cortar la
    # linea prima sobre refrescar (user, registro_006 paso 82 vs Garchomp).
    _ReglaFija("boss_deny_evo",
               lambda c: (c.deny_evo_via_boss
                          and c.card_id == Boss_Orders),
               lambda c: 1280),
    _ReglaFija("lillie_desarrollo",
               lambda c: (c.devel_lillie
                          and c.card_id == Lillie_Determination),
               lambda c: 1250),
    # Xerosic vs Alakazam (user): con la mano rival gorda (Powerful Hand =
    # 20 x carta), Meowth ex busca Xerosic para capar el dano. Refinado
    # (user, registro_004 paso 53 vs Alakazam, PERDIDA): si YA tenemos un
    # atacante fuerte en juego (Hydrapple/Ogerpon), Xerosic manda AUNQUE
    # nuestra mano quede vacia tras bajar el Meowth (la mano rival de 13
    # cartas = Powerful Hand 260 que noquea todo lo nuestro; capar eso vale
    # mas que refrescar con Lillie's cuando el ataque ya esta resuelto) ->
    # 1260, sobre el Lillie's de desarrollo (1250) y el refresco por mano
    # corta (1200), bajo el Boss's ganador (1300). Sin atacante fuerte se
    # mantiene la regla previa (solo con mano >= 3, a 1200).
    _ReglaFija("xerosic_alakazam",
               lambda c: (c.card_id == Xerosic_Machinations
                          and c.alakazam
                          and c.op_hand_count >= 6
                          and (c.hand_size >= 3 or c.strong_attacker)),
               lambda c: 1260 if c.strong_attacker else 1200),
    # Xerosic GENERICO en el fetch de Last-Ditch (plan motor Meowth, mejora
    # B): contra CUALQUIER mazo con mano rival >= 7, quitarle 4+ cartas es
    # valor real (el scorer generico de Xerosic ya lo juega a 3380 si esta
    # en mano; antes ni era candidato del fetch fuera de Alakazam). 1100:
    # bajo Lillie's de refresco/desarrollo (1200-1250) y los Boss's
    # (1280/1300) -- solo si no hay mejor opcion. Guards:
    # `strong_attacker` (con el ataque ya resuelto la disrupcion vale; SIN
    # atacante fuerte, cavar con Lillie's -escaleras 1000-1200- va primero)
    # y activo-que-no-ataca (que Xerosic no secuestre el fetch del TURNO
    # MUERTO, cuyo sentido es traer Lana's/Lillie's para salir del atasco).
    _ReglaFija("xerosic_generico",
               lambda c: (c.card_id == Xerosic_Machinations
                          and c.op_hand_count >= 7
                          and c.strong_attacker
                          and not c.active_cant_attack),
               lambda c: 1100),
    _ReglaFija("mano_corta",
               lambda c: c.hand_size <= 2,
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 100))),
    _ReglaFija("atasco_sin_energia",
               lambda c: c.active_cant_attack and c.no_energy_in_hand,
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 150))),
    _ReglaFija("atasco_sin_lillie_en_mano",
               lambda c: (c.active_cant_attack and
                          c.hand.get(Lillie_Determination, 0) == 0),
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 150))),
    _ReglaFija("sin_atacante_mano_media",
               lambda c: not c.strong_attacker and c.hand_size <= 5,
               lambda c: (1000 if c.card_id == Lillie_Determination
                          else min(c.sv, 200))),
    _ReglaFija("sin_atacante",
               lambda c: not c.strong_attacker,
               lambda c: (800 if c.card_id == Lillie_Determination
                          else min(c.sv, 400))),
    _ReglaFija("valor_del_supporter",
               lambda c: True,
               _v_meowth_fetch_valor),
]


def _meowth_fetch_prediccion(hand_counts, supp_values, hand_size,
                             strong_attacker, op_hand_count,
                             active_cant_attack, win_via_boss, gust2_via_boss,
                             deny_evo_via_boss, devel_lillie, alakazam,
                             cartas_en_mazo, first_turn=False):
    """(id, valor) del Supporter que Last-Ditch Catch traeria AHORA MISMO.

    Reproduce el fetch REAL (`_REGLAS_MEOWTH_FETCH`, el mismo tablero) sobre
    los Supporters que siguen en el MAZO, para poder decidir ANTES de gastar el
    Meowth ex si la busqueda aporta algo. `hand_size` debe ser el de DESPUES de
    bajar el Meowth (una carta menos), que es cuando se resuelve el fetch.
    Devuelve (None, 0) si no queda ningun Supporter en el mazo.
    """
    mejor_id, mejor_val = None, 0
    _lillie_alcanzable = (cartas_en_mazo.get(
        Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    for _sid in _MEOWTH_FETCH_SUPPS:
        if cartas_en_mazo.get(_sid, {}).get(ESTADO_MAZO, 0) <= 0:
            continue
        _ctx = _CtxMeowthFetch(
            _sid, supp_values.get(_sid, 0), hand_counts, supp_values,
            hand_size, strong_attacker, op_hand_count, active_cant_attack,
            win_via_boss, gust2_via_boss, deny_evo_via_boss, devel_lillie,
            alakazam, first_turn, _lillie_alcanzable)
        _val, _ = _resolver_reglas(_REGLAS_MEOWTH_FETCH, [], _ctx, 50)
        if _val > mejor_val:
            mejor_id, mejor_val = _sid, _val
    return mejor_id, mejor_val


# --- Reglas del fetch TO_HAND de Dawn ---------------------------------------
# Dawn busca un Basico + una Fase 1 + una Fase 2: cada candidato se puntua
# por tabla (mismo patron que NS/BCS, reutiliza _CtxNS). El eje del bloque es
# `_dawn_forest_avail`: con Forest of Vitality EN JUEGO o EN MANO las lineas
# se pueden evolucionar el mismo turno (rush), asi que las piezas de Fase 1/2
# suben de valor aunque su pre-evo aun no este en el tablero.


_REGLAS_DAWN_MEGANIUM = [
    _ReglaFija("ya_en_juego",
               lambda c: ESTADO.meganium_in_play, lambda c: 10),
    _ReglaFija("evo_inmediata",
               lambda c: c.campo.get(Bayleef, 0) >= 1, lambda c: 1000),
    _ReglaFija("rush_desde_campo_con_bayleef",
               lambda c: (c.campo.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 980),
    _ReglaFija("rush_desde_campo",
               lambda c: (c.campo.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 950),
    _ReglaFija("rush_desde_mano_con_bayleef",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 960),
    _ReglaFija("rush_desde_mano",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 920),
]

_REGLAS_DAWN_BAYLEEF = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play, lambda c: 10),
    # La evolucion inmediata sube si el Meganium que completa la linea es
    # alcanzable (en mano o aun en el mazo).
    _ReglaFija("evo_inmediata_rush",
               lambda c: (c.campo.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)
                          and (c.hand.get(Meganium, 0) >= 1 or
                               ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                   Meganium, {}).get(ESTADO_MAZO, 0) > 0)),
               lambda c: 970),
    _ReglaFija("evo_inmediata",
               lambda c: c.campo.get(Chikorita, 0) >= 1, lambda c: 900),
    _ReglaFija("rush_desde_mano",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 880),
    _ReglaFija("con_chikorita_en_mano",
               lambda c: (c.bench_count < 5
                          and c.hand.get(Chikorita, 0) >= 1),
               lambda c: 500),
]

_REGLAS_DAWN_CHIKORITA = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play, lambda c: 10),
    _ReglaFija("linea_en_juego",
               lambda c: (c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0) >= 1),
               lambda c: 50),
    _ReglaFija("banca_llena",
               lambda c: c.bench_count >= 5, lambda c: 30),
    _ReglaFija("rush_con_bayleef",
               lambda c: (_dawn_forest_avail(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 850),
    _ReglaFija("rush",
               lambda c: _dawn_forest_avail(c), lambda c: 800),
    _ReglaFija("con_bayleef_en_mano",
               lambda c: c.hand.get(Bayleef, 0) >= 1, lambda c: 700),
]

_REGLAS_DAWN_HYDRAPPLE = [
    _ReglaFija("ya_en_juego",
               lambda c: c.has_hydrapple, lambda c: 10),
    _ReglaFija("evo_inmediata",
               lambda c: c.campo.get(Dipplin, 0) >= 1, lambda c: 980),
    _ReglaFija("rush_desde_campo_con_dipplin",
               lambda c: (c.campo.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 960),
    _ReglaFija("rush_desde_campo",
               lambda c: (c.campo.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 930),
    _ReglaFija("rush_desde_mano_con_dipplin",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 940),
    _ReglaFija("rush_desde_mano",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 900),
]

_REGLAS_DAWN_DIPPLIN = [
    _ReglaFija("redundante_con_hydrapple",
               lambda c: (c.has_hydrapple
                          and c.campo.get(Dipplin, 0) >= 1),
               lambda c: 10),
    _ReglaFija("evo_inmediata_rush",
               lambda c: (c.campo.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)
                          and (c.hand.get(Hydrapple_ex, 0) >= 1 or
                               ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                   Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0)),
               lambda c: 950),
    _ReglaFija("evo_inmediata",
               lambda c: c.campo.get(Applin, 0) >= 1, lambda c: 880),
    _ReglaFija("rush_desde_mano",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 860),
    _ReglaFija("con_applin_en_mano",
               lambda c: (c.bench_count < 5
                          and c.hand.get(Applin, 0) >= 1),
               lambda c: 480),
]

_REGLAS_DAWN_APPLIN = [
    _ReglaFija("linea_completa",
               lambda c: (c.has_hydrapple
                          and c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0) >= 1),
               lambda c: 10),
    _ReglaFija("linea_doblada",
               lambda c: (c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0)
                          + c.campo.get(Hydrapple_ex, 0) >= 2),
               lambda c: 30),
    _ReglaFija("banca_llena",
               lambda c: c.bench_count >= 5, lambda c: 30),
    _ReglaFija("rush_con_dipplin",
               lambda c: (_dawn_forest_avail(c)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 830),
    _ReglaFija("rush",
               lambda c: _dawn_forest_avail(c), lambda c: 780),
    _ReglaFija("con_dipplin_en_mano",
               lambda c: c.hand.get(Dipplin, 0) >= 1, lambda c: 680),
]

_REGLAS_DAWN_OGERPON = [
    _ReglaFija("dos_en_juego",
               lambda c: c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 2,
               lambda c: 10),
    _ReglaFija("banca_llena",
               lambda c: c.bench_count >= 5, lambda c: 30),
    _ReglaFija("primer_ogerpon",
               lambda c: c.campo.get(Teal_Mask_Ogerpon_ex, 0) == 0,
               lambda c: 500),
]

_REGLAS_DAWN_TAPU = [
    # vs Dragapult con el tablero hecho no se puede BAJAR: no se busca.
    _ReglaFija("dragapult_no_lo_baja",
               lambda c: c.dragapult_no_tapu,
               lambda c: SCORE_VETO),
    _ReglaFija("ya_en_juego",
               lambda c: c.campo.get(Tapu_Bulu, 0) >= 1, lambda c: 10),
    _ReglaFija("anti_muro_con_meganium",
               lambda c: ((ESTADO.op_is_crustle_deck or c.op_ex_immune_active
                           or c.op_ex_immune_bench)
                          and ESTADO.meganium_in_play),
               lambda c: 700),
    _ReglaFija("anti_muro",
               lambda c: (ESTADO.op_is_crustle_deck or c.op_ex_immune_active
                          or c.op_ex_immune_bench),
               lambda c: 600),
]

_REGLAS_DAWN_FEZ = [
    _ReglaFija("ya_en_juego",
               lambda c: c.campo.get(Fezandipiti_ex, 0) >= 1, lambda c: 10),
    _ReglaFija("tras_ko",
               lambda c: ESTADO.ko_last_turn, lambda c: 500),
]

_REGLAS_DAWN_MEOWTH = [
    _ReglaFija("ya_en_juego",
               lambda c: c.campo.get(Meowth_ex, 0) >= 1, lambda c: 10),
    _ReglaFija("motor_supporter",
               lambda c: (not c.watchtower and not c.supporter_played
                          and c.bench_count < 5),
               lambda c: 300),
]

_REGLAS_DAWN_GRASS = [
    _ReglaFija("sin_planta_y_sin_adjunte",
               lambda c: (not c.energy_attached
                          and c.hand.get(Basic_Grass_Energy, 0) == 0),
               lambda c: 400),
    _ReglaFija("sin_planta",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) == 0,
               lambda c: 250),
]

_REGLAS_DAWN_FOREST = [
    _ReglaFija("falta_forest",
               lambda c: not ESTADO.forest_in_play and not _dawn_forest_avail(c),
               lambda c: 600),
]

_TABLA_DAWN_FETCH = {
    Meganium: ("dawn->meganium", _REGLAS_DAWN_MEGANIUM, 200),
    Bayleef: ("dawn->bayleef", _REGLAS_DAWN_BAYLEEF, 150),
    Chikorita: ("dawn->chikorita", _REGLAS_DAWN_CHIKORITA, 500),
    Hydrapple_ex: ("dawn->hydrapple", _REGLAS_DAWN_HYDRAPPLE, 180),
    Dipplin: ("dawn->dipplin", _REGLAS_DAWN_DIPPLIN, 130),
    Applin: ("dawn->applin", _REGLAS_DAWN_APPLIN, 480),
    Teal_Mask_Ogerpon_ex: ("dawn->ogerpon", _REGLAS_DAWN_OGERPON, 400),
    Tapu_Bulu: ("dawn->tapu", _REGLAS_DAWN_TAPU, 100),
    Fezandipiti_ex: ("dawn->fez", _REGLAS_DAWN_FEZ, 80),
    Meowth_ex: ("dawn->meowth", _REGLAS_DAWN_MEOWTH, 50),
    Basic_Grass_Energy: ("dawn->grass", _REGLAS_DAWN_GRASS, 80),
    Forest_of_Vitality: ("dawn->forest", _REGLAS_DAWN_FOREST, 10),
}

# --- Reglas del OBJETIVO del gusteo de Boss's Orders ------------------------
# Dos modos, como el bloque original: ESTORBO (nuestro activo no puede atacar:
# trabar al rival) y OFENSIVO (gustear para noquear o clavar). El score de
# entrada del bucle de opciones es 0; las contribuciones son acumulativas
# (_Ajuste). Dunsparce se descarta en el call site (regla del usuario: NUNCA
# gustearlo, en ningun modo).





# GRADUAR EL EJE DEL ATAQUE: MEDIDO Y REVERTIDO (ago 2026).
#
# `sin_ko_prefiere_cuerpo_muerto` (+1500) es un BOOLEANO con horizonte de UNA
# energia (`_op_cuerpo_inofensivo` = deficit >= 2): separa a quien puede atacar
# el turno que viene de quien no, pero deja EMPATADOS entre si a todos los
# cuerpos muertos. Como el eje de la RETIRADA si va graduado (`stall_diff` x
# 100), se probo el mismo trato para el del ATAQUE: +200 por cada energia que
# faltase POR ENCIMA de las 2 que ya cobran el +1500, topado a 2 pasos, con las
# mismas tres guardas (sin KO / cuerpo muerto / `GUST_TRAMPA_IDS` fuera).
#
# Se cayo por INERTE, no por dañino. El bonus alteraba algun score en 142 de
# 535 decisiones de objetivo (1400 partidas, 7 matchups) y cambiaba el objetivo
# elegido en CERO. La razon esta en la forma de la banda: en 117 de las 144
# decisiones con candidato bonificable el hueco hasta el elegido era 0 -- el
# cuerpo con deficit 3 YA era el argmax por otras vias (`traba_sin_ko` graduado
# + `_gust_linea_rival`), asi que el bonus solo engordaba una ventaja existente.
# En las 27 restantes el hueco era de tier de KO (>= 3000) o de la preferencia
# deliberada por cortar la linea evolutiva: justo lo que un desempate no debe
# volcar. Winrate consistente con eso -- neutro y por debajo de la resolucion
# del gate (n=3000/rama x 5 matchups: agregado -0.14 contra el control, con una
# deriva del control NULO de -0.06; ningun delta individual sale del rango del
# nulo).
#
# Lo que SI queda del intento es `_op_deficit_de_ataque`: el eje graduado existe
# como primitiva y `_op_cuerpo_inofensivo` es explicitamente su umbral, que es
# donde estaba la confusion. Si algun dia hace falta desempatar dentro de la
# banda, el dato ya esta medido; lo que no hace falta es el bonus.






_AJUSTES_GUST_OFENSIVO = [
    _Ajuste("objetivo_del_plan",
            lambda c, s: c.plan_target_match,
            lambda c, s: s + 100),
    # GUSTEO GANADOR (user, registro_011 vs Mega Heracross ex, GANADA subopt.):
    # si al noquear ESTE objetivo cobramos los premios que faltan para GANAR
    # (`wins_now`: prizes >= my_prize), es la maxima prioridad ABSOLUTA sobre
    # cualquier otro objetivo. Cuando hay varios objetivos que ganan, el
    # tier_ko de abajo (prize-aware) desempata hacia el de mas premios. Cubre el
    # caso en que el remate estaba disponible pero el juego gusteaba un ex de
    # menos premios. Deck-agnostico.
    _Ajuste("gust_gana_partida",
            lambda c, s: c.wins_now,
            lambda c, s: s + 100000),
    _Ajuste("tier_ko",
            lambda c, s: c.can_ko,
            lambda c, s: s + c.tier_ko * 3000),
    # PRIORIDAD (user, log 86504664 paso 94, PERDIDA vs Archaludon): al
    # poder NOQUEAR, una pre-evo ENERGIZADA de una linea ex (Duraludon ->
    # Archaludon ex) borra un futuro atacante ex de 2 premios. Tier
    # efectivo 6.5 (19500): sobre cualquier no-ex, bajo un ex real.
    _Ajuste("preevo_ex_prioritaria",
            lambda c, s: (c.can_ko and c.energia >= 1 and not c.is_exmega
                          and c.card_id in EX_PREEVO_IDS),
            lambda c, s: s + max(0, 19500 - c.tier_ko * 3000)),
    # Sin KO posible: gustear como estorbo (mayor coste de retirada NETO)
    # con el desempate anti pre-evo de amenaza.
    _Ajuste("traba_sin_ko",
            lambda c, s: not c.can_ko and c.stall_diff >= 1,
            lambda c, s: s + c.stall_diff * 100
            - (50 if (c.card_id in THREAT_PREEVO_IDS
                      or c.card_id in EX_PREEVO_IDS) else 0)),
    # Copia ENERGIZADA del activo rival sin energia: re-gustearla cobra la
    # inversion del rival.
    _Ajuste("regust_energizado",
            lambda c, s: c.regust_energized,
            lambda c, s: s + 200),
    _Ajuste("linea_rival",
            lambda c, s: True,
            lambda c, s: s + _gust_linea_rival(c)),
    # SIN KO manda QUIEN SUBE AL ACTIVO, no cual es la pieza mas gorda de su
    # banca. Las dos bandas de `_gust_linea_rival` puntuan al reves:
    # `_gust_linea_evolutiva` da 800 a la EVOLUCION FINAL (Dragapult ex,
    # Typhlosion, Alakazam) -- por encima de los 700 de la Fase 1 clavada, que
    # su propio docstring llama "mejor objetivo de disrupcion" -- y
    # `_gust_tiers_genericos` da 250 a un ex ENERGIZADO, el techo de su banda
    # sin KO. Sin KO eso es ponerle delante, y ademas gratis (Boss's le paga la
    # retirada), justo el cuerpo con el que queria atacar.
    #
    # Ademas contradecia al detector que JUSTIFICA la jugada: el gusteo
    # DEFENSIVO (`_bo_defensive_gust`) vale 940 porque EXISTE en su banca un
    # cuerpo que no puede rematarnos... y luego el selector subia otro.
    #
    # +1500 supera toda la banda sin KO (100-1200) y no toca los tiers de KO
    # (>= 3000), que van gateados por `can_ko`. `GUST_TRAMPA_IDS` excluye los
    # muros y el locker: sus ataques cuestan 3, asi que pelados pasarian por
    # inofensivos y son justo los cuerpos que NO queremos delante.
    _Ajuste("sin_ko_prefiere_cuerpo_muerto",
            lambda c, s: (not c.can_ko and c.cuerpo_inofensivo
                          and c.card_id not in GUST_TRAMPA_IDS),
            lambda c, s: s + 1500),
    # vs Crustle, el Dwebble NUNCA se gustea (forraje del muro)... SALVO que el
    # activo rival sea un MURO que anula a nuestro atacante y ese Dwebble sea un
    # KO real (user, episodio 88620891 paso 78, PERDIDA): Hydrapple ex activo
    # contra un Crustle inmune a los ex, con dos Dwebble noqueables en la banca.
    # El veto original (log 86339758) evita gastar Boss's persiguiendo forraje
    # cuando hay algo mejor que hacer; aqui NO hay nada mejor -- atacar de frente
    # hace 0 y el turno se cierra sin premios. Con el muro delante, el Dwebble
    # noqueable es el UNICO premio del turno y ademas niega un Crustle futuro.
    _Ajuste("forbid_dwebble_vs_crustle",
            lambda c, s: (ESTADO.op_is_crustle_deck
                          and c.card_id in (Dwebble_Grass, Dwebble_Fighting)
                          and not (c.muro_bloquea_activo and c.can_ko)),
            lambda c, s: SCORE_FORBID),
    # Retirada GRATIS sin KO: el rival lo devuelve al banco sin coste;
    # solo es gusteable cuando es un KO real.
    _Ajuste("forbid_retirada_gratis_sin_ko",
            lambda c, s: c.rc0 <= 0 and not c.can_ko,
            lambda c, s: SCORE_FORBID),
]

_REGLAS_NS_BAYLEEF = [
    _ReglaFija("combo_chikorita_meganium_en_mano",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and c.hand.get(Meganium, 0) >= 1
                          and ESTADO.forest_in_play and c.bench_count < 5
                          and not ESTADO.meganium_in_play),
               lambda c: 985),
    _ReglaFija("chikorita_en_mano_con_forest",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and ESTADO.forest_in_play and c.bench_count < 5
                          and not ESTADO.meganium_in_play),
               lambda c: 910),
    _ReglaFija("chikorita_evolucionable",
               lambda c: (c.evolvable_ns.get(Chikorita, 0) >= 1
                          and not ESTADO.meganium_in_play),
               lambda c: 870),
]

def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return my_deck

    state = obs.current
    select = obs.select
    context = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
    my_prize = len(my_state.prize)
    op_prize = len(op_state.prize)

    # Impuesto de Nighttime Mine sobre nuestros Tera. Va AQUI, antes de
    # cualquier puntuacion, porque ~50 sitios leen ATTACK_ENERGY_REQ y todos
    # tienen que ver el coste ya corregido.
    nighttime_mine_in_play = _aplicar_impuesto_tera(state.stadium)

    _update_cartas_tracking(obs, my_index, my_state)


    if state.firstPlayer >= 0:
        ESTADO.we_go_first = (state.firstPlayer == state.yourIndex)

    if ESTADO.pre_turn != state.turn:
        ESTADO.pre_turn = state.turn
        ESTADO.plan = AttackPlan()

        # Contador de Plantas puestas en el campo este turno (ver
        # `_grass_ability_slots`): es POR TURNO.
        ESTADO._grass_attaches_this_turn = 0

        ESTADO._field_at_turn_start = None

        ESTADO._ko_detected_this_turn = False

        ESTADO._poke_pad_target_id = 0

        ESTADO._ub_meowth_pending = False

        ESTADO._ub_fez_pending = False

        ESTADO._ub_engine_pivot_turn = False

        ESTADO._ld_supp_comprometido = 0

        # El cache de habilidad del activo es POR TURNO (ver mas abajo).
        ESTADO._td_ability_serial = None

    field_counts = defaultdict(int)
    hand_counts = defaultdict(int)
    discard_counts = defaultdict(int)

    ESTADO.meganium_in_play = False
    ESTADO.forest_in_play = False
    has_ogerpon = False
    has_hydrapple = False
    bench_count = 0
    # Tope de banca del estado; los estados sinteticos de los tests no siempre
    # lo traen, y las puertas de utilidad de Supporter ("¿cabe lo que traigo?")
    # lo consultan en cada turno.
    bench_max = getattr(my_state, 'benchMax', None) or 5

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Meganium:
            ESTADO.meganium_in_play = True
        if card.id == Hydrapple_ex:
            has_hydrapple = True
        if card.id == Teal_Mask_Ogerpon_ex:
            has_ogerpon = True

    for pokemon in my_state.bench:
        if pokemon is not None:
            bench_count += 1

    if ESTADO._field_at_turn_start is None:
        ESTADO._field_at_turn_start = dict(field_counts)

    if ESTADO._poke_pad_target_id > 0 and field_counts.get(ESTADO._poke_pad_target_id, 0) > 0:
        ESTADO._poke_pad_target_id = 0

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    # Con la banca LLENA, un recurso de busqueda (Ultra Ball / Poke Pad) solo
    # aporta valor si permite EVOLUCIONAR un Pokemon ya en juego (no se puede
    # banquear nada nuevo). "Hay algo que evolucionar" = tenemos en juego una
    # pre-evolucion cuya siguiente etapa esta disponible (en mano o en el mazo).
    _evolve_possible_in_play = (
        (field_counts.get(Chikorita, 0) >= 1 and
         (hand_counts.get(Bayleef, 0) >= 1 or
          ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0)) or
        (field_counts.get(Bayleef, 0) >= 1 and
         (hand_counts.get(Meganium, 0) >= 1 or
          ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0)) or
        (field_counts.get(Applin, 0) >= 1 and
         (hand_counts.get(Dipplin, 0) >= 1 or
          ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0)) or
        (field_counts.get(Dipplin, 0) >= 1 and
         (hand_counts.get(Hydrapple_ex, 0) >= 1 or
          ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0))
    )

    # Eslabon de evolucion que de verdad hace falta buscar / evoluciones
    # huerfanas (sin su pre-evolucion). Ver `_evo_link_state`.
    _evo_necesarios, _evo_huerfanos = _evo_link_state(hand_counts, field_counts)

    stadium_id = 0
    for card in state.stadium:
        stadium_id = card.id

    if stadium_id == Forest_of_Vitality:
        ESTADO.forest_in_play = True

    # Grand Tree en mesa: su habilidad es de USO COMPARTIDO (una vez por turno
    # de CADA jugador), asi que la aprovechamos tanto si la bajamos nosotros
    # como si la bajo el rival. Ver el bloque `_gt_*` para el plan concreto.
    grand_tree_in_play = (stadium_id == Grand_Tree)

    neutralization_zone_active = (stadium_id == Neutralization_Zone)

    # Team Rocket's Watchtower: los Pokemon {C} en juego (ambos jugadores) NO
    # tienen Habilidades. Meowth ex es {C}, asi que su Last-Ditch Catch (buscar
    # Supporter al banquearlo) queda ANULADA mientras este estadio siga en
    # juego. No conviene bajar Meowth ex ni buscarlo con Ultra Ball hasta poder
    # reemplazar el estadio (p.ej. con Forest of Vitality).
    watchtower_in_play = (stadium_id == Team_Rockets_Watchtower)

    # Iron Thorns ex ("Initialization") en el ACTIVO rival (P1.4): anula las
    # habilidades de TODOS los Pokemon con Rule Box de ambos lados. Teal
    # Dance / Ripening / Flip the Script desaparecen del menu (lo impone el
    # motor del juego), pero el agente ademas NO debe planear alrededor de
    # Last-Ditch Catch (bajar o buscar Meowth ex "para el fetch"): mismo
    # efecto que Team Rocket's Watchtower sobre Meowth. A diferencia del
    # estadio, Forest NO lo arregla (hay que sacar a Iron Thorns del activo:
    # KO o gusteo), por eso `watchtower_in_play` se mantiene puro para las
    # reglas de contra-estadio y este OR alimenta los gates del motor Meowth.
    op_iron_thorns_active = bool(
        op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Iron_Thorns_ex)
    meowth_ability_lock = watchtower_in_play or op_iron_thorns_active

    # Denegacion de premios del campo rival (P0.2): refresca los flags que
    # consulta `prize_count_op` (Pecharunt ex -> Munkidori ex rinde 1 menos;
    # Mega Gengar ex -> sus {D} rinden 1 menos ante nuestros ex).
    _op_field_ids = {p.id for p in ((op_state.active or [])
                                    + (op_state.bench or [])) if p is not None}
    ESTADO._op_prize_denial_pecharunt = Pecharunt_ex in _op_field_ids
    ESTADO._op_prize_denial_gengar = Mega_Gengar_ex in _op_field_ids

    # Tablero rival que necesitan las proyecciones de dano: la BANCA escala Do
    # the Wave (20 x banca) y el estadio enciende Festival Lead. Se publican como
    # flags de modulo -y no como parametros- para que los vean TODOS los
    # llamadores de `_op_active_attack_damage_to`; ver DO_THE_WAVE_ATTACK_ID.
    ESTADO._op_bench_count = sum(1 for p in (op_state.bench or []) if p is not None)
    ESTADO._festival_grounds_in_play = any(
        getattr(c, 'id', 0) == Festival_Grounds for c in (state.stadium or []))

    # Festival Grounds HOSTIL: el estadio solo nos hace dano si el rival tiene
    # de verdad la linea que lo aprovecha. Se exige haber VISTO un Applin o un
    # Dipplin suyo (campo o descarte) porque el estadio es de doble filo --
    # nuestro propio Dipplin tambien gana Festival Lead con el en mesa--, asi
    # que quitarlo "por si acaso" apagaria tambien nuestra copia. Nosotros no
    # jugamos Festival Grounds (no esta en deck.csv): si esta en mesa, es suyo.
    _festival_lead_hostil = ESTADO._festival_grounds_in_play and (
        any(p is not None and p.id in (Dipplin, Applin)
            for p in ((op_state.active or []) + (op_state.bench or [])))
        or any(getattr(c, 'id', 0) in (Dipplin, Applin)
               for c in (op_state.discard or [])))

    is_poisoned = my_state.poisoned
    is_burned = my_state.burned
    is_asleep = my_state.asleep
    is_paralyzed = my_state.paralyzed
    is_confused = my_state.confused
    has_condition = is_poisoned or is_burned or is_asleep or is_paralyzed or is_confused

    condition_blocks_action = is_paralyzed or is_asleep

    condition_risky_attack = is_confused

    condition_passive_damage = is_poisoned or is_burned

    condition_urgency = 0
    if is_paralyzed:
        condition_urgency += 5000
    if is_asleep:
        condition_urgency += 3000
    if is_confused:
        condition_urgency += 2000
    if is_poisoned:
        condition_urgency += 1500
    if is_burned:
        condition_urgency += 1200

    # Plantas que HEMOS puesto en el campo durante este turno. Los logs llegan
    # por lotes incrementales, asi que se acumulan llamada a llamada; si el lote
    # cruza el cambio de turno solo cuentan los ATTACH posteriores al ultimo
    # TURN_START/TURN_END. Con este contador `_grass_ability_slots` sabe si
    # queda viva alguna habilidad de carga (Teal Dance / Ripening Charge)
    # cuando el adjunte MANUAL del turno ya se gasto.
    _ga_desde = 0
    for _ga_i, _ga_log in enumerate(obs.logs):
        if getattr(_ga_log, 'type', None) in (LogType.TURN_START,
                                              LogType.TURN_END):
            _ga_desde = _ga_i + 1
    for _ga_log in obs.logs[_ga_desde:]:
        if (getattr(_ga_log, 'type', None) == LogType.ATTACH
                and getattr(_ga_log, 'playerIndex', None) == my_index
                and getattr(_ga_log, 'cardId', None) == Basic_Grass_Energy):
            ESTADO._grass_attaches_this_turn += 1

    # Ventana de turno de NUESTROS KO (ver `_rastrear_ventana_de_ko`): hay que
    # rastrearla en CADA observacion, tambien en las seleccciones forzadas
    # durante el turno del rival, porque el TURN_END y el KO pueden llegar en
    # lotes de logs distintos.
    _rastrear_ventana_de_ko(obs.logs, my_index, state.turn)

    ESTADO.ko_last_turn = ESTADO._ko_detected_this_turn

    if not ESTADO.ko_last_turn:

        for log in obs.logs:
            if hasattr(log, 'type'):
                if (log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and
                        log.playerIndex != my_index and hasattr(log, 'fromArea') and
                        log.fromArea == AreaType.PRIZE):
                    ESTADO.ko_last_turn = True
                    break

    if not ESTADO.ko_last_turn:

        if op_prize < ESTADO._prev_op_prize:
            ESTADO.ko_last_turn = True

    if not ESTADO.ko_last_turn:

        if context == SelectContext.TO_ACTIVE and not state.retreated:
            ESTADO.ko_last_turn = True

    # --- VENTANA DEL KO: el premio cobrado no dice CUANDO murio el cuerpo -----
    # Las tres pruebas de arriba solo ven el EFECTO de un KO nuestro (el rival
    # cobra premio, nos toca promover). Aqui se comprueba la clausula que de
    # verdad piden Flip the Script y Unfair Stamp: que el KO cayera DENTRO del
    # ultimo turno del rival. Un KO ENTRE TURNOS (Freezing Shroud de Froslass) o
    # en nuestro propio turno (auto-KO de retroceso) no las habilita, y el motor
    # simplemente no ofrece ni el Sello ni la habilidad.
    #
    # Solo REBAJA, y solo con evidencia positiva en los logs: si no vimos la
    # ventana del KO, `ko_last_turn` se queda como estaba.
    _ko_fuera_de_ventana = (ESTADO._ko_propio_fuera_del_turno_rival >= state.turn - 1)
    _ko_dentro_de_ventana = (ESTADO._ko_propio_en_turno_rival >= state.turn - 1)
    if ESTADO.ko_last_turn and _ko_fuera_de_ventana and not _ko_dentro_de_ventana:
        ESTADO.ko_last_turn = False
        ESTADO._ko_detected_this_turn = False

    # Oraculo del motor: Unfair Stamp lleva IMPRESA la misma clausula que Flip
    # the Script ("solo puedes jugar esta carta si alguno de tus Pokemon quedo
    # Fuera de Combate durante el ultimo turno de tu rival"). Si lo tenemos en
    # mano y el menu PRINCIPAL no lo ofrece, el propio juego esta diciendo que
    # la clausula no se cumple -- y entonces la habilidad de Fezandipiti tampoco
    # se podria usar. Es la verdad de referencia, por encima de cualquier
    # inferencia de logs, pero solo esta disponible con el Sello en la mano.
    if (ESTADO.ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1
            and context == SelectContext.MAIN
            and my_state.hand is not None):
        _idx_sello = {_i for _i, _c in enumerate(my_state.hand)
                      if _c is not None and _c.id == Unfair_Stamp}
        _jugables = {getattr(_o, 'index', None) for _o in select.option
                     if getattr(_o, 'type', None) == OptionType.PLAY}
        if not (_idx_sello & _jugables):
            ESTADO.ko_last_turn = False
            ESTADO._ko_detected_this_turn = False

    if ESTADO.ko_last_turn:
        ESTADO._ko_detected_this_turn = True

    # Bloqueo de la cadena Unfair Stamp -> habilidad de Fezandipiti (Flip the
    # Script): mientras tengamos Unfair Stamp jugable este turno (nos noquearon
    # el turno anterior y sigue en la mano) primero se juega el Stamp y DESPUES
    # la habilidad. Se define aqui (ambito de agent) porque el bloque de la
    # habilidad de Fezandipiti la consulta en cualquier contexto.
    # ...y solo si el Sello MERECE jugarse (regla de carta, `_sello_merece_
    # jugarse`): con la mano rival <= 2 y la nuestra grande el Sello espera, asi
    # que no debe bloquear ni la habilidad ni la cadena de Supporters.
    _stamp_blocks_supp_chain = (
        ESTADO.ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1
        and _sello_merece_jugarse(getattr(op_state, 'handCount', 0),
                                  len(my_state.hand or [])))

    # Orden Lillie's Determination -> Flip the Script (peticion usuario): si
    # tenemos Lillie's Determination en la mano y aun no hemos jugado Supporter
    # este turno, primero se juega Lillie's Determination y DESPUES la habilidad
    # de Fezandipiti. Lillie's Determination es Supporter: al jugarse sale de la
    # mano y este flag pasa a False, re-habilitando la habilidad (30000).
    _lillie_blocks_fez_ability = (hand_counts.get(Lillie_Determination, 0) >= 1
                                  and not state.supporterPlayed)

    if context == SelectContext.MAIN:
        ESTADO._prev_op_prize = op_prize

    def _op_best_damage_vs(my_pokemon, assume_attach=True):
        if my_pokemon is None:
            return 0
        _opa = _active_of(op_state)
        if _opa is None:
            return 0
        _opd = card_table.get(_opa.id)
        if not _opd or not getattr(_opd, 'attacks', None):
            return 0
        _avail = len(_opa.energies) + (1 if assume_attach else 0)
        _best = 0
        for _atk in _opd.attacks:
            _dmg = getattr(_atk, 'damage', None)
            if _dmg is None:
                continue
            _cost = getattr(_atk, 'cost', None)
            _need = 0
            if _cost is not None:
                try:
                    _need = len(_cost)
                except TypeError:
                    try:
                        _need = int(_cost)
                    except (TypeError, ValueError):
                        _need = 0
            if _need <= _avail:
                _best = max(_best, _dmg)
        _myd = card_table.get(my_pokemon.id)
        # Maximum Belt (1158, Ace Spec) en el activo rival: +50 de dano a
        # nuestro Pokemon ex ACTIVO, antes de debilidad (auditoria julio 2026:
        # las tools rivales eran invisibles y los pivotes creian que el muro
        # sobrevivia a un golpe potenciado).
        if (_best > 0 and my_pokemon.id in OUR_EX_IDS
                and any(getattr(_t, 'id', 0) == Maximum_Belt
                        for _t in (getattr(_opa, 'tools', None) or []))):
            _best += 50
        if (_myd and _opd and getattr(_myd, 'weakness', None) is not None and
                _myd.weakness == getattr(_opd, 'energyType', None)):
            _best *= 2
        return _best

    def _op_counter_threat_vs(my_pokemon):
        # Ataques que colocan CONTADORES de dano segun el tamano de mano rival
        # (p.ej. Alakazam - Powerful Hand: 20 por carta en su mano). Estos
        # ataques tienen 'damage' = None (n/a), asi que _op_best_damage_vs los
        # ignora y el agente queda ciego a la amenaza. Aqui los estimamos para
        # que el lookahead penalice subir a un Pokemon fragil que moriria.
        if my_pokemon is None:
            return 0
        _opa = _active_of(op_state)
        if _opa is None:
            return 0
        if _opa.id == Alakazam_ex:
            _h = _op_hand_size(op_state)
            if _h <= 0:
                _h = 4  # mano rival oculta: estimacion conservadora
            return 20 * _h
        # Do the Wave (Dipplin): 20 x SU banca, otro dano impreso 0. Este hook es
        # el que consulta el lookahead de promocion (SCORE_LOOKAHEAD_PROMOTE_KO),
        # asi que sin el subir un cuerpo fragil salia gratis. Se suma el Brave
        # Bangle igual que en `_op_active_attack_damage_to`.
        if _opa.id == Dipplin:
            _dmg = 20 * ESTADO._op_bench_count
            if (_dmg > 0 and my_pokemon.id in OUR_EX_IDS
                    and any(getattr(_t, 'id', 0) == Brave_Bangle
                            for _t in (getattr(_opa, 'tools', None) or []))
                    and not _tiene_rule_box(_opa.id)):
                _dmg += 30
            return _dmg
        return 0

    active_ko_likely = False
    active_hp_ratio = 1.0
    estimated_op_damage = 0
    _teal_wall_pivot = False

    _mega_line_active = False
    if my_state.active and my_state.active[0] is not None:
        my_active = my_state.active[0]
        active_hp_ratio = my_active.hp / max(1, my_active.maxHp)
        if my_active.id in (Chikorita, Bayleef, Meganium):
            _mega_line_active = True

        op_active = _active_of(op_state)
        if op_active is not None:
            op_data = card_table.get(op_active.id)
            op_energy = len(op_active.energies)

            estimated_op_damage = _op_best_damage_vs(my_active)
            # Powerful Hand (Alakazam 743): dano real = 20 x carta en la mano
            # rival, INVISIBLE para _op_best_damage_vs (dano impreso 0). Se
            # proyecta 20 x (mano + 2) via _op_active_attack_damage_to --
            # acotado al activo Alakazam para no alterar otros matchups. Esto
            # enciende toda la maquinaria de "activo condenado" (pivotes
            # defensivos, urgencia de retirada, protecciones) en el matchup
            # donde mas se necesita (sugerencia 1 anti-Alakazam: antes el
            # modelo creia que Alakazam pegaba 0).
            # Do the Wave (Dipplin 93) es el mismo caso -- dano impreso 0, real
            # 20 x su banca-- y llega potenciado con Brave Bangle contra
            # nuestros ex. Se acota al activo Dipplin por la misma razon que
            # Alakazam: no alterar la lectura de "activo condenado" en el resto
            # de matchups (log 88971843: el agente creia que Dipplin pegaba 0).
            if op_active.id in (Alakazam_ex, Dipplin):
                estimated_op_damage = max(
                    estimated_op_damage,
                    _op_active_attack_damage_to(
                        op_active, my_active,
                        getattr(op_state, 'handCount', None)))

            # Burst de banca rival (P0.3): Dusknoir 133 ("Cursed Blast": 13
            # contadores = 130) y Dusclops 132 (5 = 50) meten dano EXTRA desde
            # cualquier posicion ADEMAS del ataque del activo (usan la
            # habilidad, se noquean solos y LUEGO atacan). Sin sumarlo, los
            # pivotes defensivos creen que el muro sobrevive un golpe que en
            # realidad llega con +130. Se suma el MAYOR burst disponible (una
            # sola habilidad por proyeccion: conservador sin sobre-disparar).
            # Aplica aunque el activo rival no pueda atacar: la habilidad no
            # necesita ataque.
            _op_burst = 0
            for _ob_p in ((op_state.active or []) + (op_state.bench or [])):
                if _ob_p is not None and _ob_p.id in OP_BENCH_BURST:
                    _op_burst = max(_op_burst, OP_BENCH_BURST[_ob_p.id])
            estimated_op_damage += _op_burst

            if estimated_op_damage >= my_active.hp:
                active_ko_likely = True
            elif my_active.hp <= 60 and op_energy >= 2:
                active_ko_likely = True
            elif active_hp_ratio <= 0.3 and op_energy >= 1:
                active_ko_likely = True

            # Pivote defensivo con Teal Dance (user): si el activo es un Teal
            # Mask Ogerpon ex CONDENADO que NO podra atacar este turno (necesita
            # 3 de energia) y en la banca hay un Hydrapple ex a vida completa
            # (muro de 330), la linea correcta es usar Teal Dance en el activo
            # (adjunta Grass + ROBA 1) para tambien habilitar su retirada (coste
            # 1) y luego RETIRAR para subir al cuerpo mas fuerte (Hydrapple ex),
            # aunque aun no pueda atacar: no se regala el activo por nada.
            if (active_ko_likely
                    and my_active.id == Teal_Mask_Ogerpon_ex
                    and (len(my_active.energies) + _grass_attach_unit()) < 3
                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                for _twp_bp in (my_state.bench or []):
                    if (_twp_bp is not None and _twp_bp.id == Hydrapple_ex
                            and _twp_bp.hp >= (_twp_bp.maxHp or 0)):
                        _teal_wall_pivot = True
                        break

    # Bloqueo de ITEMS rival (P1.5). El flag conserva su nombre historico
    # (`itchy_pollen_active`, por el Itchy Pollen de Budew) pero desde el plan
    # jul 2026 significa "NO podemos jugar Items este turno" por CUALQUIER
    # fuente: (a) Itchy Pollen de Budew (ataque rival el turno pasado),
    # (b) Fulgurite de Galvantula ex (idem, attackId 210), (c) Jellicent ex
    # "Oceanic Curse" o Tyranitar "Daunting Gaze" MIENTRAS esten en el activo
    # rival. Con 10+ items en el mazo (UBx4/BCSx4/NSx2/Stamp/PokePad) todos
    # los consumidores del flag re-priorizan Supporters/habilidades.
    itchy_pollen_active = False
    for log in obs.logs:
        if hasattr(log, 'type') and log.type == LogType.ATTACK:
            if log.cardId == Budew and log.playerIndex != my_index:
                itchy_pollen_active = True
            elif (log.cardId == Galvantula_ex
                    and getattr(log, 'attackId', None) == FULGURITE_ATTACK_ID
                    and log.playerIndex != my_index):
                itchy_pollen_active = True
    if (op_state.active and op_state.active[0] is not None
            and op_state.active[0].id in OP_ITEM_LOCK_ACTIVE_IDS):
        itchy_pollen_active = True

    op_active_dodge_immune = False
    _dodge_pending_serial = None
    for log in obs.logs:
        _lt = getattr(log, 'type', None)
        if _lt == LogType.ATTACK:
            if (getattr(log, 'cardId', None) == Hops_Phantump
                    and getattr(log, 'attackId', None) == Splashing_Dodge_Atk
                    and getattr(log, 'playerIndex', None) != my_index):
                _dodge_pending_serial = getattr(log, 'serial', None)
        elif _lt == COIN_FLIP_LOG_TYPE:

            if (_dodge_pending_serial is not None
                    and getattr(log, 'playerIndex', None) != my_index):
                if getattr(log, 'head', False):

                    if (op_state.active and op_state.active[0] is not None
                            and getattr(op_state.active[0], 'serial', None)
                            == _dodge_pending_serial):
                        op_active_dodge_immune = True

                        ESTADO._dodge_immune_serial = _dodge_pending_serial
                        ESTADO._dodge_immune_turn = state.turn
                _dodge_pending_serial = None

    if (not op_active_dodge_immune
            and ESTADO._dodge_immune_serial is not None
            and ESTADO._dodge_immune_turn == state.turn
            and op_state.active and op_state.active[0] is not None
            and getattr(op_state.active[0], 'serial', None) == ESTADO._dodge_immune_serial):
        op_active_dodge_immune = True

    budew_on_op_field = False
    budew_op_index = -1
    if op_state.active and op_state.active[0] is not None and op_state.active[0].id == Budew:
        budew_on_op_field = True
        budew_op_index = 0
    else:
        for idx, pokemon in enumerate(op_state.bench):
            if pokemon is not None and pokemon.id == Budew:
                budew_on_op_field = True
                budew_op_index = idx + 1
                break

    op_has_ex_immune_active = False
    op_has_ex_immune_bench = False
    op_has_ability_immune_active = False
    op_has_sturdy_crustle = False
    op_has_dwebble_bench = False
    op_has_crustle_bench = False

    op_has_froslass = False
    op_has_snorunt_bench = False
    op_has_munkidori = False
    op_has_dragapult = False
    op_has_dreepy_line = False
    op_has_typhlosion = False
    op_has_ethan_preevo = False
    op_is_fire_deck = False
    op_is_mirror = False
    op_bench_snipe_threat = False
    op_has_latias_ex = False

    op_is_greninja_deck = False
    op_is_slowking_deck = False
    op_is_beedrill_deck = False
    op_is_drednaw_deck = False
    op_is_sylveon_deck = False
    op_has_eevee_bench = False
    op_has_non_immune_eevee_ex = False
    op_is_dragapult_dusknoir = False
    op_is_alakazam_deck = False
    op_is_gardevoir_deck = False
    op_is_zoroark_deck = False
    op_is_aggro_deck = False
    op_is_control_deck = False
    op_has_mega_starmie_active = False
    op_is_lucario_deck = False
    op_is_cubchoo_deck = False
    op_is_hop_deck = False
    op_is_comfey_deck = False
    op_is_raging_bolt_deck = False
    op_is_abomasnow_deck = False
    # Iron Thorns ex en el CAMPO rival (P1.4 plan B): aunque no este de activo
    # todavia, su presencia anuncia el lock de habilidades -> el plan pivota a
    # los atacantes SIN habilidad con Rule Box (Tapu Bulu, linea Meganium).
    op_is_iron_thorns_deck = False
    op_active_is_dunsparce = False
    if op_state.active and op_state.active[0] is not None:
        op_active_id = op_state.active[0].id
        if op_active_id in EX_IMMUNE_IDS:
            op_has_ex_immune_active = True
        if op_active_id in ABILITY_IMMUNE_IDS:
            op_has_ability_immune_active = True
        if op_active_id in (Cornerstone_Mask_Ogerpon_ex,
                            Cornerstone_Mask_Ogerpon):
            ESTADO.op_is_cornerstone_deck = True
        if op_active_id == Crustle_Fighting:
            op_has_sturdy_crustle = True
        if op_active_id in (Crustle_Grass, Crustle_Fighting, Dwebble_Grass, Dwebble_Fighting):
            ESTADO.op_is_crustle_deck = True
        if op_active_id == Mega_Kangaskhan_ex:
            ESTADO.op_has_mega_kangaskhan = True
        if op_active_id == Froslass:
            op_has_froslass = True
        if op_active_id == Munkidori:
            op_has_munkidori = True
        if op_active_id == Dragapult_ex:
            op_has_dragapult = True
            op_bench_snipe_threat = True
        if op_active_id == Typhlosion:
            op_has_typhlosion = True
        if op_active_id in (Cyndaquil, Quilava):
            op_has_ethan_preevo = True
        if op_active_id == Grimmsnarl_ex:
            op_bench_snipe_threat = True
        if op_active_id == Mega_Starmie_ex and len(op_state.active[0].energies) >= 1:

            op_has_mega_starmie_active = True
            op_bench_snipe_threat = True
        if op_active_id == Latias_ex:
            op_has_latias_ex = True
        if op_active_id in (Riolu, Mega_Lucario_ex):
            op_is_lucario_deck = True
        if op_active_id in (Cubchoo, Beartic):
            op_is_cubchoo_deck = True
        if op_active_id in (Hops_Phantump, Hops_Trevenant):
            op_is_hop_deck = True
        if op_active_id in (Comfey, Bramblin, Brambleghast):
            op_is_comfey_deck = True
        if op_active_id in DUNSPARCE_IDS:
            op_active_is_dunsparce = True

        op_active_data = card_table.get(op_active_id)
        if op_active_data and op_active_data.energyType == EnergyType.FIRE:
            op_is_fire_deck = True

        if op_active_id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex, Dipplin, Applin, Meganium, Bayleef, Chikorita):
            op_is_mirror = True

        if op_active_id == Mega_Greninja_ex:
            op_is_greninja_deck = True
            op_bench_snipe_threat = True
        if op_active_id in (Slowpoke, Slowking):
            op_is_slowking_deck = True
            op_is_control_deck = True
        if op_active_id in (Weedle, Kakuna, Beedrill):
            op_is_beedrill_deck = True
            op_is_aggro_deck = True
        if op_active_id in (Chewtle, Drednaw):
            op_is_drednaw_deck = True
        if op_active_id == Sylveon or op_active_id in EEVEE_IDS:
            op_is_sylveon_deck = True
            ESTADO.op_is_crustle_deck = True
        if op_active_id == Eevee_PRE_ex:
            op_has_non_immune_eevee_ex = True
        if op_active_id in (Abra, Kadabra, Alakazam_ex):
            op_is_alakazam_deck = True
        if op_active_id in (Ralts, Kirlia, Gardevoir_ex):
            op_is_gardevoir_deck = True
        if op_active_id in (Zorua_N, Zoroark_N):
            op_is_zoroark_deck = True
        if op_active_id in (Raging_Bolt_ex, Lugia_VSTAR):
            op_is_aggro_deck = True
        if op_active_id == Raging_Bolt_ex:
            op_is_raging_bolt_deck = True
        if op_active_id in (Snover, Mega_Abomasnow_ex):
            op_is_abomasnow_deck = True
        if op_active_id == Iron_Thorns_ex:
            op_is_iron_thorns_deck = True
    for idx, pokemon in enumerate(op_state.bench):
        if pokemon is not None:
            if pokemon.id in EX_IMMUNE_IDS:
                op_has_ex_immune_bench = True
            if pokemon.id in (Cornerstone_Mask_Ogerpon_ex,
                              Cornerstone_Mask_Ogerpon):
                ESTADO.op_is_cornerstone_deck = True
            if pokemon.id == Crustle_Fighting:
                op_has_sturdy_crustle = True
            if pokemon.id in (Dwebble_Grass, Dwebble_Fighting):
                op_has_dwebble_bench = True
                ESTADO.op_is_crustle_deck = True
            if pokemon.id in (Crustle_Grass, Crustle_Fighting):
                ESTADO.op_is_crustle_deck = True
                op_has_crustle_bench = True
            if pokemon.id == Mega_Kangaskhan_ex:
                ESTADO.op_has_mega_kangaskhan = True
            if pokemon.id in (Comfey, Bramblin, Brambleghast):
                op_is_comfey_deck = True
            if pokemon.id == Froslass:
                op_has_froslass = True
            if pokemon.id == Snorunt:
                op_has_snorunt_bench = True
            if pokemon.id == Munkidori:
                op_has_munkidori = True
            if pokemon.id == Dragapult_ex:
                op_has_dragapult = True
                op_bench_snipe_threat = True
            if pokemon.id == Typhlosion:
                op_has_typhlosion = True
            if pokemon.id in (Cyndaquil, Quilava):
                op_has_ethan_preevo = True
            if pokemon.id == Grimmsnarl_ex:
                op_bench_snipe_threat = True
            if pokemon.id in (Dreepy, Drakloak):
                op_has_dreepy_line = True
            if pokemon.id == Latias_ex:
                op_has_latias_ex = True
            if pokemon.id in (Riolu, Mega_Lucario_ex):
                op_is_lucario_deck = True
            if pokemon.id in (Cubchoo, Beartic):
                op_is_cubchoo_deck = True
            if pokemon.id in (Hops_Phantump, Hops_Trevenant):
                op_is_hop_deck = True
            if pokemon.id == Iron_Thorns_ex:
                op_is_iron_thorns_deck = True

            bench_data = card_table.get(pokemon.id)
            if bench_data and bench_data.energyType == EnergyType.FIRE:
                op_is_fire_deck = True

            if pokemon.id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex, Dipplin, Applin, Meganium, Bayleef, Chikorita):
                op_is_mirror = True

            if pokemon.id in (Mega_Greninja_ex,):
                op_is_greninja_deck = True
                op_bench_snipe_threat = True
            if pokemon.id in (Slowpoke, Slowking):
                op_is_slowking_deck = True
                op_is_control_deck = True
            if pokemon.id in (Weedle, Kakuna, Beedrill):
                op_is_beedrill_deck = True
                op_is_aggro_deck = True
            if pokemon.id in (Chewtle, Drednaw):
                op_is_drednaw_deck = True
            if pokemon.id == Sylveon or pokemon.id in EEVEE_IDS:
                op_is_sylveon_deck = True
                ESTADO.op_is_crustle_deck = True
                if pokemon.id in EEVEE_IDS:
                    op_has_eevee_bench = True
                if pokemon.id == Eevee_PRE_ex:
                    op_has_non_immune_eevee_ex = True
            if pokemon.id in (Duskull, Dusclops, Dusknoir):
                op_is_dragapult_dusknoir = op_has_dragapult or op_has_dreepy_line
            if pokemon.id in (Abra, Kadabra, Alakazam_ex):
                op_is_alakazam_deck = True
            if pokemon.id in (Ralts, Kirlia, Gardevoir_ex):
                op_is_gardevoir_deck = True
            if pokemon.id in (Zorua_N, Zoroark_N):
                op_is_zoroark_deck = True
            if pokemon.id in (Raging_Bolt_ex, Lugia_VSTAR):
                op_is_aggro_deck = True
            if pokemon.id == Raging_Bolt_ex:
                op_is_raging_bolt_deck = True
            if pokemon.id in (Snover, Mega_Abomasnow_ex):
                op_is_abomasnow_deck = True

    # Inferencia de arquetipo por el DESCARTE rival (auditoria julio 2026,
    # sugerencia 7): la deteccion por Pokemon EN JUEGO llega tarde contra
    # lineas ocultas; un Pokemon del arquetipo en el descarte identifica el
    # mazo 2-3 turnos antes y activa las preparaciones a tiempo (reserva de
    # banca/Xerosic vs Alakazam, plan solo-Ogerpon vs Comfey, whitelist vs
    # Cubchoo...). Solo se infieren flags ESTRATEGICOS de mazo; los flags de
    # "muro en juego" (Crustle/Sylveon/Cornerstone: redirigen el ataque YA) y
    # los `op_has_*` posicionales se quedan como estan (dependen del tablero).
    for _dc in (op_state.discard or []):
        _dcid = getattr(_dc, 'id', 0)
        if _dcid in (Abra, Kadabra, Alakazam_ex):
            op_is_alakazam_deck = True
        elif _dcid in (Comfey, Bramblin, Brambleghast):
            op_is_comfey_deck = True
        elif _dcid in (Riolu, Mega_Lucario_ex):
            op_is_lucario_deck = True
        elif _dcid in (Hops_Phantump, Hops_Trevenant):
            op_is_hop_deck = True
        elif _dcid in (Cubchoo, Beartic):
            op_is_cubchoo_deck = True
        elif _dcid in (Ralts, Kirlia, Gardevoir_ex):
            op_is_gardevoir_deck = True
        elif _dcid in (Zorua_N, Zoroark_N):
            op_is_zoroark_deck = True
        elif _dcid in (Slowpoke, Slowking):
            op_is_slowking_deck = True
            op_is_control_deck = True
        elif _dcid == Raging_Bolt_ex:
            op_is_aggro_deck = True
            op_is_raging_bolt_deck = True
        elif _dcid in (Snover, Mega_Abomasnow_ex):
            op_is_abomasnow_deck = True
        elif _dcid == Lugia_VSTAR:
            op_is_aggro_deck = True
        elif _dcid in (Cornerstone_Mask_Ogerpon_ex, Cornerstone_Mask_Ogerpon):
            # Flag de PLAN del matchup (linea Meganium prioritaria, whitelist
            # con Tapu Bulu): verlo en el descarte identifica el mazo. El flag
            # POSICIONAL del muro (op_has_ability_immune_active) sigue
            # dependiendo solo del tablero.
            ESTADO.op_is_cornerstone_deck = True

    # Eevee ex (id 249) NO es el muro Sylveon: es un ex atacable. Si el rival
    # sigue la linea Eevee ex y no hay ningun muro inmune real (Sylveon) en
    # juego, revocamos la estrategia anti-muro y volvemos a la estrategia ex:
    # atacamos ese ex con nuestros ex y evolucionamos Dipplin -> Hydrapple ex.
    if op_has_non_immune_eevee_ex and not (op_has_ex_immune_active or op_has_ex_immune_bench):
        ESTADO.op_is_crustle_deck = False
        op_is_sylveon_deck = False

    # Dano proyectado del snipe rival sobre UN Pokemon de nuestra banca por turno
    # (ver OP_BENCH_SNIPE_DAMAGE). Se toma el MAXIMO entre los snipers que el
    # rival tiene EN JUEGO: es el goteo que hay que sobrevivir cada turno.
    ESTADO._op_bench_snipe_dmg = 0
    if op_bench_snipe_threat:
        for _bs_pk in ([_active_of(op_state)] + list(op_state.bench or [])):
            if _bs_pk is None:
                continue
            if _bs_pk.id in OP_BENCH_SNIPE_DAMAGE:
                ESTADO._op_bench_snipe_dmg = max(
                    ESTADO._op_bench_snipe_dmg, OP_BENCH_SNIPE_DAMAGE[_bs_pk.id])
        if ESTADO._op_bench_snipe_dmg == 0:
            ESTADO._op_bench_snipe_dmg = OP_BENCH_SNIPE_DEFAULT

    # --- Las otras dos patas de LA VENTANA DE REGALO -----------------------
    # Se arman por PRESENCIA de las piezas en mesa (Froslass / Munkidori), no
    # por matchup completo: cualquier mazo que las juegue reparte el mismo
    # goteo. Ver el bloque de constantes homonimo.
    _n_froslass = 0
    _n_munkidori_cargado = 0
    _hay_munkidori_seco = False
    _op_counters_en_mesa = 0
    for _vr_pk in ([_active_of(op_state)] + list(op_state.bench or [])):
        if _vr_pk is None:
            continue
        _op_counters_en_mesa += max(0, (_vr_pk.maxHp or 0) - (_vr_pk.hp or 0))
        if _vr_pk.id == Froslass:
            _n_froslass += 1
        elif _vr_pk.id == Munkidori:
            if len(_vr_pk.energies or []) >= 1:
                _n_munkidori_cargado += 1
            else:
                _hay_munkidori_seco = True

    ESTADO._op_chip_per_round = (FREEZING_SHROUD_COUNTER * _n_froslass
                          * CHECKUPS_PER_ROUND)

    # Un Munkidori SIN energia que ya esta en mesa vale una activacion mas: al
    # rival le queda su adjunte del turno. Ignorarlo subestimaba justo el turno
    # que decide (partida 2 turno 10: el rival bajo un Munkidori, le adjunto una
    # Oscura y con las dos activaciones mato al Ogerpon de banca a 80 PV).
    _n_activaciones = _n_munkidori_cargado + (1 if _hay_munkidori_seco else 0)
    # Adrena-Brain solo mueve contadores que YA existen en su mesa, pero antes
    # de que el rival juegue hay un chequeo mas (el del final de NUESTRO turno)
    # que recarga 10 por Froslass sobre cada Munkidori -- todos tienen
    # habilidad. Sin ese termino el techo se subestima justo en el turno en que
    # el rival remata.
    _op_counters_disponibles = (
        _op_counters_en_mesa
        + FREEZING_SHROUD_COUNTER * _n_froslass * _n_activaciones)
    ESTADO._op_movable_dmg = min(ADRENA_BRAIN_MOVE * _n_activaciones,
                          _op_counters_disponibles)

    # DESCUADRE DE PREMIOS (user): matchups cuyo atacante ONE-SHOTEA a cualquiera
    # de nuestros ex -> Raging Bolt (Bellowing Thunder) y Mega Abomasnow ex. La
    # regla: siempre que nuestro activo sea un ex que NO puede noquear al activo
    # rival este turno, poner delante un cuerpo de UN premio (bajar un basico no-ex
    # de la mano y/o retirar el ex para promoverlo) -- si nos noquean ceden 1
    # premio y no 2, y su mazo (todo ex de 2-3 premios) necesita KOs grandes para
    # ganar a tiempo. EXCEPCION (user, registro_002 vs Mega Abomasnow ex): la regla
    # NO aplica en NUESTRO primer turno partiendo PRIMEROS -- ese primer turno no
    # atacamos y el rival aun no puede noquearnos su siguiente turno, asi que
    # sacrificar desarrollo temprano solo nos atrasa. Si vamos SEGUNDOS (nuestro
    # primer turno es turno 2) o en cualquier turno posterior, SI aplica.
    _descuadre_matchup = (
        (op_is_raging_bolt_deck or op_is_abomasnow_deck)
        and not (state.turn == 1 and ESTADO.we_go_first))

    total_grass = count_total_grass_energy(my_state)

    # Pivote-muro a Hydrapple ex SIN KO (user, log 85856881 paso 127, vs Mega
    # Lucario ex, partida GANADA). A diferencia de `_teal_wall_pivot` (activo que
    # NO puede atacar), aqui el Teal Mask Ogerpon ex activo SI puede atacar, pero
    # su Myriad Leaf Shower NO noquea al rival y el Mega Lucario ex lo remata el
    # proximo turno (Mega Brave, 270 > 210 HP). Si en la banca hay un Hydrapple
    # ex a vida completa (muro de 330 HP) que SOBREVIVE al mejor golpe rival y
    # puede atacar (>=2 efectivas), la linea correcta es RETIRAR el Ogerpon
    # fragil y subir al muro: resiste el golpe y sigue presionando (Syrup Storm
    # 330), en vez de atacar con el Ogerpon que moriria regalando 2 premios. El
    # unico modo de retirarse en este motor es elegir PASS en el menu principal
    # (expone el prompt de retirada, ctx=30); por eso mas abajo apuntamos el plan
    # al Hydrapple de banca para SUPRIMIR la opcion de atacar con el Ogerpon.
    # Acotado a Mega Lucario (remate rival fijo y alto).
    _hydra_wall_pivot = False
    _hwp_active = my_state.active[0] if my_state.active else None
    _hwp_op_active = _active_of(op_state)
    if (op_is_lucario_deck and active_ko_likely
            and _hwp_active is not None
            and _hwp_active.id == Teal_Mask_Ogerpon_ex
            and len(_hwp_active.energies) >= 3
            and _hwp_op_active is not None):
        _hwp_op_hp = _hwp_op_active.hp or 0
        _hwp_oger_dmg = 30 + 30 * (
            len(_hwp_active.energies) + len(_hwp_op_active.energies))
        _hwp_oger_ko = (_hwp_op_hp > 0 and _hwp_oger_dmg >= _hwp_op_hp)
        _hwp_ret_phys = _physical_energy(len(_hwp_active.energies))
        _hwp_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        if not _hwp_oger_ko and _hwp_ret_phys >= _hwp_ret_cost:
            for _hwp_bp in (my_state.bench or []):
                if (_hwp_bp is not None and _hwp_bp.id == Hydrapple_ex
                        and _hwp_bp.hp >= (_hwp_bp.maxHp or 0)
                        and len(_hwp_bp.energies) * _grass_mult() >= 2
                        and (_hwp_bp.hp or 0) > _op_best_damage_vs(_hwp_bp)):
                    _hydra_wall_pivot = True
                    break

    # Generalizacion del pivote-muro (user, registro_006 paso 84, vs Archaludon
    # ex, PERDIDA): el mismo patron aplica contra CUALQUIER rival, no solo Mega
    # Lucario. Si el Teal Mask Ogerpon ex activo SI puede atacar (>=3 energia)
    # pero su Myriad Leaf Shower NO noquea al activo rival, y el ATAQUE del activo
    # rival NOQUEA a nuestro Ogerpon el proximo turno pero un Hydrapple ex sano de
    # banca (muro 330) SOBREVIVE ese golpe y puede atacar (Syrup Storm > 0), la
    # linea correcta es RETIRAR el Ogerpon condenado y promover el muro (sobrevive
    # y sigue presionando) en vez de atacar con el Ogerpon fragil que moriria
    # regalando 2 premios. A diferencia de la rama Mega Lucario (acotada por deck
    # flag + active_ko_likely heuristico, porque no leia el dano rival), aqui
    # exigimos el remate rival REAL (`_op_active_attack_damage_to`, que resuelve
    # el ataque via attack_table) tanto para condenar al activo como para validar
    # que el muro sobrevive. Si el ataque rival no se puede leer (dano None),
    # el helper da 0 y el pivote NO dispara (conservador). Powerful Hand de
    # Alakazam SI se modela (20 x (mano rival + 2), pasando op_hand_count):
    # vs Alakazam este pivote ahora puede disparar; si a la vez hay un cuerpo
    # de 1 premio que noquea (_alakazam_pivot_1prize), el RETIRO se dispara
    # igual y la PROMOCION la resuelve el bloque `op_is_alakazam_deck` de
    # _best_promote_card (1 premio > muro), que va ULTIMO en esa cadena.
    if (not _hydra_wall_pivot and _hwp_active is not None
            and _hwp_active.id == Teal_Mask_Ogerpon_ex
            and len(_hwp_active.energies) >= 3
            and _hwp_op_active is not None):
        _gwp_op_hp = _hwp_op_active.hp or 0
        _gwp_oger_dmg = _our_effective_damage(
            _hwp_active, _hwp_op_active,
            30 + 30 * (len(_hwp_active.energies) + len(_hwp_op_active.energies)),
            ESTADO.meganium_in_play, neutralization_zone_active)
        _gwp_oger_ko = (_gwp_op_hp > 0 and _gwp_oger_dmg >= _gwp_op_hp)
        _gwp_ret_phys = _physical_energy(len(_hwp_active.energies))
        _gwp_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        # Pasar la mano rival habilita la proyeccion de Powerful Hand
        # (20 x (mano+2)) -- sin ella el helper daba 0 vs Alakazam y este
        # pivote jamas disparaba en ese matchup (sugerencia 1 anti-Alakazam).
        _gwp_op_hand = getattr(op_state, 'handCount', None)
        _gwp_op_dmg_active = _op_active_attack_damage_to(
            _hwp_op_active, _hwp_active, _gwp_op_hand)
        if (not _gwp_oger_ko and _gwp_ret_phys >= _gwp_ret_cost
                and _gwp_op_dmg_active >= (_hwp_active.hp or 0)):
            for _gwp_bp in (my_state.bench or []):
                if (_gwp_bp is not None and _gwp_bp.id == Hydrapple_ex
                        and _gwp_bp.hp >= (_gwp_bp.maxHp or 0)
                        and len(_gwp_bp.energies) * _grass_mult() >= 2
                        and (_gwp_bp.hp or 0) > _op_active_attack_damage_to(
                            _hwp_op_active, _gwp_bp, _gwp_op_hand)):
                    _gwp_wall_dmg = _our_effective_damage(
                        _gwp_bp, _hwp_op_active, 30 + 30 * total_grass,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    if _gwp_wall_dmg > 0:
                        _hydra_wall_pivot = True
                        break

    # Muro Feza -> Hydrapple ex vs Mega Lucario (user, log 86342087 paso 130,
    # PERDIMOS): si el ACTIVO es un Fezandipiti ex DEBIL a Lucha que sera
    # NOQUEADO por Mega Lucario ex el proximo turno (Mega Brave 270 x2 = 540,
    # 2 premios) y en la banca hay un Hydrapple ex sano (muro 330 que SOBREVIVE
    # el golpe rival, debilidad {R} no {F}), la linea correcta NO es cargar y
    # atacar con el Feza condenado (muere regalando 2 premios) sino cargar al
    # Hydrapple (ver energy_score), RETIRAR al Feza (coste 1) y promover el muro
    # para atacar. `_feza_lucario_wall` habilita esa carga; aqui, una vez el
    # Hydrapple ya esta listo (>=2 efectivas), activamos el pivote-muro para
    # suprimir el ataque del Feza y exponer la retirada (mismo mecanismo que el
    # pivote de Ogerpon de arriba). El Feza debe poder retirarse ya (energia
    # fisica >= coste de retirada 1).
    _feza_lucario_wall = False
    if (op_is_lucario_deck and active_ko_likely
            and _hwp_active is not None
            and _hwp_active.id == Fezandipiti_ex
            and _hwp_op_active is not None):
        _flw_ret_phys = _physical_energy(len(_hwp_active.energies))
        _flw_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        if _flw_ret_phys >= _flw_ret_cost:
            for _flw_bp in (my_state.bench or []):
                if (_flw_bp is not None and _flw_bp.id == Hydrapple_ex
                        and _flw_bp.hp >= (_flw_bp.maxHp or 0)
                        and (_flw_bp.hp or 0) > _op_best_damage_vs(_flw_bp)):
                    _feza_lucario_wall = True
                    if len(_flw_bp.energies) * _grass_mult() >= 2:
                        # Hydrapple ya cargado: activar el pivote-muro para
                        # retirar el Feza y promover el muro (reusa el bloque de
                        # reasignacion de plan.attacker de mas abajo).
                        _hydra_wall_pivot = True

    # Pivote Hydrapple ex FRAGIL: retirar el activo con poca vida y promover al
    # sano (user, log 86027506 paso 81, vs Abomasnow, GANADA). Si el ACTIVO es un
    # Hydrapple ex con poca vida (en riesgo de KO) y en la BANCA hay OTRO
    # Hydrapple ex a (casi) plena vida, que SOBREVIVE al mejor golpe rival y esta
    # listo para un Syrup Storm LETAL, la linea correcta es RETIRAR el fragil para
    # protegerlo (si se queda activo lo noquean el proximo turno = 2 premios) y
    # SUBIR al sano a rematar (mismo KO, pero desde el cuerpo sano). El motor solo
    # ofrece retirada si el activo tiene energia FISICA >= su coste de retirada
    # (3 para Hydrapple ex); por eso hay que ROUTEAR la energia de este turno
    # (adjunte manual + Ripening Charge) al ACTIVO fragil hasta alcanzar ese coste
    # en vez de dejarla en el Hydrapple de banca (que ya esta cargado). Este flag
    # habilita esa carga en `energy_score`; el retiro+promocion posterior lo cubre
    # `_hydra_lethal_promote` (retiro con score 9000) una vez que can_switch pasa
    # a True.
    _hydra_fragile_pivot = False
    _hfp_active = my_state.active[0] if my_state.active else None
    _hfp_opa = _active_of(op_state)
    if (_hfp_active is not None and _hfp_active.id == Hydrapple_ex
            and _hfp_opa is not None and (_hfp_opa.hp or 0) > 0
            and (active_ko_likely
                 or (_hfp_active.hp or 0) <= (_hfp_active.maxHp or 1) * 0.5)):
        _hfp_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _hfp_phys = _physical_energy(len(_hfp_active.energies))
        if _hfp_phys < _hfp_rc:
            for _hfp_bp in (my_state.bench or []):
                if (_hfp_bp is not None and _hfp_bp.id == Hydrapple_ex
                        and (_hfp_bp.hp or 0) > (_hfp_active.hp or 0)
                        and (_hfp_bp.hp or 0) > _op_best_damage_vs(_hfp_bp)
                        and len(_hfp_bp.energies) * _grass_mult() >= 2):
                    _hfp_bdmg = _our_effective_damage(
                        _hfp_bp, _hfp_opa, 30 + 30 * total_grass,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    if _hfp_bdmg > 0 and _hfp_bdmg >= (_hfp_opa.hp or 0):
                        _hydra_fragile_pivot = True
                        break

    _conf_active = my_state.active[0] if my_state.active else None
    # El muro inmune a ex (Crustle/Sylveon) o a habilidad (Cornerstone) solo veta
    # promover un ex CUANDO ESTA EN EL ACTIVO rival: es a quien atacaria el ex
    # tras el pivote de confusion. Con el muro en la BANCA rival y un Pokemon
    # ATACABLE en el activo (p.ej. Munkidori en un mazo Crustle), nuestro Ogerpon
    # ex SI lo noquea, asi que debe contar como atacante valido del pivote (user,
    # registro_006 paso 64 vs Crustle: el Dipplin activo a 10 PV y CONFUNDIDO
    # atacaba -- arriesgando el auto-KO si falla la moneda -- en vez de retirarse
    # (Meganium hace que su Planta pague el coste de retirada 2) y subir el
    # Ogerpon ex cargado que noquea al Munkidori). Los flags de MAZO
    # (op_is_crustle_deck/op_is_cornerstone_deck) y el de banca
    # (op_has_ex_immune_bench) son demasiado amplios: valen aunque el activo sea
    # atacable, y vetaban el pivote ganador.
    _conf_ex_immune_match = (op_has_ex_immune_active or op_has_ability_immune_active)

    def _conf_can_attack_pkmn(_p):
        if _p is None:
            return False
        _e = len(_p.energies)
        _eff = _e * _grass_mult()
        if _p.id == Hydrapple_ex:
            return _eff >= 2
        if _p.id == Dipplin:
            return _e >= 1
        if _p.id == Teal_Mask_Ogerpon_ex:
            return _eff >= 3
        if _p.id == Tapu_Bulu:
            return _eff >= 4
        if _p.id == Pinsir:
            return _eff >= 2
        if _p.id == Fezandipiti_ex:
            return _eff >= 3
        return False

    def _conf_is_matchup_attacker(_pid):
        if _conf_ex_immune_match:
            return _pid in (Tapu_Bulu, Dipplin, Pinsir)
        return _pid in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
                        Tapu_Bulu, Pinsir, Fezandipiti_ex)

    _conf_bench_attacker_ready = any(
        bp is not None and _conf_is_matchup_attacker(bp.id) and _conf_can_attack_pkmn(bp)
        for bp in (my_state.bench or []))
    _conf_bench_attacker_body = any(
        bp is not None and _conf_is_matchup_attacker(bp.id)
        for bp in (my_state.bench or []))
    _conf_active_can_retreat = False
    if is_confused and _conf_active is not None:
        # Wild Growth de Meganium duplica cada energia basica de Planta, asi que
        # la energia efectiva puede cubrir el coste de retirada con menos cartas
        # (p.ej. Meganium con 1 energia = {G}{G} -> paga su retirada de 2).
        _conf_ret_eff = len(_conf_active.energies) * _grass_mult()
        _conf_active_can_retreat = (
            _conf_ret_eff >= RETREAT_COST.get(_conf_active.id, 1))
    _conf_active_can_attack = bool(is_confused and _conf_can_attack_pkmn(_conf_active))
    _conf_should_retreat = bool(
        is_confused and _conf_active_can_retreat and _conf_bench_attacker_ready)
    _conf_should_attack = bool(
        is_confused and not _conf_bench_attacker_ready and _conf_active_can_attack)

    can_attack = False
    _active_cant_attack_this_turn = False
    _hydra_pivot_active = False
    _tapu_sac_pivot = False
    _tapu_sac_enable_retreat = False
    _prize_denial_pivot = False

    _bo_active_attack_sufficient = False

    can_switch = False
    can_op_switch = False
    has_switch_card = False
    if context == SelectContext.MAIN:
        can_switch = False
        can_op_switch = False
        for o in select.option:
            if o.type == OptionType.PLAY:
                card = get_card(obs, AreaType.HAND, o.index, my_index)
                if card is not None:
                    if card.id == Boss_Orders:
                        can_op_switch = True
            elif o.type == OptionType.RETREAT:
                can_switch = True
            elif o.type == OptionType.ATTACK:
                can_attack = True

        has_switch_card = False
        for o in select.option:
            if o.type == OptionType.PLAY:
                card = get_card(obs, AreaType.HAND, o.index, my_index)
                if card is not None and card.id == 1123:
                    can_switch = True
                    has_switch_card = True

        my_cards = [my_state.active[0]] if my_state.active else []
        for pokemon in my_state.bench:
            if pokemon is not None:
                my_cards.append(pokemon)
        op_cards = [op_state.active[0]] if op_state.active else []
        for pokemon in op_state.bench:
            if pokemon is not None:
                op_cards.append(pokemon)

        # ¿El ACTIVO ya noquea al activo rival con la energia que YA tiene?
        # Se usa como guarda de la proyeccion "Planta extra via Night Stretcher"
        # de abajo: si el activo remata, la Planta recuperada no desbloquea
        # ningun KO nuevo y la Night Stretcher NO se jugara
        # (`_ns_e_remate_via_promocion` lleva la misma guarda). Sin este espejo
        # el plan proyectaria un KO de banca que depende de una carta que nadie
        # va a jugar y vetaria el ataque del activo.
        _plan_act_kos_now = False
        _pakn_act = my_cards[0] if my_cards else None
        _pakn_op = op_cards[0] if op_cards else None
        if _pakn_act is not None and _pakn_op is not None:
            _pakn_e = len(_pakn_act.energies)
            _pakn_base = _attacker_base_damage(
                _pakn_act.id, _pakn_op, _pakn_e * _grass_mult(),
                grass_scale=total_grass, teal_self_energy=_pakn_e,
                bench_count=bench_count)
            _plan_act_kos_now = (
                _pakn_base > 0
                and _our_effective_damage(
                    _pakn_act, _pakn_op, _pakn_base, ESTADO.meganium_in_play,
                    neutralization_zone_active) >= (_pakn_op.hp or 0))

        # El rival SIN Pokemon en banca no puede promover un reemplazo si le
        # noqueamos el activo: ese KO GANA la partida (regla del juego), sin
        # importar el conteo de premios. Se usa para (a) reconocer el remate
        # ganador con el activo y (b) impedir que los pivotes de descuadre nos
        # desvien de el (user, registro_016 vs Crustle).
        _op_bench_empty = not any(
            b is not None for b in (op_state.bench or []))
        _active_win_plan = None

        if state.turn >= 2 and len(my_cards) > 0 and len(op_cards) > 0:
            best_score = SCORE_VETO
            # KO que el ACTIVO ya consigue sobre cada objetivo `j`, anotado como
            # (vida ACTUAL del activo, premios que entrega). Lo llena la vuelta
            # i == 0 -- el activo siempre es `my_cards[0]` y se recorre primero --
            # y lo consume `_pivote_banca_sin_ganancia` mas abajo, que es quien
            # compara al candidato de banca contra el cuerpo que YA esta delante.
            _atk_act_ko = {}
            for i, my_pokemon in enumerate(my_cards):
                if my_pokemon is None:
                    continue
                if i != 0 and not can_switch:
                    break

                attack_options = []
                if my_pokemon.id == Hydrapple_ex:

                    _syrup_grass = total_grass
                    # Un Hydrapple ex de BANCA (i >= 1) solo ataca si RETIRAMOS
                    # el activo, y ese retiro DESCARTA la energia del activo
                    # para pagar su coste: Syrup Storm escala con el Grass del
                    # campo, asi que hay que medirlo con el Grass que quedara
                    # DESPUES del retiro (user, registro_011 paso 138 vs
                    # Dragapult, PERDIDA). Alli el activo era un Tapu Bulu con
                    # 3 Plantas (6 efectivas): con el Grass previo (10) el
                    # Syrup Storm del Hydrapple de banca daba 330 y "noqueaba"
                    # al Dragapult ex de 320, asi que el plan lo elegia como
                    # atacante; al retirar se descartaban esas 3 Plantas y el
                    # ataque real quedaba en 150. Mismo patron que
                    # `_bo_grass_after` en la seleccion del gusteo.
                    if i >= 1 and not has_switch_card:
                        _sg_act = my_state.active[0] if my_state.active else None
                        if _sg_act is not None:
                            _syrup_grass = max(
                                0, _syrup_grass - _retreat_grass_units(
                                    RETREAT_COST.get(_sg_act.id, 1)))
                    # Planta que TODAVIA podemos poner en el campo este turno.
                    # La via no es solo el adjunte manual: Teal Dance y Ripening
                    # Charge son HABILIDADES y siguen vivas con `energyAttached`
                    # puesto. Y si no queda Planta en la mano pero SI en el
                    # descarte, Night Stretcher la recupera: cuenta como fuente
                    # de energia al medir el remate (user, registro_006 paso 78
                    # vs Archaludon ex, PERDIDA -- ver
                    # `_ns_e_remate_via_promocion`, que es quien luego PAGA por
                    # jugarla, de modo que esta proyeccion no es un espejismo).
                    _sg_ruta = _grass_attach_route_open(
                        state, field_counts, abilities_off=meowth_ability_lock)
                    # La Planta en mano se cuenta solo con el adjunte MANUAL
                    # disponible (criterio historico): contar tambien la via de
                    # habilidad aqui ensancharia el plan a muchos estados sin que
                    # el caso del usuario lo necesite, y el sentido seguro de
                    # este estimador es quedarse CORTO (si sobrestima, veta el
                    # ataque del activo por un KO de banca que no existe).
                    if (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and not state.energyAttached):
                        _syrup_grass += _grass_attach_unit()
                    elif (hand_counts.get(Basic_Grass_Energy, 0) == 0
                          and hand_counts.get(Night_Stretcher, 0) >= 1
                          and discard_counts.get(Basic_Grass_Energy, 0) >= 1
                          and _sg_ruta and not _plan_act_kos_now):
                        _syrup_grass += _grass_attach_unit()
                    syrup_dmg = 30 + 30 * _syrup_grass
                    attack_options.append((2, syrup_dmg, 0, True))
                elif my_pokemon.id == Dipplin:

                    wave_dmg = 20 * bench_count
                    attack_options.append((1, wave_dmg, 0, False))
                elif my_pokemon.id == Teal_Mask_Ogerpon_ex:

                    if len(op_cards) > 0:
                        op_active_energy = len(op_cards[0].energies) if op_cards[0] is not None else 0
                        my_energy = len(my_pokemon.energies)
                        # Myriad Leaf Shower cuenta la energia de AMBOS activos
                        # (regla VERIFICADA con 6 registros, ver
                        # _attacker_base_damage): la copia inline usaba solo
                        # nuestra energia y el argmax de ATAQUE subestimaba KOs
                        # reales (elegia otro atacante o un chip).
                        leaf_dmg = 30 + 30 * (my_energy + op_active_energy)
                        attack_options.append((3, leaf_dmg, 0, False))
                elif my_pokemon.id == Tapu_Bulu:

                    attack_options.append((4, 220, 0, False))
                elif my_pokemon.id == Meganium:

                    attack_options.append((4, 140, 0, False))
                elif my_pokemon.id == Fezandipiti_ex:

                    attack_options.append((3, 100, 0, True))
                elif my_pokemon.id == Pinsir:

                    attack_options.append((2, 100, 1, False))

                for energy_req, base_damage, attack_idx, colorless_ok in attack_options:
                    base_score = 0

                    energy_count = len(my_pokemon.energies)
                    more_energy = False
                    _ns_energy_recovery = False

                    effective_energy = energy_count * _grass_mult()

                    if effective_energy < energy_req:
                        if hand_counts[Basic_Grass_Energy] >= 1 and not state.energyAttached:
                            effective_energy += _grass_attach_unit()
                            if effective_energy < energy_req:
                                continue
                            else:
                                more_energy = True

                        elif (i != 0 and
                              hand_counts.get(Night_Stretcher, 0) >= 1 and
                              discard_counts.get(Basic_Grass_Energy, 0) >= 1 and
                              not state.energyAttached):
                            _ns_eff = _grass_attach_unit()
                            if effective_energy + _ns_eff >= energy_req:
                                more_energy = True
                                _ns_energy_recovery = True
                            else:
                                continue
                        else:
                            continue

                    my_is_ex = my_pokemon.id in OUR_EX_IDS

                    _op_active_is_drednaw = (op_state.active and op_state.active[0] is not None
                                             and op_state.active[0].id == Drednaw)
                    if my_pokemon.id == Hydrapple_ex:
                        base_score += 200
                        if op_has_ability_immune_active:
                            base_score -= 2000

                        if _op_active_is_drednaw:
                            _syrup_dmg_est = 30 + 30 * total_grass
                            if _syrup_dmg_est >= 200:
                                base_score -= 3000

                        elif op_is_fire_deck:
                            base_score += 150
                        elif op_is_aggro_deck:
                            base_score += 100
                    elif my_pokemon.id == Dipplin:
                        base_score += 50

                        if op_has_ex_immune_active:
                            base_score += 1200
                        if op_has_ability_immune_active:
                            base_score += 1500

                        if _op_active_is_drednaw:
                            base_score += 2500
                    elif my_pokemon.id == Tapu_Bulu:
                        if op_has_ex_immune_active:
                            base_score += 2200

                            if (op_state.active and op_state.active[0] is not None
                                    and op_state.active[0].id == Sylveon):
                                base_score += 800
                        elif op_has_ability_immune_active:
                            base_score += 2500
                        elif _op_active_is_drednaw:
                            base_score -= 3000
                        elif op_is_fire_deck:
                            base_score += 800

                        elif op_is_control_deck or op_is_slowking_deck:
                            base_score += 500
                        else:
                            base_score += 100
                    elif my_pokemon.id == Pinsir:
                        base_score += 50

                        if op_has_ex_immune_active:
                            base_score += 1300
                        if op_has_ability_immune_active:
                            base_score += 1600

                        if _op_active_is_drednaw:
                            base_score += 2300
                    elif my_pokemon.id == Meganium:
                        if op_has_ex_immune_active:
                            base_score += 1500

                            if (op_state.active and op_state.active[0] is not None
                                    and op_state.active[0].id == Sylveon):
                                base_score += 2000
                        if op_has_ability_immune_active:
                            base_score -= 2000

                        if _op_active_is_drednaw:
                            base_score += 3500
                    elif my_pokemon.id == Teal_Mask_Ogerpon_ex:
                        base_score -= 100
                        if op_has_ability_immune_active:
                            base_score -= 2000
                    elif my_pokemon.id == Fezandipiti_ex:

                        if op_has_ex_immune_active:
                            base_score -= 2000
                        if op_has_ability_immune_active:
                            base_score -= 2000

                    if neutralization_zone_active:
                        if my_is_ex:
                            base_score -= 3000
                        else:

                            base_score += 2000

                    for j, op_pokemon in enumerate(op_cards):
                        if op_pokemon is None:
                            continue

                        if j != 0 and not can_op_switch and my_pokemon.id != Fezandipiti_ex:
                            break

                        damage = base_damage
                        data = card_table[op_pokemon.id]

                        if op_pokemon.id in EX_IMMUNE_IDS and my_is_ex:
                            damage = 0

                        _op_has_rule_box = (data.ex or data.megaEx)
                        if (neutralization_zone_active and my_is_ex and
                                not _op_has_rule_box and damage > 0):
                            damage = 0

                        my_has_ability = (my_pokemon.id in OUR_ABILITY_IDS)
                        if op_pokemon.id in ABILITY_IMMUNE_IDS and my_has_ability:
                            damage = 0

                        # Farigiraf ex "Armor Tail" (P1.6): inmune a nuestros
                        # BASICOS ex; solo Hydrapple ex y los no-ex lo danan.
                        if (op_pokemon.id == Farigiraf_ex
                                and my_pokemon.id in OUR_BASIC_EX_IDS):
                            damage = 0

                        _drednaw_shell_active = (op_pokemon.id == Drednaw and damage > 0)

                        if damage > 0 and my_pokemon.id != Fezandipiti_ex:
                            if data.weakness == EnergyType.GRASS:
                                damage *= 2
                            elif data.resistance == EnergyType.GRASS:
                                damage -= 30

                        if _drednaw_shell_active and damage >= 200:
                            damage = 0

                        effective_ko_hp = op_pokemon.hp
                        if op_pokemon.id == Crustle_Fighting and op_pokemon.hp == op_pokemon.maxHp:

                            if damage >= op_pokemon.hp:
                                damage = op_pokemon.hp - 10
                                effective_ko_hp = op_pokemon.hp + 1

                        prize = 0
                        score = pokemon_score(op_pokemon)
                        if damage <= 0 and op_pokemon.id in EX_IMMUNE_IDS:
                            score = SCORE_USELESS_ATTACK
                        elif damage <= 0 and op_pokemon.id in ABILITY_IMMUNE_IDS:
                            score = SCORE_USELESS_ATTACK
                        elif damage <= 0 and _drednaw_shell_active:
                            score = SCORE_USELESS_ATTACK
                        elif (damage <= 0 and op_pokemon.id == Farigiraf_ex
                                and my_pokemon.id in OUR_BASIC_EX_IDS):
                            score = SCORE_USELESS_ATTACK
                        elif damage <= 0 and neutralization_zone_active and my_is_ex:
                            score = SCORE_USELESS_ATTACK
                        elif op_pokemon.hp <= damage:
                            prize = prize_count_op(op_pokemon)
                        else:
                            score *= damage / max(1, op_pokemon.hp)
                        score += base_score

                        # El ACTIVO ya remata a este objetivo: se apunta con QUE
                        # cuerpo (vida actual y premios propios) para poder
                        # comparar contra el despues. `prize_count`, no
                        # `prize_count_op`: mide un Pokemon NUESTRO.
                        if i == 0 and damage > 0 and op_pokemon.hp <= damage:
                            _atk_act_ko[j] = ((my_pokemon.hp or 0),
                                              prize_count(my_pokemon))

                        if op_pokemon.id == Budew:
                            if op_pokemon.hp <= damage:
                                score += 8000
                            else:
                                score += 3000

                        elif op_pokemon.id == Froslass:
                            if op_pokemon.hp <= damage:
                                score += 9000
                            else:
                                score += 4000

                        elif op_pokemon.id == Munkidori:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 2500

                        elif op_pokemon.id == Snorunt:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id in (Dreepy, Drakloak):
                            if op_pokemon.hp <= damage:
                                # vs la linea Dragapult, cortar un Drakloak
                                # (Stage-1 energizado a un paso de Dragapult ex,
                                # atacante de 2 premios que hace spread) con el
                                # snipe libre de Cruel Arrow (Fezandipiti ex, 100
                                # fijo) es MAS valioso que noquear a Budew (soporte
                                # de 30hp). Sin este boost el KO de Budew (8000 +
                                # 3500 basico + 300 activo = 11800) supera al de
                                # Drakloak (6500 + 3000 Stage-1 = 9500) y el juego
                                # dispara a Budew. Elevamos Drakloak por encima de
                                # Budew SOLO en el matchup Dragapult. Cruel Arrow
                                # nunca noquea al propio Dragapult ex (320hp), asi
                                # que no interfiere con KOs de mayor premio.
                                if op_pokemon.id == Drakloak and op_has_dreepy_line:
                                    score += 9800
                                else:
                                    score += 6500
                            else:
                                score += 2000

                        elif op_pokemon.id in (Dwebble_Grass, Dwebble_Fighting):
                            if op_pokemon.hp <= damage:
                                score += 6000
                            else:
                                score += 2000

                        elif op_pokemon.id in EX_IMMUNE_IDS and not my_is_ex and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 4000

                        elif op_pokemon.id == Crustle_Fighting and op_pokemon.hp < op_pokemon.maxHp:
                            if op_pokemon.hp <= damage:
                                score += 5000

                        elif op_pokemon.id in (Ralts, Kirlia):
                            if op_pokemon.hp <= damage:
                                score += 6000
                            else:
                                score += 1500
                        elif op_pokemon.id == Gardevoir_ex:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 3000

                        elif op_pokemon.id in (Abra, Kadabra):
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500
                        elif op_pokemon.id == Alakazam_ex:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Slowking:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 3000
                        elif op_pokemon.id == Slowpoke:
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500

                        elif op_pokemon.id in (Duskull, Dusclops):
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500
                        elif op_pokemon.id == Dusknoir:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Zoroark_N:
                            if op_pokemon.hp <= damage:
                                score += 6500
                            else:
                                score += 2000
                        elif op_pokemon.id == Zorua_N:
                            if op_pokemon.hp <= damage:
                                score += 5000
                            else:
                                score += 1200

                        elif op_pokemon.id == Typhlosion:
                            if op_pokemon.hp <= damage:
                                score += 6500
                            else:
                                score += 2000
                        elif op_pokemon.id in (Cyndaquil, Quilava):
                            if op_pokemon.hp <= damage:
                                score += 5000
                            else:
                                score += 1200

                        elif op_pokemon.id == Chewtle:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Drednaw and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 8000
                            else:
                                score += 3000

                        elif op_pokemon.id in EEVEE_IDS:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 2500

                        elif op_pokemon.id == Sylveon and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 9000
                            else:
                                score += 4000

                        if my_pokemon.id == Fezandipiti_ex and damage > 0:
                            _op_data = card_table.get(op_pokemon.id)
                            _is_stage2 = (_op_data and getattr(_op_data, 'stage2', False))
                            _is_stage1 = (_op_data and getattr(_op_data, 'stage1', False))
                            _is_ex = (_op_data and getattr(_op_data, 'ex', False))
                            if op_pokemon.hp <= damage:

                                if _is_stage2:
                                    score += 5000
                                elif _is_ex:
                                    score += 4500
                                elif not _is_stage1:
                                    score += 3500
                                else:
                                    score += 3000
                            else:

                                if j == 0:
                                    score += 500

                        # Noquear el ACTIVO rival cuando el rival NO tiene mas
                        # Pokemon en juego (banca vacia) GANA la partida: no puede
                        # promover un reemplazo. Se gana aunque el KO no complete
                        # los premios (user, registro_016 p138 vs Crustle).
                        _ko_wins_no_bench = (
                            j == 0
                            and op_pokemon.hp <= damage
                            and not any(b is not None
                                        for b in (op_state.bench or [])))
                        # KO GARANTIZADO (P0.1): vs Tenacious Body (moneda) o
                        # Survival Brace no se declara SCORE_WIN_GAME; el KO
                        # sigue puntuando por la via normal (prize/score).
                        if ((my_prize <= prize or _ko_wins_no_bench)
                                and not _ko_no_garantizado(op_pokemon)):
                            score = SCORE_WIN_GAME
                        elif prize > 0:

                            remaining_after_ko = op_prize - prize
                            if remaining_after_ko == 1:

                                score += 4000

                        if i == 0:
                            score += 220
                        if j == 0:
                            score += 300
                        score += effective_energy

                        _la_return = _op_best_damage_vs(my_pokemon)
                        if _la_return > 0:
                            if _la_return >= my_pokemon.hp:
                                if my_pokemon.id in OUR_EX_IDS:

                                    _la_disrupt = _op_disruption_belief(op_state, False)
                                    score -= int(SCORE_LOOKAHEAD_EX_TRADE * (0.6 + 0.4 * _la_disrupt))
                                else:
                                    score -= SCORE_LOOKAHEAD_KO_TRADE
                            elif _la_return <= my_pokemon.hp * 0.4:
                                score += SCORE_LOOKAHEAD_SAFE

                        # Un atacante de BANCA solo puede atacar si RETIRAMOS
                        # el activo para promoverlo, y entonces queda expuesto al
                        # activo rival. Si ese golpe lo NOQUEA, el pivote regala
                        # sus premios (user, registro_011 paso 138 vs Dragapult,
                        # PERDIDA: el Hydrapple ex de banca estaba a 70/330 y el
                        # rival a 2 premios, asi que promoverlo le entregaba la
                        # partida; lo correcto era atacar con el Tapu Bulu activo,
                        # ya cargado). Solo se admite si el KO que logramos GANA
                        # la partida (SCORE_WIN_GAME, ya resuelto arriba).
                        # Se mide con `_op_active_attack_damage_to` (resuelve
                        # el ataque REAL del activo rival via attack_table), no
                        # con `_op_best_damage_vs`, que aqui subestimaba el
                        # golpe del Dragapult ex y dejaba pasar el pivote.
                        _pbs_opa = (op_state.active[0]
                                    if op_state.active and op_state.active[0] is not None
                                    else None)
                        _pivote_banca_suicida = False
                        if i >= 1 and score != SCORE_WIN_GAME and _pbs_opa is not None:
                            _pbs_dmg = max(
                                _la_return,
                                _op_active_attack_damage_to(
                                    _pbs_opa, my_pokemon,
                                    getattr(op_state, 'handCount', None)))
                            _pivote_banca_suicida = (
                                _pbs_dmg >= (my_pokemon.hp or 0))

                        # Pivote de banca que NO MEJORA NADA (user, registro_014
                        # paso 166 vs Alakazam): si el ACTIVO ya noquea a ESE
                        # MISMO objetivo, atacar desde la banca obliga a retirar
                        # -- se paga energia -- y deja delante un cuerpo que
                        # aguanta lo mismo o MENOS por los mismos premios. Es un
                        # cambio a peor con coste.
                        #
                        # Lo elegia `base_score`, que lleva una preferencia de
                        # ESPECIE (+200 Hydrapple ex / -100 Teal Mask Ogerpon ex)
                        # heredada del HP IMPRESO: Hydrapple es el muro de 330.
                        # Pero es una constante de CARTA y no sabe nada del dano
                        # ya recibido. En el registro el "muro" era un Hydrapple
                        # ex a 90/330 y el activo un Teal Mask Ogerpon ex sano a
                        # 210/210; los dos noqueaban al Alakazam de 140, y esos
                        # 300 puntos de sesgo bastaban para ganarle al +220 de
                        # "soy el activo" y retirar al sano (78 puntos de
                        # diferencia) para poner delante al que muere.
                        #
                        # Se compara la vida ACTUAL y se exige que el relevo
                        # tampoco NIEGUE premios: un no-ex de banca puede seguir
                        # relevando a un ex activo aunque aguante menos, porque
                        # alli el cuerpo peor se paga con 1 premio en vez de 2
                        # (ver `_alakazam_pivot_1prize`). Mismo criterio que
                        # `_pdx_act_margin`: el que AGUANTA va delante.
                        _pivote_banca_sin_ganancia = False
                        if i >= 1 and _atk_act_ko.get(j) is not None:
                            _pbsg_hp, _pbsg_prize = _atk_act_ko[j]
                            _pivote_banca_sin_ganancia = (
                                (my_pokemon.hp or 0) <= _pbsg_hp
                                and prize_count(my_pokemon) >= _pbsg_prize)

                        if (best_score < score and not _pivote_banca_suicida
                                and not _pivote_banca_sin_ganancia):
                            best_score = score
                            ESTADO.plan.attacker = i
                            ESTADO.plan.target = j
                            ESTADO.plan.attack_index = attack_idx
                            ESTADO.plan.remain_hp = op_pokemon.hp - damage
                            ESTADO.plan.energy = more_energy

            _op_act_main = op_state.active[0] if op_state.active else None
            _ret_active = my_cards[0] if my_cards else None

            # REMATE con el ACTIVO: si el bucle eligio atacar con el activo
            # (attacker 0) NOQUEANDO al activo rival y el rival no tiene banca,
            # ese ataque GANA la partida. Se captura aqui, ANTES de los pivotes de
            # descuadre/sacrificio de premios, para restaurarlo despues (esos
            # pivotes retirarian el activo letal para subir un 1-premio, tirando
            # la victoria inmediata; user, registro_016 p138 vs Crustle).
            if (_op_bench_empty and ESTADO.plan.attacker == 0
                    and ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0):
                _active_win_plan = (
                    ESTADO.plan.attacker, ESTADO.plan.target, ESTADO.plan.attack_index,
                    ESTADO.plan.remain_hp, ESTADO.plan.energy)

            if (_op_act_main is not None and can_switch and _ret_active is not None
                    and _ret_active.id != Hydrapple_ex):

                _hydra_mc_idx = -1
                _hydra_mc_pk = None

                _hydra_charge_idx = -1
                _hydra_charge_pk = None
                _grass_in_hand_promo = hand_counts.get(Basic_Grass_Energy, 0) >= 1
                # Desempate por VIDA (user, log 86212499 paso 151, vs Alakazam,
                # GANADA): con dos o mas Hydrapple ex de banca IGUALES aptos para
                # promover y atacar (p.ej. uno a 70 hp y otro a 330 hp), promover
                # SIEMPRE al de MAS vida. Antes el bucle recorria la banca en
                # orden y tomaba el PRIMER Hydrapple apto (`break` / primer
                # candidato de carga), es decir el de menor indice de banca (el
                # de 70 hp), que es fragil y muere facil. Ahora se recorre toda
                # la banca y, a igualdad de aptitud (listo >= 2 efectivas, o
                # cargable a >= 2), se elige el de mayor hp. Se mantiene la
                # prioridad: un Hydrapple YA cargado (`_hydra_mc_idx`) prevalece
                # sobre uno que necesita carga (`_hydra_charge_idx`).
                for _mc_i, _mc_pk in enumerate(my_cards):
                    if _mc_i == 0 or _mc_pk is None:
                        continue
                    if _mc_pk.id == Hydrapple_ex:
                        _mc_eff = len(_mc_pk.energies) * _grass_mult()
                        if _mc_eff >= 2:
                            if (_hydra_mc_idx < 0
                                    or (_mc_pk.hp or 0) > (_hydra_mc_pk.hp or 0)):
                                _hydra_mc_idx = _mc_i
                                _hydra_mc_pk = _mc_pk
                        elif (_grass_in_hand_promo and
                                len(_mc_pk.energies) + _grass_attach_unit() >= 2):
                            if (_hydra_charge_idx < 0
                                    or (_mc_pk.hp or 0) > (_hydra_charge_pk.hp or 0)):
                                _hydra_charge_idx = _mc_i
                                _hydra_charge_pk = _mc_pk

                _hydra_promo_needs_charge = False
                if _hydra_mc_idx < 0 and _hydra_charge_idx >= 1:

                    _ret_req_now = None
                    if _ret_active.id == Hydrapple_ex:
                        _ret_req_now = 2
                    elif _ret_active.id == Dipplin:
                        _ret_req_now = 1
                    elif _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _ret_req_now = 3
                    elif _ret_active.id == Tapu_Bulu:
                        _ret_req_now = 4
                    elif _ret_active.id == Pinsir:
                        _ret_req_now = 2
                    elif _ret_active.id == Fezandipiti_ex:
                        _ret_req_now = 3
                    elif _ret_active.id == Meganium:
                        _ret_req_now = 4
                    _ret_eff_now = len(_ret_active.energies) * _grass_mult()
                    _ret_act_ready_now = (_ret_req_now is not None and _ret_eff_now >= _ret_req_now)

                    if _ret_req_now is None or _ret_act_ready_now:
                        _hydra_mc_idx = _hydra_charge_idx
                        _hydra_mc_pk = _hydra_charge_pk
                        _hydra_promo_needs_charge = True
                if _hydra_mc_idx >= 1:
                    _op_main_hp = _op_act_main.hp or 0

                    _ret_cost = RETREAT_COST.get(_ret_active.id, 1)
                    if has_switch_card:
                        _ret_cost = 0
                    # Wild Growth: cada Planta paga por dos, se descartan menos
                    # CARTAS de Planta para cubrir la retirada -- pero cada
                    # carta descartada borra DOS unidades del recuento con el
                    # que escala Syrup Storm (`_retreat_grass_units`), y la
                    # Planta que se adjunta para la carga tambien suma DOS
                    # (`_grass_attach_unit`). Contar cartas en vez de unidades
                    # inflaba el dano justo por ese factor: user, registro_006
                    # paso 78 vs Archaludon ex (PERDIDA), donde el pivote creia
                    # que el Hydrapple ex de banca noqueaba (300 - 30 = 270 =
                    # vida exacta) y el ataque real hizo 240.
                    _hydra_grass_after = max(
                        0, total_grass - _retreat_grass_units(_ret_cost))
                    if _hydra_promo_needs_charge:
                        _hydra_grass_after += _grass_attach_unit()
                    _hydra_base = 30 + 30 * _hydra_grass_after
                    _hydra_ko_dmg = _our_effective_damage(
                        _hydra_mc_pk, _op_act_main, _hydra_base,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    _hydra_can_ko = (_hydra_ko_dmg > 0 and _hydra_ko_dmg >= _op_main_hp)

                    _act_can_ko = False
                    _act_prof = None
                    if _ret_active.id == Dipplin:
                        _act_prof = (1, 20 * bench_count)
                    elif _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _oae = len(_op_act_main.energies)
                        _act_prof = (3, 30 + 30 * (len(_ret_active.energies) + _oae))
                    elif _ret_active.id == Tapu_Bulu:
                        _act_prof = (4, 220)
                    elif _ret_active.id == Meganium:
                        _act_prof = (4, 140)
                    elif _ret_active.id == Pinsir:
                        _act_prof = (2, 100)
                    elif _ret_active.id == Fezandipiti_ex:
                        _act_prof = (3, 100)
                    if _act_prof is not None:
                        _act_req, _act_base = _act_prof
                        _act_eff = len(_ret_active.energies) * _grass_mult()
                        if (_act_eff < _act_req and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached):
                            _act_eff += _grass_attach_unit()
                        if _act_eff >= _act_req:
                            _act_dmg = _our_effective_damage(
                                _ret_active, _op_act_main, _act_base,
                                ESTADO.meganium_in_play, neutralization_zone_active)
                            _act_can_ko = (_act_dmg > 0 and _act_dmg >= _op_main_hp)

                    _promote_hydra = _hydra_can_ko or (not _act_can_ko)

                    if _hydra_ko_dmg <= 0:
                        _promote_hydra = False
                    # Regla (user, registro 010 paso 82 vs Alakazam): un Tapu Bulu
                    # CARGADO en el activo que puede NOQUEAR al activo rival ataca
                    # el mismo; no cede el ataque al pivote de Hydrapple ex. Tapu
                    # Bulu es no-ex (1 premio si lo noquean), asi que rematar con el
                    # es mejor que exponer/gastar la Hydrapple ex (2 premios).
                    if _ret_active.id == Tapu_Bulu and _act_can_ko:
                        _promote_hydra = False
                    # La misma idea que el Tapu Bulu de arriba, pero por el
                    # cuerpo que AGUANTA (user, registro_014 paso 166 vs
                    # Alakazam): cuando el ACTIVO ya noquea, `_hydra_can_ko`
                    # promovia igualmente por la conviccion de que Hydrapple ex
                    # es el muro de 330 PV. Eso es el HP IMPRESO. En el registro
                    # el Hydrapple ex de banca estaba a 90/330 y el activo era un
                    # Teal Mask Ogerpon ex INTACTO a 210/210: los dos noqueaban
                    # al Alakazam, asi que retirar solo servia para pagar una
                    # energia y dejar delante al cuerpo que muere. Se exige
                    # mejora de vida REAL y que el relevo tampoco niegue premios
                    # (un no-ex relevando a un ex sigue valiendo aunque aguante
                    # menos: se paga 1 premio en vez de 2).
                    if (_act_can_ko and _hydra_mc_pk is not None
                            and (_hydra_mc_pk.hp or 0) <= (_ret_active.hp or 0)
                            and prize_count(_hydra_mc_pk)
                                >= prize_count(_ret_active)):
                        _promote_hydra = False
                    # El Hydrapple ex promovido queda EXPUESTO al activo rival:
                    # si ese golpe lo NOQUEA, el pivote regala 2 premios (user,
                    # registro_011 paso 138 vs Dragapult, PERDIDA: el Hydrapple
                    # de banca estaba a 70/330 y el rival a 2 premios, asi que
                    # promoverlo le entregaba la partida; lo correcto era atacar
                    # con el Tapu Bulu activo, ya cargado). `_promote_hydra` se
                    # activaba con solo `not _act_can_ko` -- "si el activo no
                    # noquea, promueve" -- sin mirar si el Hydrapple sobrevive.
                    # Solo se admite el pivote si SOBREVIVE al golpe proyectado
                    # o si su propio KO ya gana la partida. Se usa
                    # `_op_active_attack_damage_to` (resuelve el ataque REAL via
                    # attack_table: aqui Phantom Dive, 200) porque el estimador
                    # generico devolvia 0 para Dragapult ex.
                    if _promote_hydra and _hydra_mc_pk is not None:
                        _ph_gana = (_hydra_can_ko
                                    and my_prize <= prize_count_op(_op_act_main))
                        if not _ph_gana:
                            _ph_dmg_rival = _op_active_attack_damage_to(
                                _op_act_main, _hydra_mc_pk,
                                getattr(op_state, 'handCount', None))
                            if _ph_dmg_rival >= (_hydra_mc_pk.hp or 0):
                                _promote_hydra = False
                    if _promote_hydra and ESTADO.plan.attacker != _hydra_mc_idx:
                        ESTADO.plan.attacker = _hydra_mc_idx
                        ESTADO.plan.target = 0
                        ESTADO.plan.attack_index = 0
                        ESTADO.plan.remain_hp = _op_main_hp - _hydra_ko_dmg
                        ESTADO.plan.energy = False

            if (ESTADO.plan.attacker >= 1
                    and _op_act_main is not None
                    and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and _op_act_main.id not in EX_IMMUNE_IDS):
                _rule_act_immune = False
                if _op_act_main.id in ABILITY_IMMUNE_IDS and _ret_active.id in OUR_ABILITY_IDS:
                    _rule_act_immune = True
                if neutralization_zone_active and _ret_active.id in OUR_EX_IDS:
                    _op_act_data_rule = card_table.get(_op_act_main.id)
                    if not (_op_act_data_rule and (_op_act_data_rule.ex or _op_act_data_rule.megaEx)):
                        _rule_act_immune = True
                if not _rule_act_immune:
                    _rule_act_prof = None
                    if _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _oae_r = len(_op_act_main.energies)
                        _rule_act_prof = (3, 30 + 30 * (len(_ret_active.energies) + _oae_r))
                    elif _ret_active.id == Hydrapple_ex:
                        _rule_act_prof = (2, 30 + 30 * total_grass)
                    elif _ret_active.id == Fezandipiti_ex:
                        _rule_act_prof = (3, 100)
                    if _rule_act_prof is not None:
                        _rule_req, _rule_base = _rule_act_prof
                        _rule_eff = len(_ret_active.energies) * _grass_mult()
                        _rule_needs_attach = False
                        if (_rule_eff < _rule_req
                                and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached):
                            _rule_eff += _grass_attach_unit()
                            _rule_needs_attach = True
                        if _rule_eff >= _rule_req:
                            _rule_act_dmg = _our_effective_damage(
                                _ret_active, _op_act_main, _rule_base,
                                ESTADO.meganium_in_play, neutralization_zone_active)
                            _rule_bench_kos = (ESTADO.plan.target == 0
                                               and ESTADO.plan.remain_hp is not None
                                               and ESTADO.plan.remain_hp <= 0)
                            if _rule_act_dmg > 0 and not _rule_bench_kos:
                                ESTADO.plan.attacker = 0
                                ESTADO.plan.target = 0
                                ESTADO.plan.attack_index = 0
                                ESTADO.plan.remain_hp = (_op_act_main.hp or 0) - _rule_act_dmg
                                ESTADO.plan.energy = _rule_needs_attach

            # --- Pivote defensivo a Hydrapple ex ---
            # Si nuestro activo es fragil (poca vida / probable KO el proximo
            # turno) y en la banca hay un Hydrapple ex a vida completa con
            # energia propia suficiente (Wild Growth de Meganium cuenta) para
            # noquear al activo rival, conviene RETIRAR al activo fragil y subir
            # a Hydrapple ex: su altisima vida es muy dificil de noquear,
            # mantiene la presion y no regala premios. El activo fragil se
            # resguarda en la banca; el KO se entrega igual pero con un cuerpo
            # mucho mas resistente al frente. Meganium es clave: duplica la
            # energia de Planta, asi que Hydrapple puede atacar con menos cartas.
            # Regla (user, registro 010 paso 82 vs Alakazam): un Tapu Bulu CARGADO
            # en el activo que puede NOQUEAR al activo rival NUNCA se retira; debe
            # atacar. Al ser no-ex, si lo noquean solo entrega 1 premio, asi que
            # rematar con el es mejor que gastar el pivote a Hydrapple ex (2
            # premios). Vetamos el pivote defensivo a Hydrapple cuando el activo es
            # un Tapu Bulu con KO disponible (aunque sea "fragil"): no dispararlo
            # evita ademas que `plan.attacker` apunte a Hydrapple y suprima el ataque.
            _tapu_active_ko_here = False
            if (_ret_active is not None and _ret_active.id == Tapu_Bulu
                    and _op_act_main is not None
                    and len(_ret_active.energies) * _grass_mult() >= 4):
                _tapu_dmg_here = _our_effective_damage(
                    _ret_active, _op_act_main, 220, ESTADO.meganium_in_play,
                    neutralization_zone_active)
                _tapu_active_ko_here = (_tapu_dmg_here > 0
                                        and _tapu_dmg_here >= (_op_act_main.hp or 0))

            # Incluye el caso en que el ACTIVO YA es un Hydrapple ex fragil
            # (user, registro_023 vs Archaludon): con dos Hydrapple ex en juego,
            # si el activo tiene POCA vida y en banca hay OTRO Hydrapple ex con
            # MAS vida que, tras retirar, AUN noquea al activo rival, se promueve
            # al tanque: noquea igual y sobrevive el contraataque (el fragil
            # moriria y, al ser ex, cederia 2 premios). El ataque de Hydrapple
            # (Syrup Storm) escala con el Grass TOTAL del campo, que BAJA por el
            # coste de retirada; cuando el activo es Hydrapple se descuenta ese
            # coste al comprobar el KO del de banca.
            _piv_active_is_hydra = (_ret_active is not None
                                    and _ret_active.id == Hydrapple_ex)
            if _piv_active_is_hydra:
                _piv_ret_cost = 0 if has_switch_card else RETREAT_COST.get(Hydrapple_ex, 2)
                _piv_grass_after = max(
                    0, total_grass - _retreat_grass_units(_piv_ret_cost))
            else:
                _piv_grass_after = total_grass
            if (can_switch and _op_act_main is not None and _ret_active is not None
                    and not _tapu_active_ko_here
                    and (active_ko_likely or active_hp_ratio <= 0.6)):
                _piv_op_hp = _op_act_main.hp or 0
                for _piv_i, _piv_pk in enumerate(my_cards):
                    if _piv_i == 0 or _piv_pk is None or _piv_pk.id != Hydrapple_ex:
                        continue
                    # Solo si Hydrapple ex esta a vida completa (muy dificil de
                    # noquear); si ya esta danado no aporta la ventaja de muro.
                    if _piv_pk.hp < (_piv_pk.maxHp or 0):
                        continue
                    # Con activo Hydrapple, el de banca debe tener MAS vida que el
                    # activo; si no, pivotar no aporta (mismo ataque de campo) y
                    # ademas pierde Grass por la retirada.
                    if _piv_active_is_hydra and (_piv_pk.hp or 0) <= (_ret_active.hp or 0):
                        continue
                    # Necesita energia PROPIA para atacar tras subir (Wild Growth
                    # incluido): el umbral efectivo de Hydrapple ex es 2.
                    if len(_piv_pk.energies) * _grass_mult() < 2:
                        continue
                    _piv_dmg = _our_effective_damage(
                        _piv_pk, _op_act_main, 30 + 30 * _piv_grass_after,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    if _piv_dmg > 0 and _piv_dmg >= _piv_op_hp:
                        ESTADO.plan.attacker = _piv_i
                        ESTADO.plan.target = 0
                        ESTADO.plan.attack_index = 0
                        ESTADO.plan.remain_hp = _piv_op_hp - _piv_dmg
                        ESTADO.plan.energy = False
                        _hydra_pivot_active = True
                        break

            # --- Pivote-muro a Hydrapple ex SIN KO (user, log 85856881 p.127) ---
            # Si `_hydra_wall_pivot` (Ogerpon activo condenado que SI puede atacar
            # pero NO noquea, y muro Hydrapple ex a vida completa en banca que
            # sobrevive), apuntamos el plan al Hydrapple de banca para que la
            # opcion de ATACAR con el Ogerpon fragil quede SUPRIMIDA (plan.attacker
            # >= 1 con retirada disponible -> ver bloque ATTACK), de modo que el
            # agente elija PASS, el motor exponga la retirada (ctx=30) y se suba al
            # muro. No exige `can_switch` (en ctx=0 no hay opcion RETREAT; la
            # retirada solo se expone tras PASS). Solo si aun no hay un plan de
            # pivote con KO fijado.
            if (_hydra_wall_pivot and not _hydra_pivot_active
                    and ESTADO.plan.attacker == 0 and _op_act_main is not None):
                for _hwpp_i, _hwpp_pk in enumerate(my_cards):
                    if (_hwpp_i >= 1 and _hwpp_pk is not None
                            and _hwpp_pk.id == Hydrapple_ex
                            and _hwpp_pk.hp >= (_hwpp_pk.maxHp or 0)
                            and len(_hwpp_pk.energies) * _grass_mult() >= 2):
                        _hwpp_dmg = _our_effective_damage(
                            _hwpp_pk, _op_act_main, 30 + 30 * total_grass,
                            ESTADO.meganium_in_play, neutralization_zone_active)
                        ESTADO.plan.attacker = _hwpp_i
                        ESTADO.plan.target = 0
                        ESTADO.plan.attack_index = 0
                        ESTADO.plan.remain_hp = (_op_act_main.hp or 0) - _hwpp_dmg
                        ESTADO.plan.energy = False
                        break

            # --- Sacrificio de premios: pivote a Tapu Bulu de banca (user) ---
            # Si nuestro activo es un ex (2 premios) en riesgo de ser noqueado el
            # proximo turno y en la banca hay un Tapu Bulu (no-ex, 1 premio) LISTO
            # para atacar que puede noquear al activo rival, conviene RETIRAR al ex
            # y subir a Tapu Bulu para atacar: tomamos el KO igual, pero exponemos
            # al frente solo un cuerpo de 1 premio. Si el rival lo noquea entregamos
            # 1 premio en vez de 2. No aplica si ya pivotamos a un Hydrapple ex de
            # banca (muro a vida completa, mejor cuerpo).
            #
            # Ademas del caso DEFENSIVO (activo en riesgo), permitimos el pivote
            # PROACTIVO (user): con Meganium en juego y un Tapu Bulu de banca ya
            # LISTO (>=4 efectivas) que noquea al activo rival, subir a Tapu Bulu
            # (1 premio) para atacar y NO exponer el ex activo (2 premios), aunque
            # el ex este sano. No aplica en matchups con muros/inmunidades ni con
            # Zona de Neutralizacion.
            _tapu_proactive_lead = (
                ESTADO.meganium_in_play
                and not (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck
                         or op_is_sylveon_deck)
                and not neutralization_zone_active)
            if (not _hydra_pivot_active
                    and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and (active_ko_likely or active_hp_ratio <= 0.5
                         or _tapu_proactive_lead)
                    and my_prize > prize_count_op(_op_act_main)):
                _tsac_op_hp = _op_act_main.hp or 0
                _tsac_bench_kos = False
                for _tsac_i, _tsac_pk in enumerate(my_cards):
                    if _tsac_i == 0 or _tsac_pk is None or _tsac_pk.id != Tapu_Bulu:
                        continue
                    # Tapu Bulu debe estar LISTO (>=4 de Planta efectiva).
                    if len(_tsac_pk.energies) * _grass_mult() < 4:
                        continue
                    _tsac_dmg = _our_effective_damage(
                        _tsac_pk, _op_act_main, 220,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    if _tsac_dmg > 0 and _tsac_dmg >= _tsac_op_hp:
                        _tsac_bench_kos = True
                        if can_switch:
                            ESTADO.plan.attacker = _tsac_i
                            ESTADO.plan.target = 0
                            ESTADO.plan.attack_index = 0
                            ESTADO.plan.remain_hp = _tsac_op_hp - _tsac_dmg
                            ESTADO.plan.energy = False
                            _tapu_sac_pivot = True
                        break
                # Si Tapu ya puede rematar desde banca pero NO podemos retirar aun
                # al ex (le falta energia para el coste de retirada) y basta UNA
                # energia mas para habilitarla y tenemos aun el enganche manual de
                # este turno, conviene atacar esa energia al ex activo para poder
                # retirarlo y subir a Tapu. Solo aplica con Tapu YA cargado, de modo
                # que jamas le quitamos energia a Tapu.
                if (_tsac_bench_kos and not can_switch and not state.energyAttached
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                    _tsac_rc = RETREAT_COST.get(_ret_active.id, 1)
                    _tsac_cur_e = len(_ret_active.energies)
                    if _tsac_cur_e < _tsac_rc and _tsac_cur_e + 1 >= _tsac_rc:
                        _tapu_sac_enable_retreat = True

            # --- Negacion de premios: pivote defensivo a un cuerpo de 1 premio ---
            # Analisis ANTES de atacar (user, log 86211357 paso 128, PERDIDA vs
            # Mega Starmie). Si nuestro activo es un ex (2 premios) que sera
            # NOQUEADO el proximo turno y con ese KO el rival ALCANZA los premios
            # que le faltan para GANAR (prize_count(activo) >= op_prize, con
            # op_prize >= 2), NO conviene atacar con el activo condenado. En su
            # lugar lo retiramos y subimos a un Pokemon de banca de MENOS premios
            # (no-ex = 1 premio) que pueda atacar; asi, aunque lo noqueen, el
            # rival NO completa los premios para ganar ese turno. Preferimos el
            # cuerpo que ademas SOBREVIVA al ataque rival (soporta); si ninguno
            # sobrevive, el de MAS dano. A diferencia de `_tapu_sac_pivot`, este
            # NO exige que el cuerpo noquee al rival: es puramente defensivo
            # (ganar tiempo negando el premio letal). EXCEPCION: si el propio
            # activo puede rematar y GANAR ya este turno, no se retira (se ataca).
            if (not _prize_denial_pivot
                    and not _hydra_pivot_active and not _tapu_sac_pivot
                    and can_switch
                    and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and active_ko_likely
                    and op_prize >= 2
                    and prize_count(_ret_active) >= op_prize):

                # Dano del ACTIVO contra el activo rival. Lo consumen DOS cosas:
                # el remate ganador de abajo (`_pdp_active_wins_now`: si el KO
                # del activo GANA ya la partida, se ataca y no se retira) y la
                # guarda del FALLBACK EX (`_pdx_act_margin`), que compara al
                # candidato de banca contra el cuerpo que YA esta delante. Antes
                # se calculaba solo dentro del gate de "ganar ya", asi que el
                # fallback no tenia forma de saber si el activo hacia lo mismo.
                _pdp_ae = len(_ret_active.energies)
                _pdp_aeff = _pdp_ae * _grass_mult()
                _pdp_abase = 0
                if _ret_active.id == Hydrapple_ex and _pdp_aeff >= 2:
                    _pdp_abase = 30 + 30 * total_grass
                elif _ret_active.id == Teal_Mask_Ogerpon_ex and _pdp_aeff >= 3:
                    # Myriad cuenta la energia de AMBOS activos (verificado).
                    _pdp_abase = 30 + 30 * (
                        _pdp_ae + len(getattr(_op_act_main, 'energies', []) or []))
                elif _ret_active.id == Fezandipiti_ex and _pdp_aeff >= 3:
                    _pdp_abase = 100
                _pdp_adm = 0
                if _pdp_abase > 0:
                    _pdp_adm = _our_effective_damage(
                        _ret_active, _op_act_main, _pdp_abase,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                _pdp_active_ko = (_pdp_adm > 0
                                  and _pdp_adm >= (_op_act_main.hp or 0))
                # Si el propio activo puede tomar un KO que nos hace GANAR ya,
                # atacamos (no retiramos).
                _pdp_active_wins_now = (
                    _pdp_active_ko and my_prize <= prize_count_op(_op_act_main))

                if not _pdp_active_wins_now:
                    _pdp_best_i = -1
                    _pdp_best_key = None
                    for _pdp_i, _pdp_pk in enumerate(my_cards):
                        if _pdp_i == 0 or _pdp_pk is None:
                            continue
                        # Solo cuerpos que entreguen MENOS premios de los que el
                        # rival necesita para ganar (no-ex): asi el KO no cierra.
                        if prize_count(_pdp_pk) >= op_prize:
                            continue
                        _pdp_req = ESTADO.ATTACK_ENERGY_REQ.get(_pdp_pk.id)
                        if _pdp_req is None:
                            continue
                        _pdp_e = len(_pdp_pk.energies)
                        _pdp_eff = _pdp_e * _grass_mult()
                        _pdp_can_attach = (
                            hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and not state.energyAttached)
                        _pdp_eff_after = _pdp_eff + (
                            _grass_attach_unit() if _pdp_can_attach else 0)
                        if _pdp_eff_after < _pdp_req:
                            continue  # no puede atacar este turno
                        # Dano estimado del cuerpo contra el activo rival.
                        _pdp_base = 0
                        if _pdp_pk.id == Tapu_Bulu:
                            _pdp_base = 220
                        elif _pdp_pk.id == Meganium:
                            _pdp_base = 140
                        elif _pdp_pk.id == Pinsir:
                            _pdp_base = 100
                        elif _pdp_pk.id == Dipplin:
                            _pdp_base = 20 * max(0, bench_count - 1)
                        _pdp_dmg = _our_effective_damage(
                            _pdp_pk, _op_act_main, _pdp_base,
                            ESTADO.meganium_in_play, neutralization_zone_active
                        ) if _pdp_base > 0 else 0
                        # Preferencia: (sobrevive el ataque rival, dano, vida).
                        _pdp_hp = _pdp_pk.hp or 0
                        _pdp_survives = 1 if (_pdp_hp > _op_best_damage_vs(_pdp_pk)) else 0
                        _pdp_key = (_pdp_survives, _pdp_dmg, _pdp_hp)
                        if _pdp_best_key is None or _pdp_key > _pdp_best_key:
                            _pdp_best_key = _pdp_key
                            _pdp_best_i = _pdp_i
                    if _pdp_best_i >= 1:
                        ESTADO.plan.attacker = _pdp_best_i
                        ESTADO.plan.target = 0
                        ESTADO.plan.attack_index = 0
                        ESTADO.plan.remain_hp = (_op_act_main.hp or 1)
                        ESTADO.plan.energy = False
                        _prize_denial_pivot = True
                    else:
                        # FALLBACK EX (user, registro_013 paso 139 vs
                        # Archaludon/Cinderace, PERDIDA): sin ningun cuerpo de
                        # 1 premio que pueda atacar, la 2a opcion es subir un
                        # EX de banca que (a) NOQUEE al activo rival y (b)
                        # SOBREVIVA al mejor golpe proyectado de la BANCA
                        # rival (el activo rival muere con nuestro KO; la
                        # amenaza que queda es su banca promovida). Antes el
                        # agente atacaba con el Hydrapple ex de 10 HP: KO al
                        # Duraludon, pero el Cinderace de banca (Turbo Flare
                        # 50 x2 debilidad = 100) lo remataba y el rival
                        # cobraba sus 2 ULTIMOS premios = DERROTA. Lo
                        # correcto: retirar y promover el Ogerpon ex cargado
                        # (Myriad 300 - 30 resistencia = 270 >= 130 KO; 210 HP
                        # > 100) -> mismo KO sin regalar la partida. Si el
                        # candidato no noquea o tambien muere, no aplica (el
                        # rival ganaria igual con sus 2 premios sobre el ex).
                        #
                        # GUARDA "el que aguanta va DELANTE" (user, registro_012
                        # paso 174 vs Alakazam, PERDIDA): el candidato tiene que
                        # MEJORAR al cuerpo que ya esta delante, no solo cumplir
                        # los dos requisitos en abstracto. Aqui el activo era un
                        # Teal Mask Ogerpon ex a 210/210 con 4 energias -- KO al
                        # Alakazam (Myriad 30+30*(4+1)=180 >= 140) y margen
                        # 210-30 = 180 contra el mejor golpe de su banca -- y el
                        # unico candidato era el OTRO Ogerpon ex, a **50 PV** y
                        # margen 20. El fallback comparaba candidatos entre si y
                        # nunca contra el activo, asi que retiro al de 210,
                        # pago una energia y dejo delante al de 50: mismo KO,
                        # mismos 2 premios en juego y un cuerpo que muere a
                        # cualquier cosa. Ambos lados del cambio son ex (el bucle
                        # solo mira `OUR_EX_IDS`), asi que los premios empatan y
                        # lo unico que decide es cuanto AGUANTA: se exige margen
                        # ESTRICTAMENTE mayor, porque el cambio ademas cuesta la
                        # energia de la retirada.
                        _pdx_act_margin = None
                        if _pdp_active_ko:
                            _pdx_act_threat = 0
                            for _pdx_ob in op_state.bench:
                                if _pdx_ob is None:
                                    continue
                                _pdx_act_threat = max(
                                    _pdx_act_threat,
                                    _op_active_attack_damage_to(
                                        _pdx_ob, _ret_active,
                                        getattr(op_state, 'handCount', None)))
                            if _pdx_act_threat < (_ret_active.hp or 0):
                                _pdx_act_margin = (
                                    (_ret_active.hp or 0) - _pdx_act_threat)
                        _pdx_best_i = -1
                        _pdx_best_margin = None
                        for _pdx_i, _pdx_pk in enumerate(my_cards):
                            if _pdx_i == 0 or _pdx_pk is None:
                                continue
                            if _pdx_pk.id not in OUR_EX_IDS:
                                continue
                            _pdx_req = ESTADO.ATTACK_ENERGY_REQ.get(_pdx_pk.id)
                            if _pdx_req is None:
                                continue
                            _pdx_eff = len(_pdx_pk.energies) * _grass_mult()
                            _pdx_can_attach = (
                                hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached)
                            if _pdx_eff + (_grass_attach_unit()
                                           if _pdx_can_attach else 0) < _pdx_req:
                                continue  # no puede atacar este turno
                            _pdx_base = 0
                            if _pdx_pk.id == Hydrapple_ex:
                                _pdx_base = 30 + 30 * total_grass
                            elif _pdx_pk.id == Teal_Mask_Ogerpon_ex:
                                # Myriad cuenta la energia de AMBOS activos.
                                _pdx_base = 30 + 30 * (
                                    len(_pdx_pk.energies)
                                    + len(getattr(_op_act_main, 'energies', [])
                                          or []))
                            elif _pdx_pk.id == Fezandipiti_ex:
                                _pdx_base = 100
                            if _pdx_base <= 0:
                                continue
                            _pdx_dmg = _our_effective_damage(
                                _pdx_pk, _op_act_main, _pdx_base,
                                ESTADO.meganium_in_play, neutralization_zone_active)
                            if _pdx_dmg <= 0 or _pdx_dmg < (_op_act_main.hp or 0):
                                continue  # debe NOQUEAR al activo rival
                            _pdx_hp = _pdx_pk.hp or 0
                            _pdx_threat = 0
                            for _pdx_ob in op_state.bench:
                                if _pdx_ob is None:
                                    continue
                                _pdx_threat = max(
                                    _pdx_threat,
                                    _op_active_attack_damage_to(
                                        _pdx_ob, _pdx_pk,
                                        getattr(op_state, 'handCount', None)))
                            if _pdx_threat >= _pdx_hp:
                                continue  # tambien lo noquean: no niega nada
                            _pdx_margin = _pdx_hp - _pdx_threat
                            if (_pdx_act_margin is not None
                                    and _pdx_margin <= _pdx_act_margin):
                                # El activo ya noquea y aguanta igual o mas: la
                                # retirada solo cambiaria un cuerpo por otro peor
                                # (ver la guarda de arriba).
                                continue
                            if (_pdx_best_margin is None
                                    or _pdx_margin > _pdx_best_margin):
                                _pdx_best_margin = _pdx_margin
                                _pdx_best_i = _pdx_i
                        if _pdx_best_i >= 1:
                            ESTADO.plan.attacker = _pdx_best_i
                            ESTADO.plan.target = 0
                            ESTADO.plan.attack_index = 0
                            ESTADO.plan.remain_hp = 0
                            ESTADO.plan.energy = False
                            _prize_denial_pivot = True

            # Restaura el remate ganador con el activo si algun pivote de
            # descuadre lo desvio: ninguna consideracion de premios importa
            # cuando el KO del activo rival (sin banca) GANA la partida.
            if _active_win_plan is not None and ESTADO.plan.attacker != 0:
                (ESTADO.plan.attacker, ESTADO.plan.target, ESTADO.plan.attack_index,
                 ESTADO.plan.remain_hp, ESTADO.plan.energy) = _active_win_plan

        _act_stall = my_state.active[0] if my_state.active else None
        if _act_stall is not None:
            # Fuente unica de valores: ATTACK_ENERGY_REQ (solo atacantes
            # principales, mismo conjunto de claves que antes).
            _ATK_REQS_STALL = {k: ESTADO.ATTACK_ENERGY_REQ[k] for k in MAIN_ATTACKERS}
            _stall_req = _ATK_REQS_STALL.get(_act_stall.id, 999)
            _stall_eff = len(_act_stall.energies) * _grass_mult()
            _stall_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                 and not state.energyAttached)
            _stall_after = _stall_eff + (
                _grass_attach_unit() if _stall_can_attach else 0)

            if _stall_after < _stall_req:

                _nrg_deck = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                    Basic_Grass_Energy, {}).get(ESTADO_MAZO, 0)
                _deck_total = max(1, sum(
                    v.get(ESTADO_MAZO, 0) for v in ESTADO.CARTAS_ACTIVAS_EN_MAZO.values()))

                _td_stall = sum(
                    1 for p in (list(my_state.active or []) + list(my_state.bench))
                    if p is not None and p.id == Teal_Mask_Ogerpon_ex
                    and len(p.energies) >= 1)

                if _td_stall <= 0 or _nrg_deck <= 0:
                    _active_cant_attack_this_turn = True
                else:

                    _p_no = 1.0
                    for _ in range(min(_td_stall, 4)):
                        _p_no *= max(0, _deck_total - _nrg_deck) / _deck_total
                    _active_cant_attack_this_turn = (_p_no > 0.5)

            if _active_cant_attack_this_turn and can_switch:
                for _bp_s in my_state.bench:
                    if (_bp_s is not None and _bp_s.id in _ATK_REQS_STALL
                            and _bp_s.id != Meowth_ex):
                        _bp_eff_s = len(_bp_s.energies) * _grass_mult()
                        if _bp_eff_s >= _ATK_REQS_STALL[_bp_s.id]:
                            _active_cant_attack_this_turn = False
                            break

    def evaluate_supporters():
        return _evaluate_supporters_impl(
            CtxEvaluateSupporters(
            _active_cant_attack_this_turn=_active_cant_attack_this_turn,
            _plan_de_planta=_plan_de_planta,
            bench_count=bench_count,
            bench_max=bench_max,
            budew_on_op_field=budew_on_op_field,
            budew_op_index=budew_op_index,
            can_switch=can_switch,
            estimated_op_damage=estimated_op_damage,
            field_counts=field_counts,
            hand_counts=hand_counts,
            has_hydrapple=has_hydrapple,
            has_switch_card=has_switch_card,
            meowth_ability_lock=meowth_ability_lock,
            my_prize=my_prize,
            my_state=my_state,
            neutralization_zone_active=neutralization_zone_active,
            op_active_dodge_immune=op_active_dodge_immune,
            op_has_ability_immune_active=op_has_ability_immune_active,
            op_has_crustle_bench=op_has_crustle_bench,
            op_has_dreepy_line=op_has_dreepy_line,
            op_has_dwebble_bench=op_has_dwebble_bench,
            op_has_eevee_bench=op_has_eevee_bench,
            op_has_ethan_preevo=op_has_ethan_preevo,
            op_has_ex_immune_active=op_has_ex_immune_active,
            op_has_ex_immune_bench=op_has_ex_immune_bench,
            op_has_froslass=op_has_froslass,
            op_has_latias_ex=op_has_latias_ex,
            op_has_munkidori=op_has_munkidori,
            op_has_snorunt_bench=op_has_snorunt_bench,
            op_has_typhlosion=op_has_typhlosion,
            op_is_alakazam_deck=op_is_alakazam_deck,
            op_is_dragapult_dusknoir=op_is_dragapult_dusknoir,
            op_is_drednaw_deck=op_is_drednaw_deck,
            op_is_gardevoir_deck=op_is_gardevoir_deck,
            op_is_slowking_deck=op_is_slowking_deck,
            op_is_sylveon_deck=op_is_sylveon_deck,
            op_is_zoroark_deck=op_is_zoroark_deck,
            op_prize=op_prize,
            op_state=op_state,
            state=state,
            total_grass=total_grass,
            ),
        )

    _supp_values = evaluate_supporters()

    _best_supp_in_hand_val = 0
    _best_supp_in_hand_id = None
    for sid in (Boss_Orders, Dawn, Lillie_Determination, Lanas_Aid):
        if hand_counts.get(sid, 0) >= 1 and _supp_values.get(sid, 0) > _best_supp_in_hand_val:
            _best_supp_in_hand_val = _supp_values[sid]
            _best_supp_in_hand_id = sid

    # =================================================================
    # MATCH POINT contra el ACTIVO rival: el rematador esta en la BANCA
    # -----------------------------------------------------------------
    # (user, registro_010 paso 144 vs Marnie's Grimmsnarl ex, PERDIDA --
    # episodio 89104831). A 2 premios, con un Fezandipiti ex a 20 PV de activo
    # (2 efectivas: NO llega a su ataque de 3) y un Teal Mask Ogerpon ex de
    # banca ya a 4 energias, el ACTIVO rival era el propio **Marnie's
    # Grimmsnarl ex a 310/320 PV, con 3 energias y DEBILIDAD Planta**:
    # Myriad Leaf Shower = 30 + 30 x (4 propias + 3 SUYAS) = 240, x2 por
    # debilidad = **480 >= 310** -> KO de un ex de **2 premios** = los 2 que
    # nos faltaban = PARTIDA GANADA. La cadena (retirar -> promover -> atacar)
    # estaba servida y era pagable: el Fezandipiti llevaba energia de sobra
    # para su coste de retirada 1. El agente jugo Boss's Orders y gusteo una
    # Froslass de 1 premio; el rival remato en su turno.
    #
    # **Why:** todas las lecturas de "¿puedo noquear al ACTIVO rival?" se hacen
    # con el Pokemon que esta HOY en el activo (`_boss_dmg_to` ->
    # `_bo_can_ko_active`, `_bpr_active_can_ko`). Con el activo propio ATASCADO
    # eso da 0 -> `_bo_active_prize = 0` -> el activo rival se vuelve INVISIBLE
    # como objetivo y CUALQUIER premio de banca (1) le gana a ese "0". La
    # asimetria es el bug: para los objetivos de BANCA el mismo bloque SI mira a
    # traves de la retirada (`_bench_attacker_can_ko` en `_boss_prize_rank` y en
    # `_bo_win_via_bench`), pero para el ACTIVO nunca. Aqui se cierra esa
    # simetria en el unico caso que no admite discusion: cuando ese KO GANA la
    # partida. Ganar es VETO -- mismo criterio que PROMO_MATCH_POINT_VETO: si el
    # turno cierra la partida retirando, ningun gusteo de premio menor puede
    # desviarlo.
    #
    # Exige que el rematador este en la BANCA: si el activo ACTUAL ya noquea, la
    # via es atacar (`_active_attack_wins_now`, 99000) y no retirar.
    #
    # NO aplica contra MUROS INMUNES de activo (Crustle/Sylveon ex-inmunes,
    # Cornerstone inmune a habilidad). Ese caso ya tiene maquinaria propia y
    # medida -- `_wall_ko_promote` hace exactamente este relevo y CEDE al gusteo
    # a proposito ([[boss-el-chip-al-activo-no-es-un-premio]]: el mismo premio
    # sale mas barato sin pagar la retirada), y `rematar_muro_inmune_antes_de_
    # gustear` ordena el resto. Sin esta guarda el veto pisaba esa cesion: medido
    # en self-play, la regla disparaba en el **8%** de las partidas de
    # crustle/cornerstone (120/1500, frente al 0.8% vs Marnie) y ambos matchups
    # perdian ~0.6-0.75 pp. Con la guarda el disparo queda restringido a los
    # tableros donde nadie mas mira al activo rival a traves de la retirada.
    _win_ko_active_via_promote = False
    if (context == SelectContext.MAIN and can_switch
            and not op_has_ex_immune_active
            and not op_has_ability_immune_active
            and op_state.active and op_state.active[0] is not None
            and my_state.active and my_state.active[0] is not None):
        _wkap_opa = op_state.active[0]
        _wkap_act = my_state.active[0]
        if ((_wkap_opa.hp or 0) > 0
                and prize_count_op(_wkap_opa) >= my_prize):
            # ¿El activo ACTUAL ya lo remata? Entonces se ataca, no se retira.
            _wkap_a_e = len(_wkap_act.energies)
            _wkap_a_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                              and not state.energyAttached)
            _wkap_a_eff = (_wkap_a_e * _grass_mult()
                           + (_grass_attach_unit() if _wkap_a_attach else 0))
            _wkap_a_base = _attacker_base_damage(
                _wkap_act.id, _wkap_opa, _wkap_a_eff,
                grass_scale=total_grass,
                teal_self_energy=_wkap_a_e + (1 if _wkap_a_attach else 0),
                bench_count=bench_count)
            _wkap_active_kos = (
                _wkap_a_base > 0
                and _our_effective_damage(
                    _wkap_act, _wkap_opa, _wkap_a_base, ESTADO.meganium_in_play,
                    neutralization_zone_active) >= (_wkap_opa.hp or 0))
            _wkap_cost = 0 if has_switch_card else RETREAT_COST.get(_wkap_act.id, 1)
            if (not _wkap_active_kos
                    and (has_switch_card
                         or len(_wkap_act.energies) >= _wkap_cost)):
                # La retirada DESCARTA cartas enteras: el Grass del campo que
                # escala a Hydrapple se mide DESPUES del retiro.
                _wkap_grass_after = max(
                    0, total_grass - (0 if has_switch_card
                                      else _retreat_grass_units(_wkap_cost)))
                _win_ko_active_via_promote = _bench_attacker_can_ko(
                    my_state, _wkap_opa, ESTADO.meganium_in_play, total_grass,
                    bench_count, _wkap_grass_after, neutralization_zone_active)

    _boss_prize_rank = 0
    # `_boss_ko_threat_preevo`: hay una PRE-EVOLUCION AMENAZA en la banca rival
    # (Duraludon->Archaludon, etc.: THREAT_PREEVO_IDS) que podemos gustear y
    # NOQUEAR este turno. A diferencia de `_boss_prize_rank`, NO se anula cuando
    # el ataque al activo es "suficiente": sirve para decidir GUARDAR el Boss's
    # (vetar Lillie's) aunque el activo pudiera atacar (user, registro_007 p78).
    _boss_ko_threat_preevo = False
    if (context == SelectContext.MAIN
            and hand_counts.get(Boss_Orders, 0) >= 1
            and op_state.active and op_state.active[0] is not None):
        _bpr_active = my_state.active[0] if my_state.active else None
        _bpr_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                       and not state.energyAttached)

        _bpr_ret_cost = 0 if has_switch_card else (
            RETREAT_COST.get(_bpr_active.id, 1) if _bpr_active is not None else 1)
        # Wild Growth: cada Planta paga por dos, menos cartas descartadas al retirar.
        _bpr_ret_cards = _retreat_grass_units(_bpr_ret_cost)
        _bpr_grass_after = max(0, total_grass - _bpr_ret_cards)

        def _bpr_active_can_ko(_tgt):
            if _bpr_active is None or _tgt is None:
                return False
            e = len(_bpr_active.energies)
            eff = e * _grass_mult()
            eff_a = eff + (_grass_attach_unit() if _bpr_attach else 0)
            e_a = e + (1 if _bpr_attach else 0)
            base = _attacker_base_damage(_bpr_active.id, _tgt, eff_a,
                                         grass_scale=total_grass,
                                         teal_self_energy=e_a, bench_count=bench_count)
            if base <= 0:
                return False
            _d = _our_effective_damage(_bpr_active, _tgt, base,
                                       ESTADO.meganium_in_play, neutralization_zone_active)
            return _d >= (_tgt.hp or 0) and _d > 0

        for _bpr_tgt in (op_state.bench or []):
            if _bpr_tgt is None:
                continue
            _bpr_td = card_table.get(_bpr_tgt.id)
            if _bpr_td is None:
                continue
            # log 86339758 paso 98: Dwebble esta vetado como objetivo de gusteo
            # en mazo Crustle; no debe contar en el ranking de premios de Boss's.
            if ESTADO.op_is_crustle_deck and _bpr_tgt.id in (Dwebble_Grass, Dwebble_Fighting):
                continue

            if getattr(_bpr_td, 'megaEx', False):
                _bpr_base = 1
            elif getattr(_bpr_td, 'ex', False):
                _bpr_base = 3
            elif getattr(_bpr_td, 'stage2', False):
                _bpr_base = 5
            elif getattr(_bpr_td, 'stage1', False):
                _bpr_base = 7
            elif _bpr_tgt.id in THREAT_PREEVO_IDS:

                _bpr_base = 7
            else:
                continue

            _bpr_ko = _bpr_active_can_ko(_bpr_tgt)
            if not _bpr_ko and can_switch:
                _bpr_ko = _bench_attacker_can_ko(
                    my_state, _bpr_tgt, ESTADO.meganium_in_play, total_grass,
                    bench_count, _bpr_grass_after, neutralization_zone_active)
            if not _bpr_ko:
                continue
            _bpr_rank = _bpr_base + (0 if len(_bpr_tgt.energies) >= 1 else 1)
            if _boss_prize_rank == 0 or _bpr_rank < _boss_prize_rank:
                _boss_prize_rank = _bpr_rank
            if _bpr_tgt.id in THREAT_PREEVO_IDS:
                _boss_ko_threat_preevo = True

    if (_bo_active_attack_sufficient
            or _supp_values.get('_active_attack_sufficient')
            # El activo rival YA es el premio ganador y lo remata la banca tras
            # retirar: ningun gusteo de premio menor puede motivar el Supporter.
            or _win_ko_active_via_promote):
        _boss_prize_rank = 0

    # =================================================================
    # Req H (log 86023830, paso 69): vs mazo Mega Lucario, si el rival
    # tiene un Riolu (pre-evolucion de su atacante principal Mega Lucario
    # ex) en la banca que podemos gustear y noquear, y ya tenemos banca
    # propia establecida (>=2 Pokemon, suficientes atacantes cargados), la
    # prioridad NO es refrescar la mano ni desarrollar (Meowth ex,
    # Chikorita, Tapu...), sino jugar Boss's Orders sobre el Riolu para
    # cortar la linea del atacante principal. `_boss_deny_evo` ya confirma
    # que hay una pre-evolucion ex gusteable y noqueable en la banca rival
    # (muro inofensivo en el activo); el objetivo concreto lo elige
    # el ajuste tier_ko/traba, que prefiere el Riolu por THREAT_PREEVO_IDS. Este flag
    # VETA los desarrollos (tier DEVELOP) mas abajo para que Boss's
    # (supporter, tier 0) sea la jugada elegida por encima de Meowth ex.
    # El veto EXIME a Fezandipiti ex con la habilidad viva (ver alli): bajarlo
    # no consume el Supporter del turno, asi que no compite con el Boss's.
    # =================================================================
    _lucario_riolu_gust = (
        op_is_lucario_deck
        and not state.supporterPlayed
        and hand_counts.get(Boss_Orders, 0) >= 1
        and bench_count >= 2
        and bool(_supp_values.get('_boss_deny_evo'))
        and any(bp is not None and bp.id == Riolu
                for bp in (op_state.bench or [])))

    _boss_win_via_bench = bool(_supp_values.get('_boss_win_via_bench'))

    _boss_dodge_redirect = bool(_supp_values.get('_boss_dodge_redirect'))

    _boss_deny_alakazam_line = bool(_supp_values.get('_boss_deny_alakazam_line'))

    _best_supp_in_mazo_val = 0
    _best_supp_in_mazo_id = None
    for sid in (Boss_Orders, Dawn, Lillie_Determination, Lanas_Aid):
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0:
            val = _supp_values.get(sid, 0)
            if val > _best_supp_in_mazo_val:
                _best_supp_in_mazo_val = val
                _best_supp_in_mazo_id = sid

    # DISPONIBILIDAD DE TEAL DANCE, ESTABLE DURANTE TODO EL TURNO (user).
    # Las habilidades solo aparecen como opciones en el MENU PRINCIPAL; en los
    # prompts encadenados (buscar en el mazo, elegir el objetivo de un adjunte,
    # descartar...) el select NO las lista. Leer `select.option` desde esos
    # prompts daba SIEMPRE "Teal Dance no disponible", asi que el MISMO turno
    # proyectaba distinto dano segun el prompt en que estuvieramos: el motor
    # bajaba Meowth ex "para buscar Boss's Orders" (flag calculado en el menu,
    # CON Teal Dance) y dos pasos despues el fetch valoraba ese mismo Boss's a 0
    # (flag SIN Teal Dance) y se llevaba otra carta (registro_010 pasos 118/120).
    # Se cachea el SERIAL del activo cuya habilidad ofrecio el ultimo menu
    # principal del turno: entre menu y menu el estado de la habilidad no puede
    # cambiar, y exigir el serial evita arrastrar el cache si retiramos y
    # promovemos otro Pokemon.
    if context == SelectContext.MAIN:
        ESTADO._td_ability_serial = None
        _td_act = _active_of(my_state)
        if _td_act is not None and any(
                o.type == OptionType.ABILITY and o.area == AreaType.ACTIVE
                for o in select.option):
            ESTADO._td_ability_serial = getattr(_td_act, 'serial', None)

    _gust_2prize_via_boss = False
    _win_via_boss_gust = False
    _deny_evo_via_boss = False
    # El MURO INMUNE A EX (Crustle / Sylveon) esta de ACTIVO rival y nuestro
    # activo lo NOQUEA HOY -> matarlo va PRIMERO (ver la regla
    # `rematar_muro_inmune_antes_de_gustear` de _REGLAS_BOSS_PLAY).
    _ex_immune_wall_ko_ready = False
    if (not state.supporterPlayed
            and my_state.active and my_state.active[0] is not None
            and op_state.active and op_state.active[0] is not None
            and op_state.bench
            and (hand_counts.get(Boss_Orders, 0) >= 1
                 or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0)):
        _mbw_atk = my_state.active[0]
        _mbw_grass_hand = hand_counts.get(Basic_Grass_Energy, 0)
        _mbw_attach = (_mbw_grass_hand >= 1 and not state.energyAttached)
        # Teal Dance del PROPIO activo (user, pendiente del combo Myriad): la
        # habilidad adjunta OTRA Planta de la mano y es INDEPENDIENTE del
        # adjunte manual, asi que la energia alcanzable este turno puede ser +2
        # (adjunte + Teal Dance) y no +1. Sin modelarla, el remate ganador via
        # Boss's no se detectaba en cuanto el adjunte manual ya estaba gastado
        # (energyAttached) aunque la habilidad siguiera disponible. Se detecta
        # como en el resto del fichero: por la opcion ABILITY del menu, que el
        # motor solo ofrece si la habilidad es usable. El total extra no puede
        # superar las Plantas que hay en la mano (ambas salen de ahi).
        _mbw_td = (_mbw_atk is not None
                   and _mbw_atk.id == Teal_Mask_Ogerpon_ex
                   and _mbw_grass_hand >= 1
                   and ESTADO._td_ability_serial is not None
                   and getattr(_mbw_atk, 'serial', None) == ESTADO._td_ability_serial)
        _mbw_extra = min(_mbw_grass_hand,
                         (1 if _mbw_attach else 0) + (1 if _mbw_td else 0))

        def _mbw_dmg_to(_tgt):
            if _mbw_atk is None or _tgt is None:
                return 0
            _eff = len(_mbw_atk.energies) * _grass_mult()
            # Energia EFECTIVA tras las cargas pendientes de este turno. Cada
            # Planta adjuntada suma `_grass_attach_unit()` (2 con Meganium), asi
            # que la energia propia de Myriad es la MISMA magnitud efectiva
            # (antes `_atk_e` sumaba +1 en crudo y con Meganium se quedaba corta).
            _eff_after = _eff + _mbw_extra * _grass_attach_unit()
            _atk_e = _eff_after
            # Dano base via la tabla unica _attacker_base_damage (misma formula
            # y umbrales que antes; el remate debilidad/resistencia/inmunidad
            # queda inline debajo para conservar el comportamiento exacto de
            # este sitio, que NO aplica zona de neutralizacion ni el tope de
            # Crustle a plena vida).
            _d = _attacker_base_damage(_mbw_atk.id, _tgt, _eff_after,
                                       grass_scale=total_grass,
                                       teal_self_energy=_atk_e,
                                       bench_count=bench_count)
            if _d <= 0:
                return 0
            if _tgt.id in EX_IMMUNE_IDS and _mbw_atk.id in OUR_EX_IDS:
                return 0
            if _tgt.id in ABILITY_IMMUNE_IDS and _mbw_atk.id in OUR_ABILITY_IDS:
                return 0
            _td = card_table.get(_tgt.id)
            if _mbw_atk.id != Fezandipiti_ex and _td:
                if _td.weakness == EnergyType.GRASS:
                    _d *= 2
                elif _td.resistance == EnergyType.GRASS:
                    _d -= 30
            if _tgt.id == Drednaw and _d >= 200:
                return 0
            return _d

        _mbw_act = op_state.active[0]
        _mbw_act_dmg = _mbw_dmg_to(_mbw_act)
        _mbw_act_ko = (_mbw_act_dmg >= (_mbw_act.hp or 0) and _mbw_act_dmg > 0)
        _mbw_act_wins = _mbw_act_ko and my_prize <= prize_count_op(_mbw_act)

        # MURO INMUNE A EX DE ACTIVO QUE HOY NOQUEAMOS (user, registro_006
        # paso 47 vs Crustle, PERDIDA). Crustle/Sylveon anulan el dano de TODO
        # nuestro motor (Ogerpon ex, Hydrapple ex, Meowth ex, Fezandipiti ex):
        # la ventana para matarlos existe solo cuando un cuerpo NO-ex propio
        # (Tapu Bulu, Meganium...) esta cargado y de activo, y esa ventana se
        # cierra sola (el auto-dano de Wood Hammer, el golpe rival, la
        # retirada...). Por eso el muro va PRIMERO y los premios despues: en el
        # registro el agente gusteo un Ogerpon ex de banca para cobrar 2
        # premios con el mismo Tapu Bulu y dejo al Crustle vivo, con el resto
        # del tablero incapaz de tocarlo. Se calcula con el evaluador central
        # `_our_effective_damage` (no con `_mbw_dmg_to`) porque este SI aplica
        # el tope de Sturdy: el Crustle 533 a vida completa sobrevive a 10 PV,
        # asi que ahi NO hay KO del muro y la regla no debe disparar.
        if _mbw_act.id in EX_IMMUNE_IDS:
            _wall_eff = (len(_mbw_atk.energies) * _grass_mult()
                         + _mbw_extra * _grass_attach_unit())
            _wall_dmg = _our_effective_damage(
                _mbw_atk, _mbw_act,
                _attacker_base_damage(_mbw_atk.id, _mbw_act, _wall_eff,
                                      grass_scale=total_grass,
                                      teal_self_energy=_wall_eff,
                                      bench_count=bench_count),
                meganium_active=ESTADO.meganium_in_play,
                neutralization_zone=neutralization_zone_active)
            _ex_immune_wall_ko_ready = (_wall_dmg > 0
                                        and _wall_dmg >= (_mbw_act.hp or 0))

        if not _mbw_act_wins:
            for _mbw_bp in op_state.bench:
                if _mbw_bp is None:
                    continue
                # log 86339758 paso 98: Dwebble vetado como gusteo en mazo Crustle.
                if ESTADO.op_is_crustle_deck and _mbw_bp.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue
                _mbw_bp_dmg = _mbw_dmg_to(_mbw_bp)
                if (_mbw_bp_dmg >= (_mbw_bp.hp or 0) and _mbw_bp_dmg > 0
                        and my_prize <= prize_count_op(_mbw_bp)):
                    _win_via_boss_gust = True
                    break

            _mbw_act_prize = prize_count_op(_mbw_act) if _mbw_act_ko else 0
            _mbw_best_bench_prize = 0
            for _mbw_bp2 in op_state.bench:
                if _mbw_bp2 is None:
                    continue
                # log 86339758 paso 98: Dwebble vetado como gusteo en mazo Crustle.
                if ESTADO.op_is_crustle_deck and _mbw_bp2.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue
                _mbw_bp2_dmg = _mbw_dmg_to(_mbw_bp2)
                if _mbw_bp2_dmg >= (_mbw_bp2.hp or 0) and _mbw_bp2_dmg > 0:
                    _mbw_bp2_pr = prize_count_op(_mbw_bp2)
                    if _mbw_bp2_pr > _mbw_best_bench_prize:
                        _mbw_best_bench_prize = _mbw_bp2_pr
            _mbw_trade_down = (not _mbw_act_ko and _mbw_act_dmg > 0
                               and prize_count_op(_mbw_act) > _mbw_best_bench_prize)
            # `_ex_immune_wall_ko_ready`: con el muro Crustle/Sylveon de activo
            # y noqueable HOY, los 2 premios del ex de banca NO valen la
            # ventana (el flag alimenta tambien el motor Meowth ex ->
            # Last-Ditch -> Boss's, que se llevaria el turno buscando la carta).
            if (_mbw_best_bench_prize >= 2
                    and _mbw_best_bench_prize > _mbw_act_prize
                    and not _mbw_trade_down
                    and not _ex_immune_wall_ko_ready):
                _gust_2prize_via_boss = True

            # Gusteo de VALOR (deny-evo) disponible via mano O MAZO (plan motor
            # Meowth, mejora A): pre-evolucion de linea ex ENERGIZADA en la
            # banca rival que NOQUEAMOS tras gustearla. La maquinaria in-hand
            # (`_boss_deny_evo` en evaluate_supporters) exige Boss's EN MANO;
            # este flag standalone replica sus condiciones con el helper local
            # `_mbw_dmg_to` para que el motor Meowth ex -> Last-Ditch -> Boss's
            # tenga camino cuando el Boss's esta en el MAZO. Regla del user
            # (registro_006 paso 82 vs Garchomp): privilegiar SIEMPRE derrotar
            # la linea evolutiva del atacante ex rival. Espejo conservador:
            # solo dano del ACTIVO (sin fallback de banca tras retirar).
            # Misma cesion al muro inmune noqueable (`_ex_immune_wall_ko_ready`):
            # cortar una linea evolutiva rinde a futuro, matar al Crustle que
            # bloquea a todos nuestros ex rinde HOY y solo hoy.
            if (not _win_via_boss_gust and not _gust_2prize_via_boss
                    and not _ex_immune_wall_ko_ready):
                _dev_act_prize = prize_count_op(_mbw_act)
                for _dev_pe in op_state.bench:
                    if _dev_pe is None:
                        continue
                    # log 86339758 paso 98: Dwebble vetado como gusteo vs Crustle.
                    if (ESTADO.op_is_crustle_deck
                            and _dev_pe.id in (Dwebble_Grass, Dwebble_Fighting)):
                        continue
                    # Pre-evo de linea ex (2 premios al final) ENERGIZADA; la
                    # linea Alakazam (final no-ex, 1 premio) queda excluida.
                    # La clase sale del DATO DE CARTA (`_preevo_de_linea_ex`),
                    # no de `EX_PREEVO_IDS`: la lista curada cubria las lineas
                    # que alguien inscribio a mano tras perder una partida, y
                    # dejaba fuera cualquier otra del entorno (p.ej. Frillish ->
                    # Jellicent ex, que SI esta en el mazo jellicent_lock). El
                    # helper es un superconjunto exacto de la lista: todos sus
                    # miembros salvo Abra/Kadabra -- que es justo lo que
                    # `NONEX_FINAL_PREEVO_IDS` excluia -- culminan en un ex.
                    if (not _preevo_de_linea_ex(_dev_pe.id)
                            or len(_dev_pe.energies) < 1):
                        continue
                    _dev_dmg = _mbw_dmg_to(_dev_pe)
                    if not (_dev_dmg >= (_dev_pe.hp or 0) and _dev_dmg > 0):
                        continue
                    # Excepcion (registro_006 paso 75 vs Archaludon): si el
                    # ACTIVO rival es TAMBIEN una pre-evo AMENAZA igual o mas
                    # desarrollada, noquearlo ya remueve la misma clase de
                    # amenaza por el mismo premio -- no gastar el motor.
                    if (_mbw_act.id in THREAT_PREEVO_IDS
                            and len(_mbw_act.energies) >= len(_dev_pe.energies)):
                        continue
                    # Espejo del VETO DE ETAPA (registro_008 paso 93): si el
                    # ACTIVO es un eslabon MAS EVOLUCIONADO de la MISMA linea,
                    # noquearlo ya corta la cadena mas arriba y no cuesta el
                    # motor de busqueda ni el Supporter.
                    if (_mbw_act_ko
                            and _supera_en_evolucion(_mbw_act, _dev_pe)
                            and _dev_act_prize >= prize_count_op(_dev_pe)):
                        continue
                    # Espejo de `_bo_pe_is_ex_preevo_energized` (premios
                    # IGUALES: mismo cobro pero corta la linea) y de
                    # `_bo_pe_is_energized_preevo_vs_bare_wall` (activo muro
                    # desnudo de <=1 premio: noquearlo no corta nada).
                    if ((_mbw_act_ko
                         and _dev_act_prize == prize_count_op(_dev_pe))
                            or (len(_mbw_act.energies) == 0
                                and _dev_act_prize <= 1)):
                        _deny_evo_via_boss = True
                        break

    # No malgastar Boss's Orders en un gusteo defensivo si YA podemos noquear al
    # activo rival este mismo turno retirando a un atacante listo de la banca
    # (p. ej. subir a Tapu Bulu). can_attack solo mira el activo actual, no la
    # opcion de retirada, por eso hay que comprobarlo aparte.
    _bdg_retreat_ko = False
    if (can_switch and op_state.active and op_state.active[0] is not None
            and my_state.active and my_state.active[0] is not None):
        _bdg_cur_active = my_state.active[0]
        _bdg_ret_cost = (0 if has_switch_card
                         else RETREAT_COST.get(_bdg_cur_active.id, 1))
        _bdg_ret_cards = _retreat_grass_units(_bdg_ret_cost)
        _bdg_grass_after = max(0, total_grass - _bdg_ret_cards)
        _bdg_retreat_ko = _bench_attacker_can_ko(
            my_state, op_state.active[0], ESTADO.meganium_in_play, total_grass,
            bench_count, _bdg_grass_after, neutralization_zone_active)

    # Adjunte que HABILITA la retirada hacia un atacante de banca LETAL (user,
    # registro_034 paso 141 vs mazo Crustle/Terrakion, PERDIDA): el activo
    # (Fezandipiti ex, 0 energia) no puede atacar NI retirarse, pero en banca
    # hay un atacante listo (Dipplin cargado: Do the Wave x2 por debilidad
    # Planta del Terrakion = KO) y UNA energia de la mano paga el coste de
    # retirada. La linea correcta: energia -> ACTIVO, retirar, promover y
    # noquear. Generaliza `_tapu_sac_enable_retreat` (que exige un Tapu Bulu
    # >=4e) a CUALQUIER atacante de banca via `_bench_attacker_can_ko` (el
    # mismo detector de `_bdg_retreat_ko`, que aqui no aplica porque exige
    # `can_switch`: la retirada aun NO es legal). Sin esto, el ruteo de
    # energia prefiere Teal Dance / cargas de banca (~30000-31600) y la
    # linea de KO se pierde por completo.
    # Nucleo compartido (`_grass_unlocks_active_retreat`): ¿las Plantas que aun
    # pueden aterrizar en el activo pagan su retirada y dejan atacar a un cuerpo
    # de banca? Aqui se consume para el adjunte MANUAL; mas abajo, sin la guarda
    # de `state.energyAttached`, para la ruta por HABILIDAD.
    #
    # PRESUPUESTO de carga hacia el ACTIVO (mismo calculo que
    # `_carga_activo_remata`): adjunte manual si sigue libre + habilidades que
    # pueden apuntar al activo (`_grass_ability_slots_activo`), acotado por las
    # Plantas de la mano. El suelo de 1 preserva el comportamiento historico para
    # los consumidores que traen su propia Planta de fuera de la mano (la Night
    # Stretcher la recupera del DESCARTE: alli `hand_counts` es 0 y la linea de
    # una sola Planta debe seguir viva).
    _grass_active_routes = (0 if state.energyAttached else 1)
    if not meowth_ability_lock:
        # Con Watchtower / Iron Thorns ex las habilidades de carga estan
        # apagadas: contarlas dejaria la 1a Planta tirada en un activo atrapado
        # sin nadie que complete el coste (mismo guardia que
        # `_grass_attach_route_open(abilities_off=...)`).
        _grass_active_routes += _grass_ability_slots_activo(
            state, my_state, field_counts)
    _grass_active_budget = max(
        1, min(hand_counts.get(Basic_Grass_Energy, 0), _grass_active_routes))
    _grass_unlock_ko, _grass_unlock_chip = _grass_unlocks_active_retreat(
        my_state, op_state, ESTADO.meganium_in_play, total_grass, bench_count,
        neutralization_zone_active, can_attack, budget=_grass_active_budget)

    _attach_enable_retreat_ko = (
        not _bdg_retreat_ko and not can_switch
        and not state.energyAttached
        and hand_counts.get(Basic_Grass_Energy, 0) >= 1
        and _grass_unlock_ko)

    # MISMA LINEA PERO SIN KO (user, log 88162794 turnos 11 y 13 vs Archaludon ex,
    # PERDIDA 6-1 sin atacar NUNCA desde el turno 7). Nuestro activo (Meowth ex, 0
    # energia, coste de retirada 1) no puede atacar NI retirarse, y en la banca
    # espera un Meganium con energia de sobra (e6/e8) que SI puede atacar. Solar
    # Beam no noquea a nada del rival (Archaludon ex de 300/400 PV; Duraludon
    # RESISTE Planta -30 y Full Metal Lab quita otros -30), asi que
    # `_attach_enable_retreat_ko` -- y con el TODA la familia de pivotes de
    # retirada, que exige KO -- nunca disparaba: el agente adjuntaba la Planta al
    # Meganium de banca (ya cargadisimo, +0 de dano: Solar Beam es plano) y
    # cerraba el turno. Cuatro turnos seguidos regalados.
    #
    # Si el activo NO puede atacar de ninguna forma este turno, el chip del
    # atacante de banca es infinitamente mejor que 0: la energia va al ACTIVO para
    # pagar la retirada. El resto de la cadena (RETREAT, promocion, ataque) ya la
    # resuelve la maquinaria existente en cuanto la retirada es legal.
    #
    # Deck-agnostica y conservadora:
    #  - exige que el atacante de banca YA este listo SIN esta energia (si la
    #    energia es la que lo deja listo, su sitio es la banca: turno 9 del mismo
    #    log, Meganium a e2 -> e4);
    #  - cede siempre a la version LETAL (`_attach_enable_retreat_ko`, 41000);
    #  - si el activo es un ex, replica la guarda "no cambiar un ex por un cuerpo
    #    peor" del scorer de retirada (`_xx_vale`): el cuerpo que sube debe
    #    aguantar al menos lo que le queda al ex. Asi el adjunte nunca habilita
    #    una retirada que despues se vetaria, malgastando la energia del turno.
    _attach_enable_retreat_attack = (
        not _bdg_retreat_ko and not _attach_enable_retreat_ko
        and not can_switch and not can_attack
        and not state.energyAttached
        and hand_counts.get(Basic_Grass_Energy, 0) >= 1
        and _grass_unlock_chip)

    # RUTA POR HABILIDAD de la misma linea (user, registro_014 pasos 137/141 vs
    # Alakazam, GANADA pero con tres turnos malgastados): Ripening Charge del
    # Hydrapple ex "adjunta una Planta basica de tu mano a 1 de tus Pokemon" y
    # NO consume el adjunte manual del turno. Con el Fezandipiti ex activo a 0
    # energias (coste de retirada 1) y un Hydrapple ex de banca ya listo, la
    # linea "Planta al activo -> retirar -> Syrup Storm" seguia disponible
    # DESPUES de haber gastado el adjunte manual, pero las dos banderas de
    # arriba se apagan con `state.energyAttached` y nadie mas la veia: la
    # habilidad se vetaba, las Plantas se quemaban como coste de una Ultra Ball
    # y el turno acababa sin atacar.
    #
    # Estas dos NO miran `state.energyAttached` ni la mano: cada consumidor
    # anade su propia condicion (la habilidad exige Planta en mano; la Night
    # Stretcher exige Planta en el DESCARTE y ruta de carga viva).
    _ability_unlock_retreat_ko = (
        not _bdg_retreat_ko and not can_switch and _grass_unlock_ko)
    _ability_unlock_retreat_attack = (
        not _bdg_retreat_ko and not can_switch and not can_attack
        and _grass_unlock_chip)

    # Regla (user, log 85804848 paso 49, vs Alakazam, PERDIMOS): si un atacante
    # de banca YA puede noquear al activo rival este turno (retirar+promover,
    # `_bdg_retreat_ko`), Boss's Orders es redundante como remate: no hace falta
    # gustear a la banca para cobrar premio, basta con noquear al activo. En ese
    # caso, si tenemos Lillie's Determination en la mano, refrescar con Lillie's
    # rinde mas que gastar el supporter en un gusteo innecesario, asi que anulamos
    # `_boss_prize_rank` para ceder la prioridad a Lillie's. Se respetan los
    # gusteos realmente ejecutables/valiosos (letal a banca, 2 premios) que se
    # puntuan por sus propias ramas antes que `_boss_prize_rank`.
    if (_bdg_retreat_ko
            and hand_counts.get(Lillie_Determination, 0) >= 1
            and not _win_via_boss_gust
            and not _gust_2prize_via_boss):
        _boss_prize_rank = 0

    _boss_defensive_gust = False
    if (ESTADO.op_is_crustle_deck and not state.supporterPlayed and not can_attack
            and not _bdg_retreat_ko
            and not _conf_should_retreat
            and not _win_via_boss_gust and not _gust_2prize_via_boss
            and hand_counts.get(Boss_Orders, 0) >= 1
            and op_state.active and op_state.active[0] is not None
            and len(op_state.active[0].energies) >= 1
            and op_state.bench):
        _bdg_op_act_rc = RETREAT_COST.get(op_state.active[0].id, 0)
        _bdg_threshold = 1 if _bdg_op_act_rc == 0 else 2
        for _bdg_bp in op_state.bench:
            if _bdg_bp is None:
                continue
            _bdg_rc = RETREAT_COST.get(_bdg_bp.id, 0)
            _bdg_e = len(_bdg_bp.energies)
            if (_bdg_rc - _bdg_e) >= _bdg_threshold:
                _boss_defensive_gust = True
                break

    _meowth_devel_lillie = False
    if (not state.supporterPlayed
            and (hand_counts.get(Meowth_ex, 0) >= 1
                 or field_counts.get(Meowth_ex, 0) >= 1)
            and (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                 or hand_counts.get(Lillie_Determination, 0) >= 1)):
        _mdl_in_play = 0
        for _mdl_p in (list(my_state.active or []) + list(my_state.bench or [])):
            if _mdl_p is not None and _mdl_p.id != Meowth_ex:
                _mdl_in_play += 1
        _mdl_hand_size = len(my_state.hand) if my_state.hand else 0
        _mdl_max_in_play = 4 if _mdl_hand_size <= 2 else 3
        if _mdl_in_play <= _mdl_max_in_play:
            _meowth_devel_lillie = True

    # ¿Podemos usar Last-Ditch Catch de Meowth ex este turno? Su habilidad se
    # dispara al JUGARLO desde la mano, y "no puedes usar mas de 1 habilidad
    # Last-Ditch por turno". Si algun Meowth ex EN JUEGO ya aparecio este turno
    # (appearThisTurn), su Last-Ditch ya se gasto -> jugar OTRO Meowth ex no
    # buscaria Supporter. Si el/los Meowth en juego son de turnos anteriores
    # (appearThisTurn False), la habilidad esta disponible y jugar uno nuevo SI
    # busca Supporter. Sin Meowth en juego, tambien esta disponible.
    _meowth_ld_free = not any(
        _mlf_p is not None and _mlf_p.id == Meowth_ex
        and getattr(_mlf_p, 'appearThisTurn', False)
        for _mlf_p in (list(my_state.active or []) + list(my_state.bench or [])))

    # ¿Sigue VIVO el motor Last-Ditch de este turno? Es decir: ¿queda un Meowth
    # ex que se pueda BAJAR y buscar Supporter (Xerosic vs Alakazam)? Exige las
    # tres cosas: hueco de habilidad (< 2 copias en campo), la Last-Ditch del
    # turno sin gastar y un cuerpo ALCANZABLE (mano o mazo). Es el mismo
    # criterio que `_alakazam_dig_xerosic_engine` y que la rama PLAY de Meowth
    # ex; vive aqui arriba porque lo consultan DOS sitios lejanos entre si: el
    # veto del cuerpo ex redundante y la reserva del ultimo hueco de banca.
    _alk_ld_engine_vivo = (
        field_counts.get(Meowth_ex, 0) < 2
        and _meowth_ld_free
        and (hand_counts.get(Meowth_ex, 0) >= 1
             or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                 Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0))

    # ¿Nuestro ACTIVO ya es un atacante LISTO para atacar este turno? (activo en
    # MAIN_ATTACKERS con energia efectiva suficiente y podemos atacar). Se usa
    # para no malgastar jugadas en cuerpos de utilidad (p.ej. Meowth ex, que solo
    # busca un Supporter) cuando ya tenemos con que atacar.
    _active_ready_attacker = False
    _ara_act = my_state.active[0] if my_state.active else None
    # ¿El activo NO puede DAÑAR al activo rival por INMUNIDAD? (Cornerstone Mask
    # Ogerpon ex anula a nuestros Pokemon CON habilidad; Crustle/Sylveon anulan a
    # nuestros ex; Neutralization Zone anula ex vs un 1-premio). Un atacante
    # "cargado" que hace 0 al muro rival NO es un atacante util este turno: la
    # jugada productiva es el motor Boss's (bajar Meowth ex -> buscar Boss's ->
    # gustear un objetivo ATACABLE de la banca rival). Sin esto, el activo parecia
    # listo (`_active_ready_attacker`) y vetaba a Meowth ex, y la opcion de ATACAR
    # (0 dano) ganaba (user: Hydrapple ex vs Cornerstone activo + Mega Lucario en
    # banca). `_active_immune_vs_op_active` se reutiliza en el score del ataque.
    _op_act_imm = _active_of(op_state)
    _op_act_imm_data = (card_table.get(_op_act_imm.id)
                        if _op_act_imm is not None else None)
    _op_act_is_exmega = bool(_op_act_imm_data and (
        getattr(_op_act_imm_data, 'ex', False)
        or getattr(_op_act_imm_data, 'megaEx', False)))
    _active_immune_vs_op_active = False
    if _ara_act is not None and _op_act_imm is not None:
        if op_has_ability_immune_active and _ara_act.id in OUR_ABILITY_IDS:
            _active_immune_vs_op_active = True
        elif op_has_ex_immune_active and _ara_act.id in OUR_EX_IDS:
            _active_immune_vs_op_active = True
        elif (neutralization_zone_active and _ara_act.id in OUR_EX_IDS
              and not _op_act_is_exmega):
            _active_immune_vs_op_active = True
    if (can_attack and _ara_act is not None and _ara_act.id in MAIN_ATTACKERS
            and _can_attack_eff(_ara_act.id, len(_ara_act.energies))
            and not _active_immune_vs_op_active):
        _active_ready_attacker = True

    # ¿Hay un objetivo ATACABLE en la banca rival al que gustear con Boss's cuando
    # el activo rival es inmune a nuestro atacante? Un Pokemon de banca que NO
    # reproduzca la misma inmunidad de habilidad (no es otro Cornerstone) puede
    # subirse al activo con Boss's Orders y atacarse. Habilita el motor Meowth ex
    # -> Last-Ditch -> Boss's -> gustear+atacar la banca (user: Hydrapple ex vs
    # Cornerstone activo con Mega Lucario en banca; atacar al Cornerstone = 0).
    _boss_gust_immune_active = False
    if _active_immune_vs_op_active:
        for _bt in (op_state.bench or []):
            if _bt is not None and _bt.id not in ABILITY_IMMUNE_IDS:
                _boss_gust_immune_active = True
                break
    # Motor completo Meowth ex -> Last-Ditch -> Boss's (en el MAZO) -> gustear un
    # objetivo atacable de la banca cuando el activo rival es inmune. Se usa para
    # (a) EXIMIR a Meowth ex del veto `_block_4th_ex` (que vs Cornerstone/Crustle
    # bloquea bajar un 4o ex) -- Meowth es UTILIDAD, no un atacante de mas -- y
    # (b) puntuar su bajada en la cadena de PLAY.
    _meowth_immune_boss_engine = (
        _boss_gust_immune_active
        and hand_counts.get(Boss_Orders, 0) == 0
        and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
            Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
        and not state.supporterPlayed
        and _meowth_ld_free
        and field_counts.get(Meowth_ex, 0) < 2
        and bench_count < 5)

    # Numero de atacantes LISTOS (activo + banca) con energia suficiente para
    # atacar ya. Sirve para decidir si merece la pena refrescar la mano (bajar
    # Meowth ex -> Lillie's) o si ya tenemos atacantes de sobra.
    _ready_attacker_count = 0
    for _rac_p in (list(my_state.active or []) + list(my_state.bench or [])):
        if (_rac_p is not None and _rac_p.id in MAIN_ATTACKERS
                and _can_attack_eff(_rac_p.id, len(_rac_p.energies))):
            _ready_attacker_count += 1

    # ¿Existe ALGUN camino a un SEGUNDO atacante (aparte del activo) sin refrescar
    # la mano? Se usa para el motor Meowth->Lillie's cuando la banca no tiene
    # atacante de repuesto (user, registro_006 paso 78). Hay camino si:
    #   * ya hay un cuerpo ATACANTE en banca (aunque este sin energia: se carga), o
    #   * podemos poner en banca un basico atacante desde la mano, o
    #   * hay una evolucion LEGAL a un atacante (pre-evo en juego + evo en mano).
    _BASIC_ATTACKER_IDS = (Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex, Pinsir)
    _has_bench_attacker_body = any(
        _b is not None and _b.id in MAIN_ATTACKERS
        for _b in (my_state.bench or []))
    _can_bench_basic_attacker = (bench_count < 5 and any(
        hand_counts.get(_bid, 0) >= 1 for _bid in _BASIC_ATTACKER_IDS))
    _can_evolve_to_attacker = (
        (field_counts.get(Applin, 0) >= 1 and hand_counts.get(Dipplin, 0) >= 1)
        or (field_counts.get(Dipplin, 0) >= 1
            and hand_counts.get(Hydrapple_ex, 0) >= 1)
        or (field_counts.get(Chikorita, 0) >= 1
            and hand_counts.get(Bayleef, 0) >= 1)
        or (field_counts.get(Bayleef, 0) >= 1
            and hand_counts.get(Meganium, 0) >= 1))
    _no_second_attacker_path = not (
        _has_bench_attacker_body or _can_bench_basic_attacker
        or _can_evolve_to_attacker)

    # Remate rival REAL sobre nuestro activo (resuelve el ataque via attack_table,
    # no el heuristico `active_ko_likely`/`_op_best_damage_vs` que subestima a Mega
    # Lucario y otros). True si el activo rival NOQUEA a nuestro activo el proximo
    # turno.
    _active_doomed_real = False
    _adr_act = my_state.active[0] if my_state.active else None
    _adr_opa = _active_of(op_state)
    if _adr_act is not None and _adr_opa is not None:
        _active_doomed_real = (
            _op_active_attack_damage_to(
                _adr_opa, _adr_act, getattr(op_state, 'handCount', None))
            >= (_adr_act.hp or 0))

    _ctm_dipplin_low = False
    _ctm_tapu_high = False
    _ctm_tapu_ready = False
    if ESTADO.op_is_crustle_deck:
        _ctm_op_act = op_state.active[0] if op_state.active else None
        _ctm_active_is_crustle = (_ctm_op_act is not None and
                                  _ctm_op_act.id in (Crustle_Grass, Crustle_Fighting))
        _ctm_all_in_play = (field_counts.get(Dipplin, 0) >= 1
                            and field_counts.get(Tapu_Bulu, 0) >= 1
                            and field_counts.get(Meganium, 0) >= 1)
        if _ctm_active_is_crustle and _ctm_all_in_play:
            # Tapu Bulu es nuestro mejor atacante vs Crustle (no-ex, 220). Si esta
            # cargado (activo O banca), priorizarlo SIEMPRE: no retirar un Tapu
            # activo ya listo, y si esta en banca hacer el maximo esfuerzo por
            # subirlo a atacar. Solo se pica con Dipplin cuando Tapu NO esta listo.
            for _ctm_tp in (([my_state.active[0]] if my_state.active else [])
                            + list(my_state.bench or [])):
                if (_ctm_tp is not None and _ctm_tp.id == Tapu_Bulu
                        and _can_attack_eff(Tapu_Bulu, len(_ctm_tp.energies))):
                    _ctm_tapu_ready = True
                    break
            if _ctm_tapu_ready:
                _ctm_tapu_high = True
            elif len(_ctm_op_act.energies) <= 2:
                _ctm_dipplin_low = True
            else:
                _ctm_tapu_high = True

    _ctm_chikorita_bench = False
    _ctm_applin_bench = False
    if ESTADO.op_is_crustle_deck:
        _ctm_chikorita_bench = any(
            bp is not None and bp.id in (Chikorita, Bayleef, Meganium)
            for bp in (my_state.bench or []))
        _ctm_applin_bench = any(
            bp is not None and bp.id in (Applin, Dipplin, Hydrapple_ex)
            for bp in (my_state.bench or []))

    _ctm_charge_active_dipplin = False
    if ESTADO.op_is_crustle_deck and not _ctm_tapu_ready:
        _ctm_cad_op_act = op_state.active[0] if op_state.active else None
        _ctm_cad_act_crustle = (_ctm_cad_op_act is not None and
                                _ctm_cad_op_act.id in (Crustle_Grass, Crustle_Fighting))
        _ctm_cad_dipplin_active = (my_state.active and my_state.active[0] is not None
                                   and my_state.active[0].id == Dipplin)
        if _ctm_cad_dipplin_active:
            if _ctm_cad_act_crustle:
                if len(_ctm_cad_op_act.energies) <= 2:
                    _ctm_charge_active_dipplin = True
            else:
                _ctm_charge_active_dipplin = True

    if context == SelectContext.MAIN and _ctm_dipplin_low:
        _my_cards_ctm = ([my_state.active[0]] if my_state.active else [])
        for _bp_ctm in my_state.bench:
            if _bp_ctm is not None:
                _my_cards_ctm.append(_bp_ctm)
        _dip_idx_ctm = -1
        for _idx_ctm, _mc_ctm in enumerate(_my_cards_ctm):
            if _mc_ctm is not None and _mc_ctm.id == Dipplin:
                if _dip_idx_ctm < 0:
                    _dip_idx_ctm = _idx_ctm
                if len(_mc_ctm.energies) >= 1:
                    _dip_idx_ctm = _idx_ctm
                    break
        if _dip_idx_ctm >= 0:
            ESTADO.plan.attacker = _dip_idx_ctm
            ESTADO.plan.target = 0
            ESTADO.plan.attack_index = 0
            ESTADO.plan.energy = (len(_my_cards_ctm[_dip_idx_ctm].energies) < 1)
            if op_state.active and op_state.active[0] is not None:
                ESTADO.plan.remain_hp = (op_state.active[0].hp or 0)

    if context == SelectContext.MAIN and _ctm_tapu_ready:
        _my_cards_tpr = ([my_state.active[0]] if my_state.active else [])
        for _bp_tpr in my_state.bench:
            if _bp_tpr is not None:
                _my_cards_tpr.append(_bp_tpr)
        _tapu_idx_tpr = -1
        for _idx_tpr, _mc_tpr in enumerate(_my_cards_tpr):
            if (_mc_tpr is not None and _mc_tpr.id == Tapu_Bulu
                    and _can_attack_eff(Tapu_Bulu, len(_mc_tpr.energies))):
                _tapu_idx_tpr = _idx_tpr
                break
        if _tapu_idx_tpr >= 0:
            # Tapu Bulu ya cargado: si es el activo (idx 0) se ataca sin retirar;
            # si esta en banca, forzar la promocion retirando el activo.
            ESTADO.plan.attacker = _tapu_idx_tpr
            ESTADO.plan.target = 0
            ESTADO.plan.attack_index = 0
            ESTADO.plan.energy = False
            if op_state.active and op_state.active[0] is not None:
                ESTADO.plan.remain_hp = (op_state.active[0].hp or 0)

    _active_pokemon = my_state.active[0] if my_state.active else None
    _active_needs_energy = False
    if _active_pokemon is not None and not state.energyAttached:
        _act_energy = len(_active_pokemon.energies)
        _act_effective = _act_energy * _grass_mult()
        if _active_pokemon.id == Hydrapple_ex:
            _active_needs_energy = (_act_effective < 2)
        elif _active_pokemon.id == Dipplin:
            _active_needs_energy = (_act_energy < 1)
        elif _active_pokemon.id == Teal_Mask_Ogerpon_ex:
            _active_needs_energy = (_act_effective < 3)
        elif _active_pokemon.id == Tapu_Bulu:

            _active_needs_energy = (_act_effective < 4)
        elif _active_pokemon.id == Pinsir:

            _active_needs_energy = (_act_effective < 2)
        elif _active_pokemon.id == Meowth_ex:

            _active_needs_energy = (_act_energy == 0)
        elif _active_pokemon.id == Fezandipiti_ex:

            _fez_eff_after_att = _act_energy + _grass_attach_unit()
            if _act_effective >= 3:
                _active_needs_energy = False
            elif _fez_eff_after_att >= 3:
                _active_needs_energy = True
            else:

                _active_needs_energy = (_act_energy == 0)
        elif _active_pokemon.id in (Chikorita, Bayleef, Meganium):

            _retreat_needed = RETREAT_COST.get(_active_pokemon.id, 1)
            # Con Wild Growth cada energia basica de Planta vale por dos para
            # pagar la retirada, por lo que basta la energia efectiva (p.ej.
            # Meganium con 1 energia ya puede retirarse: 1*2 >= 2).
            _active_needs_energy = (_act_effective < _retreat_needed)

    _energy_in_hand = hand_counts.get(Basic_Grass_Energy, 0)
    _enough_for_both = (_energy_in_hand >= 2)

    _active_hydra_ready = (
        _active_pokemon is not None
        and _active_pokemon.id == Hydrapple_ex
        and len(_active_pokemon.energies) * _grass_mult() >= 2
    )

    _active_hydra_capped = (
        _active_pokemon is not None
        and _active_pokemon.id == Hydrapple_ex
        and len(_active_pokemon.energies) >= 2
    )

    _bench_has_chargeable = any(bp is not None for bp in (my_state.bench or []))

    _reserve_hydra_active_charge = False
    if (_active_pokemon is not None and _active_pokemon.id == Hydrapple_ex
            and _energy_in_hand == 1 and not op_has_ex_immune_active):
        _rhac_mult = _grass_mult()
        _rhac_cur = len(_active_pokemon.energies) * _rhac_mult
        _rhac_after = len(_active_pokemon.energies) + _grass_attach_unit()
        if _rhac_cur < 2 and _rhac_after >= 2:
            _reserve_hydra_active_charge = True

    _prob_energy_draw_soon = _prob_draw_any(Basic_Grass_Energy, draws=2)
    _energy_starved_low_draw = (
        _active_needs_energy and _energy_in_hand == 0 and
        not state.energyAttached and _prob_energy_draw_soon < 0.5
    )

    _hydrapple_bench_needs_energy = False
    if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
        for _bp in (my_state.bench or []):
            if _bp is not None and _bp.id == Hydrapple_ex:
                _hydra_bench_e = len(_bp.energies)
                _hydra_bench_eff = _hydra_bench_e * _grass_mult()
                if _hydra_bench_eff < 2:
                    _hydrapple_bench_needs_energy = True
                    break

    _energy_demands_before_teal = 0
    if _active_needs_energy:
        _energy_demands_before_teal += 1
    if _hydrapple_bench_needs_energy:
        _energy_demands_before_teal += 1
    _enough_after_priorities = (_energy_in_hand > _energy_demands_before_teal)

    _reserve_energy_for_hydra_evolve = False
    if (_active_pokemon is not None and _active_pokemon.id == Dipplin
            and _energy_in_hand == 1 and not op_has_ex_immune_active):
        _hydra_reachable_this_turn = (
            hand_counts.get(Hydrapple_ex, 0) >= 1
            or hand_counts.get(Ultra_Ball, 0) >= 1)
        if _hydra_reachable_this_turn:
            if len(_active_pokemon.energies) + _grass_attach_unit() >= 2:
                _reserve_energy_for_hydra_evolve = True

    _bcs_playable_in_hand = False
    if hand_counts.get(Bug_Catching_Set, 0) >= 1:
        for _bcs_cid, _bcs_states in ESTADO.CARTAS_ACTIVAS_EN_MAZO.items():
            if _bcs_states[ESTADO_MAZO] <= 0:
                continue
            if _bcs_cid == Basic_Grass_Energy:
                _bcs_playable_in_hand = True
                break
            _bcs_cdata = card_table.get(_bcs_cid)
            if (_bcs_cdata is not None and _bcs_cdata.cardType == CardType.POKEMON
                    and _bcs_cdata.energyType == EnergyType.GRASS):
                _bcs_playable_in_hand = True
                break

    _pp_playable_in_hand = False
    if hand_counts.get(Poke_Pad, 0) >= 1:
        for _pp_cid in (Chikorita, Bayleef, Meganium, Applin, Dipplin, Tapu_Bulu):
            _pp_states = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(_pp_cid)
            if _pp_states is not None and _pp_states[ESTADO_MAZO] > 0:
                _pp_playable_in_hand = True
                break

    # --- Regla (user): Meowth ex + Lillie's Determination en NUESTRO primer turno ---
    # En nuestro primer turno NO se debe jugar Meowth ex primero: se despliega el
    # resto de la mano (Pokemon basicos y artefactos) y se juega Lillie's
    # Determination al FINAL. Motivo: Lillie's baraja toda la mano en el mazo, asi
    # que cualquier Supporter que Meowth ex buscara terminaria barajado (fetch
    # desperdiciado) y Meowth ex quedaria de mas en la banca como Pokemon de 2
    # premios. EXCEPCION: al finalizar el turno, si en juego solo queda el Pokemon
    # activo (banca vacia) y Meowth ex es la UNICA carta de la mano, entonces si se
    # baja Meowth ex para buscar Lillie's Determination y jugarla el siguiente turno.
    _our_first_turn = ((state.turn == 1 and ESTADO.we_go_first)
                       or (state.turn == 2 and not ESTADO.we_go_first))
    _lillie_available = (
        hand_counts.get(Lillie_Determination, 0) >= 1
        or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
            Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    _meowth_hand_only_card = (
        hand_counts.get(Meowth_ex, 0) >= 1
        and (len(my_state.hand) if my_state.hand else 0) == 1)
    _meowth_lone_fetch = (
        _our_first_turn
        and bench_count == 0
        and field_counts.get(Meowth_ex, 0) == 0
        and _meowth_hand_only_card
        and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
            Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)

    # DONK PROYECTADO EN NUESTRO PRIMER TURNO (bandera de tablero, no depende de
    # la carta que se este puntuando): banca VACIA, solo el basico activo, y el
    # ACTIVO rival ya proyecta un KO con una sola energia (via
    # `_op_active_attack_damage_to`, que asume su adjunte del turno). Sin banca,
    # ese KO es DERROTA instantanea, asi que bajar Meowth ex como CUERPO es la
    # jugada de supervivencia. Es la UNICA razon por la que el primer turno se
    # baja un Meowth ex teniendo Lillie's en mano; la usan el guard anti-donk
    # (score 21900) y la excepcion del veto `no-meowth-para-lillie`.
    _meowth_antidonk_now = False
    if (state.turn == 1 and ESTADO.we_go_first
            and bench_count == 0
            and field_counts.get(Meowth_ex, 0) == 0
            and _meowth_ld_free
            and my_state.active and my_state.active[0] is not None
            and op_state.active and op_state.active[0] is not None):
        _mdk_act0 = my_state.active[0]
        _mdk_hp0 = getattr(_mdk_act0, 'hp', 0) or 0
        _mdk_hit0 = _op_active_attack_damage_to(op_state.active[0], _mdk_act0)
        _meowth_antidonk_now = (
            _mdk_hit0 > 0 and _mdk_hp0 > 0 and _mdk_hit0 >= _mdk_hp0)

    _bench_attacker_ready = False
    for _bp in (my_state.bench or []):
        if _bp is None:
            continue
        _bp_e = len(_bp.energies)
        _bp_eff = _bp_e * _grass_mult()
        if _bp.id == Hydrapple_ex and _bp_eff >= 2:
            _bench_attacker_ready = True
            break
        if _bp.id == Teal_Mask_Ogerpon_ex and _bp_eff >= 3:
            _bench_attacker_ready = True
            break
        if _bp.id == Dipplin and _bp_e >= 1:
            _bench_attacker_ready = True
            break
        if _bp.id == Tapu_Bulu and _bp_eff >= 4:
            _bench_attacker_ready = True
            break
        if _bp.id == Pinsir and _bp_eff >= 2:
            _bench_attacker_ready = True
            break
        if _bp.id == Meganium and _bp_eff >= 4:
            _bench_attacker_ready = True
            break

    _bench_attacker_needs_energy = False
    for _bp in (my_state.bench or []):
        if _bp is None:
            continue
        _bp_e = len(_bp.energies)
        _bp_eff = _bp_e * _grass_mult()
        if _bp.id == Hydrapple_ex and _bp_eff < 2:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Teal_Mask_Ogerpon_ex and _bp_eff < 3:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Dipplin and _bp_e < 1:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Tapu_Bulu and _bp_eff < 4:
            _bench_attacker_needs_energy = True
            break

    _op_active_hp = 0
    _op_active_weakness_grass = False
    _op_active_resistance_grass = False
    if op_state.active and op_state.active[0] is not None:
        _op_active_hp = op_state.active[0].hp
        _op_data = card_table.get(op_state.active[0].id)
        if _op_data and _op_data.weakness == EnergyType.GRASS:
            _op_active_weakness_grass = True
        # Resistencia a Grass (p.ej. Archaludon ex): el motor resta 30 de dano
        # (ver _our_effective_damage). Debe restarse aqui para no sobreestimar
        # el Syrup Storm y creer que ya hacemos KO cuando faltan 30.
        if _op_data and _op_data.resistance == EnergyType.GRASS:
            _op_active_resistance_grass = True

    _active_hydra_cannot_ko = False
    if _active_hydra_capped and _op_active_hp > 0:
        _syrup_dmg_now = 30 + 30 * total_grass
        if _op_active_weakness_grass:
            _syrup_dmg_now *= 2
        elif _op_active_resistance_grass:
            _syrup_dmg_now = max(0, _syrup_dmg_now - 30)
        _active_hydra_cannot_ko = (_syrup_dmg_now < _op_active_hp)

    def _extra_energy_enables_ko(pokemon_id: int, current_energy: int) -> bool:
        if _op_active_hp <= 0:
            return False
        if not (op_state.active and op_state.active[0] is not None):
            return False
        _mult = _grass_attach_unit()
        _op_act = op_state.active[0]

        # Evaluador CENTRAL (P0.1): la copia inline solo aplicaba debilidad/
        # resistencia; contra Drednaw (anula >=200), Sturdy/Resolute Heart o
        # Crustle (inmune a ex) creia que una energia extra "habilitaba" un KO
        # inexistente y desperdiciaba la carga.
        def _eff(_base):
            return _our_effective_damage(
                _ProjTarget(pokemon_id), _op_act, _base,
                ESTADO.meganium_in_play, neutralization_zone_active)

        if pokemon_id == Hydrapple_ex:
            _dmg_now = _eff(30 + 30 * total_grass)
            _dmg_extra = _eff(30 + 30 * (total_grass + _mult))
            return _dmg_now < _op_active_hp <= _dmg_extra

        if pokemon_id == Teal_Mask_Ogerpon_ex:
            _op_e = len(_op_act.energies)
            _my_eff = current_energy
            _dmg_now = _eff(30 + 30 * (_my_eff + _op_e))
            _dmg_extra = _eff(30 + 30 * (_my_eff + _mult + _op_e))
            return _dmg_now < _op_active_hp <= _dmg_extra

        return False

    _active_already_kos = False
    if _active_pokemon is not None and _op_active_hp > 0:

        _ak_eff = len(_active_pokemon.energies)
        _ak_dmg = 0
        if _active_pokemon.id == Teal_Mask_Ogerpon_ex and _ak_eff >= 3:
            _ak_op_e = (len(op_state.active[0].energies)
                        if (op_state.active and op_state.active[0] is not None) else 0)
            # Myriad cuenta la energia de AMBOS activos (_ak_op_e se computaba
            # y NO se usaba -- mismo bug que la copia inline del ATAQUE).
            _ak_dmg = 30 + 30 * (_ak_eff + _ak_op_e)
        elif _active_pokemon.id == Hydrapple_ex and _ak_eff >= 2:
            _ak_dmg = 30 + 30 * total_grass
        elif _active_pokemon.id == Tapu_Bulu and _ak_eff >= 4:
            _ak_dmg = 220
        elif _active_pokemon.id == Meganium and _ak_eff >= 4:
            _ak_dmg = 140
        elif _active_pokemon.id == Fezandipiti_ex and _ak_eff >= 3:
            # Cruel Arrow: 100 de dano FIJO (tipo Oscuridad, no Planta) a
            # cualquier Pokemon. Cuenta como KO del activo rival para habilitar
            # la carga del atacante futuro (Tapu Bulu). No aplica la debilidad /
            # resistencia a Planta porque no es dano de Planta
            # (_our_effective_damage lo sabe via `is_fez`).
            _ak_dmg = 100
        # Evaluador CENTRAL (P0.1): la copia inline solo aplicaba debilidad/
        # resistencia, asi que `_active_already_kos` podia declarar un KO falso
        # vs Crustle (inmune a ex), Drednaw (anula >=200), Sturdy/Resolute
        # Heart (sobreviven a 10) o Cornerstone. `_our_effective_damage` ya
        # salta la debilidad para Fezandipiti (dano fijo), cubriendo
        # `_ak_is_grass`.
        if _ak_dmg > 0 and op_state.active and op_state.active[0] is not None:
            _ak_dmg = _our_effective_damage(
                _active_pokemon, op_state.active[0], _ak_dmg,
                ESTADO.meganium_in_play, neutralization_zone_active)
        _active_already_kos = (_ak_dmg >= _op_active_hp)

    # --- SNIPE DEL ACTIVO: el mejor objetivo no siempre es el activo rival ----
    # (user, registro_004 paso 54 vs Alakazam.) Cruel Arrow de Fezandipiti ex
    # golpea a CUALQUIER Pokemon del rival por 100 fijos. `_active_already_kos`
    # y `_active_can_ko_now` (scorer de retirada) solo miran al ACTIVO rival, asi
    # que con el Alakazam de 140 PV delante el turno parecia esteril: el agente
    # retiro al Fezandipiti (pagando su energia) para promover un Ogerpon que ni
    # siquiera podia atacar, y paso -- con un Kadabra de 80 PV noqueable en la
    # banca rival. Aqui se resuelve UNA vez el mejor objetivo del snipe (activo o
    # banca) y el resultado alimenta al planificador de retirada/ataque y a la
    # seleccion real del objetivo en el menu de DAMAGE.
    _snipe_target, _snipe_dmg, _snipe_is_ko = (None, 0, False)
    if _active_pokemon is not None:
        _snipe_target, _snipe_dmg, _snipe_is_ko = _snipe_best_target(
            _active_pokemon, op_state,
            len(_active_pokemon.energies) * _grass_mult(),
            ESTADO.meganium_in_play, neutralization_zone_active,
            bench_count=bench_count, grass_scale=total_grass)
    # El KO por snipe solo cuenta como jugada REAL de este turno si de verdad
    # podemos atacar (y la confusion no lo convierte en una moneda).
    #
    # `plan.attacker <= 0` (el activo, o ningun plan) es OBLIGATORIO y evita un
    # bloqueo mutuo: con `plan.attacker >= 1` el planificador ya prefirio retirar
    # y atacar con un cuerpo de banca, y el scorer de ATTACK veta el ataque del
    # activo justo por eso. Si ademas dejaramos que el snipe vetara la RETIRADA
    # (via `_active_can_ko_now`) no quedaria ninguna jugada viva y el turno se
    # cerraria en blanco -- peor que las dos alternativas. Cuando el plan si
    # apunta al activo, ambos lados coinciden y el snipe manda.
    _active_snipe_ko_now = bool(_snipe_is_ko and can_attack and not is_confused
                                and ESTADO.plan.attacker <= 0)
    _active_snipe_ko_prizes = (prize_count_op(_snipe_target)
                               if _active_snipe_ko_now else 0)

    # ¿El ataque del ACTIVO este turno GANA la partida? (user, registro_009 paso
    # 125 vs Archaludon ex, PERDIDA): nuestro Ogerpon ex con Meganium en juego
    # (Wild Growth duplica cada Planta) hacia Myriad 30+30x(8 efectivas + 3 del
    # rival) = 360, menos 30 de resistencia a Planta = 330 >= 300 -> NOQUEA al
    # Archaludon ex (2 premios) y con 2 premios restantes GANA. El agente, en
    # vez de ATACAR, cargaba energia a Tapu Bulu (`_tapu_future_charge`, 40000) y
    # luego retiraba al Ogerpon para atacar con Tapu -- tirando el remate. Cuando
    # el KO del activo GANA la partida (mis premios restantes <= premios que da
    # el KO), ATACAR es la jugada de MAXIMA prioridad: nada mas importa. El
    # calculo de dano (con Meganium, energia rival y resistencia) ya es correcto
    # via `_active_already_kos`; lo que faltaba era priorizar el remate.
    # El KO del activo rival GANA la partida en DOS casos: (a) nos da los premios
    # que faltan (my_prize <= premios del objetivo), o (b) el rival NO tiene mas
    # Pokemon en juego -- banca VACIA -- y por tanto no puede promover un nuevo
    # activo tras el KO (regla del juego: sin Pokemon para reemplazar el activo
    # noqueado, PIERDE). El caso (b) faltaba (user, registro_016 paso 138 vs
    # Crustle, GANADA con jugada suboptima): con Ogerpon activo LETAL (Myriad 150
    # >= 110) y el rival con SOLO su activo Munkidori (1 premio, banca vacia),
    # noquearlo GANA aunque my_prize (2) > premios del objetivo (1). El agente,
    # sin detectar el remate, RETIRABA el Ogerpon para atacar con un 1-premio
    # (Dipplin) -- tirando la victoria inmediata. ATACAR es la maxima prioridad.
    # `_op_bench_empty` se computo antes (junto a op_cards).
    #
    # --- REMATE SUICIDA: el KO que EMPATA (o REGALA) en vez de ganar --------
    # (user, registro_016 paso 184 vs Marnie's Grimmsnarl, EMPATE.) Nuestro Tapu
    # Bulu ACTIVO, a 20/140 PV y cargado, remataba al Impidimp rival (Wood Hammer
    # 220 >= 70) con UN premio restante para cada lado, asi que el agente marco
    # `_active_attack_wins_now` y ataco con prioridad absoluta (99000). Pero Wood
    # Hammer "also does 30 damage to itself": el propio ataque NOQUEO a Tapu Bulu,
    # el rival cobro SU ultimo premio en el mismo instante y la partida acabo 0-0,
    # EMPATE. En la banca esperaba un Teal Mask Ogerpon ex con 6 energias: retirar
    # (coste 3) y rematar con Myriad Leaf Shower (30+30x6 = 210 >= 70) GANABA
    # limpio -- verificado contra el simulador real (result 0 = victoria) frente
    # al result 2 (empate) de la linea que jugo el agente.
    #
    # Al agente le faltaban DOS datos, ninguno deducible del dano infligido:
    #   1. el AUTO-DANO del ataque (ahora `_attack_self_damage`, leido del texto
    #      de la carta), y
    #   2. que el KO de NUESTRO propio cuerpo tambien PAGA PREMIOS: con el rival
    #      a `op_prize` premios, dejarle un cadaver de `prize_count` >= op_prize
    #      le cierra la cuenta a el TAMBIEN.
    # De ahi los tres estados del remate suicida:
    #   * `_suicide_hands_op_win`: el rival llega a 0 con nuestro cadaver.
    #   * `_suicide_only_draws`  : ademas NUESTRO KO gana -> EMPATE, no victoria.
    #   * `_suicide_loses`       : el rival llega a 0 y nosotros NO -> DERROTA.
    # El auto-dano se mide con el peor caso (`incierto=True`): un remate que
    # PUEDE matarnos y cerrarle la cuenta al rival no merece prioridad absoluta.
    _active_self_ko_now = (
        _active_pokemon is not None
        and can_attack
        and not is_confused
        and _self_ko_by_own_attack(_active_pokemon, incierto=True))
    _active_self_ko_prizes = (prize_count(_active_pokemon)
                              if _active_self_ko_now else 0)
    _suicide_hands_op_win = (_active_self_ko_now
                             and op_prize <= _active_self_ko_prizes)

    _active_attack_wins_now = (
        _active_already_kos
        and can_attack
        and not is_confused
        and op_state.active and op_state.active[0] is not None
        # KO GARANTIZADO (P0.1): vs Tenacious Body/Survival Brace el "remate"
        # puede fallar la moneda; no se le da prioridad absoluta de victoria.
        and not _ko_no_garantizado(op_state.active[0])
        # El remate que nos MATA y le cierra la cuenta al rival NO gana: empata
        # (los dos KOs son simultaneos y cada uno cobra su ultimo premio).
        and not _suicide_hands_op_win
        and (my_prize <= prize_count_op(op_state.active[0])
             or _op_bench_empty))

    # El SNIPE tambien puede cerrar la partida: si Cruel Arrow noquea a un cuerpo
    # de la BANCA rival cuyos premios nos bastan, atacar GANA igual que el remate
    # sobre el activo, y merece la misma prioridad absoluta (score y tier). El
    # caso "banca rival vacia" no aplica aqui: el rival solo pierde por no poder
    # reemplazar a su ACTIVO, y este KO no lo toca.
    _snipe_attack_wins_now = (
        _active_snipe_ko_now
        and _snipe_target is not None
        and not _ko_no_garantizado(_snipe_target)
        and not _suicide_hands_op_win
        and my_prize <= _active_snipe_ko_prizes)
    if _snipe_attack_wins_now:
        _active_attack_wins_now = True

    # El remate suicida EMPATA si nuestro KO tambien cerraba la cuenta; si no,
    # directamente REGALA la partida (nos matamos por nada).
    _suicide_ko_would_win = (
        _suicide_hands_op_win
        and _active_already_kos
        and op_state.active and op_state.active[0] is not None
        and not _ko_no_garantizado(op_state.active[0])
        and (my_prize <= prize_count_op(op_state.active[0])
             or _op_bench_empty))
    _suicide_only_draws = _suicide_hands_op_win and _suicide_ko_would_win
    _suicide_loses = _suicide_hands_op_win and not _suicide_ko_would_win

    # RELEVO DEL SUICIDA: atacante de BANCA que, promovido tras retirar, gana la
    # partida LIMPIO (noquea, cobra los premios que faltan y NO se suicida).
    # Mide el dano con el Grass que quedara DESPUES de pagar la retirada (el
    # coste descarta cartas enteras del activo: mismo cuidado que
    # `_hlp_grass_after`), porque Syrup Storm escala con el Grass del CAMPO.
    _suicide_swap_winner = None
    if (_suicide_hands_op_win and can_switch and _active_pokemon is not None
            and op_state.active and op_state.active[0] is not None
            and not _ko_no_garantizado(op_state.active[0])):
        _ssw_opa = op_state.active[0]
        _ssw_opa_hp = _ssw_opa.hp or 0
        _ssw_gana_premios = (my_prize <= prize_count_op(_ssw_opa)
                             or _op_bench_empty)
        _ssw_grass_after = max(
            0, total_grass - (0 if has_switch_card else _retreat_grass_units(
                RETREAT_COST.get(_active_pokemon.id, 1))))
        if _ssw_gana_premios and _ssw_opa_hp > 0:
            for _ssw_bp in (my_state.bench or []):
                if _ssw_bp is None or not isinstance(_ssw_bp, Pokemon):
                    continue
                _ssw_e = len(_ssw_bp.energies)
                if not _can_attack_eff(_ssw_bp.id, _ssw_e):
                    continue  # no ataca hoy con la energia que ya tiene
                # El relevo no puede repetir el problema: si el, al atacar,
                # tambien se suicida y con ello el rival llega a 0, no sirve.
                if (_self_ko_by_own_attack(_ssw_bp, incierto=True)
                        and op_prize <= prize_count(_ssw_bp)):
                    continue
                _ssw_base = _attacker_base_damage(
                    _ssw_bp.id, _ssw_opa, _ssw_e * _grass_mult(),
                    grass_scale=_ssw_grass_after, teal_self_energy=_ssw_e,
                    bench_count=bench_count)
                if _ssw_base <= 0:
                    continue
                if _our_effective_damage(
                        _ssw_bp, _ssw_opa, _ssw_base, ESTADO.meganium_in_play,
                        neutralization_zone_active) >= _ssw_opa_hp:
                    _suicide_swap_winner = _ssw_bp
                    break

    # Retirar para dar paso al relevo: es la jugada que convierte el empate (o la
    # derrota) en victoria, asi que manda por encima de todo lo demas.
    _suicide_swap_win_promote = (_suicide_swap_winner is not None)

    # Syrup Storm cuenta la Planta de TODOS nuestros Pokemon, no solo la del
    # atacante: con el Hydrapple ex ACTIVO ya listo para atacar, UNA Planta mas
    # EN CUALQUIER SITIO (Teal Dance en un Ogerpon de banca, Ripening Charge en
    # quien sea) puede convertir un ataque corto en el KO. User, registro_006
    # paso 68 vs Mega Abomasnow ex (PERDIDA): 30+30x10 = 330 contra 350 PV, y
    # con una Planta mas 390 -> KO de 3 premios. `_extra_energy_enables_ko` ya
    # hace la cuenta (rama Hydrapple_ex, con debilidad/resistencia e
    # inmunidades); lo que faltaba era que las HABILIDADES de carga la
    # consultasen aunque su propio portador no gane nada con la energia.
    _grass_anywhere_enables_syrup_ko = False
    if (_active_pokemon is not None
            and _active_pokemon.id == Hydrapple_ex
            and not _active_already_kos
            and can_attack and not is_confused
            and len(_active_pokemon.energies) * _grass_mult() >= 2
            and _extra_energy_enables_ko(Hydrapple_ex,
                                         len(_active_pokemon.energies))):
        _grass_anywhere_enables_syrup_ko = True

    # --- ATACAR CON EL ACTIVO ES LO PRIMERO ------------------------------
    # (user, episodio 88433181 registro_006 paso 67 vs Marnie's Grimmsnarl,
    # GANADA con error): turno 6 con el Hydrapple ex ACTIVO recien evolucionado
    # a 0 energias, TRES Plantas en mano, el adjunte manual sin gastar y DOS
    # habilidades de carga vivas -- y el activo rival (Munkidori) a 10 PV. La
    # linea correcta era trivial: adjuntar 1 Planta al ACTIVO + Ripening Charge
    # sobre el ACTIVO = 2 efectivas = Syrup Storm (180) = KO. En vez de eso el
    # agente cargo al Hydrapple de BANCA y mando las dos habilidades a un
    # Ogerpon de banca: turno ESTERIL, sin atacar, con el KO servido.
    #
    # Causa raiz (deck-agnostica): existia toda una familia de reglas para
    # cargar a un atacante de BANCA y promoverlo (41000), pero NINGUNA que
    # preguntase lo primero de todo -- "¿puede ATACAR el activo este turno si
    # le llevo la energia que aun puedo mover?" --. Las cargas al activo vivian
    # en la banda de desarrollo (~31200), por debajo de cualquier plan de banca.
    # Ademas ese plan de banca era IMPOSIBLE: promoverlo exigia retirar al
    # Hydrapple activo (coste 3) con 0 energias encima.
    #
    # Lo que se mide aqui es el PRESUPUESTO REAL de energia que todavia puede
    # aterrizar EN EL ACTIVO este turno: adjunte manual (si no se gasto) mas las
    # habilidades de carga que pueden apuntarle (`_grass_ability_slots_activo`),
    # limitado por las Plantas de la mano. Si con ese presupuesto el activo
    # alcanza su coste de ataque y el ataque hace dano, la carga va al ACTIVO.
    # Nada de esto depende del rival ni del mazo propio: el coste sale de
    # ATTACK_ENERGY_REQ (con `_coste_de_ataque_min` como respaldo derivado del
    # dato de carta) y el dano de los evaluadores centrales.
    _carga_activo_falta = 0        # unidades de carga que aun faltan
    _carga_activo_remata = False   # ...y el ataque resultante NOQUEA
    _carga_activo_habilita_ataque = False  # ...solo hace chip, pero hoy no hay otro ataque
    _cav_op_act = _active_of(op_state)
    # OJO: NO se usa `can_attack` como guarda -- ese flag solo dice si el juego
    # ofrece YA la opcion ATTACK, y por definicion aqui el activo todavia no
    # llega a su coste (es lo que venimos a arreglar). La guarda correcta es que
    # nada IMPIDA atacar: dormido/paralizado (`condition_blocks_action`) o
    # confuso (la moneda hace el remate no fiable; lo cubre la maquinaria de
    # confusion).
    if (_active_pokemon is not None and _cav_op_act is not None
            and not condition_blocks_action and not is_confused
            and not _active_already_kos
            and _op_active_hp > 0
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _cav_req = ESTADO.ATTACK_ENERGY_REQ.get(_active_pokemon.id)
        if _cav_req is None:
            _cav_req = _coste_de_ataque_min(_active_pokemon.id)
        _cav_e = len(_active_pokemon.energies)
        if _cav_req is not None and _cav_e < _cav_req:
            _cav_unit = _grass_attach_unit()
            # Cargas que aun pueden aterrizar en el ACTIVO, limitadas por mano.
            _cav_rutas = ((0 if state.energyAttached else 1)
                          + _grass_ability_slots_activo(state, my_state, field_counts))
            _cav_disp = min(hand_counts.get(Basic_Grass_Energy, 0), _cav_rutas)
            # Plantas necesarias para llegar al coste (redondeo hacia arriba).
            _cav_need = -(-(_cav_req - _cav_e) // _cav_unit)
            if 1 <= _cav_need <= _cav_disp:
                _cav_e_after = _cav_e + _cav_need * _cav_unit
                _cav_base = _attacker_base_damage(
                    _active_pokemon.id, _cav_op_act, _cav_e_after,
                    grass_scale=total_grass + _cav_need * _cav_unit,
                    teal_self_energy=_cav_e_after, bench_count=bench_count)
                _cav_dmg = _our_effective_damage(
                    _active_pokemon, _cav_op_act, _cav_base,
                    ESTADO.meganium_in_play, neutralization_zone_active)
                if _cav_dmg > 0:
                    _carga_activo_falta = _cav_need
                    if (_cav_dmg >= _op_active_hp
                            and not _ko_no_garantizado(_cav_op_act)
                            # ...salvo que YA exista un KO mas BARATO: un
                            # atacante de banca ya cargado al que solo le falta
                            # que paguemos la retirada del activo
                            # (`_attach_enable_retreat_ko` /
                            # `_ability_unlock_retreat_ko`). Esa linea cobra el
                            # mismo premio gastando UNA Planta -- y ademas pone a
                            # salvo al activo -- mientras que cargar al activo
                            # hasta su coste puede costar dos o tres. El KO mas
                            # barato manda (user, registro_014 paso 136 vs
                            # Alakazam: Fezandipiti ex activo a 0 energias con el
                            # Hydrapple ex de banca YA listo).
                            and not _attach_enable_retreat_ko
                            and not _ability_unlock_retreat_ko):
                        _carga_activo_remata = True
                    elif (not (_bench_attacker_ready and can_switch)
                            and not op_is_cubchoo_deck):
                        # Sin KO la carga solo se prioriza cuando NO hay otro
                        # cuerpo que vaya a atacar hoy (un atacante de banca ya
                        # listo y promovible manda: esa linea la resuelve la
                        # maquinaria de retirada). El chip del activo vale
                        # infinitamente mas que cerrar el turno sin atacar.
                        # Excluido el matchup Cubchoo: alli el rival BLOQUEA el
                        # ataque de nuestro activo cada turno (Snotted Up), asi
                        # que la energia se reserva en mano para pagar retiradas
                        # (regla del usuario, [[anti-cubchoo-...]]). El remate
                        # (arriba) si se permite: un premio vale la apuesta.
                        _carga_activo_habilita_ataque = True

    # Variante con el rematador todavia en BANCA: retirar el activo lo promueve
    # y el coste de la retirada BAJA el recuento de Planta, asi que la Planta
    # extra puede ser justo la que devuelve el KO (user, registro_006 paso 78 vs
    # Archaludon ex). Sirve para que el FETCH de la Night Stretcher elija la
    # ENERGIA (y no una pieza de desarrollo) cuando esa es la linea del remate.
    _grass_enables_promote_ko = False
    _gep_op = _active_of(op_state)
    if (_active_pokemon is not None and _gep_op is not None
            and (_gep_op.hp or 0) > 0 and can_switch):
        _gep_rc = RETREAT_COST.get(_active_pokemon.id, 1)
        if len(_active_pokemon.energies) >= _gep_rc:
            _gep_after = max(0, total_grass - _retreat_grass_units(_gep_rc))

            def _gep_ko(_g):
                return _bench_attacker_can_ko(
                    my_state, _gep_op, ESTADO.meganium_in_play, total_grass,
                    bench_count, _g, neutralization_zone_active)
            _grass_enables_promote_ko = (
                _gep_ko(_gep_after + _grass_attach_unit())
                and not _gep_ko(_gep_after))

    # KO LETAL de Ogerpon por DOBLE carga en un turno (user, log 85803267 turno
    # 4): Myriad Leaf Shower ({G}{G}{G}) hace 30 + 30 por cada energia en AMBOS
    # activos. Si el activo es Teal Mask Ogerpon ex y este turno podemos sumarle
    # DOS energias (adjunte MANUAL + Teal Dance, que adjunta 1 Planta y ademas
    # roba), puede alcanzar las 3 energias necesarias y un dano LETAL (x2 si el
    # rival es debil a Planta, p.ej. Marnie's Grimmsnarl ex 320 HP -> con 3
    # energias y 2 del rival: (30+30*5)*2 = 360 >= 320). El scorer codicioso solo
    # mira +1 energia por opcion, asi que ni `_active_already_kos` ni
    # `_extra_energy_enables_ko` (que solo cuentan +1) detectan este letal de +2;
    # esta bandera evita que se penalice/despriorice cargar el ACTIVO.
    _ogerpon_td_manual_lethal = False
    if (_active_pokemon is not None
            and _active_pokemon.id == Teal_Mask_Ogerpon_ex
            and not state.energyAttached
            and _op_active_hp > 0
            and not _active_already_kos
            and hand_counts.get(Basic_Grass_Energy, 0) >= 2):
        _td_avail_lethal = any(
            o.type == OptionType.ABILITY and o.area == AreaType.ACTIVE
            for o in select.option)
        if _td_avail_lethal:
            _otml_unit = _grass_attach_unit()
            _otml_op_e = (len(op_state.active[0].energies)
                          if (op_state.active and op_state.active[0] is not None)
                          else 0)
            _otml_e_after = len(_active_pokemon.energies) + 2 * _otml_unit
            # Myriad cuenta la energia de AMBOS activos (_otml_op_e existia
            # sin usarse).
            _otml_dmg = 30 + 30 * (_otml_e_after + _otml_op_e)
            # Evaluador CENTRAL (P0.1): ademas de debilidad/resistencia aplica
            # Drednaw, Sturdy/Resolute Heart e inmunidades a ex.
            if op_state.active and op_state.active[0] is not None:
                _otml_dmg = _our_effective_damage(
                    _active_pokemon, op_state.active[0], _otml_dmg,
                    ESTADO.meganium_in_play, neutralization_zone_active)
            if _otml_e_after >= 3 and _otml_dmg >= _op_active_hp:
                _ogerpon_td_manual_lethal = True

    op_active_is_kangaskhan = bool(
        op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Mega_Kangaskhan_ex)

    op_kang_ko_target = False
    if op_active_is_kangaskhan and _op_active_hp > 0:
        _mult_kk = _grass_attach_unit()

        _kk_grass_max = total_grass
        if not state.energyAttached and hand_counts.get(Basic_Grass_Energy, 0) >= 1:
            _kk_grass_max += _mult_kk
        _syrup_max_kk = 30 + 30 * _kk_grass_max

        _hydra_in_play = field_counts.get(Hydrapple_ex, 0) >= 1
        _dipplin_evolvable = (field_counts.get(Dipplin, 0) >= 1
                              or hand_counts.get(Dipplin, 0) >= 1)
        _hydra_reachable = (
            hand_counts.get(Hydrapple_ex, 0) >= 1
            or (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Hydrapple_ex, 0) >= 1))

        _hydra_line_available = (
            _hydra_in_play
            or (_dipplin_evolvable and _hydra_reachable))

        if _hydra_line_available and _syrup_max_kk >= _op_active_hp:
            op_kang_ko_target = True

    # NUEVA REGLA (preparar atacante futuro): si Meganium y Tapu Bulu estan en
    # juego y el activo YA asegura el KO al activo rival, cargamos energia en
    # Tapu Bulu (banca) para dejarlo listo como atacante del proximo turno. Con
    # Meganium cada energia basica cuenta como {G}{G}, asi que 2 energias
    # fisicas = 4 efectivas = Tapu Bulu listo para atacar (220). Ademas de la
    # adjuncion manual, aprovechamos la habilidad Ripening Charge de Hydrapple
    # ex (que adjunta a CUALQUIER Pokemon) para poner la 2a energia. Solo aplica
    # fuera de los matchups especiales, que ya tienen su propia logica.
    _tapu_bench_future = None
    for _bp_tf in (my_state.bench or []):
        if _bp_tf is not None and _bp_tf.id == Tapu_Bulu:
            _tapu_bench_future = _bp_tf
            break
    _tapu_future_charge = (
        ESTADO.meganium_in_play
        and _active_already_kos
        and not _active_attack_wins_now
        and _tapu_bench_future is not None
        and len(_tapu_bench_future.energies) * _grass_mult() < 4
        and not ESTADO.op_is_crustle_deck
        and not ESTADO.op_is_cornerstone_deck
        and not neutralization_zone_active)

    # SEGUNDO ATACANTE por habilidad (user, registro_014 paso 137 vs Alakazam):
    # ¿UNA Planta mas deja LISTO a un atacante REAL de banca que ahora no llega a
    # su coste? Solo `MAIN_ATTACKERS` (nunca un Applin/Chikorita, que "atacan"
    # por 0-10) y solo si de verdad cruza el umbral: es el destino util que le
    # faltaba a Ripening Charge cuando el Hydrapple ya llega a su propio ataque.
    # Solo cuando el adjunte MANUAL ya se gasto (`state.energyAttached`): ahi la
    # habilidad es la UNICA ruta que queda y vetarla deja la Planta muerta en la
    # mano (acaba de forraje en el coste de una Ultra Ball). Mientras el adjunte
    # manual siga libre, el ruteo normal de energia ya coloca la Planta y no hay
    # que tocar esa decision (pinada por los tests de Meganium futuro y de
    # Ripening/curacion).
    _ripen_bench_ready_pivot = False
    if (state.energyAttached
            and not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck
            and not neutralization_zone_active):
        for _rbr_bp in (my_state.bench or []):
            if _rbr_bp is None or _rbr_bp.id not in MAIN_ATTACKERS:
                continue
            _rbr_eff = len(_rbr_bp.energies) * _grass_mult()
            if (not _can_attack_eff(_rbr_bp.id, _rbr_eff)
                    and _can_attack_eff(_rbr_bp.id,
                                        _rbr_eff + _grass_attach_unit())):
                _ripen_bench_ready_pivot = True
                break

    # NUEVA REGLA (user, registro_008 paso 108 vs Alakazam, GANADA con jugada
    # suboptima): vs Alakazam, Meganium es un EXCELENTE atacante de UN premio
    # (140 de dano derrota a Alakazam 743 y su linea Kadabra/Abra). Cuando el
    # activo YA asegura su KO este turno (no le robamos energia a un ataque
    # necesario) y en la banca hay un Meganium PARCIALMENTE cargado (0 <
    # efectivas < 4, le falta 1 carta de Planta para su Wood Hammer coste 4,
    # que con Wild Growth = 2 fisicas), cargamos ese Meganium para dejarlo LISTO
    # como atacante de 1 premio del proximo turno -- en vez de desperdiciar la
    # energia (adjunte manual) o ceder el ataque sin cargarlo. La prioridad
    # sigue siendo los atacantes principales (Ogerpon/Applin/Dipplin/Hydrapple/
    # Tapu Bulu): el score de Meganium (25000) queda por DEBAJO de sus cargas
    # (26000-40000), asi que solo gana cuando ellos ya no necesitan la energia.
    # Reusada por el adjunte manual (OptionType.ATTACH) y por el objetivo de
    # Ripening Charge (SelectContext.ATTACH_FROM), ambos via energy_score. El
    # Meganium a 0 energias ya lo cubre la rama de banca a 0 (27000).
    _meganium_bench_future = None
    for _bp_mf in (my_state.bench or []):
        if _bp_mf is not None and _bp_mf.id == Meganium:
            _meganium_bench_future = _bp_mf
            break
    _meganium_alk_future_charge = (
        op_is_alakazam_deck
        and _active_already_kos
        and not _active_attack_wins_now
        and _meganium_bench_future is not None
        and 0 < len(_meganium_bench_future.energies) * _grass_mult() < 4
        and not ESTADO.op_is_crustle_deck
        and not ESTADO.op_is_cornerstone_deck
        and not neutralization_zone_active)

    # NUEVA REGLA (ex atascado vs muro inmune): cuando nuestro ACTIVO es un ex
    # que el activo rival BLOQUEA (Crustle inmuniza a nuestros ex; Cornerstone
    # a nuestros Pokemon con habilidad) no hace dano, asi que conviene retirarlo
    # y promover un atacante que SI golpee al muro (el que pega mas fuerte se
    # elige al promover via `_best_promote_card`). Para poder retirar, primero
    # hay que cargar el ex hasta su coste de retirada. `_ex_stuck_promo_ready` =
    # nuestro activo esta bloqueado por el muro Y hay en banca un atacante NO
    # bloqueado y LISTO para golpear al muro este turno.
    _op_wall_active = None
    if op_has_ex_immune_active or op_has_ability_immune_active:
        _op_wall_active = _active_of(op_state)

    def _dmg_vs_wall(_p):
        # Dano efectivo de _p contra el activo rival inmune; 0 si esta bloqueado
        # por la inmunidad o si no puede atacar este turno.
        if _p is None or _op_wall_active is None:
            return 0
        if op_has_ex_immune_active and _p.id in OUR_EX_IDS:
            return 0
        if op_has_ability_immune_active and _p.id in OUR_ABILITY_IDS:
            return 0
        _e = len(_p.energies)
        _eff = _e * _grass_mult()
        # Dano base crudo (sin debilidad/resistencia: es el golpe directo contra
        # el muro) via la tabla unica _attacker_base_damage.
        return _attacker_base_damage(_p.id, _op_wall_active, _eff,
                                     grass_scale=total_grass,
                                     teal_self_energy=_e,
                                     bench_count=bench_count)

    _my_active_pk = (my_state.active[0]
                     if (my_state.active and my_state.active[0] is not None)
                     else None)
    _active_blocked_by_wall = (
        _op_wall_active is not None and _my_active_pk is not None
        and ((op_has_ex_immune_active and _my_active_pk.id in OUR_EX_IDS)
             or (op_has_ability_immune_active and _my_active_pk.id in OUR_ABILITY_IDS)))
    _wall_bench_attacker_ready = any(
        _dmg_vs_wall(_bp) > 0 for _bp in (my_state.bench or []))

    # ATACANTE de 1 PREMIO vs Alakazam ESTE TURNO (user, registro_008 paso ~112
    # vs Alakazam, PERDIDA): vs Alakazam SIEMPRE debemos noquear con un cuerpo de
    # 1 PREMIO cuando se pueda. Si el ACTIVO es un ex NUESTRO (2 premios) y en la
    # banca hay un Meganium a UNA Planta de su coste de ataque (Wood Hammer 4 ef;
    # Wild Growth duplica cada Planta fisica) cuyo dano (140) NOQUEA al activo
    # rival, la carga (adjunte manual) debe ir al MEGANIUM -- no al ex activo --
    # para dejarlo LISTO y atacar ESTE turno con el 1-premio: se retira el ex y se
    # promueve Meganium (la logica de retirada ya lo hace cuando Meganium esta
    # LISTO; se verifico que con Meganium a 4 ef el agente retira el ex y promueve
    # el 1-premio). Cedemos 1 premio en vez de 2 y el ex-tanque se resguarda. A
    # diferencia de `_meganium_alk_future_charge` (25000, prepara a Meganium para
    # el PROXIMO turno manteniendo al ex como atacante de ESTE), aqui Meganium
    # ATACA este turno, por lo que domina la carga del ex activo. Solo cuando 1
    # Planta basta (2 <= ef < 4) y Meganium NOQUEA; si atacar con el ex ya GANA la
    # partida no aplica (no hay turno futuro que proteger). Deck-gated (Alakazam),
    # sin fuga a otros matchups.
    # GUARDA (user, registro_014 paso 136 vs Alakazam): toda la regla se apoya en
    # "se retira el ex y se promueve Meganium", asi que solo vale si la RETIRADA
    # es legal este turno (`can_switch`). Con el Fezandipiti ex activo a 0
    # energias (coste 1) el Meganium cargado se quedaba en la banca sin atacar y
    # este 43000 pisaba al adjunte que SI habilitaba la jugada: la Planta al
    # ACTIVO para pagar la retirada y subir al Hydrapple ex listo
    # (`_attach_enable_retreat_ko`, 41000). Si la retirada no es legal, Meganium
    # no ataca hoy: su carga decae al tier FUTURO (25000) y la energia se rutea
    # a desbloquear el turno.
    _meganium_alk_1prize_attacker = False
    if (op_is_alakazam_deck
            and can_switch
            and not _active_attack_wins_now
            and not _win_via_boss_gust
            and _my_active_pk is not None and _my_active_pk.id in OUR_EX_IDS
            and _meganium_bench_future is not None
            and op_state.active and op_state.active[0] is not None
            and not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck
            and not neutralization_zone_active):
        _malk_eff = len(_meganium_bench_future.energies) * _grass_mult()
        _malk_unit = _grass_attach_unit()
        if _malk_eff < 4 and _malk_eff + _malk_unit >= 4:
            _malk_opa = op_state.active[0]
            _malk_base = _attacker_base_damage(
                Meganium, _malk_opa, 4, grass_scale=total_grass,
                teal_self_energy=4, bench_count=bench_count)
            _malk_dmg = _our_effective_damage(
                _meganium_bench_future, _malk_opa, _malk_base,
                ESTADO.meganium_in_play, neutralization_zone_active)
            if _malk_dmg > 0 and _malk_dmg >= (_malk_opa.hp or 0):
                _meganium_alk_1prize_attacker = True

    # Regla (user, log 86174943 turno 22, vs Crustle, PERDIDA): si nuestro
    # activo es un Teal Mask Ogerpon ex LISTO para atacar (>=3 efectivas) y este
    # turno podemos jugar Boss's Orders para SUBIR un Mega Kangaskhan ex de la
    # banca rival, NO retiramos a Ogerpon para promover a Dipplin. El Kangaskhan
    # NO es la linea inmune (Crustle), asi que Ogerpon SI lo puede atacar y es su
    # MEJOR atacante; Dipplin se RESERVA para romper el muro Crustle (nuestros ex
    # le hacen 0). Antes, `_ex_stuck_promo_ready` veia el activo Ogerpon bloqueado
    # por el muro Crustle + Dipplin listo en banca y lo retiraba (6000), aunque el
    # plan real del turno era Boss's sobre el Kangaskhan y atacarlo con Ogerpon.
    _keep_ogerpon_for_kang = False
    if (ESTADO.op_is_crustle_deck
            and _my_active_pk is not None
            and _my_active_pk.id == Teal_Mask_Ogerpon_ex
            and len(_my_active_pk.energies) * _grass_mult() >= 3
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        for _kbp in (op_state.bench or []):
            if _kbp is not None and _kbp.id == Mega_Kangaskhan_ex:
                _keep_ogerpon_for_kang = True
                break

    _ex_stuck_promo_ready = (_active_blocked_by_wall and _wall_bench_attacker_ready
                             and not _keep_ogerpon_for_kang)

    # Regla (user, log 86406907 paso 87, GANADA vs Crustle): si nuestro ACTIVO
    # es un atacante NO-ex que SI golpea al muro inmune-a-ex (el activo rival ES
    # el Crustle/Sylveon, op_has_ex_immune_active True) y puede atacar este
    # turno, NUNCA se retira: DEBE atacar. Retirarlo promoveria un Pokemon ex de
    # banca que hace 0 dano al muro (nuestros ex no le pegan). La UNICA razon
    # para retirar vs Crustle es que el activo rival NO sea el muro (p.ej. un
    # Mega Kangaskhan ex), caso en que op_has_ex_immune_active es False y este
    # flag no aplica. `_dmg_vs_wall` ya devuelve 0 para nuestros ex bloqueados y
    # >0 solo para un atacante no-ex con energia suficiente contra ese muro.
    #
    # RELEVO LETAL CONTRA EL MURO (user, registro_018 paso 113 vs Crustle,
    # PERDIDA): la premisa "retirarlo solo promoveria un ex que hace 0" es FALSA
    # cuando en la banca espera OTRO cuerpo no bloqueado que ademas REMATA al
    # muro. Alli el activo era un Meganium a 4 efectivas -- Solar Beam 140 contra
    # un Crustle de **170** PV (lleva una Grass Energy, que da +20 PV a los
    # Pokemon Planta) --: atacar dejaba el muro vivo a 30 y regalaba el turno,
    # mientras en banca esperaba un Tapu Bulu ya a 4 efectivas cuyo Wood Hammer
    # (220) lo noqueaba. La regla que faltaba, general: **si el activo NO remata
    # y un cuerpo de banca SI, se retira y se remata**. Nota: la retirada DESCARTA
    # energia (cartas enteras), asi que el Grass que quedara en el campo se mide
    # DESPUES del retiro -- mismo criterio que `_hlp_grass_after`.
    _wall_ko_promote = None
    if (_op_wall_active is not None and _my_active_pk is not None
            and can_switch and (_op_wall_active.hp or 0) > 0):
        _wkp_hp = _op_wall_active.hp or 0
        _wkp_active_dmg = _our_effective_damage(
            _my_active_pk, _op_wall_active, _dmg_vs_wall(_my_active_pk),
            ESTADO.meganium_in_play, neutralization_zone_active)
        if _wkp_active_dmg < _wkp_hp:
            _wkp_cost = RETREAT_COST.get(_my_active_pk.id, 1)
            _wkp_grass_after = max(
                0, total_grass - (0 if has_switch_card
                                  else _retreat_grass_units(_wkp_cost)))
            for _wkp_bp in (my_state.bench or []):
                if _wkp_bp is None:
                    continue
                if op_has_ex_immune_active and _wkp_bp.id in OUR_EX_IDS:
                    continue  # el muro le hace inmune: 0 dano
                if op_has_ability_immune_active and _wkp_bp.id in OUR_ABILITY_IDS:
                    continue
                _wkp_e = len(_wkp_bp.energies)
                _wkp_base = _attacker_base_damage(
                    _wkp_bp.id, _op_wall_active, _wkp_e * _grass_mult(),
                    grass_scale=_wkp_grass_after, teal_self_energy=_wkp_e,
                    bench_count=bench_count)
                if _wkp_base <= 0:
                    continue  # no llega a su requisito de energia
                _wkp_dmg = _our_effective_damage(
                    _wkp_bp, _op_wall_active, _wkp_base,
                    ESTADO.meganium_in_play, neutralization_zone_active)
                if _wkp_dmg >= _wkp_hp:
                    _wall_ko_promote = _wkp_bp
                    break
    # ...pero el relevo CEDE al gusteo (user, registro_020 paso 122): si con
    # Boss's Orders podemos subir un cuerpo de la banca rival que NUESTRO ACTIVO
    # noquea, ese premio sale SIN pagar la retirada (no se descarta energia ni se
    # expone al relevo al contragolpe) y ademas retira de la mesa un cuerpo ya
    # herido. Mismo premio, mas barato: primero el gusteo.
    if (_wall_ko_promote is not None and can_attack
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        for _wkp_gt in (op_state.bench or []):
            if _wkp_gt is None:
                continue
            _wkp_gt_e = len(_my_active_pk.energies)
            _wkp_gt_base = _attacker_base_damage(
                _my_active_pk.id, _wkp_gt, _wkp_gt_e * _grass_mult(),
                grass_scale=total_grass, teal_self_energy=_wkp_gt_e,
                bench_count=bench_count)
            if _wkp_gt_base <= 0:
                continue
            _wkp_gt_dmg = _our_effective_damage(
                _my_active_pk, _wkp_gt, _wkp_gt_base,
                ESTADO.meganium_in_play, neutralization_zone_active)
            if _wkp_gt_dmg > 0 and _wkp_gt_dmg >= (_wkp_gt.hp or 0):
                _wall_ko_promote = None
                break

    _nonex_active_hits_wall = (
        can_attack
        and op_has_ex_immune_active
        and _my_active_pk is not None
        and _my_active_pk.id not in OUR_EX_IDS
        and _dmg_vs_wall(_my_active_pk) > 0
        # ...salvo que el relevo de banca REMATE y el activo no (ver arriba).
        and _wall_ko_promote is None)

    # Pivote Teal Dance -> retirar -> promover atacante letal (user, log
    # 85802744 turno 16): si el activo es un Teal Mask Ogerpon ex BLOQUEADO por
    # el muro rival (Crustle/Sylveon inmuniza a nuestros ex) que AUN no puede
    # retirarse (energia efectiva < coste de retirada) pero hay un atacante
    # no-ex LISTO en banca que SI golpea al muro, y tenemos una Energia Planta
    # basica en mano, la linea correcta es usar TEAL DANCE en el activo (adjunta
    # la Planta al propio activo + ROBA 1 carta) para habilitar su retirada, y
    # NO malgastar la Planta cargando desarrolladores de banca (p.ej. Dipplin).
    # Tras Teal Dance el activo tendra energia para retirarse el proximo paso y
    # subir al atacante que noquea al muro. `_grass_attach_unit()` = energia
    # EFECTIVA que aporta 1 Planta (2 con Meganium en juego, 1 sin).
    _teal_dance_ko_pivot = False
    if (_ex_stuck_promo_ready
            and _my_active_pk is not None
            and _my_active_pk.id == Teal_Mask_Ogerpon_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _tdkp_rc = RETREAT_COST.get(Teal_Mask_Ogerpon_ex, 1)
        _tdkp_eff_now = len(_my_active_pk.energies) * _grass_mult()
        _tdkp_eff_after = _tdkp_eff_now + _grass_attach_unit()
        if _tdkp_eff_now < _tdkp_rc and _tdkp_eff_after >= _tdkp_rc:
            _teal_dance_ko_pivot = True

    # Pivote de SACRIFICIO a 1 premio (user, registro_008 paso 110 vs Mega
    # Lucario, PERDIDA): si el ACTIVO es un ex NUESTRO (2 premios) FRAGIL que
    # sera NOQUEADO el proximo turno, y en la banca hay un atacante NO-ex (1
    # premio) LISTO que NOQUEA al activo rival, la linea correcta es RETIRAR el
    # ex y promover al no-ex para atacar: se hace el MISMO KO, pero si el rival
    # nos noquea el proximo turno cede 1 premio (no 2) y el ex tanque se
    # resguarda en la banca. Regla del user: siempre que veamos que nuestro ex
    # puede caer el proximo turno y un cuerpo de 1 premio en banca puede derrotar
    # al activo, retiramos el ex y usamos el no-ex para reducir los premios que
    # el rival puede ganar. NO aplica si atacar con el ex YA gana la partida (no
    # hay turno futuro que proteger). Para el Hydrapple ex activo, la retirada se
    # habilita con Ripening Charge (ver _ripen_retreat_ko_pivot). El dano del
    # atacante de banca se mide con la tabla unica y aplica debilidad/zona.
    _fragile_ex_sac_pivot = False
    _fragile_ex_sac_attacker = None
    if (_my_active_pk is not None and _my_active_pk.id in OUR_EX_IDS
            and op_state.active and op_state.active[0] is not None
            and (active_ko_likely
                 or (estimated_op_damage > 0
                     and estimated_op_damage >= (_my_active_pk.hp or 0)))
            and not (my_prize <= prize_count_op(op_state.active[0]))):
        _fesp_opa = op_state.active[0]
        _fesp_opa_hp = _fesp_opa.hp or 0
        for _fesp_bp in (my_state.bench or []):
            if (_fesp_bp is None or _fesp_bp.id in OUR_EX_IDS
                    or _fesp_bp.id not in MAIN_ATTACKERS):
                continue
            _fesp_req = ESTADO.ATTACK_ENERGY_REQ.get(_fesp_bp.id)
            if _fesp_req is None:
                continue
            _fesp_e = len(_fesp_bp.energies)
            _fesp_eff = _fesp_e * _grass_mult()
            if _fesp_eff < _fesp_req:
                continue
            _fesp_base = _attacker_base_damage(
                _fesp_bp.id, _fesp_opa, _fesp_eff,
                grass_scale=total_grass, teal_self_energy=_fesp_e,
                bench_count=bench_count)
            _fesp_dmg = _our_effective_damage(
                _fesp_bp, _fesp_opa, _fesp_base, ESTADO.meganium_in_play,
                neutralization_zone_active)
            if _fesp_dmg > 0 and _fesp_dmg >= _fesp_opa_hp:
                _fragile_ex_sac_pivot = True
                _fragile_ex_sac_attacker = _fesp_bp
                break

    # Pivote Ripening Charge -> retirar -> promover atacante letal (user, log
    # 86028607 turno 22, GANADA): analogo a _teal_dance_ko_pivot pero con el
    # ACTIVO = Hydrapple ex BLOQUEADO por el muro rival (Crustle inmuniza a
    # nuestros ex, Hydrapple ex hace 0). Hydrapple ex no puede atacar pero tiene
    # la habilidad Ripening Charge: se usa para adjuntar una Planta AL PROPIO
    # Hydrapple activo y alcanzar su coste de retirada (EFECTIVO), retirarlo y
    # subir a un atacante no-ex LISTO en banca (Tapu Bulu, 220) que noquea al
    # muro. La retirada se mide en energia EFECTIVA (Wild Growth de Meganium
    # duplica cada Planta fisica), por eso 1 Planta (=2 ef con Meganium) basta
    # para pasar de 2 a 4 ef >= coste 3. Requiere _ex_stuck_promo_ready (activo
    # bloqueado + atacante de banca ya LISTO); por eso solo se activa DESPUES de
    # cargar a Tapu con el adjunte manual (que lo deja listo este mismo turno),
    # momento en que el desempate greedy re-evalua y esta bandera pasa a True.
    # Pivote anti-Cubchoo: activo Hydrapple ex BLOQUEADO (Snotted Up) -> Ripening
    # Charge -> retirar -> promover atacante de banca LISTO (user, registro_008
    # paso 82 vs cornerstone_cubchoo, PERDIDA). El Hydrapple ex activo NO puede
    # atacar (lock de Cubchoo), pero en la banca hay un Ogerpon ex YA cargado que
    # noquea al Cubchoo. Linea correcta: usar Ripening Charge en el PROPIO
    # Hydrapple para alcanzar su coste de retirada (efectivo), retirarlo y subir
    # al Ogerpon para atacar. La regla del user vs este mazo: si el activo NO
    # puede atacar, priorizar la retirada para atacar. A diferencia de
    # [[anti-cubchoo-no-retirada-pivote-conservar-energia]] (activo Ogerpon
    # CARGADO cuya energia se malgastaria -> conservar/PASAR), aqui el activo es
    # un Hydrapple ex cuya energia extra es peso muerto (Syrup Storm escala con
    # el Grass del CAMPO, no con su energia) y esta SUB-cargado (no puede pagar
    # la retirada): cargarlo con la habilidad y retirarlo NO malgasta potencial
    # de ataque y HABILITA un KO. Acotado a Hydrapple ex (cuerpo con Ripening y
    # energia de peso muerto) para no chocar con el veto de conservacion, que
    # cubre al Ogerpon cargado. No depende de la energia actual del activo, asi
    # que sigue True en el paso de la retirada (can_switch ya True).
    _cubchoo_lock_stuck = False
    if (op_is_cubchoo_deck and not can_attack
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and op_state.active and op_state.active[0] is not None):
        _cls_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _cls_grass_after = max(
            0, total_grass - _retreat_grass_units(_cls_rc))
        _cubchoo_lock_stuck = _bench_attacker_can_ko(
            my_state, op_state.active[0], ESTADO.meganium_in_play, total_grass,
            bench_count, _cls_grass_after, neutralization_zone_active)

    _ripen_retreat_ko_pivot = False
    if ((_ex_stuck_promo_ready or _fragile_ex_sac_pivot or _cubchoo_lock_stuck)
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _rrkp_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _rrkp_eff_now = len(_my_active_pk.energies) * _grass_mult()
        _rrkp_eff_after = _rrkp_eff_now + _grass_attach_unit()
        if _rrkp_eff_now < _rrkp_rc and _rrkp_eff_after >= _rrkp_rc:
            _ripen_retreat_ko_pivot = True

    # Pivote Ripening Charge -> cargar Tapu de banca a LETAL -> retirar Hydrapple
    # -> promover Tapu -> noquear al muro (user, log 86182112 paso 82, GANADA vs
    # Crustle). Variante de _ripen_retreat_ko_pivot para cuando el activo
    # Hydrapple ex bloqueado por el muro Crustle YA puede retirarse (energia
    # efectiva >= coste de retirada) pero el Tapu Bulu de banca AUN no esta listo
    # (necesita una 2a Planta para llegar a 4 efectivas = Wood Hammer 220). Sin
    # esta bandera, Teal Dance (Ogerpon, cap Crustle) y Ripening Charge quedaban
    # AMBOS en -1 y el desempate greedy elegia Teal Dance, sobrecargando a
    # Ogerpon (fisicas > cap) y dejando a Tapu en 2 efectivas, sin poder rematar
    # al muro. Ripening Charge (adjunta una Planta a CUALQUIER Pokemon) debe GANAR
    # para poner la 2a Planta en Tapu; el objetivo Tapu se fija en energy_score
    # (ATTACH_FROM, +20000 porque _tapu_eff_ct < 4). Solo se activa DESPUES del
    # adjunte manual que deja a Tapu en 2 efectivas (el greedy re-evalua paso a
    # paso). _grass_attach_unit() = energia EFECTIVA de 1 Planta (2 con Meganium).
    _ripen_bench_tapu_ko_pivot = False
    if (ESTADO.op_is_crustle_deck
            and _active_blocked_by_wall
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _rbtk_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _rbtk_act_eff = len(_my_active_pk.energies) * _grass_mult()
        if _rbtk_act_eff >= _rbtk_rc:
            _rbtk_unit = _grass_attach_unit()
            _rbtk_req = ESTADO.ATTACK_ENERGY_REQ.get(Tapu_Bulu, 4)
            for _rbtk_bp in (my_state.bench or []):
                if _rbtk_bp is None or _rbtk_bp.id != Tapu_Bulu:
                    continue
                _rbtk_eff_now = len(_rbtk_bp.energies) * _grass_mult()
                _rbtk_eff_after = _rbtk_eff_now + _rbtk_unit
                if _rbtk_eff_now >= _rbtk_req or _rbtk_eff_after < _rbtk_req:
                    continue
                _rbtk_base = _attacker_base_damage(
                    Tapu_Bulu, _op_wall_active, _rbtk_eff_after,
                    grass_scale=total_grass, teal_self_energy=0,
                    bench_count=bench_count)
                if _our_effective_damage(
                        _rbtk_bp, _op_wall_active, _rbtk_base,
                        ESTADO.meganium_in_play) >= (_op_wall_active.hp or 0):
                    _ripen_bench_tapu_ko_pivot = True
                    break

    # --- Foco de carga en UN Ogerpon que puede volverse LETAL este turno ---
    # (user, registro_006 paso 62 vs Marnie's Grimmsnarl ex, KO no rematado):
    # con DOS Teal Mask Ogerpon ex en juego, la carga (Teal Dance + adjunte
    # manual) se repartia entre ambos y NINGUNO llegaba a las 3 energias letales,
    # asi que el KO por debilidad (Myriad 180 x2 = 360 >= 320) nunca se armaba.
    # Aqui se identifica UN solo Ogerpon que, concentrando sus 2 fuentes de carga
    # de este turno (Teal Dance adjunta 1 Planta de la mano + el adjunte manual),
    # alcanza las 3 energias EFECTIVAS y NOQUEA al activo rival -- considerando
    # SIEMPRE la debilidad del rival via `_our_effective_damage`. Se prefiere el
    # Ogerpon MAS cargado (menos energia extra necesaria) para maximizar la
    # probabilidad de completar el remate. energy_score concentra el adjunte
    # manual en ese cuerpo y VETA cargar a OTRO Ogerpon (no repartir); la
    # promocion+ataque la resuelve `_ogerpon_lethal_promote` una vez cargado.
    # El foco SOLO aplica cuando el ACTIVO esta ESTANCADO: es un cuerpo que NO
    # llega a su propio ataque este turno ni cargando (adjunte manual + su
    # habilidad de carga: Ripening del Hydrapple / Teal Dance del Ogerpon). Si el
    # activo SI puede atacar cargandose (p.ej. Hydrapple ex activo con Ripening
    # Charge -> Syrup Storm, registro_009/lucario), la energia debe ir al ACTIVO
    # y NO desviarse a un Ogerpon de banca: en ese caso el foco no se activa.
    _olf_active = my_state.active[0] if my_state.active else None
    _olf_active_viable = False
    if _olf_active is not None and _olf_active.id in MAIN_ATTACKERS:
        _olf_a_eff = len(_olf_active.energies) * _grass_mult()
        _olf_a_grass = (hand_counts.get(Basic_Grass_Energy, 0) >= 1)
        _olf_a_extra = 0
        if not state.energyAttached and _olf_a_grass:
            _olf_a_extra += _grass_attach_unit()
        if (_olf_active.id in (Hydrapple_ex, Teal_Mask_Ogerpon_ex)
                and _olf_a_grass):
            _olf_a_extra += _grass_attach_unit()
        if _olf_a_eff + _olf_a_extra >= ESTADO.ATTACK_ENERGY_REQ.get(_olf_active.id, 99):
            _olf_active_viable = True

    # El foco NO se activa cuando la Planta de este turno tiene un destino mas
    # urgente: pagar la RETIRADA del activo para que ataque un cuerpo de banca YA
    # listo (`_ability_unlock_retreat_*`). Ese es el fallo del registro_006 paso
    # 101 vs Alakazam (PERDIDA): con un Ogerpon de banca a 6 efectivas (letal
    # sobre el Alakazam) atrapado detras de un Applin activo a 0 energias, el
    # foco mandaba la Planta al OTRO Ogerpon "para volverlo letal" -- un segundo
    # rematador igual de atrapado -- y el turno moria sin atacar. Mientras la
    # retirada no este pagada, cargar banca no promueve a nadie.
    _ogerpon_lethal_focus_serial = None
    _olf_opa = _active_of(op_state)
    if (_olf_opa is not None and (_olf_opa.hp or 0) > 0
            and not _olf_active_viable
            and not _ability_unlock_retreat_ko
            and not _ability_unlock_retreat_attack
            and not op_has_ex_immune_active
            and not neutralization_zone_active):
        _olf_unit = _grass_attach_unit()
        _olf_grass = hand_counts.get(Basic_Grass_Energy, 0)
        if (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Basic_Grass_Energy, 0) >= 1):
            _olf_grass += 1
        _olf_opp_e = len(getattr(_olf_opa, 'energies', []) or [])
        _olf_best = None
        _olf_best_cur = -1
        for _olf_pk in (list(my_state.active or []) + list(my_state.bench or [])):
            if _olf_pk is None or _olf_pk.id != Teal_Mask_Ogerpon_ex:
                continue
            _olf_cur = len(_olf_pk.energies)
            if _olf_cur >= 3:
                continue  # ya listo: no necesita foco de carga
            # Energia ALCANZABLE concentrando Teal Dance (+1 si hay Planta) y el
            # adjunte manual (+1 si aun no se adjunto y queda una 2a Planta).
            _olf_reach = _olf_cur
            if _olf_grass >= 1:
                _olf_reach += _olf_unit
            if not state.energyAttached and _olf_grass >= 2:
                _olf_reach += _olf_unit
            if _olf_reach < 3:
                continue
            _olf_dmg = _our_effective_damage(
                _olf_pk, _olf_opa, 30 + 30 * (_olf_reach + _olf_opp_e),
                ESTADO.meganium_in_play, neutralization_zone_active)
            if _olf_dmg <= 0 or _olf_dmg < (_olf_opa.hp or 0):
                continue
            if _olf_cur > _olf_best_cur:
                _olf_best_cur = _olf_cur
                _olf_best = _olf_pk
        if _olf_best is not None:
            _ogerpon_lethal_focus_serial = getattr(_olf_best, 'serial', None)

    def _energy_score_base(pokemon, active):
        return _energy_score_base_impl(
            CtxEnergyScoreBase(
            _ability_unlock_retreat_attack=_ability_unlock_retreat_attack,
            _ability_unlock_retreat_ko=_ability_unlock_retreat_ko,
            _active_already_kos=_active_already_kos,
            _active_hydra_capped=_active_hydra_capped,
            _active_needs_energy=_active_needs_energy,
            _active_pokemon=_active_pokemon,
            _attach_enable_retreat_attack=_attach_enable_retreat_attack,
            _attach_enable_retreat_ko=_attach_enable_retreat_ko,
            _bench_attacker_needs_energy=_bench_attacker_needs_energy,
            _bench_attacker_ready=_bench_attacker_ready,
            _bench_has_chargeable=_bench_has_chargeable,
            _carga_activo_habilita_ataque=_carga_activo_habilita_ataque,
            _carga_activo_remata=_carga_activo_remata,
            _conf_active=_conf_active,
            _conf_active_can_attack=_conf_active_can_attack,
            _conf_active_can_retreat=_conf_active_can_retreat,
            _conf_bench_attacker_body=_conf_bench_attacker_body,
            _conf_bench_attacker_ready=_conf_bench_attacker_ready,
            _conf_can_attack_pkmn=_conf_can_attack_pkmn,
            _conf_is_matchup_attacker=_conf_is_matchup_attacker,
            _ctm_applin_bench=_ctm_applin_bench,
            _ctm_charge_active_dipplin=_ctm_charge_active_dipplin,
            _ctm_chikorita_bench=_ctm_chikorita_bench,
            _ctm_tapu_high=_ctm_tapu_high,
            _cubchoo_lock_stuck=_cubchoo_lock_stuck,
            _ex_stuck_promo_ready=_ex_stuck_promo_ready,
            _extra_energy_enables_ko=_extra_energy_enables_ko,
            _feza_lucario_wall=_feza_lucario_wall,
            _gust_2prize_via_boss=_gust_2prize_via_boss,
            _hydra_fragile_pivot=_hydra_fragile_pivot,
            _meganium_alk_1prize_attacker=_meganium_alk_1prize_attacker,
            _meganium_alk_future_charge=_meganium_alk_future_charge,
            _ogerpon_lethal_focus_serial=_ogerpon_lethal_focus_serial,
            _ogerpon_td_manual_lethal=_ogerpon_td_manual_lethal,
            _ripen_retreat_ko_pivot=_ripen_retreat_ko_pivot,
            _tapu_future_charge=_tapu_future_charge,
            _win_via_boss_gust=_win_via_boss_gust,
            active_ko_likely=active_ko_likely,
            bench_count=bench_count,
            field_counts=field_counts,
            hand_counts=hand_counts,
            has_hydrapple=has_hydrapple,
            is_confused=is_confused,
            my_state=my_state,
            neutralization_zone_active=neutralization_zone_active,
            op_has_ex_immune_active=op_has_ex_immune_active,
            op_has_ex_immune_bench=op_has_ex_immune_bench,
            op_has_froslass=op_has_froslass,
            op_is_aggro_deck=op_is_aggro_deck,
            op_is_alakazam_deck=op_is_alakazam_deck,
            op_is_beedrill_deck=op_is_beedrill_deck,
            op_is_cubchoo_deck=op_is_cubchoo_deck,
            op_is_drednaw_deck=op_is_drednaw_deck,
            op_is_fire_deck=op_is_fire_deck,
            op_is_hop_deck=op_is_hop_deck,
            op_is_lucario_deck=op_is_lucario_deck,
            op_is_sylveon_deck=op_is_sylveon_deck,
            op_kang_ko_target=op_kang_ko_target,
            op_state=op_state,
            state=state,
            total_grass=total_grass,
            ),
            pokemon, active,
        )

    def _cuerpo_condenado(pokemon, active) -> bool:
        """FASE C (plan Marnie, D3): ¿el rival puede COBRAR este cuerpo antes de
        nuestro proximo turno, sin que el cuerpo cobre nada antes?

        Partida 2 turno 10: Teal Dance sobre el Ogerpon de BANCA a 80/210, que
        murio ese mismo turno con 5 Plantas encima. De las 13 Plantas del mazo,
        8 se fueron al descarte dentro de cuerpos noqueados.

        Mientras el cuerpo VIVE la energia NO se desperdicia -- Syrup Storm
        escala con la Planta de TODA nuestra mesa y Myriad Leaf Shower con la
        del propio Ogerpon (por eso NO se implementa el tope "coste de ataque +
        1" que pedia el plan: sobrecargar no es el defecto). El desperdicio
        ocurre en el KO, asi que la condicion no es "ya tiene bastante" sino
        "el rival puede cobrarlo".

        Se mide con la ventana COMPLETA -- la que incluye el dano DIRIGIBLE de
        Adrena-Brain --, al reves que la curacion de Ripening Charge, que usa la
        GARANTIZADA. La asimetria es deliberada: alli un falso positivo gasta la
        habilidad entera en un cuerpo que moria igual; aqui solo desvia la
        Planta a otro cuerpo NUESTRO, y para Syrup Storm da lo mismo donde
        caiga. Falso positivo casi gratis, falso negativo = un premio.

        Sin Froslass ni Munkidori en mesa los dos terminos de la ventana son 0 y
        esto no se enciende en ningun otro matchup.
        """
        if ESTADO._op_chip_per_round <= 0 and ESTADO._op_movable_dmg <= 0:
            return False
        _cc_hp = pokemon.hp or 0
        if _cc_hp <= 0:
            return False
        # El ACTIVO que ataca HOY no esta condenado a estos efectos: la energia
        # se cobra antes de que el rival juegue. Se cuenta la Planta que estamos
        # a punto de adjuntar (una carta = _grass_mult() efectivas).
        if active and _can_attack_eff(pokemon.id,
                                      len(pokemon.energies) + _grass_mult()):
            return False
        _cc_golpe = estimated_op_damage if active else ESTADO._op_bench_snipe_dmg
        return _cc_hp <= _ventana_de_regalo(pokemon, active, _cc_golpe)

    def energy_score(pokemon: Pokemon, active: bool) -> float:
        """`_energy_score_base` + el techo de la FASE C.

        El techo va en el ENVOLTORIO y no al final del cuerpo porque
        `_energy_score_base` tiene ~60 `return` repartidos (topes por matchup,
        bandas de banca a 0, pivotes...): un techo al final solo alcanzaria a la
        cola generica. Aqui pasa por el UNICO punto por el que salen todas.

        CAPAR, no vetar, y solo por DEBAJO del piso letal (41000): todo lo que
        llega a esa banda es energia que cobra o niega un premio HOY --
        `_carga_activo_remata`, los pivotes de retirada, `_win_via_boss_gust` --
        y ahi el cuerpo no llega a morir sin haber pagado. Lo de abajo es
        desarrollo, y desarrollar un cuerpo que el rival cobra esta noche es
        regalarle la Planta. Se conserva el ORDEN relativo entre condenados
        (fraccion diminuta) para que, si TODA la mesa esta en la ventana, siga
        ganando el mismo cuerpo que ganaba antes.
        """
        score = _energy_score_base(pokemon, active)
        if 0 < score < SCORE_CARGA_LETAL_FLOOR and _cuerpo_condenado(pokemon, active):
            return SCORE_CARGA_CONDENADA + score / 1000000.0
        return score

    # --- Ripening Charge como CURA: salvar un cuerpo condenado por el snipe ---
    # (user, registro_006/008 pasos 96-122 vs Marnie's Grimmsnarl ex, PERDIDA.)
    # Ripening Charge no solo ADJUNTA una Planta: CURA 30 al Pokemon que la
    # recibe. Cuando el Dipplin de banca esta a 20/80 y Shadow Bullet le mete 30
    # automaticos cada turno, ese cuerpo muere solo y regala un premio; curarlo
    # (20 -> 50) lo hace SOBREVIVIR. El agente adjuntaba esa misma Planta a mano
    # (adjunte manual, sin curacion) o vetaba la habilidad por "no sobrecargar",
    # perdiendo 30 de vida GRATIS: la energia acaba en el mismo campo, asi que
    # Syrup Storm (escala con el Grass TOTAL) hace exactamente el mismo dano.
    #
    # El umbral NO es el snipe (user, registros/marnie partidas 1-3, PERDIDAS):
    # con `_rh_thr = _op_bench_snipe_dmg = 30` ningun cuerpo por encima de 30 PV
    # entraba jamas al detector, y usamos la curacion UNA vez en tres partidas
    # mientras encajabamos 410/620/60 de dano de contadores. El umbral correcto
    # es `_ventana_de_regalo`: golpe proyectado + goteo de Froslass + dano
    # dirigible de Munkidori. Sin esas piezas en mesa la ventana es el golpe de
    # siempre, asi que el resto de matchups no cambia.
    #
    # `_ripen_heal_serial` = serial del cuerpo al que dirigir la Planta. Solo se
    # arma cuando la curacion CAMBIA el resultado (el cuerpo esta DENTRO de la
    # ventana y con +30 SALE), nunca como curacion cosmetica. Se calcula DESPUES
    # de `energy_score` para poder consultar sus prioridades: si alguna carga
    # vale >= 41000 hay un REMATE/pivote letal pendiente y la Planta no se desvia
    # a curar. Ante varios candidatos gana el de MAS PREMIOS (negar dos vale mas
    # que negar uno -- en la partida 2 el Ogerpon ex de banca a 80 PV competia
    # con un Meganium a 90), luego el de MENOS vida y, a igualdad, el de banca
    # (el activo tiene ademas la retirada).
    _ripen_heal_serial = None
    _ripen_heal_ex = False
    if (field_counts.get(Hydrapple_ex, 0) >= 1
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1
            and not neutralization_zone_active):
        _rh_cands = ([(True, _p) for _p in (my_state.active or []) if _p is not None]
                     + [(False, _p) for _p in (my_state.bench or []) if _p is not None])
        _rh_lethal_pending = any(
            energy_score(_p, _act) >= 41000 for _act, _p in _rh_cands)
        if not _rh_lethal_pending:
            _rh_og_cap = None
            if op_is_cubchoo_deck:
                _rh_og_cap = 2 if ESTADO.meganium_in_play else 4
            elif op_is_alakazam_deck or op_is_hop_deck:
                _rh_og_cap = _ogerpon_base_phys_cap(
                    ESTADO.meganium_in_play, op_is_hop_deck)
            _rh_best = None
            _rh_best_key = None
            for _rh_act, _rh_pk in _rh_cands:
                _rh_hp = _rh_pk.hp or 0
                _rh_max = _rh_pk.maxHp or 0
                if _rh_hp <= 0 or _rh_hp >= _rh_max:
                    continue  # sin dano: la curacion no rinde nada
                if _ripen_energy_capped(_rh_pk, _rh_og_cap):
                    continue  # tope duro de energia: no dirigir la Planta ahi
                # Golpe proyectado: al activo el mejor ataque rival; a la banca
                # el snipe automatico. La VENTANA le suma el goteo y el dano
                # dirigible; curar SALVA si ahora esta dentro y despues no.
                _rh_golpe = (estimated_op_damage if _rh_act
                             else ESTADO._op_bench_snipe_dmg)
                _rh_vent = _ventana_de_regalo(_rh_pk, _rh_act, _rh_golpe)
                _rh_gar = _ventana_de_regalo(_rh_pk, _rh_act, _rh_golpe,
                                             incluir_movible=False)
                if _rh_vent <= 0 or _rh_hp > _rh_vent:
                    continue  # fuera de la ventana: no hay premio que negar
                _rh_nuevo = min(_rh_max, _rh_hp + RIPENING_HEAL)
                if _rh_nuevo <= _rh_gar:
                    continue  # muere igual sin que el rival gaste nada
                # Dos grados de salvacion, y el primero manda: salir de la
                # ventana COMPLETA deja al cuerpo fuera de su alcance este
                # turno; salir solo de la GARANTIZADA le obliga a gastar en el
                # Adrena-Brain, que solo alcanza a un cuerpo. Sin Froslass ni
                # Munkidori ambas ventanas coinciden y esto es la regla de
                # siempre. Despues, PREMIOS (negar dos vale mas que negar uno),
                # menos vida, y a igualdad el de banca.
                _rh_key = (0 if _rh_nuevo > _rh_vent else 1,
                           -prize_count(_rh_pk), _rh_hp, 1 if _rh_act else 0)
                if _rh_best_key is None or _rh_key < _rh_best_key:
                    _rh_best_key = _rh_key
                    _rh_best = _rh_pk
            if _rh_best is not None:
                _ripen_heal_serial = getattr(_rh_best, 'serial', None)
                _ripen_heal_ex = prize_count(_rh_best) >= 2

    _sel_active_cant_attack = False
    _sel_active_pkmn = my_state.active[0] if my_state.active else None
    if _sel_active_pkmn is not None:
        # Fuente unica de requisitos: ATTACK_ENERGY_REQ.
        _sel_req = ESTADO.ATTACK_ENERGY_REQ.get(_sel_active_pkmn.id)
        if _sel_req is not None:
            _sel_mult = _grass_mult()
            _sel_eff_now = len(_sel_active_pkmn.energies) * _sel_mult
            _sel_can_now = (_sel_eff_now >= _sel_req)
            _sel_can_attach = False
            if (not _sel_can_now and not state.energyAttached
                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                _sel_eff_after = len(_sel_active_pkmn.energies) + _grass_attach_unit()
                _sel_can_attach = (_sel_eff_after >= _sel_req)
            _sel_active_cant_attack = not (_sel_can_now or _sel_can_attach)
        elif _sel_active_pkmn.id == Meowth_ex:
            _sel_active_cant_attack = True

    _sel_ctx_card = getattr(select, 'contextCard', None)
    # EL FETCH DE LAST-DITCH NO APORTA NADA: el Supporter que queremos jugar ya
    # esta en la MANO y solo se juega UNO por turno. Predicado de TABLERO -- sin
    # el contexto del select -- para que la decision de BAJAR el Meowth ex y la
    # de USAR su habilidad no puedan contradecirse. Antes vivia embebido en
    # `_meowth_skip_fetch` (solo contexto ACTIVATE) y eso abria el agujero del
    # log 88162677 paso 16 vs Alakazam (PERDIDA): el motor bajaba el Meowth ex
    # y acto seguido el prompt de la habilidad RECHAZABA el fetch, asi que se
    # regalaba un cuerpo de 2 premios en la banca por nada.
    _meowth_fetch_ya_en_mano = (
        _meowth_devel_lillie
        and hand_counts.get(Lillie_Determination, 0) >= 1
        and not _win_via_boss_gust and not _gust_2prize_via_boss
    )
    _meowth_skip_fetch = (
        context == SelectContext.ACTIVATE
        and _sel_ctx_card is not None and _sel_ctx_card.id == Meowth_ex
        and _meowth_fetch_ya_en_mano
    )

    # Nuestro PRIMER turno de juego (mismo criterio que el bloque de Ultra
    # Ball): la linea anti-donk baja Meowth ex aunque el Supporter ya este en
    # la mano, asi que las reglas de "copia redundante" no aplican todavia.
    _our_first_action_turn = (
        (state.turn == 1 and ESTADO.we_go_first) or
        (state.turn == 2 and not ESTADO.we_go_first))

    # ¿Hay una Lillie's Determination entre las cartas que ofrece ESTE prompt
    # de Last-Ditch Catch? Se mira la oferta REAL (no la creencia del mazo,
    # que cuenta copias premiadas o ya vistas): la regla de primer turno solo
    # puede degradar al resto de Supporters si de verdad hay una Lillie's que
    # elegir. Fuera del prompt del fetch queda en False y no afecta a nada.
    _ld_lillie_ofrecida = False
    if select.effect is not None and select.effect.id == Meowth_ex:
        for _ld_opt in select.option:
            if _ld_opt.type != OptionType.CARD:
                continue
            _ld_card = get_card(obs, _ld_opt.area, _ld_opt.index,
                                _ld_opt.playerIndex)
            if _ld_card is not None and _ld_card.id == Lillie_Determination:
                _ld_lillie_ofrecida = True
                break

    # BUSQUEDA REDUNDANTE DE MEOWTH EX (user, registro_010 paso 118 vs
    # Alakazam, GANADA con error): bajar Meowth ex solo vale por su Last-Ditch
    # Catch, asi que ANTES de gastarlo hay que mirar QUE Supporter traeria de
    # verdad; si ESE MISMO Supporter ya esta en la mano, la busqueda no aporta
    # nada y ademas expone un cuerpo de 2 premios en la banca. Lo correcto es
    # cancelar el Meowth y seguir el turno jugando ese Supporter.
    #
    # La prediccion usa el MISMO motor que el fetch real
    # (`_REGLAS_MEOWTH_FETCH`), no una lista de casos: por eso vale para
    # CUALQUIER mazo y para cualquier Supporter. Los guards existentes miraban
    # `_best_supp_in_hand_val`, que solo pondera Boss's/Dawn/Lillie's/Lana's --
    # con Xerosic's Machinations en mano valia 0 y el veto nunca disparaba,
    # que es justo lo que paso aqui: se bajo Meowth ex teniendo ya el Xerosic
    # que el fetch acabo trayendo (una 2a copia inutil).
    #
    # `hand_size - 1` porque el fetch se resuelve DESPUES de banquear el Meowth.
    _meowth_fetch_id, _meowth_fetch_val = _meowth_fetch_prediccion(
        hand_counts, _supp_values,
        max(0, (len(my_state.hand) if my_state.hand else 0) - 1),
        (field_counts.get(Hydrapple_ex, 0) >= 1
         or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1),
        getattr(op_state, 'handCount', 0),
        (_active_cant_attack_this_turn or _sel_active_cant_attack),
        _win_via_boss_gust, _gust_2prize_via_boss, _deny_evo_via_boss,
        _meowth_devel_lillie, op_is_alakazam_deck,
        ESTADO.CARTAS_ACTIVAS_EN_MAZO, _our_first_action_turn)
    _meowth_fetch_redundante = (
        _meowth_fetch_id is not None
        and hand_counts.get(_meowth_fetch_id, 0) >= 1)

    # Cuando vamos por detras en premios y el unico gusteo de Boss's Orders es
    # un objetivo de bajo valor (basico/pre-evo de 1 premio, rank alto) que no
    # gana la partida ni toma 2 premios, es mejor desarrollar con Lillie's que
    # quemar el Boss's Orders por un premio menor.
    _boss_low_value_gust = (
        _boss_prize_rank >= 7
        and not _win_via_boss_gust
        and not _gust_2prize_via_boss
        and not _boss_win_via_bench
        and not _boss_dodge_redirect
        and my_prize > op_prize
        and hand_counts.get(Lillie_Determination, 0) >= 1
    )

    # Prioridad entre COPIAS de la misma amenaza (user, registro_007 paso 80 vs
    # Archaludon, GANADA con error): el activo rival es una pre-evo AMENAZA
    # (Duraludon con 3 energias + Hero's Cape) y en banca solo hay copias de la
    # MISMA especie menos desarrolladas (menos energias y sin herramienta de
    # vida). Regla del user: entre dos Pokemon iguales la prioridad la tiene el
    # que lleva un artefacto que le da mas vida y, en 2o lugar, el de mas
    # energias -- es decir, ATACAR al activo grande y NO quemar el Boss's en
    # gustear la copia debil. La correccion anterior
    # (`_bo_active_prize_dominates`) exigia poder NOQUEAR al activo
    # (`_bo_can_ko_active`) y la Hero's Cape (230 > Syrup 210) la desactivaba;
    # ademas la rama low-value/prize-rank del scorer (1500/5200) seguia
    # superando al ATTACK (~1100). Este flag corta TODAS las ramas de valor
    # bajo/medio del PLAY de Boss's (los remates ganadores y de 2 premios
    # retornan antes y no se ven afectados).
    _bo_act_threat_dom = False
    if (op_state.active and op_state.active[0] is not None
            and my_state.active and my_state.active[0] is not None
            and op_state.bench):
        _atd_act = op_state.active[0]
        if _atd_act.id in THREAT_PREEVO_IDS and can_attack:
            _atd_act_tool = len(getattr(_atd_act, 'tools', None) or []) > 0
            _atd_all_dominated = True
            _atd_any_copy = False
            for _atd_bp in op_state.bench:
                if _atd_bp is None:
                    continue
                if _atd_bp.id != _atd_act.id:
                    _atd_all_dominated = False
                    break
                _atd_any_copy = True
                _atd_bp_tool = len(getattr(_atd_bp, 'tools', None) or []) > 0
                # 1a prioridad: herramienta de vida; 2a: energias.
                if _atd_bp_tool and not _atd_act_tool:
                    _atd_all_dominated = False
                    break
                if (_atd_bp_tool == _atd_act_tool
                        and len(_atd_bp.energies) > len(_atd_act.energies)):
                    _atd_all_dominated = False
                    break
            _bo_act_threat_dom = _atd_all_dominated and _atd_any_copy

    # --- Regla anti-2-premios vs Mega Lucario (Riolu activo rival) ---
    # Si en nuestro primer turno (yendo segundos) el rival tiene un Riolu activo
    # con energia, el proximo turno evolucionara a Mega Lucario ex y noqueara a
    # nuestro Ogerpon ex (2 premios). Para evitarlo, retiramos el Ogerpon ex y
    # promovemos un basico de 1 premio como sacrificio (prioridad Tapu Bulu >
    # Applin > Chikorita), entregando solo 1 premio de un Pokemon que no se
    # necesita.
    _lucario_sac_context = (
        state.turn == 2 and not ESTADO.we_go_first
        and op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Riolu
        and len(op_state.active[0].energies) >= 1
        and field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
    )
    _lucario_sac_pivot = (
        _lucario_sac_context
        and my_state.active and my_state.active[0] is not None
        and my_state.active[0].id == Teal_Mask_Ogerpon_ex
    )
    _lucario_sac_available = (
        field_counts.get(Tapu_Bulu, 0) >= 1
        or field_counts.get(Applin, 0) >= 1
        or field_counts.get(Chikorita, 0) >= 1
        or (hand_counts.get(Tapu_Bulu, 0) >= 1 and bench_count < 5)
    )
    # Dentro del escenario anti-Lucario, Tapu Bulu SOLO es el sacrificio/objetivo
    # prioritario cuando de verdad aporta:
    #   * rival con proteccion a ex (Crustle / Cornerstone Ogerpon / Sylveon),
    #     donde nuestros ex hacen 0 dano, o
    #   * motor Hydrapple ex cargado + Meganium en juego, que permite bajar Tapu
    #     Bulu y cargarlo al instante (con Meganium 2 energias cuentan como 4 y
    #     puede atacar de inmediato).
    # En caso contrario preferimos gastar Applin > Chikorita y conservar Tapu Bulu.
    _lucario_hydra_engine = False
    if ESTADO.meganium_in_play and has_hydrapple:
        for _lhp in (my_state.active + my_state.bench):
            if (_lhp is not None and _lhp.id == Hydrapple_ex
                    and len(_lhp.energies) * _grass_mult() >= 2):
                _lucario_hydra_engine = True
                break
    _tapu_sac_priority = _lucario_sac_pivot and (
        ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck or op_is_sylveon_deck
        or op_has_ex_immune_active or op_has_ex_immune_bench
        or op_has_ability_immune_active or _lucario_hydra_engine)
    _lucario_other_sac_available = (
        field_counts.get(Applin, 0) >= 1 or field_counts.get(Chikorita, 0) >= 1
        or hand_counts.get(Applin, 0) >= 1 or hand_counts.get(Chikorita, 0) >= 1)

    # vs DRAGAPULT: Tapu Bulu solo se baja con el tablero SIN desarrollar
    # (user, registro_003 paso 43, episodio 88912610, PERDIDA).
    #
    # Alli teniamos CINCO Pokemon en juego (Meganium activo + Dipplin + tres
    # Teal Mask Ogerpon ex) y el agente bajo Tapu Bulu, llenando la banca. Tapu
    # Bulu es el atacante MANUAL del mazo: su unico papel es pegar cuando el
    # rival apaga nuestras habilidades o inmuniza a nuestros ex. Dragapult no
    # hace ni lo uno ni lo otro -- Ogerpon ex e Hydrapple ex atacan con
    # normalidad --, asi que ahi Tapu Bulu es un cuerpo de relleno sin energia
    # y cada cuerpo extra le PAGA al rival:
    #   * Phantom Dive reparte 6 contadores por la banca; con la banca llena
    #     el reparto siempre encuentra donde doler (`op_bench_snipe_threat`
    #     ya esta encendido en este matchup), y
    #   * un cuerpo mas es un premio mas que regalar, y bloquea el hueco que
    #     necesitan las lineas que SI atacan (Applin/Dipplin/Hydrapple ex y
    #     Chikorita/Bayleef/Meganium).
    # El unico caso en que baja es el de supervivencia: con <=2 Pokemon en
    # juego cualquier cuerpo vale mas que el hueco (un KO nos dejaria sin
    # banca -> [[nunca-terminar-turno-banca-vacia]]).
    #
    # EXCEPCION por COLISION DE MATCHUPS ([[tech-rival-no-activa-matchup-completo]],
    # [[colision-cubchoo-muro-inmune-pivote]]): si ademas hay un muro que anula
    # habilidades o inmuniza a nuestros ex en la mesa rival, Tapu Bulu vuelve a
    # ser el UNICO atacante y el veto se levanta (lo decide `_op_is_crustle_like`
    # en la rama PLAY, que es quien conoce esa lista completa).
    _op_is_dragapult_deck = op_has_dragapult or op_has_dreepy_line
    _tapu_en_juego_total = (
        (1 if (my_state.active and my_state.active[0] is not None) else 0)
        + bench_count)
    _dragapult_no_tapu = (_op_is_dragapult_deck and _tapu_en_juego_total > 2)

    # AMENAZA DE BLOQUEO DE ITEMS (Itchy Pollen de Budew). Se calcula una sola
    # vez y la consumen las dos caras de la misma decision: la red de rescate
    # del turno esteril (finalizacion) y la cadena UB->Meowth->Lillie's via
    # `_ub_meowth_para_manana`. Ver `_bloqueo_de_items_inminente`.
    _item_lock_incoming = _bloqueo_de_items_inminente(
        budew_on_op_field, op_has_dragapult, op_has_dreepy_line)

    # Al valorar descartes, conservar siempre al menos una Lillie's: la primera
    # copia evaluada recibe puntaje protector y solo las copias sobrantes son
    # libremente descartables.
    _lillie_protected_once = False

    # ------------------------------------------------------------------
    # Promocion tras KO: elegir SIEMPRE el mejor atacante de banca segun el
    # Pokemon ACTIVO rival (no segun que cartas tenga en el mazo). Para cada
    # candidato que pueda atacar este turno se estima su dano EFECTIVO contra
    # el activo rival, respetando:
    #   * Inmunidad a ex del activo (Crustle / Sylveon): nuestros ex hacen 0.
    #   * Inmunidad de habilidad del activo (Cornerstone Ogerpon ex): nuestros
    #     atacantes que dependen de habilidad hacen 0.
    #   * Debilidad del activo rival a nuestro tipo (x2).
    # El que mas dano hace se marca para promoverlo de forma decisiva:
    #   - Activo normal / Mega (p.ej. Mega Kangaskhan ex): sube el que pega mas
    #     fuerte (con banca cargada suele ser Hydrapple ex).
    #   - Crustle activo: descarta nuestros ex y sube el mejor no-ex.
    #   - Cornerstone activo: sube un atacante que no dependa de habilidad.
    _best_promote_card = None
    _forced_ko_promote = (
        (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
        and not (my_state.active and my_state.active[0] is not None)
        and not _lucario_sac_context)

    # --- FESTIVAL LEAD: el rival vuelve a atacar EN CUANTO promovemos ---------
    # (user, log 88971843 paso 117 vs Festival Lead, PERDIDA.) Con Festival
    # Grounds en mesa -de quien sea, es un estadio COMPARTIDO- y un Dipplin en
    # su Activo, Festival Lead le deja repetir el ataque justo despues de que
    # elijamos el reemplazo. Eso invierte la premisa sobre la que esta escrita
    # TODA esta rama ("la promocion ocurre en el turno RIVAL, donde nadie ataca
    # ya"): el cuerpo que subimos come un golpe ENTERO antes de que juguemos,
    # asi que "puede atacar este turno" no vale nada si no llega vivo a nuestro
    # turno. Alli se subio un Dipplin de 80 PV contra un Do the Wave de 100 con
    # el rival a 1 premio -- derrota inmediata- teniendo detras un Tapu Bulu de
    # 140 que aguantaba.
    #
    # Se exige `_ko_dentro_de_ventana` (nuestro cuerpo cayo DENTRO del turno
    # rival) porque el segundo ataque solo existe si el primero noqueo: una
    # promocion tras un auto-KO en NUESTRO turno (Wood Hammer) no lo dispara.
    _op_prom_act_dbl = (op_state.active[0]
                        if op_state.active and op_state.active[0] is not None
                        else None)
    op_double_attack_pending = (
        _forced_ko_promote
        and ESTADO._festival_grounds_in_play
        and _ko_dentro_de_ventana
        and _op_prom_act_dbl is not None
        and _op_prom_act_dbl.id in FESTIVAL_LEAD_IDS)

    if _forced_ko_promote:
        _op_prom_active = (op_state.active[0]
                           if op_state.active and op_state.active[0] is not None
                           else None)
        _op_prom_data = (card_table.get(_op_prom_active.id)
                         if _op_prom_active is not None else None)
        _op_prom_weak = getattr(_op_prom_data, 'weakness', None) if _op_prom_data else None
        _op_prom_en = len(_op_prom_active.energies) if _op_prom_active is not None else 0
        _op_prom_remain = (getattr(_op_prom_active, 'hp', 0)
                           if _op_prom_active is not None else 0)
        _prom_bench_after = max(0, bench_count - 1)
        _prom_can_attach = (
            hand_counts.get(Basic_Grass_Energy, 0) >= 1
            or (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Basic_Grass_Energy, 0) >= 1))
        _best_promote_dmg = -1
        _best_promote_key = None
        # Bajo Festival Lead el candidato tiene que SOBREVIVIR al segundo golpe
        # para llegar a atacar. Solo se descartan los condenados si queda algun
        # cuerpo que aguante (mismo criterio que `_promo_survivors`): si no
        # aguanta nadie, la eleccion vuelve a ser la de siempre y la gobiernan
        # las reglas de premios de mas abajo.
        _dbl_hay_superviviente = False
        if op_double_attack_pending:
            for _db in my_state.bench:
                if _db is None or not isinstance(_db, Pokemon):
                    continue
                _db_hit = _op_active_attack_damage_to(
                    _op_prom_active, _db, getattr(op_state, 'handCount', None))
                if _db_hit < (getattr(_db, 'hp', 0) or 0):
                    _dbl_hay_superviviente = True
                    break
        for _pb in my_state.bench:
            if _pb is None or not isinstance(_pb, Pokemon):
                continue
            if op_double_attack_pending and _dbl_hay_superviviente:
                _pb_hit_now = _op_active_attack_damage_to(
                    _op_prom_active, _pb, getattr(op_state, 'handCount', None))
                if _pb_hit_now >= (getattr(_pb, 'hp', 0) or 0):
                    continue  # muere antes de poder atacar: no es candidato
            _pb_req = ESTADO.ATTACK_ENERGY_REQ.get(_pb.id)
            if _pb_req is None:
                continue
            _pb_en_eff = len(_pb.energies)
            if _pb_en_eff < _pb_req and _prom_can_attach:
                _pb_en_eff += _grass_attach_unit()
            if _pb_en_eff < _pb_req:
                continue  # no puede atacar este turno
            if _pb.id == Hydrapple_ex:
                _pb_dmg = 30 + 30 * total_grass
            elif _pb.id == Teal_Mask_Ogerpon_ex:
                # Myriad cuenta la energia de AMBOS activos: el promovido
                # atacara al activo rival ACTUAL, cuya energia es conocida.
                _pb_dmg = 30 + 30 * (
                    len(_pb.energies)
                    + len(getattr(_active_of(op_state), 'energies', []) or []))
            elif _pb.id == Dipplin:
                _pb_dmg = 20 * _prom_bench_after
            elif _pb.id == Tapu_Bulu:
                _pb_dmg = 220
            elif _pb.id == Meganium:
                _pb_dmg = 140
            elif _pb.id == Fezandipiti_ex:
                _pb_dmg = 100
            else:
                _pb_dmg = 10
            # Inmunidad a ex del activo rival (Crustle / Sylveon): ex -> 0.
            if op_has_ex_immune_active and _pb.id in OUR_EX_IDS:
                _pb_dmg = 0
            # Neutralization Zone (id 1247, user): al promover tras un KO debemos
            # evaluar si la zona esta en juego. Bajo la zona, nuestros ex (recuadro
            # de regla) NO danan a un activo rival SIN recuadro (1 premio): su dano
            # es 0. Por eso el UNICO atacante util a promover es uno NO-ex (Meganium/
            # Tapu Bulu/Pinsir/Dipplin), a menos que el activo rival sea un ex
            # (recuadro), contra el que nuestros ex si danan. Sin esto se promovia
            # un ex que hace 0 y dejaba el turno sin ataque.
            if (neutralization_zone_active and _pb.id in OUR_EX_IDS
                    and not (_op_prom_data
                             and (_op_prom_data.ex or _op_prom_data.megaEx))):
                _pb_dmg = 0
            # Inmunidad de habilidad del activo rival (Cornerstone): los
            # atacantes que dependen de habilidad quedan bloqueados -> 0.
            if op_has_ability_immune_active and _pb.id in OUR_ABILITY_IDS:
                _pb_dmg = 0
            # Debilidad del activo rival a nuestro tipo -> x2.
            _pb_data = card_table.get(_pb.id)
            if (_pb_data is not None and _op_prom_weak is not None
                    and getattr(_pb_data, 'energyType', None) == _op_prom_weak):
                _pb_dmg *= 2
            if _pb_dmg <= 0:
                continue  # inmune / sin ataque util: no puede derrotar al rival
            # Regla: subir SIEMPRE el de MAS VIDA que pueda derrotar al rival.
            # Prioridad lexicografica: (puede noquear, prudencia de premios,
            # vida restante, dano). PRUDENCIA GENERAL (auditoria julio 2026,
            # sugerencia 6 -- generaliza el patron por-matchup de Alakazam/
            # Tapu): si el golpe rival PROYECTADO noquea al candidato, un
            # cuerpo de 1 premio que tambien noquea es mejor intercambio que
            # un ex de 2 premios igualmente condenado. Con dano rival ilegible
            # (proyeccion 0, p.ej. ataques de contadores no modelados) todos
            # "sobreviven" y la clave queda EXACTAMENTE como antes
            # (conservador: solo cambia conducta con evidencia).
            _pb_can_ko = 1 if (_op_prom_remain > 0 and _pb_dmg >= _op_prom_remain) else 0
            _pb_hp = getattr(_pb, 'hp', 0) or 0
            # La prudencia SOLO discrimina entre candidatos que NOQUEAN
            # (regla del user: "cualquier no-ex que noquee IGUAL"); si nadie
            # noquea, la clave queda como antes (el mas tanque/fuerte).
            _pb_pref = 1
            if _pb_can_ko:
                _pb_op_hit = _op_active_attack_damage_to(
                    _active_of(op_state), _pb,
                    getattr(op_state, 'handCount', None))
                _pb_pref = 1 if (_pb_op_hit < _pb_hp
                                 or prize_count(_pb) == 1) else 0
            _pb_key = (_pb_can_ko, _pb_pref, _pb_hp, _pb_dmg)
            if _best_promote_key is None or _pb_key > _best_promote_key:
                _best_promote_key = _pb_key
                _best_promote_dmg = _pb_dmg
                _best_promote_card = _pb
        if _best_promote_card is None or _best_promote_dmg <= 0:
            _best_promote_card = None

        # Tanque RECARGABLE sobre atacante ex CONDENADO (user, registro_009
        # paso 130 vs Archaludon, GANADA): al promover tras un KO, si el mejor
        # candidato es un ex que NO noquea y el golpe rival proyectado lo MATA
        # (Ogerpon 210 vs Ion Beam 220 -> regala 2 premios), y en banca hay un
        # Hydrapple ex que SOBREVIVE al golpe (330) y es RECARGABLE el proximo
        # turno (adjunte manual + Ripening Charge = 2 adjuntes; energias
        # accesibles en mano o recuperables del descarte con Lana's Aid),
        # promover el tanque. El filtro "puede atacar este turno" excluia al
        # Hydrapple sin energias aunque esta promocion ocurre en el turno
        # RIVAL, donde nadie ataca ya; con Lana's + 3 Plantas en el descarte
        # el Hydrapple queda a 2 efectivas y ataca el proximo turno (Syrup
        # Storm), mientras que el Ogerpon promovido solo muere. Los overrides
        # de ABAJO (Tapu que noquea / 1-premio vs Alakazam) siguen ganando
        # porque se aplican despues y exigen KO real.
        if (_best_promote_card is not None
                and _best_promote_key is not None
                and _best_promote_key[0] == 0
                and prize_count(_best_promote_card) >= 2
                and _op_prom_remain > 0):
            _rt_op_act = _active_of(op_state)
            _rt_hit = _op_active_attack_damage_to(
                _rt_op_act, _best_promote_card,
                getattr(op_state, 'handCount', None))
            if (_rt_hit > 0
                    and _rt_hit >= (getattr(_best_promote_card, 'hp', 0) or 0)):
                _rt_unit = _grass_attach_unit()
                _rt_grass_discard = sum(
                    1 for _rc in (my_state.discard or [])
                    if getattr(_rc, 'id', 0) == Basic_Grass_Energy)
                _rt_avail = hand_counts.get(Basic_Grass_Energy, 0)
                if hand_counts.get(Lanas_Aid, 0) >= 1:
                    _rt_avail += min(3, _rt_grass_discard)
                for _rt_pb in my_state.bench:
                    if (_rt_pb is None or not isinstance(_rt_pb, Pokemon)
                            or _rt_pb.id != Hydrapple_ex):
                        continue
                    _rt_hp = getattr(_rt_pb, 'hp', 0) or 0
                    if _rt_hit >= _rt_hp:
                        continue  # tampoco sobrevive: no es tanque
                    _rt_req = ESTADO.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
                    _rt_deficit = _rt_req - len(_rt_pb.energies)
                    if _rt_deficit <= 0:
                        continue  # ya atacaria: el bucle normal lo evaluo
                    # cartas fisicas necesarias, maximo 2 adjuntes next turn
                    _rt_need = -(-_rt_deficit // max(1, _rt_unit))
                    if _rt_need > 2 or _rt_avail < _rt_need:
                        continue
                    _best_promote_card = _rt_pb
                    break

        # Regla (user, registro 007 paso 90 vs Alakazam, GANADA): al promover tras
        # un KO, si en la banca hay un Tapu Bulu que puede ATACAR este turno (>=4
        # energia efectiva, o le falta y la tenemos en mano / recuperable con Night
        # Stretcher) y con su ataque de 220 NOQUEA al activo rival, subirlo SIEMPRE
        # -aunque un ex de banca (Ogerpon/Hydrapple ex) tenga mas vida o pegue algo
        # mas fuerte-. Tapu Bulu es no-ex (solo 1 premio si lo noquean) y remata
        # igual que un ex de 2 premios: exponer el cuerpo barato es lo correcto.
        # Complementa [[tapu-bulu-activo-que-noquea-ataca-no-retira]] (que decide no
        # retirar un Tapu Bulu que noquea); esta decide a QUIEN promover.
        if _op_prom_remain > 0:
            _tapu_prom = None
            for _tb in my_state.bench:
                if _tb is None or not isinstance(_tb, Pokemon) or _tb.id != Tapu_Bulu:
                    continue
                _tb_req = ESTADO.ATTACK_ENERGY_REQ.get(Tapu_Bulu, 4)
                _tb_eff = len(_tb.energies)
                if _tb_eff < _tb_req and _prom_can_attach:
                    _tb_eff += _grass_attach_unit()
                if _tb_eff < _tb_req:
                    continue
                _tb_dmg = 220
                _tb_data = card_table.get(Tapu_Bulu)
                if (_tb_data is not None and _op_prom_weak is not None
                        and getattr(_tb_data, 'energyType', None) == _op_prom_weak):
                    _tb_dmg *= 2
                if _tb_dmg >= _op_prom_remain:
                    _tapu_prom = _tb
                    break
            if _tapu_prom is not None:
                _best_promote_card = _tapu_prom

        # Regla (user, registro_010 paso 127, vs Alakazam, PERDIDA): al PROMOVER
        # (retiro voluntario o KO) contra un mazo de Alakazam, preferir SIEMPRE un
        # cuerpo de UN premio (Meganium o Tapu Bulu) que NOQUEE al activo rival
        # sobre un ex de 2 premios, aunque el ex tenga MAS vida. Extiende la regla
        # universal de Tapu Bulu (arriba) para incluir a Meganium en este matchup:
        # si nos noquean el atacante solo cedemos 1 premio en vez de 2. Entre
        # varios candidatos de 1 premio se sube el de MAS vida.
        if op_is_alakazam_deck and _op_prom_remain > 0:
            _ak_1prize_prom = None
            _ak_1prize_hp = -1
            for _mb in my_state.bench:
                if _mb is None or not isinstance(_mb, Pokemon):
                    continue
                # Dipplin y Pinsir incluidos (user, registro_005 paso 56 vs
                # Alakazam): cualquier cuerpo de 1 premio con ataque modelado
                # que noquee sirve; consistente con la deteccion generalizada
                # de `_alakazam_pivot_1prize`.
                if _mb.id not in (Meganium, Tapu_Bulu, Dipplin, Pinsir):
                    continue
                _mb_req = ESTADO.ATTACK_ENERGY_REQ.get(_mb.id)
                if _mb_req is None:
                    continue
                _mb_eff = len(_mb.energies)
                if _mb_eff < _mb_req and _prom_can_attach:
                    _mb_eff += _grass_attach_unit()
                if _mb_eff < _mb_req:
                    continue
                if _mb.id == Tapu_Bulu:
                    _mb_dmg = 220
                elif _mb.id == Meganium:
                    _mb_dmg = 140
                elif _mb.id == Pinsir:
                    _mb_dmg = 100
                else:
                    # Do the Wave de Dipplin = 20 x nuestra banca; al promoverlo
                    # deja la banca (conservador: bench_count - 1).
                    _mb_dmg = 20 * max(0, bench_count - 1)
                _mb_data = card_table.get(_mb.id)
                if (_mb_data is not None and _op_prom_weak is not None
                        and getattr(_mb_data, 'energyType', None) == _op_prom_weak):
                    _mb_dmg *= 2
                if _mb_dmg < _op_prom_remain:
                    continue
                _mb_hp = getattr(_mb, 'hp', 0) or 0
                if _mb_hp > _ak_1prize_hp:
                    _ak_1prize_hp = _mb_hp
                    _ak_1prize_prom = _mb
            if _ak_1prize_prom is not None:
                _best_promote_card = _ak_1prize_prom

        # Tanque via EVOLUCION sobre atacante CONDENADO (user, registro_013 paso
        # 99 vs Mega Lucario ex, PERDIDA): al promover tras un KO, si NADIE en la
        # banca NOQUEA al activo rival (`_best_promote_key[0] == 0`) y el candidato
        # normal es un ex de 2+ premios que MUERE al golpe proyectado (Ogerpon ex
        # 210 vs los 270 del Mega Lucario -> regala 2 premios), pero una PRE-EVO de
        # banca (Dipplin) puede EVOLUCIONAR el proximo turno a un cuerpo que
        # SOBREVIVE (Hydrapple ex 330 > 270), promover esa pre-evo: cede 0 premios
        # y aguanta el golpe para seguir en juego. Generaliza el "tanque
        # recargable" de arriba (que exige el tanque YA en banca) a la via de
        # EVOLUCION (la evolucion esta en la MANO). El atacante de 1 premio que
        # NOQUEA (Tapu/Meganium, ramas de arriba) mantiene la prioridad: esto solo
        # actua cuando no hay KO posible. La prioridad del usuario es: (1) 1-premio
        # que noquea; (2) el que mejor AGUANTE un golpe futuro -aqui-; (3) sacrificar
        # el 1-premio menos necesario (ramas basic-prefer de abajo). Deck-agnostico.
        # Se dispara cuando NO hay atacante que noquee al activo rival: o el mejor
        # candidato es un ex de 2+ premios condenado (`_best_promote_key[0]==0`),
        # o directamente no hay cuerpo que pueda atacar este turno
        # (`_best_promote_card is None`, p.ej. sin energia para adjuntar). En ambos
        # casos la prioridad (2) del usuario -"el que mejor AGUANTE un golpe
        # futuro"- manda: si NINGUN cuerpo de banca sobrevive al golpe proyectado
        # tal cual, pero una PRE-EVO puede EVOLUCIONAR el proximo turno a un cuerpo
        # que SOBREVIVE, promover esa pre-evo.
        _ev_no_koer = (_best_promote_card is None
                       or (_best_promote_key is not None
                           and _best_promote_key[0] == 0
                           and prize_count(_best_promote_card) >= 2))
        if _forced_ko_promote and _ev_no_koer and _op_prom_remain > 0:
            _ev_op_act = _active_of(op_state)
            _ev_hand = getattr(op_state, 'handCount', None)
            # ¿Sobrevive algun cuerpo TAL CUAL (sin evolucionar) al golpe
            # proyectado? Si si, no forzamos la via de evolucion (la logica normal
            # decide; evitamos colateral). Solo actuamos cuando NADA aguanta.
            _ev_survivor_asis = False
            for _sb in my_state.bench:
                if _sb is None or not isinstance(_sb, Pokemon):
                    continue
                _sb_hit = _op_active_attack_damage_to(_ev_op_act, _sb, _ev_hand)
                if _sb_hit > 0 and _sb_hit < (getattr(_sb, 'hp', 0) or 0):
                    _ev_survivor_asis = True
                    break
            if not _ev_survivor_asis:
                _ev_best = None
                _ev_best_hp = -1
                for _ev_pb in my_state.bench:
                    if _ev_pb is None or not isinstance(_ev_pb, Pokemon):
                        continue
                    if getattr(_ev_pb, 'appearThisTurn', False):
                        continue  # recien salio: no evoluciona el proximo turno
                    _ev_pb_data = card_table.get(_ev_pb.id)
                    _ev_pb_name = getattr(_ev_pb_data, 'name', None)
                    if _ev_pb_name is None:
                        continue
                    # Evolucion DIRECTA en la mano cuya pre-evo es este cuerpo.
                    _ev_to_id = None
                    for _hid, _hn in hand_counts.items():
                        if _hn <= 0:
                            continue
                        _hd = card_table.get(_hid)
                        if (_hd is not None
                                and getattr(_hd, 'evolvesFrom', None) == _ev_pb_name):
                            _ev_to_id = _hid
                            break
                    if _ev_to_id is None:
                        continue
                    _ev_to_data = card_table.get(_ev_to_id)
                    # CardData expone la vida base como `.hp` (no `.maxHp`); los
                    # Pokemon del TABLERO si tienen `.maxHp`/`.hp` (actual).
                    _ev_max = getattr(_ev_to_data, 'hp', 0) or 0
                    # El dano ya sufrido por la pre-evo se conserva al evolucionar.
                    _ev_dmg_taken = ((getattr(_ev_pb, 'maxHp', 0) or 0)
                                     - (getattr(_ev_pb, 'hp', 0) or 0))
                    _ev_survive_hp = _ev_max - max(0, _ev_dmg_taken)
                    _ev_op_hit = _op_active_attack_damage_to(
                        _ev_op_act, _ProjTarget(_ev_to_id), _ev_hand)
                    if _ev_op_hit <= 0 or _ev_op_hit >= _ev_survive_hp:
                        continue  # la evolucion tampoco sobrevive
                    if _ev_survive_hp > _ev_best_hp:
                        _ev_best_hp = _ev_survive_hp
                        _ev_best = _ev_pb
                if _ev_best is not None:
                    _best_promote_card = _ev_best

    # Regla (user) vs Mega Lucario: cuando el rival nos NOQUEA un Pokemon y en
    # la banca NO hay NINGUN atacante capaz de atacar este turno
    # (`_best_promote_card is None`), preferimos SIEMPRE promover primero un
    # Pokemon BASICO (Applin es la prioridad entre los basicos), o Dipplin si no
    # tenemos ningun basico. Asi entregamos un cuerpo barato (1 premio) en vez de
    # un ex (2 premios) que igual no puede contraatacar. Si no hay basico ni
    # Dipplin en la banca, se conserva la logica actual de promocion.
    _lucario_ko_prefer_basic = (
        _forced_ko_promote
        and op_is_lucario_deck
        and _best_promote_card is None)

    # Generalizacion deck-agnostica de la regla anterior (user, registro_004
    # paso 37): al PROMOVER (tras retiro o KO) SIN ningun atacante de banca listo
    # (`_best_promote_card is None`), si el ataque del activo rival NOQUEA incluso
    # al cuerpo mas tanque que promoveriamos, cualquier cuerpo que pongamos delante
    # cae -> exponer un BASICO de 1 premio (no un ex de 2). Es el lado de promocion
    # del pivote `_doomed_ex_sac_pivot`: se detecta con el remate rival REAL, no con
    # una lista de matchups, asi que aplica a cualquier mazo (Mega Lucario incluido).
    # Excluye muros inmunes a ex/habilidad (ahi la promocion sube su propio muro).
    _ko_prefer_basic_general = False
    if (_forced_ko_promote and _best_promote_card is None
            and not _lucario_ko_prefer_basic
            and my_prize >= 3
            and not op_has_ex_immune_active
            and not op_has_ability_immune_active
            and op_state.active and op_state.active[0] is not None):
        _kpb_opa = op_state.active[0]
        _kpb_has_basic = False
        _kpb_tank = None
        _kpb_tank_hp = -1
        for _kbp in my_state.bench:
            if _kbp is None or not isinstance(_kbp, Pokemon):
                continue
            _kbp_d = card_table.get(_kbp.id)
            if (_kbp_d is not None
                    and not getattr(_kbp_d, 'stage1', False)
                    and not getattr(_kbp_d, 'stage2', False)
                    and _kbp.id not in OUR_EX_IDS):
                _kpb_has_basic = True
            if (_kbp.hp or 0) > _kpb_tank_hp:
                _kpb_tank_hp = _kbp.hp or 0
                _kpb_tank = _kbp
        if _kpb_has_basic and _kpb_tank is not None:
            _kpb_hit = _op_active_attack_damage_to(
                _kpb_opa, _kpb_tank, getattr(op_state, 'handCount', None))
            if _kpb_hit >= (_kpb_tank.hp or 0):
                _ko_prefer_basic_general = True
    # ------------------------------------------------------------------

    # Promover al mejor atacante FUTURO tras un KO (user, registro_009 paso 111 vs
    # Alakazam, PERDIDA): cuando NINGUN cuerpo puede atacar ESTE turno
    # (`_best_promote_card is None`) pero un atacante de banca esta a UNA sola
    # energia de su requisito y, completado, NOQUEA al activo rival, y ademas
    # tenemos como refrescar/buscar esa energia (Lillie's/Dawn en mano + Planta
    # en el mazo o la mano), promover ESE atacante en vez de un muro basico
    # barato. La promocion ocurre en el turno RIVAL; el proximo turno adjuntamos
    # 1 Planta (x2 con Meganium en juego) y atacamos. Ejemplo: Ogerpon ex a 2/3
    # efectivas -> con 1 adjunte llega a Myriad ({G}{G}{G}) y remata (30+30*(4+
    # energia del activo rival)); Tapu Bulu (0/4) tardaria varios turnos y no
    # contraataca. No aplica en sacrificio puro (el rival one-shotea hasta el
    # tanque -> `_ko_prefer_basic_general`), vs Lucario, ni con inmunidades a
    # ex/habilidad o Zona de Neutralizacion. Deck-agnostico.
    # Nota: este remate FUTURO OVERRIDE a `_ko_prefer_basic_general` (sacrificar
    # un basico porque el rival one-shotea al tanque): si el ex promovido NOQUEA
    # al activo rival el PROXIMO turno -que es NUESTRO turno, atacamos primero-,
    # el rival ni llega a golpearlo, asi que la premisa del sacrificio no aplica.
    _promote_setup_ko_attacker = None
    if (_forced_ko_promote and _best_promote_card is None
            and not _lucario_ko_prefer_basic
            and not op_has_ex_immune_active
            and not op_has_ability_immune_active
            and not neutralization_zone_active
            and op_state.active and op_state.active[0] is not None):
        _ps_opa = op_state.active[0]
        _ps_opa_data = card_table.get(_ps_opa.id)
        _ps_weak = getattr(_ps_opa_data, 'weakness', None) if _ps_opa_data else None
        _ps_opa_en = len(_ps_opa.energies or [])
        _ps_remain = getattr(_ps_opa, 'hp', 0) or 0
        _ps_unit = _grass_attach_unit()
        # Planta OCULTA (en mazo o premios) = total del mazo - Plantas VISIBLES
        # (mano + descarte + adjuntadas a nuestros Pokemon). Se calcula desde la
        # observacion para NO depender del contador por-zona
        # `CARTAS_ACTIVAS_EN_MAZO[MAZO]`, que se desincroniza en registros que no
        # arrancan en el turno 1 (este empieza en el turno 9). El total del mazo
        # (suma de todas las zonas) SI es fiable (se conserva).
        _ps_grass_total = sum(
            ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Basic_Grass_Energy, {}).values())
        _ps_grass_visible = (
            hand_counts.get(Basic_Grass_Energy, 0)
            + discard_counts.get(Basic_Grass_Energy, 0))
        for _pp in ([_active_of(my_state)] + list(my_state.bench or [])):
            if _pp is not None:
                _ps_grass_visible += sum(
                    1 for _e in (getattr(_pp, 'energyCards', None) or [])
                    if getattr(_e, 'id', 0) == Basic_Grass_Energy)
        _ps_grass_hidden = _ps_grass_total - _ps_grass_visible
        # Como conseguir la energia que falta el proximo turno. La version
        # original solo aceptaba un Supporter de robo YA en la mano
        # (Lillie's/Dawn) + Planta accesible; con eso, una mano que solo tiene
        # el MOTOR que consigue ese Supporter quedaba fuera y se promovia un
        # muro inutil (user, registro_007 paso 126 vs Marnie's Grimmsnarl ex,
        # PERDIDA: mano = Meowth ex + Meganium, banca = 2 Ogerpon ex a 2/3
        # energias -que con 1 adjunte rematan por debilidad a Planta- y un Tapu
        # Bulu a 1/4; se subio el Tapu Bulu, que no puede atacar ni retirarse
        # -coste 3- y regalo el turno). Ahora se enumeran TODAS las vias reales,
        # deck-agnosticas:
        #   a) Supporter de robo en mano (Lillie's/Dawn) + Planta accesible
        #      (mano o aun oculta en mazo/premios).
        #   b) Recuperacion del DESCARTE con Lana's Aid en mano (Night Stretcher
        #      ya lo cubre `_prom_can_attach`, que ataca el MISMO turno).
        #   c) Motor Meowth ex: bajarlo a la banca dispara Last-Ditch Catch y
        #      trae del mazo el Supporter que falta -Lana's Aid (levanta Plantas
        #      del descarte) o Lillie's/Dawn (rehace la mano)-. Exige hueco en
        #      banca tras la promocion y la habilidad viva (sin Watchtower /
        #      Iron Thorns).
        #   d) Motor Fezandipiti ex -> Flip the Script: roba 3. Es la via que
        #      faltaba y la UNICA cuyo disparador esta garantizado en esta rama
        #      -estamos promoviendo PORQUE nos acaban de noquear, que es
        #      exactamente lo que enciende Flip the Script- (user, registro_008
        #      paso 122 vs Dragapult, PERDIDA: mano con Fezandipiti ex + Ultra
        #      Ball, tres Ogerpon ex a 2/3 efectivas que con UN adjunte rematan
        #      al Dragapult ex a 50 PV... y se subio el Tapu Bulu a 0/4 con
        #      retirada 3, que ni ataca ni se puede cambiar). Watchtower NO la
        #      apaga: solo anula habilidades de Pokemon {C} y Fezandipiti ex es
        #      {D}; el que si la mata es Iron Thorns (anula TODA habilidad con
        #      Rule Box). Vale tanto con el Fezandipiti YA en juego como con uno
        #      en la mano y hueco de banca tras la promocion.
        # Las copias "ocultas" (mazo o premios) se miden como total del mazo
        # menos las VISIBLES (mano + descarte), mismo criterio observacional que
        # `_ps_grass_hidden` para no depender del contador por-zona.
        def _ps_hidden_copies(_cid):
            _tot = sum(ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(_cid, {}).values())
            return _tot - (hand_counts.get(_cid, 0)
                           + discard_counts.get(_cid, 0))

        _ps_grass_reachable = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                               or _ps_grass_hidden >= 1)
        _ps_grass_in_discard = discard_counts.get(Basic_Grass_Energy, 0) >= 1
        _ps_draw_supp_hand = (hand_counts.get(Lillie_Determination, 0) >= 1
                              or hand_counts.get(Dawn, 0) >= 1)
        _ps_meowth_engine = (
            hand_counts.get(Meowth_ex, 0) >= 1
            and not meowth_ability_lock
            and _prom_bench_after < 5
            and ((_ps_hidden_copies(Lanas_Aid) >= 1 and _ps_grass_in_discard)
                 or ((_ps_hidden_copies(Lillie_Determination) >= 1
                      or _ps_hidden_copies(Dawn) >= 1)
                     and _ps_grass_reachable)))
        _ps_can_find_energy = (
            (_ps_draw_supp_hand and _ps_grass_reachable)
            or (hand_counts.get(Lanas_Aid, 0) >= 1 and _ps_grass_in_discard)
            or _ps_meowth_engine)
        # Ruta (d): el robo de 3 de Flip the Script. Se lleva aparte de
        # `_ps_can_find_energy` porque es la mas floja de las cuatro -roba a
        # ciegas, no busca- y por eso lleva DOS guardas propias: abajo se le
        # exige que el cuerpo promovido conserve la SALIDA
        # (`_ps_conserva_salida`), y aqui que el KO que compra valga de verdad.
        #
        # MATCHUP DE MURO (MEDIDO): la apuesta no se hace contra un mazo que
        # neutraliza estructuralmente a nuestros ex -- inmunidad a ex (Crustle /
        # Sylveon), a habilidades (Cornerstone) o lock (Iron Thorns). Ahi el
        # premio que compra el remate rinde poco (en cuanto el muro vuelve al
        # activo, el ex promovido no le hace nada) y lo que se arriesga -- un
        # cuerpo de 2 premios -- se paga igual. La guarda exterior de
        # `_promote_setup_ko_attacker` solo mira el ACTIVO rival; esta mira
        # tambien la BANCA, que es donde el muro espera su turno. Gate de
        # self-play vs deck/rivales/crustle_kangaskhan.csv, 18000 partidas por
        # rama: 70.2% con la ruta abierta frente a 70.9% sin ella (-0.68, z
        # -1.4, y el signo se repitio en 5 de 6 brazos pareados). No es
        # significativo, pero la ruta dispara en el 5.8% de esas partidas y no
        # tiene por que estar ahi: se acota al matchup donde el plan SI cobra.
        _ps_matchup_de_muro = (
            ESTADO.op_is_crustle_deck or op_is_sylveon_deck or ESTADO.op_is_cornerstone_deck
            or op_is_iron_thorns_deck
            or op_has_ex_immune_active or op_has_ex_immune_bench
            or op_has_ability_immune_active)
        _ps_fez_draw_engine = (
            not op_iron_thorns_active
            and not _ps_matchup_de_muro
            and _ps_grass_reachable
            and (field_counts.get(Fezandipiti_ex, 0) >= 1
                 or (hand_counts.get(Fezandipiti_ex, 0) >= 1
                     and _prom_bench_after < 5)))

        def _ps_conserva_salida(_pk):
            """El candidato puede PAGAR SU RETIRADA con la energia que ya lleva.

            Es la mitad que hace segura la ruta (d) (user, registro_008 paso
            122): subir al casi-atacante NO es una apuesta a ciegas mientras
            siga siendo reversible. Si el robo falla y la Planta no aparece,
            el proximo turno lo retiramos y subimos ENTONCES el muro de 1
            premio -- el sacrificio es una decision DIFERIBLE; quedarse clavado
            no. Un cuerpo a 0 energias con retirada 3 (Tapu Bulu) regala el
            turno entero: ni ataca ni se puede cambiar.
            """
            return len(_pk.energies) >= RETREAT_COST.get(_pk.id, 1)

        if _ps_remain > 0 and (_ps_can_find_energy or _ps_fez_draw_engine):
            _ps_best_key = None
            for _psb in my_state.bench:
                if _psb is None or not isinstance(_psb, Pokemon):
                    continue
                _ps_req = ESTADO.ATTACK_ENERGY_REQ.get(_psb.id)
                if _ps_req is None:
                    continue
                # Con SOLO la ruta (d) viva -el robo a ciegas de Flip the
                # Script-, el candidato tiene que conservar la salida: si la
                # Planta no aparece, se retira y el muro sube el turno
                # siguiente. Con cualquiera de las rutas de BUSQUEDA (a/b/c) la
                # energia esta practicamente asegurada y no hace falta.
                if not _ps_can_find_energy and not _ps_conserva_salida(_psb):
                    continue
                _ps_cur = len(_psb.energies)
                _ps_deficit = _ps_req - _ps_cur
                # A UNA sola adjuncion de su requisito (el bucle normal ya cubre
                # a los que atacan ya mismo). Mas lejos = no es "casi listo".
                if _ps_deficit <= 0 or _ps_deficit > _ps_unit:
                    continue
                _ps_after = _ps_cur + _ps_unit
                if _psb.id == Hydrapple_ex:
                    _ps_dmg = 30 + 30 * total_grass
                elif _psb.id == Teal_Mask_Ogerpon_ex:
                    _ps_dmg = 30 + 30 * (_ps_after + _ps_opa_en)
                elif _psb.id == Dipplin:
                    _ps_dmg = 20 * max(0, bench_count - 1)
                elif _psb.id == Tapu_Bulu:
                    _ps_dmg = 220
                elif _psb.id == Meganium:
                    _ps_dmg = 140
                elif _psb.id == Fezandipiti_ex:
                    _ps_dmg = 100
                else:
                    _ps_dmg = 10
                _ps_bd = card_table.get(_psb.id)
                if (_ps_bd is not None and _ps_weak is not None
                        and getattr(_ps_bd, 'energyType', None) == _ps_weak):
                    _ps_dmg *= 2
                if _ps_dmg < _ps_remain:
                    continue  # aun completado no remata al activo rival
                _ps_hp = getattr(_psb, 'hp', 0) or 0
                # PREMIOS ANTES QUE VIDA (user): entre dos cuerpos que quedan a
                # la MISMA distancia de rematar el proximo turno, sube el que
                # cede MENOS premios si lo noquean. Como el remate es nuestro y
                # va primero, la vida es un desempate secundario; lo que se
                # arriesga de verdad es el premio. Coherente con
                # [[alakazam-atacar-con-1-premio-no-ex]] y
                # [[promover-supervivencia-y-menos-premios]].
                _ps_key = (-_ps_deficit, -prize_count(_psb), _ps_hp, _ps_dmg)
                if _ps_best_key is None or _ps_key > _ps_best_key:
                    _ps_best_key = _ps_key
                    _promote_setup_ko_attacker = _psb
    # ------------------------------------------------------------------

    # --- SUPERVIVENCIA AL PROMOVER (user, registro_005 paso 64 vs Archaludon,
    # PERDIDA) -----------------------------------------------------------------
    # Al elegir que cuerpo sube al activo, lo PRIMERO es si aguanta el ataque
    # del activo rival. En aquel turno Archaludon ex pegaba 220: solo el
    # Hydrapple ex (330 PV) sobrevivia, y el agente subio un Teal Mask Ogerpon ex
    # de 210 PV con SEIS energias (4557 frente a 259) -- moria sin haber noqueado
    # (Myriad proyectaba 300 contra 400 PV) y regalaba 2 premios y toda la carga.
    #
    # Dos criterios, en este orden, deck-agnosticos:
    #   1) si ALGUN candidato sobrevive, los que mueren se penalizan;
    #   2) si NINGUNO sobrevive, gana el que entregue MENOS premios.
    #
    # Excepcion: un candidato que NOQUEA al activo rival conserva su score. Ahi
    # el intercambio (cobrar premio aunque muera) es correcto y ya lo gobiernan
    # las reglas de arriba; esta regla solo ordena a los que NO cobran nada.
    _promo_op_act = _active_of(op_state)
    _promo_survivors = 0
    _promo_min_prize = None

    def _promo_survives(_pk):
        """El candidato aguanta el ataque proyectado del activo rival."""
        if _promo_op_act is None or _pk is None:
            return True
        return _op_active_attack_damage_to(_promo_op_act, _pk) < (_pk.hp or 0)

    def _promo_kos_op(_pk):
        """El candidato NOQUEA al activo rival tras promoverlo (con su energia
        actual mas el adjunte manual si aun queda por gastar)."""
        if _promo_op_act is None or _pk is None:
            return False
        _pe = len(_pk.energies) * _grass_mult()
        if not state.energyAttached and hand_counts.get(Basic_Grass_Energy, 0) >= 1:
            _pe += _grass_attach_unit()
        # El candidato SALE de la banca al promoverlo, asi que el ataque que
        # escala con nuestra banca (Do the Wave de Dipplin) cuenta un cuerpo
        # MENOS. Con `bench_count` crudo, el Dipplin del log 88971843 paso 117
        # proyectaba 20x4 = 80 y "noqueaba" al Dipplin rival de 80 PV: eso le
        # daba el PROMO_KO_BONUS de 20000 y ademas saltaba la penalizacion por
        # condenado, subiendo un cuerpo de 80 PV a un golpe de 100. El real es
        # 20x3 = 60. Los otros dos sitios que proyectan a un promovido
        # (`_prom_bench_after` y `_promote_setup_ko_attacker`) ya restaban 1.
        _pbase = _attacker_base_damage(
            _pk.id, _promo_op_act, _pe, grass_scale=total_grass,
            teal_self_energy=_pe, bench_count=max(0, bench_count - 1))
        if _pbase <= 0:
            return False
        _peff = _our_effective_damage(
            _pk, _promo_op_act, _pbase, ESTADO.meganium_in_play,
            neutralization_zone_active)
        return _peff >= (_promo_op_act.hp or 0)

    if (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE):
        for _pb in my_state.bench:
            if _pb is None:
                continue
            if _promo_survives(_pb):
                _promo_survivors += 1
            _pp = prize_count(_pb)
            if _promo_min_prize is None or _pp < _promo_min_prize:
                _promo_min_prize = _pp
    # ------------------------------------------------------------------

    # Regla (user, log 86345562 p55): al PROMOVER (retiro o KO) cuando NINGUN
    # cuerpo de la banca puede atacar este turno y tenemos Lillie's Determination
    # en mano para refrescar la mano, preferimos subir un BASICO de 1 premio
    # (Applin es la prioridad) en vez de un ex de 2 premios (Meowth ex / Ogerpon
    # ex). Asi entregamos solo 1 premio como muro mientras rehacemos la mano con
    # Lillie's y conservamos los ex -y su energia ya cargada- a salvo en la banca
    # para atacar mas tarde. Solo aplica si el activo rival NO es inmune a ex ni
    # a habilidad (esos matchups ya suben un ex-muro con su propia logica).
    _ref_grass_attachable = (
        hand_counts.get(Basic_Grass_Energy, 0) >= 1
        or (hand_counts.get(Night_Stretcher, 0) >= 1
            and discard_counts.get(Basic_Grass_Energy, 0) >= 1))
    _ref_forced_promote = not (my_state.active and my_state.active[0] is not None)
    _ref_can_attach = _ref_grass_attachable and (
        not state.energyAttached or _ref_forced_promote)
    _refresh_no_attacker = True
    for _rbp in my_state.bench:
        if _rbp is None or not isinstance(_rbp, Pokemon):
            continue
        if _rbp.id not in MAIN_ATTACKERS:
            continue
        _rbp_e = len(_rbp.energies)
        if _can_attack_eff(_rbp.id, _rbp_e) or (
                _ref_can_attach
                and _can_attack_eff(_rbp.id, _rbp_e + _grass_attach_unit())):
            _refresh_no_attacker = False
            break
    _refresh_promote_prefer_basic = (
        (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
        and not _lucario_sac_context
        and not _lucario_ko_prefer_basic
        and _promote_setup_ko_attacker is None
        and hand_counts.get(Lillie_Determination, 0) >= 1
        and not op_has_ex_immune_active
        and not op_has_ability_immune_active
        and _refresh_no_attacker)
    # ------------------------------------------------------------------

    # --- Matchup Crustle + Mega Kangaskhan ex: reparto de atacantes (user) ---
    # Contra este mazo hay que atacar al Mega Kangaskhan ex (u otro objetivo NO
    # inmune a ex) con NUESTRO ex, y RESERVAR los no-ex -sobre todo Tapu Bulu,
    # que noquea a Crustle de un solo ataque- para cuando Crustle este activo.
    # Si el activo rival es Crustle (inmune a ex) se sube un no-ex; si no hay
    # ningun ex nuestro capaz de atacar, se usa un basico igualmente.
    _cm_matchup = ESTADO.op_is_crustle_deck and ESTADO.op_has_mega_kangaskhan
    _cm_have_ex_attacker = False
    _cm_vs_ex_target = (_cm_matchup and not op_has_ex_immune_active
                        and op_state.active and op_state.active[0] is not None)
    if _cm_vs_ex_target:
        for _cmp in my_state.bench:
            if _cmp is None or not isinstance(_cmp, Pokemon):
                continue
            if _cmp.id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex):
                _cm_req = ESTADO.ATTACK_ENERGY_REQ.get(_cmp.id)
                if _cm_req is None:
                    continue
                _cm_e = len(_cmp.energies)
                if (_cm_e < _cm_req and not state.energyAttached
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                    _cm_e += _grass_attach_unit()
                if _cm_e >= _cm_req:
                    _cm_have_ex_attacker = True
                    break
    # Solo repartimos (reservar Tapu Bulu / priorizar ex) cuando el activo rival
    # NO es inmune a ex y tenemos un ex capaz de atacarlo este turno.
    _cm_use_ex = _cm_vs_ex_target and _cm_have_ex_attacker

    # =================================================================
    # GRAND TREE: plan del turno (ver la cabecera del bloque `_gt_*`).
    #
    # Se calcula SIEMPRE que el estadio este en mesa, no solo cuando el menu
    # ofrece la habilidad: el plan tambien lo consultan (a) la retencion del
    # Forest of Vitality -- "primero la habilidad, DESPUES el reemplazo" -- y
    # (b) las sub-selecciones que abre la habilidad (que Basico evoluciona, que
    # carta se trae del mazo), que llegan en llamadas posteriores a `agent()`
    # con otro `context`.
    #
    # `_gt_ability_slot` = posicion de la opcion ABILITY del estadio en ESTE
    # menu. Su ausencia significa que la habilidad ya se uso este turno (el
    # motor del juego deja de ofrecerla), asi que el Forest deja de esperar.
    # Se identifica por la CARTA (id 1249), no por el area, para no depender de
    # como el simulador etiquete la habilidad de un estadio.
    # =================================================================
    _gt_veta_etapa_ex = (ESTADO.op_is_crustle_deck or op_is_sylveon_deck
                         or op_has_ex_immune_active or op_has_ex_immune_bench)
    _gt_planes_turno = (
        _gt_planes(my_state, ESTADO.CARTAS_ACTIVAS_EN_MAZO, field_counts,
                   _our_first_turn, veta_etapa_ex=_gt_veta_etapa_ex,
                   activo_condenado=(active_ko_likely or _active_doomed_real))
        if grand_tree_in_play else [])
    _gt_plan = _gt_planes_turno[0] if _gt_planes_turno else None

    _gt_ability_slot = None
    if grand_tree_in_play and context == SelectContext.MAIN:
        for _gt_o in select.option:
            if _gt_o.type != OptionType.ABILITY:
                continue
            _gt_c = get_card(obs, _gt_o.area, _gt_o.index, my_index)
            if _gt_c is not None and _gt_c.id == Grand_Tree:
                _gt_ability_slot = (_gt_o.area, _gt_o.index)
                break
    _gt_ability_pending = (_gt_ability_slot is not None and _gt_plan is not None)

    # Confirmaciones ("¿buscar?") emitidas MIENTRAS se resuelve la habilidad.
    _gt_prompt_si_no = (select.effect is not None
                        and select.effect.id == Grand_Tree)

    # Ranking de Basicos que abren cadena (fetch + bajada desde la mano). Solo
    # tiene sentido con el estadio ya en mesa o con una copia en la mano lista
    # para bajarse: sin estadio, la cadena no es gratis y mandan las reglas
    # normales de desarrollo.
    _gt_estadio_disponible = (grand_tree_in_play
                              or (hand_counts.get(Grand_Tree, 0) >= 1
                                  and not state.stadiumPlayed))
    _gt_ranking_basicos = (
        _gt_basicos_deseados(ESTADO.CARTAS_ACTIVAS_EN_MAZO, field_counts,
                             veta_etapa_ex=_gt_veta_etapa_ex)
        if _gt_estadio_disponible else {})
    # Solo se BUSCA un Basico si no hay ya uno en juego que sirva de raiz el
    # proximo turno (aqui NO se filtra por `appearThisTurn`: el que baje hoy
    # sera evolucionable manana) y si queda hueco en la banca.
    _gt_raiz_en_juego = any(field_counts.get(b, 0) >= 1
                            for b in _gt_ranking_basicos)
    _gt_quiere_basico = (bool(_gt_ranking_basicos) and not _gt_raiz_en_juego
                         and bench_count < 5)

    # PESCA DE REMATE (ver `_pesca_de_remate`): con Lillie's Determination en
    # mano y el Supporter del turno libre, ¿hay algun ataque que HOY solo
    # dependa de que el robo traiga Plantas? Se calcula una sola vez, solo en
    # MAIN (fuera de ahi no hay jugada de Supporter que decidir) y solo con el
    # refresco en mano, para no pagar la hipergeometrica en cada opcion.
    _pesca_remate = None
    if (context == SelectContext.MAIN
            and not state.supporterPlayed
            and hand_counts.get(Lillie_Determination, 0) >= 1):
        _pesca_remate = _pesca_de_remate(
            my_state, op_state, state, hand_counts, field_counts,
            grass_en_mazo=ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                Basic_Grass_Energy, {}).get(ESTADO_MAZO, 0),
            robo=_robo_de_lillie(my_prize),
            baraja_la_mano=True,
            meganium_in_play=ESTADO.meganium_in_play,
            neutralization_zone_active=neutralization_zone_active,
            total_grass=total_grass, bench_count=bench_count,
            puede_cambiar=can_switch, has_switch_card=has_switch_card,
            habilidades_apagadas=meowth_ability_lock)

    # Contexto de decision (refactor Prioridad 1): entradas invariantes que
    # consumen los scorers extraidos `_score_*`. Se construye una sola vez.
    ctx = DecisionContext(
        state=state,
        my_state=my_state,
        op_state=op_state,
        hand_counts=hand_counts,
        field_counts=field_counts,
        supp_values=_supp_values,
        cartas_en_mazo=ESTADO.CARTAS_ACTIVAS_EN_MAZO,
        field_at_turn_start=ESTADO._field_at_turn_start,
        bench_count=bench_count,
        my_hand_len=len(my_state.hand or []),
        my_prize=my_prize,
        op_prize=op_prize,
        op_hand_count=getattr(op_state, 'handCount', 0),
        meganium_in_play=ESTADO.meganium_in_play,
        forest_in_play=ESTADO.forest_in_play,
        itchy_pollen_active=itchy_pollen_active,
        has_hydrapple=has_hydrapple,
        watchtower_in_play=watchtower_in_play,
        festival_lead_hostil=_festival_lead_hostil,
        meowth_ability_lock=meowth_ability_lock,
        neutralization_zone_active=neutralization_zone_active,
        mega_line_active=_mega_line_active,
        active_needs_energy=_active_needs_energy,
        evolve_possible_in_play=_evolve_possible_in_play,
        energy_starved_low_draw=_energy_starved_low_draw,
        pp_playable_in_hand=_pp_playable_in_hand,
        can_attack=can_attack,
        best_supp_in_hand_val=_best_supp_in_hand_val,
        best_supp_in_mazo_val=_best_supp_in_mazo_val,
        op_is_alakazam_deck=op_is_alakazam_deck,
        op_is_hop_deck=op_is_hop_deck,
        op_is_comfey_deck=op_is_comfey_deck,
        op_active_is_dunsparce=op_active_is_dunsparce,
        op_has_ability_immune_active=op_has_ability_immune_active,
        op_has_ex_immune_active=op_has_ex_immune_active,
        op_has_ex_immune_bench=op_has_ex_immune_bench,
        op_is_control_deck=op_is_control_deck,
        op_is_slowking_deck=op_is_slowking_deck,
        op_is_gardevoir_deck=op_is_gardevoir_deck,
        op_is_zoroark_deck=op_is_zoroark_deck,
        op_is_aggro_deck=op_is_aggro_deck,
        op_is_beedrill_deck=op_is_beedrill_deck,
        op_is_crustle_deck=ESTADO.op_is_crustle_deck,
        op_is_cornerstone_deck=ESTADO.op_is_cornerstone_deck,
        op_is_fire_deck=op_is_fire_deck,
        op_is_mirror=op_is_mirror,
        op_kang_ko_target=op_kang_ko_target,
        stadium_id=stadium_id,
        ko_last_turn=ESTADO.ko_last_turn,
        our_first_turn=_our_first_turn,
        active_cant_attack=_active_cant_attack_this_turn,
        bdg_retreat_ko=_bdg_retreat_ko,
        supporter_boost=(500 if itchy_pollen_active else 0),
        we_go_first=ESTADO.we_go_first,
        budew_op_index=budew_op_index,
        budew_on_op_field=budew_on_op_field,
        item_lock_incoming=_item_lock_incoming,
        lucario_sac_pivot=_lucario_sac_pivot,
        win_via_boss_gust=_win_via_boss_gust,
        gust_2prize_via_boss=_gust_2prize_via_boss,
        ex_immune_wall_ko_ready=_ex_immune_wall_ko_ready,
        boss_win_via_bench=_boss_win_via_bench,
        boss_dodge_redirect=_boss_dodge_redirect,
        boss_defensive_gust=_boss_defensive_gust,
        boss_deny_alakazam_line=_boss_deny_alakazam_line,
        boss_low_value_gust=_boss_low_value_gust,
        boss_active_threat_dominates=_bo_act_threat_dom,
        boss_prize_rank=_boss_prize_rank,
        win_ko_active_via_promote=_win_ko_active_via_promote,
        boss_ko_threat_preevo=_boss_ko_threat_preevo,
        active_ko_likely=active_ko_likely,
        active_doomed_real=_active_doomed_real,
        ability_unlock_retreat_ko=_ability_unlock_retreat_ko,
        ability_unlock_retreat_attack=_ability_unlock_retreat_attack,
        has_ready_bench_attacker=_bench_attacker_ready,
        grand_tree_in_play=grand_tree_in_play,
        grand_tree_ability_pending=_gt_ability_pending,
        meowth_ld_free=_meowth_ld_free,
        pesca_remate=_pesca_remate,
    )

    # =================================================================
    # EL SUPPORTER DEL TURNO YA ESTA EN LA MANO (user, registro_004 paso 36 vs
    # Alakazam, GANADA con error). Solo se juega UN Supporter por turno, asi que
    # ANTES de bajar el Meowth ex hay que decidir CUAL Supporter se va a jugar:
    # si el ganador es uno que YA tenemos en la mano, el que traiga el Last-Ditch
    # Catch NO se puede jugar hoy y el Meowth solo regala un cuerpo de 2 premios
    # en la banca.
    #
    # En aquel turno: Ogerpon ex activo con 1 energia, y en la mano Boss's +
    # Xerosic's Machinations + Meowth ex. El agente bajo el Meowth ex (motor
    # `_meowth_devel_lillie`, 21800), su fetch trajo Lillie's Determination...
    # y acto seguido jugo el XEROSIC que ya tenia en la mano (7300 > 5000 de la
    # Lillie's). La Lillie's recien buscada se quedo muerta en la mano y el
    # cuerpo de 2 premios en la banca, gratis, para nada.
    #
    # Por que no bastaba `_meowth_fetch_redundante`: ese veto solo mira si el
    # fetch traeria una carta que YA esta en la mano (una COPIA inutil). Aqui el
    # fetch traia algo distinto y util -- el problema es que compite por el
    # UNICO hueco de Supporter del turno y lo pierde. Son dos fallos distintos
    # del mismo recurso.
    #
    # Y por que no bastaba comparar en la escala del fetch: las dos escalas
    # ORDENAN AL REVES. `_REGLAS_MEOWTH_FETCH` puntuo Lillie's 1200 vs Xerosic
    # <=150 (la rama `atasco_sin_lillie_en_mano`), mientras el scorer de jugada
    # puntua Xerosic 7300 vs Lillie's 5000. La escala que DECIDE es la de
    # jugada, asi que la prediccion tiene que hacerse ahi: ambos lados se miden
    # con `_supp_play_score`, sobre la mano HIPOTETICA de despues del fetch
    # (- el Meowth que se baja, + el Supporter que llega), que es el tablero
    # exacto en el que se resolvera la eleccion. Deck-agnostico: no nombra
    # cartas, solo cuenta Supporters y sus scorers reales.
    #
    # Solo veta BAJAR el Meowth ex. La HABILIDAD de un Meowth ya en juego sigue
    # buscando: el Last-Ditch Catch es gratis y guardar el Supporter para el
    # proximo turno es ganancia neta (a diferencia de la copia redundante de
    # `_meowth_skip_fetch`, que no aporta nada nunca).
    _meowth_supp_turno_id, _meowth_supp_turno_val = None, 0
    _meowth_fetch_play_val = 0
    _meowth_fetch_pierde_el_turno = False
    if (context == SelectContext.MAIN
            and not state.supporterPlayed
            and not _our_first_action_turn
            and hand_counts.get(Meowth_ex, 0) >= 1
            and _meowth_fetch_id is not None
            and not _meowth_fetch_redundante):
        # defaultdict, no dict: los scorers acceden por corchete (p.ej.
        # hand_counts[Basic_Grass_Energy]) y un dict pelado reventaria.
        _mw_hand_post = defaultdict(int, hand_counts)
        _mw_hand_post[Meowth_ex] = max(0, _mw_hand_post.get(Meowth_ex, 0) - 1)
        _mw_hand_post[_meowth_fetch_id] = (
            _mw_hand_post.get(_meowth_fetch_id, 0) + 1)
        # `my_hand_len` no cambia: se baja una carta (Meowth) y entra otra
        # (el Supporter buscado).
        _ctx_post_fetch = _dc_replace(ctx, hand_counts=_mw_hand_post)
        _meowth_fetch_play_val = _supp_play_score(
            _ctx_post_fetch, _meowth_fetch_id)
        _meowth_supp_turno_id, _meowth_supp_turno_val = (
            _mejor_supporter_de_mano(_ctx_post_fetch, _mw_hand_post))
        _meowth_fetch_pierde_el_turno = (
            _meowth_supp_turno_id is not None
            and _meowth_supp_turno_id != _meowth_fetch_id
            and _meowth_supp_turno_val >= _meowth_fetch_play_val)

    # Teal Dance PRECEDE al adjunte manual (user, registro_004 paso 28, vs
    # Mega Starmie): si un Teal Mask Ogerpon ex TODAVIA tiene su habilidad Teal
    # Dance disponible este turno (aparece una opcion ABILITY para ese mismo
    # Ogerpon), no se debe cargar energia MANUALMENTE sobre el. Teal Dance
    # adjunta una Planta Y ademas ROBA una carta, asi que tiene prioridad: el
    # adjunte manual se pospone hasta que la habilidad se haya usado. Aqui
    # recopilamos las posiciones (area, index) de los Ogerpon que aun pueden
    # usar Teal Dance para vetar en la rama ATTACH el adjunte manual a ese slot.
    _teal_dance_slots = set()
    if context == SelectContext.MAIN:
        for _tds_o in select.option:
            if _tds_o.type == OptionType.ABILITY:
                _tds_card = get_card(obs, _tds_o.area, _tds_o.index, my_index)
                if _tds_card is not None and _tds_card.id == Teal_Mask_Ogerpon_ex:
                    _teal_dance_slots.add((_tds_o.area, _tds_o.index))

    # Pivote vs Alakazam (user, registro_010 paso 127, PERDIDA): contra un mazo de
    # Alakazam preferimos atacar con cuerpos de UN premio (Meganium, Tapu Bulu) en
    # vez de con un ex (2 premios). Si el ACTIVO es un ex NUESTRO que va a atacar,
    # pero hay en banca un atacante NO-ex de 1 premio (Meganium/Tapu Bulu) LISTO
    # que NOQUEA al activo rival, y el ex activo puede pagar su coste de retirada,
    # RETIRAMOS el ex y promovemos al cuerpo de 1 premio para atacar: si luego nos
    # lo noquean cedemos 1 premio en vez de 2. NO aplica si atacar con el ex GANA
    # la partida (entonces se ataca y punto). La promocion posterior elige el
    # cuerpo de 1 premio via `_best_promote_card` (rama vs Alakazam de arriba).
    _alakazam_pivot_1prize = False
    if (context == SelectContext.MAIN and op_is_alakazam_deck
            and can_attack and my_state.active and my_state.active[0] is not None):
        _akp_act = my_state.active[0]
        _akp_op = op_state.active[0] if op_state.active else None
        if (_akp_act.id in OUR_EX_IDS and _akp_op is not None
                and not op_has_ex_immune_active):
            _akp_op_hp = _akp_op.hp or 0
            _akp_rc = RETREAT_COST.get(_akp_act.id, 1)
            _akp_can_retreat = len(_akp_act.energies) >= _akp_rc
            _akp_bench_ko_1prize = False
            for _akp_bp in (my_state.bench or []):
                # Cualquier cuerpo de UN premio (no-ex) que noquee sirve para el
                # pivote: Dipplin/Meganium/Tapu Bulu/... (user, registro_005
                # paso 56 vs Alakazam, PERDIDA: Dipplin cargado con Do the Wave
                # 20 x banca noquea al Abra activo -- antes la whitelist
                # (Meganium, Tapu_Bulu) lo excluia y se atacaba con el Ogerpon
                # ex, exponiendo 2 premios al Powerful Hand). Los cuerpos sin
                # ataque modelado caen por `_akp_base <= 0`.
                if _akp_bp is None or prize_count(_akp_bp) != 1:
                    continue
                _akp_be = len(_akp_bp.energies)
                if not _can_attack_eff(_akp_bp.id, _akp_be):
                    continue
                _akp_base = _attacker_base_damage(
                    _akp_bp.id, _akp_op, _akp_be * _grass_mult(),
                    grass_scale=0, teal_self_energy=_akp_be, bench_count=bench_count)
                if _akp_base <= 0:
                    continue
                if _our_effective_damage(_akp_bp, _akp_op, _akp_base,
                                         ESTADO.meganium_in_play,
                                         neutralization_zone_active) >= _akp_op_hp:
                    _akp_bench_ko_1prize = True
                    break
            _akp_prizes_from_ko = prize_count_op(_akp_op)
            _akp_my_left = len([p for p in (my_state.prize or []) if p is None])
            _akp_win_now = _akp_my_left <= _akp_prizes_from_ko
            if _akp_can_retreat and _akp_bench_ko_1prize and not _akp_win_now:
                _alakazam_pivot_1prize = True

    # Indices de adjuntes manuales que CEDEN ante una Teal Dance pendiente
    # (ver la regla en la rama OptionType.ATTACH): ademas del cap de score, se
    # les deja el tier 0 del orden de jugada para que el score decida.
    _attach_cede_a_teal_dance = set()

    # Vetos de ORDEN sobre habilidades, DIFERIBLES: {indice de opcion:
    # (score_real, (ids de las cartas que deben jugarse antes, ...))}. Los llena
    # la rama OptionType.ABILITY cuando la habilidad es buena pero otra carta de
    # la mano debe jugarse ANTES; el bloque "REVOCAR VETOS DE ORDEN" (mas abajo)
    # los levanta si ese "antes" no va a ocurrir en este menu. Sin esta capa un
    # veto de orden se comia habilidades gratuitas de UNA VEZ POR TURNO cuyo
    # bloqueador nunca llegaba a jugarse (registro_006 paso 78).
    _ability_order_veto = {}

    # LANA'S AID: lectura de mesa para la RECUPERACION (contexto TO_HAND).
    # `_lana_plan` dice cuanta Planta sabe usar el campo y si alguna desbloquea
    # un ataque hoy; `_lana_orden_planta` numera las opciones de Planta del menu
    # (0, 1, 2...) para que solo las PRIMERAS `demanda` cobren la banda alta: los
    # scores se calculan por carta, asi que sin el ordinal las 4 copias de Planta
    # empatarian y arrasarian el menu aunque la mesa solo supiera usar una.
    _lana_plan = None
    _lana_orden_planta = {}
    if (select.effect is not None and select.effect.id == Lanas_Aid
            and context == SelectContext.TO_HAND):
        _lana_plan = _plan_de_planta(my_state, state, field_counts, hand_counts,
                                     tope=select.maxCount or 1,
                                     puede_cambiar=can_switch,
                                     habilidades_apagadas=meowth_ability_lock)
        _lana_n = 0
        for _lana_i, _lana_o in enumerate(select.option):
            if _lana_o.type != OptionType.CARD:
                continue
            _lana_c = get_card(obs, _lana_o.area, _lana_o.index,
                               getattr(_lana_o, 'playerIndex', my_index))
            if _lana_c is not None and _lana_c.id == Basic_Grass_Energy:
                _lana_orden_planta[_lana_i] = _lana_n
                _lana_n += 1

    scores = []
    # Contexto de puntuacion: se construye UNA VEZ, no por opcion. Se puebla
    # desde locals() porque parte de estas variables solo se ligan en ciertas
    # ramas del turno; y de globals() porque algunas funciones y tablas que la
    # cadena consulta siguen definidas a nivel de modulo en main.py.
    _tcp = PuntuacionCtx()
    _loc = {**globals(), **locals()}
    for _campo in PuntuacionCtx.__dataclass_fields__:
        if _campo in _loc:
            setattr(_tcp, _campo, _loc[_campo])
    for o in select.option:
        score = 0

        score = puntuar_opcion(_tcp, o, score)
        if score is _SALTAR:
            continue

        scores.append(score)

    # El contexto se puebla desde `locals()`, no con kwargs explicitos: algunas
    # de estas variables solo se ligan en ciertas ramas (`_b`, `i`, ...). Pasarlas
    # a mano forzaria su evaluacion y daria NameError justo en los caminos donde
    # el codigo original ni siquiera las lee -- el propio corte inventaria un
    # fallo que no existe. Lo que no este ligado queda en None, y la misma
    # guarda que impedia leerlo antes lo sigue impidiendo.
    _tc = TurnoCtx()
    _locales = locals()
    for _campo in TurnoCtx.__dataclass_fields__:
        if _campo in _locales:
            setattr(_tc, _campo, _locales[_campo])
    return finalizar(_tc)
