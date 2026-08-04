"""`evaluate_supporters`, extracted VERBATIM from `agent()` (wave 5).

It used to capture 41 variables of the turn; they now arrive in a context that
is unpacked on entry, with the SAME names, so the body is exactly the one that
was in main.py.
"""

from cg.api import EnergyType
from ptcg.calculo.carta import prize_count_op
from ptcg.calculo.dano import _attacker_base_damage, _bench_attacker_can_ko, _our_effective_damage
from ptcg.calculo.energia import _grass_attach_unit, _grass_mult, _retreat_grass_units
from ptcg.cartas.grupos import EVO_LINES
from ptcg.cartas.ids import ABILITY_IMMUNE_IDS, Abra, Alakazam_ex, Applin, BOSS_PRIORITY_CRUSTLE_GUST, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Crustle_Fighting, Crustle_Grass, Dawn, Dipplin, Drednaw, Dusclops, Duskull, Dwebble_Fighting, Dwebble_Grass, EX_IMMUNE_IDS, EX_PREEVO_IDS, Fezandipiti_ex, Froslass, HIGH_PRIORITY_BENCH_TARGETS, Hydrapple_ex, KEY_BENCH_ATTACKER_IDS, Kadabra, Kirlia, LANA_PLAY_BASE_RECUPERABLE, LANA_PLAY_SIN_DEMANDA, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Munkidori, NONEX_FINAL_PREEVO_IDS, OUR_ABILITY_IDS, OUR_EX_IDS, Pinsir, RETREAT_COST, Ralts, Slowpoke, THREAT_PREEVO_IDS, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Zorua_N
from ptcg.cartas.lineas import _pokemon_injugable, _preevo_de_linea_ex, _supera_en_evolucion
from ptcg.cartas.tablas import card_table
from ptcg.decision.boss_orders import _gust_releva_al_atacante
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.turno.supporters_ctx import CtxEvaluateSupporters  # noqa: F401


def evaluate_supporters(tc):
    # Unpacking of the captures.
    _active_cant_attack_this_turn = tc._active_cant_attack_this_turn
    _plan_de_planta = tc._plan_de_planta
    bench_count = tc.bench_count
    bench_max = tc.bench_max
    budew_on_op_field = tc.budew_on_op_field
    budew_op_index = tc.budew_op_index
    can_switch = tc.can_switch
    estimated_op_damage = tc.estimated_op_damage
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_hydrapple = tc.has_hydrapple
    has_switch_card = tc.has_switch_card
    meowth_ability_lock = tc.meowth_ability_lock
    my_prize = tc.my_prize
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    op_active_dodge_immune = tc.op_active_dodge_immune
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_crustle_bench = tc.op_has_crustle_bench
    op_has_dreepy_line = tc.op_has_dreepy_line
    op_has_dwebble_bench = tc.op_has_dwebble_bench
    op_has_eevee_bench = tc.op_has_eevee_bench
    op_has_ethan_preevo = tc.op_has_ethan_preevo
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_has_froslass = tc.op_has_froslass
    op_has_latias_ex = tc.op_has_latias_ex
    op_has_munkidori = tc.op_has_munkidori
    op_has_snorunt_bench = tc.op_has_snorunt_bench
    op_has_typhlosion = tc.op_has_typhlosion
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_dragapult_dusknoir = tc.op_is_dragapult_dusknoir
    op_is_drednaw_deck = tc.op_is_drednaw_deck
    op_is_gardevoir_deck = tc.op_is_gardevoir_deck
    op_is_slowking_deck = tc.op_is_slowking_deck
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_is_zoroark_deck = tc.op_is_zoroark_deck
    op_prize = tc.op_prize
    op_state = tc.op_state
    state = tc.state
    total_grass = tc.total_grass

    values = {}

    _fez_active_can_attack = False
    if (my_state.active and my_state.active[0] and
            my_state.active[0].id == Fezandipiti_ex):
        _fez_eff_e = len(my_state.active[0].energies) * _grass_mult()
        _fez_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                           and not state.energyAttached)
        _fez_eff_after = _fez_eff_e + (_grass_attach_unit() if _fez_can_attach else 0)
        if _fez_eff_after >= 3:
            _fez_active_can_attack = True

    _op_active_is_crustle = (op_state.active and op_state.active[0] and
                             op_state.active[0].id in (Crustle_Grass, Crustle_Fighting))
    _tapu_can_attack = (field_counts.get(Tapu_Bulu, 0) >= 1 and ESTADO.meganium_in_play and
                        any(bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 2
                            for bp in (my_state.bench + my_state.active)))

    # --- Boss's Orders vs Crustle: our active ex is blocked by Crustle's
    # immunity (we do 0 damage to it). We look on the opposing bench for a
    # target we CAN hit (_our_effective_damage > 0). Boss's takes priority if we
    # can knock that target out OR it cannot retreat (attached energy < its
    # retreat cost, i.e. at most n-1). The only reason NOT to play Boss's is that
    # we cannot knock it out and it also has enough energy to retreat. Immune
    # targets (e.g. another Crustle) return 0 damage and are discarded
    # automatically.
    crustle_gust_worth_it = False
    if (ESTADO.op_is_crustle_deck and op_has_ex_immune_active
            and my_state.active and my_state.active[0] is not None
            and my_state.active[0].id in OUR_EX_IDS):
        our_attacker = my_state.active[0]
        can_attach_grass = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and not state.energyAttached)
        raw_energy = len(our_attacker.energies)
        effective_energy = raw_energy * _grass_mult()
        effective_energy_after_attach = effective_energy + (
            _grass_attach_unit() if can_attach_grass else 0)
        raw_energy_after_attach = raw_energy + (1 if can_attach_grass else 0)
        for gust_target in (op_state.bench or []):
            if gust_target is None:
                continue
            base_damage = _attacker_base_damage(
                our_attacker.id, gust_target, effective_energy_after_attach,
                grass_scale=total_grass,
                teal_self_energy=raw_energy_after_attach,
                bench_count=bench_count)
            if base_damage <= 0:
                continue
            damage = _our_effective_damage(our_attacker, gust_target, base_damage,
                                           ESTADO.meganium_in_play,
                                           neutralization_zone_active)
            if damage <= 0:
                continue  # immune / unattackable target
            can_ko_target = damage >= (gust_target.hp or 0)
            target_cannot_retreat = (
                len(gust_target.energies) < RETREAT_COST.get(gust_target.id, 1))
            if can_ko_target or target_cannot_retreat:
                crustle_gust_worth_it = True
                break

        # NOTE (jul 2026 cycle, MEASURED AND REVERTED): an attempt was made
        # to extend this detector with the ALTERNATIVE KO after retreating
        # (autopsy v2.1 crustle p049 t10: Fez ex stuck in front, a benched
        # Dipplin knocks out the gusted Dwebble 80>=70; `worth_it` came out
        # False and a 4500 Lillie's burned the Supporter with the prize
        # served). It came together with the PER-CANDIDATE mode in target
        # selection (a can_ko evaluates in offensive mode even with the
        # active stuck). The specific line is real (fixture of step 72), but
        # the aggregate measured consistently NEGATIVE in THREE independent
        # runs vs crustle (-1.5 and -2.1 with n=1000, -1.0 with n=2000;
        # ~-1.4 aggregate with n=4000/branch). Hypothesis for the cost: the
        # Dwebble prize BURNS one of the 2 Boss's the endgame needs
        # (win_via_boss_gust) and exposes the promoted body to the
        # counterattack. If retried: require the promoted body to SURVIVE the
        # projected opposing finisher or the prize to close the game, and
        # measure against this same record.

    # FIRE-EXTINGUISHING gust: the target is not worth its prizes but the
    # MACHINE it switches off (Froslass 850, Munkidori 750). The card is noted
    # here and revoked further down if we cannot knock it out THIS turn --
    # `_boss_dmg_to` does not exist yet at this point of the block.
    _bo_apagafuegos = None

    if crustle_gust_worth_it:
        values[Boss_Orders] = BOSS_PRIORITY_CRUSTLE_GUST
    elif _fez_active_can_attack:

        values[Boss_Orders] = 0
    elif (ESTADO.op_is_crustle_deck and _tapu_can_attack and not _op_active_is_crustle and
            op_has_crustle_bench):
        values[Boss_Orders] = 950

    elif (op_is_drednaw_deck and op_state.active and op_state.active[0] is not None
          and op_state.active[0].id == Drednaw):

        _has_shell_bypass_attacker = False
        _meganium_can_attack = False
        _dipplin_can_attack = False
        for _bp_dr in list(my_state.active or []) + list(my_state.bench):
            if _bp_dr is None:
                continue
            _bp_dr_eff = len(_bp_dr.energies) * _grass_mult()
            if _bp_dr.id == Meganium and _bp_dr_eff >= 4:
                _has_shell_bypass_attacker = True
                _meganium_can_attack = True
            elif _bp_dr.id == Dipplin and len(_bp_dr.energies) >= 1:
                _has_shell_bypass_attacker = True
                _dipplin_can_attack = True

        _drednaw_bench_targets = False
        for _op_bp_dr in op_state.bench:
            if _op_bp_dr is not None and _op_bp_dr.id != Drednaw:
                _drednaw_bench_targets = True
                break
        if not _has_shell_bypass_attacker and _drednaw_bench_targets:

            values[Boss_Orders] = 980
        elif _has_shell_bypass_attacker and _drednaw_bench_targets:

            if _meganium_can_attack:
                values[Boss_Orders] = 500
            else:

                values[Boss_Orders] = 850

    elif op_is_sylveon_deck and op_has_eevee_bench:

        values[Boss_Orders] = 850
    elif (op_is_sylveon_deck and op_has_ex_immune_bench and
          not op_has_ex_immune_active):

        _has_nonex_attacker_sylveon = False
        for _bp_sv in list(my_state.active or []) + list(my_state.bench):
            if _bp_sv is None:
                continue
            _bp_sv_eff = len(_bp_sv.energies) * _grass_mult()
            if _bp_sv.id == Tapu_Bulu and _bp_sv_eff >= 4:
                _has_nonex_attacker_sylveon = True
                break
            elif _bp_sv.id == Meganium and _bp_sv_eff >= 4:
                _has_nonex_attacker_sylveon = True
                break
            elif _bp_sv.id == Dipplin and len(_bp_sv.energies) >= 1:
                _has_nonex_attacker_sylveon = True
                break
            elif _bp_sv.id == Pinsir and _bp_sv_eff >= 2:
                _has_nonex_attacker_sylveon = True
                break
        if _has_nonex_attacker_sylveon:
            values[Boss_Orders] = 900
    elif op_has_froslass and not (op_state.active and op_state.active[0] and op_state.active[0].id == Froslass):
        values[Boss_Orders] = 850
        _bo_apagafuegos = Froslass
    elif budew_on_op_field and budew_op_index >= 1:
        values[Boss_Orders] = 800
    elif op_has_snorunt_bench:
        values[Boss_Orders] = 780
    elif op_has_munkidori and not (op_state.active and op_state.active[0] and op_state.active[0].id == Munkidori):
        values[Boss_Orders] = 750
        _bo_apagafuegos = Munkidori
    elif op_has_dwebble_bench:
        values[Boss_Orders] = 740
    elif op_has_eevee_bench:
        values[Boss_Orders] = 750
    # --- EVOLUTION-LINE decks: a gust without a KO requires RELIEF -------
    # The six branches below shared the same defect as the Alakazam one
    # (registro_002 step 20): they paid 690-730 for the mere fact that there
    # was a piece of their line on the bench. Dragapult and Ethan's also
    # required `bench_stage > active_stage`, that is, they preferred bringing
    # up the MOST evolved piece -- exactly the one the opponent wants in front
    # so they can evolve it and attack. Gardevoir/Slowking/Dusknoir/Zoroark did
    # not even compare: seeing the pre-evolution on their bench was enough.
    #
    # None of them required a KO. Now all of them go through
    # `_gust_releva_al_atacante`: without a KO, a gust only costs the opponent
    # a turn if it swaps a body that ATTACKS for one that cannot. The gusts
    # that DO take prizes are scored apart and with the KO already verified:
    # `_bo_deny_evo_target` (965), `_bo_gust_key_bench` (975),
    # `_boss_ko_ex_value` (985) and `_boss_prize_rank`. The per-deck value is
    # kept so the relative order between matchups does not move when the relief
    # DOES exist.
    elif op_has_dreepy_line:
        values[Boss_Orders] = 700 if _gust_releva_al_atacante(op_state) else 0
    elif op_has_typhlosion or op_has_ethan_preevo:
        values[Boss_Orders] = 700 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_gardevoir_deck and any(
        p is not None and p.id in (Ralts, Kirlia) for p in op_state.bench):
        values[Boss_Orders] = 730 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_alakazam_deck:
        # vs Alakazam this branch does NOT invent value for the gust.
        #
        # It used to score 700 for "bring up the highest evolution of the line on
        # their bench" (`_az_best_bench_stage > _az_act_stage`), without requiring
        # a KO. With their bare Fezandipiti ex as the active and four Abra on the
        # bench that was worth 700 and GAVE AWAY the pre-evolution of their ONLY
        # attacking line -- plus a free retreat for the wall (user, registro_002
        # step 20, LOST): the opponent had the Kadabra in hand, evolved the Abra we
        # brought up and attacked with it.
        #
        # The only gust without a KO that pays off in this matchup is the RELIEF of
        # their attacker (`_alakazam_relevo_de_atacante`), but that LIFTS THE VETO
        # (`_boss_regala_linea_alakazam`), it does not buy priority: the engine
        # Night Stretcher -> Meowth ex -> Lillie's competes for the SAME Supporter
        # of the turn (the Last-Ditch fetches one to play it) and that engine is
        # measured (registro_006 step 51). The gusts that do take prizes are scored
        # apart and with a KO required: `_bo_deny_alakazam_line` (965),
        # `_boss_ko_ex_value` (985) and `_boss_prize_rank`.
        values[Boss_Orders] = 0

    elif op_is_slowking_deck and any(
        p is not None and p.id == Slowpoke for p in op_state.bench):
        values[Boss_Orders] = 710 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_dragapult_dusknoir and any(
        p is not None and p.id in (Duskull, Dusclops) for p in op_state.bench):
        values[Boss_Orders] = 700 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_zoroark_deck and any(
        p is not None and p.id == Zorua_N for p in op_state.bench):
        values[Boss_Orders] = 690 if _gust_releva_al_atacante(op_state) else 0
    elif ESTADO.plan.target >= 1:
        values[Boss_Orders] = 650
    elif op_prize <= 2:
        values[Boss_Orders] = 500
    else:
        values[Boss_Orders] = 0

    _bo_active_attack_sufficient = False
    if (hand_counts.get(Boss_Orders, 0) >= 1 and not _fez_active_can_attack
            and op_state.active and op_state.active[0] is not None):
        _bo_atk = my_state.active[0] if my_state.active else None
        _bo_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                      and not state.energyAttached)

        def _boss_dmg_to(_tgt, _wave_bench_override=None):
            if _bo_atk is None or _tgt is None:
                return 0
            _eff = len(_bo_atk.energies) * _grass_mult()
            _eff_after = _eff + (_grass_attach_unit() if _bo_attach else 0)
            _atk_e = len(_bo_atk.energies) + (1 if _bo_attach else 0)
            _d = 0
            if _bo_atk.id == Hydrapple_ex and _eff_after >= 2:
                _d = 30 + 30 * total_grass
            elif _bo_atk.id == Teal_Mask_Ogerpon_ex and _eff_after >= 3:
                _d = 30 + 30 * _atk_e
            elif _bo_atk.id == Tapu_Bulu and _eff_after >= 4:
                _d = 220
            elif _bo_atk.id == Fezandipiti_ex and _eff_after >= 3:
                _d = 100
            elif _bo_atk.id == Meganium and _eff_after >= 4:
                _d = 140
            elif _bo_atk.id == Dipplin and _eff_after >= 1:
                _wave_bench = (bench_count if _wave_bench_override is None
                               else _wave_bench_override)
                _d = 20 * _wave_bench
            elif _bo_atk.id == Pinsir and _eff_after >= 2:
                _d = 100
            if _d <= 0:
                return 0

            # CENTRAL damage evaluator (step 9 of the jul 2026 plan, call-site
            # audit): the inline copy applied ex/ability immunities, the
            # Neutralization Zone, weakness/resistance (except Fezandipiti,
            # fixed damage) and Drednaw, but ignored Sturdy/Resolute Heart
            # (FULL_HP_SURVIVE_IDS: at full HP the damage is capped at hp-10)
            # and Farigiraf ex's Armor Tail (immune to Basic ex) ->
            # `_bo_can_ko_active`/the bench KOs of the gust could declare a
            # FALSE finisher on those bodies and burn the Boss's on a "win"
            # that never happened. The same migration fca07a1 did in ~30
            # places (P0.1).
            return _our_effective_damage(
                _bo_atk, _tgt, _d, ESTADO.meganium_in_play,
                neutralization_zone_active)

        _bo_op_active = op_state.active[0]

        _bo_active_dmg = 0 if op_active_dodge_immune else _boss_dmg_to(_bo_op_active)
        _bo_can_ko_active = (_bo_active_dmg >= (_bo_op_active.hp or 0) and _bo_active_dmg > 0)
        _bo_active_prize = prize_count_op(_bo_op_active) if _bo_can_ko_active else 0

        _bo_best_bench_prize = 0
        _bo_best_bench_dmg = 0
        for _bo_bp in op_state.bench:
            if _bo_bp is None:
                continue
            # log 86339758 step 98: in a Crustle deck we do NOT gust a Dwebble
            # (the selection handler vetoes it with score=-100000), so it must not
            # MOTIVATE playing Boss's Orders either. Without this the game played
            # Boss's chasing a KO on a Dwebble it never gusts, and in the selection
            # it ended up bringing up a LESS jammed Pokemon (Mega Kangaskhan ex with
            # energies) instead of leaving as active the most jammed one (higher NET
            # retreat cost) and attackable.
            if ESTADO.op_is_crustle_deck and _bo_bp.id in (Dwebble_Grass, Dwebble_Fighting):
                continue
            _bo_bp_dmg = _boss_dmg_to(_bo_bp)
            if _bo_bp_dmg > _bo_best_bench_dmg:
                _bo_best_bench_dmg = _bo_bp_dmg
            if _bo_bp_dmg >= (_bo_bp.hp or 0) and _bo_bp_dmg > 0:
                _bo_bp_prize = prize_count_op(_bo_bp)
                if _bo_bp_prize > _bo_best_bench_prize:
                    _bo_best_bench_prize = _bo_bp_prize

        # --- The FIRE-EXTINGUISHING gust requires a KO THIS TURN --------
        # (user, registros/marnie game 1, turns 4 and 6, LOST.) The Froslass
        # (850) and Munkidori (750) branches paid for the mere fact that the
        # piece was on their bench, without checking whether we could kill it.
        # With an active Tapu Bulu at 0-1 energies we gusted the Froslass
        # TWICE and passed the turn without attacking: we burned the turn's
        # Supporter, gave the opponent a free retreat and the Froslass kept
        # dealing 20 per round to each of our bodies with an ability. Without
        # a KO, that gust is worse than playing nothing.
        #
        # It is the same gate `_gust_releva_al_atacante` imposes on the
        # evolution-line decks, but here the criterion is harder (a KO, not
        # relief): the value of these pieces is in SWITCHING THEM OFF, and a
        # live Froslass in the active spot does exactly the same damage as on
        # the bench. It is revoked BEFORE the finisher raises
        # (`_bo_win_via_bench` and company), which can still lift the Boss's
        # for their own reasons.
        if _bo_apagafuegos is not None:
            _bo_apaga_ko = False
            for _bo_ap in (op_state.bench or []):
                if _bo_ap is None or _bo_ap.id != _bo_apagafuegos:
                    continue
                _bo_ap_dmg = _boss_dmg_to(_bo_ap)
                if _bo_ap_dmg > 0 and _bo_ap_dmg >= (_bo_ap.hp or 0):
                    _bo_apaga_ko = True
                    break
            if not _bo_apaga_ko:
                values[Boss_Orders] = 0

        _bo_dipplin_combo = False
        _OUR_BASICS_COMBO = (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                             Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir)
        if (_bo_atk is not None and _bo_atk.id == Dipplin
                and (len(_bo_atk.energies) + (1 if _bo_attach else 0)) >= 1
                and bench_count < 5
                and any(hand_counts.get(_b, 0) >= 1 for _b in _OUR_BASICS_COMBO)):
            _combo_bench = bench_count + 1
            for _bo_cp in op_state.bench:
                if _bo_cp is None:
                    continue
                if (_bo_cp.id not in HIGH_PRIORITY_BENCH_TARGETS
                        and _bo_cp.id not in THREAT_PREEVO_IDS):
                    continue
                _cp_hp = _bo_cp.hp or 0
                _cur_dmg = _boss_dmg_to(_bo_cp)
                _boost_dmg = _boss_dmg_to(_bo_cp, _combo_bench)
                _cur_ko = (_cur_dmg >= _cp_hp and _cur_dmg > 0)
                _boost_ko = (_boost_dmg >= _cp_hp and _boost_dmg > 0)
                if _boost_ko and not _cur_ko:
                    _bo_dipplin_combo = True
                    break
        if _bo_dipplin_combo:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 960)
            values['_boss_dipplin_combo'] = True

        _bo_win_via_bench = (_bo_best_bench_prize > 0
                             and _bo_best_bench_prize >= my_prize
                             and not (_bo_can_ko_active
                                      and my_prize <= prize_count_op(_bo_op_active)))
        if _bo_win_via_bench:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 990)

            values['_boss_win_via_bench'] = True

        # Win via RETREAT+PROMOTE (user, registro_012 p241 vs Iono, WON): the
        # current active does NOT knock out the bench target, but a BENCHED
        # attacker (Hydrapple ex: Syrup Storm scales with the TOTAL Grass on the
        # field, not with its own energy) DOES knock it out after RETREATING the
        # active, and that KO gives us the prizes to WIN. The previous detection
        # only looked at the CURRENT active's attack; that is why the game did not
        # "see" the finisher and played Lana's Aid instead of Boss's Orders.
        if (not _bo_win_via_bench and my_prize >= 1):
            _bo_wr_active = my_state.active[0] if my_state.active else None
            _bo_wr_switch = hand_counts.get(1123, 0) >= 1
            _bo_wr_cost = 0 if _bo_wr_switch else (
                RETREAT_COST.get(_bo_wr_active.id, 1)
                if _bo_wr_active is not None else 1)
            if (_bo_wr_active is not None
                    and (_bo_wr_switch
                         or len(_bo_wr_active.energies) >= _bo_wr_cost)):
                _bo_wr_grass_after = max(
                    0, total_grass - _retreat_grass_units(_bo_wr_cost))
                for _bo_wr_tgt in op_state.bench:
                    if _bo_wr_tgt is None:
                        continue
                    if (ESTADO.op_is_crustle_deck
                            and _bo_wr_tgt.id in (Dwebble_Grass, Dwebble_Fighting)):
                        continue
                    if prize_count_op(_bo_wr_tgt) < my_prize:
                        continue
                    if _bench_attacker_can_ko(
                            my_state, _bo_wr_tgt, ESTADO.meganium_in_play, total_grass,
                            bench_count, _bo_wr_grass_after,
                            neutralization_zone_active):
                        _bo_win_via_bench = True
                        values[Boss_Orders] = max(values.get(Boss_Orders, 0), 990)
                        values['_boss_win_via_bench'] = True
                        break

        _bo_deny_evo_target = False
        _bo_ko_active_wins = (_bo_can_ko_active
                              and my_prize <= prize_count_op(_bo_op_active))

        _bo_cur_act = my_state.active[0] if my_state.active else None
        _bo_de_switch = hand_counts.get(1123, 0) >= 1
        _bo_de_can_retreat = False
        _bo_de_grass_after = total_grass
        if _bo_cur_act is not None:
            _bo_de_rc = RETREAT_COST.get(_bo_cur_act.id, 1)
            if _bo_de_switch or len(_bo_cur_act.energies) >= _bo_de_rc:
                _bo_de_can_retreat = True
                _bo_de_grass_after = max(
                    0, total_grass - (0 if _bo_de_switch
                                      else _retreat_grass_units(_bo_de_rc)))
        if not _bo_win_via_bench and not _bo_ko_active_wins:
            for _bo_pe in op_state.bench:
                if _bo_pe is None:
                    continue
                # log 86339758 step 98: Dwebble is vetoed as a gust target in a
                # Crustle deck, it cannot motivate denying the line.
                if ESTADO.op_is_crustle_deck and _bo_pe.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue

                _bo_pe_is_threat = _bo_pe.id in THREAT_PREEVO_IDS
                _bo_pe_is_ex_preevo_energized = (
                    _bo_pe.id in EX_PREEVO_IDS
                    and _bo_pe.id not in NONEX_FINAL_PREEVO_IDS
                    and len(_bo_pe.energies) >= 1
                    and _bo_can_ko_active
                    and prize_count_op(_bo_op_active) == prize_count_op(_bo_pe))
                # Deny an EX line from the bench EVEN IF the pre-evolution has NO
                # energy: when the opposing active is a harmless wall with no
                # energy (knocking it out cuts no threat) and on the bench there
                # is a pre-evolution of an ex line (e.g. Abra -> Alakazam ex,
                # Ralts -> Gardevoir ex) that we can knock out, it is better to
                # gust it with Boss's to stop it evolving into a 2-prize
                # attacker, even if the immediate prize is the same as knocking
                # out the wall.
                _bo_pe_is_ex_line_vs_wall = (
                    _bo_pe.id in EX_PREEVO_IDS
                    and _bo_pe.id not in NONEX_FINAL_PREEVO_IDS
                    and _bo_can_ko_active
                    and len(_bo_op_active.energies) == 0
                    and prize_count_op(_bo_op_active) <= 1
                    and _bo_op_active.id not in EX_PREEVO_IDS
                    and _bo_op_active.id not in THREAT_PREEVO_IDS
                    and _bo_op_active.id not in KEY_BENCH_ATTACKER_IDS)
                # Deny an EX line when the opposing active is ANOTHER pre-evolution
                # of the SAME chain but a BARE wall (0 energy) and on the bench
                # there is a CHARGED ex pre-evolution (closer to its attacker).
                # `_bo_pe_is_ex_line_vs_wall` does not cover this case because it
                # requires the active NOT to be in EX_PREEVO_IDS, but in the Marnie
                # line (Impidimp -> Morgrem -> Grimmsnarl ex) both Impidimp and
                # Morgrem are in EX_PREEVO_IDS. Knocking out the bare Impidimp in
                # the active spot (replaceable, 1 prize) yields the same as
                # gusting+knocking out the charged Morgrem (1 prize) BUT lets
                # Morgrem evolve into Grimmsnarl ex; gusting the Morgrem cuts the
                # line of their main attacker (user, log 86402439 step 100).
                _bo_pe_is_energized_preevo_vs_bare_wall = (
                    _bo_pe_is_ex_preevo_energized
                    and len(_bo_op_active.energies) == 0)
                # Deny an EX line when the opposing active is OUTSIDE that line
                # (knocking it out does not touch it), even if it HAS energy. It
                # generalises `_bo_pe_is_energized_preevo_vs_bare_wall` (which
                # requires an active with 0 energy): with EQUAL prizes,
                # gusting+knocking out the charged ex pre-evolution on the bench
                # (Morgrem -> Grimmsnarl ex) cuts the main attacker, while knocking
                # out an active OUTSIDE the line (Munkidori, a 1-prize support)
                # yields the same prize but leaves the evolution alive. The active
                # must be an UNRELATED target: not an ex pre-evolution, not a threat
                # pre-evolution, not a key benched attacker (if the active were
                # already of that class, knocking it out would already contribute,
                # and the prize comparison below decides). The equality of prizes is
                # already guaranteed by `_bo_pe_is_ex_preevo_energized`
                # (prize_count active == prize_count pre-evolution). (user,
                # registro_004 step 47 vs Marnie: active Munkidori 1e + charged
                # Morgrem on the bench; the game played Dawn/stadium instead of
                # Boss's on the Morgrem.)
                _bo_pe_is_energized_preevo_off_line = (
                    _bo_pe_is_ex_preevo_energized
                    and _bo_op_active.id not in EX_PREEVO_IDS
                    and _bo_op_active.id not in THREAT_PREEVO_IDS
                    and _bo_op_active.id not in KEY_BENCH_ATTACKER_IDS)
                # BENCH STEP (user, registro_008 step 136 vs Marnie's
                # Grimmsnarl ex, LOST): the exact mirror of the STAGE VETO
                # further down. Inside a Basic -> Stage 1 -> Stage 2 line the
                # HIGHEST reachable stage is ALWAYS knocked out; when the one
                # higher up is on the BENCH, that stage is only reachable by
                # GUSTING it. Active Marnie's Impidimp (Basic) and Morgrem
                # (Stage 1, 2 energies) on the bench: both yield 1 prize and
                # the Hydrapple ex knocks out either, but knocking out the
                # Impidimp lets the Morgrem evolve into Marnie's Grimmsnarl ex
                # (Stage 2, 320 HP, 2 prizes, Punk Up searches 5 energies);
                # gusting the Morgrem forces the opponent to rebuild BOTH
                # steps. The three exceptions above did not cover this board:
                # `vs_bare_wall` requires an active with 0 energy (the Impidimp
                # had 1) and `off_line` requires an active UNRELATED to the
                # line (the Impidimp is its own pre-evolution).
                # Deck-agnostic by double entry: the STAGE comes from the card
                # data (`_supera_en_evolucion`) and "it is worth the Boss's"
                # comes from the chain ending in an ex (`_preevo_de_linea_ex`),
                # not from per-deck lists. The equality of prizes is required
                # explicitly here because this predicate does not go through
                # `_bo_pe_is_ex_preevo_energized` (the pre-evolution's energy
                # is irrelevant when what cuts the line is the STAGE).
                _bo_pe_outranks_active = (
                    _bo_can_ko_active
                    and _supera_en_evolucion(_bo_pe, _bo_op_active)
                    and prize_count_op(_bo_op_active) == prize_count_op(_bo_pe)
                    and _preevo_de_linea_ex(_bo_pe.id))
                if not (_bo_pe_is_threat or _bo_pe_is_ex_preevo_energized
                        or _bo_pe_is_ex_line_vs_wall
                        or _bo_pe_outranks_active):
                    continue
                _bo_pe_dmg = _boss_dmg_to(_bo_pe)
                _bo_pe_ko = (_bo_pe_dmg >= (_bo_pe.hp or 0) and _bo_pe_dmg > 0)

                if not _bo_pe_ko and _bo_de_can_retreat:
                    _bo_pe_ko = _bench_attacker_can_ko(
                        my_state, _bo_pe, ESTADO.meganium_in_play, total_grass,
                        bench_count, _bo_de_grass_after,
                        neutralization_zone_active)
                if _bo_pe_ko:
                    # With a THREAT PRE-EVOLUTION (Duraludon->Archaludon ex) that
                    # we can knock out, knocking out the active is only preferred
                    # if it yields STRICTLY more prizes; with EQUAL prizes gusting
                    # the pre-evolution is better (same prize and it REMOVES the
                    # deck's attacker). For the other targets the >= criterion is
                    # kept (user, registro_007 p78 vs Archaludon: a non-ex
                    # Cinderace active = 1 prize, same as Duraludon; the game
                    # knocked out the Cinderace instead of gusting Duraludon).
                    # EXCEPTION (user, registro_006 step 75 vs Archaludon): if the
                    # opposing ACTIVE is ALSO a THREAT pre-evolution (Duraludon)
                    # that we can knock out and is equally or MORE developed (>=
                    # energy) than the benched pre-evolution, KNOCKING OUT the
                    # active already removes a threat of the SAME class for the
                    # SAME prize, and it is also the more dangerous body (more
                    # energy + tools such as Hero's Cape). Gusting a weaker benched
                    # copy wastes the Boss's and leaves the big Duraludon alive: we
                    # prefer attacking the active (dominates=True even though the
                    # prizes are equal).
                    _bo_active_is_threat_ko = (
                        _bo_op_active.id in THREAT_PREEVO_IDS
                        and len(_bo_op_active.energies) >= len(_bo_pe.energies))
                    _bo_active_prize_dominates = (
                        (prize_count_op(_bo_op_active) > prize_count_op(_bo_pe)
                         or _bo_active_is_threat_ko)
                        if _bo_pe_is_threat
                        else prize_count_op(_bo_op_active) >= prize_count_op(_bo_pe))
                    # STAGE VETO (user, registro_008 step 93 vs Cynthia's
                    # Garchomp ex, WON with a mistake): the opposing ACTIVE is a
                    # MORE EVOLVED link of the SAME line as the benched
                    # pre-evolution (active Cynthia's Gabite Stage 1 BARE, bench
                    # Cynthia's Gible Basic with 1 energy). Knocking out the
                    # Gabite takes the same prize and cuts the line ONE STEP
                    # HIGHER UP -- and it is also FREE, it spends neither the
                    # Boss's nor the turn's Supporter. This veto overrides the
                    # three exceptions: here `_energized_preevo_vs_bare_wall`
                    # fired (designed for the OPPOSITE case of the Marnie line:
                    # active bare BASIC Impidimp, bench charged STAGE 1 Morgrem),
                    # which only looked at the active's energy and not at its
                    # STAGE.
                    _bo_active_outranks_pe = (
                        _supera_en_evolucion(_bo_op_active, _bo_pe)
                        and prize_count_op(_bo_op_active) >= prize_count_op(_bo_pe))
                    if (_bo_can_ko_active
                            and (_bo_active_outranks_pe
                                 or (_bo_active_prize_dominates
                                     and not _bo_pe_is_ex_line_vs_wall
                                     and not _bo_pe_is_energized_preevo_vs_bare_wall
                                     and not _bo_pe_is_energized_preevo_off_line
                                     and not _bo_pe_outranks_active))):
                        continue
                    _bo_deny_evo_target = True
                    break
        if _bo_deny_evo_target:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 965)
            values['_boss_deny_evo'] = True

        # --- Cutting the Alakazam line by gusting its benched pre-evolution ---
        # Rule (user, registro 010, step 64 vs Alakazam, WON): when the opposing
        # active does NOT belong to the Alakazam line (Abra 741 -> Kadabra
        # 742 -> Alakazam 743) -- e.g. a Dunsparce acting as a wall -- and on the
        # BENCH there is a pre-evolution of that line our active can knock out,
        # the priority is to GUST IT with Boss's Orders and knock it out to cut
        # the development of the Psychic attacker. Attacking the wall in the
        # active spot does not touch the line; gusting+knocking out the
        # pre-evolution yields the same prize BUT stops Alakazam. Target priority
        # Kadabra > Abra > Alakazam (chosen by the selection handler, ~L2300).
        # NOTE: this does NOT contradict [[boss-no-gustear-preevo-linea-no-ex]]:
        # there the opposing active WAS part of the Alakazam line (attacking it
        # already hits it), so gusting a benched copy is useless. Here the active
        # is OUTSIDE the line, which is why the condition requires
        # `_bo_op_active.id not in` the chain. Since Abra/Kadabra are
        # NONEX_FINAL_PREEVO (Alakazam is 1 prize) the generic deny-evo ignores
        # them; this rule covers them only in the "active outside the line" case.
        _bo_deny_alakazam_line = False
        if (op_is_alakazam_deck
                and _bo_op_active.id not in (Abra, Kadabra, Alakazam_ex)):
            for _bo_al in op_state.bench:
                if _bo_al is None or _bo_al.id not in (Abra, Kadabra, Alakazam_ex):
                    continue
                _bo_al_dmg = _boss_dmg_to(_bo_al)
                _bo_al_ko = (_bo_al_dmg >= (_bo_al.hp or 0) and _bo_al_dmg > 0)
                if not _bo_al_ko and _bo_de_can_retreat:
                    _bo_al_ko = _bench_attacker_can_ko(
                        my_state, _bo_al, ESTADO.meganium_in_play, total_grass,
                        bench_count, _bo_de_grass_after,
                        neutralization_zone_active)
                if _bo_al_ko:
                    _bo_deny_alakazam_line = True
                    break
        if _bo_deny_alakazam_line:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 965)
            values['_boss_deny_alakazam_line'] = True

        # --- Hunting the deck's key Pokemon on the bench ------------------
        # If the opposing active is NOT a key Pokemon (e.g. a Hop's Snorlax with
        # no energy) but on the bench there is a key attacker of the deck (Hop's
        # Trevenant / Phantump) we can knock out with our active, the right play
        # is to gust that attacker instead of settling for knocking out the
        # harmless active (same prize value). We set the flag so the "attacking
        # is enough" rule does not cancel the Boss's Orders further down. The
        # specific target is chosen by the adjustments of _AJUSTES_GUST_OFENSIVO.
        _bo_gust_key_bench = False
        if (_bo_op_active.id not in KEY_BENCH_ATTACKER_IDS
                and not _bo_win_via_bench and not _bo_deny_evo_target
                and not _bo_ko_active_wins):
            for _bo_kp in op_state.bench:
                if _bo_kp is None or _bo_kp.id not in KEY_BENCH_ATTACKER_IDS:
                    continue
                _bo_kp_dmg = _boss_dmg_to(_bo_kp)
                _bo_kp_ko = (_bo_kp_dmg >= (_bo_kp.hp or 0) and _bo_kp_dmg > 0)
                if not _bo_kp_ko and _bo_de_can_retreat:
                    _bo_kp_ko = _bench_attacker_can_ko(
                        my_state, _bo_kp, ESTADO.meganium_in_play, total_grass,
                        bench_count, _bo_de_grass_after,
                        neutralization_zone_active)
                if _bo_kp_ko:
                    _bo_gust_key_bench = True
                    break
        if _bo_gust_key_bench:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 975)
            values['_boss_gust_key_bench'] = True

        if op_active_dodge_immune and not _bo_win_via_bench:
            if _bo_best_bench_prize > 0:
                values[Boss_Orders] = max(values.get(Boss_Orders, 0), 985)
                values['_boss_dodge_redirect'] = True
            elif _bo_best_bench_dmg > 0:
                values[Boss_Orders] = max(values.get(Boss_Orders, 0), 970)
                values['_boss_dodge_redirect'] = True

        _bo_bench_prize_beats_active = False
        if _bo_best_bench_prize > _bo_active_prize and _bo_best_bench_prize > 0:

            _bo_active_prize_val = prize_count_op(_bo_op_active)
            _bo_trade_down = (not _bo_can_ko_active and _bo_active_dmg > 0
                              and _bo_active_prize_val > _bo_best_bench_prize)
            if not _bo_trade_down:
                _bo_bench_prize_beats_active = True
                _bo_prize_diff = _bo_best_bench_prize - _bo_active_prize
                values[Boss_Orders] = max(values.get(Boss_Orders, 0),
                                          960 + 10 * _bo_prize_diff)

        if _bo_can_ko_active and len(_bo_op_active.energies) == 0:
            for _bo_bp in op_state.bench:
                if (_bo_bp is not None and _bo_bp.id == _bo_op_active.id
                        and len(_bo_bp.energies) >= 1):
                    _bo_mirror_dmg = _boss_dmg_to(_bo_bp)
                    if _bo_mirror_dmg >= (_bo_bp.hp or 0) and _bo_mirror_dmg > 0:
                        values[Boss_Orders] = max(values.get(Boss_Orders, 0), 955)
                        break

        # --- DEFENSIVE Boss's Orders (avoiding the lethal KO) -------------
        # If our active is going to be knocked out next turn (the opponent's
        # estimated damage >= our HP) and we canNOT knock out the opposing
        # active nor win through the bench, the right play may be to gust a
        # harmless Pokemon from the opposing bench: one that canNOT attack next
        # turn (not even with one extra energy) and canNOT retreat (energy <
        # retreat cost), so that the opponent loses their lethal attack. All the
        # rest of the Boss's scoring is offensive, so without this the "attacking
        # is enough" rule (below) cancels it and the game is lost.
        # RULE (user): if our ACTIVE is a Basic or a Stage 1 (e.g. Applin,
        # Dipplin, Bayleef) that will be defeated next turn, play Boss's Orders
        # ONLY if we can bring up a Pokemon from the opposing bench that CANNOT
        # defeat our active. The specific choice of target is made by the
        # selection handler (the current Boss's Orders rules).
        _bo_defensive_gust = False
        _bo_active_basic_or_s1 = (
            _bo_atk is not None
            and len(getattr(_bo_atk, 'preEvolution', []) or []) <= 1)
        _bo_my_active_data = card_table.get(_bo_atk.id) if _bo_atk is not None else None
        _bo_my_active_weak = getattr(_bo_my_active_data, 'weakness', None) if _bo_my_active_data else None
        if (_bo_atk is not None and _bo_active_basic_or_s1
                and estimated_op_damage > 0
                and estimated_op_damage >= (_bo_atk.hp or 0)
                and not _bo_can_ko_active and not _bo_win_via_bench
                and not _bo_deny_evo_target and not _bo_gust_key_bench
                and not _bo_dipplin_combo):
            for _bo_dg in op_state.bench:
                if _bo_dg is None:
                    continue
                _bo_dg_e = len(_bo_dg.energies)
                _bo_dg_rc = RETREAT_COST.get(_bo_dg.id, 1)
                if _bo_dg_e >= _bo_dg_rc:
                    continue  # it could retreat and put the lethal attacker back
                _bo_dg_d = card_table.get(_bo_dg.id)
                # MAXIMUM damage this benched Pokemon would do to OUR active next
                # turn (assuming they attach 1 energy to it).
                _bo_dg_dmg_vs_us = 0
                if _bo_dg_d and getattr(_bo_dg_d, 'attacks', None):
                    _bo_dg_avail = _bo_dg_e + 1
                    for _bo_dg_atk in _bo_dg_d.attacks:
                        _bo_dg_dmg = getattr(_bo_dg_atk, 'damage', None)
                        if _bo_dg_dmg is None or _bo_dg_dmg <= 0:
                            continue
                        _bo_dg_cost = getattr(_bo_dg_atk, 'cost', None)
                        _bo_dg_need = 0
                        if _bo_dg_cost is not None:
                            try:
                                _bo_dg_need = len(_bo_dg_cost)
                            except TypeError:
                                try:
                                    _bo_dg_need = int(_bo_dg_cost)
                                except (TypeError, ValueError):
                                    _bo_dg_need = 0
                        if _bo_dg_need <= _bo_dg_avail:
                            _bo_dg_dmg_vs_us = max(_bo_dg_dmg_vs_us, _bo_dg_dmg)
                # apply OUR active's weakness to the benched Pokemon's type
                if (_bo_my_active_weak is not None and _bo_dg_d is not None
                        and _bo_dg_dmg_vs_us > 0
                        and _bo_my_active_weak == getattr(_bo_dg_d, 'energyType', None)):
                    _bo_dg_dmg_vs_us *= 2
                # VALID target = this Pokemon canNOT defeat our active
                if _bo_dg_dmg_vs_us < (_bo_atk.hp or 0):
                    _bo_defensive_gust = True
                    break
        if _bo_defensive_gust:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 940)
            values['_boss_defensive_gust'] = True

        if (_bo_can_ko_active and not _bo_win_via_bench and not _bo_deny_evo_target
                and not _bo_dipplin_combo and not _bo_gust_key_bench
                and not _bo_deny_alakazam_line):
            _bo_active_prize_now = prize_count_op(_bo_op_active)
            if my_prize <= _bo_active_prize_now:
                values[Boss_Orders] = 0
            elif (_bo_active_prize_now >= _bo_best_bench_prize
                    and len(_bo_op_active.energies) > 0):
                values[Boss_Orders] = 0
            elif (_bo_op_active.id == Crustle_Grass
                    and _bo_best_bench_prize <= _bo_active_prize_now
                    and len(_bo_op_active.energies) > 0):

                values[Boss_Orders] = 0

        # "ATTACKING THE ACTIVE IS ENOUGH" -- but CHIP damage is not a prize
        # (user, registro_020 step 122 vs Crustle, LOST). There the opposing
        # active was a 150 HP Crustle and Meganium did 140 to it: the remainder
        # (10) fell below the threshold of 100 and this rule cancelled the
        # Boss's... which was worth 970 because on the BENCH there was another
        # Crustle at **30 HP** with two energies, a prize served up for the same
        # Solar Beam. Chip damage takes nothing and the opponent simply rotates
        # the wounded body to the bench (which is what they did). That is why the
        # rule yields -- as it already yielded to deny_evo / key_bench /
        # defensive -- when the gust takes a prize that attacking the active does
        # NOT (`_bo_bench_prize_beats_active`, exactly the same predicate that
        # gave it the 960+ above).
        if (_bo_active_dmg > 0 and not _bo_win_via_bench and not _bo_deny_evo_target
                and not _bo_dipplin_combo and not _bo_gust_key_bench
                and not _bo_defensive_gust and not _bo_deny_alakazam_line
                and not _bo_bench_prize_beats_active):
            _bo_active_remaining = (_bo_op_active.hp or 0) - _bo_active_dmg
            if _bo_can_ko_active or _bo_active_remaining <= 100:
                values[Boss_Orders] = 0
                _bo_active_attack_sufficient = True

                values['_active_attack_sufficient'] = True

    if _active_cant_attack_this_turn and hand_counts.get(Boss_Orders, 0) >= 1:

        _boss_ko_ex_value = 0
        _boss_ko_energy_value = 0

        _our_attackers_info = []
        for _idx_ba, _our_p in enumerate(list(my_state.active or []) + list(my_state.bench)):
            if _our_p is None:
                continue

            if _idx_ba != 0 and not can_switch:
                continue
            _our_dmg = 0
            _our_eff_e = len(_our_p.energies) * _grass_mult()

            _can_attach_ba = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                              and not state.energyAttached)
            _our_eff_after = _our_eff_e + (_grass_attach_unit() if _can_attach_ba else 0)

            if _our_p.id == Hydrapple_ex and _our_eff_after >= 2:
                _our_dmg = 30 + 30 * total_grass
            elif _our_p.id == Dipplin and _our_eff_after >= 1:
                _our_dmg = 20 * bench_count
            elif _our_p.id == Teal_Mask_Ogerpon_ex and _our_eff_after >= 3:
                _our_dmg = 30 + 30 * (len(_our_p.energies) + (1 if _can_attach_ba else 0))
            elif _our_p.id == Tapu_Bulu and _our_eff_after >= 4:
                _our_dmg = 220
            elif _our_p.id == Fezandipiti_ex and _our_eff_after >= 3:
                _our_dmg = 100
            elif _our_p.id == Meganium and _our_eff_after >= 4:
                _our_dmg = 140
            elif _our_p.id == Pinsir and _our_eff_after >= 2:
                _our_dmg = 100
            elif _our_p.id == Bayleef and _our_eff_after >= 2:
                _our_dmg = 60
            elif _our_p.id == Chikorita and _our_eff_after >= 1:
                _our_dmg = 30

            if _our_dmg > 0:
                _our_attackers_info.append((_our_p, _our_dmg))

        for _op_bp in op_state.bench:
            if _op_bp is None:
                continue
            _op_data_b = card_table.get(_op_bp.id)
            _is_ex_target = (_op_data_b and getattr(_op_data_b, 'ex', False))
            _is_stage2_target = (_op_data_b and getattr(_op_data_b, 'stage2', False))
            _op_bench_energy = len(_op_bp.energies)

            for _atk_p, _atk_dmg in _our_attackers_info:
                _eff_dmg = _atk_dmg

                if _atk_p.id != Fezandipiti_ex and _op_data_b:
                    if _op_data_b.weakness == EnergyType.GRASS:
                        _eff_dmg *= 2
                    elif _op_data_b.resistance == EnergyType.GRASS:
                        _eff_dmg -= 30

                _atk_is_ex = (_atk_p.id in OUR_EX_IDS)
                if _op_bp.id in EX_IMMUNE_IDS and _atk_is_ex:
                    _eff_dmg = 0

                if _op_bp.id in ABILITY_IMMUNE_IDS and _atk_p.id in OUR_ABILITY_IDS:
                    _eff_dmg = 0

                if _op_bp.id == Drednaw and _eff_dmg >= 200:
                    _eff_dmg = 0

                if _eff_dmg >= _op_bp.hp:

                    if _is_ex_target or _is_stage2_target:
                        _boss_ko_ex_value = max(_boss_ko_ex_value, 985)
                    elif _op_bench_energy >= 1:
                        _boss_ko_energy_value = max(_boss_ko_energy_value, 970)

        if _boss_ko_ex_value > 0:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), _boss_ko_ex_value)
        elif _boss_ko_energy_value > 0:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), _boss_ko_energy_value)
        else:

            _op_active_pkmn = op_state.active[0] if op_state.active else None
            _op_active_stuck = False
            if _op_active_pkmn is not None:
                _op_active_rc = RETREAT_COST.get(_op_active_pkmn.id, 0)
                _op_active_energy_cnt = len(_op_active_pkmn.energies)
                _op_active_diff = _op_active_rc - _op_active_energy_cnt
                if _op_active_diff >= 2:
                    _op_active_stuck = True

            if _op_active_stuck:

                if values.get(Boss_Orders, 0) <= 0:
                    values[Boss_Orders] = 0
            else:

                _stall_threshold = 1 if _op_active_rc == 0 else 2
                _best_stall_diff = 0
                _has_stall_target = False
                for _bps in op_state.bench:
                    if _bps is not None:
                        _rc = RETREAT_COST.get(_bps.id, 0)
                        _bps_energy = len(_bps.energies)
                        _diff = _rc - _bps_energy
                        if _diff >= _stall_threshold:

                            if op_has_latias_ex:
                                _cd = card_table.get(_bps.id)
                                if (_cd and not getattr(_cd, 'stage1', False)
                                        and not getattr(_cd, 'stage2', False)):
                                    continue
                            if _diff > _best_stall_diff:
                                _best_stall_diff = _diff
                                _has_stall_target = True

                if _has_stall_target:

                    if _best_stall_diff >= 2:
                        stall_val = 975
                    else:
                        stall_val = 900
                    values[Boss_Orders] = max(values.get(Boss_Orders, 0), stall_val)
                elif values.get(Boss_Orders, 0) <= 0:
                    values[Boss_Orders] = 0

        # RULE (user, log 86507974 step 141): ONLY vs a Crustle deck. If our
        # active canNOT attack this turn, play Boss's Orders for defensive
        # reasons only when the opposing ACTIVE is an imminent threat: it can
        # attack us next turn or it is only 1 energy short of doing so
        # (current_energy + 1 >= the minimum cost of an attack of theirs with
        # damage). If it needs 2 or more energies (e.g. Mega Kangaskhan ex with
        # 1 energy and an attack costing 3) there is no attack to neutralise, so
        # we do not spend the supporter. It does not apply if there is already a
        # real offensive reason (a KO on a bench target) nor in the Crustle
        # immunity gust.
        if (ESTADO.op_is_crustle_deck and not crustle_gust_worth_it
                and _boss_ko_ex_value <= 0 and _boss_ko_energy_value <= 0):
            _boc_active = op_state.active[0] if op_state.active else None
            _boc_imminent = False
            if _boc_active is not None:
                _boc_energy = len(_boc_active.energies)
                _boc_min_cost = None
                _boc_data = card_table.get(_boc_active.id)
                if _boc_data and getattr(_boc_data, 'attacks', None):
                    for _boc_atk in _boc_data.attacks:
                        _boc_dmg = getattr(_boc_atk, 'damage', None)
                        if _boc_dmg is None or _boc_dmg <= 0:
                            continue
                        _boc_cost = getattr(_boc_atk, 'cost', None)
                        _boc_need = 0
                        if _boc_cost is not None:
                            try:
                                _boc_need = len(_boc_cost)
                            except TypeError:
                                try:
                                    _boc_need = int(_boc_cost)
                                except (TypeError, ValueError):
                                    _boc_need = 0
                        if _boc_min_cost is None or _boc_need < _boc_min_cost:
                            _boc_min_cost = _boc_need
                if (_boc_min_cost is not None
                        and _boc_energy + 1 >= _boc_min_cost):
                    _boc_imminent = True
            if not _boc_imminent:
                values[Boss_Orders] = 0

    if op_has_ability_immune_active and ESTADO.plan.target >= 1:

        _attacker_ready = (ESTADO.plan.attacker >= 0 and not ESTADO.plan.energy)
        _attacker_ready_with_attach = (ESTADO.plan.attacker >= 0 and ESTADO.plan.energy and
                                       hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                       not state.energyAttached)
        if _attacker_ready or _attacker_ready_with_attach:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 980)
    elif op_has_ability_immune_active and len(op_state.bench) >= 1:

        _has_non_ability_attacker_ready = False
        _ATK_REQS_BOSS = {
            Tapu_Bulu: 4, Dipplin: 1, Bayleef: 2, Chikorita: 1, Applin: 1,
            Pinsir: 2,
        }
        for _bp in (list(my_state.active or []) + list(my_state.bench)):
            if _bp is not None and _bp.id not in OUR_ABILITY_IDS:
                _req = _ATK_REQS_BOSS.get(_bp.id, 999)
                _eff = len(_bp.energies) * _grass_mult()

                if _eff >= _req:
                    _has_non_ability_attacker_ready = True
                    break
                elif (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                      not state.energyAttached):
                    _eff_after = _eff + _grass_attach_unit()
                    if _eff_after >= _req:
                        _has_non_ability_attacker_ready = True
                        break
        if _has_non_ability_attacker_ready:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 960)

    if not ESTADO.meganium_in_play and not has_hydrapple:
        values[Dawn] = 900
    elif not ESTADO.meganium_in_play:
        values[Dawn] = 800
    elif not has_hydrapple:
        values[Dawn] = 700
    else:
        values[Dawn] = 200

    hand_size = len(my_state.hand) if my_state.hand else 0

    _remaining_plays = 0
    if hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached:
        _remaining_plays += 1
    if bench_count < 5:
        for _pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex):
            if hand_counts.get(_pid, 0) >= 1:
                _remaining_plays += 1
    if hand_counts.get(Meganium, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:
        _remaining_plays += 1
    if hand_counts.get(Bayleef, 0) >= 1 and field_counts.get(Chikorita, 0) >= 1:
        _remaining_plays += 1
    if hand_counts.get(Hydrapple_ex, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:
        _remaining_plays += 1
    if hand_counts.get(Dipplin, 0) >= 1 and field_counts.get(Applin, 0) >= 1:
        _remaining_plays += 1

    if my_prize == 6:
        values[Lillie_Determination] = 750
        if hand_size <= 3:
            values[Lillie_Determination] = 800
    elif hand_size <= 2:
        values[Lillie_Determination] = 800
    elif hand_size <= 3:
        values[Lillie_Determination] = 700
    elif _remaining_plays <= 1:
        values[Lillie_Determination] = 650
    elif hand_size <= 5:
        values[Lillie_Determination] = 550
    else:
        values[Lillie_Determination] = 400

    if op_is_alakazam_deck and hand_size >= 4:
        values[Lillie_Determination] = min(values[Lillie_Determination], 450)

        if _remaining_plays >= 2:
            values[Lillie_Determination] = min(values[Lillie_Determination], 300)

    if (hand_counts.get(Dawn, 0) >= 1 and
            hand_counts.get(Lillie_Determination, 0) >= 1 and
            not (ESTADO.meganium_in_play and has_hydrapple)):
        if ESTADO.forest_in_play:

            values[Dawn] = max(values.get(Dawn, 0),
                               values.get(Lillie_Determination, 0) + 50)
        else:

            values[Lillie_Determination] = max(values.get(Lillie_Determination, 0),
                                               values.get(Dawn, 0) + 50)

    lana_val = 0
    discard_basic_pokemon = []
    discard_basic_energy = 0
    for c in my_state.discard:
        if c.id == Basic_Grass_Energy:
            discard_basic_energy += 1
        # Lana's Aid only recovers Pokemon WITHOUT a Rule Box. The ex Pokemon
        # (Teal Mask Ogerpon ex, Meowth ex, Fezandipiti ex) HAVE a Rule Box and are
        # NOT recoverable by Lana's Aid, so they must not count as a target or
        # inflate its value. Counting them made Lana's Aid score high (e.g. 700 for
        # a Meowth ex in the discard) and that phantom value blocked the Night
        # Stretcher -> Meowth ex -> Lillie's line by raising
        # `_best_supp_in_hand_val` (registro 006, step 51 vs Alakazam).
        elif c.id in (Chikorita, Applin, Tapu_Bulu, Pinsir):
            discard_basic_pokemon.append(c.id)

    total_recoverable = len(discard_basic_pokemon) + discard_basic_energy
    if total_recoverable >= 1:
        lana_val = LANA_PLAY_BASE_RECUPERABLE
        if bench_count <= 1:
            lana_val += 400
        elif bench_count <= 2:
            lana_val += 200
        if Chikorita in discard_basic_pokemon and not ESTADO.meganium_in_play:
            if field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium] == 0:
                lana_val += 350
        if Applin in discard_basic_pokemon and not has_hydrapple:
            if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] == 0:
                lana_val += 300
        if ESTADO.forest_in_play and any(pid in discard_basic_pokemon for pid in (Chikorita, Applin)):
            lana_val += 200
        if total_recoverable >= 3:
            lana_val += 150

        if ESTADO.op_is_crustle_deck:
            _tapu_in_play_lana = field_counts.get(Tapu_Bulu, 0) >= 1
            if Tapu_Bulu in discard_basic_pokemon and not _tapu_in_play_lana:
                lana_val += 350
            if (Applin in discard_basic_pokemon and
                    field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0):
                lana_val += 200

    # Value of the need bonuses ONLY (short bench, fallen line, Forest, >=3
    # recoverable, matchup): it is frozen BEFORE the floor of 950 for energy,
    # which is a different reason. `> LANA_PLAY_BASE_RECUPERABLE` means "some
    # bonus was collected", that is, the board ASKS for what is down there --
    # and not just "there is a recoverable card".
    _lana_val_bonos = lana_val

    # Does the ENERGY in the discard enable an attack? Before, this only knew
    # how to look at Hydrapple ex (active, or benched with a switch available),
    # which is why it stayed silent with an active Tapu Bulu one Grass away
    # from firing Wood Hammer (registro_018 step 118 vs Crustle, LOST). Now it
    # is resolved by `_plan_de_planta`, which walks ALL the `MAIN_ATTACKERS` in
    # play with `ATTACK_ENERGY_REQ` and counts the real attachment routes
    # (manual, Teal Dance, Ripening Charge). It is the SAME reading that then
    # decides what is picked up from the discard, so playing the card and using
    # it cannot disagree.
    _lana_plan_play = _plan_de_planta(
        my_state, state, field_counts, hand_counts,
        puede_cambiar=(can_switch or has_switch_card),
        habilidades_apagadas=meowth_ability_lock)
    _lana_energy_enables_attack = (
        discard_basic_energy >= 1
        and _lana_plan_play.desbloquea_hoy
        and _lana_plan_play.cartas_para_atacar <= discard_basic_energy)
    if _lana_energy_enables_attack:

        lana_val = max(lana_val, 950)

    # WHAT IS PICKED UP HAS TO BE PLAYABLE (user, episode 88904232
    # step 140 vs Marnie, WON -- the leak did not cost the game, but it is a
    # leak all the same). Board: active Hydrapple ex, FULL bench (5/5),
    # discard with NO Grass and a single Applin. Lana's Aid could only pick up
    # that Applin -- a Basic that with a full bench does not fit in any way, and
    # from a line that was already evolved in the active spot. The agent spent
    # the turn's Supporter to put a DEAD card into hand. The cause: the block
    # above collects its base of 300 for "total_recoverable >= 1", which only
    # counts cards in the discard and looks at neither the bench slot nor the
    # attachment routes.
    #
    # The user's rule: Lana's is played ONLY if we really need something that
    # can be put into play THIS turn -- playable Pokemon or attachable Energy.
    # It is applied in two steps, with the SAME board reading that then decides
    # what is picked up (`_pokemon_injugable` / `_plan_de_planta`):
    #
    #   1. VETO if nothing recoverable can enter play today: no playable
    #      Pokemon (`_pokemon_injugable`: a full bench kills a Basic, and an
    #      evolution only lives if its pre-evolution is IN PLAY) and no live
    #      attachment route for a Grass.
    #   2. CEILING if what is playable is not NEEDED: Energy that NOBODY asks
    #      for (every attacker in play already reaches `ATTACK_ENERGY_REQ`, or
    #      the hand already has more Grass than fits today), or a Pokemon that
    #      fits on the bench but that no need bonus is claiming (the line is
    #      already in play, the bench is not short...). It is a ceiling and not
    #      a veto because the card is still playable: it merely yields the turn
    #      to any other useful Supporter.
    _lana_pk_jugable = any(
        not _pokemon_injugable(_pid, field_counts, bench_count,
                               bench_max)
        for _pid in discard_basic_pokemon)
    _lana_pk_necesario = (_lana_pk_jugable
                          and _lana_val_bonos > LANA_PLAY_BASE_RECUPERABLE)
    _lana_energia_jugable = (discard_basic_energy >= 1
                             and _lana_plan_play.slots_hoy >= 1)
    _lana_energia_util = (_lana_energia_jugable
                          and _lana_plan_play.nuevas_utiles_hoy >= 1
                          and _lana_plan_play.demanda >= 1)
    if not (_lana_pk_jugable or _lana_energia_jugable):
        lana_val = 0
    elif not (_lana_pk_necesario or _lana_energia_util
              or _lana_energy_enables_attack):
        lana_val = min(lana_val, LANA_PLAY_SIN_DEMANDA)

    values[Lanas_Aid] = lana_val
    # Exposed for the PLAY scoring layer: it distinguishes the case where
    # Lana's recovers energy that ENABLES an attack (the only reason to
    # prioritise it over Lillie's when we have no attacker) from the rest.
    values['_lana_enables_attack'] = _lana_energy_enables_attack

    if state.turn == 2 and not ESTADO.we_go_first:
        values[Lillie_Determination] = 1000
        for _sid in (Boss_Orders, Dawn, Lanas_Aid):
            if _sid in values:
                values[_sid] = min(values[_sid], 200)

    if state.turn <= 2 and hand_size >= 10:
        values[Lillie_Determination] = -1

    if (ESTADO.ko_last_turn and
            hand_counts.get(Dawn, 0) >= 1 and
            hand_counts.get(Lillie_Determination, 0) == 0 and
            hand_counts.get(Meowth_ex, 0) == 0 and
            hand_counts.get(Ultra_Ball, 0) == 0 and
            field_counts.get(Fezandipiti_ex, 0) == 0 and
            ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Fezandipiti_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            bench_count < 5):
        values[Dawn] = 1100

        for _sid in (Boss_Orders, Lanas_Aid):
            if _sid in values:
                values[_sid] = min(values[_sid], 200)

    if values.get(Boss_Orders, 0) > 0 and op_state.active and op_state.active[0] is not None:
        _bo_active_pkmn = op_state.active[0]
        _bo_has_distinct_target = False
        for _bo_bench_pkmn in op_state.bench:
            if _bo_bench_pkmn is None:
                continue
            if (_bo_bench_pkmn.id != _bo_active_pkmn.id or
                    len(_bo_bench_pkmn.energies) != len(_bo_active_pkmn.energies)):
                _bo_has_distinct_target = True
                break
        if not _bo_has_distinct_target:
            values[Boss_Orders] = 0

    # Supporter reserve vs Crustle: without a relevant target on the opposing
    # bench, Boss's is not burned. `crustle_gust_worth_it` is precisely the
    # check that there IS one (our ex is blocked by the wall and on the bench
    # there is a body we damage and knock out or jam), so it cannot override
    # it: with the opposing bench full of Dwebble this cut-off cancelled the
    # 990 gust just computed and the turn died without prizes (user, episode
    # 88620891 step 78 vs Crustle, LOST).
    if (ESTADO.op_is_crustle_deck and values.get(Boss_Orders, 0) > 0
            and not crustle_gust_worth_it):
        _cru_act = op_state.active[0] if op_state.active else None
        _cru_act_ok = (_cru_act is not None and
                       _cru_act.id in (Dwebble_Grass, Crustle_Grass,
                                       Dwebble_Fighting, Crustle_Fighting))
        _cru_has_nondwebble_bench = any(
            bp is not None and bp.id not in (Dwebble_Grass, Dwebble_Fighting)
            for bp in op_state.bench)
        if not _cru_act_ok or not _cru_has_nondwebble_bench:
            values[Boss_Orders] = 0

    # Rule (user, vs Alakazam): with a FULL BENCH we only play Dawn if we
    # REALLY are missing an evolution (Stage 1 / Stage 2) for a Pokemon we
    # ALREADY have in play (bench or active) and that we could evolve. Dawn
    # searches up to 3 Pokemon from the deck into hand (it thins the deck);
    # with a full bench we cannot put down new basics, so if we do NOT need
    # any evolution, playing Dawn only draws / empties the deck further and
    # risks LOSING by deckout (there are no cards left to draw). In that case
    # it is NOT played (value 0). An evolution is only considered "needed" if
    # we have the pre-evolution in play, we do NOT have its evolution in hand
    # and that evolution is still available in the deck (Dawn can bring it).
    #
    # GENERALISED TO ALL MATCHUPS (user, episode 88904232 step 140
    # vs Marnie): it is the SAME utility gate as the Lana's Aid one further
    # up -- what the Supporter brings to hand has to be playable -- and it had
    # nothing Alakazam-specific about it. On that step, with Lana's already
    # vetoed, the turn's Supporter went into a Dawn that, with the bench 5/5
    # and both lines already evolved (Meganium + Hydrapple ex in play), could
    # only bring inert cards. The pre->evo pairs now come from `EVO_LINES`
    # instead of a fixed table.
    if bench_count >= bench_max:
        _dawn_need_evo = False
        for _dw_linea in EVO_LINES:
            for _dw_pre, _dw_evo in zip(_dw_linea, _dw_linea[1:]):
                if (field_counts.get(_dw_pre, 0) >= 1
                        and hand_counts.get(_dw_evo, 0) < 1
                        and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                            _dw_evo, {}).get(ESTADO_MAZO, 0) > 0):
                    _dawn_need_evo = True
                    break
            if _dawn_need_evo:
                break
        if not _dawn_need_evo:
            values[Dawn] = 0

    return values


__all__ = ['evaluate_supporters']
