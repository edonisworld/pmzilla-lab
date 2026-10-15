"""Chaînes distinctives de history_jira.py (change jira-gdpr-alignment, tâche 2.4).

    uv run --with pyyaml --with requests python -m unittest discover -s tests/history_jira -v

Spécifications : jira-flow-labels (« Only declared labels are stored »), jira-flow-history (rien de sensible imprimé).
Un historique inventé porte des changements d'étiquette et de version corrective aux chaînes distinctives ci-dessous, et
le CSV d'entrée porte des colonnes d'étiquette déclarée et de version : aucune ne doit apparaître dans la console. Depuis le
groupe 6, le cache garde les événements de fix version (jamais l'étiquette, ici non déclarée) : la version n'est écrite que
dans le cache, nulle part ailleurs.
"""
import unittest

from test_history_jira import Base, JETON, AUTEUR, hj, dt

ETIQUETTE = "ZZDISTINCT-ETIQUETTE"
VERSION = "ZZDISTINCT-VERSION"
CLE = "ZZKEY-77"
EQUIPE = "ZZDISTINCT-EQUIPE"
FICHIER = "zzdistinct-fichier.csv"


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
        """Tickets inventés dont l'historique porte les chaînes ; CSV d'entrée avec colonnes d'étiquette et de version."""
        lignes = []
        for i in range(1, n + 1):
            cle = f"{CLE}-{i}"
            self.faux.ajouter(cle)
            ident, _ = self.faux.tickets[cle]
            self.faux.tickets[cle] = (ident, historique_avec_etiquettes(i))
            resolu = (hj.aujourd_hui() - dt.timedelta(days=30)).strftime("%d/%b/%Y") + " 10:00"
            lignes.append(f"{cle},Story,Done,{resolu},{EQUIPE},{ETIQUETTE},{VERSION}\n")
        chemin = self.ws / FICHIER
        chemin.write_text("Issue key,Issue Type,Status,Resolved,Team,Declared Label,Fix Version\n" + "".join(lignes),
                          encoding="utf-8")
        return str(chemin)

    def ecrit(self) -> str:
        """Tout ce que l'outil a écrit : le cache et les autres fichiers (le CSV d'entrée est celui du test)."""
        return self.tous_les_fichiers()

    def test_collect_n_imprime_ni_ne_garde_etiquette_version_cle_equipe_fichier(self):
        export = self.preparer()
        code, sortie = self.lancer("collect", export, "--team", EQUIPE)
        self.assertEqual(code, 0, sortie)
        cache = self.cache()
        self.assertEqual(len(cache), 4)
        for entree in cache.values():
            self.assertEqual(set(entree), {"termine", "resolu", "vu_le", "transitions", "versions"})
            self.assertEqual(len(entree["transitions"]), 2)
            self.assertEqual([e[1:] for e in entree["versions"]], [["add", VERSION]])
            for transition in entree["transitions"]:
                self.assertEqual(len(transition), 3)
        for nom, texte in (("console", sortie), ("fichiers écrits", self.ecrit())):
            for chaine in (ETIQUETTE, EQUIPE, FICHIER, "labels", "fixVersions", JETON, AUTEUR) + (
                    (VERSION,) if nom == "console" else ()):         # la version est dans le cache, et seulement là
                self.assertNotIn(chaine, texte, f"{chaine} dans {nom}")
        # Les clés sont l'index du cache (dossier de flux, hors Git) ; jamais dans la console.
        self.assertNotIn(CLE, sortie)

    def test_collect_nom_de_fichier_et_equipe_absents_de_la_console_avec_option_de_langue(self):
        export = self.preparer()
        code, sortie = self.lancer("collect", export, "--language", "en")
        self.assertEqual(code, 0, sortie)
        for chaine in (ETIQUETTE, VERSION, CLE, EQUIPE, FICHIER):
            self.assertNotIn(chaine, sortie)

    def test_check_n_imprime_ni_etiquette_ni_version_ni_cle(self):
        self.preparer(1)
        code, sortie = self.lancer("check", "--key", f"{CLE}-1")
        for chaine in (ETIQUETTE, VERSION, "labels", "fixVersions", JETON, AUTEUR):
            self.assertNotIn(chaine, sortie)
        # La clé demandée est une option explicite de l'utilisateur : le code de sortie seul est vérifié.
        self.assertIn(code, (0, 1))


if __name__ == "__main__":
    unittest.main()
