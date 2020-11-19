from nmigen.vendor.lattice_ecp5 import *
from nmigen.build import *
from nmigen_boards.resources import DirectUSBResource,RGBLEDResource,SPIFlashResources

class DCNextPlatform(LatticeECP5Platform):
    device      = "LFE5U-12F"
    package     = "BG256"
    speed       = "6"

    default_clk = "clk"

    resources = [
            Resource("clk", 0, Pins("K13", dir="i"),
                 Clock(48e6), Attrs(IO_TYPE="LVCMOS33")),

            Resource("usr_btn", 0, Pins("A15", dir="i"), Attrs(IO_TYPE="LVCMOS33")),

            Resource("osc_suspend", 0, Pins("P16", dir="o", invert=True), Attrs(IO_TYPE="LVCMOS33")),

            DirectUSBResource(0, d_p="G16", d_n="H15", pullup="G15", vbus_valid="J16"),

            Resource("spi", 0, 
                Subsignal("cs",   Pins("N8", dir="o", invert=True), Attrs(IO_TYPE="LVCMOS33")),
                Subsignal("cipo", Pins("T7", dir="i"), Attrs(IO_TYPE="LVCMOS33")),
                Subsignal("copi", Pins("T8", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
                Subsignal("wp",   Pins("M7", dir="o", invert=True), Attrs(IO_TYPE="LVCMOS33")),
                Subsignal("hold", Pins("N7", dir="o", invert=True), Attrs(IO_TYPE="LVCMOS33")),
            ),

            RGBLEDResource(0, r="B14", g="A14", b="B13", invert=True),
            RGBLEDResource(1, r="A13", g="B12", b="A12", invert=True),
            RGBLEDResource(2, r="B11", g="A11", b="B10", invert=True),
            RGBLEDResource(3, r="A10", g="B9",  b="A9",  invert=True),

    ]
    connectors = []
