# Pololu #1999 universal aluminium mounting hub (6 mm shaft, M3 holes)

Vendor files for the J9 drive hub, downloaded on 2026-11-03 from the product's resources page (https://www.pololu.com/product/1999/resources):

| File | Source |
|---|---|
| `1999-6mm-m3-hub-dimensions.pdf` | https://www.pololu.com/file/0J667/1999-6mm-m3-hub-dimensions.pdf (drawing dated 5 August 2013) |
| `pololu-universal-aluminum-mounting-hub-for-6mm-shaft-m3-holes.step` | https://www.pololu.com/file/0J1153/pololu-universal-aluminum-mounting-hub-for-6mm-shaft-m3-holes.step |

What the drawing and STEP give:
- **Size:** Ø25.4 × 5 mm flange, Ø12 × 4.2 mm boss, Ø6 bore, 9.2 mm overall.
- **Mounting holes:** six M3 tapped through holes on a Ø19.05 circle (R9.525), 60° apart.
- **Set screws:** two M3 radial set-screw holes at the same angle. One is in the flange mid-plane; the other is at the boss mid-height, 4.6 mm further along the axis.

Product page facts (https://www.pololu.com/product/1999):
- Sold as a pair: two hubs, four M3 set screws (two per hub, the longer ones for the deeper flange hole) and a 1.5 mm hex key.
- Made for 6 mm round and D shafts.
- Pololu gives no set-screw lengths and no torque rating.

`J9/source/build_j9.py` places this STEP in the J9 pose and compares it with the modelled hub (`validation.json → drive_hub.vendor_step_check`).
