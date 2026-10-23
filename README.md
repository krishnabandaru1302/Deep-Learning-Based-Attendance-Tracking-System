# Deep Learning-Based Attendance Tracking System

A Google Colab prototype that detects faces in enrollment images, represents them with a pretrained VGGFace model, and matches faces from an uploaded image to mark attendance in an Excel workbook.

> **Status:** research/learning prototype. The repository does not include a benchmark, validation protocol, or measured accuracy. Do not use it as the sole basis for real attendance or other consequential decisions.

## How it works

The main implementation is the [AAS_v3 notebook](AAS_v3.ipynb).

1. Enrollment images are read from `Students/`; a Haar cascade detects faces and the notebook saves face crops under `group_of_faces/`.
2. A VGGFace network loaded with pretrained weights produces a descriptor for each enrolled face.
3. The notebook asks the operator to upload an image. It detects faces and compares their descriptors with enrolled descriptors using cosine distance.
4. Matches are annotated in the output image and written with a timestamp to `Attendance_Sheet.xlsx`.

The notebook uses a distance cutoff of 0.35. This value is an implementation setting, not a validated operating threshold; performance can vary with image quality, pose, lighting, and the people represented in the enrollment images.

## Run in Google Colab

This project is currently organized as a Colab notebook and depends on files and paths that are not fully configured for a clean local install.

1. Open [AAS_v3.ipynb](AAS_v3.ipynb) in Google Colab.
2. Place the repository files in Google Drive under `My Drive/Projects/Automated Attendance System`, matching the path used by the notebook, or update the working-directory cell to match your own location.
3. Add consented enrollment images to the notebook's `Students/` directory. The notebook expects the Haar cascade XML files in its working directory.
4. Run the cells in order. The notebook installs `keras_vggface` and downloads the VGGFace weights using the Kaggle CLI. Configure Kaggle credentials through a secure Colab secret or the official Kaggle setup; never commit API keys to the notebook or repository.
5. Upload a test image when prompted. The notebook writes the annotated image and attendance workbook to its current working directory.

The notebook was authored for Google Colab. Its dependencies are not pinned, and compatibility with current Colab runtimes has not been established. A local, reproducible installation workflow is not currently provided.

## Repository contents

- `AAS_v3.ipynb` — end-to-end Colab notebook
- Haar cascade XML files — face detection resources used by the notebook
- `README.md` — project overview and usage notes

## Limitations and responsible use

- This is a prototype, not a production attendance system. It has no documented test set, accuracy measurements, false-match analysis, or fairness evaluation.
- The notebook uses a fixed cosine-distance cutoff. Validate and document any threshold against representative, consented data before drawing conclusions.
- Face images and face descriptors are sensitive biometric data. Obtain informed consent, restrict access, define retention and deletion practices, and avoid uploading identifiable images to services without authorization.
- Provide a non-biometric attendance alternative and human review for any consequential decision.
- The current workflow is Colab-centered and includes a hard-coded Drive path. It needs configuration, dependency pinning, and error handling before it can be considered reproducible.

## Research notes

To make this project suitable for research evaluation, document the enrollment and test protocol, dataset provenance and consent, preprocessing choices, threshold selection, and metrics such as precision, recall, false acceptance rate, and false rejection rate. Report results on a held-out evaluation set; do not infer accuracy from a successful demo run.

## License

No license file is currently documented in this repository. Add a license before inviting reuse or contributions.
