# Power Architecture

## Overview

Just1 uses a single 4S LiFePO4 32700 pack (12.8V nominal, 7Ah) as the sole power source for the entire robot. A single battery eliminates the need for a separate Pi power bank and a motor pack, reduces failure points, and simplifies charging (one charger, one connector). LiFePO4 chemistry eliminates thermal runaway risks and offers >1200 cycle lifespan.

## Power Distribution Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  4S LiFePO4 32700 Pack (12.8V nominal, 11.2–14.6V range)   │
│  Built-in BMS: 4S 40A balanced, over-discharge,            │
│  short-circuit, cell balance                                │
└──────────────────┬──────────────────────────────────────────┘
                   │ XT60 (red + / black −) → master switch (see Step 1) → XT60 out → optional 1→3 splitter → loads
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌───────────────┐   ┌──────────────────────────────────┐
│  2× TB6612FNG │   │  DC-DC Buck Converter            │
│  Motor Driver │   │  Input: 11.2–14.6V               │
│               │   │  Output: 5V / 8A (40W)           │
│  VM: 12.8V    │   │  (XL4016)                        │
│  (within      │   └─────────────┬────────────────────┘
│  4.5–15V spec)│                 │ BuckVout (5V rail)
│               │      ┌──────────┴──────────────────────────────┐
│  4× Encoder   │      │                                         │
│  TT Motors    │      ▼                    ▼                      │
└───────────────┘  ┌──────────────┐   ┌─────────────────┐         │
                   │ RelayCoil+   │   │ Esp32VIN        │         │
                   │ Pi5V path    │   │ (always on 5V)  │         │
                   │ (switched)   │   └────────┬────────┘         │
                   └──────┬───────┘            │                  │
                          │    ESP32 GPIO     │                  │
                          │    closes relay   │                  │
                          ▼                   │                  │
                   ┌──────────────┐◄──────────┘                  │
                   │ Pi5V_USB-C   │   (common GND; not in series │
                   │ via relay NO │    with ESP32 supply)         │
                   └──────────────┘                               │
```

**5V topology:** **ESP32 VIN** and **relay module VCC** tie directly to **buck VOUT+**. Only the **Raspberry Pi 5V** path runs **through the relay contacts** (Pi off, ESP32 still powered). “Upstream of the relay” means **parallel to the Pi feed**, not “before the battery master switch.”

### How the Battery Connects to the System — Physical Wiring Guide

Your battery has two wires: **+ (red)** and **− (black)**. Here is exactly where each wire goes, step by step.

#### Step 1: Battery → XT60 → master switch → XT60 (your harness)

An **XT60** is always **two conductors**: **red = battery +**, **black = battery −** (same pin names on male and female).

Many RC-style harnesses use a **DPST** toggle: **both red and black** run through the switch. **OFF** disconnects the whole pack; **ON** connects both. That matches a battery XT60 on one side of the switch and a second XT60 on the load side — both polarities are switched together.

(Some builds switch **only** the red wire and leave black always tied to a ground bus. Your photos use **both** switched; that is fine and is often safer for storage.)

```
Battery ──XT60──► [ DPST: RED + BLACK both through switch ] ──XT60──► rest of robot
```

#### Step 2: After the switch — 1→3 XT60 splitter → TB6612 ×2 + XL4016

Plug the **load-side XT60** of the switch into a **1-to-3 parallel XT60 splitter**. Inside that harness, the input **red** is bussed to three reds and the input **black** to three blacks — same voltage on every branch; current is shared.

You can **cut off the three output XT60 plugs** and solder **each pair** to one board:

| Branch | Red → | Black → |
| --- | --- | --- |
| 1 | TB6612FNG #1 **VM** (or **VCC** motor supply) | TB6612FNG #1 **GND** |
| 2 | TB6612FNG #2 **VM** | TB6612FNG #2 **GND** |
| 3 | XL4016 **VIN+** (or **IN+**) | XL4016 **VIN−** (or **IN−**) |

**Yes — every branch needs both red and black.** DC only flows in a loop; **VM/VIN+ without GND/VIN−** (or the reverse) does nothing useful and can damage something if signals are connected without a common return.

The three blacks from the splitter are **electrically the same node** (battery negative after the switch). They still need to meet the **rest** of the system ground (ESP32, Pi, PCA9685, buck **VOUT−**, etc.) at one **common ground** so logic signals share a reference — use a ground bus, star point, or the splitter blacks as part of that bus.

#### Step 3: COMMON GND BUS — every device connects its ground here

The **three blacks** from the splitter (to TB6612 ×2 and XL4016 **VIN−**) are already on battery **−** (via the switch, if DPST). Tie those points together with **all other grounds** below (same metal/node):

From the common ground bus, run **black wires** to every device's GND:

| Wire | From | To | Terminal Name |
|------|------|----|---------------|
| Black wire 1 | GND bus | TB6612FNG chip #1 | **GND** |
| Black wire 2 | GND bus | TB6612FNG chip #2 | **GND** |
| Black wire 3 | GND bus | XL4016 Buck Converter | **VIN−** (or **IN−**) |
| Black wire 4 | GND bus | ESP32 DevKit | **GND** pin |
| Black wire 5 | GND bus | Relay module | **GND** |
| Black wire 6 | GND bus | Raspberry Pi 5 | **GND** pin (or USB-C ground) |
| Black wire 7 | GND bus | PCA9685 | **GND** |

> **Why is the shared ground critical?** Every signal wire (I2C, UART, GPIO, PWM) is measured as a voltage *relative to ground*. If two devices don't share the same ground, a "HIGH" signal from one device could look like noise to another. Worse, current can flow through data lines trying to find a ground path — this can damage GPIO pins.

#### Step 4: 5V rail from the Buck Converter

The XL4016 buck converter has output terminals: **VOUT+** and **VOUT−**. Set the output to **5.0V** using the adjustment potentiometer (measure with a multimeter before connecting anything!). 

From the buck converter's **VOUT+** (5V), run red wires to:

| Wire | From | To | Terminal Name | Notes |
|------|------|----|---------------|-------|
| Red wire 4 | VOUT+ | ESP32 DevKit | **VIN** pin | ESP32's onboard regulator converts 5V → 3.3V |
| Red wire 5 | VOUT+ | Relay module | **VCC** | Powers the relay coil |
| Red wire 6 | VOUT+ → through relay → | Pi 5 | **USB-C 5V** (or GPIO 5V) | Only powered when ESP32 closes the relay. Use 18AWG wire to minimise contact-resistance voltage drop (mechanical relay contacts can drop ~0.2–0.3V under 5A load). |
| Red wire 7 | VOUT+ | PCA9685 | **V+** only | Servo motor power rail (up to 1.4A stall for 2× SG90) |
| Red wire 8 | ESP32 3.3V out | PCA9685 | **VCC** | Logic power — MUST be 3.3V, NOT 5V. The PCA9685 has 10 kΩ I2C pull-ups tied to VCC; if VCC = 5V, SDA/SCL are pulled to 5V and will over-voltage the ESP32 GPIO (3.3V max), causing long-term damage. |

The buck converter's **VOUT−** connects to the same **common ground bus**.

#### Complete Physical Wiring Diagram

```
BATTERY          MASTER SWITCH (DPST: RED+BLK)     1→3 SPLITTER          12V LOADS
═══════          ═══════════════════════════        ═════════════          ═════════

(+) RED ──XT60──► both legs ON/OFF ──XT60──►  ├── red → TB6612 #1 VM
                                             ├── red → TB6612 #2 VM
                                             └── red → XL4016 VIN+
                                                    │
                                              [buck 12.8V→5V]
                                                    │
                                              VOUT+ (5V) ──► ESP32 / relay / PCA9685 / Pi (via relay)

(−) BLACK ─XT60─► both legs ON/OFF ──XT60──►  ├── black → TB6612 #1 GND
             (same switch)                   ├── black → TB6612 #2 GND
                                             └── black → XL4016 VIN−
                                                    │
                              COMMON GND ◄──── VOUT− + ESP32 GND + Pi GND + relay GND + PCA9685 GND
```

> **Summary:** After the switch you have one **XT60 pair** (red + black). The **1→3 splitter** gives **three parallel pairs**; solder **each full pair** to one of the two TB6612 boards and the XL4016. All blacks meet one **common ground** with the 5V return and logic grounds.

## Rail Summary

| Rail | Voltage | Source | Powers |
| --- | --- | --- | --- |
| Main bus | 12.8V (nom.) | 4S LiFePO4 pack | TB6612FNG VM input, Buck converter input |
| Motor rail | 12.8V (nom.) | Main bus → TB6612FNG | 4× TT encoder motors (PWM-capped to ~6V avg) |
| 5V logic rail | 5V / up to 8A | High-current DC-DC Buck (XL4016) | ESP32 VIN (via onboard LDO), Relay coil VCC, Pi 5 (via relay), PCA9685 **V+** (servo motor power only) |
| 3.3V | 3.3V | ESP32 onboard AMS1117 LDO (from 5V VIN) | ESP32 logic, PCA9685 **VCC** (I2C logic power — avoids 5V pull-ups on ESP32 I2C bus), pan/tilt servo signal lines |

## Key Design Decisions

**Why 4S LiFePO4 (12.8V)?**
The TB6612FNG accepts 4.5–15V on the motor supply. 4S LiFePO4 full charge is 14.6V — safely within spec (with 0.4V margin). Running motors closer to their 6V TT-motor rating is done via PWM duty cycle (47% duty at 12.8V ≈ 6.0V average). LiFePO4 offers no thermal runaway, >1200 cycle life, and a nearly flat discharge curve giving consistent motor behavior throughout the charge.

**Why not power motors from a separate 6V rail?**
Adding a second high-current buck converter adds cost, board space, and weight. PWM-based speed control through the TB6612FNG is the standard approach for TT-scale robots and provides adequate precision when combined with encoder feedback.

Optional **INA219/INA226** (I2C) high-side or low-side shunt sensing on the motor path (see BOM) can back up encoder-based stall cutout if an encoder cable fails.

**Buck Converter and Servo Safety:**
The Pi 5 alone can draw up to 5A. Therefore, a high-current buck converter like the XL4016 (rated up to 8A) is strictly required — do not use an LM2596(HV) as it will overheat. The pan/tilt SG90 servos are powered through a PCA9685 servo driver: the PCA9685 has a dedicated **V+** servo power pin connected to the 5V rail (for motor current), and a separate **VCC** logic pin connected to the **ESP32 3.3V** output. This is critical: the PCA9685 has 10 kΩ I2C pull-up resistors tied to VCC. If VCC were 5V, the SDA/SCL lines would be pulled to 5V, over-voltaging the ESP32's 3.3V-tolerant I2C GPIO pins and causing hardware damage over time. At 3.3V VCC, the PCA9685 logic still functions correctly and the I2C bus stays safely within the ESP32's input voltage range.

**ESP32 standby behavior and Power Switching:**
The ESP32 **VIN** is fed from **buck VOUT+** on the **same** 5V bus as the relay coil — **not** through the relay’s switched path to the Pi — so the ESP32 stays alive when the Pi is off. (Do not confuse this with the **battery master** DPST switch, which removes all loads.) The ESP32 draws ~10μA in deep-sleep. On wake (BLE, RTC, or button), it drives the relay so **only** the Pi 5V feed is energized. **Crucial Note:** A high-side switch or relay on the **Pi 5V path** preserves a **shared system ground**. A low-side N-channel cut on Pi “ground” would break that reference and risks current through data lines.

**BMS protection:**
The built-in 4S 40A balanced BMS in the pack prevents over-discharge (below ~11.2V / 2.8V per cell), over-charge (above ~14.6V / 3.65V per cell), cell imbalance, and short-circuit faults. The master power switch (your XT60 harness) provides a hard disconnect for storage.

**14.6V full-charge and TB6612FNG safety margin:**
At full charge (14.6V), the motor supply is only 0.4V below the TB6612FNG's 15V absolute maximum. This is acceptable because:
1. Under load, the battery voltage immediately sags to ~13.0–13.5V.
2. LiFePO4 has a very flat discharge curve — it spends >90% of its time between 12.4V and 13.2V.
3. The BMS limits charging to 14.6V ± 0.2V, so it cannot exceed 14.8V.
4. The 47% PWM cap means the motor driver never sources sustained high current at peak voltage.

If this margin concerns you, add a single Schottky diode (e.g., SB560, 5A 60V) in series on the motor driver VM path — it drops ~0.4V, bringing the worst-case from 14.8V to 14.4V.

---

## Battery Specifications

| Property | Value |
| --- | --- |
| Chemistry | LiFePO4 (32700 cells) |
| Configuration | 4S1P |
| Nominal voltage | 12.8V |
| Full charge voltage | 14.6V |
| BMS cutoff (min) | ~11.2V (2.8V/cell) |
| Capacity | 7Ah (89.6Wh) |
| BMS | 4S 40A balanced |
| Max charge current | 7A |
| Cycle life | >1200 cycles @ 0.2C |
| Weight | ~760g |
| Charge temp | 0 to 45°C |
| Discharge temp | −20 to 60°C |
| Ingress | IP5 |

> **Charger:** Use a **LiFePO4-specific** balance charger rated for 4S (14.6V). Do NOT use a standard Li-Ion charger (which targets 16.8V for 4S Li-Ion) — it will overcharge the cells and damage or destroy them.

---

## Power Budget Estimate

| Consumer | Voltage | Max Current | Max Power |
| --- | --- | --- | --- |
| Raspberry Pi 5 (under load) | 5V | 5.0A | 25.0W |
| 2× SG90 servos (stall, worst case) | 5V | 1.4A | 7.0W |
| ESP32 (active) | 5V → 3.3V | 0.24A | 0.8W |
| PCA9685 (logic) | 5V | 0.01A | 0.05W |
| Relay module | 5V | 0.07A | 0.35W |
| **5V rail total** | **5V** | **~6.7A** | **~33.2W** |
| 4× TT motors (running loaded) | 12.8V (PWM) | ~2.0A total | ~12.0W |
| **System total from battery** | **12.8V** | — | **~45W** |

At 12.8V and 45W total draw, the battery supplies ~3.5A. With 7Ah capacity, theoretical runtime is ~2 hours. Real-world runtime with typical (not worst-case) loads: **2.5–3 hours**.

The XL4016 buck converter is rated 8A — the 5V rail peak of ~6.7A is within spec with 1.3A headroom. ✅
