"""Rapport de dépendances par Mission Team ou par site (change jira-gdpr-alignment, tâche 9.2).

    uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira -v

Specs : jira-flow-dependencies (« Aggregation by Mission Team or site »), jira-flow-organisation (« Reports by Mission Team
and by site », « Headcount describes the structure only », « Names stay in the flow folder »). Données inventées : trois
équipes de deux Mission Teams (et de deux sites), une quatrième équipe absente du référentiel, des effectifs distinctifs.
La voie base est exercée en direct avec un faux flow_store qui rend les données du CSV : le calcul est le même code.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from test_dependencies_jira import AUJOURDHUI, Base, t

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.append(str(Path(__file__).resolve().parents[2] / "tests" / "flux_jira"))      # à la fin : test_language existe aussi là-bas
import chargeur_csv as chargeur  # noqa: E402
import dependencies_jira as dj  # noqa: E402

REFERENTIEL = """source_date: 2026-10-01
sites: [Site-Zorblax, Site-Quimbo]
departments:
  - name: Dept-Wumpa
    site: Site-Zorblax
    headcount: 9100
    mission_teams:
      - name: MT-Frobnic
        teams: [Eq-Alpha, Eq-Beta]
  - name: Dept-Autre
    site: Site-Quimbo
    headcount: 9200
    mission_teams:
      - name: MT-Plinth
        teams: [Eq-Gamma]
teams:
  - name: Eq-Alpha
    headcount: 4101
  - name: Eq-Beta
    headcount: 4202
  - name: Eq-Gamma
    headcount: 4303
"""

NOMS = ["Eq-Alpha", "Eq-Beta", "Eq-Gamma", "MT-Frobnic", "MT-Plinth", "Site-Zorblax", "Site-Quimbo", "Eq-Delta"]

TICKETS = [
    t("AAA-1", "Eq-Alpha", sortants=["BBB-1"]),                         # interne à MT-Frobnic (Alpha bloque Beta)
    t("BBB-1", "Eq-Beta", entrants=["AAA-1"]),
    t("GGG-1", "Eq-Gamma", etat="Open", cat="To Do", sortants=["BBB-2"]),   # Beta attend Gamma
    t("BBB-2", "Eq-Beta", entrants=["GGG-1"]),
    t("AAA-2", "Eq-Alpha", sortants=["GGG-2"]),                         # Gamma attend Alpha
    t("GGG-2", "Eq-Gamma", entrants=["AAA-2"]),
    t("DDD-1", "Eq-Delta", sortants=["BBB-3"]),                         # Beta attend une équipe hors référentiel
    t("BBB-3", "Eq-Beta", entrants=["DDD-1"]),
]


class ParGroupe(Base):
    def referentiel(self, texte: str = REFERENTIEL) -> None:
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(texte, encoding="utf-8")

    def rapports(self) -> list[Path]:
        dossier = self.ws / "Flux-Lab" / "rapports"
        return sorted(dossier.glob("dependances-*")) if dossier.exists() else []

    def calcul_par(self, par: str, *extra: str, nom: str = "g") -> tuple[dict, str]:
        export = self.csv(TICKETS)
        sortie = self.lancer("compute", export, "--name", nom, "--by", par, *extra)
        fichier = self.ws / "Flux-Lab" / "rapports" / f"dependances-{nom}-{par}-{AUJOURDHUI.isoformat()}.json"
        return json.loads(fichier.read_text(encoding="utf-8")), sortie

    def test_matrice_par_mission_team_deux_lignes_internes_dites_totaux_egaux(self):
        self.referentiel()
        export = self.csv(TICKETS)
        self.lancer("compute", export, "--name", "e")
        equipe = json.loads((self.ws / "Flux-Lab" / "rapports" / f"dependances-e-{AUJOURDHUI.isoformat()}.json")
                            .read_text(encoding="utf-8"))
        r, sortie = self.calcul_par("mission-team")
        self.assertEqual(r["par"], "mission-team")
        groupes = {g for ligne in r["matrice_totale"] for g in ligne[:2]}
        self.assertEqual(groupes, {"MT-Frobnic", "MT-Plinth", "hors référentiel"})
        entre = {(a, b): n for a, b, n in r["matrice_totale"] if a != b}
        self.assertEqual(entre, {("MT-Frobnic", "MT-Plinth"): 1, ("MT-Plinth", "MT-Frobnic"): 1,
                                 ("MT-Frobnic", "hors référentiel"): 1})
        self.assertEqual(r["dependances_internes"], [["MT-Frobnic", 1], ["MT-Plinth", 0], ["hors référentiel", 0]])   # Alpha bloque Beta
        self.assertEqual(r["dependances"], equipe["dependances"])
        self.assertEqual(sum(n for *_, n in r["matrice_totale"]), sum(n for *_, n in equipe["matrice_totale"]))
        self.assertEqual(sum(n for *_, n in r["matrice_ouverte"]), sum(n for *_, n in equipe["matrice_ouverte"]))
        md = (self.ws / "Flux-Lab" / "rapports" / f"dependances-g-mission-team-{AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        self.assertIn("| MT-Frobnic | 5 | 1 |", md)                     # l'interne de la Mission Team est dit dans le rapport
        self.assertIn("Mission Team", md)

    def test_matrice_par_site(self):
        self.referentiel()
        r, _ = self.calcul_par("site")
        entre = {(a, b): n for a, b, n in r["matrice_totale"] if a != b}
        self.assertEqual(entre, {("Site-Zorblax", "Site-Quimbo"): 1, ("Site-Quimbo", "Site-Zorblax"): 1,
                                 ("Site-Zorblax", "hors référentiel"): 1})
        self.assertEqual(r["dependances_internes"], [["Site-Quimbo", 0], ["Site-Zorblax", 1], ["hors référentiel", 0]])

    def test_equipe_hors_referentiel_regroupee_et_comptee(self):
        self.referentiel()
        r, _ = self.calcul_par("mission-team")
        self.assertEqual(r["equipes_tickets"], {"MT-Frobnic": 5, "MT-Plinth": 2, "hors référentiel": 1})
        self.assertNotIn("Eq-Delta", json.dumps(r, ensure_ascii=False))

    def test_identifiant_du_catalogue_qu_aucune_equipe_du_referentiel_ne_liste_regroupe_hors_referentiel(self):
        """Change team-mapping, tâche 3.3 : un libellé du catalogue est une équipe inconnue du référentiel ; le groupe garde son libellé."""
        self.referentiel()
        (self.ws / "Flux-Lab" / "equipes-jira.yaml").write_text(
            "teams:\n  - name: Libelle-Quimbo\n    jira_team_ids: ['50']\n", encoding="utf-8")
        tickets = TICKETS + [t("QQQ-1", "Libelle-Quimbo", sortants=["BBB-4"]), t("BBB-4", "Eq-Beta", entrants=["QQQ-1"])]
        sortie = self.lancer("compute", self.csv(tickets), "--name", "g", "--by", "mission-team")
        fichier = self.ws / "Flux-Lab" / "rapports" / f"dependances-g-mission-team-{AUJOURDHUI.isoformat()}.json"
        r = json.loads(fichier.read_text(encoding="utf-8"))
        self.assertEqual(r["equipes_tickets"], {"MT-Frobnic": 6, "MT-Plinth": 2, "hors référentiel": 2})
        self.assertNotIn("Libelle-Quimbo", json.dumps(r, ensure_ascii=False))
        self.assertNotIn("Libelle-Quimbo", sortie)

    def test_identifiant_present_dans_les_deux_fichiers_reste_dans_son_equipe_du_referentiel(self):
        ref = REFERENTIEL.replace("  - name: Eq-Alpha\n    headcount: 4101\n", "  - name: Eq-Alpha\n    headcount: 4101\n    jira_team_ids: ['1']\n")
        self.referentiel(ref)
        (self.ws / "Flux-Lab" / "equipes-jira.yaml").write_text(
            "teams:\n  - name: Libelle-Partage\n    jira_team_ids: ['1', '52']\n", encoding="utf-8")
        r, _ = self.calcul_par("mission-team")
        self.assertEqual(r["equipes_tickets"], {"MT-Frobnic": 5, "MT-Plinth": 2, "hors référentiel": 1})
        self.assertNotIn("Libelle-Partage", json.dumps(r, ensure_ascii=False))

    def test_libelle_hors_referentiel_en_anglais(self):
        self.referentiel()
        export = self.csv(TICKETS)
        self.lancer("compute", export, "--name", "g", "--by", "mission-team", "--language", "en")
        md = (self.ws / "Flux-Lab" / "rapports" / f"dependances-g-mission-team-{AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        self.assertIn("outside the referential", md)
        self.assertNotIn("hors référentiel", md)

    def test_referentiel_absent_code_1_aucun_rapport(self):
        for par in ("mission-team", "site"):
            sortie = self.lancer("compute", self.csv(TICKETS), "--name", "g", "--by", par, attendu=1)
            self.assertIn("organisation.yaml", sortie)
        self.assertEqual(self.rapports(), [])

    def test_referentiel_invalide_code_1_sans_valeur_aucun_rapport(self):
        self.referentiel(REFERENTIEL + "personne: Valeur-Secrete\n")
        sortie = self.lancer("compute", self.csv(TICKETS), "--name", "g", "--by", "mission-team", attendu=1)
        self.assertIn("organisation.yaml", sortie)
        self.assertNotIn("Valeur-Secrete", sortie)
        self.assertEqual(self.rapports(), [])

    def test_par_equipe_ne_lit_pas_le_referentiel(self):
        r = self.calcul(self.csv(TICKETS), nom="e")          # aucun organisation.yaml : comportement inchangé
        self.assertEqual(r["par"], "equipe")

    def test_aucun_ratio_aucun_classement_effectif_dans_le_resume_de_structure_seul(self):
        self.referentiel()
        self.calcul_par("mission-team")
        md = (self.ws / "Flux-Lab" / "rapports" / f"dependances-g-mission-team-{AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        # l'effectif n'apparaît que dans les lignes du tableau de structure (Mission Team | équipes | effectif)
        for effectif in ("4101", "4202", "4303", "8303"):
            for ligne in md.splitlines():
                if effectif in ligne:
                    self.assertRegex(ligne, r"^\| (MT-|Site-|hors|outside)[^|]* \| \d+ \| \d+ \|$", ligne)
        self.assertIn("| MT-Frobnic | 2 | 8303 |", md)
        self.assertIn("| MT-Plinth | 1 | 4303 |", md)
        # ordre par nom dans les deux tableaux de groupes, jamais par un chiffre
        structure = [m.group(1) for m in re.finditer(r"^\| ([^|]+?) \| \d+ \| \d{4} \|$", md, re.M)]
        comptes = [m.group(1) for m in re.finditer(r"^\| ([^|]+?) \| \d+ \| \d+ \|$", md, re.M)
                   if m.group(0) not in re.findall(r"^\| [^|]+? \| \d+ \| \d{4} \|$", md, re.M)]
        self.assertEqual(structure, ["MT-Frobnic", "MT-Plinth"])
        self.assertEqual(comptes, ["MT-Frobnic", "MT-Plinth", "hors référentiel"])
        self.assertEqual(comptes, sorted(comptes))

    def test_aucun_classement_par_un_chiffre(self):
        """Une paire plus chargée qu'une autre ne passe pas devant : ordre par nom, pas de « paire la plus chargée »."""
        self.referentiel()
        plus = TICKETS + [t(f"AAA-{i}", "Eq-Alpha", sortants=[f"GGG-{i}"]) for i in (3, 4)] + \
            [t(f"GGG-{i}", "Eq-Gamma", entrants=[f"AAA-{i}"]) for i in (3, 4)]
        self.lancer("compute", self.csv(plus), "--name", "g", "--by", "mission-team")
        chemin = self.ws / "Flux-Lab" / "rapports" / f"dependances-g-mission-team-{AUJOURDHUI.isoformat()}"
        md = chemin.with_suffix(".md").read_text(encoding="utf-8")
        r = json.loads(chemin.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertNotIn("la plus chargée", md)
        paires = [(a, b) for a, b, _ in r["matrice_totale"]]
        self.assertEqual(paires, sorted(paires))
        lignes = [ligne for ligne in md.splitlines() if re.match(r"^\| (MT-|hors)[^|]+ \| (MT-|hors)[^|]+ \| \d+ \|", ligne)]
        cles = [tuple(c.strip() for c in ligne.split("|")[1:3]) for ligne in lignes]
        self.assertEqual(cles, sorted(cles))

    def test_aucun_nom_en_console(self):
        self.referentiel()
        for options in ((), ("--keys",)):
            _, sortie = self.calcul_par("mission-team", *options)
            for nom in NOMS:
                self.assertNotIn(nom, sortie, (options, nom))
        _, sortie = self.calcul_par("site", "--keys")
        for nom in NOMS:
            self.assertNotIn(nom, sortie)

    def test_voie_base_meme_calcul_que_la_voie_csv(self):
        """Le calcul en direct, avec un faux flow_store qui rend les données du CSV, donne le même rapport que le lanceur de test."""
        self.referentiel()
        r_csv, _ = self.calcul_par("mission-team", nom="csv")
        export = self.csv(TICKETS, nom="base.csv")
        donnees = chargeur.lire_export_dependances(Path(export), dj.config())
        magasin = types.SimpleNamespace(lire_dependances=lambda settings: dict(donnees))
        args = ["compute", "--by", "mission-team", "--name", "db"]
        racine = self.ws / "Flux-Lab"
        with mock.patch.dict(sys.modules, {"flow_store": magasin}), mock.patch.dict(os.environ), \
                mock.patch.object(dj, "FLUX_DIR", racine), mock.patch.object(dj, "CONFIG_FILE", racine / "flux.yaml"), \
                mock.patch.object(dj, "REPORT_DIR", racine / "rapports"), contextlib.redirect_stdout(io.StringIO()):
            os.environ.pop("CLAUDECODE", None)
            dj.main(args)
        fichier = racine / "rapports" / f"dependances-db-mission-team-{AUJOURDHUI.isoformat()}.json"
        r_db = json.loads(fichier.read_text(encoding="utf-8"))
        for cle in ("matrice_totale", "matrice_ouverte", "dependances_internes", "equipes_tickets", "aretes", "structure"):
            self.assertEqual(r_db[cle], r_csv[cle], cle)
        self.assertEqual(r_db["export"], "base")

    def test_voie_base_referentiel_absent_code_1_avant_toute_lecture(self):
        racine = self.ws / "Flux-Lab"
        lecture = mock.Mock(side_effect=AssertionError("la base ne doit pas être lue"))
        with mock.patch.dict(sys.modules, {"flow_store": types.SimpleNamespace(lire_dependances=lecture)}), \
                mock.patch.dict(os.environ), \
                mock.patch.object(dj, "FLUX_DIR", racine), mock.patch.object(dj, "CONFIG_FILE", racine / "flux.yaml"), \
                mock.patch.object(dj, "REPORT_DIR", racine / "rapports"):
            os.environ.pop("CLAUDECODE", None)
            with self.assertRaises(SystemExit) as sortie:
                dj.main(["compute", "--by", "site"])
        self.assertIn("organisation.yaml", str(sortie.exception))
        lecture.assert_not_called()
        self.assertEqual(self.rapports(), [])


if __name__ == "__main__":
    unittest.main()
