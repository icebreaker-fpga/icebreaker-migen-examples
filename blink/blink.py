from migen import *
from migen.build.platforms import icebreaker

class Blinker(Module):
    def __init__(self, led, maxperiod):
        counter = Signal(max=maxperiod+1)
        period = Signal(max=maxperiod+1)
        self.comb += period.eq(maxperiod)
        self.sync += If(counter == 0,
                                led.eq(~led),
                                counter.eq(period)
                        ).Else(
                                counter.eq(counter - 1)
                        )

plat = icebreaker.Platform()
led = plat.request("user_ledr_n")
my_blinker = Blinker(led, 10000000)
plat.build(my_blinker)
plat.create_programmer().flash(0, 'build/top.bin')
