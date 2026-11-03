# THK RU66 cross-roller ring: source of the turntable-seat dimensions

The X1 turntable seat is sized from THK's Cross-Roller Ring catalogue, model RU (integrated inner/outer ring type), pages A18-20 and A18-21. Both pages are saved here as images.

- Official product page: https://www.thk.com/jp/en/products/cross_roller_ring/cross_roller_ring/ru/ru/ (it links the catalogue E_18_CrossRollerRing.pdf).
- Copy actually read on 2026-11-03: https://cdn.shopify.com/s/files/1/1148/4670/files/Cross_Roller_Ring_-_Catalog.pdf. It is a THK catalogue PDF dated 2016-07-21 (SHA-256 `d05adb212ff9a98823996a94f19cac3881fa3fefe4cd2a47dcb6ab31fdd10726`). Check the current THK revision before ordering.
- `thk_A18-20_model_RU_dimensions.png`: main dimensions, shoulder limits, load ratings and mass.
- `thk_A18-21_model_RU_mounting_holes.png`: mounting-hole table and the mounting drawing.

## Values used (RU66 row)

| Item | Catalogue value | Used in X1 |
|---|---|---|
| Inner diameter d / outer diameter D / width B | 35 / 95 / 15 mm | Ring model; turntable face at Z 85 + 15 = 100 |
| Roller pitch circle dp | 66 mm | Not used for fitting |
| ds (max): largest shoulder that may touch the inner ring | 59 mm | The turntable's flange on the inner ring must stay within Ø59 |
| Dh (min): smallest bore of the housing that carries the outer ring | 74 mm | The X-frame relief under the inner ring is Ø75, so the seat touches only the outer ring |
| Inner ring mounting holes | 8 × M4 tapped through, PCD 45 | Left for the turntable |
| Outer ring mounting holes | 8 × Ø4.5 drilled through, Ø8 counterbore 4.4 deep, PCD 83 | 8 × M4 × 16 socket screws from above into heat-set inserts in the X-frame |
| Basic load rating C / C0 (radial) | 17.5 / 22.3 kN | Recorded only; no load rating is claimed for the chassis |
| Mass | 0.62 kg | Recorded |

The mounting drawing on A18-21 shows the outer ring bolted down onto a housing, with its counterbores on top, and the inner ring carrying the rotating part. X1 follows that arrangement: the X-frame is the housing and the turntable bolts to the inner ring.

THK RU66 rings are sold through bearing distributors, and other makers sell parts labelled as RU66 equivalents. Before buying a non-THK part, confirm that its hole pattern and counterbore side match this table.

The catalogue pages remain © THK CO., LTD. They are kept here as engineering references.
