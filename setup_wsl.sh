#!/bin/bash
# Setup script for RAG_HS_CODE on WSL Ubuntu with Conda

set -e

echo "=== RAG HS Code Setup for WSL Ubuntu ==="

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Error: conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_NAME="rag_hs_code"

# Check if environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Environment '$ENV_NAME' already exists."
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Updating environment..."
        conda env update -f environment.yml --prune
    fi
else
    echo "Creating conda environment '$ENV_NAME'..."
    conda env create -f environment.yml
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To activate the environment, run:"
echo "  conda activate $ENV_NAME"
echo ""
echo "To run the application, use:"
echo "  ./run.sh"
echo "  # or: streamlit run appuiux.py"
echo ""
echo "Make sure your .env file contains your OPENAI_API_KEY"
