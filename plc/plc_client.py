import socket

try:
    import serial
except ImportError:  # PLC remains usable-disabled when optional dependency is absent
    serial = None

STX = b"\x02"
ETX = b"\x03"
ACK = 0x06
NAK = 0x15
D_BASE_ADDRESS = 0x1000
MAX_D_REGISTER = 7999


class PlcCommError(Exception):
    """Protocol or serial communication failure."""


def checksum(body):
    return f"{sum(body) & 0xFF:02X}".encode("ascii")


def _validate(d_index, word_count):
    if not isinstance(d_index, int) or not 0 <= d_index <= MAX_D_REGISTER:
        raise ValueError(f"D register index must be between 0 and {MAX_D_REGISTER}")
    if not isinstance(word_count, int) or not 1 <= word_count <= 127:
        raise ValueError("word_count must be between 1 and 127")


def build_read_frame(d_index, word_count=1):
    _validate(d_index, word_count)
    body = f"0{d_index * 2 + D_BASE_ADDRESS:04X}{word_count * 2:02X}".encode("ascii") + ETX
    return STX + body + checksum(body)


def build_write_frame(d_index, value):
    _validate(d_index, 1)
    if not isinstance(value, int) or not 0 <= value <= 0xFFFF:
        raise ValueError("PLC value must be between 0 and 65535")
    word = f"{value:04X}"
    data = (word[2:] + word[:2]).encode("ascii")
    body = f"1{d_index * 2 + D_BASE_ADDRESS:04X}02".encode("ascii") + data + ETX
    return STX + body + checksum(body)


def _read_exact(ser, size):
    data = ser.read(size)
    if len(data) != size:
        raise PlcCommError("PLC timeout while reading response")
    return data


def read_register(ser, d_index):
    ser.reset_input_buffer()
    ser.write(build_read_frame(d_index))
    first = _read_exact(ser, 1)[0]
    if first == NAK:
        raise PlcCommError("PLC returned NAK")
    if first != STX[0]:
        raise PlcCommError(f"Unexpected PLC response byte: 0x{first:02X}")
    data = bytearray()
    while True:
        byte = _read_exact(ser, 1)
        if byte == ETX:
            break
        data.extend(byte)
    received_checksum = _read_exact(ser, 2)
    body = bytes(data) + ETX
    if received_checksum != checksum(body):
        raise PlcCommError("PLC response checksum mismatch")
    try:
        text = data.decode("ascii")
        if len(text) != 4:
            raise ValueError
        return int(text[2:] + text[:2], 16)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PlcCommError("Invalid PLC register payload") from exc


def write_register(ser, d_index, value):
    ser.reset_input_buffer()
    ser.write(build_write_frame(d_index, value))
    first = _read_exact(ser, 1)[0]
    if first == ACK:
        return True
    if first == NAK:
        raise PlcCommError("PLC returned NAK")
    raise PlcCommError(f"Unexpected PLC ACK byte: 0x{first:02X}")


def open_serial(port, timeout=1.0):
    if serial is None:
        raise PlcCommError("Thiếu dependency pyserial")
    return serial.Serial(port=port, baudrate=9600, bytesize=7,
                         parity=serial.PARITY_EVEN, stopbits=1, timeout=timeout)


# ---------------------------------------------------------------------------
# MC Protocol (Ethernet, khung "A-compatible 1E frame") — cung du lieu byte
# da doi chieu tung byte voi tools/plc_mc_protocol_1e_test.py (da xac nhan
# tren PLC that FX3GE) va 2 manual chinh chu Mitsubishi (FX3U-ENET-ADP
# User's Manual sec. 7.5.5/7.5.6; QnUCPU Built-in Ethernet Port User's
# Manual chuong 5) — ca 2 dong PLC dang dung trong project nay (FX3GE test,
# Q06UDV production) deu ho tro khung 1E, xem tools/plc_mc_protocol_1e_test.py
# de biet chi tiet vi sao chon khung nay thay vi 3E/4E.
MC_SUBHEADER_READ_WORD = 0x01
MC_SUBHEADER_WRITE_WORD = 0x03
MC_COMPLETE_OK = 0x00
MC_COMPLETE_ABNORMAL = 0x5B
MC_PC_NO = 0xFF
MC_DEFAULT_MONITOR_TIMER = 0x000A  # 10 x 250ms = 2.5s — dung trong moi vi du cua manual
MC_DEVICE_CODE_D = bytes([0x20, 0x44])  # "D"+" " (44H,20H) truyen dao thu tu byte


def _mc_build_read_frame(d_index, word_count, monitor_timer=MC_DEFAULT_MONITOR_TIMER):
    return (
        bytes([MC_SUBHEADER_READ_WORD, MC_PC_NO])
        + monitor_timer.to_bytes(2, "little")
        + d_index.to_bytes(4, "little")
        + MC_DEVICE_CODE_D
        + word_count.to_bytes(2, "little")
    )


def _mc_build_write_frame(d_index, values, monitor_timer=MC_DEFAULT_MONITOR_TIMER):
    data = b"".join(v.to_bytes(2, "little") for v in values)
    return (
        bytes([MC_SUBHEADER_WRITE_WORD, MC_PC_NO])
        + monitor_timer.to_bytes(2, "little")
        + d_index.to_bytes(4, "little")
        + MC_DEVICE_CODE_D
        + len(values).to_bytes(2, "little")
        + data
    )


def _mc_recv_exact(sock, size):
    data = b""
    while len(data) < size:
        try:
            chunk = sock.recv(size - len(data))
        except socket.timeout as exc:
            raise PlcCommError("PLC timeout while reading response") from exc
        except OSError as exc:
            raise PlcCommError(f"Loi socket khi doc phan hoi PLC: {exc}") from exc
        if not chunk:
            raise PlcCommError("PLC dong ket noi TCP giua chung (mat ket noi)")
        data += chunk
    return data


def _mc_send_and_check(sock, frame):
    try:
        sock.sendall(frame)
    except OSError as exc:
        raise PlcCommError(f"Loi socket khi gui lenh PLC: {exc}") from exc
    header = _mc_recv_exact(sock, 2)
    complete_code = header[1]
    if complete_code == MC_COMPLETE_ABNORMAL:
        extra = _mc_recv_exact(sock, 2)
        raise PlcCommError(f"PLC bao loi bat thuong (abnormal code 0x{extra[0]:02X})")
    if complete_code != MC_COMPLETE_OK:
        raise PlcCommError(f"PLC tra ve loi (complete code 0x{complete_code:02X})")


def read_register_mc(sock, d_index):
    _validate(d_index, 1)
    _mc_send_and_check(sock, _mc_build_read_frame(d_index, 1))
    data = _mc_recv_exact(sock, 2)
    return int.from_bytes(data, "little")


def write_register_mc(sock, d_index, value):
    _validate(d_index, 1)
    if not isinstance(value, int) or not 0 <= value <= 0xFFFF:
        raise ValueError("PLC value must be between 0 and 65535")
    _mc_send_and_check(sock, _mc_build_write_frame(d_index, [value]))
    return True


def open_tcp(host, port, timeout=3.0):
    if not host:
        raise PlcCommError("Chưa nhập địa chỉ IP cho PLC")
    if not isinstance(port, int) or not 0 < port <= 65535:
        raise PlcCommError("Cổng TCP không hợp lệ")
    try:
        return socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        raise PlcCommError(f"Không kết nối được {host}:{port}: {exc}") from exc
