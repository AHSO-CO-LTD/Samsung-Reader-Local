"""
Cong cu test doc/ghi thanh ghi D cua PLC Mitsubishi FX3G/FX3GE (va tuong
thich FX2N) qua RS232 — CHI dung protocol nay, KHONG phai "Computer Link"/
"Dedicated Protocol" chinh thuc cua Mitsubishi (xem "LICH SU" ben duoi).

XAC NHAN THAT qua hardware (khong con nghi ngo):
  - Doc/ghi thanh ghi D: DA KIEM CHUNG NHIEU LAN qua PLC that (FX3G, CPU
    2.10) — doc dung, ghi dung, doc lai dung, on dinh qua rat nhieu vong
    lap va qua ca 2 kieu cau hinh serial (chi 7E1 hoat dong dung — xem
    "Cau hinh cong COM" ben duoi).
  - Force ON/OFF bit (M): DA THU VA TU BO — xem "LICH SU".

LICH SU (de khong ai lap lai duong cu):
  Protocol nay KHONG PHAI "Computer Link"/"Dedicated Protocol" chinh thuc
  (STX+lenh 1 ky tu+dia chi hex tu tinh+ETX+checksum, KHONG co ENQ/station/
  PLC number nhu chuan Mitsubishi). Da thu doi PLC parameter sang dung
  "Dedicated Protocol" (BR/WR/WW/BT, co ENQ+station+PLC No, dung tai lieu
  goc "FX Series PLC User's Manual - Data Communication Edition" JY997D16901)
  nhung PLC LUON tu choi (NAK tung byte), BAT KE cau hinh dung/sai/tat han.
  Nguyen nhan xac dinh duoc: PLC test CHI CO 1 cong vat ly duy nhat (khong
  co board mo rong RS232 nhu FX3G-232-BD) — CPU BAT BUOC giu cong nay lam
  "Programming Communication" (giao thuc GX Works2 tu dung de lap trinh/
  giam sat), nen KHONG THE dong thoi chay Dedicated Protocol tren cung
  cong do. Da xac nhan bang cach tat han "Operate Communication Setting"
  tren PLC — protocol nay VAN chay y het, chung to no hoan toan doc lap
  voi D8120/PLC parameter, dung la kenh Programming Communication noi bo.
  => Muon dung that Dedicated Protocol/Force ON-OFF, BAT BUOC phai gan
  them board mo rong RS232 that (FX3G-232-BD) de co CH2 rieng cho no,
  giu CH1 (cong co san) cho GX Works2. Khong co board, CHI dung duoc
  protocol trong file nay (doc/ghi D-register).

Cau hinh cong COM (BAT BUOC, da kiem chung 7E1 khac han 8N1):
  9600 baud, 7 data bit, Even parity, 1 stop bit. Da test cheo: cung 1
  frame gui qua 8N1 tra ve du lieu rac, chi 7E1 moi doc/ghi dung — day la
  cau hinh serial-port THAT can, khong lien quan gi PLC Parameter dialog.

KHONG can chinh gi tren PLC (GX Works2) de dung tool nay — protocol nay
hoat dong bat ke PLC Parameter Communication Setting dang bat/tat/o mode
nao, vi no khong phai tinh nang do dieu khien.

Cau truc frame (suy ra tu thuc nghiem, KHONG phai tai lieu chinh thuc):
  Doc  : STX(02H) + "0" + dia_chi_hex(4, = d_index*2+1000H) +
         so_byte_hex(2) + ETX(03H) + checksum(2 hex)
  Ghi  : STX(02H) + "1" + dia_chi_hex(4) + so_byte_hex(2) +
         du_lieu_hex(dao byte trong tung word) + ETX(03H) + checksum(2 hex)
  checksum = 2 ky tu hex cua tong byte TU SAU STX toi HET ETX, mod 256.
  Phan hoi ghi: ACK(06H) don. Phan hoi doc: STX+data+ETX+checksum(2 hex).

Cach dung:
    python tools/plc_fx_dregister_test.py --list
    python tools/plc_fx_dregister_test.py --port COM3

Lenh trong luc chay:
    rd <so_D> [count_word]   doc count_word thanh ghi D lien tiep tu D<so_D>
    wd <so_D> <gia_tri>      ghi 1 gia tri (0-65535) vao D<so_D>
    quit                     thoat
"""

import argparse

import serial
import serial.tools.list_ports

STX = b"\x02"
ETX = b"\x03"
ACK = 0x06
NAK = 0x15

D_BASE_ADDRESS = 0x1000


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("Khong tim thay cong COM nao dang cam.")
        return
    print("Danh sach cong COM dang co:")
    for p in ports:
        print(f"  {p.device} - {p.description}")


def checksum(body):
    """body = moi byte TU SAU STX cho toi HET ETX (bao gom ca ETX)."""
    total = sum(body) & 0xFF
    return f"{total:02X}".encode()


def build_read_frame(d_index, word_count):
    addr = d_index * 2 + D_BASE_ADDRESS
    byte_count = word_count * 2
    body = f"0{addr:04X}{byte_count:02X}".encode() + ETX
    return STX + body + checksum(body)


def build_write_frame(d_index, word_count, data_words):
    addr = d_index * 2 + D_BASE_ADDRESS
    byte_count = word_count * 2
    hex_data = "".join(f"{w & 0xFFFF:04X}"[2:4] + f"{w & 0xFFFF:04X}"[0:2] for w in data_words)
    # PLC tra ve/nhan vao theo thu tu byte thap truoc (little-endian trong tung word)
    body = f"1{addr:04X}{byte_count:02X}".encode() + hex_data.encode() + ETX
    return STX + body + checksum(body)


def send_and_read(ser, frame, expect_data=False):
    ser.reset_input_buffer()
    ser.write(frame)
    print(f"GUI -> {frame!r}")
    first = ser.read(1)
    if not first:
        return None, "TIMEOUT - khong nhan duoc gi tu PLC (kiem tra day/toc do/parity - phai 7E1)"
    if first[0] == NAK:
        return None, "PLC tra NAK - lenh bi tu choi (sai dia chi/checksum/dinh dang)"
    if first[0] == ACK:
        return b"", None
    if not expect_data or first != STX:
        return None, f"Phan hoi khong ro: {first!r}"
    rest = b""
    while not rest.endswith(ETX):
        chunk = ser.read(1)
        if not chunk:
            return None, "TIMEOUT giua chung khi doc du lieu tra ve"
        rest += chunk
    data_part = rest[:-1]  # bo ETX
    checksum_recv = ser.read(2)
    if len(checksum_recv) < 2:
        return None, "TIMEOUT khi doc 2 byte checksum sau ETX"
    expected = checksum(rest)  # rest = data + ETX
    if checksum_recv != expected:
        return None, f"SAI CHECKSUM - nhan {checksum_recv!r}, tinh ra {expected!r} (nhieu duong day/sai baud?)"
    return data_part, None


def run_command(ser, parts):
    cmd = parts[0].lower()
    try:
        if cmd == "rd":
            d_index = int(parts[1])
            word_count = int(parts[2]) if len(parts) > 2 else 1
            frame = build_read_frame(d_index, word_count)
            data, err = send_and_read(ser, frame, expect_data=True)
            if err:
                return err
            words = []
            for i in range(0, len(data), 4):
                pair = data[i:i + 4].decode()
                # doi lai thu tu byte (xem ghi chu o build_write_frame)
                value = int(pair[2:4] + pair[0:2], 16)
                words.append(value)
            return f"OK - D{d_index}..: {words}"
        if cmd == "wd":
            d_index = int(parts[1])
            value = int(parts[2])
            frame = build_write_frame(d_index, 1, [value])
            _, err = send_and_read(ser, frame)
            return err or "OK - da ghi"
    except (IndexError, ValueError):
        return "Sai cu phap lenh. Go 'rd <so_D> [count]' hoac 'wd <so_D> <gia_tri>'."
    return None


def main():
    parser = argparse.ArgumentParser(description="Doc/ghi thanh ghi D cua PLC Mitsubishi FX qua RS232")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--port", help="Ten cong COM, vd COM3")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--bytesize", type=int, choices=[7, 8], default=7)
    parser.add_argument("--parity", choices=["N", "E", "O"], default="E", help="N=None, E=Even, O=Odd")
    parser.add_argument("--stopbits", type=int, choices=[1, 2], default=1)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    if args.list:
        list_ports()
        return
    if not args.port:
        print("Thieu --port. Chay voi --list de xem cac cong COM dang co.")
        return

    parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=args.bytesize,
            parity=parity_map[args.parity],
            stopbits=args.stopbits,
            timeout=args.timeout,
        )
    except serial.SerialException as e:
        print(f"KHONG MO DUOC CONG {args.port}: {e}")
        return

    print(f"Da mo {args.port} @ {args.baud}, {args.bytesize}{args.parity}{args.stopbits}.")
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
            output = run_command(ser, line.split())
            print(output if output is not None else f"Lenh khong ro: {line}")
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("\nDa dong cong COM.")


if __name__ == "__main__":
    main()
