# Part classes, product-type codes and standard candidates

The classifier reads the store's **category, description and parameters** — never
the part number — and answers two questions: what kind of part is this, and could a
standard symbol represent it? Every decision records the text it used, so the report
can be audited line by line:

```
1.          resistor in category/description
1.          footprint R_0603 from the standard library (2 pads, package 0603)
1.          symbol R from the standard library
```

## Classes

| Class | Product-type prefix | Passive? | Standard symbol candidates | Standard footprint |
|---|---|---|---|---|
| `RESISTOR` | `R` | yes | `R` | `R_<size>` |
| `RESISTOR_NETWORK` | `RN` | no | — | — |
| `CAPACITOR` | `C` | yes | `C` | `C_<size>` |
| `CAPACITOR_POL` | `C` | yes | `C_POL_P1N2` (needs `1=+ 2=−` evidence) | — (tantalum/electrolytic land patterns are not MLCC land patterns) |
| `CAPACITOR_NETWORK` | `C` | no | — | — |
| `INDUCTOR` | `L` | yes | `L` | — |
| `FERRITE_BEAD` | `FB` | yes | `FB` | — |
| `FUSE` | `F` | yes | `FUSE` | — |
| `FUSE_PTC` | `F` | yes | `FUSE_PTC` | — |
| `THERMISTOR_NTC` | `RT` | yes | `Thermistor_NTC` | — |
| `CRYSTAL` | `XTAL` | yes | `XTAL`, `XTAL13_GND24`, `XTAL13_GND24_Small` | — |
| `OSCILLATOR` | `XTAL` | no | — | — |
| `DIODE_SCHOTTKY` | `D` | no | `D_SCHOTTKY_A1C2`, `D_SCHOTTKY_A2C1` | — |
| `DIODE_ZENER` | `D` | no | `D_Zener_A1C2`, `D_Zener_A2C1` | — |
| `DIODE_TVS` | `D` | no | `D_TVS_A1C2`, `D_TVS_A2C1` | — |
| `DIODE_TVS_BIDIR` | `D` | no | `D_TVS_BIDIR` | — |
| `DIODE`, `DIODE_LED` | `D` | no | — | — |
| `TRANSISTOR_NMOS` | `Q` | no | `Q_NMOS_SOT23` (SOT-23 only) | — |
| `TRANSISTOR_PMOS` | `Q` | no | `Q_PMOS_SOT23` | — |
| `TRANSISTOR_NPN` | `Q` | no | `Q_NPN_SOT23` | — |
| `TRANSISTOR_PNP` | `Q` | no | `Q_PNP_SOT23` | — |
| `TRANSISTOR` | `Q` | no | — | — |
| `IC` | `IC` | no | — | — |
| `CONNECTOR` | `CON` | no | — | — |
| `SWITCH` | `SW` | no | — | — |
| `RELAY` | `RLY` | no | — | — |
| `TESTPOINT` | `TP` | yes | `TP` | — |
| `MOUNTING` | `M` | yes | `MountingHole` | — |
| `OTHER` | `X` | no | — | — |

A candidate is only *proposed*. It is used only if it survives the gate in
[`library-layout.md`](library-layout.md#the-mapping-gate-in-order) — existence,
package lock, pad/pin equality, pin-role evidence.

`--mode` decides how far the table is consulted:

| Mode | Behaviour |
|---|---|
| `auto` (default) | standard symbols only for classes marked *passive*; the downloaded symbol is used for everything else (rule 2) |
| `all` | also try standard symbols for diodes and transistors; the pin-role evidence is still required |
| `off` | always the downloaded symbol and footprint, whatever the class |

## How the class is decided

Ordered checks, first match wins. Each rule needs the words in the store's category
or description (English or Chinese), so a mislabelled part falls through rather than
being forced into a class:

1. mounting hole, test point;
2. ferrite bead → common-mode choke → inductor;
3. NTC thermistor → resistor network → resistor (also: a `Resistance` parameter);
4. capacitor network → polarised capacitor (electrolytic/tantalum/aluminium/polymer/
   `ALUM`) → capacitor;
5. PTC fuse → fuse;
6. oscillator → crystal;
7. TVS (bidirectional by parameter) → LED → zener → schottky → diode/rectifier;
8. MOSFET/transistor (`N-CH`, `N-channel`, `NMOS`, `NPN`, …) → transistor;
9. connector → switch → relay → integrated circuit (PMIC, MCU, regulator,
   amplifier, logic, ADC/DAC, driver, sensor, memory) → `OTHER`.

Package parsing runs alongside: `chip_size_of("0603 (1608 Metric)")` → `0603`, and
`package_family_of` normalises `SOT-23-5`, `SOD-323`, `LQFP-48(7x7)`, `DFN-8`, …

## Package locks

Some standard symbols name their package, so a mismatch is a wrong-part signal:

| Symbol | Required package family |
|---|---|
| `*_SOT23` | SOT-23 |
| `*_SOT23-5` | SOT-23-5 |
| `*_SOT23-6` | SOT-23-6 |
| `*_SO8` | SOIC-8 / SOP-8 |
| `*_DFN8` | DFN-8 |

## Product-type prefixes

The prefix of a downloaded file name (`IC_STM32G103C8T6`). The table above is the
default; a BOM `type` column overrides it when the classifier cannot tell — e.g. a
module that the store files under "Integrated Circuits" but that the project names
`MOD_…`. Prefixes are uppercased and the MPN keeps its published case, matching the
files already in the tree (`D_BAT54L2-TP`, `XTAL_830108160801`).

## When the class is wrong

Do **not** edit the classifier and do not rename library files by hand. Put the
answer in the BOM line:

```csv
lcsc,value,type,symbol,footprint
C12345,,MOD,Symbol:MOD_MYMODULE,Footprint:MOD_MYMODULE
```

An explicit `symbol`/`footprint` override is still validated: an override that does
not resolve, or whose pins and pads disagree, blocks the row with the reason.
