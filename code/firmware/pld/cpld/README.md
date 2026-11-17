# SolderDemon m68k CPLD firmware: two ATF1502AS

Board revision 2.14 replaces the four ATF22V10C GALs of r2.13 (IC2 address decoder, IC3 DUART
select, IC5 general glue, IC6 watchdog) with two **ATF1502AS-10JU44** CPLDs in through-hole
PLCC-44 sockets, like the DUART IC4:

| Ref | Source | Does | Replaces |
|---|---|---|---|
| IC2 | [`ic2_decoder.pld`](ic2_decoder.pld) | address decode (RAM/ROM/IO/expansion), DTACK, WR, boot latch, ANYIACK | r2.13 IC2 + the boot counter and ANYIACK of IC5 |
| IC3 | [`ic3_glue.pld`](ic3_glue.pld) | DUART /CS and /IACK, RESET/HALT, RUN LED, bus-error watchdog | r2.13 IC3 + IC6 + the rest of IC5 |

IC2 production firmware **r1.1 (2026-11-17)** keeps the reset-vector ROM overlay until
the first normal read in **0xE00000-0xEFFFFF**, then selects RAM at low addresses.
It replaces the previous four-AS-edge boot counter. The reset PC must point into
high ROM, as the existing rosco firmware does. Both RESET and HALT clear BOOT;
a CPU RESET instruction alone does not remap RAM.

The assembled board's owner reported stable startup and reset with this handoff
after intermittent failures with the counter. Extra AS edges can reproduce early
RAM selection in the model; their physical presence has not been measured.
The unsuccessful reset_guard watchdog experiment is not part of production IC3.

The normal memory map, signal levels and physical pin assignments are unchanged.
BOOT and ANYIACK are internal to IC2; ANYIACK is also decoded in IC3. IC2 uses
24 pins and 14 macrocells, IC3 31 pins and 21 macrocells.
Use **bin/ic2_decoder.jed -> IC2** and **bin/ic3_glue.jed -> IC3** for production.
Historical counter images remain under diagnostics/legacy_as_counter/ for rollback.

## Building

```sh
./build.sh
```

It needs a running Docker: it uses the `dinoboards/cpld-toolchain` image (WinCUPL plus the
Atmel `find1502` fitter, see `tools/cpld-toolchain` in the workspace), writes `bin/*.jed`, and
fails if the fitter moved any pin away from where the `.pld` puts it -- the board is routed to
those pins.

## Checking the logic

```sh
python3 tools/verify_boot_handoff.py
python3 tools/verify_cpld.py [steps] [seed]
python3 tools/check_startup_fit.py
```

Run these commands from the mainboard directory. The first checks vector reads with
extra AS edges, high-ROM handoff, reset, byte lanes and write/IACK exclusions.
The second compares all 14 driven nets against real r2.13 GAL fuse maps, with
only their old BOOT counter output replaced by an independent Python reference
for the new handoff. It requires BOOT and BERR activity and exercises wired-AND
RESET/HALT/DTACK/BERR. This intentionally is not full legacy-counter equivalence.
The third checks the actual fitter equations, enables, next states, asynchronous
controls, clock assignments and pin placement against the CUPL sources.
The build script gates on the handoff and fitter checks after compiling.
These are zero-delay logic checks; they do not measure physical timing.

After validation, run `python3 tools/package_cpld.py` from the mainboard directory. It checks both fuse maps against the hardware-tested identities and writes [the production ZIP](release/solderdemon_m68k-cpld-r1.1.zip), with programming images, sources, fitter reports and SHA-256 checksums.

## Programming

For Linux and USB-Blaster, see the [ATF1502AS programming guide](../../../../docs/USB_BLASTER_ATF1502_PROGRAMMING.md).

For a standalone PLCC-44 breakout and USB-Blaster, see the
[step-by-step programming and chip-check note](PROGRAMMING.md).

The ATF1502AS is programmed in circuit over JTAG; the TL866/minipro cannot program it. Header J9
has the Altera/Atmel 10-pin layout (1 TCK, 2 GND, 3 TDO, 4 VCC, 5 TMS, 9 TDI, 10 GND) and the
two chips are chained TDI -> IC2 -> IC3 -> TDO, so IC2 is the first device in the chain. Use an
Atmel ATDH1150USB with ATMISP, or any FT232H/FT2232H adapter with OpenOCD (convert the `.jed` to
SVF first). The board must be powered while programming.

Both designs keep JTAG enabled (`JTAG = ON`) with the internal pull-ups on TDI and TMS. Do not
turn JTAG off: the chip can then only be recovered with a high-voltage programmer.

## Pinout

The `PIN` lines in the `.pld` files are the only place the pinout is written down;
`tools/cpld_sch.py` and `cpld_board.py` read them. They were chosen by
`cpld_board.py --suggest`, which puts each signal on the pin nearest to where its net already
runs on the board. To move a pin: edit the `.pld`, run `./build.sh`, `verify_cpld.py`, then
`cpld_sch.py`, `cpld_board.py` and `cpld_route.py` (see [design/README.md](../../../../design/README.md)).
