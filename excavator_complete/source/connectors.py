"""Every connector of the complete X1 excavator: type, exact model, what mates with it, where it is and how it is fitted.

This is the single source for CONNECTORS.md / connectors.csv (build_connectors.py), the BOM rows (build_bom.py) and the
connector layer of the viewer (build_viewer.py: realistic models of the free connectors, their assembly step, the
direction they are pushed in). The plugs on the main board, the battery pack and the toolbox parts are drawn by the
body CAD (track_wheel_jgy370/X1/source/x1_body.py from stdparts.py and the board STEP) and reach the viewer through
body_scene.json.gz; the wire-to-wire joints in the carbody and at the body seam are drawn here.

Frames: vehicle (X forward, Y left, Z up, origin on the ground under the swing centre), swing 0.
"""
import math
import numpy as np
import common as K
import harness as H

# ------------------------------------------------------------------ the connector types (one row per model number)
TYPES = {
    'XT30PW-M': dict(maker='Amass (Changzhou Amass Electronics)', model='XT30PW-M30.G.Y', family='XT30, PCB right-angle male', pins=2, rating='15 A, 500 V DC',
                     mates='XT30U-F', body='PA yellow UL94 V-0, brass gold-flash contacts', source='LCSC C431092; Amass spec XT30PW-M V1.2 (TME XT30PW-M.pdf)',
                     note='through-hole, 2 x Ø1.7 pins at 5.0 pitch and 2 x Ø1.0 pegs'),
    'XT30U-F': dict(maker='Amass', model='XT30U-F', family='XT30 cable female', pins=2, rating='15 A, 500 V DC',
                    mates='XT30U-M or XT30PW-M', body='PA yellow, gold-flash brass sockets, solder cups for 18 AWG', source='Amass spec XT30U-F V1.2 (TME XT30U-F.pdf): 10.2 x 5.2, 12.4 long',
                    note='the battery side of a joint is always the female: no live pin exposed'),
    'XT30U-M': dict(maker='Amass', model='XT30U-M', family='XT30 cable male', pins=2, rating='15 A, 500 V DC',
                    mates='XT30U-F', body='PA yellow, gold-flash brass pins, solder cups for 18 AWG', source='Amass spec XT30U-M V1.2 (TME XT30U-M.pdf): 10.2 x 5.2, 13.7 long', note=''),
    'S2B-XH-A': dict(maker='JST', model='S2B-XH-A(LF)(SN)', family='XH 2.5 mm, side-entry header, 2 circuits', pins=2, rating='3 A, 250 V',
                     mates='XHP-2 + 2 x SXH-001T-P0.6', body='PA 66 natural, tin-plated brass posts', source='LCSC C157931; JST eXH.pdf p.5 (B 7.4, 6.1 high, 7.0 deep)', note=''),
    'S4B-XH-A': dict(maker='JST', model='S4B-XH-A(LF)(SN)', family='XH 2.5 mm, side-entry header, 4 circuits', pins=4, rating='3 A, 250 V',
                     mates='XHP-4 + 4 x SXH-001T-P0.6', body='PA 66 natural, tin-plated brass posts', source='LCSC C157925; JST eXH.pdf p.5 (B 12.4)', note=''),
    'XHP-2': dict(maker='JST', model='XHP-2', family='XH housing, 2 circuits', pins=2, rating='3 A', mates='S2B-XH-A (or B2B-XH-A)',
                  body='PA 6 natural (white), 7.3 x 5.7 x 7.5', source='JST eXH.pdf p.4', contacts='SXH-001T-P0.6 (AWG 28-22, insulation Ø0.9-1.9), crimp tool JST WC-110 or Engineer PA-09',
                  note='the V6 cable wires (28 AWG PTFE, Ø0.8) are under the insulation range: slip 1.2 mm heat-shrink over each wire end before crimping'),
    'XHP-4': dict(maker='JST', model='XHP-4', family='XH housing, 4 circuits', pins=4, rating='3 A', mates='S4B-XH-A',
                  body='PA 6 natural (white), 12.3 x 5.7 x 7.5', source='JST eXH.pdf p.4', contacts='SXH-001T-P0.6 x 4', note='the slip ring\'s own leads (about Ø1.0) crimp directly'),
    'S3B-PH-K-S': dict(maker='JST', model='S3B-PH-K-S(LF)(SN)', family='PH 2.0 mm, side-entry header, 3 circuits', pins=3, rating='2 A, 100 V',
                       mates='PHR-3 + 3 x SPH-002T-P0.5S', body='PA natural, tin-plated posts', source='LCSC C157929; JST ePH.pdf p.3 (B 7.9)', note=''),
    'S4B-PH-K-S': dict(maker='JST', model='S4B-PH-K-S(LF)(SN)', family='PH 2.0 mm, side-entry header, 4 circuits', pins=4, rating='2 A, 100 V',
                       mates='PHR-4 + 4 x SPH-002T-P0.5S', body='PA natural, tin-plated posts', source='LCSC C157926; JST ePH.pdf p.3 (B 9.9)', note='expansion port, not fitted'),
    'PHR-3': dict(maker='JST', model='PHR-3', family='PH housing, 3 circuits', pins=3, rating='2 A', mates='S3B-PH-K-S',
                  body='PA natural (white), 7.8 x 4.5 x 6.85', source='JST ePH.pdf p.3', contacts='SPH-002T-P0.5S (AWG 32-24, insulation Ø0.5-1.5), crimp tool JST WC-240 or Engineer PA-09',
                  note='the roof lamps\' 0.2 mm enamelled wires are spliced to 26 AWG before the plug'),
    'SMR-02V-B': dict(maker='JST', model='SMR-02V-B', family='SM 2.5 mm wire-to-wire receptacle housing (pin contacts), 2 circuits', pins=2, rating='3 A, 250 V',
                      mates='SMP-02V-BC', body='PA 6 black UL94 V-0, 7.5 x 8.0 x 18.2', source='JST eSM.pdf p.3', contacts='SYM-001T-P0.6 pin contacts (AWG 28-22, insulation Ø1.2-1.8), crimp tool JST YC-160R or Engineer PA-09',
                      note='carries the pins: put it on the side that is dead when unplugged (the lamp, the stator leads)'),
    'SMP-02V-BC': dict(maker='JST', model='SMP-02V-BC', family='SM 2.5 mm wire-to-wire plug housing (socket contacts), 2 circuits', pins=2, rating='3 A, 250 V',
                       mates='SMR-02V-B', body='PA 6 black UL94 V-0, 7.4 x 5.5 x 11.7, latch arm on top', source='JST eSM.pdf p.3', contacts='SHF-001T-0.8BS socket contacts (AWG 28-22), same tool', note=''),
    'TYPE-C-31-M-12': dict(maker='Korean Hroparts', model='TYPE-C-31-M-12', family='USB-C receptacle, 16-pin, mid-mount', pins=16, rating='3 A',
                           mates='any USB-C cable (USB 2.0 pins used)', body='stainless shell 8.94 x 7.30, 3.26 high', source='LCSC C165948', note='service port through the slot in B102'),
    'KCD1-101': dict(maker='generic (Finglai KCD1 series drawing)', model='KCD1-101 (SPST ON-OFF, 2 pins)', family='rocker switch, 19 x 13 cut-out', pins=2, rating='6 A, 250 V AC (10 A 125 V AC)',
                     mates='2 x 4.8 mm faston or solder', body='bezel 21.2 x 15.1, 3.5 above the panel; body 18.7 x 12.2 x 13.2; terminals 4.8 x 0.6 at 7.1 pitch', source='finglai.com KCD1-19x13 drawing',
                     note='snaps into the 19 x 13 cut-out in the toolbox top; panel 1-3 mm'),
    'DC-022B': dict(maker='generic (metal 5.5 x 2.1 panel jack, M8)', model='DC-022B pattern (pcboard.ca jack-panel-5521)', family='DC barrel jack 5.5 x 2.1, panel mount', pins=3,
                    rating='about 2 A (charge current 1 A)', mates='5.5 x 2.1 barrel plug of the 12.6 V 3S charger', body='Ø8 M8 threaded barrel, nut and lock washer, 18.2 long, 3 solder lugs',
                    source='pcboard.ca jack-panel-5521 (8 mm hole, max panel 2.1 mm); Maplin DC-022B (8 mm cut-out, 18.2 x 10.2)', note='the toolbox front wall is 2.0 mm'),
    'MINI-FHM': dict(maker='Littelfuse', model='0FHM0001ZXJ (14 AWG GXL leads) + MINI fuse 5 A (0297005 pattern: 0997005 MINI)', family='in-line waterproof MINI blade fuse holder', pins=2,
                     rating='20 A, 32 V DC holder; 5 A fuse', mates='MINI blade fuse', body='two-part black thermoplastic with the sealed cover, IP67',
                     source='Littelfuse MINI FHM series datasheet 061622-A (lvelectronics mirror)', note='the body envelope in the CAD is taken from the photos: 36 x 15 x 16'),
    'Keystone-1043': dict(maker='Keystone Electronics', model='1043 (THM 18650 holder)', family='single 18650 battery holder, PC pins', pins=2, rating='3 A per contact',
                          mates='18650 cell (INR18650-35E)', body='heat-resistant nylon (Stanyl 46) cradle 77.05 x 20.65 x 14.86; tin-nickel plated phosphor-bronze spring and plate contacts; PC pins Ø1.57 x 3.30 at 71.64; 2 x Ø3.68 mounting holes at 55.00',
                          source='Keystone drawing 1043 rev C (TME KEYS1043.pdf)', note='snaps into the hatch sled; the pins carry the series links'),
    'HX-3S-01': dict(maker='generic', model='HX-3S-01 (3S 10 A protection board)', family='Li-ion BMS, 3S', pins=6, rating='10 A continuous, 12.6 V charge', mates='B-, B1, B2, B+ to the pack; P-, P+ to the XT30U-F lead',
                     body='50 x 16 x about 3.4 (seller data)', source='seller listings (skroutz, otronic): 50 x 16 x 2 board', note='taped to the hatch sled wall with 1 mm VHB'),
}

# ------------------------------------------------------------------ the joints (one row per place where two parts mate)
# 'fixed' is the side that stays with the machine part named in 'on'; 'free' is the harness side that is pushed in along
# 'mate_dir' by 'travel' mm at assembly step 'step' (build_viewer.py STEPS). 'pos' is the mating face / mouth plane (vehicle, mm).
_xh = lambda j, n, circuit, step, plug: dict(
    id=j, where='main board rev A, inboard edge (left bay)', circuit=circuit, fixed=f'S{n}B-XH-A', free=f'XHP-{n}', contacts=f'{n} x SXH-001T-P0.6',
    on='main board', pos=(H.BOARD[j]['x'], H.HEADER_FACE_Y, H.PLUG_Z['XH']), mate_dir=(0, 1, 0), travel=14.0, step=step, drawn_by='x1_body.main_board (board_plugs*)',
    wire=plug, qty=1)

JOINTS = [
    dict(id='J101', where='main board rev A, front edge (X -40)', circuit='12 V in: switch -> board', fixed='XT30PW-M', free='XT30U-F', contacts='solder cups',
         on='main board', pos=(-40.54, 133.5, 114.2), mate_dir=(-1, 0, 0), travel=16.0, step='plugs', drawn_by='build_connectors (board_link_XT30U-F*)',
         wire='2 x 20 AWG silicone (the 12 V link)', qty=1),
    _xh('J102', 4, 'tracks (slip ring rotor rings 1-4)', 'plugs', "the slip ring's own 6 leads (4 crimped, 2 taped)"),
    _xh('J103', 2, 'swing motor', 'plugs', '2 x 26 AWG silicone'),
    _xh('J104', 2, 'boom drive L', 'plugs', 'V6 cable: 2 x 28 AWG PTFE in the 3 mm sleeve'),
    _xh('J105', 2, 'boom drive R', 'plugs', 'V6 cable'),
    _xh('J106', 2, 'stick drive', 'plugs', 'V6 cable'),
    _xh('J107', 2, 'bucket drive', 'plugs', 'V6 cable'),
    dict(id='J108', where='main board rev A, inboard edge', circuit='lamps: +5 V, roof return, toolbox return', fixed='S3B-PH-K-S', free='PHR-3', contacts='3 x SPH-002T-P0.5S',
         on='main board', pos=(H.BOARD['J108']['x'], H.HEADER_FACE_Y, H.PLUG_Z['PH']), mate_dir=(0, 1, 0), travel=14.0, step='plugs', drawn_by='x1_body.main_board (board_plugs*)',
         wire='2 x 26 AWG silicone (toolbox lamp) + 26 AWG from the cab splice (roof lamps)', qty=1),
    dict(id='J109', where='main board rev A, inboard edge', circuit='expansion UART (not fitted)', fixed='S4B-PH-K-S', free='(PHR-4 when used)', contacts='4 x SPH-002T-P0.5S',
         on='main board', pos=(H.BOARD['J109']['x'], H.HEADER_FACE_Y, H.PLUG_Z['PH']), mate_dir=(0, 1, 0), travel=0.0, step=None, drawn_by='board STEP (header only)', wire='-', qty=0),
    dict(id='J201', where='main board rev A, outboard edge, through the B102 slot', circuit='USB service port', fixed='TYPE-C-31-M-12', free='USB-C cable', contacts='-',
         on='main board', pos=(-98.0, 148.5, 113.2), mate_dir=(0, -1, 0), travel=0.0, step=None, drawn_by='board STEP', wire='-', qty=1),
    dict(id='FEED', where='hood cavity under the hatch, right of the centreline', circuit='battery pack -> fuse (the hatch lead)', fixed='XT30U-M (on the feed from the fuse)', free='XT30U-F (on the hatch lead)',
         contacts='solder cups', on='right half (feed lead) / hatch (lead)', pos=H.FEED_SOCKET, mate_dir=(0, 0, -1), travel=18.0, step='hatch', drawn_by='x1_body.electronics (battery_lead_XT30*, feed_socket_XT30*)',
         wire='2 x 20 AWG silicone, 150 mm lead', qty=1),
    dict(id='SM-L', where='carbody, left of the slip ring', circuit='left track motor <- slip ring stator rings 1-2', fixed='SMR-02V-B (stator leads)', free='SMP-02V-BC (motor leads)',
         contacts='2 x SYM-001T-P0.6 + 2 x SHF-001T-0.8BS', on='X-frame carbody', pos=(0.0, 30.0, 52.0), mate_dir=(0, -1, 0), travel=14.0, step='slewing', drawn_by='build_connectors (SM-L*)',
         wire='2 x 26 AWG silicone', qty=1),
    dict(id='SM-R', where='carbody, right of the slip ring', circuit='right track motor <- rings 3-4', fixed='SMR-02V-B (stator leads)', free='SMP-02V-BC (motor leads)',
         contacts='2 x SYM-001T-P0.6 + 2 x SHF-001T-0.8BS', on='X-frame carbody', pos=(0.0, -30.0, 52.0), mate_dir=(0, 1, 0), travel=14.0, step='slewing', drawn_by='build_connectors (SM-R*)',
         wire='2 x 26 AWG silicone', qty=1),
    dict(id='SM-LAMP', where='right bay under the deck (X -12, Y -128), 10 mm outboard of the feed and the 12 V link', circuit='toolbox lamp: J108 pins 1, 3 -> LED in B103', fixed='SMR-02V-B (board side, cable from the left bay)', free='SMP-02V-BC (lamp side, right half)',
         contacts='2 x SYM-001T-P0.6 + 2 x SHF-001T-0.8BS', on='right bay (plugged with the right half held beside the machine)', pos=H.SM_LAMP, mate_dir=(-1, 0, 0), travel=14.0, step='right', drawn_by='build_connectors (SM-LAMP*)',
         wire='2 x 26 AWG silicone', qty=1),
    dict(id='SW', where='toolbox top (B103)', circuit='main switch in the 12 V feed', fixed='KCD1-101', free='2 x 20 AWG soldered to the 4.8 mm tabs', contacts='-',
         on='right half', pos=(34.5, -104.5, 164.78), mate_dir=(0, 0, -1), travel=20.0, step='right_parts', drawn_by='x1_body.electronics (main_switch*)', wire='20 AWG', qty=1),
    dict(id='JACK', where='toolbox front face (B103)', circuit='12.6 V charge input, to the battery side of the fuse', fixed='DC-022B', free='charger plug 5.5 x 2.1', contacts='3 solder lugs',
         on='right half', pos=(57.9, -141.0, 150.0), mate_dir=(1, 0, 0), travel=16.0, step='right_parts', drawn_by='x1_body.electronics (charge_jack*)', wire='2 x 22 AWG', qty=1),
    dict(id='FUSE', where='toolbox floor (B103), on VHB tape', circuit='5 A in the battery feed', fixed='MINI-FHM', free='MINI blade fuse 5 A', contacts='-',
         on='right half', pos=(28.0, -130.0, 137.0), mate_dir=(0, 0, -1), travel=20.0, step='right_parts', drawn_by='x1_body.electronics (fuse_holder_5A*)', wire='14 AWG leads, spliced to 20 AWG', qty=1),
]

# the battery pack on the hatch (not connectors, but the same catalogue carries them for the installation steps)
PACK = [
    dict(id='HOLDER', part='Keystone-1043', qty=3, where='under the hatch B106, between the sled walls at X -131 / -110 / -89', fit='press up between the sled walls against the two standoff ribs until the lips snap over the end walls; cell opening down',
         step='pack', drawn_by='x1_body.electronics (holder_1043_*)'),
    dict(id='CELL', part='Samsung INR18650-35E (Ø18.55 x 65.25 max)', qty=3, where='in the holders, the + end against the plate contact', fit='push the cell in from below (hatch turned over): - end onto the spring first, then press the + end past the lips',
         step='cells', drawn_by='x1_body.electronics (cell_18650_*)'),
    dict(id='BMS', part='HX-3S-01', qty=1, where='outer face of the +Y sled wall, X -135..-85, Z 197..213', fit='1 mm VHB tape; B- to holder 1 (-), B1 and B2 to the two series links, B+ to holder 3 (+); P-/P+ to the XT30U-F lead (150 mm)',
         step='pack', drawn_by='x1_body.electronics (battery_BMS_HX3S01*)'),
]

SYS_LABEL = 'Connectors and battery pack'


def type_rows():
    rows = []
    for key, t in TYPES.items():
        n_fixed = sum(j['qty'] for j in JOINTS if j['fixed'].split(' ')[0] == key)
        n_free = sum(j['qty'] for j in JOINTS if j['free'].split(' ')[0] == key)
        n_pack = sum(p['qty'] for p in PACK if p['part'] == key)
        rows.append(dict(key=key, qty=n_fixed + n_free + n_pack, **t))
    return rows


def rot_to(dir_from, dir_to):
    """Rotation (axis, degrees) turning unit vector dir_from onto dir_to (for stdparts.place)."""
    a, b = np.asarray(dir_from, float), np.asarray(dir_to, float)
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    c = np.cross(a, b)
    if np.linalg.norm(c) < 1e-9:
        if np.dot(a, b) > 0:
            return ((0, 0, 1), 0.0)
        # opposite: turn 180 about any perpendicular axis
        perp = np.cross(a, [0, 0, 1]) if abs(a[2]) < .9 else np.cross(a, [1, 0, 0])
        return (tuple(perp / np.linalg.norm(perp)), 180.0)
    ang = math.degrees(math.atan2(np.linalg.norm(c), np.dot(a, b)))
    return (tuple(c / np.linalg.norm(c)), ang)
