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

1. **Checkerboard vs slate: closed (author, 2026-10-07).** Not a switch. The two were used
   concurrently, split by setting:
   - **Lab:** the checkerboard, because a machine could find it.
   - **Field:** the slate, because a diver had one and it was easier than the board.

   The checkerboard came first, in the lab. A mount broke while other cameras were being prepared
   for shipping, so the H slate was improvised, and new cameras continued with the proven method.
   The DB dates interleave because cameras and techniques overlapped. The timeline now carries
   `track: lab | field`.
2. **Green laser rationale: closed (author, 2026-10-07).** Green was chosen because it penetrates
   further in water and was expected to be easier to see. IMWUT gives that rationale as it stood at
   the time; this paper reports the outcome: easier for divers, harder for automated detection.
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
2. **Green labels in red 2023 dives: answered "unknown" (2026-10-06).** Whether a green laser was
   used alongside red in the 2023-08-29 pool sessions is not known. Task 3d keeps dropping those
   frames, and the paper must not claim either way.
3. **V-slate reference points: answered (2026-10-06).** The V-slate has 6 reference points by
   design, and skipped points are listed in the skipped-points list. 27 of 113 V-slate frames list
   one; no H or Tic-Tac-Toe frame does.
   - Consequence: `calibration_analysis/e1j_size_constancy/slate_unknown.py` keeps only complete
     8-point labels, so it silently excluded every V-slate frame.
   - The earlier statement that the reef dives had "V-slates with skipped points" was wrong: most
     V-slate labels are complete.
   - Pool results (Tic-Tac-Toe) are unaffected.
   - **Fixed 2026-10-06:** `slate_unknown.load` keeps complete labels of each pattern's own count
     (8 or 6). Short labels are still dropped, since the missing point is not identified.
   - The reef dives now have a human-corner comparison in `reef_labelfree.py`. Fig 3 and the pool
     results are unchanged (Fig 3 rebuilt byte-identical).
4. **For analysis 3f (author, 2026-10-06: not known, but a floor date per camera may be
   recoverable).**
   - **The data cannot infer the mount.** No camera's dive laser line steps over 2023-08..2024-12
     (200 dives with a line from >= 20 dots): the line angle stays at 162-163 deg on every camera,
     consistent with the fixed laser origin in the fingerprint roadmap. Dive-to-dive offsets wander
     tens to hundreds of px within a month, with no break.
   - **Stored calibrations are too few** to carry 3f: 23 of 31 are from the 2023-08 pool sessions,
     and 8 are later.
   - **Planned design with a floor:**
     - Per camera, dives after the floor date count as aluminium; dives before are unknown (PLA
       or aluminium).
     - Metric: dive-to-dive spread of the laser line's offset per camera (pointing stability),
       aluminium vs unknown, within camera.
     - Mixing aluminium into "unknown" can only shrink a difference, so a positive result stands
       but a null is inconclusive.
     - Confound: the diode can rotate in its bore whatever the mount (fingerprint roadmap).
   - **Needed:** for each camera (FSL-01..06, 10), the earliest date by which it certainly had an
     aluminium mount, if any.
5. **TG-6 -> TG-7 for FSL-08+ (Jan 2025):** availability, cost, or a sensing reason?
6. **Slate pose predictor:** when was it retired, and why? (Inferred from the auto-accept commit:
   confident false fits passed the ECC gate. Driver currently machine, medium confidence.)
7. **Label Studio "Calibration Targets" branch (2026-07-21)** and **checkerboard calibration
   automation (2026-09-08):** why?
8. **Labelling starts and campaigns:**
   - Why did laser (2024-10), head/tail (2025-04), species (2025-10) and slate-corner (2025-11)
     labelling start when they did?
   - Why the 2025-10/11 campaigns that pre-filled earlier *human* labels?
   - Which model produced the 38 prediction-seeded laser annotations in 2024-11?
9. **Pipeline:**
   - What drove services/database (2024-10), the data-processing workers (2025-03), and moving
     the remaining stages onto Temporal (2026-05..09)?
   - Did core 3.0.0 -> 4.0.0 (2026-09-16) change anything that matters here?
10. **Isolated green-laser dives in 2023** (dive 242, 2023-10-19; dive 253, named "102724_..." but
   dated 2023-10-27): test dives or camera-clock errors?
11. **When was the per-dive calibration plan adopted?** Before 2023-08-01 is all the record shows.
   When was the first partner unit shipped?

## B''. Automation history (from the repos, 2026-10-07)

1. **Why did the CLI drop its neural laser detector for human labels on 2025-01-21?**
   (fishsense-lite-cli de881b42; the commit gives no reason.) Was it accuracy, speed or GPU needs
   (a 2024-11 commit raised its VRAM requirement), or the move to Label Studio?
2. **Were the 2024-11 Label Studio pre-fills (NN laser dots, Fishial masks) shown to labellers at
   scale?** The DB shows 38 prediction-seeded laser labels that month.
3. **The Depth Anything detector (2025-08..11) and the GMM detector (2025-04)** have no recorded
   reason for not being used. The GMM's committed result (~1,000 px RMS against human labels) speaks
   for itself; the Depth Anything one has no committed metric.

## B'. For the slate project (found 2026-10-06, `rectfit_sizes.py`)

- **Wrong poses in the rigid-board fit: fixed** (commit 4fa1c8d, tilt prior). The largest pool tilt
  is now 22 deg. Board-fit depth at the dot is 3.9% vs tape, against 2.8% for sqrt(area).
- **Range-correlated fill-in (still present after 4fa1c8d: r = 0.96 / -0.91).** In session 114 the fit adds more unseen outline on distant
  (small) boards. Its size then departs from sqrt(area) in step with range (r = 0.98 with added
  outline, -0.92 with size), and tape favours sqrt(area) there (1.3% vs 7.2%). Session 94 shows the
  same pattern but tape favours the fit (0.0% vs 4.2%). Worth a look at what the fill-in adds on
  far boards.
- **Choice order.** The candidate choice uses the label outline first. For label-free use the
  dot rule is what applies; on our 326 frames the two give the same mask.

## C. Open decisions (the author's, not mine)

- **Repository visibility during review** (author and advisors). Until decided, I will not link
  the repo, and I will prepare an anonymised mirror only if an artifact link is needed.
- **Sentences that reveal authorship.** These need rewriting in the third person:
  - Existing drafts (PAPER.md, p2-results.md) use "we" for the IMWUT and WUWNet work.
  - Dive names in the DB contain people's names. `tools/anonymize.py` pseudonymises them in
    committed files, and figures must be checked too.

## D. Status of known issues 1-4 (reported 2026-10-06; no change)

1. **Reef end-to-end lengths: done 2026-10-06** (`calibration_analysis/e1j_size_constancy/reef_labelfree.py`).
   - Label-free calibrations on dives 341, 347, 349 and 436 (68 slate frames, SAM 3.1 masks).
   - Fully automatic: median +2.8%, MAE 6.1%, 80% within 10%, vs -0.1% / 5.0% / 84% with the stored
     calibration.
   - The angle alone moves lengths by 1.3% MAE. The 104 mm |O| stand-in accounts for most of the
     rest, so the CAD value matters more than the angle method here.
   - Dives 279, 465 and 471 have only 2-3 slate frames with a dot. Detector-positive slate frames
     without a dot would need the laser detector on raw frames.
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
