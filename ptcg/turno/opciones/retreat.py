"""Puntuacion de las opciones `RETREAT`.

Rama `o.type == OptionType.RETREAT` de la cadena de `agent()`, extraida VERBATIM.
Desempaqueta del contexto los 60 campos que lee y devuelve los
11 que reasigna; los demas quedan como estaban, igual que antes.
"""

from cg.api import AreaType, CardType, OptionType, Pokemon
from ptcg.calculo.carta import get_card, prize_count, prize_count_op
from ptcg.calculo.dano import _attacker_base_damage, _op_active_attack_damage_to, _our_effective_damage
from ptcg.calculo.energia import _can_attack_eff, _grass_attach_route_open, _grass_attach_unit, _grass_mult, _physical_energy, _retreat_grass_units
from ptcg.calculo.tablero import _active_of
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Cornerstone_Mask_Ogerpon_ex, Crustle_Fighting, Crustle_Grass, Cubchoo, Dawn, Dipplin, Drednaw, Dwebble_Fighting, Dwebble_Grass, EEVEE_IDS, Fezandipiti_ex, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, OP_BENCH_SNIPE_DAMAGE, OUR_ABILITY_IDS, OUR_EX_IDS, Pinsir, RETREAT_COST, SCORE_VETO, Sylveon, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cartas.puntuacion import MAIN_ATTACKERS
from ptcg.cartas.tablas import card_table
from ptcg.estado.agente import ESTADO


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o`. Puede devolver `_SALTAR`."""
    _active_snipe_ko_now = tc._active_snipe_ko_now
    _active_snipe_ko_prizes = tc._active_snipe_ko_prizes
    _alakazam_pivot_1prize = tc._alakazam_pivot_1prize
    _b = tc._b
    _bdg_retreat_ko = tc._bdg_retreat_ko
    _bench_attacker_ready = tc._bench_attacker_ready
    _bp_e = tc._bp_e
    _bp_eff = tc._bp_eff
    _conf_can_attack_pkmn = tc._conf_can_attack_pkmn
    _conf_should_retreat = tc._conf_should_retreat
    _cubchoo_lock_stuck = tc._cubchoo_lock_stuck
    _descuadre_matchup = tc._descuadre_matchup
    _e = tc._e
    _eff = tc._eff
    _ex_stuck_promo_ready = tc._ex_stuck_promo_ready
    _has_bench_attacker = tc._has_bench_attacker
    _hydra_pivot_active = tc._hydra_pivot_active
    _hydra_wall_pivot = tc._hydra_wall_pivot
    _lucario_sac_available = tc._lucario_sac_available
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _nonex_active_hits_wall = tc._nonex_active_hits_wall
    _op_act = tc._op_act
    _op_best_damage_vs = tc._op_best_damage_vs
    _our_first_turn = tc._our_first_turn
    _p = tc._p
    _prize_denial_pivot = tc._prize_denial_pivot
    _sid = tc._sid
    _suicide_swap_win_promote = tc._suicide_swap_win_promote
    _supp_values = tc._supp_values
    _tapu_sac_pivot = tc._tapu_sac_pivot
    _teal_wall_pivot = tc._teal_wall_pivot
    _wall_ko_promote = tc._wall_ko_promote
    _win_ko_active_via_promote = tc._win_ko_active_via_promote
    active_ko_likely = tc.active_ko_likely
    bench_count = tc.bench_count
    bp = tc.bp
    can_attack = tc.can_attack
    can_switch = tc.can_switch
    condition_urgency = tc.condition_urgency
    discard_counts = tc.discard_counts
    estimated_op_damage = tc.estimated_op_damage
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_switch_card = tc.has_switch_card
    meowth_ability_lock = tc.meowth_ability_lock
    my_index = tc.my_index
    my_prize = tc.my_prize
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    obs = tc.obs
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_state = tc.op_state
    select = tc.select
    state = tc.state
    total_grass = tc.total_grass

    try:
        _active_reloc = my_state.active[0] if my_state.active else None
        
        # Regla (user, log 86510119 paso 26, vs Dragapult, PERDIDA): si al
        # retirar el activo la promocion volveria a subir un Pokemon de la
        # MISMA especie que el que estamos retirando, la retirada no cambia
        # nada y solo malgasta la energia del coste de retirada. Se cancela
        # (score = SCORE_VETO) para dejar al Pokemon en el activo. Dos casos:
        #   (a) todos los candidatos de banca son la misma especie que el
        #       activo (el unico candidato es el mismo Pokemon), o
        #   (b) la promocion prefiere subir un BASICO de 1 premio (tenemos
        #       Lillie's Determination y NINGUN atacante de banca listo para
        #       atacar este turno, rival no inmune a ex/habilidad) y ese
        #       basico volveria a ser la especie del activo (p.ej. Applin
        #       activo con otro Applin en banca): subir Applin por Applin no
        #       aporta nada.
        _same_species_retreat = False
        if _active_reloc is not None:
            _ss_bench = [bp for bp in (my_state.bench or [])
                         if bp is not None and isinstance(bp, Pokemon)]
            if _ss_bench:
                # (a) Caso literal: no hay ningun candidato de otra especie.
                _ss_only_same = all(bp.id == _active_reloc.id
                                    for bp in _ss_bench)
        
                # (b) Caso "preferir basico": reproducimos la condicion de la
                # promocion (`_refresh_promote_prefer_basic`).
                _ss_grass_attach = (
                    hand_counts.get(Basic_Grass_Energy, 0) >= 1
                    and not state.energyAttached)
                _ss_bench_atk_ready = False
                for bp in _ss_bench:
                    if bp.id not in MAIN_ATTACKERS:
                        continue
                    _ss_e = len(bp.energies)
                    if _can_attack_eff(bp.id, _ss_e) or (
                            _ss_grass_attach
                            and _can_attack_eff(
                                bp.id, _ss_e + _grass_attach_unit())):
                        _ss_bench_atk_ready = True
                        break
                _ss_prefer_basic = (
                    hand_counts.get(Lillie_Determination, 0) >= 1
                    and not op_has_ex_immune_active
                    and not op_has_ability_immune_active
                    and not _ss_bench_atk_ready)
                _ss_act_data = card_table.get(_active_reloc.id)
                _ss_act_is_basic = (
                    _ss_act_data is not None
                    and not getattr(_ss_act_data, 'stage1', False)
                    and not getattr(_ss_act_data, 'stage2', False))
                # Basicos no-ex candidatos de banca (los que la promocion
                # preferiria como muro de 1 premio).
                _ss_bench_basics = []
                for bp in _ss_bench:
                    _bp_d = card_table.get(bp.id)
                    if (_bp_d is not None
                            and not getattr(_bp_d, 'stage1', False)
                            and not getattr(_bp_d, 'stage2', False)
                            and bp.id not in OUR_EX_IDS):
                        _ss_bench_basics.append(bp.id)
                # El basico promovido es de la especie del activo si: el
                # activo es Applin (basico de maxima prioridad) y hay otro
                # Applin en banca, o todos los basicos candidatos son de la
                # especie del activo (suba el que suba, misma especie).
                _ss_same_basic = False
                if _ss_bench_basics:
                    if _active_reloc.id == Applin:
                        _ss_same_basic = (Applin in _ss_bench_basics)
                    else:
                        _ss_same_basic = (
                            Applin not in _ss_bench_basics
                            and all(_b == _active_reloc.id
                                    for _b in _ss_bench_basics))
                _ss_prefer_same = (
                    _ss_prefer_basic and _ss_act_is_basic
                    and _active_reloc.id not in OUR_EX_IDS
                    and _ss_same_basic)
        
                _same_species_retreat = _ss_only_same or _ss_prefer_same
        
        # Regla: Meganium activo + Hydrapple ex en banca + rival SIN
        # proteccion-ex (no Crustle/Sylveon/inmunes a ex) => retirar Meganium
        # para promover a Hydrapple ex (atacante/motor clave). Meganium sigue
        # en banca, asi que Wild Growth se mantiene. NO aplica vs muros
        # inmunes a ex, donde Hydrapple ex (ex) no podria golpear.
        _meg_retreat_for_hydra = False
        if (_active_reloc is not None and _active_reloc.id == Meganium
                and can_switch
                and not (ESTADO.op_is_crustle_deck or op_has_ex_immune_active
                         or op_has_ex_immune_bench or op_is_sylveon_deck)):
            for _mrh_bp in (my_state.bench or []):
                if _mrh_bp is not None and _mrh_bp.id == Hydrapple_ex:
                    _meg_retreat_for_hydra = True
                    break
        
        _grd_prefer_attack = False
        if (_active_reloc is not None and can_switch
                and not (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck)):
            _grd_opa = (op_state.active[0]
                        if (op_state.active and op_state.active[0] is not None)
                        else None)
            _grd_opa_hp = (_grd_opa.hp or 0) if _grd_opa is not None else 0
            _grd_opa_e = len(_grd_opa.energies) if _grd_opa is not None else 0
        
            def _grd_damage(_p):
                _e = len(_p.energies)
                _eff = _e * _grass_mult()
                if _p.id == Hydrapple_ex and _eff >= 2:
                    return 30 + 30 * total_grass
                if _p.id == Teal_Mask_Ogerpon_ex and _eff >= 3:
                    return 30 + 30 * (_e + _grd_opa_e)
                if _p.id == Dipplin and _e >= 1:
                    return 100
                if _p.id == Tapu_Bulu and _eff >= 4:
                    return 220
                if _p.id == Fezandipiti_ex and _eff >= 3:
                    return 100
                if _p.id == Pinsir and _eff >= 2:
                    return 100
                if _p.id == Meganium and _eff >= 4:
                    return 140
                return 0
        
            _grd_active_can_attack = _grd_damage(_active_reloc) > 0
            _grd_any_ko = False
            for _grd_p in ([_active_reloc] + list(my_state.bench)):
                if _grd_p is None:
                    continue
                _grd_d = _grd_damage(_grd_p)
                if _grd_d > 0 and _grd_opa_hp > 0 and _grd_d >= _grd_opa_hp:
                    _grd_any_ko = True
                    break
            if _grd_active_can_attack and not _grd_any_ko:
                _grd_prefer_attack = True
        
        _active_can_ko_now = False
        if (can_attack and _active_reloc is not None
                and op_state.active and op_state.active[0] is not None):
            _acn_op = op_state.active[0]
            _acn_e = len(_active_reloc.energies)
            _acn_eff = _acn_e * _grass_mult()
            _acn_base = 0
            if _active_reloc.id == Dipplin and _acn_e >= 1:
                _acn_base = 20 * bench_count
            elif _active_reloc.id == Hydrapple_ex and _acn_eff >= 2:
                _acn_base = 30 + 30 * total_grass
            elif _active_reloc.id == Teal_Mask_Ogerpon_ex and _acn_eff >= 3:
                # Myriad cuenta la energia de AMBOS activos.
                _acn_base = 30 + 30 * (
                    _acn_e + len(getattr(_acn_op, 'energies', []) or []))
            elif _active_reloc.id == Tapu_Bulu and _acn_eff >= 4:
                _acn_base = 220
            elif _active_reloc.id == Fezandipiti_ex and _acn_eff >= 3:
                _acn_base = 100
            elif _active_reloc.id == Meganium and _acn_eff >= 4:
                _acn_base = 140
            elif _active_reloc.id == Pinsir and _acn_eff >= 2:
                _acn_base = 100
            if _acn_base > 0:
                _acn_dmg = _our_effective_damage(
                    _active_reloc, _acn_op, _acn_base,
                    ESTADO.meganium_in_play, neutralization_zone_active)
                if _acn_dmg > 0 and _acn_dmg >= (_acn_op.hp or 0):
                    _active_can_ko_now = True
        
        # El activo TAMBIEN "puede noquear ahora" cuando su ataque elige
        # objetivo y el KO esta en la BANCA rival (Cruel Arrow de Fezandipiti
        # ex; user, registro_004 paso 54 vs Alakazam). Sin esto el bloque de
        # arriba solo miraba al activo rival, `_active_can_ko_now` salia
        # False y la retirada -- que ademas DESCARTA la energia del snipe --
        # ganaba el menu tirando un premio gratis.
        # `_active_kos_op_active` conserva el sentido ESTRICTO (el KO cae
        # sobre el activo rival) para los pivotes que comparan premios.
        _active_kos_op_active = _active_can_ko_now
        if _active_snipe_ko_now:
            _active_can_ko_now = True
        
        # Proteger a Hydrapple ex: si nuestro Hydrapple ex activo va a ser
        # noqueado el proximo turno y no puede tomar un KO este turno, es
        # mejor retirarlo y promover un atacante de banca no-ex (p.ej.
        # Dipplin) que si pueda atacar. Hydrapple ex es clave para acelerar
        # energia y cargar a Tapu Bulu en un solo turno, asi que evitamos
        # entregarlo (2 premios) por nada.
        _hydra_ex_protect_retreat = False
        if (_active_reloc is not None and _active_reloc.id == Hydrapple_ex
                and can_switch and active_ko_likely
                and not _active_can_ko_now):
            for _hpr_bp in my_state.bench:
                if _hpr_bp is None:
                    continue
                _hpr_e = len(_hpr_bp.energies)
                _hpr_eff = _hpr_e * _grass_mult()
                if _hpr_bp.id == Dipplin and _hpr_e >= 1:
                    _hydra_ex_protect_retreat = True
                    break
                elif _hpr_bp.id == Tapu_Bulu and _hpr_eff >= 4:
                    _hydra_ex_protect_retreat = True
                    break
                elif _hpr_bp.id == Meganium and _hpr_eff >= 4:
                    _hydra_ex_protect_retreat = True
                    break
                elif _hpr_bp.id == Pinsir and _hpr_eff >= 2:
                    _hydra_ex_protect_retreat = True
                    break
        
        # Regla (user): si un Hydrapple ex de BANCA (ya con >=2 efectivas)
        # puede subir al activo y rematar con un Syrup Storm LETAL sobre el
        # activo rival, retirar el activo actual para promoverlo y ganar la
        # partida. Solo cuando se puede cambiar (can_switch). La promocion
        # posterior elige a ese Hydrapple ex via `_best_promote_card`.
        # IMPORTANTE (user, log 86338560 paso 114, GANADA vs Mega Lucario):
        # NO retirar el activo si el PROPIO activo YA puede rematar este turno
        # (`_active_can_ko_now`). En ese caso subir a otro Hydrapple ex de
        # banca (mismo tipo, con MENOS energia) solo pagaria el coste de
        # retirada y reduciria el ataque sin ganar nada: el activo debe atacar.
        # EXCEPCION (user, log 86412738 paso 145 vs Hops; GENERALIZADA en log
        # 86505760 paso 55, GANADA vs Alakazam): aunque el activo YA pueda
        # noquear, si es un ex FRAGIL (2 premios, distinto de Hydrapple y con
        # menos HP que el muro 330) y un Hydrapple ex de BANCA TAMBIEN puede
        # rematar (Syrup Storm letal), SIEMPRE se prefiere retirar y atacar con
        # el Hydrapple ex: mismo KO pero deja el muro de 330 HP como activo en
        # vez de exponer el ex fragil (Hydrapple aguanta ataques mayores que
        # Ogerpon en turnos futuros). Regla del user: siempre que un Hydrapple
        # ex de banca pueda derrotar al rival, es nuestro atacante prioritario.
        # UNICA excepcion: no pivotar si atacar con el activo YA gana la partida
        # este turno (my_prize <= premios del activo rival): ahi no hay turno
        # futuro que proteger, se ataca directo. El pivote NO aplica cuando el
        # activo es NO-ex (retirarlo para exponer un ex de 2 premios seria peor)
        # ni cuando el activo ya es el propio Hydrapple ex.
        _active_ex_fragile_pivot = (
            _active_reloc is not None
            and _active_can_ko_now
            and _active_reloc.id in OUR_EX_IDS
            and _active_reloc.id != Hydrapple_ex
            and (_active_reloc.maxHp or 0) < 330
            and op_state.active and op_state.active[0] is not None
            and not (my_prize <= prize_count_op(op_state.active[0])))
        _hydra_lethal_promote = False
        if (_active_reloc is not None and can_switch
                and (not _active_can_ko_now or _active_ex_fragile_pivot)
                and op_state.active and op_state.active[0] is not None):
            _hlp_opa = op_state.active[0]
            _hlp_opa_hp = _hlp_opa.hp or 0
            # Syrup Storm escala con el Grass DEL CAMPO, y la retirada
            # DESCARTA la energia del activo para pagar su coste: hay que
            # medir el dano con el Grass que quedara DESPUES del retiro
            # (user, registro_011 paso 138 vs Dragapult, PERDIDA). Alli el
            # activo era un Tapu Bulu con 3 Plantas (6 efectivas): con el
            # Grass previo (10) Syrup Storm daba 330 y "noqueaba" al
            # Dragapult ex de 320, pero al retirar se descartaban esas 3
            # Plantas y el ataque real quedaba en 150. Mismo patron que
            # `_bo_grass_after` en la seleccion del gusteo.
            _hlp_ret_cost = RETREAT_COST.get(_active_reloc.id, 1)
            _hlp_grass_after = max(
                0, total_grass - (0 if has_switch_card
                                  else _retreat_grass_units(_hlp_ret_cost)))
            for _hlp_bp in (my_state.bench or []):
                if _hlp_bp is None or _hlp_bp.id != Hydrapple_ex:
                    continue
                if len(_hlp_bp.energies) * _grass_mult() < 2:
                    continue  # no puede pagar Syrup Storm
                # El pivote de "ex fragil" (`_active_ex_fragile_pivot`) es
                # el UNICO que retira un activo que YA noquea: no gana ni un
                # premio (los dos cuerpos son ex de 2) y encima paga la
                # energia del coste de retirada. Lo unico que lo justifica es
                # dejar delante al cuerpo que AGUANTA MAS -- y eso se mide
                # con la vida ACTUAL, no con el HP IMPRESO (user,
                # registro_014 paso 166 vs Alakazam). Alli el "muro de 330"
                # era un Hydrapple ex a 90/330 y el activo un Teal Mask
                # Ogerpon ex a 210/210: los dos noqueaban al Alakazam, asi
                # que retirar solo servia para poner delante al cuerpo que
                # muere. `_active_ex_fragile_pivot` mide la fragilidad con
                # `maxHp < 330`, que es una constante de la carta y no
                # sabe nada del dano ya recibido; esta comparacion es la que
                # mira el tablero. Mejora ESTRICTA: empatados, el cambio
                # sigue costando la energia de la retirada. Mismo criterio
                # que `_pdx_act_margin` en `_prize_denial_pivot` ("el que
                # AGUANTA va delante"). No toca la rama de activo
                # ESTANCADO (`not _active_can_ko_now`), donde el pivote si
                # compra el KO que no teniamos.
                if (_active_ex_fragile_pivot
                        and (_hlp_bp.hp or 0) <= (_active_reloc.hp or 0)):
                    continue
                # No promover un Hydrapple ex al que el activo rival NOQUEA
                # (user): regalaria 2 premios. En el registro el Hydrapple
                # estaba a 70/330 y el rival a 2 premios, asi que promoverlo
                # entregaba la partida. Lo correcto era atacar con el activo.
                _hlp_dmg_rival = _op_active_attack_damage_to(
                    _hlp_opa, _hlp_bp,
                    getattr(op_state, 'handCount', None))
                if _hlp_dmg_rival >= (_hlp_bp.hp or 0):
                    continue
                _hlp_dmg = _our_effective_damage(
                    _hlp_bp, _hlp_opa, 30 + 30 * _hlp_grass_after,
                    ESTADO.meganium_in_play, neutralization_zone_active)
                if _hlp_dmg > 0 and _hlp_opa_hp > 0 and _hlp_dmg >= _hlp_opa_hp:
                    _hydra_lethal_promote = True
                    break
        
        # Regla (user, log 86583929 turno 4, vs Alakazam, PERDIDA): pivote de
        # KO con Teal Mask Ogerpon ex. Si el activo esta ESTANCADO (no puede
        # noquear este turno, p.ej. un Fezandipiti ex sin las 3 energias de su
        # ataque) y en la banca hay un Teal Mask Ogerpon ex que, al PROMOVERLO
        # y usar Teal Dance, alcanza >=3 energias EFECTIVAS y su Myriad Leaf
        # Shower NOQUEA al activo rival, retirar el activo para subir al Ogerpon
        # y rematar. La Planta que necesita Teal Dance se obtiene de la mano o,
        # con Night Stretcher, recuperando una Planta del descarte -- incluida
        # la que el propio coste de retirada acaba de descartar del activo. El
        # scorer greedy evaluaba a los Ogerpon de banca a su energia ACTUAL
        # (via _grd_damage/_bench_attacker_can_ko, que exigen >=3 efectivas) y
        # nunca modelaba la rampa de Teal Dance tras promover, por eso no "veia"
        # esta linea. Solo si el rival NO inmuniza a nuestros ex (Ogerpon no
        # daña a Crustle/Sylveon). len(energies) es EFECTIVA (Wild Growth de
        # Meganium duplica cada Planta): sin Meganium un Ogerpon a 1 Planta
        # llega a 2 tras Teal Dance (<3) y el detector no dispara.
        # El "activo estancado" que exige este pivote ya no es simplemente
        # `not _active_can_ko_now`: un Fezandipiti ex activo con Cruel Arrow
        # letal sobre la BANCA rival SI tiene premio hoy (user, registro_004
        # paso 54). Retirarlo cuesta su energia y expone otro cuerpo, asi que
        # el pivote solo se le impone cuando el KO del Ogerpon vale MAS
        # premios que el del snipe; empatado o por debajo, se ataca.
        _olp_active_stuck = not _active_can_ko_now
        if (not _olp_active_stuck and _active_snipe_ko_now
                and not _active_kos_op_active
                and op_state.active and op_state.active[0] is not None):
            _olp_active_stuck = (prize_count_op(op_state.active[0])
                                 > _active_snipe_ko_prizes)
        
        _ogerpon_lethal_promote = False
        if (_active_reloc is not None and can_switch
                and _olp_active_stuck
                and _active_reloc.id != Teal_Mask_Ogerpon_ex
                and not op_has_ex_immune_active
                and op_state.active and op_state.active[0] is not None):
            _olp_opa = op_state.active[0]
            _olp_opa_hp = _olp_opa.hp or 0
            _olp_op_e = len(_olp_opa.energies)
            # Planta disponible para Teal Dance: en mano, o recuperable con
            # Night Stretcher desde el descarte (o desde la energia que la
            # retirada acaba de descartar del activo, que en nuestro mazo es
            # Planta).
            # Y ademas tiene que QUEDAR una via para ponerla en el campo
            # (user, registro_004 paso 54): alli habia una Planta en mano,
            # pero el adjunte manual ya estaba gastado y los tres Ogerpon
            # habian usado su Teal Dance, asi que el "remate" era imposible y
            # la retirada (8900) aplastaba al ataque real del Fezandipiti.
            # `_grass_attach_route_open` mira justo eso: adjunte manual libre
            # o alguna habilidad de carga aun sin usar.
            _olp_ruta_ok = _grass_attach_route_open(
                state, field_counts, abilities_off=meowth_ability_lock)
            _olp_grass_ok = _olp_ruta_ok and (
                hand_counts.get(Basic_Grass_Energy, 0) >= 1
                or (hand_counts.get(Night_Stretcher, 0) >= 1
                    and (discard_counts.get(Basic_Grass_Energy, 0) >= 1
                         or _physical_energy(len(_active_reloc.energies)) >= 1)))
            if _olp_grass_ok:
                for _olp_bp in (my_state.bench or []):
                    if _olp_bp is None or _olp_bp.id != Teal_Mask_Ogerpon_ex:
                        continue
                    _olp_eff_after = len(_olp_bp.energies) + _grass_attach_unit()
                    if _olp_eff_after < 3:
                        continue
                    _olp_dmg = _our_effective_damage(
                        _olp_bp, _olp_opa,
                        30 + 30 * (_olp_eff_after + _olp_op_e),
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    if _olp_dmg > 0 and _olp_opa_hp > 0 and _olp_dmg >= _olp_opa_hp:
                        _ogerpon_lethal_promote = True
                        break
        
        # Regla (user): un Tapu Bulu CARGADO en el activo que puede noquear
        # al Pokemon activo rival NO debe retirarse; debe atacar. Al no ser
        # ex, si lo noquean solo entrega 1 premio, asi que conviene rematar
        # con el en lugar de gastar el pivote a Hydrapple ex (que si es
        # noqueado entrega 2 premios). Por eso vetamos el retiro/promocion.
        # EXCEPCION: en matchups ex-inmunes (Crustle / Cornerstone /
        # Sylveon), si el activo rival NO pertenece a la linea ex-inmune
        # (no requiere a Tapu para ser danado) y hay un Pokemon de banca que
        # lo puede rematar, SI retiramos a Tapu Bulu para reservarlo como
        # atacante clave contra los muros con proteccion ex. Si el activo
        # rival ES de la linea ex-inmune, Tapu Bulu ataca (es quien puede
        # con esos muros).
        if (_active_reloc is not None and _active_reloc.id == Tapu_Bulu
                and _active_can_ko_now):
            _tapu_ex_immune_match = (ESTADO.op_is_crustle_deck
                                     or ESTADO.op_is_cornerstone_deck
                                     or op_is_sylveon_deck)
            _tapu_opa_id = (op_state.active[0].id
                            if op_state.active
                            and op_state.active[0] is not None else None)
            _tapu_opa_is_immune_line = (
                _tapu_opa_id in {
                    Crustle_Grass, Crustle_Fighting, Dwebble_Grass,
                    Dwebble_Fighting, Sylveon,
                    Cornerstone_Mask_Ogerpon_ex}
                or _tapu_opa_id in EEVEE_IDS)
            _tapu_reserve = (_tapu_ex_immune_match
                             and not _tapu_opa_is_immune_line
                             and not op_has_ex_immune_active)
            if not _tapu_reserve:
                # Tapu Bulu debe atacar: no lo retiramos para promover.
                _hydra_lethal_promote = False
        
        _op_active_is_cubchoo = bool(
            op_state.active and op_state.active[0] is not None
            and op_state.active[0].id == Cubchoo)
        _cub_bench_attacker_ready = any(
            _bp_cub is not None and _conf_can_attack_pkmn(_bp_cub)
            for _bp_cub in (my_state.bench or []))
        
        # DESCUADRE DE PREMIOS (user, registro_002 paso 27 vs Raging Bolt; y
        # vs Mega Abomasnow ex). Nuestro activo es un ex de 2 premios que NO
        # puede noquear al activo rival este turno y hay un cuerpo de UN
        # premio en la banca (bajado por la regla del PLAY o previo):
        # RETIRAR el ex y promover el 1-premio. Su atacante one-shotea a
        # cualquiera de los nuestros, asi que quien este delante va a caer:
        # que el KO rival pague 1 premio y no 2 (su mazo, todo ex de 2-3
        # premios, necesita KOs grandes para ganar a tiempo).
        _raging_sac_pivot = (
            _descuadre_matchup
            and _active_reloc is not None
            and _active_reloc.id in OUR_EX_IDS
            and not _active_can_ko_now
            and can_switch
            and any(bp is not None and prize_count(bp) == 1
                    for bp in (my_state.bench or [])))
        
        # DESCUADRE GENERALIZADO (user, registro_004 paso 37 vs Mega Lucario
        # ex): mismo patron que `_raging_sac_pivot` pero para CUALQUIER mazo,
        # detectado con el remate rival REAL en vez de una lista fija de
        # matchups. Nuestro activo es un ex (2 premios) que SI puede atacar
        # pero cuyo ataque NO noquea al activo rival (`not _active_can_ko_now`)
        # y el ataque del activo rival NOQUEA a nuestro ex el proximo turno
        # (`_op_active_attack_damage_to` >= HP). Si ademas NO hay ningun
        # atacante LISTO en la banca (no tenemos jugada mejor que preservar el
        # ex) y hay un cuerpo de 1 premio para poner delante, RETIRAR el ex y
        # sacrificar el 1-premio: si atacaramos no noqueariamos y el ex moriria
        # el proximo turno regalando 2 premios; retirandolo cedemos solo 1
        # premio y conservamos el ex -con su energia- en la banca para
        # re-promoverlo tras el KO. La promocion elige el basico mas barato
        # (`_lucario_ko_prefer_basic` / `_ko_prefer_basic_general`). Excluye
        # los muros inmunes a ex en el activo rival (ahi el ex no ataca y ya
        # hay logica dedicada: `_ex_stuck_promo_ready` / `_nonex_active_hits_wall`).
        # No sacrificar-retirar cuando estamos EN RANGO DE REMATE (my_prize<=2):
        # ahi hay que RACEAR/rematar, no ceder tempo (user, test Dragapult win
        # engine, my_prize=1 -> atacar). El descuadre defensivo solo aplica
        # cuando aun faltan >=3 KOs para ganar, donde frenar el 2x1 importa.
        # El retiro-sacrificio se POSPONE mientras queden jugadas de desarrollo
        # de este turno (user, registro_004 paso 36): un Supporter aun sin
        # jugar (p.ej. Xerosic, que descarta mano rival) o un ATACANTE basico
        # en mano que podemos poner en banca (montar el proximo atacante) valen
        # mas que retirar YA -- retirar y desarrollar no son excluyentes en el
        # mismo turno, asi que primero se desarrolla y el retiro sale al final
        # (paso 37, con la mano ya vaciada de esas jugadas). No se pospone por
        # items sueltos de bajo valor (p.ej. Unfair Stamp), que no aportan mas
        # que el retiro con el activo condenado al frente.
        _doomed_pending_play = False
        for _dpo in select.option:
            if _dpo.type != OptionType.PLAY:
                continue
            _dpc = get_card(obs, AreaType.HAND, _dpo.index, my_index)
            if _dpc is None:
                continue
            _dpd = card_table.get(_dpc.id)
            if (_dpd is not None
                    and getattr(_dpd, 'cardType', None) == CardType.SUPPORTER
                    and not state.supporterPlayed):
                _doomed_pending_play = True
                break
            if (_dpc.id in MAIN_ATTACKERS and bench_count < 5
                    and _dpd is not None
                    and not getattr(_dpd, 'stage1', False)
                    and not getattr(_dpd, 'stage2', False)):
                _doomed_pending_play = True
                break
        
        _doomed_ex_sac_pivot = False
        if (not _raging_sac_pivot
                and not _doomed_pending_play
                and _active_reloc is not None
                and _active_reloc.id in OUR_EX_IDS
                and not _active_can_ko_now
                and can_switch
                and my_prize >= 3
                and not _bench_attacker_ready
                and not op_has_ex_immune_active
                and op_state.active and op_state.active[0] is not None
                and any(bp is not None and prize_count(bp) == 1
                        for bp in (my_state.bench or []))):
            _des_opa = op_state.active[0]
            _des_op_dmg = _op_active_attack_damage_to(
                _des_opa, _active_reloc, getattr(op_state, 'handCount', None))
            # GUARDA DEL SNIPE (user, registro_004 t4 vs Marnie's
            # Grimmsnarl, PERDIDA): esconder el ex en la banca solo niega
            # premios si ALLI SOBREVIVE. Contra un atacante que ademas pega
            # a la banca (Shadow Bullet: 180 al activo + 30 a un banquillo;
            # Phantom Dive, Jetting Blow...) un ex ya herido por debajo de
            # ese chip muere igual, y entonces la retirada CONCEDE MAS:
            #   quedarse  -> 2 premios (el ex activo noqueado)
            #   retirarse -> 1 (el cuerpo promovido) + 2 (el ex sniped) = 3
            # La aritmetica nunca favorece retirarse en ese caso: como
            # mucho empata (si el snipe iba a matar otro cuerpo de banca
            # igual de caro), asi que el pivote se apaga.
            #
            # Se mide con el ATACANTE concreto (`OP_BENCH_SNIPE_DAMAGE` del
            # ACTIVO rival), no con el flag de mesa `_op_bench_snipe_dmg`:
            # ese cae a `OP_BENCH_SNIPE_DEFAULT` en cuanto hay CUALQUIER
            # amenaza de goteo en juego, y apagar el pivote por un sniper
            # que no esta al frente cuesta partidas (medido vs
            # crustle/Kangaskhan: -3.1 puntos con la version amplia).
            _des_snipe = OP_BENCH_SNIPE_DAMAGE.get(_des_opa.id, 0)
            if (_des_op_dmg >= (_active_reloc.hp or 0)
                    and _des_snipe < (_active_reloc.hp or 0)):
                _doomed_ex_sac_pivot = True
        
        if _suicide_swap_win_promote:
            # RELEVO DEL REMATE SUICIDA (user, registro_016 paso 184 vs
            # Marnie's Grimmsnarl, EMPATE): el ataque del activo noquea pero
            # su AUTO-DANO lo mata, y con ese cadaver el rival cobra su
            # ultimo premio -> empate (o derrota). En la banca hay un
            # rematador que gana LIMPIO: retirar para promoverlo es la unica
            # jugada que convierte el 0-0 en victoria, asi que va por encima
            # de cualquier otro motivo de retiro (incluidos los pivotes
            # letales de Hydrapple/Ogerpon, que persiguen el MISMO premio con
            # menos urgencia). El tier de orden de jugada (`_TIER_WIN_ATTACK`)
            # la sube ademas por encima de cargas y desarrollo, que si no
            # dominarian por TIER pese a su menor score.
            score = 9600
        elif _win_ko_active_via_promote:
            # MATCH POINT AL ACTIVO (user, registro_010 paso 144 vs Marnie's
            # Grimmsnarl ex, PERDIDA): noquear al ACTIVO rival cobra los
            # premios que faltan y el rematador esta en la BANCA. Es la
            # MISMA jugada que el relevo del remate suicida -- cerrar la
            # partida este turno --, asi que comparte score y `_TIER_WIN_ATTACK`:
            # sin el tier, cualquier carga de energia (tier ENERGY) la
            # aplastaria por ORDEN pese a valer menos. Excluyente con
            # `_suicide_swap_win_promote`: la bandera exige que el activo
            # ACTUAL no remate.
            score = 9600
        elif _hydra_lethal_promote:
            # Retirar el activo para promover al Hydrapple ex de banca cuyo
            # Syrup Storm es LETAL y rematar. Maxima prioridad de retiro.
            score = 9000
        elif _ogerpon_lethal_promote:
            # Retirar el activo estancado para promover un Teal Mask Ogerpon
            # ex de banca y rematar con Myriad Leaf Shower tras Teal Dance
            # (user, log 86583929 turno 4 vs Alakazam). Prioridad de retiro
            # equiparada a la del pivote de Hydrapple: cobrar el premio AHORA.
            # Las acciones posteriores (Night Stretcher para recuperar la
            # Planta, Teal Dance sobre el nuevo activo y el ataque) ya las
            # habilitan sus scorers (_td_ko_on_active da 31500 al Teal Dance
            # que habilita el KO, y el scorer de ATTACK remata si es letal).
            score = 8900
        elif (_op_active_is_cubchoo and can_switch
                and not _cub_bench_attacker_ready):
            # Matchup vs Cubchoo: su ataque deja a nuestro activo sin poder
            # atacar el proximo turno. Retirar ahora para subir a un Pokemon
            # de banca que TAMPOCO puede atacar (sin energia suficiente) solo
            # lo expone al mismo ataque y desperdicia el pivote. Mientras no
            # haya un atacante LISTO en banca, NO se retira: se mantiene el
            # activo (Cubchoo pega poco) y se aprovecha el turno para cargar
            # energia hasta dejar listo a un atacante de banca. Cuando ese
            # atacante este cargado, _cub_bench_attacker_ready sera True y se
            # permitira el retiro para subirlo y atacar en nuestro turno.
            score = SCORE_VETO
        elif (_lucario_sac_pivot and _lucario_sac_available
                and bench_count >= 1 and can_switch):
            # Retirar el Ogerpon ex para no entregar 2 premios al Mega Lucario;
            # despues promoveremos un sacrificio de 1 premio.
            score = 8000
        elif _conf_should_retreat:
            score = 4000 + condition_urgency
        elif _hydra_ex_protect_retreat:
        
            score = 6000
        elif (_ex_stuck_promo_ready or _cubchoo_lock_stuck) and can_switch:
            # Nuestro activo es un ex bloqueado por un muro inmune (Crustle /
            # Sylveon) y hay un atacante no-ex LISTO en banca: retirar para
            # promover al que SI golpea al muro (el mas fuerte se elige en
            # `_best_promote_card`). Evita malgastar el turno atacando por 0.
            # `_cubchoo_lock_stuck`: mismo patron con el activo Hydrapple ex
            # BLOQUEADO por Snotted Up y un atacante de banca listo (paso 82).
            score = 6000
        elif _hydra_pivot_active:
            # Pivote defensivo: retirar al activo fragil y subir a Hydrapple
            # ex (vida completa) que tambien noquea. Prioridad alta para que
            # gane sobre atacar con el activo fragil (que moriria el proximo
            # turno). El plan ya apunta a Hydrapple, por lo que la opcion de
            # ATACAR con el activo queda suprimida (plan.attacker >= 1).
            score = 6500
        elif _teal_wall_pivot and can_switch:
            # Activo Teal Mask Ogerpon ex condenado que NO puede atacar: ya
            # se uso Teal Dance (adjunto 1 Grass -> paga la retirada de 1).
            # Retirar y subir al cuerpo mas fuerte de banca (Hydrapple ex,
            # 330 HP) aunque aun no pueda atacar: no regalar el activo por
            # nada y poner un muro. La promocion elige el de mas vida.
            score = 6450
        elif _hydra_wall_pivot:
            # Activo Teal Mask Ogerpon ex condenado que SI puede atacar pero
            # NO noquea (muro Hydrapple ex sano en banca). Retirar y subir al
            # muro (330 HP) que sobrevive al remate rival y sigue atacando
            # (Syrup Storm 330), en vez de atacar con el Ogerpon fragil que
            # moriria regalando 2 premios. El plan apunta a Hydrapple, asi que
            # ATACAR con el activo queda suprimido (plan.attacker >= 1).
            score = 6450
        elif _tapu_sac_pivot:
            # Sacrificio de premios (user): nuestro activo es un ex de 2
            # premios en riesgo y un Tapu Bulu de banca (1 premio) listo puede
            # noquear al activo rival. Retirar el ex y subir a Tapu Bulu para
            # atacar: mismo KO, pero si nos noquean entregamos 1 premio en vez
            # de 2. Prioridad alta: gana incluso cuando el activo tambien puede
            # noquear ahora (_active_can_ko_now). El plan apunta a Tapu, asi que
            # la opcion de ATACAR con el activo queda suprimida (plan.attacker>=1).
            score = 6600
        elif _raging_sac_pivot:
            # Descuadre vs Raging Bolt (ver el flag arriba). 6540: junto a
            # los demas sacrificios de premios (6450-6600), sobre el veto
            # generico "el activo puede atacar" (_grd_prefer_attack) que
            # aqui seria un error: atacar sin noquear regala 2 premios.
            score = 6540
        elif _prize_denial_pivot:
            # Negacion de premios (user): retirar el ex activo CONDENADO (2
            # premios) que si atacamos igual moriria el proximo turno dando al
            # rival los premios para GANAR, y subir un cuerpo de 1 premio que
            # ataca. Asi el KO rival del proximo turno NO cierra la partida. El
            # plan apunta a ese cuerpo (plan.attacker>=1), por lo que ATACAR con
            # el activo condenado queda suprimido.
            score = 6550
        elif _doomed_ex_sac_pivot:
            # Descuadre generalizado (user, registro_004 paso 37 vs Mega
            # Lucario ex): el ex activo puede atacar pero NO noquea y el rival
            # lo remata el proximo turno, sin atacante de banca listo. Retirar
            # el ex y sacrificar un cuerpo de 1 premio (cede 1 en vez de 2 y
            # preserva el ex). Mismo tier que los demas sacrificios de premios,
            # por debajo del veto "el activo puede atacar" que aqui seria un
            # error (atacar sin noquear regala 2 premios).
            score = 6530
        elif _meg_retreat_for_hydra and not _active_can_ko_now:
            # Meganium activo: subir a Hydrapple ex de banca (rival sin
            # proteccion-ex). Prioridad alta para que gane sobre atacar con
            # Meganium o mantenerlo. Excepcion: si Meganium noquea AHORA
            # (_active_can_ko_now) se queda para tomar el premio.
            score = 6400
        elif _wall_ko_promote is not None and can_switch:
            # RELEVO LETAL CONTRA EL MURO (user, registro_018 paso 113 vs
            # Crustle, PERDIDA): el activo golpea al muro pero NO lo remata y
            # en banca hay un cuerpo no bloqueado que SI (Meganium 140 vs
            # Crustle de 170 <- Tapu Bulu 220). Retirar y rematar. Va por
            # ENCIMA del veto `_nonex_active_hits_wall` -- que ya se apaga en
            # este caso -- y de los pivotes de sacrificio: cobrar el premio
            # ahora manda. El plan apunta al relevo, asi que ATACAR con el
            # activo queda suprimido.
            score = 6700
        elif _nonex_active_hits_wall:
            # user, log 86406907 paso 87, GANADA vs Crustle: nuestro activo
            # es un atacante NO-ex (p.ej. Meganium) que SI golpea al muro
            # inmune-a-ex (Crustle activo). NUNCA se retira: retirarlo solo
            # promoveria un ex de banca que hace 0 al muro. Debe ATACAR.
            score = SCORE_VETO
        elif _grd_prefer_attack:
        
            score = SCORE_VETO
        elif _active_can_ko_now:
        
            score = SCORE_VETO
        elif ESTADO.plan.attacker >= 1:
        
            _retreat_active = my_state.active[0] if my_state.active else None
            _retreat_active_can_attack = False
            if _retreat_active is not None:
                _ra_eff = len(_retreat_active.energies) * _grass_mult()
                _ra_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                  not state.energyAttached)
                _ra_eff_after = _ra_eff + (_grass_attach_unit() if _ra_can_attach else 0)
                if _retreat_active.id == Hydrapple_ex:
                    _retreat_active_can_attack = (_ra_eff_after >= 2)
                elif _retreat_active.id == Dipplin:
                    _retreat_active_can_attack = (len(_retreat_active.energies) >= 1 or _ra_can_attach)
                elif _retreat_active.id == Teal_Mask_Ogerpon_ex:
                    _retreat_active_can_attack = (_ra_eff_after >= 3)
                elif _retreat_active.id == Tapu_Bulu:
                    _retreat_active_can_attack = (_ra_eff_after >= 4)
                elif _retreat_active.id == Pinsir:
                    _retreat_active_can_attack = (_ra_eff_after >= 2)
                elif _retreat_active.id == Fezandipiti_ex:
                    _retreat_active_can_attack = (_ra_eff_after >= 3)
        
            if not _retreat_active_can_attack:
        
                score = 3500
            else:
        
                score = 2500
        elif my_state.active and my_state.active[0] is not None:
            active = my_state.active[0]
            active_energy = len(active.energies)
        
            _our_first_turn = (state.turn == 1 and ESTADO.we_go_first) or (state.turn == 2 and not ESTADO.we_go_first)
        
            NON_ATTACKERS = (Meganium, Meowth_ex, Chikorita, Bayleef, Applin)
        
            # Meganium incluido: puede atacar (req 4 efectivo) y debe contar
            # como atacante disponible en banca. Fuente unica: MAIN_ATTACKERS.
            STRATEGIC_ATTACKERS = MAIN_ATTACKERS
        
            _bench_ready_for_retreat = False
            for bp in my_state.bench:
                if bp is None:
                    continue
                _brr_e = len(bp.energies)
                _brr_eff = _brr_e * _grass_mult()
                if bp.id == Hydrapple_ex and _brr_eff >= 2:
                    _bench_ready_for_retreat = True
                    break
                elif bp.id == Dipplin and _brr_e >= 1:
                    _bench_ready_for_retreat = True
                    break
                elif bp.id == Teal_Mask_Ogerpon_ex and _brr_eff >= 3:
                    _bench_ready_for_retreat = True
                    break
                elif bp.id == Tapu_Bulu and _brr_eff >= 4:
                    _bench_ready_for_retreat = True
                    break
                elif bp.id == Fezandipiti_ex and _brr_eff >= 3:
                    _bench_ready_for_retreat = True
                    break
                elif bp.id == Meganium and _brr_eff >= 4:
                    _bench_ready_for_retreat = True
                    break
        
            _BASIC_OR_STAGE1_NONEX = (
                Applin, Dipplin, Chikorita, Bayleef, Tapu_Bulu, Pinsir)
            _fase58_promo_ready = any(
                bp is not None and bp.id in _BASIC_OR_STAGE1_NONEX
                for bp in my_state.bench)
        
            _meg_only_attacker_retreat = False
            if ((ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) and
                    can_switch and active.id != Meganium):
        
                _opa_km = (op_state.active[0]
                           if (op_state.active and op_state.active[0] is not None)
                           else None)
                _opa_km_hp = (_opa_km.hp or 0) if _opa_km is not None else 0
        
                def _meg_blk_ko(_p):
                    # ¿este atacante no-ex noquea al activo rival (Crustle) este turno?
                    # len(energies) YA es la energia EFECTIVA (Wild Growth ya
                    # aplicado en la observacion) -> Solar Beam (140) con 4.
                    if _p is None or _opa_km is None or _opa_km_hp <= 0:
                        return False
                    _e = len(_p.energies)
                    _eff = _e * _grass_mult()
                    _base = 0
                    if _p.id == Dipplin and _e >= 1:
                        _base = 20 * bench_count
                    elif _p.id == Tapu_Bulu and _eff >= 4:
                        _base = 220
                    elif _p.id == Pinsir and _eff >= 2:
                        _base = 100
                    elif _p.id == Meganium and _eff >= 4:
                        _base = 140
                    if _base <= 0:
                        return False
                    return _our_effective_damage(
                        _p, _opa_km, _base, ESTADO.meganium_in_play,
                        neutralization_zone_active) >= _opa_km_hp
        
                _other_atk_ready_meg = any(
                    _mp_meg is not None and _mp_meg.id != Meganium and
                    _meg_blk_ko(_mp_meg)
                    for _mp_meg in ([active] + list(my_state.bench)))
        
                _meganium_bench_ready_meg = any(
                    bp is not None and bp.id == Meganium and _meg_blk_ko(bp)
                    for bp in my_state.bench)
        
                _act_ko_rival_meg = False
                if (can_attack and op_state.active and
                        op_state.active[0] is not None):
                    _opa_meg = op_state.active[0]
                    _opa_meg_e = len(_opa_meg.energies)
                    _act_base_meg = 0
                    if active.id == Teal_Mask_Ogerpon_ex:
                        _act_base_meg = 30 + 30 * (len(active.energies) + _opa_meg_e)
                    elif active.id == Hydrapple_ex:
                        _act_base_meg = 30 + 30 * total_grass
                    if _act_base_meg > 0:
                        _act_dmg_meg = _our_effective_damage(
                            active, _opa_meg, _act_base_meg,
                            ESTADO.meganium_in_play, neutralization_zone_active)
                        if _act_dmg_meg >= (_opa_meg.hp or 0) and _act_dmg_meg > 0:
                            _act_ko_rival_meg = True
                if (not _other_atk_ready_meg and _meganium_bench_ready_meg and
                        not _act_ko_rival_meg):
                    _meg_only_attacker_retreat = True
        
            if _meg_only_attacker_retreat:
        
                score = 3500
        
            elif ((ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) and
                  active.id == Teal_Mask_Ogerpon_ex):
                if not can_switch:
                    score = SCORE_VETO
                else:
        
                    _tmo_ko_rival = False
                    _opa_tmo = (op_state.active[0]
                                if (op_state.active and op_state.active[0] is not None)
                                else None)
                    if can_attack and _opa_tmo is not None:
                        _opa_tmo_e = len(_opa_tmo.energies)
                        _tmo_base = 30 + 30 * (len(active.energies) + _opa_tmo_e)
                        _tmo_dmg = _our_effective_damage(
                            active, _opa_tmo, _tmo_base,
                            ESTADO.meganium_in_play, neutralization_zone_active)
                        if _tmo_dmg >= (_opa_tmo.hp or 0) and _tmo_dmg > 0:
                            _tmo_ko_rival = True
                    if _tmo_ko_rival:
                        score = SCORE_VETO
                    else:
        
                        _tmo_attacker_ready = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_e = len(bp.energies)
                            _bp_eff = _bp_e * _grass_mult()
                            if bp.id == Pinsir and _bp_eff >= 2:
                                _tmo_attacker_ready = True
                                break
                            elif bp.id == Tapu_Bulu and _bp_eff >= 4:
                                _tmo_attacker_ready = True
                                break
                            elif (ESTADO.op_is_crustle_deck and
                                  bp.id == Dipplin and _bp_e >= 1):
                                _tmo_attacker_ready = True
                                break
                            elif (ESTADO.op_is_crustle_deck and
                                  bp.id == Meganium and _bp_eff >= 4):
                                _tmo_attacker_ready = True
                                break
                            elif (not op_has_ex_immune_active and
                                  bp.id == Hydrapple_ex and _bp_eff >= 2):
                                _tmo_attacker_ready = True
                                break
                            elif (not op_has_ex_immune_active and
                                  bp.id == Teal_Mask_Ogerpon_ex and _bp_eff >= 3):
                                _tmo_attacker_ready = True
                                break
                        if _tmo_attacker_ready:
                            score = 3400
                        else:
                            score = SCORE_VETO
            elif (not can_attack) and can_switch and _bench_ready_for_retreat:
        
                # GUARDA "no cambiar un ex por un cuerpo peor" (user,
                # registro_009 vs Archaludon ex): retirar un ex del ACTIVO
                # solo compensa si el cuerpo que sube (a) NOQUEA al activo
                # rival -- cobra premio YA, sea de 1 o de 2 -- o (b) aguanta
                # AL MENOS lo mismo que el que baja (pivote a un muro igual
                # o mayor). Cambiar un Hydrapple ex de 330 PV por un Teal
                # Mask Ogerpon ex de 210 "porque el segundo puede atacar"
                # tira el muro y pone delante un cuerpo de 2 premios mas
                # facil de derrotar: el rival cobra lo mismo con menos
                # esfuerzo. Y si el que sube ni remata ni aguanta, el chip
                # no paga el cambio. Deck-agnostica: mira vida, KO efectivo
                # y coste de retirada, no cartas concretas.
                _xx_act = active
                _xx_op = _active_of(op_state)
                _xx_act_hp = (_xx_act.hp or 0) if _xx_act is not None else 0
                _xx_vale = False
                if _xx_act is None or _xx_act.id not in OUR_EX_IDS:
                    _xx_vale = True   # el activo no es un ex: regla no aplica
                else:
                    for _xx_bp in (my_state.bench or []):
                        if _xx_bp is None:
                            continue
                        _xx_req = ESTADO.ATTACK_ENERGY_REQ.get(_xx_bp.id)
                        if _xx_req is None:
                            continue
                        _xx_e = len(_xx_bp.energies)
                        if _xx_e * _grass_mult() < _xx_req:
                            continue  # no es un atacante listo
                        if (_xx_bp.hp or 0) >= _xx_act_hp:
                            _xx_vale = True   # pivote a un muro igual o mayor
                            break
                        if _xx_op is not None:
                            _xx_base = _attacker_base_damage(
                                _xx_bp.id, _xx_op, _xx_e * _grass_mult(),
                                grass_scale=max(
                                    0, total_grass - _retreat_grass_units(
                                        RETREAT_COST.get(_xx_act.id, 1))),
                                teal_self_energy=_xx_e,
                                bench_count=bench_count)
                            if _xx_base > 0 and _our_effective_damage(
                                    _xx_bp, _xx_op, _xx_base,
                                    ESTADO.meganium_in_play,
                                    neutralization_zone_active) >= (
                                        _xx_op.hp or 0):
                                _xx_vale = True
                                break
                score = 3200 if _xx_vale else SCORE_VETO
        
            elif (ESTADO.op_is_cornerstone_deck and can_switch and
                  active.id in OUR_ABILITY_IDS and
                  op_state.active and op_state.active[0] is not None and
                  op_state.active[0].id == Cornerstone_Mask_Ogerpon_ex):
                _cs_tapu_ready = any(
                    bp is not None and bp.id == Tapu_Bulu and
                    len(bp.energies) >= 4
                    for bp in my_state.bench)
                if _cs_tapu_ready:
                    score = 3400
                else:
                    score = SCORE_VETO
        
            elif (ESTADO.op_is_crustle_deck and can_switch and
                  active.id in OUR_EX_IDS):
        
                _cr_op_act = op_state.active[0] if op_state.active else None
                _cr_ex_can_ko = False
                if can_attack and _cr_op_act is not None:
                    _cr_op_e = len(_cr_op_act.energies)
                    _cr_base = 0
                    if active.id == Teal_Mask_Ogerpon_ex:
                        _cr_base = 30 + 30 * (len(active.energies) + _cr_op_e)
                    elif active.id == Hydrapple_ex:
                        _cr_base = 30 + 30 * total_grass
                    if _cr_base > 0:
                        _cr_dmg = _our_effective_damage(
                            active, _cr_op_act, _cr_base,
                            ESTADO.meganium_in_play, neutralization_zone_active)
                        if _cr_dmg >= (_cr_op_act.hp or 0) and _cr_dmg > 0:
                            _cr_ex_can_ko = True
                if _cr_ex_can_ko:
                    score = SCORE_VETO
                else:
                    _crustle_bench_atk = False
                    for bp in my_state.bench:
                        if bp is None:
                            continue
                        _ce_eff = len(bp.energies) * _grass_mult()
                        if ((bp.id == Tapu_Bulu and _ce_eff >= 4) or
                                (bp.id == Dipplin and len(bp.energies) >= 1) or
                                (bp.id == Meganium and _ce_eff >= 4)):
                            _crustle_bench_atk = True
                            break
                    if _crustle_bench_atk:
                        score = 3400
                    else:
                        score = SCORE_VETO
        
            elif (active.id in OUR_EX_IDS and (not can_attack) and can_switch
                  and estimated_op_damage >= (active.hp or 0)
                  and _fase58_promo_ready):
                score = 3300
        
            elif active.id == Fezandipiti_ex and ESTADO.plan.attacker == 0:
                score = SCORE_VETO
        
            elif (active.id == Fezandipiti_ex and
                  state.turn == 2 and not ESTADO.we_go_first):
                score = SCORE_VETO
        
            elif active.id in NON_ATTACKERS:
        
                _has_bench_attacker = False
                for bp in my_state.bench:
                    if bp is not None and bp.id in STRATEGIC_ATTACKERS:
                        _has_bench_attacker = True
                        break
        
                _bench_has_only_non_attackers = True
                for bp in my_state.bench:
                    if bp is not None and bp.id in STRATEGIC_ATTACKERS:
                        _bench_has_only_non_attackers = False
                        break
        
                _HAND_PLAYABLE_ATTACKERS = (Tapu_Bulu, Teal_Mask_Ogerpon_ex)
                _has_attacker_in_hand = False
                if bench_count < 5:
                    for _hpa_id in _HAND_PLAYABLE_ATTACKERS:
                        if (hand_counts.get(_hpa_id, 0) >= 1 and
                                field_counts.get(_hpa_id, 0) == 0):
                            _has_attacker_in_hand = True
                            break
        
                    if (not _has_attacker_in_hand and
                            hand_counts.get(Fezandipiti_ex, 0) >= 1 and
                            field_counts.get(Fezandipiti_ex, 0) == 0 and
                            state.turn > 1):
                        _has_attacker_in_hand = True
        
                # ¿Hay en la banca un atacante REALMENTE listo para atacar
                # este turno? No basta con que exista un atacante por
                # identidad (p.ej. un Teal ex): debe tener la energia
                # efectiva suficiente (Wild Growth incluido), o poder
                # completarla adjuntando UNA energia de Planta este turno.
                # Sin esta comprobacion se retiraba el activo para subir a
                # un atacante SIN cargar, que tampoco podia atacar,
                # desperdiciando el turno y el coste de retirada.
                _grass_attach_this_turn = (
                    hand_counts.get(Basic_Grass_Energy, 0) >= 1
                    and not state.energyAttached)
                _bench_attacker_ready = False
                for bp in my_state.bench:
                    if bp is None or bp.id not in STRATEGIC_ATTACKERS:
                        continue
                    _bar_req = ESTADO.ATTACK_ENERGY_REQ.get(bp.id)
                    if _bar_req is None:
                        continue
                    _bar_eff = len(bp.energies) * _grass_mult()
                    if _bar_eff >= _bar_req:
                        _bench_attacker_ready = True
                        break
                    if (_grass_attach_this_turn
                            and _bar_eff + _grass_attach_unit() >= _bar_req):
                        _bench_attacker_ready = True
                        break
        
                # Pivote de rescate: si el activo es una pre-evolucion FRAGIL
                # (Chikorita/Bayleef) CONDENADA este turno (probable KO) y en la
                # banca hay un cuerpo que SOBREVIVE al mejor golpe rival, conviene
                # RETIRAR aunque el atacante de banca no pueda atacar todavia:
                # resguardamos la pre-evolucion (se evoluciona luego en banca),
                # subimos un muro que aguanta y refrescamos la mano (Lillie's se
                # habilita tras evolucionar). Mantener el cuerpo de poca vida al
                # frente solo lo entrega gratis y frena la linea de evolucion.
                _fragile_doomed_pivot = False
                if (can_switch and active.id in (Chikorita, Bayleef)
                        and (active_ko_likely
                             or estimated_op_damage >= (active.hp or 0))):
                    for _fdp_bp in my_state.bench:
                        if _fdp_bp is None:
                            continue
                        if (_fdp_bp.hp or 0) > _op_best_damage_vs(_fdp_bp):
                            _fragile_doomed_pivot = True
                            break
        
                # Pivote de LINEA EVOLUTIVA (user, registro_003 paso 29 vs
                # Dragapult, PERDIDA): el activo es un Chikorita con Bayleef
                # en la mano. El scorer de EVOLVE ya VETA evolucionar en el
                # ACTIVO cuando la pre-evolucion puede pagar su retirada
                # ("conviene RETIRARLO primero y evolucionarlo ya en la
                # banca", ver la rama Bayleef/_is_active), pero aqui el
                # retiro quedaba vetado porque el atacante de banca (Tapu
                # Bulu) aun no tenia energia, asi que el agente se quedaba
                # con el Chikorita arriba y gastaba el turno en Growl (0 de
                # dano) con la linea de Meganium muerta en la mano. Retirar
                # es la jugada: sube un cuerpo con mas vida y el Chikorita
                # evoluciona en la BANCA -- con Forest of Vitality en juego,
                # incluso la cadena Chikorita->Bayleef->Meganium entera este
                # mismo turno. Ademas Wild Growth de Meganium DUPLICA cada
                # Planta: baja de 4 a 2 las Plantas FISICAS que Tapu Bulu
                # necesita para Wood Hammer. Solo si la pre-evolucion puede
                # evolucionar de verdad este turno (lleva en juego desde el
                # inicio del turno, o Forest lo permite aunque acabe de
                # jugarse) y hay un cuerpo en banca al que promover.
                _evo_line_bench_pivot = (
                    can_switch
                    and active.id == Chikorita
                    and hand_counts.get(Bayleef, 0) >= 1
                    and bench_count >= 1
                    and not _active_can_ko_now
                    and (ESTADO.forest_in_play
                         or not getattr(active, 'appearThisTurn', False)))
        
                if active.id in (Chikorita, Bayleef, Meganium):
        
                    # Regla (user, log 86607718 turno 2, vs Crustle, PERDIMOS):
                    # vs Crustle, si el ACTIVO es un Chikorita y NO hay ningun
                    # Chikorita en la banca, la prioridad es RETIRARLO (para
                    # evolucionarlo a Meganium en banca y subir un cuerpo util),
                    # AUNQUE en la banca no haya todavia un atacante LISTO (el
                    # veto de "atacante de banca sin energia" de abajo lo
                    # bloqueaba). Chikorita activo es un lastre que no daña al
                    # muro. Requiere poder retirar (can_switch: ya cargamos 1
                    # Planta al Chikorita, ver energy_score) y tener un cuerpo en
                    # banca al que promover. La promocion prefiere un atacante y,
                    # si no hay, un ex (Ogerpon ex primero, ver _best_promote).
                    if (ESTADO.op_is_crustle_deck and active.id == Chikorita
                            and field_counts.get(Chikorita, 0) <= 1
                            and bench_count >= 1):
                        score = 6500
                    elif _has_bench_attacker and _bench_attacker_ready:
                        score = 6000
                    elif _fragile_doomed_pivot:
                        # Activo fragil condenado: retirar para subir un cuerpo
                        # que sobrevive y resguardar la pre-evolucion, aunque el
                        # atacante de banca no pueda atacar aun. Gana sobre atacar
                        # con un cuerpo que morira el proximo turno.
                        score = 5800
                    elif _evo_line_bench_pivot:
                        # Chikorita activo con Bayleef en mano: retirar para
                        # montar la linea de Meganium en la BANCA (ver el
                        # comentario del flag). Va por debajo de los pivotes
                        # de rescate pero POR ENCIMA de los dos vetos de
                        # "atacante de banca sin cargar", que son los que
                        # dejaban al Chikorita atacando por chip.
                        score = 5700
                    elif _has_bench_attacker and not _bench_attacker_ready:
                        # Hay un atacante en banca pero SIN energia para
                        # atacar este turno: retirar ahora solo subiria un
                        # cuerpo que tampoco ataca. Mejor mantener el activo
                        # y seguir cargando al atacante de la banca.
                        score = SCORE_VETO
                    elif _bench_has_only_non_attackers and _has_attacker_in_hand:
        
                        score = SCORE_VETO
                    else:
                        score = 5500
                elif active.id == Meowth_ex:
        
                    _ATK_REQS_RETREAT = {
                        Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
                        Tapu_Bulu: 4, Fezandipiti_ex: 3,
                    }
                    _has_ready_bench_for_meowth = False
                    for bp in my_state.bench:
                        if bp is None or bp.id not in _ATK_REQS_RETREAT:
                            continue
                        _bp_eff_m = len(bp.energies) * _grass_mult()
                        if _bp_eff_m >= _ATK_REQS_RETREAT[bp.id]:
                            _has_ready_bench_for_meowth = True
                            break
        
                    _meowth_data_r = card_table.get(Meowth_ex)
                    _op_act_r = op_state.active[0] if op_state.active else None
                    _op_act_data_r = card_table.get(_op_act_r.id) if _op_act_r is not None else None
                    _meowth_weak_to_op = (
                        _meowth_data_r is not None and getattr(_meowth_data_r, 'weakness', None) is not None and
                        _op_act_data_r is not None and
                        getattr(_op_act_data_r, 'energyType', None) == _meowth_data_r.weakness)
                    _safe_chargeable_body = False
                    if _meowth_weak_to_op:
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_data_r = card_table.get(bp.id)
                            _bp_weak_r = (
                                _bp_data_r is not None and getattr(_bp_data_r, 'weakness', None) is not None and
                                _op_act_data_r is not None and
                                getattr(_op_act_data_r, 'energyType', None) == _bp_data_r.weakness)
                            if _bp_weak_r:
                                continue
                            _bp_e_r = len(bp.energies)
                            _bp_eff_r = _bp_e_r * _grass_mult()
        
                            if bp.id == Teal_Mask_Ogerpon_ex and _bp_eff_r >= 2:
                                _safe_chargeable_body = True
                                break
                            elif bp.id == Hydrapple_ex and _bp_eff_r >= 2:
                                _safe_chargeable_body = True
                                break
                            elif bp.id == Dipplin and _bp_e_r >= 1:
                                _safe_chargeable_body = True
                                break
                            elif bp.id == Tapu_Bulu and _bp_eff_r >= 4:
                                _safe_chargeable_body = True
                                break
                            elif bp.id == Meganium and _bp_eff_r >= 4:
                                _safe_chargeable_body = True
                                break
        
                    if _meowth_weak_to_op and _safe_chargeable_body:
                        score = 6000
                    elif _has_ready_bench_for_meowth:
                        score = 5000
                    else:
                        score = SCORE_VETO
                elif _has_bench_attacker:
                    score = 3000
                elif _bench_has_only_non_attackers and _has_attacker_in_hand:
        
                    score = SCORE_VETO
                else:
                    score = 2500
        
            elif active.id in STRATEGIC_ATTACKERS:
        
                # Listo-para-atacar via energia efectiva (fuente unica:
                # ATTACK_ENERGY_REQ). El branch ya garantiza pertenencia a
                # STRATEGIC_ATTACKERS (= MAIN_ATTACKERS).
                _active_can_attack = _can_attack_eff(active.id, active_energy)
        
                if not _active_can_attack:
        
                    _has_ready_bench = False
                    for bp in my_state.bench:
                        if bp is None:
                            continue
                        # Cuenta cualquier atacante principal listo en banca
                        # (incluye Meganium, antes omitido).
                        if (bp.id in MAIN_ATTACKERS
                                and _can_attack_eff(bp.id, len(bp.energies))):
                            _has_ready_bench = True
                            break
        
                    if _has_ready_bench:
                        score = 2500
                    else:
                        score = SCORE_VETO
        
                elif (can_switch
                      and estimated_op_damage > 0
                      and estimated_op_damage >= (active.hp or 0)
                      and not (ESTADO.plan.remain_hp is not None
                               and ESTADO.plan.remain_hp <= 0)):
                    # RETIRO DEFENSIVO: nuestro atacante activo PUEDE atacar
                    # pero sera noqueado el proximo turno (dano estimado del
                    # rival >= sus HP) y atacar con el no noquea al activo
                    # rival. Si en la banca hay un atacante MAS resistente
                    # que sobrevive al ataque rival y puede atacar tras subir,
                    # retirarse a el evita la derrota (muro que ademas
                    # presiona). Sin esto el codigo asume "si puedo atacar,
                    # ataco" y deja morir al activo condenado.
                    _def_retreat_target = False
                    for bp in my_state.bench:
                        if bp is None or bp.id not in MAIN_ATTACKERS:
                            continue
                        if (bp.hp or 0) <= _op_best_damage_vs(bp):
                            continue  # tambien seria noqueado el proximo turno
                        if _can_attack_eff(bp.id, len(bp.energies)):
                            _def_retreat_target = True
                            break
                    if _def_retreat_target:
                        score = 5600
                    else:
                        score = SCORE_VETO
        
                elif (active.id in (Hydrapple_ex, Tapu_Bulu) and
                      op_state.active and op_state.active[0] is not None and
                      op_state.active[0].id == Drednaw):
                    _has_shell_bypass_bench = False
                    for bp in my_state.bench:
                        if bp is None:
                            continue
                        _bp_energy = len(bp.energies)
                        _bp_effective = _bp_energy * _grass_mult()
                        if bp.id == Meganium and _bp_effective >= 4:
                            _has_shell_bypass_bench = True
                            break
                        elif bp.id == Dipplin and _bp_energy >= 1:
                            _has_shell_bypass_bench = True
                            break
                    if _has_shell_bypass_bench:
                        score = 5500
                    else:
                        score = SCORE_VETO
        
                elif (active.id in OUR_EX_IDS and
                      op_state.active and op_state.active[0] is not None and
                      op_state.active[0].id == Sylveon):
                    _has_nonex_bench = False
                    for bp in my_state.bench:
                        if bp is None:
                            continue
                        _bp_energy = len(bp.energies)
                        _bp_effective = _bp_energy * _grass_mult()
                        if bp.id == Tapu_Bulu and _bp_effective >= 4:
                            _has_nonex_bench = True
                            break
                        elif bp.id == Meganium and _bp_effective >= 4:
                            _has_nonex_bench = True
                            break
                        elif bp.id == Dipplin and _bp_energy >= 1:
                            _has_nonex_bench = True
                            break
                    if _has_nonex_bench:
                        score = 5500
                    else:
                        score = SCORE_VETO
        
                elif (neutralization_zone_active and active.id in OUR_EX_IDS):
                    _has_nz_bypass_bench = False
                    for bp in my_state.bench:
                        if bp is None:
                            continue
                        _bp_energy = len(bp.energies)
                        _bp_effective = _bp_energy * _grass_mult()
                        if bp.id == Tapu_Bulu and _bp_effective >= 4:
                            _has_nz_bypass_bench = True
                            break
                        elif bp.id == Meganium and _bp_effective >= 4:
                            _has_nz_bypass_bench = True
                            break
                        elif bp.id == Dipplin and _bp_energy >= 1:
                            _has_nz_bypass_bench = True
                            break
                        elif bp.id == Pinsir and _bp_effective >= 2:
                            _has_nz_bypass_bench = True
                            break
        
                    _op_act = op_state.active[0] if op_state.active else None
                    _op_act_has_rb = False
                    if _op_act is not None:
                        _op_act_data = card_table[_op_act.id]
                        _op_act_has_rb = (_op_act_data.ex or _op_act_data.megaEx)
                    if _has_nz_bypass_bench and not _op_act_has_rb:
                        score = 5000
                    else:
                        score = SCORE_VETO
                else:
                    score = SCORE_VETO
            else:
                score = SCORE_VETO
        else:
            score = SCORE_VETO
        
        # Cancelar la retirada si solo reubicaria al mismo Pokemon (misma
        # especie) al activo: es inutil y malgasta la energia del coste de
        # retirada (user, log 86510119 paso 26). Ver `_same_species_retreat`.
        # EXCEPCION (user, registro_005 vs Comfey): si el activo esta CONFUNDIDO
        # (Brambleghast), retirarlo para promover un cuerpo de la MISMA especie
        # SI aporta: el nuevo activo NO esta confundido y puede atacar sin la
        # moneda. Con dos Teal Mask Ogerpon ex (el plan del matchup) este es el
        # caso normal, asi que no se veta la retirada de escape de confusion.
        if (_same_species_retreat and score > 0 and not _conf_should_retreat
                and not _suicide_swap_win_promote):
            score = SCORE_VETO
        
        # Pivote vs Alakazam (user, registro_010 paso 127): retirar el ex
        # activo para promover un cuerpo de 1 premio (Meganium/Tapu Bulu) que
        # NOQUEA al activo rival (ver `_alakazam_pivot_1prize`). Debe SUPERAR
        # al ataque del ex de 2 premios (score ~1100) para que el motor retire
        # en vez de atacar con el ex; sigue por debajo del umbral de
        # "Supporter antes de retirar" (2000) para respetar ese orden.
        if _alakazam_pivot_1prize:
            score = max(score, 6000)
        
        # Regla (user, registro 004 paso 53 vs Archaludon ex, GANADA):
        # SIEMPRE jugar el Supporter (Dawn / Lillie's / Lana's Aid) ANTES de
        # retirar. Retirar primero desaprovecha lo que el Supporter aporta al
        # resto del turno (p.ej. Dawn busca la linea Applin -> Dipplin ->
        # Hydrapple ex que se evoluciona con Forest ESTE mismo turno, y solo
        # despues conviene retirar el Fezandipiti ex y promover al Hydrapple
        # ex). El retiro NO lo bloquea jugar el Supporter (sigue disponible
        # despues), asi que se POSPONE: se rebaja su score por debajo de la
        # jugada del Supporter (>=2400) para que el motor elija primero el
        # Supporter y re-evalue el retiro en la siguiente decision.
        # EXCEPCION: el relevo del remate suicida CIERRA la partida este turno
        # (user, registro_016 paso 184). No hay "resto del turno" al que el
        # Supporter pueda aportar nada, y posponer el retiro es justo lo que
        # deja al agente atacando con el suicida y firmando el empate.
        if (score > 2000 and not state.supporterPlayed
                and not _suicide_swap_win_promote):
            _rt_supp_first = any(
                hand_counts.get(_sid, 0) >= 1 and _supp_values.get(_sid, 0) > 0
                for _sid in (Dawn, Lillie_Determination, Lanas_Aid))
            if _rt_supp_first:
                score = 2000
        
        # Regla anti-Cubchoo (user, registro_004 paso 47/49 vs
        # cornerstone_cubchoo, PERDIDA): el mazo de Cubchoo/Beartic bloquea
        # nuestro activo cada turno -- Snotted Up (506) y Sheer Cold (507)
        # dejan al Defensor "sin poder usar ataques" el turno siguiente --,
        # forzandonos a RETIRAR para atacar con otro cuerpo. Su atacante es
        # debilisimo (no nos noquea), pero como nos obliga a retirarnos una y
        # otra vez, CADA retirada que DESCARTA energia (coste pagado con la
        # energia del activo, sin carta de cambio gratis) sangra el recurso
        # que mas escasea contra este control. Contra ESTE mazo eliminamos la
        # retirada-pivote voluntaria: si retirar solo cambiaria de atacante y
        # gastaria energia, es preferible PASAR y conservarla. El activo NO
        # esta en peligro de KO (Cubchoo pega 10), asi que quedarse no cuesta
        # nada. Salvaguarda `not active_ko_likely`: si el activo SI va a morir
        # (p.ej. Beartic Sheer Cold sobre un cuerpo fragil), se permite la
        # retirada de rescate. La regla se limita a este matchup: contra
        # cualquier otro mazo la retirada-pivote sigue siendo correcta.
        # EXCEPCION: retirada que NOQUEA y no destruye inversion (user,
        # registro_036 paso 146). Las dos reglas del usuario conviven asi:
        #
        #  - registro_004 p47 (PASAR): el activo es un Ogerpon ex con TRES
        #    Plantas fisicas encima. Retirar tira una de esas tres: destruye
        #    energia ya invertida en el tablero, que es justo el recurso que
        #    el control de Cubchoo nos niega. Aunque haya KO detras, se pasa.
        #  - registro_036 p146 (RETIRAR): el activo tiene CERO energia -- no
        #    ataca ni se retira, es peso muerto. La Planta la ponemos nosotros
        #    ESE turno (Teal Dance, que ademas roba) con el unico proposito de
        #    pagar la retirada. No se destruye nada acumulado: se convierte
        #    una carta de la mano en un premio.
        #
        # Discriminante: energia FISICA del activo <= coste de retirada, es
        # decir que no queda excedente que perder. Mas `_bdg_retreat_ko` (el
        # mismo detector de `_attach_enable_retreat_ko`) para exigir que haya
        # KO de verdad y no un pivote pelado.
        _cc_ret_cost_pre = (RETREAT_COST.get(_active_reloc.id, 1)
                            if _active_reloc is not None else 1)
        _cc_cashes_dead_body = (
            _bdg_retreat_ko
            and _active_reloc is not None
            and _physical_energy(
                len(_active_reloc.energies)) <= _cc_ret_cost_pre)
        # El relevo del remate suicida gana la partida AHORA: conservar
        # energia para turnos futuros no significa nada si no hay futuro.
        #
        # COLISION Cubchoo <-> muro inmune (autopsia cornerstone_cubchoo,
        # jul 2026): `_ex_stuck_promo_ready` -- nuestro activo esta
        # BLOQUEADO por el muro (Cornerstone anula a los cuerpos con
        # Habilidad; Crustle/Sylveon a los ex) y en la banca hay un atacante
        # que SI le pega -- tambien exime. El veto existe para no destruir
        # energia invertida en el tablero, pero la energia de un cuerpo que
        # hace CERO al activo rival no esta invertida: esta muerta, y la
        # retirada es la unica via para convertirla en dano. Medido en 250
        # partidas vs cornerstone_cubchoo: con el muro delante, Tapu Bulu
        # cargado a >=4 en banca y la retirada LEGAL, subiamos a Tapu solo
        # el 13.7% de las veces en las derrotas por premios (36% en las
        # ganadas; vs Crustle -- mismo escenario SIN Cubchoo en el mazo --
        # es el 82.6-100%). El activo era Teal Mask Ogerpon ex en 167 de 169
        # de esos menus y el turno se cerraba ATACANDO por 0 (67 veces).
        if (op_is_cubchoo_deck and score > 0 and not active_ko_likely
                and not _cubchoo_lock_stuck
                and not _cc_cashes_dead_body
                and not _ex_stuck_promo_ready
                and not _suicide_swap_win_promote
                and _active_reloc is not None):
            _cc_ret_cost = RETREAT_COST.get(_active_reloc.id, 1)
            _cc_wastes_energy = (
                not has_switch_card
                and _cc_ret_cost >= 1
                and _physical_energy(
                    len(_active_reloc.energies)) >= _cc_ret_cost)
            if _cc_wastes_energy:
                score = SCORE_VETO
        return score
    finally:
        tc._b = _b
        tc._bench_attacker_ready = _bench_attacker_ready
        tc._bp_e = _bp_e
        tc._bp_eff = _bp_eff
        tc._e = _e
        tc._eff = _eff
        tc._has_bench_attacker = _has_bench_attacker
        tc._op_act = _op_act
        tc._our_first_turn = _our_first_turn
        tc._sid = _sid
        tc.bp = bp


__all__ = ['puntuar']
