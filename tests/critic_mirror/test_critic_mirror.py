"""
Tests de l'extraction des objections de Critic (tools/critic_mirror.py) sur des livrables inventés.

    uv run python -m unittest discover -s tests/critic_mirror -v

Les livrables sont écrits dans un dossier temporaire (jamais _bmad-output/pmzilla) ; la date du jour est fixée
par l'option cachée --today. Le script ne classe rien : on vérifie la période, la détection des sections,
le découpage et le décompte des objections, que le classement de /critic-mirror doit retrouver.
"""
import contextlib
import datetime as dt
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import critic_mirror as miroir  # noqa: E402

DIAGNOSTIC = """\
# Diagnostic de flux

[Posture : Delivery]

## 1. Constat

Le temps de cycle est stable.

## 8. Revue de Critic

[Posture : Critic]

1. Le diagnostic suppose que les tickets sont comparables entre équipes.
   - sous-point rattaché à la première objection
2. Aucune limite de l'approche n'est donnée.
3) Le seuil de 85 % n'est pas justifié.

Amélioration : ajouter une limite.

## 9. Sources

- une source
"""

MESSAGE = """\
[Posture : Scaling]

Voici la réponse.

Ce que Critic conteste

- Le périmètre n'est pas précisé.
- La recommandation ignore le pouvoir de dire non.

Corrections faites

- Périmètre précisé.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sortie_dir = self.tmp / "_bmad-output" / "pmzilla"
        patch = mock.patch.object(miroir, "OUTPUT_DIR", self.sortie_dir)
        patch.start()
        self.addCleanup(patch.stop)

    def ecrire(self, relatif: str, texte: str, mtime: str | None = None) -> Path:
        chemin = self.sortie_dir / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        if mtime:
            stamp = dt.datetime.fromisoformat(mtime).timestamp()
            os.utime(chemin, (stamp, stamp))
        return chemin

    def lancer(self, *arguments, aujourdhui="2026-10-15") -> str:
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["critic_mirror.py", "--today", aujourdhui, *arguments]), \
                contextlib.redirect_stdout(sortie):
            miroir.main()
        return sortie.getvalue()


class Sections(unittest.TestCase):
    def test_section_a_titre_markdown(self):
        sections = miroir.critic_sections(DIAGNOSTIC.splitlines())
        self.assertEqual(len(sections), 1)
        items = miroir.objections(sections[0])
        self.assertEqual(len(items), 3)
        self.assertTrue(items[0].startswith("Le diagnostic suppose"))
        self.assertIn("sous-point rattaché", items[0])        # un sous-point reste rattaché à son point
        self.assertTrue(items[2].startswith("Le seuil de 85 %"))
        self.assertNotIn("Amélioration", " ".join(items))     # la piste d'amélioration n'est pas une objection
        self.assertNotIn("Posture", " ".join(items))
        self.assertNotIn("une source", " ".join(items))        # la section s'arrête au titre suivant

    def test_section_a_ligne_simple_s_arrete_a_corrections_faites(self):
        sections = miroir.critic_sections(MESSAGE.splitlines())
        self.assertEqual(len(sections), 1)
        items = miroir.objections(sections[0])
        self.assertEqual(items, ["Le périmètre n'est pas précisé.",
                                 "La recommandation ignore le pouvoir de dire non."])

    def test_variantes_de_titres(self):
        for titre in ("## Ce que Critic conteste", "### Revue de critic", "# CRITIC"):
            with self.subTest(titre):
                self.assertEqual(len(miroir.critic_sections([titre, "", "- une objection", "", "## Suite"])), 1)

    def test_section_sans_liste_est_une_seule_objection(self):
        corps = ["Un texte continu qui conteste", "sur deux lignes sans puces."]
        self.assertEqual(miroir.objections(corps), ["Un texte continu qui conteste sur deux lignes sans puces."])

    def test_section_vide_et_sans_critic(self):
        self.assertEqual(miroir.critic_sections(["## Revue de Critic", "", "## Suite", "texte"]), [])
        self.assertEqual(miroir.critic_sections(["## Résumé", "texte sur la critique en général"]), [])
        self.assertEqual(miroir.objections([]), [])

    def test_plusieurs_sections_dans_un_fichier(self):
        lignes = ["## Revue de Critic", "- A", "## Autre", "texte", "## Second passage de Critic", "- B", "- C"]
        sections = miroir.critic_sections(lignes)
        self.assertEqual([len(miroir.objections(s)) for s in sections], [1, 2])

    def test_citations_retirees(self):
        corps = ["> 1. Première objection citée", "> 2. Seconde objection citée", "▎ 3. Troisième"]
        self.assertEqual(miroir.objections(corps),
                         ["Première objection citée", "Seconde objection citée", "Troisième"])

    def test_titre_avec_marque_de_posture_n_ouvre_pas_de_section(self):
        """Comportement actuel (à connaître) : un titre qui porte « [Posture : … » n'ouvre jamais de section,
        même s'il nomme Critic ; une section écrite sous « ## [Posture : Critic] » seul n'est donc pas lue."""
        lignes = ["## [Posture : Critic]", "", "- une objection", "- une autre"]
        self.assertEqual(miroir.critic_sections(lignes), [])


LECTURE_FR = """\
# Lecture des dépendances

- **Posture :** Scaling (vue d'ensemble). Delivery ne commente aucune équipe : première série.
- **Demande :** relire le rapport.

## Constat

Texte.

## Ce que Critic a contesté

[Posture : Critic]

1. Le périmètre n'est pas défini.
2. Le seuil n'est pas justifié.
"""

LECTURE_EN = """\
# Flow reading

- **Posture:** Delivery (capacité DF)
- **Request:** read the report.

## 8. Revue de Critic

> [Posture : Critic]
>
> 1. The sample is too small.
"""


class PostureEnMetadonnee(Base):
    def test_formes_de_la_ligne_de_posture(self):
        cas = {
            "- **Posture :** Delivery": ["Delivery"],                  # typographie française
            "- **Posture:** Delivery": ["Delivery"],                   # typographie anglaise
            "**Posture :** Scaling": ["Scaling"],                      # sans puce
            "- **Posture** : Discovery": ["Discovery"],                # deux-points hors du gras
            "* *Posture :* Facilitation": ["Facilitation"],            # italique
            "- Posture: facilitation": ["Facilitation"],               # sans gras, casse libre
            "Posture : Delivery": ["Delivery"],
            "- **POSTURE :** Delivery": ["Delivery"],
            "- **Posture :** Delivery et Scaling": ["Delivery", "Scaling"],
            "- **Posture:** Delivery, Scaling and Facilitation": ["Delivery", "Scaling", "Facilitation"],
            "- **Posture :** Delivery + Scaling (vue d'ensemble)": ["Delivery", "Scaling"],
            "- **Posture :** Scaling (vue d'ensemble). Delivery ne commente aucune équipe": ["Scaling"],
            "- **Posture :** Delivery (capacité DF)": ["Delivery"],
            "- **Posture :** Critic": [],                              # Critic n'est jamais la posture d'un livrable
            "- **Posture :** aucune": [],
            "- **Posture :** Magie": [],                               # posture inconnue : rien d'inventé
            "- **Posture :**": [],
            "- **Postures utilisées :** Delivery": [],                 # autre champ
            "[Posture : Delivery]": [],                                # la balise est lue ailleurs
            "Texte qui parle de Posture : Delivery": [],
        }
        for ligne, attendu in cas.items():
            with self.subTest(ligne):
                self.assertEqual(miroir.metadata_postures(["# Titre", "", ligne, "", "## Suite"]), attendu)

    def test_seul_l_en_tete_est_lu(self):
        self.assertEqual(miroir.metadata_postures(["# T", "## Constat", "- **Posture :** Delivery"]), [])
        self.assertEqual(miroir.metadata_postures(["# T", "- **Posture :** Delivery", "## Constat"]), ["Delivery"])
        self.assertEqual(miroir.metadata_postures([]), [])

    def test_livrables_aux_deux_formats_dans_le_miroir(self):
        self.ecrire("dependances/2026-10-06-lecture-fr.md", LECTURE_FR)
        self.ecrire("flux/2026-10-07-lecture-en.md", LECTURE_EN)
        sortie = self.lancer()
        self.assertIn("## dependances/2026-10-06-lecture-fr.md · 2026-10-06 · livrable de posture · posture Scaling", sortie)
        self.assertIn("## flux/2026-10-07-lecture-en.md · 2026-10-07 · livrable de posture · posture Delivery", sortie)
        self.assertNotIn("non indiquée", sortie)
        self.assertEqual(sortie.count("- O"), 3)              # les objections sont toujours trouvées

    def test_balise_et_metadonnee_se_completent_sans_doublon(self):
        self.ecrire("2026-10-08-mixte.md", "- **Posture :** Delivery\n\n[Posture : Delivery]\n\n"
                                           "[Bascule vers Scaling]\n\n[Posture : Scaling]\n\nTexte.\n\n"
                                           "## Revue de Critic\n\n[Posture : Critic]\n\n- Une objection.\n")
        self.assertIn("2026-10-08-mixte.md · 2026-10-08 · livrable de posture · posture Delivery, Scaling", self.lancer())

    def test_sans_metadonnee_ni_balise_reste_non_indiquee(self):
        self.ecrire("2026-10-08-nu.md", "## Revue de Critic\n\n- Une objection.\n")
        self.assertIn("posture non indiquée", self.lancer())


class Periode(unittest.TestCase):
    def test_periode_par_defaut(self):
        self.assertEqual(miroir.default_period(dt.date(2026, 10, 15)), (dt.date(2026, 10, 1), dt.date(2026, 10, 15)))
        self.assertEqual(miroir.default_period(dt.date(2026, 10, 7)), (dt.date(2026, 9, 1), dt.date(2026, 9, 30)))
        self.assertEqual(miroir.default_period(dt.date(2026, 10, 8)), (dt.date(2026, 10, 1), dt.date(2026, 10, 8)))
        self.assertEqual(miroir.default_period(dt.date(2026, 1, 3)), (dt.date(2025, 12, 1), dt.date(2025, 12, 31)))
        self.assertEqual(miroir.default_period(dt.date(2026, 3, 2)), (dt.date(2026, 2, 1), dt.date(2026, 2, 28)))


class Corpus(Base):
    def setUp(self):
        super().setUp()
        self.ecrire("2026-10-03-diagnostic-flux.md", DIAGNOSTIC)
        self.ecrire("messages/2026-10-10-message.md", MESSAGE)
        self.ecrire("2026-10-12-sans-critic.md", "# Livrable\n\n[Posture : Facilitation]\n\nTexte.\n")
        self.ecrire("2026-09-20-ancien.md", DIAGNOSTIC)
        self.ecrire("miroir/miroir-2026-09.md", "## Revue de Critic\n\n- ne doit jamais être relu\n")
        self.ecrire("veille/2026-10-05-synthese.md", "## Ce que Critic conteste\n\n- Un article pèse comme un livre.\n\n"
                                                   "## Sources\n\n- x\n")

    def test_corpus_du_mois_en_cours(self):
        sortie = self.lancer()
        self.assertIn("# Objections de Critic du 2026-10-01 au 2026-10-15", sortie)
        self.assertIn("3 livrable(s) avec une section Critic · 6 objection(s) · 1 livrable(s) de la période sans section Critic",
                      sortie)
        self.assertIn("## 2026-10-03-diagnostic-flux.md · 2026-10-03 · livrable de posture · posture Delivery", sortie)
        self.assertIn("## messages/2026-10-10-message.md · 2026-10-10 · messages adaptés · posture Scaling", sortie)
        self.assertIn("## veille/2026-10-05-synthese.md · 2026-10-05 · synthèse de veille · posture non indiquée", sortie)
        self.assertIn("- 2026-10-12-sans-critic.md", sortie.split("sans section Critic\n")[-1])
        self.assertNotIn("ne doit jamais être relu", sortie)     # miroirs ignorés
        self.assertNotIn("2026-09-20-ancien", sortie)            # hors période

    def test_objections_numerotees_en_continu_et_nombre_exact(self):
        sortie = self.lancer()
        numeros = [int(l.split(" : ")[0][3:]) for l in sortie.splitlines() if l.startswith("- O")]
        self.assertEqual(numeros, list(range(1, 7)))

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        for ancien, actuel, arguments in (("--depuis", "--since", ("--depuis", "2026-09-01")),
                                          ("--jusqu", "--until", ("--jusqu=2026-09-30",))):
            with self.subTest(ancien=ancien):
                erreur = io.StringIO()
                with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
                    self.lancer(*arguments)
                self.assertEqual(stop.exception.code, 2)
                self.assertIn(f"« {ancien} »", erreur.getvalue())
                self.assertIn(f"« {actuel} »", erreur.getvalue())

    def test_periodes_explicites(self):
        sortie = self.lancer("--since", "2026-09-01", "--until", "2026-09-30")
        self.assertIn("1 livrable(s) avec une section Critic · 3 objection(s)", sortie)
        self.assertIn("2026-09-20-ancien.md", sortie)
        # --depuis seul : jusqu'à aujourd'hui
        sortie = self.lancer("--since", "2026-09-01")
        self.assertIn("du 2026-09-01 au 2026-10-15", sortie)
        self.assertIn("4 livrable(s) avec une section Critic · 9 objection(s)", sortie)
        # bornes incluses
        sortie = self.lancer("--since", "2026-10-03", "--until", "2026-10-03")
        self.assertIn("1 livrable(s) avec une section Critic", sortie)

    def test_debut_de_mois_porte_sur_le_mois_ecoule(self):
        sortie = self.lancer(aujourdhui="2026-10-04")
        self.assertIn("du 2026-09-01 au 2026-09-30", sortie)
        self.assertIn("2026-09-20-ancien.md", sortie)

    def test_date_du_nom_sinon_date_du_fichier(self):
        self.ecrire("sans-date-dans-le-nom.md", DIAGNOSTIC, mtime="2026-10-09T10:00:00")
        self.ecrire("2026-13-45-date-impossible.md", MESSAGE, mtime="2026-10-11T10:00:00")
        sortie = self.lancer()
        self.assertIn("## sans-date-dans-le-nom.md · 2026-10-09", sortie)
        self.assertIn("## 2026-13-45-date-impossible.md · 2026-10-11", sortie)

    def test_dossier_absent_ou_vide(self):
        shutil.rmtree(self.sortie_dir)
        sortie = self.lancer()
        self.assertIn("0 livrable(s) avec une section Critic · 0 objection(s) · 0 livrable(s)", sortie)

    def test_plusieurs_postures_dans_un_livrable(self):
        self.ecrire("2026-10-14-double.md", "[Posture : Discovery]\n\nA.\n\n[Bascule vers Scaling]\n\n"
                                            "[Posture : Scaling]\n\nB.\n\n## Revue de Critic\n\n[Posture : Critic]\n\n- Une objection.\n")
        self.assertIn("2026-10-14-double.md · 2026-10-14 · livrable de posture · posture Discovery, Scaling",
                      self.lancer())


class VocabulaireCommun(unittest.TestCase):
    """Le miroir lit le même vocabulaire que le jeu d'essai (tests/postures/vocabulaire.yaml)."""

    def test_le_fichier_est_celui_du_jeu_d_essai(self):
        self.assertEqual(miroir.VOCABULARY_FILE, Path(__file__).resolve().parents[2] / "tests" / "postures" / "vocabulaire.yaml")
        self.assertEqual(sorted(miroir.load_vocabulary()), ["en", "fr"])

    def test_formules_francaises_toujours_reconnues(self):
        for ligne in ("Ce que Critic conteste", "Ce que Critic a relevé :", "Objections de Critic", "Revue de Critic"):
            self.assertTrue(miroir.START_PLAIN.match(ligne), ligne)
        for ligne in ("Corrections faites", "Points non corrigés", "Point non corrigé", "Second passage",
                      "Rien n'est enregistré", "Ce que j'en retiens", "Prochaines étapes"):
            self.assertTrue(miroir.PLAIN_END.match(ligne), ligne)
        self.assertEqual(miroir.POSTURE.findall("[Posture : Scaling] et [Posture : Critic]"), ["Scaling", "Critic"])

    def test_formules_anglaises_reconnues(self):
        for ligne in ("What Critic challenges", "Critic's objections", "Critic's review"):
            self.assertTrue(miroir.START_PLAIN.match(ligne), ligne)
        for ligne in ("Corrections made", "Points not corrected", "Second pass", "What I take from it", "Next steps"):
            self.assertTrue(miroir.PLAIN_END.match(ligne), ligne)
        self.assertEqual(miroir.POSTURE.findall("[Posture: Delivery]"), ["Delivery"])

    def test_une_formule_ajoutee_au_vocabulaire_est_reconnue(self):
        vocabulaire = miroir.load_vocabulary()
        vocabulaire["fr"]["critic_plain_start"] = vocabulaire["fr"]["critic_plain_start"] + ["Avis de Critic"]
        debut, fin, balise = miroir.build_patterns(vocabulaire)
        self.assertTrue(debut.match("Avis de Critic"))
        self.assertIsNone(miroir.START_PLAIN.match("Avis de Critic"))

    def test_un_livrable_en_anglais_donne_ses_objections(self):
        lignes = ["# Diagnostic", "- **Posture:** Delivery", "", "What Critic challenges", "1. The title goes beyond the data.",
                  "2. A source is cited for another object.", "Corrections made", "- the title is reworded"]
        sections = miroir.critic_sections(lignes)
        self.assertEqual(len(sections), 1)
        self.assertEqual(len(miroir.objections(sections[0])), 2)


if __name__ == "__main__":
    unittest.main()
