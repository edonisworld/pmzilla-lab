"""PMZilla Lab : messages de tools/flow_compare.py par langue (change database-only, D9). Des comptes, jamais une clé de ticket."""

CATALOGS = {
    "fr": {
        "reports_section": "Rapports : {a} lignes et {b} lignes (titre, fusion et noms de fichiers ignorés)",
        "reports_section_differs": "  section {section} : {n} ligne(s) en écart",
        "identical": "Aucun écart : les deux voies donnent les mêmes données.",
        "differences": "Écarts : {n}.",
        "error": "Erreur : {message}",
        "file_missing": "fichier introuvable",
        "data_retired": "data est retirée : la voie CSV n'existe plus",
    },
    "en": {
        "reports_section": "Reports: {a} lines and {b} lines (title, merge and file names ignored)",
        "reports_section_differs": "  section {section}: {n} line(s) differing",
        "identical": "No difference: both routes give the same data.",
        "differences": "Differences: {n}.",
        "error": "Error: {message}",
        "file_missing": "file not found",
        "data_retired": "data is retired: the CSV route no longer exists",
    },
}
