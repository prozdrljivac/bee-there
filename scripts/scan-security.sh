#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root. Keep the complete report before applying the gate.
scan_type="$1"
target="$2"
report="$3"
scanners='vuln,misconfig,secret'
set --
if [[ "$scan_type" == image ]]; then
  scanners='vuln,secret'
else
  # Filesystem-only exclusions must not hide installed packages in images.
  skip_dirs='.git,**/.venv,**/node_modules,**/.cache,**/.pytest_cache'
  skip_dirs+=',**/.mypy_cache,**/.ruff_cache,**/__pycache__,graphify-out'
  skip_dirs+=',.trivy-reports,**/dist,**/release'
  set -- --skip-dirs "$skip_dirs"
fi

mkdir -p "$(dirname "$report")"
trivy "$scan_type" --config trivy.yaml --scanners "$scanners" "$@" \
  --format json --exit-code 0 --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
  --output "$report" "$target"
trivy convert --config trivy.yaml --format table --scanners "$scanners" \
  --severity HIGH,CRITICAL --exit-code 1 "$report"
