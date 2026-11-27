# MCB-01 schematic build — page & net specification (V1.0)

Source of record: `Document/DesignDoc/主控核心板_硬件设计说明书_V3.4.md` (HW-DD-MCB-001 V3.4).
This file fixes the decisions that the document leaves open — page split, reference
designators, global net names — so the seven pages agree with each other. Where the
document and this file disagree, **this file wins** for references and net names; the
document wins for component values and circuit topology, except at the places listed
under §9 *Deviations* below.

Parts may only be placed through the component database: every netlist component is
identified by `lcsc` (or `mpn`, exact match), never by a library id. Symbols,
footprints and values come from `kicad_lib/components.db` via
`kicad_lib/components_db_windows.kicad_dbl`.

Pin numbers are the **numbers of the symbol**, and the authority for them is
`kicad_lib/manifest.json` (downloaded parts) and `kicad_lib/Symbol/Standard/Standard.kicad_sym`
(passives). Never guess a pin number.

---

## 1. Pages

| # | Netlist | Page file | Contents | Doc section |
|---|---|---|---|---|
| 1 | `Document/Netlist/MCU.json` | `Design/MCU.kicad_sch` | STM32H743VGT6, 25 MHz crystal, decoupling, VCAP, analog front end, reset/boot, board LED | §2.4, §6.2, §8.1 |
| 2 | `Document/Netlist/Power.json` | `Design/Power.kicad_sch` | input protection, 3.3 V buck, 8 channel load switches | §5.2–§5.4, §8.2 |
| 3 | `Document/Netlist/USB.json` | `Design/USB.kicad_sch` | USB-C receptacle, CH132B ULPI PHY, 12 MHz crystal, USB ESD | §8.3 |
| 4 | `Document/Netlist/Channel_1-4.json` | `Design/Channel_1-4.kicad_sch` | J1–J4 channel interfaces: bead, bulk + HF caps, ESD, series resistors | §7, §8.3 |
| 5 | `Document/Netlist/Channel_5-8.json` | `Design/Channel_5-8.kicad_sch` | J5–J8, identical to page 4 | §7, §8.3 |
| 6 | `Document/Netlist/Sync.json` | `Design/Sync.kicad_sch` | SYNC buffer + 8-way star, external timebase input J11 | §3.4, §3.5 |
| 7 | `Document/Netlist/Indicator.json` | `Design/Indicator.kicad_sch` | AW21024 + 8 RGB channel LEDs | §6.1 |

`MainController.kicad_sch` stays the empty top page; the user links these seven pages
into it by hand. Pages are therefore built as standalone root schematics, and every
net that leaves a page carries a **global label** (the builder is invoked with
`--label-type global_label`).

---

## 2. Reference designators (global allocation — do not re-use a number)

| Prefix | Allocation |
|---|---|
| `U` | U2 = buck, U3 = MCU, U5 = CH132B, U6 = 74LVC1G125, U7 = AW21024 |
| `Y` | Y1 = 25 MHz (MCU), Y2 = 12 MHz (USB) |
| `L` | L1 = 2.2 µH (Power) |
| `F` | F1 = PTC fuse (Power) |
| `Q` | Q1 = AO3401A (Power) |
| `SW` | SW1…SW8 = SY6280AAC, CH1…CH8 (Power) |
| `J` | J1…J8 = channel connectors, J9 = USB-C, J11 = external timebase. **J10 does not exist in this build** |
| `FB` | FB1…FB8 = channel beads, FB9 = VDDA bead (MCU), FB10 = VLED bead (Indicator) |
| `D` | D1 = SMBJ6.0A, D2 = XL-1615SURUGC dual LED, D3 = D5V0F4U6SO-7 (USB ESD), D4…D11 = SRV05-4 per channel 1…8, D12…D19 = ES06D1HA03 per channel 1…8 |
| `LED` | LED1…LED8 = RGB channel indicator 1…8 |
| `R` | MCU R1…R8 and R10, Power R11…R31, USB R9 and R32…R34, Channel R35…R50, Sync R51…R61, Indicator R62…R89 (see the per-page lists) |
| `C` | MCU C1…C18, Power C19…C33, USB C34…C37, Channel C38…C53 (8 per page), Sync C54, C55, Indicator C56…C58 (see the per-page lists) |

Numbering inside a page must be exactly as listed in §4…§10 — the page builders and the
reviewer compare against this table, and duplicate references across pages make the
assembled board BOM wrong.

---

## 3. Global net glossary (exact spelling, used verbatim on every page)

Power:

| Net | Meaning |
|---|---|
| `VBUS` | 5 V from the USB-C receptacle, before the fuse |
| `VBUS_PROT` | after F1 and D1, at Q1 drain |
| `5V_SYS` | system 5 V after the reverse-polarity FET |
| `3V3` | 3.3 V main rail |
| `VDDA` | 3.3 V after FB9 (analog) |
| `5V_CH1` … `5V_CH8` | channel supply after the bead, at the connector |
| `5V_CH1_SW` … `5V_CH8_SW` | channel supply at the load-switch output, before the bead |
| `5V_LED` | 5 V after FB10, at AW21024 VLED |
| `3V3_EXT` | 3.3 V reference handed to an external timebase |
| `GND` | ground |

Control and status:

`SYNC` (MCU PA8 / buffer input), `SYNC_EN` (MCU PA9 / buffer `/OE`), `SYNC_DIST`
(buffer output), `SYNC_CH1`…`SYNC_CH8` (after the 100 Ω series resistors),
`SYNC_IN` (conditioned external sync at the MCU), `SYNC_IN_RAW` (at J11 pin 1),
`CH1_EN`…`CH8_EN`, `3V3_PG`, `LED_EN`, `LED_G`, `LED_R`,
`VBUS_SENSE`, `3V3_SENSE` (divider midpoints).

Serial links — direction is named from the MCU's point of view, and the node-side net
carries the `_P` (protected) suffix because it sits on the connector side of the 33 Ω
series resistor:

| Net | Path |
|---|---|
| `CH1_TX` … `CH8_TX` | MCU TX pin → 33 Ω pin 1 |
| `CH1_TX_P` … `CH8_TX_P` | 33 Ω pin 2 → ESD → connector pin 4 (node RX) |
| `CH1_RX_P` … `CH8_RX_P` | connector pin 3 (node TX) → ESD → 33 Ω pin 1 |
| `CH1_RX` … `CH8_RX` | 33 Ω pin 2 → MCU RX pin |

USB / ULPI:

`USB_DP`, `USB_DN`, `USB_CC1`, `USB_CC2`, `USB_SHIELD`,
`ULPI_CK`, `ULPI_DIR`, `ULPI_NXT`, `ULPI_STP`, `ULPI_D0`…`ULPI_D7`,
`PHY_XI`, `PHY_XO`.

Indicator: `I2C4_SCL`, `I2C4_SDA`, `LED1_R`, `LED1_G`, `LED1_B` … `LED8_R`, `LED8_G`, `LED8_B`.

---

## 4. Page 1 — MCU (`Document/Netlist/MCU.json`)

Components (30): `U3` C730183; `Y1` C20612972; `C1`,`C2` C106997 15pF; `C3`…`C12`
C5350800 100nF; `C14`,`C15` C53222698 4.7 µF; `C16`,`C17` C20539421 2.2 µF; `C18`
C20070242 1 µF; `FB9` C107335; `R1` C25744 10k; `R2` C25741 100k; `R3`,`R4` C25779 33k;
`R5`,`R6` C25779 33k; `R7`,`R8` C54920677 470R; `R10` C44183161 0R; `D2` C965839.
(`C13`, the eleventh 100 nF of the MCU subsystem, sits on the Sync page as `U6`'s VCC
decoupling — see §8.)

Nets (pin names in brackets, resolve to numbers from the manifest):

| Net | Members |
|---|---|
| `3V3` | U3 [VDD] ×5, U3 [VBAT], C3…C7 pin 1, C14 pin 1, C15 pin 1, C8 pin 1, R1 pin 1, R5 pin 1, R7 pin 1, R8 pin 1, FB9 pin 1 |
| `VDDA` | FB9 pin 2, U3 [VDDA], U3 [VREF+], C10 pin 1, C11 pin 1, C12 pin 1, C18 pin 1 |
| `GND` | U3 every [VSS] and [VSSA] pin, C1 pin 2, C2 pin 2, C3…C18 pin 2 (C16/C17 pin 2 included), R2 pin 2, R4 pin 2, R6 pin 2, Y1 ground pins, FB9 — none |
| `NRST` | U3 [NRST], R1 pin 2, C9 pin 1 |
| `BOOT0` | U3 [BOOT0], R2 pin 1 |
| `VCAP1` / `VCAP2` | U3 [VCAP1]→C16 pin 1; U3 [VCAP2]→C17 pin 1 |
| `HSE_IN` | U3 [OSC_IN / PH0], Y1 pin 1, C1 pin 1 |
| `HSE_OUT` | U3 [OSC_OUT / PH1], R10 pin 1 |
| `HSE_XO` | R10 pin 2, Y1 pin 3, C2 pin 1 |
| `VBUS` | R3 pin 1 |
| `VBUS_SENSE` | R3 pin 2, R4 pin 1, U3 [PA6 / ADC1_INP3] |
| `3V3_SENSE` | R5 pin 2, R6 pin 1, U3 [PA7 / ADC1_INP7] |
| `LED_G` | U3 [PD1], D2 green cathode |
| `LED_R` | U3 [PD5], D2 red cathode |
| cross-page outputs | `SYNC` U3 [PA8]; `SYNC_EN` U3 [PA9]; `SYNC_IN` U3 [PA15]; `3V3_PG` U3 [PD7]; `LED_EN` U3 [PD10]; `I2C4_SCL` U3 [PD12]; `I2C4_SDA` U3 [PD13]; `CH1_EN`…`CH8_EN` U3 [PB2, PB3, PB4, PB8, PB9, PD0, PD3, PD4] |
| ULPI | `ULPI_STP` U3 [PC0]; `ULPI_DIR` U3 [PC2_C]; `ULPI_NXT` U3 [PC3_C]; `ULPI_D0`…`ULPI_D7` U3 [PA3, PB0, PB1, PB10, PB11, PB12, PB13, PB5]; `ULPI_CK` U3 [PA5] |
| UART | CH1 `CH1_TX` [PA0], `CH1_RX` [PA1]; CH2 [PA2, PD6]; CH3 [PB14, PB15]; CH4 [PD8, PD9]; CH5 [PC12, PD2]; CH6 [PC6, PC7]; CH7 [PE8, PE7]; CH8 [PE1, PE0] |

Rules for this page:

- `C9` sits on `NRST` to `GND` (reset RC), `C8` on `3V3` (VBAT decoupling).
- The five 100 nF `C3`…`C7` are one per `VDD` pin; `C10`, `C11` are the `VDDA` and
  `VREF+` high-frequency parts after the bead and `C12` is an additional 100 nF on
  the `VDDA` branch. The eleventh 100 nF of the subsystem, `C13`, is `U6`'s VCC
  decoupling on the Sync page — the document counts those eleven parts inside the
  MCU subsystem, and the buffer is one of them.
- `VCAP1`/`VCAP2` each get their own 2.2 µF to `GND` and nothing in parallel
  (DS requirement); do not add a third capacitor.
- Every unused MCU pin is deliberately left out of the netlist (they will show up as
  floating pins in the build report — that is expected).
- `D2` is the dual-colour board LED; its two anodes both go through `R7`/`R8` to `3V3`,
  its cathodes to `PD1`/`PD5` (§6.2 of the document).

## 5. Page 2 — Power (`Document/Netlist/Power.json`) — page size A2

Components (49): `F1` C720075; `D1` C113976; `Q1` C347476; `R11` C25741 100k; `C19` C1524 10nF;
`C20` C5448891 10 µF; `C21` C5350800 100nF; `U2` C53368594; `L1` C315717; `C22`,`C23`
C56321508 22 µF; `C24` C5350800 100nF; `R12` C324855 45.3k; `R13` C25744 10k; `C25` C106200
100pF; `R14` C25741 100k; `R15` C25741 100k; `SW1`…`SW8` C55136; `R16`…`R23` C324962 68.1k;
`R24`…`R31` C25741 100k; `C26`…`C33` C20070242 1 µF.

Topology:

- `VBUS` → F1 pin 1; F1 pin 2 = `VBUS_PROT` = D1 cathode, Q1 drain.
- D1 anode → `GND`. Q1 source = `5V_SYS`. Q1 gate = `Q1_GATE` → R11 pin 1, C19 pin 1;
  R11 pin 2 and C19 pin 2 → `GND`.
- `5V_SYS`: Q1 source, C20 pin 1, C21 pin 1, U2 [IN], R14 pin 1, SW1…SW8 [IN].
- `EN_3V3`: R14 pin 2, U2 [EN]. `5V_SYS` also feeds FB10 on the Indicator page (no
  member on this page).
- `SW_3V3`: U2 [SW], L1 pin 1. `3V3`: L1 pin 2, C22 pin 1, C23 pin 1, C24 pin 1,
  R12 pin 1, C25 pin 1, R15 pin 1.
- `3V3_FB`: R12 pin 2, R13 pin 1, C25 pin 2, U2 [FB]. R13 pin 2 → `GND`.
- `3V3_PG`: U2 [PG], R15 pin 2, and the MCU page's PD7 (cross-page member is only this
  page's two parts).
- Channel switch *n* (n = 1…8): `5V_SYS` → SWn [IN] and C(25+n) pin 1;
  `CHn_EN` → SWn [EN] and R(23+n) pin 1; `GND` → R(23+n) pin 2 and C(25+n) pin 2;
  `ILIM_n` → SWn [ILIM] and R(15+n) pin 1; R(15+n) pin 2 → `GND`;
  `5V_CHn_SW` → SWn [OUT].
- `GND`: U2 [GND], C19/C20/C21/C22/C23/C24/C26…C33 pin 2, R11/D1 anodes, R13 pin 2,
  R16…R31 pin 2, D1 anode, SW1…SW8 [GND].
- Soft-start on the channel switches is internal; do **not** add parts.

## 6. Page 3 — USB (`Document/Netlist/USB.json`)

Components (12): `J9` C2906289; `R9` C25092 22R; `R32`,`R33` C25905 5.1k; `R34` C44183161 0R;
`C34` C696917 4.7nF; `D3` C19723969; `U5` C41416597; `Y2` C7420719; `C35`,`C36` C5350800
100nF; `C37` C53222698 4.7 µF.

- `VBUS`: J9 pins `A4B9` and `B4A9`, D3 [VDD] (pin 5), and it leaves the page to F1.
- `GND`: J9 pins `A1B12` and `B1A12`, D3 [GND] (pin 2), U5 pins 24 and 33, and
  C34/C35/C36/C37 pin 2.
- `USB_SHIELD`: J9 pin `0` (the four shell tabs), R34 pin 1, C34 pin 1; R34 pin 2 and
  C34 pin 2 → `GND` (the two are alternatives, both are placed, R34 is the DNI option).
- `USB_CC1`: J9 [CC1], R32 pin 1, D3 [CH3] (pin 4); R32 pin 2 → `GND`.
  `USB_CC2`: J9 [CC2], R33 pin 1, D3 [CH4] (pin 6); R33 pin 2 → `GND`.
- `USB_DP`: J9 [DP1] + [DP2], D3 [CH1] (pin 1), U5 [D+] (pin 18).
  `USB_DN`: J9 [DN1] + [DN2], D3 [CH2] (pin 3), U5 [D−] (pin 19).
  This gives the array all four channels (D+, D−, CC1, CC2) and its VDD pin on `VBUS`,
  so VBUS is clamped as well — see §9.
- `PHY_XI` / `PHY_XO`: U5 [XI] / [XO], Y2 pins 1 and 3. Y2 pins 2 and 4 → `GND`.
  No load capacitors: the document's BOM has none for Y2 (CH132B integrates them) — if
  the datasheet contradicts this, stop and report.
- `ULPI_CK`: U5 [CLK] → R9 pin 1; R9 pin 2 → `ULPI_CK` to the MCU (R9 is the 22 Ω option,
  normally not fitted).
- `ULPI_DIR`, `ULPI_NXT`, `ULPI_STP`, `ULPI_D0`…`ULPI_D7`: U5 pins of those names.
- Supply: U5 [VDD33], [VDDIO], [V5], [VBUS] → `3V3` (document §8.3); C35/C36/C37 pin 1 →
  `3V3`.
- Pins the document lists as NC (8, 11, 12, 14, 15, 16, 17, 23, 28, 30 in its numbering)
  are left out of the netlist; if the manifest names them `NC`, say so in your report
  instead of wiring them.

Confirmed pin facts (checked against `WCH CH132 数据手册 V2.2` 表 1-2 and the LCSC symbols;
the manifest carries the same numbers — use it, not this table, as your source):

| Part | Pins |
|---|---|
| `CH132B` (C41416597) | 1 CLK, 2 NXT, 3–7 D0–D4, 9 D5, 10 D6, 13 D7, 18 D+, 19 D−, 20 VDD33, 21 V5, 22 VBUS, 24 + 33 GND, 25 XO, 26 XI, 27 RESET#, 29 STP, 31 DIR, 32 VDDIO, NC on 8/11/12/14/15/16/17/23/28/30 |
| `TYPE-C 16P CB0.8 073` (C2906289) | `A4B9`, `B4A9` = VBUS; `A1B12`, `B1A12` = GND; `A5` = CC1; `B5` = CC2; `A6`+`B6` = D+; `A7`+`B7` = D−; `A8`/`B8` = SBU (leave floating); `0` = the four shell/mounting tabs → `USB_SHIELD`. The pin numbers are strings, not numbers — keep them exactly as the manifest prints them |
| `D5V0F4U6SO-7` (C19723969) | 1 CH1, 2 GND, 3 CH2, 4 CH3, 5 VDD, 6 CH4 |
| `SN74LVC1G125DCKR` (C7394030) | 1 `OE#`, 2 `IN A`, 3 GND, 4 Y, 5 VCC |

## 7. Pages 4 and 5 — Channel interfaces

`Channel_1-4.json` holds channels n = 1…4, `Channel_5-8.json` channels n = 5…8.
Components per channel (8): `Jn` C53151845; `FBn` C21519; `Cn+37` C5448891 10 µF;
`Cn+45` C5350800 100nF; `D(3+n)` C558418 SRV05-4; `D(11+n)` C5137779 ES06D1HA03;
`R(33+2n)` C2906868 33R (RX); `R(34+2n)` C2906868 33R (TX).

Worked out, to avoid arithmetic mistakes:

| n | J | FB | 10 µF | 100 nF | SRV05-4 | ES06D1HA03 | R (RX) | R (TX) |
|---|---|---|---|---|---|---|---|---|
| 1 | J1 | FB1 | C38 | C46 | D4 | D12 | R35 | R36 |
| 2 | J2 | FB2 | C39 | C47 | D5 | D13 | R37 | R38 |
| 3 | J3 | FB3 | C40 | C48 | D6 | D14 | R39 | R40 |
| 4 | J4 | FB4 | C41 | C49 | D7 | D15 | R41 | R42 |
| 5 | J5 | FB5 | C42 | C50 | D8 | D16 | R43 | R44 |
| 6 | J6 | FB6 | C43 | C51 | D9 | D17 | R45 | R46 |
| 7 | J7 | FB7 | C44 | C52 | D10 | D18 | R47 | R48 |
| 8 | J8 | FB8 | C45 | C53 | D11 | D19 | R49 | R50 |

Per-channel nets (connector pin numbers are the symbol's, taken from the manifest — the
document's pin functions are **1 = 5V, 2 = GND, 3 = node TX, 4 = node RX, 5 = SYNC**):

| Net | Members |
|---|---|
| `5V_CHn_SW` | SWn [OUT] (other page), FBn pin 1 |
| `5V_CHn` | FBn pin 2, 10 µF pin 1, 100 nF pin 1, ES06D1HA03 pin 1 (K), Jn pin 1 |
| `GND` | Jn pin 2, 10 µF pin 2, 100 nF pin 2, ES06D1HA03 pin 2 (A), SRV05-4 pin 2 |
| `CHn_RX_P` | Jn pin 3, SRV05-4 pin 1, R(RX) pin 1 |
| `CHn_RX` | R(RX) pin 2 (leaves the page) |
| `CHn_TX` | R(TX) pin 1 (leaves the page) |
| `CHn_TX_P` | R(TX) pin 2, SRV05-4 pin 3, Jn pin 4 |
| `SYNC_CHn` | SRV05-4 pin 6, Jn pin 5 |
| `3V3` | SRV05-4 pin 5 (VCC) |
| — | SRV05-4 pin 4 (I/O 4) stays unconnected — only three signals per channel |

`SRV05-4` pin numbering (1 = I/O1, 2 = GND, 3 = I/O2, 4 = I/O3, 5 = VCC, 6 = I/O4) is the
Semtech datasheet layout; the LCSC symbol carries numbers only, with no pin names. Use
those numbers, and repeat the assumption in your report so the reviewer can check it
against the datasheet image.

**Connector mounting pads:** `HC-0.6-5PWT` (C53151845) has seven pads — 1…5 are the
signal contacts (1 = 5V, 2 = GND, 3 = node TX, 4 = node RX, 5 = SYNC) and **pads 6 and 7
are the shell/mounting tabs**. Tie 6 and 7 to `GND` on every channel page (mechanical and
EMC grounding); say so in your report.

## 8. Page 6 — Sync (`Document/Netlist/Sync.json`)

Components (16): `U6` C7394030; `C13` C5350800 100nF (U6 VCC decoupling — the eleventh
100 nF of the MCU subsystem, see §4); `R51`…`R58` C2906860 100R; `R59` C2906860 100R;
`R60` C25744 10k; `R61` C2906860 100R; `C54` C106200 100pF; `C55` C5350800 100nF;
`J11` C53055380.

- `SYNC`: U6 [A] (input) ← MCU PA8 (cross-page).
- `SYNC_EN`: U6 [`/OE`] ← MCU PA9. If the symbol names the pin `OE` or `~OE`, that is the
  one; state which in your report.
- `SYNC_DIST`: U6 [Y] (output), R51…R58 pin 1.
- `SYNC_CH1`…`SYNC_CH8`: R51…R58 pin 2 → the corresponding channel connector pin 5
  (`SYNC_CH1` ↔ J1, `SYNC_CH8` ↔ J8).
- `3V3`: U6 [VCC], C13 pin 1, R61 pin 1. `GND`: U6 [GND], C13 pin 2, C54 pin 2,
  C55 pin 2, R60 pin 2,
  J11 pin 2, **J11 pins 4 and 5** (the GH1.25 shell/mounting pads — the footprint has five
  pads for three contacts).
- `SYNC_IN_RAW`: J11 pin 1, R59 pin 1. `SYNC_IN`: R59 pin 2, R60 pin 1, C54 pin 1,
  U3 [PA15] (cross-page, member only on the MCU page).
- `3V3_EXT`: R61 pin 2, C55 pin 1, J11 pin 3.

## 9. Page 7 — Indicator (`Document/Netlist/Indicator.json`)

Components (25 with the 4-pin common-anode LED): `U7` C2891574; `FB10` C21519; `C56` C5350800
100nF; `C57` C20070242 1 µF; `C58` C20070242 1 µF; `R62` C140179 22k; `R63`,`R64` C140158
4.7k; `R65` C25741 100k; `LED1`…`LED8` C965840; `R66`…`R73` C54920677 470R.

- `3V3`: U7 [VDD] (pin 27), C56 pin 1, C57 pin 1, R63 pin 1, R64 pin 1.
- `5V_LED`: FB10 pin 2, C58 pin 1, R66…R73 pin 1. **The AW21024 has no VLED pin** — the
  LED anodes are fed from `5V_LED` and the driver sinks the cathodes; do not look for a
  `VLED` pin on U7.
- `5V_SYS`: FB10 pin 1 (cross-page).
- `GND`: U7 [GND] (pin 33, the exposed pad is the same net if the symbol has it),
  C56/C57/C58 pin 2, R62 pin 2, U7 [AD0] (25), U7 [AD1] (26).
- `REXT`: U7 [ISET] (pin 31), R62 pin 1.
- `I2C4_SCL`: R63 pin 2, U7 [SCL] (29); `I2C4_SDA`: R64 pin 2, U7 [SDA] (28).
- `LED_EN`: R65 pin 1, U7 [EN] (pin 30); R65 pin 2 → `GND`.
- U7 pin 32 is `NC` — leave it out of the netlist and say so in your report.
- `LEDn_R` / `LEDn_G` / `LEDn_B` (n = 1…8): U7 output channel pin ↔ RGB LED cathode.
  Map channel numbers in order: `LED1_R` = LED1, `LED1_G` = LED2, `LED1_B` = LED3,
  `LED2_R` = LED4, … `LED8_B` = LED24 — i.e. 3 channels per LED, R/G/B, ascending.
- **RGB LED pins (C965840) — CORRECTED after review against the manufacturer drawing**
  (`XL-1615RGBC-RF.pdf` p.8 "外形尺寸 / 极性": pin 2 = ＋, pin 1 = R, pin 3 = G, pin 4 = B):
  pin 2 = `COM+` (common anode), pin 1 = `R−`, **pin 3 = `G−`, pin 4 = `B−`**. So
  `LEDn_R` → pin 1, `LEDn_G` → **pin 3**, `LEDn_B` → **pin 4**.
  The converted LCSC symbol originally carried the names the other way round (pin 3 =
  `B−`, pin 4 = `G−`), which contradicted the drawing; the symbol's two pin *names* were
  corrected to `G−`/`B−` and the netlist was re-wired to the drawing. Reviewer finding
  I-1 of `Document/.review/review_IF_LED.md`.
- **RGB LED anode resistors:** the part is a **4-pin common-anode** device, so only one
  resistor per LED can sit in the anode path. Use `R66`…`R73` (470 Ω) from `5V_LED` to
  each LED's `COM+` (pin 2), leave `R74`…`R89` out of the netlist, and report the
  deviation — the document's 24 × 470 Ω cannot be realised with a common-anode LED
  (its §6.1 "每色一只" assumed three separate anodes). The AW21024 is a constant-current
  sink, so the drop is set by the driver, not by a per-colour resistor.
- **Board LED `D2` (C965839) pins (confirmed):** 1 = `R−`, 2 = `G−`, 3 = `G+`, 4 = `R+`.
  `LED_G` (MCU PD1) → pin 2, `LED_R` (MCU PD5) → pin 1, `R7` → pin 4, `R8` → pin 3.

---

## 10. Deviations from the design document (decided here, report them)

1. **J10 (TAG-Connect SWD pads) and TP1…TP12 are not built** — the user chose to keep
   bare copper pads out of the schematic; they belong to the PCB stage. No SWD or test
   point symbol/part appears on any page.
2. **Part substitutions for lcsc.com availability** (the document's numbers are
   szlcsc-only or unavailable internationally):

| Document | LCSC (doc) | Built | Reason |
|---|---|---|---|
| L1 WPN201610H2R2MT | C97005 | **C315717 WIP201610P-2R2ML** (INPAQ, 2.2 µH, 1.71 A Isat, 135 mΩ, 0806) | C97005 exists in szlcsc only (lcsc.com returns 0 hits, szlcsc.com needs a sign-in) and both numbers of the international equivalent (C52741374) and of the document's part have **no EasyEDA library**, so they cannot be drawn. C315717 is the closest 0806 shielded part on lcsc.com with a published symbol/footprint: Isat 1.71 A ≫ the 0.27 A peak of §5.3 |
| Y2 12 MHz SX32Y012000BA1T001 | C7420719 | **C7500570 XL2EL89CMI-111YLC-12M** (YXC, 12 MHz ±10 ppm, **CL 10 pF**, 3225) | C7420719 has no EasyEDA library at all (`easyeda.com has no component record`). The replacement is the same 3225 four-pad family with the same 10 pF load capacitance, so the CH132B's internal oscillator capacitors see the intended load |
| D1 SMBJ6.0A (Yangjie) | C699023 | C113976 SMBJ6.0A (MDD) | not on lcsc.com |
| FB1–FB8 GZ2012D601TF | C1017 | C21519 MPZ2012S601AT000 (TDK) | not on lcsc.com |
| FB_VDDA 600 Ω 0603 | C1002 | C107335 MPZ1608S601ATA00 (TDK) | not on lcsc.com |
| R 33 kΩ 0402 | C22369463 | C25779 0402WGF3302TCE | not on lcsc.com |
| R 22 Ω 0402 | C22369461 | C25092 0402WGF220JTCE | not on lcsc.com |
| R 5.1 kΩ 0402 | C22369457 | C25905 0402WGF5101TCE | not on lcsc.com |

3. **USB ESD allocation**: `D5V0F4U6SO-7` protects `D+`, `D−`, `CC1`, `CC2`; VBUS is
   protected by `D1` on the Power page (the document said "VBUS and CC together", which
   a 4-channel array cannot do).
4. **J11 external-timebase ESD** is not fitted: the document's §3.5 asks for a ≤3 pF
   array, but its BOM lists no such part. Report as an open item.
5. **Board LED anodes** (`D2`) go to `3V3` through 470 Ω as §6.2 says, not to `5V_SYS`.

---

## 11. Netlist file format (exactly what the builder consumes)

```json
{
  "design": "MCB-01",
  "subsystem": "MCU",
  "source": "HW-DD-MCB-001 V3.4 §2.4, §6.2, §8.1",
  "components": [
    { "ref": "U3", "lcsc": "C730183" },
    { "ref": "R1", "lcsc": "C25744", "value": "10k" }
  ],
  "nets": [
    { "name": "3V3", "class": "power", "members": [ { "ref": "R1", "pin": "1" } ] }
  ]
}
```

Rules:

- `ref` must be unique in the file; `lcsc` is mandatory for every component (the
  database resolves symbol, footprint and value from it).
- `pin` is the **symbol pin number as a string**.
- Every pin appears in at most one net. A pin in two nets aborts the build. A pin in no
  net is a floating pin and must be deliberate.
- `class` is `power` for supply rails and `signal` for the rest.
- Do not invent a net name outside §3 unless the page is self-contained; if you must,
  say why in your report.
- Validate before you finish: every component appears in at least one net (components
  with no net at all cannot be placed), no `(ref, pin)` pair appears twice, every pin
  number exists in `kicad_lib/manifest.json` or in the standard symbol, and the part
  counts match §4…§9.

## 12. Reference: standard-symbol pin numbers

| Symbol | Pins |
|---|---|
| `Standard:R`, `Standard:C`, `Standard:L`, `Standard:FB` | `1`, `2` |
| `Standard:FUSE_PTC` | `1`, `2` |
| `Standard:Q_PMOS_SOT23` | `1` = G, `2` = S, `3` = D |
| `Standard:D_TVS_*` | `1` = A, `2` = K (check the exact variant the database picks) |

Everything else comes from `kicad_lib/manifest.json`:
`{ "<MPN>": { "pins": [ { "number", "name", "type" } ] } }`.
