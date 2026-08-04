"""`_energy_score_base`, extracted VERBATIM from `agent()` (wave 5).

It used to capture 61 variables of the turn; they now arrive in a context that
is unpacked on entry, with the SAME names, so the body is exactly the one that
was in main.py.
"""

from cg.api import Pokemon
from ptcg.calc.damage import _our_effective_damage
from ptcg.calc.energy import _can_attack_eff, _grass_attach_unit, _grass_mult, _ogerpon_base_phys_cap, _physical_energy
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Meowth_ex, NON_ATTACKER_ENERGY_WASTE_IDS, OUR_EX_IDS, Pinsir, RETREAT_COST, SCORE_CHARGE_ACTIVE_ATTACK, SCORE_CHARGE_ACTIVE_FINISHER, SCORE_VETO, Sylveon, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cards.tables import card_table
from ptcg.state.agent_state import AGENT_STATE
from ptcg.turn.energy_ctx import CtxEnergyScoreBase  # noqa: F401


def _energy_score_base(tc, pokemon, active):
    # Unpacking of the captures.
    _ability_unlock_retreat_attack = tc._ability_unlock_retreat_attack
    _ability_unlock_retreat_ko = tc._ability_unlock_retreat_ko
    _active_already_kos = tc._active_already_kos
    _active_hydra_capped = tc._active_hydra_capped
    _active_needs_energy = tc._active_needs_energy
    _active_pokemon = tc._active_pokemon
    _attach_enable_retreat_attack = tc._attach_enable_retreat_attack
    _attach_enable_retreat_ko = tc._attach_enable_retreat_ko
    _bench_attacker_needs_energy = tc._bench_attacker_needs_energy
    _bench_attacker_ready = tc._bench_attacker_ready
    _bench_has_chargeable = tc._bench_has_chargeable
    _charge_active_enables_attack = tc._charge_active_enables_attack
    _charge_active_finishes = tc._charge_active_finishes
    _conf_active = tc._conf_active
    _conf_active_can_attack = tc._conf_active_can_attack
    _conf_active_can_retreat = tc._conf_active_can_retreat
    _conf_bench_attacker_body = tc._conf_bench_attacker_body
    _conf_bench_attacker_ready = tc._conf_bench_attacker_ready
    _conf_can_attack_pkmn = tc._conf_can_attack_pkmn
    _conf_is_matchup_attacker = tc._conf_is_matchup_attacker
    _ctm_applin_bench = tc._ctm_applin_bench
    _ctm_charge_active_dipplin = tc._ctm_charge_active_dipplin
    _ctm_chikorita_bench = tc._ctm_chikorita_bench
    _ctm_tapu_high = tc._ctm_tapu_high
    _cubchoo_lock_stuck = tc._cubchoo_lock_stuck
    _ex_stuck_promo_ready = tc._ex_stuck_promo_ready
    _extra_energy_enables_ko = tc._extra_energy_enables_ko
    _feza_lucario_wall = tc._feza_lucario_wall
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _hydra_fragile_pivot = tc._hydra_fragile_pivot
    _meganium_alk_1prize_attacker = tc._meganium_alk_1prize_attacker
    _meganium_alk_future_charge = tc._meganium_alk_future_charge
    _ogerpon_lethal_focus_serial = tc._ogerpon_lethal_focus_serial
    _ogerpon_td_manual_lethal = tc._ogerpon_td_manual_lethal
    _ripen_retreat_ko_pivot = tc._ripen_retreat_ko_pivot
    _tapu_future_charge = tc._tapu_future_charge
    _win_via_boss_gust = tc._win_via_boss_gust
    active_ko_likely = tc.active_ko_likely
    bench_count = tc.bench_count
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_hydrapple = tc.has_hydrapple
    is_confused = tc.is_confused
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_has_froslass = tc.op_has_froslass
    op_is_aggro_deck = tc.op_is_aggro_deck
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_beedrill_deck = tc.op_is_beedrill_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_drednaw_deck = tc.op_is_drednaw_deck
    op_is_fire_deck = tc.op_is_fire_deck
    op_is_hop_deck = tc.op_is_hop_deck
    op_is_lucario_deck = tc.op_is_lucario_deck
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_kang_ko_target = tc.op_kang_ko_target
    op_state = tc.op_state
    state = tc.state
    total_grass = tc.total_grass

    energy_count = len(pokemon.energies)

    # ATTACKING WITH THE ACTIVE COMES FIRST (see `_charge_active_finishes`): if the
    # energy that can still move this turn leaves the ACTIVE at its attack cost
    # and that attack KNOCKS OUT, the charge goes to the ACTIVE, full stop. It
    # goes FIRST in the whole function, ahead of the Ogerpon charging focus and
    # the per-matchup energy caps: those caps exist so energy is not WASTED
    # (saving it for retreats, not overcharging a body that already reaches its
    # cost), and energy that takes a prize TODAY is not wasted. It only yields to
    # the WINNING finisher via Boss's (42000). It covers the MANUAL attachment
    # (OptionType.ATTACH) and the target of Ripening Charge
    # (SelectContext.ATTACH_FROM), both of which score through here.
    if active and _charge_active_finishes:
        return SCORE_CHARGE_ACTIVE_FINISHER

    # TARGET of the line "Grass to the ACTIVE -> RETREAT -> attack with the
    # benched one" (user, registro_006 step 101 vs Alakazam, LOST). The four
    # flags already detect the whole line and score the ACT of charging (the
    # manual attachment in its OptionType.ATTACH branch, the abilities in theirs),
    # but the DESTINATION of the energy is decided here -- and here there was
    # nothing: the ACTIVE fell into the generic development band (~8000) and any
    # benched body beat it. Result: Ripening Charge was activated "for the right
    # line" and the Grass ended up on a benched Ogerpon, with the real finisher
    # trapped behind an Applin that could not retreat. Same bands the consumers
    # use: 41000 (lethal) and 31250 (chip). It covers the MANUAL attachment
    # (OptionType.ATTACH) and the target of the charging abilities
    # (SelectContext.ATTACH_FROM).
    if active and (_attach_enable_retreat_ko or _ability_unlock_retreat_ko):
        return 41000
    if active and (_attach_enable_retreat_attack
                   or _ability_unlock_retreat_attack):
        return 31250

    # Lethal charging focus on ONE Ogerpon (see `_ogerpon_lethal_focus_serial`):
    # concentrate the manual attachment on THAT body and do NOT split it to
    # another Ogerpon.
    if (_ogerpon_lethal_focus_serial is not None
            and pokemon.id == Teal_Mask_Ogerpon_ex):
        if getattr(pokemon, 'serial', None) == _ogerpon_lethal_focus_serial:
            return 41700
        return SCORE_VETO
    # Tie-break by HP (user, log 86212499 step 151, vs Alakazam, WON): when there
    # are two or more IDENTICAL Pokemon as energy charging targets (e.g. two
    # Hydrapple ex on the bench, one at 70 hp and another at 330 hp), ALWAYS
    # charge the one with MORE HP. Before, both fell into the same branch and got
    # the same integer score, so the tie was broken by the option order (lower
    # bench index -> the 70 hp one). A TINY fraction of the HP is added (< 1
    # point: hp/100000, maximum 0.0033) which ONLY alters exact ties and never
    # crosses the integer thresholds of the other branches, so that on an equal
    # score the one with more HP wins. It covers the MANUAL attachment
    # (OptionType.ATTACH) and the target of Ripening Charge
    # (SelectContext.ATTACH_FROM), since both score via energy_score.
    score = 8000 + (getattr(pokemon, 'hp', 0) or 0) / 100000.0

    # Rule (user, log 86028607 step 21, vs Crustle, WE WON): a Chikorita may have
    # at MOST 1 energy. NEVER attach a 2nd energy to a Chikorita (its only attack
    # uses 1 energy; the surplus is wasted and the energy is better saved for real
    # attackers or retreats). It applies to the active and the bench, and to any
    # attachment route (manual or Ripening Charge). len(energies) is EFFECTIVE
    # (Meganium's Wild Growth DOUBLES every Grass), so it is converted to PHYSICAL
    # cards.
    if pokemon.id == Chikorita and _physical_energy(energy_count) >= 1:
        return SCORE_VETO

    # Rule (user, registro_004 step 36, episode 87675043 vs Mega Lucario, LOST):
    # an Applin may have at MOST 1 PHYSICAL energy. Its only attack costs 1 and it
    # evolves soon (Dipplin's Do the Wave also costs 1), so the 2nd energy is
    # WASTED: it should go to an Ogerpon (Teal Dance / attachment) or to a future
    # attacker. Before, the 2nd energy only got a soft penalty (-300 -> 7700) that
    # still beat Teal Dance (7500) and the agent overcharged the Applin.
    # Exceptions:
    #   (a) a COMPLETE evolution this turn (Dipplin AND Hydrapple ex in hand,
    #       without Meganium): the extra energy ends up on the future Hydrapple ex
    #       (2 effective = Syrup Storm ready) -> it is let through to the normal
    #       ranking (branch _applin_full_evolve_now);
    #   (b) OUR Hydrapple ex already in play: energy on the field does boost
    #       Syrup Storm (it scales with the TOTAL Grass), but ONLY as a LAST
    #       resort (minimum score 10) when there is no other Pokemon left to
    #       charge (everything else vetoed).
    # It applies to the active and the bench, and to any attachment route (manual
    # or Ripening Charge). len(energies) is EFFECTIVE (Meganium's Wild Growth
    # DOUBLES every Grass), so it is converted to PHYSICAL cards.
    if pokemon.id == Applin and _physical_energy(energy_count) >= 1:
        _apl_full_evolve_now = (hand_counts.get(Dipplin, 0) >= 1
                                and hand_counts.get(Hydrapple_ex, 0) >= 1
                                and not AGENT_STATE.meganium_in_play)
        if not _apl_full_evolve_now:
            if field_counts.get(Hydrapple_ex, 0) >= 1:
                return 10
            return SCORE_VETO

    # Rule (user, registro_004 step 43, episode 88120517 vs Marnie's
    # Grimmsnarl, WON with a mistake): a Dipplin may have at MOST 1 PHYSICAL
    # energy -- Do the Wave costs 1 and its damage does NOT scale with
    # energy, so the 2nd is wasted and takes the place of Teal Dance / of
    # charging an Ogerpon towards Myriad. Exceptions (mirror of the Applin
    # rule):
    #   (a) an evolution into Hydrapple THIS turn (Hydrapple ex in hand and
    #       the Dipplin did NOT appear/evolve this turn): the 2nd energy
    #       lands immediately on the Hydrapple (2 effective = Syrup Storm
    #       ready). A Dipplin that evolved THIS turn cannot evolve again,
    #       so there is NO exception there (the case in the record: a 2nd
    #       energy on a freshly evolved Dipplin).
    #   (b) OUR Hydrapple ex already in play: last resort (10), energy on
    #       the field boosts Syrup Storm but only if there is nothing
    #       better to charge.
    if pokemon.id == Dipplin and _physical_energy(energy_count) >= 1:
        _dip_evolve_now = (hand_counts.get(Hydrapple_ex, 0) >= 1
                           and not getattr(pokemon, 'appearThisTurn', False))
        if not _dip_evolve_now:
            if field_counts.get(Hydrapple_ex, 0) >= 1:
                return 10
            return SCORE_VETO

    # Rule (user, log 86607718 turn 2, vs Crustle, WE LOST): if we start the turn
    # with a Chikorita in the ACTIVE spot and NO Chikorita on the bench, the
    # priority vs Crustle is to RETREAT it (to evolve it into Meganium on the
    # bench and bring up a useful body; an active Chikorita is a 1-prize burden
    # that does not attack the wall). To be able to retreat (cost 1) it needs 1
    # Grass attached, so the energy attachment goes to the ACTIVE Chikorita
    # (0 physical) ABOVE charging benched attackers (e.g. Tapu Bulu), as long as
    # there is a body on the bench to promote after the retreat. Only the 1st
    # energy: the "Chikorita max 1" rule above still stands. It goes AFTER the
    # winning finisher (42000) so a KO is not blocked.
    if (AGENT_STATE.op_is_crustle_deck and active and pokemon.id == Chikorita
            and _physical_energy(energy_count) == 0
            and field_counts.get(Chikorita, 0) <= 1
            and bench_count >= 1
            and not state.energyAttached):
        return 41500

    # Rule (user, log 85855786 step 141, vs Alakazam, WE WON): if this turn there
    # is a WINNING / 2-prize play via Boss's Orders (gusting from the opposing
    # bench a target we knock out to take the prizes we are missing) and that
    # lethal KO relies on having the energy on the ACTIVE (which is the attacker),
    # the charge MUST go to the ACTIVE. Winning the game NOW is the top priority
    # and prevails over charging Tapu Bulu as a FUTURE attacker
    # (`_tapu_future_charge`, 40000), which only serves next turn and is
    # irrelevant if we already close the game.
    # EXCEPTION (user, registro_006 p79 and registro_008 p109-113 vs Alakazam):
    # do NOT force the charge onto the active when the EXTRA energy adds nothing
    # to ITS attack and it ALREADY meets its requirement; that way it is not
    # wasted on a charged active and flows to a FUTURE benched attacker (e.g. a
    # benched Hydrapple ex at 0 energies, which besides developing adds to Syrup
    # Storm's damage). It covers:
    #   - Tapu Bulu / Meganium: FIXED damage with a hard cap (Wood Hammer cost 4);
    #     the extra energy does not increase the damage.
    #   - Hydrapple ex: Syrup Storm scales with the Grass on the FIELD (all our
    #     Pokemon), NOT with the attacker's OWN energy; putting it on a benched
    #     Hydrapple gives EXACTLY the same damage this turn and also leaves a 2nd
    #     attacker ready.
    # Ogerpon ex (Myriad) is NOT included: its damage scales with its OWN energy,
    # so there the 42000 to the active STILL applies (more energy grows/enables
    # the finisher).
    if active and (_win_via_boss_gust or _gust_2prize_via_boss):
        _active_extra_charge_wasted = (
            pokemon.id in (Tapu_Bulu, Meganium, Hydrapple_ex)
            and energy_count >= AGENT_STATE.ATTACK_ENERGY_REQ.get(pokemon.id, 99))
        if not _active_extra_charge_wasted:
            return 42000

    # Rule (user, log 86342087 step 130, vs Mega Lucario, WE LOST): if the active
    # is a Fezandipiti ex WEAK to Fighting that will be KNOCKED OUT by Mega
    # Lucario ex next turn (Mega Brave 270 x2 = 540, 2 prizes) and there is a
    # healthy Hydrapple ex on the bench (a 330 wall that SURVIVES the opposing
    # hit), this turn's energy must NOT go to the doomed Feza (which would only
    # attack once before dying and giving away 2 prizes) but to the Hydrapple: that
    # way we leave it ready (>=2 effective) so that, after RETREATING the Feza
    # (cost 1) and promoting it, we attack with Syrup Storm. The attachment to the
    # active is vetoed and charging the benched Hydrapple until its attack is
    # enabled is prioritised. It goes AFTER the winning finisher (42000) so a
    # lethal KO is not blocked.
    if _feza_lucario_wall:
        if active:
            return SCORE_VETO
        if (pokemon.id == Hydrapple_ex
                and len(pokemon.energies) * _grass_mult() < 2):
            return 41000

    # Rule (user): a Tapu Bulu in play may have at MOST 4 PHYSICAL energies if
    # there is NO Meganium in play, or 2 if there IS. With Meganium (Wild Growth)
    # each physical Grass counts DOUBLE, so 2 physical = 4 effective = enough for
    # Wood Hammer (cost 4); without Meganium 4 physical are needed. Do not attach
    # more: the surplus is wasted and the energy is better saved. len(energies) is
    # EFFECTIVE => it is converted to PHYSICAL cards with _physical_energy. It
    # applies to the manual attachment (OptionType.ATTACH) and to the target of
    # Ripening Charge (SelectContext.ATTACH_FROM), active or bench. It goes AFTER
    # the return of the winning play (42000) so a lethal finisher is not blocked.
    if pokemon.id == Tapu_Bulu:
        _tapu_max_phys = 2 if AGENT_STATE.meganium_in_play else 4
        if _physical_energy(energy_count) >= _tapu_max_phys:
            return SCORE_VETO

    # Rule (user, vs Crustle, log 86583376 step 84): a Teal Mask Ogerpon ex may
    # not hold more than TWO PHYSICAL energies charged (by manual attachment or
    # Ripening Charge). Against the Crustle wall (which makes our ex useless)
    # Ogerpon cannot attack the wall, so we SAVE energy and do not overcharge it.
    # On the BENCH the cap is HARD (max 2 physical). The ONLY exception for a 3rd
    # energy: when the Ogerpon is the ACTIVE and that energy ENABLES the KO on the
    # opposing active (_extra_energy_enables_ko) -- the opposing active is not
    # always the immune wall; it can be a non-ex that Ogerpon DOES damage. The
    # op_kang_ko_target bypass is also kept (a KO on Mega Kangaskhan ex with
    # Hydrapple ex, where the extra energy on the board raises Syrup Storm's
    # damage). len(energies) is EFFECTIVE (Meganium's Wild Growth doubles every
    # Grass) => it is converted to PHYSICAL cards with _physical_energy.
    if (AGENT_STATE.op_is_crustle_deck and pokemon.id == Teal_Mask_Ogerpon_ex
            and not op_kang_ko_target):
        _crus_phys = _physical_energy(energy_count)
        if not active:
            if _crus_phys >= 2:
                return SCORE_VETO
        else:
            if _crus_phys >= 3:
                return SCORE_VETO
            if (_crus_phys >= 2
                    and not _extra_energy_enables_ko(
                        Teal_Mask_Ogerpon_ex, energy_count)):
                return SCORE_VETO

    # Rule (user, vs Alakazam and vs Hop's): energy caps for Teal Mask Ogerpon ex
    # (MANUAL attachment or Ripening Charge). PHYSICAL base with Meganium in play
    # = 2 (Wild Growth doubles every Grass, so 2 physical = 4 effective = ready
    # for Myriad Leaf Shower, cost 3). Without Meganium: 4 vs Alakazam and 3 vs
    # Hop's (user: "an Ogerpon cannot have more than three energies attached if we
    # do not have Meganium in play, or two if Meganium is out"). On the BENCH the
    # cap is HARD: we do not overcharge, we save energy. On the ACTIVE ONE extra
    # PHYSICAL energy is allowed ONLY if that energy is the one that ENABLES the
    # KO on the opposing active (_extra_energy_enables_ko: the current damage does
    # not knock out but with +1 it does). A WINNING line via Boss's already
    # returned 42000 above, so this cap does not block lethal finishers.
    # len(energies) is EFFECTIVE => it is converted to PHYSICAL cards with
    # _physical_energy.
    if (op_is_alakazam_deck or op_is_hop_deck) and pokemon.id == Teal_Mask_Ogerpon_ex:
        _alk_base_phys = _ogerpon_base_phys_cap(AGENT_STATE.meganium_in_play, op_is_hop_deck)
        _alk_phys = _physical_energy(energy_count)
        if not active:
            if _alk_phys >= _alk_base_phys:
                return SCORE_VETO
        else:
            if _alk_phys >= _alk_base_phys + 1:
                return SCORE_VETO
            if (_alk_phys >= _alk_base_phys
                    and not _extra_energy_enables_ko(
                        Teal_Mask_Ogerpon_ex, energy_count)):
                return SCORE_VETO

    # Cubchoo matchup (user): PHYSICAL energy caps per Pokemon. Cubchoo blocks our
    # attack next turn, so we do not overcharge and we SAVE energies in HAND to pay
    # retreats. USER'S DECISION (jul 2026, after the autopsy of the mixed
    # Cornerstone/Cubchoo deck): these caps are NOT relaxed even when the matchup
    # is the mixed one. The reason for the reserve is that these decks play Boss's
    # Orders and other supporters that SWAP our active: without energy in hand you
    # cannot pay the retreat of the wrong body they brought up, and you never get
    # back to the right attacker. The "dead energy in hand" the autopsy sees
    # (ATTACH vetoed) is the deliberate price of that insurance. IMPORTANT: the
    # observation DUPLICATES every physical Grass when Meganium is in play (Wild
    # Growth), so len(energies) is EFFECTIVE; we convert it to PHYSICAL cards
    # (_cub_phys) to apply the caps the user defined in cards. It applies to the
    # manual attachment (OptionType.ATTACH) and to the target of Ripening Charge
    # (SelectContext.ATTACH_FROM).
    if op_is_cubchoo_deck:
        _cub_phys = _physical_energy(energy_count)
        if pokemon.id == Teal_Mask_Ogerpon_ex and _cub_phys >= (2 if AGENT_STATE.meganium_in_play else 4):
            return SCORE_VETO
        if pokemon.id == Applin and _cub_phys >= 1:
            return SCORE_VETO
        if pokemon.id == Dipplin and _cub_phys >= (1 if AGENT_STATE.meganium_in_play else 2):
            return SCORE_VETO
        if pokemon.id == Hydrapple_ex and _cub_phys >= (2 if AGENT_STATE.meganium_in_play else 3):
            return SCORE_VETO
        # Meganium line (Chikorita/Bayleef/Meganium): a cap of 3 PHYSICAL energies
        # across the whole line (user's rule, change 4).
        if pokemon.id in (Chikorita, Bayleef, Meganium) and _cub_phys >= 3:
            return SCORE_VETO

    # Retreat status of our own ACTIVE: to promote a LETHAL Hydrapple ex from the
    # BENCH the active has to RETREAT, which requires PHYSICAL energy on the
    # active >= its retreat cost. len(energies) is EFFECTIVE (Meganium's Wild
    # Growth DOUBLES every Grass), but the retreat is paid with PHYSICAL cards, so
    # physical = effective // 2 when Meganium is in play. If the active CANNOT
    # retreat yet, the charge must go to the ACTIVE to start paying the retreat,
    # not to the benched Hydrapple (which does not attack from the bench).
    _hls_my_act = (my_state.active[0]
                   if (my_state.active and my_state.active[0] is not None)
                   else None)
    _hls_act_phys = 0
    _hls_act_rc = 1
    if _hls_my_act is not None:
        _hls_act_eff = len(_hls_my_act.energies)
        _hls_act_phys = _physical_energy(_hls_act_eff)
        _hls_act_rc = RETREAT_COST.get(_hls_my_act.id, 1)
    # The shortcut "if the active is a Hydrapple ex, treat the promotion as good"
    # only holds when that Hydrapple CAN ALREADY ATTACK: there the Grass is
    # fungible (Syrup Storm scales with the Grass on the WHOLE field, so it does
    # not matter which body it lands on) and nobody has to retreat. With the
    # active Hydrapple STILL SHORT of its attack cost, the promotion really
    # requires retreating it (cost 3) and the shortcut became a FALSE premise:
    # user, registro_006 step 67 (episode 88433181, WON with a mistake) --
    # active Hydrapple at 0 energies, impossible to retreat, and the rule sent the
    # Grass to the BENCHED Hydrapple "to promote it", leaving the turn sterile
    # with the opposing active at 10 HP.
    _hls_act_retreatable = (_hls_my_act is None
                            or (_hls_my_act.id == Hydrapple_ex
                                and not _hydra_fragile_pivot
                                and _can_attack_eff(
                                    Hydrapple_ex,
                                    len(_hls_my_act.energies)))
                            or _hls_act_phys >= _hls_act_rc)

    # Rule (user): if charging a BENCHED Hydrapple ex leaves it ready (>=2
    # effective) for a LETHAL Syrup Storm on the opposing active, prioritise that
    # charge (Ripening Charge or manual attachment) above any other, so it can be
    # promoted (retreating the active) and finish. It goes AFTER the Cubchoo cap
    # (which saves energy) and BEFORE the Tapu Bulu charge, because winning the
    # game is the top priority. ONLY if the active CAN already retreat this turn
    # (if not, the lethal charge must go to the ACTIVE, see the next block):
    # charging a benched Hydrapple that cannot be promoted is useless (it does not
    # attack from the bench).
    if (not active and pokemon.id == Hydrapple_ex
            and _hls_act_retreatable
            and op_state.active and op_state.active[0] is not None):
        _hls_eff_after = energy_count * _grass_mult() + _grass_attach_unit()
        if _hls_eff_after >= 2:
            _hls_opa = op_state.active[0]
            _hls_opa_hp = _hls_opa.hp or 0
            # total_grass is EFFECTIVE; attaching 1 Grass adds _grass_attach_unit().
            _hls_dmg = _our_effective_damage(
                pokemon, _hls_opa,
                30 + 30 * (total_grass + _grass_attach_unit()),
                AGENT_STATE.meganium_in_play, neutralization_zone_active)
            if _hls_dmg > 0 and _hls_opa_hp > 0 and _hls_dmg >= _hls_opa_hp:
                return 41000

    # Rule (user): if the LETHAL Hydrapple ex is on the BENCH but our own active
    # CANNOT retreat yet (physical energy < retreat cost), the charge must go to
    # the ACTIVE to start paying the retreat and so enable the retreat ->
    # promotion of the Hydrapple -> lethal Syrup Storm. Only if the retreat is
    # COMPLETABLE this turn: (cost - current physical) Grass are needed and we have
    # at least that many in hand and enough attachments (1 manual + one Ripening
    # Charge per benched Hydrapple).
    if (active and _hls_my_act is not None
            and not _hls_act_retreatable
            and _hls_my_act.id != Hydrapple_ex
            and op_state.active and op_state.active[0] is not None):
        _hls_bench_hydra = [
            _bp for _bp in (my_state.bench or [])
            if _bp is not None and _bp.id == Hydrapple_ex
            and len(_bp.energies) >= 2]
        _hls_promote_lethal = False
        if _hls_bench_hydra:
            _hls_opa2 = op_state.active[0]
            _hls_opa2_hp = _hls_opa2.hp or 0
            for _bp in _hls_bench_hydra:
                _hls_bdmg = _our_effective_damage(
                    _bp, _hls_opa2, 30 + 30 * total_grass,
                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
                if _hls_bdmg > 0 and _hls_opa2_hp > 0 and _hls_bdmg >= _hls_opa2_hp:
                    _hls_promote_lethal = True
                    break
        if _hls_promote_lethal:
            _hls_need = _hls_act_rc - _hls_act_phys
            _hls_grass_hand = sum(
                1 for _c in (my_state.hand or [])
                if _c.id == Basic_Grass_Energy)
            _hls_max_attach = 1 + len(_hls_bench_hydra)
            if (_hls_need >= 1 and _hls_grass_hand >= _hls_need
                    and _hls_max_attach >= _hls_need):
                return 41000

    # Rule (user, log 86027506 step 81, vs Abomasnow, WON): if the ACTIVE is a
    # FRAGILE Hydrapple ex and there is a healthy, lethal Hydrapple ex on the bench
    # (`_hydra_fragile_pivot`), this turn's energy must go to the fragile ACTIVE to
    # reach its retreat cost (3 physical) and be able to RETREAT it (protecting it)
    # -> promote the healthy one -> lethal Syrup Storm. It covers the MANUAL
    # attachment (OptionType.ATTACH) and the target of Ripening Charge
    # (SelectContext.ATTACH_FROM). Only if the retreat is COMPLETABLE this turn:
    # the Grass in hand and the available attachments are enough (1 manual + one
    # Ripening Charge per benched Hydrapple).
    if (active and _hydra_fragile_pivot
            and _hls_my_act is not None
            and _hls_my_act.id == Hydrapple_ex
            and _hls_act_phys < _hls_act_rc):
        _hfp_need = _hls_act_rc - _hls_act_phys
        _hfp_grass_hand = sum(
            1 for _c in (my_state.hand or [])
            if _c.id == Basic_Grass_Energy)
        _hfp_bench_hydra_ct = sum(
            1 for _bp in (my_state.bench or [])
            if _bp is not None and _bp.id == Hydrapple_ex)
        _hfp_max_attach = (0 if state.energyAttached else 1) + _hfp_bench_hydra_ct
        if (_hfp_need >= 1 and _hfp_grass_hand >= _hfp_need
                and _hfp_max_attach >= _hfp_need):
            return 41000

    # Ripening -> retreat -> promote a lethal Tapu pivot vs the immune wall (user,
    # log 86028607 turn 22): if _ripen_retreat_ko_pivot is active (active =
    # Hydrapple ex blocked by Crustle with a benched Tapu ALREADY READY that knocks
    # the wall out), the Ripening Charge Grass must go to the ACTIVE Hydrapple
    # ITSELF to reach its (effective) retreat cost and be able to retreat it ->
    # bring up Tapu -> lethal Wood Hammer. It covers the target of Ripening Charge
    # (SelectContext.ATTACH_FROM); the manual attachment was already spent charging
    # Tapu (which is why the pivot only exists after that charge).
    if _ripen_retreat_ko_pivot and active and pokemon.id == Hydrapple_ex:
        return 41000

    # NON-lethal mirror of `_charge_active_finishes` (see the flag): the charge leaves
    # the ACTIVE at its attack cost but the attack does not finish. It is still the
    # only way to attack today (there is no ready, promotable benched attacker), and
    # chip damage is worth infinitely more than closing the turn without attacking
    # -- the same reasoning as `_attach_enable_retreat_attack` (31200), but without
    # paying a retreat. It goes AFTER all the lethal lines (41000+), which still
    # rule, and BEFORE the charges of FUTURE attackers.
    if active and _charge_active_enables_attack:
        return SCORE_CHARGE_ACTIVE_ATTACK

    # Rule (user, log 85857426 step 37, vs Mega Lucario, WE LOST): do NOT waste the
    # manual attachment on a doomed ACTIVE Tapu Bulu. If the active is a Tapu Bulu
    # that, after attaching 1 Grass, STILL cannot attack (Wood Hammer needs 4
    # effective) and STILL cannot retreat (PHYSICAL energy < retreat cost 3) — the
    # energy is useless to it this turn and it will be knocked out next turn — and
    # there is also an uncharged Teal Mask Ogerpon ex on the bench (energy < 3) to
    # which Teal Dance can attach Grass + DRAW, veto the manual attachment (-1).
    # That way the play order (ATTACH is tier ENERGY=1, Teal Dance ABILITY is tier
    # 0) no longer puts the wasted charge first and Teal Dance is used: the energy
    # is not lost and a card is drawn. Limited to Mega Lucario (a fixed, high
    # opposing finisher). It covers the MANUAL attachment (OptionType.ATTACH) and
    # the target of Ripening Charge (SelectContext.ATTACH_FROM).
    if (active and pokemon.id == Tapu_Bulu and op_is_lucario_deck
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _twt_eff_after = energy_count + _grass_attach_unit()
        _twt_phys_after = _physical_energy(energy_count) + 1
        _twt_rc = RETREAT_COST.get(Tapu_Bulu, 3)
        if _twt_eff_after < 4 and _twt_phys_after < _twt_rc:
            for _twt_bp in (my_state.bench or []):
                if (_twt_bp is not None
                        and _twt_bp.id == Teal_Mask_Ogerpon_ex
                        and len(_twt_bp.energies) < 3):
                    return SCORE_VETO

    # Top priority: charge a benched Tapu Bulu as a future attacker when the active
    # already secures the KO and Meganium is in play. Reused both by the manual
    # attachment (OptionType.ATTACH) and by the target of Ripening Charge
    # (SelectContext.ATTACH_FROM).
    if (_tapu_future_charge and not active and pokemon.id == Tapu_Bulu
            and len(pokemon.energies) * _grass_mult() < 4):
        return 40000

    # Charge a benched Meganium as a FUTURE 1-prize attacker vs Alakazam (140
    # beats the Alakazam line). Lower priority than Tapu Bulu and than the bench
    # charges at 0 (26000-30000): 25000 only wins when the main attackers no longer
    # need the energy. It covers the manual attachment and the Ripening Charge
    # target. See `_meganium_alk_future_charge`.
    # Meganium as a 1-prize ATTACKER THIS turn vs Alakazam: it dominates charging
    # the active ex (41000) so the manual attachment completes its cost and we
    # attack with the 1-prize body (retreat the ex, promote Meganium). See the flag.
    if (_meganium_alk_1prize_attacker and not active and pokemon.id == Meganium
            and len(pokemon.energies) * _grass_mult() < 4):
        return 43000

    if (_meganium_alk_future_charge and not active and pokemon.id == Meganium
            and len(pokemon.energies) * _grass_mult() < 4):
        return 25000

    if (AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck) and \
            pokemon.id == Meganium and energy_count >= 4:
        return SCORE_VETO

    if is_confused and _conf_active is not None:
        if (not active and _conf_is_matchup_attacker(pokemon.id)
                and not _conf_can_attack_pkmn(pokemon)):
            return 40000
        if active and _conf_bench_attacker_ready and not _conf_active_can_retreat:
            _ret_eff_es = energy_count * _grass_mult()
            if _ret_eff_es < RETREAT_COST.get(pokemon.id, 1):
                return 35000
        if (active and not _conf_bench_attacker_body
                and _conf_is_matchup_attacker(pokemon.id)
                and not _conf_active_can_attack):
            return 33000

    if AGENT_STATE.op_is_cornerstone_deck and not AGENT_STATE.op_is_crustle_deck:

        if pokemon.id == Tapu_Bulu:

            if energy_count < 4:
                score += 22000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Pinsir:

            if energy_count < 2:
                score += 23000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Teal_Mask_Ogerpon_ex:

            if active and energy_count == 0:
                _tapu_ready_cs = any(
                    bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 4
                    for bp in (my_state.bench or []))
                if _tapu_ready_cs:
                    score += 10
                    score += 40
                else:
                    score -= 500
            else:
                score -= 500
        else:

            if active and energy_count == 0:
                _tapu_ready_cs2 = any(
                    bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 4
                    for bp in (my_state.bench or []))
                if _tapu_ready_cs2:
                    score += 10
                    score += 30
                else:
                    score -= 300
            else:
                score -= 300
        return score

    if AGENT_STATE.op_is_crustle_deck:

        # SURPLUS energy: if the ACTIVE Tapu Bulu is already charged (>=4
        # effective) it can attack as it is, so this turn's manual attachment
        # must not be wasted overcharging it. It is redirected in priority
        # order: (1) another benched Tapu Bulu that does not reach 4 effective
        # yet, (2) a Dipplin with no energy, (3) a Meganium short of its 4
        # effective. If none of them needs it, the energy is KEPT (a negative
        # score -> the agent does not play it).
        _ctm_act_te = my_state.active[0] if my_state.active else None
        _ctm_active_tapu_full = (
            _ctm_act_te is not None
            and _ctm_act_te.id == Tapu_Bulu
            and len(_ctm_act_te.energies) * _grass_mult() >= 4)
        if _ctm_active_tapu_full:
            if (pokemon.id == Tapu_Bulu and not active
                    and energy_count * _grass_mult() < 4):
                return 40000
            if pokemon.id == Dipplin and energy_count < 1:
                return 39000
            if pokemon.id == Meganium and energy_count * _grass_mult() < 4:
                return 38000
            return SCORE_VETO

        if pokemon.id == Tapu_Bulu:

            # Rule (user, log 85802744 step 55): if Meganium is NOT in play yet
            # but can be evolved THIS turn (Bayleef in play + Meganium in hand),
            # Wild Growth will double Tapu Bulu's CURRENT physical energies. If
            # with that doubling Tapu already reaches its 4 effective (>= 2
            # physical energies now), do NOT waste the manual attachment
            # overcharging it: the energy is saved and Meganium is evolved, which
            # leaves Tapu ready to attack without spending it. The scorer is
            # greedy (it does not simulate "evolve first"), which is why here,
            # with Meganium out of play, it saw Tapu with only its physical
            # energies (< 4) and gave it charging priority.
            _meg_evolvable_now_tapu = (
                not active
                and not AGENT_STATE.meganium_in_play
                and field_counts.get(Bayleef, 0) >= 1
                and hand_counts.get(Meganium, 0) >= 1)
            if _meg_evolvable_now_tapu and energy_count * 2 >= 4:
                return SCORE_VETO

            # len(energies) is ALREADY the EFFECTIVE energy (the observation
            # doubles Grass through Wild Growth): Wood Hammer needs 4 effective.
            # Do not overcharge beyond that.
            _tapu_eff_ct = energy_count * _grass_mult()
            if _tapu_eff_ct < 4:
                score += 20000
                if _ctm_tapu_high:

                    score += 5000
                if _ctm_chikorita_bench:

                    score += 11000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Teal_Mask_Ogerpon_ex:

            if active and energy_count == 0:

                _tapu_bench_og = any(
                    bp is not None and bp.id in (Tapu_Bulu, Dipplin, Meganium) and
                    len(bp.energies) >= (1 if bp.id == Dipplin else 4)
                    for bp in (my_state.bench or []))
                if _tapu_bench_og:
                    score += 10
                    score += 40
                else:
                    score -= 500
            else:
                score -= 500
        elif pokemon.id == Applin:

            if energy_count < 1:
                score += 22000
                if _ctm_applin_bench and not _ctm_chikorita_bench:

                    score += 6500
                if active:
                    score += 100
            else:
                score -= 40
        elif pokemon.id == Dipplin:

            if _ctm_charge_active_dipplin and active and energy_count < 1:

                score = 50000
            elif _ctm_tapu_high:

                score = SCORE_VETO
            elif energy_count < 1:
                score += 23000
                if active:
                    score += 100
            else:
                score = SCORE_VETO
        elif pokemon.id == Pinsir:

            if energy_count < 2:
                score += 21000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Meganium:

            # Meganium is the key doubler against Crustle; it must not be left as
            # a wall in the active spot. If it is active and cannot retreat yet
            # (0 energies) and there is an already charged non-ex benched attacker
            # to promote, we prioritise charging it 1 energy: with Wild Growth
            # 1 basic energy = {G}{G}, enough to pay its retreat cost of 2 and get
            # it to the bench next turn.
            _meg_promo_ready = any(
                bp is not None and (
                    (bp.id == Tapu_Bulu and
                     len(bp.energies) * _grass_mult() >= 4) or
                    (bp.id == Dipplin and len(bp.energies) >= 1) or
                    (bp.id == Pinsir and
                     len(bp.energies) * _grass_mult() >= 2))
                for bp in (my_state.bench or []))

            _tapu_in_play_meg = field_counts.get(Tapu_Bulu, 0) >= 1
            _dipplin_in_play_meg = any(
                bp is not None and bp.id == Dipplin
                for bp in (list(my_state.active or []) + list(my_state.bench)))

            # len(energies) is ALREADY the EFFECTIVE energy (Wild Growth already
            # applied in the observation): Solar Beam needs 4.
            _meg_eff = energy_count * _grass_mult()
            if active and energy_count == 0 and _meg_promo_ready:
                score += 24000
                score += 100
            elif not _tapu_in_play_meg and not _dipplin_in_play_meg and _meg_eff < 4:
                score += 19000
                if active:
                    score += 100
            elif _meg_eff < 4:
                score -= 50
            else:
                score -= 80
        else:

            if (active and pokemon.id in OUR_EX_IDS
                    and (_ex_stuck_promo_ready or _cubchoo_lock_stuck)
                    and energy_count * _grass_mult()
                        < RETREAT_COST.get(pokemon.id, 1)):
                # Our active ex cannot damage the Crustle (immune) and there is a
                # non-ex attacker READY on the bench: we charge the ex up to its
                # retreat cost so it can retreat on the next step and promote the
                # attacker that DOES hit the Crustle.
                # `_cubchoo_lock_stuck`: active Hydrapple ex blocked by Snotted Up --
                # route the energy to the ACTIVE to enable the retreat towards the
                # benched attacker (step 82).
                score += 24000
                score += 100
            elif active:
                score += 10

                _tapu_on_bench = field_counts.get(Tapu_Bulu, 0) >= 1
                if _tapu_on_bench and energy_count == 0:
                    score += 50
                else:
                    score -= 300
            else:
                score -= 300
        return score

    if neutralization_zone_active:
        if pokemon.id == Tapu_Bulu:
            effective_energy = energy_count * _grass_mult()
            if active:
                score += 10
                if effective_energy < 4:
                    score += 23200
                else:
                    score -= 50
            else:
                if effective_energy < 4:
                    score += 600
                else:
                    score -= 80
            return score
        elif pokemon.id == Dipplin:
            if active:
                score += 10
                if energy_count < 1:
                    score += 23200
                else:
                    score -= 30
            else:
                if energy_count < 1:
                    score += 400
                else:
                    score -= 50
            return score
        elif pokemon.id == Pinsir:

            effective_energy = energy_count * _grass_mult()
            if active:
                score += 10
                if effective_energy < 2:
                    score += 23000
                else:
                    score -= 40
            else:
                if effective_energy < 2:
                    score += 380
                else:
                    score -= 60
            return score
        elif pokemon.id == Meganium:

            effective_energy = energy_count * _grass_mult()
            if active:
                score += 10
                if effective_energy < 4:
                    score += 15000
                else:
                    score -= 100
            else:
                if effective_energy < 4:
                    score += 300
                else:
                    score -= 100
            return score
        elif pokemon.id == Teal_Mask_Ogerpon_ex:

            if energy_count >= 2:
                score -= 500
            elif active:
                score += 10
                score += 100
            else:
                score += 200
            return score
        elif pokemon.id in OUR_EX_IDS:

            _op_act_nz_e = op_state.active[0] if op_state.active else None
            _op_nz_e_rb = False
            if _op_act_nz_e is not None:
                _op_nz_e_data = card_table[_op_act_nz_e.id]
                _op_nz_e_rb = (_op_nz_e_data.ex or _op_nz_e_data.megaEx)
            if _op_nz_e_rb:
                pass
            elif active:
                score += 10
                score -= 200
                return score
            else:
                score -= 300
                return score

    if (AGENT_STATE.meganium_in_play and _active_pokemon is not None
            and _active_pokemon.id == Hydrapple_ex
            and len(_active_pokemon.energies) >= 1
            and _bench_has_chargeable
            and not AGENT_STATE.op_is_crustle_deck and not AGENT_STATE.op_is_cornerstone_deck
            and not neutralization_zone_active):

        if active:
            return SCORE_VETO
        _raw_mb = len(pokemon.energies)
        if pokemon.id == Hydrapple_ex:
            return 20000 if _raw_mb < 1 else -1
        if pokemon.id == Teal_Mask_Ogerpon_ex:

            return 19000 if _raw_mb < 2 else 5000
        if pokemon.id == Dipplin:
            return 18000 if _raw_mb < 1 else -1
        if pokemon.id == Meganium:
            return 17000 if _raw_mb < 2 else -1
        if pokemon.id == Tapu_Bulu:
            return 16000 if _raw_mb < 2 else -1
        return SCORE_VETO

    if (_active_hydra_capped and _bench_has_chargeable
            and not AGENT_STATE.op_is_crustle_deck and not AGENT_STATE.op_is_cornerstone_deck
            and not neutralization_zone_active):
        if active:
            return SCORE_VETO
        _eff_bench_sc = energy_count * _grass_mult()
        if pokemon.id == Teal_Mask_Ogerpon_ex:

            if energy_count < 3:
                return 20000 - energy_count * 100
            return SCORE_VETO
        if pokemon.id == Meganium:
            return 18000 if energy_count < 2 else -1
        if pokemon.id == Hydrapple_ex:
            return 16000 if _eff_bench_sc < 2 else -1
        if pokemon.id == Dipplin:
            return 14000 if energy_count < 1 else -1
        if pokemon.id == Applin:
            return 12000 if energy_count < 2 else -1
        if pokemon.id == Tapu_Bulu:
            _tapu_cap_sc = 4
            return 10000 if _eff_bench_sc < _tapu_cap_sc else -1

        return 8000 if energy_count < 1 else -1

    if _active_already_kos and not active and energy_count == 0 \
            and not AGENT_STATE.op_is_crustle_deck and not AGENT_STATE.op_is_cornerstone_deck \
            and not neutralization_zone_active:
        if pokemon.id in NON_ATTACKER_ENERGY_WASTE_IDS:
            return SCORE_VETO
        return {
            Hydrapple_ex: 30000,
            Teal_Mask_Ogerpon_ex: 29000,
            Dipplin: 28000,
            Meganium: 27000,
            Tapu_Bulu: 26000,
        }.get(pokemon.id, 25000)

    _bench_hydra_pre_target = any(
        bp is not None and bp.id in (Dipplin, Applin) and len(bp.energies) < 1
        for bp in (my_state.bench or []))
    if (not AGENT_STATE.op_is_crustle_deck and not AGENT_STATE.op_is_cornerstone_deck
            and not neutralization_zone_active
            and not _active_needs_energy
            and _active_pokemon is not None
            and _active_pokemon.id != Hydrapple_ex
            and _bench_hydra_pre_target):
        if active:
            return SCORE_VETO
        if pokemon.id == Dipplin and energy_count < 1:
            return 24000
        if pokemon.id == Applin and energy_count < 1:
            return 23500

    if active:
        score += 10

        if active_ko_likely:
            _after_energy = energy_count + _grass_attach_unit()
            _after_energy_raw = energy_count + 1

            _can_attack_after = False
            if pokemon.id == Hydrapple_ex:
                _can_attack_after = (_after_energy >= 2)
            elif pokemon.id == Dipplin:
                _can_attack_after = (_after_energy_raw >= 1)
            elif pokemon.id == Teal_Mask_Ogerpon_ex:
                _can_attack_after = (_after_energy >= 3 or _ogerpon_td_manual_lethal)
            elif pokemon.id == Tapu_Bulu:
                _can_attack_after = (_after_energy >= 4)
            elif pokemon.id == Fezandipiti_ex:
                _can_attack_after = (_after_energy >= 3)

            _retreat_cost_pkmn = RETREAT_COST.get(pokemon.id, 1)
            # Effective energy after attaching (Wild Growth doubles Grass):
            # 1 energy on Meganium already pays its retreat cost of 2.
            _can_retreat_after = (_after_energy >= _retreat_cost_pkmn)

            _has_bench_atk_retreat = False
            for _bp in (my_state.bench or []):
                if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex):
                    _has_bench_atk_retreat = True
                    break

            if not _can_attack_after and (not _can_retreat_after or not _has_bench_atk_retreat):
                return score - 100

        effective_energy = energy_count * _grass_mult()

        if pokemon.id == Hydrapple_ex:
            energy_threshold = 2
            if effective_energy < energy_threshold:
                score += 23200
                if op_is_fire_deck:
                    score += 500
                if op_is_aggro_deck or op_is_beedrill_deck:
                    score += 300
            elif energy_count < 2:

                score += 23200
            elif _extra_energy_enables_ko(Hydrapple_ex, energy_count):

                score += 15000
            elif _bench_attacker_ready and not _active_already_kos:

                score += 23200
            else:
                score -= 100
        elif pokemon.id == Dipplin:
            if energy_count < 1:
                score += 23200
                if op_has_ex_immune_active:
                    score += 500
            else:
                score -= 30
        elif pokemon.id == Teal_Mask_Ogerpon_ex:
            if effective_energy < 3:
                score += 23200
            elif energy_count < 3:

                score += 23200
            elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, energy_count):

                score += 15000
            elif (_bench_attacker_ready and not _bench_attacker_needs_energy
                    and not _active_already_kos):

                score += 23200
            else:

                score -= 100
        elif pokemon.id == Tapu_Bulu:

            if energy_count < 4:
                if AGENT_STATE.meganium_in_play:
                    score += 23200
                    if op_has_ex_immune_active:
                        score += 500
                else:
                    score += 15000
            else:
                score -= 80
        elif pokemon.id == Meganium:

            _sylveon_active = (op_state.active and op_state.active[0] is not None
                               and op_state.active[0].id == Sylveon)
            if op_is_drednaw_deck or _sylveon_active:

                _meg_eff = energy_count * _grass_mult()
                if _meg_eff < 4:
                    score += 23200
                else:
                    score -= 100
            elif energy_count < 2:
                score += 23200
            else:
                score -= 500
        elif pokemon.id in (Chikorita, Bayleef):

            _retreat_cost = RETREAT_COST.get(pokemon.id, 1)
            # Wild Growth doubles the basic Grass energy for the retreat.
            _cb_ret_eff = energy_count * _grass_mult()
            if _cb_ret_eff < _retreat_cost:
                score += 23200
            else:
                score -= 500
        elif pokemon.id == Meowth_ex:

            # ACTIVE Meowth ex: we only charge it when the retreat is NECESSARY, that is,
            # when there is a real attacker on the bench to promote. If there is nobody to
            # hand over to, charging it adds nothing and it is demoted.
            if energy_count == 0:
                _has_bench_attacker = False
                for _bp in my_state.bench:
                    if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex):
                        _has_bench_attacker = True
                        break
                if _has_bench_attacker:
                    score += 23200
                else:
                    score -= 500
            else:
                score -= 500
        elif pokemon.id == Fezandipiti_ex:

            _fez_eff = energy_count * _grass_mult()
            _fez_eff_after = energy_count + _grass_attach_unit()
            if _fez_eff >= 3:

                score -= 100
            elif _fez_eff_after >= 3:

                score += 23200
            elif energy_count == 0:

                _has_bench_attacker = False
                for _bp in my_state.bench:
                    if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu):
                        _has_bench_attacker = True
                        break
                if _has_bench_attacker:
                    score += 23200
                else:
                    score += 5000
            else:

                score -= 200
        elif pokemon.id == Pinsir:

            if effective_energy < 2:
                score += 23200
                if op_has_ex_immune_active:
                    score += 500
            else:
                score -= 60

    else:

        if pokemon.id == Teal_Mask_Ogerpon_ex:
            if energy_count < 2:
                score += 400
            elif energy_count < 3:
                score += 250
            elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, energy_count):
                score += 150
            else:
                score -= 100
        elif pokemon.id == Tapu_Bulu:

            if not AGENT_STATE.meganium_in_play:
                score -= 100
            elif op_has_ex_immune_active or op_has_ex_immune_bench:
                if energy_count < 2:
                    score += 350
                else:
                    score -= 80
            elif energy_count < 2:
                score += 100
            else:
                score -= 80
        elif pokemon.id == Hydrapple_ex:

            effective_energy = energy_count * _grass_mult()
            if effective_energy < 2:

                score += 23100
                if op_is_fire_deck:
                    score += 100
                if op_is_aggro_deck or op_is_beedrill_deck:
                    score += 80
            elif energy_count < 2:
                score += 150
                if op_is_fire_deck:
                    score += 100
            elif _extra_energy_enables_ko(Hydrapple_ex, energy_count):
                score += 100
            else:
                score -= 100
        elif pokemon.id == Dipplin:
            if energy_count < 1:
                score += 150
                if op_has_ex_immune_active:
                    score += 80

                if op_is_drednaw_deck:
                    score += 200

                elif op_is_sylveon_deck:
                    score += 150
            else:
                score -= 30
        elif pokemon.id == Applin:

            if energy_count == 0:
                score += 40
            elif energy_count == 1:
                _applin_full_evolve_now = (hand_counts.get(Dipplin, 0) >= 1 and
                                           hand_counts.get(Hydrapple_ex, 0) >= 1)
                if _applin_full_evolve_now and not AGENT_STATE.meganium_in_play:
                    score += 50
                else:
                    score -= 300
            else:
                score -= 400
        elif pokemon.id == Meganium:

            _sylveon_threat = (op_is_sylveon_deck and op_has_ex_immune_active and
                               op_state.active and op_state.active[0] is not None and
                               op_state.active[0].id == Sylveon)
            if op_is_drednaw_deck or _sylveon_threat:
                _meg_eff_bench = energy_count * _grass_mult()
                if _meg_eff_bench < 4:
                    score += 500
                else:
                    score -= 50
            elif energy_count >= 2:
                score -= 100
            elif (has_hydrapple and _active_pokemon is not None and
                  _active_pokemon.id == Hydrapple_ex and energy_count < 1):
                score += 60
            else:
                score -= 50
        elif pokemon.id == Meowth_ex:
            score -= 100
            if op_has_froslass:
                score -= 50
        elif pokemon.id == Fezandipiti_ex:

            _fez_energy_req = 3
            _is_fez_attacker = (AGENT_STATE.plan.attacker >= 1 and
                my_state.bench[AGENT_STATE.plan.attacker - 1] is not None and
                my_state.bench[AGENT_STATE.plan.attacker - 1].id == Fezandipiti_ex)
            if _is_fez_attacker and energy_count < _fez_energy_req:
                score += 300
            elif energy_count < _fez_energy_req and not any(
                p is not None and p.id in (Hydrapple_ex, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Dipplin)
                for p in my_state.bench + list(my_state.active or [])):

                score += 200
            else:
                score -= 100
            if op_has_froslass:
                score -= 50
        elif pokemon.id == Pinsir:

            _pinsir_eff_bench = energy_count * _grass_mult()
            if op_has_ex_immune_active or op_has_ex_immune_bench:
                if _pinsir_eff_bench < 2:
                    score += 350
                else:
                    score -= 60
            elif _pinsir_eff_bench < 2:
                score += 80
            else:
                score -= 60

    return score


__all__ = ['_energy_score_base']
