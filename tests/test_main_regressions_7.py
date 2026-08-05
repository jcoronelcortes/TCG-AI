"""Regression slice 7 of 8. Marnie's gift window, the anti-Cubchoo rules and the
Grand Tree chain."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

def _load_fixture_obs(name):
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" / name, encoding="utf-8"))["observation"]

def _idx_ability(obs, card_id):
    """The index of the ABILITY option of the Pokemon `card_id` (active or bench)."""
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") != int(m.OptionType.ABILITY):
            continue
        area = o.get("area")
        if area == int(m.AreaType.ACTIVE):
            pk = me["active"][0]
        else:
            pk = me["bench"][o["index"]]
        if pk and pk["id"] == card_id:
            return i
    raise AssertionError(f"sin opcion ABILITY para {card_id}")

def test_marnie_step122_ripening_charge_heals_doomed_dipplin():
    # The state (registro_008 step 122): an active Hydrapple ex (150/330) ALREADY charged
    # for Syrup Storm, a bench Dipplin at 20/80 and a SINGLE Grass in hand.
    # The agent attached it manually (the same energy on the field, ZERO healing) and
    # the Dipplin died to the next Shadow Bullet. It must use Ripening Charge: the
    # Grass ends up in the same place and it also heals 30 (20 -> 50 > the snipe's 30).
    obs = _load_fixture_obs("marnie_step122_ripening_heals_doomed_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    ripen = _idx_ability(obs, m.Hydrapple_ex)
    attach_dipplin = next(
        i for i, o in enumerate(obs["select"]["option"])
        if o.get("type") == int(m.OptionType.ATTACH)
        and o.get("inPlayArea") != int(m.AreaType.ACTIVE)
        and me["bench"][o["inPlayIndex"]]["id"] == m.Dipplin)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [ripen], (
        f"con el Dipplin a 20/80 condenado por el snipe de 30, la ultima Planta "
        f"debe ir por Ripening Charge (opt {ripen}, cura 30) y no por el adjunte "
        f"manual (opt {attach_dipplin}, sin curacion); obtuvo {result}")

def test_marnie_step122_healthy_dipplin_keeps_manual_attach():
    # Boundary: if the Dipplin SURVIVES the snipe (60 > 30), the healing does not
    # change anything and there is no reason to divert the ability: the previous
    # behaviour is kept (a manual attachment).
    import copy as _copy
    obs = _copy.deepcopy(
        _load_fixture_obs("marnie_step122_ripening_heals_doomed_dipplin.json"))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in me["bench"]:
        if b["id"] == m.Dipplin:
            b["hp"] = 60
    ripen = _idx_ability(obs, m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [ripen], (
        "con el Dipplin a 60/80 (sobrevive el snipe de 30) la curacion no salva "
        f"nada: no debe desviarse Ripening Charge (opt {ripen})")

def test_marnie_step122_ripening_targets_the_doomed_dipplin():
    # Once Ripening Charge is chosen, the Grass must go to the DOOMED body (the Dipplin
    # at 20/80), not to the active Hydrapple nor to a healthy Ogerpon: it is where the 30 of
    # healing changes the outcome, and Syrup Storm's damage (it scales with the
    # TOTAL Grass on the field) is identical wherever it is put.
    obs = _load_fixture_obs("marnie_step122_ripening_target_doomed_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    dipplin = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("area") == int(m.AreaType.BENCH)
                   and me["bench"][o["index"]]["id"] == m.Dipplin)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [dipplin], (
        f"Ripening Charge debe curar al Dipplin condenado (opt {dipplin}); "
        f"obtuvo {result}")

def test_marnie_ripening_lethal_charge_beats_the_heal():
    # A guard: the healing NEVER steals the Grass from a finisher. The same board as
    # the previous fixture (a Dipplin doomed at 20/80) but with a BENCH Hydrapple ex
    # at 1 energy for which the 2nd Grass builds a LETHAL Syrup Storm
    # on the Grimmsnarl ex (a Grass weakness) and a retreatable active: the Grass
    # must go to that Hydrapple (41000), not to healing.
    obs = _load_fixture_obs("marnie_ripening_lethal_charge_over_heal.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    hydra = next(i for i, o in enumerate(obs["select"]["option"])
                 if o.get("area") == int(m.AreaType.BENCH)
                 and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    dipplin = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("area") == int(m.AreaType.BENCH)
                   and me["bench"][o["index"]]["id"] == m.Dipplin)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [hydra], (
        f"con un Syrup Storm LETAL pendiente la Planta va al Hydrapple ex de "
        f"banca (opt {hydra}), no a curar al Dipplin (opt {dipplin}); "
        f"obtuvo {result}")

def test_marnie_night_stretcher_recovers_hydrapple_to_save_dipplin():
    # A Night Stretcher with the bench Dipplin doomed (20/80 against the 30
    # snipe): recovering the Hydrapple ex to EVOLVE it (80 -> 330) is worth more
    # than recovering a Grass of mere development, which is what the agent
    # picked even when the turn's KO was already secured.
    obs = _load_fixture_obs("marnie_ns_recovers_hydrapple_saves_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    hydra = next(i for i, o in enumerate(opts)
                 if me["discard"][o["index"]]["id"] == m.Hydrapple_ex)
    energy = next(i for i, o in enumerate(opts)
                   if me["discard"][o["index"]]["id"] == m.Basic_Grass_Energy)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [hydra], (
        f"debe recuperar Hydrapple ex (opt {hydra}) para salvar al Dipplin "
        f"condenado, no la energia redundante (opt {energy}); obtuvo {result}")

def test_marnie_night_stretcher_healthy_dipplin_keeps_energy():
    # Boundary: with the Dipplin healthy (50 > the snipe's 30) there is no rescue to make
    # and the recovery goes back to the normal criterion (development energy).
    import copy as _copy
    obs = _copy.deepcopy(
        _load_fixture_obs("marnie_ns_recovers_hydrapple_saves_dipplin.json"))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in me["bench"]:
        if b["id"] == m.Dipplin:
            b["hp"] = 50
    opts = obs["select"]["option"]
    hydra = next(i for i, o in enumerate(opts)
                 if me["discard"][o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [hydra], (
        f"sin Dipplin condenado no debe dispararse el rescate (opt {hydra})")

def test_op_bench_snipe_damage_table_covers_grimmsnarl():
    # The drip to the bench is now quantified (before there was only a boolean that
    # was read solely in the setup).
    assert m.OP_BENCH_SNIPE_DAMAGE[m.Grimmsnarl_ex] == 30
    assert m.RIPENING_HEAL == 30

def test_marnie_ub_fetch_takes_the_missing_link_not_the_orphan_stage2():
    obs = _load_fixture_obs("marnie_ub_fetch_missing_link_dipplin.json")
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dipplin = [i for i, o in enumerate(opts)
               if deck[o["index"]]["id"] == m.Dipplin]
    hydra = next(i for i, o in enumerate(opts)
                 if deck[o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result and result[0] in dipplin, (
        f"con un Applin en banca y ningun Dipplin, la Ultra Ball debe traer "
        f"el eslabon que falta (Dipplin, opts {dipplin}), no el Hydrapple ex "
        f"huerfano (opt {hydra}); obtuvo {result}")

def test_marnie_ub_cancels_when_the_missing_link_left_the_deck():
    # The same board but with BOTH Dipplin in the discard: the link is no longer
    # in the DECK and the bench is FULL, so the Ultra Ball cannot
    # contribute anything and must not be played.
    obs = _load_fixture_obs("marnie_ub_cancel_link_not_in_deck.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["bench"]) >= 5, "el escenario exige la banca llena"
    ub = next(i for i, o in enumerate(obs["select"]["option"])
              if o.get("type") == int(m.OptionType.PLAY)
              and me["hand"][o["index"]]["id"] == m.Ultra_Ball)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [ub], (
        f"sin Dipplin en el mazo y con la banca llena la Ultra Ball "
        f"(opt {ub}) no aporta nada: debe cancelarse; obtuvo {result}")

def test_evo_link_state_classifies_missing_link_and_orphan():
    # An Applin in play, no Dipplin: the Dipplin is missing and the Hydrapple ex is
    # an orphan. The stage 2 NEVER enters `necesarios` (its own branches already
    # score it and apply the matchup clamps).
    nec, huer = m._evo_link_state({}, {m.Applin: 1})
    assert nec == {m.Dipplin} and m.Hydrapple_ex in huer
    # With the Dipplin already in play, the Hydrapple ex stops being an orphan and is not
    # forced from here.
    nec, huer = m._evo_link_state({}, {m.Applin: 1, m.Dipplin: 1})
    assert m.Hydrapple_ex not in huer and m.Hydrapple_ex not in nec
    # Linea completa (Hydrapple ex en juego): no se fuerza ningun eslabon.
    nec, _ = m._evo_link_state({}, {m.Applin: 1, m.Hydrapple_ex: 1})
    assert m.Dipplin not in nec

def test_alakazam_last_ditch_does_not_fetch_a_copy_already_in_hand():
    obs = _load_fixture_obs("alakazam_ld_fetch_no_duplica_supporter.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    in_hand = {c["id"] for c in me["hand"]}
    xerosic = next(i for i, o in enumerate(opts)
                   if deck[o["index"]]["id"] == m.Xerosic_Machinations)
    assert m.Xerosic_Machinations in in_hand, "el escenario exige Xerosic en mano"
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    traido = deck[opts[result[0]]["index"]]["id"]
    assert traido not in in_hand, (
        f"el Last-Ditch no debe traer una 2a copia de un Supporter que ya esta "
        f"en la mano (Xerosic, opt {xerosic}); trajo {traido}")

def test_alakazam_cancels_meowth_if_the_search_is_redundant():
    # The same board but with ALL the other Supporters out of the deck: the only thing
    # the Last-Ditch could bring is another Xerosic, which is already in hand.
    obs = _load_fixture_obs("alakazam_meowth_cancela_busqueda_redundante.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"con el unico Supporter buscable ya en mano, bajar Meowth ex (opt "
        f"{meowth}) solo regala 2 premios: debe cancelarse; obtuvo {result}")

def test_the_meowth_fetch_prediction_spots_the_duplicate():
    # The helper that decides BEFORE playing the Meowth: with Xerosic as the only
    # Supporter in the deck and a copy in hand, the predicted target is that
    # duplicate (the signal that cancels the play).
    deck = {m.Xerosic_Machinations: {m.ZONE_DECK: 1}}
    target, _ = m._meowth_fetch_prediction(
        {m.Xerosic_Machinations: 1}, {}, 4, True, 12, False,
        False, False, False, False, True, deck)
    assert target == m.Xerosic_Machinations
    # Our first turn keeps the anti-donk exception (it is not capped).
    target_t1, value_t1 = m._meowth_fetch_prediction(
        {m.Xerosic_Machinations: 1}, {}, 4, True, 12, False,
        False, False, False, False, True, deck, first_turn=True)
    assert target_t1 == m.Xerosic_Machinations and value_t1 > 40

def test_meowth_is_not_played_if_the_turn_supporter_is_already_in_hand():
    obs = _load_fixture_obs(
        "alakazam_no_meowth_si_el_supporter_del_turno_esta_en_mano.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    # The scenario requires the Xerosic in hand and NO Lillie's: the fetch would
    # bring one from the deck, but the Xerosic takes the turn's Supporter.
    in_hand = [c["id"] for c in me["hand"]]
    assert m.Xerosic_Machinations in in_hand
    assert m.Lillie_Determination not in in_hand
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"el Supporter del turno (Xerosic, ya en mano) gana a la Lillie's que "
        f"traeria el Last-Ditch: bajar Meowth ex (opt {meowth}) regala 2 "
        f"premios para nada; obtuvo {result}")

def test_supp_play_score_orders_by_the_scale_that_decides():
    # The FETCH scale (`_RULES_MEOWTH_FETCH`) and the PLAY scale
    # contradicted each other: the first put Lillie's (1200) above Xerosic (<=150), the
    # second the other way round. `_supp_play_score` is the one that DECIDES, so the
    # Meowth's prediction has to be made in it.
    from collections import defaultdict
    ctx = _make_boss_ctx(
        op_is_alakazam_deck=True,
        op_hand_count=13,
        hand_counts={m.Xerosic_Machinations: 1, m.Meowth_ex: 1},
    )
    val_xerosic = m._supp_play_score(ctx, m.Xerosic_Machinations)
    # The Lillie's is valued on the hand AFTER the fetch (it enters the slot
    # the Meowth leaves), which is the board on which it would be decided.
    hand_after = defaultdict(int, {m.Xerosic_Machinations: 1,
                                  m.Lillie_Determination: 1})
    ctx_post = m._dc_replace(ctx, hand_counts=hand_after)
    val_lillie = m._supp_play_score(ctx_post, m.Lillie_Determination)
    # (here the Lillie's is even VETOED by `do_not_shuffle_the_last_xerosic`:
    # with the Xerosic in hand, shuffling it away is worse than refreshing.)
    assert val_xerosic > val_lillie, (
        f"Xerosic ({val_xerosic}) debe ganar a la Lillie's buscada "
        f"({val_lillie}) en la escala de JUGADA")
    best_id, best_val = m._best_supporter_in_hand(ctx_post, hand_after)
    assert best_id == m.Xerosic_Machinations and best_val == val_xerosic

def test_supp_play_score_lets_through_the_fetch_that_wins_the_game():
    # A counterweight: if what the fetch would bring is a Boss's Orders that WINS the
    # game, the turn's slot is worth it and the Meowth ex must still be played.
    from collections import defaultdict
    ctx = _make_boss_ctx(
        op_is_alakazam_deck=True,
        op_hand_count=13,
        hand_counts={m.Xerosic_Machinations: 1, m.Meowth_ex: 1},
    )
    hand_after = defaultdict(int, {m.Xerosic_Machinations: 1, m.Boss_Orders: 1})
    ctx_post = m._dc_replace(ctx, hand_counts=hand_after,
                             win_via_boss_gust=True)
    val_boss = m._supp_play_score(ctx_post, m.Boss_Orders)
    best_id, best_val = m._best_supporter_in_hand(ctx_post, hand_after)
    assert best_id == m.Boss_Orders, (
        f"el gusteo GANADOR ({val_boss}) debe llevarse el turno; "
        f"gano {best_id} con {best_val}")

def test_alakazam_the_fetch_follows_the_menu_plan_boss_orders():
    menu = _load_fixture_obs("alakazam_step118_menu_principal.json")
    fetch = _load_fixture_obs("alakazam_ld_fetch_no_duplica_supporter.json")
    me = menu["current"]["players"][menu["current"]["yourIndex"]]
    meowth = next(i for i, o in enumerate(menu["select"]["option"])
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    xerosic = next(i for i, o in enumerate(menu["select"]["option"])
                   if o.get("type") == int(m.OptionType.PLAY)
                   and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    # On THIS board the Meowth ex is NO longer played: `_meowth_fetch_loses_the_turn`
    # (registro_004 step 36) discovers that the fetch's Boss's (a 2-prize gust,
    # 6800) LOSES the turn's only Supporter slot against the
    # Xerosic already in hand (7300) -- which is literally the agent's tuned
    # scale: XEROSIC_SCORE_SOBRE_BOSS (7000) > GUST_2PRIZE (6800),
    # "capping the hand beats any gust that does not WIN the game". Playing the
    # Meowth to search for a card that is not going to be played gave away 2 prizes.
    decision = m.agent(menu)
    assert decision != [meowth], (
        f"con el Xerosic en mano el fetch del Boss's no se juega este turno: "
        f"no debe bajarse el Meowth ex (opt {meowth}); obtuvo {decision}")
    assert xerosic >= 0
    # What THIS test protects still stands: if the Last-Ditch does get resolved
    # the SAME turn, the prompt must bring what the menu had in mind (the
    # Boss's), not revalue it with the Teal Dance already spent.
    # The same turn, a chained prompt: the fetch must bring what motivated the play.
    deck = fetch["select"]["deck"]
    result = m.agent(fetch)
    traido = deck[fetch["select"]["option"][result[0]]["index"]]["id"]
    assert traido == m.Boss_Orders, (
        f"el Last-Ditch debe traer el Boss's Orders que motivo bajar el Meowth "
        f"(gusteo de 2 premios al Fezandipiti ex); trajo {traido}")

def test_teal_dance_availability_is_stable_outside_the_menu():
    # The cache is filled in the MAIN MENU and survives the prompts that do not
    # list abilities; with no previous menu it stays None (conservative).
    menu = _load_fixture_obs("alakazam_step118_menu_principal.json")
    me = menu["current"]["players"][menu["current"]["yourIndex"]]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    m.agent(menu)
    assert m._td_ability_serial == me["active"][0]["serial"], (
        "tras el menu principal queda cacheado el serial del activo con "
        "habilidad disponible")

def test_cubchoo_dead_turn_plays_meowth_instead_of_ending():
    obs = _load_fixture_obs("cubchoo_turno_muerto_baja_meowth.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    fin = next(i for i, o in enumerate(opts)
               if o.get("type") == int(m.OptionType.END))
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [meowth], (
        f"sin ningun atacante ni jugada posible, bajar Meowth ex (opt {meowth}) "
        f"para que Last-Ditch traiga Lillie's es mejor que terminar el turno "
        f"(opt {fin}); obtuvo {result}")

def test_cubchoo_with_a_real_play_still_vetoes_the_second_meowth():
    # Boundary: the rescue ONLY overrides the dead turn. If there is a real play
    # (here an attachable Grass), the anti-Cubchoo veto of the 2nd Meowth ex rules.
    import copy as _copy
    obs = _copy.deepcopy(_load_fixture_obs("cubchoo_turno_muerto_baja_meowth.json"))
    obs["current"]["energyAttached"] = False
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    energy = next(i for i, c in enumerate(me["hand"])
                   if c["id"] == m.Basic_Grass_Energy)
    obs["select"]["option"].insert(0, {
        "area": 2, "inPlayArea": 5, "inPlayIndex": 0,
        "index": energy, "type": int(m.OptionType.ATTACH)})
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"con una jugada real disponible el turno no esta muerto: el veto "
        f"anti-Cubchoo del 2o Meowth ex (opt {meowth}) sigue mandando; "
        f"obtuvo {result}")

def _idx_evolve(obs):
    return [i for i, o in enumerate(obs["select"]["option"])
            if o.get("type") == int(m.OptionType.EVOLVE)]

def test_cubchoo_does_not_evolve_hydrapple_without_energy():
    obs = _load_fixture_obs("cubchoo_no_evolucionar_hydrapple_sin_energia.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["active"][0]["energies"]) == 0, "el escenario exige 0 energias"
    assert m.RETREAT_COST[m.Hydrapple_ex] >= 3
    evo = _idx_evolve(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] not in evo, (
        f"vs Cubchoo no se evoluciona a Hydrapple ex (retirada 3) sin energia "
        f"para atacar: quedaria clavado en el activo; obtuvo {result} (evo {evo})")

def test_cubchoo_does_evolve_hydrapple_with_energy():
    # Boundary: with enough energy for Syrup Storm the evolution IS worth it
    # (it attacks, and the 330 HP wall makes up for the retreat cost).
    obs = _load_fixture_obs("cubchoo_si_evoluciona_hydrapple_con_energia.json")
    evo = _idx_evolve(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in evo, (
        f"con energia para atacar la evolucion a Hydrapple ex sigue siendo la "
        f"jugada (opts {evo}); obtuvo {result}")

def test_the_slow_body_rule_is_bounded_to_the_cubchoo_matchup():
    # Boundary: the same board against a generic rival does NOT switch the rule on --
    # there it recharges and retreats normally and the wall makes up for it.
    obs = _load_fixture_obs("generico_si_evoluciona_hydrapple_sin_energia.json")
    evo = _idx_evolve(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in evo, (
        f"fuera del matchup Cubchoo la evolucion a Hydrapple ex se mantiene "
        f"(opts {evo}); obtuvo {result}")

def test_cubchoo_teal_dance_enables_the_retreat_towards_the_ko():
    obs = _load_fixture_obs("cubchoo_teal_dance_habilita_retirada_ko.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["active"][0]["energies"]) == 0
    td = [i for i, o in enumerate(obs["select"]["option"])
          if o.get("type") == int(m.OptionType.ABILITY)
          and o.get("area") == int(m.AreaType.ACTIVE)]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in td, (
        f"con el activo a 0 energias y un Ogerpon letal en banca, Teal Dance en "
        f"el ACTIVO (opts {td}) habilita la retirada y ademas roba; "
        f"obtuvo {result}")

def test_cubchoo_after_teal_dance_it_does_retreat():
    obs = _load_fixture_obs("cubchoo_tras_teal_dance_retira_al_ogerpon.json")
    ret = [i for i, o in enumerate(obs["select"]["option"])
           if o.get("type") == int(m.OptionType.RETREAT)]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in ret, (
        f"el veto anti-Cubchoo de retirada cede cuando la retirada NOQUEA y el "
        f"activo no tiene excedente de energia que perder; obtuvo {result}")

def test_cubchoo_promotes_the_ogerpon_not_the_nailed_down_hydrapple():
    obs = _load_fixture_obs("cubchoo_promueve_ogerpon_letal_tras_retirar.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    oger = [i for i, o in enumerate(opts)
            if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    hydra = [i for i, o in enumerate(opts)
             if me["bench"][o["index"]]["id"] == m.Hydrapple_ex]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in oger, (
        f"vs Cubchoo se promueve el Ogerpon ex (retirada 1, 4 energias) y no el "
        f"Hydrapple ex (retirada 3, 2 energias -> clavado); oger={oger} "
        f"hydra={hydra}, obtuvo {result}")

def test_cubchoo_with_energy_already_invested_it_still_passes():
    # The BOUNDARY between the user's two rules: here the active has THREE
    # physical Grass. Retreating would destroy investment already put on the board, so
    # we PASS even though there is also a KO behind (registro_004 p47).
    obs = _load_fixture_obs("cubchoo_step47_no_energy_wasting_retreat.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert m._physical_energy(len(me["active"][0]["energies"])) > \
        m.RETREAT_COST[me["active"][0]["id"]], "el escenario exige excedente"
    ret = [i for i, o in enumerate(obs["select"]["option"])
           if o.get("type") == int(m.OptionType.RETREAT)]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] not in ret, (
        f"con excedente de energia invertida el veto anti-Cubchoo se mantiene; "
        f"obtuvo {result}")

def _promo_elegido(obs):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    r = m.agent(obs)
    return me["bench"][obs["select"]["option"][r[0]]["index"]]

def test_archaludon_promotes_the_body_that_survives_the_attack():
    obs = _load_fixture_obs("archaludon_step64_promueve_el_que_aguanta.json")
    o = m.to_observation_class(obs)
    op_act = o.current.players[1].active[0]
    vivos = [b for b in o.current.players[0].bench
             if m._op_active_attack_damage_to(op_act, b) < b.hp]
    assert [b.id for b in vivos] == [m.Hydrapple_ex], (
        "el escenario exige que solo el Hydrapple ex aguante los 220")
    picked = _promo_elegido(obs)
    assert picked["id"] == m.Hydrapple_ex, (
        f"sube el unico cuerpo que aguanta (330 PV), no el Ogerpon ex cargado "
        f"que muere a 220 sin noquear; obtuvo {picked['id']}")

def test_with_no_survivor_it_promotes_the_one_worth_fewer_prizes():
    # The REAL scenario (lucario_step99): Mega Lucario hits for 270 and on the bench
    # nobody survives -- Meganium 130, Ogerpon ex 210, Dipplin 80. Then criterion
    # 2 rules: give away the FEWEST prizes. Dipplin/Meganium are worth 1, the
    # Ogerpon ex is worth 2. (Meganium is left out by its own promotion veto:
    # it is the Wild Growth engine that doubles all our energy.)
    obs = _load_lucario_step99_obs()
    o = m.to_observation_class(obs)
    op_act = o.current.players[1].active[0]
    assert not [b for b in o.current.players[0].bench
                if m._op_active_attack_damage_to(op_act, b) < b.hp], \
        "el escenario exige que no sobreviva nadie"
    chosen = _promote_choice_id(obs)
    assert chosen != m.Teal_Mask_Ogerpon_ex, (
        f"sin superviviente se entrega el minimo de premios (1), no el ex de 2; "
        f"promovio id {chosen}")

def test_the_survivor_does_not_override_the_one_that_knocks_out():
    # THE PRIORITY OF THE ONE THAT KNOCKS OUT (user): the charged attacker is brought up instead of the
    # tank ONLY when that attacker knocks out the rival. Taking the prize rules
    # even if it dies afterwards. With the Archaludon at 60 HP, the charged Ogerpon
    # (Myriad 300) knocks it out; the Hydrapple ex, with 0 energies, does not reach its
    # attack even though it survives the blow. Implemented as a GUARANTEE
    # (`PROMO_KO_BONUS`, above the maximum score of the other branches) and not
    # as a mere exemption from the penalty.
    import copy as _c
    obs = _c.deepcopy(_load_fixture_obs(
        "archaludon_step64_promueve_el_que_aguanta.json"))
    obs["current"]["players"][1]["active"][0]["hp"] = 60
    picked = _promo_elegido(obs)
    assert picked["id"] == m.Teal_Mask_Ogerpon_ex, (
        f"el cuerpo que NOQUEA se promueve aunque muera despues; obtuvo "
        f"{picked['id']} ({m.card_table[picked['id']].name})")

_IRON_THORNS_TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iron_thorns_t16_baja_tapu_no_end.json")

def test_iron_thorns_t16_plays_tapu_instead_of_ending():
    with open(_IRON_THORNS_TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Tapu_Bulu in play_map.values()
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result == [tapu_opt], (
        f"vs Iron Thorns ex activo, con Tapu Bulu en mano el turno no se "
        f"cierra con END: se baja el atacante sin habilidad (opt {tapu_opt}); "
        f"obtuvo {result} (map={play_map})")

_IRON_THORNS_2TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iron_thorns_t2_baja_segundo_tapu.json")

def test_iron_thorns_t2_plays_a_second_tapu_as_backup():
    with open(_IRON_THORNS_2TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Tapu_Bulu in play_map.values()
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result == [tapu_opt], (
        f"vs Iron Thorns ex activo con Tapu Bulu ACTIVO nuestro, el 2o Tapu "
        f"de la mano se baja como respaldo del unico atacante (opt "
        f"{tapu_opt}); obtuvo {result} (map={play_map})")

def test_generic_a_second_tapu_stays_vetoed_without_a_lock():
    """An inverse control: with no wall/lock across the table the copy veto is kept."""
    with open(_IRON_THORNS_2TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    # The rival stops being an Iron Thorns ex: a neutral active with no lock or
    # immunities (Applin) -> no matchup flag fires.
    op_index = 1 - obs["current"]["yourIndex"]
    obs["current"]["players"][op_index]["active"][0]["id"] = m.Applin

    play_map = _resolve_play_options(obs)
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result != [tapu_opt], (
        f"sin lock enfrente, el 2o Tapu Bulu sigue vetado (copia "
        f"redundante); obtuvo {result} (map={play_map})")

_IRON_THORNS_UNLOCK_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iron_thorns_t10_boss_deslockea.json")

def test_iron_thorns_t10_boss_deslockea_habilidades():
    with open(_IRON_THORNS_UNLOCK_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Boss_Orders in play_map.values()
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    result = m.agent(obs)
    assert result == [boss_opt], (
        f"con Iron Thorns ex activo rival y no-lockers en su banca, Boss's "
        f"se juega para DES-LOCKEAR el motor (opt {boss_opt}); obtuvo "
        f"{result} (map={play_map})")

def test_boss_does_not_unlock_if_the_opponent_bench_is_all_iron_thorns():
    """Inverse control A: with no non-locker to bring up, the gust switches nothing off."""
    with open(_IRON_THORNS_UNLOCK_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    op_index = 1 - obs["current"]["yourIndex"]
    for b in obs["current"]["players"][op_index]["bench"]:
        if b is not None:
            b["id"] = m.Iron_Thorns_ex

    play_map = _resolve_play_options(obs)
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    result = m.agent(obs)
    assert result != [boss_opt], (
        f"con la banca rival TODA Iron Thorns el gusteo mantiene el lock: "
        f"Boss's sigue vetado; obtuvo {result} (map={play_map})")

def test_boss_does_not_unlock_with_no_engine_to_wake():
    """Inverse control B: with no Ogerpon/Hydrapple in play and no Meowth in hand,
    the unlocking buys nothing TODAY and the Boss's is kept."""
    with open(_IRON_THORNS_UNLOCK_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    cur = obs["current"]
    yo = cur["players"][cur["yourIndex"]]
    for b in yo["bench"]:
        if b is not None and b["id"] == m.Teal_Mask_Ogerpon_ex:
            b["id"] = m.Tapu_Bulu
    for c in yo["hand"]:
        if c["id"] == m.Meowth_ex:
            c["id"] = m.Xerosic_Machinations

    play_map = _resolve_play_options(obs)
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    result = m.agent(obs)
    assert result != [boss_opt], (
        f"sin habilidades que despertar, Boss's no se quema en el "
        f"des-lockeo; obtuvo {result} (map={play_map})")

def test_gust_estorbo_forbid_iron_thorns():
    """NUISANCE mode never brings up an Iron Thorns ex: it creates/keeps the lock
    on our own engine (the rule nuisance_creates_the_iron_thorns_lock)."""
    def _ctx(card_id):
        return m._CtxGustObjetivo(
            card_id=card_id, energy=0, rc0=2, rc1=2, stall_diff=2,
            is_ex=True, is_exmega=True, is_megaex=False, prizes=2,
            wins_now=False, is_stage1=False, is_stage2=False,
            tiene_tool=False, can_ko=False, tier_ko=0,
            plan_target_match=False, regust_energized=False,
            line_rank=0, line_can_ko=False, op_alakazam=False,
            op_latias=False, op_dragapult_line=False,
            op_typhlosion_line=False)

    s_iron, _ = m._resolve_rules(
        m._RULES_GUST_NUISANCE, m._ADJUST_GUST_NUISANCE,
        _ctx(m.Iron_Thorns_ex), default=-200)
    assert s_iron == m.SCORE_FORBID, (
        f"estorbo con Iron Thorns ex debe ser FORBID; obtuvo {s_iron}")

    # Control: another ex with the same net stuckness keeps its nuisance value.
    s_otro, _ = m._resolve_rules(
        m._RULES_GUST_NUISANCE, m._ADJUST_GUST_NUISANCE,
        _ctx(m.Alakazam_ex), default=-200)
    assert s_otro > 0, (
        f"un ex no-locker con traba neta sigue siendo estorbo valido; "
        f"obtuvo {s_otro}")

_CORNERSTONE_TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cornerstone_t2_baja_tapu_no_end.json")

def test_cornerstone_t2_plays_tapu_instead_of_ending():
    with open(_CORNERSTONE_TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Tapu_Bulu in play_map.values()
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result == [tapu_opt], (
        f"vs Cornerstone, con Tapu Bulu en mano el turno 2 no se cierra con "
        f"END: se baja el unico atacante del matchup (opt {tapu_opt}); "
        f"obtuvo {result} (map={play_map})")

_COMFEY_BCS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "comfey_t8_juega_bug_catching_set.json")

def test_comfey_t8_plays_bug_catching_set():
    with open(_COMFEY_BCS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Bug_Catching_Set in play_map.values()
    bcs_opts = [i for i, cid in play_map.items() if cid == m.Bug_Catching_Set]

    result = m.agent(obs)
    assert result[0] in bcs_opts, (
        f"vs Comfey con 0 Plantas en mano, Bug Catching Set (surtidor de "
        f"energia) debe jugarse (opts {bcs_opts}); obtuvo {result} "
        f"(map={play_map})")

_STERIL_UB_FIXTURE = (
    ROOT / "tests" / "fixtures" / "crustle_t2_red_esteril_juega_ub.json")

def test_the_sterile_net_revives_the_ultra_ball_with_a_bench():
    with open(_STERIL_UB_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    ub_opts = [i for i, cid in play_map.items() if cid == _ULTRA_BALL]
    assert ub_opts

    result = m.agent(obs)
    assert result[0] in ub_opts, (
        f"turno esteril con UB vetada y objetivo util en mazo: la red debe "
        f"jugar la Ultra Ball (opts {ub_opts}); obtuvo {result} (map={play_map})")

_STARMIE_NS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "starmie_step75_ns_recupera_energia.json")

_STARMIE_FEZ_FIXTURE = (
    ROOT / "tests" / "fixtures" / "starmie_step74_baja_fez_flip_script.json")

def test_starmie_step75_the_ns_recovers_energy_not_tapu():
    with open(_STARMIE_NS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    elegida = me["discard"][opt["index"]]["id"]
    assert elegida == m.Basic_Grass_Energy, (
        f"NS debe recuperar la Planta (habilita Syrup Storm este turno), no "
        f"{m.card_table[elegida].name}")

def test_starmie_step74_plays_fez_with_flip_the_script_alive():
    with open(_STARMIE_FEZ_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Fezandipiti_ex, (
        f"con KO sufrido el turno anterior, bajar Fezandipiti ex (Flip the "
        f"Script roba 3) supera al resto; jugo {m.card_table[elegida].name}")

_ROCKET_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "rocket_t4_lillie_sobre_boss_condenado.json")

def test_rocket_t4_lillie_over_boss_with_a_doomed_active():
    with open(_ROCKET_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Lillie_Determination, (
        f"con el activo condenado y sin relevo en banca, el gusteo de +1 "
        f"premio cede a Lillie's (cavar el plan futuro); jugo "
        f"{m.card_table[elegida].name}")

_ALK_MEOWTH_ENGINE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_step85_meowth_engine_sobre_boss.json")

def test_alakazam_step85_meowth_engine_sobre_boss():
    with open(_ALK_MEOWTH_ENGINE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Meowth_ex, (
        f"con la mano rival gorda y Xerosic en el mazo, bajar Meowth ex "
        f"(Last-Ditch -> Xerosic) supera el gusteo de Boss's; jugo "
        f"{m.card_table[elegida].name}")

_MARNIE_DIPPLIN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step43_dipplin_max_una_energia.json")

def test_marnie_step43_no_sobrecargar_dipplin_recien_evolucionado():
    with open(_MARNIE_DIPPLIN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    # The 2nd energy to the Dipplin (an ATTACH to bench1) is vetoed; the play
    # chosen is Teal Dance (ABILITY, type 10) from either of the Ogerpon.
    assert opt.get("type") != 8 or opt.get("inPlayIndex") != 1, (
        f"no se debe cargar la 2a energia al Dipplin recien evolucionado: {opt}")
    assert opt.get("type") == 10, (
        f"la linea correcta es Teal Dance (energia al Ogerpon + robo); {opt}")
