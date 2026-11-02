# Track R4: drive, guidance and width references

This revision uses real undercarriage component references in addition to the Cat 320 whole-machine drawing. The geometry is adapted to the model's 20 mm chain pitch and purchased hardware; it is not a factory replacement part or a uniformly scaled replica.

## Primary sources

Sources inspected on 29 October 2026:

- [Berco sprockets](https://www.berco.com/drive-sprockets-undercarriage/): construction-excavator cast/forged sprockets and final-drive flange drilling patterns. The product photograph directly shows deep rounded tooth pockets and a bolted annular wheel. [Offline reference image](berco_sprockets.png).
- [Berco rollers](https://www.berco.com/rollers-undercarriage/): track and carrier rollers, with single, double and inner-flange variants. The product photograph shows running surfaces bounded by flanges. [Offline reference image](berco_rollers.png).
- [Berco track chains](https://www.berco.com/tga-track-chains-undercarriage/): construction-excavator chains with distinct steel pins and bushings, selected and heat-treated for high loads and impacts.
- [Berco idlers](https://www.berco.com/idlers-undercarriage/): idlers and track adjusters for pretension, external loads and controlled frame clearance.
- Caterpillar [320 technical specifications](https://s7d2.scene7.com/is/content/Caterpillar/CM20240927-d80d6-c6a9b), with an [offline copy](../../excavator_arm_60mm/references/cat320_specifications.pdf). Page 2 lists 49 shoes, eight lower rollers and two carrier rollers per side. Pages 3 and 20 specify triple-grouser shoes and track guides. Page 4 gives 2,780 mm upperframe width, 2,380 mm track gauge and 3,170 mm overall undercarriage width with 790 mm shoes.

Berco and Caterpillar reference images remain copyright their respective owners. They are engineering references, not a claim of manufacturer approval. The public sources establish component architecture and appearance; they do not publish a manufacturing tooth profile for this model.

## 1. Sprocket and chain joint

R3 drove the exposed Ø3 pin directly. R4 fits a replaceable steel sleeve, Ø6 OD × Ø3.1 ID × 17 mm long, between the inner link ears. The sprocket now contacts the sleeve. The model uses a captured, replaceable sleeve on a through-pin; it does not reproduce a full-size sealed/press-fit track joint.

The 12-tooth wheel is recalculated for 20 mm pitch: pitch radius 38.637 mm, tooth-tip radius 40.821 mm, nominal pocket clearance 0.3 mm around the sleeve. Its bidirectional entry/exit relief follows the actual rigid-link swing. Tooth tips have 0.5 mm nominal clearance to the shoe web at the straight chord. Six open web windows make the toothed rim and hub distinct, while retaining the four-bolt purchased clamp-hub interface.

A full-size sprocket outline cannot simply be copied: pitch, bushing diameter, tooth count and axial width must agree with this chain. The reference component layout is used directly; these dimensions and the swept tooth relief are model-specific engineering choices.

Pins are now Ø3 × 56 mm, with clip grooves at ±26.5 mm. This keeps retaining clips outside the roller flanges during lateral guidance. Actual clip groove dimensions remain supplier-dependent.

## 2. Roller support and lateral guidance

Lower rollers carry load through the two link rails. Carrier rollers support the upper return run. Their steel axles remain frame-mounted; the rollers rotate on paired 608 bearings. Real excavator rollers generally guide with clearance rather than squeezing the shoes or acting as sideways spring clamps.

R4 replaces the loose central-flange arrangement with two outer guide flanges. Each flange projects 2 mm past its running surface. Guide faces are at Y = ±21.6 mm, outside the link rail faces at ±21 mm, leaving 0.6 mm running clearance per side. Idlers have matching outer guidance, rail-support rims and a central disc relieved for the larger steel bushings.

The sprocket/idler axes are raised 2 mm relative to the central ground run so the lower rollers carry the main chassis load. Complete horizontal chords remain around the end wheels; adjacent transition links slope to the central runs. The 34-link polygon retains exact 20 mm pitches by retracting the assembly idler 0.2005 mm from nominal. The quasi-static support rectangle uses the shorter, actually grounded run (79.30 mm conservative half-length).

The front idler retains its sprung -3 to +6 mm fore/aft take-up. That compliance accommodates pitch changes around the wheels; the lateral flanges prevent the chain walking off while leaving the pin joints free to articulate. Carrier centres move from X = ±45 to ±35 mm to clear the larger guide flanges of the lower rollers.

The simulation applies a 5 N sideways load to the free chain in each direction, with no artificial lateral restraint. Acceptance requires contact on both guide flanks and less than 1 mm lateral displacement. Separate checks require the three lower rollers to carry at least 70% of the supported weight together and each roller to carry at least 10% in both directions. Carrier support and passive rotation of every free wheel are checked separately. Small painted witness marks in the viewer make wheel rotation visible.

## 3. Tracks versus platform

“Wider than the platform” refers to the overall outside width of both tracks, not the width of one shoe. The comparison below is for the aligned upper body, not its swept envelope during slew.

| Dimension | Real Cat 320 | Model R3 | Model R4 |
|---|---:|---:|---:|
| Shoe width | 790 mm | 46 mm | 54 mm |
| Track centre spacing | 2,380 mm | 300 mm | 340 mm |
| Overall shoe width | 3,170 mm | 346 mm | 394 mm |
| Upper platform width | 2,780 mm | 294 mm | 308 mm |
| Outside-width/platform ratio | 1.14 | 1.18 | 1.28 |

Track R3 was already wider overall, but the cab-side overhang was only 15 mm. Track R4 gave 39 mm on the cab side and 61 mm on the other side of the offset 294 mm R2 platform. The R4 column now uses the centred 308 mm R3 upper body, leaving 43 mm beyond each side. Its 54 mm shoes are close to the 52.7 mm implied by the 1:15 reference; the broader stance is an explicit adaptation around the retained arm/base and bearing hardware.

Frame modules move outward by 16 mm and wheel centres by 20 mm. The bridge mounting pattern, drive/free axles and inboard spacers change together. Drive-sprocket bearing overhang increases from 29.5 to 33.5 mm and is included in the repeated shaft/bearing load calculation.

## Simulation and limits

The sprocket drives free rigid links through contact; belt positions are not prescribed. CAD-derived link/wheel masses, centres and inertias include the new steel sleeves. The loaded case supports half the calculated machine mass plus half the 0.15 kg study payload on a carriage free in X and Z. Pitch, roll and yaw are guided. The separate reduced vehicle model covers steering.

Exact moving-CAD checks include shoes, sleeves, pins and retaining clips against all wheels and neighbouring links. The contact model uses the actual running-rail outline, including the hinge-entry recess; the former short-box approximation hid carrier-roller interference. Numerical contact tolerances are 0.5 mm³ solid overlap and 0.1 mm floor penetration.

The browser replays the loaded straight-travel trace on both tracks, including reversal, braking and idler take-up. Ground is rigid; soil, wear, printed elasticity, dynamic chassis-rail collision and motor heating are not modeled. Bearings use declared procurement masses; the entire bearing ring contributes to rotating inertia, while reflected gearbox inertia is unknown. Physical fit, printed strength and powered endurance still need prototype testing.
