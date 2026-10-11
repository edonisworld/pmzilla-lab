"""Jeu inventé commun aux tests de flow_store : mêmes tickets écrits en CSV (voie des fichiers) et en lignes SQL (voie de la base).

Aucune donnée réelle : tickets PROJ-n, équipes « Alpha » et « Beta ». Les dates sont des heures locales naïves du fuseau
d'export (Europe/Paris), relatives à aujourd'hui, entre 9 h et 17 h (jamais dans l'heure d'un changement d'heure).
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path
from zoneinfo import ZoneInfo

FUSEAU = ZoneInfo("Europe/Paris")
MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def date_csv(moment: dt.datetime | None, avec_heure: bool = True) -> str:
    """Date au format de l'export manuel, mois en anglais sans dépendre de la langue du poste."""
    if moment is None:
        return ""
    jour = f"{moment.day:02d}/{MOIS[moment.month - 1]}/{moment.year}"
    return f"{jour} {moment:%H:%M}" if avec_heure else jour


def moment(jours: int, heure: int = 10, minute: int = 0, aujourdhui: dt.date | None = None) -> dt.datetime:
    jour = (aujourdhui or dt.date.today()) - dt.timedelta(days=jours)
    return dt.datetime(jour.year, jour.month, jour.day, heure, minute)


def issue(cle, type_="Story", etat="Closed", categorie="Done", cree=None, resolu=None, motif="", debut=None, equipes=(),
          parent="", points=None):
    return {"cle": cle, "type": type_, "etat": etat, "categorie": categorie, "cree": cree, "resolu": resolu, "motif": motif,
            "debut": debut, "equipes": list(equipes), "parent": parent, "points": points}


def tickets(aujourdhui: dt.date | None = None) -> list[dict]:
    """48 tickets : équipes seules, deux équipes, sans équipe, Epic et enfants, quelques fermetures dans la même minute."""
    rng = random.Random(11)
    liste = []
    choix_equipes = [["Alpha"], ["Alpha"], ["Beta"], ["Beta"], ["Alpha", "Beta"], ["Beta", "Alpha"], []]
    for i in range(1, 49):
        cree = moment(rng.randint(12, 200), rng.randint(9, 17), rng.randint(0, 59), aujourdhui)
        r = rng.random()
        type_ = "Epic" if i <= 3 else rng.choice(["Story", "Bug"])
        if r < 0.5:
            etat, cat, motif = "Closed", "Done", "Done"
            resolu = min(cree + dt.timedelta(days=rng.randint(3, 60)), moment(8, 11, 0, aujourdhui))
            resolu = resolu.replace(hour=rng.randint(9, 17), minute=rng.randint(0, 59))
            debut = cree + dt.timedelta(days=1)
        elif r < 0.8:
            etat, cat, motif, resolu = "In Progress", "In Progress", "", None
            debut = cree + dt.timedelta(days=2)
        else:
            etat, cat, motif, resolu, debut = "Open", "To Do", "", None, None
        liste.append(issue(f"PROJ-{i}", type_, etat, cat, cree, resolu, motif, debut, rng.choice(choix_equipes),
                           parent=f"PROJ-{1 + i % 3}" if i > 3 else "", points=rng.choice([None, 1, 2, 3, 5])))
    # cinq fermetures dans la même minute (règle des fermetures groupées)
    groupe = moment(30, 15, 42, aujourdhui)
    for t in liste[10:15]:
        t.update(etat="Closed", categorie="Done", motif="Done", resolu=groupe, equipes=["Alpha"])
        t["cree"] = min(t["cree"], groupe - dt.timedelta(days=5))
        t["debut"] = t["cree"] + dt.timedelta(days=1)
    return liste


def liens() -> list[tuple[str, str, str, str]]:
    """Liens en base : (source, cible, type, direction). Bloque : sortant d'un côté, entrant de l'autre, ou d'un seul côté ;
    un lien « Depends » sortant ; deux liens sans type (type vide, direction absente)."""
    return [
        ("PROJ-10", "PROJ-20", "Blocks", "outward"), ("PROJ-20", "PROJ-10", "Blocks", "inward"),
        ("PROJ-21", "PROJ-30", "Blocks", "outward"),
        ("PROJ-31", "PROJ-22", "Blocks", "inward"),
        ("PROJ-23", "PROJ-40", "Depends", "outward"),
        ("PROJ-24", "PROJ-41", "", None), ("PROJ-25", "PROJ-33", "", None),
        ("PROJ-26", "ABC-9", "Blocks", "outward"),
    ]


def ecrire_csv(chemin: Path, liste: list[dict], liens_base: list | None = None, avec_heure: bool = True,
               noms_liens: bool = True) -> None:
    """Export manuel équivalent : deux colonnes Team (la première est l'attribution), une colonne par couple (type, sens),
    une colonne « Linked Issues » pour les liens sans type. Colonnes de liens dans l'ordre trié des couples."""
    liens_base = liens() if liens_base is None else liens_base
    couples = sorted({(typ, "entrant" if d == "inward" else "sortant") for _, _, typ, d in liens_base if typ and d})
    entete = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
              "Status Category Changed", "Parent key", "Team", "Team"]
    if noms_liens:
        entete += [f"{'Inward' if sens == 'entrant' else 'Outward'} issue link ({typ})" for typ, sens in couples]
        if any(not typ for _, _, typ, _ in liens_base):
            entete += ["Linked Issues"]
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(entete)
        for t in liste:
            ligne = [t["cle"], t["type"], t["etat"], t["categorie"], date_csv(t["cree"], avec_heure),
                     date_csv(t["resolu"], avec_heure), t["motif"], date_csv(t["debut"], avec_heure), t["parent"],
                     t["equipes"][0] if t["equipes"] else "", t["equipes"][1] if len(t["equipes"]) > 1 else ""]
            if noms_liens:
                for typ, sens in couples:
                    d = "inward" if sens == "entrant" else "outward"
                    ligne.append(", ".join(c for s, c, ty, di in liens_base if s == t["cle"] and ty == typ and di == d))
                if any(not typ for _, _, typ, _ in liens_base):
                    ligne.append(", ".join(c for s, c, ty, _ in liens_base if s == t["cle"] and not ty))
            w.writerow(ligne)


def a_minuit(liste: list[dict]) -> list[dict]:
    """Même jeu, dates à minuit."""
    def minuit(m):
        return None if m is None else m.replace(hour=0, minute=0)
    return [{**t, "cree": minuit(t["cree"]), "resolu": minuit(t["resolu"]), "debut": minuit(t["debut"])} for t in liste]


def transitions() -> list[tuple[str, dt.datetime, str | None, str]]:
    """(clé, instant, départ, arrivée) : hiver (+01:00), été (+02:00), autour du changement d'heure d'octobre 2025 et de mars
    2026, un ticket sans transition (PROJ-3)."""
    def loc(a, m, j, h, mi):
        return dt.datetime(a, m, j, h, mi, tzinfo=FUSEAU)
    return [
        ("PROJ-1", loc(2026, 1, 15, 9, 30), None, "Open"),
        ("PROJ-1", loc(2026, 1, 20, 14, 5), "Open", "In Progress"),
        ("PROJ-1", loc(2026, 7, 2, 8, 45), "In Progress", "Closed"),
        ("PROJ-2", loc(2025, 10, 26, 3, 30), None, "Open"),             # après le retour à l'heure d'hiver (+01:00)
        ("PROJ-2", loc(2025, 10, 25, 23, 59), None, "Backlog"),          # avant : été (+02:00), classé avant par l'instant
        ("PROJ-2", loc(2026, 3, 29, 3, 30), "Open", "In Progress"),      # après le passage à l'heure d'été
        ("PROJ-4", loc(2026, 3, 28, 12, 0), "Open", "Closed"),
    ]
