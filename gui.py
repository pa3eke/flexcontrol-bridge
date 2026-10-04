import queue
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QVBoxLayout, QWidget)

from .bridge import FlexControlBridge
from .constants import DEFAULT_TCI_URL, STEPS
from .settings import load_settings, save_settings


class MainWindow(QMainWindow):
    def __init__(self, bridge=None):
        super().__init__()
        self.bridge = bridge or FlexControlBridge()
        self.settings = load_settings()
        self._closing = False
        self.setWindowTitle("PA3EKE · FlexControl voor Thetis")
        self.resize(560, 460)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        heading = QLabel("FlexControl → Thetis")
        heading.setFont(QFont("", 22, QFont.Weight.Bold))
        layout.addWidget(heading)
        layout.addWidget(QLabel("TCI · RX1 / VFO A"))
        self.frequency = QLabel("— Hz")
        self.frequency.setFont(QFont("", 32, QFont.Weight.Bold))
        self.frequency.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.frequency)
        self.status = QLabel("USB: niet verbonden  ·  TCI: niet verbonden")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.step = QPushButton("Stap: 100 Hz")
        self.step.clicked.connect(lambda: self.bridge.request("step"))
        self.lock = QPushButton("AUX3 · Vrij afstemmen")
        self.lock.clicked.connect(lambda: self.bridge.request("lock"))
        self.ptt = QPushButton("PTT uit")
        self.ptt.clicked.connect(lambda: self.bridge.request("ptt_off"))
        for button in (self.step, self.lock, self.ptt):
            controls.addWidget(button)
        layout.addLayout(controls)
        help_label = QLabel("AUX1: PTT aan/uit  ·  AUX3: afstemmen vergrendelen\n"
                            "Draaiknop indrukken: 100 → 250 → 1.000 Hz → herhalen\n"
                            "Bij 1.000 Hz: afronden naar het dichtstbijzijnde kHz")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        form = QFormLayout()
        self.usb = QComboBox()
        self.usb.setEditable(True)
        self.refresh = QPushButton("Vernieuwen")
        self.refresh.clicked.connect(self.refresh_ports)
        usb_row = QHBoxLayout()
        usb_row.addWidget(self.usb, 1)
        usb_row.addWidget(self.refresh)
        form.addRow("FlexControl USB", usb_row)
        self.url = QLineEdit(self.settings.get("tci_url", DEFAULT_TCI_URL))
        self.url.setPlaceholderText("ws://IP-van-Thetis:40001")
        form.addRow("Thetis TCI-adres", self.url)
        layout.addLayout(form)
        self.auto = QCheckBox("Automatisch verbinden bij openen")
        self.auto.setChecked(self.settings.get("autostart", True))
        self.auto.toggled.connect(self.persist)
        layout.addWidget(self.auto)
        self.connect = QPushButton("Verbinden")
        self.connect.setMinimumHeight(40)
        self.connect.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect)
        self.message = QLabel("Zet de TCI-server aan in Thetis en sluit de FlexControl aan.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.refresh_ports()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.render)
        self.timer.start(100)
        if self.auto.isChecked():
            QTimer.singleShot(200, self.toggle_connection)

    def refresh_ports(self):
        saved = self.selected_port() or self.settings.get("flex_port", "")
        self.usb.clear()
        self.usb.addItem("Automatisch detecteren", "")
        for port in self.bridge.port_manager.refresh_ports():
            self.usb.addItem(f"{port.device} · {port.description}", port.device)
        index = self.usb.findData(saved)
        if index >= 0:
            self.usb.setCurrentIndex(index)
        elif saved:
            self.usb.setEditText(saved)

    def selected_port(self):
        index = self.usb.currentIndex()
        if index >= 0 and self.usb.currentText() == self.usb.itemText(index):
            return self.usb.itemData(index) or ""
        return self.usb.currentText().strip()

    def persist(self):
        try:
            save_settings(self.selected_port(), self.url.text().strip(), self.auto.isChecked())
        except OSError as exc:
            self.message.setText(f"Instellingen opslaan mislukt: {exc}")

    def toggle_connection(self):
        if self.bridge.snapshot().running:
            self.bridge.stop()
            self.connect.setEnabled(False)
        else:
            error = self.bridge.start(self.selected_port(), self.url.text())
            if error:
                self.message.setText(error)
                return
            self.persist()
        self.render()

    def render(self):
        state = self.bridge.snapshot()
        self.frequency.setText((f"{state.current_freq:,}".replace(",", ".") + " Hz")
                               if state.current_freq is not None else "— Hz")
        usb = "verbonden" if state.flex_connected else "wachten"
        tci = "verbonden" if state.tci_connected else "wachten"
        radio = "ZENDEN" if state.ptt_on else "Ontvangst"
        self.status.setText(f"USB: {usb}  ·  TCI: {tci}  ·  {radio}")
        self.status.setStyleSheet("color: #ff746c; font-weight: bold;" if state.ptt_on else "")
        self.step.setText(f"Stap: {STEPS[state.current_step_idx]:,} Hz".replace(",", "."))
        self.lock.setText("AUX3 · Vergrendeld" if state.vfo_lock else "AUX3 · Vrij afstemmen")
        self.connect.setText("Verbinding stoppen" if state.running else "Verbinden")
        self.connect.setEnabled(not self.bridge.stop_event.is_set() or not state.running)
        for control in (self.usb, self.url, self.refresh):
            control.setEnabled(not state.running)
        self.step.setEnabled(state.running)
        self.lock.setEnabled(state.running)
        self.ptt.setEnabled(state.tci_connected)
        while True:
            try:
                self.message.setText(self.bridge.error_queue.get_nowait())
            except queue.Empty:
                break
        if self._closing and not state.running:
            self.close()

    def closeEvent(self, event):
        self.persist()
        if self.bridge.snapshot().running:
            self._closing = True
            self.bridge.stop()
            self.message.setText("Verbinding afsluiten en PTT vrijgeven…")
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PA3EKE FlexControl Bridge")
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QWidget { background: #17212b; color: #e7eff5; font-size: 13px; }
        QLineEdit, QComboBox { background: #233342; padding: 8px; border: 1px solid #405366; border-radius: 5px; }
        QPushButton { background: #2a4257; padding: 9px; border-radius: 6px; }
        QPushButton:hover { background: #365974; }
        QPushButton:disabled { color: #8293a0; background: #202e3a; }
        QCheckBox { spacing: 8px; }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
