import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from just1_interface.msg import WheelSpeeds
from just1_motors.utils_motors import setup, stop_all, control_wheel, cleanup
import math


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
        self.max_rpm = 165  # Maximum wheel RPM

        # Create subscriber for cmd_vel
        self.cmd_vel_subscription = self.create_subscription(
            Twist, "cmd_vel", self.cmd_vel_callback, 10
        )

        # Create publisher for wheel speeds
        self.wheel_speeds_publisher = self.create_publisher(
            WheelSpeeds, "wheel_speeds", 10
        )

        self.get_logger().info("Autonomous Motor Controller initialized")

    def cmd_vel_callback(self, msg):
        """
        Callback function for cmd_vel messages.
        Converts linear and angular velocities to wheel speeds for mecanum drive.
        """
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

        # Publish wheel speeds as RPM
        wheel_speeds_msg = WheelSpeeds()
        wheel_speeds_msg.front_left = float(wheel_speeds["front_left"])
        wheel_speeds_msg.front_right = float(wheel_speeds["front_right"])
        wheel_speeds_msg.back_left = float(wheel_speeds["back_left"])
        wheel_speeds_msg.back_right = float(wheel_speeds["back_right"])

        self.wheel_speeds_publisher.publish(wheel_speeds_msg)

        # Control motors with percent speeds
        self.control_motors(wheel_speeds_percent)

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
            dict: Wheel speeds as percentages (-100 to 100)
        """
        percent_speeds = {}
        for wheel_name, rpm in wheel_speeds.items():
            # Convert RPM to percentage of max RPM, clamped to [-100, 100]
            percentage = (rpm / self.max_rpm) * 100
            percentage = max(-100, min(100, percentage))  # Clamp to [-100, 100]
            percent_speeds[wheel_name] = int(percentage)
        return percent_speeds

    def control_motors(self, wheel_speeds):
        """
        Control motors based on calculated wheel speeds.

        Args:
            wheel_speeds: dict containing speeds for each wheel (in percent)
        """
        for wheel_name, percentage in wheel_speeds.items():
            control_wheel(wheel_name, percentage)

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
