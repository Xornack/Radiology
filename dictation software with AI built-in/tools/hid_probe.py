"""HID probe for identifying medical dictation mics.

Usage:
    python tools/hid_probe.py list            # list all HID devices
    python tools/hid_probe.py sniff VID PID   # print raw reports as buttons are pressed

VID/PID can be given as hex (0x0554) or decimal (1364).
Press Ctrl+C to exit sniff mode.
"""
import sys
import time
import hid


KNOWN_VENDORS = {
    0x0554: "Dictaphone / Nuance (PowerMic)",
    0x0911: "Philips (SpeechMike)",
    0x07b4: "Olympus",
    0x17a0: "Samson",
    0x046d: "Logitech",
    0x1532: "Razer",
}


def _parse_id(s: str) -> int:
    return int(s, 0)


def list_devices():
    devices = hid.enumerate()
    if not devices:
        print("No HID devices found.")
        return

    print(f"{'VID':>6}  {'PID':>6}  {'Vendor':<32}  {'Product':<40}  Path")
    print("-" * 120)
    # Deduplicate (VID, PID, product_string) — same device can show on
    # multiple interface collections on Windows.
    seen = set()
    for d in devices:
        vid = d["vendor_id"]
        pid = d["product_id"]
        product = d.get("product_string") or "?"
        key = (vid, pid, product)
        if key in seen:
            continue
        seen.add(key)
        vendor_label = KNOWN_VENDORS.get(vid, "")
        print(
            f"0x{vid:04x}  0x{pid:04x}  {vendor_label:<32}  {product:<40}  "
            f"{d.get('path', b'').decode(errors='replace')[:40]}"
        )


def sniff(vid: int, pid: int):
    print(f"Opening HID device VID=0x{vid:04x}, PID=0x{pid:04x}...")
    device = hid.device()
    try:
        device.open(vid, pid)
    except Exception as e:
        print(f"Failed to open device: {e}")
        print("\nTry running `python tools/hid_probe.py list` first.")
        return

    mfr = device.get_manufacturer_string() or "?"
    prod = device.get_product_string() or "?"
    print(f"Opened: {mfr} / {prod}")
    print("Press mic buttons to see raw HID reports. Ctrl+C to exit.\n")

    last = None
    try:
        while True:
            data = device.read(64, timeout_ms=50)
            if data and data != last:
                hex_repr = " ".join(f"{b:02x}" for b in data)
                bits_nonzero = [i for i, b in enumerate(data) if b != 0]
                print(
                    f"[{time.strftime('%H:%M:%S')}] "
                    f"len={len(data):2d}  nonzero_bytes={bits_nonzero}  "
                    f"hex=[{hex_repr}]"
                )
                last = data
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        device.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        list_devices()
    elif cmd == "sniff":
        if len(sys.argv) != 4:
            print("Usage: python tools/hid_probe.py sniff VID PID")
            sys.exit(1)
        vid = _parse_id(sys.argv[2])
        pid = _parse_id(sys.argv[3])
        sniff(vid, pid)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
