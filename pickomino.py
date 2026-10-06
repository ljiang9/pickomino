"""Pickomino (Heckmeck) 骰子游戏：8 颗骰子，留骰凑点数，抢烤架上的虫子牌。"""
import argparse
import copy
import random
import sys

WORM = 6  # 虫面，点数按 5 计算

# 牌：点数 -> 虫子数（21-36）
TILE_WORMS = {21: 1, 22: 1, 23: 1, 24: 1,
              25: 2, 26: 2, 27: 2, 28: 2,
              29: 3, 30: 3, 31: 3, 32: 3,
              33: 4, 34: 4, 35: 4, 36: 4}
MIN_TILE, MAX_TILE = 21, 36


class IllegalMove(Exception):
    pass


def face_value(face):
    """骰面点数：虫面按 5 算。"""
    return 5 if face == WORM else face


def face_name(face):
    return "虫" if face == WORM else str(face)


class Turn:
    """一回合的留骰状态。"""

    def __init__(self):
        self.kept = {}      # face -> 颗数
        self.dice_left = 8

    def total(self):
        return sum(face_value(f) * n for f, n in self.kept.items())

    def has_worm(self):
        return self.kept.get(WORM, 0) > 0

    def roll(self, rng):
        return [rng.randint(1, 6) for _ in range(self.dice_left)]

    def legal_faces(self, rolled):
        """可留的骰面：掷出来了且之前没留过。"""
        return sorted({f for f in rolled if f not in self.kept})

    def keep(self, rolled, face):
        if face not in rolled:
            raise IllegalMove(f"这一掷没有{face_name(face)}")
        if face in self.kept:
            raise IllegalMove(f"{face_name(face)}已经留过了")
        n = rolled.count(face)
        self.kept[face] = n
        self.dice_left -= n


class Pickomino:
    def __init__(self, n_players=2, seed=None):
        self.rng = random.Random(seed)
        self.n_players = n_players
        self.center = list(range(MIN_TILE, MAX_TILE + 1))  # 烤架上的牌
        self.stacks = [[] for _ in range(n_players)]       # 每人拿到的牌，末尾=最上面
        self.current = 0

    # ---- 结算 ----
    def take_tile(self, player, total):
        """按点数拿牌：精确牌优先（可偷对手最上面一张），否则拿烤架上不大于点数的最大牌。"""
        if total < MIN_TILE:
            return None
        # 偷牌：对手最上面一张正好等于点数
        for opp in range(self.n_players):
            if opp != player and self.stacks[opp] and self.stacks[opp][-1] == total:
                return ("steal", opp, self.stacks[opp].pop())
        avail = [t for t in self.center if t <= total]
        if not avail:
            return None
        tile = max(avail)
        self.center.remove(tile)
        return ("center", None, tile)

    def bust(self, player):
        """爆掉：最上面一张牌翻面移出游戏（简化：直接移出）。"""
        if self.stacks[player]:
            return self.stacks[player].pop()
        return None

    def worms(self, player):
        return sum(TILE_WORMS[t] for t in self.stacks[player])

    def game_over(self):
        return not self.center

    def winner(self):
        scores = [self.worms(p) for p in range(self.n_players)]
        best = max(scores)
        return [p for p, s in enumerate(scores) if s == best], scores

    # ---- AI ----
    def ai_choose_face(self, turn, rolled):
        legal = turn.legal_faces(rolled)
        # 优先拿虫（拿牌必需），否则取 期望点数 最高的面
        def key(f):
            return (0 if f == WORM else 1, -(face_value(f) * rolled.count(f)))
        return min(legal, key=key)

    def ai_should_stop(self, turn):
        if not turn.has_worm():
            return False  # 没虫不能停，只能继续赌
        if turn.dice_left == 0:
            return True
        total = turn.total()
        if total < MIN_TILE:
            return False
        # 爆掉概率近似：下一掷所有面都已留过
        bust_p = (len(turn.kept) / 6.0) ** turn.dice_left
        # 点数越高越不值得冒险
        threshold = 0.45 if total < 30 else 0.25
        return bust_p > threshold

    def play_turn(self, player, verbose=False):
        turn = Turn()
        while True:
            rolled = turn.roll(self.rng)
            legal = turn.legal_faces(rolled)
            if not legal:
                lost = self.bust(player)
                if verbose:
                    print(f"  玩家{player} 爆掉了！" +
                          (f"失去牌 {lost}" if lost else "（没有牌可失去）"))
                return "bust"
            face = self.ai_choose_face(turn, rolled)
            turn.keep(rolled, face)
            if verbose:
                kept_s = " ".join(f"{face_name(f)}x{n}" for f, n in sorted(turn.kept.items()))
                print(f"  掷出 {[face_name(d) for d in rolled]}，留下{face_name(face)}"
                      f"；已留 [{kept_s}]，点数 {turn.total()}，剩 {turn.dice_left} 颗")
            if turn.dice_left == 0 or self.ai_should_stop(turn):
                break
        total = turn.total()
        if not turn.has_worm():
            lost = self.bust(player)  # 无虫停手等于爆掉
            if verbose:
                print(f"  点数 {total} 但没有虫子，爆掉了！" +
                      (f"失去牌 {lost}" if lost else ""))
            return "bust"
        got = self.take_tile(player, total)
        if got is None:
            lost = self.bust(player)
            if verbose:
                print(f"  点数 {total} 拿不到牌，爆掉了！" +
                      (f"失去牌 {lost}" if lost else ""))
            return "bust"
        kind, opp, tile = got
        self.stacks[player].append(tile)
        if verbose:
            if kind == "steal":
                print(f"  点数 {total}，从玩家{opp}手里偷走 {tile}（{TILE_WORMS[tile]}虫）！")
            else:
                print(f"  点数 {total}，拿走烤架上的 {tile}（{TILE_WORMS[tile]}虫）")
        return "take"

    def play_game(self, verbose=False):
        rounds = 0
        while not self.game_over():
            p = self.current
            if verbose:
                print(f"第{rounds + 1}轮 玩家{p} 行动，烤架：{self.center}")
            self.play_turn(p, verbose=verbose)
            self.current = (self.current + 1) % self.n_players
            rounds += 1
        winners, scores = self.winner()
        if verbose:
            for p in range(self.n_players):
                print(f"玩家{p}：{self.stacks[p]}，共 {scores[p]} 条虫")
            print(f"获胜：{winners}")
        return winners, scores


def cmd_auto(args):
    w0 = w1 = draws = 0
    total_rounds = 0
    for g in range(args.games):
        game = Pickomino(n_players=args.players, seed=args.seed + g if args.seed is not None else None)
        winners, scores = game.play_game(verbose=args.verbose and g == 0)
        total_rounds += sum(len(s) for s in game.stacks)
        if len(winners) == 1:
            if winners[0] == 0:
                w0 += 1
            elif winners[0] == 1:
                w1 += 1
        else:
            draws += 1
    print(f"共 {args.games} 局：玩家0胜 {w0}，玩家1胜 {w1}，平局 {draws}")


def cmd_play(args):
    game = Pickomino(n_players=2, seed=args.seed)
    if not sys.stdin.isatty():
        print("交互模式需要终端运行。")
        sys.exit(2)
    print("Pickomino：你是玩家0，对手是 AI。输入留骰面（1-5 或 虫/w），s=停手，q=退出")
    turn = Turn()
    rolled = None
    while not game.game_over():
        p = game.current
        if p == 0:
            if rolled is None:
                rolled = turn.roll(game.rng)
                print(f"\n你掷出：{[face_name(d) for d in rolled]}")
            legal = turn.legal_faces(rolled)
            if not legal:
                lost = game.bust(0)
                print("爆掉了！" + (f"失去牌 {lost}" if lost else ""))
                turn, rolled = Turn(), None
                game.current = 1
                continue
            kept_s = " ".join(f"{face_name(f)}x{n}" for f, n in sorted(turn.kept.items()))
            print(f"已留 [{kept_s}] 点数 {turn.total()} 剩 {turn.dice_left} 颗；可留 { [face_name(f) for f in legal]}")
            s = input("留哪面？(s=停手) ").strip()
            if s == "q":
                return
            if s == "s":
                if not turn.has_worm():
                    print("没有虫子不能停，继续！")
                    continue
                total = turn.total()
                got = game.take_tile(0, total)
                if got is None:
                    lost = game.bust(0)
                    print(f"点数 {total} 拿不到牌，爆掉了！" + (f"失去牌 {lost}" if lost else ""))
                else:
                    kind, opp, tile = got
                    game.stacks[0].append(tile)
                    print(f"点数 {total}，拿下 {tile}（{TILE_WORMS[tile]}虫）" +
                          ("（偷的！）" if kind == "steal" else ""))
                turn, rolled = Turn(), None
                game.current = 1
                continue
            face = WORM if s in ("虫", "w", "W") else int(s)
            try:
                turn.keep(rolled, face)
            except (IllegalMove, ValueError) as e:
                print(f"非法：{e}")
                continue
            rolled = None
        else:
            print(f"\nAI 行动，烤架：{game.center}")
            game.play_turn(1, verbose=True)
            turn, rolled = Turn(), None
            game.current = 0
    winners, scores = game.winner()
    print(f"\n结束！你的牌 {game.stacks[0]}（{scores[0]}虫），AI {game.stacks[1]}（{scores[1]}虫），获胜：{winners}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pickomino 骰子虫子牌")
    ap.add_argument("--seed", type=int, default=None)
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("auto", help="AI 自动对局")
    a.add_argument("--games", type=int, default=10)
    a.add_argument("--players", type=int, default=2, choices=[2])
    a.add_argument("--verbose", action="store_true")
    a.add_argument("--seed", type=int, default=None)
    sub.add_parser("play", help="人机对战")
    args = ap.parse_args(argv)
    if args.cmd == "auto":
        cmd_auto(args)
    else:
        cmd_play(args)


if __name__ == "__main__":
    main()
