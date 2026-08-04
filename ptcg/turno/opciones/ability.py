"""Puntuacion de las opciones `ABILITY`.

Rama `o.type == OptionType.ABILITY` de la cadena de `agent()`, extraida VERBATIM.
Desempaqueta del contexto los 53 campos que lee y devuelve los
2 que reasigna; los demas quedan como estaban, igual que antes.
"""

from cg.api import AreaType, Pokemon
from ptcg.calculo.carta import get_card
from ptcg.calculo.dano import _our_effective_damage
from ptcg.calculo.energia import _grass_attach_unit, _grass_mult, _ogerpon_base_phys_cap, _physical_energy
from ptcg.cartas.grupos import GT_SCORE_CADENA_COMPLETA, GT_SCORE_SOLO_FASE1
from ptcg.cartas.ids import Basic_Grass_Energy, Dipplin, FEZ_DRAW_ABILITY_SCORE, Fezandipiti_ex, Grand_Tree, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Pinsir, RIPEN_HEAL_ABILITY_SCORE, RIPEN_HEAL_EX_ABILITY_SCORE, SCORE_CARGA_ACTIVO_ATAQUE, SCORE_CARGA_ACTIVO_REMATE, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Unfair_Stamp
from ptcg.estado.agente import ESTADO


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o`. Puede devolver `_SALTAR`."""
    _ability_order_veto = tc._ability_order_veto
    _ability_unlock_retreat_attack = tc._ability_unlock_retreat_attack
    _ability_unlock_retreat_ko = tc._ability_unlock_retreat_ko
    _active_already_kos = tc._active_already_kos
    _active_hydra_cannot_ko = tc._active_hydra_cannot_ko
    _active_hydra_ready = tc._active_hydra_ready
    _active_needs_energy = tc._active_needs_energy
    _attach_enable_retreat_attack = tc._attach_enable_retreat_attack
    _attach_enable_retreat_ko = tc._attach_enable_retreat_ko
    _bench_attacker_ready = tc._bench_attacker_ready
    _bench_has_chargeable = tc._bench_has_chargeable
    _bp = tc._bp
    _carga_activo_falta = tc._carga_activo_falta
    _carga_activo_habilita_ataque = tc._carga_activo_habilita_ataque
    _carga_activo_remata = tc._carga_activo_remata
    _enough_after_priorities = tc._enough_after_priorities
    _enough_for_both = tc._enough_for_both
    _extra_energy_enables_ko = tc._extra_energy_enables_ko
    _grass_anywhere_enables_syrup_ko = tc._grass_anywhere_enables_syrup_ko
    _gt_plan = tc._gt_plan
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _hydrapple_bench_needs_energy = tc._hydrapple_bench_needs_energy
    _lillie_blocks_fez_ability = tc._lillie_blocks_fez_ability
    _ogerpon_lethal_focus_serial = tc._ogerpon_lethal_focus_serial
    _reserve_energy_for_hydra_evolve = tc._reserve_energy_for_hydra_evolve
    _reserve_hydra_active_charge = tc._reserve_hydra_active_charge
    _ripen_bench_ready_pivot = tc._ripen_bench_ready_pivot
    _ripen_bench_tapu_ko_pivot = tc._ripen_bench_tapu_ko_pivot
    _ripen_heal_ex = tc._ripen_heal_ex
    _ripen_heal_serial = tc._ripen_heal_serial
    _ripen_retreat_ko_pivot = tc._ripen_retreat_ko_pivot
    _stamp_blocks_supp_chain = tc._stamp_blocks_supp_chain
    _tapu_future_charge = tc._tapu_future_charge
    _teal_dance_ko_pivot = tc._teal_dance_ko_pivot
    _teal_wall_pivot = tc._teal_wall_pivot
    _win_via_boss_gust = tc._win_via_boss_gust
    card = tc.card
    hand_counts = tc.hand_counts
    my_index = tc.my_index
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    obs = tc.obs
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_hop_deck = tc.op_is_hop_deck
    op_kang_ko_target = tc.op_kang_ko_target
    op_state = tc.op_state
    scores = tc.scores
    state = tc.state

    try:
        card = get_card(obs, o.area, o.index, my_index)
        if card is not None:
            if card.id == Grand_Tree:
                # HABILIDAD DE GRAND TREE (estadio compartido, id 1249):
                # cadena Basico -> Fase 1 -> Fase 2 sacada del mazo, gratis
                # y una vez por turno. `_gt_plan` ya trae el mejor objetivo
                # (ver el bloque `_gt_*`); aqui solo se decide CUANTO vale
                # la jugada. Si no hay plan ejecutable -- primer turno,
                # ningun Basico elegible, cadena agotada en el mazo -- se
                # veta: activarla sin objetivo solo baraja el mazo.
                if _gt_plan is None:
                    score = SCORE_VETO
                elif _gt_plan.stage2_id:
                    score = GT_SCORE_CADENA_COMPLETA
                else:
                    # Cadena que se detiene en Fase 1 (Fase 2 agotada o
                    # desaconsejada por el matchup anti-ex). Sigue siendo
                    # desarrollo gratis, pero por debajo de la cadena
                    # completa y de la evolucion a Meganium desde la mano.
                    score = GT_SCORE_SOLO_FASE1
            elif card.id == Teal_Mask_Ogerpon_ex:
        
                _ogerpon_energy = len(card.energies) if isinstance(card, Pokemon) else 0
        
                _crustle_atk_needs_grass = False
                if ESTADO.op_is_crustle_deck and hand_counts.get(Basic_Grass_Energy, 0) == 1:
                    for _cng in (list(my_state.active or []) + list(my_state.bench or [])):
                        if _cng is None:
                            continue
                        _cng_e = len(_cng.energies)
                        if ((_cng.id == Tapu_Bulu and _cng_e < 4) or
                                (_cng.id == Dipplin and _cng_e < 1) or
                                (_cng.id == Pinsir and _cng_e < 2)):
                            _crustle_atk_needs_grass = True
                            break
        
                _td_ko_on_active = False
                if (o.area == AreaType.ACTIVE
                        and op_state.active and op_state.active[0] is not None
                        and not op_has_ex_immune_active
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                    _td_op_act = op_state.active[0]
                    _td_op_hp = _td_op_act.hp or 0
                    _td_eff_now = _ogerpon_energy
                    _td_eff_after = _ogerpon_energy + _grass_attach_unit()
                    # Myriad Leaf Shower = 30 + 30 por CADA energia unida a
                    # AMBOS activos (la propia MAS la del activo rival); de ahi
                    # el `_td_eff_now + _td_opp_e` de abajo. (El comentario
                    # anterior decia "solo energia propia": era un error ya
                    # corregido en `_attacker_base_damage`, el codigo siempre
                    # sumo las dos.) Se pasa por _our_effective_damage para
                    # aplicar debilidad Y RESISTENCIA (user, registro_012 paso
                    # 93: Duraludon resiste -30 a Planta, asi que Teal Dance
                    # habilita el KO al pasar de 4 a >=5 energias efectivas).
                    # `card` es el propio Teal Mask Ogerpon ex.
                    _td_opp_e = len(getattr(_td_op_act, 'energies', []) or [])
                    _td_base_now = (30 + 30 * (_td_eff_now + _td_opp_e)
                                    if _td_eff_now >= 3 else 0)
                    _td_base_after = (30 + 30 * (_td_eff_after + _td_opp_e)
                                      if _td_eff_after >= 3 else 0)
                    _td_dmg_now = _our_effective_damage(
                        card, _td_op_act, _td_base_now,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    _td_dmg_after = _our_effective_damage(
                        card, _td_op_act, _td_base_after,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    _td_ko_now = (_td_dmg_now > 0 and _td_dmg_now >= _td_op_hp)
                    _td_ko_after = (_td_dmg_after > 0 and _td_dmg_after >= _td_op_hp)
                    _td_ko_on_active = (_td_ko_after and not _td_ko_now)
                # Teal Dance del Ogerpon FOCO de carga letal (bench o activo):
                # se usa para acercarlo a las 3 energias del KO por debilidad
                # (user, registro_006 paso 62). A diferencia de `_td_ko_on_active`
                # (solo el ACTIVO), esto cubre un Ogerpon de BANCA que luego se
                # promueve. Exige que aun no llegue a 3 (no sobrecargar).
                _td_is_lethal_focus = (
                    _ogerpon_lethal_focus_serial is not None
                    and isinstance(card, Pokemon)
                    and getattr(card, 'serial', None) == _ogerpon_lethal_focus_serial
                    and _ogerpon_energy < 3)
                if hand_counts[Basic_Grass_Energy] < 1:
                    score = SCORE_VETO
                elif _carga_activo_remata and o.area == AreaType.ACTIVE:
                    # El ACTIVO que llega a su ataque LETAL con esta carga es
                    # este mismo Ogerpon: su Teal Dance adjunta la Planta Y
                    # ROBA, asi que hereda la banda del remate.
                    score = SCORE_CARGA_ACTIVO_REMATE
                elif _carga_activo_habilita_ataque and o.area == AreaType.ACTIVE:
                    # Espejo sin KO: la Planta deja atacar al Ogerpon activo
                    # (y roba) en un turno que si no seria esteril.
                    score = SCORE_CARGA_ACTIVO_ATAQUE
                elif ((_carga_activo_remata or _carga_activo_habilita_ataque)
                        and o.area != AreaType.ACTIVE
                        and hand_counts[Basic_Grass_Energy]
                            <= _carga_activo_falta):
                    # Teal Dance solo se adjunta a SI MISMA: en un Ogerpon de
                    # BANCA se comeria la Planta que el ACTIVO necesita para
                    # rematar hoy. Se veta mientras la mano no de para ambos
                    # (user, registro_006 paso 67 vs Marnie's Grimmsnarl).
                    score = SCORE_VETO
                elif ((_attach_enable_retreat_ko
                       or _ability_unlock_retreat_ko)
                        and o.area == AreaType.ACTIVE):
                    # TEAL DANCE que habilita la retirada hacia un atacante de
                    # banca LETAL (user, registro_036 paso 146 vs Cubchoo).
                    # `_attach_enable_retreat_ko` ya detecta la linea completa
                    # -- activo sin energia para retirarse + atacante de banca
                    # que NOQUEA -- y le da 41000 al adjunte MANUAL sobre el
                    # activo. Pero si ese activo es un Teal Mask Ogerpon ex con
                    # Teal Dance viva, el adjunte manual se veta por la
                    # precedencia "Teal Dance antes que el adjunte" y la linea
                    # se perdia entera: el agente acababa cargando un cuerpo de
                    # banca cualquiera (alli, un Tapu Bulu a 10 PV) y el KO no
                    # ocurria.
                    #
                    # La precedencia es correcta -- Teal Dance adjunta la misma
                    # Planta Y ADEMAS ROBA --, lo que faltaba era que la propia
                    # Teal Dance heredase la prioridad de esa linea letal. Va
                    # ANTES de los topes de energia por matchup (Cubchoo,
                    # Alakazam/Hop's, Crustle): esto no es sobrecargar, es la
                    # unica forma de pagar el coste de retirada.
                    #
                    # `_teal_dance_ko_pivot`/`_teal_wall_pivot` (31600) cubren
                    # solo el caso del MURO inmune con un atacante NO-ex; aqui
                    # el activo rival es atacable y el letal de banca es otro
                    # ex, asi que ninguno de los dos disparaba.
                    score = 41000
                elif ((_attach_enable_retreat_attack
                       or _ability_unlock_retreat_attack)
                        and o.area == AreaType.ACTIVE):
                    # Espejo no-letal del caso anterior (log 88162794 turnos
                    # 11/13): si el activo que necesita la energia para
                    # retirarse es este Ogerpon, su propia Teal Dance paga el
                    # coste Y ROBA, asi que hereda la prioridad del pivote --
                    # justo por encima del adjunte manual (31200) para no
                    # perder el robo, y por debajo de las lineas de KO (31500).
                    score = 31250
                elif _td_ko_on_active or _td_is_lethal_focus:
        
                    score = 31500
                elif _grass_anywhere_enables_syrup_ko:
                    # Teal Dance como ACELERADOR del Syrup Storm del
                    # Hydrapple ex ACTIVO (user, registro_006 paso 68 vs Mega
                    # Abomasnow ex, PERDIDA): la Planta suma al recuento de
                    # TODOS nuestros Pokemon, asi que este Ogerpon no
                    # necesita ganar nada con ella -- de hecho aqui los dos
                    # Ogerpon de banca ya estaban a 4 energias y la rama
                    # `_ogerpon_energy >= 3` los VETABA por "sobrecarga",
                    # dejando muerta en la mano la Planta que subia el
                    # ataque de 330 a 390 sobre 350 PV. Va ANTES de los
                    # topes por matchup (Cubchoo / Alakazam / Hop's /
                    # Crustle) por la misma razon que `_td_ko_on_active`:
                    # esto no es sobrecargar, es rematar.
                    #
                    # Desempate entre varios Ogerpon: la Planta habilita el
                    # mismo KO caiga donde caiga, asi que se prefiere el que
                    # AUN NO llega a su propio ataque (< 3 efectivas) -- de
                    # paso queda listo como segundo atacante -- sobre el que
                    # ya estaba cargado (registro_008 paso 94).
                    score = 31500 if _ogerpon_energy < 3 else 31490
                elif (op_is_cubchoo_deck and
                        _physical_energy(_ogerpon_energy)
                        >= (2 if ESTADO.meganium_in_play else 4)):
                    # Matchup Cubchoo (user): no sobrecargar al Ogerpon con
                    # Teal Dance mas alla del tope FISICO (2 con Meganium / 4
                    # sin). len(energies) viene DUPLICADO por Wild Growth con
                    # Meganium, por eso convertimos a cartas fisicas antes de
                    # comparar. No se necesita mas energia para atacar.
                    # Excepcion: si habilita un KO (arriba, _td_ko_on_active).
                    score = SCORE_VETO
                elif ((op_is_alakazam_deck or op_is_hop_deck)
                        and _physical_energy(_ogerpon_energy)
                        >= _ogerpon_base_phys_cap(ESTADO.meganium_in_play,
                                                  op_is_hop_deck)):
                    # Regla (user, vs Alakazam y vs Hop's): tope de energia
                    # para Teal Mask Ogerpon ex via Teal Dance. Base FISICA =
                    # 2 con Meganium (Wild Growth duplica cada Planta), 3 sin
                    # Meganium vs Hop's y 4 sin Meganium vs Alakazam. En
                    # BANCA es DURO; en el ACTIVO la energia extra solo se
                    # permite si HABILITA el KO al activo rival, caso ya
                    # resuelto arriba por _td_ko_on_active (31500) -- la
                    # UNICA razon para pasar del tope con Teal Dance. Fuera
                    # de esa excepcion no sobrecargamos: reservamos energia.
                    # len(energies) es EFECTIVA => se pasa a cartas fisicas.
                    score = SCORE_VETO
                elif _teal_wall_pivot and o.area == AreaType.ACTIVE:
                    # Activo condenado (Teal Mask Ogerpon ex) que no puede
                    # atacar + Hydrapple ex (muro) en banca: usar Teal Dance
                    # en el ACTIVO (adjunta Grass + ROBA 1) para habilitar su
                    # retirada (coste 1) y luego subir al cuerpo mas fuerte.
                    # Debe GANAR al adjunte manual (~31200) para aprovechar el
                    # robo y no malgastar la energia del turno.
                    score = 31600
                elif _teal_dance_ko_pivot and o.area == AreaType.ACTIVE:
                    # Pivote Teal Dance -> retirar -> promover atacante letal
                    # (user, log 85802744 turno 16): activo Teal Mask Ogerpon
                    # ex bloqueado por el muro Crustle que aun no puede
                    # retirarse, con un atacante no-ex LISTO en banca (Tapu
                    # Bulu, 220 de dano) que noquea al muro. Teal Dance en el
                    # activo adjunta la Planta (+ROBA) y habilita la retirada
                    # de coste 1 para subir a Tapu y noquear el proximo paso.
                    # Debe GANAR al adjunte manual a Dipplin (~31000).
                    score = 31600
                elif (((ESTADO.op_is_crustle_deck and not op_kang_ko_target)
                        or ESTADO.op_is_cornerstone_deck
                        or op_has_ability_immune_active)
                        and _physical_energy(_ogerpon_energy) >= 2):
                    # Regla (user, vs Crustle, log 86583376 paso 84): un Teal
                    # Mask Ogerpon ex no puede tener mas de DOS energias
                    # FISICAS cargadas via Teal Dance. Contra el muro Crustle
                    # (que inmuniza a nuestros ex) Ogerpon no ataca al muro,
                    # asi que reservamos energia y no lo sobrecargamos. La
                    # UNICA excepcion (Ogerpon ACTIVO cuya 3a energia habilita
                    # el KO del activo rival) ya se resolvio arriba con
                    # _td_ko_on_active (31500). Se conserva ademas el bypass
                    # op_kang_ko_target (KO de Mega Kangaskhan ex con Hydrapple
                    # ex, donde la energia extra sube el dano de Syrup Storm).
                    # len(energies) es EFECTIVA (Wild Growth duplica) => se
                    # pasa a cartas fisicas con _physical_energy.
                    #
                    # EXTENSION a Cornerstone (autopsia v2.1 p025 t20, ciclo
                    # jul 2026; mismo patron que d801d57 amplio la whitelist
                    # anti-Cubchoo): Cornerstone Stance anula el dano de
                    # nuestros Pokemon CON habilidad, asi que este Ogerpon
                    # tampoco ataca alli -- y el agente le acumulo 3 fisicas
                    # via Teal Dance (un cuerpo muerto de 6 efectivas)
                    # mientras Tapu Bulu, EL atacante del matchup, moria de
                    # hambre a 1 fisica con la mano sin energia. El tope de
                    # 2 redirige el excedente: la regla de energy_score
                    # "cornerstone -> Tapu +22000" ya existia y ahora la
                    # energia le llega. `op_has_ability_immune_active` cubre
                    # ademas cualquier muro anti-habilidad posicional
                    # (Sylveon...). La excepcion _td_ko_on_active (arriba)
                    # sigue cubriendo el activo rival atacable del mazo
                    # mixto (Cubchoo/Beartic delante).
                    score = SCORE_VETO
                elif _crustle_atk_needs_grass:
        
                    score = 7500
                elif _reserve_energy_for_hydra_evolve and o.area != AreaType.ACTIVE:
        
                    score = 7500
                elif _ogerpon_energy >= 3:
        
                    if (o.area == AreaType.ACTIVE
                            and (_win_via_boss_gust or _gust_2prize_via_boss)):
                        # Combo Myriad ganador (user, registro_012 paso 227
                        # vs Iono, PERDIDA): este turno hay un remate via
                        # Boss's Orders (gustear de la banca rival un
                        # objetivo que NOQUEAMOS para cobrar los premios que
                        # faltan) y el atacante es este Ogerpon activo. Sin
                        # esta rama, el veto de abajo ("ya tiene >=3 energias
                        # y ya noquea al activo rival, no gastes mas Plantas")
                        # mataba la habilidad, y como el adjunte manual al
                        # activo esta vetado a su vez por la PRECEDENCIA de
                        # Teal Dance, la energia acababa en un cuerpo de
                        # banca y la linea ganadora se perdia. El objetivo
                        # del gusteo no es el activo rival: la energia extra
                        # es justo la que sube Myriad hasta su vida. Score
                        # sobre las demas ramas de Teal Dance (31600) y
                        # >= 29000, para conservar el tier ENERGY y jugarse
                        # ANTES del PLAY de Boss's (tier 0).
                        score = 31700
                    elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, _ogerpon_energy):
                        score = 29000
                    elif _active_already_kos and o.area != AreaType.ACTIVE:
        
                        score = 31050
                    elif (o.area == AreaType.ACTIVE and _bench_attacker_ready
                            and not _active_already_kos):
        
                        score = 31050
                    else:
                        score = SCORE_VETO
                elif _active_hydra_ready:
        
                    score = 31300
                elif (_active_needs_energy and not _enough_for_both and ESTADO.plan.attacker < 1
                        and not (
                            ((state.turn == 1 and ESTADO.we_go_first) or
                             (state.turn == 2 and not ESTADO.we_go_first))
                            and o.area == AreaType.ACTIVE
                            and card.id in (Teal_Mask_Ogerpon_ex, Tapu_Bulu))):
        
                    score = 7500
                elif _reserve_hydra_active_charge and o.area != AreaType.ACTIVE:
        
                    score = 7500
                elif _hydrapple_bench_needs_energy and not _enough_after_priorities:
        
                    score = 7500
                elif (o.area != AreaType.ACTIVE and
                        ((not _active_needs_energy) or _enough_for_both)):
        
                    score = 31500
                else:
        
                    score = 31000
            elif card.id == Hydrapple_ex:
        
                _hydra_energy = len(card.energies) if isinstance(card, Pokemon) else 0
                # Guard (user, log 85848966 paso 76, GANADO vs Crustle): NO
                # activar Ripening Charge si la Grass extra no tiene destino
                # util. Ripening Charge (una vez activada) OBLIGA a adjuntar
                # a algun Pokemon; si el activo es un Tapu Bulu YA cargado
                # (>=4 efectivas) y en banca no hay ningun atacante que
                # necesite energia (Tapu<4ef, Dipplin sin energia o
                # Meganium<4ef), energy_score (ATTACH_FROM) devuelve -1 para
                # TODAS las opciones -> el desempate elige la 1a (el ACTIVO)
                # y se sobrecarga al Tapu ya listo, malgastando una carta de
                # Grass de la mano (que con Meganium sirve para retiradas /
                # el proximo turno). Espeja el override de energy_score
                # (~L4326). Como Hydrapple ex es ex y NO daña a Crustle, no
                # se pierde ningun Syrup Storm letal al no activarla.
                _ripen_wasted_vs_crustle = False
                if ESTADO.op_is_crustle_deck:
                    _rip_act = my_state.active[0] if my_state.active else None
                    _rip_active_tapu_full = (
                        _rip_act is not None and _rip_act.id == Tapu_Bulu
                        and len(_rip_act.energies) * _grass_mult() >= 4)
                    if _rip_active_tapu_full:
                        _rip_bench_needs = any(
                            _bp is not None and (
                                (_bp.id == Tapu_Bulu and len(_bp.energies) * _grass_mult() < 4)
                                or (_bp.id == Dipplin and len(_bp.energies) < 1)
                                or (_bp.id == Meganium and len(_bp.energies) * _grass_mult() < 4))
                            for _bp in (my_state.bench or []))
                        _ripen_wasted_vs_crustle = not _rip_bench_needs
                if hand_counts[Basic_Grass_Energy] < 1:
                    score = SCORE_VETO
                elif _carga_activo_remata:
                    # Ripening Charge adjunta a CUALQUIERA de nuestros
                    # Pokemon: es la via de carga que completa el coste de
                    # ataque del ACTIVO cuando el adjunte manual no basta (o
                    # ya se gasto). El objetivo -- el ACTIVO -- lo fija
                    # energy_score / ATTACH_FROM con la misma banda.
                    score = SCORE_CARGA_ACTIVO_REMATE
                elif _carga_activo_habilita_ataque:
                    # Espejo sin KO: sin esta carga el activo no ataca y el
                    # turno se cierra en blanco.
                    score = SCORE_CARGA_ACTIVO_ATAQUE
                elif _ripen_retreat_ko_pivot and o.area == AreaType.ACTIVE:
                    # Pivote Ripening -> retirar -> promover Tapu letal vs
                    # Crustle (user, log 86028607 turno 22): activo Hydrapple
                    # ex bloqueado por el muro con un Tapu de banca YA LISTO
                    # (220 de dano) que noquea a Crustle. Activar Ripening
                    # Charge para adjuntar una Planta al PROPIO Hydrapple y
                    # alcanzar su coste de retirada (efectivo), habilitando
                    # retirarlo y subir a Tapu para rematar. Debe GANAR a
                    # Teal Dance / adjuntes normales; el objetivo (activo
                    # Hydrapple) se fija en energy_score (ATTACH_FROM).
                    score = 31600
                elif _ripen_bench_tapu_ko_pivot and o.area == AreaType.ACTIVE:
                    # Pivote Ripening -> cargar Tapu de banca a letal ->
                    # retirar Hydrapple -> promover Tapu -> noquear al muro
                    # (user, log 86182112 paso 82): activo Hydrapple ex
                    # bloqueado por el muro Crustle y YA retirable, con un
                    # Tapu de banca en 2 efectivas que con 1 Planta mas llega
                    # a 4 (Wood Hammer 220, letal). Activar Ripening Charge
                    # para adjuntar la 2a Planta a Tapu (objetivo fijado en
                    # energy_score / ATTACH_FROM, +20000) en vez de malgastar
                    # el adjunte en Teal Dance sobre Ogerpon. Ver
                    # _ripen_bench_tapu_ko_pivot (~L4395).
                    score = 31600
                elif _ripen_wasted_vs_crustle:
                    score = SCORE_VETO
                elif _ability_unlock_retreat_ko:
                    # Ripening Charge que DESBLOQUEA LA RETIRADA hacia un
                    # atacante de banca LETAL (user, registro_014 paso 137 vs
                    # Alakazam). Espejo exacto de la rama homonima de Teal
                    # Dance: `_ability_unlock_retreat_ko` detecta la linea
                    # completa (activo sin energia para retirarse + cuerpo de
                    # banca que NOQUEA) y, a diferencia del adjunte manual,
                    # sigue viva con `energyAttached` ya gastado porque la
                    # habilidad adjunta aparte. Misma banda letal (41000): por
                    # encima de cualquier carga de desarrollo. El objetivo
                    # (el ACTIVO) se fija en energy_score / ATTACH_FROM.
                    score = 41000
                elif _ability_unlock_retreat_attack:
                    # Espejo no-letal: el atacante de banca solo hace CHIP,
                    # pero el activo no ataca ni se retira, asi que el turno
                    # entero depende de esta Planta. Banda 31250, la misma que
                    # usa Teal Dance para este caso.
                    score = 31250
                elif _hydra_energy >= 2:
                    if _extra_energy_enables_ko(Hydrapple_ex, _hydra_energy):
                        score = 29000
                    elif (o.area == AreaType.ACTIVE and _active_hydra_cannot_ko
                            and _bench_has_chargeable):
        
                        score = 30000
                    elif _tapu_future_charge:
                        # El activo ya asegura el KO: usamos Ripening Charge
                        # (adjunta a cualquier Pokemon) para poner una 2a
                        # energia en Tapu Bulu de banca y dejarlo listo
                        # (2 fisicas = 4 efectivas con Meganium). El objetivo
                        # Tapu Bulu se elige en energy_score (ATTACH_FROM).
                        score = 30000
                    elif _ripen_heal_serial is not None:
                        # Ripening Charge por su CURACION (user, registro_008
                        # paso 122 vs Marnie's Grimmsnarl ex, PERDIDA): el
                        # Hydrapple ya llega a su ataque, asi que la rama de
                        # abajo VETABA la habilidad y la ultima Planta de la
                        # mano se iba por el adjunte MANUAL (14000) -- misma
                        # energia en el campo pero SIN los 30 de curacion.
                        # Con el Dipplin de banca a 20/80 y Shadow Bullet
                        # metiendo 30 automaticos cada turno, esos 30 son la
                        # diferencia entre conservar el cuerpo y regalar un
                        # premio. El objetivo se fija en ATTACH_FROM.
                        #
                        # Si el cuerpo que sale de la ventana es un ex son
                        # DOS premios y la curacion gana tambien a Teal Dance
                        # (31500): un robo de una carta no vale dos premios
                        # (user, partida 2 turno 10 -- el agente eligio Teal
                        # Dance sobre el Ogerpon ex de banca a 80 PV, que
                        # murio ese mismo turno con 5 Plantas encima).
                        score = (RIPEN_HEAL_EX_ABILITY_SCORE if _ripen_heal_ex
                                 else RIPEN_HEAL_ABILITY_SCORE)
                    elif _ripen_bench_ready_pivot:
                        # SEGUNDO ATACANTE con la habilidad (user,
                        # registro_014 paso 137 vs Alakazam): el Hydrapple ya
                        # llega a su ataque, asi que todas las ramas de arriba
                        # miran solo si la Planta le sirve A EL y la habilidad
                        # se VETABA -- las Plantas acababan de forraje en el
                        # coste de una Ultra Ball. Pero Ripening Charge adjunta
                        # a CUALQUIERA de nuestros Pokemon: si con ella un
                        # atacante REAL de banca pasa de "no llega" a LISTO,
                        # es un cuerpo mas que ataca el proximo turno (o este
                        # mismo, si se retira el activo) por una carta que no
                        # tenia otro destino. Banda 30000, la de las demas
                        # cargas de banca por habilidad (`_tapu_future_charge`).
                        score = 30000
                    else:
                        score = SCORE_VETO
                elif _active_needs_energy and not _enough_for_both and o.area != AreaType.ACTIVE:
        
                    score = 7500
                else:
        
                    _hydra_eff = _hydra_energy * _grass_mult()
                    if _hydra_eff < 2:
        
                        if _hydra_energy == 0 and o.area != AreaType.ACTIVE:
                            score = 31150
                        else:
                            score = 31100
                    else:
        
                        score = 30500
            elif card.id == Fezandipiti_ex:
                # Orden correcto Unfair Stamp -> Flip the Script: mientras
                # tengamos Unfair Stamp jugable este turno (nos noquearon el
                # turno anterior y sigue en la mano) primero se juega Unfair
                # Stamp y DESPUES la habilidad de Fezandipiti. Asi el Stamp
                # no baraja de vuelta las 3 cartas que roba la habilidad;
                # quedan 5 (Stamp) + 3 (habilidad) = 8 cartas. Unfair Stamp
                # es Item: al jugarse sale de la mano y _stamp_blocks_supp_chain
                # pasa a False, re-habilitando la habilidad (30000).
                # Ademas, si tenemos Lillie's Determination en la mano (y aun
                # no jugamos Supporter), la jugamos ANTES que la habilidad.
                #
                # ATENCION (user, registro_006 paso 78 vs Archaludon ex,
                # PERDIDA): los dos son vetos de ORDEN, no de VALOR -- dicen
                # "primero X, DESPUES la habilidad". Si X no se va a jugar en
                # este menu no hay "despues" y el veto se convierte en una
                # perdida seca: Flip the Script es UNA VEZ POR TURNO y su
                # condicion (nos noquearon el turno anterior) no vuelve. Por
                # eso se registran como veto DIFERIBLE en
                # `_ability_order_veto` y se revocan mas abajo (ver el bloque
                # "REVOCAR VETOS DE ORDEN"), en vez de matar la habilidad
                # aqui de forma incondicional. El freno de deck-out, que si
                # es un veto de VALOR, se evalua ANTES y no se revoca nunca.
                if getattr(my_state, 'deckCount', 60) <= 4:
                    # FRENO DE DECK-OUT (autopsia crustle jul 2026): con
                    # el mazo en <=4, robar 3 con Flip the Script deja el
                    # mazo a <=1 y el robo obligatorio del proximo turno
                    # nos pone al borde de perder por deck-out. El draw
                    # opcional no vale la partida.
                    score = SCORE_VETO
                else:
                    # BANDA (user, registro_006 pasos 95-102, episodio
                    # 88710543 vs Mega Lucario): el robo de 3 va ANTES de
                    # gastar la energia del turno. Con 30000 la habilidad
                    # perdia contra Teal Dance (31300) y Ripening Charge
                    # (31100) menu tras menu y el turno se cerraba con la
                    # habilidad SIN USAR -- gratis, UNA VEZ POR TURNO y con
                    # su condicion (que nos noquearan) muerta al acabar el
                    # turno. Ademas el orden correcto es este por
                    # informacion: las 3 cartas nuevas pueden traer Plantas,
                    # asi que decidir los adjuntes DESPUES del robo es
                    # estrictamente mejor que al contrario. Se queda por
                    # DEBAJO de las bandas letales de esas mismas habilidades
                    # (41000/41900: la habilidad que HABILITA el KO de hoy
                    # sigue primero) y del remate ganador (_TIER_WIN_ATTACK):
                    # si la partida se cierra este turno, robar no aporta.
                    score = FEZ_DRAW_ABILITY_SCORE
                    _ab_order_blockers = tuple(
                        _blk_id for _blk_id, _blk_on in (
                            (Unfair_Stamp, _stamp_blocks_supp_chain),
                            (Lillie_Determination, _lillie_blocks_fez_ability))
                        if _blk_on)
                    if _ab_order_blockers:
                        _ability_order_veto[len(scores)] = (
                            score, _ab_order_blockers)
                        score = SCORE_VETO
            elif card.id == Meowth_ex:
        
                score = 30000
            elif card.id == 1267:
                score = 1
            else:
                score = 29000
        return score
    finally:
        tc._bp = _bp
        tc.card = card


__all__ = ['puntuar']
