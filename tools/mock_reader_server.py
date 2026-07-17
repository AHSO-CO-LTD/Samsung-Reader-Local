"""
Mock TCP server giả lập nhiều reader SR-X (N reader vai trò LED BAR + 1
QRCODE BOTTOM) để test khi chưa có phần cứng thật — port khớp sẵn với
readers_config.json.

Mỗi lần bấm "LON (Trigger ON)" trong app (hoặc qua Config Window), server đọc
LẠI file mock_codes.json rồi trả về mã kế tiếp trong danh sách ứng với port đó
(hết danh sách thì quay vòng lại từ đầu). Muốn đổi mã test: sửa trực tiếp
mock_codes.json và lưu lại — KHÔNG cần tắt/chạy lại server, lần LON tiếp theo
sẽ tự lấy dữ liệu mới.

Cách dùng:
    python mock_reader_server.py
"""

import json
import os
import socket
import threading

# Port khớp với readers_config.json: 9101/9201/9401 = 3 reader vai trò LED BAR
# (không còn gắn cứng "LED BAR 1 -> cột 1" — cột thật xác định qua nội dung
# mã lúc chạy), 9301 = QRCODE BOTTOM (dedicated, không đổi).
PORTS = [9101, 9201, 9401, 9301]

CODES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_codes.json")


def load_codes(port):
    try:
        with open(CODES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        codes = data.get(str(port)) or []
        return [str(c) for c in codes] if codes else ["NO_CODE_CONFIGURED"]
    except (OSError, json.JSONDecodeError) as e:
        print(f"[{port}] KHONG DOC DUOC {CODES_FILE}: {e}")
        return ["FILE_READ_ERROR"]


def handle_client(conn, addr, port):
    idx = [0]
    buffer = b""
    print(f"[{port}] Client connected: {addr}")
    try:
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data
                while b"\r" in buffer:
                    line, buffer = buffer.split(b"\r", 1)
                    text = line.decode(errors="ignore")
                    if text == "LON":
                        codes = load_codes(port)
                        code = codes[idx[0] % len(codes)]
                        idx[0] += 1
                        conn.sendall(f"{code}\r".encode())
                        print(f"[{port}] LON -> {code}")
                    elif text == "LOFF":
                        print(f"[{port}] LOFF received")
    except (ConnectionResetError, OSError):
        pass
    print(f"[{port}] Client disconnected: {addr}")


def serve(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("127.0.0.1", port))
    except OSError as e:
        # In rõ lỗi thay vì để thread âm thầm chết — ví dụ khi đã có 1 tiến
        # trình mock_reader_server.py khác đang chiếm port này.
        print(
            f"[{port}] KHONG THE LANG NGHE: {e} (co the da co tien trinh mock khac dang chay port nay)"
        )
        return
    srv.listen(5)
    print(f"Mock reader listening on 127.0.0.1:{port}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(
            target=handle_client, args=(conn, addr, port), daemon=True
        ).start()


def main():
    threads = []
    for port in PORTS:
        t = threading.Thread(target=serve, args=(port,), daemon=True)
        t.start()
        threads.append(t)

    print(f"Ca {len(PORTS)} mock reader dang chay. Sua {CODES_FILE} de doi ma test (khong can restart).")
    print("Nhan Ctrl+C de dung.")
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
