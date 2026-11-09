# Clinical and public datasets for TrueRehab RF

Reviewed 9 November 2026. Purpose: reusable data for algorithm development and clinical evidence for the AEII presentation.

Start with the University of Minho fatigue dataset for sEMG analysis, and the Don Carlo Gnocchi dataset for real post-stroke movement examples. Toronto Rehab is particularly relevant to compensation labels. These sources do not supply the synchronized radar recordings required by the current radar-only network.

## What the repository needs

`model/README.md`, `model/trnet/contract.py` and `model/trnet/labels.py` describe an untrained radar-only network. Contract v1 expects per-frame H `[4,64,32]` (angle magnitude, phase change, point height and presence) and D `[1,64,16]`, with 128 frames per repetition. Its fatigue target rescales a 20% sEMG median-frequency drop to 1.0; shrug 2 cm, lean 10 degrees, ROM 80% of baseline and the three-repetition risk horizon are explicitly placeholders.

External EMG, skeleton or IMU recordings can support separate reference models, signal-processing checks and label design. They cannot become measured radar input merely by reshaping arrays. Training the existing network still needs radar and independent reference measurements from the same participants and repetitions. Any simulated radar derived from motion must retain its synthetic status and cannot establish clinical performance.

## Priority datasets

| Priority | Source and participants | Available measurements and labels | Fit for this project | Access and reuse |
|---|---|---|---|---|
| 1, exercise fatigue | University of Minho: 13 healthy adults, 12 dynamic upper-limb movements, 13 h 20 min | Raw sEMG at 1,259 Hz; timestamped self-perceived fatigue at 50 Hz, levels 0–2; MVC recordings and protocol | Check sEMG processing and agreement with independent perceived-fatigue labels. Downloaded protocol identifies Trial 5 as right biceps and Trial 6 as left biceps | [Zenodo v2](https://zenodo.org/records/14182446); CC BY 4.0 verified in its API metadata. Full archive is about 3.3 GB; the raw sEMG archive has not been downloaded |
| 2, real clinical movement | IRCCS Fondazione Don Carlo Gnocchi, Milan: 10 post-stroke and 10 healthy participants, six functional tasks | Joint/marker kinematics and 12-muscle sEMG, including biceps; MATLAB files. Motion 125 Hz, EMG 1,000 Hz | Clinical reference examples and joint-motion/sEMG comparisons. The tasks are functional activities, not a fatigue-labelled dumbbell-curl study | [Figshare collection](https://doi.org/10.6084/m9.figshare.c.7720187.v1); CC BY 4.0 verified on the ST03 record. One original patient file downloaded |
| 3, compensation | Toronto Rehab: 9 stroke survivors and 10 healthy participants using a rehabilitation robot | Kinect v2 25-joint coordinates, frame-level posture ratings, participant demographics | Develop/evaluate a separate pose-based compensation reference. Robotic reaching differs from our standing curls | [Author repository](https://github.com/zhiderek/TRSPD) links the [Kaggle dataset](https://www.kaggle.com/datasets/derekdb/toronto-robot-stroke-posture-dataset). Dataset license and current download access need verification before importing |
| 4, larger patient cohort | REHAB: 120 enrolled post-stroke patients from two hospitals in China | Wearable IMU/flex-sensor kinematics, 27 assessment movements, 16 training movements, therapist-scored assessment labels; NumPy files | Separate clinical movement/assessment research. Fugl-Meyer-derived task scores are not fatigue or imminent-compensation labels | [Dataset DOI](https://doi.org/10.57760/sciencedb.37018), [ScienceDB](https://www.scidb.cn/en/s/YrUnie), [paper](https://doi.org/10.1038/s41597-026-07802-2). Paper states public availability; the current dataset license/download package was not independently verified |
| Reserve, isometric fatigue | Biceps Muscular Failure sEMG Dataset: 12 trained men, 192 recordings | sEMG at 2,000 Hz during 50%-MVIC isometric elbow holds to failure | Alternate EMG/failure benchmark. Static holds and mechanical failure differ from dynamic curls, perceived fatigue and compensation | [Mendeley Data](https://data.mendeley.com/datasets/5mhj643jtf/1); CC BY 4.0 shown on the repository page. No files imported |

Clinical source: [Lucchetti et al., Scientific Data, 2025](https://www.nature.com/articles/s41597-025-06174-3.pdf). Fatigue source: [Cerqueira et al., Sensors, 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11678945/). Toronto source: [Dolatabadi et al., dataset paper](https://eudl.eu/doi/10.1145/3154862.3154925).

The article license and dataset license can differ. The Italy and Minho **dataset** licenses were verified directly; do not infer another dataset's terms from its paper. REHAB contains repeated assessments, so a future clinical model must split by patient, keeping pre/post recordings together, rather than randomly dividing recordings. Preserve subject-group splits for all datasets.

## Local sample files

Original data are in `model/data/external_reference_v01/`, an already git-ignored data location. Keep them separate from the project's recorder sessions.

- `ST03.mat`: one published de-identified post-stroke participant from [Figshare ST03](https://figshare.com/articles/dataset/ST_03/28596086), 51,687,920 bytes. MD5 `9bf584b5e8a67548c54d36a053b56910`. Original checksum matches; MATLAB v5 header verified. Numerical signals have not yet been decoded or evaluated.
- `protocol.xlsx`: original Minho protocol, 1,094,424 bytes. MD5 `1da11ab1e8211615c7d2e9bf73e9cad4`. Workbook contents inspected as data, not executed.
- `self_perceived_fatigue_index.zip`: original Minho fatigue-label archive, 5,140,559 bytes. MD5 `3352c990b2baf2246cfa7b331e52607a`. It contains 13 nested subject ZIPs. Subject 1 contains 12 trial CSVs; inspected header is `time,label`, with 0.02-second initial increments. The paired raw EMG is in the separate 3.3-GB archive; labels alone cannot train an EMG classifier.
- `zenodo-v2.json`, `figshare-st03.json`, `download-manifest_v01.json` and `dataset-sources_v01.json` retain provenance, licenses, source links and checksums.

Credit clinical data to Lucchetti, Bailo and Lencioni / Fondazione Don Carlo Gnocchi, collection DOI 10.6084/m9.figshare.c.7720187.v1, ST03 DOI 10.6084/m9.figshare.28596086.v1. Credit fatigue data to Cerqueira, Vilas-Boas, Figueiredo and Santos / University of Minho, DOI 10.5281/zenodo.14182446. Both downloaded datasets use [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the sample bytes were not modified.

## Evidence suitable for the presentation

1. **Fatigue can change shoulder movement during a curl.** A study of 12 healthy men combined eight-channel sEMG and optical motion capture and observed increased shoulder involvement under fatigue. This directly motivates observing more than elbow repetitions. It is a healthy-volunteer study, not proof in stroke patients or proof that radar detects fatigue. [Chua et al., 2024](https://arxiv.org/html/2402.11421v1).
2. **Recovery assessment needs movement quality as well as completion.** Toronto Rehab provides expert-annotated compensatory postures during robotic rehabilitation, supporting the relevance of compensation-aware assessment. Its sample cannot establish a general percentage of all patients who compensate. [Dataset paper](https://eudl.eu/doi/10.1145/3154862.3154925).
3. **Home exercise needs an individual plan and professional oversight.** NICE recommends repetitive upper-limb task practice and says independently continued programmes should be safe and tailored to individual needs; rehabilitation sessions should account for fatigue. This supports the intended role of feedback alongside clinicians. It does not prove our product speeds recovery or prevents injuries. [NICE NG236, 1.2.19 and 1.13.7–1.13.8, 1.13.20](https://www.nice.org.uk/guidance/ng236/chapter/Recommendations).

Suggested slide wording, as paraphrases:

- “Fatigue can shift movement toward the shoulder, even while the exercise continues.”
- “Movement quality adds information beyond repetition count.”
- “Our goal is feedback during prescribed home exercises, alongside professional care.”

These are proposed additions to the editable presentation, not edits to the submitted poster or existing slides.

## Project changes worth considering

- **Use an independent fatigue label.** Record time-stamped perceived exertion at agreed points alongside sEMG, with a physiotherapist reviewing the interpretation. Benchmark the MDF indicator against those labels. Minho's 0–2 scale, another study's Borg rating and our 0–1 MDF score are distinct quantities.
- **Review the 20% MDF rule before calling the display “fatigue percent.”** It is currently a chosen rescaling. The 12-person curl study reported MDF reductions across muscles of about 0.50–7.01%, with the biceps comparison not reaching its 0.05 significance criterion (p=0.054). That finding does not establish a replacement threshold, but it cautions against assuming all fatigued curls must cross 20%. [Study results, IV-A](https://arxiv.org/html/2402.11421v1).
- **Keep compensation labels independently observable.** Use pose/clinician labels for shoulder and trunk deviations, with missing labels masked. Do not use healthy isometric failure recordings as evidence that our next-three-repetition compensation prediction works.
- **Keep the clinical constructs separate.** Acute exercise-related fatigue, mechanical failure, movement compensation, Fugl-Meyer motor function and longer-term post-stroke fatigue measure different things. NICE's fatigue scales assess a broader clinical condition; they are not per-repetition radar labels.
- **Collect the paired radar data next.** External sets can establish reference baselines, but our main claim needs synchronized radar and reference measurements on curls, then evaluation on people excluded from training. Only actual held-out recordings can establish performance.

No training, threshold changes, patient recruitment, firmware updates, poster edits, presentation edits, commit or push was performed. This is a dataset/evidence review with a small local reference collection.
