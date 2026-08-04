"""Puntuacion de las opciones `EVOLVE`.

Rama `o.type == OptionType.EVOLVE` de la cadena de `agent()`, extraida VERBATIM.
Desempaqueta del contexto los 41 campos que lee y devuelve los
6 que reasigna; los demas quedan como estaban, igual que antes.
"""

from cg.api import AreaType
from ptcg.calculo.carta import get_card
from ptcg.calculo.dano import _our_effective_damage
from ptcg.calculo.energia import _grass_attach_unit, _grass_mult
from ptcg.calculo.tablero import _active_of
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Grand_Tree, Hydrapple_ex, Lillie_Determination, Meganium, RETREAT_COST, SCORE_VETO, Tapu_Bulu
from ptcg.cartas.tablas import card_table
from ptcg.estado.agente import ESTADO


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o`. Puede devolver `_SALTAR`."""
    _SALTAR = tc._SALTAR
    _atk = tc._atk
    _bp = tc._bp
    _gt_plan = tc._gt_plan
    _gt_planes_turno = tc._gt_planes_turno
    _gt_score_seleccion = tc._gt_score_seleccion
    _op_act = tc._op_act
    active_ko_likely = tc.active_ko_likely
    bench_count = tc.bench_count
    bp = tc.bp
    can_switch = tc.can_switch
    card = tc.card
    condition_blocks_action = tc.condition_blocks_action
    condition_urgency = tc.condition_urgency
    estimated_op_damage = tc.estimated_op_damage
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_condition = tc.has_condition
    has_hydrapple = tc.has_hydrapple
    my_index = tc.my_index
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    obs = tc.obs
    op_active_is_kangaskhan = tc.op_active_is_kangaskhan
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_drednaw_deck = tc.op_is_drednaw_deck
    op_is_fire_deck = tc.op_is_fire_deck
    op_is_mirror = tc.op_is_mirror
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_kang_ko_target = tc.op_kang_ko_target
    op_state = tc.op_state
    pokemon = tc.pokemon
    scores = tc.scores
    select = tc.select
    state = tc.state
    total_grass = tc.total_grass

    try:
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        # La carta de evolucion normalmente viene de la MANO, pero la
        # habilidad de Grand Tree la saca del MAZO. Se respeta `o.area`
        # cuando el simulador la informa (para el juego normal vale HAND,
        # asi que el comportamiento no cambia) en vez de asumir la mano.
        _evo_area = o.area if o.area is not None else AreaType.HAND
        card = get_card(obs, _evo_area, o.index, my_index)
        if (card is not None and select.effect is not None
                and select.effect.id == Grand_Tree):
            # Evolucion servida por Grand Tree: la decide el plan del
            # estadio, no las bandas de la evolucion desde la mano (que
            # asumen que se gasta una carta de la mano y que el cuerpo ya
            # estaba elegido).
            _gt_evo_score = _gt_score_seleccion(
                o, card, _gt_plan, _gt_planes_turno, my_state, field_counts)
            if pokemon is not None and _gt_plan is not None:
                # Desempate por el Basico elegido: la opcion apunta a la
                # vez a la carta y al cuerpo, asi que el objetivo del plan
                # tiene que ganar.
                if getattr(pokemon, 'serial', None) == _gt_plan.serial:
                    _gt_evo_score += 5000
            scores.append(_gt_evo_score)
            return _SALTAR   # ya hizo scores.append por su cuenta
        if card is not None and pokemon is not None:
            _is_active = (o.inPlayArea == AreaType.ACTIVE)
            _pkmn_energy = len(pokemon.energies)
            _has_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached)
        
            score = 9000 + _pkmn_energy
        
            if card.id == Meganium:
                score = 35000
                # vs Cornerstone Mask Ogerpon ex (user, registro_004 turno 4):
                # su Cornerstone Stance anula el dano de TODOS nuestros Pokemon
                # CON habilidad (Teal Mask Ogerpon ex, Hydrapple ex, Dipplin...),
                # asi que el unico atacante real es Tapu Bulu (Bayleef solo hace
                # chip). Meganium no dana a Cornerstone -- tambien tiene
                # habilidad -- pero su Wild Growth DUPLICA cada Planta, y con el
                # en juego Tapu Bulu ataca con 2 Plantas FISICAS en vez de 4.
                # Montar la linea es por tanto prioritario en este matchup.
                if (op_is_fire_deck or op_is_mirror or ESTADO.op_is_crustle_deck
                        or op_has_ability_immune_active
                        or ESTADO.op_is_cornerstone_deck):
                    score = 35500
        
                if pokemon.id == Chikorita:
                    score += 500
        
            elif card.id == Hydrapple_ex:
                score = 33000
        
                if ESTADO.op_is_crustle_deck and op_kang_ko_target:
        
                    score = 34500
                elif ESTADO.op_is_crustle_deck and op_active_is_kangaskhan:
        
                    score = 33000
                elif ESTADO.op_is_crustle_deck:
                    score = SCORE_VETO
                elif op_is_fire_deck:
                    score = 33500
        
                elif op_is_drednaw_deck:
                    _other_dipplin_count = field_counts.get(Dipplin, 0)
                    _has_hydrapple_already = field_counts.get(Hydrapple_ex, 0) >= 1
                    if _has_hydrapple_already:
        
                        score = 22000
                    elif _other_dipplin_count >= 2:
        
                        score = 32500
                    elif _other_dipplin_count >= 1 and not _is_active:
        
                        score = 32000
                    else:
        
                        score = 22000
        
                elif op_is_sylveon_deck and op_has_ex_immune_active:
                    _other_dipplin_count = field_counts.get(Dipplin, 0)
                    _has_hydrapple_already = field_counts.get(Hydrapple_ex, 0) >= 1
        
                    _tapu_ready_sv = any(
                        bp is not None and bp.id == Tapu_Bulu and
                        len(bp.energies) * _grass_mult() >= 4
                        for bp in list(my_state.active or []) + list(my_state.bench))
                    if _tapu_ready_sv:
                        score = 32500
                    elif _has_hydrapple_already:
                        score = 22000
                    elif _other_dipplin_count >= 2:
                        score = 32500
                    elif _other_dipplin_count >= 1 and not _is_active:
                        score = 32000
                    else:
                        score = 22000
        
                if pokemon.id == Applin and not ESTADO.op_is_crustle_deck:
                    score += 500
        
                # ── Regla: no malgastar un KO letal de Dipplin ──────────
                # Si el activo es un Dipplin al que, cargandole 1 energia
                # Grass este turno, "Do the Wave" (20 x banca) noquearia al
                # Pokemon activo rival, PERO al evolucionar a Hydrapple ex NO
                # podriamos noquear este turno (Syrup Storm exige 2 energias),
                # NO evolucionamos: conservamos el Dipplin para atacar y
                # llevarnos el KO. Reglas del usuario:
                #   (1) Dipplin noquea y Hydrapple no -> NO evolucionar.
                #   (2) Dipplin no noquea -> evolucionar con normalidad.
                #   (3) sin energia disponible -> evolucionar (protege Dipplin).
                if _is_active and pokemon.id == Dipplin:
                    _dip_can_attack_now = (_pkmn_energy >= 1 or _has_energy_in_hand)
                    if _dip_can_attack_now:
                        _op_act_evo = (op_state.active[0]
                                       if op_state.active and op_state.active[0] is not None
                                       else None)
                        if _op_act_evo is not None and (_op_act_evo.hp or 0) > 0:
                            _dip_dmg = _our_effective_damage(
                                pokemon, _op_act_evo, 20 * bench_count,
                                ESTADO.meganium_in_play, neutralization_zone_active)
                            _dip_kos = (_dip_dmg > 0 and _dip_dmg >= (_op_act_evo.hp or 0))
                            # Energia efectiva de Hydrapple ex tras evolucionar
                            # (hereda la energia del Dipplin + posible adjunto).
                            _hydra_eff = _pkmn_energy * _grass_mult()
                            if _has_energy_in_hand:
                                _hydra_eff += _grass_attach_unit()
                            _hydra_kos = False
                            if _hydra_eff >= ESTADO.ATTACK_ENERGY_REQ[Hydrapple_ex]:
                                _hydra_grass = total_grass + (1 if _has_energy_in_hand else 0)
                                _hydra_dmg = _our_effective_damage(
                                    pokemon, _op_act_evo, 30 + 30 * _hydra_grass,
                                    ESTADO.meganium_in_play, neutralization_zone_active)
                                _hydra_kos = (_hydra_dmg > 0 and _hydra_dmg >= (_op_act_evo.hp or 0))
                            if _dip_kos and not _hydra_kos:
                                score = SCORE_VETO
        
            elif card.id == Bayleef:
        
                if _is_active:
                    if has_condition and condition_blocks_action:
        
                        score = 34000 + condition_urgency
                    elif not can_switch:
        
                        score = 31300
                    else:
                        # Activo evolucionable (p.ej. Chikorita) que SI puede
                        # cambiar de activo. Por defecto NO se evoluciona en el
                        # activo (dejaria un Bayleef fragil arriba). Dos
                        # escenarios ajustan este veto:
                        _evo_active_rc = RETREAT_COST.get(pokemon.id, 1)
                        _evo_active_eff = _pkmn_energy * _grass_mult()
                        _evo_can_attach_now = (
                            hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                            not state.energyAttached)
                        _evo_eff_after_attach = _evo_active_eff + (
                            _grass_attach_unit() if _evo_can_attach_now else 0)
                        if _evo_active_eff >= _evo_active_rc:
                            # Escenario 1: ya tiene energia cargada para pagar
                            # la retirada -> conviene RETIRARLO primero y
                            # evolucionarlo ya en la banca. Se mantiene el veto;
                            # la logica de retiro sube un atacante de banca y el
                            # Chikorita evoluciona despues desde la banca.
                            score = SCORE_VETO
                        elif (hand_counts.get(Lillie_Determination, 0) >= 1
                                and not state.supporterPlayed):
                            # Escenario 2: no puede pagar la retirada con su
                            # energia actual, pero tenemos Lillie's Determination
                            # en mano y podremos cargar energia despues de
                            # jugarla -> evolucionamos el activo a Bayleef ahora.
                            score = 31300
                        elif _evo_eff_after_attach >= _evo_active_rc:
                            # Escenario 1 (variante): se le puede cargar energia
                            # este turno para pagar la retirada -> retirar primero
                            # y evolucionar en banca. Se mantiene el veto.
                            score = SCORE_VETO
                        else:
                            score = SCORE_VETO
                else:
                    score = 32000
                    if op_is_fire_deck or op_is_mirror or ESTADO.op_is_crustle_deck:
                        score = 32500
                    if op_is_cubchoo_deck:
                        # Cambio 4 (user): la linea de Meganium es la PRIORIDAD
                        # principal de evolucion vs Cubchoo, por delante de la
                        # linea de Hydrapple ex (Dipplin->Hydrapple = 33000).
                        # Meganium final ya vale 35000 (> este 34000).
                        score = 34000
        
            elif card.id == Dipplin:
        
                if _pkmn_energy >= 1 or _has_energy_in_hand:
                    score = 31500
                    if op_has_ex_immune_active or op_has_ex_immune_bench:
                        if not has_hydrapple:
                            score = 32000
        
                    if op_is_drednaw_deck:
                        score = 33000
        
                    elif op_is_sylveon_deck:
                        score = 32500
                else:
        
                    score = 25000
                    if op_is_drednaw_deck:
                        score = 31000
                    elif op_is_sylveon_deck:
                        score = 30500
        
            if _is_active and active_ko_likely and score > 0 and card.id != Meganium:
                _evo_effective_energy = _pkmn_energy * _grass_mult()
                if _has_energy_in_hand:
                    _evo_effective_energy += _grass_attach_unit()
                _evo_can_attack = False
                if card.id == Hydrapple_ex:
                    _evo_can_attack = (_evo_effective_energy >= 2)
                elif card.id == Dipplin:
                    _evo_can_attack = (_pkmn_energy >= 1 or _has_energy_in_hand)
                elif card.id == Bayleef:
                    _evo_can_attack = False
        
                if not _evo_can_attack and not (has_condition and _is_active):
                    score = 8000
        
                elif _evo_can_attack and card.id != Hydrapple_ex:
        
                    _evo_data = card_table.get(card.id)
                    _evo_max_hp = _evo_data.hp if (_evo_data and hasattr(_evo_data, 'hp')) else 0
        
                    _current_damage = pokemon.maxHp - pokemon.hp if hasattr(pokemon, 'maxHp') else 0
                    _evo_hp_after = _evo_max_hp - max(0, _current_damage)
        
                    _evo_op_damage = estimated_op_damage
                    if _evo_data:
                        _op_act = _active_of(op_state)
                        if _op_act is not None:
                            _op_act_data = card_table.get(_op_act.id)
                            if (_op_act_data and hasattr(_evo_data, 'weakness') and
                                    hasattr(_op_act_data, 'energyType') and
                                    _evo_data.weakness == _op_act_data.energyType):
        
                                _base_op_dmg = 0
                                if _op_act_data.attacks:
                                    for _atk in _op_act_data.attacks:
                                        if hasattr(_atk, 'damage') and _atk.damage is not None:
                                            _base_op_dmg = max(_base_op_dmg, _atk.damage)
                                _evo_op_damage = _base_op_dmg * 2
                            elif (hasattr(_evo_data, 'weakness') and
                                  hasattr(_op_act_data, 'energyType') and
                                  _evo_data.weakness != _op_act_data.energyType):
        
                                _base_op_dmg = 0
                                if _op_act_data.attacks:
                                    for _atk in _op_act_data.attacks:
                                        if hasattr(_atk, 'damage') and _atk.damage is not None:
                                            _base_op_dmg = max(_base_op_dmg, _atk.damage)
                                _evo_op_damage = _base_op_dmg
        
                    _evo_survives = (_evo_hp_after > _evo_op_damage)
        
                    if not _evo_survives:
        
                        _bench_has_same_preevo = False
                        for _bp in my_state.bench:
                            if _bp is not None and _bp.id == pokemon.id:
                                _bench_has_same_preevo = True
                                break
        
                        if _bench_has_same_preevo and not (has_condition and _is_active):
        
                            score = 8000
        
            # ANTI-CUBCHOO: NO evolucionar a un cuerpo LENTO que no llega a
            # su ataque (user, registro_034 paso 131 vs Cubchoo, PERDIDA).
            # Ese mazo bloquea y descarta energia, asi que un Pokemon con
            # coste de retirada ALTO (Hydrapple ex: 3) que ademas NO alcanza
            # su requisito de ataque queda CLAVADO: ni ataca ni se retira, y
            # regala un cuerpo de 2 premios plantado en el activo. En aquel
            # turno el Dipplin activo tenia 0 energias y aun asi se
            # evoluciono a Hydrapple ex (33000), quedando inutil el resto de
            # la partida.
            #
            # El gate es el COSTE DE RETIRADA (>= 3), que es la razon real:
            # en nuestro mazo solo lo cumple Hydrapple ex (Meganium/Bayleef/
            # Dipplin cuestan 2), pero asi cubre cualquier evolucion futura
            # igual de lenta. Va al FINAL de la rama para tener la ultima
            # palabra sobre las subidas de score de arriba.
            #
            # SOLO vs Cubchoo (`op_is_cubchoo_deck`): en el resto de
            # matchups la evolucion es desarrollo normal -- se recarga y se
            # retira sin problema, y el muro de 330 PV compensa.
            if (op_is_cubchoo_deck and score > 0
                    and RETREAT_COST.get(card.id, 1) >= 3):
                # Energia con la que contaria el cuerpo YA evolucionado: la
                # que hereda de la pre-evolucion mas el adjunte manual si
                # sigue disponible este turno.
                _cub_evo_eff = _pkmn_energy
                if _has_energy_in_hand:
                    _cub_evo_eff += _grass_attach_unit()
                if _cub_evo_eff < ESTADO.ATTACK_ENERGY_REQ.get(card.id, 99):
                    score = SCORE_VETO
        
            if has_condition and _is_active and score > 0:
                score += condition_urgency
        return score
    finally:
        tc._atk = _atk
        tc._bp = _bp
        tc._op_act = _op_act
        tc.bp = bp
        tc.card = card
        tc.pokemon = pokemon


__all__ = ['puntuar']
