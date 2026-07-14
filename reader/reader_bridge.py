from PyQt5.QtCore import QObject, QThread, pyqtSignal

from reader.SRX_comm import SRXConnection


class _SocketWorker(QThread):
    """1 QThread chạy 1 SRXConnection (1 socket). Dùng làm khối xây dựng cho
    SRXReaderQt — 1 reader có thể cần 1 hoặc 2 khối này (Data / Command)."""

    dataReceived = pyqtSignal(str, str, str)    # (reader_name, channel, text)
    statusChanged = pyqtSignal(str, str, str)   # (reader_name, channel, status)

    def __init__(self, reader_name, channel, ip, port, terminator=b"\r", parent=None):
        super().__init__(parent)
        self.channel = channel
        self.conn = SRXConnection(reader_name, ip, port, terminator=terminator)
        self.conn.on_receive = lambda dev, text: self.dataReceived.emit(dev.name, self.channel, text)
        self.conn.on_status = lambda dev, status: self.statusChanged.emit(dev.name, self.channel, status)

    def run(self):
        self.conn.running = True
        self.conn.run_loop()

    def stop(self):
        self.conn.stop()
        self.wait(2000)

    def send(self, cmd):
        return self.conn.send(cmd)

    def is_connected(self):
        return self.conn.is_connected()

    @property
    def port(self):
        return self.conn.port


class SRXReaderQt(QObject):
    """1 reader SR-X.

    - command_port is None       -> chỉ có kênh Data (luôn lắng nghe), không
      có khả năng gửi lệnh (LON/LOFF vô hiệu).
    - command_port == data_port  -> dùng chung 1 socket cho cả Data và Command.
    - command_port khác data_port -> 2 socket riêng biệt (Data luôn lắng nghe
      bất kể nguồn trigger, Command riêng để gửi lệnh LON/LOFF debug).
    """

    dataReceived = pyqtSignal(str, str)        # (reader_name, text) — luôn từ kênh Data
    statusChanged = pyqtSignal(str, str, str)  # (reader_name, channel, status) — channel: "data" | "command"

    def __init__(self, name, ip, data_port, command_port=None, terminator=b"\r", parent=None):
        super().__init__(parent)

        self._name = name
        self._ip = ip
        self._has_command = command_port is not None
        self._shared = self._has_command and command_port == data_port

        self._data_worker = _SocketWorker(name, "data", ip, data_port, terminator=terminator, parent=self)
        self._data_worker.dataReceived.connect(lambda n, ch, text: self.dataReceived.emit(n, text))
        self._data_worker.statusChanged.connect(lambda n, ch, status: self.statusChanged.emit(n, "data", status))

        if not self._has_command:
            self._cmd_worker = None
        elif self._shared:
            self._cmd_worker = self._data_worker
        else:
            self._cmd_worker = _SocketWorker(name, "command", ip, command_port, terminator=terminator, parent=self)
            self._cmd_worker.statusChanged.connect(lambda n, ch, status: self.statusChanged.emit(n, "command", status))

    def start(self):
        self._data_worker.start()
        if self._has_command and not self._shared:
            self._cmd_worker.start()

    def stop(self):
        self._data_worker.stop()
        if self._has_command and not self._shared:
            self._cmd_worker.stop()

    def is_running(self):
        return self._data_worker.isRunning()

    def send(self, cmd):
        if self._cmd_worker is None:
            return False
        return self._cmd_worker.send(cmd)

    def is_data_connected(self):
        return self._data_worker.is_connected()

    def is_command_connected(self):
        if self._cmd_worker is None:
            return False
        return self._cmd_worker.is_connected()

    def has_command_channel(self):
        """True nếu reader này có khả năng gửi lệnh (dùng chung hoặc port riêng)."""
        return self._has_command

    def has_separate_command_channel(self):
        """True nếu Command dùng port riêng, khác với Data."""
        return self._has_command and not self._shared

    @property
    def name(self):
        return self._name

    @property
    def ip(self):
        return self._ip

    @property
    def data_port(self):
        return self._data_worker.port

    @property
    def command_port(self):
        if self._cmd_worker is None:
            return None
        return self._cmd_worker.port


class ReaderManager:
    """Sổ sách thuần Python quản lý tập SRXReaderQt theo tên."""

    def __init__(self):
        self._readers = {}

    def add_reader(self, name, ip, data_port, command_port=None, terminator=b"\r", parent=None):
        if not name or name in self._readers:
            raise ValueError(f"Tên reader trống hoặc đã tồn tại: '{name}'")
        reader = SRXReaderQt(name, ip, data_port, command_port=command_port, terminator=terminator, parent=parent)
        self._readers[name] = reader
        return reader

    def remove_reader(self, name):
        reader = self._readers.pop(name, None)
        if reader:
            reader.stop()
            reader.deleteLater()

    def get(self, name):
        return self._readers.get(name)

    def names(self):
        return list(self._readers.keys())

    def stop_all(self):
        for r in self._readers.values():
            r.stop()
