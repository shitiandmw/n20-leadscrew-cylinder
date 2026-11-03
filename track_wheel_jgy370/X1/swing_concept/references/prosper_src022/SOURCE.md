# Slip ring SRC022A-6 (sold as Adafruit 736): source of the sizes in the swing concept

- **Product page:** https://www.adafruit.com/product/736 ("Slip Ring with Flange - 22mm diameter, 6 wires, max 240V @ 2A"). Adafruit points to the datasheet for part number SRC022A-6.
- **Datasheet actually read on 2026-11-03:** https://core-electronics.com.au/attachments/localcontent/SRC022A-6_6228710fdf5.pdf, linked from Core Electronics' listing of the same product.
  - It is four catalogue pages (020–023) of the maker's SRC022 series.
  - SHA-256: `8430ee31168cd5d0eaeb0635b9e561169d073056077e99b3f8e8f5c0336de568`.
  - The PDF itself is not kept here. These two pages are rendered from it:
    - `prosper_SRC022_p020_outline_dimensions.png`: outline drawings, including the A type;
    - `prosper_SRC022_p022_specifications.png`: electrical and mechanical data for the series.

## Values used (A type, 6 rings)

| Item | Datasheet | Used in the concept |
|---|---|---|
| Stator body | Ø22, L = 19 (SRC022A-6; 28 for SRC022A-12) | Hangs under the X-frame top plate |
| Flange | Ø44 × 2.4 at the rotor end, 3 × Ø5.5 holes on Ø35 | Screwed to 3 new bosses under the top plate |
| Rotor | Ø7.8 × 9 | Points up into the Ø25 passage; the turntable turns it |
| Rated current / voltage | 2 A per ring / 240 VDC or VAC | 4 rings for the two track motors (stall 1.3 A each), 2 spare |
| Leads | AWG26, FEP insulated, silver-plated copper, 250 mm | Both ends |
| Speed / temperature | 0–300 rpm / −20 to +80 °C | Swing about 7.5 rpm |
| Electrical noise | < 0.01 Ω | — |
| Contacts / housing | Precious metals / engineering plastics | — |

Check the seller's current drawing before buying: rings sold under other part numbers may differ in flange size and hole pattern.

The catalogue pages remain the maker's copyright. They are kept here as engineering references.
