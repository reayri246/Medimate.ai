# Handwritten OCR sample lines

These 21 crops were prepared from selected synthetic demo prescription images supplied for this project. Only handwritten line regions were retained; full-page images, printed headers, and patient-identifying fields were not copied. Very blurry or heavily overwritten pages were left out rather than turned into unreliable samples.

`candidate_transcriptions.csv` contains draft labels for review. Every row is explicitly unverified; blank draft text means the line was too ambiguous to transcribe confidently. `training_demo_unverified.csv` is the small subset used only for this experimental run, and its transcriptions are also unverified. The user approved proceeding with this sample for a demonstration, not as clinical data. Do not copy it into a production training set.

This small sample is not sufficient to train or evaluate a useful handwriting recognizer. The archive's CRNN expects one text-line image and transcription pairs; it does not locate lines on full pages. Do not use OCR output to make treatment decisions.

To repeat the experimental training run from the project root, install the optional dependencies from `requirements-crnn.txt` and run `python prescriptions/scripts/train_crnn.py --train prescriptions/sample_data/training_demo_unverified.csv --epochs 100 --out artifacts`. With the model artifacts present, run `python -m prescriptions.scripts.predict_crnn_line prescriptions/sample_data/handwritten_lines/line_001.png` to test one crop. The observed demo predictions omitted or changed medicine names and strengths. This experimental line-only recognizer is not connected to the app's full-page OCR flow.
