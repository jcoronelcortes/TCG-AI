"""Regression slice 2 of 8. The Alakazam matchup (Xerosic, the bench
reservation), the Comfey plan and the Neutralization Zone."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

_BOSS_WIN_GUST_FIXTURE = ROOT / "tests" / "fixtures" / "dragapult_boss_win_gust_not_retreat_step190.json"

def test_dragapult_step190_plays_boss_win_gust_instead_of_retreating():
    with open(_BOSS_WIN_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    hand = obs["current"]["players"][1]["hand"]
    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and hand[o["index"]]["id"] == m.Boss_Orders)
    retreat_opts = [i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.RETREAT)]

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"debe jugar Boss's Orders (opt {boss_opt}) para gustear+rematar y ganar, "
        f"obtuvo {result}"
    )
    assert result[0] not in retreat_opts, "no retirar el activo teniendo un gusteo ganador"

_UB_CANCEL_FULL_BENCH_FIXTURE = ROOT / "tests" / "fixtures" / "hops_ultraball_cancel_full_bench_no_evo_step72.json"

def test_hops_step72_cancels_useless_ultraball_full_bench_no_evo_in_deck():
    with open(_UB_CANCEL_FULL_BENCH_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    final_obs = None
    result = None
    for item in seq:
        final_obs = item["observation"]
        result = m.agent(final_obs)

    options = final_obs["select"]["option"]
    hand = final_obs["current"]["players"][0]["hand"]
    ub_opts = [i for i, o in enumerate(options)
               if o.get("type") == int(OptionType.PLAY)
               and hand[o["index"]]["id"] == m.Ultra_Ball]

    assert result[0] not in ub_opts, (
        "no jugar una Ultra Ball inutil (banca llena y sin evolucion en el mazo); "
        f"obtuvo {result}"
    )

_TEAL_DANCE_BEFORE_ATTACH_FIXTURE = ROOT / "tests" / "fixtures" / "starmie_teal_dance_before_attach_step28.json"

def test_starmie_step28_teal_dance_before_manual_attach():
    with open(_TEAL_DANCE_BEFORE_ATTACH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    teal_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.ABILITY))
    _teal_slot = (options[teal_opt].get("area"), options[teal_opt].get("index"))
    ogerpon_attach_opts = [
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and (o.get("inPlayArea"), o.get("inPlayIndex")) == _teal_slot
    ]

    result = m.agent(obs)

    assert result == [teal_opt], (
        f"debe usar Teal Dance (opt {teal_opt}, adjunta + ROBA) antes de cargar "
        f"energia manualmente al Ogerpon ex; obtuvo {result}"
    )
    assert result[0] not in ogerpon_attach_opts, (
        "nunca cargar energia manualmente a un Ogerpon ex que aun puede usar Teal Dance"
    )

_UB_NO_ATTACKER_MEOWTH_FIXTURE = ROOT / "tests" / "fixtures" / "starmie_ub_meowth_no_attacker_step29.json"

def test_starmie_step29_ultraball_searches_meowth_when_no_usable_attacker():
    with open(_UB_NO_ATTACKER_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    deck = obs["select"]["deck"]
    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if deck[o["index"]]["id"] == m.Meowth_ex)
    meganium_opts = [i for i, o in enumerate(options)
                     if deck[o["index"]]["id"] == m.Meganium]

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"sin atacante usable este turno, Ultra Ball debe buscar Meowth ex "
        f"(opt {meowth_opt}) para el motor Lillie's; obtuvo {result}"
    )
    assert result[0] not in meganium_opts, (
        "no buscar un Meganium (evolucion sin ataque este turno) cuando no hay atacante usable"
    )

_ALAKAZAM_RETREAT_EX_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_retreat_ex_attack_meganium_step127.json"

_ALAKAZAM_PROMOTE_MEGANIUM_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_promote_meganium_1prize_step127.json"

def test_alakazam_step127_retreats_ex_to_attack_with_meganium():
    with open(_ALAKAZAM_RETREAT_EX_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"vs Alakazam, con un Meganium (1 premio) que noquea en banca, debe RETIRAR "
        f"el ex activo (opt {retreat_opt}) en vez de atacar con el ex (opt {attack_opt}); "
        f"obtuvo {result}"
    )

def test_alakazam_step127_promotes_meganium_1prize_over_ex():
    with open(_ALAKAZAM_PROMOTE_MEGANIUM_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    bench = obs["current"]["players"][1]["bench"]
    options = obs["select"]["option"]
    meganium_opt = next(i for i, o in enumerate(options)
                        if bench[o["index"]]["id"] == m.Meganium)
    ex_opts = [i for i, o in enumerate(options)
               if bench[o["index"]]["id"] in m.OUR_EX_IDS]

    result = m.agent(obs)

    assert result == [meganium_opt], (
        f"vs Alakazam, al promover tras retirar debe subir el Meganium (1 premio, "
        f"opt {meganium_opt}) que noquea, no un ex de 2 premios; obtuvo {result}"
    )
    assert result[0] not in ex_opts, "no promover un ex (2 premios) si Meganium noquea vs Alakazam"

_MARNIE_FROSLASS_MEOWTH_FIXTURE = ROOT / "tests" / "fixtures" / "marnie_froslass_meowth_dead_turn_step84.json"

def test_marnie_froslass_step84_plays_meowth_dead_turn_not_tapu():
    with open(_MARNIE_FROSLASS_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    hand = obs["current"]["players"][1]["hand"]
    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY)
                      and hand[o["index"]]["id"] == m.Meowth_ex)
    tapu_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and hand[o["index"]]["id"] == m.Tapu_Bulu)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"turno muerto vs Froslass: debe bajar Meowth ex (opt {meowth_opt}) para el "
        f"motor Lana's/Lillie's, no Tapu Bulu (opt {tapu_opt}); obtuvo {result}"
    )
    assert result[0] != tapu_opt, "no bajar un cuerpo redundante (Tapu Bulu) en un turno muerto"

_DURALUDON_TEAL_DANCE_FIXTURE = ROOT / "tests" / "fixtures" / "duraludon_teal_dance_ko_resistance_step93.json"

def test_duraludon_step93_teal_dance_for_ko_accounting_resistance():
    with open(_DURALUDON_TEAL_DANCE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    # Teal Dance (an ability) on the ACTIVE Ogerpon ex (area 4)
    teal_active_opt = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ABILITY)
        and o.get("area") == int(AreaType.ACTIVE))
    # Attaching a manual energy to a bench Tapu Bulu (what it used to do)
    bench = obs["current"]["players"][0]["bench"]
    tapu_attach_opts = [
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and o.get("inPlayArea") == int(AreaType.BENCH)
        and bench[o["inPlayIndex"]]["id"] == m.Tapu_Bulu]

    # UPDATED (July 2026 audit, the inline copies of Myriad corrected):
    # with the VERIFIED formula (30+30*(ours+theirs); the memory
    # ogerpon-myriad-cuenta-ambos-activos, 6 records of real damage), the
    # Duraludon of the fixture carries 1 energy -> 30+30*(4+1)=180 -> 150 after the
    # resistance >= 130: the active ALREADY knocks out WITHOUT Teal Dance, and charging the
    # future Tapu (the alakazam-cargar-meganium-atacante-futuro rule generalised by
    # _tapu_future_charge) is the right line. This test had been written
    # with the old "ours only" formula (voided as wrong).
    result = m.agent(obs)
    assert result[0] in tapu_attach_opts, (
        f"con el KO ya asegurado (180-30=150 >= 130) se carga el Tapu futuro; "
        f"obtuvo {result}")

    # A COUNTERFACTUAL (it preserves the test's original intent: the RESISTANCE
    # is accounted for): with the Duraludon WITHOUT energy, 30+30*4=150 -> 120 after
    # the resistance < 130 -> the active does NOT knock out and Teal Dance (it goes up to 6 of ours:
    # 30+30*6=210 -> 180 >= 130) enables the KO.
    import copy as _c
    obs2 = _c.deepcopy(obs)
    obs2["current"]["players"][1]["active"][0]["energies"] = []
    obs2["current"]["players"][1]["active"][0]["energyCards"] = []
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result2 = m.agent(obs2)
    assert result2 == [teal_active_opt], (
        f"sin energia rival la resistencia deja el golpe en 120 < 130: Teal "
        f"Dance en el activo habilita el KO; obtuvo {result2}")

def test_ogerpon_damage_counts_both_active_energy():
    # Myriad Leaf Shower (attack 120): 30 + 30 for each Energy attached to BOTH
    # Active Pokemon (ours + the rival's). Verified with the REAL damage of 6
    # records: own 3 + opp 2 -> 180; own 4 + opp 2 -> 210; own 4 + opp 0 -> 150;
    # own 3 + opp 1 -> 150. `_attacker_base_damage` returns the BASE damage (before
    # weakness/resistance), so it counts own(4)+target(3) = 7 -> 30+210 = 240.
    from types import SimpleNamespace as _NS
    tgt3 = _NS(id=169, hp=130, energies=[8, 8, 8], maxHp=130)   # 3 energy on the target
    base = m._attacker_base_damage(m.Teal_Mask_Ogerpon_ex, tgt3, 4,
                                   grass_scale=0, teal_self_energy=4, bench_count=5)
    assert base == 240, f"Myriad = 30+30*(propia 4 + objetivo 3) = 240; obtuvo {base}"
    # a target with no energy -> only ours counts (30+30*4 = 150)
    tgt0 = _NS(id=169, hp=130, energies=[], maxHp=130)
    base0 = m._attacker_base_damage(m.Teal_Mask_Ogerpon_ex, tgt0, 4,
                                    grass_scale=0, teal_self_energy=4, bench_count=5)
    assert base0 == 150, f"con objetivo sin energia = 30+30*4 = 150; obtuvo {base0}"

_CYNTHIA_BOSS_GUST_EVO_FIXTURE = ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json"

def test_cynthia_step51_boss_gusts_highest_evolution_gabite_not_gible():
    with open(_CYNTHIA_BOSS_GUST_EVO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    bench = obs["current"]["players"][0]["bench"]
    options = obs["select"]["option"]
    gabite_tool_opt = next(
        i for i, o in enumerate(options)
        if bench[o["index"]]["id"] == 380 and bench[o["index"]].get("tools"))
    gible_opts = [i for i, o in enumerate(options)
                  if bench[o["index"]]["id"] == 379]

    result = m.agent(obs)

    assert result == [gabite_tool_opt], (
        f"Boss's debe gustear el Cynthia's Gabite (mayor evolucion, opt {gabite_tool_opt}) "
        f"que podemos noquear, no el Gible basico; obtuvo {result}"
    )
    assert result[0] not in gible_opts, (
        "no gustear el basico (Gible) cuando podemos noquear la evolucion superior (Gabite)"
    )

def _comfey_main_obs(ogerpon_field, comfey=True):
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    if comfey:
        op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                         "hp": 70, "id": 164, "maxHp": 70, "playerIndex": 0,
                         "preEvolution": [], "serial": 900, "tools": []}]
        op["bench"] = []
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 210,
                    "id": 96, "maxHp": 210, "playerIndex": 1, "preEvolution": [],
                    "serial": 810 + k, "tools": []} for k in range(max(0, ogerpon_field - 1))]
    me["hand"] = [{"id": 96, "playerIndex": 1, "serial": 820},
                  {"id": 710, "playerIndex": 1, "serial": 821},
                  {"id": 1121, "playerIndex": 1, "serial": 822}]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"index": 0, "type": 7}, {"index": 1, "type": 7},
                              {"index": 2, "type": 7}, {"type": 14}]}
    cur["yourIndex"] = 1
    return o

def _score_by_hand_id(obs):
    captured = {}
    orig = m._debug_log_decision
    def spy(context, select, scores, obs_, my_index, top_n=3):
        captured["s"] = list(scores)
    _restaurar_spy = instalar("_debug_log_decision", spy)
    m.DEBUG_DECISIONS = True
    try:
        m._init_cards_tracking(); m.plan = m.AttackPlan()
        m.agent(obs)
    finally:
        _restaurar_spy()
    me = obs["current"]["players"][1]
    out = {}
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(OptionType.PLAY):
            out[me["hand"][o["index"]]["id"]] = captured["s"][i]
    return out

def test_comfey_rule1_only_ogerpon_max_two_and_veto_others():
    # With 0 Ogerpon ex in play: playing an Ogerpon ex is OK, another Pokemon vetoed.
    s0 = _score_by_hand_id(_comfey_main_obs(0, comfey=True))
    assert s0[m.Teal_Mask_Ogerpon_ex] > 0, "vs Comfey debe poder bajar Teal Mask Ogerpon ex"
    assert s0[m.Meganium] == -1, "vs Comfey NO se baja ningun Pokemon que no sea Ogerpon ex"
    # With 2 Ogerpon ex in play: do not play a 3rd.
    s2 = _score_by_hand_id(_comfey_main_obs(2, comfey=True))
    assert s2[m.Teal_Mask_Ogerpon_ex] == -1, "maximo 2 Teal Mask Ogerpon ex vs Comfey"

def test_comfey_rule5_cancel_ultraball_when_two_ogerpon():
    s2 = _score_by_hand_id(_comfey_main_obs(2, comfey=True))
    assert s2[m.Ultra_Ball] < 0, "vs Comfey con 2 Ogerpon ex, la Ultra Ball es inutil -> cancelar"

def test_comfey_rules_do_not_fire_vs_other_decks():
    # Control: without Comfey, Meganium is played normally and the Ultra Ball is not cancelled.
    s = _score_by_hand_id(_comfey_main_obs(0, comfey=False))
    assert s[m.Meganium] > 0, "vs un mazo normal, la regla Ogerpon-only NO debe vetar otros Pokemon"

def _comfey_supporter_obs(hand_size, grass_discard, comfey=True, ogerpon=False,
                          deck_count=None):
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    cur["supporterPlayed"] = False; cur["stadiumPlayed"] = False
    cur["energyAttached"] = False; cur["turn"] = 5
    if comfey:
        op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                         "hp": 70, "id": 164, "maxHp": 70, "playerIndex": 0,
                         "preEvolution": [], "serial": 900, "tools": []}]
        op["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 40,
                        "id": 92, "maxHp": 40, "playerIndex": 0, "preEvolution": [],
                        "serial": 901, "tools": []}]
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = []
    hand = [{"id": m.Lillie_Determination, "playerIndex": 1, "serial": 820},
            {"id": m.Lanas_Aid, "playerIndex": 1, "serial": 821},
            {"id": m.Dawn, "playerIndex": 1, "serial": 822}]
    # `ogerpon` puts a PRODUCTIVE PLAY in the menu without altering the hand
    # size (it replaces a filler): with an empty bench, playing Teal Mask
    # Ogerpon ex scores 22000 vs Comfey (Rule 1). It is needed to isolate the
    # Supporter PRIORITY rules from the dead-turn rescue: with no real
    # play, the rescue lifts the Lillie's veto on purpose.
    relleno = max(0, hand_size - 3 - (1 if ogerpon else 0))
    for k in range(relleno):
        hand.append({"id": 1, "playerIndex": 1, "serial": 830 + k})
    options = [{"index": 0, "type": 7}, {"index": 1, "type": 7},
                {"index": 2, "type": 7}]
    if ogerpon:
        hand.append({"id": m.Teal_Mask_Ogerpon_ex, "playerIndex": 1, "serial": 890})
        options.append({"index": len(hand) - 1, "type": 7})
    options.append({"type": 14})
    me["hand"] = hand
    if deck_count is not None:
        me["deckCount"] = deck_count
    me["discard"] = [{"id": 1, "playerIndex": 1, "serial": 700 + k}
                     for k in range(grass_discard)]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0, "option": options}
    cur["yourIndex"] = 1
    return o

def test_comfey_lillie_only_with_ten_or_more_cards():
    # With a productive play in the menu (playing an Ogerpon) the PRIORITY rule
    # rules: vs Comfey, Lillie's only comes in with a hand >= 10.
    s10 = _score_by_hand_id(_comfey_supporter_obs(10, 1, comfey=True, ogerpon=True))
    assert s10[m.Lillie_Determination] > 0, "vs Comfey con mano>=10 se puede jugar Lillie's"
    s9 = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True, ogerpon=True))
    assert s9[m.Lillie_Determination] == -1, "vs Comfey con mano<10 NO se juega Lillie's"

def test_comfey_dead_turn_plays_lillie_even_with_a_short_hand():
    s = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True, ogerpon=False))
    assert s[m.Lillie_Determination] > 0, (
        "sin ninguna jugada productiva el turno muere: hay que refrescar con "
        f"Lillie's en vez de terminar; obtuvo {s[m.Lillie_Determination]}")

def test_comfey_dead_turn_respects_the_deckout_brake():
    # The same dead turn but with a CRITICAL deck: with 9 cards in hand and the 6
    # prizes intact Lillie's draws 8, so the deck stays the same (6) --- below
    # the threshold. There the anti-mill reservation DOES rule and the veto holds.
    s = _score_by_hand_id(
        _comfey_supporter_obs(9, 1, comfey=True, ogerpon=False, deck_count=6))
    assert s[m.Lillie_Determination] == -1, (
        "con el mazo critico refrescar acerca el deck-out: el veto debe "
        f"aguantar aunque el turno muera; obtuvo {s[m.Lillie_Determination]}")

def test_comfey_lana_only_when_recovers_two_energies():
    s2 = _score_by_hand_id(_comfey_supporter_obs(9, 2, comfey=True))
    assert s2[m.Lanas_Aid] > 0, "vs Comfey con >=2 energias en descarte, Lana's Aid es jugable"
    s1 = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True))
    assert s1[m.Lanas_Aid] == -1, "vs Comfey con <2 energias recuperables NO se juega Lana's Aid"

def test_comfey_vetoes_other_trainers_like_dawn():
    s = _score_by_hand_id(_comfey_supporter_obs(10, 2, comfey=True))
    assert s[m.Dawn] == -1, "vs Comfey NO se juegan otros entrenadores (p.ej. Dawn)"
    # Control: without Comfey, Dawn is played as usual.
    sc = _score_by_hand_id(_comfey_supporter_obs(9, 2, comfey=False))
    assert sc[m.Dawn] > 0, "vs un mazo normal, Dawn NO debe estar vetada por la regla Comfey"

def _comfey_discard_obs():
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 70,
                     "id": 164, "maxHp": 70, "playerIndex": 0, "preEvolution": [],
                     "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = []
    # hand: 2 grass, Night Stretcher, Lana's, Unfair Stamp, Dawn (rest), Ogerpon
    me["hand"] = [{"id": 1, "serial": 1, "playerIndex": 1},
                  {"id": 1, "serial": 2, "playerIndex": 1},
                  {"id": m.Night_Stretcher, "serial": 3, "playerIndex": 1},
                  {"id": m.Lanas_Aid, "serial": 4, "playerIndex": 1},
                  {"id": m.Unfair_Stamp, "serial": 5, "playerIndex": 1},
                  {"id": m.Dawn, "serial": 6, "playerIndex": 1},
                  {"id": 96, "serial": 7, "playerIndex": 1}]
    o["select"] = {"context": 8, "contextCard": None, "deck": None,
                   "effect": {"id": 1197, "playerIndex": 1, "serial": 999},
                   "maxCount": 4, "minCount": 4, "type": 1, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"area": 2, "index": i, "playerIndex": 1, "type": 3}
                              for i in range(7)]}
    cur["yourIndex"] = 1
    return o

def test_comfey_rule2_xerosic_keeps_energy_over_trainers():
    obs = _comfey_discard_obs()
    hand = obs["current"]["players"][1]["hand"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    discarded = set(m.agent(obs))  # the indices of the 4 cards to discard
    discarded_ids = [hand[obs["select"]["option"][i]["index"]]["id"] for i in discarded]
    # The energies are KEPT (they are never discarded).
    assert m.Basic_Grass_Energy not in discarded_ids, "vs Comfey/Xerosic las energias se mantienen"
    # The rest of the trainers (Dawn) are discarded before Night Stretcher/Lana's.
    assert m.Dawn in discarded_ids, "vs Comfey/Xerosic se descarta el resto de entrenadores (Dawn)"

def _comfey_confused_obs(bench_ready):
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    me["confused"] = True
    cur["supporterPlayed"] = False; cur["energyAttached"] = False; cur["turn"] = 6
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 70,
                     "id": 164, "maxHp": 70, "playerIndex": 0, "preEvolution": [],
                     "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = [{"appearThisTurn": False, "energies": [1, 1, 1] if bench_ready else [],
                    "energyCards": [], "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                    "preEvolution": [], "serial": 810, "tools": []}]
    me["hand"] = []
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"attackId": 120, "type": 13}, {"type": 12}, {"type": 14}]}
    cur["yourIndex"] = 1
    return o

def test_comfey_rule4_confused_active_retreats_to_bench_attacker():
    obs = _comfey_confused_obs(bench_ready=True)
    retreat_opt = next(i for i, o in enumerate(obs["select"]["option"])
                       if o.get("type") == int(OptionType.RETREAT))
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [retreat_opt], (
        "activo confundido con atacante de banca listo: retirar (promover el cuerpo NO confundido)"
    )

def test_comfey_rule4_confused_active_attacks_when_no_bench_attacker():
    obs = _comfey_confused_obs(bench_ready=False)
    attack_opt = next(i for i, o in enumerate(obs["select"]["option"])
                      if o.get("type") == int(OptionType.ATTACK))
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [attack_opt], (
        "activo confundido sin atacante de banca: atacar con el confundido (aceptar la moneda)"
    )

_ZONE_BOSS_GUST_EX_FIXTURE = ROOT / "tests" / "fixtures" / "zone_boss_gust_bench_ex_step.json"

def test_zone_promote_nonex_over_ex_when_active_single_prize():
    # After a KO, with the Neutralization Zone in play and the rival ACTIVE worth 1
    # prize (Alakazam-like), promote the NON-ex attacker (Meganium) instead of an
    # ex (Ogerpon ex) which under the zone does 0 damage to that active.
    with open(_ZONE_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    assert obs["current"]["stadium"][0]["id"] == m.Neutralization_Zone
    options = obs["select"]["option"]
    ex_opt = next(i for i, o in enumerate(options) if o.get("index") == 0)      # Ogerpon ex
    nonex_opt = next(i for i, o in enumerate(options) if o.get("index") == 1)   # Meganium
    result = m.agent(obs)
    assert result == [nonex_opt], (
        f"bajo la zona con activo rival de 1 premio, promover el NO-ex Meganium "
        f"(opt {nonex_opt}), no el ex Ogerpon (opt {ex_opt}); obtuvo {result}")
    assert result != [ex_opt]

def test_zone_promote_ex_when_active_is_ex():
    # A positive control: if the rival ACTIVE is an ex (a rule box), our
    # ex DO damage under the zone, so the ex is promoted (Ogerpon ex).
    with open(_ZONE_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    # op active -> Iono's Bellibolt ex (269, a rule box), 130hp (our ex KOs it)
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 130, "id": 269, "maxHp": 280, "playerIndex": 1 - yi,
                     "preEvolution": [], "serial": 301, "tools": []}]
    # The original fixture brings Abra/Kadabra in the rival DISCARD; with the
    # archetype inference by discard (the July 2026 audit) that switches on
    # `op_is_alakazam_deck` and the 1-prize rule would dominate the promotion
    # (correct vs Alakazam, but this test is the positive control of the
    # ZONE LOGIC). The discard is cleaned to isolate what is being tested.
    op["discard"] = [c for c in op["discard"]
                     if c["id"] not in (m.Abra, m.Kadabra, m.Alakazam_ex)]
    options = obs["select"]["option"]
    ex_opt = next(i for i, o in enumerate(options) if o.get("index") == 0)      # Ogerpon ex
    nonex_opt = next(i for i, o in enumerate(options) if o.get("index") == 1)   # Meganium
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [ex_opt], (
        f"activo rival ex bajo la zona: nuestros ex SI danan, promover el ex "
        f"(opt {ex_opt}), no el no-ex (opt {nonex_opt}); obtuvo {result}")

def test_zone_boss_gust_bench_ex():
    # With the Neutralization Zone, a 1-prize rival active (our ex does 0)
    # and a rival ex on the BENCH that our ex CAN knock out: play Boss's
    # Orders to gust the bench ex and finish it off (the 2 prizes / the game).
    with open(_ZONE_BOSS_GUST_EX_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    assert obs["current"]["stadium"][0]["id"] == m.Neutralization_Zone
    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o.get("index") == 0)
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [boss_opt], (
        f"bajo la zona, gustear con Boss's al ex del rival en banca para poder "
        f"atacarlo con nuestro ex (opt {boss_opt}); obtuvo {result}")

_ALK_CHARGE_MEGANIUM_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_charge_meganium_future_step108.json")

def test_alakazam_step108_charges_bench_meganium_before_attacking():
    with open(_ALK_CHARGE_MEGANIUM_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    # a manual attachment (type 8) to the bench Meganium (inPlayArea 5, inPlayIndex 2)
    meganium_attach = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and o.get("inPlayArea") == 5 and o.get("inPlayIndex") == 2)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meganium_attach], (
        f"vs Alakazam, con el activo asegurando su KO, cargar el Meganium de banca "
        f"(opt {meganium_attach}) como atacante de 1 premio antes de atacar; "
        f"no atacar de una (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]

_LUCARIO_FRAGILE_EX_SAC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "lucario_retreat_fragile_ex_sac_step110.json")

def test_lucario_step110_ripening_charge_to_retreat_fragile_ex_not_attack():
    with open(_LUCARIO_FRAGILE_EX_SAC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    ability_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.ABILITY))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [attack_opt], (
        f"no atacar con el Hydrapple ex fragil (opt {attack_opt}): quedaria activo y "
        f"cederia 2 premios; obtuvo {result}")
    assert result == [ability_opt], (
        f"usar Ripening Charge (opt {ability_opt}) para habilitar la retirada del ex "
        f"fragil y promover un atacante de 1 premio; obtuvo {result}")

_MEWTWO_BOSS_GUST_FIXTURE = (
    ROOT / "tests" / "fixtures" / "mewtwo_boss_gust_2prize_step119.json")

def test_mewtwo_step119_boss_gust_2prize_over_attacking_active():
    with open(_MEWTWO_BOSS_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o.get("index") == 0)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"jugar Boss's (opt {boss_opt}) para gustear+noquear el Mewtwo ex de banca "
        f"(2 premios), no atacar al activo de 1 premio (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]

def _load_xerosic_obs():
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]

def test_xerosic_played_vs_alakazam_big_hand():
    # A rival hand of 8 (Powerful Hand threatens 160): play Xerosic (opt 0), above
    # a hydra-charged Lillie's (5800) which would also shuffle the Xerosic away.
    obs = _load_xerosic_obs()
    assert obs["current"]["players"][1]["handCount"] == 8
    result = m.agent(obs)
    assert result == [0], (
        f"vs Alakazam con mano rival 8, jugar Xerosic (opt 0) para capar "
        f"Powerful Hand; obtuvo {result}")

def test_xerosic_vetoed_when_op_hand_small():
    # A rival hand <= 3: Xerosic does nothing -> vetoed; the Lillie's is played.
    obs = _load_xerosic_obs()
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][1]["handCount"] = 3
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [0], (
        f"con mano rival 3 Xerosic no tiene efecto: NO jugarlo; obtuvo {result}")
    assert result == [1], (
        f"con Xerosic vetado, el supporter del turno es Lillie's (opt 1); "
        f"obtuvo {result}")

def test_xerosic_vetoed_when_supporter_played():
    # The supporter already played: Xerosic and Lillie's vetoed -> attack (opt 2).
    obs = _load_xerosic_obs()
    obs = _copy.deepcopy(obs)
    obs["current"]["supporterPlayed"] = True
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [2], (
        f"con supporter jugado, ni Xerosic ni Lillie's: atacar (opt 2); "
        f"obtuvo {result}")

_MEOWTH_FETCH_XEROSIC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_meowth_fetch_xerosic.json")

def test_meowth_fetch_xerosic_vs_alakazam_big_hand():
    with open(_MEOWTH_FETCH_XEROSIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    assert obs["select"]["deck"][2]["id"] == 1197
    result = m.agent(obs)
    assert result == [2], (
        f"vs Alakazam con mano rival 8, Meowth debe buscar Xerosic (opt 2); "
        f"obtuvo {result}")

def test_meowth_fetch_not_xerosic_when_op_hand_small():
    with open(_MEOWTH_FETCH_XEROSIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][1]["handCount"] = 3
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [2], (
        f"con mano rival 3, Xerosic no aporta: buscar otro supporter; obtuvo {result}")

_ALK_RESERVE_BENCH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_reserve_bench_slot.json")

def test_alakazam_reserve_last_bench_slot_for_meowth():
    # Hand: a 2nd Teal Mask Ogerpon ex (a duplicate; there is already one on the bench).
    with open(_ALK_RESERVE_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    assert obs["current"]["players"][0]["hand"][0]["id"] == 96
    assert len(obs["current"]["players"][0]["bench"]) == 4
    result = m.agent(obs)
    assert result != [0], (
        f"con banca 4/5 y Meowth pendiente vs Alakazam, NO bajar un duplicado "
        f"(reservar el slot para Meowth ex); obtuvo {result}")
    assert result == [1], f"la jugada correcta es atacar (opt 1); obtuvo {result}"

def test_alakazam_reserve_allows_line_pieces():
    # A positive control: a FIRST copy of Applin (it advances the Hydrapple line)
    # IS played even with the reservation active.
    with open(_ALK_RESERVE_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][0]["hand"][0]["id"] = 92
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [0], (
        f"la reserva no debe bloquear piezas de linea (Applin, 1ra copia); "
        f"obtuvo {result}")

_ALK_RESERVE_MEOWTH_ON_BENCH_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step150_reserva_con_meowth_en_banca.json")

def _alk_reserve_obs():
    with open(_ALK_RESERVE_MEOWTH_ON_BENCH_FIXTURE, encoding="utf-8") as f:
        return _copy.deepcopy(json.load(f)["observation"])

def _alk_reserve_run(obs):
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    return m.agent(obs)

def test_alakazam_reserves_the_slot_with_a_meowth_already_benched():
    obs = _alk_reserve_obs()
    me = obs["current"]["players"][0]
    assert [b["id"] for b in me["bench"]] == [709, 96, 150, 1071]
    assert me["hand"][3]["id"] == 96  # a 3rd Teal Mask Ogerpon ex (a duplicate)
    result = _alk_reserve_run(obs)
    assert result != [3], (
        f"con un Meowth ex de turnos anteriores en banca la Last-Ditch sigue "
        f"libre: el ultimo slot se reserva y NO se baja el 3er Ogerpon ex; "
        f"obtuvo {result}")
    assert result == [27], (
        f"la jugada correcta es Ripening Charge sobre el Hydrapple ex de banca "
        f"(opt 27); obtuvo {result}")

_ALK_OPPONENT_HAND_NO_FINISHER = 8

def _alk_no_finisher(obs):
    obs["current"]["players"][1]["handCount"] = _ALK_OPPONENT_HAND_NO_FINISHER
    return obs

def test_alakazam_reservation_off_when_the_last_ditch_is_spent():
    # A negative control: the bench Meowth ex APPEARED THIS TURN -> its
    # Last-Ditch is already spent and a 2nd Meowth would search for nothing. With no engine to
    # take the slot there is nothing to reserve: the body is played again.
    obs = _alk_no_finisher(_alk_reserve_obs())
    for b in obs["current"]["players"][0]["bench"]:
        if b["id"] == 1071:
            b["appearThisTurn"] = True
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"con la Last-Ditch del turno gastada la reserva no aplica; "
        f"obtuvo {result}")

def test_alakazam_reservation_off_with_no_reachable_meowth():
    # A negative control: the 2nd copy of Meowth ex is in the DISCARD -> no
    # body is left that could take the reserved slot.
    obs = _alk_no_finisher(_alk_reserve_obs())
    obs["current"]["players"][0]["discard"].append(
        {"id": 1071, "playerIndex": 0, "serial": 19})
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"sin Meowth ex alcanzable la reserva no aplica; obtuvo {result}")

def test_alakazam_reservation_off_with_no_xerosic_in_the_deck():
    # A negative control: the 2nd Xerosic to the discard as well -> there is no disruption
    # to dig for, the slot is not worth more than the body.
    obs = _alk_no_finisher(_alk_reserve_obs())
    obs["current"]["players"][0]["discard"].append(
        {"id": 1197, "playerIndex": 0, "serial": 62})
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"sin Xerosic en el mazo la reserva no aplica; obtuvo {result}")

def _alk_no_reservation(obs):
    obs["current"]["players"][0]["discard"].append(
        {"id": 1071, "playerIndex": 0, "serial": 19})
    return obs

def test_alakazam_does_not_play_a_redundant_ex_under_a_lethal_powerful_hand():
    obs = _alk_no_reservation(_alk_reserve_obs())
    op = obs["current"]["players"][1]
    assert op["handCount"] == 12 and len(op["prize"]) == 2
    assert m._powerful_hand_projected(op["handCount"]) >= 210  # Ogerpon ex HP
    result = _alk_reserve_run(obs)
    assert result != [3], (
        f"con Powerful Hand proyectado 280 >= 210 PV y el rival a 2 premios, "
        f"un 3er Teal Mask Ogerpon ex es un remate servido: no se baja; "
        f"obtuvo {result}")

def test_alakazam_ex_redundante_ok_si_powerful_hand_no_remata():
    # A negative control: a rival hand of 8 -> 20 x 10 = 200 < 210 HP. The body does NOT
    # die in one blow, the veto does not apply and the duplicate is played again.
    obs = _alk_no_finisher(_alk_no_reservation(_alk_reserve_obs()))
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"si Powerful Hand no remata al cuerpo, el veto no aplica; "
        f"obtuvo {result}")

def test_alakazam_a_redundant_ex_is_fine_if_the_opponent_is_far_from_its_prizes():
    # A negative control: the rival at 4 prizes. Even if Powerful Hand finishes, one more
    # target does not close the game: normal development continues.
    obs = _alk_no_reservation(_alk_reserve_obs())
    obs["current"]["players"][1]["prize"] = [None] * 4
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"con el rival a 4 premios el veto no aplica; obtuvo {result}")

_ALK_DISCARD_XEROSIC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_discard_protect_xerosic.json")

def test_discard_protects_xerosic_vs_alakazam():
    with open(_ALK_DISCARD_XEROSIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    result = m.agent(obs)
    discarded = [obs["current"]["players"][0]["hand"][i]["id"] for i in result]
    assert 1197 not in discarded, (
        f"vs Alakazam nunca descartar el Xerosic para pagar costes; descarto {discarded}")

_MARNIE_FETCH_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_meowth_fetch_lillie_no_forest_step53.json")

def test_marnie_step53_meowth_fetch_lillie_not_dawn_without_forest():
    with open(_MARNIE_FETCH_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dawn_opt = next(i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1231)
    lillie_opts = [i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1227]
    # Forest of Vitality is NOT in play (there is the rival's Spikemuth Gym).
    assert 1261 not in [s["id"] for s in (obs["current"].get("stadium") or [])]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [dawn_opt], (
        f"sin Forest of Vitality en juego, NO buscar Dawn (opt {dawn_opt}); obtuvo {result}")
    assert result[0] in lillie_opts, (
        f"buscar Lillie's (opts {lillie_opts}) para refrescar la mano; obtuvo {result}")

def test_marnie_step53_meowth_fetch_dawn_when_forest_in_play():
    # A positive control: with Forest of Vitality (1261) IN PLAY, Dawn keeps its
    # value (we can rush the evolution) and is the best search again.
    import copy as _c
    with open(_MARNIE_FETCH_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    obs["current"]["stadium"] = [{"id": 1261, "playerIndex": 0, "serial": 999}]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dawn_opt = next(i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1231)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [dawn_opt], (
        f"con Forest en juego, Dawn (opt {dawn_opt}) sigue siendo la mejor busqueda; "
        f"obtuvo {result}")
