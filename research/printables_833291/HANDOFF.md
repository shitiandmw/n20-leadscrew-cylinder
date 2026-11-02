# Printables excavator structure review

The original research examined whether Printables model 833291 offers useful structural references for R7, using its public description, all six project photographs and the file list. That research preceded the subsequent R8 trial.

## Current status after R10 and workspace cleanup

The user rejected R8's boom modification and work motion. Later revisions culminated in R10: two symmetric boom drives and a deeper boomerang-shaped boom. See [the current R10 handoff](../../excavator_arm_dual/HANDOFF.md). The user subsequently requested removal of all R6–R9 folders, their motion-review folder and associated delivery files. Those workspace files are removed; tracked history remains in Git. This directory preserves independent reference research. The reference project's STEP remains unmeasured, and the observations below do not validate the withdrawn R8 design.

## Sources and access

- Project: https://www.printables.com/model/833291-diy-rc-excavator
- Author: ProfessorBoots. Title: DIY RC Excavator.
- Author-linked video: https://youtu.be/bLtUqkhdQGQ. Its link was verified in the description; the video itself was not reviewed.
- The webpage returned an access challenge. Public project metadata and image paths were available through the site's public GraphQL endpoint. The successful metadata is saved in `public_project_metadata.json`.
- The six public photographs were fetched and visually inspected; temporary copies are in `/tmp/printables-833291/` if still available.
- The file list includes both STL and STEP, but STEP/STL geometry was NOT downloaded or measured. Do not claim measured pivot coordinates, actuator travel, motor thrust or digging depth for this project.
- The metadata lists Creative Commons Attribution–NonCommercial–ShareAlike. It also describes optional paid workshop electronics/build guidance; no paid material was accessed.

## Confirmed observations and relevance

- Rear photograph `extra-2.jpg` shows one central boom screw assembly. Side photograph `extra.jpg` shows its placement on the body-facing/back side of the boom root. This differs from R7's actuator base pin forward of and below its boom pivot. It is a useful alternative mounting topology to investigate; no superiority in force or reach is established by the photos.
- Public files include `9.) Main Boom Holder`, `14.) Main Boom Push Rod`, `17.) Main Boom`, `18.) Dipper`, `12.) Motor Holder` and `13.) Motor Holder Lock`, including STEP equivalents. These support further examination of a separate root support and serviceable drive mounts. File names alone do not establish internal fastening details.
- The bucket has a visible rocker/link mechanism. Files `19.) Attacher`, `20.) Bucket`, `21.) Bucket Swing Arm` and `22.) Bucket Push Link` are useful references for curl geometry. R7 already has a four-bar mechanism; the possible improvement is its pivot placement and packaging, not merely adding a four-bar.
- The photographs offer bucket shell and cutting-edge shape references. No separately named tooth part is present in the public file list. Do not claim the project implements replaceable teeth; preserve the user's R7 removable-tooth requirement.
- The project also has a Thumb and optional attachments, but adding these is outside the user's current question and is not proposed as a priority.

## Recommended next steps if the user requests a redesign

1. Obtain the publicly listed STEP arm/support/actuator/linkage parts through the normal download interface, then measure actual pivot centers and actuator interfaces.
2. Compare any proposed reference mounting topology with current R10 under the same 380 mm boom, 193.333 mm stick and existing U60 140–200 mm pin spacing. Determine extension/retraction direction from geometry.
3. Evaluate full-motion clearance, below-base reach, minimum effective moment arm, required thrust and bucket entry/curl angles together. Avoid gaining travel by making the drive almost collinear with the driven pivot.
4. Preserve the latest user requirements: two symmetric boom actuators, a deeper-middle boomerang profile and individually replaceable teeth. The original one-actuator requirement has been superseded.

## Existing design and constraints

R10's current geometry, fixed-base dynamics, verification and limitations are documented in the linked handoff. Real drive capacity, hardware synchronization, structural strength and soil interaction remain unverified. The historical research used commit `cfa225d`; the tracked R6–R9 directories were still present at pre-cleanup commit `2c44f83`.

The shared handoff MCP tools are unavailable. This is a local fallback for task `dcb205db-7475-4d77-b86f-89548a1531ad`; no shared-note update is claimed. No subagents or persistent services were used. User-facing answers should be in Chinese for this question.
