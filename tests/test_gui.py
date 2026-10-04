import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from pa3eke_flexcontrol_bridge.gui import MainWindow


class GUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_window_status_controls_and_manual_usb(self):
        with patch("pa3eke_flexcontrol_bridge.gui.load_settings", return_value={"autostart": False}), \
             patch("pa3eke_flexcontrol_bridge.gui.save_settings") as save:
            window = MainWindow()
            try:
                window.show()
                window.usb.setEditText("COM9")
                self.assertEqual(window.selected_port(), "COM9")
                window.bridge._update(current_freq=14201000, current_step_idx=1,
                                      ptt_on=True, vfo_lock=True, tci_connected=True)
                window.render()
                self.app.processEvents()
                self.assertEqual(window.frequency.text(), "14.201.000 Hz")
                self.assertEqual(window.step.text(), "Stap: 250 Hz")
                self.assertIn("ZENDEN", window.status.text())
                self.assertIn("Vergrendeld", window.lock.text())
                self.assertTrue(window.ptt.isEnabled())
                self.assertFalse(window.grab().isNull())
                window.persist()
                save.assert_called_with("COM9", "ws://127.0.0.1:40001", False)
            finally:
                window.close()
