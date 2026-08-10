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
