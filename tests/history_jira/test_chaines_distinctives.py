"""Chaînes distinctives de history_jira.py (change jira-gdpr-alignment, tâche 2.4 ; change database-only).

    uv run --with pyyaml --with requests --with "psycopg[binary]" python -m unittest discover -s tests/history_jira -v

Spécifications : jira-flow-labels (« Only declared labels are stored »), jira-flow-history (rien de sensible imprimé).
Un historique inventé porte des changements d'étiquette et de version corrective aux chaînes distinctives ci-dessous, et les tickets de la
base fictive portent une équipe et une clé distinctives : aucune ne doit apparaître dans la console. La version n'est écrite que dans les
périodes de versions de la base (jamais l'étiquette, ici non déclarée), nulle part ailleurs ; aucun fichier n'est écrit.
"""
import unittest

from test_history_jira import AUTEUR, JETON, Base

ETIQUETTE = "ZZDISTINCT-ETIQUETTE"
VERSION = "ZZDISTINCT-VERSION"
CLE = "ZZKEY-77"
EQUIPE = "ZZDISTINCT-EQUIPE"


def historique_avec_etiquettes(i: int) -> list[dict]:
    """Deux transitions de statut, un ajout et un retrait d'étiquette, un changement de version corrective."""
    base = f"2026-0{1 + i % 8}-10T09:00:00.000+0200"
    return [
        {"id": f"{i}1", "created": base, "author": {"displayName": AUTEUR},
         "items": [{"field": "status", "fieldId": "status", "fromString": "Open", "toString": "In Progress"},
                   {"field": "labels", "fieldId": "labels", "fromString": None, "toString": ETIQUETTE},
                   {"field": "Fix Version", "fieldId": "fixVersions", "fromString": None, "toString": VERSION}]},
        {"id": f"{i}2", "created": base.replace("T09", "T15"), "author": {"displayName": AUTEUR},
         "items": [{"field": "status", "fieldId": "status", "fromString": "In Progress", "toString": "Done"},
                   {"field": "labels", "fieldId": "labels", "fromString": ETIQUETTE, "toString": None}]},
    ]


class ChainesDistinctives(Base):
    def preparer(self, n: int = 4):
        """Tickets inventés dont l'historique porte les chaînes ; les mêmes tickets sont dans la base fictive."""
        lignes = []
        for i in range(1, n + 1):
            cle = f"{CLE}-{i}"
            self.faux.ajouter(cle)
            ident, _ = self.faux.tickets[cle]
            self.faux.tickets[cle] = (ident, historique_avec_etiquettes(i))
            self.faux.courantes[cle] = {"fixVersions": [VERSION], "labels": [ETIQUETTE]}
            lignes.append((cle, "Story", EQUIPE, True))
        self.ecrire_export(lignes)

    def ecrit(self) -> str:
        """Tout ce que l'outil a écrit : la base fictive et les fichiers (il n'y en a aucun)."""
        return self.tous_les_fichiers() + repr(self.magasin.transitions) + repr(self.magasin.periodes)

    def test_collect_n_imprime_ni_ne_garde_etiquette_non_declaree_equipe_cle_fichier(self):
        self.preparer()
        code, sortie = self.lancer("collect", "--team", EQUIPE)
        self.assertEqual(code, 0, sortie)
        cache = self.cache()
        self.assertEqual(len(cache), 4)
        for entree in cache.values():
            self.assertEqual(set(entree), {"transitions"})
            self.assertEqual(len(entree["transitions"]), 2)
            for transition in entree["transitions"]:
                self.assertEqual(len(transition), 3)
        self.assertEqual(self.magasin.periodes["etiquettes"], {})                    # étiquette non déclarée : jamais gardée
        for cle in cache:
            self.assertEqual([valeur for valeur, _ in self.magasin.periodes["versions"][cle]], [VERSION])
        for nom, texte in (("console", sortie), ("base fictive et fichiers", self.ecrit())):
            for chaine in (ETIQUETTE, "labels", "fixVersions", JETON, AUTEUR) + ((VERSION, EQUIPE) if nom == "console" else ()):
                self.assertNotIn(chaine, texte, f"{chaine} dans {nom}")
        self.assertNotIn(CLE, sortie)                                               # les clés ne sortent pas dans la console

    def test_collect_equipe_et_cle_absents_de_la_console_avec_option_de_langue(self):
        self.preparer()
        code, sortie = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, sortie)
        for chaine in (ETIQUETTE, VERSION, CLE, EQUIPE):
            self.assertNotIn(chaine, sortie)

    def test_check_n_imprime_ni_etiquette_ni_version_ni_cle(self):
        self.preparer(1)
        self.lancer("collect")
        code, sortie = self.lancer("check")
        for chaine in (ETIQUETTE, VERSION, "labels", "fixVersions", JETON, AUTEUR, CLE, EQUIPE):
            self.assertNotIn(chaine, sortie)
        self.assertEqual(code, 0, sortie)


if __name__ == "__main__":
    unittest.main()
