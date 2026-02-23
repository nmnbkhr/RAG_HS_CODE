#!/bin/bash
# Japan Customs HS Code Calculator - Standalone Launcher
# Runs independently from Pakistan app (PK=8502, JP=8503)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create japan/data directory if missing
mkdir -p japan/data

# Check if running in conda environment
if [[ -z "$CONDA_DEFAULT_ENV" ]] || [[ "$CONDA_DEFAULT_ENV" != "rag_hs_code" ]]; then
    echo "Activating conda environment 'rag_hs_code'..."
    eval "$(conda shell.bash hook)"
    conda activate rag_hs_code
fi

echo "Starting Japan Customs Calculator on port 8503..."
streamlit run app_japan.py --server.address localhost --server.port 8503
