# GestureOS

A gesture-controlled desktop interface with a full embedded systems simulation running underneath. Hand gestures detected via webcam control your desktop (cursor, volume, window switching, etc.) while simultaneously driving a simulated 8051 microcontroller, communication protocols, and an RTOS — all visualized in a real-time dashboard.

## Features

### Gesture-Controlled Desktop
| Gesture | Action |
|---|---|
| Point (index finger) | Move cursor (trackpad mode) |
| Open palm | Press Space bar |
| Spiderman (thumb + index + pinky) | Toggle mute |
| Three fingers (index + middle + ring) | Alt+Tab window cycling |
| Thumbs up | Volume up |
| Thumbs down | Volume down |
| Pinch index (thumb touches index) | Right click |
| Pinch middle (thumb touches middle) | Left click |

### Embedded Systems Simulation
Every gesture flows through a complete embedded systems stack:

- **8051 MCU Model** — Full SFR map (P0–P3, ACC, PSW, TCON, TMOD, IE, IP, SCON, SBUF, SP, DPTR), 128-byte IRAM, 256-byte XRAM, interrupt system, machine cycle counter at 11.0592 MHz
- **ADC/DAC** — 10-bit SAR (Successive Approximation Register) ADC converts webcam brightness to digital values step-by-step; DAC reconstructs the analog output
- **Timers** — 8051 Timer 0/1 in Mode 1 (16-bit) and Mode 2 (8-bit auto-reload) with overflow interrupts
- **Watchdog Timer** — Resets MCU if no hand is detected (system alive check)
- **UART** — 9600 baud serial with start/data/parity/stop bit framing and waveform generation
- **I2C** — START, 7-bit address + R/W, ACK/NACK, data, STOP with SDA/SCL waveforms
- **CAN 2.0A** — SOF, 11-bit arbitration ID, DLC, data, CRC-15, ACK, EOF with full frame encoding
- **Bluetooth Low Energy** — Advertisement packets, AD structures, GATT characteristics
- **RTOS Scheduler** — EDF, Rate Monotonic (RMS), and Hybrid scheduling with task preemption, deadline miss detection, and utilization tracking

### Real-Time Dashboard
- Live webcam feed with hand landmark overlay and gesture label
- 8051 register view (SFR values in hex/binary with bit-field breakdowns)
- Logic analyzer waveforms (UART TX, I2C SDA/SCL, CAN frames)
- ADC/DAC pipeline visualization (analog input → digital staircase → reconstructed output)
- RTOS scheduler timeline (task execution, deadlines, preemption)

## Requirements

- Python 3.10+
- Webcam
- Linux with X11 session (for desktop control features)

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd emb-sys-proj

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m gestureos.main
```

The MediaPipe hand landmarker model (~16 MB) is downloaded automatically on first run.

## Project Structure

```
gestureos/
├── config.py                    # All configuration parameters
├── main.py                      # Entry point — wires gestures to embedded sim
├── gesture/
│   ├── engine.py                # MediaPipe hand detection + gesture classification
│   └── controller.py            # Maps gestures to desktop actions
├── embedded/
│   ├── mcu/
│   │   └── core_8051.py         # 8051 register-level MCU model
│   ├── peripherals/
│   │   ├── adc.py               # SAR ADC simulator
│   │   ├── dac.py               # DAC simulator
│   │   ├── timer.py             # Timer 0/1 + Watchdog
│   │   └── uart.py              # UART frame-level protocol
│   ├── protocols/
│   │   ├── i2c.py               # I2C bus protocol with waveforms
│   │   ├── can.py               # CAN 2.0A frame encoding + CRC-15
│   │   └── bluetooth.py         # BLE advertisements + GATT
│   └── rtos/
│       ├── task.py              # RTOS task model
│       └── scheduler.py         # EDF / RMS / Hybrid scheduler
└── ui/
    ├── dashboard.py             # Main PyQt6 window
    ├── webcam_widget.py         # Webcam feed display
    ├── register_view.py         # 8051 SFR/RAM viewer
    ├── waveform_view.py         # UART/I2C/CAN logic analyzer
    ├── adc_view.py              # ADC/DAC pipeline plots
    └── scheduler_view.py        # RTOS timeline visualization
```

## How It Works

1. **Webcam** captures frames → **MediaPipe** detects hand landmarks → **Gesture Engine** classifies the gesture
2. Each gesture **writes to 8051 MCU ports** (P0, P1, P2, ACC) — simulating sensor input on a real microcontroller
3. The gesture command is **serialized simultaneously** over UART, I2C, CAN, and BLE — generating protocol-correct frames with waveforms
4. **ADC** converts webcam brightness (analog) to a digital value using the SAR algorithm; **DAC** reconstructs it
5. **Timers** tick at the MCU clock rate; the **Watchdog** resets if no hand is detected
6. The **RTOS scheduler** manages all subsystem tasks with real-time scheduling policies
7. The **desktop controller** executes the mapped action (move cursor, change volume, switch windows, etc.)
8. The **dashboard** visualizes everything in real-time

## Configuration

All parameters are in `gestureos/config.py`:

- `MOUSE_SENSITIVITY` — cursor speed (default: 800)
- `MOUSE_DEAD_ZONE` — jitter filter threshold (default: 0.003)
- `GESTURE_HOLD_FRAMES` — frames to hold before action fires (default: 4)
- `VOLUME_STEP` — volume change per gesture (default: 5%)
- MCU, ADC, Timer, UART, I2C, CAN, BLE, and RTOS parameters are all configurable
