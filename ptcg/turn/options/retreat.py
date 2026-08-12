"""Scoring the RETREAT options: swapping the body in front, and what it costs.

Retreating looks defensive and mostly is not. Three quite different plays wear
the same option type, and separating them is the key to reading this file:

  * THE RELAY -- retreat so a CHARGED body on the bench can come up and attack.
    Offensive; often the whole turn. Most of the long comment blocks here are
    about getting this one right.
  * THE PIVOT -- get a doomed or useless body out of the front seat before
    their turn. Defensive.
  * THE FEE -- retreat purely to hide a two-prize ex behind a one-prize wall.
    Costs energy and buys a cheaper corpse.

THE COST IS NEVER JUST THE COST. Paying a retreat DISCARDS energy off the
retreating body, and that has three consequences this file keeps re-learning:
the attack we are retreating INTO may scale on the field's total Grass, so the
payment can weaken the very attack it enables; the discarded Grass becomes
recoverable by Night Stretcher, which is a route rather than a loss; and the
body left behind keeps whatever was not spent.

WHAT THE PROMOTED BODY MUST BE. A retreat that promotes a body which cannot act
is worse than no retreat -- a mute survivor hands over the front seat and the
tempo. So the rules ask what the promoted body DOES, not just whether it
survives, and the promotion itself is scored in `card.py` under
SelectContext.SWITCH; this branch decides whether to open that menu at all.

READ THEIR REPLY, NOT ONLY OUR TURN. Several rules here turn on what happens
AFTER we retreat -- what they promote, what it hits for, whether the relay we
just brought up survives it. Those readings come from `ptcg/calc/damage.py`
(`_promoted_reply_damage`, `_bench_finisher_that_survives`) and from the turn
plan's defensive half, never recomputed locally.

"THE ACTIVE CAN KNOCK OUT NOW" IS NOT A REASON TO STAY. It looks like one and
was written as one, and the long block about the surviving relay is the record
of that being wrong: a healthy body in front that can trade is still worth
swapping when the relay takes the same prize and lives through the answer.

Extracted VERBATIM from the `agent()` chain: it unpacks from the context only
the fields it reads and returns only the ones it reassigns.
"""

from cg.api import AreaType, CardType, OptionType, Pokemon
from ptcg.calc.card import get_card, prize_count, prize_count_op
from ptcg.calc.damage import UPGRADE_PRIZE, _attacker_base_damage, _bench_finisher_that_survives, _bench_finisher_upgrade, _ex_active_is_a_wall, _hand_revealed_lethal_reply, _op_active_attack_damage_to, _our_effective_damage, _promoted_lethal_reply, _promoted_reply_damage, _reply_reaches_match_point
from ptcg.calc.energy import _can_attack_eff, _grass_attach_route_open, _grass_attach_unit, _grass_mult, _physical_energy, _reachable_grass_for, _retreat_grass_to_discard, _retreat_grass_units
from ptcg.calc.board import _active_of
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Cornerstone_Mask_Ogerpon_ex, Crustle_Fighting, Crustle_Grass, Cubchoo, Dawn, Dipplin, Drednaw, Dwebble_Fighting, Dwebble_Grass, EEVEE_IDS, Fezandipiti_ex, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, OP_BENCH_SNIPE_DAMAGE, OUR_ABILITY_IDS, OUR_EX_IDS, Pinsir, RETREAT_COST, SCORE_VETO, Sylveon, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cards.scoring import MAIN_ATTACKERS
from ptcg.cards.tables import card_table
from ptcg.state.agent_state import AGENT_STATE


def score_play(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
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
    _cubchoo_mute_cashes_prize = tc._cubchoo_mute_cashes_prize
    _doomed_mute_pivot = tc._doomed_mute_pivot
    _doomed_sac_context = tc._doomed_sac_context
    _ft_wall_pivot = tc._ft_wall_pivot
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _win_via_boss_gust = tc._win_via_boss_gust
    _prize_mismatch_matchup = tc._prize_mismatch_matchup
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
    _op_evo_dmg_to_active = tc._op_evo_dmg_to_active
    _our_first_turn = tc._our_first_turn
    _p = tc._p
    _plan_relay_is_inert = tc._plan_relay_is_inert
    _prize_denial_pivot = tc._prize_denial_pivot
    _sid = tc._sid
    _opening_sac_pivot = tc._opening_sac_pivot
    _suicide_swap_win_promote = tc._suicide_swap_win_promote
    _supp_values = tc._supp_values
    _tapu_sac_pivot = tc._tapu_sac_pivot
    _festival_sac_pivot = tc._festival_sac_pivot
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
        
        # Rule (user, log 86510119 step 26, vs Dragapult, LOST): if retreating
        # the active would make the promotion bring up a Pokemon of the SAME
        # species as the one we are retreating, the retreat changes nothing and
        # only wastes the energy of the retreat cost. It is cancelled
        # (score = SCORE_VETO) to leave the Pokemon in the active spot. Three cases:
        #   (a) every bench candidate is the same species as the active (the only
        #       candidate is the same Pokemon), or
        #   (b) the promotion prefers bringing up a 1-prize BASIC (we have
        #       Lillie's Determination and NO benched attacker ready to attack
        #       this turn, opponent not immune to ex/abilities) and that basic
        #       would again be the active's species (e.g. an active Applin with
        #       another Applin on the bench): swapping Applin for Applin adds
        #       nothing, or
        #   (c) NOBODY ELSE CAN TAKE THE FRONT: the twin is on the bench and no
        #       body of another species would act on the spot, so the promotion
        #       has nothing to prefer over the twin (see below).
        _same_species_retreat = False
        if _active_reloc is not None:
            _ss_bench = [bp for bp in (my_state.bench or [])
                         if bp is not None and isinstance(bp, Pokemon)]
            if _ss_bench:
                # (a) Literal case: there is no candidate of another species.
                _ss_only_same = all(bp.id == _active_reloc.id
                                    for bp in _ss_bench)
        
                # (b) "Prefer a basic" case: we reproduce the condition of the
                # promotion (`_refresh_promote_prefer_basic`).
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
                # Non-ex basics that are bench candidates (the ones the promotion
                # would prefer as a 1-prize wall).
                _ss_bench_basics = []
                for bp in _ss_bench:
                    _bp_d = card_table.get(bp.id)
                    if (_bp_d is not None
                            and not getattr(_bp_d, 'stage1', False)
                            and not getattr(_bp_d, 'stage2', False)
                            and bp.id not in OUR_EX_IDS):
                        _ss_bench_basics.append(bp.id)
                # The promoted basic is of the active's species if: the active is
                # an Applin (the top-priority basic) and there is another Applin
                # on the bench, or every candidate basic is of the active's
                # species (whichever comes up, same species).
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
        
                # (c) THE TWIN TAKES THE FRONT BECAUSE NOBODY ELSE CAN (user,
                # records/registro_002 step 20 vs Marnie, WON). Cases (a) and
                # (b) only see the twin when it is the ONLY candidate or when a
                # Lillie's in hand turns the promotion into "prefer a basic".
                # On that board neither fired -- the bench held the twin AND a
                # Chikorita, and the Lillie's had already been played on step
                # 19 -- and the promotion brought the twin up anyway: the
                # Meganium line does not go active with a bench of two
                # (SCORE_NEVER in ptcg/turn/options/card.py), so the second
                # Applin was the only body the menu could choose. The fee
                # discarded the Grass that let the ACTIVE attack and the front
                # spot ended up holding the same 40 HP, now bare.
                #
                # The veto only fires where the twin is CERTAIN to be the body
                # that comes up, and it is certain when the promotion has no
                # other body it is allowed to choose. That is exactly what
                # happened on the record: the Chikorita was not passed over,
                # it was REFUSED, and the reason a menu refuses a body does not
                # depend on the retreat -- see `_ss_promotion_refuses`. A body
                # of another species the menu can take is the escape: there the
                # promotion has something to prefer and the retreat is a real
                # play, decided by the rules that own it.
                _ss_twins = [bp for bp in _ss_bench
                             if bp.id == _active_reloc.id]
                _ss_op_act = _active_of(op_state)
                _ss_attach_unit = (_grass_attach_unit() if _ss_grass_attach
                                   else 0)

                def _ss_front_damage(_pk):
                    """What `_pk` would hit the opposing active for if the
                    retreat handed it the front. The canonical damage model
                    (ATTACK_ENERGY_REQ + weakness/immunity), counting the Grass
                    still to be attached this turn and a bench that does NOT
                    shrink -- the retreat SWAPS bodies."""
                    if _pk is None or _ss_op_act is None:
                        return 0
                    _pk_eff = (len(_pk.energies) * _grass_mult()
                               + _ss_attach_unit)
                    _pk_base = _attacker_base_damage(
                        _pk.id, _ss_op_act, _pk_eff,
                        grass_scale=total_grass,
                        teal_self_energy=_pk_eff,
                        bench_count=bench_count)
                    if _pk_base <= 0:
                        return 0
                    return _our_effective_damage(
                        _pk, _ss_op_act, _pk_base,
                        AGENT_STATE.meganium_in_play,
                        neutralization_zone_active)

                def _ss_promotion_refuses(_pk):
                    """The promotion menu cannot hand the front to `_pk`.

                    THE MEGANIUM LINE DOES NOT GO ACTIVE (the SCORE_NEVER of
                    ptcg/turn/options/card.py): with more than one body on the
                    bench a Chikorita/Bayleef/Meganium is struck out of the
                    menu to protect Wild Growth from the front spot, and every
                    exemption it has is a Meganium that ATTACKS on the spot
                    (the remaining one, `_forced_ko_promote`, needs an EMPTY
                    active spot and so cannot apply to our own retreat)."""
                    if _pk.id in (Chikorita, Bayleef, Meganium) and bench_count > 1:
                        return not (_pk.id == Meganium
                                    and _can_attack_eff(Meganium,
                                                        len(_pk.energies)))
                    return False

                _ss_other_candidates = [
                    bp for bp in _ss_bench
                    if bp.id != _active_reloc.id and not _ss_promotion_refuses(bp)]
                _ss_promotion_is_twin = (bool(_ss_twins)
                                         and not _ss_other_candidates)

                _same_species_retreat = (_ss_only_same or _ss_prefer_same
                                         or _ss_promotion_is_twin)

                # THE TWO EXCEPTIONS THE RULE NAMES (user), and both are about
                # the twin itself, not about the rest of the bench:
                #   * IT KNOCKS THE OPPONENT OUT. Then the swap is not a swap,
                #     it is a prize: the body in front cannot take it and the
                #     one behind can, which is the whole point of retreating.
                #   * IT HAS LESS LIFE LEFT THAN THE ACTIVE. The two copies
                #     hand over the same prize, so the front spot should be
                #     paid with the body already spent and the healthy copy
                #     kept behind for its evolution.
                # Read on remaining HP (`hp`), not on the printed maximum: what
                # the exception is about is the copy that is already damaged.
                if _same_species_retreat and _ss_twins:
                    _ss_act_hp = (_active_reloc.hp or 0)
                    for _ss_tw in _ss_twins:
                        _ss_tw_dmg = _ss_front_damage(_ss_tw)
                        if (_ss_op_act is not None and _ss_tw_dmg > 0
                                and _ss_tw_dmg >= (_ss_op_act.hp or 0)):
                            _same_species_retreat = False
                            break
                        if (_ss_tw.hp or 0) < _ss_act_hp:
                            _same_species_retreat = False
                            break

                # (d) THE BODY THAT ATTACKS DOES NOT HAND THE FRONT TO ITS TWIN
                # (user, registro_004 step 55 vs Mega Abomasnow ex, LOST).
                #
                #   US                                   RIVAL
                #   active Teal Mask Ogerpon ex 210 (4)  active Mega Abomasnow ex 350
                #          Myriad Leaf Shower ON THE MENU        hits for 200
                #   bench  Meganium 160, Meowth ex 170,
                #          Applin 40, Fezandipiti ex 210,
                #          Teal Mask Ogerpon ex 210 (2)  <- the twin, MUTE
                #
                # The menu offered the attack and the agent retreated instead:
                # the fee discarded a Grass and the promotion brought up the
                # twin, because at 200 damage the only bodies that ENDURE are
                # the two 210s and the twin is the better-scoring one. The turn
                # ended with the same 210 HP Ogerpon ex in front, one energy
                # poorer and unable to attack.
                #
                # Cases (a)-(c) all ask WHO comes up, and answer only where the
                # twin is the sole body the promotion may take -- here it was
                # one candidate among five. This case does not ask who comes up,
                # because on this board NO answer was worth the fee: THE FRONT
                # SPOT CANNOT BE UPGRADED. Nothing behind attacks, nothing
                # behind is bigger, and one of the bodies back there is the
                # active's own copy. Whatever the promotion picks, the turn
                # hands back the attack it already had and gets no more body for
                # it.
                #
                # The clauses are what keeps it from eating the retreats that
                # ARE right, and each one names the family it excludes:
                #   * `can_attack`: the attack is really on the menu. The pivots
                #     that open the turn with no attack available
                #     (`_ft_wall_pivot`, `_opening_sac_pivot`) never reach here.
                #   * `not _ss_bench_atk_ready`: nothing behind can attack, this
                #     turn's pending attachment included. Any pivot that
                #     retreats TOWARDS a body that acts (`_wall_ko_promote`,
                #     `_tapu_sac_pivot`, `_alakazam_pivot_1prize`,
                #     `_hydra_wall_pivot`) is out, and so is the twin that
                #     KNOCKS OUT -- the first exception of the block above, which
                #     is why it is not re-asked here.
                #   * NOTHING BEHIND IS BIGGER (`_ss_bench_max_hp`, read on
                #     remaining HP). This is the clause that tells the record
                #     apart from a retreat that swaps a 40 HP Applin for a 140 HP
                #     Tapu Bulu: there the front spot IS upgraded even though
                #     neither body attacks. It also keeps the second exception of
                #     the block above -- the twin already damaged goes to the
                #     front -- because a bench holding a healthier body than the
                #     active fails it.
                #   * the active ENDURES: the retreat is not buying a prize
                #     sacrifice. Every sacrifice pivot -- `_raging_sac_pivot`,
                #     `_doomed_ex_sac_pivot`, `_prize_denial_pivot`,
                #     `_teal_wall_pivot` -- is written on a DOOMED active, and
                #     the evolution the opponent has not played yet is read too
                #     (`_op_evo_dmg_to_active`), the same way those pivots read
                #     it. It is also what makes the HP clause enough on its own:
                #     a cheaper body behind is only an upgrade when the front
                #     body is going to FALL, and here it is not.
                #   * no wall in front: with an ex-immune or ability-immune
                #     active facing us, "the active can attack" does not mean
                #     the attack does anything, and that board has its own rules
                #     (`_nonex_active_hits_wall`, `_ex_stuck_promo_ready`).
                _ss_active_survives = (
                    not active_ko_likely
                    and (_op_evo_dmg_to_active or 0) < (_active_reloc.hp or 0))
                _ss_bench_max_hp = max((bp.hp or 0) for bp in _ss_bench)
                if (_ss_twins and can_attack and not _ss_bench_atk_ready
                        and _ss_bench_max_hp <= (_active_reloc.hp or 0)
                        and _ss_active_survives
                        and not op_has_ex_immune_active
                        and not op_has_ability_immune_active):
                    _same_species_retreat = True

        # Rule: Meganium active + Hydrapple ex on the bench + opponent WITHOUT
        # ex protection (no Crustle/Sylveon/ex-immune bodies) => retreat Meganium
        # to promote Hydrapple ex (the key attacker/engine). Meganium stays on the
        # bench, so Wild Growth is kept. It does NOT apply against ex-immune walls,
        # where Hydrapple ex (an ex) could not hit.
        _meg_retreat_for_hydra = False
        if (_active_reloc is not None and _active_reloc.id == Meganium
                and can_switch
                and not (AGENT_STATE.op_is_crustle_deck or op_has_ex_immune_active
                         or op_has_ex_immune_bench or op_is_sylveon_deck)):
            for _mrh_bp in (my_state.bench or []):
                if _mrh_bp is not None and _mrh_bp.id == Hydrapple_ex:
                    _meg_retreat_for_hydra = True
                    break
        
        _grd_prefer_attack = False
        if (_active_reloc is not None and can_switch
                and not (AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck)):
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
                # Myriad counts the energy of BOTH actives.
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
                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
                if _acn_dmg > 0 and _acn_dmg >= (_acn_op.hp or 0):
                    _active_can_ko_now = True
        
        # The active ALSO "can knock out now" when its attack chooses a target
        # and the KO is on the opposing BENCH (Fezandipiti ex's Cruel Arrow;
        # user, registro_004 step 54 vs Alakazam). Without this the block above
        # only looked at the opposing active, `_active_can_ko_now` came out
        # False and the retreat -- which also DISCARDS the snipe's energy --
        # won the menu, throwing away a free prize.
        # `_active_kos_op_active` keeps the STRICT sense (the KO lands on the
        # opposing active) for the pivots that compare prizes.
        _active_kos_op_active = _active_can_ko_now
        if _active_snipe_ko_now:
            _active_can_ko_now = True

        # THE RELAY THAT SURVIVES (user, registro_012 step 120 vs Alakazam,
        # LOST -- deck-agnostic). "The active can knock out now" vetoes the
        # retreat further down, and most of the time that is right: taking the
        # prize from the front costs nothing. It costs something when the body
        # taking it cannot afford to stand there afterwards.
        #
        # Turn 12, four prizes to three. Our active was a Hydrapple ex at 110 of
        # its 330 HP, its Syrup Storm finished their Alakazam, and one energy
        # short of its retreat cost sat a benched Teal Mask Ogerpon ex with
        # three energies whose Myriad Leaf Shower finished it just as well --
        # from 210 HP. We attacked from the front, their Powerful Hand read a
        # hand of six, and the two prizes that body hands over ended the game.
        #
        # The generalisation of `_active_ex_fragile_pivot`, which asks the same
        # question through the card: it wants the active to be an ex other than
        # Hydrapple with a PRINTED HP under 330, and the relay to be a benched
        # Hydrapple ex. Printed HP is the wrong number -- a Hydrapple at 110 of
        # 330 is the fragile body here, and the tougher relay is an Ogerpon --
        # so this one asks the board instead: does their projected reply knock
        # our active out, are those their LAST prizes, and is there a benched
        # body that finishes the same target, outlasts that reply and hands over
        # no more prizes.
        #
        # The prize gate is what keeps it a defensive pivot rather than a
        # preference. A trade we merely dislike is not worth the retreat cost;
        # the game is.
        #
        # The named pivots above keep their scores and their priority; this one
        # only picks up what they do not name.
        # THE REPLY COMES OFF THEIR BENCH, AND THE RELAY ARRIVES CHARGED (user,
        # registro_006 step 54 vs Mega Starmie ex, LOST -- episode 91693960).
        # Deck-agnostic; the two readings the pivots below are built on, both of
        # which were being taken from the wrong board.
        #
        #   US                                    RIVAL
        #   active Teal Mask Ogerpon ex 210 (4G)  active Cinderace 160 (1W)
        #          Myriad Leaf Shower -> 180              Turbo Flare -> 50
        #   bench  Hydrapple ex 330/330 (1G)      bench  Mega Starmie ex 330 (3W)
        #          Bayleef 110 (0)                       Mega Starmie ex 330 (3W)
        #   hand   Night Stretcher, ... ; discard 2 Grass ; six prizes to five
        #
        # We took the prize from the front. They promoted a Mega Starmie ex,
        # Nebula Beam read 210 against exactly 210 HP, and the trade was one
        # prize for two plus the four Grass that went to the discard with the
        # body. The line that was on the menu takes the SAME prize: retreat
        # (one Grass), promote the Hydrapple ex, Night Stretcher the Grass back,
        # attach it -- Syrup Storm at 30 + 30x5 = 180 over 160 -- and 210 lands
        # on a 330 HP body instead, with the Ogerpon safe on the bench under its
        # own Tera.
        #
        # Neither pivot below could see it, for two independent reasons:
        #
        #   1. THE REPLY. Both are scoped by the blow their ACTIVE lands, and
        #      both only ever run when that active is the body our attack is
        #      about to knock out. So the number came off a corpse: 50 from the
        #      Cinderace, where the board's real answer was 210 from the bench.
        #      `_promoted_reply_damage` reads the body that stands up; it is the
        #      same projection `TurnPlan.op_prizes_after_ko` already published as
        #      data, and this is the first rule to consume it.
        #
        #      It is taken as the MAX with the hand-revealed reading, not in
        #      place of it. That reading exists for the attacks whose damage only
        #      their HAND SIZE reveals (Powerful Hand), the machinery downstream
        #      of it was measured on boards where it fires, and the honest
        #      defensive projection is the worse of the two blows anyway.
        #
        #   2. THE RELAY. `len(bp.energies)` and nothing else: a Hydrapple ex one
        #      energy short of Syrup Storm reads MUTE, and the Night Stretcher in
        #      hand plus the attachment nobody has spent are not part of the
        #      question. `_reachable_grass_for` is what the rest of this file
        #      already uses for exactly that -- it knows the CARDS (hand, plus one
        #      per Night Stretcher over the discard, the retreat's own payment
        #      included) and the ROUTES that can still put them on that body.
        #
        # Both corrections point the same way and neither invents a route: what
        # they buy is that the body cashing the prize is the one that can afford
        # to stand there when the prize is collected.
        #
        # THE SCOPE, AND WHY IT IS THIS ONE. The promoted reading is allowed to
        # speak only where EVERY reading the agent already has says the body in
        # front is safe: `not active_ko_likely`, which is the whole defensive
        # model of this turn condensed into one flag, and it is computed from
        # their ACTIVE (plus bench bursts) -- exactly the reading the promotion
        # is blind to. `_promoted_lethal_reply` adds the same test on the raw
        # projection; this adds the two clauses the flag carries on top of it (a
        # body under 60 HP against two energies, a body under a third of its
        # maximum against one).
        #
        # Measured, and each one is a decision the project already paid for:
        #
        #   * WITHOUT the flag, `iono_step161` and `mewtwo_step119` flip. Both
        #     are a Hydrapple ex at 30 of its 330 taking a knockout from the
        #     front: their active reads 20 and the reading opens, but that body
        #     is a corpse to anything on their board and the rules written on a
        #     doomed active own it -- there the turn is worth a Boss's Orders
        #     onto a 2-prize bench body, not a retreat that saves a body already
        #     lost.
        #   * `marnie_step107` is the same shape one step further along (an
        #     Ogerpon ex at 10 of 210) and is what makes the pair a boundary and
        #     not a coincidence.
        #
        # What is left is the seam and nothing else: a HEALTHY body in front,
        # every projection saying it survives, and one blow on their bench that
        # says otherwise the moment our own attack clears the way for it.
        #
        # AND A BIGGER PRIZE ON THE TABLE SILENCES IT (user, registro_006 step
        # 119 vs Mewtwo ex; the same shape at Iono step 161). This reading is
        # about WHO takes a knockout that is happening either way; a Boss's
        # Orders onto a 2-prize body on their bench is about a DIFFERENT and
        # bigger knockout, and `_front_spot_upgrade`'s own note says the swap
        # must not talk over it. The quiet-on-safe-boards scoping used to buy
        # that for free -- a rule that never fired where the active was safe
        # could not outbid anything -- and seeing a danger that was previously
        # invisible is what takes it away.
        #
        # It is not only an ordering preference. The blow being projected comes
        # off their BENCH, and the gust REMOVES a body from that bench -- quite
        # possibly the very one the projection is reading. Weighing a bench
        # reply against a turn that is about to delete a body from that bench is
        # incoherent whichever way it lands.
        _promoted_reply = 0
        if (_active_reloc is not None and _active_kos_op_active
                and not active_ko_likely
                and not (_win_via_boss_gust or _gust_2prize_via_boss)
                and my_state.active and my_state.active[0] is not None):
            _promoted_reply = _promoted_lethal_reply(
                my_state, op_state, getattr(op_state, 'handCount', None))

        # AND IT MAY ONLY TURN THE PIVOTS ON, NEVER OFF. Both predicates below
        # FILTER by the reply -- a relay whose HP does not clear it is dropped --
        # so feeding them a bigger number can silence a pivot the old reading
        # found, and the boards where that happens were measured under the old
        # reading. So the promoted number is not substituted into the question:
        # it is asked as a SECOND question, and only where the first answered
        # nothing. `_promoted_retry` is that "the first said nothing" guard.
        #
        # Measured (utils/gate_promoted_relay.py, n=1500 per arm against a
        # baseline built from this same tree with the change switched off):
        # substituting the number reads 47.8% [45.3-50.3], asking it additively
        # 50.5% [47.9-53.0]. The census (utils/promoted_relay_census.py, 300
        # games over the 87 real opponent decks) says why: additively the change
        # touches 12 of 19 886 decisions, and what substitution added on top of
        # those were REMOVALS -- retreats the hand-revealed reading had granted
        # and the bigger number took away, on the Alakazam boards the front-spot
        # rule was measured on. Asked second, those boards keep the answer they
        # were measured with and the new reading only speaks where nothing spoke.
        def _promoted_retry(found, old_reply):
            return (not found) and _promoted_reply > old_reply

        def _relay_grass(_bp, _act=_active_reloc):
            # PHYSICAL Grass the turn can still put on `_bp` if we retreat now.
            # The retreat's own payment is part of the discard this reads,
            # because a Night Stretcher reaches it there.
            return _reachable_grass_for(
                _bp, state, my_state, hand_counts, field_counts,
                extra_discard_grass=_retreat_grass_to_discard(_act),
                abilities_off=meowth_ability_lock)

        _relay_finisher_pivot = False
        if (_active_reloc is not None and can_switch
                and _active_kos_op_active
                and op_state.active and op_state.active[0] is not None):
            _rfp_opa = op_state.active[0]
            # Attacking from the front when it already WINS the game needs no
            # relay: there is no next turn to survive into.
            if not (my_prize <= prize_count_op(_rfp_opa)):
                _rfp_reply = _hand_revealed_lethal_reply(
                    _rfp_opa, _active_reloc,
                    getattr(op_state, 'handCount', None))
                _rfp_grass_after = max(0, total_grass - _retreat_grass_units(
                    RETREAT_COST.get(_active_reloc.id, 1)))

                def _rfp_ask(_reply):
                    if _reply <= 0 or not _reply_reaches_match_point(
                            _active_reloc, op_state, _rfp_opa):
                        return False
                    return _bench_finisher_that_survives(
                        my_state, _rfp_opa, AGENT_STATE.meganium_in_play,
                        bench_count, _rfp_grass_after,
                        neutralization_zone_active, _reply,
                        prize_count(_active_reloc),
                        reachable_grass=_relay_grass)

                _relay_finisher_pivot = _rfp_ask(_rfp_reply)
                if _promoted_retry(_relay_finisher_pivot, _rfp_reply):
                    _relay_finisher_pivot = _rfp_ask(_promoted_reply)

        # THE LAST PRIZE IS CASHED BY A BODY THAT IS STILL THERE (user,
        # registro_012 step 133 vs Archaludon, LOST -- episode 92260006).
        # Deck-agnostic: it names no card, only the prize count.
        #
        #   US                                     RIVAL   (one prize left)
        #   active Hydrapple ex   10/330 (4G)      active Duraludon 130 (2M)
        #          Syrup Storm -> lethal                  <- gusted by our Boss's
        #   bench  Teal Mask Ogerpon ex 210 (6G)   bench  Cinderace 160 (1M)
        #          Myriad 30+30x(6+2) = 270               Duraludon 130, Fan Rotom
        #
        # We attacked from the front. The knockout was real -- our second prize
        # of the game -- and then the Cinderace came up, 10 HP was all it had to
        # get through, and the two prizes that Hydrapple ex hands over closed a
        # count that only needed one. The same knockout was on the bench: retreat,
        # promote the Ogerpon ex, Myriad finishes the same Duraludon for the same
        # prize, and what stands in the active spot afterwards is 210 HP against a
        # 100-damage reply. Same prize, and the game does not end.
        #
        # WHY NOTHING SAW IT, and it is one reason with two faces. The turn plan
        # had the whole picture -- `op_prizes_after_ko=2`, `op_wins_after_ko=True`
        # on that very board -- and it is published as DATA that no rule reads.
        # The two pivots above are the ones that should have read it, and both go
        # silent for the same reason: their reply is scoped to blows the ordinary
        # projector CANNOT see (`_hand_revealed_lethal_reply` for the ones only a
        # hand size reveals, `_promoted_lethal_reply` for the ones only a bench
        # promotion reveals), and here the ordinary projector saw it perfectly
        # well -- their Duraludon reads 80 against 10 HP. So the board fell into
        # "their active already kills our active", where the machinery written on
        # a doomed body owns the turn... except that machinery is switched off by
        # `_active_can_ko_now`, which vetoes the retreat outright (score -1) on
        # the grounds that taking the prize from the front costs nothing.
        #
        # It costs nothing EXCEPT on the boards this flag names, and there it
        # costs the game. Hence the gate: `op_wins_after_ko`, the plan's own
        # sentence for "the knockout we are about to take is the one that loses
        # the game". The body they promote knocks our active out AND those prizes
        # close their count. It is the strictly worse half of what
        # `_relay_finisher_pivot` calls match point, so it is asked FIRST and
        # scored just above it.
        #
        # WHAT IT DOES NOT DO, on purpose. It does not give up the prize. The
        # relay has to take the SAME knockout (`_bench_finisher_that_survives`,
        # the same predicate, the same charge reading, the same "no more prizes
        # than the body it replaces" clause), so the only bill is the retreat's
        # energy: the prize is collected either way and what changes is the
        # corpse left behind. A retreat that DROPS the prize to survive is the
        # pivot `TurnPlan.denial_saves_the_game` describes, measured and reverted
        # twice (game_plan.py), and it stays reverted.
        #
        # AND THAT IS NOT FASTIDIOUSNESS, IT IS THE PRICE OF THE READING.
        # `op_wins_after_ko` projects the WORST body on their bench and assumes
        # they promote it and can pay for it -- the only honest assumption a
        # defensive projection can make, and wrong about half the time. Measured
        # (utils/match_point_reply_census.py, 300 mirror games): of the boards
        # where the flag was true and we attacked anyway, the game actually ended
        # on their reply 32 times out of 59, 54.2%. A rule that cashes the same
        # prize either way survives a coin flip -- when the projection is wrong
        # we still took the prize and merely stood behind a healthier body. One
        # that pays a PRIZE for the same reading does not. Same census, same
        # sample: that wider pivot's whole population is 9 decisions in 19 018,
        # and exactly one of them was an attack-or-retreat decision.
        #
        # And it reads the reply off the body that will actually make it --
        # `_promoted_reply_damage`, not their active, which by construction is
        # the corpse our own attack is about to make. That is the reading the
        # plan already uses for `op_wins_after_ko`; taking it from anywhere else
        # would let the flag and its evidence drift apart.
        _relay_saves_the_game = False
        if (_active_reloc is not None and can_switch
                and _active_kos_op_active
                and getattr(AGENT_STATE.turn_plan, 'op_wins_after_ko', False)
                and op_state.active and op_state.active[0] is not None):
            _rsg_opa = op_state.active[0]
            # Attacking from the front when it already WINS the game needs no
            # relay: there is no reply to survive into.
            if not (my_prize <= prize_count_op(_rsg_opa)):
                _rsg_reply = _promoted_reply_damage(
                    my_state, op_state, getattr(op_state, 'handCount', None))
                _rsg_grass_after = max(0, total_grass - _retreat_grass_units(
                    RETREAT_COST.get(_active_reloc.id, 1)))
                _relay_saves_the_game = _bench_finisher_that_survives(
                    my_state, _rsg_opa, AGENT_STATE.meganium_in_play,
                    bench_count, _rsg_grass_after, neutralization_zone_active,
                    _rsg_reply, prize_count(_active_reloc),
                    reachable_grass=_relay_grass)

        # THE FRONT SPOT GOES TO THE BODY THAT PAYS LESS (user, registro_008
        # step 126 vs Alakazam, WON -- episode 90336164).
        #
        # Turn 8, five prizes to four. Their Alakazam had just hit our active
        # Teal Mask Ogerpon ex for 140 and left it at 70 of its 210. Myriad Leaf
        # Shower still finished the Alakazam from there -- 30 + 30x(6+1) = 240
        # over 140 -- and the agent took the prize from the front. On the bench
        # stood the SAME card at 210/210 with four energies, whose Myriad
        # finished the same Alakazam just as well (30 + 30x(4+1) = 180). Their
        # next Powerful Hand read a hand of seven: 140. Against the body we left
        # in front that is a knockout and two prizes; against the one we left on
        # the bench it is 140 of 210 and nothing.
        #
        # `_relay_finisher_pivot`, right above, asks the same question and only
        # answers it when their reply CLOSES THE GAME. Here it did not -- two of
        # their four prizes were left -- so the pivot stayed silent and the
        # cheapest reading of the board never happened: when two of our bodies
        # take the SAME knockout, the one that stands there afterwards is not
        # free, and the bill has two lines. PRIZES first: a 1-prize finisher
        # takes the same prize and hands over half as much if it falls. Then HP:
        # with the prizes tied, the healthier body makes the opponent spend more
        # cards on the same removal.
        #
        # Both comparisons are STRICT, because the swap pays the retreat's
        # energy, and it is CURRENT HP that is compared -- the mirror of
        # `_pdx_act_margin`, which stops the same retreat when the bench body is
        # the wounded one (registro_012 step 174: a healthy 210 active does NOT
        # step aside for its twin at 50).
        #
        # What it does NOT widen is the rest of that pivot. The relay still has
        # to OUTLAST the blow the active does not -- where their reply kills
        # both bodies, or neither, the swap buys nothing and only pays the
        # retreat -- and the blow is still the one only their HAND reveals.
        # Reading it with the ordinary projector instead makes the rule general
        # and costs four decisions the project already measured (the Marnie
        # step 107 Meowth and the three of `test_ns_no_evolution_without_its_preevo`
        # step 84, which spend that turn on the Unfair Stamp): where the threat
        # is plainly readable, the machinery built against those boards keeps
        # its say. Widening it there is a separate change and needs its own
        # measurement.
        #
        # Measured: 1 flip in the whole record corpus (this step). Fires 8 times
        # in 300 games against the Alakazam bot -- 3 PRIZE, 5 BODY -- and never
        # in 400 mirror games, where nothing hides its damage behind a hand.
        #
        # SINCE THEN, one more blow reaches this question, and it is asked
        # SECOND (registro_006 step 54, the block above): the body they PROMOTE
        # once our own attack clears their active. "The blow is still the one
        # only their HAND reveals" remains true of the FIRST ask, and every
        # board in the paragraph above still gets exactly the answer it was
        # measured with -- the promoted reading is only consulted where this one
        # answered nothing, and only where their active is harmless, our active
        # is in no danger by any existing reading, and no bigger prize is on the
        # table. That is the separate change with its own measurement the
        # paragraph above asks for.
        _front_spot_upgrade = ''
        if (_active_reloc is not None and can_switch
                and not _relay_finisher_pivot
                and _active_kos_op_active
                and op_state.active and op_state.active[0] is not None):
            _fsu_opa = op_state.active[0]
            # Attacking from the front when it already WINS the game needs no
            # relay: there is no next turn to be standing in.
            if not (my_prize <= prize_count_op(_fsu_opa)):
                _fsu_grass_after = max(0, total_grass - _retreat_grass_units(
                    RETREAT_COST.get(_active_reloc.id, 1)))
                _fsu_reply = _hand_revealed_lethal_reply(
                    _fsu_opa, _active_reloc,
                    getattr(op_state, 'handCount', None))

                def _fsu_ask(_reply):
                    return _bench_finisher_upgrade(
                        my_state, _active_reloc, _fsu_opa,
                        AGENT_STATE.meganium_in_play, bench_count,
                        _fsu_grass_after, neutralization_zone_active, _reply,
                        reachable_grass=_relay_grass)

                _front_spot_upgrade = _fsu_ask(_fsu_reply)
                if _promoted_retry(_front_spot_upgrade, _fsu_reply):
                    _front_spot_upgrade = _fsu_ask(_promoted_reply)

        # Protecting Hydrapple ex: if our active Hydrapple ex is going to be
        # knocked out next turn and cannot take a KO this turn, it is better to
        # retreat it and promote a non-ex benched attacker (e.g. Dipplin) that
        # can attack. Hydrapple ex is key for accelerating energy and charging
        # Tapu Bulu in a single turn, so we avoid handing it over (2 prizes) for
        # nothing.
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
        
        # Rule (user): if a BENCHED Hydrapple ex (already at >=2 effective) can
        # come up to the active spot and finish with a LETHAL Syrup Storm on the
        # opposing active, retreat the current active to promote it and win the
        # game. Only when switching is possible (can_switch). The later promotion
        # chooses that Hydrapple ex via `_best_promote_card`.
        # IMPORTANT (user, log 86338560 step 114, WON vs Mega Lucario):
        # do NOT retreat the active if the ACTIVE ITSELF can ALREADY finish this
        # turn (`_active_can_ko_now`). In that case bringing up another benched
        # Hydrapple ex (same type, with LESS energy) would only pay the retreat
        # cost and reduce the attack for nothing: the active must attack.
        # EXCEPTION (user, log 86412738 step 145 vs Hops; GENERALISED in log
        # 86505760 step 55, WON vs Alakazam): even if the active can ALREADY
        # knock out, if it is a FRAGILE ex (2 prizes, other than Hydrapple and
        # with less HP than the 330 wall) and a BENCHED Hydrapple ex can ALSO
        # finish (lethal Syrup Storm), retreating and attacking with the
        # Hydrapple ex is ALWAYS preferred: the same KO but it leaves the 330 HP
        # wall as the active instead of exposing the fragile ex (Hydrapple takes
        # bigger attacks than Ogerpon in future turns). User's rule: whenever a
        # benched Hydrapple ex can defeat the opponent, it is our priority
        # attacker. The ONLY exception: do not pivot if attacking with the active
        # ALREADY wins the game this turn (my_prize <= the opposing active's
        # prizes): there is no future turn to protect there, we attack directly.
        # The pivot does NOT apply when the active is NON-ex (retreating it to
        # expose a 2-prize ex would be worse) nor when the active is already the
        # Hydrapple ex itself.
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
            # Syrup Storm scales with the Grass ON THE FIELD, and the retreat
            # DISCARDS the active's energy to pay its cost: the damage has to be
            # measured with the Grass that will remain AFTER the retreat (user,
            # registro_011 step 138 vs Dragapult, LOST). There the active was a
            # Tapu Bulu with 3 Grass (6 effective): with the previous Grass (10)
            # Syrup Storm gave 330 and "knocked out" the 320 HP Dragapult ex, but
            # retreating discarded those 3 Grass and the real attack came out at
            # 150. Same pattern as `_bo_grass_after` in the gust selection.
            _hlp_ret_cost = RETREAT_COST.get(_active_reloc.id, 1)
            _hlp_grass_after = max(
                0, total_grass - (0 if has_switch_card
                                  else _retreat_grass_units(_hlp_ret_cost)))
            for _hlp_bp in (my_state.bench or []):
                if _hlp_bp is None or _hlp_bp.id != Hydrapple_ex:
                    continue
                if len(_hlp_bp.energies) * _grass_mult() < 2:
                    continue  # it cannot pay for Syrup Storm
                # The "fragile ex" pivot (`_active_ex_fragile_pivot`) is the
                # ONLY one that retreats an active that ALREADY knocks out: it
                # gains not a single prize (both bodies are 2-prize ex) and on
                # top of that pays the energy of the retreat cost. The only
                # thing that justifies it is leaving in front the body that
                # ENDURES MORE -- and that is measured with CURRENT HP, not with
                # PRINTED HP (user, registro_014 step 166 vs Alakazam). There
                # the "330 wall" was a Hydrapple ex at 90/330 and the active a
                # Teal Mask Ogerpon ex at 210/210: both knocked out the
                # Alakazam, so retreating only served to put in front the body
                # that dies. `_active_ex_fragile_pivot` measures fragility with
                # `maxHp < 330`, which is a card constant and knows nothing
                # about damage already taken; this comparison is the one that
                # looks at the board. STRICT improvement: on a tie, the swap
                # still costs the retreat energy. Same criterion as
                # `_pdx_act_margin` in `_prize_denial_pivot` ("the one that
                # ENDURES goes in front"). It does not touch the STUCK active
                # branch (`not _active_can_ko_now`), where the pivot does buy
                # the KO we did not have.
                if (_active_ex_fragile_pivot
                        and (_hlp_bp.hp or 0) <= (_active_reloc.hp or 0)):
                    continue
                # Do not promote a Hydrapple ex that the opposing active KNOCKS
                # OUT (user): it would give away 2 prizes. In the record the
                # Hydrapple was at 70/330 and the opponent at 2 prizes, so
                # promoting it handed over the game. The right play was to
                # attack with the active.
                _hlp_dmg_opponent = _op_active_attack_damage_to(
                    _hlp_opa, _hlp_bp,
                    getattr(op_state, 'handCount', None))
                if _hlp_dmg_opponent >= (_hlp_bp.hp or 0):
                    continue
                _hlp_dmg = _our_effective_damage(
                    _hlp_bp, _hlp_opa, 30 + 30 * _hlp_grass_after,
                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
                if _hlp_dmg > 0 and _hlp_opa_hp > 0 and _hlp_dmg >= _hlp_opa_hp:
                    _hydra_lethal_promote = True
                    break
        
        # Rule (user, log 86583929 turn 4, vs Alakazam, LOST): KO pivot with
        # Teal Mask Ogerpon ex. If the active is STUCK (it cannot knock out this
        # turn, e.g. a Fezandipiti ex without the 3 energies of its attack) and
        # on the bench there is a Teal Mask Ogerpon ex that, once PROMOTED and
        # using Teal Dance, reaches >=3 EFFECTIVE energies and whose Myriad Leaf
        # Shower KNOCKS OUT the opposing active, retreat the active to bring up
        # the Ogerpon and finish. The Grass that Teal Dance needs comes from hand
        # or, with Night Stretcher, by recovering a Grass from the discard --
        # including the one the retreat cost has just discarded from the active.
        # The greedy scorer evaluated the benched Ogerpon at their CURRENT energy
        # (via _grd_damage/_bench_attacker_can_ko, which require >=3 effective)
        # and never modelled the Teal Dance ramp after promoting, which is why it
        # did not "see" this line. Only if the opponent does NOT make our ex
        # useless (Ogerpon does not damage Crustle/Sylveon). len(energies) is
        # EFFECTIVE (Meganium's Wild Growth doubles every Grass): without
        # Meganium an Ogerpon at 1 Grass reaches 2 after Teal Dance (<3) and the
        # detector does not fire.
        # The "stuck active" this pivot requires is no longer simply
        # `not _active_can_ko_now`: an active Fezandipiti ex with a lethal Cruel
        # Arrow on the opposing BENCH DOES have a prize today (user, registro_004
        # step 54). Retreating it costs its energy and exposes another body, so
        # the pivot is only imposed on it when the Ogerpon's KO is worth MORE
        # prizes than the snipe's; on a tie or below, we attack.
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
            # Grass available for Teal Dance: in hand, or recoverable with
            # Night Stretcher from the discard (or from the energy the
            # retreat has just discarded from the active, which in our deck is
            # Grass).
            # And there also has to be a route LEFT to put it on the field
            # (user, registro_004 step 54): there was a Grass in hand there,
            # but the manual attachment was already spent and all three Ogerpon
            # had used their Teal Dance, so the "finisher" was impossible and
            # the retreat (8900) crushed the Fezandipiti's real attack.
            # `_grass_attach_route_open` looks at exactly that: a free manual
            # attachment or some charging ability still unused.
            _olp_route_ok = _grass_attach_route_open(
                state, field_counts, abilities_off=meowth_ability_lock)
            _olp_grass_ok = _olp_route_ok and (
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
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    if _olp_dmg > 0 and _olp_opa_hp > 0 and _olp_dmg >= _olp_opa_hp:
                        _ogerpon_lethal_promote = True
                        break
        
        # Rule (user): a CHARGED Tapu Bulu in the active spot that can knock out
        # the opposing active Pokemon must NOT retreat; it must attack. Since it
        # is not an ex, if it is knocked out it only hands over 1 prize, so it is
        # better to finish with it than to spend the pivot to Hydrapple ex (which
        # if knocked out hands over 2 prizes). That is why we veto the
        # retreat/promotion.
        # EXCEPTION: in ex-immune matchups (Crustle / Cornerstone /
        # Sylveon), if the opposing active does NOT belong to the ex-immune line
        # (it does not need Tapu to be damaged) and there is a benched Pokemon
        # that can finish it, we DO retreat Tapu Bulu to keep it as the key
        # attacker against the walls with ex protection. If the opposing active
        # IS of the ex-immune line, Tapu Bulu attacks (it is the one that can
        # handle those walls).
        if (_active_reloc is not None and _active_reloc.id == Tapu_Bulu
                and _active_can_ko_now):
            _tapu_ex_immune_match = (AGENT_STATE.op_is_crustle_deck
                                     or AGENT_STATE.op_is_cornerstone_deck
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
                # Tapu Bulu must attack: we do not retreat it to promote.
                _hydra_lethal_promote = False
        
        _op_active_is_cubchoo = bool(
            op_state.active and op_state.active[0] is not None
            and op_state.active[0].id == Cubchoo)
        _cub_bench_attacker_ready = any(
            _bp_cub is not None and _conf_can_attack_pkmn(_bp_cub)
            for _bp_cub in (my_state.bench or []))
        
        # PRIZE MISMATCH (user, registro_002 step 27 vs Raging Bolt; and
        # vs Mega Abomasnow ex). Our active is a 2-prize ex that canNOT knock
        # out the opposing active this turn and there is a ONE-prize body on the
        # bench (put down by the PLAY rule or already there): RETREAT the ex and
        # promote the 1-prize body. Their attacker one-shots any of ours, so
        # whoever is in front is going to fall: let the opponent's KO pay 1 prize
        # and not 2 (their deck, all 2-3 prize ex, needs big KOs to win in time).
        #
        # AND THE BODY IN FRONT HAS TO BE THE ONE THAT FALLS (user,
        # registro_004 step 55 vs Mega Abomasnow ex, LOST). The sentence the
        # rule is written on -- "their attacker one-shots any of ours, so
        # whoever is in front is going to fall" -- is a claim about the BOARD,
        # and the flag only checked the MATCHUP. On that record their Mega
        # Abomasnow ex hit for 200 and our active Teal Mask Ogerpon ex had 210:
        # it endured. There is no prize to save, so the sacrifice bought
        # nothing -- and the promotion, correctly preferring a body that
        # survives 200, brought up the OTHER 210 HP ex, mute where the one it
        # replaced had Myriad Leaf Shower on the menu.
        # It is read exactly as its deck-agnostic twin `_doomed_ex_sac_pivot`
        # reads it, the opponent's unplayed evolution included: the finisher
        # that kills us is not always the body already in front.
        _rsp_doomed = False
        if (_active_reloc is not None
                and op_state.active and op_state.active[0] is not None):
            _rsp_doomed = max(
                _op_active_attack_damage_to(
                    op_state.active[0], _active_reloc,
                    getattr(op_state, 'handCount', None)),
                _op_evo_dmg_to_active or 0) >= (_active_reloc.hp or 0)
        _raging_sac_pivot = (
            _prize_mismatch_matchup
            and _active_reloc is not None
            and _active_reloc.id in OUR_EX_IDS
            and not _active_can_ko_now
            and can_switch
            and _rsp_doomed
            and any(bp is not None and prize_count(bp) == 1
                    for bp in (my_state.bench or [])))
        
        # GENERALISED MISMATCH (user, registro_004 step 37 vs Mega Lucario
        # ex): same pattern as `_raging_sac_pivot` but for ANY deck, detected
        # with the REAL opposing finisher instead of a fixed list of matchups.
        # Our active is an ex (2 prizes) that CAN attack but whose attack does
        # NOT knock out the opposing active (`not _active_can_ko_now`) and the
        # opposing active's attack KNOCKS OUT our ex next turn
        # (`_op_active_attack_damage_to` >= HP). If there is also NO READY
        # attacker on the bench (we have no better play than preserving the ex)
        # and there is a 1-prize body to put in front, RETREAT the ex and
        # sacrifice the 1-prize body: if we attacked we would not knock out and
        # the ex would die next turn giving away 2 prizes; retreating it we
        # concede only 1 prize and keep the ex -- with its energy -- on the bench
        # to re-promote it after the KO. The promotion chooses the cheapest basic
        # (`_lucario_ko_prefer_basic` / `_ko_prefer_basic_general`). It excludes
        # ex-immune walls in the opposing active spot (there the ex does not
        # attack and there is already dedicated logic: `_ex_stuck_promo_ready` /
        # `_nonex_active_hits_wall`).
        # Do not sacrifice-retreat when we are IN FINISHING RANGE (my_prize<=2):
        # there we have to RACE/finish, not concede tempo (user, Dragapult win
        # engine test, my_prize=1 -> attack). The defensive mismatch only applies
        # when >=3 KOs are still needed to win, where stopping the 2-for-1 matters.
        # The retreat-sacrifice is POSTPONED while there are development plays
        # left this turn (user, registro_004 step 36): a Supporter still unplayed
        # (e.g. Xerosic, which discards the opposing hand) or a basic ATTACKER in
        # hand we can put on the bench (assembling the next attacker) are worth
        # more than retreating NOW -- retreating and developing are not mutually
        # exclusive in the same turn, so we develop first and the retreat comes
        # out at the end (step 37, with the hand already emptied of those plays).
        # It is not postponed for loose low-value items (e.g. Unfair Stamp),
        # which contribute no more than the retreat with the doomed active in
        # front.
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
        _doomed_sac_deferred = False
        if (not _raging_sac_pivot
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
            # THE FINISHER THAT IS NOT ON THE BOARD YET (user, registro_002
            # step 25 vs Mega Lucario ex, LOST): the body in front is not always
            # the one that kills us. A Riolu with one energy projects 60 against
            # our 170 HP Meowth ex; the Mega Lucario ex it becomes next turn
            # hits for 320. `_op_evo_dmg_to_active` is the same projection run
            # against what the active can BECOME (main.py, next to the turn
            # plan), and it is 0 when the active is already a final stage -- so
            # the max() costs nothing where there is no line to read.
            _des_op_dmg = max(
                _op_active_attack_damage_to(
                    _des_opa, _active_reloc,
                    getattr(op_state, 'handCount', None)),
                _op_evo_dmg_to_active or 0)
            # SNIPE GUARD (user, registro_004 t4 vs Marnie's
            # Grimmsnarl, LOST): hiding the ex on the bench only denies
            # prizes if it SURVIVES THERE. Against an attacker that also hits
            # the bench (Shadow Bullet: 180 to the active + 30 to a benched
            # body; Phantom Dive, Jetting Blow...) an ex already wounded below
            # that chip dies anyway, and then the retreat CONCEDES MORE:
            #   staying   -> 2 prizes (the knocked-out active ex)
            #   retreating -> 1 (the promoted body) + 2 (the sniped ex) = 3
            # The arithmetic never favours retreating in that case: at best it
            # ties (if the snipe was going to kill another equally expensive
            # benched body), so the pivot switches off.
            #
            # It is measured with the specific ATTACKER (`OP_BENCH_SNIPE_DAMAGE`
            # of the opposing ACTIVE), not with the board flag
            # `_op_bench_snipe_dmg`: that one falls back to
            # `OP_BENCH_SNIPE_DEFAULT` as soon as there is ANY drip threat in
            # play, and switching the pivot off because of a sniper that is not
            # in front costs games (measured vs crustle/Kangaskhan: -3.1 points
            # with the broad version).
            # THE GUARD STAYS ON THE BODY IN FRONT, and deliberately does NOT
            # read the evolution the way the damage above does. Extending it was
            # tried and it turns off the pivot for a sniper that is not there
            # yet -- an opposing Morgrem, whose Grimmsnarl ex snipes for 30, is
            # enough to strand a doomed ex at 30 HP (tests/
            # test_doomed_ex_falls_back_vs_sniper.py). That is the same
            # broadening the paragraph above records as measured at -3.1 points.
            # The asymmetry is on purpose: the damage reading TURNS THE PIVOT
            # ON where the agent was blind, the snipe reading would turn it OFF
            # where it has been measured to work.
            _des_snipe = OP_BENCH_SNIPE_DAMAGE.get(_des_opa.id, 0)
            if (_des_op_dmg >= (_active_reloc.hp or 0)
                    and _des_snipe < (_active_reloc.hp or 0)):
                # THE POSTPONEMENT IS NOT A CANCELLATION (user, registro_002
                # step 25). While a development play is still pending the
                # retreat waits its turn, and that is right -- but the record
                # shows what the waiting used to cost: the pending play was a
                # Tapu Bulu that the turn-2 rule VETOES, so it never happened,
                # the pivot stayed off all turn and the agent ENDED the turn
                # with the doomed ex in front. A play that is not going to be
                # made cannot postpone anything, and from inside this scorer
                # there is no way to know which ones those are. So the deferral
                # stops being a switch-off and becomes a score floor (see the
                # end of the chain): the retreat still yields to any real play
                # -- they all score above it, and putting a Pokemon down also
                # outranks it by TIER -- but it never yields to ENDING THE TURN.
                if _doomed_pending_play:
                    _doomed_sac_deferred = True
                else:
                    _doomed_ex_sac_pivot = True

        # THE PLAN'S POINTER IS A PROMISE, AND IT EXPIRES (user, registro_004
        # step 28 vs Alakazam, WON). `plan.attacker` is chosen ONCE per turn:
        # the loop that picks it only overwrites the pointer when it finds a
        # BETTER route, never when the route it already wrote stops existing.
        # So the pointer survives the turn that spends what backed it.
        #
        # In the record it pointed at the benched Teal Mask Ogerpon ex on turn
        # 4, when the plan was "attach the Grass in hand to it -> Myriad Leaf
        # Shower for the KO". The Grass did get attached -- by Teal Dance, and
        # to the ACTIVE Ogerpon, which is another body. By the end of the turn
        # both twins carried 2 energies, Myriad costs 3, and neither could
        # attack. The pointer still said "the bench attacks", and the branch
        # below cashed it for 3500: retreat, pay one Grass to the discard,
        # promote the identical twin. Same species, same HP, one Grass less --
        # the swap bought nothing and the menu did not even offer an ATTACK.
        #
        # So before the branch trusts the pointer, the body it points at is
        # ASKED AGAIN whether it can attack TODAY. `_reachable_grass_for` is
        # wider than the test the plan itself used (it also counts Teal Dance /
        # Ripening Charge and the Grass the retreat fee is about to send to the
        # discard), so a pointer that is still valid always survives this
        # re-reading: only a promise that has actually expired falls through.
        _plan_relay = None
        _pr_bench = my_state.bench or []
        _pr_i = AGENT_STATE.plan.attacker - 1
        if 0 <= _pr_i < len(_pr_bench):
            _plan_relay = _pr_bench[_pr_i]
        _plan_relay_can_attack = False
        if _plan_relay is not None:
            _pr_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_plan_relay.id)
            if _pr_req is not None:
                _pr_eff = len(_plan_relay.energies) * _grass_mult()
                if _pr_eff >= _pr_req:
                    _plan_relay_can_attack = True
                else:
                    _pr_reach = _reachable_grass_for(
                        _plan_relay, state, my_state, hand_counts, field_counts,
                        extra_discard_grass=_retreat_grass_to_discard(
                            _active_reloc))
                    _plan_relay_can_attack = (
                        _pr_eff + _pr_reach * _grass_attach_unit() >= _pr_req)

        # THE RELAY THAT TAKES NO PRIZE DOES NOT EARN THE FRONT SPOT (user,
        # registro_004 step 37 vs Iono's Bellibolt ex, LOST). The arm below cashes
        # `plan.attacker` on the strength of `_plan_relay_can_attack`, which says
        # the relay's attack is LEGAL and never that it is worth the swap. The
        # other half of the question is `_plan_relay_is_inert`, written out in
        # main.py: no prize by ANY route today (`prizes_today` already counts this
        # very retreat, through `_prizes_via_promote`) and nothing to run from.
        #
        # `_conf_should_retreat` is the escape this side adds to the ones the flag
        # already carries: a swap that is escaping a special condition is not
        # being paid for by the relay's damage either.
        _relay_earns_the_front_spot = (
            not _plan_relay_is_inert or bool(_conf_should_retreat))

        if _suicide_swap_win_promote:
            # RELIEF OF THE SUICIDAL FINISHER (user, registro_016 step 184 vs
            # Marnie's Grimmsnarl, DRAW): the active's attack knocks out but
            # its SELF-DAMAGE kills it, and with that corpse the opponent takes
            # their last prize -> a draw (or a loss). On the bench there is a
            # finisher that wins CLEANLY: retreating to promote it is the only
            # play that turns the 0-0 into a win, so it goes above any other
            # reason to retreat (including the lethal Hydrapple/Ogerpon pivots,
            # which chase the SAME prize with less urgency). The play-order tier
            # (`_TIER_WIN_ATTACK`) also raises it above charges and development,
            # which would otherwise dominate by TIER despite their lower score.
            score = 9600
        elif _win_ko_active_via_promote:
            # MATCH POINT ON THE ACTIVE (user, registro_010 step 144 vs Marnie's
            # Grimmsnarl ex, LOST): knocking out the opposing ACTIVE takes the
            # prizes we are missing and the finisher is on the BENCH. It is the
            # SAME play as the relief of the suicidal finisher -- closing the
            # game this turn -- so it shares its score and `_TIER_WIN_ATTACK`:
            # without the tier, any energy charge (tier ENERGY) would crush it
            # by ORDER despite being worth less. Mutually exclusive with
            # `_suicide_swap_win_promote`: that flag requires the CURRENT active
            # not to finish.
            score = 9600
        elif _hydra_lethal_promote:
            # Retreat the active to promote the benched Hydrapple ex whose
            # Syrup Storm is LETHAL and finish. Top retreat priority.
            score = 9000
        elif _ogerpon_lethal_promote:
            # Retreat the stuck active to promote a benched Teal Mask Ogerpon
            # ex and finish with Myriad Leaf Shower after Teal Dance
            # (user, log 86583929 turn 4 vs Alakazam). Retreat priority equal
            # to that of the Hydrapple pivot: take the prize NOW.
            # The later actions (Night Stretcher to recover the Grass, Teal
            # Dance on the new active and the attack) are already enabled by
            # their own scorers (_td_ko_on_active gives 31500 to the Teal Dance
            # that enables the KO, and the ATTACK scorer finishes if it is lethal).
            score = 8900
        elif _relay_saves_the_game:
            # Retreat and take the SAME prize with the benched body that is
            # still standing when the reply lands, on the boards where the body
            # in front is not (see the flag). 8860: immediately above the pivot
            # it is the extreme case of -- there their reply reaches match
            # point, here it ARRIVES -- and under the lethal promotions, which
            # end the game outright and need no reply projected at all.
            score = 8860
        elif _relay_finisher_pivot:
            # Retreat and take the same prize with the benched body that
            # survives their reply (see the flag). 8850: the same family as the
            # two lethal promotions above -- take the prize now -- and just
            # under them, so the cases they already name keep their behaviour.
            score = 8850
        elif _front_spot_upgrade:
            # Retreat and take the same prize with the body that pays less for
            # standing there afterwards (see the flag). Under the relay that
            # survives (8850) -- the case it generalises keeps its own reading --
            # and the cheaper CORPSE goes above the tougher BODY, which is the
            # order the ladder is written in.
            score = 8840 if _front_spot_upgrade == UPGRADE_PRIZE else 8830
        elif (_op_active_is_cubchoo and can_switch
                and not _cub_bench_attacker_ready):
            # Cubchoo matchup: their attack leaves our active unable to attack
            # next turn. Retreating now to bring up a benched Pokemon that ALSO
            # cannot attack (not enough energy) only exposes it to the same
            # attack and wastes the pivot. While there is no READY attacker on
            # the bench, we do NOT retreat: we keep the active (Cubchoo hits for
            # little) and use the turn to charge energy until a benched attacker
            # is ready. When that attacker is charged, _cub_bench_attacker_ready
            # will be True and the retreat will be allowed to bring it up and
            # attack on our turn.
            score = SCORE_VETO
        elif (_lucario_sac_pivot and _lucario_sac_available
                and bench_count >= 1 and can_switch):
            # Retreat the Ogerpon ex so as not to hand 2 prizes to the Mega Lucario;
            # afterwards we will promote a 1-prize sacrifice.
            score = 8000
        elif _conf_should_retreat:
            score = 4000 + condition_urgency
        elif _hydra_ex_protect_retreat:
        
            score = 6000
        elif (_ex_stuck_promo_ready or _cubchoo_lock_stuck) and can_switch:
            # Our active is an ex blocked by an immune wall (Crustle /
            # Sylveon) and there is a READY non-ex attacker on the bench: retreat to
            # promote the one that DOES hit the wall (the strongest is chosen in
            # `_best_promote_card`). It avoids wasting the turn attacking for 0.
            # `_cubchoo_lock_stuck`: the same pattern with the active Hydrapple ex
            # BLOCKED by Snotted Up and a ready benched attacker (step 82).
            score = 6000
        elif _hydra_pivot_active:
            # Defensive pivot: retreat the fragile active and bring up Hydrapple
            # ex (at full HP) which also knocks out. High priority so it beats
            # attacking with the fragile active (which would die next turn). The
            # plan already points at Hydrapple, so the option of ATTACKING with
            # the active is suppressed (plan.attacker >= 1).
            score = 6500
        elif _teal_wall_pivot and can_switch:
            # A doomed active Teal Mask Ogerpon ex that CANNOT attack: Teal
            # Dance has already been used (1 Grass attached -> it pays the
            # retreat cost of 1). Retreat and bring up the strongest body on
            # the bench (Hydrapple ex, 330 HP) even if it cannot attack yet: do
            # not give the active away for nothing and put up a wall. The
            # promotion chooses the one with the most HP.
            score = 6450
        elif _doomed_mute_pivot and can_switch:
            # THE MUTE BODY DOES NOT PAY FOR THE FRONT SPOT: the same play as
            # the branch above, read off any two bodies instead of off the
            # Ogerpon/Hydrapple pair (see the flag in main.py). The active
            # cannot attack today, the opponent's REAL finisher kills it before
            # our next turn and its retreat is ALREADY paid -- so standing
            # there buys nothing and costs its whole price, while the body that
            # relieves it either survives the hit or is cheaper.
            #
            # Same score as the special case, because it is the same play: the
            # ladder above (lethal promotions, the prize sacrifices) keeps
            # ruling, and WHICH body comes up is not decided here but by the
            # promotion chain, which already ranks survival first and prizes
            # second.
            score = 6450
        elif _hydra_wall_pivot:
            # A doomed active Teal Mask Ogerpon ex that CAN attack but does
            # NOT knock out (a healthy Hydrapple ex wall on the bench). Retreat
            # and bring up the wall (330 HP) which survives the opposing
            # finisher and keeps attacking (Syrup Storm 330), instead of
            # attacking with the fragile Ogerpon which would die giving away 2
            # prizes. The plan points at Hydrapple, so ATTACKING with the active
            # is suppressed (plan.attacker >= 1).
            score = 6450
        elif _tapu_sac_pivot:
            # Prize sacrifice (user): our active is a 2-prize ex at risk and a
            # ready benched Tapu Bulu (1 prize) can knock out the opposing
            # active. Retreat the ex and bring up Tapu Bulu to attack: the same
            # KO, but if we are knocked out we hand over 1 prize instead of 2.
            # High priority: it wins even when the active can also knock out now
            # (_active_can_ko_now). The plan points at Tapu, so the option of
            # ATTACKING with the active is suppressed (plan.attacker>=1).
            score = 6600
        elif _festival_sac_pivot:
            # THE STADIUM THEY BROUGHT ARMS OUR DIPPLIN TOO (user, registro_006
            # steps 81-86 vs Festival Lead, LOST): the same prize sacrifice as
            # the arm above with the body Festival Grounds turns into an
            # attacker. Our doomed 2-prize ex retreats, the benched Dipplin takes
            # the SAME knockout with Do the Wave and -- because the stadium is on
            # the field -- throws it a second time (`_festival_double_wave`).
            # 6590, just under the charged Tapu Bulu, which hits for 220 and does
            # not need this turn's attachment. Like every arm in this family it
            # is ABOVE the `_active_can_ko_now` veto, which is exactly the rule
            # that kept the 10 HP ex in front of the record: the prize is not
            # given up, it is cashed by the body that survives to keep it.
            score = 6590
        elif _raging_sac_pivot:
            # Mismatch vs Raging Bolt (see the flag above). 6540: alongside
            # the other prize sacrifices (6450-6600), above the generic veto
            # "the active can attack" (_grd_prefer_attack), which here would
            # be a mistake: attacking without knocking out gives away 2 prizes.
            score = 6540
        elif _prize_denial_pivot:
            # Prize denial (user): retreat the DOOMED active ex (2
            # prizes) which, if we attacked, would die next turn anyway giving
            # the opponent the prizes to WIN, and bring up a 1-prize body that
            # attacks. That way the opponent's KO next turn does NOT close the
            # game. The plan points at that body (plan.attacker>=1), so ATTACKING
            # with the doomed active is suppressed.
            score = 6550
        elif _doomed_ex_sac_pivot:
            # Generalised mismatch (user, registro_004 step 37 vs Mega
            # Lucario ex): the active ex can attack but does NOT knock out and the
            # opponent finishes it next turn, with no ready benched attacker.
            # Retreat the ex and sacrifice a 1-prize body (concede 1 instead of 2
            # and preserve the ex). Same tier as the other prize sacrifices,
            # below the "the active can attack" veto which here would be a
            # mistake (attacking without knocking out gives away 2 prizes).
            score = 6530
        elif _meg_retreat_for_hydra and not _active_can_ko_now:
            # Active Meganium: bring up the benched Hydrapple ex (opponent with
            # no ex protection). High priority so it beats attacking with
            # Meganium or keeping it. Exception: if Meganium knocks out NOW
            # (_active_can_ko_now) it stays to take the prize.
            score = 6400
        elif _wall_ko_promote is not None and can_switch:
            # LETHAL RELIEF AGAINST THE WALL (user, registro_018 step 113 vs
            # Crustle, LOST): the active hits the wall but does NOT finish it and
            # on the bench there is an unblocked body that DOES (Meganium 140 vs
            # a 170 Crustle <- Tapu Bulu 220). Retreat and finish. It goes ABOVE
            # the `_nonex_active_hits_wall` veto -- which is already switched off
            # in this case -- and above the sacrifice pivots: taking the prize
            # now rules. The plan points at the relief, so ATTACKING with the
            # active is suppressed.
            score = 6700
        elif _nonex_active_hits_wall:
            # user, log 86406907 step 87, WON vs Crustle: our active is a
            # NON-ex attacker (e.g. Meganium) that DOES hit the ex-immune wall
            # (active Crustle). It NEVER retreats: retreating would only
            # promote a benched ex that does 0 to the wall. It must ATTACK.
            score = SCORE_VETO
        elif _grd_prefer_attack:
        
            score = SCORE_VETO
        elif _active_can_ko_now:
        
            score = SCORE_VETO
        elif AGENT_STATE.plan.attacker >= 1 and _plan_relay_can_attack:

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
        
            if not _relay_earns_the_front_spot:
                # The pointer names a body that CAN attack and the plan says
                # that attack takes nothing: the swap has no buyer. See the
                # flag above.
                score = SCORE_VETO
            elif not _retreat_active_can_attack:

                score = 3500
            else:

                score = 2500
        elif my_state.active and my_state.active[0] is not None:
            active = my_state.active[0]
            active_energy = len(active.energies)
        
            _our_first_turn = (state.turn == 1 and AGENT_STATE.we_go_first) or (state.turn == 2 and not AGENT_STATE.we_go_first)
        
            NON_ATTACKERS = (Meganium, Meowth_ex, Chikorita, Bayleef, Applin)
        
            # Meganium included: it can attack (req 4 effective) and must count
            # as an available benched attacker. Single source: MAIN_ATTACKERS.
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
            if ((AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck) and
                    can_switch and active.id != Meganium):
        
                _opa_km = (op_state.active[0]
                           if (op_state.active and op_state.active[0] is not None)
                           else None)
                _opa_km_hp = (_opa_km.hp or 0) if _opa_km is not None else 0
        
                def _meg_blk_ko(_p):
                    # does this non-ex attacker knock out the opposing active (Crustle) this
                    # turn? len(energies) is ALREADY the EFFECTIVE energy (Wild Growth
                    # already applied in the observation) -> Solar Beam (140) with 4.
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
                        _p, _opa_km, _base, AGENT_STATE.meganium_in_play,
                        neutralization_zone_active) >= _opa_km_hp
        
                _other_atk_ready_meg = any(
                    _mp_meg is not None and _mp_meg.id != Meganium and
                    _meg_blk_ko(_mp_meg)
                    for _mp_meg in ([active] + list(my_state.bench)))
        
                _meganium_bench_ready_meg = any(
                    bp is not None and bp.id == Meganium and _meg_blk_ko(bp)
                    for bp in my_state.bench)
        
                _act_ko_opponent_meg = False
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
                            AGENT_STATE.meganium_in_play, neutralization_zone_active)
                        if _act_dmg_meg >= (_opa_meg.hp or 0) and _act_dmg_meg > 0:
                            _act_ko_opponent_meg = True
                if (not _other_atk_ready_meg and _meganium_bench_ready_meg and
                        not _act_ko_opponent_meg):
                    _meg_only_attacker_retreat = True
        
            if _meg_only_attacker_retreat:
        
                score = 3500
        
            elif ((AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck) and
                  active.id == Teal_Mask_Ogerpon_ex):
                if not can_switch:
                    score = SCORE_VETO
                else:
        
                    _tmo_ko_opponent = False
                    _opa_tmo = (op_state.active[0]
                                if (op_state.active and op_state.active[0] is not None)
                                else None)
                    if can_attack and _opa_tmo is not None:
                        _opa_tmo_e = len(_opa_tmo.energies)
                        _tmo_base = 30 + 30 * (len(active.energies) + _opa_tmo_e)
                        _tmo_dmg = _our_effective_damage(
                            active, _opa_tmo, _tmo_base,
                            AGENT_STATE.meganium_in_play, neutralization_zone_active)
                        if _tmo_dmg >= (_opa_tmo.hp or 0) and _tmo_dmg > 0:
                            _tmo_ko_opponent = True
                    if _tmo_ko_opponent:
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
                            elif (AGENT_STATE.op_is_crustle_deck and
                                  bp.id == Dipplin and _bp_e >= 1):
                                _tmo_attacker_ready = True
                                break
                            elif (AGENT_STATE.op_is_crustle_deck and
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
        
                # GUARD "do not swap an ex for a worse body" (user,
                # registro_009 vs Archaludon ex): retreating an ex from the
                # ACTIVE spot only pays off if the body coming up (a) KNOCKS
                # OUT the opposing active -- taking a prize NOW, whether 1 or
                # 2 -- or (b) endures AT LEAST as much as the one going down
                # (a pivot to an equal or bigger wall). Swapping a 330 HP
                # Hydrapple ex for a 210 HP Teal Mask Ogerpon ex "because the
                # second one can attack" throws the wall away and puts in
                # front a 2-prize body that is easier to defeat: the opponent
                # takes the same prizes with less effort. And if the one
                # coming up neither finishes nor endures, the chip damage does
                # not pay for the swap. Deck-agnostic: it looks at HP,
                # effective KO and retreat cost, not at specific cards.
                #
                # A THIRD WAY OUT, (c), when the body going down is not a wall
                # (user, episode 90321662 step 104 vs Crustle/Great Tusk, LOST):
                # a Meowth ex at 170/170 has no attack in any state of the game,
                # so the 170 it "endures" buys nothing but the two prizes it
                # hands over when it eventually falls. With their Neutralization
                # Zone zeroing our ex against their 1-prize active, the only
                # bodies that could hurt anything were non-ex smaller than 170,
                # (a) and (b) both failed, the retreat was vetoed and the turn
                # ended without attacking -- again.
                #
                # So when the active is an ex we never attack with
                # (`_ex_active_is_a_wall`), a relay that DOES damage and hands
                # over no more prizes is also enough. It is strictly a way OUT:
                # (a) and (b) keep their say untouched, which is what leaves the
                # defensive pivot to a bigger wall in place for the boards where
                # nothing can hurt their active at all.
                _xx_act = active
                _xx_op = _active_of(op_state)
                _xx_act_hp = (_xx_act.hp or 0) if _xx_act is not None else 0
                _xx_wall = _ex_active_is_a_wall(_xx_act)
                _xx_act_prizes = prize_count(_xx_act) if _xx_act is not None else 0
                _xx_vale = False
                if _xx_act is None or _xx_act.id not in OUR_EX_IDS:
                    _xx_vale = True   # the active is not an ex: the rule does not apply
                else:
                    for _xx_bp in (my_state.bench or []):
                        if _xx_bp is None:
                            continue
                        _xx_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_xx_bp.id)
                        if _xx_req is None:
                            continue
                        _xx_e = len(_xx_bp.energies)
                        if _xx_e * _grass_mult() < _xx_req:
                            continue  # it is not a ready attacker
                        if (_xx_bp.hp or 0) >= _xx_act_hp:
                            _xx_vale = True   # a pivot to an equal or bigger wall
                            break
                        if _xx_op is not None:
                            _xx_base = _attacker_base_damage(
                                _xx_bp.id, _xx_op, _xx_e * _grass_mult(),
                                grass_scale=max(
                                    0, total_grass - _retreat_grass_units(
                                        RETREAT_COST.get(_xx_act.id, 1))),
                                teal_self_energy=_xx_e,
                                bench_count=bench_count)
                            _xx_dmg = _our_effective_damage(
                                _xx_bp, _xx_op, _xx_base,
                                AGENT_STATE.meganium_in_play,
                                neutralization_zone_active) if _xx_base > 0 else 0
                            if _xx_dmg >= (_xx_op.hp or 0) and _xx_base > 0:
                                _xx_vale = True
                                break
                            if (not _xx_wall and _xx_dmg > 0
                                    and prize_count(_xx_bp) <= _xx_act_prizes):
                                _xx_vale = True
                                break
                score = 3200 if _xx_vale else SCORE_VETO
        
            elif (AGENT_STATE.op_is_cornerstone_deck and can_switch and
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
        
            elif (AGENT_STATE.op_is_crustle_deck and can_switch and
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
                            AGENT_STATE.meganium_in_play, neutralization_zone_active)
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
        
            elif active.id == Fezandipiti_ex and AGENT_STATE.plan.attacker == 0:
                score = SCORE_VETO
        
            elif (active.id == Fezandipiti_ex and
                  state.turn == 2 and not AGENT_STATE.we_go_first):
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
        
                # Is there a benched attacker REALLY ready to attack this
                # turn? It is not enough for an attacker to exist by
                # identity (e.g. a Teal ex): it has to have enough
                # effective energy (Wild Growth included), or be able to
                # complete it by attaching ONE Grass energy this turn.
                # Without this check the active was retreated to bring up
                # an UNCHARGED attacker, which could not attack either,
                # wasting the turn and the retreat cost.
                # "Attaching ONE Grass this turn" is not only the one in hand:
                # `_reachable_grass_for` also counts the discard through Night
                # Stretcher and the card the retreat itself is about to pay
                # (ptcg/calc/energy.py).
                _bar_discards = _retreat_grass_to_discard(active)
                _bench_attacker_ready = False
                for bp in my_state.bench:
                    if bp is None or bp.id not in STRATEGIC_ATTACKERS:
                        continue
                    _bar_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(bp.id)
                    if _bar_req is None:
                        continue
                    _bar_eff = len(bp.energies) * _grass_mult()
                    if _bar_eff >= _bar_req:
                        _bench_attacker_ready = True
                        break
                    _bar_reach = _reachable_grass_for(
                        bp, state, my_state, hand_counts, field_counts,
                        extra_discard_grass=_bar_discards)
                    if (_bar_reach
                            and _bar_eff + _bar_reach * _grass_attach_unit() >= _bar_req):
                        _bench_attacker_ready = True
                        break
        
                # Rescue pivot: if the active is a FRAGILE pre-evolution
                # (Chikorita/Bayleef) DOOMED this turn (a likely KO) and on the
                # bench there is a body that SURVIVES the opponent's best hit, it is
                # worth RETREATING even if the benched attacker cannot attack yet:
                # we shelter the pre-evolution (it evolves later on the bench), we
                # bring up a wall that endures and we refill the hand (Lillie's
                # becomes available after evolving). Keeping the low-HP body in
                # front only gives it away for free and stalls the evolution line.
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
        
                # EVOLUTION LINE pivot (user, registro_003 step 29 vs
                # Dragapult, LOST): the active is a Chikorita with a Bayleef
                # in hand. The EVOLVE scorer already VETOES evolving in the
                # ACTIVE spot when the pre-evolution can pay its retreat
                # ("it is better to RETREAT it first and evolve it on the
                # bench", see the Bayleef/_is_active branch), but here the
                # retreat was vetoed because the benched attacker (Tapu
                # Bulu) had no energy yet, so the agent kept the Chikorita
                # up front and spent the turn on Growl (0 damage) with the
                # Meganium line dead in hand. Retreating is the play: it
                # brings up a body with more HP and the Chikorita evolves on
                # the BENCH -- with Forest of Vitality in play, even the
                # whole Chikorita->Bayleef->Meganium chain that same turn.
                # Besides, Meganium's Wild Growth DOUBLES every Grass: it
                # lowers from 4 to 2 the PHYSICAL Grass Tapu Bulu needs for
                # Wood Hammer. Only if the pre-evolution can really evolve
                # this turn (it has been in play since the start of the
                # turn, or Forest allows it even if it was just played) and
                # there is a body on the bench to promote.
                _evo_line_bench_pivot = (
                    can_switch
                    and active.id == Chikorita
                    and hand_counts.get(Bayleef, 0) >= 1
                    and bench_count >= 1
                    and not _active_can_ko_now
                    and (AGENT_STATE.forest_in_play
                         or not getattr(active, 'appearThisTurn', False)))

                # THE FRONT SPOT IS A BILL AND THE RETREAT CHOOSES WHO PAYS IT
                # (user, episode 90481101 step 58, vs Teal Mask Ogerpon ex, WE
                # LOST). Active Applin 40/40 -- ONE prize -- with a Teal Mask
                # Ogerpon ex on the bench carrying two energies (Myriad Leaf
                # Shower costs three, so it cannot attack the turn it is
                # promoted), and in front of us their Ogerpon ex with FIVE:
                # 30 + 30x(5+2) = 240 against anything we can put up. The agent
                # retreated -- 3000, awarded for nothing more than a
                # STRATEGIC_ATTACKER being on the bench -- and handed over a mute
                # 2-prize body. Ending the turn hands over the Applin and ONE.
                #
                # The two generic arms of this branch only ever asked "is there
                # an attacker on the bench?": not whether it can act today, not
                # what it costs when it falls, and above all not whether their
                # attack knocks it out next turn. That last question is the one
                # this flag adds. If EVERY body we could promote (a) hands over
                # MORE prizes than the active we are retreating, (b) cannot
                # attack the turn it goes up and (c) dies to the opponent's
                # projected attack, then the retreat buys no damage, no wall and
                # no tempo -- only a bigger prize for the same knock-out.
                #
                # Any one of the three failing is an escape: a body that costs no
                # more is a free swap, one that attacks pays its own way, and one
                # that SURVIVES is the defensive pivot this branch exists for.
                #
                # `scaled=True` is deliberate, and it is the same reading the
                # turn plan uses in `_opponent_reply`: the blind projector
                # answers the 30 PRINTED on a Myriad Leaf Shower the engine
                # resolves at 240, and with that number this rule could never see
                # a knock-out at all. It is admissible here for the reason stated
                # in `_op_active_attack_damage_to`: this is a NEW rule, with no
                # threshold ever fitted to the blind reading.
                _pf_op = _active_of(op_state)
                _pf_act_prizes = prize_count(active) if active is not None else 0
                _pf_op_hand = getattr(op_state, 'handCount', None)
                _pf_every_relay_costs_more = False
                if (can_switch and _pf_op is not None and bench_count >= 1
                        and not _bench_attacker_ready):
                    _pf_every_relay_costs_more = True
                    for _pf_bp in (my_state.bench or []):
                        if _pf_bp is None:
                            continue
                        if prize_count(_pf_bp) <= _pf_act_prizes:
                            _pf_every_relay_costs_more = False   # (a) costs no more
                            break
                        if _can_attack_eff(_pf_bp.id, len(_pf_bp.energies)):
                            _pf_every_relay_costs_more = False   # (b) it acts today
                            break
                        if _op_active_attack_damage_to(
                                _pf_op, _pf_bp, _pf_op_hand,
                                scaled=True) < (_pf_bp.hp or 0):
                            _pf_every_relay_costs_more = False   # (c) it survives
                            break

                if active.id in (Chikorita, Bayleef, Meganium):
        
                    # Rule (user, log 86607718 turn 2, vs Crustle, WE LOST):
                    # vs Crustle, if the ACTIVE is a Chikorita and there is NO
                    # Chikorita on the bench, the priority is to RETREAT it (to
                    # evolve it into Meganium on the bench and bring up a useful
                    # body), EVEN IF there is not yet a READY attacker on the
                    # bench (the "benched attacker with no energy" veto below
                    # blocked it). An active Chikorita is a burden that does not
                    # damage the wall. It requires being able to retreat
                    # (can_switch: we already charged 1 Grass onto the Chikorita,
                    # see energy_score) and having a body on the bench to promote.
                    # The promotion prefers an attacker and, failing that, an ex
                    # (Ogerpon ex first, see _best_promote).
                    if (AGENT_STATE.op_is_crustle_deck and active.id == Chikorita
                            and field_counts.get(Chikorita, 0) <= 1
                            and bench_count >= 1):
                        score = 6500
                    elif _has_bench_attacker and _bench_attacker_ready:
                        score = 6000
                    elif _fragile_doomed_pivot:
                        # A doomed fragile active: retreat to bring up a body
                        # that survives and shelter the pre-evolution, even if the
                        # benched attacker cannot attack yet. It beats attacking
                        # with a body that will die next turn.
                        score = 5800
                    elif _evo_line_bench_pivot:
                        # Active Chikorita with a Bayleef in hand: retreat to
                        # assemble the Meganium line on the BENCH (see the
                        # flag's comment). It goes below the rescue pivots but
                        # ABOVE the two "benched attacker with no charge"
                        # vetoes, which were the ones leaving the Chikorita
                        # attacking for chip damage.
                        score = 5700
                    elif _has_bench_attacker and not _bench_attacker_ready:
                        # There is a benched attacker but WITHOUT energy to
                        # attack this turn: retreating now would only bring up
                        # a body that does not attack either. Better to keep
                        # the active and go on charging the benched attacker.
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
                    score = (SCORE_VETO if _pf_every_relay_costs_more
                             else 3000)
                elif _bench_has_only_non_attackers and _has_attacker_in_hand:

                    score = SCORE_VETO
                else:
                    score = (SCORE_VETO if _pf_every_relay_costs_more
                             else 2500)
        
            elif active.id in STRATEGIC_ATTACKERS:
        
                # Ready-to-attack via effective energy (single source:
                # ATTACK_ENERGY_REQ). The branch already guarantees membership of
                # STRATEGIC_ATTACKERS (= MAIN_ATTACKERS).
                _active_can_attack = _can_attack_eff(active.id, active_energy)
        
                if not _active_can_attack:
        
                    # The Grass the retreat itself is about to discard: with a
                    # Night Stretcher in hand it comes straight back and can be
                    # attached to the body we promote. Weighing the retreat
                    # WITHOUT counting it is what left a free prize on the table
                    # in registro_004 step 45 -- see the block comment in
                    # ptcg/calc/energy.py.
                    _rt_discards = _retreat_grass_to_discard(active)

                    # ... but only when the turn HAS an attack. Going first on
                    # turn 1 nobody may attack, so promoting a body that becomes
                    # ready is not a play, it is an energy thrown away and a turn
                    # of development lost (tests/test_state_builder.py,
                    # test_abomasnow_first_turn_going_first_it_does_not_sacrifice).
                    # The already-charged branch below keeps the behaviour it had.
                    _rt_attackless_turn = (state.turn == 1
                                           and AGENT_STATE.we_go_first)

                    _has_ready_bench = False
                    for bp in my_state.bench:
                        if bp is None:
                            continue
                        # It counts any ready main attacker on the bench
                        # (Meganium included, previously omitted), and any that
                        # BECOMES ready with the energy this turn can still reach
                        # it: the manual attachment, a Teal Dance / Ripening
                        # Charge, and the discard through Night Stretcher.
                        if bp.id not in MAIN_ATTACKERS:
                            continue
                        _rb_eff = len(bp.energies)
                        if _can_attack_eff(bp.id, _rb_eff):
                            _has_ready_bench = True
                            break
                        if _rt_attackless_turn:
                            continue
                        _rb_reach = _reachable_grass_for(
                            bp, state, my_state, hand_counts, field_counts,
                            extra_discard_grass=_rt_discards)
                        if _rb_reach and _can_attack_eff(
                                bp.id, _rb_eff + _rb_reach * _grass_attach_unit()):
                            _has_ready_bench = True
                            break

                    if _has_ready_bench:
                        score = 2500
                    else:
                        score = SCORE_VETO
        
                elif (can_switch
                      and estimated_op_damage > 0
                      and estimated_op_damage >= (active.hp or 0)
                      and not (AGENT_STATE.plan.remain_hp is not None
                               and AGENT_STATE.plan.remain_hp <= 0)):
                    # DEFENSIVE RETREAT: our active attacker CAN attack
                    # but will be knocked out next turn (the opponent's
                    # estimated damage >= its HP) and attacking with it does
                    # not knock out the opposing active. If on the bench
                    # there is a MORE resilient attacker that survives the
                    # opposing attack and can attack once promoted,
                    # retreating to it avoids the loss (a wall that also
                    # applies pressure). Without this the code assumes "if I
                    # can attack, I attack" and lets the doomed active die.
                    _def_retreat_target = False
                    for bp in my_state.bench:
                        if bp is None or bp.id not in MAIN_ATTACKERS:
                            continue
                        if (bp.hp or 0) <= _op_best_damage_vs(bp):
                            continue  # it would also be knocked out next turn
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
        
        # Cancel the retreat if it would only relocate the same Pokemon (same
        # species) to the active spot: it is useless and wastes the energy of
        # the retreat cost (user, log 86510119 step 26). See `_same_species_retreat`.
        # EXCEPTION (user, registro_005 vs Comfey): if the active is CONFUSED
        # (Brambleghast), retreating it to promote a body of the SAME species
        # DOES contribute: the new active is NOT confused and can attack without
        # the coin flip. With two Teal Mask Ogerpon ex (the matchup's plan) this
        # is the normal case, so the confusion-escape retreat is not vetoed.
        if (_same_species_retreat and score > 0 and not _conf_should_retreat
                and not _suicide_swap_win_promote):
            score = SCORE_VETO
        
        # Pivot vs Alakazam (user, registro_010 step 127): retreat the active
        # ex to promote a 1-prize body (Meganium/Tapu Bulu) that KNOCKS OUT
        # the opposing active (see `_alakazam_pivot_1prize`). It must BEAT
        # the attack of the 2-prize ex (score ~1100) so the engine retreats
        # instead of attacking with the ex; it is still below the
        # "Supporter before retreating" threshold (2000) to respect that order.
        if _alakazam_pivot_1prize:
            score = max(score, 6000)

        # THE ONE-PRIZE WALL TAKES THE FRONT ON OUR FIRST TURN (user,
        # registro_002 step 14 vs Marnie, LOST). See `_ft_wall_pivot` in
        # main.py: the flag already asked for everything that matters -- our
        # first turn, no attack available, an undamaged wall on the bench, and
        # an active that either hands over more prizes or endures less than it.
        #
        # The same 6000 as the pivot above, and for the same reason: it has to
        # beat attacking with the body in front (~1100) while staying under the
        # "play the Supporter BEFORE retreating" ceiling (2000) that the block
        # below applies. That ceiling is not an obstacle here, it is the rest
        # of the rule -- the refill is played first and the retreat is
        # re-evaluated when nothing else in the turn is left, which is exactly
        # "if by the end of the turn we cannot attack".
        if _ft_wall_pivot:
            score = max(score, 6000)

        # THE EX DOES NOT WAIT IN FRONT OF THE MEGA STARMIE LINE (user,
        # registro_002 step 28, episode 90583594, LOST). See
        # `_starmie_sac_pivot` in main.py: the flag has already asked for the
        # matchup, for no attack being available, for a 2-prize ex in the
        # active spot, for a one-prize body to put in front of it and for the
        # fee being payable.
        #
        # The same 6000 as the two pivots above, and it is the same sentence:
        # it beats attacking with the body in front (~1100) and stays under the
        # "play the Supporter BEFORE retreating" ceiling (2000) applied below,
        # which is not an obstacle but the rest of the rule -- the refill is
        # played first and the retreat comes back when the turn has nothing
        # else left, which is what "if we cannot attack" means at the end of a
        # turn.
        if _opening_sac_pivot:
            score = max(score, 6000)

        # Rule (user, registro 004 step 53 vs Archaludon ex, WON):
        # ALWAYS play the Supporter (Dawn / Lillie's / Lana's Aid) BEFORE
        # retreating. Retreating first wastes what the Supporter contributes to
        # the rest of the turn (e.g. Dawn searches the Applin -> Dipplin ->
        # Hydrapple ex line, which evolves with Forest THIS same turn, and only
        # afterwards is it worth retreating the Fezandipiti ex and promoting the
        # Hydrapple ex). Playing the Supporter does NOT block the retreat (it is
        # still available afterwards), so it is POSTPONED: its score is lowered
        # below the Supporter's play (>=2400) so the engine chooses the Supporter
        # first and re-evaluates the retreat on the next decision.
        # EXCEPTION: the relief of the suicidal finisher CLOSES the game this
        # turn (user, registro_016 step 184). There is no "rest of the turn" for
        # the Supporter to contribute to, and postponing the retreat is exactly
        # what leaves the agent attacking with the suicidal body and signing the
        # draw.
        if (score > 2000 and not state.supporterPlayed
                and not _suicide_swap_win_promote):
            _rt_supp_first = any(
                hand_counts.get(_sid, 0) >= 1 and _supp_values.get(_sid, 0) > 0
                for _sid in (Dawn, Lillie_Determination, Lanas_Aid))
            if _rt_supp_first:
                score = 2000
        
        # Anti-Cubchoo rule (user, registro_004 step 47/49 vs
        # cornerstone_cubchoo, LOST): the Cubchoo/Beartic deck blocks our
        # active every turn -- Snotted Up (506) and Sheer Cold (507) leave the
        # Defending Pokemon "unable to use attacks" the following turn --
        # forcing us to RETREAT in order to attack with another body. Their
        # attacker is extremely weak (it does not knock us out), but since it
        # forces us to retreat again and again, EVERY retreat that DISCARDS
        # energy (a cost paid with the active's energy, with no free switching
        # card) bleeds the resource that is scarcest against this control.
        # Against THIS deck we remove the voluntary retreat-pivot: if retreating
        # would only change attacker and spend energy, it is better to PASS and
        # keep it. The active is NOT in danger of a KO (Cubchoo hits for 10), so
        # staying costs nothing. Safeguard `not active_ko_likely`: if the active
        # IS going to die (e.g. Beartic's Sheer Cold on a fragile body), the
        # rescue retreat is allowed. The rule is limited to this matchup: against
        # any other deck the retreat-pivot is still correct.
        # EXCEPTION: a retreat that KNOCKS OUT and does not destroy investment
        # (user, registro_036 step 146). The user's two rules coexist like this:
        #
        #  - registro_004 p47 (PASS): the active is an Ogerpon ex with THREE
        #    physical Grass on it. Retreating throws one of those three away: it
        #    destroys energy already invested on the board, which is exactly the
        #    resource the Cubchoo control denies us. Even with a KO behind it, we
        #    pass.
        #  - registro_036 p146 (RETREAT): the active has ZERO energy -- it
        #    neither attacks nor retreats, it is dead weight. The Grass is put
        #    there by us THAT turn (Teal Dance, which also draws) with the sole
        #    purpose of paying the retreat. Nothing accumulated is destroyed: a
        #    card from hand is converted into a prize.
        #
        # Discriminant: the active's PHYSICAL energy <= the retreat cost, that
        # is, no surplus left to lose. Plus `_bdg_retreat_ko` (the same detector
        # as `_attach_enable_retreat_ko`) to require a real KO and not a bare
        # pivot.
        _cc_ret_cost_pre = (RETREAT_COST.get(_active_reloc.id, 1)
                            if _active_reloc is not None else 1)
        _cc_cashes_dead_body = (
            _bdg_retreat_ko
            and _active_reloc is not None
            and _physical_energy(
                len(_active_reloc.energies)) <= _cc_ret_cost_pre)
        # The relief of the suicidal finisher wins the game NOW: saving
        # energy for future turns means nothing if there is no future.
        #
        # Cubchoo <-> immune-wall COLLISION (cornerstone_cubchoo autopsy,
        # jul 2026): `_ex_stuck_promo_ready` -- our active is BLOCKED by the
        # wall (Cornerstone cancels bodies with an Ability; Crustle/Sylveon
        # cancel the ex) and on the bench there is an attacker that DOES hit
        # it -- also exempts. The veto exists so as not to destroy energy
        # invested on the board, but the energy of a body that does ZERO to
        # the opposing active is not invested: it is dead, and retreating is
        # the only way to turn it into damage. Measured over 250 games vs
        # cornerstone_cubchoo: with the wall in front, a Tapu Bulu charged to
        # >=4 on the bench and the retreat LEGAL, we brought Tapu up only
        # 13.7% of the time in the losses on prizes (36% in the wins; vs
        # Crustle -- the same scenario WITHOUT Cubchoo in the deck -- it is
        # 82.6-100%). The active was a Teal Mask Ogerpon ex in 167 of 169 of
        # those menus and the turn closed by ATTACKING for 0 (67 times).
        # `_cubchoo_mute_cashes_prize` (user, registro_007 turn 7 vs
        # crustle_cubchoo_spheal): the muted active is a body that does not attack
        # at all -- Meowth ex, Fezandipiti ex -- so its energy was never attack
        # investment and there is nothing to conserve, while a benched attacker
        # knocks out the opposing active. See the flag in main.py: it is separate
        # from `_cubchoo_lock_stuck` so that it exempts ONLY here.
        if (op_is_cubchoo_deck and score > 0 and not active_ko_likely
                and not _cubchoo_lock_stuck
                and not _cubchoo_mute_cashes_prize
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

        # NEVER END THE TURN WITH THE SACRIFICE STILL AVAILABLE (user,
        # registro_002 step 25 vs Mega Lucario ex, LOST). See
        # `_doomed_sac_deferred` above: the retreat is postponed behind the
        # development plays of the turn, not cancelled. A floor of 1 is all it
        # takes -- ENDING THE TURN scores 0 and every real play scores in the
        # thousands -- so the order of the turn is untouched and only the dead
        # end changes: with a doomed 2-prize ex in front and a 1-prize body on
        # the bench, retreating beats doing nothing.
        #
        # `_doomed_sac_context` is the same reading computed once on the board
        # (main.py), and it is asked here for two reasons: it adds the guard
        # this floor needs -- a turn that can still take a prize
        # (`prizes_today`) is not a dead end -- and it keeps the whole rule
        # switchable from a single place, which is what makes the A/B of the
        # self-play gate measure the change and not half of it.
        if _doomed_sac_deferred and _doomed_sac_context and score <= 0:
            score = 1
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


__all__ = ['score_play']
