#!/bin/bash
# PMZilla Lab : enveloppe figée du lecteur des vues agrégées (niveau 2 du bac à sable, design D4, D12 ; tâches 7.2 et 7.3 ; Q11 (a)).
#
#     /bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/flow_views.sh show <vue> [--min-cell N] [--lang fr|en]
#
# Appelée par la session elle-même, seule dans son appel Bash. Sans elle, le lecteur des vues n'atteindrait aucune base sous le bac à sable.
# Seule la sous-commande `show` est permise (sinon 96) ; le relevé des empreintes est contrôlé d'abord (97) ; le script figé tourne avec un
# environnement fermé, depuis le dossier des copies figées. Aucun argument n'est un fichier : rien d'autre n'est contrôlé ici (la liste fermée des vues est celle du script figé).
# Remplace : l'appel direct de tools/flow_views.py show depuis la session. Retrait : avec le bac à sable.
# R-20261111-13, -15 : première instruction, avant tout nom de commande (une fonction exportée ou BASH_ENV ne doit rien exécuter ici). Relance sous `env -i`
# (rien de la session ne passe) par /bin/bash --noprofile --norc ; le marqueur est le PID, conservé par exec. Limite réelle (R-20261111-19 à -22, -23, -38) :
# l'appel se fait dans la forme /bin/bash --noprofile --norc -p (la garde refuse l'ancien ordre `/bin/bash -p --noprofile --norc`). Sur le /bin/bash 3.2.57 du Mac,
# -p ferme BASH_ENV, ENV, les fonctions importées et SHELLOPTS (suite forme_p_mac, M1) ; CDPATH y reste suivi (constat M2) : il est tenu par la relance sous
# `env -i` ci-dessus, qui n'est précédée d'aucune commande nommée ni d'aucun `cd` (test statique), et par la garde de session. Restent à la garde : PATH, IFS,
# LANG, LC_*, et le marqueur, qui se forge par un exec qui garde le PID ; une fonction exportée `exec` ou `unset` détourne la relance.
# Remplace : rien. Retrait : permanent tant que les enveloppes sont exclues du bac à sable. Bash 3.2 (macOS) : `[[ ]]` et `$$` seulement.
if [[ ${FIGE_RELANCE-} != "$$" ]]; then
  exec /usr/bin/env -i "FIGE_RELANCE=$$" /bin/bash --noprofile --norc "$0" "$@"
fi
unset FIGE_RELANCE
case "$0" in */*) ICI=${0%/*} ;; *) ICI=. ;; esac
ICI=$(cd -P -- "$ICI" 2>/dev/null && pwd -P) || exit 97
FIGES=$ICI
if [ ! -r "$FIGES/enveloppe.sh" ]; then
  printf "outil figé : empreinte différente de son relevé, rien n'est lancé : enveloppe.sh\n" >&2
  exit 97
fi
. "$FIGES/enveloppe.sh"

fige_verifier flow_views.sh enveloppe.sh dossiers.conf copie/tools/flow_views.py copie/tools/db.py copie/tools/messages.py \
  copie/tools/flow_views_messages.py copie/tools/lab_paths.py
fige_conf_controle

sous=${1-}
[ "$sous" = show ] || fige_sous_refusee "$sous"
shift

fige_env
cd -P -- "$FIGES/copie" 2>/dev/null || fige_97 copie
exec /usr/bin/env -i "${ENV_FIGE[@]}" uv run --script "$FIGES/copie/tools/flow_views.py" show ${1+"$@"}
