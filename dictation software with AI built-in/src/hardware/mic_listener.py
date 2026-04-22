import hid
import threading
import time
from loguru import logger
from PyQt6.QtCore import QObject, pyqtSignal


class MicListener(QObject):
    """
    Background listener for medical microphones (SpeechMike, PowerMic, etc.).
    Spawns a daemon polling thread on start() that emits `trigger_changed`
    whenever the button state changes (press or release).

    The emit happens from the polling thread; receivers connected via the
    default AutoConnection will have their slots dispatched on the owning
    (GUI) thread, which is required for any Qt widget / timer access.
    """
    trigger_changed = pyqtSignal(bool)

    def __init__(self, vendor_id: int, product_id: int, parent=None):
        super().__init__(parent)
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self._running = False
        self._thread = None
        self._button_pressed = False

    def start(self) -> bool:
        """Opens the HID device and starts the background polling thread."""
        try:
            self.device = hid.device()
            self.device.open(self.vendor_id, self.product_id)
            self._running = True
            self._button_pressed = False
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            logger.error(
                f"Failed to open HID device "
                f"{self.vendor_id:#06x}/{self.product_id:#06x}: {e}"
            )
            self.device = None
            return False

    def _poll_loop(self):
        """Continuously polls the HID device until stop() is called."""
        while self._running:
            if not self._poll_once():
                # Yield briefly when nothing was read to avoid pinning a core
                time.sleep(0.001)

    def _poll_once(self) -> bool:
        """
        Reads one HID report and emits trigger_changed on state transitions.
        Returns True if data was read, False otherwise.
        Safe to call directly in tests (inject self.device before calling).
        """
        if not self.device:
            return False
        try:
            data = self.device.read(64, timeout_ms=10)
            if data:
                pressed = any(b > 0 for b in data)
                if pressed != self._button_pressed:
                    self._button_pressed = pressed
                    # Queued to the GUI thread by AutoConnection — safe to
                    # emit from this polling thread.
                    self.trigger_changed.emit(pressed)
                return True
            return False
        except (IOError, ValueError, AttributeError) as e:
            logger.warning(f"HID read error: {e}")
            return False

    def stop(self):
        """Stops the polling thread and closes the HID device."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                # Daemon thread will exit with the process; warn so we notice
                # if device.read() starts blocking indefinitely.
                logger.warning("HID poll thread did not exit within 1s")
        if self.device:
            try:
                self.device.close()
            except Exception as e:
                logger.warning(f"Error closing HID device: {e}")
            self.device = None
