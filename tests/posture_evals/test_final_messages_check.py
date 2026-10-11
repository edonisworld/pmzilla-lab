"""tools/final_messages_check.py : comptage, sans modèle, des séances à plusieurs messages finaux."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import final_messages_check as mesure  # noqa: E402


def ecrire(chemin: Path, evenements: list) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(json.dumps(e) for e in evenements), encoding="utf-8")


def texte(t, parent=None):
    return {"type": "assistant", "parent_tool_use_id": parent, "message": {"content": [{"type": "text", "text": t}]}}


class Mesure(unittest.TestCase):
    def test_compte_les_seances_a_un_et_a_plusieurs_messages(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d)
            ecrire(data / "2026-10-01-000000" / "cas-a.jsonl", [texte("seul"), {"type": "result", "result": "seul"}])
            ecrire(data / "2026-10-02-000000" / "cas-a.jsonl",
                   [texte("analyse"), {"type": "result", "result": "analyse"}, texte("critic"),
                    {"type": "result", "result": "critic"}])
            ecrire(data / "2026-10-02-000000" / "cas-a.rejeu1.jsonl", [texte("x"), {"type": "result", "result": "x"}])
            comptes, plusieurs = mesure.measure(data)
        self.assertEqual(dict(comptes), {"cas-a": [1, 1]})              # le rejeu n'est pas compté
        self.assertEqual(dict(plusieurs), {"cas-a": ["2026-10-02-000000"]})


class SortieDeLEntreePrincipale(unittest.TestCase):
    """main() sur des traces temporaires : option par cas, liste des passages, part en pourcentage, message vide."""

    @staticmethod
    def lancer(data: Path, *options: str) -> str:
        import contextlib
        import io
        from unittest import mock
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["final_messages_check.py", "--data", str(data), *options]), \
                contextlib.redirect_stdout(sortie):
            mesure.main()
        return sortie.getvalue()

    @staticmethod
    def traces(data: Path) -> None:
        un = [texte("seul"), {"type": "result", "result": "seul"}]
        deux = [texte("analyse"), {"type": "result", "result": "analyse"}, texte("critic"),
                {"type": "result", "result": "critic"}]
        ecrire(data / "2026-10-01-000000" / "cas-a.jsonl", un)
        ecrire(data / "2026-10-02-000000" / "cas-a.jsonl", deux)
        ecrire(data / "2026-10-01-000000" / "cas-b.jsonl", un)
        ecrire(data / "2026-10-03-000000" / "cas-b.jsonl", un)

    def test_part_en_pourcentage_et_totaux(self):
        with tempfile.TemporaryDirectory() as d:
            self.traces(Path(d))
            sortie = self.lancer(Path(d))
        self.assertIn("25.0 % de séances à plusieurs messages", sortie)     # 1 séance sur 4
        self.assertRegex(sortie, r"TOTAL\s+3\s+1")
        self.assertNotIn("2026-10-02-000000", sortie)                         # sans --list, pas de passage nommé

    def test_option_par_cas(self):
        with tempfile.TemporaryDirectory() as d:
            self.traces(Path(d))
            sortie = self.lancer(Path(d), "--case", "cas-b")
        self.assertNotIn("cas-a", sortie)
        self.assertIn("0.0 %", sortie)

    def test_liste_des_passages_concernes(self):
        with tempfile.TemporaryDirectory() as d:
            self.traces(Path(d))
            sortie = self.lancer(Path(d), "--list")
        self.assertIn("cas-a : 2026-10-02-000000", sortie)
        self.assertNotIn("cas-b :", sortie)

    def test_aucune_trace(self):
        with tempfile.TemporaryDirectory() as d:
            sortie = self.lancer(Path(d))
        self.assertEqual(sortie.strip(), "Aucune trace trouvée.")


if __name__ == "__main__":
    unittest.main()
