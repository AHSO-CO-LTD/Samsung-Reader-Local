import os
import uuid

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QMessageBox
try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None

from app_paths import get_bundle_dir
from plc.plc_store import load_plc_config, save_plc_config


class PlcWindow(QDialog):
    def __init__(self, worker, parent=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(get_bundle_dir(), "ui", "plc_window.ui"), self)
        self._worker = worker
        self._pending = {}
        self._load_fields()
        self._refresh_ports()
        self.pushButtonRefreshPorts.clicked.connect(self._refresh_ports)
        self.pushButtonTestRead.clicked.connect(self._test_read)
        self.pushButtonTestWrite.clicked.connect(self._test_write)
        self.pushButtonSave.clicked.connect(self._save)
        self.radioPulse.toggled.connect(self._mode_changed)
        worker.connectionChanged.connect(self._on_connection)
        worker.commandSucceeded.connect(self._on_success)
        worker.commandFailed.connect(self._on_failed)
        self._on_connection(worker.is_connected)

    def _load_fields(self):
        c = load_plc_config()
        self.checkBoxEnabled.setChecked(bool(c["enabled"]))
        self.comboBoxPort.setCurrentText(c.get("port", ""))
        self.spinBoxDRegister.setValue(int(c.get("d_register", 0)))
        self.spinBoxNgValue.setValue(int(c.get("ng_value", 1)))
        self.radioPulse.setChecked(c.get("mode", "pulse") == "pulse")
        self.radioState.setChecked(c.get("mode", "pulse") == "state")
        self.spinBoxPulseDuration.setValue(int(c.get("pulse_duration_ms", 1500)))
        self.spinBoxOkReset.setValue(int(c.get("ok_reset_value", 0)))
        self.checkBoxNormalNg.setChecked(bool(c.get("send_on_normal_ng", True)))
        self.checkBoxReworkNg.setChecked(bool(c.get("send_on_rework_ng", True)))
        self._mode_changed(self.radioPulse.isChecked())

    def _refresh_ports(self):
        current = self.comboBoxPort.currentText()
        self.comboBoxPort.clear()
        ports = list_ports.comports() if list_ports is not None else []
        self.comboBoxPort.addItems([p.device for p in ports])
        if current and self.comboBoxPort.findText(current) < 0:
            self.comboBoxPort.addItem(current)
        self.comboBoxPort.setCurrentText(current)

    def _mode_changed(self, pulse):
        self.spinBoxPulseDuration.setEnabled(bool(pulse))
        self.spinBoxOkReset.setEnabled(not pulse)

    def _current_form_config(self):
        return {
            "enabled": self.checkBoxEnabled.isChecked(),
            "port": self.comboBoxPort.currentText().strip(),
            "d_register": self.spinBoxDRegister.value(),
            "ng_value": self.spinBoxNgValue.value(),
            "mode": "pulse" if self.radioPulse.isChecked() else "state",
            "pulse_duration_ms": self.spinBoxPulseDuration.value(),
            "ok_reset_value": self.spinBoxOkReset.value(),
            "send_on_normal_ng": self.checkBoxNormalNg.isChecked(),
            "send_on_rework_ng": self.checkBoxReworkNg.isChecked(),
        }

    def _test_read(self):
        # Test phải phản ánh đúng giá trị ĐANG NHẬP trên form, không phải
        # cấu hình đã lưu lần trước — worker chỉ biết config qua
        # apply_config(), nên phải đẩy config hiện tại vào TRƯỚC khi
        # enqueue, không chờ user bấm Save (nút Save hiện đóng luôn dialog
        # nên không có cách nào "Save rồi Test" trong cùng 1 lần mở).
        self._worker.apply_config(self._current_form_config())
        correlation = uuid.uuid4().hex
        self._pending[correlation] = "read"
        self._worker.enqueue_test_read(correlation, kind="test_read")

    def _test_write(self):
        self._worker.apply_config(self._current_form_config())
        correlation = uuid.uuid4().hex
        self._pending[correlation] = "write"
        self._worker.enqueue_test_write(self.spinBoxNgValue.value(), correlation)

    def _on_success(self, kind, correlation, result):
        action = self._pending.pop(correlation, None)
        if action == "read":
            self.labelReadResult.setText(f"Đọc được: D{self.spinBoxDRegister.value()} = {result['value']}")
        elif action == "write":
            self.labelWriteResult.setText(f"Đã ghi thành công: {result['value']}")

    def _on_failed(self, kind, correlation, message):
        action = self._pending.pop(correlation, None)
        if action == "read":
            self.labelReadResult.setText(f"Lỗi khi đọc: {message}")
        elif action == "write":
            self.labelWriteResult.setText(f"Lỗi khi ghi: {message}")
        if action:
            QMessageBox.warning(self, "PLC", message)

    def _on_connection(self, connected):
        self.labelConnection.setText("PLC: Đã kết nối" if connected else "PLC: Chưa kết nối")

    def _save(self):
        config = self._current_form_config()
        save_plc_config(config)
        self._worker.apply_config(config)
        self.accept()

    def closeEvent(self, event):
        for signal, slot in ((self._worker.connectionChanged, self._on_connection),
                             (self._worker.commandSucceeded, self._on_success),
                             (self._worker.commandFailed, self._on_failed)):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        super().closeEvent(event)
