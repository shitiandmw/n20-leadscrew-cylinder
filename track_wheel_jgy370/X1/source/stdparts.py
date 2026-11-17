"""Bought standard parts of the X1 electrical system as CadQuery solids, each drawn from the maker's own drawing.

Every builder returns a list of (sub-name, shape, colour) in the part's local frame, so a caller can place the
pieces (place()) and keep the colours for the viewer and the STEP export. Frames are chosen for mating:

  XH / PH housings      mated on a top-entry header (pushed down, -Z): board top z = 0, pins along X at the pitch,
                        centred, the pin row at y = 0; the wires leave the top. The headers use the same frame.
  XT30U-F / XT30U-M     one mated frame: the male's mouth is x = 0, the male body and wires at -X, the female's nose
                        inside it and her body and wires at +X; the two contacts along Y at 5.0 pitch.
  SM plug / receptacle  one mated frame: the receptacle's mouth is x = 0, its body and wires at -X; the plug sits in
                        the hood with its body and wires at +X.
  Keystone 1043         holder base on z = 0, cell axis along Y, open side up (+Z); the two mounting holes at y = +-27.5.
  18650 cell            axis along Y, centred, positive end at +Y.
  BMS board             PCB on z = 0, 50 along X, 16 along Y.
  KCD1-101 rocker       panel surface at z = 0, the bezel above it (+Z), the body and terminals below; 21.2 along X.
  DC jack 5.5 x 2.1     panel surface at x = 0, the barrel forward (+X), the body behind (-X).
  Mini blade holder     body centred, leads along Y.

Sources (dimensions in mm):
  JST XH catalogue eXH.pdf: housing XHP-2/-4 (B 7.3 / 12.3 wide, 5.7 + 0.25 lock, 7.5 long); top-entry headers
      B2B-XH-A / B4B-XH-A (B 7.4 / 12.4, 5.75 deep, 7.0 tall, 9.8 mated); contacts SXH-001T-P0.6.
  JST PH catalogue ePH.pdf: housing PHR-3/-4 (B 7.8 / 9.8, 4.5 x 6.85); top-entry headers B3B/B4B-PH-K-S (B 7.9 / 9.9,
      4.5 deep, 6.0 tall, 8.0 mated).
  JST SM catalogue eSM.pdf: SMR-02V-B receptacle 7.5 x 8 x 18.2 (10.2 front), SMP-02V-BC plug 7.4 x 5.5 x 11.7;
      contacts SYM-001T-P0.6 (pin) and SHF-001T-0.8BS (socket).
  Amass drawings XT30U-F (10.2 x 5.2, 12.4 long, 3.0 solder tail), XT30U-M (13.7 long), XT30PW-M (on the board).
  Keystone drawing 1043 rev C (19 Aug 2010): 77.05 x 20.65 x 14.86, mounting holes 2 x Ø3.68 at 55.00, PC pins
      Ø1.57 x 3.30 at 71.64, contact tin-nickel plated phosphor bronze, base heat-resistant nylon.
  Samsung INR18650-35E: Ø18.55 x 65.25 max.
  Finglai KCD1-101 drawing: bezel 21.2 x 15.1, 3.5 above the panel; body 18.7 x 12.2 x 13.2; terminals 4.8 x 0.6
      at 7.1 pitch, 22.4 overall; panel cut-out 19 x 13 (+0.5/0).
  5.5 x 2.1 mm metal panel jack (DC-022B pattern, pcboard.ca jack-panel-5521): 8 mm hole, M8 nut and lock washer,
      max panel 2.1, solder terminals, 18.2 long overall.
  Littelfuse MINI FHM in-line holder (0FHM0001ZXJ): body size taken from the product photos (approximate, see BOM).
  HX-3S-01 3S 10 A protection board: 50 x 16 x 2 (seller data).
"""
import math
import cadquery as cq

# colours (viewer and STEP), linear RGB as the rest of the X1 CAD
NYLON_WHITE = (.93, .92, .86)      # JST natural PA
NYLON_BLACK = (.10, .10, .11)      # SM black housings, Keystone base, switch body
TIN = (.80, .81, .78)
GOLD = (.85, .66, .22)
XT_YELLOW = (.93, .72, .10)
CELL_PINK = (.78, .32, .52)        # Samsung 35E wrap
CELL_CAP = (.82, .82, .80)
PCB_BLUE = (.10, .28, .55)
PCB_GREEN = (.08, .20, .14)
RED = (.78, .12, .10)
BLACK_WIRE = (.12, .12, .13)
NUT = (.72, .73, .72)
CLEAR_BLACK = (.14, .14, .15)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl(axis, r, a0, a1, c1, c2):
    """Cylinder of radius r along axis ('x', 'y' or 'z') from a0 to a1, centred at the other two coordinates (in order)."""
    lo, hi = sorted([a0, a1])
    if axis == 'z':
        return cq.Workplane('XY').circle(r).extrude(hi - lo).translate((c1, c2, lo))
    if axis == 'y':
        return cq.Workplane('XZ').circle(r).extrude(-(hi - lo)).translate((c1, lo, c2))
    return cq.Workplane('YZ').circle(r).extrude(hi - lo).translate((lo, c1, c2))


def union_all(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.union(s)
    return out


def place(parts, origin=(0, 0, 0), rot=None, prefix=''):
    """Move every (name, shape, colour) of a builder: rot = (axis, degrees) or a list of them, applied in order about
    the local origin, then the translation. Returns the same list with the names prefixed."""
    out = []
    rots = [] if rot is None else ([rot] if not isinstance(rot[0], (list, tuple)) or len(rot) == 2 and isinstance(rot[1], (int, float)) else list(rot))
    for n, s, c in parts:
        for axis, deg in rots:
            s = s.rotate((0, 0, 0), axis, deg)
        out.append((prefix + n, s.translate(origin), c))
    return out


# ------------------------------------------------------------------ JST XH (2.5 mm)
# The X1 main board's JST headers are top entry since 2026-11-14 (side-entry S*B before). Frame of the headers and of
# the housings mated on them: board top z = 0, pins along X at the pitch, centred, the pin row at y = 0; the header's
# far side from the pin row (3.4 XH, 2.8 PH) toward -y.
XH_TOP = dict(header_h=7.0, near=2.35, far=3.4, mated=9.8)        # eXH.pdf p.2 and p.5 (B2B-XH-A)
PH_TOP = dict(header_h=6.0, near=1.7, far=2.8, mated=8.0)         # ePH.pdf p.1 and p.3 (B*B-PH-K-S)


def xh_housing(n, wire_len=6.0, wire_colours=None):
    """XHP-n housing pushed down onto a top-entry B{n}B-XH-A header: B x 5.7 (+ 0.25 latch ramp) x 7.5 long, its top 9.8
    above the board (the mated height), so its leading face is 2.3 above the board inside the 7.0 header. Centred on the
    header body; the latch ramp is drawn on the -y face. The wires leave the top (+Z) over the pins."""
    pitch, B, T, L, top = 2.5, 2.5 * (n - 1) + 4.8, 5.7, 7.5, XH_TOP['mated']
    yc = (XH_TOP['near'] - XH_TOP['far']) / 2                     # -0.525: the header body's centre
    body = box(-B / 2, B / 2, yc - T / 2, yc + T / 2, top - L, top).edges('|Z').chamfer(0.4)
    for i in range(n):
        x = (i - (n - 1) / 2) * pitch
        body = body.cut(cyl('z', .8, top - 2.0, top + .1, x, 0.0))                     # wire holes over the contacts
    lock = box(-B / 2 + 1.0, B / 2 - 1.0, yc - T / 2 - .25, yc - T / 2 + .01, top - 5.0, top - 1.6)
    parts = [('housing', body.union(lock), NYLON_WHITE)]
    cols = wire_colours or ([RED, BLACK_WIRE] + [(.9, .5, .1), (.5, .2, .6)])[:n]
    for i in range(n):
        x = (i - (n - 1) / 2) * pitch
        parts.append((f'wire_{i + 1}', cyl('z', .45, top - .5, top + wire_len, x, 0.0), cols[i]))
    return parts


def xh_header(n):
    """B{n}B-XH-A top-entry header for a stand-alone model (the board carries KiCad's own model): body B x 5.75, 7.0
    tall, open at the top; the pin row 2.35 from its +y face and 3.4 from its -y face, where the latch window is; square
    0.64 posts from 3.4 below the board."""
    pitch, B, h = 2.5, 2.5 * (n - 1) + 4.9, XH_TOP['header_h']
    y0, y1 = -XH_TOP['far'], XH_TOP['near']
    body = box(-B / 2, B / 2, y0, y1, 0.0, h)
    body = body.cut(box(-B / 2 + .8, B / 2 - .8, y0 + .8, y1 - .8, 1.5, h + .1))       # cavity for the housing
    body = body.cut(box(-B / 2 + 1.5, B / 2 - 1.5, y0 - .1, y0 + .9, 3.0, h - 1.0))     # latch window
    pins = [box(x - .32, x + .32, -.32, .32, -3.4, h - 1.0) for x in ((i - (n - 1) / 2) * pitch for i in range(n))]
    return [('header', body, NYLON_WHITE), ('pins', union_all(pins), TIN)]


# ------------------------------------------------------------------ JST PH (2.0 mm)
def ph_housing(n, wire_len=6.0, wire_colours=None):
    """PHR-n housing pushed down onto a top-entry B{n}B-PH-K-S header: B x 4.5 x 6.85 long, its top 8.0 above the board
    (the mated height). Centred on the header body; latch ramp on the -y face; the wires leave the top."""
    pitch, B, T, L, top = 2.0, 2.0 * (n - 1) + 3.8, 4.5, 6.85, PH_TOP['mated']
    yc = (PH_TOP['near'] - PH_TOP['far']) / 2                     # -0.55
    body = box(-B / 2, B / 2, yc - T / 2, yc + T / 2, top - L, top).edges('|Z').chamfer(0.3)
    for i in range(n):
        x = (i - (n - 1) / 2) * pitch
        body = body.cut(cyl('z', .65, top - 1.6, top + .1, x, 0.0))
    lock = box(-B / 2 + .8, B / 2 - .8, yc - T / 2 - .3, yc - T / 2 + .01, top - 4.2, top - 1.2)
    parts = [('housing', body.union(lock), NYLON_WHITE)]
    cols = wire_colours or ([RED, (.9, .5, .1), BLACK_WIRE, (.5, .2, .6)])[:n]
    for i in range(n):
        x = (i - (n - 1) / 2) * pitch
        parts.append((f'wire_{i + 1}', cyl('z', .4, top - .5, top + wire_len, x, 0.0), cols[i]))
    return parts


def ph_header(n):
    """B{n}B-PH-K-S top-entry header (stand-alone model): body B x 4.5, 6.0 tall, open at the top; the pin row 1.7 from
    its +y face; 0.5 square posts from 3.0 below the board."""
    pitch, B, h = 2.0, 2.0 * (n - 1) + 3.9, PH_TOP['header_h']
    y0, y1 = -PH_TOP['far'], PH_TOP['near']
    body = box(-B / 2, B / 2, y0, y1, 0.0, h).cut(box(-B / 2 + .6, B / 2 - .6, y0 + .6, y1 - .6, 1.0, h + .1))
    body = body.cut(box(-B / 2 + 1.2, B / 2 - 1.2, y0 - .1, y0 + .7, 2.5, h - 1.0))     # latch window
    pins = [box(x - .25, x + .25, -.25, .25, -3.0, h - 1.0) for x in ((i - (n - 1) / 2) * pitch for i in range(n))]
    return [('header', body, NYLON_WHITE), ('pins', union_all(pins), TIN)]


# ------------------------------------------------------------------ Amass XT30 (cable ends)
def _xt_profile(w, h, r):
    return cq.Workplane('YZ').rect(w, h).extrude(1).edges('|X').fillet(r)


XT30 = dict(w=10.2, h=5.2, pitch=5.0, tail=3.0, f_len=12.4, m_len=13.7, nose=6.0, nose_w=9.0, nose_h=4.0, pin_r=1.0)


def xt30u_f(wire_len=8.0, tail=True):
    """XT30U-F female cable connector: housing 10.2 x 5.2, 12.4 long including the 3.0 solder tail; its 6.0 long nose
    (9.0 x 4.0, carrying the two socket contacts at 5.0 pitch) slides into the male's shroud. Mated frame shared with
    xt30u_m(): the male's mouth is the plane x = 0, the female sits on the +X side with its nose inside (x -6..0),
    its shoulder at x 0..3.4, the tail to 6.4 and the wires on beyond (+X)."""
    W, H, T, L, N = XT30['w'], XT30['h'], XT30['tail'], XT30['f_len'], XT30['nose']
    shoulder = L - T - N                                                    # 3.4
    nose = cq.Workplane('YZ').rect(XT30['nose_w'], XT30['nose_h']).extrude(N).edges('|X').fillet(.6).translate((-N, 0, 0))
    body = cq.Workplane('YZ').rect(W, H).extrude(shoulder).edges('|X').fillet(1.2)
    body = body.union(nose)
    for y in (-XT30['pitch'] / 2, XT30['pitch'] / 2):
        body = body.cut(cyl('x', 1.4, -N - .1, shoulder + .1, y, 0.0))
    parts = [('housing', body, XT_YELLOW)]
    socks = []
    for y in (-XT30['pitch'] / 2, XT30['pitch'] / 2):
        socks.append(cyl('x', 1.35, -N + .4, shoulder, y, 0.0).cut(cyl('x', 1.08, -N + .3, shoulder - 1.0, y, 0.0)))
        if tail:
            socks.append(cyl('x', 1.0, shoulder - .5, L - T + T, y, 0.0).cut(box(shoulder + .8, L + .1, y - 1.1, y + 1.1, .2, 1.2)))
    parts.append(('contacts', union_all(socks), GOLD))
    if wire_len > 0:
        for y, c in ((-XT30['pitch'] / 2, RED), (XT30['pitch'] / 2, BLACK_WIRE)):
            parts.append((f'wire_{"pos" if c is RED else "neg"}', cyl('x', 1.0, L - 1.5, L + wire_len, y, 0.0), c))
    return parts


def xt30u_m(wire_len=8.0, tail=True):
    """XT30U-M male cable connector: 10.2 x 5.2, 13.7 long including the 3.0 tail; a 6.0 deep shroud (9.1 x 4.1) at the
    mouth (x = 0) with the two Ø2 pins inside; the body runs to x = -10.7, the tail to -13.7, the wires on in -X."""
    W, H, T, L, N = XT30['w'], XT30['h'], XT30['tail'], XT30['m_len'], XT30['nose']
    body = cq.Workplane('YZ').rect(W, H).extrude(L - T).edges('|X').fillet(1.2).translate((-(L - T), 0, 0))
    body = body.cut(cq.Workplane('YZ').rect(XT30['nose_w'] + .1, XT30['nose_h'] + .1).extrude(N + .1).edges('|X').fillet(.6).translate((-N, 0, 0)))
    for y in (-XT30['pitch'] / 2, XT30['pitch'] / 2):
        body = body.cut(cyl('x', 1.05, -(L - T) - .1, -N + .1, y, 0.0))
    parts = [('housing', body, XT_YELLOW)]
    pins = [cyl('x', XT30['pin_r'], -(L - T) + .5, -.6, y, 0.0) for y in (-XT30['pitch'] / 2, XT30['pitch'] / 2)]
    if tail:
        pins += [cyl('x', 1.0, -L, -(L - T) + .6, y, 0.0).cut(box(-L - .1, -(L - T) - .8, y - 1.1, y + 1.1, .2, 1.2)) for y in (-XT30['pitch'] / 2, XT30['pitch'] / 2)]
    parts.append(('contacts', union_all(pins), GOLD))
    if wire_len > 0:
        for y, c in ((-XT30['pitch'] / 2, RED), (XT30['pitch'] / 2, BLACK_WIRE)):
            parts.append((f'wire_{"pos" if c is RED else "neg"}', cyl('x', 1.0, -L - wire_len, -L + 1.5, y, 0.0), c))
    return parts


# ------------------------------------------------------------------ JST SM (wire-to-wire, 2.5 mm)
SM = dict(pitch=2.5, r_w=7.5, r_h=8.0, r_len=18.2, hood=8.0, rear_h=5.5, p_w=7.4, p_h=5.5, p_len=11.7)


def sm_receptacle(n=2, wire_len=8.0):
    """SMR-0nV-B receptacle housing (pin contacts SYM-001T-P0.6): 7.5 wide x 8.0 high, 18.2 long; the front 8.0 is the
    hood that takes the 7.4 x 5.5 plug (open at the sides, with the latch catches), the rear 10.2 is the 5.5 high wire
    end. Mouth at x = 0, body in -X; the plug comes from +X (sm_plug() at the same origin)."""
    W, Hh, Hr, L, hood = 2.5 * (n - 1) + 5.0, SM['r_h'], SM['rear_h'], SM['r_len'], SM['hood']
    zc = Hr / 2                                                                   # the wire-end centre line
    plate_t = (Hh - SM['p_h'] - .1) / 2                                            # 1.2 hood plates above and below the plug
    hood_s = box(-hood, 0.0, -W / 2, W / 2, 0.0, Hh)
    hood_s = hood_s.cut(box(-hood + 1.0, .1, -W / 2 - .1, W / 2 + .1, plate_t, plate_t + SM['p_h'] + .1))   # open-sided cavity
    hood_s = hood_s.cut(box(-hood + 2.5, -1.0, -W / 2 + 1.5, W / 2 - 1.5, Hh - plate_t - .1, Hh + .1))        # latch window on top
    rear = box(-L, -hood + .01, -W / 2 + .05, W / 2 - .05, plate_t + SM['p_h'] / 2 - Hr / 2, plate_t + SM['p_h'] / 2 + Hr / 2).edges('|X').chamfer(.5)
    body = hood_s.union(rear)
    zp = plate_t + SM['p_h'] / 2                                                   # contact axis
    pins = []
    for i in range(n):
        y = (i - (n - 1) / 2) * 2.5
        body = body.cut(cyl('x', .8, -L - .1, -hood + 1.0, y, zp))
        pins.append(cyl('x', .45, -hood + .5, -1.0, y, zp))
    parts = [('housing', body, NYLON_BLACK), ('pins', union_all(pins), TIN)]
    for i in range(n):
        y = (i - (n - 1) / 2) * 2.5
        parts.append((f'wire_{i + 1}', cyl('x', .65, -L - wire_len, -L + .5, y, zp), [RED, BLACK_WIRE][i % 2]))
    return parts


def sm_plug(n=2, wire_len=8.0, inserted=None):
    """SMP-0nV-BC plug housing (socket contacts SHF-001T-0.8BS): 7.4 wide x 5.5 high, 11.7 long, with the latch arm on
    top and the ramp below. Drawn mated into sm_receptacle() at the same origin: its front sits in the hood (x -8..0),
    3.7 stands proud, the wires leave in +X."""
    W, L, H = 2.5 * (n - 1) + 4.9, SM['p_len'], SM['p_h']
    ins = SM['hood'] if inserted is None else inserted
    z0 = (SM['r_h'] - H - .1) / 2 + .05
    x0 = -ins
    body = box(x0, x0 + L, -W / 2, W / 2, z0, z0 + H).edges('|X').chamfer(.4)
    arm = (cq.Workplane('XZ').polyline([(x0 + 2.5, z0 + H - .01), (x0 + L - .5, z0 + H - .01), (x0 + L - .5, z0 + H + 1.4),
                                        (x0 + 6.0, z0 + H + 1.4), (x0 + 4.5, z0 + H + 2.3), (x0 + 2.5, z0 + H + 2.3)]).close()
           .extrude(-(W - 3.4)).translate((0, -(W - 3.4) / 2, 0)))
    body = body.union(arm)
    zp = z0 + H / 2
    for i in range(n):
        y = (i - (n - 1) / 2) * 2.5
        body = body.cut(cyl('x', .75, x0 + L - 4.0, x0 + L + .1, y, zp))
        body = body.cut(cyl('x', .6, x0 - .1, x0 + 3.0, y, zp))
    parts = [('housing', body, NYLON_BLACK)]
    for i in range(n):
        y = (i - (n - 1) / 2) * 2.5
        parts.append((f'wire_{i + 1}', cyl('x', .65, x0 + L - .5, x0 + L + wire_len, y, zp), [RED, BLACK_WIRE][i % 2]))
    return parts


# ------------------------------------------------------------------ Keystone 1043 and the 18650 cell
K1043 = dict(l=77.05, w=20.65, h=14.86, hole_d=3.68, hole_pitch=55.0, pin_d=1.57, pin_l=3.30, pin_pitch=71.64,
             wall=1.3, base=1.8, cell_d=18.55, cell_l=65.25)
K1043['cell_y'] = (K1043['l'] / 2 - K1043['wall'] - 0.8) - K1043['cell_l'] / 2     # the spring presses the cell onto the + dimple: cell centre +3.8


def keystone_1043(with_pins=True):
    """Keystone 1043 single 18650 holder (THM): a nylon cradle 77.05 long (Y) x 20.65 wide (X), 14.86 high, open at
    the top; two end walls carry the tin-nickel contacts (coil spring at -Y, flat button contact at +Y), each with a
    Ø1.57 PC pin 3.30 below the base at 71.64 pitch; two Ø3.68 mounting holes in the base at 55.00 pitch (y = +-27.5).
    The cell axis is 10.9 above the base bottom (base 1.8 + radius 9.1 of the cradle), so the cell stands 5.4 proud."""
    L, W, H, wall, base = K1043['l'], K1043['w'], K1043['h'], K1043['wall'], K1043['base']
    rc = K1043['cell_d'] / 2 + .15
    zc = base + rc
    body = box(-W / 2, W / 2, -L / 2, L / 2, 0.0, H)
    # the cradle: a cylinder along Y between the end walls, open at the top
    body = body.cut(cyl('y', rc, -L / 2 + wall, L / 2 - wall, 0.0, zc))
    body = body.cut(box(-rc, rc, -L / 2 + wall, L / 2 - wall, zc, H + 1))
    # lightening windows in the side walls (as the Keystone cradle: open sides between the end walls)
    for y0, y1 in ((-L / 2 + 6.0, -14.0), (-9.0, 9.0), (14.0, L / 2 - 6.0)):
        body = body.cut(box(-W / 2 - .1, W / 2 + .1, y0, y1, base + 2.0, H - 2.2))
    # retaining lips at the top of the side walls near the ends: above the cell's equator, where it is narrower (0.4 engagement)
    for y in (-L / 2 + 10.0, L / 2 - 10.0):
        for sx in (1, -1):
            body = body.union(box(min(sx * (rc - .5), sx * rc), max(sx * (rc - .5), sx * rc), y - 2.0, y + 2.0, H - 1.0, H))
    # mounting holes in the base, on the centreline, and the holes the PC pins pass through
    for y in (-K1043['hole_pitch'] / 2, K1043['hole_pitch'] / 2):
        body = body.cut(cyl('z', K1043['hole_d'] / 2, -1.0, base + .1, 0.0, y))
    for y in (-K1043['pin_pitch'] / 2, K1043['pin_pitch'] / 2):
        body = body.cut(cyl('z', K1043['pin_d'] / 2 + .05, -1.0, base + .1, 0.0, y))
    parts = [('cradle', body, NYLON_BLACK)]
    # contacts on the end walls' inner faces: the coil spring at -Y (compressed to 7.8 by the cell), the flat plate with the
    # dimple at +Y; the cell (K1043['cell_y']) sits against the dimple
    yw = L / 2 - wall
    y_cell_end = K1043['cell_y'] - K1043['cell_l'] / 2                   # -28.8
    spring = None
    n_turns = 7
    pitch = (y_cell_end - .1 - (-yw + .3)) / n_turns
    for k in range(n_turns):
        y0 = -yw + .3 + k * pitch
        ring = cyl('y', 4.2, y0, y0 + .5, 0.0, zc).cut(cyl('y', 3.4, y0 - .1, y0 + .6, 0.0, zc))
        spring = ring if spring is None else spring.union(ring)
    plate_neg = box(-5.0, 5.0, -yw, -yw + .3, zc - 6.0, zc + 6.0)
    plate_pos = box(-5.0, 5.0, yw - .3, yw, zc - 6.0, zc + 6.0).union(cyl('y', 2.2, yw - .8, yw - .3, 0.0, zc))
    cont = spring.union(plate_neg).union(plate_pos)
    if with_pins:
        for y in (-K1043['pin_pitch'] / 2, K1043['pin_pitch'] / 2):
            cont = cont.union(cyl('z', K1043['pin_d'] / 2, -K1043['pin_l'], base, 0.0, y))
    parts.append(('contacts', cont, TIN))
    return parts


def cell_18650():
    """Samsung INR18650-35E (Ø18.55 x 65.25 max): pink wrap, bare steel ends, the positive button at +Y (flat-top cell:
    the button is flush, shown as a Ø8.5 pad)."""
    r, L = 18.55 / 2, 65.25
    wrap = cyl('y', r, -L / 2 + 1.0, L / 2 - 1.0, 0.0, 0.0)
    neg = cyl('y', r - .35, -L / 2, -L / 2 + 1.0, 0.0, 0.0)
    pos = cyl('y', r - .35, L / 2 - 1.0, L / 2 - .3, 0.0, 0.0).union(cyl('y', 4.25, L / 2 - .3, L / 2, 0.0, 0.0))
    ring = cyl('y', r - .35, L / 2 - .3, L / 2 - .05, 0.0, 0.0).cut(cyl('y', 6.5, L / 2 - .4, L / 2 + .1, 0.0, 0.0))
    return [('wrap', wrap, CELL_PINK), ('ends', neg.union(pos), CELL_CAP), ('insulator', ring, (.95, .95, .92))]


def bms_hx3s01():
    """HX-3S-01 3S 10 A protection board: 50 x 16 PCB, 1.2 thick, two SOP-8 MOSFETs and the protection IC on top,
    pads B-, B1, B2, B+ at one long edge and P-, P+ at the other end. Board on z = 0."""
    pcb = box(-25.0, 25.0, -8.0, 8.0, 0.0, 1.2).edges('|Z').fillet(1.0)
    parts = [('pcb', pcb, PCB_BLUE)]
    fets = union_all([box(x - 2.5, x + 2.5, -2.0, 2.0, 1.2, 2.7) for x in (-9.0, 9.0)])
    ic = box(-3.0, 3.0, -3.5, -.5, 1.2, 2.2)
    parts.append(('parts', fets.union(ic), (.12, .12, .13)))
    pads = union_all([box(x - 1.6, x + 1.6, 5.2, 7.5, 1.2, 1.25) for x in (-21.0, -14.0, -7.0, 0.0)] +
                     [box(x - 1.6, x + 1.6, -7.5, -5.2, 1.2, 1.25) for x in (14.0, 21.0)])
    parts.append(('pads', pads, TIN))
    return parts


# ------------------------------------------------------------------ toolbox parts
def kcd1_101():
    """KCD1-101 rocker switch (Finglai drawing): bezel 21.2 x 15.1, 3.5 above the panel (z = 0) including the rocker;
    body 18.7 x 12.2 and 13.2 deep below the panel; two 4.8 x 0.6 solder/faston terminals at 7.1 pitch, 5.7 long."""
    bezel = box(-10.6, 10.6, -7.55, 7.55, 0.0, 1.6).edges('|Z').fillet(1.0)
    bezel = bezel.cut(box(-9.0, 9.0, -4.6, 4.6, 1.0, 1.7))
    body = box(-9.35, 9.35, -6.1, 6.1, -13.2, .01)
    rocker = (cq.Workplane('XY').polyline([(-8.8, 1.0), (8.8, 1.0), (8.8, 1.9), (0.0, 3.5), (-8.8, 2.4)]).close()
              .extrude(9.2).translate((0, -4.6, 0)))
    rocker = rocker.rotate((0, 0, 0), (0, 0, 1), 0)
    terms = union_all([box(x - 2.4, x + 2.4, -.3, .3, -13.2 - 5.7, -13.2 + .01) for x in (-3.55, 3.55)])
    return [('bezel', bezel.union(body), NYLON_BLACK), ('rocker', rocker, (.16, .16, .18)), ('terminals', terms, TIN)]


def dc_jack_5521(panel_t=2.0):
    """5.5 x 2.1 mm metal panel-mount DC jack (DC-022B pattern): Ø8 M8 threaded barrel through the panel (x = 0 is the
    panel's outer face, +X outward) with the nut and lock washer outside, the round plastic body and three solder
    lugs behind; 18.2 long overall."""
    barrel = cyl('x', 4.0, -panel_t - 1.0, 7.0, 0.0, 0.0).cut(cyl('x', 2.9, 1.0, 7.1, 0.0, 0.0))
    pin = cyl('x', 1.05, 1.5, 6.5, 0.0, 0.0)
    washer = cyl('x', 5.2, .0, 1.0, 0.0, 0.0).cut(cyl('x', 4.05, -.1, 1.1, 0.0, 0.0))
    nut = (cq.Workplane('YZ').polygon(6, 11.0 / math.cos(math.pi / 6)).extrude(2.3).translate((1.0, 0, 0))
           .cut(cyl('x', 4.05, .9, 3.4, 0.0, 0.0)))
    body = cyl('x', 5.1, -panel_t - 1.0 - 8.2, -panel_t - .99, 0.0, 0.0)
    xb = -panel_t - 1.0 - 8.2
    lugs = union_all([box(xb - 6.0, xb, y - 1.0, y + 1.0, z - .3, z + .3) for y, z in ((0.0, 3.6), (3.2, -2.4), (-3.2, -2.4))])
    return [('barrel', barrel.union(pin), NUT), ('nut_and_washer', nut.union(washer), NUT), ('body', body, NYLON_BLACK), ('lugs', lugs, TIN)]


def fuse_holder_mini(lead_len=15.0):
    """Littelfuse MINI FHM in-line waterproof blade fuse holder (0FHM0001ZXJ-F7.5 pattern): a two-piece body with the
    hinged cover over the fuse, leads out of both ends along Y. The body envelope (36 x 15 x 16) is taken from the
    product photographs, not from a drawing: an approximation, see the BOM note."""
    body = box(-7.5, 7.5, -18.0, 18.0, 0.0, 9.0).edges('|Y').fillet(2.5)
    cover = box(-6.5, 6.5, -11.0, 11.0, 8.9, 16.0).edges('|Y').fillet(2.0)
    strap = box(-1.5, 1.5, 8.0, 19.0, 12.0, 14.0)
    leads = union_all([cyl('y', 1.65, -18.0 - lead_len, -17.5, 0.0, 4.5), cyl('y', 1.65, 17.5, 18.0 + lead_len, 0.0, 4.5)])
    return [('body', body.union(cover).union(strap), CLEAR_BLACK), ('leads', leads, RED)]


ALL = dict(XHP_2=lambda: xh_housing(2), XHP_4=lambda: xh_housing(4), B2B_XH_A=lambda: xh_header(2), B4B_XH_A=lambda: xh_header(4),
           PHR_3=lambda: ph_housing(3), PHR_4=lambda: ph_housing(4), B3B_PH_K_S=lambda: ph_header(3), B4B_PH_K_S=lambda: ph_header(4),
           XT30U_F=xt30u_f, XT30U_M=xt30u_m, SMR_02V_B=sm_receptacle, SMP_02V_BC=sm_plug,
           Keystone_1043=keystone_1043, INR18650_35E=cell_18650, HX_3S_01=bms_hx3s01, KCD1_101=kcd1_101,
           DC_jack_5521=dc_jack_5521, Mini_FHM_fuse_holder=fuse_holder_mini)


if __name__ == '__main__':
    import sys
    from pathlib import Path
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    for name, fn in ALL.items():
        parts = fn()
        bb = union_all([s for _, s, _ in parts]).val().BoundingBox()
        print(f'{name:22s} {len(parts)} pieces  {bb.xlen:6.2f} x {bb.ylen:6.2f} x {bb.zlen:6.2f}  '
              f'[{bb.xmin:.2f},{bb.xmax:.2f}] [{bb.ymin:.2f},{bb.ymax:.2f}] [{bb.zmin:.2f},{bb.zmax:.2f}]')
        if out:
            asm = cq.Assembly(name=name)
            for n, s, c in parts:
                asm.add(s, name=n, color=cq.Color(*c))
            asm.save(str(out / f'{name}.step'), exportType='STEP')
