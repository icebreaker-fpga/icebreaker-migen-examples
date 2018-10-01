# This example is based on Whitequark's lab notebook
# https://lab.whitequark.org/notes/2016-10-18/implementing-an-uart-in-verilog-and-migen/

from migen import *
from migen.genlib.fsm import *


def _divisor(freq_in, freq_out, max_ppm=None):
    divisor = freq_in // freq_out
    if divisor <= 0:
        raise ArgumentError("output frequency is too high")

    ppm = 1000000 * ((freq_in / divisor) - freq_out) / freq_out
    if max_ppm is not None and ppm > max_ppm:
        raise ArgumentError("output frequency deviation is too high")

    return divisor


class UART(Module):
    def __init__(self, serial, clk_freq, baud_rate):
        self.rx_data = Signal(8)
        self.rx_ready = Signal()
        self.rx_ack = Signal()
        self.rx_error = Signal()

        self.tx_data = Signal(8)
        self.tx_ready = Signal()
        self.tx_ack = Signal()

        divisor = _divisor(freq_in=clk_freq, freq_out=baud_rate, max_ppm=50000)

        ###

        rx_counter = Signal(max=divisor)
        self.rx_strobe = rx_strobe = Signal()
        self.comb += rx_strobe.eq(rx_counter == 0)
        self.sync += \
            If(rx_counter == 0,
                rx_counter.eq(divisor - 1)
            ).Else(
                rx_counter.eq(rx_counter - 1)
            )

        self.rx_bitno = rx_bitno = Signal(3)
        self.submodules.rx_fsm = FSM(reset_state="IDLE")
        self.rx_fsm.act("IDLE",
            If(~serial.rx,
                NextValue(rx_counter, divisor // 2),
                NextState("START")
            )
        )
        self.rx_fsm.act("START",
            If(rx_strobe,
                NextState("DATA")
            )
        )
        self.rx_fsm.act("DATA",
            If(rx_strobe,
                NextValue(self.rx_data, Cat(self.rx_data[1:8], serial.rx)),
                NextValue(rx_bitno, rx_bitno + 1),
                If(rx_bitno == 7,
                    NextState("STOP")
                )
            )
        )
        self.rx_fsm.act("STOP",
            If(rx_strobe,
                If(~serial.rx,
                    NextState("ERROR")
                ).Else(
                    NextState("FULL")
                )
            )
        )
        self.rx_fsm.act("FULL",
            self.rx_ready.eq(1),
            If(self.rx_ack,
                NextState("IDLE")
            ).Elif(~serial.rx,
                NextState("ERROR")
            )
        )
        self.rx_fsm.act("ERROR",
            self.rx_error.eq(1))

        ###

        tx_counter = Signal(max=divisor)
        self.tx_strobe = tx_strobe = Signal()
        self.comb += tx_strobe.eq(tx_counter == 0)
        self.sync += \
            If(tx_counter == 0,
                tx_counter.eq(divisor - 1)
            ).Else(
                tx_counter.eq(tx_counter - 1)
            )

        self.tx_bitno = tx_bitno = Signal(3)
        self.tx_latch = tx_latch = Signal(8)
        self.submodules.tx_fsm = FSM(reset_state="IDLE")
        self.tx_fsm.act("IDLE",
            self.tx_ack.eq(1),
            If(self.tx_ready,
                NextValue(tx_counter, divisor - 1),
                NextValue(tx_latch, self.tx_data),
                NextState("START")
            ).Else(
                NextValue(serial.tx, 1)
            )
        )
        self.tx_fsm.act("START",
            If(self.tx_strobe,
                NextValue(serial.tx, 0),
                NextState("DATA")
            )
        )
        self.tx_fsm.act("DATA",
            If(self.tx_strobe,
                NextValue(serial.tx, tx_latch[0]),
                NextValue(tx_latch, Cat(tx_latch[1:8], 0)),
                NextValue(tx_bitno, tx_bitno + 1),
                If(self.tx_bitno == 7,
                    NextState("STOP")
                )
            )
        )
        self.tx_fsm.act("STOP",
            If(self.tx_strobe,
                NextValue(serial.tx, 1),
                NextState("IDLE")
            )
        )


class _TestPads(Module):
    def __init__(self):
        self.rx = Signal(reset=1)
        self.tx = Signal()


def _test_rx(rx, dut):
    def T():
        yield; yield; yield; yield
    def B(bit):
        yield rx.eq(bit)
        yield from T()
    def S():
        yield from B(0)
        assert (yield dut.rx_error) == 0
        assert (yield dut.rx_ready) == 0
    def D(bit):
        yield from B(bit)
        assert (yield dut.rx_error) == 0
        assert (yield dut.rx_ready) == 0
    def E():
        yield from B(1)
        assert (yield dut.rx_error) == 0
    def O(bits):
        yield from S()
        for bit in bits:
            yield from D(bit)
        yield from E()

    def A(octet):
        yield from T()
        assert (yield dut.rx_data) == octet
        yield dut.rx_ack.eq(1)
        while (yield dut.rx_ready) == 1: yield
        yield dut.rx_ack.eq(0)
    def F():
        yield from T()
        assert (yield dut.rx_error) == 1
        yield rx.eq(1)
        yield dut.cd_sys.rst.eq(1)
        yield
        yield
        yield dut.cd_sys.rst.eq(0)
        yield
        yield
        assert (yield dut.rx_error) == 0

    # bit patterns
    yield from O([1, 0, 1, 0, 1, 0, 1, 0])
    yield from A(0x55)
    yield from O([1, 1, 0, 0, 0, 0, 1, 1])
    yield from A(0xC3)
    yield from O([1, 0, 0, 0, 0, 0, 0, 1])
    yield from A(0x81)
    yield from O([1, 0, 1, 0, 0, 1, 0, 1])
    yield from A(0xA5)
    yield from O([1, 1, 1, 1, 1, 1, 1, 1])
    yield from A(0xFF)

    # framing error
    yield from S()
    for bit in [1, 1, 1, 1, 1, 1, 1, 1]:
        yield from D(bit)
    yield from S()
    yield from F()

    # overflow error
    yield from O([1, 1, 1, 1, 1, 1, 1, 1])
    yield from B(0)
    yield from F()


def _test_tx(tx, dut):
    def Th():
        yield; yield
    def T():
        yield; yield; yield; yield
    def B(bit):
        yield from T()
        assert (yield tx) == bit
    def S(octet):
        assert (yield tx) == 1
        assert (yield dut.tx_ack) == 1
        yield dut.tx_data.eq(octet)
        yield dut.tx_ready.eq(1)
        while (yield tx) == 1: yield
        yield dut.tx_ready.eq(0)
        assert (yield tx) == 0
        assert (yield dut.tx_ack) == 0
        yield from Th()
    def D(bit):
        assert (yield dut.tx_ack) == 0
        yield from B(bit)
    def E():
        assert (yield dut.tx_ack) == 0
        yield from B(1)
        yield from Th()
    def O(octet, bits):
        yield from S(octet)
        for bit in bits:
            yield from D(bit)
        yield from E()

    yield from O(0x55, [1, 0, 1, 0, 1, 0, 1, 0])
    yield from O(0x81, [1, 0, 0, 0, 0, 0, 0, 1])
    yield from O(0xFF, [1, 1, 1, 1, 1, 1, 1, 1])
    yield from O(0x00, [0, 0, 0, 0, 0, 0, 0, 0])


def _test(tx, rx, dut):
    yield from _test_rx(rx, dut)
    yield from _test_tx(tx, dut)


class _LoopbackTest(Module):
    def __init__(self, platform):
        serial = platform.request("serial")
        leds   = Cat([platform.request("user_ledr_n"), platform.request("user_ledg_n")])
        debug  = platform.request("debug")

        self.submodules.uart = UART(serial, clk_freq=12000000, baud_rate=115200)

        empty = Signal(reset=1)
        data = Signal(8)
        rx_strobe = Signal()
        tx_strobe = Signal()
        self.comb += [
            rx_strobe.eq(self.uart.rx_ready & empty),
            tx_strobe.eq(self.uart.tx_ack & ~empty),
            self.uart.rx_ack.eq(rx_strobe),
            self.uart.tx_data.eq(data),
            self.uart.tx_ready.eq(tx_strobe)
        ]
        self.sync += [
            If(rx_strobe,
                data.eq(self.uart.rx_data),
                empty.eq(0)
            ),
            If(tx_strobe,
                empty.eq(1)
            )
        ]

        self.comb += [
            leds.eq(self.uart.rx_data[0:2]),
            debug.eq(Cat(
                serial.rx,
                serial.tx,
                self.uart.rx_strobe,
                self.uart.tx_strobe,
                # self.uart.rx_fsm.ongoing("IDLE"),
                # self.uart.rx_fsm.ongoing("START"),
                # self.uart.rx_fsm.ongoing("DATA"),
                # self.uart.rx_fsm.ongoing("STOP"),
                # self.uart.rx_fsm.ongoing("FULL"),
                # self.uart.rx_fsm.ongoing("ERROR"),
                # self.uart.tx_fsm.ongoing("IDLE"),
                # self.uart.tx_fsm.ongoing("START"),
                # self.uart.tx_fsm.ongoing("DATA"),
                # self.uart.tx_fsm.ongoing("STOP"),
            ))
        ]


if __name__ == "__main__":
    import sys
    if sys.argv[1] == "sim":
        pads = _TestPads()
        dut = UART(pads, clk_freq=4800, baud_rate=1200)
        dut.clock_domains.cd_sys = ClockDomain("sys")
        run_simulation(dut, _test(pads.tx, pads.rx, dut), vcd_name="uart.vcd")
    elif sys.argv[1] == "loopback":
        from migen.build.generic_platform import *
        from migen.build.platforms import icebreaker

        plat = icebreaker.Platform()

        # The debug pins are on the PMOD1A in the following order on the connector:
        # 7 8 9 10 1 2 3 4
        # Yes that means that the pins at the edge of the board come first
        # and the pins further away from the edge second
        plat.add_extension([
            ("debug", 0, Pins("3 48 46 44 4 2 47 45"))
        ])

        plat.build(_LoopbackTest(plat))
        plat.create_programmer().flash(0, "build/top.bin")
