from nmigen import *
import colorsys

class RgbController(Elaboratable):
    def __init__(self, leds):
        self.leds = leds
        color_array = [
            tuple(map(lambda c: int(c * 256), colorsys.hsv_to_rgb(i/256, 1, .05)))
            for i in range(256)
        ]
        self.r_array = Array([c[0] for c in color_array])
        self.g_array = Array([c[1] for c in color_array])
        self.b_array = Array([c[2] for c in color_array])

    def elaborate(self, platform):
        m = Module()

        clk_freq = platform.default_clk_frequency if platform else 1e4
        timer = Signal(range(int(clk_freq//128)), reset=int(clk_freq//128) - 1)

        pwm_ctr = Signal(8)
        array_ctr = Signal(8)

        m.d.sync += pwm_ctr.eq(pwm_ctr - 1)

        with m.If(timer == 0):
            m.d.sync += [
                timer.eq(timer.reset),
                array_ctr.eq(array_ctr + 1)
            ]
        with m.Else():
            m.d.sync += timer.eq(timer - 1)

        idx_offset = 256 // len(self.leds)
        for idx, led in enumerate(self.leds):
            offset = idx_offset * idx
            r_latch = Signal(8)
            g_latch = Signal(8)
            b_latch = Signal(8)

            array_idx = Signal(8, reset=offset)

            m.d.comb += [
                array_idx.eq(offset + array_ctr),
                led.r.eq(r_latch > pwm_ctr),
                led.g.eq(g_latch > pwm_ctr),
                led.b.eq(b_latch > pwm_ctr)
            ]

            with m.If(pwm_ctr == 0):
                m.d.sync += [
                    r_latch.eq(self.r_array[array_idx]),
                    g_latch.eq(self.g_array[array_idx]),
                    b_latch.eq(self.b_array[array_idx])
                ]

        return m

if __name__ == "__main__":
    from nmigen.sim import Simulator
    leds = [Record([("r", 1), ("g", 1), ("b", 1)]) for _ in range(4)]
    rgb = RgbController(leds)
    sim = Simulator(rgb)
    with sim.write_vcd("rgb.vcd"):
        sim.add_clock(1e-4)
        sim.run_until(256, run_passive=True)