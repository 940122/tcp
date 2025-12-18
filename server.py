import socket
import threading
import random

HOST = "0.0.0.0"
PORT = 5555

players = []
dealer = None
lock = threading.Lock()
GAME_RUNNING = False

CARDS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
VALUES = {
    "A":11,"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,
    "8":8,"9":9,"10":10,"J":10,"Q":10,"K":10
}

# ======================
# 玩家類別
# ======================
class Player:
    def __init__(self, conn, name, dealer=False):
        self.conn = conn
        self.name = name
        self.is_dealer = dealer
        self.coins = 500 if dealer else 100
        self.hand = []
        self.bet = 0
        self.alive = True
        self.spectator = False


# ======================
# 工具函式
# ======================
def draw_card():
    return random.choice(CARDS)

def calc(hand):
    total = sum(VALUES[c] for c in hand)
    aces = hand.count("A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def broadcast(msg):
    offline = []
    for idx, p in enumerate(players):
        try:
            p.conn.sendall((msg + "\n").encode())
        except:
            if p.alive:
                p.alive = False
                p.spectator = True
                offline.append((idx, p.name))

    for idx, name in offline:
        for p in players:
            if p.alive:
                try:
                    p.conn.sendall(
                        f"玩家{idx}號 {name} 已離開房間\n".encode()
                    )
                except:
                    pass

def recv_timeout(conn, prompt, timeout=10):
    try:
        conn.sendall((prompt + "\n").encode())
        conn.settimeout(timeout)
        data = conn.recv(1024)
        if not data:
            return None
        return data.decode().strip()
    except socket.timeout:
        return "TIMEOUT"
    except:
        return "DISCONNECT"

def player_list():
    result = []
    for i, p in enumerate(players):
        role = "莊家" if p.is_dealer else f"玩家{i}"
        status = "離線" if not p.alive else ("觀戰" if p.spectator else "進行中")
        result.append(f"{role} {p.name} - 金幣:{p.coins} 狀態:{status}")
    return "\n".join(result)


# ======================
# 單回合遊戲
# ======================
def play_one_round():
    global dealer

    actives = [
        p for p in players
        if not p.is_dealer and p.alive and not p.spectator
    ]

    if not actives:
        broadcast("玩家方已無可下注玩家，遊戲結束！")
        return False

    # ===== 下注 =====
    for p in actives:
        r = recv_timeout(p.conn, f"{p.name}，請下注（10秒，0=跳過）", 10)
        if r == "DISCONNECT":
            p.alive = False
            p.spectator = True
            broadcast(f"{p.name} 已離開房間")
            continue
        try:
            p.bet = min(int(r), p.coins)
        except:
            p.bet = 0

    broadcast("=== 玩家列表 ===\n" + player_list())

    # ===== 發牌 =====
    for p in actives + [dealer]:
        if not p.alive or p.spectator:
            continue
        p.hand = [draw_card(), draw_card()]
        if not p.is_dealer:
            p.conn.sendall(f"你的手牌: {p.hand}\n".encode())

    # ===== 玩家補牌 =====
    for p in actives:
        if p.bet == 0 or not p.alive or p.spectator:
            continue
        while True:
            r = recv_timeout(
                p.conn,
                f"{p.name} 你的牌 {p.hand} 要補牌嗎？(y/n)",
                10
            )
            if r == "DISCONNECT":
                p.alive = False
                p.spectator = True
                broadcast(f"{p.name} 已離開房間")
                break
            if r != "y":
                break

            card = draw_card()
            p.hand.append(card)
            point = calc(p.hand)

            if point > 21:
                broadcast(
                    f"{p.name} 補到 {card} → 爆牌 {p.hand} ({point})"
                )
                break

            if len(p.hand) >= 5:
                broadcast(
                    f"{p.name} 五張牌 {p.hand} ({point})"
                )
                break

    # ===== 莊家補牌 =====
    while calc(dealer.hand) < 17:
        dealer.hand.append(draw_card())

    broadcast(
        f"莊家手牌: {dealer.hand} ({calc(dealer.hand)})"
    )

    # ===== 結算 =====
    d_point = calc(dealer.hand)
    for p in actives:
        if p.bet == 0 or not p.alive or p.spectator:
            continue

        p_point = calc(p.hand)

        if p_point > 21:
            p.coins -= p.bet
            dealer.coins += p.bet
            broadcast(
                f"{p.name} 爆牌 {p.hand} ({p_point})，輸了 {p.bet}"
            )

        elif d_point > 21:
            p.coins += p.bet
            dealer.coins -= p.bet
            broadcast(
                f"{p.name} 贏了 {p.bet}（莊家爆牌）"
            )

        elif p_point > d_point:
            p.coins += p.bet
            dealer.coins -= p.bet
            broadcast(f"{p.name} 贏了 {p.bet}")

        elif p_point < d_point:
            p.coins -= p.bet
            dealer.coins += p.bet
            broadcast(f"{p.name} 輸了 {p.bet}")

        else:
            broadcast(
                f"{p.name} 平手（Push） {p.hand} ({p_point})"
            )

        if p.coins <= 0:
            p.spectator = True

    broadcast("=== 回合結束 ===\n" + player_list())

    if dealer.coins <= 0:
        broadcast("玩家方獲勝！遊戲結束")
        return False

    if all(p.spectator for p in players if not p.is_dealer):
        broadcast("莊家獲勝！遊戲結束")
        return False

    return True


# ======================
# Client 連線處理
# ======================
def handle(conn):
    global dealer, GAME_RUNNING
    try:
        conn.sendall("請輸入暱稱:\n".encode())
        name = conn.recv(1024).decode().strip()

        with lock:
            is_dealer = dealer is None
            p = Player(conn, name, is_dealer)
            players.append(p)
            if is_dealer:
                dealer = p

        broadcast(f"{name} 進入房間\n" + player_list())

        if p.is_dealer:
            conn.sendall("你是莊家，按任意鍵開始遊戲\n".encode())
            conn.recv(1024)
            broadcast("遊戲開始！")
            GAME_RUNNING = True

            while GAME_RUNNING:
                if not play_one_round():
                    GAME_RUNNING = False
                    break
    except:
        pass


def main():
    s = socket.socket()
    s.bind((HOST, PORT))
    s.listen()
    print("Server started")

    while True:
        conn, addr = s.accept()
        threading.Thread(
            target=handle,
            args=(conn,),
            daemon=True
        ).start()


if __name__ == "__main__":
    main()