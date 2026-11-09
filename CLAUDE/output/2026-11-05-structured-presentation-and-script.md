# Four part presentation and matching script

Date: 5 November 2026
Result: Completed a new presentation following the user's requested structure, preserving the earlier versions.

## Deliverables

- `presentation/TrueRehab_RF_Structured_Visual.pptx`: 15 visible slides, 16:9, editable text, diagrams and two developer flowcharts. Same Arial, white/black and blue visual language as the earlier stage deck.
- `presentation/TrueRehab_RF_Structured_Presentation_Script.docx`: six A4 pages, 884 spoken words, target 460 seconds (about 7 to 8 minutes) plus demonstration time. Contains presenter, developer and demo-lead cues, with matching speech in all 15 slide notes.

## Requested structure

1. Short introduction: slide 1.
2. Background and problems: slides 2 to 9. Team and school/country; traditional measurement photo; the requested here's-the-thing bridge; scoped practical constraints; transition to the current radar photo; contactless design aims; clinician-guided rehabilitation at home; the movement-quality concept.
3. How it works: slides 10 and 11. Current radar-to-screen flowchart and the research model-development flowchart, with an explicit developer handoff.
4. Showcase: slides 12 to 15. Actual dashboard interface with synthetic-data disclosure, practical setup illustration, actual recorded radar output and closing.

## Sources and image provenance

- School identity comes from the submitted poster's original school logo and wordmark: Prasarnmit Demonstration School (Secondary), Srinakharinwirot University. Thailand is corroborated in the existing app footer. Individual names were omitted because the poster and app have conflicting spellings.
- Traditional-measurement photo: Costa et al., 2020, PeerJ 8:e9687, Figure 4, CC BY 4.0. Original unmodified image, credited visibly on slide 3 and in notes. Shows manual elbow goniometry alongside strapped IMUs, not the TrueRehab team.
  - Article: https://peerj.com/articles/9687/
  - Image: https://cdn.ncbi.nlm.nih.gov/pmc/blobs/cc73/7427560/fc9120391fa6/peerj-08-9687-g004.jpg
  - Publisher PDF/license: https://peerj.com/articles/9687.pdf
- Home rehabilitation wording is based on NICE NG236 recommendations 1.1.8, 1.2.22 and 1.13.7 to 1.13.8: continuing rehabilitation where beneficial, travel/access needs and supported safe independent exercise. https://www.nice.org.uk/guidance/ng236/chapter/Recommendations
- Surface EMG preparation is supported by the manufacturer's MyoWare guide: https://learn.sparkfun.com/tutorials/getting-started-with-the-myoware-20-muscle-sensor-ecosystem/hardware-hookup
- Movement completion versus movement strategy is informed by Levin, Kleim and Wolf: https://pubmed.ncbi.nlm.nih.gov/19118128/
- Actual AWR2944PEVM photo is the user's original board photo. The slide and speech explain substitution for the submitted AWR1843BOOST/DCA1000EVM arrangement.
- Dashboard image was captured from the existing `frontend/dist` in local synthetic demo mode. The interface banner and slide caption both identify simulated scores. The temporary loopback-only asset server on port 8871 was stopped afterward. No real kit, sensor, bridge or camera was connected by this task.
- Recorded real radar image is `radar-lab/real_room3d.png`. It remains distinct from the synthetic dashboard. The relief surface represents radar intensity, not physical height or anatomical tracking.

## Verification

All fifteen slide renders and all six script pages visually inspected. PPTX finalization passed package integrity, first-party import, Arial policy and geometry checks with zero layout findings. All fifteen speaker-note scripts match the DOCX speech. All slides remain visible and are ordered in the requested four parts. Repo copies match the verified files by SHA-256.

The packaged DOCX renderer remains unavailable because LibreOffice is absent; the established Word-to-PDF path was used for page QA. No PowerPoint desktop inspection is claimed. Task-local sources, extracted assets and QA are in the project workspace `tmp/aeii-structure-deck/`. The established PPTX fallback remains in use after the earlier Spaces MXC runtime failures.

## Boundaries

The in-practice slide is explicitly a setup illustration, followed by actual recorded radar output; it is not a photo or video of a completed integrated biceps-curl study. Current acquisition and planned models remain clearly distinguished. Contactless advantages are design aims; no validated fatigue scores, predictions, clinical benefits or comparative accuracy are claimed.

Submitted poster/proposal, earlier slide and speech files, software, firmware, radar configuration and Pi setup remain unchanged. No commit or push.
