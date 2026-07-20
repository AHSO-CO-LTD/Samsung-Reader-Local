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
        # KHÔNG đặt timeout — self.conn.stop() giờ đánh thức ngay reconnect
        # sleep qua threading.Event (xem SRXConnection._stop_event), nên
        # thread thoát nhanh trong mọi trường hợp trừ lúc đang kẹt giữa
        # chừng socket.create_connection() (tối đa 5s, không có cách ngắt
        # giữa chừng 1 syscall blocking từ thread khác). Chờ có timeout rồi
        # bỏ qua (như trước) để nơi gọi tưởng đã dừng trong khi thread vẫn
        # còn sống → xoá/deleteLater() reader lúc đó là "QThread: Destroyed
        # while thread is still running", crash cứng — đã tự verify bằng
        # test thật. Đợi vô hạn ở đây đảm bảo isRunning()=False chắc chắn
        # trước khi nơi gọi (ReaderManager.remove_reader) được phép xoá.
        self.wait()

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

        # Cờ "Is Master" (chế độ Master/Slave) — đặt TRỰC TIẾP trên object
        # reader (không phải dict riêng ở MainWindow/ConfigWindow) để 2 cửa
        # sổ luôn thấy CÙNG 1 giá trị tức thời, không có độ trễ đồng bộ. Đã
        # từng dùng 2 dict riêng (MainWindow._reader_is_master/
        # ConfigWindow._is_master, chỉ đồng bộ lúc đóng Config Window) —
        # gây bug thật: tick Master trong lúc dialog đang mở, có dữ liệu
        # Slave tới ĐÚNG lúc đó thì MainWindow vẫn dùng giá trị cũ, nhận
        # trùng dữ liệu ngẫu nhiên theo thời điểm.
        self.is_master = False

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
