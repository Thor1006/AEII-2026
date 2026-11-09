# Report Poster speaking script

**Date:** 2026-11-04
**Result:** Done
**Plan:** Direct user request to save the already drafted speech in the repository

## Goal
Save the English poster speech as a genuine Word 97-2003 .doc file for rehearsal and printing.

## What changed
- `presentation/TrueRehab_RF_Poster_Speaking_Script_Expanded.doc`: three A4 pages, 626 spoken words, eight poster cues in italics, plain black-and-white formatting.
- Expanded the original 352-word speech at the user's request. Added AI development and validation plus expected benefits, with fuller radar, point-cloud/heatmap and next-step explanations. The original short file was open and locked, so the expanded speech uses a new filename in the same directory. The hardware substitution is explicit, and model outputs remain demonstration targets pending validation.
- Poster speech and live demonstration are the primary preparation. Keep the existing slides as backup. A stage requirement and official presentation time have not been confirmed.

## Verification
Created a task-local DOCX using python-docx, then converted it with Word to genuine OLE .doc. The packaged DOCX renderer could not run because LibreOffice was absent; Word exported the finished document to PDF instead, and all three expanded rendered pages were visually inspected after removing an inherited title border. Read-back preserved all 31 revised spoken paragraphs. PDF has three pages. The repository copy SHA-256 matches the verified source.

## Boundaries
Submitted poster/proposal, slides, firmware, radar settings and Pi setup were unchanged. No commit or push. Task-local builders and preview files are outside the repository.

## Next
Rehearse aloud, measure actual delivery time, and update the speech if prototype validation changes before the event.

## 2026-11-05 Format only DOCX version
- User requested the same speech content in `.docx`: saved `presentation/TrueRehab_RF_Poster_Speaking_Script_Expanded.docx` beside the original `.doc`.
- Reused the original expanded speech's DOCX source after verifying that its complete normalized text matches the existing DOC. All three DOCX rendered pages were visually inspected, and extracted page text and page breaks match the original approved PDF exactly.
- Original DOC retained and unchanged. No speech rewrite, poster/proposal edits, commit or push.
