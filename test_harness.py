import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, ClockCycles, with_timeout, Timer
from cocotb.result import ReturnValue
from collections import namedtuple

NUMBER_OF_PROJECTS = 5
NUMBER_OF_PINS = 38

ADDR_PROJECT = 0x30000000
ADDR_OEB0    = 0x30000004
ADDR_OEB1    = 0x30000008
ADDR_WS2812  = 0x30000100
ADDR_7SEG    = 0x30000200

ADDR_FREQ    = 0x30000400


async def wishbone_write(dut, address, data):
    assert dut.wbs_ack_o == 0
    await RisingEdge(dut.wb_clk_i)
    dut.wbs_stb_i   <= 1
    dut.wbs_cyc_i   <= 1
    dut.wbs_we_i    <= 1        # write
    dut.wbs_sel_i   <= 0b1111   # select all bytes,      // which byte to read/write
    dut.wbs_dat_i   <= data
    dut.wbs_adr_i   <= address

    await with_timeout (RisingEdge(dut.wbs_ack_o), 100, 'us')
    await RisingEdge(dut.wb_clk_i)

    dut.wbs_cyc_i   <= 0
    dut.wbs_stb_i   <= 0
    dut.wbs_sel_i   <= 0
    dut.wbs_dat_i   <= 0
    dut.wbs_adr_i   <= 0

    await with_timeout (FallingEdge(dut.wbs_ack_o), 100, 'us')

async def wishbone_read(dut, address):
    assert dut.wbs_ack_o == 0
    await RisingEdge(dut.wb_clk_i)
    dut.wbs_stb_i   <= 1
    dut.wbs_cyc_i   <= 1
    dut.wbs_we_i    <= 0        # read
    dut.wbs_sel_i   <= 0b1111   # select all bytes,      // which byte to read/write
    dut.wbs_adr_i   <= address

    await with_timeout (RisingEdge(dut.wbs_ack_o), 100, 'us')
    await RisingEdge(dut.wb_clk_i)

    # grab data
    data = dut.wbs_dat_o

    dut.wbs_cyc_i   <= 0
    dut.wbs_stb_i   <= 0
    dut.wbs_sel_i   <= 0
    dut.wbs_dat_i   <= 0
    dut.wbs_adr_i   <= 0

    await with_timeout (FallingEdge(dut.wbs_ack_o), 100, 'us')

    return data

# reset
async def reset(dut):
    dut.la_data_in <= 0
    dut.wbs_cyc_i   <= 0
    dut.wbs_stb_i   <= 0
    dut.wbs_sel_i   <= 0
    dut.wbs_dat_i   <= 0
    dut.wbs_adr_i   <= 0

    dut.wb_rst_i <= 1;
    await ClockCycles(dut.wb_clk_i, 5)
    dut.wb_rst_i <= 0;
    await ClockCycles(dut.wb_clk_i, 5)

# bit-bang SPI data exchange
async def spix(dut, sig, v):
    tick = 7
    snd = v
    sig.ss <= False
    await ClockCycles(dut.wb_clk_i, tick)
    rcv = 0
    for i in range(16):
        sig.mosi <= (v >> 15)
        sig.sck <= True
        await ClockCycles(dut.wb_clk_i, tick)
        rcv = (rcv << 1) | sig.miso.value
        sig.sck <= False
        v <<= 1
        await ClockCycles(dut.wb_clk_i, tick)
    await ClockCycles(dut.wb_clk_i, tick)
    sig.ss <= True
    dut._log.info("SPI: snd %4.4x rcv %4.4x", snd, rcv)
    return rcv

@cocotb.test()
async def test_wb_access(dut):
    clock = Clock(dut.wb_clk_i, 10, units="us")
    cocotb.fork(clock.start())

    await reset(dut)

    for project_number in range(NUMBER_OF_PROJECTS):
        # activate design 1
        await wishbone_write(dut, ADDR_PROJECT, project_number)
        assert dut.active_project == project_number

        # check active design
        active_project = await wishbone_read(dut, ADDR_PROJECT)
        assert active_project == project_number

@cocotb.test()
async def test_oeb(dut):
    clock = Clock(dut.wb_clk_i, 10, units="us")
    cocotb.fork(clock.start())

    await reset(dut)

    for io in range(NUMBER_OF_PINS):
        # activate design 1
        if io < 32:
            await wishbone_write(dut, ADDR_OEB0, 1 << io )
            await wishbone_write(dut, ADDR_OEB1, 0)
        else:
            await wishbone_write(dut, ADDR_OEB0, 0)
            await wishbone_write(dut, ADDR_OEB1, 1 << (io - 32))
        assert dut.reg_oeb == 1 << io


@cocotb.test()
# 7 segment
async def test_project_0(dut):
    clock = Clock(dut.wb_clk_i, 10, units="us")
    cocotb.fork(clock.start())

    await reset(dut)

    # activate design 0
    project_number = 0
    await wishbone_write(dut, ADDR_PROJECT, project_number)
    assert dut.active_project == project_number

    # use a gpio as a clock
    io_clock = Clock(dut.io_in[0], 10, units="us")
    clk_gen = cocotb.fork(io_clock.start())

    # use external gpio as reset
    dut.io_in[1] <= 1
    await ClockCycles(dut.wb_clk_i, 5)
    dut.io_in[1] <= 0

    # update compare to 10 - will also reset the counter
    await wishbone_write(dut, ADDR_7SEG, 10)

    # wait some cycles
    await ClockCycles(dut.wb_clk_i, 10)
    assert dut.proj_0.digit == 1
    await ClockCycles(dut.wb_clk_i, 10)
    assert dut.proj_0.digit == 2

@cocotb.test()
# ws2812
async def test_project_1(dut):
    clock = Clock(dut.wb_clk_i, 10, units="us")
    cocotb.fork(clock.start())

    await reset(dut)

    # activate design 1
    project_number = 1
    await wishbone_write(dut, ADDR_PROJECT, project_number)
    assert dut.active_project == project_number

    # use a gpio as a clock
    io_clock = Clock(dut.io_in[0], 10, units="us")
    clk_gen = cocotb.fork(io_clock.start())

    # use external gpio as reset
    dut.io_in[1] <= 1
    await ClockCycles(dut.wb_clk_i, 5)
    dut.io_in[1] <= 0

    # setup a colour for some leds
    led_num = 7
    r = 255
    g = 10
    b = 100
    await wishbone_write(dut, ADDR_WS2812, (led_num << 24) + (r << 16) + (g << 8) + b)

    # wait some cycles
    await ClockCycles(dut.wb_clk_i, 500)

@cocotb.test()
# vga_clk
async def test_project_2(dut):
    clock = Clock(dut.wb_clk_i, 10, units="us")
    cocotb.fork(clock.start())

    await reset(dut)

    # activate design 2
    project_number = 2
    await wishbone_write(dut, ADDR_PROJECT, project_number)
    assert dut.active_project == project_number

    # use a gpio as a clock
    io_clock = Clock(dut.io_in[0], 10, units="us")
    clk_gen = cocotb.fork(io_clock.start())

    # use external gpio as reset
    dut.io_in[1] <= 1
    await ClockCycles(dut.wb_clk_i, 5)
    dut.io_in[1] <= 0

    # wait some cycles
    await ClockCycles(dut.wb_clk_i, 600*800)

@cocotb.test()
# spinet
async def test_project_3(dut):
    clock = Clock(dut.wb_clk_i, 10, units="us")
    cocotb.fork(clock.start())

    await reset(dut)

    # activate design 3
    project_number = 3
    await wishbone_write(dut, ADDR_PROJECT, project_number)
    assert dut.active_project == project_number

    # group SPI & ready signals for net nodes 0, 1
    SPIsigs = namedtuple('SPIsigs', 'miso mosi ss sck txrdy rxrdy')
    spi0 = SPIsigs(miso=dut.io_out[18], mosi=dut.io_in[0], ss=dut.io_in[12],
                      sck=dut.io_in[6], txrdy=dut.io_out[24], rxrdy=dut.io_out[30])
    spi1 = SPIsigs(miso=dut.io_out[19], mosi=dut.io_in[1], ss=dut.io_in[13],
                      sck=dut.io_in[7], txrdy=dut.io_out[25], rxrdy=dut.io_out[31])

    spi0.ss <= False
    spi1.ss <= False
    await ClockCycles(dut.wb_clk_i, 1)
    spi0.ss <= True
    spi1.ss <= True
    await ClockCycles(dut.wb_clk_i, 10)

    assert spi0.txrdy.value and spi1.txrdy.value
    assert (not spi0.rxrdy.value) and (not spi1.rxrdy.value)

    # node 0 sends one byte to node 1
    data = ord('B')
    ctl = 0x80 | (0<<0) | (1<<3)
    await spix(dut, spi0, (ctl<<8) | data)

    # node 1 waits for the byte and receives it
    #await RisingEdge(spi1.rxrdy)
    await ClockCycles(dut.wb_clk_i, 10)
    assert spi1.rxrdy.value
    rcv = await spix(dut, spi1, 0)

    # check data and sender address
    assert (rcv & 0xFF) == data and ((rcv>>8) & 0x7) == 0

@cocotb.test()
# MMM_SA_2by2_posit_4_0
async def test_project_2(dut):
    clock = Clock(dut.wb_clk_i, 10, units="us")
    cocotb.fork(clock.start())

    await reset(dut)

    # activate design 4
    project_number = 4
    await wishbone_write(dut, ADDR_PROJECT, project_number)
    assert dut.active_project == project_number

    # use a gpio as a clock
    io_clock = Clock(dut.io_in[0], 10, units="us")
    clk_gen = cocotb.fork(io_clock.start())

    # use external gpio as reset
    dut.io_in[1] <= 1
    dut.io_in[2] <= 0
    await ClockCycles(dut.wb_clk_i, 5)
    dut.io_in[1] <= 0
    dut.io_in[2] <= 1

    # wait some cycles
    await ClockCycles(dut.wb_clk_i, 8)


def int2bcd(v):
    out = 0
    for s in str(v):
        out = (out << 4) | int(s)
    return out


@cocotb.test()
# freq_cnt
async def test_project_4(dut):
    T_sys_clk = 100  # system clock period [ns] (10 MHz)
    T_sut_clk = 10  # signal under test period [ns] (100 MHz)
    meas_cycles = 0x100
    f_meter_value_expect = meas_cycles * T_sys_clk // T_sut_clk

    clock = Clock(dut.wb_clk_i, T_sys_clk, units="ns")
    cocotb.fork(clock.start())

    await reset(dut)

    # activate design 4
    project_number = 4
    await wishbone_write(dut, ADDR_PROJECT, project_number)
    assert dut.active_project == project_number

    # drive gpio25 which is the signal under test
    sut_clk = Clock(dut.io_in[25], T_sut_clk, units="ns")
    cocotb.fork(sut_clk.start())

    # Write to the 2 config registers
    await wishbone_write(dut, ADDR_FREQ, 4)  # min. UART clock divider
    await wishbone_write(dut, ADDR_FREQ + 4, meas_cycles)  # Meas. period cnt.
    await wishbone_write(dut, ADDR_FREQ + 0x14, 0b100000010)  # decimal dots

    # Make sure the Wishbone writes succeeded
    assert dut.proj_4.serial.uart.divisor == 4
    assert dut.proj_4.f_meter.period == meas_cycles
    assert dut.proj_4.seven_seg.decimal_pts == 0b100000010

    # Wait for the measurement cycle to complete ...
    # first count is incomplete due to wishbone write, wait for second one
    await RisingEdge(dut.proj_4.b2bcd_trig_out)
    await RisingEdge(dut.proj_4.b2bcd_trig_out)

    # .vcd file does not match testbench state at this point ... WTF???
    # import pdb; pdb.set_trace()
    await ClockCycles(dut.wb_clk_i, 1)  # this works around it

    # Compare simulation values against expected values
    assert dut.proj_4.f_meter_value == f_meter_value_expect
    assert dut.proj_4.b2bcd_bcd_out == int2bcd(f_meter_value_expect)

    # Read the current frequency counter value
    readVal = await wishbone_read(dut, ADDR_FREQ + 0x18)  # periodic count val.
    assert readVal == f_meter_value_expect
