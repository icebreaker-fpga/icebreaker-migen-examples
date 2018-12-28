from migen import *
from migen.build.generic_platform import Pins
from migen.build.platforms import icebreaker

class SevenSegCounter(Module):
    def __init__(self, segment_pins, digit_sel):
        segment_count = len(segment_pins)
        segments = Signal(segment_count)
        counter = Signal(30)
        ones = Signal(4)
        tens = Signal(4)
        ones_segments = Signal(segment_count)
        tens_segments = Signal(segment_count)
        display_state = Signal(3)

        # Segment pins are active-low so invert here
        self.comb += [segment_pins[i].eq(~segments[i]) for i in range(segment_count)]
        self.comb += ones.eq(counter[21:25])
        self.comb += tens.eq(counter[25:30])
        self.comb += display_state.eq(counter[2:5])
        self.digit_to_segments(ones, ones_segments)
        self.digit_to_segments(tens, tens_segments)

        self.sync += counter.eq(counter + 1)
        self.sync += Case(display_state, {
            0: segments.eq(ones_segments),
            1: segments.eq(ones_segments),
            2: segments.eq(0),
            3: digit_sel.eq(0),
            4: segments.eq(tens_segments),
            5: segments.eq(tens_segments),
            6: segments.eq(0),
            7: digit_sel.eq(1),
        })

    def digit_to_segments(self, digit, segments):
        self.comb += Case(digit, {
            0x0: segments.eq(0b0111111),
            0x1: segments.eq(0b0000110),
            0x2: segments.eq(0b1011011),
            0x3: segments.eq(0b1001111),
            0x4: segments.eq(0b1100110),
            0x5: segments.eq(0b1101101),
            0x6: segments.eq(0b1111101),
            0x7: segments.eq(0b0000111),
            0x8: segments.eq(0b1111111),
            0x9: segments.eq(0b1101111),
            0xa: segments.eq(0b1110111),
            0xb: segments.eq(0b1111100),
            0xc: segments.eq(0b0111001),
            0xd: segments.eq(0b1011110),
            0xe: segments.eq(0b1111001),
            0xf: segments.eq(0b1110001),
        })

sevenseg_pmod = [
     ("segments", 0, Pins("PMOD1A:0")),
     ("segments", 1, Pins("PMOD1A:1")),
     ("segments", 2, Pins("PMOD1A:2")),
     ("segments", 3, Pins("PMOD1A:3")),
     ("segments", 4, Pins("PMOD1A:4")),
     ("segments", 5, Pins("PMOD1A:5")),
     ("segments", 6, Pins("PMOD1A:6")),
     ("digit_sel", 0, Pins("PMOD1A:7")),
]

plat = icebreaker.Platform()
plat.add_extension(sevenseg_pmod)
segments = [plat.request("segments") for i in range(7)]
digit_sel = plat.request("digit_sel")
my_counter = SevenSegCounter(segments, digit_sel)
plat.build(my_counter)
plat.create_programmer().flash(0, 'build/top.bin')
