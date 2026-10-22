"""Idée #179 (change jira-data-architecture, D10) : attribution à la première équipe alignée sur la première valeur, et section
« Tickets partagés par équipe » du rapport de flux. Tâche 4.3 (rouges d'abord), vertes avec les tâches 6.1 et 6.2.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Lancements dans le processus (aide_espace.py), exports inventés (tickets PROJ-n, équipes Alpha, Beta, Gamma, Zeta), sans base ni réseau.
La voie base est exercée par un faux flow_store qui rend les tickets tels que la base les rend (équipe = première équipe).
"""
import csv
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import chargeur_csv as chargeur  # noqa: E402
from aide_espace import AvecEspace, faux_store, fj  # noqa: E402

FMT = "%d/%b/%Y %H:%M"
AUJOURDHUI = dt.date(2026, 10, 4)
ENTETE = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
          "Status Category Changed", "Team", "Team"]
SENTINELLE = "SENTINELLE-CLE"
REFERENTIEL = """source_date: 2026-10-01
sites:
  - Site Nord
departments:
  - name: Departement 1
    site: Site Nord
    headcount: 20
    mission_teams:
      - name: MT Alpha
        teams: [Alpha, Beta, Gamma, Zeta]
teams:
  - name: Alpha
    headcount: 5
  - name: Beta
    headcount: 5
  - name: Gamma
    headcount: 5
  - name: Zeta
    headcount: 5
"""


def ligne(numero, premiere, seconde="", termine=False):
    cree = AUJOURDHUI - dt.timedelta(days=60)
    resolu = (AUJOURDHUI - dt.timedelta(days=20 + numero % 5)).strftime(FMT) if termine else ""
    return [f"PROJ-{numero}", "Story", "Done" if termine else "In Progress", "Done" if termine else "In Progress",
            cree.strftime(FMT), resolu, "Done" if termine else "", (cree + dt.timedelta(days=2)).strftime(FMT), premiere, seconde]


def jeu(*groupes):
    """groupes : (nombre, première colonne, seconde colonne). Rend les lignes de l'export, numérotées de 1."""
    lignes = []
    for nombre, premiere, seconde in groupes:
        for _ in range(nombre):
            lignes.append(ligne(len(lignes) + 1, premiere, seconde, termine=len(lignes) % 3 == 0))
    return lignes


def ecrire(chemin, lignes):
    with chemin.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows([ENTETE, *lignes])


class Base(AvecEspace):
    def calculer(self, lignes, *plus, nom="s", langue=None):
        chemin = self.flux / "export.csv"
        ecrire(chemin, lignes)
        argv = ["compute", str(chemin), "--name", nom, "--today", AUJOURDHUI.isoformat(), "--no-comparison", *plus]
        if langue:
            argv += ["--language", langue]
        code, sortie, erreur = self.lancer(*argv)
        self.assertIsNone(code, sortie + erreur)
        suffixe = "" if "--by" not in plus or plus[plus.index("--by") + 1] == "team" else "-" + plus[plus.index("--by") + 1]
        stem = f"flux-{nom}{suffixe}-2026-10-04"            # le nom du rapport porte l'agrégation par groupe
        return json.loads(self.lire_rapport(stem + ".json")), self.lire_rapport(stem + ".md"), sortie

    def partages(self, rapport):
        return rapport["tickets_partages_par_equipe"]["par_equipe"]


class PremiereValeur(Base):
    """Attribution : première valeur de la première colonne d'équipe, jamais la cellule entière."""

    def test_cellule_avec_separateur_attribuee_a_la_premiere_valeur(self):
        lignes = jeu((6, "Alpha;Beta", ""), (6, "Gamma", ""))
        rapport, md, _ = self.calculer(lignes)
        self.assertEqual(sorted(rapport["par_equipe"]), ["Alpha", "Gamma"])
        self.assertNotIn("Alpha;Beta", json.dumps(rapport, ensure_ascii=False))
        self.assertEqual(rapport["tickets_plusieurs_equipes"]["total"], 6)

    def test_les_valeurs_suivantes_et_les_autres_colonnes_n_attribuent_rien(self):
        lignes = jeu((6, "Alpha;Beta", "Zeta"), (6, "Gamma", "Beta"))
        rapport, _, _ = self.calculer(lignes)
        self.assertEqual(sorted(rapport["par_equipe"]), ["Alpha", "Gamma"])

    def test_meme_attribution_que_la_voie_base(self):
        """La voie base attribue la première équipe du ticket (valeur, pas cellule) : mêmes tickets, même rapport."""
        lignes = jeu((6, "Alpha;Beta", ""), (6, "Gamma", "Alpha"), (6, "Beta", ""))
        chemin = self.flux / "export.csv"
        ecrire(chemin, lignes)
        reglages = {**fj.DEFAULT_CONFIG}
        tickets_csv, trouves, illisibles, doublons = chargeur.lire_tickets_flux(reglages, [str(chemin)])
        self.assertEqual([t["equipe"] for t in tickets_csv[:2]], ["Alpha", "Alpha"])
        tickets_base = [{**t, "equipe": t["equipes"][0] if t["equipes"] else "(sans équipe)"} for t in tickets_csv]
        self.assertEqual([t["equipe"] for t in tickets_base], [t["equipe"] for t in tickets_csv])
        base = faux_store(lire_tickets_flux=lambda settings: (tickets_base, trouves, 0, 0))
        code, _, _ = self.lancer("compute", "--name", "s", "--today", AUJOURDHUI.isoformat(),
                                 "--no-comparison", store=base)
        self.assertIsNone(code)
        depuis_la_base = (self.lire_rapport("flux-s-2026-10-04.json"), self.lire_rapport("flux-s-2026-10-04.md"))
        code, _, _ = self.lancer("compute", str(chemin), "--name", "s", "--today", AUJOURDHUI.isoformat(), "--no-comparison")
        self.assertIsNone(code)
        self.assertEqual(depuis_la_base, (self.lire_rapport("flux-s-2026-10-04.json"), self.lire_rapport("flux-s-2026-10-04.md")))


class SectionPartages(Base):
    def test_absente_sans_ticket_a_plusieurs_equipes(self):
        rapport, md, _ = self.calculer(jeu((6, "Alpha", ""), (6, "Beta", "")))
        self.assertNotIn("tickets_partages_par_equipe", rapport)
        self.assertNotIn("Tickets partagés par équipe", md)
        self.assertNotIn("Attribution à la première équipe", md)

    def test_un_ticket_sans_second_nom_distinct_ne_compte_pas(self):
        """Même équipe dans les deux colonnes : un seul nom distinct, ce n'est pas un ticket partagé."""
        rapport, md, _ = self.calculer(jeu((6, "Alpha", "Alpha"), (6, "Beta", "")))
        self.assertNotIn("tickets_partages_par_equipe", rapport)

    def test_cellules_sous_cinq_masquees_dans_le_markdown_et_nulles_dans_le_json(self):
        """Alpha : 12 attribués partagés, 11 portés ailleurs ; Beta : 2 (masqué) et 12 ; Gamma : 5 (limite, rendu) et 0 (masqué) ;
        Zeta : 4 (limite, masqué) et 0 (masqué)."""
        lignes = jeu((12, "Alpha", "Beta"), (2, "Beta", "Alpha"), (5, "Gamma", "Alpha"), (4, "Zeta", "Alpha"),
                     (5, "Alpha", ""), (5, "Beta", ""))
        rapport, md, _ = self.calculer(lignes)
        self.assertEqual(self.partages(rapport),
                         {"Alpha": {"attribues_partages": 12, "portes_ailleurs": 11},
                          "Beta": {"attribues_partages": None, "portes_ailleurs": 12},
                          "Gamma": {"attribues_partages": 5, "portes_ailleurs": None},
                          "Zeta": {"attribues_partages": None, "portes_ailleurs": None}})
        self.assertIn("| Alpha | 12 | 11 |", md)
        self.assertIn("| Beta | masqué | 12 |", md)                  # idée #417 : le mot, jamais « <5 »
        self.assertIn("| Gamma | 5 | masqué |", md)
        self.assertIn("| Zeta | masqué | masqué |", md)
        self.assertIn("Une cellule de moins de 5 tickets s'écrit « masqué ».", md)     # le seuil reste dans le glossaire

    def test_lignes_dans_l_ordre_des_noms_jamais_des_effectifs(self):
        lignes = jeu((9, "Zeta", "Alpha"), (5, "Alpha", "Zeta"), (7, "Gamma", "Beta"), (6, "Beta", "Gamma"))
        rapport, md, _ = self.calculer(lignes)
        self.assertEqual(list(self.partages(rapport)), ["Alpha", "Beta", "Gamma", "Zeta"])
        debut = md.index("Tickets partagés par équipe")
        ordre = [md.index(f"| {nom} |", debut) for nom in ("Alpha", "Beta", "Gamma", "Zeta")]
        self.assertEqual(ordre, sorted(ordre))

    def test_sommes_des_colonnes(self):
        """Sans cellule masquée : la première colonne totalise les tickets partagés, la seconde les équipes portées en plus."""
        lignes = jeu((10, "Alpha", "Beta"), (8, "Beta", "Alpha"), (7, "Gamma", "Alpha;Beta"), (5, "Alpha", "Gamma"),
                     (5, "Alpha", ""))
        rapport, _, _ = self.calculer(lignes)
        partages = self.partages(rapport)
        total = rapport["tickets_plusieurs_equipes"]["total"]
        self.assertEqual(total, 30)
        self.assertEqual(sum(c["attribues_partages"] for c in partages.values()), total)
        self.assertEqual(sum(c["portes_ailleurs"] for c in partages.values()), 10 + 8 + 7 * 2 + 5)

    def test_les_deux_langues(self):
        lignes = jeu((12, "Alpha", "Beta"), (2, "Beta", "Alpha"))
        _, fr, _ = self.calculer(lignes, nom="f")
        _, en, _ = self.calculer(lignes, nom="e", langue="en")
        for texte in ("Tickets partagés par équipe", "Attribution à la première équipe : chaque ticket compte une fois, "
                      "pour sa première équipe.", "Attribués ici, partagés", "Portés ici, attribués ailleurs"):
            self.assertIn(texte, fr)
        for texte in ("Shared tickets by team", "First-team attribution: each ticket counts once, for its first team.",
                      "Attributed here, shared", "Carried here, attributed elsewhere"):
            self.assertIn(texte, en)
        self.assertNotIn("Tickets partagés par équipe", en)
        self.assertNotIn("Shared tickets by team", fr)

    def test_la_section_suit_les_arrivees_et_sorties_par_equipe(self):
        lignes = jeu((12, "Alpha", "Beta"), (6, "Beta", ""))
        _, md, _ = self.calculer(lignes)
        self.assertLess(md.index("| Équipe | Arrivées | Sorties | Différence |"), md.index("Tickets partagés par équipe"))
        self.assertLess(md.index("Tickets partagés par équipe"), md.index("## ", md.index("Tickets partagés par équipe") + 3))

    def test_entree_du_guide_de_lecture_seulement_quand_la_section_est_la(self):
        _, avec, _ = self.calculer(jeu((12, "Alpha", "Beta"), (6, "Beta", "")), nom="a")
        _, sans, _ = self.calculer(jeu((12, "Alpha", ""), (6, "Beta", "")), nom="b")
        guide = avec[avec.index("## Comment lire ce rapport"):]
        self.assertIn("**Tickets partagés**", guide)
        self.assertNotIn("**Tickets partagés**", sans)

    def test_aucune_cle_et_aucun_couple_d_equipes(self):
        lignes = jeu((12, "Alpha", "Beta"), (6, "Gamma", "Alpha"))
        for i, l in enumerate(lignes):
            l[0] = f"{SENTINELLE}-{i}"
        rapport, md, sortie = self.calculer(lignes)
        section = md[md.index("Tickets partagés par équipe"):]
        section = section[:section.index("\n## ")] if "\n## " in section else section
        for texte in (json.dumps(rapport["tickets_partages_par_equipe"], ensure_ascii=False), section, sortie):
            self.assertNotIn(SENTINELLE, texte)
        self.assertNotIn("Alpha et Beta", section)
        self.assertNotIn("Alpha / Beta", section)
        self.assertNotIn("Alpha → Beta", section)

    def test_absente_avec_un_regroupement(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        lignes = jeu((12, "Alpha", "Beta"), (6, "Gamma", "Alpha"), (6, "Beta", ""))
        for par in ("mission-team", "site"):
            rapport, md, _ = self.calculer(lignes, "--by", par, nom=f"g{par[:2]}")
            self.assertNotIn("tickets_partages_par_equipe", rapport, par)
            self.assertNotIn("Tickets partagés par équipe", md, par)
            self.assertIn("tickets_plusieurs_equipes", rapport, par)           # le comptage existant reste

    def test_present_avec_by_team(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        rapport, md, _ = self.calculer(jeu((12, "Alpha", "Beta"), (6, "Gamma", "")), "--by", "team")
        self.assertIn("tickets_partages_par_equipe", rapport)


if __name__ == "__main__":
    unittest.main()
