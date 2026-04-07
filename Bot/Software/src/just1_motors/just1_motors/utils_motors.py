from gpiozero import Device, Motor, OutputDevice
from gpiozero.pins.lgpio import LGPIOFactory
import time

Device.pin_factory = LGPIOFactory()

# TT encoder motors in this build are rated 6V. The unified 3S Li-Ion battery
# supplies 11.1V to the TB6612FNG motor rail. Capping PWM duty at 55% keeps
# the average motor voltage at ~6.1V (11.1V × 0.55), within motor spec.
MAX_MOTOR_SPEED = 55  # percent (0–100 scale)

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


def setup():
    """Initialize TB6612FNG driver chips and motor objects."""
    global front_left_motor, front_right_motor, back_left_motor, back_right_motor
    global _stby1, _stby2

    _stby1 = OutputDevice(tb6612_1_stby, initial_value=True)
    _stby2 = OutputDevice(tb6612_2_stby, initial_value=True)

    front_left_motor  = Motor(forward=front_left_ain1,  backward=front_left_ain2,  enable=front_left_pwma,  pwm=True)
    front_right_motor = Motor(forward=front_right_bin1, backward=front_right_bin2, enable=front_right_pwmb, pwm=True)
    back_left_motor   = Motor(forward=back_left_ain1,   backward=back_left_ain2,   enable=back_left_pwma,   pwm=True)
    back_right_motor  = Motor(forward=back_right_bin1,  backward=back_right_bin2,  enable=back_right_pwmb,  pwm=True)


def stop_all():
    """Stop all motors (STBY remains active — motors hold position briefly then coast)."""
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
                     clamped to protect 6V-rated motors from the 11.1V supply.
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
    """Stop all motors and put both TB6612FNG chips into standby (low-power)."""
    stop_all()
    if _stby1:
        _stby1.off()
    if _stby2:
        _stby2.off()
