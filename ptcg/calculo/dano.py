"""Dano: base de nuestros atacantes, KO no garantizado y snipe.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.calculo.carta import prize_count_op
from ptcg.estado.agente import ESTADO
from ptcg.cartas.tablas import attack_table, card_table
from ptcg.cartas.ids import ABILITY_IMMUNE_IDS, Alakazam_ex, Brave_Bangle, DO_THE_WAVE_ATTACK_ID, Dipplin, Drednaw, EX_IMMUNE_IDS, FULL_HP_SURVIVE_IDS, Farigiraf_ex, Fezandipiti_ex, Hydrapple_ex, Maximum_Belt, Meganium, OUR_ABILITY_IDS, OUR_BASIC_EX_IDS, OUR_EX_IDS, POWERFUL_HAND_ATTACK_ID, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calculo.energia import _grass_mult
from cg.api import EnergyType
from typing import NamedTuple
from ptcg.cartas.ids import Mega_Hawlucha_ex, Survival_Brace


def _powerful_hand_proyectado(op_hand_count: int) -> int:
    """Dano de Powerful Hand proyectado al PROXIMO turno rival.

    Mismo modelo que `_op_active_attack_damage_to`: 20 x (mano + 2), donde el
    +2 es el robo del turno + el Psychic Draw de evolucionar. Vive suelto (y no
    detras de "su activo es un Alakazam") porque el Alakazam que rematara puede
    estar todavia en la BANCA rival: en su turno promueve, evoluciona y ataca.
    Dentro del matchup `op_is_alakazam_deck` es la unica linea atacante del
    mazo (Abra -> Kadabra -> Alakazam), asi que proyectarla siempre es correcto.
    """
    return 20 * (max(0, op_hand_count) + 2)


def _ko_no_garantizado(op_pokemon):
    """True si el KO del defensor NO esta garantizado aunque el dano proyectado
    sea letal: Mega Hawlucha ex (Tenacious Body: moneda, con cara sobrevive a
    10 PV) o Survival Brace (tool 1155: a vida completa sobrevive a 10 PV).

    Lo consultan SOLO los evaluadores de REMATE que declaran victoria segura
    (`wins_now`, SCORE_WIN_GAME, `_active_attack_wins_now`): contra estos
    cuerpos "ganar este turno" puede fallar y regalar el turno de vuelta. El
    dano/can_ko normal NO se toca (atacarlos sigue siendo la mejor jugada la
    mayoria de veces). Los que sobreviven a vida completa via Sturdy/Resolute
    Heart (FULL_HP_SURVIVE_IDS) no necesitan este predicado porque
    `_our_effective_damage` ya capa su dano a hp-10 y el can_ko sale False."""
    if op_pokemon is None:
        return False
    if op_pokemon.id == Mega_Hawlucha_ex:
        return True
    if (op_pokemon.hp == op_pokemon.maxHp
            and any(getattr(_t, 'id', 0) == Survival_Brace
                    for _t in (getattr(op_pokemon, 'tools', None) or []))):
        return True
    return False


class _ProjTarget(NamedTuple):
    """Objetivo ligero para proyectar el dano rival contra un cuerpo que aun no
    esta en juego (p.ej. la EVOLUCION de una pre-evo de banca). Solo necesita
    `id` (para debilidad/resistencia via card_table); `tools`/`energies` vacios."""
    id: int
    tools: tuple = ()
    energies: tuple = ()


def _snipe_targets(op_state):
    """Pokemon rivales alcanzables por un ataque-snipe: activo + banca."""
    out = []
    if op_state is None:
        return out
    for _p in (list(getattr(op_state, 'active', None) or [])
               + list(getattr(op_state, 'bench', None) or [])):
        if _p is not None:
            out.append(_p)
    return out


def _ventana_de_regalo(pokemon, es_activo, golpe_proyectado, incluir_movible=True):
    """Dano que el rival puede concentrar sobre `pokemon` antes de nuestro
    proximo turno. Un cuerpo con `hp <= _ventana_de_regalo(...)` es un premio
    que el rival puede cobrar cuando quiera.

    `golpe_proyectado` es el ataque que le llega: `estimated_op_damage` al
    ACTIVO, `_op_bench_snipe_dmg` a la banca. A eso se le suman las dos fuentes
    que no son ataque (ver "LA VENTANA DE REGALO"):

      * el goteo de Freezing Shroud, que solo paga quien tiene HABILIDAD;
      * el dano DIRIGIBLE de Adrena-Brain, que llega a cualquier cuerpo.

    `incluir_movible=False` devuelve la ventana **GARANTIZADA**: solo lo que
    llega SI O SI. La distincion importa porque el dano movible es ELASTICO --
    el rival lo aima donde quiera, pero solo mata a UN cuerpo por turno. Medir
    siempre con el techo dejaria a media mesa "condenada" y apagaria la
    curacion igual que la medias con el snipe solo.

    Sin Froslass ni Munkidori en mesa ambos terminos son 0 y las dos ventanas
    son el golpe proyectado de siempre."""
    pid = getattr(pokemon, 'id', 0)
    # Tera de Teal Mask Ogerpon ex: EN BANCA previene el dano de ATAQUES (y por
    # tanto el snipe automatico), nunca los contadores puestos o movidos.
    golpe = 0 if (not es_activo and pid == Teal_Mask_Ogerpon_ex) \
        else max(0, golpe_proyectado or 0)
    chip = ESTADO._op_chip_per_round if pid in OUR_ABILITY_IDS else 0
    return golpe + chip + (ESTADO._op_movable_dmg if incluir_movible else 0)


def _our_effective_damage(my_pokemon, op_pokemon, base_damage,
                          meganium_active=False, neutralization_zone=False):
    if op_pokemon is None or base_damage is None:
        return 0
    data = card_table.get(op_pokemon.id)
    if data is None:
        return max(0, base_damage)
    my_is_ex = my_pokemon.id in OUR_EX_IDS
    my_has_ability = my_pokemon.id in OUR_ABILITY_IDS
    is_fez = (my_pokemon.id == Fezandipiti_ex)
    damage = base_damage

    if op_pokemon.id in EX_IMMUNE_IDS and my_is_ex:
        return 0

    _op_has_rule_box = bool(getattr(data, 'ex', False) or getattr(data, 'megaEx', False))
    if neutralization_zone and my_is_ex and not _op_has_rule_box:
        return 0

    if op_pokemon.id in ABILITY_IMMUNE_IDS and my_has_ability:
        return 0

    # Farigiraf ex ("Armor Tail"): inmune al dano de ataques de BASICOS ex.
    # Solo Hydrapple ex (Etapa 2) y los no-ex lo danan (plan jul 2026, P1.6).
    if op_pokemon.id == Farigiraf_ex and my_pokemon.id in OUR_BASIC_EX_IDS:
        return 0

    if not is_fez:
        if data.weakness == EnergyType.GRASS:
            damage *= 2
        elif data.resistance == EnergyType.GRASS:
            damage -= 30

    if op_pokemon.id == Drednaw and damage >= 200:
        return 0

    # Sturdy (Crustle 533) / Resolute Heart (Pikachu ex 210): a vida COMPLETA
    # sobreviven al golpe letal quedandose a 10 PV -> cap a hp-10 (P0.1).
    if (op_pokemon.id in FULL_HP_SURVIVE_IDS and
            op_pokemon.hp == op_pokemon.maxHp and damage >= op_pokemon.hp):
        damage = op_pokemon.hp - 10

    return max(0, int(damage))


def _tiene_rule_box(card_id) -> bool:
    """¿La carta tiene Rule Box (Pokemon ex / Mega ex / V ...)?

    Lo consultan las tools condicionadas a "si el portador NO tiene Rule Box"
    (Brave Bangle). Ante una carta desconocida devuelve True -> el bonus NO se
    suma: preferimos no inventarnos dano sobre datos que no podemos leer.
    """
    _d = card_table.get(card_id)
    if _d is None:
        return True
    return bool(getattr(_d, 'ex', False) or getattr(_d, 'megaEx', False))


def _op_active_attack_damage_to(op_active, target, op_hand_count=None):
    """Maximo dano IMPRESO que el activo rival puede hacerle a `target`.

    Resuelve los IDs de ataque via `attack_table` (los `card.attacks` son ints,
    no objetos, por eso `_op_best_damage_vs` -que hace getattr(id,'damage')- da
    siempre 0). Solo considera ataques cuyo coste (nº de energias) el activo
    rival puede pagar, asumiendo 1 energia adjunta el proximo turno. Aplica la
    debilidad/resistencia del OBJETIVO frente al tipo de energia del atacante
    rival. Devuelve 0 si el ataque no se puede leer (dano None, p.ej. ataques
    que ponen contadores) -> el llamador queda conservador.

    EXCEPCION (sugerencia 1 anti-Alakazam): Powerful Hand (Alakazam 743,
    attackId 1072) tiene dano impreso 0 pero real = 20 x carta en la mano
    rival. Sin modelarlo, TODOS los pivotes defensivos (muro Hydrapple,
    sacrificio de ex fragil, promociones) creian que Alakazam pega 0 y nunca
    disparaban en el matchup donde mas los necesitamos. Si el llamador pasa
    `op_hand_count`, se proyecta `20 x (mano + 2)` (+2 = robo del turno +
    Psychic Draw al evolucionar); sin el parametro se mantiene el 0
    conservador de siempre.

    EXCEPCION 2 (log 88971843 paso 117, vs Festival Lead, PERDIDA): Do the Wave
    (Dipplin 93, attackId 115) tambien tiene dano impreso 0 y real = 20 x la
    BANCA rival. La escala se lee del flag por turno `_op_bench_count` (ver
    DO_THE_WAVE_ATTACK_ID): asi la ven TODOS los llamadores, sin depender de que
    cada uno recuerde pasar un parametro extra.
    """
    if op_active is None or target is None:
        return 0
    opd = card_table.get(op_active.id)
    if not opd or not getattr(opd, 'attacks', None):
        return 0
    avail = len(op_active.energies) + 1
    best = 0
    for _aid in opd.attacks:
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        _dmg = getattr(_atk, 'damage', 0) or 0
        _need = len(getattr(_atk, 'energies', []) or [])
        if (op_active.id == Alakazam_ex and _aid == POWERFUL_HAND_ATTACK_ID
                and op_hand_count is not None and _need <= avail):
            _dmg = 20 * (op_hand_count + 2)
        elif _aid == DO_THE_WAVE_ATTACK_ID:
            _dmg = max(_dmg, 20 * ESTADO._op_bench_count)
        if _need <= avail and _dmg > best:
            best = _dmg
    if best <= 0:
        return 0
    # Tools del atacante rival que suman dano contra nuestro Pokemon ex ACTIVO,
    # antes de debilidad/resistencia. Maximum Belt (1158, +50) es incondicional;
    # Brave Bangle (1175, +30) solo cuenta si el PORTADOR no tiene Rule Box
    # (Dipplin no lo tiene; un ex rival con Bangle no obtendria el bonus).
    if target.id in OUR_EX_IDS:
        _op_tool_ids = {getattr(_t, 'id', 0)
                        for _t in (getattr(op_active, 'tools', None) or [])}
        if Maximum_Belt in _op_tool_ids:
            best += 50
        if Brave_Bangle in _op_tool_ids and not _tiene_rule_box(op_active.id):
            best += 30
    tgt = card_table.get(target.id)
    _op_type = getattr(opd, 'energyType', None)
    if tgt is not None and _op_type is not None:
        if getattr(tgt, 'weakness', None) == _op_type:
            best *= 2
        elif getattr(tgt, 'resistance', None) == _op_type:
            best = max(0, best - 30)
    return max(0, int(best))


def _attacker_base_damage(attacker_id, target, effective_energy,
                          grass_scale, teal_self_energy, bench_count):
    """Dano base de un atacante propio contra `target`, ANTES de aplicar
    debilidad/resistencia/inmunidad (de eso se encarga _our_effective_damage).

    - effective_energy: energia EFECTIVA disponible para atacar (len(energies)
      ya es efectiva; incluir aqui la energia a adjuntar si corresponde).
    - grass_scale: nº de energias Grass para escalar el ataque de Hydrapple.
    - teal_self_energy: energia propia para escalar el ataque de Teal Mask
      (internamente se le suma la energia del objetivo).
    - bench_count: nº de Pokemon en nuestra banca (escala el ataque de Dipplin).

    Devuelve 0 si el atacante no llega a su requisito de energia
    (ATTACK_ENERGY_REQ, fuente unica de verdad).
    """
    req = ESTADO.ATTACK_ENERGY_REQ
    if attacker_id == Hydrapple_ex and effective_energy >= req[Hydrapple_ex]:
        return 30 + 30 * grass_scale
    if attacker_id == Teal_Mask_Ogerpon_ex and effective_energy >= req[Teal_Mask_Ogerpon_ex]:
        # Myriad Leaf Shower (ataque 120): "30 mas de dano por cada Energia unida
        # a AMBOS Pokemon Activos" -> cuenta la energia de NUESTRO activo Ogerpon
        # MAS la del activo rival. Verificado con el dano REAL de 6 registros
        # (own 3 + opp 2 -> 180; own 4 + opp 2 -> 210; own 4 + opp 0 -> 150;
        # own 3 + opp 1 -> 150): con la misma energia propia el dano cambia segun
        # la energia del rival, asi que NO es solo la propia. `teal_self_energy` ya
        # es la energia EFECTIVA propia (Wild Growth de Meganium la duplica);
        # `len(target.energies)` es la energia del activo rival, o la del objetivo
        # que gusteamos con Boss's (que pasa a ser el activo y por tanto suma).
        _opp_active_e = len(getattr(target, 'energies', []) or []) if target is not None else 0
        return 30 + 30 * (teal_self_energy + _opp_active_e)
    if attacker_id == Tapu_Bulu and effective_energy >= req[Tapu_Bulu]:
        return 220
    if attacker_id == Fezandipiti_ex and effective_energy >= req[Fezandipiti_ex]:
        return 100
    if attacker_id == Meganium and effective_energy >= req[Meganium]:
        return 140
    if attacker_id == Dipplin and effective_energy >= req[Dipplin]:
        return 20 * bench_count
    if attacker_id == Pinsir and effective_energy >= req[Pinsir]:
        return 100
    return 0


def _bench_attacker_can_ko(my_state, target, meganium_active, total_grass_field,
                           bench_count, retreat_grass_after, neutral_zone):
    if target is None:
        return False
    _thp = target.hp or 0
    if _thp <= 0:
        return False
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        e = len(bp.energies)
        eff = e * _grass_mult()
        base = _attacker_base_damage(bp.id, target, eff,
                                     grass_scale=retreat_grass_after,
                                     teal_self_energy=e, bench_count=bench_count)
        if base <= 0:
            continue
        if _our_effective_damage(bp, target, base, meganium_active, neutral_zone) >= _thp:
            return True
    return False


def _bench_attacker_best_damage(my_state, target, meganium_active, bench_count,
                                retreat_grass_after, neutral_zone,
                                min_body_hp=0):
    """Mejor dano EFECTIVO que haria hoy un atacante de banca sobre `target` si lo
    promovemos (0 = ninguno esta listo). Hermano no-letal de
    `_bench_attacker_can_ko`: mide el CHIP, no el KO.

    `min_body_hp` descarta cuerpos que aguantan menos que ese umbral (espejo de la
    guarda "no cambiar un ex por un cuerpo peor" del scorer de retirada).
    """
    if target is None:
        return 0
    best = 0
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        if (bp.hp or 0) < min_body_hp:
            continue
        e = len(bp.energies)
        base = _attacker_base_damage(bp.id, target, e * _grass_mult(),
                                     grass_scale=retreat_grass_after,
                                     teal_self_energy=e, bench_count=bench_count)
        if base <= 0:
            continue
        best = max(best, _our_effective_damage(
            bp, target, base, meganium_active, neutral_zone))
    return best


def _snipe_target_score(damage, target):
    """Ranking de un objetivo de snipe con el dano YA efectivo:
      1) KO (mas premios > mas cargado > mas vida = mas desarrollado),
      2) si nadie muere, el chip que MAS cerca deja del KO,
      3) inmunes (dano 0) como ultimo recurso -- la seleccion es obligatoria."""
    if target is None:
        return 0
    _hp = target.hp or 0
    if damage <= 0:
        return 1
    if damage >= _hp:
        return (10000 + 1000 * prize_count_op(target)
                + 10 * len(getattr(target, 'energies', []) or [])
                + _hp // 10)
    return 100 + int(100 * damage / max(1, _hp))

__all__ = [
    '_powerful_hand_proyectado',
    '_ProjTarget',
    '_ko_no_garantizado',
    '_snipe_targets',
    '_our_effective_damage',
    '_tiene_rule_box',
    '_op_active_attack_damage_to',
    '_attacker_base_damage',
    '_bench_attacker_can_ko',
    '_bench_attacker_best_damage',
    '_snipe_target_score',
    '_ventana_de_regalo',
]
