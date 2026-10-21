# Questions and open items for the SenSys 2027 Experiences paper (result parity vs task parity)

## N3. Author responses to the citations and records report (author's account, 2026-10-19)

Each item is the author's account. Where no commit or file backs it, the entry says so.

1. **Laser colour (item 11).** Early testing used both red and green while the team worked out what
   the system needed. Red was deployed first (User Manual Rev 0, 2023-08-01, lists the Innovative
   Scuba red pointer; author's copy, not in the repo). The red pointers began to leak after a few
   months of use (stakeholder notes, 2023-12-14; PDF to be added), and replacing them prompted the
   team to reconsider red versus green: the leak is the **trigger**. Green was chosen because it
   penetrates further in water and was expected to be easier for divers to see: that is the
   **reason** for the choice. No 2024 record of the decision exists; the per-camera switch dates
   (2024-03 to 2024-12) are from the DB. Recorded in `timeline.yaml` as two entries ("red pointers
   leak", driver: other; "red → green laser", driver: human).
2. **November 2024 pre-fill (item 9b).** Turned on to help labellers; its predictions were wrong
   often, labellers found constantly correcting them annoying and found it faster to label without
   assistance, so it was withdrawn. Dates are from fishsense-lite-cli c1c447d3..708a2ce3. **No revert
   commit exists; the withdrawal rests on the author's account.**
3. **Neural detector removed from laser calibration (item 9a).** Too inaccurate, the same reason as
   the pre-fill; it is the same model that produced the pre-filled predictions. Removed in two steps:
   checkerboard calibration 2025-01-21 (de881b42) and field calibration by 2025-03-25 (bf8cbc8a). The
   steps are from the commits; **the reason has no commit, issue or note behind it.**
4. **Classical slate detector (item 10a).** The homography-to-slate-PDF approach: match each image to
   the slate's scan, compute the homography, transform the keypoints. Multiple keypoint-matching
   methods were tried; none was consistently successful. **No per-method results are recorded.**
   This answers N.1 (the homography-to-slate-PDF attempt).
5. **Definition of "attempt" (item 8).** Count distinct detection methods; exclude the 2023
   coordinate refiner (it refines a given location rather than finding the dot); count a model once
   even if used in more than one place. Two classical methods came before the neural network:
   brightest spot in the image (failed: bubbles, reflections and, in low light, sensor noise amplified
   by the camera's gain are often brighter than the dot; low-light case to be linked to the dive 279
   red-speck false positives) and a 2D Gaussian fit on the brightness channel (failed: the dot is
   clipped, so its top is flat). Sequence of distinct methods: brightest spot; Gaussian fit; neural
   network (2023 CLI demo / 2024 NNLaserDetector); Gaussian-mixture colour detector (2025);
   fine-tuned Depth Anything (2025); ResNet-34 U-Net on RAW input (deployed 2026-07).
   **Closed (code search, 2026-10-21):** the 2023-09 CLI demo checkpoint and the 2024 NNLaserDetector
   are the same network: identical architecture and byte-identical weights (sha256 57b19f89...4f08,
   133,975 bytes; fishsense-lite-cli@860c801 and the Hugging Face annotator114/laser-detector file). So
   five methods failed before a sixth worked. Classical methods:
   - **Brightest spot: code found.** pyFishSenseDev_bak@1113e62 (2023-07-13) `detect_laser.py`
     keeps saturated pixels inside the laser-line mask; threshold lowered at dac85dc (2023-07-31);
     superseded by the packaged NN at 3b81397 (2023-09-21). The failure reason has no record behind
     it (author's account). Dive 279's red specks taken for the laser are recorded in
     imwut_2026_fishsense_lite `fish_model_analysis/IN_PLANE_DRIFT.md:347-358` (ce372d6,
     2026-10-18), but that record does not mention low light or gain, so the low-light link rests on
     the author's account.
   - **2D Gaussian fit: no code found** in any searched repo or org-wide search
     (pyFishSenseDev_bak2 not searched). It and its failure reason rest on the author's account; its
     date is unknown (placed at 2023-08 in `automation_attempts.yaml` by the author's ordering).

## N2. Pending files (author, 2026-10-21)

- `writing-rules.md` and the shared-facts file are not in the repo yet; the author will add both.
  Until then, confirmed facts are kept here and in `claims.yaml`.
- The 2023-12-14 stakeholder notes PDF will be added. Until it is, everything drawn from it (red
  pointers leaking, early two-color pool testing) is a secondary summary in `timeline.yaml`.

## N3. Records audit follow-ups (2026-10-21)

- **Demo checkpoint (2023-09-22): closed.** It is NNLaserDetector (author's recollection,
  2026-10-21; confirmed by byte-identical weights, automation_attempts.yaml header).
- **Red pointers leaking vs the switch to green: closed (author, 2026-10-21).** The leak required
  replacing the laser; the team evaluated new lasers and switched to the green Shark laser. The leak
  is the driver of the replacement, the evaluation chose green. No written record of the evaluation.

## N1. Toward image-only laser calibration (author preference, 2026-10-19: image measurements, not physical ones)

Remaining non-image inputs in the label-free laser calibration:
1. **The slate-frame dots are human clicks.** Running the deployed detector on the ~326 pool and reef
   slate frames would remove them. It needs NAS raws plus the GPU (T3 ran at about 7 s a frame,
   limited by the NAS). Run it?
2. **The laser offset |O| is the 104 mm stand-in**, a physical value. Images can only supply metric
   scale through a target of known size, e.g. the lab checkerboard, whose laser calibration is
   automatic and per rig. Use that, re-measured whenever the rig is rebuilt?

## N0. From the user manual and the IMWUT submission (2026-10-18)

- **A written protocol exists.** User Manual Revision 0 (2023-08-01) covers field procedure,
  photo guidelines, the laser calibration (board, out and back, 10-50 images) and slate validation
  (three photos at three meters). The IMWUT submission s4.1 says units were distributed with it.
  "No written protocol" is withdrawn.
- **Sweep protocol: answered (author, 2026-10-18).** Date unknown; it was triggered by the mount
  break (the mount moved and did not survive, so the sweep was added). The manual had no later
  revisions. Driver recorded as other (mount break), not machine.
- **Field calibrations, frame by frame (analysis/codesign/field_calibration_frames.py, 2026-10-18):**
  - Of the slate frames on the seven field dives (all found by the slate detector), 65 were never
    corner-labelled; each is answered "Laser not on slate" by the labeller.
  - Another 26 answered "Laser on slate" had their laser dot superseded, so stage 13 never saw them.
  - What superseded them (the line validator or a relabel) is not recorded per frame. Can you say?
- **Laser product.** The manual names the red laser: Innovative Scuba Aluminum Laser Pointer
  High-Intensity Red Beam. The green products (Shark, Orca Torch) by camera are still open (B1).

## N. From the 2026-10-07 brief (open)

1. **Homography-to-slate-PDF laser calibration attempt.** Waiting on your description. It is a
   placeholder in the laser-calibration figure footnote, not placed, with no date or details invented.
2. **Per-camera mount material and approximate dates** (see B4). The figure draws the mount as one
   band; redesign ticks and the aluminium switch need dates.
3. **Which green laser product was on which camera** (B1). The 2023-12-14 stakeholder notes record
   pool testing of "laser brands and how they attenuate relative to one another", and a search for a
   push-button laser because the red ones leaked. Do those test results survive anywhere?
4. **Camera naming across papers.** WUWNet says "OM System TG-6"; the timeline has Olympus TG-6
   (FSL-01..07) and OM System TG-7 (FSL-08+). Which names should this paper use?
5. **"SAM 3" vs "SAM 3.1".** Every SAM run here used the SAM 3.1 checkpoint (sam3.1_multiplex.pt,
   production's model). Should the paper say SAM 3.1, or SAM 3 with the checkpoint in a footnote?
6. **Spread threshold for task 3a.** The brief asks for the share of field dives with >= 1.5x
   apparent-size spread. Task 3c found that 1.5x gets the median fit within 0.05 deg, but 2x is
   needed for 98% of fits. Report both?
7. **Task 2 result to check: the two interfaces agree to 0.019 deg median, not exactly.** SAM 3 and
   labelled corners both land near the stored calibration, but their per-session difference reaches
   0.072 deg (session 94), and their errors correlate only weakly (r = 0.25). Is "nearly the same
   result" the right claim, given both are within target in 9-10 of 10 sessions?
8. **From the 2023-12-14 stakeholder notes (added to timeline.yaml):**
   - **Protocol.** The notes are the first record of protocol reasoning: volunteer task overload,
     "1 individual fish per species per minute", and ~5 m maximum range. Did any of this become an
     instruction to divers? If not, the paper still says "communicated at trainings" with a \todo.
   - **Video: answered (author, 2026-10-11).** Not adopted because laser detection needed the RAW
     stills; video is still on the to-do list (future work).
   - **Naming: answered (author, 2026-10-11).** The paper says "a citizen-science partner", not the
     program's name.
   - **The PDF names people**, so it is cited from your copy and not committed.
9. **Task 3 follow-ups that need compute or your input:**
   - **3a:** the full ~60k-image slate scan has not run. The spread result uses the 1,403 labelled
     slate frames.
   - **3b:** the detector project's line-mask gain re-picks the dot inside the corridor. Testing it
     with an own-prediction line needs re-running inference on T3's frames (NAS + GPU, about 11 h
     last time). Run it?
   - **3e:** needs the per-camera mount material and dates (item 2).
   - **3f:** a clean RAW-vs-JPEG number needs JPEG epoch_007 re-evaluated through the canonical
     full-validation path in the detector repo.
   - **New:** after 2026-07-27, 85% of "unseeded" laser labels copy the prediction to 0.00 px
     (no parent link, origin "manual"). How do accepted pre-fills lose their provenance:
     auto-accept write-back or the UI?
10. **Slate pose predictor retirement** (B5): **closed (records audit, 2026-10-21).** Retired
   2026-08-02/03 (fishsense-lite@65582b6e, @e32bd9bc); reason recorded in 65582b6e: the ECC gate,
   calibrated on 8 clear-water reef dives, passed confident false fits on pool frames. Was: inferred (2026-09, confident
   false fits). Needed for the "reverted" marker in the automation figure.



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
2. **Green laser rationale: closed (author, 2026-10-07; reconfirmed 2026-10-19).** Green was chosen
   because it penetrates further in water and was expected to be easier for divers to see. The
   trigger for reconsidering the colour was the red pointers leaking (see N3.1): the leak required
   replacing the laser, and the evaluation of replacements chose the green Shark laser (author,
   2026-10-21). This is the
   author's account; there is no 2024 record of the decision. The IMWUT sentence giving this
   rationale is not a contemporaneous source: it was added 2026-09-29
   (papers/fishsense-lite-imwut@25d7901) and removed 2026-10-19 (@364e022). This paper reports the
   outcome: easier for divers, harder for automated detection.
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
6. **Slate pose predictor: closed (records audit, 2026-10-21).** Retired 2026-08-02/03
   (fishsense-lite@65582b6e, @e32bd9bc), about 14 hours after deployment; the commit body records
   the reason (ECC gate does not transfer to pool frames; confident false fits). Was: when was it retired, and why? (Inferred from the auto-accept commit:
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

## B''. Automation history: answered (author, 2026-10-07)

1. **The CLI dropped its neural laser detector for human labels in 2025-01 because of accuracy.**
2. **The 2024-11 Label Studio pre-fills were shown to labellers at scale**, found poor, and labelling
   reverted to tasks with no pre-fill. Only 38 seeded annotations survive in the DB.
3. **The Gaussian-mixture (2025-04) and Depth Anything (2025-08..11) detectors** were not used
   because of poor accuracy.

Records audit (2026-10-21) of what the commits show for 1-2; the reasons remain the author's account:
- fishsense-lite-cli@de881b42 (2025-01-21) replaced NNLaserDetector with LabelStudioLaserDetector in
  checkerboard calibration (`commands/calibrate_laser.py`) only. Field calibration kept
  NNLaserDetector until the jobs rewrite, @bf8cbc8a (2025-03-25). No commit records a reason.
- The 2024-11 pre-fill is fishsense-lite-cli@c1c447d3 (2024-11-09) through @708a2ce3 (2024-11-13).
  No revert commit exists; `commands/label_studio.py` was still present at @650d1ba9 (2025-03-31),
  so the revert was operational.

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
   - Production-corpus size-constancy cross-check (2,927 frames, 32 dives), from the sections
     prepared for this paper (LASER_SECTIONS_FOR_P2.md); not a WUWNet result.
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
