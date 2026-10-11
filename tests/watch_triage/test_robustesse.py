"""
Tests de robustesse du pré-tri (tools/watch_triage.py) : réponses inutilisables du modèle, relances après délai
dépassé, fusion des références d'un passage à l'autre, ordre de la liste « à lire » à dates égales.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/watch_triage -v

Faux modèle : `httpx.post` est remplacé par une fonction scénarisée ; `library.embed` par un vecteur déterministe.
Aucun accès réseau, aucun modèle local, aucun dossier réel : tout est dans le dossier temporaire de la classe Base voisine.
"""
import argparse
import contextlib
import datetime as dt
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_triage as tri  # noqa: E402
import watch_lab as veille  # noqa: E402
import watch_paths  # noqa: E402
import test_watch_triage as voisin  # noqa: E402

CRITERES = list(tri.CRITERIA)
ARGS_SCORE = dict(limit=0, rescore=False, no_model=False, compilations=False, promotional=False, max_substance=None)


def reponse_valide(n: int = 5) -> dict:
    item = lambda ok: {"justification": "j", "ok": ok}  # noqa: E731
    reponse = {"resume": "résumé", "pourquoi": "pourquoi", "compilation": item(False),
               "dans_themes": item(True), "promotionnel": item(False)}
    reponse.update({k: item(i < n) for i, k in enumerate(CRITERES)})
    return reponse


def reponse_http(contenu=None, *, corps=None, statut=200, texte=""):
    """Réponse httpx minimale : `contenu` est le texte renvoyé par le modèle, `corps` remplace tout le JSON."""
    return types.SimpleNamespace(
        status_code=statut, text=texte, raise_for_status=lambda: None,
        json=lambda: corps if corps is not None else {"message": {"content": contenu}})


def faux_embed(textes):
    return [np.array([1.0, 0.0], dtype=np.float32) for _ in textes]


class Notation(voisin.Base):
    """Réponses inutilisables, délais dépassés et relances, vus de judge() puis de la commande score."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(tri.library, "embed", side_effect=faux_embed)
        patch.start()
        self.addCleanup(patch.stop)
        tri.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tri.CONFIG_FILE.write_text(
            "mode: observation\nmodel: faux\nto_read: 5\ndays: 7\nsubstance_threshold: 3\nthemes:\n  - t\n"
            "shadow:\n  enabled: false\n  language: en\n", encoding="utf-8")

    def article(self, nom):
        (self.articles / nom).write_text(
            f"---\ntitle: Titre {nom}\nurl: https://s.test/{nom}\nsource: s.test\npublished: 2026-10-01\n"
            f"collected: {dt.date.today().isoformat()}\ncomplete: true\n---\n\ntexte inventé de {nom}\n", encoding="utf-8")

    def noter(self, scenario) -> tuple[str, list]:
        """Lance `score` avec un faux modèle. `scenario(nom_de_l_article, numero_d_appel)` renvoie la réponse HTTP
        ou lève l'exception à simuler. Renvoie la sortie et la liste des (article, numéro d'appel)."""
        appels = []

        def faux_post(url, json=None, timeout=None):  # noqa: A002
            texte = json["messages"][1]["content"]
            nom = next(n for n in ("a1.md", "a2.md") if f"texte inventé de {n}" in texte)
            numero = sum(1 for a, _ in appels if a == nom) + 1
            appels.append((nom, numero))
            return scenario(nom, numero)

        with mock.patch.object(tri.httpx, "post", side_effect=faux_post):
            sortie = self.lancer(tri.cmd_score, **ARGS_SCORE)
        return sortie, appels

    def notes(self):
        return {r["file"]: r["substance"] for r in self.connection.execute("SELECT file, substance FROM scores")}

    # -- réponses inutilisables ---------------------------------------------

    def test_judge_refuse_les_reponses_vides_mal_formees_ou_hors_plage(self):
        article = {"title": "t", "source": "s", "body": "corps"}
        incomplete = reponse_valide()
        incomplete.pop(CRITERES[1])
        hors_plage = reponse_valide()
        hors_plage[CRITERES[0]]["ok"] = 7          # ni vrai ni faux
        en_chaine = reponse_valide()
        en_chaine[CRITERES[2]]["ok"] = "oui"       # texte à la place d'un booléen
        sans_objet = reponse_valide()
        sans_objet[CRITERES[3]] = "oui"            # le critère n'est pas un objet
        cas = {"vide": "", "pas du json": "pas du json", "tronque": '{"resume": "x", "compil',
               "critere manquant": json.dumps(incomplete), "valeur hors plage": json.dumps(hors_plage),
               "texte au lieu d'un booleen": json.dumps(en_chaine), "critere sans objet": json.dumps(sans_objet)}
        for nom, contenu in cas.items():
            with self.subTest(nom), mock.patch.object(tri.httpx, "post", return_value=reponse_http(contenu)):
                with self.assertRaises(ValueError):
                    tri.judge("faux", ["t"], article)

    def test_judge_accepte_une_reponse_valide_et_calcule_la_substance(self):
        article = {"title": "t", "source": "s", "body": "corps"}
        with mock.patch.object(tri.httpx, "post", return_value=reponse_http(json.dumps(reponse_valide(4)))):
            verdict = tri.judge("faux", ["t"], article)
        self.assertEqual(sum(verdict["criteria"].values()), 4)

    def test_un_article_a_la_reponse_inutilisable_n_est_pas_note_et_la_suite_continue(self):
        self.article("a1.md")
        self.article("a2.md")
        mauvaises = {"vide": "", "mal formee": "pas du json", "hors plage": json.dumps(
            {**reponse_valide(), CRITERES[0]: {"justification": "j", "ok": 7}})}
        for nom, contenu in mauvaises.items():
            with self.subTest(nom):
                self.connection.execute("DELETE FROM scores")
                self.connection.commit()
                sortie, _ = self.noter(lambda n, k, c=contenu: reponse_http(
                    c if n == "a1.md" else json.dumps(reponse_valide(4))))
                self.assertEqual(self.notes(), {"a2.md": 4})   # a1 n'a pas de note, surtout pas une note fausse
                self.assertIn("NON NOTÉ", sortie)
                self.assertIn("repris au prochain passage", sortie)

    def test_une_reponse_json_qui_n_est_pas_un_objet_n_arrete_pas_le_passage(self):
        # "[]" ou "null" : JSON valide mais pas un objet ; judge() le refuse (ValueError), l'article n'est pas noté
        # et le passage continue (écart de R-1, corrigé par R-19).
        self.article("a1.md")
        self.article("a2.md")
        sortie, _ = self.noter(lambda n, k: reponse_http("[]" if n == "a1.md" else json.dumps(reponse_valide(4))))
        self.assertEqual(self.notes(), {"a2.md": 4})
        self.assertIn("NON NOTÉ (réponse illisible du modèle : objet attendu, reçu list)", sortie)

    def test_une_enveloppe_sans_message_n_arrete_pas_le_passage(self):
        # Un corps de réponse sans « message » : judge() le refuse (ValueError), l'article n'est pas noté et le passage
        # continue (écart de R-1, corrigé par R-19).
        self.article("a1.md")
        self.article("a2.md")
        sortie, _ = self.noter(lambda n, k: reponse_http(corps={"error": "x"}) if n == "a1.md"
                               else reponse_http(json.dumps(reponse_valide(4))))
        self.assertEqual(self.notes(), {"a2.md": 4})
        self.assertIn("NON NOTÉ (réponse du modèle sans message)", sortie)

    # -- délais dépassés et relances ------------------------------------------

    def test_judge_ne_relance_pas_lui_meme_un_delai_depasse(self):
        article = {"title": "t", "source": "s", "body": "corps"}
        with mock.patch.object(tri.httpx, "post", side_effect=httpx.ReadTimeout("lent")) as post:
            with self.assertRaises(ValueError) as erreur:
                tri.judge("faux", ["t"], article)
        self.assertEqual(post.call_count, 1)
        self.assertIn(str(tri.JUDGE_TIMEOUT), str(erreur.exception))

    def test_delai_depasse_puis_succes_relance_une_fois_et_note(self):
        self.article("a1.md")
        sortie, appels = self.noter(lambda n, k: (_ for _ in ()).throw(httpx.ReadTimeout("lent")) if k == 1
                                    else reponse_http(json.dumps(reponse_valide(4))))
        self.assertEqual(appels, [("a1.md", 1), ("a1.md", 2)])
        self.assertEqual(self.notes(), {"a1.md": 4})
        self.assertNotIn("NON NOTÉ", sortie)

    def test_deux_delais_depasses_de_suite_ne_notent_pas_et_ne_relancent_pas_plus(self):
        self.article("a1.md")
        self.article("a2.md")
        sortie, appels = self.noter(lambda n, k: (_ for _ in ()).throw(httpx.ReadTimeout("lent")) if n == "a1.md"
                                    else reponse_http(json.dumps(reponse_valide(3))))
        self.assertEqual([a for a in appels if a[0] == "a1.md"], [("a1.md", 1), ("a1.md", 2)])   # une seule relance
        self.assertEqual(self.notes(), {"a2.md": 3})
        self.assertIn("NON NOTÉ", sortie)
        self.assertIn("pas de réponse du modèle", sortie)

    def test_reponse_inutilisable_puis_valide_est_aussi_relancee_une_fois(self):
        self.article("a1.md")
        sortie, appels = self.noter(lambda n, k: reponse_http("" if k == 1 else json.dumps(reponse_valide(5))))
        self.assertEqual(len(appels), 2)
        self.assertEqual(self.notes(), {"a1.md": 5})

    def test_modele_sans_mode_de_reflexion_repete_la_requete_sans_think(self):
        article = {"title": "t", "source": "s", "body": "corps"}
        charges = []

        def faux_post(url, json=None, timeout=None):  # noqa: A002
            charges.append("think" in json)
            if "think" in json:
                return reponse_http(statut=400, texte="model does not support think")
            return reponse_http(__import__("json").dumps(reponse_valide(2)))

        with mock.patch.object(tri.httpx, "post", side_effect=faux_post):
            verdict = tri.judge("faux", ["t"], article)
        self.assertEqual(charges, [True, False])
        self.assertEqual(sum(verdict["criteria"].values()), 2)

    def test_modele_inconnu_arrete_avec_la_commande_pour_le_telecharger(self):
        article = {"title": "t", "source": "s", "body": "corps"}
        with mock.patch.object(tri.httpx, "post", return_value=reponse_http(statut=404)):
            with self.assertRaises(SystemExit) as erreur:
                tri.judge("faux", ["t"], article)
        self.assertIn("ollama pull faux", str(erreur.exception))


class FusionDesReferences(voisin.Base):
    def lancer_references(self, refs):
        args = argparse.Namespace(claude_export=["x.zip"], without_own=True)
        with mock.patch.object(tri, "signalpm_references", return_value=refs), \
                mock.patch.object(tri.library, "embed", side_effect=lambda t: [voisin.vecteur(0) for _ in t]), \
                contextlib.redirect_stdout(io.StringIO()):
            tri.cmd_references(args)
        return dict(self.connection.execute("SELECT url, origin FROM refs").fetchall())

    @staticmethod
    def ref(url):
        return {"url": url, "title": url, "origin": "signalpm", "text": "réponse " + url}

    def test_un_second_passage_remplace_les_references_et_ne_les_ajoute_pas(self):
        self.connection.execute("INSERT INTO refs VALUES ('p', 'p', 'partage', ?)", (tri.to_blob(voisin.vecteur(0)),))
        self.connection.commit()
        premier = self.lancer_references([self.ref("https://x.test/a"), self.ref("https://x.test/b")])
        self.assertEqual(set(premier), {"p", "https://x.test/a", "https://x.test/b"})
        second = self.lancer_references([self.ref("https://x.test/c")])
        self.assertEqual(set(second), {"p", "https://x.test/c"})   # a et b ont disparu, le partage reste
        self.assertEqual(second["p"], "partage")

    def test_relancer_avec_les_memes_references_ne_les_duplique_pas(self):
        refs = [self.ref("https://x.test/a"), self.ref("https://x.test/b")]
        self.lancer_references(refs)
        self.lancer_references(refs)
        nombre = self.connection.execute("SELECT COUNT(*) FROM refs WHERE origin = 'signalpm'").fetchone()[0]
        self.assertEqual(nombre, 2)


class OrdreADatesEgales(voisin.Base):
    """Dates de publication identiques : la date ne départage rien, la pertinence décide, puis l'ordre d'insertion."""

    def titres_a_lire(self):
        self.lancer(tri.cmd_digest)
        texte = veille.to_read_file().read_text(encoding="utf-8")
        a_lire = texte.split("## Les autres")[0]
        return [ligne.split("](")[0][5:] for ligne in a_lire.splitlines() if ligne.startswith("### [")]

    def reglages(self):
        tri.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tri.CONFIG_FILE.write_text("mode: observation\nmodel: faux\nto_read: 5\ndays: 7\nsubstance_threshold: 3\n"
                                   "themes:\n  - t\n", encoding="utf-8")

    def ajouter_recent(self, nom, angle):
        self.ajouter(nom, 4)
        self.connection.execute("UPDATE scores SET published = '2026-10-01', collected = ?, vector = ? WHERE file = ?",
                                (dt.date.today().isoformat(), tri.to_blob(voisin.vecteur(angle)), nom))
        self.connection.commit()

    def test_a_dates_egales_la_plus_pertinente_vient_d_abord(self):
        self.reglages()
        for nom, angle in (("c.md", 0.9), ("a.md", 0.1), ("b.md", 0.5)):   # insérés dans le désordre
            self.ajouter_recent(nom, angle)
        self.assertEqual(self.titres_a_lire(), ["Titre a.md", "Titre b.md", "Titre c.md"])

    def test_a_pertinence_et_date_egales_l_ordre_est_stable_d_un_passage_a_l_autre(self):
        self.reglages()
        for nom in ("m.md", "k.md", "z.md"):
            self.ajouter_recent(nom, 0.3)
        premier = self.titres_a_lire()
        self.assertEqual(sorted(premier), ["Titre k.md", "Titre m.md", "Titre z.md"])
        for _ in range(3):
            self.assertEqual(self.titres_a_lire(), premier)


if __name__ == "__main__":
    unittest.main()
