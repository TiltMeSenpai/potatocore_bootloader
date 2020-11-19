from nmigen import *
from luna.gateware.usb.devices.acm import USBSerialDevice
from .util import A2I, I2A

class SerialIHexInput(Elaboratable):
    # Tokenizer control for Intel Hex over serial
    # Detects incoming ":" followed by a series of hex-encoded bytes
    # in ASCII
    def __init__(self, serial_rx):
        # Hex Tokenizer
        self.data  = Signal(8)
        self.ready = Signal()
        self.start = Signal()
        self.done  = Signal()
        self.err   = Signal()
        self.rx    = serial_rx
        self.checksum     = Signal(8)

    
    def elaborate(self, platform):
        m = Module()

        m.submodules.a2i = a2i = A2I()

        m.d.sync += self.rx.ready.eq(0)
        decode = Signal()
        with m.FSM(domain="usb") as fsm:
            m.d.comb += [
                self.ready.eq(fsm.ongoing("START")),
                self.done.eq(fsm.ongoing("DONE")),
                self.err.eq(fsm.ongoing("ERROR")),
            ]
            with m.State("START"):
                m.d.sync += self.rx.ready.eq(~self.start)
                with m.If(~self.start & self.rx.valid & (self.rx.payload == ord("."))):
                    m.d.sync += decode.eq(0)
                    m.d.usb += self.checksum.eq(0)
                    m.next = "HIGH"
            with m.State("HIGH"):
                with m.If(self.rx.valid & ~decode):
                    m.d.sync += [
                        decode.eq(1),
                        a2i.din.eq(self.rx.payload),
                        self.rx.ready.eq(1)
                    ]
                with m.If(decode):
                    m.d.sync += [
                        decode.eq(0),
                        self.data[4:].eq(a2i.dout),
                    ]
                    with m.If(a2i.err):
                        m.next = "ERROR"
                    with m.Else():
                        m.next = "LOW"
            with m.State("LOW"):
                with m.If(self.rx.valid & ~decode):
                    m.d.sync += [
                        decode.eq(1),
                        a2i.din.eq(self.rx.payload),
                        self.rx.ready.eq(1)
                    ]
                with m.If(decode):
                    m.d.sync += [
                        decode.eq(0),
                        self.data[:4].eq(a2i.dout),
                    ]
                    with m.If(a2i.err):
                        m.next = "ERROR"
                    with m.Else():
                        m.next = "DONE"
            with m.State("DONE"):
                m.d.sync += decode.eq(0)
                with m.If(self.start):
                    m.d.usb += self.checksum.eq(self.checksum + self.data)
                    m.next = "HIGH"
            with m.State("ERROR"):
                m.d.sync += decode.eq(0)
                with m.If(self.start):
                    m.next = "START"

        return m

class SerialIHexOutput(Elaboratable):
    def __init__(self, tx):
        self.tx = tx
        self.first = Signal()
        self.last  = Signal()
        self.empty = Signal()
        self.s_chr = Signal(8)
        self.data  = Signal(8)
        self.ready = Signal()
        self.start = Signal()

    def elaborate(self, platfrom):
        m = Module()
        last = Signal()
        empty = Signal()
        with m.FSM(domain="usb") as fsm:
            m.d.comb += [
                self.ready.eq(fsm.ongoing("START")),
                self.tx.first.eq(fsm.ongoing("SOL")),
                self.tx.last.eq(fsm.ongoing("EOL"))
            ]

            m.d.sync += self.tx.valid.eq(0)
            with m.State("START"):
                with m.If(self.start):
                    m.d.sync += [
                        last.eq(self.last),
                        empty.eq(self.empty)
                    ]
                    with m.If(self.first):
                        m.next = "SOL"
                    with m.Else():
                        m.next = "HIGH"
            with m.State("SOL"):
                m.d.sync += [
                    self.tx.valid.eq(1),
                    self.tx.payload.eq(self.s_chr)
                ]
                with m.If(self.tx.ready):
                    with m.If(empty):
                        m.next = "EOL"
                    with m.Else():
                        m.next = "HIGH"
            with m.State("HIGH"):
                m.d.sync += [
                    self.tx.valid.eq(1),
                    self.tx.payload.eq(I2A[self.data[4:]])
                ]
                with m.If(self.tx.ready):
                    m.next = "LOW"
            with m.State("LOW"):
                m.d.sync += [
                    self.tx.valid.eq(1),
                    self.tx.payload.eq(I2A[self.data[:4]])
                ]
                with m.If(self.tx.ready):
                    with m.If(last):
                        m.next = "EOL"
                    with m.Else():
                        m.next = "START"
            with m.State("EOL"):
                m.d.sync += [
                    self.tx.valid.eq(1),
                    self.tx.payload.eq(0x0a)
                ]
                with m.If(self.tx.ready):
                    m.next = "START"

        return m