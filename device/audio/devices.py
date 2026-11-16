"""Choosing audio devices, for USB speakers and microphones on a Raspberry Pi (D-026).

Devices are named by the AUDIO_INPUT_DEVICE / AUDIO_OUTPUT_DEVICE settings or the simulator's
--input-device / --output-device options: a number from --list-devices, or part of a name such
as "USB". Unset means the system default.
"""

Device = int | str | None


def device_from_text(text: str | None) -> Device:
    if text is None or not text.strip():
        return None
    text = text.strip()
    return int(text) if text.isdigit() else text


def list_devices() -> str:
    import sounddevice  # Optional "voice" dependency group.

    return str(sounddevice.query_devices())


def default_rate(device: Device, kind: str) -> int:
    """The sample rate a device prefers; always supported by that device."""
    import sounddevice

    return int(sounddevice.query_devices(device, kind)["default_samplerate"])
