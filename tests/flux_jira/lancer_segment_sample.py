# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "numpy", "requests", "psycopg[binary]"]
# ///
"""Lance tools/segment_sample.py sur des fixtures CSV, sans base (tests seulement : voir lanceur_csv.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lanceur_csv  # noqa: E402

lanceur_csv.executer("segment_sample", sys.argv[1:])
