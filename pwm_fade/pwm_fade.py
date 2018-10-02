# Small example fading the red led on the board up and down using PWM

from migen import *
from migen.build.platforms import icebreaker

class PWM(Module):
    def __init__(self, pwm, bitwidth, value):
        pwm_counter = Signal(bitwidth)
        self.comb += pwm.eq(pwm_counter < value)
        self.sync += pwm_counter.eq(pwm_counter + 1)

class UpdownCounter(Module):
    def __init__(self, counter, bitwidth):
        icounter = Signal(bitwidth+1)
        direction = Signal()
        self.comb += direction.eq(icounter[bitwidth])
        self.sync += If(direction,
                        counter.eq(~icounter[0:bitwidth])
                        ).Else(
                        counter.eq( icounter[0:bitwidth]))
        self.sync += icounter.eq(icounter + 1)

class PWMFade(Module):
    def __init__(self, pwm_signal, dbg, width, div):
        pwm_value = Signal(width)
        self.submodules.pwm = PWM(pwm_signal, width, pwm_value)
        counter = Signal(width+div)
        self.submodules.updown = UpdownCounter(counter, width+div)
        self.comb += pwm_value.eq(counter[div:width+div])
        self.comb += dbg.eq(counter[7])

def _test(dut):
    for i in range(1000):
        yield

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 1:
        if sys.argv[1] == "sim":
            pwm_out = Signal()
            dbg_sig = Signal()
            dut = PWMFade(pwm_out, dbg_sig, 4, 4)
            dut.clock_domains.cd_sys = ClockDomain("sys")
            run_simulation(dut, _test(dut), vcd_name="pwm_fade.vcd")
    else:
        plat = icebreaker.Platform()
        led = plat.request("user_ledr_n")
        dbg_led = plat.request("user_ledg_n")
        pwm_fade = PWMFade(led, dbg_led, 16, 9)
        plat.build(pwm_fade)
        plat.create_programmer().flash(0, 'build/top.bin')
