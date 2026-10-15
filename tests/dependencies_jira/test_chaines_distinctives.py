"""Chaînes distinctives de dependencies_jira.py (change jira-gdpr-alignment, tâche 2.4).

    uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira -v

Spécification : jira-flow-dependencies (« Labels and versions absent from the dependency report »), scénario « Keys option ».
L'export porte une étiquette déclarée et une version corrective distinctives (colonnes « Declared Label » et « Fix Version »),
des clés et une équipe distinctives, dans un fichier au nom distinctif. Ni l'étiquette ni la version ne paraissent dans la
console (diagnose, compute, compute --keys), le diagnostic, les rapports Markdown et JSON. Autorisé aujourd'hui et donc non
interdit : les équipes dans les rapports du dossier de flux, les clés dans la console avec --keys seulement (jamais dans les
rapports). Le code actuel ne lit pas les colonnes d'étiquette et de version : le test verrouille la régression.
"""
import csv

from test_dependencies_jira import Base, ecrire_manuel, t

ETIQUETTE = "ZZDISTINCT-ETIQUETTE"
VERSION = "ZZDISTINCT-VERSION"
EQUIPE_1 = "ZZDISTINCT-EQUIPE-1"
EQUIPE_2 = "ZZDISTINCT-EQUIPE-2"
FICHIER = "zzdistinct-fichier.csv"

TICKETS = [t("ZZKEY-1", EQUIPE_1, sortants=["ZZKEY-2"]),
           t("ZZKEY-2", EQUIPE_2, entrants=["ZZKEY-1"]),
           t("ZZKEY-3", EQUIPE_2, etat="Open", cat="To Do", sortants=["ZZKEY-4"]),
           t("ZZKEY-4", EQUIPE_1, entrants=["ZZKEY-3"])]


class ChainesDistinctives(Base):
    def export(self) -> str:
        """Le CSV manuel des tickets, complété des colonnes d'étiquette déclarée et de version corrective."""
        chemin = self.ws / FICHIER
        ecrire_manuel(chemin, TICKETS)
        with chemin.open(encoding="utf-8", newline="") as f:
            lignes = list(csv.reader(f))
        lignes[0] += ["Declared Label", "Fix Version"]
        for ligne in lignes[1:]:
            ligne += [ETIQUETTE, VERSION]
        with chemin.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(lignes)
        return str(chemin)

    def fichiers_ecrits(self) -> dict[str, str]:
        return {p.name: p.read_text(encoding="utf-8", errors="ignore") for p in self.ws.rglob("*")
                if p.is_file() and p.name not in (FICHIER, "flux.yaml")}

    def test_rien_d_etiquette_ni_de_version_en_console_ni_dans_les_rapports(self):
        export = self.export()
        sorties = {"diagnose": self.lancer("diagnose", export),
                   "compute": self.lancer("compute", export, "--name", "zz"),
                   "compute --keys": self.lancer("compute", export, "--name", "zzk", "--keys")}
        ecrits = self.fichiers_ecrits()
        self.assertTrue(any(nom.endswith(".md") for nom in ecrits), list(ecrits))
        self.assertTrue(any(nom.endswith(".json") for nom in ecrits), list(ecrits))
        for nom, texte in {**sorties, **ecrits}.items():
            for chaine in (ETIQUETTE, VERSION, "Declared Label", "Fix Version"):
                self.assertNotIn(chaine, texte, f"{chaine} dans {nom}")

    def test_option_cles_lignes_de_cles_equipes_et_etats_seulement(self):
        export = self.export()
        sortie = self.lancer("compute", export, "--name", "zzk", "--keys")
        self.assertIn(f"ZZKEY-2 ({EQUIPE_2}) attend ZZKEY-1 ({EQUIPE_1}, en cours)", sortie)
        for chaine in (ETIQUETTE, VERSION):
            self.assertNotIn(chaine, sortie)
        # Les clés restent dans le Terminal : jamais dans les rapports écrits.
        for nom, texte in self.fichiers_ecrits().items():
            self.assertNotIn("ZZKEY-", texte, nom)

    def test_sans_option_cles_aucune_cle_en_console(self):
        sortie = self.lancer("compute", self.export(), "--name", "zz")
        self.assertNotIn("ZZKEY-", sortie)
        self.assertNotIn(FICHIER, sortie.replace(str(self.ws), ""))


if __name__ == "__main__":
    unittest.main()
