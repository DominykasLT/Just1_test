import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from just1_interface.msg import WheelSpeeds
from just1_motors.utils_motors import setup, stop_all, control_wheel, cleanup
import math
import time


class AutonomousMotorController(Node):
    """
    Listens to the /cmd_vel topic and publishes the wheel speeds to the wheel_speeds topic.
    Controls a mecanum drive robot with 4 wheels.
    """

    def __init__(self):
        super().__init__("autonomous_motor_controller")

        # Initialize motor hardware
        setup()

        # Robot parameters for mecanum drive
        self.wheel_radius = 0.03  # meters (30mm radius)
        self.wheel_separation_x = (
            0.11  # meters (distance between front and back wheels)
        )
        self.wheel_separation_y = (
            0.13  # meters (distance between left and right wheels)
        )
        # The FIT0450 motor is rated 160 RPM at 6V. The battery supplies 12.8V,
        # so at 100% duty the motor would theoretically spin at ~341 RPM
        # (160 × 12.8/6). We set max_rpm to this value so that rpm_to_percent
        # produces a duty cycle that maps linearly to actual motor speed.
        # The safety clamp in control_wheel (MAX_MOTOR_SPEED=47%) then caps
        # effective voltage at ~6V / 160 RPM. This keeps Nav2's velocity
        # commands proportional to real motor output across the usable range.
        self.max_rpm = 341  # 160 RPM × (12.8V / 6V) — theoretical RPM at 100% duty

        # Create subscriber for cmd_vel
        self.cmd_vel_subscription = self.create_subscription(
            Twist, "cmd_vel", self.cmd_vel_callback, 10
        )

        # Create publisher for wheel speeds
        self.wheel_speeds_publisher = self.create_publisher(
            WheelSpeeds, "wheel_speeds", 10
        )

        # Watchdog: timestamp of the last received cmd_vel message.
        # If no message arrives within CMD_VEL_TIMEOUT_SEC, stop_all() is called.
        # This prevents the robot from running indefinitely if Nav2 crashes or
        # the final zero-velocity message is dropped over the network.
        self._CMD_VEL_TIMEOUT_SEC = 0.5
        self._last_cmd_vel_time = self.get_clock().now()
        self._watchdog_timer = self.create_timer(
            0.1, self._watchdog_callback  # runs at 10 Hz
        )

        self.get_logger().info("Autonomous Motor Controller initialized")

    def cmd_vel_callback(self, msg):
        """
        Callback function for cmd_vel messages.
        Converts linear and angular velocities to wheel speeds for mecanum drive.
        """
        # Reset watchdog timestamp on every received message.
        self._last_cmd_vel_time = self.get_clock().now()

        # Extract velocities
        linear_x = msg.linear.x
        linear_y = msg.linear.y
        angular_z = msg.angular.z

        # Calculate wheel speeds for mecanum drive (in RPM)
        wheel_speeds = self.calculate_mecanum_wheel_speeds(
            linear_x, linear_y, angular_z
        )

        # Convert wheel speeds to percent based on max RPM
        wheel_speeds_percent = self.rpm_to_percent(wheel_speeds)

        wheel_speeds_msg = WheelSpeeds()
        wheel_speeds_msg.front_left = float(wheel_speeds_percent["front_left"])
        wheel_speeds_msg.front_right = float(wheel_speeds_percent["front_right"])
        wheel_speeds_msg.back_left = float(wheel_speeds_percent["back_left"])
        wheel_speeds_msg.back_right = float(wheel_speeds_percent["back_right"])

        self.wheel_speeds_publisher.publish(wheel_speeds_msg)

        self.control_motors(wheel_speeds_percent)

    def _watchdog_callback(self):
        """
        Called at 10 Hz. Stops all motors if no /cmd_vel has been received
        within CMD_VEL_TIMEOUT_SEC. Prevents indefinite motor runaway when
        Nav2 crashes, the goal is reached without a final zero-velocity message,
        or the operator disconnects.
        """
        elapsed = (
            self.get_clock().now() - self._last_cmd_vel_time
        ).nanoseconds / 1e9
        if elapsed > self._CMD_VEL_TIMEOUT_SEC:
            stop_all()

    def calculate_mecanum_wheel_speeds(self, linear_x, linear_y, angular_z):
        """
        Calculate wheel speeds for mecanum drive based on desired velocities.

        Args:
            linear_x: Forward/backward velocity (m/s)
            linear_y: Left/right velocity (m/s)
            angular_z: Rotational velocity (rad/s)

        Returns:
            dict: Wheel speeds for each wheel with the speed in RPM
        """
        # Mecanum wheel speed equations
        # Front left: vx - vy - (Lx + Ly) * ω
        # Front right: vx + vy + (Lx + Ly) * ω
        # Back left: vx + vy - (Lx + Ly) * ω
        # Back right: vx - vy + (Lx + Ly) * ω

        Lx = self.wheel_separation_x / 2.0
        Ly = self.wheel_separation_y / 2.0

        front_left = linear_x - linear_y - (Lx + Ly) * angular_z
        front_right = linear_x + linear_y + (Lx + Ly) * angular_z
        back_left = linear_x + linear_y - (Lx + Ly) * angular_z
        back_right = linear_x - linear_y + (Lx + Ly) * angular_z

        # Convert from m/s to RPM (approximate)
        # RPM = (m/s) / (2 * π * radius) * 60
        rpm_factor = 60.0 / (2.0 * math.pi * self.wheel_radius)

        wheel_speeds = {
            "front_left": front_left * rpm_factor,
            "front_right": front_right * rpm_factor,
            "back_left": back_left * rpm_factor,
            "back_right": back_right * rpm_factor,
        }

        return wheel_speeds

    def rpm_to_percent(self, wheel_speeds):
        """
        Convert wheel speeds from RPM to percent based on max RPM.
        Args:
            wheel_speeds: dict containing speeds for each wheel (in RPM)
        Returns:
            dict: Wheel speeds as percentages (-100.0 to 100.0)
        """
        percent_speeds = {}
        for wheel_name, rpm in wheel_speeds.items():
            percentage = (rpm / self.max_rpm) * 100.0
            percentage = max(-100.0, min(100.0, percentage))
            percent_speeds[wheel_name] = percentage
        return percent_speeds

    def control_motors(self, wheel_speeds):
        """
        Control motors based on calculated wheel speeds.

        Args:
            wheel_speeds: dict containing speeds for each wheel (in percent)
        """
        for wheel_name, percentage in wheel_speeds.items():
            control_wheel(wheel_name, int(round(percentage)))

    def on_shutdown(self):
        """
        Cleanup when node is shutting down.
        """
        self.get_logger().info("Shutting down Autonomous Motor Controller")
        stop_all()
        cleanup()


def main(args=None):
    rclpy.init(args=args)

    autonomous_controller = AutonomousMotorController()

    try:
        rclpy.spin(autonomous_controller)
    except KeyboardInterrupt:
        pass
    finally:
        autonomous_controller.on_shutdown()
        autonomous_controller.destroy_node()


if __name__ == "__main__":
    main()
