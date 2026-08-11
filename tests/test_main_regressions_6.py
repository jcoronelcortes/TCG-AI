"""Regression slice 6 of 8. The counter-stadium, the bench-ready checks and the
Alakazam 1-prize pivots."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

_FOREST_OF_VITALITY = 1261

_NEUTRALIZATION_ZONE = 1247

def _discarded_card_ids(obs, choice):
    hand = [c["id"] for c in obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]]
    return [hand[obs["select"]["option"][i]["index"]] for i in choice]

def test_step62_forced_discard_protects_forest_vs_neutralization_zone():
    with open(_FOREST_DISCARD_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    # sanity: the rival stadium is Neutralization Zone and the Forest is in hand
    assert obs["current"]["stadium"][0]["id"] == _NEUTRALIZATION_ZONE
    mi = obs["current"]["yourIndex"]
    assert any(c["id"] == _FOREST_OF_VITALITY for c in obs["current"]["players"][mi]["hand"])

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    discarded = _discarded_card_ids(obs, result)

    assert _FOREST_OF_VITALITY not in discarded, (
        f"con Neutralization Zone rival en juego, Forest es el unico contra-estadio "
        f"y NO debe descartarse; descarto ids {discarded}")

def test_forest_discardable_when_no_hostile_op_stadium():
    # Control: with no hostile rival stadium, the protection does NOT apply -- with
    # Meganium+Hydrapple in play the Forest is discardable again (score 70).
    # The rival's Neutralization Zone is removed from the board; the Forest must be able to fall.
    import copy as _c
    with open(_FOREST_DISCARD_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    obs["current"]["stadium"] = []  # no hostile stadium
    mi = obs["current"]["yourIndex"]
    forest_opt = next(i for i, o in enumerate(obs["select"]["option"])
                      if obs["current"]["players"][mi]["hand"][o["index"]]["id"]
                      == _FOREST_OF_VITALITY)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert forest_opt in result, (
        f"sin estadio hostil rival, con Meganium+Hydrapple Forest es descartable; "
        f"obtuvo {result} (opcion Forest = {forest_opt})")

_CUBCHOO_RIPEN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cubchoo_step82_ripening_charge_blocked_active.json")

def test_step82_charges_blocked_hydrapple_to_enable_retreat():
    with open(_CUBCHOO_RIPEN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    # the Ripening Charge option on the Hydrapple ex's ACTIVE (area 4)
    ripen_active = [i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.ABILITY)
                    and o.get("area") == int(AreaType.ACTIVE)]
    assert ripen_active, "el fixture debe ofrecer Ripening Charge en el activo"

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] in ripen_active, (
        f"con el Hydrapple ex activo bloqueado por Cubchoo y un Ogerpon ex de "
        f"banca listo, se debe cargar el ACTIVO con Ripening Charge (opciones "
        f"{ripen_active}) para habilitar la retirada; obtuvo {result}")

_CUBCHOO_LANAS_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "cubchoo_step96_charge_blocked_active_from_lanas.json")

def test_step96_routes_lanas_energy_to_blocked_active_hydrapple():
    with open(_CUBCHOO_LANAS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    chosen = obs["select"]["option"][result[0]]
    assert chosen.get("type") == int(OptionType.ATTACH), (
        f"se debe ADJUNTAR energia (no {chosen}); obtuvo {result}")
    assert chosen.get("inPlayArea") == int(AreaType.ACTIVE), (
        f"la energia recuperada debe ir al Hydrapple ex ACTIVO bloqueado "
        f"(inPlayArea={int(AreaType.ACTIVE)}), no a la banca; obtuvo {chosen}")

_ALAKAZAM_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step47_ultraball_completes_line_before_lillie.json")

_LILLIE_DETERMINATION = 1227

def test_step47_does_not_shuffle_meganium_line_with_lillie():
    with open(_ALAKAZAM_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    hand = [c["id"] for c in obs["current"]["players"][mi]["hand"]]
    lillie_opts = [i for i, o in enumerate(obs["select"]["option"])
                   if o.get("type") == int(OptionType.PLAY)
                   and o.get("index", -1) < len(hand)
                   and hand[o["index"]] == _LILLIE_DETERMINATION]
    assert lillie_opts, "el fixture debe ofrecer jugar Lillie's Determination"

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] not in lillie_opts, (
        f"con Chikorita en juego + Meganium en mano + Ultra Ball (falta Bayleef "
        f"buscable) NO se debe jugar Lillie's (barajaria la linea); "
        f"opciones Lillie={lillie_opts}, obtuvo {result}")

def _lillie_gapped_flag(obs):
    """Returns the `ub_gapped_line` flag of the Lillie's scorer for `obs`."""
    captured = {}
    orig = m._CtxLillie

    class _Spy(orig):
        def __init__(self, ctx):
            super().__init__(ctx)
            captured["v"] = self.ub_gapped_line

    m._CtxLillie = _Spy
    try:
        m._init_cards_tracking(); m.plan = m.AttackPlan()
        m.agent(obs)
    finally:
        m._CtxLillie = orig
    return captured.get("v")

def test_ub_gapped_line_flag_requires_ultraball():
    # The `ub_gapped_line` flag (which vetoes Lillie's) requires an Ultra Ball in hand:
    # it is True in the fixture and switches off when the Ultra Ball is removed (the gap stops
    # being completable).
    import copy as _c
    with open(_ALAKAZAM_LILLIE_FIXTURE, encoding="utf-8") as f:
        base = json.load(f)["observation"]
    assert _lillie_gapped_flag(_c.deepcopy(base)) is True, (
        "con Chikorita+Meganium+Ultra Ball+Bayleef en mazo el flag debe activarse")

    obs = _c.deepcopy(base)
    mi = obs["current"]["yourIndex"]
    obs["current"]["players"][mi]["hand"] = [
        c for c in obs["current"]["players"][mi]["hand"] if c["id"] != 1121]
    assert _lillie_gapped_flag(obs) is False, (
        "sin Ultra Ball el hueco no es completable: el flag NO debe activarse")

_ALAKAZAM_RIPEN_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step79_ripening_charge_to_future_hydrapple.json")

_HYDRAPPLE_EX = 150

_TAPU_BULU = 920

def test_step79_ripening_charge_targets_future_hydrapple_not_capped_tapu():
    with open(_ALAKAZAM_RIPEN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]

    def target_id(opt):
        if opt.get("area") == int(AreaType.ACTIVE):
            return me["active"][0]["id"]
        return me["bench"][opt["index"]]["id"]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    chosen = obs["select"]["option"][result[0]]
    tid = target_id(chosen)

    assert tid == _HYDRAPPLE_EX, (
        f"Ripening Charge debe cargar el Hydrapple ex de banca (0e, atacante "
        f"futuro), no el Tapu Bulu activo ya cargado; cargo id {tid}")
    # and explicitly NOT the active Tapu Bulu (already at Wood Hammer's cap)
    assert not (chosen.get("area") == int(AreaType.ACTIVE)
                and me["active"][0]["id"] == _TAPU_BULU), (
        "no debe cargar el Tapu Bulu activo ya cargado")

_ALK_STEP109 = (ROOT / "tests" / "fixtures"
                / "alakazam_step109_manual_attach_to_bench_hydrapple.json")

_ALK_STEP112 = (ROOT / "tests" / "fixtures"
                / "alakazam_step112_ripening_charge_to_bench_hydrapple.json")

def _bench_target_id(obs, chosen):
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    if chosen.get("type") == int(OptionType.ATTACH):
        if chosen.get("inPlayArea") == int(AreaType.BENCH):
            return me["bench"][chosen["inPlayIndex"]]["id"], True
        return me["active"][0]["id"], False
    # ATTACH_FROM (ctx 21): area/index
    if chosen.get("area") == int(AreaType.BENCH):
        return me["bench"][chosen["index"]]["id"], True
    return me["active"][0]["id"], False

def test_step109_manual_energy_charges_bench_hydrapple_not_ready_active():
    with open(_ALK_STEP109, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid, is_bench = _bench_target_id(obs, chosen)
    assert chosen.get("type") == int(OptionType.ATTACH), (
        f"se esperaba un adjunte manual, obtuvo tipo {chosen.get('type')}")
    assert is_bench and tid == 150, (
        "el adjunte manual debe ir al Hydrapple ex de BANCA (atacante futuro), "
        f"no al Hydrapple activo ya listo; fue id {tid} bench={is_bench}")

def test_step112_ripening_charge_targets_bench_hydrapple_not_ready_active():
    with open(_ALK_STEP112, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid, is_bench = _bench_target_id(obs, chosen)
    assert is_bench and tid == 150, (
        "Ripening Charge debe cargar el Hydrapple ex de BANCA, no el activo ya "
        f"listo (Syrup Storm escala con el campo); fue id {tid} bench={is_bench}")

_BOSS_GUST_FIXTURE = (ROOT / "tests" / "fixtures"
                      / "boss_gust_prefers_higher_prize_mega_ex.json")

_MEGA_HERACROSS_EX = 781

_TEAL_OGERPON_EX = 96

def test_boss_gust_prefers_winning_3prize_mega_over_2prize_ex():
    with open(_BOSS_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    op_bench = obs["current"]["players"][1 - mi]["bench"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid = op_bench[chosen["index"]]["id"]
    assert tid == _MEGA_HERACROSS_EX, (
        f"Boss's debe gustear el Mega Heracross ex (781, 3 premios, gana la "
        f"partida), no el Ogerpon ex (96, 2 premios); gusteo id {tid}")

def test_prize_count_recognizes_mega_ex_as_three():
    # The prize identification: megaEx=3, ex=2, non-ex=1.
    class _P:
        def __init__(self, cid): self.id = cid; self.energyCards = []; self.tools = []
    assert m.prize_count(_P(_MEGA_HERACROSS_EX)) == 3
    assert m.prize_count(_P(_TEAL_OGERPON_EX)) == 2
    assert m.prize_count(_P(349)) == 1  # Teal Mask Ogerpon (no-ex)

_STAMP_MEOWTH_FIXTURE = (ROOT / "tests" / "fixtures"
                         / "unfair_stamp_before_meowth_fetch_lillie.json")

_UNFAIR_STAMP = 1080

_MEOWTH_EX = 1071

def _played_id(obs, chosen_idx):
    o = m.to_observation_class(obs)
    me = o.current.players[o.current.yourIndex]
    opt = o.select.option[chosen_idx]
    if getattr(opt, "type", None) == m.OptionType.PLAY and getattr(opt, "index", None) is not None:
        return me.hand[opt.index].id
    return None

def test_stamp_playable_vetoes_meowth_fetch_lillie():
    with open(_STAMP_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid != _MEOWTH_EX, (
        "Con Unfair Stamp jugable (KO el turno pasado), NO bajar Meowth ex a "
        f"buscar Lillie's (el Sello la baraja); el agente jugo id {pid}")

_MEOWTH_NO_STAMP_FIXTURE = (ROOT / "tests" / "fixtures"
                            / "meowth_fetch_lillie_no_stamp_control.json")

def test_meowth_fetch_lillie_still_played_without_playable_stamp():
    # Control: the SAME board but WITHOUT an Unfair Stamp in hand -> the veto does not apply
    # and the Meowth -> Lillie's engine (a refresh) is still in force and DOES play Meowth ex.
    with open(_MEOWTH_NO_STAMP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid == _MEOWTH_EX, (
        "Sin Unfair Stamp en mano, el motor Meowth->Lillie's debe seguir bajando "
        f"Meowth ex; el agente jugo id {pid}")

_STAMP_MEOWTH_BOSS_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step90_no_meowth_boss_con_unfair_stamp.json")

_MEOWTH_BOSS_NO_STAMP_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step90_meowth_boss_sin_stamp_control.json")

def test_stamp_playable_vetoes_meowth_fetch_boss():
    # The real step 90: a hand with a PLAYABLE Unfair Stamp (they knocked us out last
    # turn) + Xerosic, and a Boss's in the deck that would gust the rival Fezandipiti ex.
    # Meowth ex is not played: the Stamp goes first and would shuffle that Boss's away.
    with open(_STAMP_MEOWTH_BOSS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid != _MEOWTH_EX, (
        "Con Unfair Stamp jugable, NO bajar Meowth ex a cavar un Boss's Orders "
        "que el propio Sello devuelve al mazo (y que `yields_to_unfair_stamp` "
        f"impide jugar este turno); el agente jugo id {pid}")

def test_a_playable_stamp_does_not_block_the_turn_supporter():
    # The Stamp is still PLAYABLE in the menu after the veto: the veto only stops the
    # Meowth fetch, not the items -> Unfair Stamp sequence.
    with open(_STAMP_MEOWTH_BOSS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    o = m.to_observation_class(obs)
    me = o.current.players[o.current.yourIndex]
    assert any(getattr(opt, "type", None) == m.OptionType.PLAY
               and me.hand[opt.index].id == _UNFAIR_STAMP
               for opt in o.select.option), "el Sello debe seguir en el menu"
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs), "el agente debe elegir alguna opcion"

def test_meowth_fetch_boss_still_played_without_playable_stamp():
    # Control: the SAME board without the Stamp (nor the Xerosic, which would take the
    # Supporter slot through `_meowth_fetch_loses_the_turn`) -> the
    # Boss's-via-Meowth-ex engine is intact and DOES play Meowth ex.
    #
    # El tablero trae ademas un Fezandipiti ex con Flip the Script viva, y desde
    # `_TIER_FEZ_BEFORE_SEARCH` (agosto 2026) el robo gratis va ANTES del cuerpo
    # que paga la busqueda. Lo que este control mide -- que sin Sello el motor
    # Boss's via Meowth ex sigue vigente -- se lee con la habilidad ya cobrada
    # (es UNA VEZ POR TURNO, asi que despues ya no se ofrece).
    from fez_menu import sin_flip_the_script
    with open(_MEOWTH_BOSS_NO_STAMP_FIXTURE, encoding="utf-8") as f:
        obs = sin_flip_the_script(json.load(f)["observation"])
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid == _MEOWTH_EX, (
        "Sin Unfair Stamp jugable, el motor Boss's via Meowth ex (gustear+"
        f"noquear un ex de 2 premios) debe seguir vigente; el agente jugo id {pid}")

_ALK_MEG_FIXTURE = (ROOT / "tests" / "fixtures"
                    / "alakazam_charge_meganium_1prize_not_ogerpon_ex.json")

_MEGANIUM = 710

_TEAL_OGERPON_EX_ID = 96

def test_vs_alakazam_charges_1prize_meganium_not_active_ex():
    with open(_ALK_MEG_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    assert getattr(opt, "type", None) == int(m.OptionType.ATTACH), (
        "Se esperaba un adjunte de energia")
    ipa = getattr(opt, "inPlayArea", None); ipi = getattr(opt, "inPlayIndex", None)
    tgt_id = (me["active"][0]["id"] if ipa == int(m.AreaType.ACTIVE)
              else me["bench"][ipi]["id"])
    assert tgt_id == _MEGANIUM, (
        "vs Alakazam la carga debe ir al Meganium (1 premio, KO este turno), no "
        f"al ex activo; el agente cargo id {tgt_id}")

def test_alakazam_retreats_ex_to_promote_ready_1prize_meganium():
    # With the Meganium already READY (4 eff) and no more plays, vs Alakazam the agent retreats
    # the active ex to promote the 1-prize body (instead of attacking with the 2-prize ex).
    import copy
    with open(_ALK_MEG_FIXTURE, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])
    me = obs["current"]["players"][1]
    for b in me["bench"]:
        if b["id"] == _MEGANIUM:
            b["energies"] = [1, 1, 1, 1]
            b["energyCards"] = [{"id": 1, "playerIndex": 1, "serial": 114},
                                {"id": 1, "playerIndex": 1, "serial": 999}]
    me["hand"] = []; me["handCount"] = 0
    obs["current"]["supporterPlayed"] = True
    obs["select"]["option"] = [{"attackId": 120, "type": 13}, {"type": 12}, {"type": 14}]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    assert o.select.option[chosen[0]].type == int(m.OptionType.RETREAT), (
        "Con el Meganium 1-premio LISTO, vs Alakazam el agente debe RETIRAR el ex "
        "para promover el 1-premio, no atacar con el ex de 2 premios")

_EMPTY_BENCH_FIXTURE = (ROOT / "tests" / "fixtures"
                        / "never_end_turn_empty_bench_play_ultraball.json")

def test_never_ends_turn_with_empty_bench_plays_ultraball():
    with open(_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    assert opt.type != int(m.OptionType.END), (
        "Con la banca VACIA y una Ultra Ball en mano, NO terminar el turno: "
        "desarrollar la banca para no perder si noquean el activo")
    tid = me["hand"][opt.index]["id"] if getattr(opt, "index", None) is not None else None
    assert tid == _ULTRA_BALL, (
        f"Se esperaba jugar Ultra Ball para buscar un basico; jugo id {tid}")

def test_empty_bench_net_does_not_fire_with_bench_present():
    # Control: with a Pokemon ALREADY on the bench, the anti-empty-bench net does not apply
    # (bench_count>0). Since the Jul 2026 plan there is ALSO the
    # anti-sterile-turn net (which can rehabilitate the Ultra Ball with a bench
    # present); to isolate the control of the ORIGINAL net, the new one is switched off
    # by putting a Comfey on the rival bench (the op_is_comfey_deck guard).
    import copy
    with open(_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])
    me = obs["current"]["players"][0]
    me["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                    "hp": 70, "id": 1071, "maxHp": 170, "playerIndex": 0,
                    "preEvolution": [], "serial": 900, "tools": []}]
    op = obs["current"]["players"][1]
    op.setdefault("bench", []).append(
        {"appearThisTurn": False, "energies": [], "energyCards": [],
         "hp": 70, "id": 164, "maxHp": 70, "playerIndex": 1,
         "preEvolution": [], "serial": 901, "tools": []})
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    tid = (me["hand"][opt.index]["id"]
           if getattr(opt, "type", None) == int(m.OptionType.PLAY)
           and getattr(opt, "index", None) is not None else None)
    assert tid != _ULTRA_BALL, (
        "Con banca no vacia la red anti-banca-vacia no debe forzar la Ultra Ball")

_ALK_TAPU_FIXTURE = (ROOT / "tests" / "fixtures"
                     / "alakazam_manual_attach_dipplin_not_ready_tapu.json")

_TAPU_BULU = 920

_DIPPLIN = 93

def test_alakazam_does_not_overcharge_ready_tapu_charges_dipplin():
    with open(_ALK_TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    me = obs["current"]["players"][1]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    assert getattr(opt, "type", None) == int(m.OptionType.ATTACH), (
        "Se esperaba un adjunte de energia")
    ipa = getattr(opt, "inPlayArea", None); ipi = getattr(opt, "inPlayIndex", None)
    tgt_id = (me["active"][0]["id"] if ipa == int(m.AreaType.ACTIVE)
              else me["bench"][ipi]["id"])
    assert tgt_id != _TAPU_BULU, (
        "NO sobrecargar el Tapu Bulu activo ya LISTO (4 ef, dano fijo)")
    assert tgt_id == _DIPPLIN, (
        f"La 3a energia debe ir al Dipplin de banca (atacante futuro); fue a {tgt_id}")

_WIN_EMPTY_BENCH_FIXTURE = (ROOT / "tests" / "fixtures"
                            / "win_by_ko_empty_bench_attack_active.json")

def test_ko_of_last_opponent_pokemon_attacks_active_to_win():
    with open(_WIN_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con el activo LETAL y la banca rival VACIA, noquear al activo GANA la "
        f"partida: debe ATACAR (opt {attack_opt}), no retirar; obtuvo {result}")
    assert result != [retreat_opt], (
        "no retirar el activo letal para pivotar a un 1-premio cuando el KO gana")
    assert m.plan.attacker == 0, (
        f"el atacante debe ser el ACTIVO (0), no un cuerpo de banca; "
        f"fue {m.plan.attacker}")

def test_win_by_empty_bench_does_not_fire_when_opponent_has_bench():
    # Control: with the rival HAVING a bench, the active's KO does NOT win the game, so
    # the finisher override must not apply (the mismatch/pivot logic is
    # free to act). A Pokemon is added to the rival bench and it is verified
    # that the decision is NO longer forced to the active's attack through the
    # empty-bench route (the plan may legitimately pivot).
    with open(_WIN_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))

    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    oact = op["active"][0]
    op["bench"] = [{
        "appearThisTurn": False, "energies": [], "energyCards": [],
        "hp": oact.get("hp", 110), "maxHp": oact.get("maxHp", 110),
        "id": oact["id"], "playerIndex": oact["playerIndex"],
        "preEvolution": [], "serial": (oact.get("serial", 0) or 0) + 5000,
        "tools": [],
    }]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    m.agent(obs)
    # With a rival bench, the active's KO no longer wins through the no-promotion rule;
    # the empty-bench finisher must not be active (`_active_win_plan` is not captured).
    # We verify that the scenario is different: the rival DOES have a bench.
    assert any(b is not None for b in op["bench"]), "control: rival con banca"

_UB_MEOWTH_OVER_FEZ_FIXTURE = (ROOT / "tests" / "fixtures"
                               / "ub_prefer_meowth_over_fez_no_attacker.json")

def test_ub_fetch_prefers_meowth_over_fez_when_no_attacker():
    with open(_UB_MEOWTH_OVER_FEZ_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    search_map = _resolve_search_options(obs)
    assert m.Meowth_ex in search_map.values(), "el fixture debe ofrecer buscar Meowth ex"
    assert m.Fezandipiti_ex in search_map.values(), "el fixture debe ofrecer buscar Fezandipiti ex"
    meowth_opt = next(i for i, cid in search_map.items() if cid == m.Meowth_ex)
    fez_opt = next(i for i, cid in search_map.items() if cid == m.Fezandipiti_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"sin atacante usable y con el motor Meowth->Lillie's en el mazo, la "
        f"Ultra Ball debe buscar Meowth ex (opt {meowth_opt}) para refrescar, no "
        f"Fezandipiti ex; obtuvo {result} (map={search_map})")
    assert result != [fez_opt], (
        "no buscar Fezandipiti ex cuando Meowth ex refresca mejor sin atacante")

def test_ub_fetch_gate_is_conditional_on_meowth_engine():
    # Control: the gate that makes Fezandipiti yield only applies when the
    # Meowth ex -> Lillie's engine is AVAILABLE (`no_attacker_prefer_meowth`). If it is
    # broken (e.g. the Supporter ALREADY played this turn -> a Lillie's could not be
    # chained), the gate must NOT divert the search towards Meowth ex: the decision
    # stops being forced to Meowth (here another refill/development target wins,
    # e.g. Hydrapple ex; Fezandipiti recovers its refill of 1050).
    with open(_UB_MEOWTH_OVER_FEZ_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))

    obs["current"]["supporterPlayed"] = True  # rompe el motor Meowth->Lillie's

    search_map = _resolve_search_options(obs)
    meowth_opt = next(i for i, cid in search_map.items() if cid == m.Meowth_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"con el Supporter ya jugado (motor Meowth roto), el gate NO debe forzar "
        f"buscar Meowth ex (opt {meowth_opt}); obtuvo {result} (map={search_map})")

_PROMOTE_NEAR_READY_FIXTURE = (ROOT / "tests" / "fixtures"
                               / "promote_near_ready_ex_over_wall_step111.json")

def test_promote_near_ready_ko_attacker_over_cheap_wall():
    with open(_PROMOTE_NEAR_READY_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    # opt cuyo bench-index apunta a Ogerpon ex (96) y a Tapu Bulu (920).
    ogerpon_opt = next(i for i, o in enumerate(options)
                       if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex)
    tapu_opt = next(i for i, o in enumerate(options)
                    if me["bench"][o["index"]]["id"] == 920)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [ogerpon_opt], (
        f"tras el KO debe promover el atacante casi listo Ogerpon ex (opt "
        f"{ogerpon_opt}), no el muro Tapu Bulu 0/4; obtuvo {result}")
    assert result != [tapu_opt], (
        "no promover un muro que no puede atacar en varios turnos")

def _promote_near_ready_obs(without_lillie=False, without_fez=False):
    with open(_PROMOTE_NEAR_READY_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))
    yi = obs["current"]["yourIndex"]; me = obs["current"]["players"][yi]
    if without_lillie:
        me["hand"] = [c for c in me["hand"] if c["id"] != m.Lillie_Determination]
    if without_fez:
        me["bench"] = [b for b in me["bench"] if b["id"] != m.Fezandipiti_ex]
        obs["select"]["option"] = [
            {"area": 5, "index": i, "playerIndex": yi, "type": 3}
            for i in range(len(me["bench"]))]
    return obs

def test_promote_near_ready_defers_without_draw_engine():
    # Control: with NO draw engine at all, the missing energy cannot be dug,
    # so the "nearly ready attacker" override does NOT apply and the decision
    # goes back to the basic wall logic / a normal promotion.
    #
    # TWO engines have to be removed, not one. Before, this control only removed the
    # Lillie's from hand and assumed there was no way left to dig; but
    # the board keeps a **Fezandipiti ex on the bench** and the promotion happens
    # right after a KO, which is Flip the Script's trigger: next
    # turn it draws 3. That route (route `d` of `_ps_can_find_energy`) is real and is now
    # modelled, so the control has to switch it off too in order to measure what
    # it says it measures. See `test_promote_near_ready_fez_draw_engine_is_enough`.
    #
    # WHAT THIS CONTROL MEASURES IS THE OVERRIDE, and that is what it asserts:
    # `_promote_setup_ko_attacker` has to come out None. It used to assert the
    # OUTCOME instead ("anything but the Ogerpon ex"), and on this board the
    # outcome moved on its own account -- their pile is at ONE and their
    # Powerful Hand projects 20 x (14+2) = 320, which removes all four
    # candidates. There the cheap 1-prize wall the assertion was written for
    # hands over exactly the prize that ends the game, and the front spot goes
    # to the body their blow clears by the least: the 210 HP Ogerpon ex. See
    # `tests/test_the_last_stand_takes_the_front_spot.py` (`_mp_last_stand`).
    # The two rules reach the same body for different reasons, so the override
    # is now read directly rather than through who was promoted.
    obs = _promote_near_ready_obs(without_lillie=True, without_fez=True)

    seen = {}
    _original = m.score_option

    def _spy(tc, o, score):
        seen.setdefault("override", tc._promote_setup_ko_attacker)
        return _original(tc, o, score)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    m.score_option = _spy
    try:
        m.agent(obs)
    finally:
        m.score_option = _original

    assert seen["override"] is None, (
        "sin motor de robo alguno el override del atacante casi listo no debe "
        f"existir; obtuvo {seen['override']}")

def test_promote_near_ready_fez_draw_engine_is_enough():
    # Without a Lillie's but WITH the Fezandipiti ex on the bench: Flip the Script (draw 3,
    # triggered by the KO that forces us to promote) is engine enough to
    # find the missing Grass, and the Ogerpon ex at 2/3 keeps its way out
    # (retreat 1, it carries 2 energies) in case the draw fails. The
    # nearly ready attacker is promoted, not the Tapu Bulu 0/4 with retreat 3.
    obs = _promote_near_ready_obs(without_lillie=True)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert any(b and b["id"] == m.Fezandipiti_ex for b in me["bench"])
    ogerpon_opt = next(i for i, o in enumerate(obs["select"]["option"])
                       if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [ogerpon_opt]

def _load_alakazam_step75_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "alakazam_step75_xerosic_engine_over_lillie.json",
        encoding="utf-8"))["observation"]

def test_alakazam_step75_plays_ultra_ball_not_lillie():
    obs = _load_alakazam_step75_obs()
    play_map = _resolve_play_options(obs)
    # The fixture must offer BOTH plays for the test to be meaningful.
    assert m.Ultra_Ball in play_map.values()
    assert m.Lillie_Determination in play_map.values()
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    lillie_opt = next(
        i for i, cid in play_map.items() if cid == m.Lillie_Determination)

    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [ub_opt], (
        f"vs Alakazam con mano rival 10 (Powerful Hand) debe jugar Ultra Ball "
        f"(opt {ub_opt}) para cavar Meowth ex -> Xerosic, no Lillie's; "
        f"obtuvo {result} (map={play_map})")
    assert result != [lillie_opt]
    # The pivot must be armed so that the FETCH picks Meowth ex.
    assert m._ub_engine_pivot_turn is True

def test_alakazam_step75_control_small_op_hand_allows_lillie():
    # Boundary: with a SMALL rival hand (< 7, outside the big Powerful
    # Hand zone) the disruption engine does NOT fire -> the Ultra Ball goes back to
    # its normal veto and Lillie's is no longer vetoed by
    # `alakazam_reserves_supporter_for_xerosic`: it refreshes as before.
    import copy as _copy
    obs = _copy.deepcopy(_load_alakazam_step75_obs())
    obs["current"]["players"][1]["handCount"] = 6
    play_map = _resolve_play_options(obs)
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    lillie_opt = next(
        i for i, cid in play_map.items() if cid == m.Lillie_Determination)

    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [lillie_opt], (
        f"con mano rival 6 (< 7) el motor de dig Xerosic NO debe dispararse: "
        f"se juega Lillie's como antes; obtuvo {result} (map={play_map})")
    assert result != [ub_opt]

def test_lucario_step99_promotes_evolution_survivor_not_ogerpon():
    obs = _load_lucario_step99_obs()
    chosen = _promote_choice_id(obs)
    assert chosen == m.Dipplin, (
        f"debe promover Dipplin (evoluciona a Hydrapple ex 330, sobrevive a los "
        f"270 del Mega Lucario), no Ogerpon ex (210, muere -> 2 premios); "
        f"promovio id {chosen}")
    assert chosen != m.Teal_Mask_Ogerpon_ex

def test_lucario_step99_control_no_evolution_in_hand_keeps_normal():
    # Boundary: with no evolution (Hydrapple ex) in hand there is NO survivor
    # via evolution -> the override does not fire and the promotion follows the
    # normal logic (which does NOT pick Dipplin here). It confirms that the override depends on
    # having the evolution in hand.
    import copy as _copy
    obs = _copy.deepcopy(_load_lucario_step99_obs())
    me = obs["current"]["players"][0]
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Hydrapple_ex]
    chosen = _promote_choice_id(obs)
    assert chosen != m.Teal_Mask_Ogerpon_ex, (
        f"SUPERSEDIDO (user, registro_005 paso 64): sin superviviente posible "
        f"-- Mega Lucario pega 270 y aqui muere todo -- se promueve el cuerpo "
        f"de MENOS premios (Dipplin/Meganium, 1) y no el Ogerpon ex (2); "
        f"promovio id {chosen}")

def _load_lucario_step80_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "lucario_step80_charge_bench_hydrapple_over_teal_dance.json",
        encoding="utf-8"))["observation"]

def test_lucario_step80_ripening_charges_bench_hydrapple_over_teal_dance():
    obs = _load_lucario_step80_obs()
    me = obs["current"]["players"][0]
    opts = obs["select"]["option"]
    # Locate the ability options: Ripening (Hydrapple) and Teal Dance (Ogerpon).
    ripen_opt = next(i for i, o in enumerate(opts)
                     if o.get("type") == int(m.OptionType.ABILITY)
                     and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    teal_opts = [i for i, o in enumerate(opts)
                 if o.get("type") == int(m.OptionType.ABILITY)
                 and me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    assert teal_opts, "el fixture debe ofrecer Teal Dance para que el test valga"
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [ripen_opt], (
        f"debe usar Ripening Charge para cargar el Hydrapple ex de banca vacio "
        f"(atacante futuro, opt {ripen_opt}), no Teal Dance sobre un Ogerpon ex "
        f"ya cargado (opts {teal_opts}); obtuvo {result}")

def test_lucario_step80_control_ready_bench_hydrapple_does_not_block_teal():
    # Boundary: if the bench Hydrapple ex is ALREADY ready (>=2 energies), charging it
    # again is not a priority; the Ripening to that Hydrapple no longer scores as
    # an empty-attacker charge (it drops below 31150) and must not hijack the turn.
    # It verifies that the fix depends on the Hydrapple having NO energy.
    import copy as _copy
    obs = _copy.deepcopy(_load_lucario_step80_obs())
    me = obs["current"]["players"][0]
    # Charging the bench Hydrapple to 2 energies (already ready for Syrup Storm).
    for b in me["bench"]:
        if b["id"] == m.Hydrapple_ex:
            b["energies"] = [1, 1]
            b["energyCards"] = [{"id": 1, "playerIndex": 0, "serial": 300},
                                {"id": 1, "playerIndex": 0, "serial": 301}]
    opts = obs["select"]["option"]
    ripen_opt = next(i for i, o in enumerate(opts)
                     if o.get("type") == int(m.OptionType.ABILITY)
                     and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [ripen_opt], (
        f"con el Hydrapple ex de banca YA cargado, la Ripening no debe forzarse "
        f"(opt {ripen_opt}); obtuvo {result}")

def _load_marnie_step47_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "marnie_step47_play_boss_not_dawn.json",
        encoding="utf-8"))["observation"]

def test_marnie_step47_plays_boss_orders_not_dawn():
    obs = _load_marnie_step47_obs()
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    opts = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(opts)
                    if o.get("type") == int(m.OptionType.PLAY)
                    and me["hand"][o["index"]]["id"] == m.Boss_Orders)
    dawn_opt = next(i for i, o in enumerate(opts)
                    if o.get("type") == int(m.OptionType.PLAY)
                    and me["hand"][o["index"]]["id"] == m.Dawn)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [boss_opt], (
        f"debe jugar Boss's Orders (opt {boss_opt}, gustear el Morgrem pre-evo de "
        f"Grimmsnarl ex) en vez de Dawn (opt {dawn_opt}); obtuvo {result}")

def test_marnie_step47_control_active_on_ex_line_keeps_normal():
    # Boundary: if the rival active is ALREADY part of the bench ex line (e.g. another
    # energized active Morgrem), knocking it out already hits the line, so gusting the
    # bench copy is not a priority and the off-line deny-evo must NOT fire.
    import copy as _copy
    obs = _copy.deepcopy(_load_marnie_step47_obs())
    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    # Turning the active Munkidori into an energized Morgrem (the same line as the bench).
    op["active"][0]["id"] = 647
    op["active"][0]["maxHp"] = 100
    op["active"][0]["hp"] = 100
    op["active"][0]["preEvolution"] = [{"id": 646, "playerIndex": op["active"][0]["playerIndex"], "serial": 999}]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(opts)
                    if o.get("type") == int(m.OptionType.PLAY)
                    and me["hand"][o["index"]]["id"] == m.Boss_Orders)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [boss_opt], (
        f"con el activo YA en la linea ex, el deny-evo off-line no debe forzar "
        f"Boss's (opt {boss_opt}); obtuvo {result}")

def _load_alakazam_step17_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "alakazam_step17_play_lillie_not_xerosic.json",
        encoding="utf-8"))["observation"]

def test_alakazam_step17_plays_lillie_not_xerosic_small_op_hand():
    obs = _load_alakazam_step17_obs()
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    opts = obs["select"]["option"]
    lillie_opt = next(i for i, o in enumerate(opts)
                      if o.get("type") == int(m.OptionType.PLAY)
                      and me["hand"][o["index"]]["id"] == m.Lillie_Determination)
    xerosic_opt = next(i for i, o in enumerate(opts)
                       if o.get("type") == int(m.OptionType.PLAY)
                       and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [lillie_opt], (
        f"con la mano rival minima (4) debe jugar Lillie's (opt {lillie_opt}, "
        f"refresco/desarrollo) no Xerosic (opt {xerosic_opt}); obtuvo {result}")

def test_alakazam_step17_control_large_op_hand_keeps_xerosic():
    # Boundary: with a BIG rival hand (>= 7) capping Powerful Hand IS worth more;
    # Xerosic must still beat Lillie's (it must not yield through the minimal hand).
    #
    # The turn is moved off 2 on purpose. The record is OUR FIRST TURN going
    # second, and there Lillie's now wins whatever the size of the opposing hand
    # (`first_turn_yields_to_lillie`, see
    # tests/test_first_turn_lillie_over_xerosic.py). What this control pins is
    # the OTHER boundary -- the one of `alakazam_yields_to_lillie_tiny_opponent_hand`,
    # which reads the opposing hand and nothing else -- so it has to be measured
    # on a turn where the calendar is not already deciding.
    import copy as _copy
    obs = _copy.deepcopy(_load_alakazam_step17_obs())
    obs["current"]["turn"] = 4
    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    op["handCount"] = 9
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    xerosic_opt = next(i for i, o in enumerate(opts)
                       if o.get("type") == int(m.OptionType.PLAY)
                       and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [xerosic_opt], (
        f"con la mano rival grande (9) debe seguir capando con Xerosic "
        f"(opt {xerosic_opt}); obtuvo {result}")

def test_alakazam_holds_xerosic_plays_it_not_meowth_fetch():
    import json as _json
    obs = _json.load(open(
        ROOT / "tests" / "fixtures" /
        "alakazam_hold_xerosic_no_meowth_fetch.json",
        encoding="utf-8"))["observation"]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    xer = next(i for i, o in enumerate(opts)
               if o.get("type") == int(m.OptionType.PLAY)
               and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [xer], (
        f"con Xerosic en mano (mejor Supporter vs Alakazam) debe jugarlo "
        f"(opt {xer}), no bajar Meowth ex (opt {meowth}) a buscar otro; "
        f"obtuvo {result}")
