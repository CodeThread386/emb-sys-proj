"""GestureOS configuration."""

# Gesture engine
GESTURE_HOLD_FRAMES = 4
SMOOTHING_FACTOR = 0.4

# Desktop control (trackpad mode)
MOUSE_SENSITIVITY = 800       # pixels per unit of normalized hand movement
MOUSE_DEAD_ZONE = 0.003       # ignore jitter smaller than this
CLICK_PINCH_THRESHOLD = 0.045
VOLUME_STEP = 5

# 8051 MCU
MCU_CLOCK_HZ = 11_059_200
MCU_MACHINE_CYCLE = 12

# ADC
ADC_RESOLUTION_BITS = 10
ADC_VREF = 5.0
ADC_SAMPLE_RATE_HZ = 100

# Timer
TIMER_PRESCALER = 12

# UART
UART_BAUD_RATE = 9600
UART_DATA_BITS = 8
UART_STOP_BITS = 1
UART_PARITY = "NONE"

# I2C
I2C_CLOCK_HZ = 100_000
I2C_DEVICE_ADDR = 0x50

# CAN
CAN_BAUD_RATE = 500_000
CAN_ARB_ID = 0x100

# Bluetooth
BLE_ADV_INTERVAL_MS = 100

# RTOS
RTOS_TICK_MS = 1
RTOS_SPEED_FACTOR = 5.0

# UI
UI_REFRESH_MS = 33
WAVEFORM_VISIBLE_SAMPLES = 300

# Gesture-to-command mapping
GESTURE_COMMANDS = {
    "INDEX_FINGER":  {"action": "mouse_move",      "desc": "Move cursor (trackpad)"},
    "FIST":          {"action": "meta_d",           "desc": "Show desktop (Meta+D)"},
    "OPEN_PALM":     {"action": "space",            "desc": "Press Space bar"},
    "SPIDERMAN":     {"action": "toggle_mute",      "desc": "Toggle mute"},
    "THREE_FINGERS": {"action": "alt_tab",           "desc": "Switch window (Alt+Tab)"},
    "THUMBS_UP":     {"action": "volume_up",        "desc": "Volume up"},
    "THUMBS_DOWN":   {"action": "volume_down",      "desc": "Volume down"},
    "PINCH_INDEX":   {"action": "right_click",      "desc": "Right click"},
    "PINCH_MIDDLE":  {"action": "left_click",       "desc": "Left click"},
}

OVERVIEW_MIN_HOLD_SEC = 1.0
