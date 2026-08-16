"""Scoring the ABILITY options: the free plays, and their hidden costs.

Abilities cost no card and do not end the turn, so most of them are close to
free value. The decisions that matter here are about ORDER and about the
resources an ability quietly consumes.

THE ABILITIES THIS DECK ACTUALLY DECIDES ABOUT:

  * TEAL DANCE (Ogerpon) -- attach a Grass from hand to ITSELF and draw. The
    most-scored ability in the file, because it competes with the manual
    attachment for the same card in hand: it is free in tempo but it SPENDS
    the Grass. Where a body other than the Ogerpon needs that energy more, the
    dance has to yield.
  * RIPENING CHARGE (Hydrapple ex) -- attach to ANY of ours, which makes it the
    flexible route and the one that should be saved for targets Teal Dance
    cannot reach.
  * GRAND TREE -- a free evolution chain out of the deck. Scored by whether an
    executable plan exists at all, and vetoed when there is none: firing it
    with no target only shuffles the deck.
  * LAST-DITCH CATCH, FLIP THE SCRIPT and the rest -- once-per-turn effects
    whose value is in what they fetch.

TWO THINGS TO KNOW BEFORE EDITING:

  * ORDER IS THE WHOLE GAME with the charging abilities. Attaching before
    dancing, or dancing onto the wrong body, wastes the turn's only energy --
    the tie between "the attachment" and "the ability" over the same body has
    been measured more than once, and the current ordering is the measured one.
  * AN ABILITY THAT ENABLES A KNOCKOUT IS NOT DEVELOPMENT. The Teal Dance
    block computes damage BEFORE and AFTER the dance and treats "it becomes
    lethal" as a different kind of play. Note it prices the attack through
    `_our_effective_damage` rather than raw damage, so resistance and the
    stadium are included -- the case that taught this was a Duraludon resisting
    Grass, where the dance was exactly what closed the 30-point gap.

Extracted VERBATIM from the `agent()` chain: it unpacks from the context only
the fields it reads and returns only the ones it reassigns.
"""

from cg.api import AreaType, Pokemon
from ptcg.calc.card import get_card
from ptcg.calc.damage import _our_effective_damage, _wall_mutes_our_ex
from ptcg.calc.energy import _grass_attach_unit, _grass_mult, _ogerpon_base_phys_cap, _physical_energy
from ptcg.cards.groups import GT_SCORE_FULL_CHAIN, GT_SCORE_STAGE1_ONLY
from ptcg.cards.ids import Basic_Grass_Energy, Dipplin, MEGANIUM_IS_OWED_THE_LAST_GRASS, FEZ_DRAW_ABILITY_SCORE, Fezandipiti_ex, Grand_Tree, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Pinsir, RETREAT_COST, RIPEN_HEAL_ABILITY_SCORE, RIPEN_HEAL_EX_ABILITY_SCORE, SCORE_CHARGE_ACTIVE_ATTACK, SCORE_CHARGE_ACTIVE_FINISHER, SCORE_CHARGE_LETHAL_FLOOR, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Unfair_Stamp
from ptcg.state.agent_state import AGENT_STATE


def score_play(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
    _order_veto = tc._order_veto
    _ability_unlock_retreat_attack = tc._ability_unlock_retreat_attack
    _ability_unlock_retreat_ko = tc._ability_unlock_retreat_ko
    _active_already_kos = tc._active_already_kos
    _active_hydra_cannot_ko = tc._active_hydra_cannot_ko
    _active_hydra_ready = tc._active_hydra_ready
    _active_needs_energy = tc._active_needs_energy
    _attach_enable_retreat_attack = tc._attach_enable_retreat_attack
    _attach_enable_retreat_ko = tc._attach_enable_retreat_ko
    _attach_reaches_no_cost = tc._attach_reaches_no_cost
    _bench_attacker_ready = tc._bench_attacker_ready
    _bench_has_chargeable = tc._bench_has_chargeable
    _bp = tc._bp
    _ctm_wall_in_the_way = tc._ctm_wall_in_the_way
    _charge_active_missing = tc._charge_active_missing
    _charge_active_enables_attack = tc._charge_active_enables_attack
    _charge_active_finishes = tc._charge_active_finishes
    _enough_after_priorities = tc._enough_after_priorities
    _enough_for_both = tc._enough_for_both
    _extra_energy_enables_ko = tc._extra_energy_enables_ko
    _grass_anywhere_enables_syrup_ko = tc._grass_anywhere_enables_syrup_ko
    _gt_plan = tc._gt_plan
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _hydra_fragile_pivot = tc._hydra_fragile_pivot
    _hydrapple_bench_needs_energy = tc._hydrapple_bench_needs_energy
    _lillie_blocks_fez_ability = tc._lillie_blocks_fez_ability
    _ogerpon_lethal_focus_serial = tc._ogerpon_lethal_focus_serial
    _festival_wave_needs_the_grass = tc._festival_wave_needs_the_grass
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
                # GRAND TREE ABILITY (shared stadium, id 1249):
                # a Basic -> Stage 1 -> Stage 2 chain pulled out of the deck,
                # free and once per turn. `_gt_plan` already brings the best
                # target (see the `_gt_*` block); here only HOW MUCH the play
                # is worth is decided. If there is no executable plan -- first
                # turn, no eligible Basic, chain exhausted in the deck -- it is
                # vetoed: activating it without a target only shuffles the deck.
                if _gt_plan is None:
                    score = SCORE_VETO
                elif _gt_plan.stage2_id:
                    score = GT_SCORE_FULL_CHAIN
                else:
                    # A chain that stops at Stage 1 (Stage 2 exhausted or advised
                    # against by the anti-ex matchup). It is still free
                    # development, but below the complete chain and below evolving
                    # into Meganium from hand.
                    score = GT_SCORE_STAGE1_ONLY
            elif card.id == Teal_Mask_Ogerpon_ex:
        
                _ogerpon_energy = len(card.energies) if isinstance(card, Pokemon) else 0
        
                # THE LAST GRASS BELONGS TO THE BODY THAT CAN STILL HIT THE WALL.
                # Teal Dance attaches from HAND, so with a single Grass left it is
                # not a free charge: it is that Grass spent on a body the wall has
                # already switched off, and the deck's real attacker in the matchup
                # goes without. Demoted (7500), not vetoed -- the draw is still
                # worth something once nobody else needs the card.
                #
                # Extended to Cornerstone (user, ago 2026): Cornerstone Stance
                # blanks this very Ogerpon ex (Teal Dance is an Ability), so the
                # argument is identical -- and the list of bodies still owed the
                # Grass is SHORTER there, not longer. Dipplin also carries an
                # Ability (Festival Lead), so against Cornerstone only Tapu Bulu is
                # asking, which is exactly why the reservation matters more.
                # AND NEUTRALIZATION ZONE IS THE THIRD WALL (user,
                # `records/registro_010_pasos_070_hasta_080` step 70, vs a
                # Mesprit/Uxie/Azelf deck). Their stadium prevents all damage
                # done to bodies WITHOUT a Rule Box by attacks from our ex, and
                # their whole board was Rule-Box-less 70 HP basics: the active
                # Hydrapple ex and both Ogerpon ex were mute, and the only body
                # of ours that could still knock anything out was a Meganium on
                # the bench at ZERO energy. The turn's only Grass went to a
                # benched Ogerpon via Teal Dance (31300, the `_active_hydra_ready`
                # rung: "the active covers Syrup Storm's cost, so the surplus
                # goes to the bench" -- true of the cost and false of the board).
                #
                # It is the same sentence as the two walls above, so it is the
                # same rung: the last Grass belongs to the body that can still
                # hit. This list and Crustle's are the WIDE ones, because both
                # walls filter by something Meganium does not carry -- a Rule
                # Box here, a Rule Box there -- so Meganium still hits and is
                # owed the Grass. Only Cornerstone's list drops it, and that is
                # not an oversight: Cornerstone Stance blanks the bodies WITH an
                # Ability, and Wild Growth is one.
                #
                # MEGANIUM WAS MISSING FROM THE CRUSTLE LIST (user,
                # `records/registro_014_pasos_090_hasta_096.json` step 92, turn
                # 14, LOST). The tuple read `(Tapu_Bulu, Dipplin, Pinsir)` and
                # the note above justified the absence with "against Crustle and
                # Cornerstone it is the doubler" -- true of Cornerstone, false of
                # Crustle. Crustle's Mysterious Rock Inn switches off our ex, and
                # Meganium is not one: Solar Beam does its 140 into the wall like
                # any other non-ex of ours. On that board the omission cost the
                # whole turn: ONE Grass in hand (a Night Stretcher had just
                # recovered it), a Meganium on our bench at 0 of 4, two Crustle
                # waiting on theirs -- one already at three energies -- and the
                # only body of ours that could ever answer them went without,
                # because the reservation did not name it and the benched Teal
                # Mask Ogerpon ex's dance took the card at 31500 against the
                # attachment's 27000. A SECOND ex charged against the wall that
                # blanks ex, while the one attacker sat at zero.
                #
                # AND THE FOURTH WALL IS A CARD IN THEIR HAND (user, episode
                # 93163758 vs Comfey/Chandelure, turns 13-19, LOST at one
                # prize). Acerola's Mischief says the same sentence as the
                # stadium -- our ex do zero to the body it protects, effects
                # included -- for one turn and on one body, and it leaves
                # nothing on the board to read it off (`_shield_mutes_our_ex`).
                # The creditor list is the stadium's, unchanged, because the
                # question the reservation asks is the same one: which of our
                # bodies can still knock something out today.
                #
                # `_wall_mutes_our_ex` asks the CURRENT opposing active and not
                # the matchup: the stadium is harmless the moment they promote
                # an ex, the shield the moment its turn is over or the body it
                # was pinned on leaves the front -- and then this reservation
                # must stop being owed.
                _wall_atk_needs_grass = False
                _cng_wall_ids = None
                # Cornerstone only: the Grass must FINISH a cost, not merely
                # advance one (the measurement is quoted below).
                _cng_needs_completion = False
                if AGENT_STATE.op_is_crustle_deck:
                    # ...AND MEGANIUM ONLY WHILE THE WALL IS ACTUALLY IN THE WAY
                    # (`_ctm_wall_in_the_way`, main.py -- the rules-oracle split
                    # that pinned it is written out there). The other three
                    # creditors keep the archetype reading they were measured
                    # under; what the oracle graded is the name that was added.
                    _cng_wall_ids = ((Tapu_Bulu, Dipplin, Pinsir, Meganium)
                                     if (MEGANIUM_IS_OWED_THE_LAST_GRASS
                                         and _ctm_wall_in_the_way)
                                     else (Tapu_Bulu, Dipplin, Pinsir))
                elif (AGENT_STATE.op_is_cornerstone_deck
                        or op_has_ability_immune_active):
                    _cng_wall_ids = (Tapu_Bulu, Pinsir)
                    _cng_needs_completion = True
                elif _wall_mutes_our_ex(
                        op_state.active[0] if op_state.active else None,
                        neutralization_zone_active):
                    _cng_wall_ids = (Tapu_Bulu, Dipplin, Pinsir, Meganium)
                if _cng_wall_ids and hand_counts.get(Basic_Grass_Energy, 0) == 1:
                    for _cng in (list(my_state.active or []) + list(my_state.bench or [])):
                        if _cng is None or _cng.id not in _cng_wall_ids:
                            continue
                        _cng_e = len(_cng.energies)
                        _cng_req = (4 if _cng.id in (Tapu_Bulu, Meganium)
                                    else 1 if _cng.id == Dipplin else 2)
                        if _cng_e >= _cng_req:
                            continue
                        if (_cng_needs_completion
                                and _cng_e + _grass_attach_unit() < _cng_req):
                            # AND THE GRASS HAS TO ACTUALLY FINISH SOMETHING.
                            # Measured (n=4000 vs otro_cornerstone_mask_ogerpon_ex_1,
                            # ago 2026): the Cornerstone half of this reservation
                            # alone scored -0.9 against the branch's other three
                            # changes at +0.1/+0.4/-0.2, and the reason is a real
                            # difference between the two walls rather than variance.
                            # Against Crustle the creditors are cheap -- a Dipplin
                            # wants ONE energy, a Pinsir two -- so the single Grass
                            # in hand almost always completes a cost. Against
                            # Cornerstone the only creditor left is Tapu Bulu at
                            # FOUR, and "Tapu is short" is not the same question as
                            # "this card makes Tapu ready": from zero or one energy
                            # the attachment finishes nothing, and refusing the
                            # dance there pays a whole card -- the draw that finds
                            # the next Grass and the Meganium line -- for a body
                            # that still cannot attack this turn.
                            #
                            # So the reservation is asked ONE step later: reserve
                            # the Grass when it puts the attacker AT its cost, not
                            # merely when the attacker is under it. The Crustle
                            # list keeps its old, looser reading, which is the one
                            # its own measurements were taken against.
                            continue
                        _wall_atk_needs_grass = True
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
                    # Myriad Leaf Shower = 30 + 30 for EACH energy attached to
                    # BOTH actives (ours PLUS the opposing active's); hence the
                    # `_td_eff_now + _td_opp_e` below. (The previous comment said
                    # "own energy only": that was an error already corrected in
                    # `_attacker_base_damage`, the code always added both.) It goes
                    # through _our_effective_damage to apply weakness AND RESISTANCE
                    # (user, registro_012 step 93: Duraludon resists -30 against
                    # Grass, so Teal Dance enables the KO by going from 4 to >=5
                    # effective energies). `card` is the Teal Mask Ogerpon ex itself.
                    _td_opp_e = len(getattr(_td_op_act, 'energies', []) or [])
                    _td_base_now = (30 + 30 * (_td_eff_now + _td_opp_e)
                                    if _td_eff_now >= 3 else 0)
                    _td_base_after = (30 + 30 * (_td_eff_after + _td_opp_e)
                                      if _td_eff_after >= 3 else 0)
                    _td_dmg_now = _our_effective_damage(
                        card, _td_op_act, _td_base_now,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    _td_dmg_after = _our_effective_damage(
                        card, _td_op_act, _td_base_after,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    _td_ko_now = (_td_dmg_now > 0 and _td_dmg_now >= _td_op_hp)
                    _td_ko_after = (_td_dmg_after > 0 and _td_dmg_after >= _td_op_hp)
                    _td_ko_on_active = (_td_ko_after and not _td_ko_now)
                # Teal Dance on the Ogerpon that is the FOCUS of a lethal charge
                # (bench or active): it is used to bring it closer to the 3
                # energies of the weakness KO (user, registro_006 step 62). Unlike
                # `_td_ko_on_active` (the ACTIVE only), this covers a BENCHED
                # Ogerpon that is promoted afterwards. It requires that it does
                # not reach 3 yet (do not overcharge).
                _td_is_lethal_focus = (
                    _ogerpon_lethal_focus_serial is not None
                    and isinstance(card, Pokemon)
                    and getattr(card, 'serial', None) == _ogerpon_lethal_focus_serial
                    and _ogerpon_energy < 3)
                if hand_counts[Basic_Grass_Energy] < 1:
                    score = SCORE_VETO
                elif _charge_active_finishes and o.area == AreaType.ACTIVE:
                    # The ACTIVE that reaches its LETHAL attack with this charge is
                    # this very Ogerpon: its Teal Dance attaches the Grass AND
                    # DRAWS, so it inherits the finisher band.
                    score = SCORE_CHARGE_ACTIVE_FINISHER
                elif _charge_active_enables_attack and o.area == AreaType.ACTIVE:
                    # Mirror without a KO: the Grass lets the active Ogerpon attack
                    # (and draws) on a turn that would otherwise be sterile.
                    score = SCORE_CHARGE_ACTIVE_ATTACK
                elif ((_charge_active_finishes or _charge_active_enables_attack)
                        and o.area != AreaType.ACTIVE
                        and hand_counts[Basic_Grass_Energy]
                            <= _charge_active_missing):
                    # Teal Dance only attaches to ITSELF: on a BENCHED Ogerpon it
                    # would eat the Grass the ACTIVE needs to finish today. It is
                    # vetoed while the hand cannot pay for both (user, registro_006
                    # step 67 vs Marnie's Grimmsnarl).
                    score = SCORE_VETO
                elif ((_attach_enable_retreat_ko
                       or _ability_unlock_retreat_ko)
                        and o.area == AreaType.ACTIVE):
                    # TEAL DANCE that enables the retreat towards a LETHAL benched
                    # attacker (user, registro_036 step 146 vs Cubchoo).
                    # `_attach_enable_retreat_ko` already detects the whole line
                    # -- an active with no energy to retreat + a benched attacker
                    # that KNOCKS OUT -- and gives 41000 to the MANUAL attachment on
                    # the active. But if that active is a Teal Mask Ogerpon ex with
                    # Teal Dance still alive, the manual attachment is vetoed by the
                    # "Teal Dance before the attachment" precedence and the whole
                    # line was lost: the agent ended up charging some benched body
                    # (there, a Tapu Bulu at 10 HP) and the KO never happened.
                    #
                    # The precedence is correct -- Teal Dance attaches the same
                    # Grass AND ALSO DRAWS -- what was missing was for Teal Dance
                    # itself to inherit the priority of that lethal line. It goes
                    # BEFORE the per-matchup energy caps (Cubchoo, Alakazam/Hop's,
                    # Crustle): this is not overcharging, it is the only way to pay
                    # the retreat cost.
                    #
                    # `_teal_dance_ko_pivot`/`_teal_wall_pivot` (31600) only cover
                    # the case of the immune WALL with a NON-ex attacker; here the
                    # opposing active is attackable and the lethal benched body is
                    # another ex, so neither of them fired.
                    score = 41000
                elif ((_attach_enable_retreat_attack
                       or _ability_unlock_retreat_attack)
                        and o.area == AreaType.ACTIVE):
                    # Non-lethal mirror of the previous case (log 88162794 turns
                    # 11/13): if the active that needs the energy to retreat is
                    # this Ogerpon, its own Teal Dance pays the cost AND DRAWS, so
                    # it inherits the pivot's priority -- just above the manual
                    # attachment (31200) so the draw is not lost, and below the KO
                    # lines (31500).
                    score = 31250
                elif _td_ko_on_active or _td_is_lethal_focus:
        
                    score = 31500
                elif _grass_anywhere_enables_syrup_ko:
                    # Teal Dance as an ACCELERATOR of the ACTIVE Hydrapple ex's
                    # Syrup Storm (user, registro_006 step 68 vs Mega Abomasnow
                    # ex, LOST): the Grass adds to the count of ALL our Pokemon,
                    # so this Ogerpon does not need to gain anything from it -- in
                    # fact here both benched Ogerpon were already at 4 energies
                    # and the `_ogerpon_energy >= 3` branch VETOED them for
                    # "overcharging", leaving dead in hand the Grass that raised
                    # the attack from 330 to 390 against 350 HP. It goes BEFORE
                    # the per-matchup caps (Cubchoo / Alakazam / Hop's /
                    # Crustle) for the same reason as `_td_ko_on_active`: this is
                    # not overcharging, it is finishing.
                    #
                    # Tie-break between several Ogerpon: the Grass enables the
                    # same KO wherever it lands, so the one that does NOT reach
                    # its own attack yet (< 3 effective) is preferred -- it also
                    # ends up ready as a second attacker -- over the one that was
                    # already charged (registro_008 step 94).
                    score = 31500 if _ogerpon_energy < 3 else 31490
                elif (op_is_cubchoo_deck and
                        _physical_energy(_ogerpon_energy)
                        >= (2 if AGENT_STATE.meganium_in_play else 4)):
                    # Cubchoo matchup (user): do not overcharge the Ogerpon with
                    # Teal Dance beyond the PHYSICAL cap (2 with Meganium / 4
                    # without). len(energies) comes DOUBLED by Wild Growth with
                    # Meganium, which is why we convert to physical cards before
                    # comparing. No more energy is needed to attack.
                    # Exception: if it enables a KO (above, _td_ko_on_active).
                    score = SCORE_VETO
                elif ((op_is_alakazam_deck or op_is_hop_deck)
                        and _physical_energy(_ogerpon_energy)
                        >= _ogerpon_base_phys_cap(AGENT_STATE.meganium_in_play,
                                                  op_is_hop_deck)):
                    # Rule (user, vs Alakazam and vs Hop's): energy cap for Teal
                    # Mask Ogerpon ex via Teal Dance. PHYSICAL base = 2 with
                    # Meganium (Wild Growth doubles every Grass), 3 without
                    # Meganium vs Hop's and 4 without Meganium vs Alakazam. On the
                    # BENCH it is HARD; on the ACTIVE the extra energy is only
                    # allowed if it ENABLES the KO on the opposing active, a case
                    # already resolved above by _td_ko_on_active (31500) -- the
                    # ONLY reason to go past the cap with Teal Dance. Outside that
                    # exception we do not overcharge: we save the energy.
                    # len(energies) is EFFECTIVE => it is converted to physical cards.
                    score = SCORE_VETO
                elif (_teal_wall_pivot and o.area == AreaType.ACTIVE
                        and _physical_energy(_ogerpon_energy)
                            < RETREAT_COST.get(Teal_Mask_Ogerpon_ex, 1)):
                    # A doomed active (Teal Mask Ogerpon ex) that cannot attack +
                    # Hydrapple ex (the wall) on the bench: use Teal Dance on the
                    # ACTIVE (it attaches Grass + DRAWS 1) to enable its retreat
                    # (cost 1) and then bring up the stronger body. It must BEAT
                    # the manual attachment (~31200) so the draw is used and the
                    # turn's energy is not wasted.
                    #
                    # ...WHILE THE RETREAT IS STILL UNPAID. The band buys one
                    # thing, the retreat cost of a body that is leaving the
                    # front spot, and once the body already pays it the Grass
                    # is only riding to the discard with the retreat (user,
                    # `records/registro_006_pasos_085_hasta_102.json` turn 6:
                    # active Ogerpon ex with one Grass on it, benched Hydrapple
                    # ex one Grass short of Syrup Storm -- Teal Dance took the
                    # 31600 and the wall came up MUTE). Same reading as the
                    # `_attach_buys_retreat` guard in `_energy_score_base`: an
                    # attachment justified by a fee is worth the fee only while
                    # the fee is owed.
                    score = 31600
                elif _teal_dance_ko_pivot and o.area == AreaType.ACTIVE:
                    # Teal Dance -> retreat -> promote a lethal attacker pivot
                    # (user, log 85802744 turn 16): active Teal Mask Ogerpon ex
                    # blocked by the Crustle wall and unable to retreat yet, with
                    # a non-ex attacker READY on the bench (Tapu Bulu, 220 damage)
                    # that knocks the wall out. Teal Dance on the active attaches
                    # the Grass (+DRAWS) and enables the cost-1 retreat to bring
                    # up Tapu and knock out on the next step. It must BEAT the
                    # manual attachment to Dipplin (~31000).
                    score = 31600
                elif (((AGENT_STATE.op_is_crustle_deck and not op_kang_ko_target)
                        or AGENT_STATE.op_is_cornerstone_deck
                        or op_has_ability_immune_active)
                        and _physical_energy(_ogerpon_energy) >= 2):
                    # Rule (user, vs Crustle, log 86583376 step 84): a Teal Mask
                    # Ogerpon ex may not hold more than TWO PHYSICAL energies
                    # charged via Teal Dance. Against the Crustle wall (which makes
                    # our ex useless) Ogerpon does not attack the wall, so we save
                    # energy and do not overcharge it. The ONLY exception (an
                    # ACTIVE Ogerpon whose 3rd energy enables the KO on the opposing
                    # active) was already resolved above with _td_ko_on_active
                    # (31500). The op_kang_ko_target bypass is also kept (a KO on
                    # Mega Kangaskhan ex with Hydrapple ex, where the extra energy
                    # raises Syrup Storm's damage). len(energies) is EFFECTIVE (Wild
                    # Growth doubles) => it is converted to physical cards with
                    # _physical_energy.
                    #
                    # EXTENSION to Cornerstone (autopsy v2.1 p025 t20, jul 2026
                    # cycle; same pattern by which d801d57 widened the anti-Cubchoo
                    # whitelist): Cornerstone Stance cancels the damage of our
                    # Pokemon WITH an ability, so this Ogerpon does not attack there
                    # either -- and the agent piled 3 physical energies on it via
                    # Teal Dance (a dead body with 6 effective) while Tapu Bulu, THE
                    # attacker of the matchup, starved at 1 physical with no energy
                    # in hand. The cap of 2 redirects the surplus: the energy_score
                    # rule "cornerstone -> Tapu +22000" already existed and now the
                    # energy reaches it. `op_has_ability_immune_active` also covers
                    # any positional anti-ability wall (Sylveon...). The
                    # _td_ko_on_active exception (above) still covers the attackable
                    # opposing active of the mixed deck (Cubchoo/Beartic in front).
                    score = SCORE_VETO
                elif _wall_atk_needs_grass:
        
                    score = 7500
                elif _reserve_energy_for_hydra_evolve and o.area != AreaType.ACTIVE:

                    score = 7500
                elif (_festival_wave_needs_the_grass
                        and o.area != AreaType.ACTIVE):
                    # THE GRASS THE WAVE IS COUNTING IS NOT SURPLUS (user,
                    # registro_010 step 103 vs Festival Lead). Under Festival
                    # Grounds our Dipplin throws Do the Wave twice, and
                    # `_festival_lead_pays_us_now` says that wave is already
                    # lethal on their Active -- but the Dipplin it read is
                    # sitting on zero energy and the card that charges it is the
                    # one in hand.
                    #
                    # The rung this stands in front of (`_active_already_kos`
                    # and not the Active spot, 31050) is a DEVELOPMENT charge:
                    # our active can finish it anyway, so the Grass is banked on
                    # a benched Ogerpon for tomorrow. Banking it is right when
                    # the alternative is nothing; here the alternative is the
                    # second prize the stadium hands us today, and the record
                    # measured what banking it costs -- the Dipplin went
                    # uncharged, and the following action evolved it, because
                    # the detector that had vetoed exactly that evolution had
                    # gone False with the Grass.
                    #
                    # 7500, the same band as the reserve above it, so it sits
                    # BELOW the manual attachment (~28000) that puts the card on
                    # the body which cashes it. It does not veto the dance: with
                    # a second Grass in hand `_festival_wave_needs_the_grass` is
                    # still true and this pays for the wave first -- the dance is
                    # a charge, and a charge waits its turn behind the one that
                    # is the attack ([[lo-que-la-mano-paga-va-antes-que-lo-que-gasta-la-mano]]).
                    # The ACTIVE spot is exempt for the same reason
                    # `_reserve_energy_for_hydra_evolve` exempts it: a dance on
                    # the body in front may be paying the retreat fee this very
                    # route needs, and the pivots that buy it (31600) rule above.
                    score = 7500
                elif _ogerpon_energy >= 3:
        
                    if (o.area == AreaType.ACTIVE
                            and (_win_via_boss_gust or _gust_2prize_via_boss)):
                        # Winning Myriad combo (user, registro_012 step 227
                        # vs Iono, LOST): this turn there is a finisher via
                        # Boss's Orders (gusting from the opposing bench a
                        # target we KNOCK OUT to take the prizes we are
                        # missing) and the attacker is this active Ogerpon.
                        # Without this branch, the veto below ("it already has
                        # >=3 energies and already knocks out the opposing
                        # active, do not spend more Grass") killed the ability,
                        # and since the manual attachment to the active is in
                        # turn vetoed by Teal Dance's PRECEDENCE, the energy
                        # ended up on a benched body and the winning line was
                        # lost. The gust target is not the opposing active: the
                        # extra energy is precisely what raises Myriad up to
                        # its HP. Scored above the other Teal Dance branches
                        # (31600) and >= 29000, to keep the ENERGY tier and be
                        # played BEFORE the Boss's PLAY (tier 0).
                        score = 31700
                    elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, _ogerpon_energy):
                        score = 29000
                    elif _active_already_kos and o.area != AreaType.ACTIVE:
        
                        score = 31050
                    elif (o.area == AreaType.ACTIVE and _bench_attacker_ready
                            and not _active_already_kos):

                        score = 31050
                    elif _attach_reaches_no_cost:
                        # NOTHING ELSE ON THE FIELD CAN CASH THIS GRASS (user,
                        # registro_006 step 55 vs a Dragapult ex deck, LOST --
                        # the board is drawn out in `_attach_reaches_no_cost`,
                        # main.py). The veto below is "it already covers its
                        # cost, save the energy", and saving it is a real
                        # answer only while there is somewhere better for it to
                        # go. On that board there was not: the only other
                        # target was an active Tapu Bulu at 0 of 4 that could
                        # reach neither its attack nor its own retreat, so the
                        # Grass was going to sit on a body that never paid it
                        # out. "Overcharging" the one that IS ready costs
                        # nothing and buys two things -- Myriad Leaf Shower
                        # scales with the energy on it, and the dance DRAWS.
                        #
                        # It is the LAST rung of the block on purpose: every
                        # per-matchup cap (Cubchoo, Alakazam/Hop's, Crustle,
                        # Cornerstone) is asked far above and still rules. This
                        # only speaks where no cap said no and the alternative
                        # was a dead attachment.
                        #
                        # 7500 is the DEGRADED Teal Dance band the file already
                        # uses (`_wall_atk_needs_grass`,
                        # `_reserve_energy_for_hydra_evolve`): free value, below
                        # anything that plays for today, and just above the 7000
                        # the attachment is capped to when it yields -- which is
                        # how the two are made to decide by score inside tier 0.
                        score = 7500
                    else:
                        score = SCORE_VETO
                elif _active_hydra_ready:
        
                    score = 31300
                elif (_active_needs_energy and not _enough_for_both
                        and AGENT_STATE.plan.attacker < 1
                        # A RESERVATION CANNOT VETO THE BODY IT IS RESERVING FOR
                        # (user, registro_004 step 39 vs Marnie's Grimmsnarl ex).
                        # The band below is "the ACTIVE needs the Grass and the
                        # hand holds only one, so do not spend it dancing" -- and
                        # it was being applied to the ACTIVE's OWN dance. Teal
                        # Dance attaches to ITSELF: on the active it IS the
                        # reservation being honoured, and with a card drawn on
                        # top. The manual attachment to that same active is
                        # vetoed by the Teal Dance precedence, so between the two
                        # of them the Grass had no way of reaching the body every
                        # rule agreed it belonged to -- it sat in hand at 7500,
                        # under the tier-0 ceiling, until an Ultra Ball discarded
                        # it for fodder.
                        #
                        # The guard is the one the Ripening Charge sibling below
                        # has carried all along (`o.area != AreaType.ACTIVE`), and
                        # it SUBSUMES the exception that used to hang here: an
                        # opening-turn carve-out for `o.area == ACTIVE`, which is
                        # this same sentence gated on turn 1. See
                        # `la-regla-general-va-antes-que-su-caso-especial`: when a
                        # rule is generalised, the general one takes the seat.
                        #
                        # The BENCH keeps the band, and that half is not
                        # cosmetic: a benched Ogerpon dancing really would eat
                        # the Grass the active is waiting for.
                        and o.area != AreaType.ACTIVE):
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
                # Guard (user, log 85848966 step 76, WON vs Crustle): do NOT
                # activate Ripening Charge if the extra Grass has no useful
                # destination. Ripening Charge (once activated) FORCES an
                # attachment to some Pokemon; if the active is a Tapu Bulu that
                # is ALREADY charged (>=4 effective) and there is no benched
                # attacker that needs energy (Tapu<4eff, Dipplin with no energy
                # or Meganium<4eff), energy_score (ATTACH_FROM) returns -1 for
                # ALL options -> the tie-break picks the 1st (the ACTIVE) and
                # overcharges the already-ready Tapu, wasting a Grass card from
                # hand (which with Meganium is useful for retreats / next turn).
                # It mirrors the energy_score override (~L4326). Since Hydrapple
                # ex is an ex and does NOT damage Crustle, no lethal Syrup Storm
                # is lost by not activating it.
                _ripen_wasted_vs_crustle = False
                if AGENT_STATE.op_is_crustle_deck:
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
                elif _charge_active_finishes:
                    # Ripening Charge attaches to ANY of our Pokemon: it is the
                    # charging route that completes the ACTIVE's attack cost when
                    # the manual attachment is not enough (or is already spent).
                    # The target -- the ACTIVE -- is fixed by energy_score /
                    # ATTACH_FROM with the same band.
                    score = SCORE_CHARGE_ACTIVE_FINISHER
                elif _charge_active_enables_attack:
                    # Mirror without a KO: without this charge the active does not
                    # attack and the turn closes blank.
                    score = SCORE_CHARGE_ACTIVE_ATTACK
                elif _ripen_retreat_ko_pivot and o.area == AreaType.ACTIVE:
                    # Ripening -> retreat -> promote a lethal Tapu pivot vs
                    # Crustle (user, log 86028607 turn 22): active Hydrapple
                    # ex blocked by the wall with a Tapu on the bench ALREADY
                    # READY (220 damage) that knocks Crustle out. Activate
                    # Ripening Charge to attach a Grass to the Hydrapple ITSELF
                    # and reach its (effective) retreat cost, enabling it to
                    # retreat and bring up Tapu to finish. It must BEAT Teal
                    # Dance / normal attachments; the target (the active
                    # Hydrapple) is fixed in energy_score (ATTACH_FROM).
                    score = 31600
                elif _ripen_bench_tapu_ko_pivot and o.area == AreaType.ACTIVE:
                    # Ripening -> charge the benched Tapu to lethal ->
                    # retreat Hydrapple -> promote Tapu -> knock out the wall
                    # (user, log 86182112 step 82): active Hydrapple ex
                    # blocked by the Crustle wall and ALREADY able to retreat,
                    # with a benched Tapu at 2 effective that with 1 more
                    # Grass reaches 4 (Wood Hammer 220, lethal). Activate
                    # Ripening Charge to attach the 2nd Grass to Tapu (target
                    # fixed in energy_score / ATTACH_FROM, +20000) instead of
                    # wasting the attachment on Teal Dance over Ogerpon. See
                    # _ripen_bench_tapu_ko_pivot (~L4395).
                    score = 31600
                elif _ripen_wasted_vs_crustle:
                    score = SCORE_VETO
                elif _hydra_fragile_pivot and o.area == AreaType.ACTIVE:
                    # THE WOUNDED TWIN PAYS ITS RETREAT WITH THE FREE ROUTE, not
                    # with the turn's manual attachment (user, registro_008 step
                    # 105 vs Team Rocket, LOST). `_hydra_fragile_pivot` is the
                    # detector of the whole line: an active Hydrapple ex too
                    # damaged to stay in front, a healthy twin on the bench that
                    # takes the SAME knockout, and the retreat one Grass away
                    # from being payable. `energy_score` already prices the
                    # ACTIVE as that Grass's target at 41000, and with nothing
                    # of the same size on the ability the manual attachment won
                    # the tier and did the job -- same energy on the field,
                    # minus the free attachment AND minus the 30 points
                    # Ripening Charge heals on the way. On that board the active
                    # went from 150 to 180 for free, which is exactly the kind
                    # of margin the pivot exists to protect.
                    #
                    # Same band as `_ability_unlock_retreat_ko` below -- the
                    # same line with the reply read from their hand instead of
                    # from the wounded body itself -- and one notch ABOVE the
                    # floor, which is what the manual attachment scores for this
                    # very target. On a tie the play order falls back to the
                    # menu index, and the menu happens to list the attachment
                    # first; the notch says out loud what the tie was deciding
                    # by accident, and says it the right way round. Same device
                    # as `_ripen_retreat_ko_pivot` at 31600 over Teal Dance's
                    # 31500, one band up.
                    score = SCORE_CHARGE_LETHAL_FLOOR + 100
                elif _ability_unlock_retreat_ko:
                    # Ripening Charge that UNLOCKS THE RETREAT towards a
                    # LETHAL benched attacker (user, registro_014 step 137 vs
                    # Alakazam). Exact mirror of the Teal Dance branch of the
                    # same name: `_ability_unlock_retreat_ko` detects the whole
                    # line (an active with no energy to retreat + a benched
                    # body that KNOCKS OUT) and, unlike the manual attachment,
                    # is still alive with `energyAttached` already spent
                    # because the ability attaches separately. Same lethal band
                    # (41000): above any development charge. The target (the
                    # ACTIVE) is fixed in energy_score / ATTACH_FROM.
                    score = 41000
                elif _ability_unlock_retreat_attack:
                    # Non-lethal mirror: the benched attacker only does CHIP
                    # damage, but the active neither attacks nor retreats, so
                    # the whole turn depends on this Grass. Band 31250, the
                    # same one Teal Dance uses for this case.
                    score = 31250
                elif _hydra_energy >= 2:
                    if _extra_energy_enables_ko(Hydrapple_ex, _hydra_energy):
                        score = 29000
                    elif (o.area == AreaType.ACTIVE and _active_hydra_cannot_ko
                            and _bench_has_chargeable):
        
                        score = 30000
                    elif _tapu_future_charge:
                        # The active already secures the KO: we use Ripening
                        # Charge (which attaches to any Pokemon) to put a 2nd
                        # energy on the benched Tapu Bulu and make it ready
                        # (2 physical = 4 effective with Meganium). The target
                        # Tapu Bulu is chosen in energy_score (ATTACH_FROM).
                        score = 30000
                    elif _ripen_heal_serial is not None:
                        # Ripening Charge for its HEALING (user, registro_008
                        # step 122 vs Marnie's Grimmsnarl ex, LOST): the
                        # Hydrapple already reaches its attack, so the branch
                        # below VETOED the ability and the last Grass in hand
                        # went through the MANUAL attachment (14000) -- the same
                        # energy on the field but WITHOUT the 30 points of
                        # healing. With the benched Dipplin at 20/80 and Shadow
                        # Bullet putting 30 automatic damage in every turn,
                        # those 30 are the difference between keeping the body
                        # and giving away a prize. The target is fixed in
                        # ATTACH_FROM.
                        #
                        # If the body that leaves the window is an ex, that is
                        # TWO prizes and the healing also beats Teal Dance
                        # (31500): drawing one card is not worth two prizes
                        # (user, game 2 turn 10 -- the agent chose Teal Dance
                        # on the benched Ogerpon ex at 80 HP, which died that
                        # same turn with 5 Grass on it).
                        score = (RIPEN_HEAL_EX_ABILITY_SCORE if _ripen_heal_ex
                                 else RIPEN_HEAL_ABILITY_SCORE)
                    elif _ripen_bench_ready_pivot:
                        # SECOND ATTACKER with the ability (user,
                        # registro_014 step 137 vs Alakazam): the Hydrapple
                        # already reaches its attack, so every branch above only
                        # looks at whether the Grass is useful TO IT and the
                        # ability was VETOED -- the Grass ended up as fodder for
                        # the cost of an Ultra Ball. But Ripening Charge attaches
                        # to ANY of our Pokemon: if with it a REAL benched
                        # attacker goes from "not enough" to READY, that is one
                        # more body attacking next turn (or this very turn, if
                        # the active retreats) for a card that had no other
                        # destination. Band 30000, that of the other bench
                        # charges by ability (`_tapu_future_charge`).
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
                # Correct order Unfair Stamp -> Flip the Script: while we
                # have Unfair Stamp playable this turn (we were knocked out
                # last turn and it is still in hand), Unfair Stamp is played
                # first and the Fezandipiti ability AFTERWARDS. That way the
                # Stamp does not shuffle back the 3 cards the ability draws;
                # we end with 5 (Stamp) + 3 (ability) = 8 cards. Unfair Stamp
                # is an Item: once played it leaves the hand and
                # _stamp_blocks_supp_chain becomes False, re-enabling the
                # ability (30000). Also, if we have Lillie's Determination in
                # hand (and have not played a Supporter yet), we play it
                # BEFORE the ability.
                #
                # CAREFUL (user, registro_006 step 78 vs Archaludon ex,
                # LOST): both are ORDERING vetoes, not VALUE ones -- they say
                # "first X, THEN the ability". If X is not going to be played
                # in this menu there is no "then" and the veto becomes a dead
                # loss: Flip the Script is ONCE PER TURN and its condition (we
                # were knocked out last turn) does not come back. That is why
                # they are registered as DEFERRABLE vetoes in
                # `_order_veto` and revoked further down (see the
                # "REVOKE ORDERING VETOES" block), instead of killing the
                # ability unconditionally here. The deck-out brake, which IS a
                # VALUE veto, is evaluated BEFORE and is never revoked.
                if getattr(my_state, 'deckCount', 60) <= 4:
                    # DECK-OUT BRAKE (crustle autopsy jul 2026): with
                    # the deck at <=4, drawing 3 with Flip the Script leaves
                    # the deck at <=1 and next turn's mandatory draw puts us
                    # on the edge of losing by deck-out. The optional draw is
                    # not worth the game.
                    score = SCORE_VETO
                else:
                    # BAND (user, registro_006 steps 95-102, episode
                    # 88710543 vs Mega Lucario): the 3-card draw goes BEFORE
                    # spending the turn's energy. At 30000 the ability lost
                    # against Teal Dance (31300) and Ripening Charge (31100)
                    # menu after menu and the turn closed with the ability
                    # UNUSED -- free, ONCE PER TURN and with its condition
                    # (being knocked out) dead by the end of the turn.
                    # Besides, this is the correct order by information: the
                    # 3 new cards may bring Grass, so deciding the
                    # attachments AFTER the draw is strictly better than the
                    # other way around. It stays BELOW the lethal bands of
                    # those same abilities (41000/41900: the ability that
                    # ENABLES today's KO still comes first) and below the
                    # winning finisher (_TIER_WIN_ATTACK): if the game closes
                    # this turn, drawing adds nothing.
                    score = FEZ_DRAW_ABILITY_SCORE
                    _ab_order_blockers = tuple(
                        _blk_id for _blk_id, _blk_on in (
                            (Unfair_Stamp, _stamp_blocks_supp_chain),
                            (Lillie_Determination, _lillie_blocks_fez_ability))
                        if _blk_on)
                    if _ab_order_blockers:
                        _order_veto[len(scores)] = (
                            score, _ab_order_blockers)
                        score = SCORE_VETO
            elif card.id == Meowth_ex:
        
                score = 30000
            elif card.id == 1267:
                score = 1
            elif o.area == AreaType.STADIUM:
                # A STADIUM ABILITY WE DO NOT MODEL IS NOT A FREE PLAY (user,
                # `records/registro_007_pasos_098_hasta_105.json` step 101, turn
                # 7 vs Slowking, LOST). Stadiums are SHARED: the simulator
                # offers us the ability of whatever stadium is on the field,
                # including the opponent's, and every one of those options
                # landed here on the generic 29000 of the fallback -- the band
                # of a real play, above the Supporter in hand.
                #
                # That turn the field had their Academy at Night ("put a card
                # from your hand on top of your deck") and our hand was two
                # cards, one of them the Lillie's Determination that refills the
                # hand and fixes the bench, with the Supporter still unplayed.
                # The 29000 beat playing it, the ability fired, and the
                # sub-selection put the Lillie's back into the deck. The only
                # play of the turn was spent deleting itself.
                #
                # The veto is by AREA and not by card id on purpose: the ONE
                # stadium ability this deck wants is Grand Tree, and it is
                # decided above by id with a plan behind it (`_gt_plan`).
                # Anything else on the stadium slot -- theirs today, a card
                # printed tomorrow -- is an effect nobody scored, and an
                # unscored effect must not be paid for with a card from hand.
                score = SCORE_VETO
            else:
                score = 29000
        return score
    finally:
        tc._bp = _bp
        tc.card = card


__all__ = ['score_play']
