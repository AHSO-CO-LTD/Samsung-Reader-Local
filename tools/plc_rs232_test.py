"""
Cong cu test giao tiep RS232 voi PLC (dung truoc khi code that tinh nang gui
tin hieu loi cho PLC) — mo 1 cong COM, cho go lenh de gui, in lai moi byte
nhan duoc (ca hex lan ASCII) ngay khi PLC phan hoi. Chua gia dinh giao thuc
cu the nao (Modbus RTU / ASCII rieng cua hang PLC / ...) — dung de kiem tra
day, toc do baud, va quan sat PLC tra loi gi truoc khi thiet ke phan tich cu
phap that.

Cach dung:
    python tools/plc_rs232_test.py --list
    python tools/plc_rs232_test.py --port COM3 --baud 9600

Trong luc chay:
    - Go 1 chuoi roi Enter -> gui chuoi do qua cong COM (kem duoi dong theo
      --eol, mac dinh \\r\\n).
    - Go "hex:AA 01 02 03" -> gui dung day byte hex do (khong kem duoi dong).
    - Go "quit" hoac Ctrl+C -> thoat.
    - Bat ky du lieu nao PLC gui ve deu duoc in ngay (thread nen rieng),
      khong can go gi de "hoi".
"""

import argparse
import sys
import threading
import time

import serial
import serial.tools.list_ports

EOL_CHOICES = {
    "none": b"",
    "cr": b"\r",
    "lf": b"\n",
    "crlf": b"\r\n",
}

PARITY_CHOICES = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
}


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("Khong tim thay cong COM nao dang cam.")
        return
    print("Danh sach cong COM dang co:")
    for p in ports:
        print(f"  {p.device} - {p.description}")


def format_hex(data):
    return " ".join(f"{b:02X}" for b in data)


def format_ascii(data):
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def parse_hex_command(text):
    """"hex:AA 01 02" / "hex:AA0102" -> bytes. Nem ValueError neu sai dinh dang."""
    raw = text[len("hex:"):].strip().replace(" ", "")
    if len(raw) % 2 != 0:
        raise ValueError("So ky tu hex phai chan")
    return bytes.fromhex(raw)


def reader_loop(ser, stop_event):
    while not stop_event.is_set():
        try:
            n = ser.in_waiting
            data = ser.read(n if n else 1)
        except serial.SerialException as e:
            print(f"\n[LOI DOC] {e}")
            stop_event.set()
            return
        if data:
            ts = time.strftime("%H:%M:%S")
            print(f"\n[{ts}] NHAN <- HEX: {format_hex(data)}  ASCII: {format_ascii(data)!r}")
            print("> ", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Test giao tiep RS232 voi PLC")
    parser.add_argument("--list", action="store_true", help="Liet ke cong COM roi thoat")
    parser.add_argument("--port", help="Ten cong COM, vd COM3")
    parser.add_argument("--baud", type=int, default=9600, help="Toc do baud (mac dinh 9600)")
    parser.add_argument("--bytesize", type=int, choices=[5, 6, 7, 8], default=8)
    parser.add_argument("--parity", choices=list(PARITY_CHOICES), default="N", help="N=None, E=Even, O=Odd")
    parser.add_argument("--stopbits", type=float, choices=[1, 1.5, 2], default=1)
    parser.add_argument("--timeout", type=float, default=0.2, help="Timeout doc (giay), mac dinh 0.2")
    parser.add_argument(
        "--eol", choices=list(EOL_CHOICES), default="crlf",
        help="Duoi dong tu dong them khi gui chuoi thuong (khong ap dung cho lenh hex:...)",
    )
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if not args.port:
        print("Thieu --port. Chay voi --list de xem cac cong COM dang co.")
        sys.exit(1)

    stopbits_map = {1: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2: serial.STOPBITS_TWO}

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=args.bytesize,
            parity=PARITY_CHOICES[args.parity],
            stopbits=stopbits_map[args.stopbits],
            timeout=args.timeout,
        )
    except serial.SerialException as e:
        print(f"KHONG MO DUOC CONG {args.port}: {e}")
        sys.exit(1)

    print(
        f"Da mo {args.port} @ {args.baud} baud, {args.bytesize}{args.parity}{args.stopbits}. "
        f"Duoi dong khi gui chuoi thuong: {args.eol!r}."
    )
    print("Go chuoi roi Enter de gui. Go 'hex:AA 01 02' de gui byte hex. Go 'quit' de thoat.\n")

    stop_event = threading.Event()
    t = threading.Thread(target=reader_loop, args=(ser, stop_event), daemon=True)
    t.start()

    try:
        while not stop_event.is_set():
            try:
                line = input("> ")
            except EOFError:
                break
            if line.strip().lower() == "quit":
                break
            if not line:
                continue
            try:
                if line.startswith("hex:"):
                    payload = parse_hex_command(line)
                else:
                    payload = line.encode() + EOL_CHOICES[args.eol]
                ser.write(payload)
                print(f"GUI -> HEX: {format_hex(payload)}  ASCII: {format_ascii(payload)!r}")
            except (ValueError, serial.SerialException) as e:
                print(f"[LOI GUI] {e}")
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        t.join(timeout=1)
        ser.close()
        print("\nDa dong cong COM.")


if __name__ == "__main__":
    main()
