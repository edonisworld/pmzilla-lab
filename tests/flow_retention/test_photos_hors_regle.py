"""
Photos de qualité par version hors règle de conservation (change version-quality-photo, tâche 1.5 ; spec jira-flow-retention « Version
quality photos outside the rule »). Fausse connexion : aucun PostgreSQL. Le test avec base est dans test_base.py (PhotosHorsRegle).

Les cinq tables du magasin ne portent ni clé ni personne : le contrôle ne les compte pas et la purge ne les supprime pas, quel que soit leur
âge. Aucune requête de l'outil ne les nomme.
"""
import re
import unittest
from pathlib import Path

from aide_flow_retention import AUJOURDHUI, Espace, FausseBase, fr

TABLES_PHOTO = ("version_photo_versions", "version_photo_runs", "version_photo_weeks", "version_photo_rows", "version_photo_n")


class PhotosHorsRegle(Espace):
    def test_le_controle_et_la_purge_ne_nomment_aucune_table_de_photo(self):
        base = FausseBase(compte=3, plus_ancien=AUJOURDHUI, brute=1, visites=1)
        self.sauvegarde(AUJOURDHUI)
        self.lancer("check", base=base)
        self.lancer("purge", "--apply", base=base)
        for requete, _ in base.requetes:
            self.assertNotIn("version_photo", requete)

    def test_le_texte_de_l_outil_ne_cite_aucune_table_de_photo_dans_ses_requetes(self):
        source = Path(fr.__file__).read_text(encoding="utf-8")
        code = re.sub(r"#[^\n]*", "", source.split('"""', 2)[2])           # sans le texte d'en-tête ni les commentaires
        for table in TABLES_PHOTO:
            self.assertNotIn(table, code)


if __name__ == "__main__":
    unittest.main()
