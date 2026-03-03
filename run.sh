#!/bin/bash
# Activate wing_sizer conda env and run processor
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate wing_sizer
python "$SCRIPT_DIR/image_processor.py"
