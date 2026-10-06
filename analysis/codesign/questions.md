# Questions and open items for the SenSys 2027 co-design paper

Round 1 asked 2026-10-06; answered by the author the same day. Section R records those answers.
Sections A-D are what is still open.

## R. Answered (2026-10-06); recorded in timeline.yaml

- **Calibration history:**
  - Lens calibration was planned once per camera lifetime, and laser calibration once per mount
    lifetime.
  - The first partner unit's PLA mount warped and broke, so its laser calibration drifted.
  - That introduced per-dive slate calibration. Driver: other (physical failure).
- **Slate patterns:**
  - H -> tic-tac-toe: too few markable points, and hands covered some. Driver: human
    (labelability).
  - Tic-tac-toe -> chevron: the symmetric pattern hid rotation/origin from labellers. Driver: human
    (labelability).
  - Tape patterns were chosen for human keypoint labelling; computers were poor at it.
- **Model pre-fills:** `driver: unknown`, noting the author's account of task parity (automation
  designed to replace the human in the same flow). No record of the decision itself.
- **Laser colour:**
  - Red first, for fish behaviour; red was also easier to label.
  - Green for diver visibility. Driver: human.
- **Laser power:** a commodity constraint, not a revision.
- **Mounts:** redesigned repeatedly because of field breakage, ending in aluminium. Analysis 3f
  added (PLA vs aluminium spread of stored laser angles).
- **|O|:** keep the fleet median 104.0 mm as \todo.
- **Capture protocol:** communicated at trainings; no written protocol may be claimed. \todo
- **Double-blind rules:**
  - Write in the third person.
  - Never link the public repo; use an anonymised mirror if an artifact link is needed.
  - Scrub PDF and figure metadata.
  - Keep the AI-use log in `ai_use.md`.

## A. New conflicts and evidence found while applying the answers

1. **Checkerboard vs slate. The record shows the checkerboard used for *laser* calibration.**
   The author's account is that the checkerboard was the lens target and the slate the laser
   target. I have not asserted a switch. The evidence:
   - **DB, 2023-08 pool sessions:** 15 dives (2023-08-14..18) are linked to the "E4E Checkerboard"
     target (10x14, 42.17 mm pitch) and named `LaserCalibration*`.
     - Dive 490's note: a checkerboard burst shot with the laser on, during which the laser rotated
       0.82 deg in-plane.
     - Dive 521's note: laser-calibration and lens-calibration frames in one folder; the lens
       frames carry no laser. So the two uses were distinct in practice.
   - **IMWUT draft:** `imwut_2026_fishsense_lite/PAPER.md` L259-264 states a deliberate switch.
     The first 19 pool sessions (14-18 Aug) used the checkerboard; the last 12 (29-31 Aug) used the
     slate, "because a slate is something a volunteer diver already carries".
   - **2025-01-17:** the TG-7 units were laser-calibrated against checkerboards (dives 480, 481).
   - **2026-09-08:** `PerformCheckerboardCalibration` automated.
   - **But the field H-Slate was already in use on 2023-08-01**, before the checkerboard pool
     sessions. So "checkerboard then slate" holds only for the pool fish-model study, if at all.

   **Question:** Was the pool checkerboard use a laser calibration (as the DB and the IMWUT draft
   say), a lens calibration that happened to have the laser on, or both? Is the IMWUT draft's
   "moved away deliberately" sentence accurate?
2. **The IMWUT draft gives a machine-side reason for green.**
   `papers/fishsense-lite-imwut/Sections/system.tex` L163 says green was chosen "because it
   penetrates water further, and reliable detection of the laser dot in post-processing is a
   critical constraint". That contradicts your account (diver visibility; red easier to label) and
   the detector result (green missed more). One of them should be corrected before both papers are
   out.
3. **The IMWUT cost table lists a red laser.** `system.tex` L11 lists "Innovative Scuba Aluminum
   Laser Pointer (Red)", while the text says a Class IIIA 532 nm green pointer.
4. **The IMWUT draft says laser calibration is "performed once per dive site"** (`system.tex` L167).
   The timeline says per dive. Which is right for the field protocol?
5. **The IMWUT draft says "Divers are instructed to frame fish broadside"** (`system.tex` L165).
   Is there a source for that instruction, or is it the same verbal training? If verbal, this
   paper will say "communicated at trainings" and mark it \todo.
6. **The IMWUT draft says the mount file is freely available** in UCSD-E4E/fishsense-lite. Neither
   that repo (including its history) nor any other UCSD-E4E repo tree holds an STL/STEP/CAD file.
   Where is the mount file? It would also give the design |O|.

## B. Still unknown (timeline entries with `driver: unknown`, or no date)

1. **Green laser products (answered in part, 2026-10-06).** Green was two products: a "Shark"
   laser (apparently no longer sold) and an Orca Torch laser.
   - Which cameras carried which, and from when? The DB has no laser field, and no dive note names
     one. Without the assignment, task 3d can compare only red vs green, not product vs product.
   - Did the Shark and Orca differ visibly in the dot (size, brightness, beam streak)? If so, the
     dot shape in the images might identify the product, but that would be an inference. I'd use it
     only with your sign-off.
   - Was red always the Innovative Scuba pointer?
2. **Green labels in red 2023 dives (found by task 3d).** The 2023-08-29 pool dives (59, 61-63,
   65, 66, 71, 77, 80, 83) have 1-32% green laser labels, and a few 2023 reef dives have some too.
   Was a green laser used alongside red in those sessions (dive 83 is 32% green, dive 77 20%), or are
   these colour mislabels? Until answered, task 3d drops them. Either way, T3's "green, pool" cell
   (n=47) was almost entirely these frames, and the PAPER.md / p2-results.md sentences built on it
   need correcting.
3. **For analysis 3f:**
   - which cameras had PLA vs aluminium mounts, and from when;
   - any known repairs, knocks or replacement mounts, by camera and date.

   The DB has no mount field, and no dive note mentions a repair. Without this list, 3f can only
   compare cameras before and after a date you give.
4. **TG-6 -> TG-7 for FSL-08+ (Jan 2025):** availability, cost, or a sensing reason?
5. **Slate pose predictor:** when was it retired, and why? (Inferred from the auto-accept commit:
   confident false fits passed the ECC gate. Driver currently machine, medium confidence.)
6. **Label Studio "Calibration Targets" branch (2026-07-21)** and **checkerboard calibration
   automation (2026-09-08):** why?
7. **Labelling starts and campaigns:**
   - Why did laser (2024-10), head/tail (2025-04), species (2025-10) and slate-corner (2025-11)
     labelling start when they did?
   - Why the 2025-10/11 campaigns that pre-filled earlier *human* labels?
   - Which model produced the 38 prediction-seeded laser annotations in 2024-11?
8. **Pipeline:**
   - What drove services/database (2024-10), the data-processing workers (2025-03), and moving
     the remaining stages onto Temporal (2026-05..09)?
   - Did core 3.0.0 -> 4.0.0 (2026-09-16) change anything that matters here?
9. **Isolated green-laser dives in 2023** (dive 242, 2023-10-19; dive 253, named "102724_..." but
   dated 2023-10-27): test dives or camera-clock errors?
10. **When was the per-dive calibration plan adopted?** Before 2023-08-01 is all the record shows.
   When was the first partner unit shipped?

## C. Open decisions (the author's, not mine)

- **Repository visibility during review** (author and advisors). Until decided, I will not link
  the repo, and I will prepare an anonymised mirror only if an artifact link is needed.
- **Sentences that reveal authorship.** These need rewriting in the third person:
  - Existing drafts (PAPER.md, p2-results.md) use "we" for the IMWUT and WUWNet work.
  - Dive names in the DB contain people's names. `tools/anonymize.py` pseudonymises them in
    committed files, and figures must be checked too.

## D. Status of known issues 1-4 (reported 2026-10-06; no change)

1. **Reef end-to-end lengths use the stored calibration** (`e2e_measurement/tail/evaluate.py` L114).
   - A label-free run is possible on reef dives 341, 347, 349 and 436.
   - It needs NAS raws and a GPU pass.
   - Proposed for task 3.
2. **The two 0.003 deg figures are separate results:**
   - WUWNet production-corpus reproduction: 2,927 frames, 32 dives.
   - The Pinax figure: wrong. It is 0.015 deg at a 50 mm standoff. Corrected in claims.yaml.
3. **|O|:** no CAD value. The fleet median of 104.0 mm stands as \todo. A second estimate, the
   fitted origin (|O| ~106 mm over 6 calibrations, fingerprint roadmap), is consistent with it.
4. **Labelling-time medians hold under the stricter "no visible pre-fill" filter.** Task 3 switches
   the exported file to that filter.

## E. Proposal: which decisions carry the paper (unchanged except as noted)

**Full treatment:**
1. **Calibration.** The answers sharpen the story:
   - Calibration became per-dive because of a physical failure, and was solved with a
     human-labelled target.
   - The slate patterns were then revised twice *for labellers*, which made them no easier for
     machines.
   - The label-free variant removes the labelling the patterns were designed for.
2. **Labelling:** human pre-fill -> model pre-fill -> auto-accept, under task parity; anchoring
   (87%).
3. **Laser colour:** a diver-driven change that cost labelling and detection. Task 3d tests
   whether the gap survives control.
4. **Pipeline:** notebooks -> workflow engine.

**A sentence plus a design-rules row:**
- TG-6 -> TG-7;
- mounts PLA -> aluminium (promoted to a short result if 3f shows a difference);
- dot clipping;
- the calibration cues that failed;
- species;
- the gates.

**Projected:** video approach clips; the label-free reef calibration, if not run; Pinax.

## F. Task 3 order (to be confirmed)

1. 3d red vs green.
2. Label-free reef calibration (known issue 1).
3. 3f PLA vs aluminium, once B2 is answered.
4. 3a, after the server slate scan.
5. 3b, 3c and 3e as set out in the brief.

Deadlines: abstract Thu 29 Oct 2026, paper Thu 5 Nov 2026 (AoE).
