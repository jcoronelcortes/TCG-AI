"""Regression slice 3 of 8. The Archaludon wall pivots, the Meowth chains and
the Last-Ditch fetch."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

_ARCHALUDON_WALL_PIVOT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_wall_pivot_ogerpon_to_hydra_step84.json")

def test_archaludon_step84_retreat_ogerpon_to_hydra_wall():
    with open(_ARCHALUDON_WALL_PIVOT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"retirar el Ogerpon ex condenado (opt {retreat_opt}) para promover el "
        f"muro Hydrapple ex que sobrevive, no atacar con el Ogerpon fragil "
        f"(opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]

def test_archaludon_wall_pivot_not_when_wall_would_die():
    # A counterfactual: if the bench Hydrapple ex wall did NOT survive the rival
    # blow (we drop its life below the 220 damage), the pivot must NOT
    # fire: retreating to expose a body that dies anyway gains nothing,
    # so the agent attacks with the active again.
    import copy as _c
    with open(_ARCHALUDON_WALL_PIVOT_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    bench = obs["current"]["players"][0]["bench"]
    hydra = next(p for p in bench if p is not None and p["id"] == 150)
    hydra["hp"] = 200  # < 220 (Metal Defender) -> the wall would die
    hydra["maxHp"] = 200

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"si el muro Hydrapple no sobrevive (200 < 220), no pivotar: atacar "
        f"con el activo (opt {attack_opt}); obtuvo {result}")

def test_op_active_attack_damage_to_resolves_ids():
    # The helper must RESOLVE the damage of the rival active's attack (the
    # card.attacks are IDs, not objects) and apply weakness/resistance.
    arch = SimpleNamespace(id=190, energies=[8, 8, 8])   # Archaludon ex, Metal Defender 220
    oger = SimpleNamespace(id=96, hp=210)                # Ogerpon ex (not weak to Metal)
    hydra = SimpleNamespace(id=150, hp=330)              # Hydrapple ex
    assert m._op_active_attack_damage_to(arch, oger) == 220
    assert m._op_active_attack_damage_to(arch, hydra) == 220
    # no active or no target -> 0
    assert m._op_active_attack_damage_to(None, oger) == 0
    assert m._op_active_attack_damage_to(arch, None) == 0

_DRAGAPULT_MEOWTH_WIN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "dragapult_step148_play_meowth_boss_win_engine.json")

def test_dragapult_step148_play_meowth_for_boss_win_engine():
    with open(_DRAGAPULT_MEOWTH_WIN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    play_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [play_opt], (
        f"a 1 premio de ganar, JUGAR Meowth ex (opt {play_opt}) para el motor "
        f"Boss's (Last-Ditch -> Boss's -> gustear+noquear un basico), no atacar "
        f"al activo rival que no muere (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]

def test_dragapult_meowth_win_engine_needs_last_ditch_free():
    # A counterfactual: if the bench Meowth ex appeared THIS turn, its Last-Ditch
    # is already spent ("no more than 1 per turn"), so playing another Meowth would NOT search for
    # Boss's -> the engine does not apply and the agent attacks again.
    import copy as _c
    with open(_DRAGAPULT_MEOWTH_WIN_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    for p in obs["current"]["players"][1]["bench"]:
        if p is not None and p["id"] == 1071:
            p["appearThisTurn"] = True

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con Last-Ditch ya gastado este turno, NO jugar un 2o Meowth ex: "
        f"atacar (opt {attack_opt}); obtuvo {result}")

_ARCHALUDON_ATTACK_ACTIVE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step75_attack_active_duraludon_not_boss_bench.json")

def test_archaludon_step75_attack_active_duraludon_not_boss_bench():
    with open(_ARCHALUDON_ATTACK_ACTIVE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and obs["current"]["players"][0]["hand"][o["index"]]["id"] == 1182)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"ATACAR el Duraludon activo (opt {attack_opt}), no jugar Boss's "
        f"(opt {boss_opt}) para gustear el Duraludon debil de banca; obtuvo {result}")
    assert result != [boss_opt]

def test_archaludon_step75_still_boss_when_active_is_nonthreat():
    # A positive control (registro_007): if the active is NOT a threat pre-evo
    # (e.g. Cinderace 666, 1 prize) but on the bench there is a gustable+
    # knockout-able Duraludon, Boss's IS played to gust the pre-evo (the same prize, it removes
    # the future attacker). The fix only switches the gust off when the active is the
    # SAME class of threat and equally or more developed.
    import copy as _c
    with open(_ARCHALUDON_ATTACK_ACTIVE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    a = obs["current"]["players"][1]["active"][0]
    a["id"] = 666; a["maxHp"] = 160; a["hp"] = 160; a["energies"] = [2]; a["tools"] = []

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and obs["current"]["players"][0]["hand"][o["index"]]["id"] == 1182)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"con un activo NO-amenaza (Cinderace), SI jugar Boss's (opt {boss_opt}) "
        f"para gustear el Duraludon de banca; obtuvo {result}")

_IONO_BOSS_GUST_2PRIZE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iono_step161_boss_gust_bellibolt_ex_2prize.json")

def test_iono_step161_boss_gust_bellibolt_ex_over_attacking_voltorb():
    with open(_IONO_BOSS_GUST_2PRIZE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and obs["current"]["players"][0]["hand"][o["index"]]["id"] == 1182)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"jugar Boss's (opt {boss_opt}) para gustear+noquear el Bellibolt ex de "
        f"banca (2 premios), no atacar al Voltorb activo de 1 premio "
        f"(opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]

def test_iono_step161_boss_gust_target_is_bellibolt_ex():
    # When resolving the gust's target (the SWITCH context), pick an Iono's
    # Bellibolt ex (2 prizes, 280 HP), not a Kilowattrel/Voltorb worth 1 prize.
    import copy as _c
    with open(_IONO_BOSS_GUST_2PRIZE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    cur = obs["current"]
    cur["supporterPlayed"] = True
    cur["players"][0]["hand"] = [c for c in cur["players"][0]["hand"] if c["id"] != 1182]
    opbench = cur["players"][1]["bench"]
    obs["select"] = {
        "context": 3, "contextCard": None, "deck": None,
        "effect": {"id": 1182, "playerIndex": 0, "serial": 28},
        "maxCount": 1, "minCount": 1,
        "option": [{"area": 5, "index": i, "playerIndex": 1, "type": 3}
                   for i in range(len(opbench))],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    picked = opbench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert picked == 269, (
        f"gustear un Iono's Bellibolt ex (269, 2 premios), no id {picked}; "
        f"obtuvo {result}")

_HOPS_UB_MEOWTH_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures" / "hops_ub_meowth_play_after_fetch_step71.json")

def test_hops_step71_plays_ub_fetched_meowth_before_attacking():
    with open(_HOPS_UB_MEOWTH_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    result = None
    target = None
    for item in seq:
        target = item["observation"]
        result = m.agent(target)

    assert target["current"]["turnActionCount"] == 10, "el ultimo frame debe ser el paso 71"
    play_map = _resolve_play_options(target)
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    assert result == [meowth_opt], (
        f"tras buscar Meowth ex con Ultra Ball debe BAJARLO (opt {meowth_opt}) "
        f"para encadenar Lillie's antes de atacar; obtuvo {result}")

def test_hops_step71_ub_meowth_not_played_if_supporter_already_played():
    # A counterfactual (it keeps the rule of record 006 p57 vs Alakazam): if the
    # Supporter has ALREADY been played this turn, the searched Lillie's could not be played ->
    # do NOT play the searched Meowth ex; attack.
    import copy as _c
    with open(_HOPS_UB_MEOWTH_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    result = None
    for item in seq:
        obs = item["observation"]
        if item.get("tac") == 10:
            obs = _c.deepcopy(obs)
            obs["current"]["supporterPlayed"] = True
        result = m.agent(obs)

    options = seq[-1]["observation"]["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    assert result == [attack_opt], (
        f"con el Supporter ya jugado, no bajar el Meowth buscado: atacar "
        f"(opt {attack_opt}); obtuvo {result}")

_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_ub_meowth_second_copy_fetch_xerosic_step53.json")

def _alakazam_meowth2_build_fetch(s53_obs):
    import copy as _c
    o2 = _c.deepcopy(s53_obs)
    me = o2["current"]["players"][0]
    me["hand"].pop(0)
    me["bench"].append({"appearThisTurn": True, "energies": [], "energyCards": [],
                        "hp": 170, "id": 1071, "maxHp": 170, "playerIndex": 0,
                        "preEvolution": [], "serial": 20, "tools": []})
    deck = [{"id": 1227, "playerIndex": 0, "serial": 26},
            {"id": 1197, "playerIndex": 0, "serial": 43},
            {"id": 1182, "playerIndex": 0, "serial": 29},
            {"id": 1227, "playerIndex": 0, "serial": 24},
            {"id": 1227, "playerIndex": 0, "serial": 25},
            {"id": 1182, "playerIndex": 0, "serial": 28},
            {"id": 1184, "playerIndex": 0, "serial": 30}]
    o2["select"] = {"context": 7, "contextCard": None, "deck": deck,
                    "effect": {"id": 1071, "playerIndex": 0, "serial": 20},
                    "maxCount": 1, "minCount": 0,
                    "option": [{"area": 1, "index": i, "playerIndex": 0, "type": 3}
                               for i in range(len(deck))],
                    "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}
    return o2, deck

def test_alakazam_step53_plays_second_ub_meowth_with_one_in_field():
    with open(_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    result = None
    target = None
    for item in seq:
        target = item["observation"]
        result = m.agent(target)
    play_map = _resolve_play_options(target)
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    assert result == [meowth_opt], (
        f"con un Meowth de turnos previos en banca (Last-Ditch libre), el 2o "
        f"Meowth buscado por Ultra Ball debe bajarse (opt {meowth_opt}); obtuvo {result}")

def test_alakazam_step53_last_ditch_fetches_xerosic_with_strong_attacker():
    with open(_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    s53 = None
    for item in seq:
        s53 = item["observation"]
        m.agent(s53)
    o2, deck = _alakazam_meowth2_build_fetch(s53)
    result = m.agent(o2)
    picked = deck[o2["select"]["option"][result[0]]["index"]]["id"]
    assert picked == 1197, (
        f"vs Alakazam (mano rival 13) con atacante fuerte en juego, Last-Ditch "
        f"debe buscar Xerosic (1197) aunque nuestra mano quede vacia; busco id {picked}")

def test_alakazam_step53_last_ditch_falls_back_to_lillies_without_attacker():
    # A counterfactual: with no strong attacker in play and an empty hand -> the previous rule
    # (a refresh with Lillie's).
    with open(_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    s53 = None
    for item in seq:
        s53 = item["observation"]
        m.agent(s53)
    o2, deck = _alakazam_meowth2_build_fetch(s53)
    me = o2["current"]["players"][0]
    me["active"][0].update({"id": 710, "hp": 160, "maxHp": 160})
    me["bench"] = [b for b in me["bench"] if b["id"] not in (96, 150)]
    result = m.agent(o2)
    picked = deck[o2["select"]["option"][result[0]]["index"]]["id"]
    assert picked == 1227, (
        f"sin atacante fuerte y mano vacia debe refrescar con Lillie's (1227); "
        f"busco id {picked}")

_ALAKAZAM_DIPPLIN_PIVOT_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step56_retreat_ogerpon_promote_dipplin.json")

def _dipplin_pivot_replay(mutate_tac9=None):
    import copy as _c
    with open(_ALAKAZAM_DIPPLIN_PIVOT_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    result = None
    target = None
    for item in seq:
        obs = item["observation"]
        if item["tac"] == 9 and mutate_tac9 is not None:
            obs = _c.deepcopy(obs)
            mutate_tac9(obs)
        target = obs
        result = m.agent(obs)
        if item["tac"] == 9:
            break
    return result, target

def test_alakazam_step56_retreats_ex_for_charged_dipplin():
    result, target = _dipplin_pivot_replay()
    options = target["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))
    assert result == [retreat_opt], (
        f"con Dipplin cargado que noquea al Abra, retirar el Ogerpon ex "
        f"(opt {retreat_opt}) en vez de atacar con el ex; obtuvo {result}")

def test_alakazam_step56_promotes_dipplin_after_retreat():
    import copy as _c
    result, target = _dipplin_pivot_replay()
    o2 = _c.deepcopy(target)
    bench = o2["current"]["players"][1]["bench"]
    o2["select"] = {"context": 3, "contextCard": None, "deck": None,
                    "effect": None, "maxCount": 1, "minCount": 1,
                    "option": [{"area": 5, "index": i, "playerIndex": 1, "type": 3}
                               for i in range(len(bench))],
                    "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}
    result = m.agent(o2)
    picked = bench[o2["select"]["option"][result[0]]["index"]]["id"]
    assert picked == m.Dipplin, (
        f"al retirar debe promover el Dipplin (1 premio que noquea); "
        f"promovio id {picked}")

def test_alakazam_step56_attacks_when_dipplin_uncharged():
    # A counterfactual: a Dipplin WITHOUT energy cannot attack -> there is no pivot;
    # attack with the active Ogerpon ex.
    def mut(obs):
        for b in obs["current"]["players"][1]["bench"]:
            if b["id"] == m.Dipplin:
                b["energies"] = []
                b["energyCards"] = []
    result, target = _dipplin_pivot_replay(mut)
    options = target["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    assert result == [attack_opt], (
        f"sin Dipplin cargado debe atacar con el activo (opt {attack_opt}); "
        f"obtuvo {result}")

_ALAKAZAM_T7_CHAIN_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_t7_ub_meowth_xerosic_chain.json")

def test_alakazam_t7_plays_ub_fetched_meowth_then_fetches_xerosic():
    import copy as _c
    with open(_ALAKAZAM_T7_CHAIN_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    result = None
    target = None
    for item in seq:
        target = item["observation"]
        result = m.agent(target)

    # 1) tac9: play the Meowth ex searched for by the Ultra Ball (do not attack yet).
    opt = target["select"]["option"][result[0]]
    hand = [c["id"] for c in target["current"]["players"][1]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"tac9 debe bajar el Meowth ex buscado por Ultra Ball; obtuvo {result} -> {opt}")

    # 2) Last-Ditch Catch: with a rival hand of 12 and a strong attacker, search for XEROSIC.
    o2 = _c.deepcopy(target)
    me = o2["current"]["players"][1]
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Meowth_ex]
    me["bench"].append({"appearThisTurn": True, "energies": [], "energyCards": [],
                        "hp": 170, "id": 1071, "maxHp": 170, "playerIndex": 1,
                        "preEvolution": [], "serial": 80, "tools": []})
    deck = [{"id": 1227, "playerIndex": 1, "serial": 87},
            {"id": 1182, "playerIndex": 1, "serial": 89},
            {"id": 1184, "playerIndex": 1, "serial": 90},
            {"id": 1227, "playerIndex": 1, "serial": 84},
            {"id": 1197, "playerIndex": 1, "serial": 103}]
    o2["select"] = {"context": 7, "contextCard": None, "deck": deck,
                    "effect": {"id": 1071, "playerIndex": 1, "serial": 80},
                    "maxCount": 1, "minCount": 0,
                    "option": [{"area": 1, "index": i, "playerIndex": 1, "type": 3}
                               for i in range(len(deck))],
                    "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}
    r2 = m.agent(o2)
    picked = deck[o2["select"]["option"][r2[0]]["index"]]["id"]
    assert picked == 1197, (
        f"Last-Ditch debe buscar Xerosic (1197) con mano rival 12; busco id {picked}")

_CRUSTLE_SNIPE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "crustle_cruel_arrow_snipe_dwebble_step139.json")

def _crustle_snipe_target(result, obs):
    opt = obs["select"]["option"][result[0]]
    op = obs["current"]["players"][0]
    return (op["active"][opt["index"]] if opt["area"] == 4
            else op["bench"][opt["index"]])

def test_crustle_step139_cruel_arrow_snipes_koable_dwebble():
    with open(_CRUSTLE_SNIPE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    result = m.agent(obs)
    picked = _crustle_snipe_target(result, obs)
    assert picked["id"] == 344 and picked["hp"] == 70, (
        f"Cruel Arrow debe apuntar al Dwebble noqueable (70 HP), no a un "
        f"Crustle inmune a ex; apunto a id {picked['id']} hp {picked['hp']}")

def test_crustle_step139_cruel_arrow_chips_dwebble_when_no_ko():
    # A counterfactual: a Dwebble with 150 HP (it does not die) -> it is still the only
    # target that TAKES damage (the Crustle are immune to our ex).
    import copy as _c
    with open(_CRUSTLE_SNIPE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    dw = obs["current"]["players"][0]["bench"][1]
    dw["hp"] = 150
    dw["maxHp"] = 150
    result = m.agent(obs)
    picked = _crustle_snipe_target(result, obs)
    assert picked["id"] == 344, (
        f"sin KO posible debe chipear al Dwebble (unico no inmune); "
        f"apunto a id {picked['id']}")

_ALAKAZAM_MEOWTH_HAND_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step76_meowth_in_hand_xerosic_engine.json")

def _meowth_hand_replay(mutate_tac4=None):
    import copy as _c
    with open(_ALAKAZAM_MEOWTH_HAND_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    for item in seq:
        obs = item["observation"]
        if item["tac"] == 4:
            if mutate_tac4 is not None:
                obs = _c.deepcopy(obs)
                mutate_tac4(obs)
            return m.agent(obs), obs
        m.agent(obs)

def test_alakazam_step76_plays_meowth_from_hand_for_xerosic():
    result, obs = _meowth_hand_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"con Supporter libre, mano rival 10 y Xerosic en mazo debe bajar el "
        f"Meowth ex de la mano; obtuvo {result} -> {opt}")

def test_alakazam_step76_attacks_if_supporter_already_played():
    # An updated counterfactual (anti-Alakazam suggestion 1, Powerful Hand
    # modelled): with the Supporter already played the Meowth is NOT played (the original
    # intent of the test). Besides, now that the model SEES that the active
    # 130 HP Hydrapple dies to the projected Powerful Hand (20 x (10+2) =
    # 240), the user's rule "retreat the fragile ex, sacrifice 1
    # prize" applies: Ripening Charge (it enables the retreat) -> retreat -> promote
    # the 1-prize Meganium which also knocks out the 140 Alakazam. Before it
    # attacked with the doomed ex (giving away 2 prizes) because it believed
    # Alakazam hit for 0.
    result, obs = _meowth_hand_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    opt = obs["select"]["option"][result[0]]
    _my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in _my["hand"]]
    assert not (opt.get("type") == int(OptionType.PLAY)
                and opt.get("index", -1) < len(hand)
                and hand[opt["index"]] == m.Meowth_ex), (
        f"con el Supporter ya jugado no debe bajar el Meowth; "
        f"obtuvo {result} -> {opt}")
    assert (opt.get("type") == int(OptionType.ABILITY)
            and opt.get("area") == int(AreaType.ACTIVE)), (
        f"con el Hydrapple activo condenado (240 proyectado vs 130 HP) debe "
        f"activar Ripening Charge para el pivote de sacrificio de 1 premio; "
        f"obtuvo {result} -> {opt}")

def test_alakazam_step76_attacks_if_opponent_hand_small():
    result, obs = _meowth_hand_replay(
        lambda o: o["current"]["players"][0].__setitem__("handCount", 4))
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con la mano rival corta (<6) no aplica el motor Xerosic: atacar; "
        f"obtuvo {result} -> {opt}")

_ALAKAZAM_MEOWTH_OVER_APPLIN_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step147_meowth_over_applin_xerosic.json")

def _meowth_over_applin_replay(mutate_tac2=None):
    import copy as _c
    with open(_ALAKAZAM_MEOWTH_OVER_APPLIN_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    for item in seq:
        obs = item["observation"]
        if item["tac"] == 2:
            if mutate_tac2 is not None:
                obs = _c.deepcopy(obs)
                mutate_tac2(obs)
            return m.agent(obs), obs
        m.agent(obs)

def test_alakazam_step147_plays_meowth_over_applin():
    result, obs = _meowth_over_applin_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"con el motor Xerosic vivo (mano rival 11, un slot de banca) debe bajar "
        f"el Meowth ex, no el Applin; obtuvo {result} -> {opt}")

def test_alakazam_step147_applin_rush_returns_when_no_engine():
    # A counterfactual: a short rival hand -> the engine does not apply and the development
    # rush returns (Applin with Forest).
    result, obs = _meowth_over_applin_replay(
        lambda o: o["current"]["players"][1].__setitem__("handCount", 4))
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Applin, (
        f"sin mano rival gorda debe volver el rush de Applin; obtuvo {result} -> {opt}")

_MARNIE_UB_MEOWTH_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step118_ub_meowth_lillie_chain.json")

def _marnie_ub_meowth_replay(mutate_last=None):
    import copy as _c
    with open(_MARNIE_UB_MEOWTH_LILLIE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate_last is not None:
        obs = _c.deepcopy(obs)
        mutate_last(obs)
    return m.agent(obs), obs, data

def test_marnie_step118_plays_ub_fetched_meowth_before_attacking():
    result, obs, _ = _marnie_ub_meowth_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"el Meowth ex buscado por Ultra Ball debe bajarse (Supporter libre) "
        f"antes de atacar; obtuvo {result} -> {opt}")

def test_marnie_step118_ub_meowth_not_played_if_supporter_used():
    # A counterfactual: with the Supporter already played, the searched Lillie's could
    # not be played -> attack directly.
    result, obs, _ = _marnie_ub_meowth_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == 13, (
        f"con supporterPlayed=True debe atacar, no bajar el Meowth; "
        f"obtuvo {result} -> {opt}")

def test_marnie_step118_last_ditch_fetches_lillies_then_plays_it():
    _, _, data = _marnie_ub_meowth_replay()
    fetch = data["synthetic_fetch"]
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked == [m.Lillie_Determination], (
        f"Last-Ditch Catch debe buscar la Lillie's (1227) para refrescar; "
        f"obtuvo {picked}")
    main_obs = data["synthetic_lillie_main"]
    ch2 = m.agent(main_obs)
    opt = main_obs["select"]["option"][ch2[0]]
    hand = [c["id"] for c in main_obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Lillie_Determination, (
        f"la Lillie's buscada debe jugarse antes de atacar; obtuvo {ch2} -> {opt}")

def test_powerful_hand_projected_damage():
    class _P:
        def __init__(s, id, energies, hp, maxHp):
            s.id, s.energies, s.hp, s.maxHp = id, energies, hp, maxHp
    alak = _P(m.Alakazam_ex, [5], 140, 140)
    oger = _P(m.Teal_Mask_Ogerpon_ex, [1, 1, 1], 210, 210)
    # without op_hand_count: conservative (the historical behaviour)
    assert m._op_active_attack_damage_to(alak, oger) == 0
    # with the rival hand: 20 x (hand + 2)
    assert m._op_active_attack_damage_to(alak, oger, 9) == 220
    assert m._op_active_attack_damage_to(alak, oger, 5) == 140
    # rivals with printed damage do not change when the hand is passed
    dura = _P(647, [7, 7, 7], 100, 100)
    assert (m._op_active_attack_damage_to(dura, oger, 9)
            == m._op_active_attack_damage_to(dura, oger))

def _xerosic_bighand_mutated(mutate):
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mutate(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    played = (hand[opt["index"]]
              if opt.get("type") == int(OptionType.PLAY) else None)
    return played, opt

def test_xerosic_early_trigger_on_projected_ko():
    # a rival hand of 5 (below the threshold of 6) + our own active at 130 HP: the projection
    # 20 x (5+2) = 140 >= 130 -> play Xerosic NOW.
    def mut(o):
        cur = o["current"]
        cur["players"][cur["yourIndex"]]["active"][0]["hp"] = 130
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_mutated(mut)
    assert played == m.Xerosic_Machinations, (
        f"con KO proyectado (140 >= 130) debe jugar Xerosic; obtuvo {opt}")

def _xerosic_bighand_no_backup(mutate):
    # A variant with NO backup copy: the 2nd copy of Xerosic (deck, July
    # 2026) is marked as outside the deck via tracking, leaving the one in hand as
    # the last -> the conservative one-copy timing.
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mutate(obs)
    m._init_cards_tracking()
    m.ACTIVE_CARDS_IN_DECK.setdefault(
        m.Xerosic_Machinations, {m.ZONE_DECK: 0})[m.ZONE_DECK] = 0
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    played = (hand[opt["index"]]
              if opt.get("type") == int(OptionType.PLAY) else None)
    return played, opt

def test_xerosic_early_with_backup_copy():
    # The 2nd copy in the DECK (July 2026): with a rival hand of 5 (>= 4) the 1st copy
    # is played EARLY even if the active is healthy -- a double-hit
    # strategy: slow them down now and keep the 2nd for the late cap.
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_mutated(mut)
    assert played == m.Xerosic_Machinations, (
        f"con copia de respaldo en el mazo, la 1a se juega temprano "
        f"(mano rival 5 >= 4); obtuvo {opt}")

def test_xerosic_early_trigger_not_on_healthy_active_last_copy():
    # The LAST copy (no backup) + a rival hand of 5 + a healthy active (330):
    # the projection 140 < 330 -> do NOT burn it yet (the conservative timing).
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played != m.Xerosic_Machinations, (
        f"ultima copia sin KO proyectado (140 < 330): no quemarla; obtuvo {opt}")

def test_xerosic_early_trigger_needs_alakazam_active():
    # The LAST copy, a rival hand of 5, our own active at 130, but the rival has an
    # active Abra: the threat is not immediate -> do NOT trigger early.
    def mut(o):
        cur = o["current"]
        cur["players"][cur["yourIndex"]]["active"][0]["hp"] = 130
        op = cur["players"][1 - cur["yourIndex"]]
        op["handCount"] = 5
        op["active"][0]["id"] = m.Abra
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played != m.Xerosic_Machinations, (
        f"ultima copia con Abra activo: amenaza no inmediata; obtuvo {opt}")

def test_lillies_guard_protects_last_xerosic_access():
    # Xerosic in hand, a rival hand of 5, and with NO re-searchable Meowth (0 in hand,
    # 0 in the deck): Lillie's would shuffle it away with no recovery -> a veto.
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mut(obs)
    m._init_cards_tracking()
    m.ACTIVE_CARDS_IN_DECK.setdefault(
        m.Meowth_ex, {m.ZONE_DECK: 0})[m.ZONE_DECK] = 0
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    assert not (opt.get("type") == int(OptionType.PLAY)
                and hand[opt["index"]] == m.Lillie_Determination), (
        f"Lillie's barajaria el ultimo Xerosic sin re-busqueda posible; "
        f"obtuvo {opt}")

def test_lillies_allowed_when_xerosic_refetchable():
    # The LAST copy + a Meowth in the deck: the normal course is kept (the Meowth
    # re-searches the shuffled Xerosic). With a backup in the deck the 1st copy would
    # be played early (the test test_xerosic_early_with_backup_copy).
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played == m.Lillie_Determination, (
        f"ultima copia con Meowth re-buscable: Lillie's sigue su curso; "
        f"obtuvo {opt}")

def _garchomp_s82_replay(mutate=None):
    import copy as _c
    with open(_GARCHOMP_BOSS_GABITE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data

def test_garchomp_step82_plays_boss_to_cut_garchomp_line():
    result, obs, _ = _garchomp_s82_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Boss_Orders), (
        f"con Gabite energizado en banca rival debe jugar Boss's, no atacar "
        f"al muro Spiritomb; obtuvo {result} -> {opt}")

def test_garchomp_step82_attacks_if_supporter_already_played():
    result, obs, _ = _garchomp_s82_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"sin Supporter disponible debe atacar; obtuvo {result} -> {opt}")

def test_garchomp_step82_gust_targets_energized_gabite():
    _, _, data = _garchomp_s82_replay()
    tgt = data["synthetic_gust_target"]
    ch = m.agent(tgt)
    bench = tgt["current"]["players"][0]["bench"]
    picked = bench[tgt["select"]["option"][ch[0]]["index"]]
    assert (picked["id"] == m.Cynthias_Gabite
            and len(picked["energies"]) >= 1), (
        f"el gusteo debe apuntar al Gabite CON energia (mas cerca de "
        f"Garchomp ex); obtuvo idx {ch} -> id {picked['id']} "
        f"energias {picked['energies']}")

_ARCHALUDON_UB_ENGINE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step58_ub_engine_over_energy.json")

def _archaludon_s58_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_UB_ENGINE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data

def test_archaludon_step58_plays_ub_over_energy_attach():
    result, obs, _ = _archaludon_s58_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Ultra_Ball), (
        f"con el activo sin KO y banca de 1, la UB (motor Meowth->Lillie's) va "
        f"ANTES de gastar las energias; obtuvo {result} -> {opt}")

def test_archaludon_step58_attaches_when_bench_developed():
    # A counterfactual: a developed bench (3) -> the pivot does not apply and the normal
    # attachment is kept.
    def mut(o):
        my = o["current"]["players"][0]
        for i in range(2):
            my["bench"].append({
                "appearThisTurn": False, "energies": [], "energyCards": [],
                "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 0,
                "preEvolution": [], "serial": 60 + i, "tools": []})
    result, obs, _ = _archaludon_s58_replay(mut)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"con banca desarrollada el adjunte normal se mantiene; "
        f"obtuvo {result} -> {opt}")

def test_archaludon_step58_ub_fetches_meowth_and_plays_it():
    _, _, data = _archaludon_s58_replay()
    fetch = data["synthetic_ub_fetch"]
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked == [m.Meowth_ex], (
        f"el fetch de la UB del pivote debe traer Meowth ex; obtuvo {picked}")
    main_obs = data["synthetic_meowth_main"]
    ch2 = m.agent(main_obs)
    opt = main_obs["select"]["option"][ch2[0]]
    hand = [c["id"] for c in main_obs["current"]["players"][0]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Meowth_ex), (
        f"el Meowth buscado debe bajarse (Last-Ditch -> Lillie's); "
        f"obtuvo {ch2} -> {opt}")

def test_garchomp_deny_evo_plays_meowth_for_deck_boss():
    result, obs, _ = _garchomp_meowth_deny_replay()
    assert _played_meowth(obs, result), (
        f"con Gabite energizado en banca rival y Boss's en el MAZO debe bajar "
        f"Meowth ex (motor deny-evo, 22000); obtuvo {result}")

def test_garchomp_deny_evo_no_meowth_if_supporter_played():
    result, obs, _ = _garchomp_meowth_deny_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    assert not _played_meowth(obs, result), (
        f"con el Supporter jugado el Boss's buscado no se podria jugar: no "
        f"bajar Meowth; obtuvo {result}")
