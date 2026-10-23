#!/usr/bin/env bash
set -euo pipefail

if ! command -v kaggle >/dev/null 2>&1; then
  echo "Kaggle CLI is required. Install it with: python -m pip install kaggle" >&2
  exit 1
fi
mkdir -p models
kaggle datasets download -d acharyarupak391/vggfaceweights --unzip -p models

target="models/vgg_face_weights.h5"
if [[ ! -f "$target" ]]; then
  candidate="$(find models -type f -iname '*weights*.h5' -print -quit)"
  if [[ -z "$candidate" ]]; then
    echo "No HDF5 weights file found. Check the Kaggle dataset contents." >&2
    exit 1
  fi
  mv "$candidate" "$target"
fi
echo "Model weights ready at $target"
