#!/bin/bash
# Run script for RAG_HS_CODE

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default app file
APP_FILE="${1:-appuiux.py}"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found!"
    echo "Please create a .env file with your OPENAI_API_KEY"
    exit 1
fi

# Check if running in conda environment
if [[ -z "$CONDA_DEFAULT_ENV" ]] || [[ "$CONDA_DEFAULT_ENV" != "rag_hs_code" ]]; then
    echo "Activating conda environment 'rag_hs_code'..."
    eval "$(conda shell.bash hook)"
    conda activate rag_hs_code
fi

echo "Starting Streamlit app: $APP_FILE"
streamlit run "$APP_FILE" --server.address localhost --server.port 8502
