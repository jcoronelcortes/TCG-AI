"""Regression slice 8 of 8. The Ultra Ball 'use it or lose it' family, the
Archaludon finishers and the last ex-swap rules."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

_CERULEDGE_UB_FIXTURE = (
    ROOT / "tests" / "fixtures" / "ceruledge_t2_no_ub_banca_poblada.json")

def test_ceruledge_t2_does_not_play_the_ub_with_a_populated_bench():
    with open(_CERULEDGE_UB_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.END), (
        f"primer turno con banca 4/5 y mano rica: la UB no se juega (quema 2 "
        f"cartas utiles por un basico redundante); esperaba END, {opt}")

_ABOMASNOW_NS_SYRUP_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_step68_ns_energia_para_syrup_letal.json")

_ABOMASNOW_NS_FETCH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_step68b_ns_fetch_energia.json")

_ABOMASNOW_TEAL_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_step68c_teal_dance_habilita_syrup.json")

def test_abomasnow_step68_plays_the_ns_for_the_lethal_syrup():
    with open(_ABOMASNOW_NS_SYRUP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"con Syrup Storm a 20 del KO y DOS Plantas en el descarte, Night "
        f"Stretcher va ANTES de atacar; esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == m.Night_Stretcher, (
        f"esperaba Night Stretcher, jugo "
        f"{m.card_table[me['hand'][opt['index']]['id']].name}")

def test_abomasnow_step68_the_ns_recovers_the_grass_not_the_meganium():
    with open(_ABOMASNOW_NS_FETCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    elegida = me["discard"][opt["index"]]["id"]
    assert elegida == m.Basic_Grass_Energy, (
        f"la Planta habilita el Syrup Storm letal ESTE turno; recupero "
        f"{m.card_table[elegida].name}")

def test_abomasnow_step68_teal_dance_makes_the_syrup_lethal():
    with open(_ABOMASNOW_TEAL_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ABILITY), (
        f"la Planta recuperada debe entrar al campo con Teal Dance (el Syrup "
        f"Storm cuenta la Planta de TODOS nuestros Pokemon: 330 -> 390 >= "
        f"350); esperaba ABILITY, {opt}")

_ABOMASNOW_FINISHER_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_step68d_ataca_tras_teal_dance.json")

def test_abomasnow_step68_finishes_after_the_charge():
    """Closing the NS -> Grass -> Teal Dance -> ATTACK chain: with the 12
    Grass already on the field the Syrup Storm does 390 >= 350 and knocks out."""
    with open(_ABOMASNOW_FINISHER_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con la carga hecha toca rematar (390 >= 350); esperaba ATTACK, {opt}")

_UB_NO_USABLE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_t6_no_ub_si_ya_hay_pokemon_en_mano.json")

_UB_BUDEW_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_t6_ub_con_budew_rival.json")

_UB_PREEVO_FRESCA_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_t6_no_ub_preevo_bajada_este_turno.json")

_UB_PREEVO_READY_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_t6_ub_preevo_evolucionable.json")

def _elige(fixture):
    with open(fixture, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    return obs, obs["select"]["option"][m.agent(obs)[0]]

def test_the_ub_is_not_played_if_a_playable_pokemon_is_already_in_hand():
    obs, opt = _elige(_UB_NO_USABLE_FIXTURE)
    assert opt.get("type") == int(OptionType.END), (
        f"con un Meowth ex ya en mano (vetado) y nada evolucionable, cavar "
        f"con Ultra Ball trae mas de lo mismo y quema 2 cartas; "
        f"esperaba END, {opt}")

def test_the_ub_is_played_with_an_opponent_budew_because_of_the_item_lock():
    obs, opt = _elige(_UB_BUDEW_FIXTURE)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"con Budew en el campo rival la Ultra Ball es 'usala o pierdela' "
        f"(el proximo turno no hay items); esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == _ULTRA_BALL

def test_the_ub_does_not_search_an_evolution_for_a_preevo_played_this_turn():
    obs, opt = _elige(_UB_PREEVO_FRESCA_FIXTURE)
    assert opt.get("type") == int(OptionType.END), (
        f"con la banca llena y el Applin recien bajado (no puede evolucionar "
        f"este turno) la Ultra Ball no produce nada; esperaba END, {opt}")

def test_the_ub_does_search_the_evolution_when_the_preevo_can_already_evolve():
    obs, opt = _elige(_UB_PREEVO_READY_FIXTURE)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"contrafactual: con el Applin asentado la evolucion SI es jugable "
        f"este turno y la red debe cavar; esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == _ULTRA_BALL

_UB_NO_CAVA_2O_MEOWTH_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "cynthia_no_ub_para_cavar_segundo_meowth_step35.json")

def _ub_cynthia_obs(mutar=None):
    with open(_UB_NO_CAVA_2O_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    if mutar is not None:
        mutar(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    play = {}
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(OptionType.PLAY):
            play[me["hand"][o["index"]]["id"]] = i
    return obs, play, m.agent(obs)

def test_no_ub_to_dig_a_second_meowth_with_the_last_ditch_spent():
    obs, play, result = _ub_cynthia_obs()
    assert result != [play[_ULTRA_BALL]], (
        f"el Meowth ex de la banca aparecio este turno (Last-Ditch gastada): "
        f"un 2o Meowth ex no buscaria nada y la rama PLAY lo veta, asi que la "
        f"Ultra Ball (opt {play[_ULTRA_BALL]}) no debe jugarse; obtuvo {result}")
    assert result == [play[m.Boss_Orders]], (
        f"con el activo cargado la jugada del turno es Boss's Orders "
        f"(opt {play[m.Boss_Orders]}) y noquear; obtuvo {result}")

def test_the_ub_digs_the_second_meowth_if_the_last_ditch_is_still_free():
    # Counterfactual (1): the SAME board with the Meowth ex from a PREVIOUS turn.
    # The Last-Ditch is free, the 2nd Meowth WOULD search for a Supporter and the PLAY
    # branch plays it (`_ub_meowth_pending`) -> the chain is completed and it digs.
    def _asentar_meowth(obs):
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        for pk in me["bench"]:
            if pk["id"] == m.Meowth_ex:
                pk["appearThisTurn"] = False
    obs, play, result = _ub_cynthia_obs(_asentar_meowth)
    assert result == [play[_ULTRA_BALL]], (
        f"con la Last-Ditch libre la cadena UB->Meowth->Supporter si produce: "
        f"esperaba jugar la Ultra Ball (opt {play[_ULTRA_BALL]}); obtuvo {result}")

def test_the_ub_does_not_dig_the_evolution_already_in_hand():
    # A unit test of the Bayleef->Meganium branch: with the Meganium IN HAND the line
    # evolves without an Ultra Ball, so that branch cannot justify the
    # search (1000). Without it in hand, it can.
    def _target(hand_counts):
        return m._eval_ub_best_target(
            {m.Bayleef: 1}, hand_counts,
            meganium_in_play=False, has_hydrapple=False, forest_in_play=False,
            op_has_ex_immune_active=False, op_has_ex_immune_bench=False,
            op_prize=6, bench_count=1,
            state=SimpleNamespace(turn=6, supporterPlayed=True,
                                  energyAttached=True),
            ko_last_turn=False, _best_supp_in_deck_val=0,
            supporters_in_hand=0, hand_is_weak=False,
            has_energy_for_teal=False, _we_go_first=False,
            _best_supp_in_hand_val=0, op_is_crustle_deck=False,
            op_is_cornerstone_deck=False, op_active_is_budew=False,
            meowth_ability_lock=False)

    with_meganium = _target({m.Meganium: 1})
    without_meganium = _target({})
    assert without_meganium >= 1000, (
        f"sin el Meganium en la mano hay que cavarlo; objetivo {without_meganium}")
    assert with_meganium < 1000, (
        f"con el Meganium ya en la mano la Ultra Ball no aporta a esa linea; "
        f"objetivo {with_meganium}")

def test_the_ub_digs_the_evolution_when_it_is_not_in_hand():
    # Counterfactual (2): with no Meganium in hand, the Bayleef->Meganium line
    # DOES need the search and the Ultra Ball is played again.
    def _quitar_meganium(obs):
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        pos = next(i for i, c in enumerate(me["hand"])
                   if c["id"] == m.Meganium)
        del me["hand"][pos]
        for o in obs["select"]["option"]:
            if o.get("type") == int(OptionType.PLAY) and o["index"] > pos:
                o["index"] -= 1
    obs, play, result = _ub_cynthia_obs(_quitar_meganium)
    assert result == [play[_ULTRA_BALL]], (
        f"sin el Meganium en la mano la Fase 2 de la linea si hay que cavarla: "
        f"esperaba la Ultra Ball (opt {play[_ULTRA_BALL]}); obtuvo {result}")

def test_ub_dig_meowth_gets_played_needs_a_free_last_ditch():
    # A unit test of the helper: the card's rule (ONE Last-Ditch per turn) rules
    # over the body count.
    free_ctx = _make_boss_ctx(field_counts={m.Meowth_ex: 1},
                              meowth_ld_free=True)
    ctx_gastada = _make_boss_ctx(field_counts={m.Meowth_ex: 1},
                                 meowth_ld_free=False)
    ctx_dos = _make_boss_ctx(field_counts={m.Meowth_ex: 2},
                             meowth_ld_free=True)
    assert m._ub_dig_meowth_gets_played(free_ctx) is True
    assert m._ub_dig_meowth_gets_played(ctx_gastada) is False
    assert m._ub_dig_meowth_gets_played(ctx_dos) is False

_ARCHA_P78_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78_no_gustear_remate_de_dos_premios.json")

_ARCHA_P78B_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78b_ataca_por_dos_premios.json")

_ARCHA_P78C_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78c_ns_unica_via_al_remate.json")

_ARCHA_P78D_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78d_ns_recupera_la_planta.json")

def test_archaludon_step78_does_not_gust_and_throw_away_the_two_prize_finisher():
    with open(_ARCHA_P78_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    play = me["hand"][opt["index"]]["id"] if opt.get("type") == int(
        OptionType.PLAY) else None
    assert play != m.Boss_Orders, (
        "Boss's Orders sube al Duraludon (1 premio) y tira el remate de DOS "
        "premios contra el Archaludon ex: nunca se juega aqui")

def test_archaludon_step78b_finishes_the_archaludon_for_two_prizes():
    """With the turn's Supporter already spent it is time to ATTACK: Myriad Leaf Shower
    30+30x(6 ours + 3 of the rival) = 300, minus 30 of Grass resistance =
    270 = the exact life of the Archaludon ex (2 prizes)."""
    with open(_ARCHA_P78B_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"el activo noquea al Archaludon ex (270 >= 270): esperaba ATTACK, {opt}")

def test_archaludon_step78c_the_night_stretcher_joins_the_finisher():
    """The same board with the rival at 2 energies: Myriad drops to 270-30 = 240 and the
    active NO LONGER finishes. The only route to the 2 prizes is recovering a Grass
    with a Night Stretcher, charging it with Teal Dance (the manual attachment is already spent)
    and promoting the Hydrapple ex: 8 units after retreating + 2 = 10 -> Syrup 330 -
    30 = 300 >= 270. The Night Stretcher must enter that analysis."""
    with open(_ARCHA_P78C_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    assert me["hand"][opt["index"]]["id"] == m.Night_Stretcher, (
        f"la Night Stretcher es la unica via al remate de 2 premios; jugo "
        f"{m.card_table[me['hand'][opt['index']]['id']].name}")

def test_archaludon_step78d_the_night_stretcher_recovers_the_grass():
    with open(_ARCHA_P78D_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert me["discard"][opt["index"]]["id"] == m.Basic_Grass_Energy, (
        "el fetch debe traer la ENERGIA (es la que arma el remate), no un cuerpo")

_ARCHA_P123_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_step123_ns_remate_ganador.json")

def test_archaludon_step123_the_ns_builds_the_winning_finisher():
    with open(_ARCHA_P123_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"atacar por 270 contra 300 no cierra nada; la Planta del descarte SI "
        f"(330 >= 300, banca rival vacia = victoria); esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == m.Night_Stretcher, (
        f"esperaba Night Stretcher, jugo "
        f"{m.card_table[me['hand'][opt['index']]['id']].name}")

_XX_NO_EX_MENOR = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_no_retirar_ex_por_ex_menor.json")

_XX_NO_1PRIZE_WITHOUT_KO = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_no_retirar_si_el_1premio_no_remata.json")

_XX_SI_1PREMIO_KO = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_retirar_si_el_1premio_remata.json")

_XX_SI_EX_KO = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_retirar_si_el_ex_de_banca_remata.json")

def _opcion_elegida(fixture):
    with open(fixture, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    return obs, obs["select"]["option"][m.agent(obs)[0]]

def test_do_not_swap_an_ex_for_another_ex_with_less_life():
    _, opt = _opcion_elegida(_XX_NO_EX_MENOR)
    assert opt.get("type") != int(OptionType.RETREAT), (
        f"el Hydrapple ex (330) no se cambia por un Ogerpon ex (210) que ni "
        f"remata ni aguanta mas: se queda el muro; eligio {opt}")

def test_do_not_retreat_the_ex_if_the_one_prize_body_does_not_finish():
    _, opt = _opcion_elegida(_XX_NO_1PRIZE_WITHOUT_KO)
    assert opt.get("type") != int(OptionType.RETREAT), (
        f"un Meganium listo que solo hace chip (110 contra 300 PV) no paga "
        f"cambiar el muro de 330; eligio {opt}")

def test_the_ex_does_retreat_when_the_one_prize_body_finishes():
    _, opt = _opcion_elegida(_XX_SI_1PREMIO_KO)
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con un Meganium (1 premio) que NOQUEA al activo rival, retirar el ex "
        f"cobra premio y concede la mitad si nos responden; eligio {opt}")

def test_the_ex_does_retreat_when_the_bench_body_finishes():
    _, opt = _opcion_elegida(_XX_SI_EX_KO)
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"si el cuerpo de banca NOQUEA, el cambio cobra premio y si compensa; "
        f"eligio {opt}")

_AERA_T11 = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step98_energia_al_activo_para_retirar.json")

_AERA_T13 = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step117_energia_al_activo_para_retirar.json")

_AERA_T9_BENCH = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step90_energia_a_la_banca_si_deja_listo.json")

_AERA_RETREAT = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step98b_retirar_para_atacar_con_meganium.json")

def test_archaludon_step98_energy_to_the_active_to_enable_the_retreat():
    obs, opt = _opcion_elegida(_AERA_T11)
    assert opt.get("type") == int(OptionType.ATTACH), f"esperaba ATTACH, {opt}"
    assert opt.get("inPlayArea") == int(AreaType.ACTIVE), (
        f"la Planta debe ir al Meowth ex ACTIVO (paga la retirada de 1 y habilita "
        f"subir al Meganium listo a atacar); cargarla en el Meganium de banca, ya "
        f"a e4, no suma dano y regala el turno; eligio {opt}")

def test_archaludon_step117_energy_to_the_active_even_if_the_chip_does_not_finish():
    obs, opt = _opcion_elegida(_AERA_T13)
    assert opt.get("type") == int(OptionType.ATTACH), f"esperaba ATTACH, {opt}"
    assert opt.get("inPlayArea") == int(AreaType.ACTIVE), (
        f"Solar Beam (140) no noquea al Cinderace (160) pero 140 de chip valen "
        f"mas que cerrar el turno sin atacar; eligio {opt}")

def test_archaludon_step90_the_energy_goes_to_the_bench_when_that_is_what_gets_ready():
    obs, opt = _opcion_elegida(_AERA_T9_BENCH)
    assert opt.get("type") == int(OptionType.ATTACH), f"esperaba ATTACH, {opt}"
    assert opt.get("inPlayArea") == int(AreaType.BENCH), (
        f"con el Meganium a e2 (necesita 4) la Planta es la que lo deja LISTO: su "
        f"sitio es la BANCA, no pagar una retirada que promoveria a un cuerpo que "
        f"tampoco podria atacar; eligio {opt}")

def test_archaludon_step98b_retreats_to_attack_with_meganium():
    obs, opt = _opcion_elegida(_AERA_RETREAT)
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con la Planta ya en el activo la retirada es legal: hay que retirar el "
        f"Meowth ex (no puede atacar) y subir el Meganium a atacar; eligio {opt}")

_ALK_P16_NO_MEOWTH = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step16_no_meowth_con_lillie_en_mano.json")

def _secuencia_fixture(fixture):
    with open(fixture, encoding="utf-8") as f:
        return [p["observation"] for p in json.load(f)["sequence"]]

def test_alakazam_step16_plays_lillie_instead_of_playing_meowth():
    obs = _secuencia_fixture(_ALK_P16_NO_MEOWTH)[0]
    _reset_state_record_008()
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Lillie_Determination, (
        f"con DOS Lillie's en mano y el Supporter libre hay que JUGAR la "
        f"Lillie's; bajar Meowth ex solo expone un cuerpo de 2 premios (su "
        f"fetch seria redundante); jugo {m.card_table[elegida].name}")

def test_alakazam_step16_the_meowth_engine_and_the_ability_do_not_contradict():
    """An invariant: if the Meowth ex is played, its Last-Ditch MUST be used."""
    obs_play, obs_ability = _secuencia_fixture(_ALK_P16_NO_MEOWTH)

    _reset_state_record_008()
    me = obs_play["current"]["players"][obs_play["current"]["yourIndex"]]
    opt = obs_play["select"]["option"][m.agent(obs_play)[0]]
    plays_meowth = (opt.get("type") == int(OptionType.PLAY)
                   and me["hand"][opt["index"]]["id"] == m.Meowth_ex)

    _reset_state_record_008()
    uses_ability = (obs_ability["select"]["option"][m.agent(obs_ability)[0]]
                     .get("type") == int(OptionType.YES))

    assert not (plays_meowth and not uses_ability), (
        "incoherencia: se baja el Meowth ex por su Last-Ditch Catch y despues "
        "se RECHAZA el fetch -- se regala un cuerpo de 2 premios por nada")

_BCS_BEFORE_MEOWTH = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step6_bcs_antes_de_bajar_meowth.json")

_BCS_BEFORE_OGERPON = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step36_bcs_antes_de_bajar_ogerpon.json")

def _bcs_and_pokemon_in_menu(obs):
    """(the BCS's index, the indices of Pokemon plays) in the menu of `obs`."""
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    bcs, pokes = None, []
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") != int(OptionType.PLAY):
            continue
        cid = me["hand"][o["index"]]["id"]
        if cid == m.Bug_Catching_Set:
            bcs = i
        else:
            data = m.card_table.get(cid)
            if data is not None and data.cardType == m.CardType.POKEMON:
                pokes.append(i)
    return bcs, pokes

def test_archaludon_step6_plays_the_bcs_before_playing_the_meowth():
    with open(_BCS_BEFORE_MEOWTH, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    bcs, pokes = _bcs_and_pokemon_in_menu(obs)
    assert bcs is not None and pokes, "la fixture debe ofrecer BCS y bajar Pokemon"
    result = m.agent(obs)
    assert result == [bcs], (
        f"el Bug Catching Set (opt {bcs}) se juega ANTES de bajar un Pokemon "
        f"(opts {pokes}): sus 2 cartas cambian que cuerpo baja; obtuvo {result}")

def test_archaludon_step36_plays_the_bcs_before_playing_the_ogerpon():
    with open(_BCS_BEFORE_OGERPON, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    bcs, pokes = _bcs_and_pokemon_in_menu(obs)
    assert bcs is not None and pokes, "la fixture debe ofrecer BCS y bajar Pokemon"
    result = m.agent(obs)
    assert result == [bcs], (
        f"con la banca a 3/5 el BCS (opt {bcs}) va antes que los cuerpos "
        f"(opts {pokes}): jugarlo con la banca ya llena desperdicia lo que "
        f"encuentre; obtuvo {result}")

_LUCARIO_T4_SEQ = (
    ROOT / "tests" / "fixtures" / "lucario_t4_lillie_sobre_ub_y_boss.json")

def _lucario_t4_up_to(step):
    """Replays the sequence of turn 4 up to `paso` and returns (obs, result)."""
    with open(_LUCARIO_T4_SEQ, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    obs = result = None
    for item in seq:
        if item["step"] > step:
            break
        obs = item["observation"]
        result = m.agent(obs)
    return obs, result

def test_lucario_step54_plays_lillie_not_the_ultra_ball():
    obs, result = _lucario_t4_up_to(54)

    play_map = _resolve_play_options(obs)
    assert m.Lillie_Determination in play_map.values()
    assert m.Ultra_Ball in play_map.values()
    lillie_opt = next(i for i, cid in play_map.items()
                      if cid == m.Lillie_Determination)
    ub_opts = [i for i, cid in play_map.items() if cid == m.Ultra_Ball]

    assert result == [lillie_opt], (
        f"con el activo condenado y sin atacante de banca hay que refrescar con "
        f"Lillie's (opt {lillie_opt}, roba 8 con 6 premios), no gastar Ultra Ball "
        f"(opts {ub_opts}) + 2 descartes en un objetivo que Lillie's barajaria; "
        f"obtuvo {result}")

def test_lucario_step57_plays_lillie_not_boss_orders():
    obs, result = _lucario_t4_up_to(57)

    play_map = _resolve_play_options(obs)
    assert m.Lillie_Determination in play_map.values()
    assert m.Boss_Orders in play_map.values()
    lillie_opt = next(i for i, cid in play_map.items()
                      if cid == m.Lillie_Determination)
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    assert result == [lillie_opt], (
        f"el Supporter del turno debe ser Lillie's (opt {lillie_opt}): un gusteo "
        f"de 1 premio (Boss's, opt {boss_opt}) con el activo condenado y la banca "
        f"sin atacante deja el tablero sin plan; obtuvo {result}")

_ALK_T14_SEQ = (
    ROOT / "tests" / "fixtures" / "alakazam_t14_ruta_de_ataque_por_retirada.json")

def _alk_t14_up_to(step):
    """Replays the sequence of turn 14 up to `paso`; returns (obs, result)."""
    with open(_ALK_T14_SEQ, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    obs = result = None
    for item in seq:
        if item["step"] > step:
            break
        obs = item["observation"]
        result = m.agent(obs)
    return obs, result

def _alk_t14_indices(obs):
    """(attachments to the active, attachments to the bench Meganium, Ripening's index)."""
    to_active, al_meganium, ripening = [], [], None
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(OptionType.ATTACH):
            if o.get("inPlayArea") == int(AreaType.ACTIVE):
                to_active.append(i)
            else:
                bench = obs["current"]["players"][0]["bench"]
                if bench[o["inPlayIndex"]]["id"] == m.Meganium:
                    al_meganium.append(i)
        elif o.get("type") == int(OptionType.ABILITY):
            card = m.get_card(m.to_observation_class(obs), o["area"], o["index"], 0)
            if card is not None and card.id == m.Hydrapple_ex:
                ripening = i
    return to_active, al_meganium, ripening

def test_alakazam_step136_charges_the_active_to_enable_the_retreat():
    obs, result = _alk_t14_up_to(136)

    to_active, al_meganium, _ = _alk_t14_indices(obs)
    assert to_active and al_meganium, "la fixture debe ofrecer ambos destinos"

    assert result[0] in to_active, (
        f"la Planta va al ACTIVO (opts {to_active}) para pagar su retirada y subir "
        f"al Hydrapple ex listo; cargar el Meganium de banca (opts {al_meganium}) "
        f"no le da un ataque este turno porque el activo no puede retirarse; "
        f"obtuvo {result}")
    assert result[0] not in al_meganium

def test_alakazam_step137_uses_ripening_charge_instead_of_burning_the_grass():
    obs, result = _alk_t14_up_to(137)

    _, _, ripening = _alk_t14_indices(obs)
    play_map = _resolve_play_options(obs)
    assert ripening is not None, "la fixture debe ofrecer Ripening Charge"
    assert m.Ultra_Ball in play_map.values()
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)

    assert result == [ripening], (
        f"con el adjunte manual gastado, Ripening Charge (opt {ripening}) es la "
        f"UNICA via para poner la Planta en el campo; la Ultra Ball (opt {ub_opt}) "
        f"descartaria las dos Plantas para buscar lo que no hace falta; "
        f"obtuvo {result}")

def test_alakazam_step141_the_night_stretcher_recovers_the_grass_from_the_discard():
    obs, result = _alk_t14_up_to(141)

    play_map = _resolve_play_options(obs)
    assert m.Night_Stretcher in play_map.values()
    ns_opt = next(i for i, cid in play_map.items() if cid == m.Night_Stretcher)
    end_opt = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("type") == int(OptionType.END))
    # With the bench FULL the Night Stretcher is only worth the ENERGY in the discard.
    assert obs["current"]["players"][0]["bench"] and len(
        obs["current"]["players"][0]["bench"]) == 5

    assert result == [ns_opt], (
        f"la Night Stretcher (opt {ns_opt}) recupera la Planta que paga la retirada "
        f"del activo (Ripening Charge la pone y sube el Hydrapple ex a atacar); "
        f"terminar el turno (opt {end_opt}) lo regala; obtuvo {result}")

def test_alakazam_step137_ripening_charge_aims_at_the_active():
    """The ability's TARGET (ATTACH_FROM) must be the ACTIVE, not the bench.

    The other half of the chain: switching Ripening Charge on is useless if the
    Grass falls into normal bench development and the retreat stays blocked.
    `energy_score` ALREADY did that routing right (this test also passes with the
    previous code); it is pinned here because the ability's new branch depends on
    it: if anyone touches the routing, the play turns into a wasted Grass.
    The ATTACH_FROM select the engine presents right after choosing Ripening
    Charge is synthesised (the same shape as registro_004 step 27): one
    CARD option per Pokemon of ours (area 4 = active, 5 = bench).
    """
    import copy

    with open(_ALK_T14_SEQ, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    obs137 = next(x["observation"] for x in seq if x["step"] == 137)

    syn = copy.deepcopy(obs137)
    me = syn["current"]["players"][0]
    options = [{"area": int(AreaType.ACTIVE), "index": 0, "playerIndex": 0,
                 "type": int(OptionType.CARD)}]
    for i in range(len(me["bench"])):
        options.append({"area": int(AreaType.BENCH), "index": i,
                         "playerIndex": 0, "type": int(OptionType.CARD)})
    syn["select"] = {
        "context": int(SelectContext.ATTACH_FROM), "contextCard": None,
        "deck": None,
        "effect": {"id": m.Hydrapple_ex, "playerIndex": 0, "serial": 18},
        "maxCount": 1, "minCount": 1, "option": options,
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}

    for item in seq:
        if item["step"] > 137:
            break
        m.agent(item["observation"])
    result = m.agent(syn)

    assert result == [0], (
        "la Planta de Ripening Charge va al ACTIVO (opt 0, Fezandipiti ex) para "
        "pagar su coste de retirada y promover al Hydrapple ex listo; cualquier "
        f"objetivo de banca deja la retirada bloqueada; obtuvo {result}")

_UB_LILLIE_COST_FIXTURE = (
    ROOT / "tests" / "fixtures" / "comfey_t1_primeros_no_ub_que_quema_lillie.json")

def test_t1_going_first_no_ub_that_would_discard_the_lillie():
    with open(_UB_LILLIE_COST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Ultra_Ball in play_map.values(), "el fixture debe ofrecer jugar Ultra Ball"
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    end_opt = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("type") == OptionType.END)

    result = m.agent(obs)

    assert result == [end_opt], (
        f"con la Lillie's como unico pago posible de la Ultra Ball hay que "
        f"TERMINAR el turno (opt {end_opt}) y conservarla; obtuvo {result}")
    assert result != [ub_opt], (
        "jugar la Ultra Ball descarta el Lillie's para cavar un Meowth ex que "
        "vuelve a buscar otro Lillie's: tres cartas por la misma jugada")

def test_the_ub_cost_vetoes_only_when_real_fodder_is_missing():
    """The predicate that builds the guard is the one Phase C already used: it switches on
    when paying for the Ultra Ball would have to take the Supporter, and NOT
    when there is fodder to spare. It pins both faces so that the guard does not
    turn into a universal Ultra Ball veto."""
    import copy

    with open(_UB_LILLIE_COST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    # Face B: the same position but with TWO spare energies in hand (real
    # fodder). The cost veto disappears and the Ultra Ball is playable again.
    rico = copy.deepcopy(obs)
    me = rico["current"]["players"][rico["current"]["yourIndex"]]
    me["hand"].extend([
        {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 200},
        {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 201},
    ])
    me["handCount"] = len(me["hand"])

    play_map = _resolve_play_options(rico)
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)

    result = m.agent(rico)

    assert result == [ub_opt], (
        f"con 3 energias de forraje el Lillie's ya no paga la Ultra Ball: la "
        f"red anti-turno-esteril debe seguir cavando (opt {ub_opt}); "
        f"obtuvo {result}")

def _ub_dead_turn_obs(op_active_id, ogerpon_in_play):
    import copy

    with open(ROOT / "tests" / "fixtures" /
              "cynthia_boss_gust_highest_evo_gabite_step51.json",
              encoding="utf-8") as f:
        o = copy.deepcopy(json.load(f)["observation"])
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    # The turn already spent except for the Ultra Ball: no Supporter, stadium or attachment.
    cur["supporterPlayed"] = True; cur["stadiumPlayed"] = True
    cur["energyAttached"] = True; cur["turn"] = 7; cur["yourIndex"] = 1

    def body(cid, hp, serial, energies=0):
        return {"appearThisTurn": False, "energies": [1] * energies,
                "energyCards": [], "hp": hp, "id": cid, "maxHp": hp,
                "playerIndex": 1, "preEvolution": [], "serial": serial,
                "tools": []}

    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 70, "id": op_active_id, "maxHp": 70, "playerIndex": 0,
                     "preEvolution": [], "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 800, 3)]
    me["bench"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 801, 1)
                   if ogerpon_in_play >= 2 else body(m.Chikorita, 70, 802)]
    # A minimal hand with real fodder (2 Grass) so that the UB does not die on cost.
    me["hand"] = [{"id": m.Ultra_Ball, "playerIndex": 1, "serial": 810},
                  {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 811},
                  {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 812}]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"index": 0, "type": 7}, {"type": 14}]}
    return o

def test_comfey_dead_turn_digs_an_ogerpon_if_there_is_room():
    obs = _ub_dead_turn_obs(m.Comfey, ogerpon_in_play=1)
    assert m.agent(obs) == [0], (
        "vs Comfey con hueco para un 2o Ogerpon ex, la Ultra Ball del turno "
        "muerto cava justo el cuerpo que el plan del matchup quiere")

def test_comfey_dead_turn_does_not_dig_if_the_plan_allows_nothing_to_be_played():
    obs = _ub_dead_turn_obs(m.Comfey, ogerpon_in_play=2)
    assert m.agent(obs) == [1], (
        "con los 2 Ogerpon ex ya en juego el plan veta bajar cualquier cuerpo: "
        "cavar quemaria dos cartas por una carta muerta, mejor terminar")

def _hostile_stadium_obs(op_active_id, opponent_stadium, own_forest=False):
    import copy

    with open(ROOT / "tests" / "fixtures" /
              "cynthia_boss_gust_highest_evo_gabite_step51.json",
              encoding="utf-8") as f:
        o = copy.deepcopy(json.load(f)["observation"])
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    cur["supporterPlayed"] = True; cur["stadiumPlayed"] = False
    cur["energyAttached"] = True; cur["turn"] = 9; cur["yourIndex"] = 1
    cur["stadium"] = [{"id": m.Forest_of_Vitality if own_forest
                       else opponent_stadium, "playerIndex": 1 if own_forest else 0,
                       "serial": 950}]

    def body(cid, hp, serial, energies=0):
        return {"appearThisTurn": False, "energies": [1] * energies,
                "energyCards": [], "hp": hp, "id": cid, "maxHp": hp,
                "playerIndex": 1, "preEvolution": [], "serial": serial,
                "tools": []}

    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 70, "id": op_active_id, "maxHp": 70, "playerIndex": 0,
                     "preEvolution": [], "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 800, 3)]
    me["bench"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 801, 1)]
    me["hand"] = [{"id": m.Forest_of_Vitality, "playerIndex": 1, "serial": 810},
                  {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 811}]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"index": 0, "type": 7}, {"type": 14}]}
    return o

def test_comfey_plays_the_forest_to_remove_neutralization_zone():
    obs = _hostile_stadium_obs(m.Comfey, m.Neutralization_Zone)
    assert m.agent(obs) == [0], (
        "la allowlist vs Comfey no puede vetar el Forest que quita la "
        "Neutralization Zone: sin quitarla, el Ogerpon ex del propio plan no "
        "puede atacar a ningun cuerpo no-ex del rival")

def test_comfey_plays_the_forest_to_remove_watchtower():
    obs = _hostile_stadium_obs(m.Comfey, m.Team_Rockets_Watchtower)
    assert m.agent(obs) == [0], (
        "mismo criterio con Team Rocket's Watchtower, que apaga la habilidad "
        "de los {C} (Last-Ditch Catch de Meowth ex)")

def test_comfey_does_not_play_a_redundant_forest_with_ours_on_the_table():
    # Control: with OUR Forest already on the table there is no lock to lift, so
    # the matchup's allowlist rules again and the 2nd Forest is not played.
    obs = _hostile_stadium_obs(m.Comfey, m.Neutralization_Zone, own_forest=True)
    assert m.agent(obs) == [1], (
        "sin estadio hostil en mesa la excepcion no aplica: vs Comfey el "
        "Forest redundante sigue vetado")

def test_counter_stadium_urgent_is_deck_agnostic():
    # The generic scorer already prioritised the counter-stadium (28000): the failure was
    # only the allowlist. This control pins it for any deck.
    obs = _hostile_stadium_obs(m.Duraludon, m.Neutralization_Zone)
    assert m.agent(obs) == [0], (
        "vs cualquier mazo, con Neutralization Zone en mesa el Forest se juega")
