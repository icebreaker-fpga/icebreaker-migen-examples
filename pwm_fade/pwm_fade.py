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
        self.comb += If(direction,
                        counter.eq(~icounter[0:bitwidth])
                        ).Else(
                        counter.eq( icounter[0:bitwidth]))

        icounter_inv = Signal(bitwidth)
        self.comb += icounter_inv.eq(~icounter[0:bitwidth])
        self.sync += If(icounter_inv == 0,
                            icounter.eq(icounter + 2)
                        ).Else(
                            icounter.eq(icounter + 1))

class TickUpdownCounter(Module):
    def __init__(self, counter, tick, bitwidth):
        icounter = Signal(bitwidth+1)
        direction = Signal()

        self.comb += direction.eq(icounter[bitwidth])
        self.comb += If(direction,
                        counter.eq(~icounter[0:bitwidth])
                        ).Else(
                        counter.eq( icounter[0:bitwidth]))

        icounter_inv = Signal(bitwidth)
        self.comb += icounter_inv.eq(~icounter[0:bitwidth])
        self.sync += If(tick,
                        If((icounter_inv) == 0,
                            icounter.eq(icounter + 2)
                        ).Else(
                            icounter.eq(icounter + 1)))

class ClockDiv(Module):
    def __init__(self, divbitwidth, divout, divtick):
        divcounter = Signal(divbitwidth+1)
        # count every clock tick
        self.sync += divcounter.eq(divcounter + 1)
        # output 50% duty cycle clock output
        self.comb += divout.eq(divcounter[divbitwidth])
        # output a one clock wide strobe
        divcounter_inv = Signal(divbitwidth)
        self.comb += divcounter_inv.eq(~divcounter[0:divbitwidth])
        self.comb += divtick.eq(divcounter_inv == 0)

class PWMFade(Module):
    def __init__(self, pwm_signal, dbg, width, div):
        pwm_value = Signal(width)
        self.submodules.pwm = PWM(pwm_signal, width, pwm_value)

        updown_clock = Signal()
        updown_clock_strobe = Signal()
        self.submodules.updown_clk_div = \
            ClockDiv(div, updown_clock, updown_clock_strobe)

        self.submodules.updown = \
            TickUpdownCounter(pwm_value, updown_clock_strobe, width)
        self.comb += dbg.eq(updown_clock)

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
