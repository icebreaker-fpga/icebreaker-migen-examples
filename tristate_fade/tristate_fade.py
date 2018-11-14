from migen import *
from migen.build.generic_platform import *
from migen.build.platforms import icebreaker

class PWM(Module):
    def __init__(self, pwm, bitwidth, value):
        pwm_counter = Signal(bitwidth)
        self.sync += pwm.eq(pwm_counter < value)
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

class TristatePins(Module):
    def __init__(self, n, pad, on, hiz):
        self.t = []
        for i in range(n):
            self.t.append(TSTriple())
            self.specials += self.t[i].get_tristate(pad[i])
            self.comb += self.t[i].o.eq(on[i])
            self.comb += self.t[i].oe.eq(~hiz[i])

class Fader(Module):
    def __init__(self, led):
        led_counter = Signal(3 + 1)
        pwm_counter_size = 11
        #pwm_counter_size = 3
        pwm_value_counter = Signal(pwm_counter_size)


        # divided clock for the updown counter
        updown_clk = Signal()
        updown_clk_strobe = Signal()
        self.submodules.updown_clk_div = \
            ClockDiv(pwm_counter_size, updown_clk, updown_clk_strobe)

        # pwm_value_counter
        # counts up down to make a single led fade in and out
        self.submodules.pwm_value_updown = \
            TickUpdownCounter(pwm_value_counter, updown_clk_strobe, pwm_counter_size)

        led_tick = Signal()
        prev_pwm_val_cnt = Signal(pwm_counter_size)
        self.sync += If((prev_pwm_val_cnt != pwm_value_counter) &
                            (pwm_value_counter == 0),
                            led_tick.eq(1),
                            prev_pwm_val_cnt.eq(pwm_value_counter)
                        ).Else(
                            led_tick.eq(0),
                            prev_pwm_val_cnt.eq(pwm_value_counter)
                        )

        # led counter:
        # Three top bits select which one of the led outputs is used
        # Fourth bit selects sign (high/low)
        self.submodules.tick_updown = \
            TickUpdownCounter(led_counter, led_tick, 3 + 1)

        # PWM generator
        pwm = Signal()
        self.submodules.pwm = PWM(pwm, pwm_counter_size, pwm_value_counter)

        # LEDs
        on = [Signal() for l in led]
        hiz = [Signal() for l in led]
        self.submodules.tri = TristatePins(len(led), led, on, hiz)

        # Select high/low aka red green led
        for o in on:
            self.comb += o.eq(led_counter[0])

        # Fade the specific led by PWMing the oe of the GPIO
        led_active = Signal(3)
        self.comb += led_active.eq(led_counter[1:4])
        self.comb += hiz[0].eq(~(pwm & (led_active == 0)))
        self.comb += hiz[1].eq(~(pwm & (led_active == 1)))
        self.comb += hiz[2].eq(~(pwm & (led_active == 2)))
        self.comb += hiz[3].eq(~(pwm & (led_active == 3)))
        self.comb += hiz[4].eq(~(pwm & (led_active == 4)))
        self.comb += hiz[5].eq(~(pwm & (led_active == 5)))
        self.comb += hiz[6].eq(~(pwm & (led_active == 6)))
        self.comb += hiz[7].eq(~(pwm & (led_active == 7)))

def _test(dut):
    for i in range(10000):
        yield

sim = False
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 1:
        if sys.argv[1] == "sim":
            sim = True
            pwm_out = Signal()
            dbg_sig = Signal()
            led = Signal(8)
            dut = Fader(led)
            dut.clock_domains.cd_sys = ClockDomain("sys")
            run_simulation(dut, _test(dut), vcd_name="tristate_fade.vcd")
    else:
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
        my_blinker = Fader(led)
        plat.build(my_blinker)
        plat.create_programmer().flash(0, 'build/top.bin')
