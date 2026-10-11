"""
Calibration du seuil de similarité (db-lot2, groupe 14.1) : tools/cases_calibration.py, avec une fausse fonction d'embedding.

    bash tests/run_all.sh cases_store

Aucun appel à Ollama, aucune base. Le jeu d'essai livré (tests/postures/cas.yaml et ses jeux) sert pour la construction des paires.
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import cases_calibration as cc  # noqa: E402


def fake_embed(text):
    """Vecteur déterministe sur quelques mots : sans réseau."""
    mots = ["revue", "review", "wip", "limite", "limit", "refinement", "refinements", "correctif", "fix"]
    low = text.lower()
    return [float(low.count(m)) + 0.01 for m in mots]


class ProposeThreshold(unittest.TestCase):
    def test_separation_donne_le_milieu_arrondi_vers_le_bas(self):
        self.assertEqual(cc.propose_threshold([0.7, 0.9], [0.3, 0.5]), 0.6)
        self.assertEqual(cc.propose_threshold([0.71], [0.30]), 0.5)   # 0.505 -> 0.50
        self.assertEqual(cc.propose_threshold([0.68], [0.30]), 0.49)  # 0.49 exact

    def test_accepte_les_flottants_numpy(self):
        # le vrai embed rend des numpy.float64 (repr « np.float64(0.5) » avec numpy 2)
        import numpy as np
        self.assertEqual(cc.propose_threshold([np.float64(0.632), np.float64(0.7)], [np.float64(0.554)]), 0.59)

    def test_valeurs_egales_ou_inversees(self):
        self.assertIsNone(cc.propose_threshold([0.5], [0.5]))
        self.assertIsNone(cc.propose_threshold([0.4], [0.6]))

    def test_le_milieu_arrondi_tombe_sur_low(self):
        self.assertIsNone(cc.propose_threshold([0.51], [0.50]))
        self.assertIsNone(cc.propose_threshold([0.505], [0.50]))


class Paires(unittest.TestCase):
    def test_trois_liees_et_neuf_non_liees_par_langue(self):
        for lang in ("fr", "en"):
            pairs = cc.build_pairs(lang, fake_embed)
            self.assertEqual(sum(p["related"] for p in pairs), 3, lang)
            self.assertEqual(sum(not p["related"] for p in pairs), 9, lang)
            self.assertEqual({p["case_id"] for p in pairs}, {"cas-proche-reussi", "cas-proche-echoue", "experimentation-en-cours"})

    def test_la_paire_liee_est_la_premiere_entree_du_propre_jeu(self):
        pairs = cc.build_pairs("fr", fake_embed)
        for p in pairs:
            self.assertEqual(p["related"], p["entry_case_id"] == p["case_id"] and p["index"] == 1, p)
        kinds = {p["case_id"]: p["kind"] for p in pairs if p["related"]}
        self.assertEqual(kinds, {"cas-proche-reussi": "case", "cas-proche-echoue": "case", "experimentation-en-cours": "experiment"})

    def test_le_second_cas_du_meme_jeu_est_non_lie(self):
        pairs = cc.build_pairs("en", fake_embed)
        self.assertTrue(any(p["case_id"] == "cas-proche-reussi" and p["entry_case_id"] == "cas-proche-reussi" and p["index"] == 2
                            and not p["related"] for p in pairs))


class EmbeddingIndisponible(unittest.TestCase):
    """Embedding indisponible : une ligne d'erreur sur stderr, code 1, aucune ligne de paire."""

    def lance(self, embed):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cc.main([], embed=embed, out=out)
        return code, out.getvalue(), err.getvalue()

    def verifie(self, embed):
        code, out, err = self.lance(embed)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        lignes = err.strip().splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertTrue(lignes[0].startswith("error: "))
        self.assertIn("embedding service", lignes[0])

    def test_ollama_ne_repond_pas(self):
        import httpx

        def embed(text):
            raise httpx.ConnectError("injoignable")
        self.verifie(embed)

    def test_modele_inconnu(self):
        # l'embedding par défaut sort par SystemExit quand le modèle est inconnu
        def embed(text):
            raise SystemExit(1)
        self.verifie(embed)


class Sortie(unittest.TestCase):
    def run_main(self, args):
        out = io.StringIO()
        code = cc.main(args, embed=fake_embed, out=out)
        return code, out.getvalue()

    def test_sortie_sans_texte(self):
        code, text = self.run_main([])
        self.assertEqual(code, 0)
        self.assertIn("low", text)
        self.assertIn("high", text)
        self.assertTrue("proposed value" in text or "no separation" in text)
        self.assertIn("cas-proche-reussi", text)
        for forbidden in ("parties prenantes", "stakeholders", "WIP", "refinement", "sprint"):
            self.assertNotIn(forbidden.lower(), text.lower().replace("cas-proche", "").replace("experimentation-en-cours", ""))
        lines = [l for l in text.splitlines() if " related" in l or " unrelated" in l]
        self.assertEqual(len(lines), 24)
        for l in lines:
            self.assertRegex(l, r"\d\.\d{3}$")

    def test_langue_unique(self):
        code, text = self.run_main(["--language", "en"])
        lines = [l for l in text.splitlines() if " related" in l or " unrelated" in l]
        self.assertEqual(len(lines), 12)
        self.assertTrue(all(" en " in l for l in lines))

    def test_aucune_separation_avec_embedding_constant(self):
        out = io.StringIO()
        code = cc.main([], embed=lambda t: [1.0, 0.0], out=out)
        self.assertIn("no separation", out.getvalue())
        self.assertNotIn("proposed value", out.getvalue())


if __name__ == "__main__":
    unittest.main()
