#!/usr/bin/env python3
"""
kicad-sch-analyzer — High-level KiCad schematic analysis using the skip library.

Analyzes .kicad_sch files against an OrcadPCB2-format netlist (.net) to list
components, nets, and pin connections with correct KiCad net names.

Usage:
    python3 kicad-sch-analyzer.py <schematic.kicad_sch> <netlist.net> [options]

Arguments:
    schematic    Path to .kicad_sch file
    netlist      Path to OrcadPCB2 netlist (.net) file

Options:
    --list-components       List all components with manufacturer part numbers
    --list-nets             List all nets and the pins connected to each
    --list-pins <ref>       List all pins and connected nets for a component
    --hierarchical          Also parse sub-sheets referenced by the main sheet
    --help                  Show this help

Default (no options): show component list + net list.
"""
import sys
import os
import argparse
import logging
import re
import json

import sexpdata

# Suppress noisy "can't parsy" warnings from the skip library
logging.getLogger('skip').setLevel(logging.ERROR)

import skip


# ═══════════════════════════════════════════
#  OrcadPCB2 netlist parser  (.net)
# ═══════════════════════════════════════════

def _sexp_to_netname(sexp):
    """
    Reconstruct a net name string from a parsed s-expression.

    In OrcadPCB2 format, compound net names are nested s-expressions:
        (Net- (U3-SW_1))     -> "Net-(U3-SW_1)"
        (unconnected- (...))  -> "unconnected-(...)"
        GND                   -> "GND"
        5V_SYS                -> "5V_SYS"
    """
    if isinstance(sexp, list):
        parts = []
        for item in sexp:
            if isinstance(item, list):
                parts.append(f'({_sexp_to_netname(item)})')
            else:
                s = str(item)
                # sexpdata may keep {slash} as-is
                parts.append(s)
        return ''.join(parts)
    return str(sexp)


def parse_orcadpcb2_netlist(filepath):
    """
    Parse an OrcadPCB2-format netlist (.net) file.

    Returns (name_map, net_pins, all_refs)
      name_map = {(ref, pin_str): net_name}
      net_pins = {net_name: [(ref, pin_str), ...]}
      all_refs = set of all component references
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Remove only the top-level comment { EESchema Netlist ... }
    content = re.sub(r'\(\s*\{[^}]*\}\s*', '(', content, count=1)
    # Strip trailing " )*" or similar
    content = content.strip()
    if content.endswith('*'):
        content = content[:-1].strip()

    parsed = sexpdata.loads(content)

    name_map = {}
    net_pins = {}
    all_refs = set()

    for entry in parsed:
        if not isinstance(entry, list) or len(entry) < 4:
            continue
        ref = str(entry[2])
        all_refs.add(ref)
        for sub in entry[4:]:
            if not isinstance(sub, list) or len(sub) < 2:
                continue
            pin_sexp = sub[0]
            net_sexp = sub[1:]
            pin_str = str(pin_sexp)
            net_name = _sexp_to_netname(net_sexp[0] if len(net_sexp) == 1 else net_sexp)
            # Keep unconnected pins in name_map so the schematic cross-reference
            # doesn't falsely flag them, but don't add to the net listing.
            name_map[(ref, pin_str)] = net_name
            if not net_name.startswith('unconnected-'):
                net_pins.setdefault(net_name, []).append((ref, pin_str))

    return name_map, net_pins, all_refs


# ═══════════════════════════════════════════
#  Power-symbol helpers
# ═══════════════════════════════════════════
def _is_power_symbol(sym):
    try:
        if hasattr(sym, 'lib_id') and hasattr(sym.lib_id, 'value'):
            lid = str(sym.lib_id.value)
            if lid.startswith('power:') or ':PWR' in lid or ':GND' in lid:
                return True
    except Exception:
        pass
    try:
        ref = sym.property.Reference.value
        if ref.startswith('#PWR') or ref.startswith('#'):
            return True
    except Exception:
        pass
    return False


# ═══════════════════════════════════════════
#  Build net database from schematic + asc
# ═══════════════════════════════════════════
def build_net_database(sch, name_map):
    """
    Build the net database by cross-referencing every pin in the schematic
    against the OrcadPCB2 netlist.  The netlist is the ground truth for net
    names and pin groupings.

    Returns (nets, pin_to_net, errors)
      nets      = {net_name: (source, [(ref, pin_num, pin_name), ...])}
      pin_to_net = {(ref, pin_num): net_name}
      errors    = [(ref, pin_num), ...]  — pins in schematic but not in netlist
    """
    net_to_pins = {}
    pin_to_net = {}
    errors = []

    for sym in sch.symbol:
        try:
            ref = sym.property.Reference.value
        except Exception:
            continue
        try:
            for p in sym.pin:
                try:
                    pnum = p.number
                    pname = p.name
                except Exception:
                    continue
                net_name = name_map.get((ref, pnum))
                if net_name is None:
                    errors.append((ref, pnum))
                    continue
                pin_to_net[(ref, pnum)] = net_name
                # Don't group unconnected pins into nets
                if net_name.startswith('unconnected-'):
                    continue
                net_to_pins.setdefault(net_name, []).append((ref, pnum, pname))
        except Exception:
            pass

    nets = {}
    for nn in sorted(net_to_pins):
        plist = net_to_pins[nn]
        plist.sort(key=lambda e: (e[0], int(e[1]) if e[1].isdigit() else e[1]))
        nets[nn] = ('netlist', plist)

    return nets, pin_to_net, errors


# ═══════════════════════════════════════════
#  Load schematics (hierarchy support)
# ═══════════════════════════════════════════
def load_schematic(filepath, hierarchical=False):
    base_dir = os.path.dirname(os.path.abspath(filepath))
    sch = skip.Schematic(filepath)
    sheets = [sch]
    if not hierarchical:
        return sheets
    if hasattr(sch, 'sheet'):
        for sheet_ref in sch.sheet:
            fv = nv = None
            if hasattr(sheet_ref, 'property'):
                for pv in sheet_ref.property:
                    try:
                        if pv.name == 'Sheetfile':
                            fv = pv.value
                        elif pv.name == 'Sheetname':
                            nv = pv.value
                    except Exception:
                        pass
            if fv:
                sp = os.path.join(base_dir, fv)
                if os.path.exists(sp):
                    try:
                        sheets.append(skip.Schematic(sp))
                        print(f"  (loaded sub-sheet: {nv or fv})", file=sys.stderr)
                    except Exception as e:
                        print(f"  (warning: could not load {sp}: {e})", file=sys.stderr)
    return sheets


# ═══════════════════════════════════════════
#  Format helpers
# ═══════════════════════════════════════════
def _fmt_prop(sym, *names):
    for n in names:
        try:
            if n in sym.property:
                return sym.property[n].value
        except Exception:
            pass
    return '—'

# ═══════════════════════════════════════════
#  Actions
# ═══════════════════════════════════════════
def action_list_components(sheets, json_mode=False):
    seen = set()
    rows = []
    for sch in sheets:
        for sym in sch.symbol:
            try:
                ref = sym.property.Reference.value
            except Exception:
                continue
            if ref in seen:
                continue
            seen.add(ref)
            if _is_power_symbol(sym):
                continue

            if json_mode:
                # All properties as a dict
                props = {}
                try:
                    for p in sym.property:
                        props[p.name] = p.value
                except Exception:
                    pass
                try:
                    props['dnp'] = bool(sym.dnp.value)
                except Exception:
                    props['dnp'] = False
                rows.append(props)
            else:
                val = _fmt_prop(sym, 'Value')
                mpn = _fmt_prop(sym, 'Manufacturer_Part_Number', 'MPN',
                                'ManufacturerProductNumber')
                dnp_flag = 'DNP' if (hasattr(sym, 'dnp') and sym.dnp.value) else ''
                rows.append((ref, val, mpn, dnp_flag))

    if json_mode:
        print(json.dumps(rows, indent=2))
        return

    rows.sort(key=lambda r: r[0])
    print(f"\n{'Ref':<16} {'Value':<30} {'MPN':<50} {'DNP'}")
    print('-' * 110)
    for ref, val, mpn, dnp in rows:
        print(f"{ref:<16} {val:<30} {mpn:<50} {dnp}")
    print(f"\nTotal: {len(rows)} components")


def action_list_pins(sheets, ref_target, pin_to_net, net_db, json_mode=False):
    found = False
    for sch in sheets:
        try:
            if ref_target not in sch.symbol:
                continue
        except Exception:
            continue
        sym = sch.symbol[ref_target]
        found = True

        try:
            pins = sorted([p for p in sym.pin], key=lambda p: int(p.number))
        except Exception:
            pins = list(sym.pin)

        ref = sym.property.Reference.value

        if json_mode:
            mpn = _fmt_prop(sym, 'Manufacturer_Part_Number', 'MPN',
                            'ManufacturerProductNumber')
            out = {
                'reference': ref,
                'value': sym.property.Value.value if hasattr(sym.property, 'Value') else '',
                'mpn': mpn,
                'pins': []
            }
            for p in pins:
                try:
                    pnum = p.number
                    pname = p.name
                except Exception:
                    pnum, pname = '?', '?'
                nn = pin_to_net.get((ref, pnum))
                pin_entry = {'pin': f'{ref}.{pnum}', 'name': pname}
                if nn:
                    if nn.startswith('unconnected-'):
                        pin_entry['net'] = 'unconnected'
                    else:
                        pin_entry['net'] = nn
                else:
                    pin_entry['net'] = 'unconnected'
                out['pins'].append(pin_entry)
            print(json.dumps(out, indent=2))
        else:
            print(f"\nComponent: {sym.property.Reference.value}  =  {sym.property.Value.value}")
            try:
                print(f"Lib ID: {sym.lib_id.value}")
            except Exception:
                pass
            for prop in ('Description', 'Footprint', 'Datasheet', 'Manufacturer_Name',
                         'Manufacturer_Part_Number', 'Package'):
                v = _fmt_prop(sym, prop)
                if v != '—':
                    print(f"{prop}: {v}")
            print()
            print(f"{'Pin #':<12} {'Pin Name':<24} {'Net Name':<40}")
            print('-' * 80)
            for p in pins:
                try:
                    pnum = p.number
                    pname = p.name
                except Exception:
                    pnum, pname = '?', '?'
                nn = pin_to_net.get((ref, pnum))
                if nn:
                    if nn.startswith('unconnected-'):
                        print(f"{ref}.{pnum:<8} {pname:<24} {'<unconnected>':<40}")
                    else:
                        print(f"{ref}.{pnum:<8} {pname:<24} {nn:<40}")
                else:
                    print(f"{ref}.{pnum:<8} {pname:<24} {'<not found>':<40}")
        break
    if not found:
        msg = f"Component '{ref_target}' not found in schematic."
        if json_mode:
            print(json.dumps({'error': msg}))
        else:
            print(msg)


def action_list_nets(net_db, json_mode=False):
    nets_dict, _ = net_db
    sorted_nets = sorted(nets_dict.items(),
                         key=lambda it: (it[0].startswith('Net-('), it[0]))

    if json_mode:
        out = []
        for net_name, (_, pins_list) in sorted_nets:
            net_entry = {'net': net_name, 'pins': []}
            for ref, pnum, pname in pins_list:
                pin_entry = {'ref': ref, 'pin': pnum,
                             'name': pname if pname and pname != '~' else ''}
                net_entry['pins'].append(pin_entry)
            out.append(net_entry)
        print(json.dumps(out, indent=2))
        return

    print(f"\n{'Net Name':<50} {'Connected Pins'}")
    print('-' * 120)
    for net_name, (_, pins_list) in sorted_nets:
        items = []
        for ref, pnum, pname in pins_list:
            s = f"{ref}.{pnum}"
            if pname and pname != '~':
                s += f" ({pname})"
            items.append(s)
        print(f"{net_name:<50} {', '.join(items)}")
    named = sum(1 for n, _ in sorted_nets if not n.startswith('Net-('))
    conns = sum(len(v[1]) for v in nets_dict.values())
    print(f"\nTotal: {len(sorted_nets)} nets ({named} named), {conns} pin connections")


# ═══════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description='KiCad schematic analyzer — cross-references a .kicad_sch '
                    'against an OrcadPCB2 netlist (.net) for correct net names.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument('schematic', help='Path to .kicad_sch file')
    parser.add_argument('netlist', help='Path to OrcadPCB2 netlist (.net) file')
    parser.add_argument('--list-components', action='store_true',
                        help='List all components with manufacturer part numbers')
    parser.add_argument('--list-nets', action='store_true',
                        help='List all nets and connected pins')
    parser.add_argument('--list-pins', metavar='<ref>',
                        help='List all pins and nets for a component (e.g. U3)')
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')
    parser.add_argument('--hierarchical', action='store_true',
                        help='Also parse sub-sheets referenced by the main sheet')
    args = parser.parse_args()

    if not os.path.exists(args.schematic):
        print(f"Error: file not found: {args.schematic}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.netlist):
        print(f"Error: file not found: {args.netlist}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading:   {args.schematic}", file=sys.stderr)
    sheets = load_schematic(args.schematic, hierarchical=args.hierarchical)
    n_syms = sum(len(sch.symbol) if hasattr(sch, 'symbol') else 0 for sch in sheets)
    print(f"Parsed    {len(sheets)} sheet(s), {n_syms} symbol(s).", file=sys.stderr)

    print(f"Netlist:   {args.netlist}", file=sys.stderr)
    name_map, net_pins, net_refs = parse_orcadpcb2_netlist(args.netlist)
    print(f"           {len(net_refs)} components, {len(net_pins)} nets",
          file=sys.stderr)

    do_comp = args.list_components
    do_nets = args.list_nets
    do_pins = args.list_pins is not None
    if not (do_comp or do_nets or do_pins):
        do_comp = do_nets = True

    merged_nets = {}
    merged_lookup = {}
    all_errors = []
    for sch in sheets:
        nn, lk, err = build_net_database(sch, name_map)
        for name, (src, plist) in nn.items():
            if name not in merged_nets:
                merged_nets[name] = (src, [])
            for e in plist:
                if e not in merged_nets[name][1]:
                    merged_nets[name][1].append(e)
        merged_lookup.update(lk)
        all_errors.extend(err)
    net_db = (merged_nets, merged_lookup)

    if all_errors:
        print(file=sys.stderr)
        print("Warning: these pins are in the schematic but not in the netlist:",
              file=sys.stderr)
        for ref, pin in sorted(all_errors):
            print(f"  {ref}.{pin}", file=sys.stderr)

    if do_pins:
        action_list_pins(sheets, args.list_pins, merged_lookup, net_db, args.json)
    if do_comp:
        action_list_components(sheets, args.json)
    if do_nets:
        action_list_nets(net_db, args.json)


if __name__ == '__main__':
    main()
