from migen import *
from migen.build.generic_platform import *
from migen.build.platforms import icebreaker

class TristatePins(Module):
    def __init__(self, n, pad, on, hiz):
        self.t = []
        for i in range(n):
            self.t.append(TSTriple())
            self.specials += self.t[i].get_tristate(pad[i])
            self.comb += self.t[i].o.eq(on[i])
            self.comb += self.t[i].oe.eq(~hiz[i])

class Blinker(Module):
    def __init__(self, led, maxperiod):
        counter = Signal(max=maxperiod+1)
        period = Signal(max=maxperiod+1)
        state_counter = Signal(2);

        # Timer
        self.comb += period.eq(maxperiod)
        self.sync += If(counter == 0,
                                    state_counter.eq(state_counter + 1),
                                    counter.eq(period)
                            ).Else(
                                    counter.eq(counter - 1)
                            )

        # LEDs
        on = [Signal() for l in led]
        hiz = [Signal() for l in led]
        self.submodules.tri = TristatePins(len(led), led, on, hiz)
        for h in hiz:
            self.comb += h.eq(state_counter[0])
        for o in on:
            self.comb += o.eq(state_counter[1])


plat = icebreaker.Platform()
plat.add_extension([
    ("triled", 0, Pins("PMOD1B:0")),
    ("triled", 1, Pins("PMOD1B:1")),
    ("triled", 2, Pins("PMOD1B:2")),
    ("triled", 3, Pins("PMOD1B:3")),
    ("triled", 4, Pins("PMOD1B:4")),
    ("triled", 5, Pins("PMOD1B:5")),
    ("triled", 6, Pins("PMOD1B:6")),
    ("triled", 7, Pins("PMOD1B:7")),
])
led = [plat.request("triled") for i in range(8)]
my_blinker = Blinker(led, 10000000)
plat.build(my_blinker)
plat.create_programmer().flash(0, 'build/top.bin')
