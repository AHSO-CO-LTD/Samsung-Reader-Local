import os
from datetime import datetime

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QDialog, QMessageBox, QTableWidgetItem

from reader.reader_store import save_readers

UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_window.ui")

STATUS_LABELS = {
    "connecting": "Connecting...",
    "connected": "Connected",
    "disconnected": "Disconnected",
}

STATUS_COLORS = {
    "connecting": QColor("darkorange"),
    "connected": QColor("green"),
    "disconnected": QColor("red"),
}

MAX_LOG_LINES = 500

READER_NAMES = ["LED BAR 1", "LED BAR 2", "QRCODE BOTTOM"]
MAX_READERS = len(READER_NAMES)


class ConfigWindow(QDialog):
    """Cửa sổ quản lý reader: thêm/xóa, lưu vào JSON, test lệnh LON/LOFF.
    Dùng chung 1 ReaderManager với MainWindow (truyền vào constructor)."""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)

        self.manager = manager
        self._status = {}

        self.tableWidgetReaders.horizontalHeader().setStretchLastSection(True)
        self.tableWidgetReaders.setColumnWidth(0, 150)
        self.tableWidgetReaders.setColumnWidth(1, 130)
        self.tableWidgetReaders.setColumnWidth(2, 90)
        self.tableWidgetReaders.setColumnWidth(3, 120)
        self.splitter.setSizes([450, 150])

        self.pushButtonAddReader.clicked.connect(self.on_add_reader)
        self.pushButtonRemoveReader.clicked.connect(self.on_remove_reader)
        self.pushButtonConnect.clicked.connect(self.on_connect_clicked)
        self.pushButtonDisconnect.clicked.connect(self.on_disconnect_clicked)
        self.pushButtonTriggerOn.clicked.connect(lambda: self.send_to_selected("LON"))
        self.pushButtonTriggerOff.clicked.connect(lambda: self.send_to_selected("LOFF"))
        self.pushButtonClose.clicked.connect(self.close)
        self.tableWidgetReaders.itemSelectionChanged.connect(self.on_selection_changed)

        for name in self.manager.names():
            self._add_row_for_existing_reader(name)

        self._update_test_buttons()
        self._refresh_name_combo()

    ######################################################################
    # Thêm / xóa reader
    ######################################################################

    def on_add_reader(self):
        if len(self.manager.names()) >= MAX_READERS:
            QMessageBox.warning(self, "Limit reached", f"Maximum {MAX_READERS} readers allowed.")
            return

        name = self.comboBoxName.currentText().strip()
        ip = self.lineEditIp.text().strip()
        data_port = self.spinBoxDataPort.value()
        command_port_text = self.lineEditCommandPort.text().strip()

        if not name or not ip:
            QMessageBox.warning(self, "Missing information", "Name and IP Address are required.")
            return

        command_port = None
        if command_port_text:
            try:
                command_port = int(command_port_text)
                if not (1 <= command_port <= 65535):
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Invalid Command Port", "Command Port must be a number between 1 and 65535.")
                return

        try:
            reader = self.manager.add_reader(name, ip, data_port, command_port=command_port, parent=self)
        except ValueError as e:
            QMessageBox.warning(self, "Cannot add reader", str(e))
            return

        reader.dataReceived.connect(self.on_data_received)
        reader.statusChanged.connect(self.on_status_changed)

        self._status[name] = {"data": "disconnected", "command": "disconnected"}
        self._add_table_row(reader)

        reader.start()
        self._persist()

        self.lineEditIp.clear()
        self.spinBoxDataPort.setValue(9004)
        self.lineEditCommandPort.clear()
        self._refresh_name_combo()

        row = self._find_row(name)
        if row is not None:
            self.tableWidgetReaders.selectRow(row)

    def on_remove_reader(self):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "No reader selected", "Please select a reader from the list first.")
            return

        confirm = QMessageBox.question(
            self, "Remove reader", f"Remove reader '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        row = self._find_row(name)
        self.manager.remove_reader(name)
        if row is not None:
            self.tableWidgetReaders.removeRow(row)

        self._status.pop(name, None)
        self._persist()
        self._update_test_buttons()
        self._refresh_name_combo()

    ######################################################################
    # Kết nối / ngắt kết nối thủ công
    ######################################################################

    def on_connect_clicked(self):
        reader = self._selected_reader()
        if reader and not reader.is_running():
            reader.start()

    def on_disconnect_clicked(self):
        reader = self._selected_reader()
        if reader:
            reader.stop()

    ######################################################################
    # Chọn reader trong bảng
    ######################################################################

    def on_selection_changed(self):
        self._update_test_buttons()

    ######################################################################
    # Nhận dữ liệu / trạng thái từ reader (chạy trên GUI thread nhờ signal)
    ######################################################################

    def on_data_received(self, name, text):
        self._append_log(f"[{self._now()}] [{name}] RX: {text}")

    def on_status_changed(self, name, channel, status):
        self._status.setdefault(name, {})[channel] = status
        self._append_log(f"[{self._now()}] [{name}] STATUS ({channel}): {STATUS_LABELS.get(status, status)}")

        row = self._find_row(name)
        if row is not None:
            item = self.tableWidgetReaders.item(row, 4)
            item.setText(self._status_line(name))
            item.setForeground(STATUS_COLORS.get(self._status.get(name, {}).get("data"), QColor("black")))

    ######################################################################
    # Test bằng lệnh
    ######################################################################

    def send_to_selected(self, cmd):
        name = self._selected_name()
        if not name:
            return
        reader = self.manager.get(name)
        ok = reader.send(cmd)
        if ok:
            self._append_log(f"[{self._now()}] [{name}] TX: {cmd}")
        else:
            self._append_log(f"[{self._now()}] [{name}] TX FAILED (not connected): {cmd}")

    def _update_test_buttons(self):
        reader = self._selected_reader_silent()
        enabled = reader is not None and reader.has_command_channel()
        self.pushButtonTriggerOn.setEnabled(enabled)
        self.pushButtonTriggerOff.setEnabled(enabled)

    def _refresh_name_combo(self):
        used = set(self.manager.names())
        available = [n for n in READER_NAMES if n not in used]

        self.comboBoxName.clear()
        self.comboBoxName.addItems(available)

        can_add = bool(available) and len(self.manager.names()) < MAX_READERS
        self.comboBoxName.setEnabled(can_add)
        self.pushButtonAddReader.setEnabled(can_add)

    ######################################################################
    # Tiện ích nội bộ
    ######################################################################

    def _add_row_for_existing_reader(self, name):
        reader = self.manager.get(name)
        self._status[name] = {
            "data": "connected" if reader.is_data_connected() else "disconnected",
            "command": "connected" if reader.is_command_connected() else "disconnected",
        }
        self._add_table_row(reader)

    def _add_table_row(self, reader):
        row = self.tableWidgetReaders.rowCount()
        self.tableWidgetReaders.insertRow(row)

        item_name = QTableWidgetItem(reader.name)
        item_name.setData(Qt.UserRole, reader.name)
        self.tableWidgetReaders.setItem(row, 0, item_name)
        self.tableWidgetReaders.setItem(row, 1, QTableWidgetItem(reader.ip))
        self.tableWidgetReaders.setItem(row, 2, QTableWidgetItem(str(reader.data_port)))
        self.tableWidgetReaders.setItem(row, 3, QTableWidgetItem(
            str(reader.command_port) if reader.has_command_channel() else "-"
        ))
        self.tableWidgetReaders.setItem(row, 4, QTableWidgetItem(self._status_line(reader.name)))

    def _selected_name(self):
        items = self.tableWidgetReaders.selectedItems()
        if not items:
            return None
        row = items[0].row()
        return self.tableWidgetReaders.item(row, 0).data(Qt.UserRole)

    def _selected_reader(self):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "No reader selected", "Please select a reader from the list first.")
            return None
        return self.manager.get(name)

    def _selected_reader_silent(self):
        name = self._selected_name()
        return self.manager.get(name) if name else None

    def _find_row(self, name):
        for row in range(self.tableWidgetReaders.rowCount()):
            item = self.tableWidgetReaders.item(row, 0)
            if item and item.data(Qt.UserRole) == name:
                return row
        return None

    def _status_line(self, name):
        reader = self.manager.get(name)
        status = self._status.get(name, {})
        data_label = STATUS_LABELS.get(status.get("data"), "-")
        if reader is not None and reader.has_separate_command_channel():
            cmd_label = STATUS_LABELS.get(status.get("command"), "-")
            return f"Data: {data_label} | Cmd: {cmd_label}"
        return data_label

    def _append_log(self, line):
        self.textEditLog.append(line)
        doc = self.textEditLog.document()
        if doc.blockCount() > MAX_LOG_LINES:
            cursor = self.textEditLog.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, doc.blockCount() - MAX_LOG_LINES)
            cursor.removeSelectedText()

    def _persist(self):
        data = []
        for name in self.manager.names():
            r = self.manager.get(name)
            data.append({
                "name": r.name,
                "ip": r.ip,
                "data_port": r.data_port,
                "command_port": r.command_port if r.has_command_channel() else None,
            })
        save_readers(data)

    @staticmethod
    def _now():
        return datetime.now().strftime("%H:%M:%S")
