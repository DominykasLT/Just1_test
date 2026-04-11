# System Architecture

## Hardware Block Diagram

```
                         ┌─────────────────────────────────────────────────────────────┐
                         │                    RASPBERRY PI 5 (8GB)                     │
                         │                                                              │
                         │  ┌──────────────┐  ┌───────────┐  ┌──────────────────────┐ │
                         │  │  ROS2 Stack  │  │  Nav2     │  │  just1_camera node   │ │
                         │  │  (Ubuntu)    │  │  (SLAM /  │  │  (AI inference via   │ │
                         │  │             │  │  Autonomy)│  │  IMX500 CSI stream)  │ │
                         │  └──────┬───────┘  └─────┬─────┘  └──────────┬───────────┘ │
                         │         │                 │                    │              │
                         │  ┌──────▼─────────────────▼────────────────── ▼───────────┐ │
                         │  │                  GPIO / Serial / I2C / CSI Bus          │ │
                         │  └──┬──────┬─────────┬────────┬────────┬──────────────────┘ │
                         └─────│──────│─────────│────────│────────│────────────────────┘
                               │      │         │        │        │
              ┌────────────────┘      │         │        │        └──────────────────┐
              │                       │         │        │                           │
              ▼                       ▼         ▼        ▼                           ▼
  ┌───────────────────┐   ┌──────────────┐  ┌──────┐  ┌─────────────────┐  ┌────────────────┐
  │  2× TB6612FNG     │   │  LD19 Lidar  │  │IMU   │  │ ESP32 DevKit    │  │ AI Camera      │
  │  Motor Drivers    │   │  (UART/USB)  │  │MPU   │  │                 │  │ (CSI-2, IMX500)│
  │                   │   │              │  │6050  │  │ • Wake-up ctrl  │  │                │
  │  AIN1/2, BIN1/2,  │   │  360° scan   │  │(I2C) │  │ • I2C→ PCA9685  │  │ On-sensor      │
  │  PWMA/B per chip  │   │  10m range   │  │      │  │ • Encoder read  │  │ object detect  │
  │  STBY shared      │   │  12Hz scan   │  │      │  │                 │  │                │
  └────────┬──────────┘   └──────────────┘  └──────┘  └────────┬────────┘  └───────┬────────┘
           │                                                     │ I2C               │
  ┌────────▼──────────┐                                 ┌────────▼────────┐  ┌───────▼────────┐
  │  4× TT Encoder    │                                 │  PCA9685        │  │  Camera angle  │
  │  Motors           │                                 │  Servo Driver   │  │  follows target│
  │                   │                                 │  (I2C, 0x40)    │  │                │
  │  Motor+, Motor-   │                                 │  V+: 5V rail    │  │                │
  │  ENC_A, ENC_B     │                                 │  Ch0: Pan SG90  │  │                │
  │  per motor (×4)   │                                 │  Ch1: Tilt SG90 │  │                │
  └────────┬──────────┘                                 └────────┬────────┘  └────────────────┘
           │                                                      │
  ┌────────▼──────────┐                                 ┌────────▼────────┐
  │ 60mm Mecanum      │                                 │  Pan/Tilt       │
  │ Wheels (×4)       │                                 │  Servo Mount    │
  │                   │                                 │  (SG90 × 2)    │
  │ Omnidirectional   │                                 │                 │
  │ drive (strafe,    │                                 │  Pan: ±90°      │
  │ rotate in place,  │                                 │  Tilt: ±45°     │
  │ diagonal)         │                                 └─────────────────┘
  └───────────────────┘
```

---

## Component Connections

### Raspberry Pi 5 ↔ TB6612FNG (Motor Control)

Each TB6612FNG controls 2 motors. 2 chips → 4 motors total.

| Signal | Pi GPIO | TB6612FNG #1 | TB6612FNG #2 |
| --- | --- | --- | --- |
| Motor FL AIN1 | GPIO 17 | AIN1 | — |
| Motor FL AIN2 | GPIO 22 | AIN2 | — |
| Motor FL PWM | GPIO 18 (hw PWM1_0) | PWMA | — |
| Motor FR BIN1 | GPIO 23 | BIN1 | — |
| Motor FR BIN2 | GPIO 24 | BIN2 | — |
| Motor FR PWM | GPIO 13 (hw PWM0_1) | PWMB | — |
| Chip #1 Standby | GPIO 25 | STBY | — |
| Motor RL AIN1 | GPIO 27 | — | AIN1 |
| Motor RL AIN2 | GPIO 10 | — | AIN2 |
| Motor RL PWM | GPIO 12 (hw PWM0_0) | — | PWMA |
| Motor RR BIN1 | GPIO 9 | — | BIN1 |
| Motor RR BIN2 | GPIO 11 | — | BIN2 |
| Motor RR PWM | GPIO 19 (hw PWM1_1) | — | PWMB |
| Chip #2 Standby | GPIO 8 | — | STBY |
| Logic supply (VCC) | Pi 3.3V pin | VCC | VCC |
| Motor supply (VM) | Output of 6.0V Motor Buck | VM | VM |
| Ground | GND | GND | GND |

> Pi 5 has exactly 4 hardware PWM channels (GPIO 12, 13, 18, 19) — all 4 are used for motor speed control.
> STBY: pulled HIGH by `setup()` in `utils_motors.py`, pulled LOW by `cleanup()` to enter low-power standby.
> These pin assignments are implemented in `just1_motors/utils_motors.py`.

---

### Raspberry Pi 5 ↔ Encoder Signals (via 74LVC125A Level Shifter)

Each TT encoder motor has 2 quadrature encoder output signals (ENC_A, ENC_B). These signals must be level-shifted from 5V (encoder VCC) to 3.3V (Pi 5 GPIO max) before reaching the Pi.

**Level shifter wiring (74LVC125A):**

```
Encoder motor                74LVC125A               Pi 5 GPIO
(5V signal out) ──► A pin ──► Y pin (3.3V out) ──► GPIO input pin
                    OE pin pulled to GND (always enabled)
                    VCC = 3.3V (from Pi 3.3V rail)
                    GND = common ground
```

Two 74LVC125A chips needed: each has 4 channels, 4 motors × 2 signals = 8 total.

| Motor | ENC_A (Pi GPIO) | ENC_B (Pi GPIO) |
| --- | --- | --- |
| Front-Left | GPIO 4 | GPIO 5 |
| Front-Right | GPIO 6 | GPIO 7 |
| Rear-Left | GPIO 16 | GPIO 20 |
| Rear-Right | GPIO 21 | GPIO 26 |

> The LVC variant of the 125 buffer is specifically designed to be overvoltage-tolerant, meaning it can safely accept 5V inputs while powered from 3.3V to step the signals down. Do not use AHCT or HC variants for step-down.

---

### Raspberry Pi 5 ↔ LD19 Lidar (SLAM / Obstacle Avoidance)

| Connection | Detail |
| --- | --- |
| Interface | USB (via USB-to-serial adapter, included with LD19) |
| Pi port | Any USB-A on Pi 5 |
| ROS2 package | `ldlidar_stl_ros2` (already in repo) |
| Topic published | `/scan` (sensor_msgs/LaserScan) |
| Scan rate | 10–12 Hz |
| Range | 0.02–12m |

---

### Raspberry Pi 5 ↔ MPU6050 IMU

| Signal | Pi GPIO | MPU6050 |
| --- | --- | --- |
| I2C SDA | GPIO 2 (SDA1) | SDA |
| I2C SCL | GPIO 3 (SCL1) | SCL |
| Power | Pi 3.3V | VCC |
| Ground | GND | GND |
| I2C address | 0x68 (AD0 low) | — |

---

### Raspberry Pi 5 ↔ AI Camera (Sony IMX500)

| Connection | Detail |
| --- | --- |
| Interface | CSI-2 (camera ribbon cable) |
| Pi port | CAM0 or CAM1 connector on Pi 5 |
| Driver | `libcamera` + Raspberry Pi camera stack |
| IMX500 inference | Runs directly on sensor chip, result streamed via CSI |
| Resolution | Up to 12MP (AI inference typically runs at lower resolution crop) |
| ROS2 node | `just1_camera` — subscribes to libcamera, publishes `/camera/image_raw` |

---

### ESP32 DevKit ↔ Raspberry Pi 5 (Wake + Coordination)

| Signal | ESP32 Pin | Destination | Purpose |
| --- | --- | --- | --- |
| Relay Control | GPIO 32 | High-Side Relay coil control | HIGH = Pi powered ON, LOW = Pi powered OFF |
| UART TX | GPIO 17 (U2TXD) | Pi GPIO 15 (RXD) | Send encoder ticks / status to Pi (optional) |
| UART RX | GPIO 16 (U2RXD) | Pi GPIO 14 (TXD) | Receive pan/tilt commands from Pi (optional) |
| I2C SDA | GPIO 21 | PCA9685 SDA | I2C servo driver — pan/tilt PWM commands |
| I2C SCL | GPIO 22 | PCA9685 SCL | I2C servo driver clock |
| Wake button | GPIO 33 | Physical button → GND | Wakes ESP32 from deep-sleep |
| Power | 5V rail (via LDO) | — | ESP32 3.3V internal reg |

**Wake-up sequence:**
1. ESP32 enters deep-sleep → draws ~10μA. (Its UART TX pin is configured as a high-impedance input before sleep to prevent back-powering the Pi.)
2. Wake trigger fires (BLE packet, button press, or RTC timer)
3. ESP32 pulls relay control pin HIGH
4. Pi 5V rail energizes → Pi boots. (ESP32 keeps UART TX as a high-impedance input during this phase to avoid pushing 3.3V into the unpowered Pi RX pin.)
5. Pi completes boot and signals ESP32 over UART that it is ready
6. ESP32 configures its UART TX pin as an output and begins sending servo commands to PCA9685 over I2C and forwarding data to Pi over UART.

**Shutdown sequence:**
1. Pi sends UART shutdown signal to ESP32
2. Pi runs `sudo shutdown -h now`
3. After Pi GPIO goes low (confirms shutdown), ESP32 immediately reconfigures its UART TX pin as a high-impedance input to prevent back-powering.
4. ESP32 pulls relay control pin LOW
5. ESP32 enters deep-sleep

---

### ESP32 ↔ PCA9685 (I2C Servo Driver)

| Signal | ESP32 Pin | PCA9685 Pin | Notes |
| --- | --- | --- | --- |
| I2C SDA | GPIO 21 | SDA | I2C data — default ESP32 I2C bus |
| I2C SCL | GPIO 22 | SCL | I2C clock |
| Logic power | **3.3V** output | **VCC** | **Must be 3.3V from ESP32**, not 5V. The PCA9685 has 10 kΩ I2C pull-up resistors tied to VCC; if VCC = 5V, SDA/SCL are pulled to 5V and will over-voltage the ESP32 GPIO inputs (3.3V max), causing hardware damage. |
| Servo power | 5V rail (buck) | V+ | Dedicated servo motor power rail on PCA9685, isolated from VCC logic. Sources up to 1.4A stall for 2× SG90. |
| Ground | GND | GND | Common ground |

> PCA9685 default I2C address: **0x40** (all address pins low). Up to 62 boards can be chained on one I2C bus.
> **VCC** (logic) is wired to **ESP32 3.3V**; **V+** (servo motor power) is wired to the **5V buck rail**. The PCA9685 internally isolates V+ from VCC so SG90 stall current spikes do not propagate to the logic rail or Pi. Keeping VCC at 3.3V ensures I2C pull-ups hold SDA/SCL at a safe level for the ESP32.

### PCA9685 ↔ Pan/Tilt Servo Mount

| Channel | Component | Signal spec |
| --- | --- | --- |
| Ch 0 | Pan servo (SG90) | 50Hz PWM — 1ms = −90°, 1.5ms = 0°, 2ms = +90° |
| Ch 1 | Tilt servo (SG90) | 50Hz PWM — same spec; mechanically limited to ±45° in firmware to protect CSI ribbon |

| Power | Source | Notes |
| --- | --- | --- |
| Servo VCC (V+) | PCA9685 V+ → 5V rail | SG90 rated 4.8–6V; 5V rail is within spec |
| Servo GND | GND | Common ground through PCA9685 |

> SG90 draws up to 700mA stall per servo. Power is sourced through the PCA9685 V+ pin, not from ESP32 GPIO or VCC — ESP32 3.3V output pin is rated 50mA and cannot source servo current.

---

## Software / ROS2 Node Map

```
[Joystick Controller]──────►[just1_joystick_driver]──────►/joy  (manual)
                                                             │
[LD19 Lidar]───────────────►[ldlidar_stl_ros2]────────────►/scan
         │                                                   │
         └────────────►[sync + icp_odometry (rtabmap_odom)]──►/odom ──►[Nav2 Stack]
                              ▲                                │
[MPU6050 IMU]──►[just1_imu]───┘                                │
                                                              ▼
[AI Camera (IMX500)]────────►[just1_camera]──────────────►/camera/...   Autonomous nav
                                                             │          + SLAM mapping
[TB6612FNG + TT motors]────►[just1_motors]◄────────────────/cmd_vel
(encoders on Pi GPIO → `encoder_watcher` ENC_A edges → `feed_watchdog`; full quadrature /odom from wheels not implemented)
```

> Motor control: `just1_motors` (`manual_controller_node` / `autonomous_controller_node`) converts `/cmd_vel` (autonomous) or joystick input (manual) to per-wheel PWM and direction on the TB6612FNG. Encoder **ENC_A** lines (GPIO 4, 6, 16, 21) are read with **gpiozero + lgpio** (`encoder_watcher.py`) and call `feed_watchdog()` so the stall watchdog can detect blocked wheels. A **stall latch** blocks PWM after a trip until that wheel receives a zero command or an encoder edge clears the latch (prevents `/cmd_vel` streams from re-arming stall). **Odometry** for navigation remains **lidar + IMU** (`icp_odometry` in bringup), not wheel encoders.

---

## GPIO Pin Allocation Summary (Pi 5)

Motor control and STBY pin assignments match `just1_motors/utils_motors.py`. Encoder **ENC_A** pins are opened in `just1_motors/encoder_watcher.py` (same process as motor nodes). No conflicts between motor control, encoder, and communication pins.

| GPIO | Function | Connected To |
| --- | --- | --- |
| 2 | I2C SDA | MPU6050 SDA |
| 3 | I2C SCL | MPU6050 SCL |
| 4 | Encoder FL-A | 74LVC125A Y → Motor FL ENC_A |
| 5 | Encoder FL-B | 74LVC125A Y → Motor FL ENC_B |
| 6 | Encoder FR-A | 74LVC125A Y → Motor FR ENC_A |
| 7 | Encoder FR-B | 74LVC125A Y → Motor FR ENC_B |
| 8 | TB6612 #2 STBY | TB6612FNG #2 STBY |
| 9 | TB6612 #2 BIN1 | TB6612FNG #2 BIN1 (RR direction) |
| 10 | TB6612 #2 AIN2 | TB6612FNG #2 AIN2 (RL direction) |
| 11 | TB6612 #2 BIN2 | TB6612FNG #2 BIN2 (RR direction) |
| 12 | PWM0_0 (hw) | TB6612FNG #2 PWMA (RL speed) |
| 13 | PWM0_1 (hw) | TB6612FNG #1 PWMB (FR speed) |
| 14 | UART TXD | ESP32 RX (GPIO 16) |
| 15 | UART RXD | ESP32 TX (GPIO 17) |
| 16 | Encoder RL-A | 74LVC125A Y → Motor RL ENC_A |
| 17 | TB6612 #1 AIN1 | TB6612FNG #1 AIN1 (FL direction) |
| 18 | PWM1_0 (hw) | TB6612FNG #1 PWMA (FL speed) |
| 19 | PWM1_1 (hw) | TB6612FNG #2 PWMB (RR speed) |
| 20 | Encoder RL-B | 74LVC125A Y → Motor RL ENC_B |
| 21 | Encoder RR-A | 74LVC125A Y → Motor RR ENC_A |
| 22 | TB6612 #1 AIN2 | TB6612FNG #1 AIN2 (FL direction) |
| 23 | TB6612 #1 BIN1 | TB6612FNG #1 BIN1 (FR direction) |
| 24 | TB6612 #1 BIN2 | TB6612FNG #1 BIN2 (FR direction) |
| 25 | TB6612 #1 STBY | TB6612FNG #1 STBY |
| 26 | Encoder RR-B | 74LVC125A Y → Motor RR ENC_B |
| 27 | TB6612 #2 AIN1 | TB6612FNG #2 AIN1 (RL direction) |

> GPIO 8–11 are also the SPI0 pins. They are assigned to TB6612FNG #2 direction and standby here. SPI0 must remain disabled in `/boot/firmware/config.txt` (`dtparam=spi=off`) since the Lidar uses USB and no SPI device is connected.
> CSI camera uses the dedicated ribbon connector — not GPIO.
> Pan/tilt servo control is handled by the PCA9685 over **ESP32 I2C (GPIO 21 SDA / GPIO 22 SCL)** — not Pi GPIO. The Pi GPIO table above is complete as-is; no Pi pins are used for servo control.

---

## Issues and Resolutions

| Issue | Risk | Status | Resolution |
| --- | --- | --- | --- |
| Encoder signal voltage (5V vs 3.3V) | HIGH | ✅ RESOLVED | 74LVC125A quad level shifter added to BOM (2 chips, 8 channels total). LVC variant accepts 5V input while powered from 3.3V — safe for Pi 5 GPIO. |
| Motor voltage too high for TB6612 and TT motors (16.8V LiPo fully charged) | HIGH | ✅ RESOLVED | The 16.8V LiPo exceeds the 15V limit of the TB6612FNG. We added a dedicated 6.0V Buck Converter for the motor rail. Since the physical rail is 6V, the TB6612 is protected, and we can set `MAX_MOTOR_SPEED = 100` (full PWM range) in code safely. We specifically use an 8A XL4016 for this as smaller bucks (like the LM2596) will collapse under heavy TT motor stall spikes. |
| Pan/tilt cable management for CSI ribbon | MEDIUM | ✅ RESOLVED | 20cm flexible CSI extension cable added to BOM. Route cable along the tilt servo rotation axis to minimize flexion. Tilt range enforced at ±45° in ESP32 servo firmware to prevent over-twist. |
| Encoder reading accuracy under Linux RT | LOW-MEDIUM | ⚠️ NOTED | On Pi 5, prefer **gpiozero + lgpio** (same stack as motor PWM). `pigpio` is not suitable on Pi 5 (RP1 GPIO). For lowest jitter, route encoder signals to ESP32 and forward tick counts to Pi over UART (encoder ROS2 bridge). |
| Wheel encoder software on Pi | MEDIUM | ✅ RESOLVED (stall) | `encoder_watcher.py` feeds `feed_watchdog()` from ENC_A edges. Stall latch in `utils_motors.py` stops command streams from defeating the watchdog. Full quadrature odometry remains future work; navigation odometry stays lidar-based (`icp_odometry`). |
| ESP32 + Pi UART conflict during boot | LOW | ✅ RESOLVED | ESP32 UART moved to GPIO 16/17 (UART2) to avoid ESP32 ROM boot log spam on UART0. |
| Ground loop through MOSFET switch | HIGH | ✅ RESOLVED | Replaced IRF520 low-side switch with a High-Side Load Switch / Relay to maintain common system ground and prevent phantom powering the Pi via data lines. |
| Pi UART back-powering via ESP32 | HIGH | ✅ RESOLVED | If ESP32 is awake or sleeping with its UART TX driven HIGH, it will bleed 3.3V into the unpowered Pi's RX pin, powering the Pi via ESD diodes. This is mitigated by configuring the ESP32 UART TX pin as a high-impedance input prior to powering down the relay or prior to ESP32 deep sleep, and only initializing the UART TX as an output *after* the Pi boots. |
| Pi 5 power brownouts from servos | HIGH | ✅ RESOLVED | PCA9685 servo driver added. Its dedicated V+ power rail (isolated from the VCC logic pin) sources all SG90 stall current directly from the 5V bus without coupling transients back to the Pi logic supply. XL4016 8A buck converter provides headroom for Pi (5A) + both servos (700mA stall each) simultaneously. |
| TB6612FNG current limit (1.2A/ch) for TT motors | MEDIUM | ⚠️ MANAGED | DFRobot FIT0450 motors draw ~0.17A no-load, ~0.5A running, but 2.8A at stall — above TB6612FNG 1.2A continuous rating. Mitigated by hardware XL4016 8A motor buck handling the initial stall spike safely, while a software encoder-fed stall watchdog in `utils_motors.py` cuts PWM if a wheel does not produce ENC_A edges for ~500ms. |
| Drone LiPo lacks internal BMS protection | HIGH | ✅ MANAGED | A purely RC LiPo will drain to 0V and rapidly become a severe fire hazard. A BX100 RC Battery Alarm must be connected to the LiPo balance connector at all times during use. It screeches loudly if any cell drops to 3.5V, prompting manual shutdown. |
| SPI0 pins (GPIO 8–11) used for TB6612FNG #2 | LOW | ✅ ACCEPTABLE | No SPI device in this build. Disable SPI0 in device tree config. If SPI is needed in future, re-route TB6612FNG #2 direction pins to other free GPIO. |
