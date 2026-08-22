"""
Cong cu test doc/ghi thanh ghi D cua PLC Mitsubishi qua Ethernet, dung MC
Protocol khung "A-compatible 1E frame" (TCP). Cung muc dich va cach dung
nhu tools/plc_fx_dregister_test.py (ban RS232) — chay file nay TRUOC de xac
nhan doc/ghi D-register qua Ethernet hoat dong dung tren PLC that, roi moi
tich hop vao app (chua tich hop — file nay la buoc kiem chung doc lap).

TAI SAO dung khung 1E (khong phai 3E/4E nhu cac thu vien Python pho bien
vd pymcprotocol):
  Doc thang tu 2 manual chinh chu Mitsubishi (khong doan):
  - "FX3U-ENET-ADP User's Manual": "The frame type of MC protocol ... used
    by the external device to access the PLC via this product is
    equivalent to A compatible 1E frame." — PLC dong FX (bao gom FX3GE
    cong Ethernet tich hop) CHI ho tro 1E frame qua MC Protocol, KHONG ho
    tro 3E/4E.
  - "QnUCPU User's Manual (Communication via Built-in Ethernet Port)":
    Q06UDVCPU (PLC production) ho tro CA 4E/3E LAN 1E frame — nghia la
    dung 1E frame se chay dung tren CA 2 dong PLC (FX3GE test VA Q06UDV
    production), khong can code rieng 2 giao thuc.
  pymcprotocol (thu vien Python pho bien nhat) chi lam 3E/4E, tu README
  cua chinh no: "A and FX series are not supportted because they does
  not support 3E or 4E type." — khong dung duoc cho FX3GE, nen phai tu
  viet khung 1E bang socket TCP thuan (khong them dependency).

XAC NHAN THAT qua hardware:
  - Ghi bit (subheader 02H, vi du M100) — DA CHAY THAT boi user, PLC tra
    dung 82H 00H (thanh cong). Xac nhan khung 1E hoat dong that tren PLC
    that (IP 192.168.3.250, Host Station Port No. 10000, Open System=MC
    Protocol da cau hinh trong GX Works2).
  - Doc/ghi WORD thanh ghi D (subheader 01H/03H — chinh la 2 lenh file nay
    dung) — CHUA TUNG CHAY THAT. Cau truc frame trong file nay suy ra tu
    dung vi du byte-mau chinh xac trong manual (xem duoi), NHUNG can chay
    file nay tren PLC that de xac nhan truoc khi tich hop vao app.

Cau truc frame (trich dung tung byte tu FX3U-ENET-ADP User's Manual,
Section 7.5.5/7.5.6 — vi du that, khong suy dien):
  Doc  D100, 1 word (lenh 01H):
    01H FFH 0AH 00H 64H 00H 00H 00H 20H 44H 01H 00H
    |   |   |monitor  |head device(4B,LE)|devcode|so diem(2B,LE)
    |   PC No.=FFH  timer(2B,LE)=0x000A   D=[20H,44H]
    subheader=01H(doc word)
  Ghi D100..D102 = 0x1234, 0x9876, 0x0109 (lenh 03H, tu manual that):
    03H FFH 0AH 00H 64H 00H 00H 00H 20H 44H 03H 00H 34H 12H 76H 98H 09H 01H
    (header giong het lenh doc, subheader=03H) + du lieu 3 word, MOI word
    2 byte little-endian (byte thap truoc) — KHONG giong kieu dao-hex-string
    cua giao thuc RS232 tu che truoc day, day la nhi phan LE thuan tuy.
  Ma thiet bi D: 2 ky tu ASCII "D"+" " (44H,20H) nhung TRUYEN DAO thu tu
    thanh [20H,44H] — da doi chieu dung voi vi du Y ([20H,59H] cho "Y"+" ")
    va M ([20H,4DH] cho "M"+" ", trong file test cua user) => quy luat
    chung: device_code_bytes = [byte_ky_tu_2, byte_ky_tu_1].
  Response thanh cong: [subheader|80H][complete_code=00H] + du lieu (neu
    la lenh doc, cung LE tung word). Loi thuong: complete_code khac 00H;
    rieng 5BH ("abnormal completion") co them 1 byte abnormal_code (10H-
    18H) va 1 byte 00H ngay sau.

Cach dung:
    python tools/plc_mc_protocol_1e_test.py --host 192.168.3.250 --port 10000

Lenh trong luc chay:
    rd <so_D> [count_word]   doc count_word thanh ghi D lien tiep tu D<so_D>
    wd <so_D> <gia_tri>      ghi 1 gia tri (0-65535) vao D<so_D>
    quit                     thoat
"""

import argparse
import socket

SUBHEADER_READ_WORD = 0x01
SUBHEADER_WRITE_WORD = 0x03
RESPONSE_FLAG = 0x80
COMPLETE_OK = 0x00
COMPLETE_ABNORMAL = 0x5B

PC_NO = 0xFF
DEFAULT_MONITOR_TIMER = 0x000A  # 10 x 250ms = 2.5s — gia tri dung trong moi vi du cua manual

DEVICE_CODE_D = bytes([0x20, 0x44])  # "D"+" " (44H,20H) truyen dao thu tu


def build_read_frame(d_index, word_count, monitor_timer=DEFAULT_MONITOR_TIMER):
    return (
        bytes([SUBHEADER_READ_WORD, PC_NO])
        + monitor_timer.to_bytes(2, "little")
        + d_index.to_bytes(4, "little")
        + DEVICE_CODE_D
        + word_count.to_bytes(2, "little")
    )


def build_write_frame(d_index, values, monitor_timer=DEFAULT_MONITOR_TIMER):
    data = b"".join(v.to_bytes(2, "little") for v in values)
    return (
        bytes([SUBHEADER_WRITE_WORD, PC_NO])
        + monitor_timer.to_bytes(2, "little")
        + d_index.to_bytes(4, "little")
        + DEVICE_CODE_D
        + len(values).to_bytes(2, "little")
        + data
    )


def _recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("PLC dong ket noi TCP giua chung (mat ket noi)")
        data += chunk
    return data


def send_command(sock, frame, expect_read_words=0):
    sock.sendall(frame)
    print(f"GUI -> {frame.hex(' ').upper()}")
    header = _recv_exact(sock, 2)
    complete_code = header[1]
    if complete_code == COMPLETE_ABNORMAL:
        extra = _recv_exact(sock, 2)
        return None, f"PLC bao ABNORMAL COMPLETION - abnormal code: 0x{extra[0]:02X}"
    if complete_code != COMPLETE_OK:
        return None, f"PLC bao loi - complete code: 0x{complete_code:02X}"
    if expect_read_words:
        data = _recv_exact(sock, expect_read_words * 2)
        words = [int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2)]
        return words, None
    return [], None


def run_command(sock, parts):
    cmd = parts[0].lower()
    try:
        if cmd == "rd":
            d_index = int(parts[1])
            word_count = int(parts[2]) if len(parts) > 2 else 1
            frame = build_read_frame(d_index, word_count)
            words, err = send_command(sock, frame, expect_read_words=word_count)
            if err:
                return err
            return f"OK - D{d_index}..: {words}"
        if cmd == "wd":
            d_index = int(parts[1])
            value = int(parts[2])
            frame = build_write_frame(d_index, [value])
            _, err = send_command(sock, frame)
            return err or "OK - da ghi"
    except (IndexError, ValueError):
        return "Sai cu phap lenh. Go 'rd <so_D> [count]' hoac 'wd <so_D> <gia_tri>'."
    except (ConnectionError, socket.timeout) as exc:
        return f"LOI KET NOI - {exc}"
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Doc/ghi thanh ghi D cua PLC Mitsubishi qua MC Protocol (Ethernet, khung 1E)"
    )
    parser.add_argument("--host", required=True, help="Dia chi IP cua PLC, vd 192.168.3.250")
    parser.add_argument("--port", type=int, required=True, help="Host Station Port No. da cau hinh trong Open Setting")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout socket (giay)")
    args = parser.parse_args()

    try:
        sock = socket.create_connection((args.host, args.port), timeout=args.timeout)
    except OSError as e:
        print(f"KHONG KET NOI DUOC {args.host}:{args.port} - {e}")
        return

    print(f"Da ket noi {args.host}:{args.port}.")
    print("Lenh: rd <so_D> [count] | wd <so_D> <gia_tri> | quit\n")

    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.lower() == "quit":
                break
            output = run_command(sock, line.split())
            print(output if output is not None else f"Lenh khong ro: {line}")
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("\nDa dong ket noi.")


if __name__ == "__main__":
    main()
