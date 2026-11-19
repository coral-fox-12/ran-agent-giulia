#!/usr/bin/env bash
# Clone the upstream Giulia simulator (open source, UPV) next to this repo.
# The simulator itself is NOT vendored: keep it as a separate checkout so
# upstream updates stay clean. Real runs additionally need the 2.7 GB
# shadowing .mat files (UPV-network-only download — see docs/RESEARCH.md §7).
set -euo pipefail
cd "$(dirname "$0")"
if [ -d giulia ]; then
  echo "giulia/ already exists — pulling latest (depth 1)..."
  git -C giulia pull --depth 1 || echo "pull failed (offline?); keeping existing checkout"
else
  git clone --depth 1 https://github.com/giulia-open-lab/OpenGiuliaSLS.git giulia
fi
echo "Giulia checkout ready at ./giulia"
ls giulia | head -20
