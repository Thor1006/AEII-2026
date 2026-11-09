# Stage presentation and matching script

Date: 5 November 2026
Result: Completed the user's backup slide presentation and matching English speaking version.

## Deliverables

- `presentation/TrueRehab_RF_Stage_Visual.pptx`: 10 main slides plus 2 hidden optional Q&A slides, 16:9, editable text and native diagrams. White and black backgrounds, one blue accent, large typography and one main idea per slide. The user asked for simple visual storytelling inspired by Steve Jobs, with the audience guided without conspicuous pointing.
- `presentation/TrueRehab_RF_Stage_Presentation_Script.docx`: six A4 pages, 661 main spoken words, approximately 5 to 6 minutes with pauses. Includes slide timing, italic delivery cues and optional Q&A responses. Spoken wording also appears in each slide's speaker notes.

## Story and evidence

The sequence moves from a completed set of ten illustrative curls to a change in movement strategy, radar reflections, the actual AWR2944PEVM, an actual recorded radar display, the planned synchronized reference experiment, detection before prediction, current evidence and the long-term contactless goal. Native curl illustrations and the timing diagram are labeled conceptual. The actual board photo and radar-lab screenshot remain documentary images.

The hardware substitution is disclosed on slide 5, in its spoken script and on the hardware Q&A slide: AWR1843BOOST plus DCA1000EVM in the submitted poster, AWR2944PEVM plus onboard processing and USB in the current implementation. Processed points/heatmaps are not treated as raw ADC/I-Q. Fatigue and compensation models are explicitly unvalidated. Literature motivates the question without borrowing outside treatment outcomes. Relevant local evidence and the Levin, Kleim and Wolf paper are cited in slide notes.

## Verification

- All twelve slide renders inspected individually. PPTX finalization passed package integrity, geometry and font checks with zero layout findings, plus first-party re-import.
- Verified slides 11 and 12 carry the hidden flag, and all twelve speaker-note scripts match the source speech.
- Word exported the script to PDF because the packaged LibreOffice renderer remains unavailable. All six rendered pages inspected, with readable cues, complete paragraphs and no clipped text or orphaned headings.
- Repo deliverables copied from the verified artifacts without changes. Hashes checked after copying.

## Boundaries and handoff

The submitted poster/proposal, earlier poster-speaking scripts, existing decks, software, firmware, acquisition settings and Pi setup were not changed. No clinical trial or live sensor command ran. No commit or push. Poster plus booth speech remains the primary format; this deck is the backup for stage presentation. Rehearse aloud and recheck prototype readiness before the event.

The established local PPTX fallback was used because the earlier Spaces authoring attempts repeatedly failed with a missing MXC runtime error. Task-local editable authoring sources and QA files are under the Codex project workspace `tmp/aeii-stage-deck/`; they are not required to open the deliverables.
