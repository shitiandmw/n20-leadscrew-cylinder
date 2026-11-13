#!/usr/bin/env python3
"""Print kit for two J9 tracks (revision F): what to print, what to buy, and an offline installation animation.

Writes, from the current revision-F exports (no quantity or size is typed in twice):
  ../TRACK_KIT.md            what to print and what to buy for two tracks, tools, print notes
  ../track_kit.csv           the same rows in one table
  ../install_animation.html  offline step-by-step installation animation (three.js, one file)
  ../track_kit_report.json   what was measured and cross-checked: STL sizes, volumes and hashes, bed fits, and the
                             animation scene's part counts against the list
With --package it also writes ../../../output/track_print_kit/ and ../../../output/track_print_kit.zip: the STL files
renamed with their quantities, the list, the animation and the parts showcase (../parts_showcase.html, written by
build_parts_showcase.py from this script's lists: build it after this script, then run this one with --package).

Inputs: j9_scene.json.gz (the left track module and one chain link, as in 3D_preview.html), ../../X1/source/x1_scene.json.gz
(X101 and the track-joint screws, washers and nuts), the STL files and ../../X1/revf_part_exports.json.
Standard library only:  python3 track_wheel_jgy370/J9/source/build_track_kit.py [--package]
"""
import array
import base64
import csv
import gzip
import hashlib
import io
import json
import math
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # track_wheel_jgy370/J9
REPO = ROOT.parents[1]
X1 = REPO / 'track_wheel_jgy370/X1'
J9S, X1S = 'track_wheel_jgy370/J9/stl/', 'track_wheel_jgy370/X1/stl/'
PETG = 1.27                             # g/cm3, for the solid-volume upper bound only
BEDS = [(220, 220), (250, 210), (256, 256), (300, 300)]

# --------------------------------------------------------------------------------------------- the kit
# Printed parts. Settings and orientations are J9/BOM.md's (X1/BOM.md for the mirrored prints); quantities are per track.
PRINTED = [
    dict(id='J901', name='J901 H-frame', per_track=1, est=(4, .4, True), files={'left': J9S + 'J901_H_frame.stl', 'right': X1S + 'J901_H_frame_right.stl'},
         settings='PETG or PA12. No structural recipe is validated: choose walls, infill and layer direction for your load.',
         orientation='Outer wall face on the bed (as exported); supports under the inner wall.',
         note='Left and right are mirror images: print one of each file. Clean the Ø16.4 spring bore, the yoke grooves and the X1 seats.'),
    dict(id='J909', name='J909 housing with motor pod', per_track=1, est=(3, .15, True),
         files={'left': J9S + 'J909_housing.stl', 'right': X1S + 'J909_housing_right.stl'},
         settings='PETG, 3 walls.', orientation='Skirt inner face on the bed (as exported); supports inside the motor pod only.',
         note='Mirror pair: print one of each file.'),
    dict(id='J902', name='J902 sprocket', per_track=1, est=(5, .5, False), files={'both': J9S + 'J902_sprocket.stl'},
         settings='PETG or PA12, 5 walls, 50 % infill.', orientation='Outer disc face on the bed; no supports.',
         note='Same print on both sides. Ø32.4 recess for the coupling flange.'),
    dict(id='J903', name='J903 journal plug', per_track=1, est=(0, 1, False), files={'both': J9S + 'J903_journal_plug.stl'},
         settings='PETG or PA12, 100 % infill.', orientation='Standing on its end.', note='Ø9.95 journal in the 6800ZZ inner ring.'),
    dict(id='J904', name='J904 roller', per_track=7, est=(4, .4, False), files={'both': J9S + 'J904_roller.stl'},
         settings='PETG, 4 walls, 40 % infill.', orientation='On a flange face.', note='5 road and 2 support rollers per track.'),
    dict(id='J906', name='J906 idler wheel', per_track=1, est=(4, .4, True), files={'both': J9S + 'J906_idler_wheel.stl'},
         settings='PETG. The design gives no recipe; the roller settings (4 walls, 40 %) are a reasonable start.',
         orientation='Flat face on the bed (as exported).',
         note='Two 608ZZ seats, open to the faces: each bearing slides in by hand, then presses the last 7.5 mm against the central web. '
              'The web\'s underside prints as a bridge: trim any sag before fitting the bearing on the bed side.'),
    dict(id='J907', name='J907 idler spacer', per_track=2, est=(0, 1, False), files={'both': J9S + 'J907_idler_spacer.stl'},
         settings='PETG, 100 % infill.', orientation='Standing on its end.', note='Touches only the 608 inner ring.'),
    dict(id='J908', name='J908 U-yoke with spring piston', per_track=1, est=(4, .5, False), files={'both': J9S + 'J908_U_yoke.stl'},
         settings='PETG or PA12, 4 walls, 50 % infill.', orientation='Upside down on its flat top (as exported); support the rear piston as needed.',
         note='Ø15.6 piston slides in the frame\'s Ø16.4 bore.'),
    dict(id='J910', name='J910 track shoe, 70 mm', per_track=34, est=(4, .4, True), files={'both': J9S + 'J910_track_shoe_70.stl'},
         settings='PETG or PA12.', orientation='Grousers on the bed (as exported).', note='34 links per track.'),
]
OPTIONAL_PRINTED = [
    dict(id='X101', name='X101 X-frame (only to test the chassis mounting)', per_machine=1, files={'chassis': X1S + 'X101_X_frame.stl'},
         settings='PETG or PA12; qualify walls and infill for the load.', orientation='Bearing seat on the bed (as exported); support under the arm decks and head slots.',
         note='Revision F. Needs a bed of at least 300 x 300 mm.'),
]
# Bought parts, per track (J9/BOM.md, 52 pieces). 'step' is where the animation fits them.
STANDARD = [
    dict(id='motor', cat='Drive and bearings', name='JGY-370-1260 worm gear motor, 12 V, 200:1 (30 rpm)', per_track=1,
         spec='Motor only: no L-bracket, no speed controller. Vendor table: 30 rpm no load, 6 kgf·cm rated at 0.2 A, 20 kgf·cm stall at 1.3 A.',
         buy_md='Shop options "12V 电机" (motor only) and "每分钟/30转 6KG.CM" (vendor row JGY-370-1260, 200:1).'),
    dict(id='hub', cat='Drive and bearings', name='Ø32 / Ø6 aluminium flange coupling (flange Ø32 x 4, 6 x M3 tapped on Ø23, boss Ø14 x 10)', per_track=1,
         spec='Bore D = 6 mm. Seller drawing: track_wheel_jgy370/references/flange_coupling_32. Comes with one M3 set screw.'),
    dict(id='setscrew', cat='Drive and bearings', name='M3 set screw, supplied with the coupling', per_track=1,
         spec='Bears on the motor shaft\'s D-flat. The CAD assumes M3 x 4; up to 4.5 mm long stays below the boss surface.', buy='supplied'),
    dict(id='6800ZZ', cat='Drive and bearings', name='6800ZZ ball bearing, 10 x 19 x 5', per_track=1, spec='Outer support of the sprocket (journal plug).'),
    dict(id='624ZZ', cat='Drive and bearings', name='624ZZ ball bearing, 4 x 13 x 5', per_track=14, spec='Two per roller.'),
    dict(id='608ZZ', cat='Drive and bearings', name='608ZZ ball bearing, 8 x 22 x 7', per_track=2, spec='Idler.'),
    dict(id='pin8', cat='Drive and bearings', name='Steel pin Ø8 x 55 (ISO 2338 8 m6 x 55, or Ø8 shaft cut to 55)', per_track=1,
         spec='Idler axle, carried by the yoke arms.'),
    dict(id='spring', cat='Drive and bearings', name='Compression spring Lee Spring C-600-072-1500 (music wire)', per_track=1,
         spec='OD 15.24, wire 1.83, free length 38.1, about 6.3 N/mm, solid 17.0 mm: 77 N at the 25.8 mm fitted length. '
              'A substitute must slide in the Ø16.4 bore and over the Ø11 pilot.'),
    dict(id='M4x70', cat='Screws, nuts and inserts', name='M4 x 70 socket head screw (ISO 4762)', per_track=7, spec='Roller axles, from the inboard side.'),
    dict(id='nyloc', cat='Screws, nuts and inserts', name='M4 nyloc nut (DIN 985)', per_track=7, spec='Roller axles, outboard. Snug only.'),
    dict(id='M3x6', cat='Screws, nuts and inserts', name='M3 x 6 socket head screw (ISO 4762)', per_track=4, spec='Motor to the inner wall, from inside the H.'),
    dict(id='M3x20', cat='Screws, nuts and inserts', name='M3 x 20 socket head screw (ISO 4762)', per_track=3,
         spec='Sprocket to the coupling: 4 mm of thread in its flange.'),
    dict(id='M3x50', cat='Screws, nuts and inserts', name='M3 x 50 socket head screw (ISO 4762)', per_track=1,
         spec='Journal plug and sprocket onto the shaft\'s tapped end.'),
    dict(id='M3x8', cat='Screws, nuts and inserts', name='M3 x 8 button head screw (ISO 7380)', per_track=4, spec='Housing to the standoff inserts.'),
    dict(id='insert', cat='Screws, nuts and inserts', name='M3 heat-set insert for a Ø4.0 x 5.7 mm hole', per_track=4, spec='Tops of the four housing standoffs.'),
]
CHAIN = [
    dict(id='trackpin', cat='Track chain', name='Track pin Ø3 x 56, silver steel', per_track=34,
         spec='Yield at least 400 MPa. An E-clip groove 1.5 mm from each end (centred 26.5 mm each side of the middle), sized for DIN 6799 '
              'size 2.3 clips. Not an off-the-shelf part: cut and groove Ø3 silver steel, or order cut-and-grooved Ø3 shafts.'),
    dict(id='bushing', cat='Track chain', name='Track bushing, steel, Ø6 OD x Ø3.1 ID x 17', per_track=34,
         spec='The sprocket drives these. Cut from tube and deburr both ends; must slip freely on the pin.'),
    dict(id='clip', cat='Track chain', name='E-clip DIN 6799 size 2.3 (for Ø3-4 mm shafts)', per_track=68,
         spec='Two per pin (modelled as Ø6 x 0.6). Buy spares: they jump.'),
]
JOINT = [   # X1/BOM.md, revision F track joints: per machine (both tracks)
    dict(id='M4x25', cat='X1 joint', name='M4 x 25 socket head screw (ISO 4762), Ø7 x 4 head', per_machine=8, spec='Two per arm end, one in each side slot.'),
    dict(id='washer4', cat='X1 joint', name='M4 washer, Ø9 / Ø4.4 x 0.8', per_machine=16, spec='Under every screw head and every nut.'),
    dict(id='nut4', cat='X1 joint', name='M4 hex nut (ISO 4032), 7 mm AF x 3.2', per_machine=8, spec='Outside the main plate, inside the track.'),
]
BENCH = [   # not in the CAD: for the first powered test on the bench
    dict(name='26 AWG silicone wire, red and black', qty='about 0.5 m per motor', spec='Through the Ø5.5 port in the pod nose; wires only, no plug.'),
    dict(name='100 nF 50 V ceramic capacitor', qty='1 per motor', spec='Across the motor terminals (brush noise), as on the X1 machine.'),
    dict(name='12 V supply with an adjustable current limit', qty='1', spec='Set about 1.0 A: the idler only just holds the full 1.3 A stall pull in reverse.'),
    dict(name='Reversing switch (DPDT) or a DC motor H-bridge', qty='1', spec='Both directions are needed.'),
]
TOOLS = [
    ('Hex keys 1.5, 2, 2.5 and 3 mm', 'the coupling set screw, M3 button heads, M3 socket heads, M4 socket heads'),
    ('7 mm spanner or socket', 'M4 nyloc nuts'),
    ('Soldering iron with an M3 heat-set insert tip', 'inserts and motor leads'),
    ('Vise with soft jaws or a small arbor press; for the idler, a tube or socket about Ø20-21 mm across and at least 20 mm long '
     'as a drift on the 608ZZ outer ring (not the shield)', 'bearings into the printed seats'),
    ('Calipers', 'motor screw-hole depth, prints'),
    ('E-clip pliers or a small flat screwdriver', 'chain clips'),
    ('Paint marker', 'hub set-screw witness marks'),
    ('Dummy pin Ø3 x 24: an offcut of the Ø3 pin rod (or any Ø2.5-3 rod), ends deburred', 'holds the last chain bushing until the last pin pushes it out'),
    ('X1 only: 3 mm L-key with a 20 mm short leg and 80 mm arm; compact 7 mm nut holder within Ø11.2 mm', 'track joints'),
]

# --------------------------------------------------------------------------------------------- the installation steps
# Instructions condense J9/ASSEMBLY.md and X1/ASSEMBLY.md (the order is X1's, which also works on the bench).
# cams: [t, camera position, target] in left-track mm (+X front, +Y outboard, +Z up); camsX1 in vehicle mm.
X1_WIDE = [[0, [-480, 650, 520], [0, 40, 40]]]
STEPS = [
    dict(id='overview', title='The finished track', dur=5,
         caption='One J9 track: printed H-frame, JGY-370 motor in a closed pod, sprocket on a Ø32 flange coupling, 5 road and 2 support rollers, '
                 'sprung idler and a 34-link steel-pinned chain. Build two; the right one uses the mirrored J901 and J909 prints.',
         do=['Print and buy everything in the Parts list tab; its quantities are for two tracks.',
             'Use the revision F J901 and J909 files: the left ones from J9/stl, the mirrored right ones from X1/stl.',
             'Play the steps in order. Both tracks are built the same way; "Both on X101" adds the chassis step.'],
         check=['Nothing has been printed or assembled yet. Fits, strength and powered running are untested: the checks in each step are the ones to make on the real parts.'],
         tools=[], source='J9/README.md, X1/REV_F_NOTES.md',
         cams=[[0, [-250, 470, 250], [0, 0, 40]]], camsX1=[[0, [-520, 680, 500], [0, 0, 50]]]),
    dict(id='frame', title='Prepare the H-frame', dur=7,
         caption='Four M3 heat-set inserts into the housing standoffs on the inboard side; the 6800ZZ pressed into the outer wall.',
         do=['Remove the support under the inner wall. Clean the Ø16.4 spring-guide bore, the two yoke grooves, the roller-bolt holes and the shallow X1 seats.',
             'Press the four M3 heat-set inserts into the tops of the four housing standoffs on the inner wall.',
             'Press the 6800ZZ into the outer-wall seat from outside until it sits on the 1 mm lip; its face ends flush with the wall.'],
         check=['The bearing seats are press fits in a print. If the 6800ZZ is loose, or needs force that bends the wall, correct the printer\'s hole '
                'compensation before printing the second frame.'],
         tools=['soldering iron with an M3 insert tip', 'vise with soft jaws'], source='J9/ASSEMBLY.md 1',
         cams=[[0, [-200, -430, 300], [-10, -20, 45]], [0.55, [-330, 430, 230], [-70, 10, 45]]], camsX1=X1_WIDE),
    dict(id='motor', title='Motor', dur=7,
         caption='The JGY-370 seats in the recess on the inboard face of the inner plate; four M3 x 6 go in from inside the H.',
         do=['Run the motor briefly on 12 V before fitting it. Measure the depth of the gearbox screw holes: the M3 x 6 assume 3 mm of thread.',
             'Seat the motor in the recess on the inboard face of the inner main plate: its four screw bosses and Ø13.2 centre boss enter the '
             'counterbores and the shaft passes through the wall. Right track: turn the motor 180° about its can axis so the shaft and holes line up.',
             'Working inside the open H from the rear, drive the four M3 x 6 into the gearbox with a 2.5 mm L-key. They cannot be reached once the sprocket is in.'],
         check=['The gearbox face sits flat in the recess with no rocking.'],
         tools=['2.5 mm L-key', 'calipers'], source='J9/ASSEMBLY.md 2',
         cams=[[0, [-320, -380, 240], [-85, -35, 45]], [0.5, [-260, 210, 330], [-95, -22, 44]]], camsX1=X1_WIDE),
    dict(id='rollers', title='Road and support rollers', dur=10,
         caption='Two 624ZZ in each of the seven rollers. Road rollers go in from below, support rollers from above; M4 x 70 from the inboard side, nyloc nut outboard.',
         do=['Press two 624ZZ into each roller, flush with the roller faces.',
             'Put each roller between the walls: the five road rollers from below, the two support rollers from above.',
             'Push an M4 x 70 in from the inboard side, head in its recess, through the inner wall, both bearings and the outer wall.',
             'Fit an M4 nyloc nut outboard and turn it only until snug.'],
         check=['The rollers float about 0.3 mm between small wall bosses that touch only the bearing inner rings. Do not clamp the walls together: '
                'every roller must still spin freely.'],
         tools=['3 mm hex key', '7 mm spanner', 'vise with soft jaws'], source='J9/ASSEMBLY.md 1.3 and 3',
         cams=[[0, [150, 660, 130], [0, 0, 40]], [0.56, [150, -670, 230], [0, -20, 45]], [0.8, [150, 660, 170], [0, 0, 45]]], camsX1=X1_WIDE),
    dict(id='tensioner', title='Tensioner: spring, yoke and idler', dur=12,
         caption='The idler, on two 608ZZ, sits between the yoke arms on the Ø8 x 55 pin. The spring goes into the guide bore from the front, then the yoke slides into the wall grooves '
                 '(the frame\'s outboard half is cut away here to show the spring).',
         do=['Dry-fit first: the J908 yoke\'s Ø15.6 piston must slide freely in the Ø16.4 guide bore of the main web over the full 4.2 mm stroke.',
             'Fit a 608ZZ from each face of the idler. It slides in by hand through the Ø22.6 bore; press the last 7.5 mm with a Ø20-21 mm '
             'tube or socket on the outer ring (not on the shield) until it stops against the central web. The web\'s underside prints as a bridge: '
             'trim any sag before fitting the bearing on the bed side.',
             'Put the idler between the yoke arms with a J907 spacer on each side and push the Ø8 x 55 pin through arm, spacer, bearings, spacer and arm. '
             'Its ends stand 0.5 mm proud of the arms.',
             'Insert the spring into the guide bore from the front, onto the pilot at the recessed floor.',
             'Slide the yoke arms into the wall grooves from the front, with the pin ends in the deeper tracks of the groove floors, until the spring sits on the '
             'yoke pilot and the piston enters the bore.'],
         check=['Both 608ZZ stop against the central web: their outer faces sit 13 mm below the idler faces, and the idler turns freely.',
                'Without the chain the spring pushes the yoke about 12 mm ahead of its running position; the arms stay in the grooves.'],
         tools=['vise with soft jaws', 'Ø20-21 mm tube or socket as a bearing drift'], source='J9/ASSEMBLY.md 1.4 and 6',
         cams=[[0, [450, 540, 330], [150, 0, 45]], [0.5, [300, 520, 230], [70, 0, 45]]], camsX1=X1_WIDE),
    dict(id='housing', title='Housing over the motor', dur=7,
         caption='Motor leads through the Ø5.5 port in the pod nose and soldered on; the housing slides on toward the inner wall and takes four M3 x 8 button heads.',
         do=['Thread the two motor leads through the cable port in the pod\'s nose from the outside in. The port is Ø5.5: wires only, no plug.',
             'Solder the leads to the motor terminals, with a 100 nF ceramic capacitor across them.',
             'Slide the housing toward the inner wall and over the motor, pulling the slack out through the port. The pod\'s open side meets the rim on the inner wall.',
             'Fasten it with four M3 x 8 button heads into the inserts.'],
         check=['The Ø8 holes in the skirt line up with the roller-bolt heads, so the rollers can be serviced with the housing on (track off the chassis).'],
         tools=['soldering iron', '2 mm hex key'], source='J9/ASSEMBLY.md 8',
         cams=[[0, [-170, -480, 200], [-40, -40, 45]]], camsX1=X1_WIDE),
    dict(id='xframe', title='Mount both tracks on X101', x1only=True, dur=14,
         caption='Both tracks upright on 340 mm centres. The bare X101 goes 80 mm straight down into the four seats; two M4 x 25 per joint, washers and nuts outside the plate.',
         do=['Leave both rear sprockets, hubs, journal plugs and chains off until the joints are tight: the nuts are reached from inside the track.',
             'Support both tracks upright and parallel on 340 mm centres, final drives at the rear. Hold X101 80 mm above its place, align the four arm ends '
             'over the open-top seats and lower it straight down. Never push a track sideways into X101: that route hits the motor and housing.',
             'Each joint takes two M4 x 25 with a washer under the head. Lower each screw beside the arm, slide it sideways into its slot, tip toward the track, '
             'and push it through the plain hole.',
             'Inside the track, a washer and an M4 nut on each screw. Hold the nut with the 7 mm tool and turn the screw with the 3 mm L-key, handle out of the slot. '
             'Tighten each pair gradually so the faces stay seated.',
             'Run each motor\'s leads forward under the arms to the front arm, then into the carbody\'s Ø10 side hole.'],
         check=['No torque is qualified for these printed joints: do not crush the plate or the arm end, and never straighten a warped print with screw force. '
                'Every washer must lie flat.'],
         tools=['3 mm L-key, 20 mm short leg, 80 mm arm', 'compact 7 mm nut holder within Ø11.2 mm'], source='X1/ASSEMBLY.md 3',
         cams=[[0, [-260, 260, 160], [-110, 0, 45]]],
         camsX1=[[0, [560, -620, 480], [0, 0, 60]], [0.42, [280, 40, 140], [62, 130, 64]], [0.8, [250, 300, 260], [60, 150, 62]]]),
    dict(id='sprocket', title='Sprocket and coupling', dur=12,
         caption='The flange coupling bolts into the sprocket on the bench. The pair goes in between the walls from the rear, 9.6 mm outboard, then slides onto the D-shaft.',
         do=['On the bench, put the coupling\'s flange into the Ø32.4 recess in the sprocket\'s inner face, boss pointing away from the sprocket (toward the motor); '
             'the sprocket\'s centre pad goes into the coupling bore. Line up every other coupling hole with the three counterbores and fit three M3 x 20 from the '
             'sprocket\'s outer face; the heads end flush.',
             'Start the coupling\'s set screw but keep it backed out of the bore.',
             'The set screw must end up on top, where the key reaches it. A worm gearbox usually cannot be turned by hand, so jog the motor to bring the '
             'shaft\'s D-flat to the top.',
             'Bring the sprocket in between the walls from the rear, about 10 mm outboard of its place so the coupling clears the shaft tip. Slide it inboard onto the '
             'shaft until its centre pad meets the shaft end; the coupling boss stops 1 mm short of the wall.',
             'With a 1.5 mm key straight down between the walls, 6 mm from the wall face, tighten the set screw firmly on the flat and mark it with a paint line.'],
         check=['The coupling has one set screw and no torque rating on a D-flat. Recheck it after the first runs and after any stall.'],
         tools=['2.5 mm and 1.5 mm hex keys', 'paint marker'], source='J9/ASSEMBLY.md 1.5 and 4',
         cams=[[0, [-450, 280, 180], [-210, 10, 45]], [0.6, [-300, 230, 230], [-110, 0, 45]]],
         camsX1=[[0, [-600, 560, 420], [-120, 60, 50]]]),
    dict(id='plug', title='Journal plug', dur=6,
         caption='J903 goes in from outside through the 6800ZZ into the sprocket\'s socket; one M3 x 50 clamps plug and sprocket to the shaft end.',
         do=['From outside, push the J903 plug through the 6800ZZ into the socket in the sprocket\'s outer face.',
             'Fit the M3 x 50 through the plug and the sprocket into the tapped end of the motor shaft (about 5.6 mm of thread).',
             'Tighten moderately: it clamps printed parts.'],
         check=['The sprocket turns with the shaft without touching the walls or the web.'],
         tools=['2.5 mm hex key'], source='J9/ASSEMBLY.md 5',
         cams=[[0, [-330, 330, 150], [-110, 15, 45]]], camsX1=[[0, [-420, 520, 260], [-110, 170, 45]]]),
    dict(id='chain', title='Track chain', dur=48,
         caption='The chain goes on in one piece, like a real track. On the bench each joint is made in turn: next link pushed on along the strip, '
                 'bushing dropped in between the inner ears, pin through, E-clips on from the side. A dummy pin holds the last bushing while the strip is '
                 'wrapped round the sprocket and, with the idler held back at its stop, round the idler. On top the last pin pushes the dummy out; '
                 'then the spring takes up the slack.',
         do=['On the bench, join the 34 links into one straight strip, grousers down. For each joint: lay the next link down just ahead of the strip and '
             'push it back until its outer plates straddle the inner ears of the last link (the rounded plate ends slide into the hollowed ones, so it only '
             'goes on along the strip). Drop a bushing in between those inner ears from above: at Ø6 it cannot pass the Ø3.2 pin holes, so it always goes '
             'in before its pin. Push a Ø3 x 56 pin through plate, ear, bushing, ear and plate, and push an E-clip onto each groove from the side, open '
             'side first. Every joint must articulate freely.',
             'At the far end of the strip, drop the last bushing between the free inner ears and push the Ø3 x 24 dummy pin through ears and bushing '
             'until it sits inside both ears. On the top run those ears open downward, out of reach, and the dummy keeps the bushing in. This joint '
             'stays open.',
             'Lift the track, lay the strip under it and set the track down on the middle of the strip: the road rollers sit on it and the sprocket '
             'teeth drop between the bushings. The open ends stick out behind the sprocket and ahead of the idler.',
             'Wrap the rear end up round the sprocket, a bushing in every tooth gap, and lay it forward over the support rollers.',
             'Push the idler back to its recoil stop (4.2 mm behind its running position, where the yoke arms meet the groove ends) and hold it there: '
             'the spring pushes back with about 104 N, so a helper makes this easier. Wrap the front end up round the idler and back over the top, '
             'held up in a low arch so it lands a few millimetres short of the rear end.',
             'Press the arch down: the front end slides along the run until its inner ears (bushing and dummy pin inside) are between the rear end\'s '
             'outer plates. The ends meet on top between the two support rollers, where both pin ends are clear of the frame, the housing and X101.',
             'Push the last pin in from outboard. It pushes the dummy pin out on the inboard side: catch it. Push the two E-clips on from the side.',
             'Release the idler: the spring pushes it forward until the chain is tight, at its 25.8 mm fitted length and about 77 N.'],
         check=['The chain is a fixed loop of 34 x 20 mm. If the ends will not meet with the idler at its stop, look for a stiff link or a binding yoke; '
                'do not force the pin.',
                'Before closing the last joint, the dummy pin must sit inside both inner ears (24 mm in a 27.4 mm span): if it stands out, push it back, '
                'or the outer plates will not pass over the ears.',
                'Released, the idler must come forward on its own and the chain must lie on every wheel. Press the idler back by hand: it must '
                'recoil and return freely.'],
         tools=['E-clip pliers or a small flat screwdriver', 'Ø3 x 24 dummy pin'], source='J9/ASSEMBLY.md 7; spring forces from J9/README.md',
         cams=[], camsX1=[]),                   # set in main() from where the strip lies (chain_cams)
    dict(id='test', title='First run', dur=8, run=True,
         caption='One slow circuit first, then both directions with the track lifted and the current limited to about 1 A.',
         do=['Run one complete circuit slowly, on a few volts with the current limited (a worm gearbox normally cannot be turned by hand). No wheel may rub, the bushings must '
             'enter and leave the sprocket cleanly, and the idler must recoil and return.',
             'With the track lifted, run it at 12 V with the current limited to about 1.0 A, slowly in both directions.',
             'Feel the motor pod during the first runs (the pod is closed), and recheck the coupling set screw.'],
         check=['At a full 1.3 A stall in reverse the motor pulls about 50.8 N against the 51.9 N the idler holds at its stop. Keep the 1.0 A limit (about 38 N) '
                'and do not hold a stall.'],
         tools=['current-limited 12 V supply', 'reversing switch or H-bridge'], source='J9/README.md, open items 1, 6 and 7',
         cams=[[0, [-220, 470, 200], [0, 0, 40]]], camsX1=[[0, [-480, 650, 420], [0, 0, 40]]]),
]
SID = {s['id']: i for i, s in enumerate(STEPS)}
SLIDE_BENCH_X = 95                      # the idler sub-assembly is built this far ahead of the frame
SPROCKET_BENCH = (-165, 9.6, 0)         # the sprocket sub-assembly, before its radial entry (build_j9.py route: 9.6 outboard)
YOKE_REST = 12                          # the spring pushes the yoke this far forward until the chain is on
RECOIL = 4.2                            # the idler's travel behind its running position to the hard stop (J9/README.md)
# The chain goes on as a real track does (J9/ASSEMBLY.md 7). The links are joined into one flat strip with one joint left open, on
# the bench under the lifted track; the track is set down on the middle of the strip; the rear end is wrapped round the sprocket
# and then, with the idler held back at its recoil stop, the front end round the idler; the last pin goes in from outboard where
# the two ends meet on top; the idler is released. Times are fractions of the chain step.
CHAIN_T = dict(lift=(0, .03), strip=(.035, .395), lower=(.4, .44), rear=(.45, .57), push=(.58, .62), front=(.63, .73),
               close=(.735, .76), join=(.77, .9), release=(.92, .97))
CHAIN_LIFT = 40                         # mm the track is lifted while the strip is laid under it
# One joint of the strip, as a person makes it. The next link is put down LINK_AHEAD mm ahead of the strip's end (from LINK_UP mm
# up) and pushed back along the strip until its outer plates straddle the last link's inner ears: its rounded plate ends nest in
# the hollowed ends of the last link's plates (R4 in R4.3), so it can only come in along the strip. A bushing drops in between
# those ears from BUSH_UP mm above: at Ø6 it cannot pass the Ø3.2 pin holes. The pin is pushed through from PIN_OUT mm outboard
# (its tip starts in the outer plate's hole). An E-clip is pushed onto each groove from CLIP_OFF mm away, square to the pin, open
# side first. The first joint goes slowly (close-up); the other 32 follow quickly, one starting every JOINT_GAP of the step.
LINK_AHEAD, LINK_UP, BUSH_UP, PIN_OUT, CLIP_OFF = 10, 30, 20, 45, 10
FIRST_LINK = (.035, .05)
FIRST_JOINT = dict(link=(.05, .075, .1), bush=(.1, .125), pin=(.125, .155), clips=(.155, .18))
FAST_START, JOINT_GAP = .185, .0049
FAST_JOINT = dict(link=(0, .5, 1), bush=(1, 1.8), pin=(1.8, 2.8), clips=(2.8, 3.6))   # in JOINT_GAPs; a link comes down when the last is in
# The far end's free inner ears take the last bushing on the bench. On the top run those ears open downward and nothing can reach
# under them (the frame deck is 7 mm below), so a Ø3 x 24 dummy pin, pushed in from DUMMY_OUT mm outboard until it sits inside both
# ears, holds the bushing through the wrapping; the outer plates still pass over the ears. On top the last pin pushes it out inboard.
DUMMY_OUT = 30
LAST_BUSH = dict(bush=(.36, .375), dummy=(.375, .395))
# The ends meet on top. A hollowed plate end can only take a rounded one along the run (as on the bench), and the chain is slack
# while the idler is held back, so the front end comes over held up in a low arch (formed while it goes round the idler, before it
# comes down): ARCH_DEG up from the last idler joint, the same down from ARCH_PEAK. It lands short of the rear end and is pressed
# flat ('close'), sliding along the run onto it.
ARCH_DEG, ARCH_PEAK = 15.0, 3           # ARCH_PEAK: links from the end of the idler wrap to the arch's peak joint
JOIN = dict(pin=(.77, .83), dummy_gone=.845, clips=(.85, .9))
CLIP_FROM_FRONT = math.pi               # the last joint's clips come in from the front along the run: open side toward -X


def K(*keys):
    """[t, dx, dy, dz] keyframes."""
    out = [[round(min(1.0, t), 4), *[round(float(v), 3) for v in d]] for t, d in keys]
    assert all(a[0] <= b[0] for a, b in zip(out, out[1:])), out
    return out


def add(v, w):
    return [a + b for a, b in zip(v, w)]


def bounds(p):
    vs = p['vertices']
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    return lo, hi


def anchor(p, how):
    lo, hi = bounds(p)
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    ax = dict(x=0, y=1, z=2)
    if how != 'c':
        i = ax[how[0]]
        c[i] = lo[i] if how.endswith('min') else hi[i]
    return [round(v, 2) for v in c]


ROLLERS = ['road0', 'road1', 'road2', 'road3', 'road4', 'support0', 'support1']
SLIDE = re.compile(r'^(J906_idler_wheel|608ZZ_\d_\w+|J907_idler_spacer_\d|J908_U_yoke|idler_pin_8x55)$')


def module_anim(name):
    """[{s: step index, keys}] for one track-module part, in track-local mm. Fitting directions follow the routes that
    build_j9.py checks: sprocket radially from the rear 9.6 mm outboard, then onto the shaft; plug from outside; yoke from the
    front; housing along +Y; motor screws from inside the H."""
    def e(step, keys):
        return dict(s=SID[step], keys=keys)
    if name == 'J901_H_frame':
        return [e('frame', K((0, (0, 0, 0))))]
    m = re.match(r'insert_M3_(\d)$', name)
    if m:
        t = .12 + .07 * int(m[1])
        return [e('frame', K((t, (0, -30, 0)), (t + .2, (0, 0, 0))))]
    if name.startswith('6800ZZ_'):
        return [e('frame', K((.6, (0, 35, 0)), (.9, (0, 0, 0))))]
    if name.startswith('JGY370_'):
        return [e('motor', K((0, (0, -80, 0)), (.45, (0, 0, 0))))]
    m = re.match(r'motor_screw_M3x6_(\d)$', name)
    if m:
        t = .52 + .08 * int(m[1])
        return [e('motor', K((t, (0, 28, 0)), (t + .18, (0, 0, 0))))]
    m = re.match(r'(?:J904_roller_|624ZZ_|bolt_M4x70_|nyloc_M4_)(road\d|support\d)(?:_(\d)_\w+)?$', name)
    if m:
        g, j = m[1], ROLLERS.index(m[1])
        bench = (0, 0, -50) if g.startswith('road') else (0, 0, 50)
        t_in = (.28 + .025 * j) if g.startswith('road') else (.36 + .03 * (j - 5))
        settle = [(t_in, bench), (t_in + .22, (0, 0, 0))]
        if name.startswith('J904'):
            return [e('rollers', K((0, bench), *settle))]
        if name.startswith('624ZZ'):
            side = -1 if m[2] == '0' else 1             # bearing 0 is the inboard one
            return [e('rollers', K((.02, add(bench, (0, 30 * side, 0))), (.2, bench), *settle))]
        if name.startswith('bolt'):
            t = .62 + .025 * j
            return [e('rollers', K((t, (0, -90, 0)), (t + .16, (0, 0, 0))))]
        t = .83 + .02 * j
        return [e('rollers', K((t, (0, 30, 0)), (t + .07, (0, 0, 0))))]
    if SLIDE.match(name):
        b = (SLIDE_BENCH_X, 0, 0)
        if name == 'J906_idler_wheel':
            first = [(0, b)]
        elif name.startswith('608ZZ_'):
            side = -1 if name.startswith('608ZZ_0') else 1
            first = [(.02, add(b, (0, 30 * side, 0))), (.16, b)]
        elif name == 'J908_U_yoke':
            first = [(.18, add(b, (0, 0, 45))), (.32, b)]
        elif name.startswith('J907'):
            side = -1 if name.endswith('_0') else 1
            first = [(.33, add(b, (0, 28 * side, 0))), (.43, b)]
        else:                                              # idler pin, pushed through from outboard
            first = [(.45, add(b, (0, 70, 0))), (.57, b)]
        rest, stop, T = (YOKE_REST, 0, 0), (-RECOIL, 0, 0), CHAIN_T
        return [e('tensioner', K(*first, (.72, b), (.95, rest))),
                e('chain', K((0, rest), (T['push'][0], rest), (T['push'][1], stop), (T['release'][0], stop), (T['release'][1], (0, 0, 0))))]
    if name == 'recoil_spring':
        return [e('tensioner', K((.58, (75, 0, 0)), (.7, (0, 0, 0))))]
    if name == 'J909_housing':
        return [e('housing', K((0, (0, -70, 0)), (.55, (0, 0, 0))))]
    m = re.match(r'housing_screw_M3x8_(\d)$', name)
    if m:
        t = .6 + .07 * int(m[1])
        return [e('housing', K((t, (0, -25, 0)), (t + .16, (0, 0, 0))))]
    sb, ent, on = SPROCKET_BENCH, (0, SPROCKET_BENCH[1], 0), (0, 0, 0)
    travel = [(.38, sb), (.66, ent), (.84, on)]
    if name == 'J902_sprocket':
        return [e('sprocket', K((0, sb), *travel))]
    if name == 'flange_coupling_32':
        return [e('sprocket', K((.02, add(sb, (0, -35, 0))), (.16, sb), *travel))]
    m = re.match(r'hub_screw_M3x20_(\d)$', name)
    if m:
        t = .17 + .05 * int(m[1])
        return [e('sprocket', K((t, add(sb, (0, 35, 0))), (t + .1, sb), *travel))]
    if name.startswith('hub_set_screw_'):
        up = (0, 0, 2.5)
        return [e('sprocket', K((.3, add(sb, (0, 0, 14))), (.36, add(sb, up)), (.38, add(sb, up)), (.66, add(ent, up)), (.84, up), (.88, up), (.96, on)))]
    if name == 'J903_journal_plug':
        return [e('plug', K((0, (0, 45, 0)), (.45, (0, 0, 0))))]
    if name == 'sprocket_screw_M3x50':
        return [e('plug', K((.5, (0, 70, 0)), (.9, (0, 0, 0))))]
    raise SystemExit(f'No installation step for module part {name}')


def chassis_anim(p, order):
    """X101 comes down 80 mm (X1/ASSEMBLY.md 3.2); each joint screw is lowered beside the arm, slid sideways into its slot and pushed
    through; the far washer and nut go on from inside the track. Vehicle mm."""
    n = p['name']
    def e(keys):
        return [dict(s=SID['xframe'], keys=keys)]
    if n == 'X101_X_frame':
        return e(K((0, (0, 0, 80)), (.12, (0, 0, 80)), (.4, (0, 0, 0))))
    lo, hi = bounds(p)
    xc, yc = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    s = 1 if yc > 0 else -1
    sx = 1 if xc - math.copysign(63.5, xc) > 0 else -1
    i = order[re.search(r'_([LR]\d\d)$', n)[1]]
    if n.startswith(('mount_screw', 'mount_washer')):
        t = .42 + .03 * i
        return e(K((t, (sx * 16, -s * 12, 40)), (t + .07, (sx * 16, -s * 12, 0)), (t + .13, (0, -s * 12, 0)), (t + .19, (0, 0, 0))))
    t = .83 + .012 * i
    if n.startswith('mount_rear_washer'):
        return e(K((t, (0, s * 20, 0)), (t + .05, (0, 0, 0))))
    return e(K((t + .02, (0, s * 24, 0)), (t + .07, (0, 0, 0))))


def kit_id(name):
    for pre, k in [('J901_', 'J901'), ('J909_', 'J909'), ('J902_', 'J902'), ('J903_', 'J903'), ('J904_', 'J904'), ('J906_', 'J906'),
                   ('J907_', 'J907'), ('J908_', 'J908'), ('JGY370_', 'motor'), ('motor_screw_M3x6', 'M3x6'), ('sprocket_screw_M3x50', 'M3x50'),
                   ('flange_coupling_32', 'hub'), ('hub_screw_M3x20', 'M3x20'), ('hub_set_screw', 'setscrew'), ('6800ZZ', '6800ZZ'),
                   ('624ZZ', '624ZZ'), ('bolt_M4x70', 'M4x70'), ('nyloc_M4', 'nyloc'), ('idler_pin_8x55', 'pin8'), ('608ZZ', '608ZZ'),
                   ('recoil_spring', 'spring'), ('insert_M3', 'insert'), ('housing_screw_M3x8', 'M3x8'), ('X101_', 'X101'),
                   ('mount_screw_M4x25', 'M4x25'), ('mount_washer', 'washer4'), ('mount_rear_washer', 'washer4'), ('mount_nut_M4', 'nut4')]:
        if name.startswith(pre):
            return k
    raise SystemExit(f'No kit item for scene part {name}')


def piece(name):
    """One bought or printed piece may be several meshes (bearing rings and shields; the motor's gearbox, can and shaft)."""
    if name.startswith('JGY370_'):
        return 'JGY370'
    return re.sub(r'_(inner|outer|shield)$', '', name)


LABELS = {   # step: [(text, part, anchor)]; anchors on the part's bounding box in its fitted pose
    'frame': [('J901 H-frame', 'J901_H_frame', 'zmax'), ('M3 heat-set inserts x4', 'insert_M3_2', 'ymin', 0, .55), ('6800ZZ', '6800ZZ_outer', 'ymax', .55, 1)],
    'motor': [('JGY-370-1260 motor', 'JGY370_motor_can', 'ymin', 0, .5), ('M3 x 6 x4, from inside the H', 'motor_screw_M3x6_3', 'ymax', .5, 1)],
    'rollers': [('J904 road roller x5 (2 x 624ZZ each)', 'J904_roller_road2', 'zmin', 0, .56), ('J904 support roller x2', 'J904_roller_support1', 'zmax', 0, .56),
                ('M4 x 70 x7, from inboard', 'bolt_M4x70_road1', 'ymin', .56, .8), ('M4 nyloc x7, snug only', 'nyloc_M4_road3', 'ymax', .8, 1)],
    'tensioner': [('J906 idler + 2 x 608ZZ', 'J906_idler_wheel', 'zmax'), ('J908 U-yoke', 'J908_U_yoke', 'xmin'),
                  ('J907 spacer x2', 'J907_idler_spacer_1', 'ymax'), ('Ø8 x 55 pin', 'idler_pin_8x55', 'ymax'), ('spring C-600-072-1500', 'recoil_spring', 'zmax')],
    'housing': [('J909 housing', 'J909_housing', 'ymin'), ('M3 x 8 button head x4', 'housing_screw_M3x8_2', 'ymin')],
    'xframe': [('X101 X-frame', 'X101_X_frame', 'zmax'), ('M4 x 25 + washer, in the side slot', 'mount_screw_M4x25_L11', 'ymin'),
               ('washer + M4 nut, inside the track', 'mount_nut_M4_L11', 'ymax')],
    'sprocket': [('J902 sprocket', 'J902_sprocket', 'zmax'), ('Ø32 flange coupling', 'flange_coupling_32', 'ymin'),
                 ('M3 x 20 x3', 'hub_screw_M3x20_1', 'ymax'), ('set screw on the D-flat', 'hub_set_screw_M3x4', 'zmax')],
    'plug': [('J903 journal plug', 'J903_journal_plug', 'ymax'), ('M3 x 50', 'sprocket_screw_M3x50', 'ymax')],
    'chain': [('next link: down ahead, pushed back along the strip', 'link:{first}', 'c', .05, .1),   # {..}: numbers from chain_plan()
              ('bushing: in between the inner ears, from above', 'bush:{first}', 'c', .1, .125),
              ('pin: through plates, ears and bushing', 'pins:{first}', 'c', .125, .155),
              ('E-clip onto each groove, from the side', 'clip:{first_clip}', 'c', .155, .182),
              ('strip of 34 links, one joint left open', 'link:{strip}', 'c', .19, .355),
              ('last bushing, held by a Ø3 x 24 dummy pin', 'dummy:0', 'c', .36, .44),
              ('idler pushed back to its stop and held', 'J906_idler_wheel', 'zmax', .58, .7),
              ('front end lands short in a low arch, then is pressed flat', 'link:{arch_end}', 'c', .7, .765),
              ('last pin pushes the dummy pin out inboard', 'pins:{open}', 'c', .77, .845),
              ('2 E-clips, from the side', 'clip:{open_clip}', 'c', .85, .905),
              ('idler released: the spring tightens the chain', 'J906_idler_wheel', 'zmax', .92, 1)],
}


# --------------------------------------------------------------------------------------------- STL facts
def read_stl(path):
    data = path.read_bytes()
    n = struct.unpack_from('<I', data, 80)[0]
    assert len(data) == 84 + 50 * n, f'{path} is not a binary STL'
    tris = [t[3:12] for t in struct.iter_unpack('<12fH', data[84:])]
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    vol = area = 0.0
    pts = set()
    for ax, ay, az, bx, by, bz, cx, cy, cz in tris:
        vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6
        ux, uy, uz, vx, vy, vz = bx - ax, by - ay, bz - az, cx - ax, cy - ay, cz - az
        area += math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2) / 2
        for x, y, z in ((ax, ay, az), (bx, by, bz), (cx, cy, cz)):
            if x < lo[0]: lo[0] = x
            if y < lo[1]: lo[1] = y
            if z < lo[2]: lo[2] = z
            if x > hi[0]: hi[0] = x
            if y > hi[1]: hi[1] = y
            if z > hi[2]: hi[2] = z
            pts.add((round(x, 3), round(y, 3)))
    return dict(triangles=n, lo=lo, hi=hi, volume_cm3=vol / 1000, area_cm2=area / 100, hull=hull(sorted(pts)), sha256=hashlib.sha256(data).hexdigest())


def hull(p):
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for q in p:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    for q in reversed(p):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return lower[:-1] + upper[:-1]


def bed_fit(h, w, d):
    """Clearance per side of the footprint's convex hull on a w x d bed: placed straight if it fits that way, otherwise at the
    best rotation (0.25 deg steps); a negative clearance is half the shortfall."""
    def margin(deg):
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)
        xs = [x * ca - y * sa for x, y in h]
        ys = [x * sa + y * ca for x, y in h]
        return min(w - (max(xs) - min(xs)), d - (max(ys) - min(ys))) / 2
    straight = max((margin(a), a) for a in (0.0, 90.0))
    best = straight if straight[0] >= 0 else max((margin(k * .25), k * .25) for k in range(720))
    return dict(fits=best[0] >= 0, margin_per_side_mm=round(best[0], 1), angle_deg=best[1])


# --------------------------------------------------------------------------------------------- scene packing
def pack(p, extra):
    v, t = p['vertices'], p['triangles']
    wide = len(v) >= 65536
    a = array.array('f', (c for row in v for c in row))
    b = array.array('I' if wide else 'H', (c for row in t for c in row))
    if sys.byteorder != 'little':
        a.byteswap(); b.byteswap()
    return dict(name=p['name'], group=p.get('group'), kind=p.get('kind'), color=p['color'], wide=wide,
                v=base64.b64encode(a.tobytes()).decode(), t=base64.b64encode(b.tobytes()).decode(), **extra)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------------- chain hardware, piece by piece
# The CAD scene carries each joint's pin, bushing and two E-clips as one merged mesh (j9_scene.json.gz link[1]). They go in one at a
# time and by different routes (the Ø6 bushing cannot pass the Ø3.2 pin holes), so the animation draws them separately. Sizes are
# j9_design.py's and j9_parts.chain()'s; hardware_meshes() checks them against the merged mesh and the shoe.
PIN_R, PIN_HALF = 1.5, 28.0                         # Ø3 x 56 track pin
BUSH_R, BUSH_BORE, BUSH_HALF = 3.0, 1.55, 8.5       # Ø6 OD x Ø3.1 ID x 17 bushing
CLIP_R, CLIP_Y, CLIP_HALF_T = 3.0, 26.5, 0.3        # E-clip as the CAD models it: Ø6 x 0.6 on the Ø3 pin, groove 26.5 from the middle
DUMMY_HALF = 12.0                                   # Ø3 x 24 dummy pin: stays inside the inner ears, so the outer plates can come over
HW_COLORS = dict(bushing=[0.42, 0.45, 0.48], clip=[0.1, 0.1, 0.11], dummy=[0.86, 0.33, 0.12])   # pin: the scene's steel


def prism_y(name, color, outer, inner, y0, y1, closed):
    """Prism along Y between two contours paired point by point, (u, w) -> (x, z): end faces, outer and inner walls, outward
    winding. closed: both contours are loops (a tube); otherwise an open strip whose two ends close in points (the slotted clip).
    inner may be the centre repeated (a solid rod)."""
    V, T = [], []
    def vid(p):
        V.append([round(float(c), 5) for c in p])
        return len(V) - 1
    def tri(a, b, c, out):
        p, q, r = V[a], V[b], V[c]
        u, v = [q[i] - p[i] for i in range(3)], [r[i] - p[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        if math.sqrt(sum(x * x for x in n)) < 1e-9:
            return                                      # the clip's pointed tips
        T.append([a, b, c] if sum(x * y for x, y in zip(n, out)) > 0 else [a, c, b])
    m = len(outer)
    segs = list(range(m if closed else m - 1))
    nx = lambda k: (k + 1) % m
    for y, s in ((y0, -1), (y1, 1)):
        o = [vid((u, y, w)) for u, w in outer]
        i = [vid((u, y, w)) for u, w in inner]
        for k in segs:
            tri(o[k], o[nx(k)], i[nx(k)], (0, s, 0))
            tri(o[k], i[nx(k)], i[k], (0, s, 0))
    for wall, other in ((outer, inner), (inner, outer)):
        a = [vid((u, y0, w)) for u, w in wall]
        b = [vid((u, y1, w)) for u, w in wall]
        for k in segs:
            (u0, w0), (u1, w1) = wall[k], wall[nx(k)]
            if math.hypot(u1 - u0, w1 - w0) < 1e-9:
                continue
            n = [w1 - w0, u0 - u1]                      # edge normal, turned away from the material (toward the other contour)
            mid = [(u0 + u1 - other[k][0] - other[nx(k)][0]) / 2, (w0 + w1 - other[k][1] - other[nx(k)][1]) / 2]
            if n[0] * mid[0] + n[1] * mid[1] < 0:
                n = [-n[0], -n[1]]
            tri(a[k], a[nx(k)], b[nx(k)], (n[0], 0, n[1]))
            tri(a[k], b[nx(k)], b[k], (n[0], 0, n[1]))
    vol = 0.0
    for a, b, c in T:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = V[a], V[b], V[c]
        vol += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6
    poly = outer + (inner[::-1] if not closed else [])
    area = abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1]))) / 2
    if closed:
        area -= abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(inner, inner[1:] + inner[:1]))) / 2
    assert abs(vol - area * (y1 - y0)) < 1e-6 * max(1, vol), (name, vol, area * (y1 - y0))   # closed and outward
    return dict(name=name, color=color, vertices=V, triangles=T)


def hardware_meshes(scene_link):
    """The pin, the bushing, the E-clip (mouth toward +X) and the dummy pin, centred on the joint axis (Y)."""
    merged, shoe = scene_link[1]['vertices'], scene_link[0]['vertices']
    ys = sorted({round(abs(v[1]), 3) for v in merged})
    rs = sorted({round(math.hypot(v[0], v[2]), 3) for v in merged})
    assert ys == [BUSH_HALF, CLIP_Y - CLIP_HALF_T, CLIP_Y + CLIP_HALF_T, PIN_HALF], f'chain hardware lengths changed: {ys}'
    assert rs == [PIN_R, BUSH_BORE, BUSH_R] and CLIP_R == BUSH_R, f'chain hardware radii changed: {rs}'
    faces = sorted({round(abs(v[1]), 3) for v in shoe if abs(v[1]) > 6.5})
    assert faces == [8.7, 13.7, 14.0, 21.0, 35.0], f'shoe ear/plate faces changed: {faces}'
    ears, plates = faces[0:2], faces[2:4]
    assert BUSH_HALF < ears[0] and ears[0] + 2 <= DUMMY_HALF <= ears[1] - 1 and plates[1] < CLIP_Y - CLIP_HALF_T, (ears, plates)
    n = 40
    circ = lambda r, k: [(r * math.cos(2 * math.pi * i / k), r * math.sin(2 * math.pi * i / k)) for i in range(k)]
    a = math.asin(PIN_R / CLIP_R)                       # the slot is as wide as the pin: the clip goes on sideways
    k1, k2 = 8, 24
    outer = [(CLIP_R * math.cos(t), CLIP_R * math.sin(t)) for t in
             [a + (math.pi / 2 - a) * i / k1 for i in range(k1)] + [math.pi / 2 + math.pi * i / k2 for i in range(k2)] +
             [3 * math.pi / 2 + (math.pi / 2 - a) * i / k1 for i in range(k1 + 1)]]
    tip = CLIP_R * math.cos(a)
    inner = ([(tip * (1 - i / k1), PIN_R) for i in range(k1)] +
             [(PIN_R * math.cos(math.pi / 2 + math.pi * i / k2), PIN_R * math.sin(math.pi / 2 + math.pi * i / k2)) for i in range(k2)] +
             [(tip * i / k1, -PIN_R) for i in range(k1 + 1)])
    steel = scene_link[1]['color']
    return dict(
        pin=prism_y('track pin Ø3 x 56', steel, circ(PIN_R, n), [(0, 0)] * n, -PIN_HALF, PIN_HALF, True),
        bushing=prism_y('track bushing Ø6 x Ø3.1 x 17', HW_COLORS['bushing'], circ(BUSH_R, n), circ(BUSH_BORE, n), -BUSH_HALF, BUSH_HALF, True),
        clip=prism_y('E-clip (slotted Ø6 x 0.6)', HW_COLORS['clip'], outer, inner, -CLIP_HALF_T, CLIP_HALF_T, False),
        dummy=prism_y('dummy pin Ø3 x 24', HW_COLORS['dummy'], circ(PIN_R, n), [(0, 0)] * n, -DUMMY_HALF, DUMMY_HALF, True))


# --------------------------------------------------------------------------------------------- fitting the chain
def chain_plan(cfg):
    """How the chain goes on (J9/ASSEMBLY.md 7), as data for the animation. One bottom-run link stays put; the strip is that link
    with the rest of the chain straight on either side. Wrapping bends each joint from straight to its CAD angle, outward from that
    link, so the free end stays straight and tangent to the wheel it is going round. The big bends (round the sprocket and the
    idler) follow one another with overlap; the small ones on the runs go with their neighbouring big bend. The open joint is the
    top-run pin nearest the middle, between the support rollers."""
    P, n = cfg['pins'], len(cfg['pins'])
    nxt = lambda j: P[(j + 1) % n]
    th = [math.atan2(nxt(j)[1] - P[j][1], nxt(j)[0] - P[j][0]) for j in range(n)]
    bend = [(th[k] - th[k - 1] + math.pi) % (2 * math.pi) - math.pi for k in range(n)]      # at pin k, between links k-1 and k
    assert abs(sum(bend) - 2 * math.pi) < 1e-9, 'the chain does not close'
    assert all(abs(math.dist(P[j], nxt(j)) - cfg['pitch']) < 1e-6 for j in range(n)), 'link pitch'
    zb = min(p[1] for p in P)
    bottom = [j for j in range(n) if abs(P[j][1] - zb) < .1 and abs(nxt(j)[1] - zb) < .1]
    anchor = min(bottom, key=lambda j: abs(P[j][0] + nxt(j)[0]))
    s0, s1 = sorted(v[0] for k, v in cfg['rollers'].items() if k.startswith('support'))
    open_ = min((k for k in range(n) if P[k][1] > cfg['drive'][1] and s0 < P[k][0] < s1), key=lambda k: abs(P[k][0]))
    front, rear = [], []                       # joints in the order they bend: anchor+1 .. open-1, and anchor .. open+1
    k = (anchor + 1) % n
    while k != open_:
        front.append(k)
        k = (k + 1) % n
    k = anchor
    while k != open_:
        rear.append(k)
        k = (k - 1) % n
    assert len(front) + len(rear) == n - 1
    joints, groups = [None] * n, {}
    for side, (a, b) in (('front', CHAIN_T['front']), ('rear', CHAIN_T['rear'])):
        ks = front if side == 'front' else rear
        big = [k for k in ks if abs(bend[k]) > math.radians(5)]
        over = 2.0                             # each big bend lasts two spacings
        s = (b - a) / (len(big) - 1 + over)
        win = {k: (a + i * s, a + (i + over) * s) for i, k in enumerate(big)}
        cur = win[big[0]]
        for k in ks:
            cur = win.get(k, cur)
            joints[k] = [round(cur[0], 5), round(cur[1], 5)]
        groups[side] = dict(joints=len(ks), wheel_joints=len(big), wheel_bend_deg=round(math.degrees(sum(bend[k] for k in big)), 2),
                            free_end_mm=round(cfg['pitch'] * len(ks), 1))
    # the arch the front end comes over in (see ARCH_DEG): up from the last idler joint, down from ARCH_PEAK links further on
    last = [k for k in front if abs(bend[k]) > math.radians(5)][-1]
    peak = (last + ARCH_PEAK) % n
    a_r = math.radians(ARCH_DEG)
    up_links = [(last + i) % n for i in range(ARCH_PEAK)]
    down_links = []
    k = peak
    while k != open_:
        down_links.append(k)
        k = (k + 1) % n
    assert len(down_links) == len(up_links), f'the arch is not symmetric: {up_links} up, {down_links} down'
    end, ang = list(P[last]), {}
    for k in up_links + down_links:
        ang[k] = th[k] + (-a_r if k in up_links else a_r)
        end = [end[0] + cfg['pitch'] * math.cos(ang[k]), end[1] + cfg['pitch'] * math.sin(ang[k])]
    short = math.dist(end, P[open_])
    along = -((end[0] - P[open_][0]) * math.cos(th[open_ - 1]) + (end[1] - P[open_][1]) * math.sin(th[open_ - 1]))   # short of it
    assert short > 3.5 and along > 3.5 and abs(end[1] - P[open_][1]) < .5, (short, along, end)
    # formed during the last idler bend, while that joint is already turning forward (it never bends backward), complete well before
    # the end comes down
    a, b = joints[last]
    arch = dict(joints={str(last): round(-a_r, 6), str(peak): round(2 * a_r, 6)}, on=[round(a + .1 * (b - a), 5), round(a + .6 * (b - a), 5)],
                off=list(CHAIN_T['close']))
    for u in [i / 200 for i in range(201)]:
        e = lambda v: 0 if v <= 0 else 1 if v >= 1 else v * v * (3 - 2 * v)
        assert e(u) * bend[last] - e((u - .1) / .5) * a_r > 0 or u == 0, f'the arch bends joint {last} backward at {u}'
    # the strip, joint by joint: per strip position i (link (open + i) % n); i = 0 is the first link, its rear joint is the open one
    def w(base, keys, g=1.0):
        return [round(base + g * v, 5) for v in keys]
    links, ahead, bush, pin, clips = [], [], [], [], []
    for i in range(n):
        if i == 0:
            links.append([FIRST_LINK[0], FIRST_LINK[1], FIRST_LINK[1]]); ahead.append(0)
            bush.append(list(LAST_BUSH['bush'])); pin.append(list(JOIN['pin'])); clips.append(list(JOIN['clips']))
            continue
        if i == 1:
            sch = {k: list(v) for k, v in FIRST_JOINT.items()}
        else:
            t0 = FAST_START + (i - 2) * JOINT_GAP
            sch = {k: w(t0, v, JOINT_GAP) for k, v in FAST_JOINT.items()}
        links.append(sch['link']); ahead.append(LINK_AHEAD); bush.append(sch['bush']); pin.append(sch['pin']); clips.append(sch['clips'])
    seq = lambda i: [links[i][0], links[i][2], bush[i][0], bush[i][1], pin[i][0], pin[i][1], clips[i][0], clips[i][1]]
    for i in range(1, n):
        q = seq(i)
        assert all(x <= y for x, y in zip(q, q[1:])), f'joint {i}: link, bushing, pin and clips out of order {q}'
        assert links[i][0] >= links[i - 1][2], f'link {i} comes down before link {i - 1} is in place'
    assert FIRST_LINK[1] <= links[1][0] and clips[-1][1] <= LAST_BUSH['bush'][0] < LAST_BUSH['bush'][1] <= LAST_BUSH['dummy'][0]
    assert LAST_BUSH['dummy'][1] <= CHAIN_T['strip'][1] <= CHAIN_T['lower'][0] and CHAIN_T['lower'][1] < CHAIN_T['rear'][0]
    assert CHAIN_T['rear'][1] < CHAIN_T['push'][0] and CHAIN_T['push'][1] < CHAIN_T['front'][0] < CHAIN_T['front'][1] <= arch['off'][0]
    assert arch['on'][1] <= arch['off'][0] and arch['off'][1] < JOIN['pin'][0] < JOIN['pin'][1] < JOIN['dummy_gone'] < JOIN['clips'][0]
    assert JOIN['clips'][1] <= CHAIN_T['join'][1] < CHAIN_T['release'][0]
    # E-clips go on open side first: on the bench from above (open side toward the link's shoe), the last two from the front
    mouth = [round(CLIP_FROM_FRONT - th[j], 6) if j == open_ else round(-math.pi / 2, 6) for j in range(n)]
    # where the strip lies (flat, in line with the fixed link): first joint and the far end's free ears, for the cameras
    pos = {anchor: P[anchor][0]}
    for k in front:
        pos[k] = pos[(k - 1) % n] + cfg['pitch']
    for k in rear[1:] + [open_]:
        pos[k] = pos[(k + 1) % n] - cfg['pitch']
    first_joint = (open_ + 1) % n
    ears = pos[(open_ - 1) % n] + cfg['pitch']
    return dict(anchor=anchor, open=open_, joints=joints, arch=arch, t=CHAIN_T, lift=CHAIN_LIFT,
                links=links, ahead=ahead, up=LINK_UP, bush=bush, bush_up=BUSH_UP, pin=pin, pin_out=PIN_OUT, pin_half=PIN_HALF,
                clips=clips, clip_off=CLIP_OFF, clip_y=CLIP_Y, mouth=mouth,
                dummy=dict(t=list(LAST_BUSH['dummy']), out=DUMMY_OUT, gone=JOIN['dummy_gone'], half=DUMMY_HALF),
                strip=(open_ + 3) % n, first=first_joint, first_clip=2 * first_joint + 1, open_clip=2 * open_ + 1, arch_end=(open_ - 1) % n,
                bench=dict(z=zb, first_x=pos[first_joint], ears_x=ears),
                facts=dict(open_joint_pin=open_, open_joint_xz=[round(v, 2) for v in P[open_]], fixed_link=anchor,
                           strip_length_mm=round(cfg['pitch'] * n, 1), sides=groups,
                           arch=dict(up_links=up_links, down_links=down_links, deg=ARCH_DEG, lands_short_mm=round(along, 2)),
                           strip_x=[round(pos[first_joint], 1), round(ears, 1)]))


def chain_cams(plan, pins, track_y):
    """Camera keyframes for the chain step [t, position, target]: close-ups of the first joint and of the dummy pin on the bench, of the
    last joint on top, wide views between. Track-local mm (left track); camsX1 in vehicle mm, the close-ups on the left track."""
    z, o = plan['bench']['z'], plan['open']
    near = lambda x, zz, d: [[x + d[0], d[1], zz + d[2]], [x, 10, zz + 2]]
    first = near(plan['bench']['first_x'], z, (115, 150, 95))
    ears = near(plan['bench']['ears_x'], z, (115, 150, 95))
    top = near(pins[o][0], pins[o][1], (95, 190, 60))
    wide, mid, join = [[-60, 1010, 420], [0, 0, 70]], [[-240, 470, 410], [0, 0, 70]], [[30, 660, 300], [0, 0, 45]]
    wideX, midX, joinX = [[-150, 1350, 950], [0, 0, 70]], [[-330, 650, 450], [0, 170, 80]], [[-480, 650, 420], [0, 0, 40]]
    shift = lambda c: [[c[0][0], c[0][1] + track_y, c[0][2]], [c[1][0], c[1][1] + track_y, c[1][2]]]
    times = [0, .04, .182, .357, .398, .6, .765, .905]
    cams = [[t, *c] for t, c in zip(times, [wide, first, wide, ears, wide, mid, top, join])]
    camsX1 = [[t, *c] for t, c in zip(times, [wideX, shift(first), wideX, shift(ears), wideX, midX, shift(top), joinX])]
    return cams, camsX1


def tri_box(a, b, c, lo, hi):
    """Triangle against axis-aligned box, separating-axis test."""
    cen = [(l + h) / 2 for l, h in zip(lo, hi)]
    ext = [(h - l) / 2 for l, h in zip(lo, hi)]
    v = [[p[i] - cen[i] for i in range(3)] for p in (a, b, c)]
    for i in range(3):
        if min(p[i] for p in v) > ext[i] or max(p[i] for p in v) < -ext[i]:
            return False
    cross = lambda u, w: [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
    e = [[v[(i + 1) % 3][j] - v[i][j] for j in range(3)] for i in range(3)]
    for ax in [cross(e[0], e[1])] + [cross(ei, u) for ei in e for u in ([1, 0, 0], [0, 1, 0], [0, 0, 1])]:
        if all(abs(x) < 1e-12 for x in ax):
            continue
        pr = [sum(x * y for x, y in zip(ax, p)) for p in v]
        r = sum(ext[i] * abs(ax[i]) for i in range(3))
        if min(pr) > r or max(pr) < -r:
            return False
    return True


def open_joint_access(cfg, unit, x101, track_y, plan):
    """Room at the last joint, against every module part in its fitted pose and X101 (both sides): outboard for the last pin's whole
    travel, inboard for the dummy pin it pushes out, and on both sides for an E-clip pushed on from the front and for fingers and
    pliers. Each box runs from the outer plates' faces (|Y| 21) outward, from 10 mm behind the joint to beyond the clip's start, and
    from just under the pin to 35 mm above it."""
    px, pz = cfg['pins'][plan['open']]
    assert abs(math.cos(CLIP_FROM_FRONT + math.pi)) > .99, 'the box below assumes the last clips come in along +X'
    reach = dict(outboard=PIN_OUT + PIN_HALF + 2, inboard=PIN_HALF + 2 * DUMMY_HALF + 3)
    out = {}
    for side, sg in (('inboard', -1), ('outboard', 1)):
        y0, y1 = sorted([sg * 21.0, sg * reach[side]])
        lo, hi = [px - 10, y0, pz - 6], [px + CLIP_OFF + CLIP_R + 2, y1, pz + 35]
        meshes = [(p['name'], p['vertices'], p['triangles'], 1, 0) for p in unit]
        meshes += [(f'X101 ({s})', x101['vertices'], x101['triangles'], sg, track_y) for s, sg in (('left', 1), ('right', -1))]
        hits = []
        for name, vs, ts, sg, ty in meshes:
            V = [[p[0], sg * p[1] - ty, p[2]] for p in vs]
            if any(tri_box(V[a], V[b], V[c], lo, hi) for a, b, c in ts):
                hits.append(name)
        out[side] = dict(box_min=[round(v, 1) for v in lo], box_max=[round(v, 1) for v in hi], clashes=hits)
        assert not hits, f'the last chain joint is not clear on the {side} side: {hits}'
    return out


# --------------------------------------------------------------------------------------------- main
def main(package):
    report = dict(generator='track_wheel_jgy370/J9/source/build_track_kit.py', revision='J9 revision F (X1 revision F mounting)')
    j9 = json.loads(gzip.decompress((HERE / 'j9_scene.json.gz').read_bytes()))
    x1 = json.loads(gzip.decompress((X1 / 'source/x1_scene.json.gz').read_bytes()))
    cfg = j9['config']
    assert 'revision F' in cfg['revision'], cfg['revision']
    assert x1['module'] == j9['unit'] and x1['j9'] == cfg, 'X1 scene does not hold the current J9 module: run X1 build_viewer.py first'
    report['inputs_sha256'] = {str(p.relative_to(REPO)): sha(p) for p in (HERE / 'j9_scene.json.gz', X1 / 'source/x1_scene.json.gz', Path(__file__))}

    # STL files: hashes against the revision-F export report, sizes, volumes and bed fits
    revf = {e['stl_file']: e for e in json.loads((X1 / 'revf_part_exports.json').read_text())['exports']}
    stl = {}
    for it in PRINTED + OPTIONAL_PRINTED:
        for side, rel in it['files'].items():
            f = read_stl(REPO / rel)
            ext = [round(b - a, 1) for a, b in zip(f['lo'], f['hi'])]
            assert abs(f['lo'][2]) < 1e-3, f'{rel} does not sit on the bed (z min {f["lo"][2]})'
            if rel in revf:
                assert revf[rel]['stl_sha256'] == f['sha256'], f'{rel} differs from revf_part_exports.json'
            stl[rel] = dict(size_mm=ext, volume_cm3=round(f['volume_cm3'], 2), area_cm2=round(f['area_cm2'], 1), triangles=f['triangles'], sha256=f['sha256'],
                            revf_export_match=(rel in revf) or None,
                            beds={f'{w}x{d}': bed_fit(f['hull'], w, d) for w, d in BEDS})
    report['stl'] = stl
    assert stl[X1S + 'J901_H_frame_right.stl']['size_mm'] == stl[J9S + 'J901_H_frame.stl']['size_mm']
    assert stl[X1S + 'J909_housing_right.stl']['size_mm'] == stl[J9S + 'J909_housing.stl']['size_mm']

    # the animation scene against the list: every mesh belongs to one listed item, and piece counts match the per-track quantities
    per_track = {i['id']: i['per_track'] for i in PRINTED + STANDARD + CHAIN}
    pieces = {}
    for p in j9['unit']:
        pieces.setdefault(kit_id(p['name']), set()).add(piece(p['name']))
    n_links = len(cfg['pins'])
    pieces['J910'] = set(range(n_links))
    counts = {k: len(v) for k, v in pieces.items()}
    counts.update(trackpin=n_links, bushing=n_links, clip=2 * n_links)
    expect = {k: v for k, v in per_track.items()}
    report['scene_counts_per_track'] = counts
    assert counts == expect, f'scene {counts} != list {expect}'
    assert sum(i['per_track'] for i in PRINTED) - 34 == 15 and sum(i['per_track'] for i in STANDARD) == 52, 'J9/BOM.md totals changed'
    chassis = [c for c in x1['chassis'] if c['name'] == 'X101_X_frame' or c['name'].startswith('mount_')]
    jc = {}
    for c in chassis:
        k = kit_id(c['name'])
        jc[k] = jc.get(k, 0) + 1
    assert jc == {'X101': 1, 'M4x25': 8, 'washer4': 16, 'nut4': 8}, jc
    report['scene_counts_x1_joint'] = jc

    # animation data
    # the chain: how it goes on, and room at the last joint
    assert abs(cfg['recoil'] - RECOIL) < 1e-9, cfg['recoil']
    plan = chain_plan(cfg)
    x101 = next(c for c in chassis if c['name'] == 'X101_X_frame')
    report['chain_fitting'] = dict(plan['facts'], schedule=CHAIN_T,
                                   last_joint_access=open_joint_access(cfg, j9['unit'], x101, x1['config']['track_y'], plan))

    joints = sorted({re.search(r'_([LR]\d\d)$', c['name'])[1] for c in chassis if c['name'].startswith('mount_')})
    order = {j: i for i, j in enumerate(joints)}
    unit = []
    for p in j9['unit']:
        unit.append(pack(p, dict(item=kit_id(p['name']), anim=module_anim(p['name']))))
    link = [pack(j9['link'][0], {})]                     # the shoe; the joint hardware goes in piece by piece
    meshes = hardware_meshes(j9['link'])
    hw = {k: pack(v, {}) for k, v in meshes.items()}
    report['chain_hardware'] = dict(
        source='drawn separately; sizes checked against the CAD merged pin + bushing + 2 clips mesh and the shoe (j9_scene.json.gz link)',
        pin=f'Ø{2 * PIN_R:g} x {2 * PIN_HALF:g}', bushing=f'Ø{2 * BUSH_R:g} OD x Ø{2 * BUSH_BORE:g} ID x {2 * BUSH_HALF:g}',
        clip=f'Ø{2 * CLIP_R:g} x {2 * CLIP_HALF_T:g} at Y ±{CLIP_Y:g}, slotted as wide as the pin so it goes on sideways',
        dummy_pin=f'Ø{2 * PIN_R:g} x {2 * DUMMY_HALF:g} (assembly aid, inside the inner ears)',
        triangles={k: len(v['triangles']) for k, v in meshes.items()})
    chas = [pack(c, dict(item=kit_id(c['name']), anim=chassis_anim(c, order))) for c in chassis]
    byname = {p['name']: p for p in j9['unit'] + chassis}
    steps = []
    for s in STEPS:
        d = {k: v for k, v in s.items()}
        if s['id'] == 'chain':
            d['cams'], d['camsX1'] = chain_cams(plan, cfg['pins'], x1['config']['track_y'])
        d['labels'] = []
        for text, part, how, *win in LABELS.get(s['id'], []):
            w = dict(t0=win[0], t1=win[1]) if win else {}
            if ':' in part:
                d['labels'].append(dict(text=text, part=part.format(**plan), at=None, **w))
            else:
                assert part in byname, part
                d['labels'].append(dict(text=text, part=part, at=anchor(byname[part], how), **w))
        # what goes in at this step, counted from the scene (per track; X1 joint parts per machine)
        items = {}
        for p in j9['unit']:
            if any(e['s'] == SID[s['id']] for e in module_anim(p['name'])) and module_anim(p['name'])[0]['s'] == SID[s['id']]:
                items.setdefault(kit_id(p['name']), set()).add(piece(p['name']))
        if s['id'] == 'xframe':
            for c in chassis:
                items.setdefault(kit_id(c['name']), set()).add(c['name'])
        if s['id'] == 'chain':
            items.update(J910=set(range(n_links)), trackpin=set(range(n_links)), bushing=set(range(n_links)), clip=set(range(2 * n_links)))
        d['items'] = [[k, len(v)] for k, v in items.items()]
        steps.append(d)
    placed = {}
    for s in steps:
        for k, n in s['items']:
            if s['id'] != 'xframe':
                placed[k] = placed.get(k, 0) + n
    assert placed == expect, f'parts fitted across the steps {placed} != list {expect}'
    report['steps'] = [dict(id=s['id'], title=s['title'], items=dict(s['items'])) for s in steps]

    kit = dict(printed=[dict(i, files=i['files'], facts={k: stl[v] for k, v in i['files'].items()}) for i in PRINTED],
               optional=[dict(i, facts={k: stl[v] for k, v in i['files'].items()}) for i in OPTIONAL_PRINTED],
               standard=[{k: v for k, v in i.items() if k != 'buy_md'} for i in STANDARD], chain=CHAIN, joint=JOINT, bench=BENCH,
               tools=TOOLS, totals=totals(), notes=notes(stl), verify=VERIFY)
    data = dict(unit=unit, link=link, hw=hw, chassis=chas, steps=steps, kit=kit,
                cfg=dict(cfg, track_y=x1['config']['track_y'], spring=dict(x0=28.0, set=25.8, free=38.1),
                         yoke_rest=YOKE_REST, recoil=cfg['recoil'], chain_anim={k: v for k, v in plan.items() if k != 'facts'}))
    vendor = REPO / 'actuator_v6/source/vendor'
    html = (HERE / 'install_viewer.html').read_text()
    for k, v in {'__THREE__': (vendor / 'three.min.js').read_text(), '__ORBIT__': (vendor / 'OrbitControls.js').read_text(),
                 '__DATA__': json.dumps(data, separators=(',', ':'), ensure_ascii=False)}.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    (ROOT / 'install_animation.html').write_text(html)
    md = markdown(stl)
    (ROOT / 'TRACK_KIT.md').write_text(md)
    (ROOT / 'track_kit.csv').write_text(csv_text(stl))
    report['outputs_sha256'] = {f: sha(ROOT / f) for f in ('install_animation.html', 'TRACK_KIT.md', 'track_kit.csv')}
    report['pass'] = True
    (ROOT / 'track_kit_report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    print('install_animation.html', round(len(html.encode()) / 1e6, 2), 'MB;', len(steps), 'steps;', len(unit), 'module meshes;', len(chas), 'chassis meshes')
    if package:
        make_package(stl, md)


def totals():
    printed = sum(2 * i['per_track'] for i in PRINTED)
    shoes = 2 * 34
    return dict(printed_pieces=printed - shoes, shoes=shoes, printed_designs=len(PRINTED), printed_files=sum(len(i['files']) for i in PRINTED),
                bought=sum(2 * i['per_track'] for i in STANDARD), chain=sum(2 * i['per_track'] for i in CHAIN))


LINE = 0.045                            # cm: one 0.45 mm extrusion line, for the shell estimate


def estimate_cm3(f, walls, infill):
    """Shell model, not a slicer: every surface carries walls x 0.45 mm of solid line, the rest is infill. No support material."""
    shell = min(f['volume_cm3'], f['area_cm2'] * walls * LINE)
    return shell + (f['volume_cm3'] - shell) * infill


def print_notes(stl):
    vol = sum(stl[rel]['volume_cm3'] * qty_files(i)[side] for i in PRINTED for side, rel in i['files'].items())
    est = sum(estimate_cm3(stl[rel], *i['est'][:2]) * qty_files(i)[side] for i in PRINTED for side, rel in i['files'].items())
    return dict(solid_volume_cm3=round(vol), solid_petg_kg=round(vol * PETG / 1000, 2), estimate_petg_kg=round(est * PETG / 1000, 2),
                frame_beds=stl[J9S + 'J901_H_frame.stl']['beds'], housing_beds=stl[J9S + 'J909_housing.stl']['beds'],
                x101_beds=stl[X1S + 'X101_X_frame.stl']['beds'])


def notes(stl):
    """Print notes shared by TRACK_KIT.md and the animation's parts list: [(head, text, [sub-points])]."""
    n = print_notes(stl)
    return [
        ('Bed size.', 'The H-frame and the housing are the long parts; everything else fits any bed. Measured on the STL footprints:',
         ['J901 H-frame: ' + '; '.join(bed_line(n['frame_beds'])) + '.',
          'J909 housing: ' + '; '.join(bed_line(n['housing_beds'])) + '.',
          'X101 (optional): ' + '; '.join(bed_line(n['x101_beds'])) + '.',
          'Diagonal placements leave little room for a brim or the purge line; check the slicer preview.']),
        ('Filament.', f'All the parts for two tracks are {n["solid_volume_cm3"]} cm³, {n["solid_petg_kg"]} kg of PETG if printed fully solid (the upper bound). '
         f'With the settings above a rough shell estimate (not a slicer result) is {n["estimate_petg_kg"]} kg, plus support material, most of it under the '
         'H-frames\' inner walls. Where the design gives no infill (H-frame, idler, shoes, housing) the estimate assumes 4 walls and 40 % '
         '(housing: 3 walls, 15 %). Three 1 kg spools leave room for the supports, the fit-check prints and a failed print; '
         'check the slicer total.', []),
        ('Print the fit checks first.', 'The bearing seats, the plug journal and the pin bores are nominal sizes that have not been printed yet. '
         'Before the long frames, print two shoes, one roller, one idler wheel, one spacer, one plug and one sprocket, and check them against the real parts:',
         ['two shoes with a pin, a bushing and two clips: the joint articulates freely and the clips seat in the grooves;',
          'one roller: both 624ZZ press in flush without cracking the seat;',
          'one idler wheel: each 608ZZ slides in by hand through its Ø22.6 bore and presses home against the central web, 13 mm below the face '
          '(trim any bridge sag on the bed side first);',
          'the plug in a 6800ZZ inner ring, and a J907 spacer on the Ø8 pin;',
          'the sprocket: the coupling flange (Ø32) seats in its Ø32.4 recess and the centre pad slides into the Ø6 bore.',
          'If a fit is off, correct the slicer\'s hole compensation, not the CAD. Then print the left H-frame and check its 6800ZZ seat, the motor '
          'counterbores and the Ø16.4 spring bore (with the J908 piston) before printing the right one.']),
        ('Left and right.', 'Print J901_H_frame.stl and J909_housing.stl from J9/stl for the left track and the _right files from X1/stl for the right track. '
         'Do not mirror a file in the slicer instead: the _right files are the checked revision F mirrors.', []),
    ]


VERIFY = [
    ('Fits:', 'the 6800ZZ, 624ZZ and 608 press fits, the Ø9.95 plug in the 6800ZZ, the Ø32.4 coupling recess, the Ø15.6 piston in the Ø16.4 bore.'),
    ('Motor screw holes:', '3 mm of thread engagement in the gearbox is assumed. Measure the real holes.'),
    ('Coupling set screw:', 'one set screw, no torque rating on a D-flat. Mark it, and recheck after the first runs and after any stall.'),
    ('Reverse stall:', 'limit the driver to about 1.0 A; at the full 1.3 A stall the idler has almost no margin.'),
    ('Heat:', 'the pod is closed. Feel the motor pod during the first runs and do not hold a stall.'),
    ('Loads and wear:', 'no load rating is claimed; the vehicle mass is not specified.'),
]


def qty_files(i):
    """Copies to print of each file, for two tracks."""
    return {k: (i['per_track'] if len(i['files']) == 2 else 2 * i['per_track']) for k in i['files']}


def size(stl, rel):
    return ' x '.join(f'{v:g}' for v in stl[rel]['size_mm'])


def bed_line(b):
    out = []
    for k, v in b.items():
        w, d = k.split('x')
        if v['fits']:
            a = v['angle_deg'] % 90
            a = min(a, 90 - a)
            how = 'straight' if a == 0 else f'diagonally, turned {a:g}°'
            out.append(f'{w} x {d}: fits {how}, {v["margin_per_side_mm"]:g} mm spare per side')
        else:
            out.append(f'{w} x {d}: does not fit ({-2 * v["margin_per_side_mm"]:g} mm short)')
    return out


def markdown(stl):
    t, n = totals(), print_notes(stl)
    L = ['# Track kit: what to print and what to buy for two J9 tracks', '',
         'Two J9 tracks, revision F (the tracks of the [complete X1 excavator](../../excavator_complete/README.md)). Generated by '
         '`source/build_track_kit.py` from the current STL files and the CAD scene, which it cross-checks against this list '
         '([track_kit_report.json](track_kit_report.json)); the same rows are in [track_kit.csv](track_kit.csv). '
         'The subsystem lists stay authoritative: [J9 BOM](BOM.md), [X1 BOM](../X1/BOM.md).', '',
         f'- **Print:** {t["printed_pieces"]} parts plus {t["shoes"]} track shoes, from {t["printed_files"]} STL files ({t["printed_designs"]} designs; '
         'the H-frame and the housing come as a left and a mirrored right file).',
         f'- **Buy:** {t["bought"]} standard parts, plus the chain hardware ({2 * 34} pins, {2 * 34} bushings, {4 * 34} E-clips).',
         '- **Installation animation:** [install_animation.html](install_animation.html). Open it offline in any browser. It plays the fitting order '
         'step by step, with the parts, tools and checks for each step, and has the same parts list in its "Parts list" tab.',
         '- **Parts showcase:** [parts_showcase.html](parts_showcase.html). Every part to print or buy in 3D, offline: turn it, see it on the '
         'print bed or as fitted, cut it open, read its dimensions on the model (each checked against the STL or CAD mesh) and its '
         'material and print settings, and find it in the track.',
         '- **Status:** nothing has been printed or assembled yet. The fits, strength and powered running are nominal CAD only (see the end of this page).', '',
         '## 1. Parts to print', '',
         '| Part | Prints for two tracks | STL file | Size as printed, mm | Material and settings | Orientation | Notes |', '|---|---|---|---|---|---|---|']
    for i in PRINTED:
        for side, rel in i['files'].items():
            q = qty_files(i)[side]
            label = i['name'] + {'left': ', left track', 'right': ', right track (mirrored)'}.get(side, '')
            L.append(f'| {label} | **{q}** | [`{rel.split("/", 1)[1]}`](../../{rel}) | {size(stl, rel)} | {i["settings"]} | {i["orientation"]} | {i["note"]} |')
    L += ['', 'Only to test the tracks on the chassis (not part of the tracks):', '',
          '| Part | Prints | STL file | Size as printed, mm | Material and settings | Orientation | Notes |', '|---|---|---|---|---|---|---|']
    for i in OPTIONAL_PRINTED:
        rel = i['files']['chassis']
        L.append(f'| {i["name"]} | {i["per_machine"]} | [`{rel.split("/", 1)[1]}`](../../{rel}) | {size(stl, rel)} | {i["settings"]} | {i["orientation"]} | {i["note"]} |')
    L += ['', '### Print notes', '']
    for head, text, sub in notes(stl):
        L.append(f'- **{head}** {text}')
        L += [f'  - {x}' for x in sub]
    L += ['',
          '## 2. Standard parts to buy', '',
          'Quantities for two tracks. "Step" is the installation step that uses them.', '']
    stepname = {s['id']: f'{i}. {s["title"]}' for i, s in enumerate(STEPS)}   # same numbers as the animation
    first = {}
    for p in json.loads(gzip.decompress((HERE / 'j9_scene.json.gz').read_bytes()))['unit']:
        first.setdefault(kit_id(p['name']), STEPS[module_anim(p['name'])[0]['s']]['id'])
    first.update(trackpin='chain', bushing='chain', clip='chain')
    for cat in ('Drive and bearings', 'Screws, nuts and inserts', 'Track chain'):
        L += [f'### {cat}', '', '| Part | For two tracks | Per track | Notes | Step |', '|---|---|---|---|---|']
        for i in [s for s in STANDARD + CHAIN if s['cat'] == cat]:
            q = f'**{2 * i["per_track"]}**' + (f' ({i["buy"]})' if i.get('buy') else '')
            note = i['spec'] + (' ' + i['buy_md'] if i.get('buy_md') else '')
            L.append(f'| {i["name"]} | {q} | {i["per_track"]} | {note} | {stepname[first[i["id"]]]} |')
        L.append('')
    L += ['### Only to mount the tracks on X101', '', 'Per machine (both tracks), revision F track joints:', '',
          '| Part | Qty | Notes |', '|---|---|---|']
    L += [f'| {i["name"]} | **{i["per_machine"]}** | {i["spec"]} |' for i in JOINT]
    L += ['', '### For the first powered test (not in the CAD)', '', '| Part | Qty | Notes |', '|---|---|---|']
    L += [f'| {i["name"]} | {i["qty"]} | {i["spec"]} |' for i in BENCH]
    L += ['', '## 3. Tools', '', '| Tool | For |', '|---|---|']
    L += [f'| {a} | {b} |' for a, b in TOOLS]
    L += ['', '## 4. Installation order', '',
          'The animation plays these steps; each step there lists its parts, tools and checks. The order is the X1 order, which also works on the bench: '
          'housing before the sprocket, and the rear sprocket and chain last, because on the chassis the joint nuts are reached from inside the track. '
          'If you build a track on the bench first and mount it on X101 later, take its chain, sprocket and journal plug off again for the joints.', '']
    for k, s in enumerate(STEPS):
        if k == 0:
            continue
        L.append(f'{k}. **{s["title"]}**{" (only when mounting on X101)" if s.get("x1only") else ""}: {s["caption"]}')
    ch = STEPS[SID['chain']]
    L += ['', f'### Fitting the chain (step {SID["chain"]})', '',
          'The chain is not threaded on link by link round the wheels. It goes on in one piece, as a real track does; step '
          f'{SID["chain"]} of the animation shows each move:', '']
    L += [f'{i}. {x}' for i, x in enumerate(ch['do'], 1)]
    L += ['', *[f'- **Check:** {x}' for x in ch['check']]]
    L += ['', 'Full instructions: [J9 assembly](ASSEMBLY.md) (one track) and [X1 assembly](../X1/ASSEMBLY.md) (the chassis joints).', '',
          '## 5. Still to verify on the real parts', '']
    L += [f'- **{a}** {b}' for a, b in VERIFY]
    L += ['',
          'DIN 6799 size 2.3 is listed for Ø3-4 mm shafts by [Würth](https://eshop.wuerth.de/Lock-washer-For-shafts-DIN-6799-phosphated-steel-WSH-LOK-SHFT-DIN6799-PHR-D23/049023.sku/en/US/EUR) '
          'and [Böllhoff](https://eshop-ro.boellhoff.com/out/media/pdf/DIN_6799_Stahl_Federstahl___en.pdf). Cut the pin grooves to the clip supplier\'s drawing.', '']
    return '\n'.join(L)


def csv_text(stl):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['type', 'part', 'qty_two_tracks', 'per_track', 'file', 'size_mm', 'settings_or_spec', 'orientation'])
    for i in PRINTED:
        for side, rel in i['files'].items():
            w.writerow(['print', i['name'] + ('' if side == 'both' else f' ({side})'), qty_files(i)[side], i['per_track'] if side == 'both' else 1,
                        rel, size(stl, rel), i['settings'] + ' ' + i['note'], i['orientation']])
    for i in OPTIONAL_PRINTED:
        rel = i['files']['chassis']
        w.writerow(['print, optional', i['name'], i['per_machine'], '', rel, size(stl, rel), i['settings'] + ' ' + i['note'], i['orientation']])
    for i in STANDARD + CHAIN:
        w.writerow(['buy' if i['cat'] != 'Track chain' else 'buy, chain', i['name'], 2 * i['per_track'], i['per_track'], '', '', i['spec'], ''])
    for i in JOINT:
        w.writerow(['buy, X1 joint', i['name'], i['per_machine'], '', '', '', i['spec'], ''])
    for i in BENCH:
        w.writerow(['bench test', i['name'], i['qty'], '', '', '', i['spec'], ''])
    return buf.getvalue()


def package_stl(i, side, rel):
    """Where the download puts a print file: stl/<group>/<name>[_LEFT|_RIGHT]_x<copies for two tracks>.stl"""
    q = qty_files(i)[side] if i in PRINTED else i['per_machine']
    stem = Path(rel).stem.replace('_right', '')
    sub = {'left': 'left_track_only', 'right': 'right_track_only', 'both': 'both_tracks', 'chassis': 'optional_X1_chassis'}[side]
    tag = {'left': '_LEFT', 'right': '_RIGHT'}.get(side, '')
    return f'stl/{sub}/{stem}{tag}_x{q}.stl'


def make_package(stl, md):
    out = REPO / 'output/track_print_kit'
    show = ROOT / 'parts_showcase.html'
    rep = json.loads((ROOT / 'parts_showcase_report.json').read_text())
    stale = [k for k, v in rep['inputs_sha256'].items() if sha(REPO / k) != v] + ([] if rep['outputs_sha256']['parts_showcase.html'] == sha(show) else [show.name])
    assert not stale, f'parts_showcase.html is older than {stale}: run build_parts_showcase.py, then this script with --package'
    if out.exists():
        shutil.rmtree(out)
    (out / 'stl').mkdir(parents=True)
    names = {}
    for i in PRINTED + OPTIONAL_PRINTED:
        for side, rel in i['files'].items():
            dst = out / package_stl(i, side, rel)
            dst.parent.mkdir(exist_ok=True)
            shutil.copyfile(REPO / rel, dst)
            assert sha(dst) == stl[rel]['sha256']
            names[str(dst.relative_to(out))] = rel
    for f in ('install_animation.html', 'track_kit.csv'):
        shutil.copyfile(ROOT / f, out / f)
    page = show.read_text()   # the showcase links each part to its renamed file in stl/ (there are no STEP files in the download)
    assert page.count('const PACKAGE=false;') == 1
    (out / show.name).write_text(page.replace('const PACKAGE=false;', 'const PACKAGE=true;'))
    note = ('> In this download the STL files are in `stl/`, renamed with the number of copies to print for two tracks '
            '(for example `J904_roller_x14.stl`); README.txt maps each one to its file in the repository.\n\n')
    body = re.sub(r'\[([^\]]*)\]\((?!https?:)[^)]*\)', r'\1', md)
    head, rest = body.split('\n\n', 1)
    (out / 'TRACK_KIT.md').write_text(head + '\n\n' + note + rest)
    readme = ['J9 track print kit (two tracks, revision F)', '',
              'TRACK_KIT.md            what to print and what to buy, tools, print notes',
              'track_kit.csv           the same list as a table',
              'install_animation.html  installation animation; open it in a browser (works offline)',
              'parts_showcase.html     every part in 3D with its dimensions, material and print settings (works offline)',
              'stl/                    the files to print; the number after _x is how many copies for two tracks', '',
              'Files and their source in the repository:']
    readme += [f'  {k}  <-  {v}' for k, v in sorted(names.items())]
    (out / 'README.txt').write_text('\n'.join(readme) + '\n')
    z = REPO / 'output/track_print_kit.zip'
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(out.rglob('*')):
            if f.is_file():
                zf.write(f, Path('track_print_kit') / f.relative_to(out))
    with zipfile.ZipFile(z) as zf:
        assert zf.testzip() is None
    print('package', z.relative_to(REPO), round(z.stat().st_size / 1e6, 2), 'MB')


if __name__ == '__main__':
    main('--package' in sys.argv[1:])
