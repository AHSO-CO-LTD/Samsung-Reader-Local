import os

from PyQt5 import uic
from PyQt5.QtWidgets import QCheckBox, QDialog, QTableWidgetItem

from app_paths import get_bundle_dir

UI_PATH = os.path.join(get_bundle_dir(), "ui", "rework_window.ui")


class RewokWindow(QDialog):
    """Dialog chọn NHIỀU mã NG để rework cùng lúc — hiển thị + forward
    callback, KHÔNG tự đụng DB (đúng convention ReconcileWindow). Mặc định
    TÍCH CHỌN mọi dòng đang hiển thị (kể cả sau khi lọc) — operator bỏ tích
    bớt tuỳ ý rồi bấm "Bắt đầu Rework" để xác nhận danh sách cuối cùng.

    on_filter(chassis_code, vendor_char) -> list[dict] — gọi
    list_ng_unreworked_scans(...) (MainWindow sở hữu, dialog không tự query
    DB). Sau khi exec_() trả về QDialog.Accepted, gọi selected_rows() để lấy
    danh sách (giữ nguyên thứ tự hiển thị = thứ tự xử lý hàng đợi)."""

    def __init__(self, on_filter, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)

        self._on_filter = on_filter
        self._rows = []  # song song với các dòng trong bảng, index = row

        self.tableWidgetNgList.horizontalHeader().setStretchLastSection(True)
        self.tableWidgetNgList.setColumnWidth(0, 50)
        self.tableWidgetNgList.setColumnWidth(1, 140)
        self.tableWidgetNgList.setColumnWidth(2, 140)
        self.tableWidgetNgList.setColumnWidth(3, 100)
        self.tableWidgetNgList.setColumnWidth(4, 220)

        self.pushButtonApplyFilter.clicked.connect(self._reload)
        self.pushButtonRefresh.clicked.connect(self._reload)
        self.pushButtonSelectAll.clicked.connect(lambda: self._set_all_checked(True))
        self.pushButtonDeselectAll.clicked.connect(lambda: self._set_all_checked(False))
        self.pushButtonStartRework.clicked.connect(self.accept)
        self.pushButtonClose.clicked.connect(self.reject)

        self._load_filter_options()
        self._reload()

    def _load_filter_options(self):
        """Nạp option cho 2 combo lọc 1 lần duy nhất lúc mở dialog, từ danh
        sách KHÔNG lọc gì (chỉ áp dụng giới hạn 2 ngày cứng) — đơn giản, đủ
        dùng cho phạm vi tính năng này (không tự làm mới option lọc mỗi lần
        bấm Lọc)."""
        rows = self._on_filter(None, None)
        chassis_codes = sorted({r["full_chassis_code"] for r in rows if r.get("full_chassis_code")})
        vendor_chars = sorted({r["full_vendor_char"] for r in rows if r.get("full_vendor_char")})

        self.comboBoxFilterChassis.clear()
        self.comboBoxFilterChassis.addItem("Tất cả", None)
        for code in chassis_codes:
            self.comboBoxFilterChassis.addItem(code, code)

        self.comboBoxFilterVendor.clear()
        self.comboBoxFilterVendor.addItem("Tất cả", None)
        for char in vendor_chars:
            self.comboBoxFilterVendor.addItem(char, char)

    def _reload(self):
        chassis_code = self.comboBoxFilterChassis.currentData()
        vendor_char = self.comboBoxFilterVendor.currentData()
        self._rows = self._on_filter(chassis_code, vendor_char)
        self._populate_table()

    def _populate_table(self):
        table = self.tableWidgetNgList
        table.setRowCount(0)
        for row_data in self._rows:
            row = table.rowCount()
            table.insertRow(row)

            checkbox = QCheckBox()
            checkbox.setChecked(True)  # mặc định tích chọn mọi dòng, theo quyết định đã chốt
            checkbox.toggled.connect(self._update_start_button_label)
            table.setCellWidget(row, 0, checkbox)

            table.setItem(row, 1, QTableWidgetItem(row_data["scan_at"].strftime("%Y-%m-%d %H:%M:%S")))
            table.setItem(row, 2, QTableWidgetItem(row_data.get("full_chassis_code") or "-"))
            vendor_text = row_data.get("full_vendor_char") or "-"
            if row_data.get("vendor_name"):
                vendor_text = f"{vendor_text} ({row_data['vendor_name']})"
            table.setItem(row, 3, QTableWidgetItem(vendor_text))
            ng_reason_text = row_data.get("ng_reason_label") or row_data.get("local_ng_reason") or "-"
            table.setItem(row, 4, QTableWidgetItem(ng_reason_text))
            table.setItem(row, 5, QTableWidgetItem(row_data["local_scan_id"]))
        self._update_start_button_label()

    def _set_all_checked(self, checked):
        table = self.tableWidgetNgList
        for row in range(table.rowCount()):
            checkbox = table.cellWidget(row, 0)
            if checkbox is not None:
                checkbox.setChecked(checked)
        self._update_start_button_label()

    def _update_start_button_label(self, *_args):
        count = len(self.selected_rows())
        self.pushButtonStartRework.setText(f"Bắt đầu Rework ({count} mã)")
        self.pushButtonStartRework.setEnabled(count > 0)

    def selected_rows(self):
        table = self.tableWidgetNgList
        result = []
        for row in range(table.rowCount()):
            checkbox = table.cellWidget(row, 0)
            if checkbox is not None and checkbox.isChecked():
                result.append(self._rows[row])
        return result
