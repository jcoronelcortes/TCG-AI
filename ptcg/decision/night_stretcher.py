"""Night Stretcher: recuperar del descarte.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.calculo.energia import _can_attack_eff, _grass_attach_route_open, _grass_attach_unit, _retreat_grass_units
from ptcg.calculo.dano import _attacker_base_damage, _op_active_attack_damage_to, _our_effective_damage
from ptcg.calculo.carta import prize_count_op
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.estado.agente import ESTADO
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Meowth_ex, RETREAT_COST, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calculo.tablero import _active_of, _evolvable_counts
from ptcg.calculo.energia import _grass_mult, calc_syrup_storm_damage, count_total_grass_energy
from dataclasses import dataclass
from ptcg.calculo.tablero import _evolvable_counts
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex


class _CtxNSPlay:
    """Wrapper del DecisionContext para los escenarios de Night Stretcher:
    anade el inventario del descarte (basics/evos/energia) y la foto
    evolvable; el resto de campos delega en el ctx via __getattr__."""

    _BASICOS = (Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu,
                Meowth_ex, Fezandipiti_ex, Pinsir)
    _EVOS = (Bayleef, Meganium, Dipplin, Hydrapple_ex)

    def __init__(self, ctx):
        self.c = ctx
        basics, evos, energia = set(), set(), 0
        for carta in ctx.my_state.discard:
            if carta.id == Basic_Grass_Energy:
                energia += 1
            elif carta.id in self._BASICOS:
                basics.add(carta.id)
            elif carta.id in self._EVOS:
                evos.add(carta.id)
        self.basics, self.evos, self.energia = basics, evos, energia
        self.evolvable = _evolvable_counts(ctx.field_counts,
                                           ctx.field_at_turn_start,
                                           ctx.forest_in_play)

    def __getattr__(self, nombre):
        return getattr(self.c, nombre)


def _ns_energia_util_sin_planta(w):
    return (w.energia >= 1
            and w.hand_counts.get(Basic_Grass_Energy, 0) == 0)


def _ns_hay_ogerpon_teal(w):
    for bp in w.my_state.bench:
        if (bp is not None and bp.id == Teal_Mask_Ogerpon_ex
                and len(bp.energies) < 3):
            return True
    if w.my_state.active:
        act = w.my_state.active[0]
        if (act is not None and act.id == Teal_Mask_Ogerpon_ex
                and len(act.energies) < 3):
            return True
    return False


def _ns_crustle_basicos_permitidos(w):
    if w.op_is_cornerstone_deck and not w.op_is_crustle_deck:
        return (Tapu_Bulu, Pinsir)
    return (Tapu_Bulu, Pinsir, Applin, Chikorita)


def _ns_crustle_evos_permitidas(w):
    if w.op_is_cornerstone_deck and not w.op_is_crustle_deck:
        return ()
    return (Dipplin, Bayleef, Meganium)


@dataclass
class _CtxNS:
    hand: dict
    campo: dict
    evolvable_ns: dict
    bench_count: int
    total_grass: int
    has_hydrapple: bool
    active_needs_energy: bool
    op_ex_immune_active: bool
    op_ex_immune_bench: bool
    op_is_lucario: bool
    watchtower: bool
    best_supp_hand_val: int
    best_supp_mazo_val: int
    turno: int
    energy_attached: bool
    supporter_played: bool
    act_hyd_ripen: bool          # Hydrapple ex activo cargable con Ripening
    act_og_can_teal_attack: bool  # Ogerpon activo que Teal Dance habilita
    ns_bench_charge: bool        # vs Crustle: energia para atacante de banca
    ns_evo_saves_doomed: bool    # Hydrapple ex salva a un Dipplin condenado
    grass_enables_syrup_ko: bool  # la Planta vuelve LETAL al Syrup Storm
    # --- Turno muerto: el motor de ROBO manda (registro_008 paso 67) --------
    turno_muerto: bool = False   # nadie ataca hoy ni con una energia mas
    mano_agotada: bool = False   # <=2 cartas en mano tras pagar la busqueda
    ld_free: bool = True         # _meowth_ld_free (Last-Ditch sin gastar)
    ko_reciente: bool = False    # ko_last_turn (habilita Flip the Script)
    # vs Dragapult con >2 Pokemon en juego, Tapu Bulu no se podra BAJAR (ver
    # `_dragapult_no_tapu`): tampoco se busca -- traerlo a la mano solo la
    # llena de una carta muerta.
    dragapult_no_tapu: bool = False


def _v_ns_grass_sin_planta(c):
    v = 600
    if not c.energy_attached:
        v = 700
    if (c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 1
            and c.hand.get(Basic_Grass_Energy, 0) == 0):
        v = 750
    return v


def _ns_motor_meowth_vivo(c):
    """El Meowth ex recuperado se BAJA este turno y su Last-Ditch Catch trae un
    Supporter del mazo mejor que cualquier cosa que quede en la mano."""
    return (not c.watchtower and c.ld_free
            and c.campo.get(Meowth_ex, 0) < 2
            and c.bench_count < 5
            and not c.supporter_played
            and c.best_supp_hand_val < 500
            and c.best_supp_mazo_val >= 400)


def _ns_motor_fez_vivo(c):
    """El Fezandipiti ex recuperado se BAJA este turno y Flip the Script roba 3
    (exige KO propio en el turno anterior)."""
    return (not c.watchtower and c.ko_reciente
            and c.campo.get(Fezandipiti_ex, 0) == 0
            and c.bench_count < 5)


def _ns_ruta_de_carga_abierta(w):
    """Queda alguna via para poner una Planta de la mano en el campo este
    turno (adjunte manual o habilidad de carga viva)."""
    return _grass_attach_route_open(
        w.state, w.field_counts,
        abilities_off=bool(getattr(w, 'meowth_ability_lock', False)))


def _ns_ruta_de_carga_hasta_el_activo(w):
    """Igual que `_ns_ruta_de_carga_abierta` pero exigiendo que la Planta pueda
    llegar al ACTIVO: el adjunte manual va a donde queramos, Ripening Charge
    tambien (adjunta a 1 de tus Pokemon) y Teal Dance solo al propio Ogerpon."""
    if not w.state.energyAttached:
        return True
    if not _ns_ruta_de_carga_abierta(w):
        return False
    act = _active_of(w.my_state)
    if act is None:
        return False
    if w.field_counts.get(Hydrapple_ex, 0) >= 1:
        return True
    return act.id == Teal_Mask_Ogerpon_ex


def _ns_e_retirada_letal(w):
    """La Planta del DESCARTE paga el COSTE DE RETIRADA del ACTIVO y libera a un
    atacante de banca que NOQUEA este turno (user, registro_021 turno 21).

    Cadena completa: Night Stretcher -> Planta a la mano -> adjuntar al ACTIVO
    (que no puede atacar) -> RETIRAR -> promover al atacante listo -> KO. Sin
    esta pieza inicial la cadena entera es inalcanzable: el resto de eslabones
    (`_attach_enable_retreat_ko`, 41000) exigen una Planta EN LA MANO, y aqui
    justamente no la hay -- esta en el descarte.

    Deck-agnostica: todo el trabajo lo hace `_grass_unlocks_active_retreat` (via
    `ability_unlock_retreat_ko` del ctx), que se apoya en `RETREAT_COST`,
    `_can_attack_eff` y `_bench_attacker_can_ko` -- ningun id de carta. Cubre
    cualquier activo bloqueado (Fezandipiti ex, Meowth ex, un cuerpo de otro
    mazo) y cualquier rematador de banca."""
    return (w.ability_unlock_retreat_ko
            and _ns_energia_util_sin_planta(w)
            and _ns_ruta_de_carga_hasta_el_activo(w))


def _ns_e_retirada_chip(w):
    """Version NO letal de `_ns_e_retirada_letal`: el atacante de banca solo
    hace CHIP, pero el activo no puede atacar de ninguna forma este turno
    (`ability_unlock_retreat_attack` ya lo exige), asi que el chip vale
    infinitamente mas que cerrar el turno por 0. Mismo criterio que
    `_attach_enable_retreat_attack` (log 88162794: cuatro turnos seguidos
    regalados sin atacar)."""
    return (w.ability_unlock_retreat_attack
            and _ns_energia_util_sin_planta(w)
            and _ns_ruta_de_carga_hasta_el_activo(w))


def _ns_e_activo_paga_retirada(w):
    """Energia del descarte para que el ACTIVO pague su COSTE DE RETIRADA y
    suba a atacar un cuerpo de banca (user, registro_014 paso 141 vs Alakazam).

    `_ns_activo_no_llega_al_coste` solo contempla la retirada de la LINEA
    MEGANIUM (Chikorita/Bayleef/Meganium); con un Fezandipiti ex activo a 0
    energias y un Hydrapple ex de banca listo devolvia False, asi que la Night
    Stretcher que recuperaba la Planta del descarte se vetaba por banca llena y
    el turno moria sin atacar.

    Union de las dos variantes de arriba. La consume el corte de BANCA LLENA
    (`_ns_banca_llena_guardar`); el SCORE de la jugada lo producen
    `_ns_e_retirada_letal` / `_ns_e_retirada_chip` como escenarios de
    `_ESC_NS_RECUPERACION`."""
    return _ns_e_retirada_letal(w) or _ns_e_retirada_chip(w)


def _ns_e_syrup_letal(w):
    """La energia recuperada convierte el Syrup Storm del Hydrapple ACTIVO
    en LETAL sobre el activo rival (no lo era sin ella)."""
    if not (_ns_energia_util_sin_planta(w)
            and not w.op_is_crustle_deck and not w.op_is_cornerstone_deck):
        return False
    act = w.my_state.active[0] if w.my_state.active else None
    opp = (w.op_state.active[0]
           if (w.op_state.active and w.op_state.active[0] is not None)
           else None)
    if act is None or act.id != Hydrapple_ex or opp is None:
        return False
    if len(act.energies) * _grass_mult() < 2:
        return False
    ahora = calc_syrup_storm_damage(w.my_state, w.meganium_in_play)
    despues = ahora + 30 * _grass_attach_unit()
    eff_ahora = _our_effective_damage(
        act, opp, ahora, w.meganium_in_play, w.neutralization_zone_active)
    eff_despues = _our_effective_damage(
        act, opp, despues, w.meganium_in_play, w.neutralization_zone_active)
    hp = opp.hp or 0
    return eff_ahora < hp <= eff_despues and eff_despues > 0


def _ns_e_remate_con_el_activo(w):
    """La Planta recuperada, puesta en el PROPIO activo (adjunte manual,
    Teal Dance o Ripening Charge), vuelve LETAL su ataque.

    Generaliza `_ns_e_syrup_letal` a cualquier atacante activo (user,
    registro_010 paso 123 vs Archaludon ex): Ogerpon ex activo con 6 unidades
    contra un Archaludon ex 300/300 con 3 energias y SIN banca. Myriad hacia
    30+30x(6+3) = 300 - 30 de resistencia = 270: se quedaba a 30. Con una
    Planta del descarte via Teal Dance sube a 30+30x(8+3) = 360 - 30 = 330 >=
    300 y, con la banca rival vacia, ese KO GANA la partida."""
    if not (_ns_energia_util_sin_planta(w)
            and not w.op_is_crustle_deck and not w.op_is_cornerstone_deck):
        return False
    if not _ns_ruta_de_carga_hasta_el_activo(w):
        return False
    act = _active_of(w.my_state)
    opp = _active_of(w.op_state)
    if act is None or opp is None:
        return False
    hp = opp.hp or 0
    if hp <= 0:
        return False
    total = count_total_grass_energy(w.my_state)
    unidad = _grass_attach_unit()
    e = len(act.energies)

    def _eff(_e, _grass):
        base = _attacker_base_damage(
            act.id, opp, _e, grass_scale=_grass, teal_self_energy=_e,
            bench_count=w.bench_count)
        if base <= 0:
            return 0
        return _our_effective_damage(
            act, opp, base, w.meganium_in_play, w.neutralization_zone_active)

    return _eff(e, total) < hp <= _eff(e + unidad, total + unidad)


def _ns_e_remate_via_promocion(w):
    """La Planta recuperada convierte en LETAL el remate de este turno con un
    atacante de BANCA que promovemos RETIRANDO el activo.

    Hermano de `_ns_e_syrup_letal` para el caso en que el rematador todavia no
    esta en el puesto activo (user, registro_006 paso 78 vs Archaludon ex,
    PERDIDA): Hydrapple ex en banca con 2 energias, 10 unidades de Planta en el
    campo y el activo rival a 270 PV con resistencia a Planta. Retirar cuesta
    una carta entera (2 unidades con Wild Growth), asi que el Syrup Storm real
    era 30+30x8 = 270 - 30 = 240: NO noqueaba. Con UNA Planta del descarte
    (Night Stretcher + Teal Dance, que sigue viva aunque el adjunte manual se
    haya gastado) el recuento vuelve a 10 -> 330 - 30 = 300 >= 270 y el KO
    entrega DOS premios. Sin modelarlo, la Night Stretcher nunca entraba en el
    analisis del remate."""
    if not (_ns_energia_util_sin_planta(w)
            and not w.op_is_crustle_deck and not w.op_is_cornerstone_deck):
        return False
    if not _ns_ruta_de_carga_abierta(w):
        return False
    act = _active_of(w.my_state)
    opp = _active_of(w.op_state)
    if act is None or opp is None or (opp.hp or 0) <= 0:
        return False
    hp = opp.hp or 0
    coste = RETREAT_COST.get(act.id, 1)
    if len(act.energies) < coste:
        return False  # no podemos pagar la retirada: no hay promocion
    total = count_total_grass_energy(w.my_state)
    # Si el ACTIVO ya remata a ese mismo objetivo con lo que tiene, la Planta
    # no desbloquea nada: atacar cobra los mismos premios sin gastar la Night
    # Stretcher ni una energia del descarte.
    _act_eff = len(act.energies) * _grass_mult()
    _act_base = _attacker_base_damage(
        act.id, opp, _act_eff, grass_scale=total,
        teal_self_energy=len(act.energies), bench_count=w.bench_count)
    if _act_base > 0 and _our_effective_damage(
            act, opp, _act_base, w.meganium_in_play,
            w.neutralization_zone_active) >= hp:
        return False
    tras_retirar = max(0, total - _retreat_grass_units(coste))
    unidad = _grass_attach_unit()

    def _remata(bp, grass):
        e = len(bp.energies)
        base = _attacker_base_damage(
            bp.id, opp, e * _grass_mult(), grass_scale=grass,
            teal_self_energy=e, bench_count=w.bench_count)
        if base <= 0:
            return False
        return _our_effective_damage(
            bp, opp, base, w.meganium_in_play,
            w.neutralization_zone_active) >= hp

    # La linea vale la Night Stretcher solo si de verdad se puede EJECUTAR y
    # PAGA (medido en premios). Sin estas dos guardas el escenario reservaba la
    # carta para un pivote que el resto del agente luego rechazaba -- el
    # diferencial de matchup lo pagaba (-3 puntos en self-play vs iron_thorns y
    # crustle_kangaskhan; con ellas vuelve a positivo):
    #   (a) el cuerpo promovido queda EXPUESTO al activo rival: si ese golpe lo
    #       noquea, el pivote regala sus premios (misma guarda que
    #       `_pivote_banca_suicida`);
    #   (b) el KO tiene que valer 2+ premios o GANAR la partida: quemar la
    #       Night Stretcher y una energia por un premio suelto no compensa.
    _premios = prize_count_op(opp)
    _gana = (w.my_prize <= _premios
             or not any(b is not None for b in (w.op_state.bench or [])))
    if _premios < 2 and not _gana:
        return False
    for bp in (w.my_state.bench or []):
        if bp is None:
            continue
        if _remata(bp, tras_retirar):
            return False  # ya noquea sin la Planta: no hace falta la carta
    for bp in (w.my_state.bench or []):
        if bp is None:
            continue
        if not _remata(bp, tras_retirar + unidad):
            continue
        _golpe = _op_active_attack_damage_to(
            opp, bp, getattr(w.op_state, 'handCount', None))
        if not _gana and _golpe >= (bp.hp or 0):
            continue  # promoverlo seria regalar sus premios
        return True
    return False


def _ns_e_cargar_banca_crustle(w):
    if not (_ns_energia_util_sin_planta(w)
            and not w.state.energyAttached):
        return False
    for bp in (w.my_state.bench or []):
        if bp is None:
            continue
        if bp.id not in (Tapu_Bulu, Teal_Mask_Ogerpon_ex,
                         Hydrapple_ex, Meganium):
            continue
        req = ESTADO.ATTACK_ENERGY_REQ.get(bp.id)
        if req is None:
            continue
        if len(bp.energies) * _grass_mult() < req:
            return True
    return False


def _sin_ataque_hoy(my_state, state, field_counts, abilities_off=False):
    """True si NINGUN cuerpo nuestro llega a atacar este turno, ni siquiera
    poniendo UNA energia mas.

    Deck-agnostico: recorre el campo con `ATTACK_ENERGY_REQ` (la lista curada
    de cuerpos con los que de verdad atacamos) en tres pasadas:
      1) el ACTIVO ya paga su ataque con la energia que tiene;
      2) hay un atacante LISTO en banca y el activo puede pagar su retirada
         para subirlo (un atacante atascado en banca no es un atacante);
      3) queda una ruta de carga abierta (adjunte manual libre o una habilidad
         tipo Teal Dance / Ripening Charge viva) y UNA Planta mas convierte al
         activo -- o al cuerpo de banca promovible -- en atacante.
    Si ninguna se cumple el turno esta MUERTO en ataque: lo unico que produce
    valor es rehacer la mano. NO usa `_active_ready_attacker` a proposito: ese
    flag depende de `can_attack`, que solo se calcula en el menu MAIN y vale
    False en los sub-menus de seleccion (TO_HAND), donde vive esta funcion.
    """
    act = _active_of(my_state)
    if act is not None and _can_attack_eff(act.id, len(act.energies)):
        return False
    bench = [b for b in (my_state.bench or []) if b is not None]
    puede_promover = (
        act is not None
        and not getattr(state, 'retreated', False)
        and len(act.energies) >= RETREAT_COST.get(act.id, 1))
    if puede_promover and any(_can_attack_eff(b.id, len(b.energies))
                              for b in bench):
        return False
    if _grass_attach_route_open(state, field_counts,
                                abilities_off=abilities_off):
        unidad = _grass_attach_unit()
        if act is not None and _can_attack_eff(act.id,
                                               len(act.energies) + unidad):
            return False
        if puede_promover and any(
                _can_attack_eff(b.id, len(b.energies) + unidad)
                for b in bench):
            return False
    return True


def _ctx_ns_fetch(my_state, state, hand_counts, field_counts, bench_count,
                  total_grass, has_hydrapple, active_needs_energy,
                  op_ex_immune_active, op_ex_immune_bench, op_is_lucario,
                  watchtower, best_supp_hand_val, best_supp_mazo_val,
                  grass_enables_syrup_ko=False, ld_free=True,
                  dragapult_no_tapu=False):
    activo = my_state.active[0] if my_state.active else None
    # Ogerpon ACTIVO que aun no ataca (<3 efectivas) pero que con UNA Planta
    # via Teal Dance (HABILIDAD, independiente del adjunte manual) llega a
    # >=3. Pivote retirar->promover Ogerpon->NS->Teal Dance->atacar (user,
    # log 86583929 turno 4 vs Alakazam). len(energies) es EFECTIVA.
    act_og_can_teal_attack = (
        activo is not None and
        activo.id == Teal_Mask_Ogerpon_ex and
        len(activo.energies) < 3 and
        len(activo.energies) + _grass_attach_unit() >= 3 and
        hand_counts[Basic_Grass_Energy] == 0)
    # Hydrapple ex activo que aun no ataca (efectiva < 2) y sin Planta en
    # mano: recuperar ENERGIA para cargarlo con Ripening Charge (habilidad).
    act_hyd_ripen = (
        activo is not None and
        activo.id == Hydrapple_ex and
        len(activo.energies) * _grass_mult() < 2 and
        hand_counts[Basic_Grass_Energy] == 0)
    # Matchup Crustle/Cornerstone: recuperar la Planta para CARGAR un
    # atacante de banca cuando aun podemos adjuntarla este turno.
    ns_bench_charge = False
    if ((ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) and
            hand_counts[Basic_Grass_Energy] == 0 and
            not state.energyAttached):
        for bp in (my_state.bench or []):
            if bp is None:
                continue
            if bp.id not in (Tapu_Bulu, Teal_Mask_Ogerpon_ex,
                             Hydrapple_ex, Meganium):
                continue
            req = ESTADO.ATTACK_ENERGY_REQ.get(bp.id)
            if req is None:
                continue
            if len(bp.energies) * _grass_mult() < req:
                ns_bench_charge = True
                break
    # Recuperar Hydrapple ex para EVOLUCIONAR un Dipplin de banca CONDENADO por
    # el snipe automatico del rival (user, registro_006/008 vs Marnie's
    # Grimmsnarl ex, PERDIDA): con el Dipplin a <= 30 de vida, Shadow Bullet lo
    # mata solo el proximo turno y regala un premio gratis. La evolucion resetea
    # la vida (80 -> 330) y de paso convierte el cuerpo condenado en un muro, asi
    # que salvarlo vale MAS que cualquier recuperacion de desarrollo o de energia
    # (que solo suma dano cuando el KO ya esta asegurado). A diferencia de
    # `dipplin_evolucionable`, esta regla NO exige que falte un Hydrapple ex en
    # juego: aqui la evolucion no es desarrollo, es rescate.
    ns_evo_saves_doomed = False
    if ESTADO._op_bench_snipe_dmg > 0 and hand_counts.get(Hydrapple_ex, 0) == 0:
        for _nsd in (my_state.bench or []):
            if _nsd is None or _nsd.id != Dipplin:
                continue
            if (_nsd.hp or 0) > ESTADO._op_bench_snipe_dmg:
                continue  # sobrevive el goteo de este turno: no urge
            if getattr(_nsd, 'appearThisTurn', False) and not ESTADO.forest_in_play:
                continue  # evoluciono este turno: no se puede volver a evolucionar
            ns_evo_saves_doomed = True
            break
    evolvable_ns = _evolvable_counts(field_counts, ESTADO._field_at_turn_start,
                                     ESTADO.forest_in_play)
    # TURNO MUERTO (user, registro_008 paso 67 vs Alakazam, PERDIDA): sin
    # ningun cuerpo capaz de atacar hoy y con la mano vacia, recuperar una
    # EVOLUCION es preparacion que nunca llega a jugarse -- el rival noquea al
    # activo y el proximo turno seguimos sin cartas. Lo unico que produce valor
    # es el motor de ROBO. `mano_agotada` mide la mano YA sin la carta de
    # busqueda (se pago al jugarla), asi que 0 = nos quedamos secos.
    turno_muerto = _sin_ataque_hoy(my_state, state, field_counts,
                                   abilities_off=watchtower)
    mano_agotada = len(my_state.hand or []) <= 2
    return _CtxNS(
        hand=hand_counts, campo=field_counts, evolvable_ns=evolvable_ns,
        bench_count=bench_count, total_grass=total_grass,
        has_hydrapple=has_hydrapple,
        active_needs_energy=active_needs_energy,
        op_ex_immune_active=op_ex_immune_active,
        op_ex_immune_bench=op_ex_immune_bench,
        op_is_lucario=op_is_lucario, watchtower=watchtower,
        best_supp_hand_val=best_supp_hand_val,
        best_supp_mazo_val=best_supp_mazo_val,
        turno=state.turn, energy_attached=state.energyAttached,
        supporter_played=state.supporterPlayed,
        act_hyd_ripen=act_hyd_ripen,
        act_og_can_teal_attack=act_og_can_teal_attack,
        ns_bench_charge=ns_bench_charge,
        ns_evo_saves_doomed=ns_evo_saves_doomed,
        grass_enables_syrup_ko=grass_enables_syrup_ko,
        turno_muerto=turno_muerto, mano_agotada=mano_agotada,
        ld_free=ld_free, ko_reciente=ESTADO.ko_last_turn,
        dragapult_no_tapu=dragapult_no_tapu)


def _v_ns_chikorita_arrancar(c):
    v = 800
    if ESTADO.forest_in_play and (c.hand.get(Bayleef, 0) >= 1
                           or c.hand.get(Meganium, 0) >= 1):
        v = 950
    elif c.hand.get(Bayleef, 0) >= 1:
        v = 900
    if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) == 0:
        v += 100
    else:
        v -= 100
    return v


def _v_ns_applin_arrancar(c):
    v = 700
    if ESTADO.forest_in_play and (c.hand.get(Dipplin, 0) >= 1
                           or c.hand.get(Hydrapple_ex, 0) >= 1):
        v = 870
    elif c.hand.get(Dipplin, 0) >= 1:
        v = 800
    if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) == 0:
        v += 100
    else:
        v -= 100
    return v


def _v_ns_ogerpon_pocos(c):
    v = 550
    if c.campo.get(Teal_Mask_Ogerpon_ex, 0) == 0:
        v = 700
    if c.bench_count <= 1:
        v += 100
    if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
            Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) == 0:
        v += 100
    return v


def _v_ns_meowth_fetch(c):
    v = min(700, c.best_supp_mazo_val)
    if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) == 0:
        v += 100
    return v

__all__ = [
    '_CtxNSPlay',
    '_ns_energia_util_sin_planta',
    '_ns_hay_ogerpon_teal',
    '_ns_crustle_basicos_permitidos',
    '_ns_crustle_evos_permitidas',
    '_CtxNS',
    '_v_ns_grass_sin_planta',
    '_ns_motor_meowth_vivo',
    '_ns_motor_fez_vivo',
    '_ns_ruta_de_carga_abierta',
    '_ns_ruta_de_carga_hasta_el_activo',
    '_ns_e_retirada_letal',
    '_ns_e_retirada_chip',
    '_ns_e_activo_paga_retirada',
    '_ns_e_syrup_letal',
    '_ns_e_remate_con_el_activo',
    '_ns_e_remate_via_promocion',
    '_ns_e_cargar_banca_crustle',
    '_v_ns_chikorita_arrancar',
    '_v_ns_applin_arrancar',
    '_v_ns_ogerpon_pocos',
    '_v_ns_meowth_fetch',
    '_ctx_ns_fetch',
    '_sin_ataque_hoy',
]
