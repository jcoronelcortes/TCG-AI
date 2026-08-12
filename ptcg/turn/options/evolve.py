"""Scoring the EVOLVE options: which body gets the stage, and is it worth it.

Evolving is nearly always good -- it upgrades a body for one card -- so the
base score is high (~9000) and the interesting content is which evolution wins
and when the answer is "not this one".

WHAT MOVES THE SCORE:

  * THE CARD. Some evolutions are engines rather than upgrades and are scored
    far above the base -- Meganium at 35000, because Wild Growth doubles every
    Grass on the field and changes what the whole board can afford, not just
    what one body can do.
  * THE MATCHUP. Against an immune wall the question is not "is this body
    better" but "can this body hit the thing in front", which is why the
    Cornerstone and Crustle readings appear here at all.
  * WHICH BODY. Given two copies of a Basic, the stage goes on the one that
    GAINS from it -- the damaged one, since evolving heals nothing but the
    fresh HP total is what buys a turn. See `evolution_body_bias` in
    `ptcg/calc/damage.py`.
  * WHETHER THE BODY CAN USE IT. A stage on a body that cannot then act is a
    card spent for nothing.

TWO SOURCES, ONE MENU. An evolution normally comes from HAND, but the Grand
Tree ability pulls it out of the DECK. Those are scored by different logic --
Grand Tree evolutions are ranked by the stadium's own plan (see
`ptcg/decision/stadiums.py`), because the hand-evolution bands assume a card is
being spent and that the body was already chosen. That branch appends its own
score and returns `_SALTAR`. The area is read from the option rather than
assumed to be the hand, which is what lets both paths share this module.

Extracted VERBATIM from the `agent()` chain: it unpacks from the context only
the fields it reads and returns only the ones it reassigns.
"""

from cg.api import AreaType, OptionType
from ptcg.calc.card import get_card
from ptcg.calc.damage import (_op_window_against_evolution,
                              _our_effective_damage, evolution_body_bias)
from ptcg.calc.energy import (_can_attack_eff, _grass_attach_unit, _grass_mult,
                              energy_after_evolution)
from ptcg.calc.board import _active_of
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Grand_Tree, Hydrapple_ex, Lillie_Determination, Meganium, RETREAT_COST, SCORE_EVO_BODY_WITHOUT_A_JOB, SCORE_EVO_CONDITION_UNLOCK, SCORE_VETO, Tapu_Bulu
from ptcg.cards.tables import card_table
from ptcg.state.agent_state import AGENT_STATE


def _evolution_also_fits_the_bench(tc, o, card_id):
    """Does THIS MENU offer the same evolution card on a BENCH body?

    The question the demotion above depends on: refusing the front spot is only
    a play if the card has somewhere else to go. It is read off the option list
    and not off the board because the menu is the authority on which bodies are
    legal targets -- a bench copy that cannot legally wear the card never shows
    up here, and no rule has to re-derive the line.
    """
    for _other in (getattr(tc.select, 'option', None) or []):
        if _other is o or _other.type != OptionType.EVOLVE:
            continue
        if _other.inPlayArea != AreaType.BENCH:
            continue
        _area = _other.area if _other.area is not None else AreaType.HAND
        _c = get_card(tc.obs, _area, _other.index, tc.my_index)
        if _c is not None and _c.id == card_id:
            return True
    return False


def score_play(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
    _SALTAR = tc._SALTAR
    _atk = tc._atk
    _bp = tc._bp
    _gt_plan = tc._gt_plan
    _gt_turn_plans = tc._gt_turn_plans
    _gt_score_selection = tc._gt_score_selection
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
            _gt_evo_score = _gt_score_selection(
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
        
            # ── THE STAGE GOES ON A BODY THAT CAN USE IT ───────────────
            # An evolution played in the ACTIVE spot only earns its band if the
            # body it creates DOES SOMETHING in front: it attacks this turn, or
            # it survives what reaches the active spot before our next turn. A
            # body that does neither is a Stage buried under a corpse -- it
            # neither trades nor blocks, and the card dies with the prize.
            #
            # Then the same card is worth more on ANY other body the menu
            # offers on the bench: down there it charges, it inherits the energy
            # it already carries and it is still ours next turn.
            #
            # Deck-agnostic: `energy_after_evolution` + `ATTACK_ENERGY_REQ`
            # answer the attack, `_op_window_against_evolution` answers the
            # reply, and "somewhere else to put it" is read off THIS menu. No
            # card id and no matchup appear in the gate.
            #
            # User, registro_004 step 44 vs Abra/Kadabra/Alakazam (WON in spite
            # of it): active Bayleef 80/110 with ZERO energy, an identical
            # Bayleef at 110/110 WITH a Grass on the bench, Meganium in hand and
            # the turn's attachment already spent. Both options scored 35000 and
            # the +16 damage gradient of `evolution_body_bias` sent the Stage 2
            # to the front, where it could neither attack (Solar Beam costs 4,
            # it had 0) nor retreat (cost 2) nor survive the Alakazam their
            # three Kadabra were one card away from. The bench copy would have
            # started at 2 of the 4 it needs.
            if _is_active and score > 0 and not has_condition:
                _evo_eff = energy_after_evolution(
                    pokemon, card.id, 1 if _has_energy_in_hand else 0)
                _evo_can_attack = _can_attack_eff(card.id, _evo_eff)

                _evo_data = card_table.get(card.id)
                _evo_max_hp = (getattr(_evo_data, 'hp', 0) or 0) if _evo_data else 0
                _evo_damage_carried = max(
                    0, (getattr(pokemon, 'maxHp', 0) or 0) - (getattr(pokemon, 'hp', 0) or 0))
                _evo_hp_after = _evo_max_hp - _evo_damage_carried
                _evo_window = max(
                    estimated_op_damage,
                    _op_window_against_evolution(
                        _active_of(op_state), card.id,
                        getattr(op_state, 'handCount', None)))
                _evo_survives = (_evo_hp_after > _evo_window)

                # `active_ko_likely` stays as an INDEPENDENT trigger, and one
                # that does not ask where else the card could go: it is the
                # reading the branch already used and it fires on boards where
                # the projection alone reads low (a heuristic on life and their
                # energy, not on damage). With the active already condemned,
                # putting the Stage under it buries it whether or not there is a
                # second body -- it is the same play as burying it, one turn
                # earlier.
                if not _evo_can_attack and (
                        active_ko_likely
                        or (not _evo_survives
                            and _evolution_also_fits_the_bench(tc, o, card.id))):
                    score = SCORE_EVO_BODY_WITHOUT_A_JOB

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

            # ── THE EVOLUTION THAT WAKES THE ACTIVE ────────────────────
            # An Asleep active neither attacks nor pays a retreat: the turn is
            # gone. Evolving is the ONLY key we hold -- a Pokemon that evolves
            # recovers from every Special Condition -- because our deck has no
            # switching card and the other way out is the coin of the Pokemon
            # Checkup, which is not ours to call.
            #
            # This is the GENERAL rule of a special case the Bayleef branch
            # above already wrote by hand. The environment holds ten attacks
            # that put our active to sleep -- Spheal's Powder Snow (10 damage
            # for one energy, the cheapest of them, and the third lock body of
            # the Crustle/Cubchoo deck), Amaura's Icy Wind, Musharna's Sleep
            # Pulse, Milotic ex, Mega Froslass ex, Erika's Vileplume ex... --
            # and the body that has to wake up is not always a Chikorita.
            # Measured before writing it: with an Asleep Dipplin carrying two
            # Grass and Hydrapple ex in hand vs Crustle, the agent ENDED THE
            # TURN -- it could not attack, could not retreat, and declined the
            # one card that gives back both.
            #
            # THE GATE IS WHAT THE WOKEN BODY CAN DO TODAY: reach its attack
            # cost, or pay its retreat (there is a bench and the retreat is
            # still unspent). Waking a body that can do NEITHER buys nothing
            # this turn: it spends the evolution and, with a Stage 2 ex, plants
            # two prizes in the very spot the opponent is locking. That is
            # registro_034 vs Cubchoo, and the veto right above it -- whose
            # gate is the attack cost of a slow, expensive-to-retreat body --
            # keeps its word on exactly those boards.
            #
            # The damage of that attack is deliberately NOT checked. Against a
            # wall that zeroes us the attack is worth little, but the
            # alternative while asleep is literally nothing, and the retreat
            # the same wake-up restores is the way off the wall.
            #
            # It only LIFTS the score, never lowers it: Meganium (35000) and
            # the Bayleef unlock keep the values they were measured with.
            if (_is_active and condition_blocks_action
                    and score < SCORE_EVO_CONDITION_UNLOCK):
                _wake_eff = energy_after_evolution(
                    pokemon, card.id, 1 if _has_energy_in_hand else 0)
                _wake_can_retreat = (
                    can_switch and not getattr(state, 'retreated', False)
                    and _wake_eff >= RETREAT_COST.get(card.id, 1))
                if _can_attack_eff(card.id, _wake_eff) or _wake_can_retreat:
                    score = SCORE_EVO_CONDITION_UNLOCK

            # ── WHICH BODY evolves ─────────────────────────────────────
            # Everything above scores the CARD (and at most the species of the
            # body): with two copies of the same pre-evolution in play both
            # options come out with the SAME score and the argmax falls on
            # whichever the menu listed first. Damage carries over on evolution,
            # so the copy that gains from it is the DAMAGED one -- and the
            # intact one is the one that can be left waiting on the bench.
            #
            # It goes LAST, after the ceilings and vetoes, so it can only order
            # what has already been decided to be worth playing. Its magnitude
            # (<= 260, see EVO_BODY_* ) never crosses the bands above.
            if score > 0:
                score += evolution_body_bias(
                    pokemon, card.id, _is_active,
                    estimated_op_damage if _is_active
                    else AGENT_STATE._op_bench_snipe_dmg)

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


__all__ = ['score_play']
