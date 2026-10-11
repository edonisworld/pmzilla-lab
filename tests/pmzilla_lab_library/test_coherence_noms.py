"""
Cohérence du nom de la collection « watch » (l'ancien nom « veille » n'est plus un alias).

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/pmzilla_lab_library -v

Le modèle lit CLAUDE.md et les commandes : si la règle dit `collections ["watch"]`, aucun de ces fichiers ne doit
redonner l'ancien nom de la collection à interroger. Le mot français « veille » (la pratique) reste libre.
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import pmzilla_lab_library as library  # noqa: E402
import identifiants_personnels  # noqa: E402
from watch_paths import OWN_COLLECTION  # noqa: E402

FICHIERS = ("CLAUDE.md", ".claude/commands/watch-digest.md", ".claude/commands/update-readme.md")
SANS_IDENTIFIANT = ("CLAUDE.md", ".claude/agents/pmzilla-critic.md", ".claude/commands/watch-digest.md",
                    ".claude/commands/update-readme.md")
ANCIEN = re.compile(r"collections\s*\[\s*[\"']?veille[\"']?\s*\]")


class NomDeLaCollection(unittest.TestCase):
    def test_aucun_alias_de_collection(self):
        for nom in ("COLLECTION_ALIASES", "canonical", "canonical_set", "alias_warning"):
            self.assertFalse(hasattr(library, nom), nom)

    def test_claude_md_interroge_la_collection_watch(self):
        texte = (RACINE / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn('collections ["watch"]', texte)
        self.assertIsNone(ANCIEN.search(texte), 'CLAUDE.md contient encore collections ["veille"]')

    def test_aucun_fichier_lu_par_le_modele_ne_donne_l_ancien_nom(self):
        for fichier in FICHIERS:
            texte = (RACINE / fichier).read_text(encoding="utf-8")
            self.assertIsNone(ANCIEN.search(texte), f'{fichier} contient encore collections ["veille"]')

    def test_cas_d_essai_utilisent_le_nouveau_nom(self):
        for fichier in ("tests/postures/cas.yaml", "tests/postures/cas-commandes.yaml"):
            texte = (RACINE / fichier).read_text(encoding="utf-8")
            self.assertNotRegex(texte, r"collections?:\s*\[?veille\b", f"{fichier} cite encore la collection veille")

    def test_agent_critic_nomme_la_collection_personnelle(self):
        texte = (RACINE / ".claude/agents/pmzilla-critic.md").read_text(encoding="utf-8")
        self.assertIn(f"`{OWN_COLLECTION}` collection", texte)

    def test_watch_digest_nomme_la_collection_personnelle(self):
        texte = (RACINE / ".claude/commands/watch-digest.md").read_text(encoding="utf-8")
        self.assertIn(f'collections ["{OWN_COLLECTION}"]', texte)
        self.assertIn(f"Watch-Lab/{OWN_COLLECTION}/", texte)

    def test_aucun_identifiant_personnel_dans_les_fichiers_lus_par_le_modele(self):
        identifiants = identifiants_personnels.identifiants(RACINE)
        for fichier in SANS_IDENTIFIANT:
            texte = (RACINE / fichier).read_text(encoding="utf-8").lower()
            self.assertFalse(any(i in texte for i in identifiants), f"{fichier} contient un identifiant personnel")


if __name__ == "__main__":
    unittest.main()
