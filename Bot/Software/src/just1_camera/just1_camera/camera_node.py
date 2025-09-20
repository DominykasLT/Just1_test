import rclpy
from rclpy.node import Node
from foxglove_msgs.msg import CompressedVideo
import subprocess
import threading
import queue

START_CODE = b"\x00\x00\x00\x01"


class CameraNode(Node):
    def __init__(self):
        super().__init__("camera_node")

        self.publisher = self.create_publisher(CompressedVideo, "camera/video_h264", 10)
        self.frame_queue = queue.Queue(maxsize=5)

        # Store SPS and PPS NAL units for inclusion with keyframes
        self.sps_nal = None
        self.pps_nal = None

        # Start rpicam-vid subprocess
        cmd = [
            "rpicam-vid",
            "-t",
            "0",
            "--inline",
            "--codec",
            "h264",
            "--width",
            "640",
            "--height",
            "480",
            "--framerate",
            "30",
            "--bitrate",
            "4000000",
            "--intra",
            "30",
            "--profile",
            "baseline",
            "-o",
            "-",
        ]
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

        # Start processing thread
        self.reader_thread = threading.Thread(target=self.read_h264_frames, daemon=True)
        self.reader_thread.start()

        # ROS timer
        self.timer = self.create_timer(1 / 30, self.timer_callback)

    def read_h264_frames(self):
        """Parse stdout from rpicam-vid into complete H.264 frames"""
        buffer = bytearray()
        while True:
            try:
                data = self.proc.stdout.read(4096)
                if not data:
                    break
                buffer.extend(data)

                # Process complete frames in the buffer
                while True:
                    start_idx = buffer.find(START_CODE)
                    if start_idx == -1:
                        break

                    next_start_idx = buffer.find(START_CODE, start_idx + 4)
                    if next_start_idx == -1:
                        break

                    nal_unit = buffer[start_idx:next_start_idx]

                    if len(nal_unit) > 5:
                        nal_type = nal_unit[4] & 0x1F

                        if nal_type == 7:  # SPS
                            self.sps_nal = nal_unit
                        elif nal_type == 8:  # PPS
                            self.pps_nal = nal_unit
                        elif nal_type == 5:  # IDR frame (keyframe)
                            complete_frame = self._create_complete_frame(nal_unit)
                            if complete_frame:
                                try:
                                    self.frame_queue.put_nowait(complete_frame)
                                except queue.Full:
                                    _ = self.frame_queue.get_nowait()
                                    self.frame_queue.put_nowait(complete_frame)
                            else:
                                # Fallback: publish IDR frame alone
                                try:
                                    self.frame_queue.put_nowait(nal_unit)
                                except queue.Full:
                                    _ = self.frame_queue.get_nowait()
                                    self.frame_queue.put_nowait(nal_unit)
                        elif nal_type == 1:  # P-frame
                            if self.sps_nal and self.pps_nal:
                                try:
                                    self.frame_queue.put_nowait(nal_unit)
                                except queue.Full:
                                    _ = self.frame_queue.get_nowait()
                                    self.frame_queue.put_nowait(nal_unit)

                    buffer = buffer[next_start_idx:]
            except Exception:
                break

    def _create_complete_frame(self, idr_nal):
        """Create a complete H.264 frame by combining SPS, PPS, and IDR NAL units"""
        if not self.sps_nal or not self.pps_nal:
            return None

        complete_frame = bytearray()
        complete_frame.extend(self.sps_nal)
        complete_frame.extend(self.pps_nal)
        complete_frame.extend(idr_nal)

        return bytes(complete_frame)

    def timer_callback(self):
        """Publish one full H.264 frame per ROS message"""
        try:
            frame = self.frame_queue.get_nowait()
        except queue.Empty:
            return

        msg = CompressedVideo()
        msg.timestamp = self.get_clock().now().to_msg()
        msg.format = "h264"
        msg.data = frame
        msg.frame_id = "camera_link"
        self.publisher.publish(msg)

    def destroy_node(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
