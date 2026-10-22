"""
Tests du répartiteur de tools/story_quality.py et du catalogue des phrases (change story-quality-audit, design D14).

  - les cinq sous-commandes collect, review, analyse, coach et report sont déclarées, avec grid ;
  - tant que son module n'est pas écrit, une sous-commande répond « pas encore disponible » avec le code 2 ;
  - collect, review, analyse et coach refusent de démarrer dans une session Claude Code (code 3), avant toute lecture ; report et grid
    restent permises à la session ;
  - le catalogue porte toutes les phrases clés de D14, mot pour mot, dans les deux langues.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import story_quality as sq  # noqa: E402
from story_quality_messages import CATALOGS  # noqa: E402

SESSION = {"CLAUDECODE": "1"}


def lancer(*argv, environ=None):
    sortie, erreur = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
        code = sq.main(list(argv), {} if environ is None else environ, identifiers=[])
    return code, sortie.getvalue(), erreur.getvalue()


def disponible(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


class SousCommandes(unittest.TestCase):
    def test_les_cinq_sous_commandes_et_grid_sont_declarees(self):
        self.assertEqual(sq.SOUS_COMMANDES, ("collect", "review", "analyse", "coach", "report", "grid"))
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = sq.main(["--help"], {}, identifiers=[])
        self.assertEqual(code, 0)
        for nom in sq.SOUS_COMMANDES:
            self.assertIn(nom, sortie.getvalue())

    def test_un_module_par_sous_commande(self):
        self.assertEqual(sq.MODULES, {"collect": "story_quality_collect", "review": "story_quality_review",
                                      "analyse": "story_quality_engine", "coach": "story_quality_engine",
                                      "report": "story_quality_report"})

    def test_pas_encore_disponible_en_code_2(self):
        for argv in (("analyse", "--dry-run"), ("coach", "--team", "Equipe Zz"), ("report", "--name", "serie")):
            if disponible(sq.MODULES[argv[0]]):
                continue
            with self.subTest(argv=argv):
                code, sortie, erreur = lancer(*argv, "--language", "en")
                self.assertEqual(code, 2)
                self.assertIn(f"subcommand not yet available: {argv[0]}", erreur)
                self.assertEqual(sortie, "")
                self.assertNotIn("Zz", erreur)

    def test_refus_en_session_pour_les_quatre_sous_commandes_de_l_utilisateur(self):
        for argv in (("collect",), ("review", "--team", "Equipe Zz", "--sample", "2"), ("analyse",), ("analyse", "--dry-run"),
                     ("analyse", "--sample", "3", "--team", "Equipe Zz"), ("coach", "--team", "Equipe Zz"),
                     ("coach", "--keys", "ZZ-1", "--show"), ("coach", "--team", "Equipe Zz", "--dry-run")):
            with self.subTest(argv=argv):
                code, sortie, erreur = lancer(*argv, "--language", "en", environ=SESSION)
                self.assertEqual(code, 3)
                self.assertEqual((sortie + erreur).strip(), "Refused inside a Claude Code session")

    def test_report_et_grid_restent_permises_a_la_session(self):
        if not disponible(sq.MODULES["report"]):
            code, _, erreur = lancer("report", "--name", "serie", "--language", "en", environ=SESSION)
            self.assertEqual(code, 2)
            self.assertNotIn("Refused inside", erreur)
        code, _, erreur = lancer("grid", "--language", "en", environ=SESSION)
        self.assertNotIn("Refused inside", erreur)

    def test_grid_et_report_ne_chargent_ni_base_ni_jira_ni_collecte(self):
        """Dans un processus neuf : ni psycopg, ni requests, ni les modules de collecte et de magasin ne sont chargés."""
        import json
        import subprocess
        import tempfile
        programme = ("import json, sys\nsys.path.insert(0, sys.argv[1])\nimport story_quality as sq\n"
                     "code = sq.main(sys.argv[3:], {'PMZILLA_LAB_CONTEXT': sys.argv[2]}, identifiers=[])\n"
                     "print('MODULES:' + json.dumps(sorted(sys.modules)))\nsys.exit(code)\n")
        interdits = ("psycopg", "requests", "story_quality_collect", "story_quality_store", "story_quality_review", "db")
        with tempfile.TemporaryDirectory() as contexte:
            for argv in (("grid",), ("grid", "--show"), ("report", "--name", "serie")):
                if argv[0] == "report" and disponible(sq.MODULES["report"]):
                    continue
                with self.subTest(argv=argv):
                    fini = subprocess.run([sys.executable, "-c", programme, str(TOOLS), contexte, *argv], capture_output=True,
                                          text=True, timeout=120)
                    lignes = [ligne for ligne in fini.stdout.splitlines() if ligne.startswith("MODULES:")]
                    self.assertEqual(len(lignes), 1, fini.stderr[-500:])
                    charges = set(json.loads(lignes[0][len("MODULES:"):]))
                    for nom in interdits:
                        self.assertNotIn(nom, charges)

    def test_usage(self):
        for argv in ((), ("inconnue",), ("collect", "--language", "de"), ("coach", "--show"), ("report",)):
            with self.subTest(argv=argv):
                self.assertEqual(lancer(*argv)[0], 2)


# Table de D14 recopiée mot pour mot (clé du catalogue -> anglais, français). Les champs entre accolades sont ceux de D14, sauf
# overlay_refused dont le numéro de ligne s'appelle {line} dans le catalogue (même texte).
D14 = {
    "session_refused": ("Refused inside a Claude Code session", "Refusé dans une session Claude Code"),
    "person_field_refused": ("person field refused in the story quality settings: {key}",
                             "champ de personne refusé dans les réglages de qualité des stories : {key}"),
    "collect_done": ("story content collected: {n} items, {r} replacements", "contenu des stories collecté : {n} éléments, {r} remplacements"),
    "past_retention": ("items past retention, skipped: {n}", "éléments au-delà de la conservation, ignorés : {n}"),
    "out_of_collection": ("items out of collection: {n} marked, {m} back", "éléments sortis de la collecte : {n} marqués, {m} revenus"),
    "key_missing": ("analysis key missing: create it in the Keychain", "clé d'analyse absente : la créer dans le Trousseau"),
    "audit_grid_invalid": ("audit grid missing or invalid", "grille d'audit absente ou invalide"),
    "analysis_done": ("analysis done: {n} items, {u} undetermined verdicts", "analyse faite : {n} éléments, {u} verdicts indéterminés"),
    "engine_refused": ("engine answers refused: {n}", "réponses du moteur refusées : {n}"),
    "batch_estimate": ("batch: {n} items, about {t} tokens, estimated cost {c}", "lot : {n} éléments, environ {t} jetons, coût estimé {c}"),
    "confirm_prompt": ("Send this batch? Type yes to confirm:", "Envoyer ce lot ? Taper oui pour confirmer :"),
    "not_confirmed": ("not confirmed: nothing sent", "non confirmé : rien n'est envoyé"),
    "no_terminal": ("confirmation needs a terminal: nothing sent", "la confirmation demande un terminal : rien n'est envoyé"),
    "cap_reached": ("cap reached: {n} items left for the next launch", "plafond atteint : {n} éléments pour le prochain lancement"),
    "cap_invalid": ("cap per launch missing or invalid", "plafond par lancement absent ou invalide"),
    "dry_run": ("dry run: nothing sent", "essai : rien n'est envoyé"),
    "blocked": ("blocked until their team is reviewed: {n} items, {t} teams",
                "bloqués tant que leur équipe n'est pas relue : {n} éléments, {t} équipes"),
    "all_blocked": ("nothing to send: run review for each new team first",
                    "rien à envoyer : lancer d'abord review pour chaque nouvelle équipe"),
    "review_prompt": ("Sample checked, no name left? Type yes to record:",
                      "Échantillon relu, aucun nom restant ? Taper oui pour enregistrer :"),
    "review_recorded": ("team sample review recorded", "relecture de l'échantillon de l'équipe enregistrée"),
    "review_complete": ("full review: {n} items", "relecture complète : {n} éléments"),
    "sample_below_minimum": ("sample size below the minimum for review: {n}",
                             "taille d'échantillon inférieure au minimum de la relecture : {n}"),
    "no_item_for_team": ("no collected item for this team", "aucun élément collecté pour cette équipe"),
    "review_not_recorded": ("review not recorded: update the sensitive-names list and collect again",
                            "relecture non enregistrée : compléter la liste des noms sensibles et recollecter"),
    "single_po_notice": ("Single-PO team: these results are those of one person's work; never use them to evaluate that person",
                         "Équipe à un seul PO : ces résultats sont ceux du travail d'une personne ; ne jamais s'en servir pour l'évaluer"),
    "coaching_header": ("Coaching results: shown here only, kept out of every report",
                        "Résultats de coaching : affichés ici seulement, exclus de tout rapport"),
    "unreadable_dates": ("items skipped for unreadable dates: {n}", "éléments ignorés pour dates illisibles : {n}"),
    "teams_not_in_referential": ("teams absent from the referential: {n}", "équipes absentes du référentiel : {n}"),
    "unknown_items": ("unknown items: {n}", "éléments inconnus : {n}"),
    "report_written": ("story quality report written", "rapport de qualité des stories écrit"),
    "team_results_notice": ("Team results: never a person's evaluation, never a ranking",
                            "Résultats d'équipe : jamais l'évaluation d'une personne, jamais un classement"),
    "retention_store_line": ("story content: {n} items out of rule", "contenu des stories : {n} éléments hors règle"),
    "manual_notice": ("Pasted text: analysed here, written to no tracked file.", "Texte collé : analysé ici, écrit dans aucun fichier suivi."),
    "no_overlay": ("no organisation overlay: core grid only", "pas de surcouche de l'organisation : socle seul"),
    "overlay_invalid": ("organisation overlay invalid: {field}", "surcouche de l'organisation invalide : {field}"),
    "overlay_refused": ("organisation overlay refused: sensitive name or identifier in line {line}",
                        "surcouche de l'organisation refusée : nom sensible ou identifiant à la ligne {line}"),
    "grid_valid": ("grid valid: core {cv}, overlay {ov}, {a} criteria added, {d} disabled",
                   "grille valide : socle {cv}, surcouche {ov}, {a} critères ajoutés, {d} désactivés"),
    "organisation_rule": ("organisation rule", "règle de l'organisation"),
    "grid_line": ("Grid: core {cv}, organisation overlay {ov}", "Grille : socle {cv}, surcouche de l'organisation {ov}"),
    "grid_line_no_overlay": ("Grid: core {cv}, no organisation overlay", "Grille : socle {cv}, sans surcouche de l'organisation"),
    "disabled_criteria": ("Core criteria disabled by the organisation rule: {codes}",
                          "Critères du socle désactivés par règle de l'organisation : {codes}"),
    "probable_causes_heading": ("Probable causes in the chain", "Causes probables dans la chaîne"),
    "probable_causes_notice": ("Where the chain usually produces this defect: a lead to check with the team, never a person's fault",
                               "Là où la chaîne produit d'ordinaire ce défaut : une piste à vérifier avec l'équipe, jamais la faute d'une personne"),
    "no_recurrent_defect": ("No recurrent defect at the current grid", "Aucun défaut récurrent pour la grille actuelle"),
    "link_ticket_template": ("ticket template", "modèle de ticket"),
    "link_discovery_workflow_step": ("Discovery Workflow step", "étape du Discovery Workflow"),
    "link_definition_of_ready": ("Definition of Ready", "Definition of Ready"),
    "link_refinement": ("Refinement", "Refinement"),
    "product_chain_heading": ("Product chain", "Chaîne du produit"),
    "product_chain_notice": ("All teams taken together, as for the product's monthly follow-up: no figure and no name per team, never a comparison between teams",
                             "Toutes équipes réunies, comme le suivi mensuel du produit : aucun chiffre ni nom par équipe, jamais une comparaison entre équipes"),
    "overlay_changed": ("organisation overlay content changed without a new version",
                        "contenu de la surcouche de l'organisation changé sans nouvelle version"),
    "sample_size_invalid": ("sample size must be a positive integer not above the cap",
                            "taille d'échantillon : un entier positif, sans dépasser le plafond"),
    "sample_done": ("sample analysis done: {n} items, {u} undetermined verdicts; counted in no view and no report",
                    "analyse d'échantillon faite : {n} éléments, {u} verdicts indéterminés ; comptée dans aucune vue ni aucun rapport"),
    "sample_line": ("sample {code}: {m} met, {x} not met, {a} not applicable, {u} undetermined",
                    "échantillon {code} : {m} satisfaits, {x} non satisfaits, {a} sans objet, {u} indéterminés"),
    "show_header": ("Effective grid: core {cv}, overlay {ov}; criteria only, never the disabling reasons",
                    "Grille effective : socle {cv}, surcouche {ov} ; critères seulement, jamais les raisons de désactivation"),
}


class Catalogue(unittest.TestCase):
    def test_toutes_les_phrases_de_d14_mot_pour_mot(self):
        for cle, (anglais, francais) in D14.items():
            with self.subTest(cle=cle):
                self.assertEqual(CATALOGS["en"][cle], anglais)
                self.assertEqual(CATALOGS["fr"][cle], francais)

    def test_mots_de_confirmation(self):
        self.assertEqual((CATALOGS["en"]["confirm_word"], CATALOGS["fr"]["confirm_word"]), ("yes", "oui"))

    def test_catalogues_coherents(self):
        from messages import check_catalogs
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_aucun_champ_de_valeur_interdit(self):
        """Les champs des phrases ne sont que des effectifs, des versions, des codes, une clé de réglage, un chemin de clé, une ligne,
        un nom de sous-commande, un type d'erreur ou un message déjà sûr : jamais une équipe, une clé de ticket ou un texte."""
        from messages import fields
        permis = {"n", "r", "m", "u", "t", "c", "x", "a", "d", "i", "key", "cv", "ov", "field", "line", "codes", "code", "what",
                  "command", "kind", "detail", "label", "link", "source", "text", "items"}
        # Seule exception, D14 (« coach prints the keys the user typed next to their feedback, in the Terminal only ») : la clé de
        # l'élément, le verdict et le retour borné du moteur, dans les deux phrases de l'affichage du coaching et nulle part ailleurs.
        exceptions = {"coach_item": {"item"}, "coach_line": {"verdict", "feedback"}}
        for langue in CATALOGS:
            for cle, texte in CATALOGS[langue].items():
                self.assertEqual(fields(texte) - permis - exceptions.get(cle, set()), set(), f"{langue}.{cle}")
        self.assertEqual({cle for langue in CATALOGS for cle, texte in CATALOGS[langue].items()
                          if fields(texte) & {"item", "verdict", "feedback"}}, set(exceptions))


if __name__ == "__main__":
    unittest.main()
