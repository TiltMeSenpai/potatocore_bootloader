from nmigen import *

class SpiController(Elaboratable):
    def __init__(self, bus):
        self.bus        = bus
        self.clk        = Signal()
        self.start      = Signal()
        self.ready      = Signal()
        self.first      = Signal()
        self.last       = Signal()
        self.din        = Signal(8)
        self.dout       = Signal(8)
    
    def elaborate(self, platform):
        m = Module()

        din_latch  = Signal(8)
        dout_latch = Signal(8)
        last_latch = Signal()
        clk = self.clk
        
        m.d.comb += [
            self.bus.copi.eq(dout_latch[7]),
        ]
        
        with m.FSM() as fsm:
            m.d.comb += self.ready.eq(fsm.ongoing("START"))
            with m.State("START"):
                with m.If(self.start):
                    m.next = "RUN"
                    m.d.sync += [
                        dout_latch.eq(self.dout),
                        last_latch.eq(self.last)
                    ]
                    with m.If(self.first):
                        m.d.sync += self.bus.cs.eq(1)
            with m.State("RUN"):
                bit_ctr = Signal(3)
                m.d.sync += clk.eq(~clk)
                with m.If(clk): # Falling edge logic
                    m.d.sync += dout_latch.eq(dout_latch << 1)
                with m.Else(): # Rising edge logic
                    m.d.sync += [
                        bit_ctr.eq(bit_ctr + 1),
                        din_latch.eq(Cat(self.bus.cipo, din_latch))
                    ]
                    with m.If(bit_ctr == 7):
                        m.next = "DONE"
            with m.State("DONE"):
                m.d.sync += [
                    self.din.eq(din_latch),
                    self.clk.eq(0)
                ]
                m.next = "START"
                with m.If(last_latch):
                    m.d.sync += self.bus.cs.eq(0)

            return m

class SpiTest(Elaboratable):
    def elaborate(self, platform):
        from .clock import UsbDomainGenerator
        from luna.gateware.usb.devices.ila import USBIntegratedLogicAnalyer

        m = Module()

        bus = platform.request("spi")

        m.submodules.spi = spi = SpiController(bus)
        m.submodules.mclk = Instance("USRMCLK", i_USRMCLKI=spi.clk, i_USRMCLKTS=Signal()) 
        m.submodules.clock = UsbDomainGenerator()
        m.submodules.ila = ila = USBIntegratedLogicAnalyer(
            max_packet_size=64,
            signals=[
                spi.din,
                spi.dout,
                spi.clk,
                spi.bus.copi,
                spi.bus.cipo,
                spi.bus.cs,
                spi.first,
                spi.last,
                spi.ready
            ],
            sample_depth=512
        )

        with m.FSM() as fsm:
            m.d.comb += [
                spi.first.eq(fsm.ongoing("START")),
                spi.last.eq(fsm.ongoing("DONE")),
                ila.trigger.eq(fsm.ongoing("START"))
            ]
            unlock = Signal()
            with m.State("START"):
                m.d.sync += [
                    spi.dout.eq(0x9F),
                    spi.start.eq(1)
                ]
                with m.If(spi.ready):
                    m.d.sync += unlock.eq(1)
                with m.If(unlock & ~spi.ready):
                    m.d.sync += unlock.eq(0)
                    m.next = "MFG_ID"
            with m.State("MFG_ID"):
                m.d.sync += spi.dout.eq(0)
                with m.If(spi.ready):
                    m.d.sync += unlock.eq(1)
                with m.If(unlock & ~spi.ready):
                    m.d.sync += unlock.eq(0)
                    m.next = "ID_HIGH"
            with m.State("ID_HIGH"):
                with m.If(spi.ready):
                    m.d.sync += unlock.eq(1)
                with m.If(unlock & ~spi.ready):
                    m.d.sync += unlock.eq(0)
                    m.next = "ID_LOW"
            with m.State("ID_LOW"):
                with m.If(spi.ready):
                    m.d.sync += unlock.eq(1)
                with m.If(unlock & ~spi.ready):
                    m.d.sync += unlock.eq(0)
                    m.next = "DONE"
            with m.State("DONE"):
                delay = Signal(range(128), reset=127)
                m.d.sync += [
                    spi.start.eq(0),
                    delay.eq(delay - 1)
                    ]
                with m.If(delay == 0):
                    m.next = "START"

        return m

def build():
    from .board import DCNextPlatform
    import os
    os.environ["NEXTPNR_ECP5"] = "yowasp-nextpnr-ecp5"
    os.environ["ECPPACK"] = "yowasp-ecppack"
    platform = DCNextPlatform()
    platform.default_usb_connection = "usb"
    platform.build(SpiTest(), 
        ecppack_opts=["--freq", "38.8"])

def frontend():
    from luna.gateware.usb.devices.ila import USBIntegratedLogicAnalyzerFrontend
    from types import SimpleNamespace
    # Dirty hack so that we don't have to figure out how to access the ILA
    ila = SimpleNamespace()
    ila.bytes_per_sample = 4
    ila.sample_depth = 512
    ila.signals = [
        Signal(8, name="spi.din"),
        Signal(8, name="spi.dout"),
        Signal(1, name="spi.clk"),
        Signal(1, name="spi.copi"),
        Signal(1, name="spi.cipo"),
        Signal(1, name="spi.cs"),
        Signal(1, name="spi.first"),
        Signal(1, name="spi.last"),
        Signal(1, name="spi.ready"),
    ]
    ila.sample_period = 1e-4
    frontend = USBIntegratedLogicAnalyzerFrontend(ila=ila)
    frontend.interactive_display()