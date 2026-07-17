import socket
import threading
import traceback


class SRXConnection:

    def __init__(self, name, ip, port=9004, reconnect_interval=3, terminator=b"\r"):
        self.name = name
        self.ip = ip
        self.port = port

        self.sock = None

        self.running = False
        self.connected = False

        self._lock = threading.RLock()
        # time.sleep() thường (dòng reconnect cũ) không thể bị đánh thức sớm
        # khi stop() gọi giữa lúc đang ngủ chờ retry — khiến thread nền có
        # thể còn sống tới reconnect_interval giây sau khi đã "stop", trong
        # khi nơi gọi (SRXReaderQt/_SocketWorker.stop()) chỉ đợi có hạn rồi
        # cho phép xoá/deleteLater() reader dù thread vẫn đang chạy — Qt gọi
        # đây là "QThread: Destroyed while thread is still running", crash
        # cứng (segfault/abort), không phải exception Python bắt được. Event
        # cho phép stop() đánh thức ngay lập tức thay vì phải chờ hết giấc ngủ.
        self._stop_event = threading.Event()

        self.buffer = b""

        self.reconnect_interval = reconnect_interval

        self.terminator = terminator if isinstance(terminator, bytes) else str(terminator).encode()

        self.on_receive = None
        self.on_status = None

    ######################################################################

    def start(self):

        if self.running:
            return

        self.running = True
        self._stop_event.clear()

        threading.Thread(target=self.run_loop, daemon=True).start()

    ######################################################################

    def stop(self):

        self.running = False
        self._stop_event.set()

        with self._lock:
            sock, self.sock, self.connected = self.sock, None, False

        if sock:
            try:
                sock.close()
            except OSError:
                pass

    ######################################################################

    def is_connected(self):

        with self._lock:
            return self.connected

    ######################################################################

    def _connect(self):

        while self.running:

            try:

                sock = socket.create_connection((self.ip, self.port), timeout=5)

                sock.settimeout(None)

                with self._lock:
                    self.sock, self.connected = sock, True

                self._notify_status("connected")

                return

            except Exception:

                self._stop_event.wait(self.reconnect_interval)

    ######################################################################

    def run_loop(self):
        """Thân vòng lặp connect/recv. Nơi gọi (thread riêng, hoặc QThread.run()
        trong app GUI) tự quyết định host trên thread nào; nhớ set
        self.running = True trước khi gọi hàm này."""

        while self.running:

            self._notify_status("connecting")

            self._connect()

            if not self.running:
                break

            try:

                while self.running:

                    sock = self.sock

                    data = sock.recv(1024)

                    if not data:

                        raise ConnectionError()

                    self.buffer += data

                    while self.terminator in self.buffer:

                        line, self.buffer = self.buffer.split(self.terminator, 1)

                        self._notify_receive(line.decode(errors="ignore"))

            except Exception:

                with self._lock:
                    old_sock, self.sock, self.connected = self.sock, None, False

                if old_sock:
                    try:
                        old_sock.close()
                    except OSError:
                        pass

                self._notify_status("disconnected")

                if self.running:
                    self._stop_event.wait(self.reconnect_interval)

    ######################################################################

    def send(self, cmd):

        data = cmd.encode() if isinstance(cmd, str) else bytes(cmd)

        if not data.endswith(self.terminator):
            data += self.terminator

        with self._lock:

            sock = self.sock

            if not sock or not self.connected:
                return False

            try:
                sock.sendall(data)
                return True
            except OSError:
                self.connected = False

        self._notify_status("disconnected")

        return False

    ######################################################################

    def _notify_receive(self, text):

        if self.on_receive:
            try:
                self.on_receive(self, text)
            except Exception:
                traceback.print_exc()
        else:
            print(self.name, text)

    ######################################################################

    def _notify_status(self, status):

        if self.on_status:
            try:
                self.on_status(self, status)
            except Exception:
                traceback.print_exc()
