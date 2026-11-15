"""Messages de tools/train_record.py par langue (change autonomous-trains-merge, design D4 et D19). Le français est la langue de référence."""

CATALOGS = {
    "fr": {
        "unreadable": "train_record : journal des trains illisible : ligne {n}",
        "unreadable_file": "train_record : journal des trains illisible",
        "not_writable": "train_record : journal des trains non inscriptible",
        "purged": "train_record : {n} enregistrement(s) retiré(s) (plus d'un an)",
        "folders": "train_record : dossiers du lab introuvables",
        "unexpected": "train_record : erreur inattendue ({kind})",
        "invalid": "train_record : champ refusé : {field}",
        "appended": "train_record : enregistrement ajouté (code {code}, {sens})",
        "list_line": "train_record : {heure} : code {code} ({sens}), {mode}, {n} branche(s), runner {runner}, {duree} s",
        "list_empty": "train_record : journal des trains vide",
    },
    "en": {
        "unreadable": "train_record: train record unreadable: line {n}",
        "unreadable_file": "train_record: train record unreadable",
        "not_writable": "train_record: train record not writable",
        "purged": "train_record: {n} record(s) removed (older than one year)",
        "folders": "train_record: lab folders not found",
        "unexpected": "train_record: unexpected error ({kind})",
        "invalid": "train_record: field refused: {field}",
        "appended": "train_record: record added (code {code}, {sens})",
        "list_line": "train_record: {heure}: code {code} ({sens}), {mode}, {n} branch(es), runner {runner}, {duree} s",
        "list_empty": "train_record: train record empty",
    },
}
