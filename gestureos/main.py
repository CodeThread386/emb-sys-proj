"""GestureOS — Entry point.

Wires the gesture engine to the embedded systems simulation layer:
every gesture command flows through the 8051 MCU registers, gets
serialized over UART/I2C/CAN/BLE protocols, and is scheduled by the RTOS.
"""

import sys
import signal
import time
import threading

from gestureos import config
from gestureos.gesture.engine import GestureEngine, HandData
from gestureos.gesture.controller import DesktopController
from gestureos.embedded.mcu.core_8051 import (
    MCU8051, SFR_P0, SFR_P1, SFR_P2, SFR_ACC, SFR_TCON, SFR_TMOD, SFR_IE,
    TCON_TR0, TCON_TR1, IE_EA, IE_ET0,
)
from gestureos.embedded.peripherals.adc import ADCSimulator
from gestureos.embedded.peripherals.dac import DACSimulator
from gestureos.embedded.peripherals.timer import TimerPeripheral, WatchdogTimer
from gestureos.embedded.peripherals.uart import UARTSimulator
from gestureos.embedded.protocols.i2c import I2CSimulator
from gestureos.embedded.protocols.can import CANSimulator
from gestureos.embedded.protocols.bluetooth import BLESimulator
from gestureos.embedded.rtos.scheduler import RTOSScheduler
from gestureos.embedded.rtos.task import SchedulingMode


GESTURE_TO_CODE = {
    "NONE": 0x00, "INDEX_FINGER": 0x01, "FIST": 0x02, "OPEN_PALM": 0x03,
    "PEACE": 0x04, "SPIDERMAN": 0x05, "FOUR_FINGERS": 0x06,
    "THUMBS_UP": 0x07, "THUMBS_DOWN": 0x08,
    "PINCH_INDEX": 0x09, "PINCH_MIDDLE": 0x0A,
}

GESTURE_TO_PORT = {
    "NONE": 0x00, "INDEX_FINGER": 0x01, "FIST": 0x02, "OPEN_PALM": 0x04,
    "PEACE": 0x08, "SPIDERMAN": 0x10, "FOUR_FINGERS": 0x20,
    "THUMBS_UP": 0x40, "THUMBS_DOWN": 0x80,
    "PINCH_INDEX": 0x03, "PINCH_MIDDLE": 0x05,
}


class AppCore:
    """Holds all components and wires gesture events to embedded subsystems."""

    def __init__(self):
        # Gesture layer
        self.engine = GestureEngine()
        self.controller = DesktopController(self.engine)

        # 8051 MCU
        self.mcu = MCU8051()

        # Peripherals
        self.adc = ADCSimulator()
        self.dac = DACSimulator()
        self.timer = TimerPeripheral(self.mcu)
        self.watchdog = WatchdogTimer(self.mcu, timeout_s=10.0)
        self.uart = UARTSimulator(self.mcu)

        # Protocols
        self.i2c = I2CSimulator()
        self.can = CANSimulator()
        self.ble = BLESimulator()

        # RTOS
        self.scheduler = RTOSScheduler()

        # Internal state
        self._running = False
        self._sim_thread = None
        self._last_gesture = "NONE"

        # Wire gesture callbacks
        self.controller.on_gesture(self._on_gesture)
        self.controller.on_action(self._on_action)

        # Configure 8051 timers
        self.mcu.sfr_write(SFR_TMOD, 0x01)   # Timer 0 in Mode 1 (16-bit)
        self.mcu.sfr_write(SFR_TCON, TCON_TR0)  # Start Timer 0
        self.mcu.sfr_write(SFR_IE, IE_EA | IE_ET0)  # Enable interrupts

        # Set up RTOS tasks representing system components
        self.scheduler.add_task("GestureCapture", period=33, wcet=8, is_hard=True)
        self.scheduler.add_task("ADC_Sampling", period=50, wcet=5, is_hard=True)
        self.scheduler.add_task("ProtocolTX", period=100, wcet=15, is_hard=True)
        self.scheduler.add_task("DisplayUpdate", period=33, wcet=10, is_hard=False)
        self.scheduler.add_task("BLE_Advertise", period=100, wcet=8, is_hard=False)

    def start(self):
        self._running = True
        self.engine.start()
        self.controller.start()
        self.scheduler.start()
        self.watchdog.enable()

        self._sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._sim_thread.start()

    def stop(self):
        self._running = False
        self.engine.stop()
        self.controller.stop()
        self.scheduler.stop()
        if self._sim_thread:
            self._sim_thread.join(timeout=2.0)

    def _on_gesture(self, gesture: str, hand: HandData):
        """Called on every frame with the detected gesture. Drives the MCU model."""
        # Write gesture code to Port 1 (input port from camera subsystem)
        port_val = GESTURE_TO_PORT.get(gesture, 0x00)
        self.mcu.sfr_write(SFR_P1, port_val)

        # Write gesture code to accumulator
        code = GESTURE_TO_CODE.get(gesture, 0x00)
        self.mcu.acc = code

        # Feed the watchdog (hand detected = system alive)
        if gesture != "NONE":
            self.watchdog.feed()

        # ADC: sample brightness from camera frame
        brightness = hand.frame_brightness
        adc_result = self.adc.convert(brightness)
        # Write ADC result to Port 0 (upper 8 bits of 10-bit result)
        self.mcu.sfr_write(SFR_P0, (adc_result.digital_output >> 2) & 0xFF)

        # DAC: reconstruct from ADC
        self.dac.convert(adc_result.digital_output)

        # Write ADC value to BLE characteristic
        self.ble.write_characteristic(2, adc_result.digital_output.to_bytes(2, "big"))

        self._last_gesture = gesture

    def _on_action(self, action: str, gesture: str):
        """Called when a debounced gesture triggers a system command.
        Serializes the command through all protocols simultaneously.
        """
        code = GESTURE_TO_CODE.get(gesture, 0x00)

        # UART: transmit command as a serial frame
        cmd_str = f"CMD:{gesture}"
        self.uart.transmit_string(cmd_str)

        # I2C: write gesture code to a peripheral at address 0x50
        self.i2c.transfer(
            slave_addr=config.I2C_DEVICE_ADDR,
            rw="W",
            data=[code, 0x01],
            description=f"Gesture: {gesture}",
        )

        # CAN: broadcast gesture command on the bus
        self.can.send_frame(
            arb_id=config.CAN_ARB_ID,
            data=[code, ord(gesture[0]) if gesture else 0x00],
            description=f"Gesture: {gesture}",
        )

        # BLE: update characteristic and send advertisement
        self.ble.write_characteristic(0, bytes([code]))
        self.ble.send_advertisement(gesture_code=code)

        # Write command result to Port 2 (output acknowledgment)
        self.mcu.sfr_write(SFR_P2, code)

    def _simulation_loop(self):
        """Background loop: ticks MCU timers, watchdog, and periodic bus traffic."""
        tick_count = 0
        while self._running:
            # Tick MCU timer
            self.mcu.tick()
            self.timer.tick()

            # Watchdog check
            self.watchdog.check()

            tick_count += 1

            # Periodic I2C sensor read (every ~500 ticks)
            if tick_count % 500 == 0:
                self.i2c.transfer(
                    slave_addr=0x48, rw="R", data=[0x00, 0x19],
                    description="Temp sensor read",
                )

            # Periodic CAN status broadcast (every ~300 ticks)
            if tick_count % 300 == 0:
                sched = self.scheduler.get_snapshot()
                n_tasks = len(sched.get("tasks", []))
                u_int = int(sched.get("utilization", 0) * 100)
                self.can.send_frame(
                    arb_id=0x200,
                    data=[n_tasks, u_int],
                    description="Status broadcast",
                )

            # Periodic BLE advertisement (every ~200 ticks)
            if tick_count % 200 == 0:
                code = GESTURE_TO_CODE.get(self._last_gesture, 0)
                self.ble.send_advertisement(gesture_code=code)

            time.sleep(0.001)


def main():
    from PyQt6.QtWidgets import QApplication
    from gestureos.ui.dashboard import Dashboard

    app = QApplication(sys.argv)

    core = AppCore()
    dashboard = Dashboard(core)
    core.start()
    dashboard.show()

    def cleanup():
        print("\n[GestureOS] Shutting down...")
        core.stop()

    app.aboutToQuit.connect(cleanup)
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
