# Bill of Material

These are the components used to build Just1. Prices are as of April 2026, for a US based purchase.

| Item | Qty | Description | Link (as of April 2026) | Total Price (as of April 2026) | Why |
| --- | --- | --- | --- | --- | --- |
| Control Unit | 1 | Raspberry Pi 5 8GB | [Link](https://www.adafruit.com/product/5813) | $80 | Pi 5 brings a significantly faster CPU and better PCIe/IO over Pi 4. 8GB headroom is useful for running on-device ML inference alongside ROS. |
| Micro SD card | 1 | 32GB Micro SD Card (A2 rated) | [Link](https://www.amazon.com/dp/B0B7NTY2S6) | $8 | A2-rated card gives noticeably faster random I/O on Pi 5 boot and file access. |
| Encoder Motors | 4 | DFRobot TT Geared Motor with Encoder — FIT0450 (I-shape, 6V 160RPM 120:1) | [Link](https://www.dfrobot.com/product-1457.html) | $30 (~$7.50 each) | TT form-factor DC geared motor with built-in quadrature hall effect encoder (ENC_A + ENC_B). Copper D-shaped output shaft fits standard 60mm mecanum wheel hubs. 160 RPM at 6V. We run at 55% PWM (≈6.1V average) to keep within the 6V motor rating. Running current: ~0.17A no-load, ~0.5A loaded. Stall current: 2.8A — above TB6612FNG 1.2A continuous rating, but below its 3.2A peak; avoid sustained stall (software watchdog in `utils_motors.py`). |
| Mecanum Wheels | 1 | 60mm Mecanum Wheel Set for TT Motor (2× left + 2× right, includes wheel hub adapters) | [Link](https://www.amazon.com/dp/B0DK3P3Q3W) | $15 | Rubber-coated 60mm mecanum wheels with TT D-shaft hub adapters included. 2 left-hand + 2 right-hand wheels required for correct holonomic drive (strafe, rotate-in-place, diagonal). |
| Motor Drivers | 2 | TB6612FNG Dual Motor Driver | [Link](https://www.amazon.com/Dual-Motor-Driver-Module-TB6612FNG/dp/B08J3S6G2N) | $9 (3-pack) | MOSFET-based dual H-bridge, 1.2A/channel continuous (3.2A peak). Replaces L298N: no voltage drop waste, no extra logic supply needed, operates directly from Pi 3.3V GPIO. 15V max motor supply — our 11.1V 3S battery is well within spec. 2 modules × 2 channels each = 4 motors total. |
| AI Camera | 1 | Raspberry Pi AI Camera (Sony IMX500) | [Link](https://www.adafruit.com/product/5906) | $70 | On-sensor neural network inference via the IMX500 — object detection runs on the camera chip itself, offloading the Pi. |
| Camera Mount | 1 | 2-Axis Pan/Tilt Servo Bracket Kit (2× SG90 servos included) | [Link](https://www.amazon.com/dp/B07GBGPX3Z) | $12 | Allows the AI camera to pan (left/right) and tilt (up/down) independently. Servos are driven via PCA9685 I2C PWM driver. |
| Servo Driver | 1 | PCA9685 16-Channel 12-bit PWM/Servo Driver | [Link](https://www.amazon.com/dp/B0GKZR3WSG) | $8 (4-pack) | I2C servo driver (ESP32 GPIO 21 SDA / GPIO 22 SCL). Has a dedicated V+ servo power rail (separate from logic VCC) with a built-in capacitor pad — this properly isolates the SG90 stall current spikes from the 5V logic rail shared with the Pi, preventing brownouts. Drives both pan (ch 0) and tilt (ch 1) servos. |
| Lidar | 1 | LD19 Lidar | [Link](https://www.amazon.com/dp/B0B1QCV4XR) | $70 | Relatively cheap 2D Lidar for navigation and obstacle avoidance. |
| IMU | 1 | MPU6050 IMU | [Link](https://www.amazon.com/dp/B00LP25V1A) | $3 | 6-axis gyro+accelerometer for orientation feedback. |
| Wake Controller | 1 | ESP32 DevKit C (38-pin) | [Link](https://www.amazon.com/dp/B08D5ZD528) | $10 | Handles smart wake-up (Pi has no Wake-on-LAN). Stays in deep-sleep (μA draw), wakes on BLE/button/timer, then triggers the high-side switch to power the Pi. Controls pan/tilt servos via PCA9685 over I2C. |
| Pi 5V Switch | 1 | High-Side Load Switch Module (P-channel MOSFET, e.g. IRLML6402-based) | [Link](https://www.amazon.com/dp/B0D3PGWVCD) | $8 | ESP32 GPIO 32 drives the switch gate; the high-side switch opens/closes the 5V rail to the Pi. A high-side configuration is strictly required to preserve the shared system ground — a low-side N-channel MOSFET (e.g. IRF520) would break the Pi's ground reference and cause dangerous ground loops through GPIO data lines connected to the ESP32 and motor drivers. |
| Pi Power | 1 | DC-DC Buck Converter 5V/8A (40W) — XL4016 | [Link](https://www.amazon.com/dp/B08FMWM1VN) | $12 | Steps down the 3S battery voltage (9.6–12.6V) to a stable 5V/8A rail. Pi 5 can draw up to 5A under load; SG90 servos share this rail and can draw up to 700mA stall — a 40W budget is required. Do not substitute with LM2596(HV) which is rated 3A and will overheat under Pi 5 + servo load. |
| Main Battery | 1 | 3S Li-Ion 18650 Pack — 11.1V 6000mAh with built-in BMS | [Link](https://www.amazon.com/dp/B0BSNC5SGZ) | $35 | Single power source for the whole robot. 11.1V feeds the TB6612FNG motor drivers directly (within their 4.5–15V range). The buck converter steps it down to 5V/8A for the Pi. BMS handles cell balancing, over-discharge, and short-circuit protection. |
| Chassis | 1 | See 3D models | | $0 if you find a Robotic club or library with 3D printers! | |
| **Total** | | | | **~$370** | |


<br>
<br>

Here are a bunch of useful screws and wires.
| Item | Qty | Link (as of April 2026) | Total Price (as of April 2026) | Why |
| --- | --- | --- | --- | --- |
| Female Female Jumper Wires | 1 | [Link](https://www.amazon.com/dp/B09FP5PW45) | $7 | Connect Pi to Motor Drivers, ESP32, and sensors. |
| Various 2.5 Screws | 1 | [Link](https://www.amazon.com/dp/B0CRRCYZHS) | $10 | Screw Pi, Motor Drivers, ESP32 to chassis. |
| Hex Pylons | 1 | [Link](https://www.amazon.com/dp/B01EYQ1TGE) | $10 | Separate both layers of 3D model. |
| On/Off Switch | 1 | [Link](https://www.amazon.com/dp/B0C53HD8J7) | $6 | Hard power cut for the whole battery rail when storing the robot. |
| XT60 Connector + 18AWG wire | 1 | [Link](https://www.amazon.com/TMH-Upgrade-Female-Connectors-Battery/dp/B0F53RRR94) | $8 | Robust connection between the 3S pack and the power distribution point. |
| 74LVC125A Quad Level Shifter | 2 | [Link](https://www.amazon.com/dp/B07VNQX59J) | $6 (5-pack) | Shifts encoder signal lines from 5V (motor encoder VCC) down to 3.3V (Pi 5 GPIO safe input). Each chip has 4 channels; 2 chips cover all 8 encoder signals (ENC_A + ENC_B × 4 motors). The LVC variant is specifically designed to accept 5V input while powered from 3.3V — do not use AHCT or HC variants, which do not support overvoltage on input when VCC is 3.3V. |
| Flexible CSI Camera Ribbon Cable — 20cm | 1 | [Link](https://www.amazon.com/dp/B07SX8NWRT) | $6 | The standard short CSI ribbon would fatigue and break under repeated pan/tilt movement. A 20cm flexible extension provides enough slack for ±90° pan and ±45° tilt without stressing the connector. Route the cable along the tilt axis rotation point. |

You'll also need standard wires, soldering iron, and a 3S Li-Ion balance charger.

---

See `Architecture/` for full power and system architecture diagrams.
