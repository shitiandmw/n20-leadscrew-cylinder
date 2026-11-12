"""X1 control system, spec C1: two concept sheets, plus the numeric checks behind SPEC.md.

Sheet 1  system block diagram: handle, ESP-NOW link, main board (power, ESP32-S3, 7 x DRV8876, outputs), loads,
         the deferred 4G provision, and the power budget.
Sheet 2  main board concept in the B102 left bay: top view in machine coordinates (zones, connectors, antenna,
         USB-C) and a section through the USB slot (height envelope, slot moved down).
The handle is parked (issue 3): its appearance will restart from a real, cited product reference, so the
issue-2 handle sheet and its face-layout checks were removed. Issue 4 redraws sheet 2 to the PCB layout's floor plan
(main_board/source/layout.py): the module at the front end of the outboard edge, the tracks' XH-4 on the inboard edge.
Issue 5 (2026-11-10): the arm's V6-U60 actuators use the 12 V N20 1:50 motor with an M4 leadscrew, so they run from
VBAT like the other three channels and the 6 V buck is gone.

A concept, not a schematic or a layout. The board outline, holes, USB position and bay heights are read from
../../source/x1_body.py (as text, so CadQuery is not needed) and checked against the values used here.
Writes X1_control_spec_C1.pdf, X1_control_spec_C1_sheet{1,2}.png and X1_control_spec_C1_checks.json next to
SPEC.md.  Run:  /tmp/sw-venv/bin/python draw_control_spec.py   (matplotlib, numpy)
"""
import json, math, re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle
from matplotlib.backends.backend_pdf import PdfPages

HERE = Path(__file__).resolve().parent
OUT = HERE.parent                                        # X1/controller
X1_BODY = OUT.parent / 'source' / 'x1_body.py'
PDF = OUT / 'X1_control_spec_C1.pdf'
PNG = [OUT / f'X1_control_spec_C1_sheet{k}.png' for k in (1, 2)]
CHECKS = OUT / 'X1_control_spec_C1_checks.json'
FIG = (16.5, 11.7)                                       # A3 landscape, as the other X1 concept sheets
DATE = '2026-11-10'

# ---------------------------------------------------------------- data (sources in SPEC.md) --------------------
# Bay and board, as used here; checked against x1_body.py below.
BOARD = dict(x=(-136.0, -40.0), y=(84.0, 148.0), z=(110.0, 111.6))
USB_OLD = dict(x=-98.0, z=123.3, slot=(15.0, 9.0))
HOLE_INSET, HOLE_D = 4.0, 2.7                            # bosses 4 mm in from the corners (x1_body: bx +- 4)
Z_SKIRT_BOT, FLOOR_TOP, Z_DECK = 105.0, 107.5, 136.0     # x1_body: Z_BOT, Z_BOT + T_F, Z_DECK
Z_LIMIT = 134.0                                          # BODY.md open item 6: modules must fit under Z 134
Y_FLOOR_IN, Y_SKIRT_IN, Y_SKIRT_OUT = 77.0, 152.0, 154.0  # x1_body: INNER, W - T_W, W
PART_ALLOW = 20.0                                        # spec B2: components and mated plugs above the board
USBC = dict(w=8.94, h=3.2, overhang=2.6)                 # top-mount USB-C receptacle (devkit model used 8.94 wide)

CHANNELS = [  # name, motor, rail, limit A, ramp s
    ('Left track', 'JGY-370-1260', 'VBAT', 1.0, 0.3),
    ('Right track', 'JGY-370-1260 (mirrored)', 'VBAT', 1.0, 0.3),
    ('Swing', 'JGY-370-1260 (worm)', 'VBAT', 0.6, 0.4),
    ('Boom left', 'V6-U60', 'VBAT', 0.5, 0.1),
    ('Boom right', 'V6-U60', 'VBAT', 0.5, 0.1),
    ('Stick', 'V6-U60', 'VBAT', 0.5, 0.1),
    ('Bucket', 'V6-U60', 'VBAT', 0.5, 0.1)]
V_BAT_MIN, V_BAT_NOM, V_BAT_MAX = 9.6, 10.8, 12.6        # motor stop at 3.2 V/cell; 3S nominal; full
EFF = 0.90                                               # buck efficiency assumed for the budget
ACT_STALL = 0.5                                          # 12 V V6 stalled: 12.6 V / 13 ohm, held at the 0.5 A limit
ACT_RUN = 0.08                                           # 12 V N20 1:50 without load (seller's table); 0.32 A lifting
ESP_PEAK, LAMP_I, BUZ_I = 0.35, 0.10, 0.03               # A at 3.3 V (radio peak), per lamp at 5 V, buzzer at 5 V
EXP_RESERVE = 2.0                                        # A at 5 V on the expansion header (later 4G stick)
FUSE = 5.0
VREF, A_IPROPI, ADC_MAX = 2.5, 1000e-6, 3.1              # DRV8876 AIPROPI 1000 uA/A; S3 ADC1 at 12 dB, about 3.1 V
RAIL_5V = 3.0                                            # buck rating in the spec

# Connectors: name, edge, width along the edge, depth into the board (approximate housings)
XH = lambda n: (n - 1)*2.5 + 4.9                         # JST XH housing width
PH = lambda n: (n - 1)*2.0 + 3.9                         # JST PH housing width
CONN_FRONT = [('XT30 power in', 10.5, 11.0)]
CONN_INBOARD = [('Tracks L+R  XH-4', XH(4), 6.0), ('Boom L', XH(2), 6.0), ('Boom R', XH(2), 6.0), ('Stick', XH(2), 6.0),
                ('Bucket', XH(2), 6.0), ('Swing', XH(2), 6.0), ('Lamps PH-3', PH(3), 4.5), ('Exp PH-4', PH(4), 4.5)]
MODULE_X = (-78.5, -60.5)                                # issue 4: front end of the outboard edge (SPEC C3)
ANT_KEEPOUT_HALF = 22.0                                  # copper keep-out about the module centre (SPEC C3)
CONN_GAP, HOLE_CLEAR = 2.0, 3.0

GPIO_AVAILABLE = list(range(0, 22)) + list(range(35, 49))   # ESP32-S3-WROOM-1-N8 (no PSRAM): 36 GPIO
PIN_USE = {'ADC1: 7 currents + VBAT': 8, 'motor PWM + direction': 14, 'nSLEEP + nFAULT': 2,
           'lamp 1, lamp 2, buzzer': 3, 'status LED': 1, 'USB D-/D+': 2, 'expansion UART': 2, 'BOOT': 1}

LINK_TIMEOUT_MS = 350                                    # as the Sand/Lab app's input watchdog

# Values quoted in SPEC.md; the checks below must reproduce them.
SPEC_QUOTES = {'worst_case_A': 4.9, 'with_4g_A': 6.1, 'rail_5v_logic_A': 0.6, 'r_ipropi_1A_ohm': 2500,
               'r_ipropi_0.6A_ohm': 4170, 'r_ipropi_0.5A_ohm': 5000, 'v_ipropi_run_V': 0.4, 'gpio_used': 33,
               'gpio_total': 36, 'height_room_mm': 22.4, 'usb_new_z': 113.2,
               'link_timeout_ms': 350}


# ---------------------------------------------------------------- checks -----------------------------------------
def read_x1_body():
    src = X1_BODY.read_text()
    num = r'(-?\d+(?:\.\d+)?)'
    m = re.search(rf"BOARD = dict\(x=\({num}, {num}\), y=\({num}, {num}\), z=\({num}, {num}\)\)", src)
    u = re.search(rf"USB = dict\(x={num}, z={num}, slot=\({num}, {num}\)", src)
    bosses = 'for x in (bx[0] + 4, bx[1] - 4) for y in (by[0] + 4, by[1] - 4)' in src
    b = dict(x=(float(m[1]), float(m[2])), y=(float(m[3]), float(m[4])), z=(float(m[5]), float(m[6])))
    usb = dict(x=float(u[1]), z=float(u[2]), slot=(float(u[3]), float(u[4])))
    return b, usb, bosses


def budget():
    i12 = sum(c[3] for c in CHANNELS if not c[1].startswith('V6'))
    i_act = sum(min(c[3], ACT_STALL) for c in CHANNELS if c[1].startswith('V6'))   # straight from VBAT
    i5 = ESP_PEAK + 2*LAMP_I + BUZ_I                       # 3.3 V comes from the 5 V rail through the LDO
    i_logic = 5.0*i5/EFF/V_BAT_MIN
    worst = i12 + i_act + i_logic
    i_4g = 5.0*EXP_RESERVE/EFF/V_BAT_MIN
    return dict(tracks_and_swing_A=round(i12, 3), actuators_stalled_A=round(i_act, 3), logic_lamps_A=round(i_logic, 3),
                worst_case_A=round(worst, 3), fuse_A=FUSE, worst_under_fuse=worst < FUSE,
                with_4g_A=round(worst + i_4g, 3), with_4g_note='over the 5 A fuse: review the fuse in the 4G phase',
                rail_5v_logic_A=round(i5, 3), rail_5v_with_reserve_A=round(i5 + EXP_RESERVE, 3),
                rail_5v_rating_A=RAIL_5V, rail_5v_ok=i5 + EXP_RESERVE <= RAIL_5V,
                assumptions=f'every channel at its limit, actuators stalled at {ACT_STALL} A, 5 V buck {EFF:.0%} '
                            f'efficient, battery at {V_BAT_MIN} V')


def current_sense():
    rows = []
    for lim in sorted({c[3] for c in CHANNELS}, reverse=True):
        r = VREF/(lim*A_IPROPI)
        rows.append(dict(limit_A=lim, r_ipropi_ohm=round(r, 1), v_at_limit=round(lim*A_IPROPI*r, 3),
                         within_adc=lim*A_IPROPI*r <= ADC_MAX,
                         channels=[c[0] for c in CHANNELS if c[3] == lim]))
    v_run = ACT_RUN*A_IPROPI*VREF/(0.5*A_IPROPI)
    return dict(vref=VREF, a_ipropi_uA_per_A=A_IPROPI*1e6, adc_max_V=ADC_MAX, rows=rows,
                actuator_run_V=round(v_run, 3))


def place(conns, start, direction, lo, hi):
    """Place connectors along an edge from `start`, stepping in `direction` (+1/-1). Returns spans and fit."""
    out, p = [], start
    for name, w, d in conns:
        a, b = (p, p + w) if direction > 0 else (p - w, p)
        out.append(dict(name=name, span=(round(a, 2), round(b, 2)), width=round(w, 2), depth=d))
        p = (b + CONN_GAP) if direction > 0 else (a - CONN_GAP)
    used = max(o['span'][1] for o in out) - min(o['span'][0] for o in out)
    fit = all(lo <= o['span'][0] and o['span'][1] <= hi for o in out)
    return out, round(used, 2), fit


def connectors():
    bx, by = BOARD['x'], BOARD['y']
    # inboard edge (Y = by[0]): from the front hole clearance rearward
    in_lo, in_hi = bx[0] + HOLE_INSET + HOLE_CLEAR, bx[1] - HOLE_INSET - HOLE_CLEAR
    inboard, in_used, in_fit = place(CONN_INBOARD, in_hi, -1, in_lo, in_hi)
    fr_lo, fr_hi = by[0] + HOLE_INSET + HOLE_CLEAR, by[1] - HOLE_INSET - HOLE_CLEAR
    front, _, f_fit = place(CONN_FRONT, 126.5, +1, fr_lo, fr_hi)    # XT30 in front of the input-protection zone
    return dict(inboard=dict(edge=f'Y {by[0]}', usable=(in_lo, in_hi), used_mm=in_used, fits=in_fit, items=inboard),
                front=dict(edge=f'X {bx[1]}', usable=(fr_lo, fr_hi), fits=f_fit, items=front))


def run_checks():
    b, usb, bosses = read_x1_body()
    cn = connectors()
    bud, cs = budget(), current_sense()
    used = sum(PIN_USE.values())
    room = Z_LIMIT - BOARD['z'][1]
    usb_z = BOARD['z'][1] + USBC['h']/2
    slot_new = (usb_z - USB_OLD['slot'][1]/2, usb_z + USB_OLD['slot'][1]/2)
    r = {
        'board_matches_x1_body': dict(x1_body=dict(board=b, usb=usb, bosses_4mm_inset=bosses),
                                      ok=b == BOARD and usb['x'] == USB_OLD['x'] and abs(usb['z'] - usb_z) < 0.05
                                      and tuple(usb['slot']) == USB_OLD['slot'] and bosses,
                                      note=f"the body's USB slot is at the board's Z {round(usb_z, 2)}, "
                                           f"moved down from {USB_OLD['z']}"),
        'power_budget': bud,
        'current_sense': cs,
        'pin_budget': dict(module='ESP32-S3-WROOM-1-N8', available=len(GPIO_AVAILABLE), use=PIN_USE, used=used,
                           spare=len(GPIO_AVAILABLE) - used, ok=used <= len(GPIO_AVAILABLE),
                           note='preliminary; the schematic assigns pins (strapping pins 0, 3, 45, 46 used with care)'),
        'connectors': cn,
        'height': dict(board_top=BOARD['z'][1], limit=Z_LIMIT, room_mm=round(room, 2), allowance_mm=PART_ALLOW,
                       ok=PART_ALLOW <= room),
        'usb_slot': dict(old_centre_z=USB_OLD['z'], new_centre_z=round(usb_z, 2), shift_mm=round(USB_OLD['z'] - usb_z, 2),
                         new_slot_z=tuple(round(v, 2) for v in slot_new),
                         inside_skirt=Z_SKIRT_BOT < slot_new[0] and slot_new[1] < Z_DECK),
        'link_timeout_ms': LINK_TIMEOUT_MS,
    }
    computed = {'worst_case_A': bud['worst_case_A'], 'with_4g_A': bud['with_4g_A'],
                'rail_5v_logic_A': bud['rail_5v_logic_A'], 'r_ipropi_1A_ohm': cs['rows'][0]['r_ipropi_ohm'],
                'r_ipropi_0.6A_ohm': cs['rows'][1]['r_ipropi_ohm'], 'r_ipropi_0.5A_ohm': cs['rows'][2]['r_ipropi_ohm'],
                'v_ipropi_run_V': cs['actuator_run_V'], 'gpio_used': used, 'gpio_total': len(GPIO_AVAILABLE),
                'height_room_mm': round(room, 2), 'usb_new_z': round(usb_z, 2), 'link_timeout_ms': LINK_TIMEOUT_MS}
    tol = {'r_ipropi_0.6A_ohm': 10}
    r['spec_quotes'] = {k: dict(spec=v, computed=computed[k], ok=abs(computed[k] - v) <= tol.get(k, 0.05 + 0.02*abs(v)))
                        for k, v in SPEC_QUOTES.items()}
    flags = [r['board_matches_x1_body']['ok'], bud['worst_under_fuse'], bud['rail_5v_ok'],
             all(x['within_adc'] for x in cs['rows']), r['pin_budget']['ok'], cn['inboard']['fits'], cn['front']['fits'],
             r['height']['ok'], r['usb_slot']['inside_skirt'],
             all(v['ok'] for v in r['spec_quotes'].values())]
    r['all_pass'] = all(flags)
    return r


# ---------------------------------------------------------------- drawing helpers --------------------------------
C = dict(power='#f4d9b0', drv='#cfe8cf', mcu='#ddd2ee', out='#d7e6f2', load='#e9e9e9', hand='#f6e7a8',
         later='#f7f7f7', edge='#333333', board='#eef3f7', red='#c0392b', green='#2e7d32', blue='#1f5f8b')


def sheet(title, sub, n):
    fig = plt.figure(figsize=FIG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 420); ax.set_ylim(0, 297); ax.axis('off')
    ax.add_patch(Rectangle((5, 5), 410, 287, fill=False, lw=1.2, ec=C['edge']))
    ax.text(10, 285, title, fontsize=17, weight='bold', va='top')
    ax.text(10, 276.5, sub, fontsize=10.5, va='top', color='#444')
    ax.text(410, 285, f'X1 control system · spec C1 issue 5 · sheet {n}/2', fontsize=10, ha='right', va='top')
    ax.text(410, 278, f'{DATE} · concept for sign-off, not a schematic or layout', fontsize=9, ha='right', va='top',
            color='#666')
    return fig, ax


def block(ax, x, y, w, h, head, lines, fc, ls='-', fs=8.6, hs=9.6, ec=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=2.2', fc=fc, ec=ec or C['edge'],
                                lw=1.1, ls=ls))
    ax.text(x + 2.5, y + h - 2.5, head, fontsize=hs, weight='bold', va='top')
    ax.text(x + 2.5, y + h - 8.2, '\n'.join(lines), fontsize=fs, va='top', linespacing=1.32)


def arrow(ax, p, q, text=None, both=False, color='#333', ls='-', lw=1.3, tpos=0.5, tdx=0, tdy=1.5, fs=8.2, ha='center'):
    ax.annotate('', xy=q, xytext=p, arrowprops=dict(arrowstyle='<|-|>' if both else '-|>', color=color, lw=lw, ls=ls,
                                                    shrinkA=0, shrinkB=0, mutation_scale=11))
    if text:
        mx, my = p[0] + (q[0] - p[0])*tpos + tdx, p[1] + (q[1] - p[1])*tpos + tdy
        ax.text(mx, my, text, fontsize=fs, ha=ha, va='bottom', color=color, linespacing=1.25)


def table(ax, x, y, rows, widths, fs=8.4, rh=5.6, head=True):
    for i, row in enumerate(rows):
        cx = x
        for j, (cell, w) in enumerate(zip(row, widths)):
            ax.text(cx, y - i*rh, cell, fontsize=fs, va='top', weight='bold' if head and i == 0 else 'normal')
            cx += w
    if head:
        ax.plot([x, x + sum(widths) - 2], [y - rh + 1.2]*2, color='#666', lw=0.6)


# ---------------------------------------------------------------- sheet 1 -----------------------------------------
def sheet1(pdf, chk):
    fig, ax = sheet('System block diagram',
                    'Handle → ESP-NOW → main board in the B102 left bay → 7 motor channels. 4G remote deferred: only '
                    'a header and 5 V reserve are provided now.', 1)
    bud = chk['power_budget']
    # handle
    block(ax, 12, 206, 104, 60, 'HANDLE  (parked: design restarts later)',
          ['ESP32-S3, own PCB', 'sends over ESP-NOW at 50 Hz: 4 stick axes,', 'speed setting, track ↑/↓, EMERGENCY STOP,',
           'RESUME, lamps, horn, re-sync (section 6)', 'receives 10 Hz telemetry',
           'appearance: to restart from a real,', 'cited product reference'], C['hand'], ls='--')
    # power chain
    block(ax, 12, 137, 104, 34, 'B106 battery hatch', ['3 × 18650 in series (3S1P) · 3S BMS',
                                                     '9.0–12.6 V · 150 mm lead with XT30'], C['power'])
    block(ax, 12, 92, 104, 34, 'B103 toolbox', ['5 A fuse · KCD1 main switch', '5.5 × 2.1 jack: 12.6 V CC/CV charger',
                                               '→ XT30 12 V link over T101 to the left bay'], C['power'])
    arrow(ax, (64, 137), (64, 126))
    ax.text(70, 131.5, '12 V link (XT30) to the board →', fontsize=7.8, color='#a0522d', va='center')
    # budget table
    ax.text(12, 80, 'Power budget at 9.6 V (checked in the JSON)', fontsize=9.6, weight='bold', va='top')
    rows = [('Load', 'A from battery'),
            ('Tracks 2 × 1.0 A + swing 0.6 A (limits)', f"{bud['tracks_and_swing_A']:.2f}"),
            ('4 actuators stalled at 0.5 A, on VBAT', f"{bud['actuators_stalled_A']:.2f}"),
            ('ESP32-S3, lamps, buzzer, via 5 V', f"{bud['logic_lamps_A']:.2f}"),
            ('Worst case, all at once', f"{bud['worst_case_A']:.2f}  < 5 A fuse"),
            ('Later: + 4G stick 5 V × 2 A', f"{bud['with_4g_A']:.2f}  review fuse then")]
    table(ax, 12, 73, rows, (74, 30), fs=8.3, rh=6.0)
    ax.text(12, 33, f"Assumes every channel at its limit, actuators stalled\nat {ACT_STALL} A, 5 V buck {EFF:.0%} efficient, "
            f"battery at {V_BAT_MIN} V.\nTypical heavy use is far lower: an actuator runs at\n0.08-0.32 A, the JGY-370 is "
            "rated 0.2 A.", fontsize=7.8, va='top', color='#555', linespacing=1.3)

    # main board
    ax.add_patch(FancyBboxPatch((132, 18), 172, 246, boxstyle='round,pad=0,rounding_size=3', fc=C['board'],
                                ec=C['blue'], lw=1.8))
    ax.text(136, 260, 'MAIN BOARD  ·  96 × 64 mm  ·  4 layers  ·  JLCPCB assembly', fontsize=10.5, weight='bold',
            va='top', color=C['blue'])
    ax.text(136, 253, 'B102 left bay, on the 4 existing bosses; parts on top only, ≤ 20 mm tall', fontsize=8.4,
            va='top', color=C['blue'])
    block(ax, 138, 200, 74, 45, 'Power entry', ['XT30 in (12 V link)', 'P-FET reverse-polarity protection',
                                               'TVS + bulk capacitors', 'VBAT 9.0–12.6 V', 'divider → ADC (battery)'],
          C['power'])
    block(ax, 222, 200, 76, 45, 'Rails', ['VBAT 9.0–12.6 V → all 7 drivers', '5 V buck, 3 A → logic, lamps,',
                                          '      buzzer + 2 A expansion reserve', '3.3 V LDO ≥ 0.5 A → ESP32-S3',
                                          '2.5 V reference → current limits'], C['power'])
    block(ax, 138, 122, 74, 66, 'ESP32-S3-WROOM-1-N8', ['PCB antenna at the outboard edge', 'USB-C, native USB (flash, logs)',
                                                       'ADC1: 7 currents + battery', '14 PWM/direction lines',
                                                       'shared nSLEEP, nFAULT', 'status LED, BOOT, RESET',
                                                       '33 of 36 GPIO (preliminary)'], C['mcu'])
    block(ax, 222, 150, 76, 40, '3 × DRV8876 on VBAT', ['ch 1  left track     1.0 A', 'ch 2  right track   1.0 A',
                                                       'ch 3  swing          0.6 A, 0.4 s ramp'], C['drv'], fs=8.3)
    block(ax, 222, 93, 76, 49, '4 × DRV8876 on VBAT', ['ch 4  boom left      0.5 A', 'ch 5  boom right    0.5 A',
                                                     'ch 6  stick            0.5 A', 'ch 7  bucket          0.5 A',
                                                     'boom pair: same command,', 'current balance, end re-sync'],
          C['drv'], fs=8.3)
    block(ax, 138, 58, 74, 54, 'Outputs', ['2 lamp outputs, 5 V, 100 mA, PWM', 'buzzer (travel alarm, warnings)',
                                           'expansion header JST-PH 4:', '5 V ≤ 2 A · GND · UART TX/RX',
                                           '(reserved for the later 4G link)'], C['out'])
    ax.text(222, 84, 'All 7 channels: PWM 20 kHz,\ndrive / brake (slow decay)\nlimit = 2.5 V ÷ (R × 1000 µA/A)\n'
            'R = 2.5 k / 4.17 k / 5.0 kΩ; IPROPI 2.5 V at limit', fontsize=7.6, va='top', linespacing=1.3)
    ax.text(138, 47, 'Link loss 350 ms → stop · E-STOP latches, RESUME clears · disarmed at power-up\nstalled 2 s → channel off · '
            'low battery: warn 10.5 V, stop 9.6 V', fontsize=8.2, va='top', linespacing=1.35, color=C['red'])
    # internal arrows
    arrow(ax, (212, 224), (222, 224))
    arrow(ax, (175, 200), (175, 188))
    arrow(ax, (260, 200), (260, 190))
    ax.plot([298, 301.5, 301.5], [207, 207, 125], color='#333', lw=1.1)
    arrow(ax, (301.5, 125), (298, 125))
    ax.text(300.8, 146, 'VBAT', fontsize=7.5, ha='right', va='center')
    arrow(ax, (212, 170), (222, 170), both=True)
    arrow(ax, (212, 130), (222, 125), both=True)
    ax.text(213.5, 147, 'PWM, DIR\nIPROPI', fontsize=7.2, ha='left', va='center', color='#555')
    arrow(ax, (175, 122), (175, 112))

    # loads
    block(ax, 318, 206, 92, 50, '6-way slip ring (4 rings used)', ['→ left track motor', '→ right track motor (mirrored:',
                                                                 '     firmware inverts it)', 'JGY-370-1260 12 V 200:1'],
          C['load'])
    block(ax, 318, 168, 92, 30, 'Swing motor', ['JGY-370-1260, worm, self-locking', 'on the turntable (no slip ring)'],
          C['load'])
    block(ax, 318, 100, 92, 58, 'ARM60: 4 × V6-U60 actuators', ['boom left + boom right (paired)', 'stick · bucket',
                                                                 'N20 12 V 1:50, M4 leadscrew', 'Hall end stops, 0.35 A PTC inside',
                                                                 '4.4–9.3 mm/s, leadscrew self-locks'], C['load'])
    block(ax, 318, 64, 92, 26, 'Lamps', ['roof work lamps · toolbox lamp'], C['load'])
    block(ax, 318, 18, 92, 38, 'LATER: 4G stick (Debian)', ['serial via the expansion header,', 'or Wi-Fi on a fixed channel',
                                                           'not designed in this phase'], C['later'], ls='--', ec='#888')
    arrow(ax, (298, 178), (318, 225), 'ch 1, 2', tpos=0.75, tdx=-1, tdy=0)
    arrow(ax, (298, 160), (318, 180), 'ch 3', tpos=0.5, tdx=0, tdy=0.5)
    arrow(ax, (298, 118), (318, 128), 'ch 4–7', tpos=0.5, tdy=0.8)
    arrow(ax, (212, 88), (318, 86))
    arrow(ax, (212, 60), (318, 44), color='#888', ls='--')
    # power into the board and the link
    arrow(ax, (116, 109), (138, 215), color='#a0522d')
    arrow(ax, (116, 222), (138, 160), both=True, color=C['blue'], lw=1.6)
    ax.text(14, 200, 'ESP-NOW 2.4 GHz, paired + encrypted\n50 Hz commands → · ← 10 Hz telemetry\nfixed Wi-Fi channel '
            '(default 1)', fontsize=8.2, color=C['blue'], va='top', ha='left', linespacing=1.3,
            bbox=dict(fc='white', ec='none', pad=0.5))
    pdf.savefig(fig); fig.savefig(PNG[0], dpi=110); plt.close(fig)


# ---------------------------------------------------------------- sheet 2 -----------------------------------------
def sheet2(pdf, chk):
    fig, ax = sheet('Main board concept in the B102 left bay',
                    'Top view in X1 machine coordinates (mm). Zones and connector edges only (issue 4: the floor plan of '
                    'the PCB layout in main_board/).', 2)
    bx, by, bz = BOARD['x'], BOARD['y'], BOARD['z']
    t = fig.add_axes([0.035, 0.05, 0.60, 0.81])
    t.set_xlim(-162, -26); t.set_ylim(63, 160); t.set_aspect('equal'); t.set_anchor('N')
    t.tick_params(labelsize=8); t.grid(True, lw=0.3, color='#ddd')
    t.set_xlabel('X (mm), front →', fontsize=9); t.set_ylabel('Y (mm), outboard ↑', fontsize=9)
    t.axhspan(Y_SKIRT_IN, Y_SKIRT_OUT, color='#bbb'); t.text(-161, 155, 'left skirt (outboard), wall Y 152–154',
                                                            fontsize=8, va='bottom')
    t.axhline(Y_FLOOR_IN, color='#888', ls='--', lw=0.8)
    t.text(-161, 66.5, 'bay floor inner edge Y 77 (dashed) · cables arrive over T101 from here (inboard)', fontsize=8,
           va='center', color='#555')
    t.add_patch(Rectangle((bx[0], by[0]), bx[1] - bx[0], by[1] - by[0], fc=C['board'], ec=C['blue'], lw=1.6))
    for x in (bx[0] + HOLE_INSET, bx[1] - HOLE_INSET):
        for y in (by[0] + HOLE_INSET, by[1] - HOLE_INSET):
            t.add_patch(Circle((x, y), HOLE_D/2, fc='white', ec='#333', lw=0.8))
            t.add_patch(Circle((x, y), 3.0, fill=False, ec='#999', lw=0.5, ls=':'))
    zones = [((-134, 120), 28, 26, '5 V buck', C['power']),
             ((-105, 120), 24, 20, 'USB-C ESD,\n3.3 V LDO,\nbuttons', C['mcu']),
             ((-80, 120), 21, 26, 'ESP32-S3\nmodule', C['mcu']),
             ((-57, 112), 15, 28, 'input\nprot.', C['power']),
             ((-130, 94), 24, 22, 'lamps,\nbuzzer', C['out']),
             ((-105, 94), 9, 22, 'swing\nDRV\n(VBAT)', C['drv']),
             ((-95, 94), 36, 22, '4 × DRV8876 (VBAT)\nthermal pads + vias', C['drv']),
             ((-58, 94), 16, 18, 'tracks\n2 × DRV\n(VBAT)', C['drv'])]
    for (x, y), w, h, s, fc in zones:
        t.add_patch(Rectangle((x, y), w, h, fc=fc, ec='#555', lw=0.7, alpha=0.9))
        t.text(x + w/2, y + h/2, s, fontsize=7.4, ha='center', va='center', linespacing=1.2)
    # module footprint + antenna keep-out
    mx0, mxc = MODULE_X[0], sum(MODULE_X)/2               # 18 x 25.5 module, antenna end at the outboard edge
    t.add_patch(Rectangle((mx0, by[1] - 25.5), 18.0, 25.5, fill=False, ec='#5b3f8c', lw=1.0))
    t.add_patch(Rectangle((mxc - ANT_KEEPOUT_HALF, by[1] - 6.75), 2*ANT_KEEPOUT_HALF, 6.75 + 4.0, fc='none', ec=C['red'],
                          lw=0.9, hatch='///'))
    t.text(mxc, by[1] + 5.2, 'antenna keep-out (±22)', fontsize=7.4, ha='center', color=C['red'])
    t.text(-161, 128, '← rear: counterweight\n    and steel shot,\n    far from the antenna', fontsize=7.4, va='center',
           color='#555')
    # USB-C
    ux = USB_OLD['x']
    t.add_patch(Rectangle((ux - USBC['w']/2, by[1] - 7.0), USBC['w'], 7.0 + USBC['overhang'], fc='#999', ec='#333',
                          lw=0.8))
    t.annotate('USB-C at X −98\n(same X as today)', xy=(ux, by[1] + 1), xytext=(ux + 12, by[1] + 7.5), fontsize=7.6,
               arrowprops=dict(arrowstyle='-', lw=0.6))
    # connectors
    cn = chk['connectors']
    for it in cn['inboard']['items']:
        a, b = it['span']
        t.add_patch(Rectangle((a, by[0]), b - a, it['depth'], fc='white', ec='#222', lw=0.9))
        t.text((a + b)/2, by[0] - 1.2, it['name'], fontsize=6.9, rotation=90, ha='center', va='top')
    for it in cn['front']['items']:
        a, b = it['span']
        t.add_patch(Rectangle((bx[1] - it['depth'], a), it['depth'], b - a, fc='white', ec='#222', lw=0.9))
        t.text(bx[1] + 1.2, (a + b)/2, it['name'], fontsize=7.0, ha='left', va='center')
    t.text(-33, 84, 'front edge:\nthe 12 V link\narrives here', fontsize=7.4, ha='center', va='top',
           color='#555')
    t.set_title('Top view, board at Z 110–111.6 (96 × 64 × 1.6 mm, holes Ø2.7 on the existing bosses)', fontsize=9.5)

    # section through the USB slot
    s = fig.add_axes([0.675, 0.47, 0.30, 0.36])
    s.set_xlim(72, 160); s.set_ylim(100, 141); s.set_aspect('equal')
    s.tick_params(labelsize=7.5); s.grid(True, lw=0.3, color='#ddd')
    s.set_xlabel('Y (mm), outboard →', fontsize=8.5); s.set_ylabel('Z (mm)', fontsize=8.5)
    s.add_patch(Rectangle((Y_FLOOR_IN, Z_SKIRT_BOT), Y_SKIRT_OUT - Y_FLOOR_IN, FLOOR_TOP - Z_SKIRT_BOT, fc='#bbb',
                          ec='none'))
    s.add_patch(Rectangle((Y_SKIRT_IN, Z_SKIRT_BOT), Y_SKIRT_OUT - Y_SKIRT_IN, Z_DECK + 3 - Z_SKIRT_BOT, fc='#bbb',
                          ec='none'))
    s.axhline(Z_DECK, color='#888', lw=0.8); s.text(74, Z_DECK + 0.6, 'deck / hood Z 136', fontsize=7)
    s.axhline(Z_LIMIT, color=C['red'], ls='--', lw=0.8); s.text(74, Z_LIMIT - 0.6, 'limit Z 134', fontsize=7,
                                                                 color=C['red'], va='top')
    s.axhline(bz[1] + PART_ALLOW, color=C['green'], ls=':', lw=0.9)
    s.text(74, bz[1] + PART_ALLOW - 0.6, f'parts ≤ {PART_ALLOW:.0f} mm → Z {bz[1] + PART_ALLOW:.1f}', fontsize=7,
           color=C['green'], va='top')
    s.add_patch(Rectangle((by[0], bz[0]), by[1] - by[0], bz[1] - bz[0], fc=C['blue'], ec='none'))
    for y in (by[0] + HOLE_INSET, by[1] - HOLE_INSET):
        s.add_patch(Rectangle((y - 3, FLOOR_TOP), 6, bz[0] - FLOOR_TOP, fc='#999', ec='none'))
    uz = chk['usb_slot']['new_centre_z']
    s.add_patch(Rectangle((by[1] - 7.0, bz[1]), 7.0 + USBC['overhang'], USBC['h'], fc='#666', ec='none'))
    hw = USB_OLD['slot'][1]/2
    s.add_patch(Rectangle((Y_SKIRT_IN - 0.3, USB_OLD['z'] - hw), Y_SKIRT_OUT - Y_SKIRT_IN + 0.6, 2*hw, fill=False,
                          ec=C['red'], ls='--', lw=1.0))
    s.add_patch(Rectangle((Y_SKIRT_IN - 0.3, uz - hw), Y_SKIRT_OUT - Y_SKIRT_IN + 0.6, 2*hw, fc='white',
                          ec=C['green'], lw=1.2))
    s.text(Y_SKIRT_IN - 1.5, USB_OLD['z'], f"old slot Z {USB_OLD['z']} (devkit on headers)", fontsize=7, va='center',
           ha='right', color=C['red'])
    s.text(Y_SKIRT_IN - 1.5, uz + 5.5, f'new slot Z {uz} (board USB-C)', fontsize=7, va='center', ha='right',
           color=C['green'])
    s.text(116, bz[0] - 1.2, 'board', fontsize=7, ha='center', va='top', color=C['blue'])
    s.set_title('Section at X −98 (through the USB slot)', fontsize=9.5)

    # notes
    ax.text(283, 132, 'Notes', fontsize=10, weight='bold', va='top')
    in_ = cn['inboard']; fr = cn['front']
    notes = [f"Inboard edge: {len(in_['items'])} connectors use {in_['used_mm']:.1f} of "
             f"{in_['usable'][1] - in_['usable'][0]:.0f} mm between the hole clearances.",
             'The tracks XH-4 is at the front end of the inboard edge.',
             'Front edge: the XT30, in front of the input zone.',
             'Outboard edge: USB-C and the module antenna (front end), away from the motor wiring.',
             f"Height: {chk['height']['room_mm']:.1f} mm free above the board (limit Z 134); parts and mated plugs ≤ 20 mm.",
             f"USB slot moves down {chk['usb_slot']['shift_mm']:.1f} mm to Z {uz} (slot Z "
             f"{chk['usb_slot']['new_slot_z'][0]}–{chk['usb_slot']['new_slot_z'][1]}, inside the skirt).",
             'Plug orientation (top or side entry) and plug clearance are fixed in the CAD phase.',
             'Zones are indicative; drivers need copper and vias under their thermal pads.']
    ax.text(283, 125, '\n'.join('· ' + n for n in notes), fontsize=8.0, va='top', linespacing=1.55, wrap=True)
    rows = [('Connector', 'Edge', 'Width')] + [(i['name'], 'inboard', f"{i['width']:.1f}") for i in in_['items']] + \
           [(i['name'], 'front', f"{i['width']:.1f}") for i in fr['items']]
    table(ax, 283, 69, rows, (58, 22, 18), fs=7.8, rh=5.0)
    pdf.savefig(fig); fig.savefig(PNG[1], dpi=110); plt.close(fig)


def main():
    chk = run_checks()
    CHECKS.write_text(json.dumps(chk, indent=1, ensure_ascii=False))
    with PdfPages(PDF) as pdf:
        sheet1(pdf, chk); sheet2(pdf, chk)
        d = pdf.infodict(); d['Title'] = 'X1 control system, spec C1 issue 5'; d['Subject'] = 'Concept for sign-off'
    bad = [k for k, v in chk['spec_quotes'].items() if not v['ok']]
    print('all_pass', chk['all_pass'], '| spec quote mismatches:', bad or 'none')
    print('budget', chk['power_budget']['worst_case_A'], chk['power_budget']['with_4g_A'],
          '| inboard used', chk['connectors']['inboard']['used_mm'], '| usb z', chk['usb_slot']['new_centre_z'])
    if not chk['all_pass']:
        raise SystemExit('checks failed')


if __name__ == '__main__':
    main()
