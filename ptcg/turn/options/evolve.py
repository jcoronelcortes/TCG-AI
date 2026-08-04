"""Scoring of the `EVOLVE` options.

The `o.type == OptionType.EVOLVE` branch of the `agent()` chain, extracted
VERBATIM. It unpacks from the context the 41 fields it reads and returns the
6 it reassigns; the rest stay as they were, just like before.
"""

from cg.api import AreaType
from ptcg.calc.card import get_card
from ptcg.calc.damage import _our_effective_damage
from ptcg.calc.energy import _grass_attach_unit, _grass_mult
from ptcg.calc.board import _active_of
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Grand_Tree, Hydrapple_ex, Lillie_Determination, Meganium, RETREAT_COST, SCORE_VETO, Tapu_Bulu
from ptcg.cards.tables import card_table
from ptcg.state.agent_state import AGENT_STATE


def puntuar(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
    _SALTAR = tc._SALTAR
    _atk = tc._atk
    _bp = tc._bp
    _gt_plan = tc._gt_plan
    _gt_turn_plans = tc._gt_turn_plans
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
        # The evolution card normally comes from the HAND, but the Grand
        # Tree ability pulls it out of the DECK. `o.area` is respected
        # when the simulator reports it (for normal play it is HAND, so
        # the behaviour does not change) instead of assuming the hand.
        _evo_area = o.area if o.area is not None else AreaType.HAND
        card = get_card(obs, _evo_area, o.index, my_index)
        if (card is not None and select.effect is not None
                and select.effect.id == Grand_Tree):
            # Evolution served by Grand Tree: it is decided by the stadium's
            # plan, not by the bands of evolving from hand (which assume a
            # card in hand is spent and that the body was already chosen).
            _gt_evo_score = _gt_score_seleccion(
                o, card, _gt_plan, _gt_turn_plans, my_state, field_counts)
            if pokemon is not None and _gt_plan is not None:
                # Tie-break by the chosen Basic: the option points at both the
                # card and the body, so the plan's target has to win.
                if getattr(pokemon, 'serial', None) == _gt_plan.serial:
                    _gt_evo_score += 5000
            scores.append(_gt_evo_score)
            return _SALTAR   # it already did its own scores.append
        if card is not None and pokemon is not None:
            _is_active = (o.inPlayArea == AreaType.ACTIVE)
            _pkmn_energy = len(pokemon.energies)
            _has_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached)
        
            score = 9000 + _pkmn_energy
        
            if card.id == Meganium:
                score = 35000
                # vs Cornerstone Mask Ogerpon ex (user, registro_004 turn 4):
                # its Cornerstone Stance cancels the damage of ALL our Pokemon
                # WITH an ability (Teal Mask Ogerpon ex, Hydrapple ex, Dipplin...),
                # so the only real attacker is Tapu Bulu (Bayleef only chips).
                # Meganium does not damage Cornerstone -- it has an ability too --
                # but its Wild Growth DOUBLES every Grass, and with it in play
                # Tapu Bulu attacks with 2 PHYSICAL Grass instead of 4.
                # Assembling the line is therefore a priority in this matchup.
                if (op_is_fire_deck or op_is_mirror or AGENT_STATE.op_is_crustle_deck
                        or op_has_ability_immune_active
                        or AGENT_STATE.op_is_cornerstone_deck):
                    score = 35500
        
                if pokemon.id == Chikorita:
                    score += 500
        
            elif card.id == Hydrapple_ex:
                score = 33000
        
                if AGENT_STATE.op_is_crustle_deck and op_kang_ko_target:
        
                    score = 34500
                elif AGENT_STATE.op_is_crustle_deck and op_active_is_kangaskhan:
        
                    score = 33000
                elif AGENT_STATE.op_is_crustle_deck:
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
        
                if pokemon.id == Applin and not AGENT_STATE.op_is_crustle_deck:
                    score += 500
        
                # ── Rule: do not waste a lethal Dipplin KO ──────────────
                # If the active is a Dipplin for which, by charging 1 Grass
                # energy this turn, "Do the Wave" (20 x bench) would knock out
                # the opposing active Pokemon, BUT evolving into Hydrapple ex
                # would NOT let us knock out this turn (Syrup Storm demands 2
                # energies), we do NOT evolve: we keep the Dipplin to attack
                # and take the KO. User's rules:
                #   (1) Dipplin knocks out and Hydrapple does not -> do NOT evolve.
                #   (2) Dipplin does not knock out -> evolve as usual.
                #   (3) no energy available -> evolve (protects Dipplin).
                if _is_active and pokemon.id == Dipplin:
                    _dip_can_attack_now = (_pkmn_energy >= 1 or _has_energy_in_hand)
                    if _dip_can_attack_now:
                        _op_act_evo = (op_state.active[0]
                                       if op_state.active and op_state.active[0] is not None
                                       else None)
                        if _op_act_evo is not None and (_op_act_evo.hp or 0) > 0:
                            _dip_dmg = _our_effective_damage(
                                pokemon, _op_act_evo, 20 * bench_count,
                                AGENT_STATE.meganium_in_play, neutralization_zone_active)
                            _dip_kos = (_dip_dmg > 0 and _dip_dmg >= (_op_act_evo.hp or 0))
                            # Effective energy of Hydrapple ex after evolving
                            # (it inherits Dipplin's energy + a possible attachment).
                            _hydra_eff = _pkmn_energy * _grass_mult()
                            if _has_energy_in_hand:
                                _hydra_eff += _grass_attach_unit()
                            _hydra_kos = False
                            if _hydra_eff >= AGENT_STATE.ATTACK_ENERGY_REQ[Hydrapple_ex]:
                                _hydra_grass = total_grass + (1 if _has_energy_in_hand else 0)
                                _hydra_dmg = _our_effective_damage(
                                    pokemon, _op_act_evo, 30 + 30 * _hydra_grass,
                                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
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
                        # An evolvable active (e.g. Chikorita) that CAN switch out.
                        # By default we do NOT evolve in the active spot (it would
                        # leave a fragile Bayleef up front). Two scenarios adjust
                        # this veto:
                        _evo_active_rc = RETREAT_COST.get(pokemon.id, 1)
                        _evo_active_eff = _pkmn_energy * _grass_mult()
                        _evo_can_attach_now = (
                            hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                            not state.energyAttached)
                        _evo_eff_after_attach = _evo_active_eff + (
                            _grass_attach_unit() if _evo_can_attach_now else 0)
                        if _evo_active_eff >= _evo_active_rc:
                            # Scenario 1: it already has energy attached to pay the
                            # retreat -> it is better to RETREAT it first and evolve
                            # it once on the bench. The veto stands; the retreat
                            # logic brings up a benched attacker and the Chikorita
                            # evolves afterwards from the bench.
                            score = SCORE_VETO
                        elif (hand_counts.get(Lillie_Determination, 0) >= 1
                                and not state.supporterPlayed):
                            # Scenario 2: it cannot pay the retreat with its current
                            # energy, but we have Lillie's Determination in hand and
                            # will be able to attach energy after playing it -> we
                            # evolve the active into Bayleef now.
                            score = 31300
                        elif _evo_eff_after_attach >= _evo_active_rc:
                            # Scenario 1 (variant): energy can be attached to it this
                            # turn to pay the retreat -> retreat first and evolve on
                            # the bench. The veto stands.
                            score = SCORE_VETO
                        else:
                            score = SCORE_VETO
                else:
                    score = 32000
                    if op_is_fire_deck or op_is_mirror or AGENT_STATE.op_is_crustle_deck:
                        score = 32500
                    if op_is_cubchoo_deck:
                        # Change 4 (user): the Meganium line is the main evolution
                        # PRIORITY vs Cubchoo, ahead of the Hydrapple ex line
                        # (Dipplin->Hydrapple = 33000). The final Meganium is already
                        # worth 35000 (> this 34000).
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
        
            # ANTI-CUBCHOO: do NOT evolve into a SLOW body that does not reach
            # its attack (user, registro_034 step 131 vs Cubchoo, LOST).
            # That deck locks and discards energy, so a Pokemon with a HIGH
            # retreat cost (Hydrapple ex: 3) that ALSO fails to reach its
            # attack requirement ends up NAILED down: it neither attacks nor
            # retreats, and hands over a 2-prize body planted in the active
            # spot. On that turn the active Dipplin had 0 energies and was
            # still evolved into Hydrapple ex (33000), staying useless for the
            # rest of the game.
            #
            # The gate is the RETREAT COST (>= 3), which is the real reason:
            # in our deck only Hydrapple ex meets it (Meganium/Bayleef/
            # Dipplin cost 2), but this way it covers any future evolution
            # that is just as slow. It goes at the END of the branch so it has
            # the last word over the score increases above.
            #
            # ONLY vs Cubchoo (`op_is_cubchoo_deck`): in the other matchups
            # the evolution is normal development -- it recharges and retreats
            # without trouble, and the 330 HP wall makes up for it.
            if (op_is_cubchoo_deck and score > 0
                    and RETREAT_COST.get(card.id, 1) >= 3):
                # Energy the ALREADY evolved body would count on: the one it
                # inherits from the pre-evolution plus the manual attachment if
                # it is still available this turn.
                _cub_evo_eff = _pkmn_energy
                if _has_energy_in_hand:
                    _cub_evo_eff += _grass_attach_unit()
                if _cub_evo_eff < AGENT_STATE.ATTACK_ENERGY_REQ.get(card.id, 99):
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
