import socket
import threading
import os

SERVER_IP = "127.0.0.1"
PORT = 5555

sock = socket.socket()
my_name = ""

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def receive():
    while True:
        try:
            data = sock.recv(1024).decode()
            if not data:
                print("[系統] 伺服器已斷線")
                break
            print(data.strip())
        except:
            print("[系統] 連線中斷")
            break

def start_client():
    sock.connect((SERVER_IP, PORT))
    threading.Thread(target=receive, daemon=True).start()

    my_name = input().strip()
    sock.sendall((my_name + "\n").encode())

    while True:
        try:
            msg = input()
            sock.sendall((msg + "\n").encode())
        except:
            break

if __name__ == "__main__":
    clear_screen()
    print("=== 21 點遊戲 Client ===")
    start_client()