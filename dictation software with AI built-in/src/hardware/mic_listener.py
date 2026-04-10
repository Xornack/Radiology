import hid
import threading
from loguru import logger


class MicListener:
    """
    Background listener for medical microphones (SpeechMike, PowerMic, etc.).
    Spawns a daemon polling thread on start() that fires on_trigger callbacks
    whenever the button state changes (press or release).
    """
    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.on_trigger = None
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
            self._poll_once()

    def _poll_once(self):
        """
        Reads one HID report and fires on_trigger if the button state changed.
        Safe to call directly in tests (inject self.device before calling).
        """
        if not self.device:
            return
        try:
            data = self.device.read(64, timeout_ms=10)
            if data:
                pressed = any(b > 0 for b in data)
                if pressed != self._button_pressed:
                    self._button_pressed = pressed
                    if self.on_trigger:
                        self.on_trigger(pressed)
        except (IOError, ValueError, AttributeError) as e:
            logger.warning(f"HID read error: {e}")

    def stop(self):
        """Stops the polling thread and closes the HID device."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self.device:
            try:
                self.device.close()
            except Exception as e:
                logger.warning(f"Error closing HID device: {e}")
            self.device = None
