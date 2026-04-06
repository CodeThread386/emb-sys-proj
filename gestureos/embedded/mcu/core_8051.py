"""8051 Microcontroller register-level model.

Faithfully models the SFR map, internal RAM, ports, and interrupt system.
Gesture commands write to registers; the model responds like a real 8051.
"""

import threading
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, field


# SFR addresses (direct-addressable 0x80–0xFF)
SFR_P0     = 0x80
SFR_SP     = 0x81
SFR_DPL    = 0x82
SFR_DPH    = 0x83
SFR_PCON   = 0x87
SFR_TCON   = 0x88
SFR_TMOD   = 0x89
SFR_TL0    = 0x8A
SFR_TH0    = 0x8C
SFR_TL1    = 0x8B
SFR_TH1    = 0x8D
SFR_P1     = 0x90
SFR_SCON   = 0x98
SFR_SBUF   = 0x99
SFR_P2     = 0xA0
SFR_IE     = 0xA8
SFR_P3     = 0xB0
SFR_IP     = 0xB8
SFR_PSW    = 0xD0
SFR_ACC    = 0xE0
SFR_B      = 0xF0

SFR_NAMES = {
    SFR_P0: "P0", SFR_SP: "SP", SFR_DPL: "DPL", SFR_DPH: "DPH",
    SFR_PCON: "PCON", SFR_TCON: "TCON", SFR_TMOD: "TMOD",
    SFR_TL0: "TL0", SFR_TH0: "TH0", SFR_TL1: "TL1", SFR_TH1: "TH1",
    SFR_P1: "P1", SFR_SCON: "SCON", SFR_SBUF: "SBUF",
    SFR_P2: "P2", SFR_IE: "IE", SFR_P3: "P3", SFR_IP: "IP",
    SFR_PSW: "PSW", SFR_ACC: "ACC", SFR_B: "B",
}

# TCON bit masks
TCON_TF1 = 0x80  # Timer 1 overflow flag
TCON_TR1 = 0x40  # Timer 1 run
TCON_TF0 = 0x20  # Timer 0 overflow flag
TCON_TR0 = 0x10  # Timer 0 run
TCON_IE1 = 0x08  # External interrupt 1 edge flag
TCON_IT1 = 0x04  # External interrupt 1 type
TCON_IE0 = 0x02  # External interrupt 0 edge flag
TCON_IT0 = 0x01  # External interrupt 0 type

# IE bit masks
IE_EA  = 0x80  # Global enable
IE_ES  = 0x10  # Serial
IE_ET1 = 0x08  # Timer 1
IE_EX1 = 0x04  # External 1
IE_ET0 = 0x02  # Timer 0
IE_EX0 = 0x01  # External 0

# PSW bit masks
PSW_CY  = 0x80
PSW_AC  = 0x40
PSW_F0  = 0x20
PSW_RS1 = 0x10
PSW_RS0 = 0x08
PSW_OV  = 0x04
PSW_P   = 0x01

# SCON bit masks
SCON_SM0 = 0x80
SCON_SM1 = 0x40
SCON_REN = 0x10
SCON_TI  = 0x02
SCON_RI  = 0x01


@dataclass
class InterruptRequest:
    vector: int
    priority: int
    name: str


class MCU8051:
    """Register-accurate 8051 model that responds to gesture-driven writes."""

    def __init__(self):
        self._lock = threading.Lock()

        # Internal RAM: 128 bytes (0x00–0x7F)
        self._iram: bytearray = bytearray(128)

        # SFR space (0x80–0xFF), only certain addresses are valid
        self._sfr: Dict[int, int] = {}
        self._init_sfrs()

        # External RAM (simulated, 256 bytes for demo)
        self._xram: bytearray = bytearray(256)

        # Program counter
        self._pc: int = 0x0000

        # Interrupt pending queue
        self._irq_queue: List[InterruptRequest] = []

        # Callbacks for register write events
        self._write_hooks: Dict[int, List[Callable]] = {}

        # Machine cycle counter
        self._cycles: int = 0

        # Port output latches (what the CPU wrote)
        self._port_latch = {0: 0xFF, 1: 0xFF, 2: 0xFF, 3: 0xFF}

        # Port pin states (what would be read from external circuits)
        self._port_pins = {0: 0xFF, 1: 0xFF, 2: 0xFF, 3: 0xFF}

    def _init_sfrs(self):
        """Reset all SFRs to power-on defaults."""
        self._sfr = {addr: 0x00 for addr in range(0x80, 0x100)}
        self._sfr[SFR_SP] = 0x07
        self._sfr[SFR_P0] = 0xFF
        self._sfr[SFR_P1] = 0xFF
        self._sfr[SFR_P2] = 0xFF
        self._sfr[SFR_P3] = 0xFF

    def reset(self):
        with self._lock:
            self._iram = bytearray(128)
            self._init_sfrs()
            self._pc = 0x0000
            self._irq_queue.clear()
            self._cycles = 0
            self._port_latch = {0: 0xFF, 1: 0xFF, 2: 0xFF, 3: 0xFF}
            self._port_pins = {0: 0xFF, 1: 0xFF, 2: 0xFF, 3: 0xFF}

    # -- Register access ------------------------------------------------

    def sfr_write(self, addr: int, value: int):
        value &= 0xFF
        with self._lock:
            self._sfr[addr] = value

            port_map = {SFR_P0: 0, SFR_P1: 1, SFR_P2: 2, SFR_P3: 3}
            if addr in port_map:
                self._port_latch[port_map[addr]] = value

        hooks = self._write_hooks.get(addr, [])
        for hook in hooks:
            try:
                hook(addr, value)
            except Exception:
                pass

    def sfr_read(self, addr: int) -> int:
        with self._lock:
            port_map = {SFR_P0: 0, SFR_P1: 1, SFR_P2: 2, SFR_P3: 3}
            if addr in port_map:
                return self._port_pins[port_map[addr]] & self._port_latch[port_map[addr]]
            return self._sfr.get(addr, 0x00)

    def iram_write(self, addr: int, value: int):
        with self._lock:
            if 0 <= addr < 128:
                self._iram[addr] = value & 0xFF

    def iram_read(self, addr: int) -> int:
        with self._lock:
            if 0 <= addr < 128:
                return self._iram[addr]
            return 0

    def xram_write(self, addr: int, value: int):
        with self._lock:
            if 0 <= addr < len(self._xram):
                self._xram[addr] = value & 0xFF

    def xram_read(self, addr: int) -> int:
        with self._lock:
            if 0 <= addr < len(self._xram):
                return self._xram[addr]
            return 0

    def set_port_pin(self, port: int, pin: int, high: bool):
        """Simulate external circuit driving a port pin."""
        with self._lock:
            if high:
                self._port_pins[port] |= (1 << pin)
            else:
                self._port_pins[port] &= ~(1 << pin)

    # -- Register access helpers ----------------------------------------

    @property
    def acc(self) -> int:
        return self.sfr_read(SFR_ACC)

    @acc.setter
    def acc(self, val: int):
        self.sfr_write(SFR_ACC, val)

    @property
    def psw(self) -> int:
        return self.sfr_read(SFR_PSW)

    @property
    def sp(self) -> int:
        return self.sfr_read(SFR_SP)

    @property
    def dptr(self) -> int:
        return (self.sfr_read(SFR_DPH) << 8) | self.sfr_read(SFR_DPL)

    @property
    def tcon(self) -> int:
        return self.sfr_read(SFR_TCON)

    @property
    def ie(self) -> int:
        return self.sfr_read(SFR_IE)

    @property
    def pc(self) -> int:
        return self._pc

    @property
    def cycles(self) -> int:
        return self._cycles

    def tick(self):
        """Advance one machine cycle."""
        with self._lock:
            self._cycles += 1

    # -- Interrupt system -----------------------------------------------

    def request_interrupt(self, name: str, vector: int, priority: int = 0):
        ie = self.sfr_read(SFR_IE)
        if not (ie & IE_EA):
            return
        self._irq_queue.append(InterruptRequest(vector, priority, name))

    def get_pending_interrupts(self) -> List[InterruptRequest]:
        with self._lock:
            pending = sorted(self._irq_queue, key=lambda r: -r.priority)
            self._irq_queue.clear()
            return pending

    # -- Hooks ----------------------------------------------------------

    def on_sfr_write(self, addr: int, callback: Callable):
        if addr not in self._write_hooks:
            self._write_hooks[addr] = []
        self._write_hooks[addr].append(callback)

    # -- Snapshot for UI ------------------------------------------------

    def get_snapshot(self) -> dict:
        with self._lock:
            sfr_data = {}
            for addr in sorted(SFR_NAMES.keys()):
                sfr_data[SFR_NAMES[addr]] = self._sfr.get(addr, 0)

            iram_hex = self._iram[:64].hex()

            return {
                "sfr": sfr_data,
                "iram": iram_hex,
                "pc": self._pc,
                "sp": self._sfr.get(SFR_SP, 0),
                "acc": self._sfr.get(SFR_ACC, 0),
                "b": self._sfr.get(SFR_B, 0),
                "psw": self._sfr.get(SFR_PSW, 0),
                "dptr": (self._sfr.get(SFR_DPH, 0) << 8) | self._sfr.get(SFR_DPL, 0),
                "ports": dict(self._port_latch),
                "port_pins": dict(self._port_pins),
                "cycles": self._cycles,
                "tcon": self._sfr.get(SFR_TCON, 0),
                "tmod": self._sfr.get(SFR_TMOD, 0),
                "ie": self._sfr.get(SFR_IE, 0),
                "scon": self._sfr.get(SFR_SCON, 0),
            }
