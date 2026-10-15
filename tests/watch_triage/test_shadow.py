"""
Tests de la notation « en ombre » du pré-tri (lot 5b anglais) : tools/watch_triage.py, tools/watch_config.py.

    uv run --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/watch_triage -v

Faux modèle : `httpx.post` est remplacé par une fonction qui répond comme Ollama, en français ou en anglais selon le
prompt système reçu, et `library.embed` par un vecteur déterministe. Aucun accès réseau, aucun modèle local, aucun
dossier réel (Watch-Lab, watch/, ~/.pmzilla-lab) : tout est dans le dossier temporaire et le faux magasin en mémoire de la
classe Base du fichier voisin.
Couvre : réglage `shadow` (défaut, validation stricte), aucune notation en plus quand l'ombre est inactive, une ligne
par article quand elle est active (avec l'empreinte des prompts), PREUVE que l'ombre ne change aucune décision
(scores, classement, _to-read.md, articles écartés), échecs de l'ombre sans effet sur la note française, shadow-report
(accords, écarts, avis de calibration, désaccords, sortie vide, aucun fichier écrit) et contrat du module de prompts anglais.
"""
import argparse
import contextlib
import datetime as dt
import importlib
import io
import json
import json as jsonlib
import re
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
import watch_config  # noqa: E402
import watch_lab as veille  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402
import test_watch_triage as voisin  # noqa: E402

CRITERES = list(tri.CRITERIA)
REPO = Path(__file__).resolve().parents[2]


def faux_module_anglais() -> types.SimpleNamespace:
    """Un module de prompts conforme au contrat, sans dépendre du vrai fichier."""
    return types.SimpleNamespace(
        SYSTEM_PROMPT="You evaluate articles. Themes: {themes}.",
        USER_PROMPT="Title: {title}\nSource: {source}\n\nText:\n{text}\n\n{criteria}",
        CRITERIA={k: (f"question {k}", f"raison {k}") for k in CRITERES}, THEMES=["theme one", "theme two"])


def reponse_modele(langue: str, texte: str) -> dict:
    """Réponse du faux modèle. Le texte de l'article porte ses consignes : §N = N critères remplis, §SHIFT = deux de
    moins en anglais, §HT = hors thèmes en français seulement."""
    n = int(re.search(r"§(\d)", texte).group(1))
    if langue == "en" and "§SHIFT" in texte:
        n = max(0, n - 2)
    item = lambda ok: {"justification": "j", "ok": ok}  # noqa: E731
    answer = {"resume": f"résumé {langue}", "pourquoi": f"pourquoi {langue}", "compilation": item(False),
              "dans_themes": item(not ("§HT" in texte and langue == "fr")), "promotionnel": item(False)}
    answer.update({k: item(i < n) for i, k in enumerate(CRITERES)})
    return answer


class FauxModele:
    """Remplace httpx.post. `echec_en` : None, "valeur" (réponse illisible) ou "reseau" (ConnectError)."""

    def __init__(self, echec_en=None):
        self.appels = {"fr": 0, "en": 0}
        self.echec_en = echec_en

    def __call__(self, url, json=None, timeout=None):  # noqa: A002  (nom imposé par httpx.post)
        langue = "en" if json["messages"][0]["content"].startswith("You evaluate") else "fr"
        self.appels[langue] += 1
        if langue == "en" and self.echec_en == "reseau":
            raise httpx.ConnectError("faux réseau coupé")
        contenu = "pas du json" if (langue == "en" and self.echec_en == "valeur") else \
            jsonlib.dumps(reponse_modele(langue, json["messages"][1]["content"]))
        return types.SimpleNamespace(status_code=200, text="", raise_for_status=lambda: None,
                                     json=lambda: {"message": {"content": contenu}})


def faux_embed(textes):
    return [np.array([np.cos(0.01 * (len(t) % 60)), np.sin(0.01 * (len(t) % 60))], dtype=np.float32) for t in textes]


ARGS_SCORE = dict(limit=0, rescore=False, no_model=False, compilations=False, promotional=False, max_substance=None)


class Ombre(voisin.Base):
    def setUp(self):
        super().setUp()
        self.module_en = tri.check_prompts(faux_module_anglais(), "faux")
        for patch in (mock.patch.object(tri.library, "embed", side_effect=faux_embed),
                      mock.patch.object(tri, "load_shadow_prompts", return_value=self.module_en)):
            patch.start()
            self.addCleanup(patch.stop)

    def reglages(self, ombre=False, mode="filtre", extra=""):
        tri.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tri.CONFIG_FILE.write_text(
            f"mode: {mode}\nmodel: faux\nto_read: 5\ndays: 7\nsubstance_threshold: 3\nthemes:\n  - t\n"
            f"shadow:\n  enabled: {str(ombre).lower()}\n  language: en\n{extra}", encoding="utf-8")

    def article(self, nom, consigne):
        aujourd_hui = dt.date.today().isoformat()
        (self.articles / nom).write_text(
            f"---\ntitle: Titre {nom}\nurl: https://s.test/{nom}\nsource: s.test\npublished: 2026-10-01\n"
            f"collected: {aujourd_hui}\ncomplete: true\n---\n\n{consigne} texte inventé de {nom}\n", encoding="utf-8")

    def corpus(self):
        for nom, consigne in (("a1.md", "§5"), ("a2.md", "§4 §SHIFT"), ("a3.md", "§2"), ("a4.md", "§4 §HT"),
                              ("a5.md", "§3"), ("a6.md", "§5 §SHIFT")):
            self.article(nom, consigne)

    def noter(self, **options) -> str:
        return self.lancer(tri.cmd_score, **{**ARGS_SCORE, **options})

    def lignes_ombre(self):
        return self.store.shadow_rows()

    def photo(self):
        """Tout ce que le pré-tri décide : notes, classement, liste à lire, articles écartés."""
        # scored_at est l'heure de la notation (à la seconde) : deux passages à cheval sur une seconde la font différer,
        # sans que cela soit une décision du pré-tri (cause de l'instabilité de test_l_ombre_ne_change_aucune_decision)
        notes = [{k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in note.items() if k != "scored_at"}
                 for note in self.store.all_scores()]
        self.lancer(tri.cmd_digest)
        classement = [{k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in ligne.items() if k != "scored_at"}
                      for ligne in tri.ranked(self.store)]
        return {"scores": notes, "ranked": classement,
                "to_read": veille.to_read_file().read_text(encoding="utf-8")}

    def photo_apres_apply(self):
        photo = self.photo()
        self.lancer(tri.cmd_apply)
        photo["ecartes"] = sorted(p.name for p in self.archive.glob("*.md"))
        photo["restants"] = sorted(p.name for p in self.articles.glob("*.md"))
        photo["locations"] = [(n["file"], n["location"]) for n in self.store.all_scores()]
        return photo

    def remettre_a_zero_sauf_les_notes(self):
        """Vide la table de l'ombre seule et remet les articles écartés dans la bibliothèque (les emplacements enregistrés restent)."""
        self.data.edit(lambda tables: tables["shadow"].clear())
        for nom in ("a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md"):
            self.modifier_note(nom, location="watch")
        for p in list(self.archive.glob("*.md")) if self.archive.exists() else []:
            p.rename(self.articles / p.name)
        veille.to_read_file().unlink(missing_ok=True)

    def remettre_a_zero(self):
        self.data.edit(lambda tables: [tables[nom].clear() for nom in ("scores", "shadow", "picks")])
        for p in list(self.archive.glob("*.md")) if self.archive.exists() else []:
            p.rename(self.articles / p.name)
        veille.to_read_file().unlink(missing_ok=True)


class Reglage(unittest.TestCase):
    def test_defaut_absent_ou_desactive(self):
        self.assertEqual(watch_config.shadow_settings(None), {"enabled": False, "language": "en"})
        self.assertEqual(watch_config.shadow_settings({}), {"enabled": False, "language": "en"})
        self.assertIn("enabled: false", tri.DEFAULT_CONFIG)
        reglages = watch_config.shadow_settings(charger(tri.DEFAULT_CONFIG, "tri.yaml").get("shadow"))
        self.assertEqual(reglages, {"enabled": False, "language": "en"})

    def test_le_tri_yaml_du_depot_a_un_bloc_shadow_valide(self):
        """La valeur de `enabled` est le choix de l'utilisateur (activée le 2026-10-09) : seule la validité du bloc est testée."""
        brut = charger((REPO / "watch" / "tri.yaml").read_text(encoding="utf-8"), "tri.yaml")
        reglages = watch_config.shadow_settings(brut.get("shadow"))
        self.assertIsInstance(reglages["enabled"], bool)
        self.assertEqual(reglages["language"], "en")

    def test_activation(self):
        self.assertEqual(watch_config.shadow_settings({"enabled": True, "language": "en"}), {"enabled": True, "language": "en"})

    def test_cle_inconnue_type_et_langue_refuses_sans_afficher_la_valeur(self):
        secret = "valeur-secrete-xyz"
        for bloc in ({"enabled": False, "langue": secret}, {"enabled": secret}, {"enabled": 1}, {"language": secret},
                     {"language": 3}, secret, [secret]):
            with self.assertRaises(ErreurConfig) as contexte:
                watch_config.shadow_settings(bloc)
            self.assertNotIn(secret, str(contexte.exception))

    def test_message_avec_numero_de_ligne_via_le_chargeur_strict(self):
        brut = charger("shadow:\n  enabled: true\n  bidon: 1\n", "tri.yaml")
        with self.assertRaises(ErreurConfig) as contexte:
            watch_config.shadow_settings(brut["shadow"])
        self.assertIn("L3", str(contexte.exception))
        self.assertIn("bidon", str(contexte.exception))

    def test_cle_ecrite_deux_fois_refusee_par_le_chargeur(self):
        with self.assertRaises(ErreurConfig):
            charger("shadow:\n  enabled: true\n  enabled: false\n", "tri.yaml")


class Notation(Ombre):
    def test_tri_config_refuse_un_reglage_faux(self):
        self.reglages(extra="")
        tri.CONFIG_FILE.write_text(tri.CONFIG_FILE.read_text(encoding="utf-8").replace("language: en", "language: fr"), encoding="utf-8")
        with self.assertRaises(ErreurConfig):
            tri.config()

    def test_inactive_aucune_ligne_et_aucun_appel_en_plus(self):
        self.reglages(ombre=False)
        self.corpus()
        faux = FauxModele()
        with mock.patch.object(httpx, "post", faux):
            self.noter()
        self.assertEqual(faux.appels, {"fr": 6, "en": 0})
        self.assertEqual(self.lignes_ombre(), [])
        tri.load_shadow_prompts.assert_not_called()

    def test_reglage_absent_equivaut_a_inactif(self):
        tri.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tri.CONFIG_FILE.write_text("mode: observation\nmodel: faux\nto_read: 5\ndays: 7\nsubstance_threshold: 3\nthemes:\n  - t\n", encoding="utf-8")
        self.article("a1.md", "§5")
        faux = FauxModele()
        with mock.patch.object(httpx, "post", faux):
            sortie = self.noter()
        self.assertEqual(faux.appels, {"fr": 1, "en": 0})
        self.assertNotIn("ombre", sortie)

    def test_active_une_ligne_par_article_avec_l_empreinte(self):
        self.reglages(ombre=True)
        self.corpus()
        faux = FauxModele()
        with mock.patch.object(httpx, "post", faux):
            sortie = self.noter()
        self.assertEqual(faux.appels, {"fr": 6, "en": 6})
        lignes = self.lignes_ombre()
        self.assertEqual(len(lignes), 6)
        self.assertEqual({l["language"] for l in lignes}, {"en"})
        self.assertEqual({l["model"] for l in lignes}, {"faux"})
        self.assertEqual({l["prompts_hash"] for l in lignes}, {tri.prompts_hash(self.module_en)})
        self.assertRegex(lignes[0]["prompts_hash"], r"^[0-9a-f]{12}$")
        par_url = {l["url"]: l for l in lignes}
        self.assertEqual(par_url["https://s.test/a2.md"]["substance"], 2)    # 4 en français, 2 en anglais (§SHIFT)
        self.assertEqual(self.note_de("a2.md")["substance"], 4)
        self.assertEqual(par_url["https://s.test/a1.md"]["criteria"], {k: True for k in CRITERES})
        self.assertIsNotNone(par_url["https://s.test/a1.md"]["scored_at"])
        self.assertEqual(list(self.tmp.rglob("*.sqlite")), [])           # aucun fichier local ne porte les notes en ombre
        self.assertRegex(sortie, r"Notation en ombre \(en\) : 6 notés, 0 échec\(s\), \+\d+ s")

    def test_l_empreinte_change_avec_les_prompts(self):
        autre = tri.check_prompts(faux_module_anglais(), "faux")
        autre.THEMES = ["theme one", "theme changed"]
        self.assertNotEqual(tri.prompts_hash(self.module_en), tri.prompts_hash(autre))
        autre = tri.check_prompts(faux_module_anglais(), "faux")
        autre.CRITERIA = {**autre.CRITERIA, "these": ("autre question", "raison these")}
        self.assertNotEqual(tri.prompts_hash(self.module_en), tri.prompts_hash(autre))

    def test_la_photo_ignore_l_heure_de_notation(self):
        """Régression de l'instabilité (R-11) : deux notations identiques à des secondes différentes donnent la même photo."""
        self.corpus()
        self.reglages(ombre=False)
        with mock.patch.object(httpx, "post", FauxModele()):
            self.noter()
        avant = self.photo()
        for nom in ("a1.md", "a2.md", "a3.md", "a4.md", "a5.md", "a6.md"):
            self.modifier_note(nom, scored_at=dt.datetime(2000, 1, 1, 0, 0, 1).astimezone())
        self.assertEqual(self.photo(), avant)

    def test_l_ombre_ne_change_aucune_decision(self):
        """Même corpus, ombre inactive puis active, avec un faux modèle anglais qui note autrement : mêmes notes, même
        classement, même _to-read.md, mêmes articles écartés."""
        self.corpus()
        self.reglages(ombre=False)
        with mock.patch.object(httpx, "post", FauxModele()):
            self.noter()
        sans = self.photo_apres_apply()
        self.assertTrue(sans["ecartes"])                    # le test discrimine : le filtre écarte bien quelque chose
        self.remettre_a_zero()
        self.reglages(ombre=True)
        with mock.patch.object(httpx, "post", FauxModele()):
            self.noter()
        self.assertEqual(len(self.lignes_ombre()), 6)
        decisions_en = {l["url"]: l["substance"] for l in self.lignes_ombre()}
        avec = self.photo_apres_apply()
        self.assertNotEqual(decisions_en["https://s.test/a2.md"], 4)   # l'anglais note bien autrement
        self.assertEqual(avec["scores"], sans["scores"])
        self.assertEqual(avec["ranked"], sans["ranked"])
        self.assertEqual(avec["to_read"], sans["to_read"])
        self.assertEqual(avec["ecartes"], sans["ecartes"])
        self.assertEqual(avec["restants"], sans["restants"])
        self.assertEqual(avec["locations"], sans["locations"])

    def test_echec_de_l_ombre_la_note_francaise_est_ecrite(self):
        for echec in ("valeur", "reseau"):
            with self.subTest(echec=echec):
                self.remettre_a_zero()
                self.reglages(ombre=True)
                self.corpus()
                faux = FauxModele(echec_en=echec)
                with mock.patch.object(httpx, "post", faux):
                    sortie = self.noter()          # aucune exception
                self.assertEqual(len(self.store.all_scores()), 6)
                self.assertEqual(self.lignes_ombre(), [])
                self.assertIn("0 notés, 6 échec(s)", sortie)
                self.assertEqual(faux.appels["fr"], 6)

    def test_echec_partiel_compte(self):
        self.reglages(ombre=True)
        self.corpus()
        vrai = FauxModele()

        def une_sur_deux(url, json=None, timeout=None):
            if json["messages"][0]["content"].startswith("You evaluate") and "a3.md" in json["messages"][1]["content"]:
                raise httpx.ReadTimeout("trop long")
            return vrai(url, json=json, timeout=timeout)
        with mock.patch.object(httpx, "post", une_sur_deux):
            sortie = self.noter()
        self.assertIn("5 notés, 1 échec(s)", sortie)
        self.assertEqual(len(self.lignes_ombre()), 5)

    def test_module_de_prompts_defaillant_ne_bloque_pas_la_notation(self):
        self.reglages(ombre=True)
        self.corpus()
        with mock.patch.object(tri, "load_shadow_prompts", side_effect=ImportError("absent")), \
                mock.patch.object(httpx, "post", FauxModele()):
            sortie = self.noter()
        self.assertEqual(len(self.store.all_scores()), 6)
        self.assertIn("désactivée pour ce passage", sortie)

    def test_sans_modele_pas_d_ombre(self):
        self.reglages(ombre=True)
        self.article("a1.md", "§5")
        faux = FauxModele()
        with mock.patch.object(httpx, "post", faux):
            self.noter(no_model=True)
        self.assertEqual(faux.appels, {"fr": 0, "en": 0})
        self.assertEqual(self.lignes_ombre(), [])

    def test_renotation_remplace_la_ligne(self):
        self.reglages(ombre=True)
        self.article("a1.md", "§5")
        with mock.patch.object(httpx, "post", FauxModele()):
            self.noter()
            self.noter(rescore=True)
        self.assertEqual(len(self.lignes_ombre()), 1)

    def test_les_decisions_ignorent_la_table_de_l_ombre(self):
        self.reglages(ombre=True)
        self.corpus()
        with mock.patch.object(httpx, "post", FauxModele()):
            self.noter()
        self.assertEqual(len(self.lignes_ombre()), 6)
        avec = self.photo_apres_apply()
        self.remettre_a_zero_sauf_les_notes()
        self.assertEqual(self.lignes_ombre(), [])
        sans = self.photo_apres_apply()
        for cle in ("to_read", "ecartes", "restants", "locations"):
            self.assertEqual(sans[cle], avec[cle], cle)
        self.assertEqual([(r["file"], r["reasons"]) for r in sans["ranked"]], [(r["file"], r["reasons"]) for r in avec["ranked"]])

    def test_le_francais_garde_sa_charge_utile(self):
        """judge sans jeu de prompts : exactement les prompts français d'avant."""
        envoyees = []

        def capture(url, json=None, timeout=None):
            envoyees.append(json)
            return FauxModele()(url, json=json, timeout=timeout)
        with mock.patch.object(httpx, "post", capture):
            tri.judge("faux", ["t1", "t2"], {"title": "T", "source": "S", "body": "§3 corps"})
        attendu = tri.SYSTEM_PROMPT.format(themes="t1; t2")
        self.assertEqual(envoyees[0]["messages"][0]["content"], attendu)
        criteres = "\n".join(f"- {k} : {q}" for k, (q, _) in tri.CRITERIA.items())
        self.assertEqual(envoyees[0]["messages"][1]["content"],
                         tri.USER_PROMPT.format(title="T", source="S", text="§3 corps", criteria=criteres))


class Rapport(Ombre):
    def ombre(self, nom, substance, *, in_themes=1, promo=0, compilation=0):
        url = self.note_de(nom)["url"]
        criteres = {k: i < substance for i, k in enumerate(CRITERES)}
        self.store.put_shadow(url=url, language="en", model="faux", prompts_hash="abc", criteria=criteres, substance=substance,
                              is_compilation=bool(compilation), in_themes=bool(in_themes), is_promo=bool(promo),
                              scored_at=dt.datetime.now().astimezone())
        self.store.commit()

    def monter(self, avis_en_base=True):
        self.reglages(ombre=True)
        for nom, fr, en, flags in (("a1.md", 5, 5, {}), ("a2.md", 4, 2, {}), ("a3.md", 1, 1, {}), ("a4.md", 3, 3, {"in_themes": 0})):
            self.ajouter(nom, fr)
            self.ombre(nom, en, **flags)
        self.ajouter("a5.md", 4)    # noté en français seulement : hors comparaison
        # la feuille existe toujours, mais seuls les avis stockés en base comptent
        tri.CALIBRATION_FILE.write_text("fichier;titre;avis\na1.md;x;g\na2.md;x;g\na3.md;x;e\na4.md;x;g\na5.md;x;g\n",
                                        encoding="utf-8")
        if avis_en_base:
            self.store.refresh_calibration([dict(file=f, verdict="keep") for f in ("a1.md", "a2.md", "a3.md", "a4.md", "a5.md")],
                                           dt.datetime.now().astimezone())
            self.store.apply_opinions({"a1.md": True, "a2.md": True, "a3.md": False, "a4.md": True, "a5.md": True})
        self.store.restore("a2.md", "2026-10-02")
        self.store.exclude("a3.md", "2026-10-02")
        self.store.commit()

    def fichiers(self):
        return {str(p.relative_to(self.tmp)): (p.stat().st_mtime_ns, p.stat().st_size)
                for p in self.tmp.rglob("*") if p.is_file()}

    def test_comparaison_des_deux_langues(self):
        self.monter()
        sortie = self.lancer(tri.cmd_shadow_report, limit=20)
        self.assertIn("Articles notés dans les deux langues : 4", sortie)
        self.assertIn("Accord sur la décision garder/écarter : 2/4 (50 %)", sortie)
        self.assertIn("Substance moyenne : fr 3.25, en 2.75 · écart moyen -0.50 · écart absolu moyen 0.50", sortie)
        self.assertRegex(sortie, r"these\s+désaccord 0/4")
        self.assertRegex(sortie, r"original\s+désaccord 1/4")        # a2 : 4 en français, 2 en anglais
        self.assertRegex(sortie, r"dans les thèmes\s+désaccord 1/4 ")
        self.assertIn("avis de calibration : fr 4/4 (100 %) · en 2/4 (50 %)", sortie)
        self.assertIn("repêchages (à garder) : fr 1/1 (100 %) · en 0/1 (0 %)", sortie)
        self.assertIn("rejets à la main (à écarter) : fr 1/1 (100 %) · en 1/1 (100 %)", sortie)
        self.assertIn("Désaccords sur la décision : 2", sortie)
        self.assertIn("Titre a2.md · source-a.test", sortie)
        self.assertIn("fr : substance 4/5 → garder (manque non_promo)", sortie)
        self.assertIn("en : substance 2/5 → écarter (manque original/sources/non_promo)", sortie)
        self.assertIn("en : substance 3/5 → écarter (hors thèmes, manque sources/non_promo)", sortie)
        self.assertNotIn("Titre a5.md", sortie)

    def test_limite_de_la_liste(self):
        self.monter()
        sortie = self.lancer(tri.cmd_shadow_report, limit=1)
        self.assertIn("Désaccords sur la décision : 2 (les 1 premiers)", sortie)
        self.assertIn("Titre a2.md", sortie)
        self.assertNotIn("Titre a4.md", sortie)

    def test_le_rapport_n_ecrit_aucun_fichier(self):
        self.monter()
        avant = self.fichiers()
        base_avant = (self.store.shadow_rows(), self.store.calibration_entries(), len(self.store.all_scores()))
        self.lancer(tri.cmd_shadow_report, limit=20)
        self.assertEqual(self.fichiers(), avant)
        self.assertEqual((self.store.shadow_rows(), self.store.calibration_entries(), len(self.store.all_scores())), base_avant)
        self.assertEqual(self.data.roles, ["ro"])           # une seule ouverture, en lecture seule

    def test_sortie_vide_sans_reglages_ni_note(self):
        self.assertFalse(tri.CONFIG_FILE.exists())
        avant = self.fichiers()
        sortie = self.lancer(tri.cmd_shadow_report, limit=20)
        self.assertIn("Aucun article noté dans les deux langues", sortie)
        self.assertIn("inactive", sortie)
        self.assertFalse(tri.CONFIG_FILE.exists())
        self.assertEqual(self.fichiers(), avant)

    def test_sortie_vide_ombre_active_sans_passage(self):
        self.reglages(ombre=True)
        self.ajouter("a1.md", 4)
        self.assertIn("est active", self.lancer(tri.cmd_shadow_report, limit=20))

    def test_sans_avis_en_base_meme_avec_une_feuille(self):
        self.monter(avis_en_base=False)
        self.assertTrue(tri.CALIBRATION_FILE.exists())
        sortie = self.lancer(tri.cmd_shadow_report, limit=20)
        self.assertIn("avis de calibration : aucun article en commun", sortie)
        tri.CALIBRATION_FILE.unlink()
        self.assertIn("avis de calibration : aucun article en commun", self.lancer(tri.cmd_shadow_report, limit=20))

    def test_ranked_utilise_la_meme_regle(self):
        """La fonction partagée donne les raisons de ranked, hors repêchage et rejet à la main."""
        self.ajouter("a1.md", 2, in_themes=0, justifs={"dans_themes": "technique"})
        with contextlib.redirect_stdout(io.StringIO()):     # config() annonce « Réglages créés » au premier lancement : message capturé
            ligne = self.ligne("a1.md")
        brut = {"substance": 2, "criteria": {k: i < 2 for i, k in enumerate(CRITERES)}, "in_themes": 0, "promo": 0,
                "compilation": 0, "why": {"dans_themes": "technique"}}
        self.assertEqual(tri.discard_reasons(brut, 3), ligne["reasons"])


class Contrat(unittest.TestCase):
    """Le module de prompts anglais écrit pour l'ombre respecte le contrat que watch_triage.py exige."""

    def test_module_conforme(self):
        module = importlib.import_module("watch_prompts_en")
        prompts = tri.check_prompts(module)
        self.assertEqual(list(prompts.CRITERIA), CRITERES)
        self.assertTrue(prompts.THEMES)
        texte = prompts.USER_PROMPT.format(title="T", source="S", text="X", criteria="C")
        self.assertIn("T", texte)
        self.assertIn("{themes}", prompts.SYSTEM_PROMPT)
        self.assertRegex(tri.prompts_hash(prompts), r"^[0-9a-f]{12}$")
        for cle in ("resume", "pourquoi", "compilation", "dans_themes", "promotionnel"):
            self.assertIn(cle, prompts.USER_PROMPT)

    # Empreintes figées (lot 5b) : le français ne change pas, l'anglais a changé depuis la mesure du 10 octobre
    EMPREINTE_FRANCAISE = "396754ca1a38"
    EMPREINTE_ANGLAISE_AVANT_5B = "49ec8e858e3f"

    def test_prompts_francais_figes(self):
        """Prompts, critères et thèmes par défaut du français : identiques octet pour octet (empreinte figée)."""
        import yaml
        themes = yaml.safe_load(tri.DEFAULT_CONFIG)["themes"]
        francais = types.SimpleNamespace(**vars(tri.french_prompts()), THEMES=themes)
        self.assertEqual(tri.prompts_hash(francais), self.EMPREINTE_FRANCAISE)

    def test_prompts_anglais_officiels_differents_de_la_mesure_du_10_octobre(self):
        prompts = tri.check_prompts(importlib.import_module("watch_prompts_en"))
        self.assertNotEqual(tri.prompts_hash(prompts), self.EMPREINTE_ANGLAISE_AVANT_5B)

    def test_item_promotionnel_anglais_nomme_les_offres_deguisees(self):
        texte = importlib.import_module("watch_prompts_en").USER_PROMPT
        item = texte[texte.index("5. promotionnel"):texte.index("6. For each criterion")].lower()
        for offre in ("book excerpt", "book announcement", "webinar", "paid course"):
            self.assertIn(offre, item)
        # itération 2b : une mention en passant de son livre ou de ses services ne rend pas promotionnel
        self.assertIn("main purpose of the text is to sell or to get the reader to sign up", item)
        self.assertIn("mentions in passing", item)
        self.assertNotIn("even when an argued passage remains", item)

    def test_item_compilation_anglais_garde_l_argument_de_l_auteur(self):
        texte = importlib.import_module("watch_prompts_en").USER_PROMPT
        item = texte[texte.index("3. compilation"):texte.index("4. dans_themes")].lower()
        self.assertIn("own argument", item)

    def test_le_systeme_anglais_ne_commence_pas_comme_le_francais(self):
        module = importlib.import_module("watch_prompts_en")
        self.assertNotEqual(module.SYSTEM_PROMPT[:10], tri.SYSTEM_PROMPT[:10])

    def test_contrat_refuse_un_module_incomplet(self):
        bon = faux_module_anglais()
        for retirer in ("SYSTEM_PROMPT", "USER_PROMPT", "CRITERIA", "THEMES"):
            module = types.SimpleNamespace(**{k: v for k, v in vars(bon).items() if k != retirer})
            with self.assertRaises(ValueError):
                tri.check_prompts(module)
        sans_marqueur = types.SimpleNamespace(**{**vars(bon), "USER_PROMPT": "Title: {title} {source} {text}"})
        with self.assertRaises(ValueError):
            tri.check_prompts(sans_marqueur)
        mauvaises_cles = types.SimpleNamespace(**{**vars(bon), "CRITERIA": {"these": ("q", "r")}})
        with self.assertRaises(ValueError):
            tri.check_prompts(mauvaises_cles)


if __name__ == "__main__":
    unittest.main()
