from nmigen import *

class A2I(Elaboratable):
    def __init__(self):
        # Convert ASCII hex to nibble. Output 0 and raise err if out of range.
        self.din  = Signal(8)
        self.dout = Signal(4)
        self.err  = Signal()
    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.din):
            for i in "0123456789ABCDEF":
                if i.isalpha():
                    with m.Case(ord(i), ord(i.lower())):
                        m.d.comb += [
                            self.dout.eq(int(i, 16)),
                            self.err.eq(0)
                        ]
                else:
                    with m.Case(ord(i)):
                        m.d.comb += [
                            self.dout.eq(int(i, 16)),
                            self.err.eq(0)
                        ]
            with m.Default():
                m.d.comb += [
                    self.dout.eq(0),
                    self.err.eq(1)
                ]

        return m

I2A = Array([ord(i) for i in "0123456789ABCDEF"])