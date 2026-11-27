# KiCad 10 output — the exact grammar this skill emits

Read from the installed **KiCad 10.0.8** libraries on the development machine, not
from memory. Writing from KiCad 7/8 habits produces files that load but are not native:
10.x added `(show_name …)`, `(do_not_autoplace …)`, `(in_pos_files …)`,
`(duplicate_pin_numbers_are_jumpers …)`, `(hide yes)` and `(embedded_fonts no)`.

## Version stamps

| File | Stamp | Reference |
|---|---|---|
| `.kicad_sym` | `(version 20251024)` | `share/kicad/symbols/Device.kicad_sym` |
| `.kicad_mod` | `(version 20260206)` | `share/kicad/footprints/Resistor_SMD.pretty/R_0603_1608Metric.kicad_mod` |

## Symbol library

```
(kicad_symbol_lib
	(version 20251024)
	(generator "lcsc-libs")
	(generator_version "10.0")
	(symbol "STM32F103C8T6"
		(pin_names (offset 1.016))
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(in_pos_files yes)
		(duplicate_pin_numbers_are_jumpers no)
		(property "Reference" "U" (at 0 <top+2.54> 0) (show_name no) (do_not_autoplace no)
			(effects (font (size 1.27 1.27))))
		(property "Value" "STM32F103C8T6" …)
		(property "Footprint" "C8734_STM32F103C8T6:LQFP-48_…" … (hide yes))
		(property "Datasheet" "https://…pdf" … (hide yes))
		(property "Manufacturer" "STMicroelectronics" … (hide yes))
		(property "LCSC" "C8734" … (hide yes))
		(symbol "STM32F103C8T6_0_1"          ← graphics
			(rectangle (start x1 y1) (end x2 y2)
				(stroke (width 0.254) (type default))
				(fill (type background))))
		(symbol "STM32F103C8T6_1_1"          ← pins
			(pin bidirectional line
				(at x y angle)               ← angle: 0 right, 90 up, 180 left, 270 down
				(length 2.54)
				(name "PA0" (effects (font (size 1.27 1.27))))
				(number "1" (effects (font (size 1.27 1.27))))))
		(embedded_fonts no))
)
```

Rules that matter:

- pin `(at …)` is the **connection** point; the pin body extends toward the symbol body
  by `(length …)`, so the angle points *away* from the body;
- graphics live in `_0_1`, pins in `_1_1` (this is what KiCad's editor writes);
- every symbol ends with `(embedded_fonts no)`.

## Footprint

```
(footprint "C8734_STM32F103C8T6"
	(version 20260206)
	(generator "lcsc-libs")
	(generator_version "10.0")
	(layer "F.Cu")
	(descr "…")
	(tags "STM32F103C8T6 LQFP-48_L7.0-W7.0-P0.50-LS9.0-BL LCSC C8734")
	(property "Reference" "REF**" (at 0 <y> 0) (layer "F.SilkS")
		(effects (font (size 1 1) (thickness 0.15))))
	(property "Value" "STM32F103C8T6" (at 0 <y> 0) (layer "F.Fab") …)
	(attr smd)
	(duplicate_pad_numbers_are_jumpers no)
	(fp_line (start x1 y1) (end x2 y2)
		(stroke (width 0.1524) (type solid)) (layer "F.SilkS"))
	(fp_circle (center x y) (end x+ r y) (stroke (width 0.15) (type solid))
		(fill none) (layer "F.SilkS"))
	(fp_poly (pts (xy …) …) (stroke (width 0) (type solid)) (fill solid) (layer "F.Fab"))
	(pad "1" smd rect (at x y 90) (size 1.5 0.3) (layers "F.Cu" "F.Paste" "F.Mask"))
	(embedded_fonts no)
	(model "${KIPRJMOD}/../kicad_lib/Step/C8734_STM32F103C8T6.step"
		(offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
)
```

Rules that matter:

- `(attr …)` is `smd`, `through_hole`, or both, derived from the pads;
- SMD pads carry `F.Cu F.Paste F.Mask`; plated holes carry `*.Cu *.Mask` plus `(drill …)`;
- **`fp_poly` and `fp_circle` only accept `(fill yes)` or `(fill no)`.** A bare
  `(fill solid)` / `(fill none)` makes KiCad report *"Unable to load library"* and the
  whole `.pretty` becomes unreadable — verified by bisection, then by counting the
  forms in the installed libraries (43,083 × `(fill no)`, 7,626 × `(fill yes)`, zero of
  anything else);
- `(embedded_fonts no)` sits before the model block;
- the model path is written verbatim from `--model-prefix`, so it is portable only if
  the STEP ends up there.
- `kicad-cli` does not create the `--output` directory: create it first or the export
  fails with "Failed to create file".

## Verifying a generated file with KiCad itself

`kicad-cli` must be launched from a normal shell: started from inside a Python
subprocess it cannot open `HKCU\Software\kicad-cli` and fails with a registry error.

```bash
mkdir -p /tmp/out /tmp/svg
kicad-cli sym upgrade --output /tmp/out  <lib>.kicad_sym   # parses, or reports why
kicad-cli sym export svg --output /tmp/svg <lib>.kicad_sym # renders it
kicad-cli fp upgrade --output /tmp/out   <dir>.pretty      # pass the .pretty DIRECTORY
kicad-cli fp export svg --output /tmp/svg <dir>.pretty
```

"… was not updated" with exit code 0 means KiCad parsed the file and found it already
in the current format — a pass, not a failure. `exit 2` + "Unable to load library" is
a real defect; bisect by removing one op family at a time (that is how the `(fill …)`
bug above was found).

Both commands were run against the generated C25804, C8734 and C2040 libraries: all six
artefacts parse and plot.
