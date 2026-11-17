# Program the ATF1502AS with a USB-Blaster on Linux

## 1. Connect the board

Install all CPLDs in their sockets. Connect the USB-Blaster to **J9**, matching pin 1, and power the board with its normal 5 V supply. JTAG pin 4 supplies the adapter's target reference voltage; the USB-Blaster does not power the board. Keep power and the cable connected during programming. Do not enable Secure or disable JTAG.

## 2. Install the tools

On Ubuntu/Debian, run these commands from the root of this repository:

```bash
sudo apt update
sudo apt install git build-essential autoconf automake libtool pkg-config \
  libusb-1.0-0-dev libftdi1-dev python3 python3-pip openocd
REPO="$PWD"
git clone --branch v0.12.0 https://github.com/openocd-org/openocd.git /tmp/solderdemon-openocd
cd /tmp/solderdemon-openocd
git submodule update --init jimtcl
git apply "$REPO/tools/usb-blaster-bitbang.patch"
./bootstrap nosubmodule
./configure --disable-werror --enable-usb-blaster --disable-internal-libjaylink --disable-jlink
make -j"$(nproc)"
git clone https://github.com/whitequark/prjbureau.git /tmp/solderdemon-prjbureau
cd /tmp/solderdemon-prjbureau
git checkout 8b8a97122ec238b6a09868a4bc7def20acef798c
python3 -m pip install --target /tmp/solderdemon-python bitarray
```

USB access requires permission to use the adapter. The patched OpenOCD is built in `/tmp` and does not replace the system installation.

## 3. Program and verify

The firmware files correspond to the physical chips as follows, in JTAG order from TDI to TDO:

| Chip | Firmware |
|---|---|
| IC2 | `code/firmware/pld/cpld/bin/ic2_decoder.jed` |
| IC3 | `code/firmware/pld/cpld/bin/ic3_glue.jed` |

In the same terminal, select the files:

```bash
JEDS=(
  "$REPO/code/firmware/pld/cpld/bin/ic2_decoder.jed"  # IC2
  "$REPO/code/firmware/pld/cpld/bin/ic3_glue.jed"  # IC3
)
```

Convert each JEDEC file to SVF and program its chip. Each SVF erases, programs and verifies the device:

```bash
cd /tmp/solderdemon-prjbureau
OCD=/tmp/solderdemon-openocd/src/openocd
TAPS=''
for ((i=${#JEDS[@]}-1; i>=0; i--)); do
  TAPS+="jtag newtap cpld chip$i -irlen 10 -expected-id 0x0150203f; "
done
for ((i=0; i<${#JEDS[@]}; i++)); do
  PYTHONPATH=/tmp/solderdemon-python python3 -m util.fuseconv "${JEDS[i]}" "/tmp/solderdemon_$i.svf" || break
  "$OCD" -s /usr/share/openocd/scripts -f interface/altera-usb-blaster.cfg \
    -c "${TAPS}init; svf /tmp/solderdemon_$i.svf -tap cpld.chip$i -quiet -progress; shutdown" || break
  read -r -p "Check the output; press Enter for the next chip or Ctrl+C to stop "
done
```

Check that programming and verification succeed for each chip before continuing. OpenOCD can return exit code 0 even when it reports a JTAG error. The commands automatically reverse the chain for OpenOCD, which lists devices from TDO.
