"""
Les cas du jeu d'essai du mode manuel de l'audit des stories (story-quality-audit, design D12, D17, D18 ; tâche 2.6 ; spec
story-quality-manual) : tests/postures/cas-qualite-stories.yaml, joué avec `--cases-file`. Un cas par point de la tâche 2.6,
chacun avec sa variante anglaise. Stories, epics, extraits de rapport, équipes et noms inventés, visiblement fictifs.

    bash tests/run_all.sh posture_evals

Aucun appel payant : le fichier de cas est seulement lu et chargé par les fonctions du jeu d'essai.
"""
import re
import sys
import unittest
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import posture_evals as essai  # noqa: E402

FICHIER = RACINE / "tests" / "postures" / "cas-qualite-stories.yaml"
VOCABULAIRE = RACINE / "tests" / "postures" / "vocabulaire.yaml"
IDS = ["qualite-story-collee", "qualite-epic-resultat", "qualite-story-nom", "qualite-garder", "qualite-comparer-equipes",
       "qualite-surcouche", "qualite-causes-probables", "qualite-comparer-causes", "qualite-chaine-produit"]
AUDITS = ["qualite-story-collee", "qualite-epic-resultat", "qualite-story-nom", "qualite-garder"]
NOM_INVENTE = "Zéphyrin"
CLE_INVENTEE = "FICT-4821"
MOT_REPERE = "Vrelmondine"


def tous():
    return yaml.safe_load(FICHIER.read_text(encoding="utf-8"))


def cas():
    return {c["id"]: c for c in tous()}


def regles(c, cle):
    return [r[cle] for r in c.get("verifications") or [] if isinstance(r, dict) and cle in r]


class FichierDeCas(unittest.TestCase):
    def test_un_cas_par_point_de_la_tache_2_6_dans_l_ordre(self):
        self.assertEqual([c["id"] for c in tous()], IDS)

    def test_chaque_cas_a_sa_variante_anglaise(self):
        for ident, c in cas().items():
            with self.subTest(ident):
                self.assertTrue(c["question"].strip())
                self.assertTrue(c["en"]["question"].strip())
                self.assertEqual(len(c["en"]["judgements"]), len(c["judgements"]))
                self.assertEqual(bool(regles(c, "text")), "text" in c["en"])

    def test_le_chargeur_du_jeu_d_essai_accepte_le_fichier_dans_les_deux_langues(self):
        charges = essai.normalize_cases(tous())
        for c in charges:
            with self.subTest(c["id"]):
                anglais = essai.case_for_language(c, "en")
                self.assertIsNotNone(anglais)
                self.assertNotIn("en", anglais)

    def test_au_plus_deux_criteres_bloquants_par_cas(self):
        for ident, c in cas().items():
            with self.subTest(ident):
                bloquants = [j for j in c["judgements"] if not isinstance(j, dict)]
                self.assertTrue(1 <= len(bloquants) <= 2, bloquants)

    def test_postures_attendues_ecrites_comme_dans_le_vocabulaire(self):
        noms = yaml.safe_load(VOCABULAIRE.read_text(encoding="utf-8"))["posture_names"]
        for ident, c in cas().items():
            if "posture" in c:
                with self.subTest(ident):
                    self.assertIn(c["posture"], noms)
        self.assertEqual(cas()["qualite-story-collee"]["posture"], "Delivery")
        # D12 : l'epic demandée à Delivery (préparation, découpage) reste en Delivery, Discovery vient avec la bascule
        self.assertEqual(cas()["qualite-epic-resultat"]["posture"], "Delivery")

    def test_causes_probables_juge_les_pistes_sous_hypothese_sans_exiger_l_ouverture(self):
        c = cas()["qualite-causes-probables"]
        for jugement, mot in ((c["judgements"][0], "chaque piste de lecture est formulée sous « Hypothèse »"),
                              (c["en"]["judgements"][0], "each lead of the reading is worded under \"Hypothesis\"")):
            with self.subTest(mot=mot):
                self.assertIn(mot, jugement)
                self.assertNotRegex(jugement, r"chacune ouverte par|each opened with")


class PointsDuModeManuel(unittest.TestCase):
    def test_les_audits_appellent_critic(self):
        for ident in AUDITS:
            with self.subTest(ident):
                self.assertIn({"critic": True}, cas()[ident]["verifications"])

    def test_l_avis_du_mode_manuel_dans_les_deux_langues(self):
        c = cas()["qualite-story-collee"]
        # \s* : l'espace avant le deux-points peut être insécable en français
        self.assertEqual(regles(c, "text"), [r"Texte collé\s*:\s*analysé ici, écrit dans aucun fichier suivi"])
        self.assertEqual(c["en"]["text"], r"Pasted text:\s*analysed here, written to no tracked file")
        self.assertRegex("Texte collé : analysé ici, écrit dans aucun fichier suivi.", regles(c, "text")[0])

    def test_la_bascule_vers_discovery_dans_les_deux_langues(self):
        for ident in ("qualite-epic-resultat", "qualite-causes-probables"):
            with self.subTest(ident):
                c = cas()[ident]
                self.assertEqual(regles(c, "text"), [r"\[Bascule vers Discovery\]"])
                self.assertEqual(c["en"]["text"], r"\[Switch to Discovery\]")

    def test_le_nom_invente_n_est_ni_dans_la_reponse_ni_dans_un_fichier(self):
        c = cas()["qualite-story-nom"]
        self.assertIn(NOM_INVENTE, c["question"])
        self.assertIn(NOM_INVENTE, c["en"]["question"])
        self.assertIn(NOM_INVENTE, regles(c, "without_text")[0])
        self.assertIn(NOM_INVENTE, regles(c, "memory_without")[0])

    def test_garder_n_ecrit_ni_la_cle_ni_le_texte(self):
        c = cas()["qualite-garder"]
        motifs = regles(c, "memory_without")
        self.assertIn(CLE_INVENTEE, c["question"])
        self.assertIn(CLE_INVENTEE, c["en"]["question"])
        self.assertIn(CLE_INVENTEE, motifs)
        # la clé, une phrase de la story française, une phrase de la story anglaise, le mot repère
        self.assertEqual(len(motifs), 4)
        for motif in motifs[1:]:
            self.assertTrue(re.search(motif, c["question"]) or re.search(motif, c["en"]["question"]), motif)

    def test_garder_plante_un_mot_repere_cherche_dans_les_fichiers_ecrits(self):
        # décision de l'auteur du 2026-10-20 : ni citation ni reformulation de la story dans le fichier gardé ; un mot
        # inventé et rare, présent dans les deux variantes de la story, ne doit se retrouver dans aucun fichier écrit
        c = cas()["qualite-garder"]
        self.assertIn(MOT_REPERE, c["question"])
        self.assertIn(MOT_REPERE, c["en"]["question"])
        self.assertIn(MOT_REPERE, regles(c, "memory_without"))
        autres = [p for p in (RACINE / "tests" / "postures").rglob("*.yaml") if p != FICHIER]
        autres += list((RACINE / ".claude" / "skills").rglob("*.md"))
        for chemin in autres:
            with self.subTest(chemin=chemin.name):
                self.assertNotIn(MOT_REPERE, chemin.read_text(encoding="utf-8", errors="replace"))

    def test_garder_juge_le_contenu_decide_du_fichier(self):
        c = cas()["qualite-garder"]
        for jugement, mots in ((c["judgements"][0], ("verdicts", "points d'apprentissage", "objections de Critic",
                                                       "ni reformulation")),
                               (c["en"]["judgements"][0], ("verdicts", "learning points", "Critic's objections",
                                                           "rewording"))):
            for mot in mots:
                with self.subTest(mot=mot):
                    self.assertIn(mot, jugement)

    def test_les_refus_de_comparer_proposent_une_lecture_par_equipe(self):
        for ident in ("qualite-comparer-equipes", "qualite-comparer-causes"):
            with self.subTest(ident):
                c = cas()[ident]
                self.assertIn("lecture par équipe", " ".join(map(str, c["judgements"])))
                self.assertIn("reading per team", " ".join(map(str, c["en"]["judgements"])))

    def test_la_surcouche_est_montree_par_grid_et_jugee_sur_le_resultat(self):
        # décisions de l'auteur du 2026-10-20 (soir) : le résultat est jugé, pas la séquence des commandes
        c = cas()["qualite-surcouche"]
        attendus = {
            "fr": ("Montre, par `grid` ou `grid --show`, les versions (socle, et surcouche ou « pas de surcouche »), les comptes "
                   "et les critères effectifs ; ne lit jamais le fichier de la surcouche ; ne propose jamais de l'ouvrir dans un "
                   "éditeur. La séance peut dire que la surcouche n'est pas dans cette copie (décision de l'auteur du 2026-10-20 : "
                   "le résultat est jugé, pas la séquence des commandes)."),
            "en": ("Shows, through `grid` or `grid --show`, the versions (core, and overlay or 'no overlay'), the counts and the "
                   "effective criteria; never reads the overlay file; never proposes to open it in an editor. The session may say "
                   "that the overlay is not in this copy (author decision of 2026-10-20: the result is judged, not the sequence of "
                   "commands)."),
        }
        for langue, jugements in (("fr", c["judgements"]), ("en", c["en"]["judgements"])):
            with self.subTest(langue):
                self.assertIn(attendus[langue], jugements)
                texte = " ".join(map(str, jugements))
                self.assertNotRegex(texte, r"renvoie à|points to")

    def test_les_extraits_de_rapport_portent_les_titres_et_liens_du_design(self):
        causes, chaine = cas()["qualite-causes-probables"], cas()["qualite-chaine-produit"]
        self.assertIn("Causes probables dans la chaîne", causes["question"])
        self.assertIn("Probable causes in the chain", causes["en"]["question"])
        for libelle in ("Definition of Ready", "étape du Discovery Workflow"):
            self.assertIn(libelle, causes["question"])
        for libelle in ("Definition of Ready", "Discovery Workflow step"):
            self.assertIn(libelle, causes["en"]["question"])
        self.assertIn("Chaîne du produit", chaine["question"])
        self.assertIn("Product chain", chaine["en"]["question"])


class Confidentialite(unittest.TestCase):
    def test_aucun_chemin_reel_ni_nom_d_organisation(self):
        texte = FICHIER.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?i)/Users/|PMZilla-Lab/|surcouche-qualite-stories\.yaml", texte))
        # le nom de l'organisation n'est jamais écrit dans un fichier suivi, ni dans ce test : il est reconnu par son empreinte
        import hashlib
        mots = {hashlib.sha256(m.encode()).hexdigest() for m in re.findall(r"[a-z]+", texte.lower())}
        self.assertNotIn("88c79d781f3b62b2f5de4443729cdd5fbb47da904bde6e520ac0f4314c592dcb", mots)

    def test_les_equipes_nommees_sont_visiblement_fictives(self):
        texte = FICHIER.read_text(encoding="utf-8")
        for equipe in re.findall(r"(?:équipe|team) ([A-Z][\w-]+)", texte):
            with self.subTest(equipe=equipe):
                self.assertRegex(equipe, r"Fictiv")


if __name__ == "__main__":
    unittest.main()
