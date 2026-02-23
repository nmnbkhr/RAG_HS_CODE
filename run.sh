#!/bin/bash
# Run script for RAG_HS_CODE

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default app file
APP_FILE="${1:-app_integrated.py}"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found!"
    echo "Please create a .env file with your OPENAI_API_KEY"
    exit 1
fi

# Always activate rag_hs_code (deactivate any other env first)
eval "$(conda shell.bash hook)"
conda deactivate 2>/dev/null
conda activate rag_hs_code

echo "Using env: $CONDA_DEFAULT_ENV ($(python --version))"
echo "Starting Streamlit app: $APP_FILE"
streamlit run "$APP_FILE" --server.address localhost --server.port 8502
