"""
Tests du lot 5b anglais, groupe 1 : langue des prompts de décision, seuil de pertinence, couche locale des réglages.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/watch_triage -v

Même dossier temporaire et même faux modèle que les fichiers voisins : jamais Watch-Lab, watch/ ni ~/.pmzilla-lab.
Couvre : réglage `language` (absent, fr, en, valeur refusée), prompts envoyés au modèle selon la langue, module anglais
inutilisable (arrêt sans repli), réglage `relevance_threshold` (bornes), raison d'écart de pertinence limitée à la
période, repêchage et rejet à la main, ligne de règle de _to-read.md, `thresholds` (matrice, deux propositions,
enregistrement des deux seuils, feuille inchangée), couche locale `tri.local.yaml` (fusion, clé inconnue, avertissement
sans la valeur, `set_config` qui n'y écrit jamais), fichier créé au premier lancement.
"""
import contextlib
import datetime as dt
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_triage as tri  # noqa: E402
import watch_lab as veille  # noqa: E402
import flux_config  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402
import test_watch_triage as voisin  # noqa: E402
import test_shadow as ombre  # noqa: E402

AUJOURD_HUI = dt.date.today().isoformat()
COMPTE = "compte-invente.test"


def ecrire_reglages(extra: str = "", mode: str = "observation") -> None:
    tri.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tri.CONFIG_FILE.write_text(f"mode: {mode}\nmodel: faux\nto_read: 5\ndays: 7\nsubstance_threshold: 3\n"
                               f"themes:\n  - t\n{extra}", encoding="utf-8")


def stderr_de(fonction):
    """Lance `fonction` et rend (son résultat, ce qu'elle a écrit sur stderr) ; avertissements remis à zéro."""
    erreur = io.StringIO()
    with contextlib.redirect_stderr(erreur), contextlib.redirect_stdout(io.StringIO()):
        resultat = fonction()
    return resultat, erreur.getvalue()


class Langue(ombre.Ombre):
    def capture(self):
        envoyees = []

        def faux(url, json=None, timeout=None):
            envoyees.append(json)
            return ombre.FauxModele()(url, json=json, timeout=timeout)
        patch = mock.patch.object(httpx, "post", faux)
        patch.start()
        self.addCleanup(patch.stop)
        return envoyees

    def test_absente_vaut_francais(self):
        self.reglages()
        self.assertEqual(tri.config()["language"], "fr")

    def test_fr_et_en_acceptees(self):
        for langue in ("fr", "en"):
            self.reglages(extra=f"language: {langue}\n")
            self.assertEqual(tri.config()["language"], langue)

    def test_autre_valeur_refusee_avec_la_ligne_sans_la_valeur(self):
        self.reglages(extra="language: klingon\n")
        with self.assertRaises(ErreurConfig) as erreur:
            tri.config()
        message = str(erreur.exception)
        self.assertIn("L11 : language doit valoir fr ou en.", message)
        self.assertNotIn("klingon", message)

    def test_francais_charge_utile_identique(self):
        self.reglages()
        envoyees = self.capture()
        self.article("a1.md", "§3")
        self.noter()
        self.assertEqual(envoyees[0]["messages"][0]["content"], tri.SYSTEM_PROMPT.format(themes="t"))
        criteres = "\n".join(f"- {k} : {q}" for k, (q, _) in tri.CRITERIA.items())
        self.assertIn(criteres, envoyees[0]["messages"][1]["content"])

    def test_anglais_envoie_les_prompts_anglais_avec_les_themes_des_reglages(self):
        self.reglages(extra="language: en\n")
        envoyees = self.capture()
        self.article("a1.md", "§4")
        self.noter()
        systeme = envoyees[0]["messages"][0]["content"]
        self.assertTrue(systeme.startswith("You evaluate"))
        self.assertIn("Themes: t.", systeme)                 # thèmes des réglages, pas THEMES du module
        self.assertIn("question these", envoyees[0]["messages"][1]["content"])
        self.assertEqual(self.note_de("a1.md")["substance"], 4)

    def test_module_anglais_inutilisable_arrete_sans_repli(self):
        self.reglages(extra="language: en\n")
        envoyees = self.capture()
        self.article("a1.md", "§4")
        with mock.patch.object(tri, "load_shadow_prompts", side_effect=ValueError("« CRITERIA » manque")):
            with self.assertRaises(SystemExit) as erreur:
                self.noter()
        self.assertIn("Prompts de la langue en inutilisables (watch_prompts_en)", str(erreur.exception.code))
        self.assertEqual(envoyees, [])
        self.assertEqual(self.store.all_scores(), [])


class SeuilPertinence(voisin.Base):
    def reglages(self, extra="", mode="observation"):
        ecrire_reglages(extra, mode)

    def test_reglage_borne(self):
        for valeur in ("-1", "101", "12.5", "true", "beaucoup"):
            self.reglages(f"relevance_threshold: {valeur}\n")
            with self.assertRaises(ErreurConfig) as erreur:
                tri.config()
            message = str(erreur.exception)
            self.assertIn("L8 : relevance_threshold doit être un entier de 0 à 100.", message)
            self.assertNotIn(valeur, message.replace("100", "").replace("L8", ""))
        for valeur in ("0", "50", "100"):
            self.reglages(f"relevance_threshold: {valeur}\n")
            self.assertEqual(tri.config()["relevance_threshold"], int(valeur))

    def test_absent_ne_change_rien(self):
        self.reglages()
        self.ajouter("proche.md", 5, collecte=AUJOURD_HUI)
        self.ajouter("loin.md", 5, collecte=AUJOURD_HUI)
        self.assertEqual(tri.config().get("relevance_threshold", 0), 0)
        self.assertEqual(self.ligne("loin.md")["reasons"], [])

    def test_article_recent_sous_le_seuil_ecarte_puis_sorti(self):
        self.reglages("relevance_threshold: 60\n", mode="filtre")
        self.ajouter("proche.md", 5, collecte=AUJOURD_HUI)
        self.ajouter("loin.md", 5, collecte=AUJOURD_HUI)
        self.assertEqual(self.ligne("loin.md")["reasons"], ["pertinence 0/100 sous le seuil 60"])
        self.assertEqual(self.ligne("proche.md")["reasons"], [])
        sortie = self.lancer(tri.cmd_apply)
        self.assertIn("1 article(s) sorti(s)", sortie)
        self.assertEqual([p.name for p in self.articles.glob("*.md")], ["proche.md"])

    def test_article_ancien_jamais_ecarte_par_la_pertinence(self):
        self.reglages("relevance_threshold: 60\n", mode="filtre")
        self.ajouter("proche.md", 5, collecte=AUJOURD_HUI)
        self.ajouter("ancien.md", 5, collecte="2020-01-01")
        self.assertEqual(self.ligne("ancien.md")["reasons"], [])
        self.lancer(tri.cmd_apply)
        self.assertTrue((self.articles / "ancien.md").exists())

    def test_repechage_et_rejet_a_la_main(self):
        self.reglages("relevance_threshold: 60\n", mode="filtre")
        self.ajouter("proche.md", 5, collecte=AUJOURD_HUI)
        self.ajouter("loin.md", 5, collecte=AUJOURD_HUI)
        self.store.restore("loin.md", "2026-10-02")
        self.store.exclude("proche.md", "2026-10-02")
        self.store.commit()
        self.assertEqual(self.ligne("loin.md")["reasons"], [])
        self.assertEqual(self.ligne("proche.md")["reasons"], ["écarté à la main"])
        self.lancer(tri.cmd_apply)
        self.assertTrue((self.articles / "loin.md").exists())

    def test_ligne_de_regle_de_la_liste_de_lecture(self):
        self.reglages("relevance_threshold: 40\n")
        self.ajouter("proche.md", 5, collecte=AUJOURD_HUI)
        self.lancer(tri.cmd_digest)
        texte = veille.to_read_file().read_text(encoding="utf-8")
        self.assertIn("substance d'au moins 3/5, pertinence d'au moins 40/100.", texte)
        self.reglages()
        self.lancer(tri.cmd_digest)
        self.assertNotIn("pertinence d'au moins", veille.to_read_file().read_text(encoding="utf-8"))

    def test_comparaison_des_langues_sans_pertinence(self):
        """discard_reasons sans seuil de pertinence : la règle de shadow-report ne change pas."""
        ligne = {"substance": 5, "criteria": {k: True for k in tri.CRITERIA}, "pertinence": 0}
        self.assertEqual(tri.discard_reasons(ligne, 3), [])

    def test_raisons_dans_l_ordre_des_criteres_quel_que_soit_l_ordre_des_cles(self):
        """Les critères relus de la base (jsonb) arrivent dans un autre ordre de clés : mêmes raisons, ordre du code."""
        cles = list(tri.CRITERIA)
        manquants = {"etaye", "these"}
        endroit = {k: k not in manquants for k in cles}
        envers = {k: k not in manquants for k in reversed(cles)}
        self.assertNotEqual(list(endroit), list(envers))
        attendu = [tri.CRITERIA[k][1] for k in cles if k in manquants]
        for criteres in (endroit, envers):
            ligne = {"substance": 3, "criteria": criteres, "pertinence": 0}
            self.assertEqual(tri.discard_reasons(ligne, 4), attendu)


def jeu_pertinence(self):
    """Dix articles, du plus proche au plus loin : rangs 100, 89, 78, 67, 56, 44, 33, 22, 11, 0.
    Les bons sont proches sauf g5 ; tous ont une substance de 4 ou 5, donc la substance seule ne trie pas."""
    for nom, substance in [("g1", 5), ("g2", 4), ("g3", 4), ("g4", 4), ("e1", 4), ("e2", 4), ("e3", 4), ("g5", 4),
                           ("e4", 4), ("e5", 4)]:
        self.ajouter(f"{nom}.md", substance)


AVIS_PERTINENCE = {**{k: "g" for k in ("g1", "g2", "g3", "g4", "g5")}, **{k: "e" for k in ("e1", "e2", "e3", "e4", "e5")}}


class SeuilsAvecPertinence(voisin.Base):
    def setUp(self):
        super().setUp()
        jeu_pertinence(self)
        with contextlib.redirect_stdout(io.StringIO()):
            tri.config()
        self.exporter()
        voisin.remplir_avis(AVIS_PERTINENCE)
        self.importer()

    def test_matrice_et_deux_propositions_sans_rien_ecrire(self):
        avant = tri.CONFIG_FILE.read_bytes()
        feuille = tri.CALIBRATION_FILE.read_bytes()
        sortie = self.lancer(tri.cmd_thresholds, save=False)
        self.assertIn("pertinence \\ substance (bons perdus/faibles gardés)", sortie)
        self.assertIn("Proposition (substance seule) : substance_threshold: 0 "
                      "(perd 0 bon(s) article(s), garde 5 article(s) faible(s)).", sortie)
        self.assertIn("Proposition (substance et pertinence) : substance_threshold: 0, relevance_threshold: 60 "
                      "(accord 9/10, perd 1 bon(s) article(s), garde 0 article(s) faible(s)).", sortie)
        self.assertIn("restore g5.md", sortie)
        self.assertRegex(sortie, r"\n\s*60\s+1/0\s")       # ligne r = 60, colonne s = 0
        self.assertEqual(tri.CONFIG_FILE.read_bytes(), avant)
        self.assertEqual(tri.CALIBRATION_FILE.read_bytes(), feuille)

    def test_enregistrer_ecrit_les_deux_seuils_et_garde_le_mode(self):
        feuille = tri.CALIBRATION_FILE.read_bytes()
        sortie = self.lancer(tri.cmd_thresholds, save=True)
        self.assertIn("Enregistré dans", sortie)
        reglages = tri.config()
        self.assertEqual((reglages["substance_threshold"], reglages["relevance_threshold"], reglages["mode"]),
                         (0, 60, "observation"))
        self.assertIn("# nombre minimal de critères remplis", tri.CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual(tri.CALIBRATION_FILE.read_bytes(), feuille)


class CoucheLocale(voisin.Base):
    def local(self, texte):
        tri.local_config_file().write_text(texte, encoding="utf-8")

    def test_identifiant_local_utilise_par_les_partages(self):
        ecrire_reglages()
        self.local(f"bluesky: {COMPTE}\n")
        reglages, erreur = stderr_de(tri.config)
        self.assertEqual(reglages["bluesky"], COMPTE)
        self.assertEqual(erreur, "")
        with mock.patch.object(veille, "links_from_bluesky", return_value=[]) as faux:
            self.lancer(tri.cmd_shares, pages=1)
        self.assertEqual(faux.call_args.args[1], COMPTE)

    def test_sans_fichier_local_etape_sautee_en_nommant_le_fichier_local(self):
        ecrire_reglages()
        sortie = self.lancer(tri.cmd_shares, pages=1)
        self.assertIn("Partages : pas d'identifiant Bluesky dans tri.local.yaml (ligne « bluesky: »), étape sautée.",
                      sortie)

    def test_cle_inconnue_refusee_avec_la_ligne(self):
        ecrire_reglages()
        self.local(f"bluesky: {COMPTE}\nmode: filtre\n")
        with self.assertRaises(ErreurConfig) as erreur:
            tri.config()
        message = str(erreur.exception)
        self.assertIn("tri.local.yaml : L2 : clé « mode » inconnue (clés admises : bluesky).", message)
        self.assertNotIn(COMPTE, message)

    def test_cle_dupliquee_ou_fichier_non_dictionnaire_refuses(self):
        ecrire_reglages()
        for texte in (f"bluesky: {COMPTE}\nbluesky: autre\n", "- bluesky\n"):
            self.local(texte)
            with self.assertRaises(ErreurConfig) as erreur:
                tri.config()
            self.assertNotIn(COMPTE, str(erreur.exception))

    def test_identifiant_dans_tri_yaml_refuse_sans_la_valeur(self):
        ecrire_reglages(f"bluesky: {COMPTE}\n")
        with self.assertRaises(ErreurConfig) as erreur:
            tri.config()
        message = str(erreur.exception)
        self.assertIn("« bluesky » n'est plus admis ici", message)
        self.assertIn("tri.local.yaml", message)
        self.assertIn("L8", message)
        self.assertNotIn(COMPTE, message)

    def test_set_config_n_ecrit_jamais_le_fichier_local(self):
        ecrire_reglages()
        self.local(f"bluesky: {COMPTE}\n")
        avant = tri.local_config_file().read_bytes()
        tri.set_config("substance_threshold", 4)
        tri.set_config("bluesky", "x")
        self.assertEqual(tri.local_config_file().read_bytes(), avant)

    def test_premier_lancement_langue_explicite_sans_identifiant(self):
        self.assertFalse(tri.CONFIG_FILE.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            reglages = tri.config()
        texte = tri.CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("\nlanguage: fr", texte)
        self.assertNotRegex(texte, r"(?m)^bluesky\s*:")
        self.assertIn("tri.local.yaml", texte)
        self.assertEqual((reglages["language"], reglages.get("bluesky")), ("fr", None))


if __name__ == "__main__":
    unittest.main()
