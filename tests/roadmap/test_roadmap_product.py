"""
Tests du label product: dans le lecteur de la file (tools/roadmap.py) : contrôle de `check`, filtre `--product` de next, status,
board et batch. Même faux gh que test_roadmap_github.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q -f
"""
import unittest

import roadmap_model as rm
from test_roadmap_github import Base, feature, sous_issue

MOTHRA = rm.label_product("mothra")


def mothra(n, **kw):
    """Feature étiquetée product:mothra."""
    theme = kw.get("theme", "outillage")
    return feature(n, labels=[rm.LABEL_FEATURE, rm.label_theme(theme), MOTHRA], **kw)


class TestCheck(Base):
    def test_zero_ou_un_label_produit_accepte(self):
        self.depot(feature(1), mothra(2))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 0, sortie)

    def test_produit_inconnu_refuse(self):
        self.depot(feature(1, labels=[rm.LABEL_FEATURE, "theme:outillage", "product:autre"]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : labels : produit inconnu autre", sortie)

    def test_deux_labels_produit_refuses(self):
        self.depot(feature(1, labels=[rm.LABEL_FEATURE, "theme:outillage", MOTHRA, "product:autre"]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("R-1 : labels : au plus un label product:", sortie)

    def test_tache_avec_produit_connu_ou_inconnu(self):
        self.depot(mothra(1), sous_issue(1, 1, 101, labels=[rm.LABEL_TASK, "model:sonnet", MOTHRA]))
        self.assertEqual(self.lance("check")[0], 0)
        self.depot(mothra(1), sous_issue(1, 1, 101, labels=[rm.LABEL_TASK, "model:sonnet", "product:autre"]))
        code, sortie, _ = self.lance("check")
        self.assertEqual(code, 1)
        self.assertIn("produit inconnu autre", sortie)


class TestNextFiltre(Base):
    def next(self, *noeuds, produit=None):
        self.depot(*noeuds)
        extra = ("--product", produit) if produit else ()
        return self.lance("next", "--budget", "8h", "--today", "2026-10-12", *extra)

    def test_sans_option_toute_la_file(self):
        _, sortie, _ = self.next(feature(1), mothra(2))
        self.assertIn("R-1 |", sortie)
        self.assertIn("R-2 |", sortie)

    def test_mothra(self):
        code, sortie, _ = self.next(feature(1), mothra(2), produit="mothra")
        self.assertEqual(code, 0, sortie)
        self.assertIn("R-2 |", sortie)
        self.assertNotIn("R-1 |", sortie)

    def test_pmzilla(self):
        code, sortie, _ = self.next(feature(1), mothra(2), produit="pmzilla")
        self.assertEqual(code, 0, sortie)
        self.assertIn("R-1 |", sortie)
        self.assertNotIn("R-2 |", sortie)

    def test_blocage_croise_conserve(self):
        # R-2 (Mothra) est bloquée par R-1 (PMZilla) ouverte : reste bloquée même avec le filtre mothra
        _, sortie, _ = self.next(feature(1, status="Todo"), mothra(2, status="Todo", blocked_by=[101]), mothra(3), produit="mothra")
        self.assertIn("proposés :\n  R-3 |", sortie)
        self.assertNotIn("R-2 |", sortie)
        # et inversement, R-1 (PMZilla) bloquée par R-2 (Mothra)
        _, sortie, _ = self.next(mothra(2, status="Todo"), feature(1, status="Todo", blocked_by=[102]), feature(3), produit="pmzilla")
        self.assertIn("proposés :\n  R-3 |", sortie)
        self.assertNotIn("R-1 |", sortie)

    def test_bloqueur_ferme_d_un_autre_produit_ne_bloque_pas(self):
        _, sortie, _ = self.next(feature(1, status="Done", state="CLOSED", milestone="Tarasque", milestone_state="CLOSED"),
                                 mothra(2, blocked_by=[101]), produit="mothra")
        self.assertIn("R-2 |", sortie)

    def test_produit_inconnu_refuse(self):
        self.depot(feature(1))
        code, _, _ = self.lance("next", "--budget", "2h", "--product", "autre")
        self.assertEqual(code, 2)


class TestStatusFiltre(Base):
    def status(self, *noeuds, produit=None):
        self.depot(*noeuds)
        return self.lance("status", *(("--product", produit) if produit else ()))

    def test_comptes_par_produit(self):
        noeuds = (feature(1), mothra(2, status="In progress"), mothra(3, status="Todo"))
        _, tout, _ = self.status(*noeuds)
        self.assertIn("ready 1", tout)
        self.assertIn("in-progress 1", tout)
        _, m, _ = self.status(*noeuds, produit="mothra")
        self.assertIn("ready 0", m)
        self.assertIn("in-progress 1", m)
        self.assertIn("R-2 |", m)
        self.assertNotIn("R-1 |", m)
        _, p, _ = self.status(*noeuds, produit="pmzilla")
        self.assertIn("ready 1", p)
        self.assertIn("in-progress 0", p)
        self.assertIn("R-1 |", p)
        self.assertNotIn("R-2 |", p)

    def test_blocage_croise_conserve(self):
        noeuds = (feature(1, status="Todo"), mothra(2, status="Todo", blocked_by=[101]))
        code, m, _ = self.status(*noeuds, produit="mothra")
        self.assertEqual(code, 0, m)
        self.assertIn("R-2 | Travail | attend R-1", m)
        self.assertNotIn("R-1 |", m)

    def test_board_filtre(self):
        self.depot(feature(1), mothra(2))
        code, sortie, _ = self.lance("board", "--product", "mothra")
        self.assertEqual(code, 0, sortie)
        page = (self.dir / "data" / "feuille-de-route.html").read_text(encoding="utf-8")
        self.assertIn("R-2", page)
        self.assertNotIn("R-1<", page)


class TestBatchFiltre(Base):
    def batch(self, *noeuds, produit=None):
        self.depot(*noeuds)
        return self.lance("batch", "--milestone", "Hydra", "--today", "2026-10-13", *(("--product", produit) if produit else ()))

    def test_filtre(self):
        _, tout, _ = self.batch(feature(1), mothra(2))
        self.assertIn("R-1 |", tout)
        self.assertIn("R-2 |", tout)
        _, m, _ = self.batch(feature(1), mothra(2), produit="mothra")
        self.assertIn("R-2 |", m)
        self.assertNotIn("R-1 |", m)
        _, p, _ = self.batch(feature(1), mothra(2), produit="pmzilla")
        self.assertIn("R-1 |", p)
        self.assertNotIn("R-2 |", p)


if __name__ == "__main__":
    unittest.main()
