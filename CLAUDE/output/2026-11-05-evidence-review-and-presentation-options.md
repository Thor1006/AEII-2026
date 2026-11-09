# Evidence review and presentation options

Date: 5 November 2026
Result: Research review and requested Git pull completed. Recommendations only for future product work.

## Recommendation

Use movement quality and the distinction between task completion and movement strategy as the main presentation argument. Keep the poster speech and live demo as the primary format, with slides as backup. Use research to explain why the question matters. Report TrueRehab-RF measurements separately from published outcomes and proposal examples.

Do not use the pasted WITHOUT/WITH comparison as a results slide. No controlled TrueRehab-RF study currently establishes improved adherence, fewer hospital visits, injury prevention or earlier compensation warnings. Do not promise neurological recovery or describe involuntary compensation as cheating.

## Claim audit

| Supplied claim | What was checked | Presentation decision |
| --- | --- | --- |
| Fatigue thresholds 55%, 70%, 65%; compensation risk 75%/82% two to three reps ahead; fatigue progression 18%, 61%, 89% | The read-only proposal explicitly introduces these as examples in sections 7, 8 and 13. Section 8 describes a profile the project will study. | Illustrative scenarios or hypotheses only. These are neither clinical thresholds nor measured accuracy or validated predictions. |
| Wrist/trunk compensation 88%, shoulder compensation 68% | Located in the ESPRM 2024 conference abstract, printed pp. 163-164, for a Box and Block task involving 31 stroke participants and 31 controls using seven IMUs. A related Sensors 2025 paper exists, but its full-text access was inconsistent. | If used, attribute these numbers to that conference cohort and task. Do not add a fatigue trigger or generalize to all patients, biceps curls or radar performance. |
| Shoulder pain 24-64% | Appears as a literature range for inpatient stroke rehabilitation in Li et al. The study itself reports 55.6% at admission among 239 included participants over age 50. | Optional clinical context with the setting and denominator. The study describes multiple possible causes, so this is not evidence that exercise compensation alone causes these cases or that our system prevents them. |
| Up to 84% shoulder pain and 65% chronic pain | The Medicina 2025 introduction cites a 5-84% literature range and approximately 65% chronicity from prior sources. Its own longitudinal sample had 28 completers. | Do not present the upper bound or background citations as that study's outcome or a universal severe-cohort prevalence. Not a priority for the main pitch. |
| 90.9% adherence, 88.2% satisfaction, 70.9% caregiver dependency | Publisher-indexed abstract found for the named rural telerehabilitation study: 110 participants, 12 weeks, adherence over 90% and 88.2% high satisfaction. Direct full-text access and the exact 90.9%/70.9% denominators were not verified. The abstract calls it observational, not a randomized trial. | At most external feasibility background. These outcomes do not transfer to our device. Leave the exact unverified values out of the presentation. |
| Over 70% do exercises incorrectly or stop; baseline adherence 35% | The named low-back-pain systematic review covers 28 studies and reports adherence spanning 8-91%, with unclear proportions fully adhering and heterogeneous definitions. | Do not combine incorrect technique and non-adherence or generalize low-back-pain findings to stroke. A defensible point is the need for objective, clearly defined measurements. |
| Wearable setup error rate 23-27% | The JMIR 2017 review describes a specific cardiac platform: four patients, 39 training sessions, ECG connection failure in 27% and blood-pressure measurement failure in 23%. | Remove the generalized claim about elderly users attaching wearables incorrectly. Measure our own setup time, calibration success and usable recording rate instead. |
| Visits reduced 50-70%, 24-36 trips, 60+ hours saved | No matching controlled effect or complete calculation was established from the supplied citations. | Exclude as achieved or expected numeric benefit. Travel savings are a future outcome to investigate, not a demonstrated result. |
| Telerehabilitation market USD 6.97 billion | Fortune Business Insights currently gives this as its 2026 estimate/forecast for the broad global telerehabilitation market. | Optional commercial appendix with year, provider and estimate label. It is not our reachable market, radar-only market or a peer-reviewed clinical result. |
| Medicare USD 77-146+ per month | CMS 2026 documents confirm RTM code changes, including musculoskeletal device supply over distinct day ranges. They do not establish this prototype's eligibility or a universal monthly payment. | Omit product revenue/reimbursement promises. A separate assessment of eligible services, providers, device requirements and applicable rates would be needed. |

PMC and ResearchGate host/distribute papers; their presence alone does not establish study quality, trial design or applicability to our device. Use publisher/repository bibliographic records and the actual methods and results.

## Ready to use presentation material

### Main message

Title: Movement completion and movement quality

- A completed repetition can involve a different movement strategy.
- Our first task is a biceps curl, with shoulder/trunk changes annotated independently.
- We will test which radar features track those changes before estimating fatigue or predicting future compensation.

Speaker addition:

“Our research question is about how a movement is completed. We are first testing whether radar measurements correspond to independently observed movement changes during biceps curls. That evidence comes before claims about fatigue prediction or recovery.”

The conceptual distinction has a clearer foundation in Levin, Kleim and Wolf's discussion of recovery and compensation than in calling patient behavior cheating. Compensation can support task performance; clinical significance depends on the person's goals and condition.

### Optional evidence line

“An IMU study presented at ESPRM found frequent wrist, trunk and shoulder compensation during a Box and Block task in a small stroke cohort. Our initial biceps-curl work tests a different task and sensor.”

Keep cohort-specific percentages in a cited appendix or Q&A if required. A simple main slide need not include them.

### Evidence status slide or poster explanation

Working: real radar acquisition and diagnostic displays; IMU recording and Wi-Fi transport tests; camera-pose preview.

Next evidence gate: simultaneous, usable recordings with correctly aligned sensor timelines and independent movement labels. MyoWare's earlier demo was tested, but its recording sketch has not run on hardware and the latest Mac Bluetooth check received no data.

Future research: compensation classification, individualized movement baselines and prospective warnings. The percentages in the proposal are illustrative.

## Project improvements in priority order

These are design recommendations, not approved implementation work. Existing recorder markers, sensor timestamps, reconnect logging and clock alignment should be reused rather than rebuilt.

1. Complete one trustworthy multimodal recording. Resolve MyoWare recording/Bluetooth, secure IMU mounting and wiring, complete the pending calibration, and record radar, sEMG, IMU and camera pose together. Verify offsets and drift. The reported 4.1-ms Wi-Fi-versus-USB difference is not validation of alignment between all sensors or end-to-end alert latency.
2. Separate reference labels. Store repetition boundaries, observable shoulder/trunk movement, perceived exertion and uncertain/unusable intervals separately. A tiredness marker is a self-report, not physiological truth. Annotated deliberate compensation should not automatically carry a fatigue label. Keep healthy-volunteer feasibility distinct from later stroke studies.
3. Add a personal movement baseline. Compare later repetitions against each person's reference movement under a fixed setup. Validate any thresholds against independent labels and avoid hardcoded 55-70% fatigue values. Radar displacement is not automatically anatomical joint range of motion. A single IMU does not by itself reconstruct every body segment.
4. Extend data-quality reporting to inference. Reuse existing loss/stale counters, then assess clipping, signal quality, target visibility, calibration and sensor disagreement. An unusable input should produce an unavailable/uncertain result rather than a reassuring score. ENV alone should not be treated as a validated fatigue percentage; verify the proposed RAW stream before spectral fatigue analysis.
5. Evaluate compensation detection before prediction. Use participant/session-held-out evaluation, precision/recall/F1 and false-alert rates, with adequate uncertainty reporting. Later evaluate warning lead time prospectively using only data available at the decision time, while reporting false warnings and missed events. Two to three reps is a testable goal, not an established capability.
6. Make the existing session summary useful for review. Candidate fields are total reps, annotated or detected quality changes, usable-data coverage and an evidence timeline. Label models and measured inputs clearly. Quantify setup burden and usability in our own study rather than borrowing adherence or visit reductions.

## Sources checked

1. Local read-only `T-Proposal-Radar (1).docx`, sections 7, 8 and 13. The example wording and numbers were extracted from OOXML without modification.
2. ESPRM 2024 proceedings, printed pp. 163-164: https://dlib.si/stream/URN%3ANBN%3ASI%3ADOC-6CW9PPXV/5ab4265c-91f4-49d8-99a8-74099688c3b3/PDF . Related official program: https://cankarjevdom.eventsair.com/QuickEventWebsitePortal/2024-esprm/programme/Agenda/AgendaItemDetail?id=95090df9-d005-4327-b341-0788f4cdff7d . Related later paper: https://www.mdpi.com/1424-8220/25/24/7609 (full-text access inconsistent; not the confirmed source for the percentages here).
3. Li et al., Frontiers in Neurology, published 12 January 2023: https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2022.1041263/full . Abstract, introduction, methods and results checked.
4. Cotellessa et al., Medicina 2025;61(3):484: https://pmc.ncbi.nlm.nih.gov/articles/PMC11944265/ . The literature-range/chronicity statements are in the introduction.
5. Rural neurological telerehabilitation study, publisher-indexed abstract: https://sjhrafrica.org/index.php/public-html/ro/article/view/2996 ; DOI https://doi.org/10.51168/r94b5e29 . Abstract text available through search; full text/denominators not verified.
6. Van Koppen et al., European Journal of Physiotherapy 2022;24(4):227-242, DOI https://doi.org/10.1080/21679169.2020.1846783 . Author institutional record: https://cris.maastrichtuniversity.nl/en/publications/adherence-to-home-based-exercises-andor-activity-advice-in-low-ba/ . Abstract checked.
7. JMIR Rehabilitation and Assistive Technologies 2017;4(2):e7: https://rehab.jmir.org/2017/2/e7/ . Table 2 and cardiac-rehabilitation text distinguish sensor failures from user placement errors.
8. Fortune Business Insights: https://www.fortunebusinessinsights.com/telerehabilitation-market-103112 . Estimate checked on 5 November 2026.
9. CMS 2026 therapy code update: https://www.cms.gov/files/document/mm14250-therapy-code-list-2026-annual-update.pdf . Code existence/day ranges do not establish prototype revenue.
10. Levin, Kleim and Wolf, Neurorehabilitation and Neural Repair 2009;23(4):313-319, DOI https://doi.org/10.1177/1545968308328727 ; abstract https://pubmed.ncbi.nlm.nih.gov/19118128/ .
11. Pulled local `recorder/README.md`, `CLAUDE/CONTEXT.md`, `firmware/myoware_record/myoware_record.ino` and the IMU Wi-Fi verification report. These distinguish tested hardware from compiled-only code and separate acquisition from inference.

## Git pull and boundaries

Requested pull fast-forwarded `main` from `660e66d` to `8e5b6db` (IMU firmware/Wi-Fi and recorder updates). Initial pull safely refused overlapping local notes. A named stash preserves the pre-pull versions of `CLAUDE/CONTEXT.md` and `CLAUDE/DECISIONS.md`. Restoring them caused two note conflicts; both were resolved by keeping incoming hardware updates and local poster-script history. The index conflict state was cleared without committing. Safety stash retained. Both local Word scripts were preserved.

No push, firmware flash, sensor command, package install, main UI change or clinical experiment. Submitted poster/proposal and current Word/PPTX deliverables remain unchanged. The user asked for research and options; changes to the live system or presentation artifacts can follow a selected scope.
