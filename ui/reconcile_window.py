import os

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QListWidgetItem, QMessageBox

from app_paths import get_bundle_dir

UI_PATH = os.path.join(get_bundle_dir(), "ui", "reconcile_window.ui")


class ReconcileWindow(QDialog):
    """Dialog hiển thị diff sau khi POST /api/sync/reconcile/check trả về
    SYNC_RECONCILE_DIFF_FOUND — 3 danh sách (missing_on_server/missing_on_local/
    changed_records) để đọc + 2 nút hành động. KHÔNG tự gọi server — chỉ hiển
    thị + chuyển tiếp qua on_push/on_pull, đúng pattern RegisterWindow.on_sync_now:
    MainWindow giữ toàn bộ state (_serial/_uid/_batch_in_flight/_reconcile_in_flight),
    dialog con chỉ là UI + callback.

    "Review" (changed_records) đã gộp vào Pull from Server theo quyết định
    chốt trước khi làm bước này — không có checkbox chọn từng dòng, bấm Pull
    kéo về CẢ missing_on_local LẪN changed_records cùng lúc."""

    def __init__(self, diff, on_push, on_pull, parent=None):
        super().__init__(parent)
        uic.loadUi(UI_PATH, self)

        self._diff = diff
        self._on_push = on_push
        self._on_pull = on_pull

        missing_on_server = diff.get("missing_on_server") or []
        missing_on_local = diff.get("missing_on_local") or []
        changed_records = diff.get("changed_records") or []

        for r in missing_on_server:
            self.listWidgetMissingOnServer.addItem(QListWidgetItem(r.get("local_scan_id") or "?"))
        for r in missing_on_local:
            self.listWidgetMissingOnLocal.addItem(QListWidgetItem(r.get("local_scan_id") or "?"))
        for r in changed_records:
            mismatches = r.get("mismatches") or []
            detail = "; ".join(
                f"{m.get('field')}: local={m.get('local')} vs server={m.get('server')}" for m in mismatches
            )
            text = f"{r.get('local_scan_id') or '?'} — {detail}" if detail else (r.get("local_scan_id") or "?")
            self.listWidgetChanged.addItem(QListWidgetItem(text))

        self.labelSummary.setText(
            f"Missing on server: {len(missing_on_server)}   |   "
            f"Missing on local: {len(missing_on_local)}   |   "
            f"Changed: {len(changed_records)}"
        )

        self.pushButtonPush.setEnabled(bool(missing_on_server))
        self.pushButtonPull.setEnabled(bool(missing_on_local) or bool(changed_records))

        self.pushButtonPush.clicked.connect(self._on_push_clicked)
        self.pushButtonPull.clicked.connect(self._on_pull_clicked)
        self.pushButtonClose.clicked.connect(self.close)

    def _on_push_clicked(self):
        ids = [r.get("local_scan_id") for r in (self._diff.get("missing_on_server") or [])]
        if not ids:
            return
        if QMessageBox.question(
            self, "Push to Server", f"Send {len(ids)} record(s) to server?",
        ) == QMessageBox.Yes:
            self._on_push(ids)
            self.close()

    def _on_pull_clicked(self):
        ids = (
            [r.get("local_scan_id") for r in (self._diff.get("missing_on_local") or [])]
            + [r.get("local_scan_id") for r in (self._diff.get("changed_records") or [])]
        )
        if not ids:
            return
        if QMessageBox.question(
            self, "Pull from Server", f"Overwrite {len(ids)} local record(s) with server data?",
        ) == QMessageBox.Yes:
            self._on_pull(ids)
            self.close()
