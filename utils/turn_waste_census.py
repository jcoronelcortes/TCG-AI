"""What does OUR turn leave on the table? A per-turn census, split by plan mode.

WHY IT EXISTS. The project's method says to measure whether a rule would change
any decision BEFORE measuring winrate, because the self-play gate is saturated
and cannot arbitrate a rule that fires rarely. This tool answers the question one
step earlier: is there anything to write a rule ABOUT? It counts, per turn, the
resources that were LEGALLY PLAYABLE in the last main menu and were declined --
the turn's energy attachment, the Supporter slot, an evolution, a body for the
bench, an ability.

Only "offered in the menu" counts. A Supporter that is not in hand is not waste,
and neither is an Ultra Ball with nothing to dig for: what this measures is the
agent looking at a legal play and saying no.

WHAT IT SAID THE FIRST TIME (ago 2026, 250 self-play games, 2382 of our turns
outside WIN_NOW -- where leaving things unspent is correct because the game ends):

    turn's energy attachment unspent      1.8% of DEVELOP turns
    Supporter offered, slot unspent       6.8% DEVELOP / 10.9% RACE
    ... of those, on a turn that ENDS without attacking:  1 in 1017
    body offered and not benched         28.9% DEVELOP -- but 90% of them
                                          with a bench of 2-4 already

Read together that is a NEGATIVE result, and a useful one: the agent is not
leaving resources unspent. The 122 turns where a positively-scored Boss's Orders
"lost the slot" all ended by ATTACKING, and a gust before an attack is not free --
it changes which body is in front. The declined benchings are the deliberate
"do not over-extend" rules doing their job.

The consequence for whoever reads this next: what is left to gain is NOT in what
the agent fails to spend. It is in WHICH of several legal, scored plays it picks,
and that is what the golden corpus and the game records arbitrate -- not a volume
census. Three rules were written against the waste axis before this was measured;
all three came back neutral or negative.

Usage:
    python utils/turn_waste_census.py                # 250 games
    python utils/turn_waste_census.py --games 500
    python utils/turn_waste_census.py --detail       # plus the two drill-downs
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402
from cg import game  # noqa: E402
from ptcg.turn.game_plan import plan_of  # noqa: E402

# Option types of the simulator, by the names the report uses.
_PLAY, _ATTACH, _EVOLVE, _ABILITY, _ATTACK, _END = 7, 8, 9, 10, 13, 14


def _supporter_ids(m):
    return {m.Lillie_Determination, m.Boss_Orders, m.Lanas_Aid, m.Dawn,
            m.Xerosic_Machinations, m.Unfair_Stamp}


class _Census:
    """Accumulates one row per turn, keyed by the plan's mode.

    WIN_NOW is reported apart and never counted as waste: on a turn that ends the
    game, an unspent Supporter is not a loss, it is the point.
    """

    def __init__(self, m):
        self.m = m
        self.supporters = _supporter_ids(m)
        self.names = {v: k for k, v in vars(m).items()
                      if isinstance(v, int) and k.endswith(("_ex", "Orders",
                                                            "Determination"))}
        self.counts = Counter()
        self.detail = Counter()
        self.turn = {}

    # -- per-observation ------------------------------------------------
    def observe(self, obs, choice):
        if (obs.get("select") or {}).get("context") != 0:
            return
        cur = obs["current"]
        if self.turn.get("turn") != cur["turn"]:
            self.close()
            self.turn = {"turn": cur["turn"]}
        me = cur["players"][cur["yourIndex"]]
        hand = [c["id"] for c in (me.get("hand") or [])]

        types, supp_live, bodies = set(), {}, []
        attack_offered = False
        for opt in obs["select"]["option"]:
            t = opt.get("type")
            types.add(t)
            if t == _ATTACK:
                attack_offered = True
            if t != _PLAY or opt.get("index") is None or opt["index"] >= len(hand):
                continue
            card_id = hand[opt["index"]]
            if card_id in self.supporters and not cur["supporterPlayed"]:
                supp_live[card_id] = self.m._last_supp_scores.get(card_id)
            data = self.m.card_table.get(card_id)
            if data is not None and data.cardType == self.m.CardType.POKEMON:
                bodies.append(card_id)

        chosen = obs["select"]["option"][choice[0]] if choice else {}
        self.turn.update(
            mode=plan_of(self.m.AGENT_STATE).mode,
            types=types, supp=supp_live, bodies=bodies,
            attack_offered=attack_offered,
            bench=sum(1 for p in (me.get("bench") or []) if p),
            energy_attached=cur["energyAttached"],
            supporter_played=cur["supporterPlayed"],
            ended_end=(chosen.get("type") == _END),
        )

    # -- per-turn -------------------------------------------------------
    def close(self):
        t = self.turn
        if not t or "mode" not in t:
            return
        mode = t["mode"]
        self.counts[(mode, "turnos")] += 1
        if _ATTACH in t["types"] and not t["energy_attached"]:
            self.counts[(mode, "adjunte del turno sin gastar")] += 1
        if t["supp"] and not t["supporter_played"]:
            self.counts[(mode, "Supporter ofrecido, hueco perdido")] += 1
            live = [s for s in t["supp"].values() if s is not None and s > 0]
            if live and t["ended_end"]:
                # The unambiguous case: no attack whose target a gust could
                # spoil, and the Supporter still stayed in hand.
                self.counts[(mode, "  ...y el turno acaba SIN atacar")] += 1
        if _EVOLVE in t["types"]:
            self.counts[(mode, "evolucion ofrecida sin hacer")] += 1
        if _ABILITY in t["types"]:
            self.counts[(mode, "habilidad ofrecida sin usar")] += 1
        if t["bodies"]:
            self.counts[(mode, "cuerpo ofrecido sin bajar")] += 1
            self.detail[("banca", min(4, t["bench"]))] += 1
            if t["bench"] <= 1:
                self.counts[(mode, "  ...con la banca FINA (<=1)")] += 1
        if t["ended_end"]:
            self.counts[(mode, "el turno acaba en END")] += 1
        self.turn = {}

    # -- report ---------------------------------------------------------
    def report(self, detail=False):
        for mode in ("DEVELOP", "RACE", "DENY", "WIN_NOW"):
            total = self.counts[(mode, "turnos")]
            if not total:
                continue
            nota = "  (aqui NO gastar es correcto: la partida acaba)" if mode == "WIN_NOW" else ""
            print(f"\n=== {mode}: {total} turnos ==={nota}")
            for (m_, label), n in sorted(self.counts.items()):
                if m_ != mode or label == "turnos":
                    continue
                print(f"  {label:38s} {n:5d}  ({100 * n / total:5.1f}%)")
        if detail:
            tot = sum(v for (k, _), v in self.detail.items() if k == "banca")
            print(f"\n=== al declinar bajar un cuerpo, banca que se conserva ===")
            for size in range(5):
                n = self.detail[("banca", size)]
                if tot:
                    etiqueta = f"{size}" if size < 4 else "4+"
                    print(f"  banca {etiqueta:3s} {n:5d}  ({100 * n / tot:5.1f}%)")


def run(games):
    m = sp.load_agent(str(_ROOT / "main.py"), "censo")
    m._last_supp_scores = {}
    original = m._supp_play_score

    def spy(ctx, sid):
        value = original(ctx, sid)
        m._last_supp_scores[sid] = value
        return value
    m._supp_play_score = spy

    deck = sp.read_deck()
    census = _Census(m)
    for _ in range(games):
        sp._reset_si_aplica(m)
        census.turn = {}
        obs, _sd = game.battle_start(list(deck), list(deck))
        steps = 0
        while obs and obs["current"]["result"] == -1 and steps < 3000:
            m._last_supp_scores = {}
            choice = m.agent(obs)
            census.observe(obs, choice)
            obs = game.battle_select(choice)
            steps += 1
        census.close()
    return census


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=250)
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args(argv)
    run(args.games).report(detail=args.detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
