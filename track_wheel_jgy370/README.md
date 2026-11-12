# JGY-370 track module

This folder holds the current track and the crawler chassis built on it, both driven by JGY-370 gear motors.

- **[J9](J9/README.md): the single track with one printed H-frame.** It has a flat ground run, 70 mm shoes, and 5 road and 2 support rollers. The motor is the JGY-370-1260 12 V 200:1 (30 rpm), the sprocket bolts to a bought Pololu #1999 hub, and the housing closes over the motor with a pod. To build the two tracks, start with the [track kit](J9/TRACK_KIT.md).
- **[X1](X1/README.md): the crawler chassis, revision F.** Two J9 tracks sit on a printed X-frame in the Cat 320 lower-frame layout. The R3 turntable sits on a THK RU66 slewing ring and carries the B1 upper body. See the [revision F notes](X1/REV_F_NOTES.md).
- **[references/](references/)**: the motor drawings and ratings, the Pololu #1999 hub (STEP and dimensions) and the other design inputs that J9 and X1 use.

The whole machine, with the R12 arm on X1, is in [`excavator_complete/`](../excavator_complete/README.md).

## Removed

The J8 track, with continuous aluminium side frames, used to live at the top of this folder with its scripts, CAD, preview, video and design review. J9 replaced it and nothing current used it, so it was removed on 2026-11-12. It remains in Git history; for example, commit `39bc9a7` has the full J8 folder.
