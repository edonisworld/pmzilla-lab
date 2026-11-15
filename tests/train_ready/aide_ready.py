"""Aide de la suite tests/train_ready : les dépôts jetables et les lancements de tests/train_auto/aide_auto.py (une seule aide, jamais copiée)."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "train_auto"))
from aide_auto import AUTO, READY, AvecAuto, epoch  # noqa: E402,F401
