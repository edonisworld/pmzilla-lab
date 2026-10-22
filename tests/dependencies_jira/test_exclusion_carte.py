"""Exclusion de projets propre à la carte des dépendances (change dependency-project-exclusion, R-72, tâche 3.1).

    uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira -v

Specs : jira-flow-dependencies (« Exclusions », réglage de la carte, option d'exclusion, source de la liste dite),
jira-flow-config (réglage validé par chaque lecteur). Conception : D2 (priorité), D3 (option), D4 (ligne de source),
D5 (validation). Clés de projet, équipes et valeurs inventées ; aucun accès à Flux-Lab/ réel ni à Jira.

Trois projets qui portent des liens : AAA (équipe Eq-Alpha, bloquant), BBB (jamais exclu), XXA et XXB (exclus selon la liste).
"""
from __future__ import annotations

import json
import re
import unittest

from test_dependencies_jira import AUJOURDHUI, Base, t
from test_par_groupe import REFERENTIEL

TICKETS = [
    t("AAA-1", "Eq-Alpha", sortants=["BBB-1"]),          # Eq-Beta attend Eq-Alpha (jamais exclu)
    t("BBB-1", "Eq-Beta", entrants=["AAA-1"]),
    t("AAA-2", "Eq-Alpha", sortants=["XXA-1"]),          # XXA-1 attend AAA-2
    t("XXA-1", "Eq-Gamma", entrants=["AAA-2"]),
    t("AAA-3", "Eq-Alpha", sortants=["XXB-1"]),          # XXB-1 attend AAA-3
    t("XXB-1", "Eq-Gamma", entrants=["AAA-3"]),
]

PHRASE_FR = "Projets exclus de la carte : "
PHRASE_EN = "Projects excluded from the map: "
SOURCES_FR = {"option": "source : option --exclude",
              "carte": "source : réglage dependency_excluded_projects",
              "commun": "source : réglage excluded_projects, commun avec le rapport de flux"}
SOURCES_EN = {"option": "source: option --exclude",
              "carte": "source: setting dependency_excluded_projects",
              "commun": "source: setting excluded_projects, shared with the flow report"}
VUES = (("team", ""), ("project", "-projets"), ("mission-team", "-mission-team"), ("site", "-site"))
NEUTRES = ("exclus_source", "exclus_projets")


def lignes_source(texte: str, phrase: str) -> list[str]:
    return [ligne.lstrip("> ").strip() for ligne in texte.splitlines() if phrase in ligne]


class Fond(Base):
    def setUp(self):
        super().setUp()
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(REFERENTIEL, encoding="utf-8")
        self.export = self.csv(TICKETS)

    def rapport(self, *extra: str, par: str = "team", suffixe: str = "", nom: str = "x", langue: str = "fr"):
        """(JSON, Markdown) du rapport après `compute`."""
        self.lancer("compute", self.export, "--name", nom, "--by", par, "--language", langue, *extra)
        stem = self.ws / "Flux-Lab" / "rapports" / f"dependances-{nom}{suffixe}-{AUJOURDHUI.isoformat()}"
        return (json.loads(stem.with_suffix(".json").read_text(encoding="utf-8")),
                stem.with_suffix(".md").read_text(encoding="utf-8"))

    def projets_exclus(self, rapport: dict) -> list[str]:
        return sorted({p for p, _, _ in rapport["exclus"]})

    def nombre_de_rapports(self) -> int:
        dossier = self.ws / "Flux-Lab" / "rapports"
        return len(list(dossier.glob("dependances-*"))) if dossier.exists() else 0


class Priorite(Fond):
    """D2 : l'option, sinon le réglage de la carte (liste vide comprise), sinon le réglage commun."""

    def test_reglage_commun_seul(self):
        self.reglages("excluded_projects: [XXA]\n")
        r, _ = self.rapport()
        self.assertEqual(self.projets_exclus(r), ["XXA"])
        self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("reglage_commun", 1))

    def test_reglage_de_la_carte_seul(self):
        self.reglages("dependency_excluded_projects: [XXB]\n")
        r, _ = self.rapport()
        self.assertEqual(self.projets_exclus(r), ["XXB"])
        self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("reglage_carte", 1))

    def test_les_deux_reglages_celui_de_la_carte_l_emporte(self):
        self.reglages("excluded_projects: [XXA]\ndependency_excluded_projects: [XXB]\n")
        r, _ = self.rapport()
        self.assertEqual(self.projets_exclus(r), ["XXB"])
        self.assertEqual(r["exclus_source"], "reglage_carte")

    def test_reglage_de_la_carte_vide_n_exclut_rien_malgre_le_commun(self):
        self.reglages("excluded_projects: [XXA]\ndependency_excluded_projects: []\n")
        r, _ = self.rapport()
        self.assertEqual(r["exclus"], [])
        self.assertEqual(r["dependances"], 3)
        self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("reglage_carte", 0))

    def test_option_l_emporte_sur_les_deux_reglages(self):
        self.reglages("excluded_projects: [XXA]\ndependency_excluded_projects: [XXB]\n")
        r, _ = self.rapport("--exclude", " xxa , XXB ,,")
        self.assertEqual(self.projets_exclus(r), ["XXA", "XXB"])
        self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("option", 2))
        self.assertEqual(r["dependances"], 1)

    def test_doublons_de_l_option_comptes_une_fois(self):
        # choix de mise en oeuvre (à relire) : dédoublonnage après mise en majuscules, ordre de première apparition
        r, _ = self.rapport("--exclude", "xxa, XXA ,xxb,XXA")
        self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("option", 2))

    def test_option_sans_reglage(self):
        r, _ = self.rapport("--exclude", "XXB")
        self.assertEqual(self.projets_exclus(r), ["XXB"])
        self.assertEqual(r["exclus_source"], "option")

    def test_none_et_aucun_n_excluent_rien_sans_casse(self):
        self.reglages("excluded_projects: [XXA]\ndependency_excluded_projects: [XXB]\n")
        for mot in ("none", "NONE", "aucun", "Aucun", " none "):
            with self.subTest(mot=mot):
                r, _ = self.rapport("--exclude", mot)
                self.assertEqual(r["exclus"], [])
                self.assertEqual(r["dependances"], 3)
                self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("option", 0))

    def test_l_option_n_ecrit_rien_dans_les_reglages(self):
        self.reglages("dependency_excluded_projects: [XXB]\n")
        avant = (self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8")
        self.rapport("--exclude", "XXA")
        self.assertEqual((self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8"), avant)

    def test_projet_a_la_fois_dans_le_perimetre_et_exclu_reste_exclu(self):
        self.reglages("scope_projects: [AAA, XXA]\ndependency_excluded_projects: [XXA]\n")
        r, _ = self.rapport()
        self.assertEqual(self.projets_exclus(r), ["XXA"])


class SansLaNouvelleCle(Fond):
    """D2 : sans la clé ni l'option, mêmes matrices, comptes, groupes de lead time et blocages anciens qu'avant."""

    def test_sans_aucune_exclusion_rien_n_est_dit(self):
        r, md = self.rapport()
        self.assertEqual(r["exclus"], [])
        self.assertEqual(r["dependances"], 3)
        self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("aucune", 0))
        self.assertEqual(lignes_source(md, PHRASE_FR), [])
        self.assertEqual(sorted(r["matrice_totale"]), [["Eq-Beta", "Eq-Alpha", 1], ["Eq-Gamma", "Eq-Alpha", 2]])

    def test_liste_commune_donne_les_memes_sorties_qu_avant(self):
        self.reglages("excluded_projects: [XXA]\n")
        r, _ = self.rapport()
        self.assertEqual(r["dependances"], 2)
        self.assertEqual(sorted(r["matrice_totale"]), [["Eq-Beta", "Eq-Alpha", 1], ["Eq-Gamma", "Eq-Alpha", 1]])
        self.assertEqual(sorted(r["exclus"]), [["XXA", "attend l'export", 1]])

    def test_meme_liste_dans_le_reglage_de_la_carte_donne_le_meme_rapport_a_la_source_pres(self):
        self.reglages("excluded_projects: [XXA]\n")
        commun, _ = self.rapport()
        self.reglages("dependency_excluded_projects: [XXA]\n")
        carte, _ = self.rapport()
        for cle in NEUTRES:
            commun.pop(cle), carte.pop(cle)
        self.assertEqual(commun, carte)


class LigneDeSource(Fond):
    """D4 : une ligne dans le diagnostic et dans le Markdown, avec un nombre de projets, jamais une clé."""

    CAS = {"option": ("", ("--exclude", "XXA,XXB"), 2),
           "carte": ("dependency_excluded_projects: [XXA]\n", (), 1),
           "commun": ("excluded_projects: [XXA, XXB]\n", (), 2)}

    def test_chaque_source_dans_le_diagnostic_et_le_markdown_dans_les_deux_langues(self):
        for source, (reglage, option, n) in self.CAS.items():
            for langue, phrase, sources in (("fr", PHRASE_FR, SOURCES_FR), ("en", PHRASE_EN, SOURCES_EN)):
                with self.subTest(source=source, langue=langue):
                    self.reglages(reglage)
                    attendu = f"{phrase}{n} ({sources[source]})"
                    sortie = self.lancer("diagnose", self.export, "--language", langue, *option)
                    self.assertEqual(lignes_source(sortie, phrase), [attendu])
                    _, md = self.rapport(*option, langue=langue)
                    self.assertEqual(lignes_source(md, phrase), [attendu])
                    for cle in ("XXA", "XXB"):
                        self.assertNotIn(cle, attendu)

    def test_liste_vide_dit_aucun_avec_la_source(self):
        cas = (("none", ("--exclude", "none"), "option"), ("aucun", ("--exclude", "aucun"), "option"),
               ("carte vide", (), "carte"))
        for nom, option, source in cas:
            for langue, phrase, mot, sources in (("fr", PHRASE_FR, "aucun", SOURCES_FR), ("en", PHRASE_EN, "none", SOURCES_EN)):
                with self.subTest(cas=nom, langue=langue):
                    self.reglages("dependency_excluded_projects: []\n" if source == "carte" else "")
                    sortie = self.lancer("diagnose", self.export, "--language", langue, *option)
                    self.assertEqual(lignes_source(sortie, phrase), [f"{phrase}{mot} ({sources[source]})"])

    def test_aucune_ligne_sans_exclusion(self):
        for langue, phrase in (("fr", PHRASE_FR), ("en", PHRASE_EN)):
            with self.subTest(langue=langue):
                sortie = self.lancer("diagnose", self.export, "--language", langue)
                self.assertEqual(lignes_source(sortie, phrase), [])
                _, md = self.rapport(langue=langue)
                self.assertEqual(lignes_source(md, phrase), [])

    def test_la_ligne_precede_les_lignes_par_projet(self):
        self.reglages("dependency_excluded_projects: [XXA]\n")
        sortie = self.lancer("diagnose", self.export)
        self.assertLess(sortie.index(PHRASE_FR), sortie.index("Liens avec le projet exclu XXA"))
        _, md = self.rapport()
        self.assertLess(md.index(PHRASE_FR), md.index("Liens avec le projet exclu XXA"))

    def test_json_sans_la_liste_ni_les_cles_dans_les_champs_de_source(self):
        self.reglages("dependency_excluded_projects: [XXA, XXB]\n")
        r, _ = self.rapport()
        self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("reglage_carte", 2))
        self.assertIsInstance(r["exclus_projets"], int)
        for cle in ("exclus_source", "exclus_projets"):
            self.assertNotRegex(json.dumps(r[cle]), r"XX[AB]")
        self.assertEqual(self.projets_exclus(r), ["XXA", "XXB"])      # les clés restent dans `exclus`, comme avant


class OptionVide(Fond):
    """D3 : une option sans clé arrête l'exécution (code 2) avant toute lecture et tout rapport."""

    FR = "--exclude : aucune clé de projet ; donner des clés séparées par des virgules, ou « aucun »"
    EN = '--exclude: no project key; give comma-separated keys, or "none"'

    def test_refus_avant_toute_lecture_et_sans_rapport(self):
        absent = str(self.ws / "n-existe-pas.csv")           # lu, il donnerait un autre message : jamais lu
        for commande in ("diagnose", "compute"):
            for valeur in ("", ",", " , ,", "  "):
                for langue, message in (("fr", self.FR), ("en", self.EN)):
                    with self.subTest(commande=commande, valeur=valeur, langue=langue):
                        sortie = self.lancer(commande, absent, "--exclude", valeur, "--language", langue, attendu=2)
                        self.assertIn(message, sortie)
                        self.assertNotIn("No such file", sortie)
        self.assertEqual(self.nombre_de_rapports(), 0)

    def test_refus_meme_avec_un_reglage_valide(self):
        self.reglages("dependency_excluded_projects: [XXA]\n")
        self.lancer("compute", self.export, "--exclude", "", attendu=2)
        self.assertEqual(self.nombre_de_rapports(), 0)


class ReglageInvalide(Fond):
    """D5 : valeur invalide, code 1, clé et ligne nommées, valeur absente, avant tout rapport."""

    def test_refus_par_les_deux_commandes(self):
        for valeur in ("ValeurDistinctiveZZ", "[XXA, 4217]", "[XXA, '']"):
            self.reglages(f"portfolio_types: [Epic]\ndependency_excluded_projects: {valeur}\n")
            for commande in ("diagnose", "compute"):
                with self.subTest(commande=commande, valeur=valeur):
                    sortie = self.lancer(commande, self.export, attendu=1)
                    self.assertIn("flux.yaml : L2 : réglage invalide : dependency_excluded_projects", sortie)
                    self.assertIn("invalid setting: dependency_excluded_projects", sortie)
                    for secret in ("ValeurDistinctiveZZ", "XXA", "4217"):
                        self.assertNotIn(secret, sortie)
        self.assertEqual(self.nombre_de_rapports(), 0)

    def test_l_option_ne_contourne_pas_la_validation(self):
        self.reglages("dependency_excluded_projects: ValeurDistinctiveZZ\n")
        sortie = self.lancer("compute", self.export, "--exclude", "XXA", attendu=1)
        self.assertNotIn("ValeurDistinctiveZZ", sortie)


class ToutesLesVues(Fond):
    """Chaque vue (--by) applique la même liste ; la ligne de source se lit pareil dans toutes."""

    def test_meme_liste_dans_chaque_vue(self):
        self.reglages("excluded_projects: [XXA]\ndependency_excluded_projects: [XXB]\n")
        ligne = f"{PHRASE_FR}1 ({SOURCES_FR['carte']})"
        for par, suffixe in VUES:
            with self.subTest(par=par):
                r, md = self.rapport(par=par, suffixe=suffixe)
                self.assertEqual(self.projets_exclus(r), ["XXB"])
                self.assertEqual(r["dependances"], 2)
                self.assertEqual((r["exclus_source"], r["exclus_projets"]), ("reglage_carte", 1))
                self.assertEqual(lignes_source(md, PHRASE_FR), [ligne])

    def test_option_dans_chaque_vue(self):
        self.reglages("dependency_excluded_projects: [XXB]\n")
        for par, suffixe in VUES:
            with self.subTest(par=par):
                r, md = self.rapport("--exclude", "XXA", par=par, suffixe=suffixe, langue="en")
                self.assertEqual(self.projets_exclus(r), ["XXA"])
                self.assertEqual(r["exclus_source"], "option")
                self.assertEqual(lignes_source(md, PHRASE_EN), [f"{PHRASE_EN}1 ({SOURCES_EN['option']})"])

    def test_la_ligne_est_la_meme_dans_le_rapport_par_projet_et_par_equipe(self):
        self.reglages("excluded_projects: [XXA, XXB]\n")
        _, par_equipe = self.rapport()
        _, par_projet = self.rapport(par="project", suffixe="-projets")
        self.assertEqual(lignes_source(par_equipe, PHRASE_FR), lignes_source(par_projet, PHRASE_FR))
        self.assertEqual(len(lignes_source(par_projet, PHRASE_FR)), 1)


if __name__ == "__main__":
    unittest.main()
