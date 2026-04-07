# Power Architecture

## Overview

Just1 uses a single 3S Li-Ion 18650 pack (11.1V nominal, 6000mAh) as the sole power source for the entire robot. A single battery eliminates the separate Pi power bank and the old 6×AA motor pack, reduces failure points, and simplifies charging (one charger, one connector).

## Power Distribution Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  3S Li-Ion Pack (11.1V nominal, 9.6–12.6V range)           │
│  Built-in BMS: over-discharge, short-circuit, cell balance  │
└──────────────────┬──────────────────────────────────────────┘
                   │ XT60 connector → main bus (16AWG)
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌───────────────┐   ┌──────────────────────────────────┐
│  2× TB6612FNG │   │  DC-DC Buck Converter            │
│  Motor Driver │   │  Input: 9.6–12.6V                │
│               │   │  Output: 5V / 8A (40W)           │
│  VM: 11.1V    │   │  (e.g. XL4016 or 8A UBEC)        │
│  (within      │   └─────────────┬────────────────────┘
│  4.5–15V spec)│                 │ 5V rail
│               │      ┌──────────┴─────────────┐
│  4× Encoder   │      │                        │
│  TT Motors    │      ▼                        ▼
└───────────────┘  ┌──────────────┐    ┌─────────────────┐
                   │  High-Side   │    │  ESP32 DevKit   │
                   │  Load Switch │    │  (via 3.3V LDO  │
                   │  or 5V Relay │    │  from 5V rail)  │
                   └──────┬───────┘    └────────┬────────┘
                          │                     │
                          │ controlled by ESP32 │ GPIO control signal
                          │                     │
                          ▼                     │
                   ┌──────────────┐◄────────────┘
                   │ Raspberry    │
                   │ Pi 5 (8GB)   │
                   │              │
                   │ 5V / up to   │
                   │ 5A via USB-C │
                   └──────────────┘
```

## Rail Summary

| Rail | Voltage | Source | Powers |
| --- | --- | --- | --- |
| Main bus | 11.1V (nom.) | 3S Li-Ion pack | TB6612FNG VM input, Buck converter input |
| Motor rail | 11.1V (nom.) | Main bus → TB6612FNG | 4× TT encoder motors |
| 5V logic rail | 5V / up to 8A | High-current DC-DC Buck (XL4016) | High-Side switch input, ESP32 (via LDO), Pi 5 (via switch), PCA9685 VCC (logic) + V+ (servo power) |
| 3.3V | 3.3V | ESP32 internal LDO (from 5V) | ESP32 logic, pan/tilt servo signal logic |

## Key Design Decisions

**Why 3S (11.1V) and not 2S (7.4V)?**
The TB6612FNG accepts 4.5–15V on the motor supply. Running motors closer to their 6V TT-motor rating is done via PWM duty cycle (e.g., 50% duty at 11.1V ≈ 5.5V average). A 3S pack gives more capacity and headroom for the buck converter, which needs at least 7V input to deliver stable 5V / 8A output.

**Why not power motors from a separate 6V rail?**
Adding a second high-current buck converter adds cost, board space, and weight. PWM-based speed control through the TB6612FNG is the standard approach for TT-scale robots and provides adequate precision when combined with encoder feedback.

**Buck Converter and Servo Safety:**
The Pi 5 alone can draw up to 5A. Therefore, a high-current buck converter like the XL4016 (rated up to 8A) is strictly required — do not use an LM2596(HV) as it will overheat. The pan/tilt SG90 servos are powered through a PCA9685 servo driver: the PCA9685 has a dedicated V+ servo power pin that is electrically isolated from its VCC logic pin. Both V+ and VCC connect to the shared 5V rail, but the servo stall current (up to 700mA per servo) is sourced through the V+ path and the PCA9685's internal output stage — inductive transients from the servo motors do not propagate back to the logic rail or the Pi.

**ESP32 standby behavior and Power Switching:**
The ESP32 keeps the High-Side Load Switch (or Relay) disengaged (Pi OFF) when the robot is idle. It draws ~10μA in deep-sleep. On wake trigger (BLE command, RTC timer, or physical button), it signals the switch to close, and the Pi 5V rail is energized. **Crucial Note:** A High-Side switch or standard relay is strictly required to preserve the shared system ground. Using a standard low-side N-Channel MOSFET would break the Pi's grounding and cause it to dangerously source ground loops through its GPIO data lines connected to the ESP32 and motor drivers.

**BMS protection:**
The built-in BMS in the 3S pack prevents over-discharge (below ~9.6V), over-charge, cell imbalance, and short-circuit faults. The on/off switch on the main bus provides a hard disconnect for storage.

---

## LiFePO4 as a Safer Alternative

If safety and longevity are a priority (especially when running the robot indoors or near people), a **4S LiFePO4 pack** is a drop-in upgrade.

### Voltage Comparison

| Property | 3S Li-Ion (current) | 4S LiFePO4 (alternative) |
| --- | --- | --- |
| Nominal voltage | 11.1V | 12.8V |
| Full charge | 12.6V | 14.4V |
| Minimum (BMS cutoff) | 9.6V | 11.2V |
| TB6612FNG VM max | 15V — ✓ safe | 15V — ✓ safe (14.4V max) |
| Buck converter input | ✓ fine | ✓ fine |
| Motor PWM cap needed | 55% max (6V avg) | 47% max (6V avg on 12.8V) |

> If switching to LiFePO4, update `MAX_MOTOR_SPEED` in `utils_motors.py` from `55` to `47`.

### Why LiFePO4 is Safer

- **No thermal runaway.** LiFePO4 cells do not catch fire or explode if punctured, shorted, or overcharged. Li-Ion can enter thermal runaway under the same conditions.
- **More stable voltage curve.** The discharge curve is nearly flat — motors and the buck converter see a more consistent input voltage throughout the battery life.
- **Longer cycle life.** 2000+ full charge cycles vs. 300–500 for standard Li-Ion 18650. The battery lasts years of daily use.
- **Operates in wider temperature range.** Better performance in cold environments.

### Trade-offs

- Heavier for the same capacity (lower energy density: ~120 Wh/kg vs ~250 Wh/kg for Li-Ion).
- Slightly more expensive upfront.
- Requires a LiFePO4-specific charger (cannot use a standard Li-Ion balance charger).

### Recommendation

Use **LiFePO4** if the robot will be used around people, left unattended while charging, or you want a longer service life. Use **Li-Ion** if weight and runtime-per-gram are the priority.
