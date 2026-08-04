"""Unit tests of the helpers in main.py: damage, tracking, the belief,
the pure scorers. They take no fixture and read a single function each."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

def test_validate_id_constants_returns_list():
    result = m._validate_id_constants()
    assert isinstance(result, list)

def test_grass_helpers():
    assert m._grass_mult() == 1
    assert m._grass_attach_unit() == 1
    m.meganium_in_play = True
    assert m._grass_attach_unit() == 2
    m.meganium_in_play = False

def test_active_of_handles_none_and_list():
    state = SimpleNamespace(active=[make_pokemon(123), None])
    assert m._active_of(state).id == 123
    assert m._active_of(None) is None
    assert m._active_of(SimpleNamespace(active=[None])) is None

def test_physical_energy_uses_meganium_rule():
    m.meganium_in_play = False
    assert m._physical_energy(4) == 4
    m.meganium_in_play = True
    assert m._physical_energy(4) == 2
    assert m._physical_energy(5) == 2
    m.meganium_in_play = False

def test_retreat_cards_counts_effective_energy():
    m.meganium_in_play = False
    assert m._retreat_cards(0) == 0
    assert m._retreat_cards(3) == 3
    m.meganium_in_play = True
    assert m._retreat_cards(3) == 2
    m.meganium_in_play = False

def test_can_attack_eff_checks_energy_requirements():
    assert m._can_attack_eff(m.Hydrapple_ex, 2) is True
    assert m._can_attack_eff(m.Dipplin, 0) is False
    assert m._can_attack_eff(999999, 1) is False

def test_init_move_card_state_and_belief_tracking():
    first_card_id = m.my_deck[0]
    assert m._move_card_state(first_card_id, m.ZONE_DECK, m.ZONE_HAND) is True
    assert m.ACTIVE_CARDS_IN_DECK[first_card_id][m.ZONE_HAND] == 1
    assert m._move_card_state(first_card_id, m.ZONE_HAND, m.ZONE_BENCH) is True
    deck, prize = m._belief_deck_and_prizes()
    assert deck + prize == len(m.my_deck) - 1
    assert m._move_card_state(999999, m.ZONE_DECK, m.ZONE_HAND) is False
    assert m.ACTIVE_CARDS_IN_DECK[first_card_id][m.ZONE_BENCH] == 1

def test_prob_draw_any_and_prob_card_accessible_are_between_zero_and_one():
    cid = m.my_deck[0]
    prob_any = m._prob_draw_any(cid)
    prob_accessible = m._prob_card_accessible(cid)
    assert 0.0 <= prob_any <= 1.0
    assert 0.0 <= prob_accessible <= 1.0

def test_our_effective_damage_applies_immunity_and_basics():
    attacker = make_pokemon(m.Teal_Mask_Ogerpon_ex)
    immune_target = make_pokemon(m.Crustle_Grass)
    neutral_target = make_pokemon(m.Slowpoke)

    assert m._our_effective_damage(attacker, immune_target, 100) == 0
    assert m._our_effective_damage(attacker, neutral_target, 100) == 100

def test_our_effective_damage_farigiraf_armor_tail_blocks_basic_ex():
    # Armor Tail (P1.6): Farigiraf ex is immune to damage from BASIC ex.
    farigiraf = make_pokemon(m.Farigiraf_ex, hp=260, max_hp=260)
    assert m._our_effective_damage(make_pokemon(m.Teal_Mask_Ogerpon_ex), farigiraf, 300) == 0
    assert m._our_effective_damage(make_pokemon(m.Meowth_ex), farigiraf, 60) == 0
    assert m._our_effective_damage(make_pokemon(m.Fezandipiti_ex), farigiraf, 100) == 0
    # Hydrapple ex (a Stage 2 ex) and the non-ex DO damage it (weak to Grass: x2).
    assert m._our_effective_damage(make_pokemon(m.Hydrapple_ex), farigiraf, 100) == 200
    assert m._our_effective_damage(make_pokemon(m.Tapu_Bulu), farigiraf, 220) == 440

def test_our_effective_damage_resolute_heart_caps_at_full_hp():
    # Resolute Heart (P0.1): a Pikachu ex at FULL life survives on 10 HP.
    atk = make_pokemon(m.Tapu_Bulu)
    pika_full = make_pokemon(m.Pikachu_ex_Resolute, hp=200, max_hp=200)
    assert m._our_effective_damage(atk, pika_full, 220) == 190
    # Damaged, the ability no longer applies: the lethal blow goes through whole.
    pika_dmg = make_pokemon(m.Pikachu_ex_Resolute, hp=150, max_hp=200)
    assert m._our_effective_damage(atk, pika_dmg, 220) == 220

def test_prize_count_op_applies_denial_from_the_opponent_field():
    munki = make_pokemon(m.Munkidori_ex, hp=210, max_hp=210)
    opponent_fez = make_pokemon(m.Fezandipiti_ex, hp=210, max_hp=210)  # rival {D}

    # With no denials on the rival field: it counts normally.
    assert m.prize_count_op(munki) == 2
    # A rival Pecharunt ex in play ("Oh No You Don't"): Munkidori ex yields 1.
    m._op_prize_denial_pecharunt = True
    assert m.prize_count_op(munki) == 1
    assert m.prize_count_op(opponent_fez) == 2  # it is not Munkidori: no change
    # A rival Mega Gengar ex ("Shadowy Concealment"): their {D} yield 1 less.
    m._op_prize_denial_gengar = True
    assert m.prize_count_op(opponent_fez) == 1
    # The prizes OUR side gives away (prize_count) are unaffected.
    assert m.prize_count(opponent_fez) == 2

def test_ko_not_guaranteed_catches_hawlucha_and_survival_brace():
    # Tenacious Body (a coin flip): it is never a guaranteed KO.
    assert m._ko_not_guaranteed(
        make_pokemon(m.Mega_Hawlucha_ex, hp=250, max_hp=250)) is True
    # Survival Brace only protects at FULL life.
    brace = make_card(m.Survival_Brace)
    assert m._ko_not_guaranteed(
        make_pokemon(m.Slowpoke, hp=100, max_hp=100, tools=[brace])) is True
    assert m._ko_not_guaranteed(
        make_pokemon(m.Slowpoke, hp=70, max_hp=100, tools=[brace])) is False
    assert m._ko_not_guaranteed(make_pokemon(m.Slowpoke)) is False
    assert m._ko_not_guaranteed(None) is False

def test_attacker_base_damage_uses_card_specific_rules():
    target = make_pokemon(m.Slowpoke)
    assert m._attacker_base_damage(m.Hydrapple_ex, target, 2, 1, 0, 1) == 60
    assert m._attacker_base_damage(m.Dipplin, target, 1, 0, 0, 2) == 40
    assert m._attacker_base_damage(999, target, 1, 0, 0, 1) == 0

def test_bench_attacker_can_ko_detects_kos():
    target = make_pokemon(m.Slowpoke, hp=100, max_hp=100)
    my_state = SimpleNamespace(bench=[make_pokemon(m.Pinsir, energies=[EnergyType.GRASS, EnergyType.GRASS])])
    assert m._bench_attacker_can_ko(my_state, target, False, 0, 1, 0, False) is True

    target2 = make_pokemon(m.Slowpoke, hp=300, max_hp=300)
    assert m._bench_attacker_can_ko(my_state, target2, False, 0, 1, 0, False) is False

def test_op_hand_size_and_disruption_belief():
    state = SimpleNamespace(hand=[1, 2, 3])
    assert m._op_hand_size(state) == 3
    assert m._op_hand_size(SimpleNamespace(hand=None)) == 0
    assert m._op_hand_size(None) == 0
    assert m._op_disruption_belief(SimpleNamespace(hand=[]), False) == 0.05
    assert m._op_disruption_belief(SimpleNamespace(hand=[1, 2]), False) > 0.05

def test_debug_log_decision_does_not_crash():
    obs = SimpleNamespace(
        current=SimpleNamespace(players=[SimpleNamespace(hand=[]), SimpleNamespace(hand=[])]),
        select=SimpleNamespace(option=[SimpleNamespace(area=AreaType.HAND, index=0)]),
    )
    m._debug_log_decision("ctx", obs.select, [10, 20], obs, my_index=0, top_n=2)

def test_first_turn_scan_moves_cards_to_expected_states():
    my_state = SimpleNamespace(
        hand=[make_card(m.Bug_Catching_Set)],
        active=[make_pokemon(m.Chikorita)],
        bench=[make_pokemon(m.Applin)],
        discard=[make_card(9999)],
    )

    m._first_turn_scan(my_state)

    assert m.ACTIVE_CARDS_IN_DECK[m.Bug_Catching_Set][m.ZONE_HAND] == 1
    assert m.ACTIVE_CARDS_IN_DECK[m.Chikorita][m.ZONE_BENCH] == 1
    assert m.ACTIVE_CARDS_IN_DECK[m.Applin][m.ZONE_BENCH] == 1
    assert m._cards_first_scan_done is True

def test_area_to_zone_maps_all_supported_areas():
    assert m._area_to_zone(AreaType.DECK) == m.ZONE_DECK
    assert m._area_to_zone(AreaType.HAND) == m.ZONE_HAND
    assert m._area_to_zone(AreaType.ACTIVE) == m.ZONE_BENCH
    assert m._area_to_zone(AreaType.DISCARD) == m.ZONE_DISCARD
    assert m._area_to_zone(AreaType.PRIZE) == m.ZONE_PRIZE
    assert m._area_to_zone(999) is None

def test_process_logs_updates_tracking():
    m._move_card_state(m.Ultra_Ball, m.ZONE_DECK, m.ZONE_HAND)
    obs = SimpleNamespace(logs=[SimpleNamespace(type=LogType.DRAW, playerIndex=0, cardId=m.Ultra_Ball)])

    m._process_logs(obs, my_index=0)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_HAND] >= 1

def test_identify_prizes_reconciles_hidden_cards():
    m._move_card_state(m.Ultra_Ball, m.ZONE_DECK, m.ZONE_HAND)
    obs = SimpleNamespace(
        select=SimpleNamespace(
            deck=[SimpleNamespace(id=m.Ultra_Ball)],
            effect=SimpleNamespace(id=m.Ultra_Ball),
        )
    )

    m._identify_prizes(obs, my_state=None)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DECK] == 1

def test_sync_from_state_reconciles_visible_state():
    my_state = SimpleNamespace(
        hand=[SimpleNamespace(id=m.Ultra_Ball)],
        active=[],
        bench=[],
        discard=[],
    )

    m._sync_from_state(my_state)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_HAND] == 1

def test_update_cards_tracking_initial_scan():
    my_state = SimpleNamespace(
        hand=[make_card(m.Bug_Catching_Set)],
        active=[make_pokemon(m.Chikorita)],
        bench=[make_pokemon(m.Applin)],
        discard=[],
        deckCount=60,
    )
    obs = SimpleNamespace(
        current=SimpleNamespace(turn=1, players=[my_state, SimpleNamespace(hand=[], active=[], bench=[], discard=[], prize=[])])
    )
    obs.select = SimpleNamespace(deck=None, effect=None)

    m._update_cards_tracking(obs, my_index=0, my_state=my_state)

    assert m._cards_first_scan_done is True
    assert m.ACTIVE_CARDS_IN_DECK[m.Bug_Catching_Set][m.ZONE_HAND] == 1

def test_get_card_reads_from_all_relevant_areas():
    card_in_hand = SimpleNamespace(id=1000)
    card_in_discard = SimpleNamespace(id=1001)
    card_in_active = SimpleNamespace(id=1002)
    card_in_bench = SimpleNamespace(id=1003)
    card_in_prize = SimpleNamespace(id=1004)
    card_in_deck = SimpleNamespace(id=1005)
    obs = SimpleNamespace(
        current=SimpleNamespace(
            players=[
                SimpleNamespace(
                    hand=[card_in_hand],
                    discard=[card_in_discard],
                    active=[card_in_active],
                    bench=[card_in_bench],
                    prize=[card_in_prize],
                ),
                SimpleNamespace(hand=[], discard=[], active=[], bench=[], prize=[]),
            ],
            stadium=[],
            looking=[card_in_prize],
        ),
        select=SimpleNamespace(deck=[card_in_deck]),
    )

    assert m.get_card(obs, AreaType.HAND, 0, 0).id == 1000
    assert m.get_card(obs, AreaType.DISCARD, 0, 0).id == 1001
    assert m.get_card(obs, AreaType.ACTIVE, 0, 0).id == 1002
    assert m.get_card(obs, AreaType.BENCH, 0, 0).id == 1003
    assert m.get_card(obs, AreaType.PRIZE, 0, 0).id == 1004
    assert m.get_card(obs, AreaType.DECK, 0, 0).id == 1005
    assert m.get_card(obs, AreaType.STADIUM, 0, 0) is None
    assert m.get_card(obs, AreaType.LOOKING, 0, 0).id == 1004

def test_prize_count_and_pokemon_score():
    charizard = SimpleNamespace(id=m.Charizard_ex, energies=[], energyCards=[], tools=[], hp=100, maxHp=100)
    mega = SimpleNamespace(id=m.Mega_Kangaskhan_ex, energies=[SimpleNamespace(id=12)], energyCards=[], tools=[], hp=100, maxHp=100)

    assert m.prize_count(charizard) >= 2
    assert m.prize_count(mega) >= 1

    score = m.pokemon_score(SimpleNamespace(id=m.Meganium, energies=[EnergyType.GRASS], energyCards=[], tools=[], hp=180, maxHp=180))
    assert score > 0

def test_count_total_grass_energy_and_syrup_damage():
    my_state = SimpleNamespace(
        active=[SimpleNamespace(energies=[EnergyType.GRASS, EnergyType.FIRE])],
        bench=[SimpleNamespace(energies=[EnergyType.GRASS]), None],
    )

    assert m.count_total_grass_energy(my_state) == 2
    assert m.calc_syrup_storm_damage(my_state, has_meganium=False) == 90
    assert m.calc_syrup_storm_damage(my_state, has_meganium=True) == 90

def test_count_hand_play_options():
    hand_counts = {
        m.Meganium: 1,
        m.Bayleef: 1,
        m.Chikorita: 1,
        m.Lillie_Determination: 1,
        m.Basic_Grass_Energy: 1,
    }
    field_counts = {m.Bayleef: 1, m.Chikorita: 1, m.Applin: 1}

    play_options, supporters_in_hand = m._count_hand_play_options(hand_counts, field_counts, bench_count=2, energy_attached=False)

    assert play_options >= 7
    assert supporters_in_hand == 1

def test_eval_ub_best_target_returns_non_negative_value():
    state = SimpleNamespace(turn=2, supporterPlayed=False)
    field_counts = {m.Chikorita: 1}
    hand_counts = {m.Basic_Grass_Energy: 1}

    result = m._eval_ub_best_target(
        field_counts,
        hand_counts,
        meganium_in_play=False,
        has_hydrapple=False,
        forest_in_play=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_prize=2,
        bench_count=1,
        state=state,
        ko_last_turn=False,
        _best_supp_in_deck_val=0,
        supporters_in_hand=0,
        hand_is_weak=False,
        has_energy_for_teal=False,
        _we_go_first=False,
        _best_supp_in_hand_val=0,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_active_is_budew=False,
        meowth_ability_lock=False,
    )

    assert result >= 0

def test_our_effective_damage_applies_weakness_and_resistance(monkeypatch):
    # `card_table` is bound in main and in thirteen modules of ptcg/: it has to be
    # set in all of them, or the function under test reads the one from ITS module.
    patch_name(
        monkeypatch,
        "card_table",
        {
            9001: SimpleNamespace(ex=False, megaEx=False, weakness=EnergyType.GRASS, resistance=EnergyType.FIRE, name="Weak"),
            9002: SimpleNamespace(ex=False, megaEx=False, weakness=EnergyType.FIRE, resistance=EnergyType.GRASS, name="Resist"),
        },
    )

    attacker = make_pokemon(m.Teal_Mask_Ogerpon_ex)
    weak_target = make_pokemon(9001)
    resist_target = make_pokemon(9002)

    assert m._our_effective_damage(attacker, weak_target, 60) == 120
    assert m._our_effective_damage(attacker, resist_target, 60) == 30

def test_process_logs_move_card_updates_tracking():
    m._move_card_state(m.Ultra_Ball, m.ZONE_DECK, m.ZONE_HAND)
    obs = SimpleNamespace(
        logs=[
            SimpleNamespace(
                type=LogType.MOVE_CARD,
                playerIndex=0,
                cardId=m.Ultra_Ball,
                fromArea=AreaType.HAND,
                toArea=AreaType.DISCARD,
            )
        ]
    )

    m._process_logs(obs, my_index=0)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_HAND] == 0
    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DISCARD] == 1

def test_identify_prizes_ignores_partial_reveal():
    before = m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DECK]
    obs = SimpleNamespace(
        select=SimpleNamespace(
            deck=[SimpleNamespace(id=m.Ultra_Ball)],
            effect=SimpleNamespace(id=m.Bug_Catching_Set),
        )
    )

    m._identify_prizes(obs, my_state=SimpleNamespace(deckCount=2))

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DECK] == before

def test_eval_ub_best_target_handles_turn_two_and_turn_one_branches():
    m.ACTIVE_CARDS_IN_DECK[m.Meowth_ex][m.ZONE_DECK] = 1
    m.ACTIVE_CARDS_IN_DECK[m.Lillie_Determination][m.ZONE_DECK] = 1

    turn_two_result = m._eval_ub_best_target(
        field_counts={m.Chikorita: 1},
        hand_counts={},
        meganium_in_play=False,
        has_hydrapple=False,
        forest_in_play=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_prize=2,
        bench_count=1,
        state=SimpleNamespace(turn=2, supporterPlayed=False),
        ko_last_turn=False,
        _best_supp_in_deck_val=900,
        supporters_in_hand=0,
        hand_is_weak=False,
        has_energy_for_teal=False,
        _we_go_first=False,
        _best_supp_in_hand_val=0,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_active_is_budew=False,
        meowth_ability_lock=False,
    )
    assert turn_two_result >= 900

    m.ACTIVE_CARDS_IN_DECK[m.Teal_Mask_Ogerpon_ex][m.ZONE_DECK] = 1
    turn_one_result = m._eval_ub_best_target(
        field_counts={m.Applin: 1},
        hand_counts={m.Basic_Grass_Energy: 1},
        meganium_in_play=False,
        has_hydrapple=False,
        forest_in_play=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_prize=2,
        bench_count=0,
        state=SimpleNamespace(turn=1, supporterPlayed=False),
        ko_last_turn=False,
        _best_supp_in_deck_val=0,
        supporters_in_hand=0,
        hand_is_weak=False,
        has_energy_for_teal=False,
        _we_go_first=True,
        _best_supp_in_hand_val=0,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_active_is_budew=False,
        meowth_ability_lock=False,
    )
    assert turn_one_result >= 950

def test_agent_selects_high_priority_play_option_in_main_context(monkeypatch):
    monkeypatch.setattr(m, "to_observation_class", lambda obs_dict: obs_dict)

    hand_card = SimpleNamespace(id=m.Chikorita)
    opponent_active = SimpleNamespace(id=m.Applin, hp=100, maxHp=100, energies=[])

    obs = SimpleNamespace(
        current=SimpleNamespace(
            turn=1,
            yourIndex=0,
            firstPlayer=0,
            energyAttached=False,
            supporterPlayed=False,
            players=[
                SimpleNamespace(
                    hand=[hand_card],
                    active=[None],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
                SimpleNamespace(
                    hand=[],
                    active=[opponent_active],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
            ],
            stadium=[],
            looking=[],
        ),
        select=SimpleNamespace(
            context=SelectContext.MAIN,
            option=[
                SimpleNamespace(type=OptionType.PLAY, index=0),
                SimpleNamespace(type=OptionType.END),
            ],
            minCount=1,
            maxCount=1,
            deck=None,
            effect=None,
        ),
        logs=[],
    )

    result = m.agent(obs)
    assert result == [0]

def test_agent_selects_positive_option_in_setup_bench_context(monkeypatch):
    monkeypatch.setattr(m, "to_observation_class", lambda obs_dict: obs_dict)

    hand_card = SimpleNamespace(id=m.Applin)
    opponent_active = SimpleNamespace(id=m.Chikorita, hp=100, maxHp=100, energies=[])

    obs = SimpleNamespace(
        current=SimpleNamespace(
            turn=2,
            yourIndex=0,
            firstPlayer=0,
            energyAttached=False,
            supporterPlayed=False,
            players=[
                SimpleNamespace(
                    hand=[hand_card],
                    active=[None],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
                SimpleNamespace(
                    hand=[],
                    active=[opponent_active],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
            ],
            stadium=[],
            looking=[],
        ),
        select=SimpleNamespace(
            context=SelectContext.SETUP_BENCH_POKEMON,
            option=[
                SimpleNamespace(type=OptionType.PLAY, index=0),
                SimpleNamespace(type=OptionType.END),
            ],
            minCount=1,
            maxCount=1,
            deck=None,
            effect=None,
        ),
        logs=[],
    )

    result = m.agent(obs)
    assert result == [0]

def test_agent_returns_deck_when_no_selection_is_available(monkeypatch):
    monkeypatch.setattr(m, "to_observation_class", lambda obs_dict: SimpleNamespace(select=None))
    assert m.agent({}) == m.my_deck
