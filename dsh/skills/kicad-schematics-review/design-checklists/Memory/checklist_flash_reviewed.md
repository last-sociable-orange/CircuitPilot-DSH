# Flash Memory (NOR / NAND / eMMC / UFS) Design Checklist

## 1. Device Selection

- [ ] Verify Flash type (NOR, NAND, eMMC, UFS) meets application requirements
- [ ] Verify density meets system storage requirements per datasheet
- [ ] Verify interface (parallel, SPI, QSPI, Octal, HyperBus, ONFI, Toggle) is compatible with host
- [ ] Verify operating voltage range matches available rails per datasheet
- [ ] Verify read/program/erase endurance meets application lifetime requirements per datasheet
- [ ] Verify data retention meets application requirements per datasheet

## 2. Power Supply

- [ ] Verify VDD (core supply) voltage per datasheet
- [ ] If VPP (programming voltage) required, verify voltage per datasheet
- [ ] For single-supply devices: verify no strict sequencing required (confirm per datasheet)
- [ ] Verify decoupling capacitor values and placement per datasheet recommendations
- [ ] Verify active current (read, program, erase) meets system power budget
- [ ] Verify standby and deep power-down currents meet system power budget

## 3. Bus Interface

### Parallel NOR Flash
- [ ] Verify address bus (A[0:N]) routing with matched length per datasheet guidelines
- [ ] Verify data bus (DQ[0:M]) routing with matched length
- [ ] Verify address + control vs. data length skew within timing budget
- [ ] Verify control signals (CE#, OE#, WE#, RP#/RESET#) are routed cleanly
- [ ] If series termination used (22-33 Ω), verify on address/control lines
- [ ] Verify setup/hold timing budget per datasheet

### SPI / QSPI / Octal NOR Flash
- [ ] Verify SCK, CS#, MOSI (SI), MISO (SO) routing with minimal length
- [ ] For QSPI: verify IO2, IO3 routing
- [ ] If series termination on SCK used, verify value per datasheet
- [ ] For Octal SPI / HyperBus: verify differential pair routing per datasheet guidelines

### NAND Flash (parallel)
- [ ] Verify ONFI or Toggle interface compliance per datasheet
- [ ] Verify data bus (DQ[0:7] or DQ[0:15]) routing with matched length
- [ ] Verify control signals (CLE, ALE, CE#, RE#, WE#, WP#, R/B#) routing

### SD Card (SDIO)
- [ ] Verify SD mode (1-bit, 4-bit, SPI) is compatible with host controller
- [ ] Verify pull-up resistor on CMD line (10 kΩ to VDD) per SD physical layer specification
- [ ] Verify pull-up resistors on DAT0-DAT3 lines (10 kΩ to VDD) per SD physical layer specification
- [ ] For SPI mode: verify pull-up on DO (MISO) if card drives it as open-drain — check per card datasheet
- [ ] Verify CLK line does NOT have a pull-up resistor (CLK is driven by host only)
- [ ] Verify series termination resistor (10-33 Ω) on CLK line near the host source
- [ ] Verify CLK, CMD, DAT0-DAT3 trace length matching per speed mode requirements
- [ ] If UHS-I support: verify impedance matching (50 Ω single-ended) per SD specification
- [ ] If UHS-II or UHS-III: verify differential pair routing for Tx/Rx lanes
- [ ] Verify card detect (CD) signal routing — mechanical switch or pull-up sensing on DAT3 per host design
- [ ] Verify write-protect switch (WP) signal routing if supported by host
- [ ] Verify VDD voltage (2.7-3.6V for SDSC/SDHC/SDXC; 1.7-1.95V for UHS-II) matches host rail
- [ ] Verify VDDQ (I/O voltage) is compatible with host interface per SD specification
- [ ] Verify decoupling capacitor close to card connector VDD pin
- [ ] Verify ESD protection on all SDIO signals (especially if card slot is accessible to user)

### eMMC / UFS
- [ ] Verify HS-MMC or UniPro/M-PHY interface compatibility per datasheet
- [ ] Verify CMD pull-up resistor (10-50 kΩ to VDDQ) per JEDEC specification — external recommended for robust initialization
- [ ] Verify DAT0 external pull-up resistor (10-50 kΩ to VDDQ) per JEDEC specification
- [ ] Verify DAT1-DAT7: eMMC device has internal pull-ups per JEDEC (connected to unused data lines; disconnected during active bus operation) — confirm host or external pull-ups provide coverage for active lines if needed
- [ ] Verify RST_N is not left floating — check if external pull-down (10-100 kΩ to GND) is required per eMMC datasheet; some devices have internal pull-down
- [ ] Verify DS (Data Strobe) pull-down resistor per JEDEC specification if HS400 mode is used
- [ ] Verify series termination resistor (10-33 Ω) on CLK line near the host source
- [ ] For HS400 mode: verify DS (Data Strobe) differential pair routing per JEDEC specification
- [ ] Verify differential pair routing for high-speed data lines (HS400, HS200)
- [ ] Verify boot partition configuration if used — check partition size and boot mode select per datasheet
- [ ] Verify RPMB (Replay Protected Memory Block) configuration if required for security application

## 4. NOR Flash Specific

- [ ] Verify erase block size per datasheet
- [ ] Verify page program size per datasheet
- [ ] Verify read/program/erase endurance per datasheet
- [ ] Verify data retention specification per datasheet
- [ ] Verify status register read capability
- [ ] Verify continuous read vs. page read mode configuration per datasheet
- [ ] Verify protection bits/lock status on first boot

## 5. SD Card Specific

- [ ] Verify SD standard compatibility (SDSC, SDHC, SDXC, SDUC) per application requirements
- [ ] Verify speed class rating meets write throughput requirements per SD specification (Class 2/4/6/10, UHS Speed Class 1/3, Video Speed Class)
- [ ] Verify initialization sequence: power-on → CMD0 (GO_IDLE) → CMD8 (SEND_IF_COND) → ACMD41 (SD_SEND_OP_COND) per SD specification
- [ ] Verify card detection mechanism (mechanical CD switch, pull-up sensing on DAT3, or in-band command)
- [ ] Verify write-protect handling (mechanical WP switch or software write-protect) if required
- [ ] Verify boot partition support if SD card used as boot device per host requirements
- [ ] For SPI mode: verify CS (chip select) handling per SPI specification
- [ ] If using SDIO: verify function initialization and interrupt handling per SDIO specification
- [ ] Verify clock frequency configuration per speed mode (normal: 0-25 MHz, high-speed: 0-50 MHz, UHS-I: up to 208 MHz)

## 6. NAND Flash Specific

- [ ] Verify page size per datasheet
- [ ] Verify block size per datasheet
- [ ] Implement bad block management (BBM) per manufacturer recommendation
- [ ] Implement wear leveling
- [ ] Implement ECC per manufacturer requirement (SLC: 1-4 bit per 512 bytes; MLC/TLC: more)
- [ ] Verify read disturb and program disturb management per datasheet
- [ ] For eMMC/UFS: verify controller handles BBM, wear leveling, and ECC internally
- [ ] Scan bad blocks on first boot
