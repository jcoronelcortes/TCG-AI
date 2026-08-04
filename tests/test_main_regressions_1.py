"""Regression slice 1 of 8, from the chronological log of tests/test_main.py.
Mostly the Meowth/Lillie engine, the Boss's Orders scorers and the first
Ultra Ball cost vetoes."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

_STEP51_FIXTURE = ROOT / "tests" / "fixtures" / "marnie_grimmsnarl_step51.json"

def _load_step51_obs():
    with open(_STEP51_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]

def test_marnie_step51_plays_meowth_not_lanas_aid():
    obs = _load_step51_obs()

    play_map = _resolve_play_options(obs)
    # The fixture must contain both options for the test to be meaningful.
    assert m.Meowth_ex in play_map.values()
    assert m.Lanas_Aid in play_map.values()
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    lanas_opt = next(i for i, cid in play_map.items() if cid == m.Lanas_Aid)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"esperaba bajar Meowth ex (opt {meowth_opt}), obtuvo {result} "
        f"(map={play_map})"
    )
    assert result != [lanas_opt]

def test_marnie_step51_meowth_priority_holds_without_froslass():
    # Removing Froslass (id 104) and its pre-evo Snorunt (id 860) from the rival bench
    # must NOT change the decision: the Meowth->Lillie's branch already held with the
    # original `not op_has_froslass` guard. It confirms that the relaxation does not
    # alter the path without Froslass (identical behaviour).
    obs = copy.deepcopy(_load_step51_obs())
    opp_bench = obs["current"]["players"][1]["bench"]
    obs["current"]["players"][1]["bench"] = [
        p for p in opp_bench if p is not None and p.get("id") not in (104, 860)
    ]

    play_map = _resolve_play_options(obs)
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)

    result = m.agent(obs)
    assert result == [meowth_opt]

_STEP51_NS_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_ns_meowth_step51.json"

def _load_ns_step51_obs():
    with open(_STEP51_NS_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]

def test_alakazam_step51_plays_night_stretcher_for_meowth():
    obs = _load_ns_step51_obs()

    play_map = _resolve_play_options(obs)
    # The fixture must offer Night Stretcher as a play.
    assert m.Night_Stretcher in play_map.values()
    ns_opt = next(i for i, cid in play_map.items() if cid == m.Night_Stretcher)

    # The end-of-turn option (type 14) is the last of the select.
    options = obs["select"]["option"]
    pass_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.END))

    result = m.agent(obs)

    assert result == [ns_opt], (
        f"esperaba jugar Night Stretcher (opt {ns_opt}) para recuperar Meowth ex, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [pass_opt], "no debe terminar el turno sin desarrollar"

_TURN3_SEQ_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_lillie_turn3_seq.json"

def test_archaludon_step36_plays_lillie_not_end_on_dead_turn():
    with open(_TURN3_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    # Reproducing the turn's sequence to set `_field_at_turn_start`.
    final_obs = None
    result = None
    for item in seq:
        obs = item["observation"]
        result = m.agent(obs)
        final_obs = obs

    # The last decision (tac=4): it must play Lillie's Determination (opt 0), not END.
    play_map = _resolve_play_options(final_obs)
    assert m.Lillie_Determination in play_map.values()
    lillie_opt = next(i for i, cid in play_map.items()
                      if cid == m.Lillie_Determination)
    options = final_obs["select"]["option"]
    end_opt = next(i for i, o in enumerate(options)
                   if o.get("type") == int(OptionType.END))

    assert result == [lillie_opt], (
        f"esperaba jugar Lillie's Determination (opt {lillie_opt}) para refrescar, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [end_opt], "no debe terminar un turno muerto sin refrescar"

_UB_MEOWTH_FIXTURE = ROOT / "tests" / "fixtures" / "iono_ub_meowth_not_hydra_step62.json"

def test_iono_ultraball_fetches_meowth_not_dead_hydrapple():
    with open(_UB_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    search_map = _resolve_search_options(obs)
    # The fixture must offer both as search targets.
    assert m.Meowth_ex in search_map.values()
    assert m.Hydrapple_ex in search_map.values()
    meowth_opt = next(i for i, cid in search_map.items() if cid == m.Meowth_ex)
    hydra_opt = next(i for i, cid in search_map.items() if cid == m.Hydrapple_ex)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"esperaba buscar Meowth ex (opt {meowth_opt}) para refrescar, obtuvo "
        f"{result} (map={search_map})"
    )
    assert result != [hydra_opt], "no debe buscar un Hydrapple ex que no ataca este turno"

_NO_MEOWTH_SEQ_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_no_redundant_meowth_turn6.json"

def test_alakazam_step57_no_redundant_meowth_when_attacker_ready():
    with open(_NO_MEOWTH_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    # Reproducing the turn's sequence (it sets `_ub_meowth_pending` and the snapshot).
    target = None
    result = None
    for item in seq:
        obs = item["observation"]
        result = m.agent(obs)
        if item.get("tac") == 11 and item.get("status") == "ACTIVE":
            target = obs
            break

    assert target is not None, "no se encontro la decision del paso 57 (tac=11)"
    play_map = _resolve_play_options(target)
    meowth_opts = [i for i, cid in play_map.items() if cid == m.Meowth_ex]
    assert meowth_opts, "el fixture debe ofrecer jugar Meowth ex"
    options = target["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    # It must not play Meowth ex (a redundant body); with a ready attacker, it attacks.
    assert result[0] not in meowth_opts, (
        f"no debe jugar Meowth ex con un atacante ya listo; obtuvo {result} "
        f"(meowth_opts={meowth_opts})"
    )
    assert result == [attack_opt], (
        f"esperaba atacar (opt {attack_opt}) en vez de bajar Meowth ex, obtuvo {result}"
    )

_DAWN_BEFORE_RETREAT_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_dawn_before_retreat_step53.json"

def test_archaludon_step53_plays_dawn_before_retreat():
    with open(_DAWN_BEFORE_RETREAT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Dawn in play_map.values(), "el fixture debe ofrecer jugar Dawn"
    dawn_opt = next(i for i, cid in play_map.items() if cid == m.Dawn)
    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    assert result == [dawn_opt], (
        f"esperaba jugar Dawn (opt {dawn_opt}) ANTES de retirar, obtuvo {result} "
        f"(map={play_map})"
    )
    assert result != [retreat_opt], "no debe retirar antes de jugar el Supporter"

_BOSS_BEFORE_UB_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_boss_before_ub_step64.json"

def test_alakazam_step64_plays_boss_to_gust_abra_not_ultraball():
    with open(_BOSS_BEFORE_UB_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Boss_Orders in play_map.values(), "el fixture debe ofrecer jugar Boss's Orders"
    assert m.Ultra_Ball in play_map.values(), "el fixture debe ofrecer jugar Ultra Ball"
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"esperaba jugar Boss's Orders (opt {boss_opt}) para gustear el Abra, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [ub_opt], (
        "no debe jugar Ultra Ball (quema el Boss's necesario para cortar la linea Alakazam)"
    )

def test_score_boss_orders_vetoed_when_supporter_already_played():
    ctx = _make_boss_ctx(state=SimpleNamespace(supporterPlayed=True))
    assert m._score_boss_orders_play(ctx) == -1

def test_score_boss_orders_deny_alakazam_line_beats_default():
    # The Alakazam line cut scores at BOSS_SCORE_PRIZE_RANK_BASE, above
    # the default gust (2400 + val*1.4), replicating record 010.
    deny = m._score_boss_orders_play(_make_boss_ctx(boss_deny_alakazam_line=True))
    default = m._score_boss_orders_play(_make_boss_ctx())
    assert deny == m.BOSS_SCORE_PRIZE_RANK_BASE
    assert deny > default

def test_score_boss_orders_win_via_bench_has_priority_over_deny():
    # A lethal gust to the bench (win_via_bench) keeps its priority above
    # the line cut (the if/elif order is preserved after the extraction).
    ctx = _make_boss_ctx(boss_win_via_bench=True, boss_deny_alakazam_line=True)
    assert m._score_boss_orders_play(ctx) == m.BOSS_SCORE_WIN_VIA_BENCH

def test_score_unfair_stamp_dead_hand_scores_highest():
    # A hand with NO alternative use (nothing playable): Unfair Stamp is worth its maximum (7500).
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1})
    assert m._score_unfair_stamp_play(ctx) == 7500

def test_score_unfair_stamp_lower_when_hand_has_a_play():
    # With a playable item in hand (Night Stretcher) the refresh is worth less (2500):
    # it is better to use the hand before shuffling it.
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1, m.Night_Stretcher: 1})
    assert m._score_unfair_stamp_play(ctx) == 2500

def _deck(*ids):
    """A minimal deck-belief: {id: {ZONE_DECK: 1}} for the given ids."""
    return {cid: {m.ZONE_DECK: 1} for cid in ids}

def test_score_poke_pad_vetoed_when_nothing_searchable():
    # With no non-ex Pokemon in the deck, Poke Pad searches for nothing.
    ctx = _make_boss_ctx(state=SimpleNamespace(turn=6, energyAttached=False),
                         cards_in_deck={})
    assert m._score_poke_pad_play(ctx) == -1

def test_score_poke_pad_enables_evolution_this_turn_scores_high():
    # Bayleef in play (since the start of the turn) + Meganium in the deck and not in hand:
    # searching for Meganium enables the evolution THIS turn -> a high score (>=22000).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck=_deck(m.Meganium),
        field_counts={m.Bayleef: 1},
        field_at_turn_start={m.Bayleef: 1},
        bench_count=2,
    )
    assert m._score_poke_pad_play(ctx) >= 22000

def test_score_poke_pad_saves_resource_on_full_bench():
    # A full bench and no pre-evo to evolve with a search: it is kept (-1).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck=_deck(m.Chikorita),
        field_counts={},
        bench_count=5,
    )
    assert m._score_poke_pad_play(ctx) == -1

def test_score_night_stretcher_vetoed_when_discard_empty():
    # An empty discard: there is nothing to recover.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(discard=[], active=[None], bench=[], hand=[]),
    )
    assert m._score_night_stretcher_play(ctx) == -1

def test_score_night_stretcher_recovers_meowth_for_refresh_engine():
    # Meowth ex in the discard + a viable refresh engine (a strong Supporter in the
    # deck, none in hand, the Supporter unplayed): it is recovered. Record 006 p51.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(
            discard=[SimpleNamespace(id=m.Meowth_ex)], active=[None], bench=[], hand=[]),
        bench_count=1,
        best_supp_in_hand_val=0,
        best_supp_in_deck_val=700,
    )
    # best_recovery_value=830 -> tier 800..899 -> ns_score 11000.
    assert m._score_night_stretcher_play(ctx) == 11000

def test_score_forest_vetoed_when_forest_already_in_play():
    # If Forest of Vitality is already the stadium in play, it is not played again.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        stadium_id=m.Forest_of_Vitality,
    )
    assert m._score_forest_of_vitality_play(ctx) == -1

def test_score_forest_high_when_enables_evolution_chain():
    # Chikorita in play + Bayleef in hand and no Meganium: Forest enables the
    # evolution chain this turn -> a high score (>=21900).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        field_counts={m.Chikorita: 1},
        hand_counts={m.Bayleef: 1},
        stadium_id=0,
    )
    assert m._score_forest_of_vitality_play(ctx) >= 21900

def test_score_bug_catching_set_vetoed_when_nothing_eligible():
    # A deck with no Grass Pokemon or eligible Energy: there is nothing to take.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck={},
    )
    assert m._score_bug_catching_set_play(ctx) == -1

def test_score_bug_catching_set_positive_when_grass_energy_in_deck():
    # With Grass Energy in the deck (eligible), the play has positive value.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 5}},
    )
    assert m._score_bug_catching_set_play(ctx) > 0

def test_bcs_deckout_brake_with_a_critical_deck():
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=20, energyAttached=False),
        my_state=SimpleNamespace(deckCount=8, discard=[], active=[None],
                                 bench=[], hand=[]),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 3}},
        hand_counts={m.Basic_Grass_Energy: 2},  # there IS Grass in hand
    )
    assert m._score_bug_catching_set_play(ctx) == -1

def test_bcs_brake_yields_when_the_energy_is_dry():
    # The same critical deck but with NO Grass in hand and an attachment pending: the BCS
    # is still playable (it is the energy route of the anti-mill plan).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=20, energyAttached=False),
        my_state=SimpleNamespace(deckCount=8, discard=[], active=[None],
                                 bench=[], hand=[]),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 3}},
        hand_counts={},
    )
    assert m._score_bug_catching_set_play(ctx) > 0

def test_bcs_brake_does_not_apply_with_a_healthy_deck():
    # Boundary: with a deck of 9+ the brake does not fire.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=20, energyAttached=False),
        my_state=SimpleNamespace(deckCount=9, discard=[], active=[None],
                                 bench=[], hand=[]),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 3}},
        hand_counts={m.Basic_Grass_Energy: 2},
    )
    assert m._score_bug_catching_set_play(ctx) > 0

def test_score_ultra_ball_vetoed_with_tiny_hand():
    # A hand of <3 cards: playing an Ultra Ball (the cost of discarding 2) would empty the hand.
    # The cold path of the early `hand_size < 3` cut-off (a mid turn, no survival concerns).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(
            discard=[], active=[None], bench=[],
            hand=[SimpleNamespace(id=m.Ultra_Ball), SimpleNamespace(id=m.Boss_Orders)]),
        bench_count=1,
    )
    assert m._score_ultra_ball_play(ctx) == -1

def test_ub_cancel_stamp_false_without_unfair_stamp():
    # With no Unfair Stamp in hand, this guard never cancels.
    ctx = _make_boss_ctx(hand_counts={m.Ultra_Ball: 1, m.Basic_Grass_Energy: 3})
    assert m._ub_cancel_stamp(ctx) is False

def test_ub_cancel_stamp_true_when_stamp_would_be_forced_fodder():
    # A hand of {Unfair Stamp, Ultra Ball}: with no fodder (0 discardable without touching the
    # Stamp), playing the UB would discard the Stamp -> it is cancelled.
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1, m.Ultra_Ball: 1})
    assert m._ub_cancel_stamp(ctx) is True

def test_ub_cancel_meowth_false_when_no_meowth_engine():
    # With no Meowth ex in hand (or no Lillie's in the deck), the Meowth guard does not apply.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Ultra_Ball: 1},
        cards_in_deck={},
    )
    assert m._ub_cancel_meowth(ctx) is False

def test_score_lillie_vetoed_when_supporter_already_played():
    # The turn's Supporter has already been played: another cannot be played.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, supporterPlayed=True),
        my_state=SimpleNamespace(active=[None], bench=[], hand=[]),
        hand_counts={m.Lillie_Determination: 1},
    )
    assert m._score_lillie_determination_play(ctx) == -1

def test_unfair_stamp_cedes_to_lillie_when_opp_hand_small():
    # Rule (user): with a Lillie's in hand and the rival at <=3 cards, Unfair
    # Stamp is NOT played (it yields to Lillie's).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Unfair_Stamp: 1, m.Lillie_Determination: 1},
        op_hand_count=3,
    )
    assert m._score_unfair_stamp_play(ctx) == -1

def test_unfair_stamp_not_ceded_when_opp_hand_large():
    # With the rival at >3 cards the disruption is still worth it: Unfair Stamp does NOT yield.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Unfair_Stamp: 1, m.Lillie_Determination: 1},
        op_hand_count=6,
    )
    assert m._score_unfair_stamp_play(ctx) > 0

def _lillie_ctx(**over):
    base = dict(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(active=[None], bench=[],
                                 hand=[SimpleNamespace(id=0) for _ in range(5)]),
        hand_counts={m.Unfair_Stamp: 1, m.Lillie_Determination: 1},
        ko_last_turn=True,
    )
    base.update(over)
    return _make_boss_ctx(**base)

def test_lillie_playable_when_stamp_in_hand_but_opp_hand_small():
    # With Unfair Stamp in hand + a KO last turn, Lillie's is normally vetoed;
    # but if the rival has <=3 cards, Lillie's stays PLAYABLE (it wins the decision).
    assert m._score_lillie_determination_play(_lillie_ctx(op_hand_count=3)) > 0

def test_lillie_still_vetoed_by_stamp_when_opp_hand_large():
    # With the rival at >3 cards the original veto is kept: the Stamp is preferred.
    assert m._score_lillie_determination_play(_lillie_ctx(op_hand_count=6)) == -1

def _og(energy_count):
    # A Teal Mask Ogerpon ex with `energy_count` Grass -> a ready attacker with >=3.
    return SimpleNamespace(id=m.Teal_Mask_Ogerpon_ex, energies=[1] * energy_count)

def _hop_lillie_ctx(**over):
    # Record 008 step 84 vs Hops: an active + a bench with ready attackers, Boss's and
    # Lillie's in hand, a Hops rival. (ko_last_turn=False so as not to cross the Unfair
    # Stamp veto; no Unfair Stamp in hand.)
    base = dict(
        state=SimpleNamespace(turn=8, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(active=[_og(4)], bench=[_og(4)],
                                 hand=[SimpleNamespace(id=0) for _ in range(5)]),
        hand_counts={m.Boss_Orders: 1, m.Lillie_Determination: 1},
        op_is_hop_deck=True,
        ko_last_turn=False,
    )
    base.update(over)
    return _lillie_ctx(**base)

def test_lillie_vetoed_vs_hops_with_boss_and_two_attackers():
    # vs Hops with Boss's in hand and >=2 ready attackers: do NOT play Lillie's (it would shuffle
    # the Boss's into the deck); it is kept to answer a Hops Phantump with heads.
    assert m._score_lillie_determination_play(_hop_lillie_ctx()) == -1

def test_lillie_playable_vs_hops_when_active_is_only_attacker():
    # vs Hops with Boss's but with the active as the ONLY attacker: Lillie's IS played
    # (digging for resources), even though it shuffles away the Boss's.
    ctx = _hop_lillie_ctx(
        my_state=SimpleNamespace(active=[_og(4)], bench=[],
                                 hand=[SimpleNamespace(id=0) for _ in range(5)]))
    assert m._score_lillie_determination_play(ctx) > 0

def test_lillie_playable_vs_hops_when_no_boss_in_hand():
    # vs Hops WITHOUT Boss's in hand: Lillie's can be played as usual.
    ctx = _hop_lillie_ctx(hand_counts={m.Lillie_Determination: 1})
    assert m._score_lillie_determination_play(ctx) > 0

def test_lillie_playable_with_boss_and_two_attackers_when_not_hops():
    # The rule only applies vs Hops: against another deck, Lillie's is still playable.
    assert m._score_lillie_determination_play(_hop_lillie_ctx(op_is_hop_deck=False)) > 0

def test_score_lanas_aid_vetoed_when_supporter_already_played():
    # It receives the incoming score (10000) but vetoes it if the Supporter has already been played.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, supporterPlayed=True, energyAttached=False),
        my_state=SimpleNamespace(active=[None], bench=[], hand=[], discard=[]),
    )
    assert m._score_lanas_aid_play(ctx, 10000) == -1

_BOSS_GUST_ABRA_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_boss_gust_abra_step146.json"

def test_alakazam_step146_boss_gust_targets_abra_not_shaymin():
    with open(_BOSS_GUST_ABRA_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    # Mapping each option (the rival bench) to its Pokemon id.
    op_bench = obs["current"]["players"][0]["bench"]
    opt_ids = {i: op_bench[o["index"]]["id"]
               for i, o in enumerate(obs["select"]["option"])}
    abra_opts = [i for i, cid in opt_ids.items() if cid == m.Abra]
    shaymin_opts = [i for i, cid in opt_ids.items() if cid == 343]
    assert abra_opts and shaymin_opts, f"fixture debe ofrecer Abra y Shaymin (map={opt_ids})"

    result = m.agent(obs)

    assert result[0] in abra_opts, (
        f"esperaba gustear un Abra {abra_opts} (linea Alakazam), obtuvo {result} "
        f"(map={opt_ids})"
    )
    assert result[0] not in shaymin_opts, "no debe gustear el Shaymin sobre la linea Alakazam"

_LATIAS_BOSS_GUST_FIXTURE = ROOT / "tests" / "fixtures" / "dragapult_latias_boss_gust_drakloak_step76.json"

def test_boss_gust_avoids_latias_ex_and_basics_targets_drakloak():
    with open(_LATIAS_BOSS_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    op_bench = obs["current"]["players"][1]["bench"]
    opt_ids = {i: op_bench[o["index"]]["id"]
               for i, o in enumerate(obs["select"]["option"])}
    latias_opts = [i for i, cid in opt_ids.items() if cid == m.Latias_ex]
    dreepy_opts = [i for i, cid in opt_ids.items() if cid == 119]   # Dreepy (basic)
    drakloak_opts = [i for i, cid in opt_ids.items() if cid == 120]  # Drakloak (stage 1)
    assert latias_opts and drakloak_opts, f"fixture debe ofrecer Latias ex y Drakloak (map={opt_ids})"

    result = m.agent(obs)

    assert result[0] not in latias_opts, "no debe gustear la Latias ex"
    assert result[0] not in dreepy_opts, "no debe gustear un Basico (Dreepy) con Latias ex en juego"
    assert result[0] in drakloak_opts, (
        f"esperaba gustear el Drakloak {drakloak_opts} (no-basico), obtuvo {result} (map={opt_ids})"
    )

_MEOWTH_ENGINE_EOT_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_meowth_engine_end_of_turn_step105.json"

def test_alakazam_step105_plays_meowth_engine_instead_of_ending_turn():
    with open(_MEOWTH_ENGINE_EOT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Meowth_ex in play_map.values(), "el fixture debe ofrecer jugar Meowth ex"
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    options = obs["select"]["option"]
    end_opt = next(i for i, o in enumerate(options) if o.get("type") == int(OptionType.END))

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"esperaba jugar Meowth ex (opt {meowth_opt}) para el motor Lillie's, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [end_opt], "no debe terminar el turno con Meowth ex jugable en la mano"

_TAPU_KO_FIXTURE = ROOT / "tests" / "fixtures" / "tapu_bulu_step82_active_ko.json"

def test_alakazam_step82_tapu_bulu_attacks_instead_of_retreating():
    with open(_TAPU_KO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    assert result == [attack_opt], (
        f"un Tapu Bulu activo que puede noquear debe ATACAR (opt {attack_opt}), "
        f"obtuvo {result}"
    )
    assert result != [retreat_opt], "nunca retirar un Tapu Bulu que puede derrotar al rival"

_HYDRA_PIVOT_LOWHP_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_hydra_pivot_lowhp_active_step143.json"

def test_archaludon_step143_retreats_low_hp_hydrapple_to_promote_full_hp_wall():
    with open(_HYDRA_PIVOT_LOWHP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    # AN ARITHMETIC CORRECTION (registro_006 step 78 vs Archaludon ex): the
    # retreat is paid for with whole CARDS and with Wild Growth each Grass is worth
    # TWO units, so retreating the Hydrapple ex (cost 3) discards 2 cards
    # = 4 units, not 2. On THIS board (12 units) the bench tank is
    # left at 8 -> Syrup 270 - 30 of resistance = 240 < 300: it does NOT knock out. The
    # pivot's premise does not hold, and attacking with the fragile one DOES knock out
    # (12 units -> 390 - 30 = 360 >= 300) and takes 2 prizes. The pivot is still
    # valid when the tank really finishes: see the test below with one more
    # Grass on the field.
    assert result == [attack_opt], (
        f"con la cuenta correcta de la retirada el tanque NO noquea (240 < 300) "
        f"y el fragil SI (360 >= 300): debe ATACAR (opt {attack_opt}); "
        f"obtuvo {result}"
    )

_HYDRA_PIVOT_TANQUE_KO_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_hydra_pivot_tanque_si_noquea.json")

def test_archaludon_pivot_when_the_tank_really_knocks_out():
    """The same board with ONE more Grass (14 units): after the retreat 10 are
    left -> Syrup 330 - 30 = 300 >= 300, the tank DOES finish, and then the
    defensive pivot (knocking out with the body that survives) rules again."""
    with open(_HYDRA_PIVOT_TANQUE_KO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"con el tanque REALMENTE letal tras retirar, debe RETIRAR "
        f"(opt {retreat_opt}) y no atacar con el fragil; obtuvo {result}")
    assert result != [attack_opt]

_BOSS_OVER_LILLIE_DURALUDON_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_boss_over_lillie_duraludon_step78.json"

def test_archaludon_step78_plays_boss_to_gust_duraludon_not_lillie():
    with open(_BOSS_OVER_LILLIE_DURALUDON_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lillie_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"debe jugar Boss's (opt {boss_opt}) para gustear+noquear al Duraludon "
        f"(pre-evo de Archaludon ex), no Lillie's (opt {lillie_opt}); obtuvo {result}"
    )
    assert result != [lillie_opt], "no jugar Lillie's teniendo Boss's y atacantes de sobra"

_NO_MEOWTH_HAVE_LILLIE_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_no_meowth_have_lillie_step18.json"

def test_archaludon_step17_plays_lillie_not_meowth_when_lillie_in_hand():
    with open(_NO_MEOWTH_HAVE_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    lillie_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)
    meowth_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 3)

    result = m.agent(obs)

    assert result == [lillie_opt], (
        f"debe jugar la Lillie's que ya tiene (opt {lillie_opt}), no bajar Meowth ex "
        f"para buscar otra (opt {meowth_opt}); obtuvo {result}"
    )
    assert result != [meowth_opt], "no bajar Meowth ex para un fetch de Lillie's redundante"

_ABOMASNOW_NO_SECOND_MEOWTH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_no_second_meowth_supporter_played_step60.json")

def test_abomasnow_step60_no_meowth_when_supporter_played():
    with open(_ABOMASNOW_NO_SECOND_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    assert obs["current"]["supporterPlayed"] is True

    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 2)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"no bajar un segundo Meowth ex (opt {meowth_opt}) con el Supporter ya jugado: "
        f"el fetch es inutil y expone un cuerpo de 2 premios; obtuvo {result}"
    )
    assert result == [attack_opt], (
        f"debe atacar (opt {attack_opt}) en vez de desperdiciar el Meowth; obtuvo {result}"
    )

_BOSS_WIN_RETREAT_PROMOTE_FIXTURE = ROOT / "tests" / "fixtures" / "iono_boss_win_retreat_promote_hydra_step241.json"

def test_iono_step241_plays_boss_win_via_retreat_promote_not_lana():
    with open(_BOSS_WIN_RETREAT_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lana_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"debe jugar Boss's (opt {boss_opt}) para el remate ganador (gustear+noquear "
        f"al Bellibolt ex tras retirar+promover Hydrapple), no Lana's (opt {lana_opt}); "
        f"obtuvo {result}"
    )
    assert result != [lana_opt], "no jugar Lana's Aid cuando hay un remate ganador con Boss's"

_BOSS_WIN_RETREAT_OGERPON_FIXTURE = ROOT / "tests" / "fixtures" / "iono_boss_win_retreat_promote_ogerpon_step241.json"

def test_iono_step241_boss_win_via_bench_ogerpon_not_only_hydrapple():
    with open(_BOSS_WIN_RETREAT_OGERPON_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lana_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"el remate ganador debe verse con un Ogerpon ex de banca (sin Hydrapple): "
        f"Boss's (opt {boss_opt}), no Lana's (opt {lana_opt}); obtuvo {result}"
    )
    assert result != [lana_opt], "la deteccion de win-via-banca debe evaluar toda la banca, no solo Hydrapple"

_DRAGAPULT_LILLIE_OVER_BOSS_FIXTURE = ROOT / "tests" / "fixtures" / "dragapult_lillie_over_boss_one_attacker_step51.json"

def test_dragapult_step51_plays_lillie_over_boss_when_no_second_attacker():
    with open(_DRAGAPULT_LILLIE_OVER_BOSS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lillie_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [lillie_opt], (
        f"con solo el activo como atacante (banca = basicos/Applin) debe CAVAR con "
        f"Lillie's (opt {lillie_opt}), no gustear con Boss's (opt {boss_opt}); obtuvo {result}"
    )
    assert result != [boss_opt], "un gusteo de desarrollo no tiene prioridad sin un atacante de banca real"

def test_boss_dev_gust_keeps_priority_with_ready_bench_attacker():
    # A complement: WITH a ready bench attacker (!= Applin), the development
    # gust (boss_prize_rank) DOES keep priority -> Boss's does not yield.
    _hc = {m.Boss_Orders: 1, m.Lillie_Determination: 1}
    ctx = _make_boss_ctx(boss_prize_rank=7, has_ready_bench_attacker=True,
                         active_cant_attack=False, hand_counts=_hc)
    assert m._score_boss_orders_play(ctx) > m.BOSS_SCORE_EMPTY_GUST, (
        "con atacante de banca listo, el gusteo de desarrollo mantiene prioridad")
    ctx_no = _make_boss_ctx(boss_prize_rank=7, has_ready_bench_attacker=False,
                            active_cant_attack=False, hand_counts=dict(_hc))
    assert m._score_boss_orders_play(ctx_no) == m.BOSS_SCORE_EMPTY_GUST, (
        "sin atacante de banca real (y Lillie's en mano), el gusteo de desarrollo cede a Lillie's")

_UB_MEOWTH_NOT_MEGANIUM_FIXTURE = ROOT / "tests" / "fixtures" / "lucario_ub_meowth_not_meganium_step35.json"

def test_lucario_step35_ultraball_searches_meowth_not_dead_meganium():
    with open(_UB_MEOWTH_NOT_MEGANIUM_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    deck = obs["select"]["deck"]
    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if deck[o["index"]]["id"] == m.Meowth_ex)
    meganium_opt = next(i for i, o in enumerate(options)
                        if deck[o["index"]]["id"] == m.Meganium)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"Ultra Ball debe buscar Meowth ex (opt {meowth_opt}) para el motor Lillie's, "
        f"no un Meganium inutil (opt {meganium_opt}); obtuvo {result}"
    )
    assert result != [meganium_opt], "no buscar un Meganium que no se puede jugar este turno"

_PROMOTE_TAPU_KO_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_promote_tapu_bulu_ko_step90.json"

def test_alakazam_step90_promotes_tapu_bulu_ko_over_ogerpon_ex():
    with open(_PROMOTE_TAPU_KO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    bench = obs["current"]["players"][1]["bench"]
    options = obs["select"]["option"]
    tapu_opt = next(i for i, o in enumerate(options)
                    if bench[o["index"]]["id"] == m.Tapu_Bulu)
    ogerpon_opts = [i for i, o in enumerate(options)
                    if bench[o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]

    result = m.agent(obs)

    assert result == [tapu_opt], (
        f"debe promover el Tapu Bulu cargado que noquea (opt {tapu_opt}), obtuvo {result}"
    )
    assert result[0] not in ogerpon_opts, "no promover un Ogerpon ex (2 premios) si Tapu Bulu noquea"
