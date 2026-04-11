from gpiozero import Device, Motor, OutputDevice
from gpiozero.pins.lgpio import LGPIOFactory
import time
import threading
import logging

from just1_motors.encoder_watcher import start as start_encoder_watcher
from just1_motors.encoder_watcher import stop as stop_encoder_watcher

Device.pin_factory = LGPIOFactory()

logger = logging.getLogger(__name__)

# TT encoder motors in this build are rated 6V. The 4S LiFePO4 battery
# supplies 12.8V nominal to the TB6612FNG motor rail. Capping PWM duty at 47%
# keeps the average motor voltage at ~6.0V (12.8V × 0.47), within motor spec.
MAX_MOTOR_SPEED = 47  # percent (0–100 scale)

# ── Stall Watchdog Configuration ─────────────────────────────────────────────
# The TB6612FNG is rated 1.2A continuous per channel. The FIT0450 motors
# stall at 2.8A — exceeding the driver's continuous rating. If a motor is
# commanded to move but produces no encoder ticks for longer than this
# timeout, we assume it is stalled and cut power to prevent driver damage.
WATCHDOG_TIMEOUT_S = 0.5   # seconds — cut motor if stalled for 500ms
WATCHDOG_CHECK_INTERVAL_S = 0.1  # how often the background thread checks

# ── TB6612FNG #1 — Front wheels ──────────────────────────────────────────────
front_left_ain1  = 17   # direction
front_left_ain2  = 22   # direction
front_left_pwma  = 18   # hw PWM (PWM1_0)

front_right_bin1 = 23   # direction
front_right_bin2 = 24   # direction
front_right_pwmb = 13   # hw PWM (PWM0_1)

tb6612_1_stby    = 25   # standby shared across both channels on chip #1

# ── TB6612FNG #2 — Back wheels ───────────────────────────────────────────────
back_left_ain1   = 27   # direction
back_left_ain2   = 10   # direction
back_left_pwma   = 12   # hw PWM (PWM0_0)

back_right_bin1  = 9    # direction
back_right_bin2  = 11   # direction
back_right_pwmb  = 19   # hw PWM (PWM1_1)

tb6612_2_stby    = 8    # standby shared across both channels on chip #2

# Global objects
front_left_motor  = None
front_right_motor = None
back_left_motor   = None
back_right_motor  = None
_stby1 = None
_stby2 = None

# ── Watchdog State ───────────────────────────────────────────────────────────
_WHEEL_NAMES = ["front_left", "front_right", "back_left", "back_right"]
_watchdog_lock = threading.Lock()
_watchdog_thread = None
_watchdog_running = False

# Per-wheel tracking: when the wheel was last commanded with non-zero speed,
# and when the last encoder tick was received (used for stall detection).
_last_command_time = {}      # wheel_name → monotonic timestamp
_last_command_speed = {}     # wheel_name → last commanded speed (int)
_last_encoder_tick_time = {} # wheel_name → monotonic timestamp (fed by encoder code)
_stall_flags = {}            # wheel_name → True if currently stalled (to avoid log spam)
_stall_latched = {}          # wheel_name → True after watchdog cut PWM until zero cmd or encoder tick


def _init_watchdog_state():
    """Reset all watchdog tracking state."""
    now = time.monotonic()
    for name in _WHEEL_NAMES:
        _last_command_time[name] = now
        _last_command_speed[name] = 0
        _last_encoder_tick_time[name] = now
        _stall_flags[name] = False
        _stall_latched[name] = False


def _watchdog_loop():
    """Background thread: periodically checks for stalled motors."""
    while _watchdog_running:
        time.sleep(WATCHDOG_CHECK_INTERVAL_S)
        _check_for_stalls()


def _check_for_stalls():
    """
    Check each motor for stall condition.

    A motor is considered stalled when:
      1. It is being commanded to move (speed ≠ 0), AND
      2. No encoder tick has been reported for longer than WATCHDOG_TIMEOUT_S.

    When a stall is detected, the motor is immediately stopped and a
    warning is logged. A per-wheel stall latch blocks further non-zero
    commands until the operator sends zero for that wheel or an encoder
    tick clears the latch.
    """
    now = time.monotonic()
    with _watchdog_lock:
        for name in _WHEEL_NAMES:
            speed = _last_command_speed.get(name, 0)
            if speed == 0:
                # Motor is not commanded — nothing to watch.
                _stall_flags[name] = False
                continue

            time_since_tick = now - _last_encoder_tick_time.get(name, now)
            if time_since_tick > WATCHDOG_TIMEOUT_S:
                if not _stall_flags[name]:
                    # First detection — log and stop.
                    _stall_flags[name] = True
                    logger.warning(
                        f"STALL DETECTED on '{name}': commanded speed={speed}, "
                        f"no encoder tick for {time_since_tick:.2f}s. "
                        f"Cutting power to protect TB6612FNG (1.2A limit)."
                    )
                _do_stop_wheel(name)


def _do_stop_wheel(name):
    """Stop a single motor by name (no lock — caller must hold _watchdog_lock)."""
    wheel_map = {
        "front_left":  front_left_motor,
        "front_right": front_right_motor,
        "back_left":   back_left_motor,
        "back_right":  back_right_motor,
    }
    motor = wheel_map.get(name)
    if motor:
        motor.stop()
    _last_command_speed[name] = 0
    _stall_latched[name] = True


def feed_watchdog(wheel_name):
    """
    Call this whenever an encoder tick is received for a wheel.

    This tells the watchdog that the motor IS actually rotating — it resets
    the stall timer for that wheel. Should be called from the encoder
    interrupt handler or encoder reading loop.

    Args:
        wheel_name (str): 'front_left', 'front_right', 'back_left', 'back_right'
    """
    with _watchdog_lock:
        _last_encoder_tick_time[wheel_name] = time.monotonic()
        _stall_flags[wheel_name] = False
        _stall_latched[wheel_name] = False


def setup():
    """Initialize TB6612FNG driver chips, motor objects, and stall watchdog."""
    global front_left_motor, front_right_motor, back_left_motor, back_right_motor
    global _stby1, _stby2, _watchdog_thread, _watchdog_running

    _stby1 = OutputDevice(tb6612_1_stby, initial_value=True)
    _stby2 = OutputDevice(tb6612_2_stby, initial_value=True)

    front_left_motor  = Motor(forward=front_left_ain1,  backward=front_left_ain2,  enable=front_left_pwma,  pwm=True)
    front_right_motor = Motor(forward=front_right_bin1, backward=front_right_bin2, enable=front_right_pwmb, pwm=True)
    back_left_motor   = Motor(forward=back_left_ain1,   backward=back_left_ain2,   enable=back_left_pwma,   pwm=True)
    back_right_motor  = Motor(forward=back_right_bin1,  backward=back_right_bin2,  enable=back_right_pwmb,  pwm=True)

    # Start the stall watchdog background thread.
    _init_watchdog_state()
    _watchdog_running = True
    _watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True)
    _watchdog_thread.start()
    logger.info(
        f"Stall watchdog started (timeout={WATCHDOG_TIMEOUT_S}s, "
        f"check interval={WATCHDOG_CHECK_INTERVAL_S}s)"
    )
    try:
        start_encoder_watcher(feed_watchdog)
        logger.info("Encoder lines started (ENC_A per wheel) for stall watchdog feed.")
    except Exception as e:
        logger.error("Encoder watcher failed to start; stall detection may be unsafe: %s", e)


def stop_all():
    """Stop all motors (STBY remains active — motors hold position briefly then coast)."""
    with _watchdog_lock:
        for name in _WHEEL_NAMES:
            _last_command_speed[name] = 0
            _stall_latched[name] = False
    front_left_motor.stop()
    front_right_motor.stop()
    back_left_motor.stop()
    back_right_motor.stop()


def control_wheel(wheel_name, speed):
    """
    Control a specific wheel.

    Args:
        wheel_name (str): 'front_left', 'front_right', 'back_left', 'back_right'
        speed (int): -100 to 100. Values outside ±MAX_MOTOR_SPEED are silently
                     clamped to protect 6V-rated motors from the 12.8V supply.
    """
    wheel_map = {
        "front_left":  front_left_motor,
        "front_right": front_right_motor,
        "back_left":   back_left_motor,
        "back_right":  back_right_motor,
    }

    if wheel_name not in wheel_map:
        raise ValueError(
            f"Invalid wheel name: {wheel_name}. Must be one of {list(wheel_map.keys())}"
        )

    if not -100 <= speed <= 100:
        raise ValueError("Speed must be between -100 and 100")

    speed = max(-MAX_MOTOR_SPEED, min(MAX_MOTOR_SPEED, speed))

    now = time.monotonic()
    with _watchdog_lock:
        if speed == 0:
            _stall_latched[wheel_name] = False

        if speed != 0 and _stall_latched.get(wheel_name, False):
            return

        prev_speed = _last_command_speed.get(wheel_name, 0)
        _last_command_speed[wheel_name] = speed
        _last_command_time[wheel_name] = now

        if prev_speed == 0 and speed != 0:
            _last_encoder_tick_time[wheel_name] = now
            _stall_flags[wheel_name] = False

    motor = wheel_map[wheel_name]
    speed_normalized = speed / 100.0

    if speed_normalized > 0:
        motor.forward(speed_normalized)
    elif speed_normalized < 0:
        motor.backward(abs(speed_normalized))
    else:
        motor.stop()


def test_wheel(wheel_name, duration=2):
    """
    Test a specific wheel by running it forward and backward.

    Args:
        wheel_name (str): 'front_left', 'front_right', 'back_left', 'back_right'
        duration (int): Duration in seconds for each direction
    """
    print(f"Testing {wheel_name} wheel...")

    control_wheel(wheel_name, 50)
    print(f"{wheel_name} spinning forward for {duration} seconds...")
    time.sleep(duration)

    control_wheel(wheel_name, 0)
    print("Stopping for 1 second...")
    time.sleep(1)

    control_wheel(wheel_name, -50)
    print(f"{wheel_name} spinning backward for {duration} seconds...")
    time.sleep(duration)

    control_wheel(wheel_name, 0)


def cleanup():
    """Stop all motors, shut down watchdog, and put both TB6612FNG chips into standby."""
    global _watchdog_running

    stop_encoder_watcher()

    _watchdog_running = False
    if _watchdog_thread:
        _watchdog_thread.join(timeout=1.0)

    stop_all()
    if _stby1:
        _stby1.off()
    if _stby2:
        _stby2.off()
    logger.info("Motors cleaned up, watchdog stopped, drivers in standby.")
