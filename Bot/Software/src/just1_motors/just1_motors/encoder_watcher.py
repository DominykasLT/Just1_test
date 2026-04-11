from gpiozero import DigitalInputDevice

_ENC_A_PINS = (
    (4, "front_left"),
    (6, "front_right"),
    (16, "back_left"),
    (21, "back_right"),
)

_devices = []


def start(feed_fn):
    global _devices
    stop()
    for pin, wheel_name in _ENC_A_PINS:

        def tick(wn=wheel_name):
            feed_fn(wn)

        d = DigitalInputDevice(
            pin,
            pull_up=False,
            bounce_time=None,
        )
        d.when_activated = tick
        d.when_deactivated = tick
        _devices.append(d)


def stop():
    global _devices
    for d in _devices:
        try:
            d.close()
        except Exception:
            pass
    _devices = []
