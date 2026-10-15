"""compute --by team|mission-team|site (R-58, tâche 9.1 ; specs jira-flow-reports « Aggregation by team, Mission Team or site »,
jira-flow-organisation « Reports by Mission Team and by site », « Headcount describes the structure only », « Names stay in the
flow folder »).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Lancements dans le processus (aide_espace.py), sur des exports et un référentiel inventés, sans base : la voie base est
exercée avec un faux flow_store qui rend les tickets lus dans le même CSV.
"""
import json
import random
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from aide_espace import AvecEspace, faux_store, fj  # noqa: E402
import test_flux_jira as fx  # noqa: E402

EQUIPES = ["Equipe A1", "Equipe A2", "Equipe B1", "Equipe Z"]      # Equipe Z n'est pas dans le référentiel
REFERENTIEL = """source_date: 2026-10-01
sites:
  - Site Nord
  - Site Sud
departments:
  - name: Departement 1
    site: Site Nord
    headcount: 20
    mission_teams:
      - name: MT Alpha
        teams: [Equipe A1, Equipe A2]
      - name: MT Beta
        teams: [Equipe B1]
teams:
  - name: Equipe A1
    headcount: 5
  - name: Equipe A2
    headcount: 6
    site: Site Sud
  - name: Equipe B1
    headcount: 7
"""
NOMS_A_TAIRE = ("MT Alpha", "MT Beta", "Site Nord", "Site Sud", "Equipe A1", "Equipe A2", "Equipe B1", "Equipe Z", "Departement 1")


class Base(AvecEspace):
    def setUp(self):
        super().setUp()
        self.lignes = fx.construire(random.Random(11), "PROJ", fx.WORKFLOW_1, 120, EQUIPES, ["Story", "Bug"])
        self.csv = self.flux / "export.csv"
        fx.ecrire_csv(self.csv, self.lignes)
        self.ecrire("organisation.yaml", REFERENTIEL)

    def compute(self, *plus, nom="s", store=None, source_csv=True):
        argv = ["compute", *([str(self.csv)] if source_csv else []), "--name", nom, "--today", "2026-10-04", "--no-comparison",
                *plus]
        return self.lancer(*argv, store=store)

    def json_du_rapport(self, stem):
        return json.loads(self.lire_rapport(stem + ".json"))


class ParDefaut(Base):
    def test_sans_option_comme_avec_by_team_et_sans_cle_de_regroupement(self):
        """Scénario « Default » : sans --by, le rapport est celui d'avant ; --by team est le même."""
        code, _, _ = self.compute()
        self.assertIsNone(code)
        md, js = self.lire_rapport("flux-s-2026-10-04.md"), self.lire_rapport("flux-s-2026-10-04.json")
        code, _, _ = self.compute("--by", "team")
        self.assertIsNone(code)
        self.assertEqual(self.lire_rapport("flux-s-2026-10-04.md"), md)
        self.assertEqual(self.lire_rapport("flux-s-2026-10-04.json"), js)
        self.assertNotIn("regroupement", json.loads(js))
        self.assertEqual(sorted(p.name for p in self.rapports.iterdir()), ["flux-s-2026-10-04.json", "flux-s-2026-10-04.md"])

    def test_by_inconnu_refuse_par_l_usage(self):
        code, _, erreur = self.compute("--by", "department")
        self.assertEqual(code, 2)
        self.assertIn("--by", erreur)


class ParMissionTeam(Base):
    def setUp(self):
        super().setUp()
        self.compute()
        self.global_ = self.json_du_rapport("flux-s-2026-10-04")
        self.code, self.console, _ = self.compute("--by", "mission-team")
        self.r = self.json_du_rapport("flux-s-mission-team-2026-10-04")

    def test_le_nom_du_rapport_porte_l_agregation(self):
        self.assertIsNone(self.code)
        self.assertTrue((self.rapports / "flux-s-mission-team-2026-10-04.md").exists())
        self.assertEqual(self.r["nom"], "s-mission-team")
        self.assertEqual(self.r["regroupement"]["par"], "mission-team")

    def test_les_groupes_remplacent_les_equipes_et_les_sommes_egalent_les_totaux(self):
        """Scénario « Flux by Mission Team » : débit, arrivées et travail en cours par groupe, somme = chiffres globaux."""
        groupes = self.r["par_equipe"]
        self.assertEqual(sorted(groupes), ["MT Alpha", "MT Beta", "hors référentiel"])
        self.assertEqual(sum(g["termines"] for g in groupes.values()), self.r["termines"])
        self.assertEqual(sum(g["wip"] for g in groupes.values()), self.r["wip"])
        arrivees = self.r["arrivees_sorties_par_equipe"]
        self.assertEqual(sum(g["arrivees"] for g in arrivees.values()), self.r["arrivees"])
        self.assertEqual(sum(g["sorties"] for g in arrivees.values()), self.r["termines"])
        for semaine, total in enumerate(self.r["debit_par_semaine"]):
            self.assertEqual(sum(g["debit_par_semaine"][semaine] for g in groupes.values()), total)
        # les totaux globaux sont ceux du rapport par équipe
        for cle in ("termines", "wip", "arrivees", "a_faire", "debit_par_semaine", "lead_time_jours"):
            self.assertEqual(self.r[cle], self.global_[cle], cle)

    def test_equipe_hors_referentiel_comptee_avec_ses_tickets(self):
        """Scénario « Team outside the referential »."""
        z = sum(1 for t in self.lignes if t["equipe"] == "Equipe Z")
        self.assertGreater(z, 0)
        self.assertEqual(self.r["regroupement"]["hors_referentiel"], {"equipes": 1, "tickets": z})
        md = self.lire_rapport("flux-s-mission-team-2026-10-04.md")
        self.assertIn(f"1 équipe(s) et {z} ticket(s), regroupés sous « hors référentiel »", md)

    def test_resume_de_structure_effectifs_sans_ratio_et_par_nom(self):
        """Scénarios « No ratio » et « Ordering »."""
        self.assertEqual(self.r["regroupement"]["structure"],
                         [{"group": "MT Alpha", "teams": 2, "headcount": 11}, {"group": "MT Beta", "teams": 1, "headcount": 7}])
        md = self.lire_rapport("flux-s-mission-team-2026-10-04.md")
        debut = md.index("## Structure")
        structure = md[debut:md.index("\n\n", md.index("| Mission Team |"))]
        self.assertIn("| Mission Team | Équipes | Effectif |", structure)
        self.assertIn("| MT Alpha | 2 | 11 |", structure)
        self.assertIn("| MT Beta | 1 | 7 |", structure)
        self.assertLess(structure.index("MT Alpha"), structure.index("MT Beta"))
        self.assertNotIn("par personne", md)
        # les sections par groupe sont rangées par nom (clés du JSON triées), jamais par un chiffre
        self.assertEqual(list(self.r["par_equipe"]), sorted(self.r["par_equipe"]))
        self.assertEqual(list(self.r["arrivees_sorties_par_equipe"]), sorted(self.r["arrivees_sorties_par_equipe"]))

    def test_aucun_chiffre_n_est_divise_par_un_effectif(self):
        """Le rapport par groupe ne porte aucun champ rapporté à un effectif : l'effectif n'est que dans la structure."""
        champs = set()

        def parcourir(valeur):
            if isinstance(valeur, dict):
                for cle, v in valeur.items():
                    champs.add(str(cle).lower())
                    parcourir(v)
            elif isinstance(valeur, list):
                for v in valeur:
                    parcourir(v)
        parcourir(self.r)
        self.assertEqual({c for c in champs if "effectif" in c or "headcount" in c or "personne" in c or "person" in c},
                         {"headcount"})

    def test_aucun_nom_de_groupe_ni_d_equipe_en_console(self):
        """Pas de nom en console : le rapport reste dans le fichier du dossier de flux."""
        for nom in NOMS_A_TAIRE:
            self.assertNotIn(nom, self.console)
        self.assertIn("Rapport par mission-team", self.console)

    def test_les_noms_sont_dans_le_fichier_du_rapport(self):
        md = self.lire_rapport("flux-s-mission-team-2026-10-04.md")
        for nom in ("MT Alpha", "MT Beta", "hors référentiel"):
            self.assertIn(nom, md)
        self.assertIn("## Par Mission Team", md)
        self.assertNotIn("## Par équipe", md)
        self.assertIn("| Mission Team | Terminés |", md)
        self.assertIn("| Mission Team | Arrivées | Sorties | Différence |", md)

    def test_sans_nom_le_rapport_porte_l_agregation_seule(self):
        code, _, _ = self.compute("--by", "site", nom="")
        self.assertIsNone(code)
        self.assertTrue((self.rapports / "flux-site-2026-10-04.md").exists())


class ParSite(Base):
    def test_groupes_par_site_et_somme_des_totaux(self):
        code, console, _ = self.compute("--by", "site")
        self.assertIsNone(code)
        r = self.json_du_rapport("flux-s-site-2026-10-04")
        self.assertEqual(sorted(r["par_equipe"]), ["Site Nord", "Site Sud", "hors référentiel"])
        self.assertEqual(sum(g["termines"] for g in r["par_equipe"].values()), r["termines"])
        self.assertEqual(r["regroupement"]["structure"],
                         [{"group": "Site Nord", "teams": 2, "headcount": 12}, {"group": "Site Sud", "teams": 1, "headcount": 6}])
        for nom in NOMS_A_TAIRE:
            self.assertNotIn(nom, console)
        self.assertIn("## Par site", self.lire_rapport("flux-s-site-2026-10-04.md"))


class Anglais(Base):
    def test_titres_et_groupe_hors_referentiel_en_anglais_json_inchange(self):
        self.compute("--by", "mission-team", "--language", "en")
        md = self.lire_rapport("flux-s-mission-team-2026-10-04.md")
        self.assertIn("## By Mission Team", md)
        self.assertIn("| Mission Team | Teams | Headcount |", md)
        self.assertIn("outside the referential", md)
        self.assertNotIn("hors référentiel", md)
        en = self.lire_rapport("flux-s-mission-team-2026-10-04.json")
        self.compute("--by", "mission-team")
        self.assertEqual(self.lire_rapport("flux-s-mission-team-2026-10-04.json"), en)      # le JSON ne dépend pas de la langue


class Referentiel(Base):
    def test_referentiel_absent_code_1_et_aucun_rapport(self):
        """Scénario « Referential missing »."""
        (self.flux / "organisation.yaml").unlink()
        for par in ("site", "mission-team"):
            code, _, _ = self.compute("--by", par)
            self.assertIsInstance(code, str)                     # message : code de sortie 1
            self.assertIn("organisation.yaml", code)
        self.assertFalse(self.rapports.exists() and list(self.rapports.iterdir()))

    def test_referentiel_invalide_nomme_la_cle_jamais_la_valeur(self):
        self.ecrire("organisation.yaml", REFERENTIEL + "responsable: ZZVALEUR-SECRETE\n")
        code, _, _ = self.compute("--by", "site")
        self.assertIsInstance(code, str)
        self.assertIn("responsable", code)
        self.assertNotIn("ZZVALEUR-SECRETE", code)
        self.assertFalse(self.rapports.exists() and list(self.rapports.iterdir()))

    def test_sans_option_le_referentiel_n_est_pas_lu(self):
        (self.flux / "organisation.yaml").unlink()
        code, _, _ = self.compute()
        self.assertIsNone(code)


class Comparaison(Base):
    def test_comparaison_automatique_sautee_sans_nom_de_groupe_en_console(self):
        self.compute("--by", "mission-team")
        code, console, _ = self.lancer("compute", str(self.csv), "--name", "s", "--today", "2026-10-11", "--by", "mission-team")
        self.assertIsNone(code)
        self.assertIn("compare --name s-mission-team", console)
        for nom in NOMS_A_TAIRE:
            self.assertNotIn(nom, console)
        self.assertFalse((self.rapports / "evolution-s-mission-team-2026-10-11.md").exists())


class DeuxSources(Base):
    """Le même regroupement sur la voie base : un faux flow_store rend les tickets lus dans le CSV."""

    def store(self):
        reglages = fj.config()
        tickets, found, illisibles, doublons = fj.read_exports([str(self.csv)], reglages)
        return faux_store(lire_tickets_flux=lambda settings: (tickets, {k: (v or None) for k, v in found.items()}, 0, 0))

    def test_meme_rapport_par_groupe_sur_les_deux_sources(self):
        for par in ("mission-team", "site"):
            self.compute("--by", par)
            csv = self.json_du_rapport(f"flux-s-{par}-2026-10-04")
            code, console, _ = self.compute("--by", par, "--source", "db", nom="s", source_csv=False, store=self.store())
            self.assertIsNone(code, console)
            base = self.json_du_rapport(f"flux-s-{par}-2026-10-04")
            for cle in ("termines", "wip", "arrivees", "par_equipe", "arrivees_sorties_par_equipe", "regroupement"):
                self.assertEqual(base[cle], csv[cle], f"{par} {cle}")
            for nom in NOMS_A_TAIRE:
                self.assertNotIn(nom, console)


if __name__ == "__main__":
    unittest.main()
