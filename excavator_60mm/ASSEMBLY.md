# Tracked arm60 — mechanical build and commissioning

This is a digital prototype for a later physical build. The supplied arm is the unchanged R4 arm60, with four standard V6-U60 actuators. Printer size and splitting are deliberately deferred. Do not scale the meshes to fit a printer: doing so would change bearing seats, gear pitch and the existing arm interfaces.

## Materials and print preparation

Use PETG for the chassis, decks, cab and links. Use a tough, accurately printed PETG or PA gear set; the calculations use an assumed 8 MPa allowable tooth-root stress, which must be confirmed for the actual material and print process. No steel shaft, track pin, bearing, gear pinion, spring, spacer or ballast is a printed substitute. Print the hub cap TW03, which carries the ring gear, in tough PETG or PA with solid infill around the teeth.

The STL files are in millimetres and placed on Z=0. Track frames, track-wheel parts and wheels follow the orientations listed in `../track_wheel/BOM.md`. The deck, counterweight, engine hood, tank housing, toolbox and equipment tray are inverted to put their broad flat faces on the bed. Support the stepped regions under the hood nose and the toolbox step in the slicer. Track R4 shoes have three 1 mm grousers and print on their tread faces; check support and bridging across the recessed grooves in the slicer. Print one ordinary and one `_left` track frame (`TW06_track_frame_left`); the supplied left mesh is already mirrored. All other quantities are in the BOM.

Start with `22_fit_coupon.stl` and two track shoes. Establish the actual hole compensation before printing the vehicle. The coupon also carries a Ø19.7 mm 18650 groove: a real cell must drop in and turn freely. Suggested starting settings are a 0.4 mm nozzle, 0.20 mm layers, six perimeters and dense local regions around holes and gear teeth. The mass calculations use the complete modeled PETG volume, not a particular slicer infill percentage. Reweigh the actual assembly and repeat the stability calculation if the mass distribution changes substantially.

The nominal 608/6004 seats are 22.2/42.2 mm. The track-wheel hub seats (Ø52 and Ø58 in TW02, Ø40 and Ø45 on TW01) are covered in `../track_wheel/README.md`; they are clearance seats retained by shoulders and fasteners, not a promised press fit on every printer. Tune them using the coupon. Ream running pin holes to 3.2 mm and axle clearances to the drawing. Deburr every track knuckle. Check flatness of the bearing-housing flange and decks. The original monolithic boom is approximately 414 mm long; splitting it is a separate engineering task.

## Track drive and shafts

Each track side is the Track R5 unit documented in [`../track_wheel/README.md`](../track_wheel/README.md). Its BOM, assembly sequence and commissioning steps apply here; this section covers how it fits the vehicle.

- **Final drive.** A Pololu 37D 150:1 gearmotor sits in the stationary housing TW01. The housing tube passes through the boss of the track frame TW06 from the inboard side and is fixed with four M3 × 10 screws into heat-set inserts. The sprocket hub TW02 turns on a 61808-2RS1 (under the sprocket) and a 6809-2RS (inboard) around that housing. A steel m1.5 12-tooth pinion on the motor's offset shaft drives the 21-tooth ring printed in the hub cap TW03 (1.75:1). No drive shaft, coupling, clamp hub or motor strap is used any more.
- **Motor control.** The two motors have independent H-bridge channels. Set each channel's current limit to 1.0 A: that gives 1.21 N m at the sprocket, the figure every R5 check uses. Both tracks forward give straight travel; opposite directions give a skid turn. Calibrate the left and right polarities after assembly, because the units are mirror images.
- **Motor cables.** They leave each housing through a grommet in the rear cap TW05, inboard of the frame. Route them along the bridge to the drivers with strain relief.
- **Sprocket teeth.** Each sprocket has 12 rounded bushing pockets at 20 mm pitch. The pitch radius is 38.637 mm and the tooth-tip radius 40.821 mm.
- **Bushings.** Fit one Ø6 OD × Ø3.1 ID × 17 mm steel sleeve over each Ø3 pin between the inner link ears. The sprocket drives the sleeve, and the plastic knuckles stay outside its faces. Deburr both sleeve ends and check the free slip fit before assembly. This captured, replaceable sleeve adapts real pin-and-bushing chain construction to the model; it is not a full-size sealed track joint.
- **Pocket profile.** The root pocket has 0.3 mm nominal radial clearance and swept entry/exit relief calculated for rigid 20 mm links. Tooth tips clear the shoe web by 0.5 mm nominally. Do not replace this profile with closed round holes or shallow circular scallops. See the Berco reference photos in `references/TRACK_SYSTEM.md`.
- **Wheel bearing stacks.** Each road roller and carrier has two 608 bearings on a Ø8 × 79 mm ground shaft (Y=117 to 196), with a 26 mm inner spacer, a 10 mm inboard spacer, a 1 mm outboard washer and two Ø8 × 5 mm collars. The idler has its own Ø8 × 89 mm axle in the sliding yoke, with 20, 6 and 11 mm spacers. All spacers are OD12/ID8.1 and touch inner races only. Tightening a collar must not make a wheel stiff.
- **Wheel positions.**
  - Road rollers: X=-52, 0 and 52, Z=29.
  - Carriers: X=±30, Z=63.641. Their Ø33 rims stand 0.5 mm above the straight top run so they keep carrying the sprung track.
  - Drive and idler: nominal centres X=-110 and +110, Z=46.321. Both sit 2 mm above the central ground run, so the lower rollers are the main chassis supports.
  - The assembly idler sits 0.201 mm behind X110. The ground run slopes down from the end-wheel chords; the top run dips between the carriers.
- **Track pins.** Tracks are centred at Y=±170. Pins are Ø3 × 56 mm silver steel (yield at least 400 MPa; the stone-jam simulation bends them to about 260–360 MPa). They have grooves for the chosen retaining clips at Y=±26.5 from each track centre. Use 68 pins, 68 steel sleeves and 136 clips. The groove width and depth must follow the actual clip supplier. Deburr the pin ends.

## Recoil idler and polygonal motion

- **Guide flanges.** Every idler, road roller and carrier has twin rail rims and outer guide flanges. The running surfaces support the two link rails. Guide faces sit at ±21.6 mm from the track centre around the ±21 mm rail faces, which gives 0.6 mm clearance on each side and 2 mm of flange projection. The wheels guide with clearance; they do not squeeze the chain.
- **Stance.** The shoes are 54 mm wide. Overall shoe width is 394 mm against the 308 mm R3 upper platform, 43 mm beyond each side; the pin envelope is 396 mm.
- **Joining the chain.** Join 34 shoes per side, with the complementary hinge ears alternating as in the STEP assembly. A 12-tooth sprocket has about 3.4 % chordal speed variation.
- **Recoil spring.**
  - The yoke TW07 slides in the channel of TW06. A C-600-072-1500 music-wire spring (6.29 N/mm, 38.1 mm free) pushes it forward.
  - Behind the spring are the seat TW08 and an M6 × 16 adjuster in a captive nut in the rear wall.
  - The channel nose TW09 is the forward stop. The end of the channel stops the yoke after 4.0 mm of recoil, before the idler can reach the front road roller (1.35 mm left).
- **Fitting the last pin.** Back the adjuster off, push the idler back and fit the pin.
- **Setting the preload.** Screw the adjuster in until its tip is flush with the front of the rear wall, then 3.5 more turns, and lock it. The spring is then 25.8 mm long and pushes 77 N.
- **Why that preload.** It keeps the strand under the sprocket tight when reversing at the 1.0 A limit. Do not run below 2.9 mm of adjuster travel.
- **Hand check.** Turn the sprocket by hand through full circuits in both directions before powering it, and watch the idler move and return.

## Recessed slew bearing and gear assembly

R2 lowers the upper deck by 48 mm while retaining the 40 mm bearing separation. The bearing tube and motor pass through the bridge; their mounting flanges still bear on the Z80 bridge top. Assemble the lower cap before fitting the housing to the chassis. The steel spindle and paired 6004 bearings carry the upper body; the motor drives the gears.

| Item | Z interval, mm | Interface |
|---|---:|---|
| Bottom bearing cap | 28 to 32 | Four M3 clearances on Ø54 at 45° |
| Lower outer-race spacer | 32 to 44 | OD42/ID35 × 12, steel |
| Lower 6004 bearing | 44 to 56 | 20 × 42 × 12 |
| Inner-race spacer | 56 to 84 | OD26/ID20.1 × 28, steel |
| Upper 6004 bearing | 84 to 96 | Bearing centres 40 mm apart |
| Upper outer-race spacer | 96 to 102 | OD42/ID35 × 6, steel |
| Upper bearing cap | 102 to 106 | Four M3 clearances on Ø54 |
| Upper inner-race spacer | 96 to 114 | OD28/ID20.1 × 18, steel |
| Clamp flange | 114 to 124 | Ø20 clamp bore; OD70; four tapped M5 holes on Ø50 at 45° |
| Upper deck | 124 to 134 | Matching flange holes; flush screw heads |

The Ø20 × 90 spindle spans Z34 to 124. The lower Ø20-bore collar spans Z34 to 44. Use accurately faced spacers and shims to remove end float without binding. Outer spacers contact outer races; the inner and top spacers contact inner races. Bearing envelopes do not model individual balls or establish preload. Four M3 × 85 tie bolts retain both caps. The Ø64 housing body has a Ø104 flange at Z80–88, secured through the bridge with four M5 bolts on Ø84 at 45°.

The module-1.5 gears have 96 and 20 teeth, 20° pressure angle and 10 mm face width. They occupy Z106–116. Their axes are 87.2 mm apart, including backlash allowance. Mount the ring on six 8 mm metal spacers using M4 × 30 countersunk screws and captured nuts. Mount the deck to the clamp flange with M5 × 20 countersunk screws. The pinion uses a purchased Ø4 shaft clamp hub, Ø24 × 7, with three M3 tapped holes on Ø18. Use M3 × 16 screws with 1 mm washers, and keep heads below Z124. Match or machine the metal hubs to the supplied STEP interfaces.

The vertical slew motor is centred at (87.2,0), with body Z46–97 and Ø4 shaft Z97–116. Its saddle has a top flange at Z80–86, with four M4 mounts at X58.2/116.2, Y±19. The motor passes through a clearance opening in the bridge. Formed steel straps clamp the body at Z54/84; fit them before enclosing the chassis. The four mounting bolts pass outside the motor opening into the bridge. Confirm shaft length and gearbox dimensions before purchase. Set backlash with a paper strip, remove it and check the complete gear cycle by hand.

The two Ø8 steel stop posts stand from Z80 to 124 at radius120 and ±15°. Their exposed length is 44 mm, plus the M5 mounting ends. The rear tab sits at Z117–124. Normal slew is at most ±150°; sampled hard-stop contact occurs around ±160.75°. Fit position feedback and independent normally-closed direction limits before the hard stops, with reverse motion allowed away from an active limit. Do not use impacts for homing.

The removable skirt rotates with the deck. Its lower edge is Z92: 12 mm above the bridge and clear of the tracks. Six M3 × 25 countersunk screws pass through the deck into captured nuts in its bosses. A notch clears the rear stop tab. Install the nuts before assembling the skirt. It encloses the mechanism and does not carry bearing loads. Its clearance does not establish flexible-cable clearance.

## R3 upper body

The upper body follows the Cat 320 layout. The cab is at the front left, beside the boom foot. A tank housing and a stepped toolbox fill the front right. The engine hood spans the full width behind them, and a curved counterweight closes the rear. The deck is 308 mm wide. Its rear arc and the counterweight follow the 189 mm tail-swing radius (Cat 320: 2,830 mm at 1:15). A 12 mm perimeter rim (Z112–124) stiffens the deck and reads as the upper-frame side members. It is left off the boom-foot nose so the bucket can pass in low poses.

Every shell is screwed down. Standard screws pass through printed bolt tubes into hex nuts held in pockets under the deck (Z124–134). Fit each nut before its shell goes on; the screw pulls it up against the pocket roof. No screw tip may reach below Z124, where the slew stop posts pass underneath. `simulation/packaging.json` checks every screw's tip height and nut engagement.

| Part | Fasteners | Notes |
|---|---|---|
| 18 counterweight | 4 × M4 × 80 countersunk | Heads flush at Z206; internal ribs clamp the ballast plate |
| 19 engine hood | 4 × M3 × 80 countersunk | Fit the exhaust stack first: one M3 × 8 from inside into the nut in its base |
| 29 hood hatch | 4 × M3 × 12 countersunk | Nuts captured in the four hood bosses; battery access |
| 30 tank housing | 2 × M3 × 80 countersunk | Open rear and bottom: room for wiring or a controller |
| 31 toolbox | 2 × M3 × 45 countersunk | Access step at Z152 |
| 23 equipment tray | 4 × M3 × 45 countersunk | Through the four legs; carries the cradle, BMS and converters |
| 33 cell cradle | 2 × M3 × 8 | Nuts in the tray underside pockets |
| 25 battery retainer | 2 × M3 × 20 | Nuts slide into side slots in the cradle posts |

Lay the 54 × 150 × 24 mm steel ballast plate (about 1.53 kg) on the deck at X=-167 to -113, Y±75, Z134–158. Put the 1 mm rubber strip on top. The counterweight's side ribs locate the plate; its central rib presses on the strip when the four M4 bolts are tightened. Do not substitute printed plastic: the stability calculation assumes steel.

## Cab and arm

The cab is 120 × 70 × 118 mm including the roof, compared with R1's 110 × 40 × 108 mm. Its length, width and height follow estimates from the Cat 320 manufacturer drawing at the arm's 1:15 reference scale; see `references/CAB_PROPORTIONS.md` for the measurements and limitations. The source gives overall machine dimensions, not standalone factory cab dimensions. The remaining vehicle dimensions adapt to the full-size bearings and original arm interfaces.

R3 keeps the R2 cab design but moves it 23 mm forward and onto the machine's left, as on the Cat 320. It occupies X=-22 to 98, Y=84 to 154 and Z134 to 252. Four M3 threaded rods pass through roof, corner posts and deck at (-17,149), (82,149), (-17,89) and (82,89). Cut them to 130 mm; their lower ends engage the deck nuts and stop at Z125. Fit a washer and nut on the roof without crushing the print. The seat uses four M3 × 35 bolts. Each console uses one M3 × 45 socket screw in a 3 mm counterbore. All of these go into deck nuts. Print two consoles; the second sits 50 mm inboard. All console details are decorative.

The STEP assembly includes four 0.8 mm PET glazing panels. Cut their outlines from the separate glazing STEP files or SVG templates, attach to inside faces with thin adhesive strips, and confirm clearance to the tie posts. Fit glazing after the cab hardware. The roof remains removable. The cab is not a sealed enclosure.

Mount the unchanged arm60 base at (45,0,134) mm, using four M6 × 25 screws at X13/121, Y±65 and recessed underside nyloc nuts. Keep all original arm shafts, spacers and collars. Build four V6-U60 actuators from the sibling folder. The original arm and actuator files are unchanged.

## Two-18650 battery bay

The cells sit on the equipment tray inside the engine hood, under the hatch. The R2 rear cassette is removed. The cradle (33) is sized from manufacturer datasheets rather than a generic envelope:

| Datasheet | Diameter, mm | Length, mm |
|---|---|---|
| Samsung INR18650-25R (2013) | 18.26–18.40 | 64.70–65.00 |
| LG INR18650HG2 (2014) | 18.0–18.5 | 64.8–65.2 |
| Panasonic NCR18650B (2012) | 18.5 maximum | 65.3 maximum |

The cradle accepts flat-top, unprotected cells Ø18.0–18.6 × 64.7–65.3 mm; the upper limits are 0.1 mm above the largest datasheet maximum. Use a matched pair rated at least 15 A continuous each, such as the 25R or HG2. The NCR18650B fits but is a low-current cell. Button-top or protected cells, 67–70 mm long, do not fit.

Have the pair spot-welded as a side-by-side 2S1P pack. It uses 0.15 mm pure-nickel strip (one series link at the +Y end, two terminal tabs at the -Y end), a 0.5 mm insulating separator between the cans, 0.3–1.0 mm end insulators and 0.12–0.25 mm PVC wrap. Never solder to the cans, and do not use the printed cradle as electrical contacts. The finished pack is at most 38.2 × 19.1 × 67.6 mm. Its leads leave through the notch in the -Y end wall.

Two Ø19.7 mm grooves on a 19.3 mm pitch locate the cells, with their axes along Y. The groove pair is centred at X=-68, with the groove axes at Z181.35. The end walls are 69 mm apart. Put two Ø17 × 4 mm closed-cell foam discs at the +Y end and the 3 mm foam pad over the pack. Then fit the retainer bar with two M3 × 20 screws into nuts slid into the side slots of the cradle posts. Across the datasheet range the end pads compress to 1.4–3.4 mm and the top pad to 1.3–2.1 mm, so the pack is always held but never crushed. The minimum radial clearance in the grooves is 0.2 mm. Try a real cell in the coupon's groove before printing the cradle.

| Reserved component | X / Y envelope, mm | Height / installation |
|---|---|---|
| 2S BMS | X -60 to -31; Y -78 to -48 | Z173–179 on two insulating standoffs |
| 6 V buck-boost converter | X -100 to -63; Y -78 to -46 | Z173–189 on two insulating standoffs |
| 12 V boost converter | X -100 to -40; Y 46 to 78 | Z173–194 on two insulating standoffs |

These are maximum module envelopes, not verified supplier parts. Each board has two M3 holes in the tray for insulating standoffs or an adapter plate matched to the actual board. Confirm hole patterns, underside clearance and cooling. The harness leaves the tray through the slot in its front edge (X-46 to -34). It reaches the chassis through the Ø8 deck opening at (-10,25) under the hood nose; fit a grommet there.

For service, switch off and unplug the pack. Remove the four M3 × 12 hatch screws and the two retainer screws, then lift the welded pack straight up. The BMS, converters and tray stay in place, and the cab and arm do not need removal. CAD checks lift the pack from 0 to 80 mm without collision, with about 14 mm clearance around it in the hatch opening.

## Battery power and controls

Two 18650 cells in series provide about 7.2 V nominal and 8.4 V fully charged; they are not a direct 12 V supply. Use a 2S balancing/protection BMS rated at least 10 A continuous, matched cells rated at least 15 A continuous, a 10 A main fuse, master switch and accessible stop circuit. Remove the pack for charging with the matching 8.4 V CC/CV 2S charger. The model does not include a commissioned charger or control PCB.

The 12 V boost rail supplies travel and slew drivers; reserve up to 30 W. A regulated 6 V buck-boost rail supplies the four U60 actuators; reserve up to 18 W. Enforce a shared 36 W output budget and an 8 A pack current limit, so these rail maxima cannot be demanded simultaneously. At 6.2 V and assumed 85% converter efficiency, 36 W requires approximately 6.83 A. The controller cutoff is 6.2 V; BMS undervoltage protection is the backup. Rail limits, converter cooling, cell sag and motor current must be measured. The existing motor torque assumptions only hold if the regulated rails and current limits support the purchased motors. Begin with travel and arm motion separately. Do not infer torque or runtime from cell count alone.

The BMS and converters sit on the equipment tray beside the pack. Route the regulated 12 V feed and control/stop signals to lower-chassis travel/slew drivers through the deck opening at (-10,25). Provide a flexible service loop, strain relief and a grommet, with clearance from the gear, flange and spindle throughout the allowed swing. This is limited rotation with no slip ring. Test the cable loop with covers off before enclosing it.

Both boom cylinders require measured synchronisation. The inherited V6 end-stop boards do not provide position feedback. Use independent stroke sensing and stop both drives on excessive mismatch. Matching voltages alone does not establish equal stroke.

## Boom and slew operation

Lowering the deck exposed a real self-collision: with the boom down, stick tucked in and upper body sideways, the bucket can hit a track. The unrestricted failing CAD case is retained in `simulation/unrestricted_lowered_body.json`; it has not been relabelled as a pass.

Boom stroke is available over the full 0–60 mm range at every slew angle within ±150°. The 15 mm / ±20° interlock has been removed: lowering the boom does not change slew, and slewing does not change boom extension. Track clearance is an operating responsibility.

The retained CAD clearance report samples a reference region: boom stroke at least 15 mm or slew within ±20°. Its passing results apply to those samples, not all combinations of the independent controls. The known bucket/track collision remains documented; the reference region is not enforced by the preview. No vehicle controller firmware is supplied.

Limit initial travel to 0.10 m/s, slew to 6°/s and motor torque/current to the verified drive requirements. The power-loss grade simulation rolls backward: powered holding is not a parking brake. Commission on a level restrained surface and use chocks for stationary tests.

## Commissioning sequence

1. Print the fit coupon and two shoes. Check bearings, pins, steel sleeves, hinge articulation and retaining clips against the actual hardware.
2. Assemble each track wheel unit following `../track_wheel/README.md`. Verify free wheels, idler recoil and return, and several hand-driven circuits in both directions.
3. With the tracks lifted, set the 1.0 A driver current limit and run each final drive slowly in both directions. Check direction, bushing entry/exit, motor current and hub temperature.
4. Assemble the recessed slew bearing stack, empty deck and stop system. Verify backlash, feedback, independent limits and reversal away from a limit. Fit the skirt only after these checks.
5. Clamp the ballast under the counterweight, fit the tray, cradle and electronics, then the insulated two-cell pack. Measure regulated rail voltages, cutoff, current limiting and converter temperature with a current-limited supply before using the pack.
6. Install the arm and cab. Verify paired-cylinder synchronisation, feedback-loss inhibition and independent travel limits. Exercise boom and slew controls through clear paths, observing bucket/track clearance.
7. Weigh the subassemblies and update the mass model. Measure actuator thrust, motor torque/current, deflection, temperature, creep and endurance. Begin unloaded; the calculated 0.15 kg study load is not a tested payload rating.
8. Keep the bucket clear of a solid floor, or provide a digging recess. Progress to known loads only after measured margins support them. Record results before a general print release.

No physical print, fit, load, soil-digging, endurance or powered-hardware test has been performed. Digital results and assumptions are in `validation.json`, `simulation/` and `simulation_report.pdf`.
