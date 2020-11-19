from nmigen import *
from luna.full_devices import USBSerialDevice
from .serial import SerialIHexInput, SerialIHexOutput
from .spi import SpiController
from .clock import UsbDomainGenerator
from .rgb import RgbController

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        bus = platform.request("spi")
        usb = platform.request("usb")
        rgb = [platform.request("rgb_led", i) for i in range(4)]

        input_buffer = Memory(width=8, depth=255)

        m.submodules.rgb = RgbController(rgb)

        m.submodules.car = UsbDomainGenerator()

        m.submodules.spi = spi = SpiController(bus)

        m.submodules.mclk = Instance("USRMCLK", i_USRMCLKI=spi.clk, i_USRMCLKTS=Signal()) 

        m.submodules.serial = serial = USBSerialDevice(bus=usb, idVendor=1337, idProduct=1337)

        m.submodules.rx    = rx = SerialIHexInput(serial.rx)
        m.submodules.tx    = tx = SerialIHexOutput(serial.tx)

        m.submodules.read  = in_read  = input_buffer.read_port()
        m.submodules.write = in_write = input_buffer.write_port()

        byte_count   = Signal(8)
        bytes_recv   = Signal(8)
        return_bytes = Signal(8)
        stage_done   = Signal()

        m.d.usb += [
            rx.start.eq(0),
            in_write.en.eq(0),
            tx.start.eq(0),
            tx.first.eq(0),
            tx.last.eq(0),
            tx.empty.eq(0),
            spi.start.eq(0),
            spi.first.eq(0),
            spi.last.eq(0)
        ]

        m.d.comb += [
            serial.connect.eq(1),
            in_write.addr.eq(bytes_recv),
            in_read.addr.eq(bytes_recv)
        ]

        with m.FSM(domain="usb"):
            with m.State("START"):
                m.d.usb += rx.start.eq(~rx.ready)
                with m.If(~stage_done):
                    m.d.usb += [
                        bytes_recv.eq(0),
                        tx.last.eq(1),
                        spi.last.eq(1),
                        spi.start.eq(spi.ready)
                    ]
                    with m.If(~spi.bus.cs):
                        m.d.usb += stage_done.eq(1)
                with m.If(stage_done & spi.ready & rx.ready):
                    with m.If(spi.bus.cs):
                        m.d.usb += stage_done.eq(0)
                        m.next = "POLL_READY"
                    with m.Else():
                        m.d.usb += [
                            spi.dout.eq(0x05),
                            spi.first.eq(1),
                            spi.start.eq(1)
                        ]
            with m.State("POLL_READY"):
                poll_first = Signal()
                with m.If(spi.ready):
                    m.d.usb += [
                        spi.start.eq(1),
                        poll_first.eq(1)
                    ]
                    with m.If(~spi.din[0] & poll_first):
                        m.d.usb += [
                            spi.last.eq(1),
                            stage_done.eq(1),
                        ]
                with m.If(stage_done & spi.ready & ~spi.bus.cs):
                    m.d.usb += [
                        stage_done.eq(0),
                        poll_first.eq(0)
                    ]
                    m.next = "COUNT_BYTES"
            with m.State("COUNT_BYTES"):
                with m.If(rx.err):
                    m.next = "ERR"
                with m.If(rx.done):
                    m.d.usb += [
                        byte_count.eq(rx.data),
                        rx.start.eq(1),
                        stage_done.eq(1)
                    ]
                with m.If(stage_done & ~rx.done):
                    m.d.usb += stage_done.eq(0)
                    m.next = "RETURN_BYTES"
            with m.State("RETURN_BYTES"):
                with m.If(rx.err):
                    m.next = "ERR"
                with m.If(rx.done):
                    m.d.usb += [
                        return_bytes.eq(rx.data),
                        rx.start.eq(1),
                        stage_done.eq(1)
                    ]
                with m.If(stage_done & ~rx.done):
                    m.d.usb += stage_done.eq(0)
                    m.next = "READ_DATA"
            with m.State("READ_DATA"):
                with m.If(rx.err):
                    m.next = "ERR"
                with m.If(rx.done):
                    m.d.usb += [
                        stage_done.eq(1),
                        in_write.data.eq(rx.data),
                        in_write.en.eq(1),
                        rx.start.eq(1)
                    ]
                with m.If(stage_done & ~rx.done):
                    m.d.usb += [
                        bytes_recv.eq(bytes_recv + 1),
                        stage_done.eq(0)
                    ]
                with m.If((bytes_recv >= byte_count) & ~rx.done):
                    m.next = "CHECKSUM"
            with m.State("CHECKSUM"):
                with m.If(rx.err):
                    m.next = "ERR"
                with m.If(rx.done):
                    m.d.usb += [
                        stage_done.eq(1),
                        rx.start.eq(1),
                    ]
                with m.If(stage_done & ~rx.done):
                    m.d.usb += stage_done.eq(0)
                    m.next = "RUN"
            with m.State("RUN"):
                with m.If(rx.checksum):
                    m.d.usb += [
                        tx.first.eq(1),
                        tx.last.eq(1),
                        tx.s_chr.eq(ord("c")),
                        tx.data.eq(rx.checksum),
                        tx.start.eq(1)
                    ]
                    with m.If(tx.ready):
                        m.d.usb += stage_done.eq(1)
                    with m.If(~tx.ready & stage_done):
                        m.d.usb += stage_done.eq(0)
                        m.next = "START"
                with m.Else():
                    m.d.usb += [
                        bytes_recv.eq(0),
                        stage_done.eq(0),
                    ]
                    m.next = "SPI_WRITE"
            with m.State("SPI_WRITE"):
                b_next = bytes_recv + 1
                with m.If(spi.ready):
                    m.d.usb += [
                        spi.dout.eq(in_read.data),
                        spi.start.eq(bytes_recv < byte_count),
                        spi.first.eq(~spi.bus.cs),
                        spi.last.eq((return_bytes == 0) & (b_next >= byte_count)),
                        stage_done.eq(1),
                    ]
                with m.If(stage_done):
                    m.d.usb += [
                        bytes_recv.eq(b_next),
                        stage_done.eq(0),
                    ]
                    with m.If(bytes_recv >= byte_count):
                        with m.If(return_bytes == 0):
                            m.d.usb += [
                                tx.start.eq(1),
                                tx.s_chr.eq(ord(".")),
                                tx.first.eq(1),
                                tx.last.eq(1),
                                tx.empty.eq(1),
                                bytes_recv.eq(1),
                            ]
                            m.next = "START"
                        with m.Else():
                            m.next = "SPI_STALL"
            with m.State("SPI_STALL"):
                with m.If(spi.ready):
                    m.d.usb += [
                        spi.dout.eq(0),
                        spi.start.eq(1),
                        stage_done.eq(1),
                        bytes_recv.eq(1)
                    ]
                with m.If(stage_done):
                    m.next = "SPI_READ"
            with m.State("SPI_READ"):
                with m.If(spi.ready & tx.ready):
                    m.d.usb += [
                        spi.dout.eq(0),
                        spi.start.eq(1),
                        spi.last.eq((bytes_recv + 1) >= return_bytes),
                        tx.first.eq(bytes_recv == 1),
                        tx.last.eq(bytes_recv >= return_bytes),
                        tx.start.eq(1),
                        tx.data.eq(spi.din),
                        stage_done.eq(1),
                    ]
                with m.If(stage_done & ~tx.ready):
                    m.d.usb += [
                        bytes_recv.eq(bytes_recv + 1),
                        stage_done.eq(0)
                    ]
                    with m.If(bytes_recv >= return_bytes):
                        m.d.usb += stage_done.eq(0)
                        m.next = "START"
            with m.State("ERR"):
                m.d.usb += [
                    tx.first.eq(1),
                    tx.last.eq(1),
                    tx.empty.eq(1),
                    tx.s_chr.eq(ord("e")),
                    tx.data.eq(0xff),
                    tx.start.eq(1)
                ]
                with m.If(tx.ready):
                    m.d.usb += stage_done.eq(1)
                with m.If(stage_done):
                    m.d.usb += stage_done.eq(0)
                    m.next = "START"

        return m

def build():
    from .board import DCNextPlatform
    import os
    os.environ["NEXTPNR_ECP5"] = "yowasp-nextpnr-ecp5"
    os.environ["ECPPACK"] = "yowasp-ecppack"
    platform = DCNextPlatform()
    platform.build(Top(), 
        ecppack_opts=["--freq", "38.8"])