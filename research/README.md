# Research workspace

This directory is for experiment plans, evaluation scripts, and results. Keep identifiable images, face embeddings, credentials, and private datasets out of Git. Record dataset provenance, consent, preprocessing, model and weight versions, threshold selection, and the exact split used for every result.

## Evaluation protocol (to be completed before reporting results)

1. Define the intended research question and permitted use. This prototype must not make consequential decisions.
2. Obtain documented consent and approval for any dataset containing biometric data. Use a held-out test set with no identity overlap across enrollment and evaluation splits where appropriate.
3. Record image quality, pose, lighting, and demographic coverage without exposing identities.
4. Select the cosine-distance threshold on a validation split only. Report false acceptance and false rejection rates, precision, recall, confidence intervals, and subgroup results when sample sizes support them.
5. Preserve a reproducible environment and model-weight provenance. Do not report demo outputs as accuracy.

No evaluation results are currently available.
