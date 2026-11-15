"""
Aide des tests du train (aide_train.Train.lance) : un script qui laisse derrière lui des processus tenant ses tubes ne doit pas bloquer l'aide.

Cas reproduit (diagnostic R-20261104-26) : le journal de tools/finish_train.sh (open_log) lance un `tee` détaché qui ignore INT, TERM et HUP et que
drain_tee abandonne après cinq secondes ; avec subprocess.run(capture_output=True), ce `tee` tient les tubes de sortie et l'aide attend jusqu'au délai,
puis laisse un `tee` orphelin. Le faux script ci-dessous reproduit open_log, lance un `sleep 60` sans redirection, puis sort avec le code 0.
Attendu : code 0 en moins de 10 s, ni le sleep ni le tee vivants. Remplace : rien (test nouveau). Condition de retrait : permanent (garde de l'aide).
"""
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_train import AvecTrain  # noqa: E402

FAUX_SCRIPT = """#!/bin/bash
exec 3>&1 4>&2
LOG="@DOSSIER@/journal.log"
: > "$LOG"
FIFO=$(mktemp -u "@DOSSIER@/fin-tee.XXXXXX")
mkfifo "$FIFO"
( trap '' INT TERM HUP; exec tee -a "$LOG" ) < "$FIFO" >&3 3>&- 4>&- &
TEE_PID=$!
disown "$TEE_PID"
echo "$TEE_PID" > "@DOSSIER@/pid-tee"
exec > "$FIFO" 2>&1
rm -f "$FIFO"
sleep 60 &
echo $! > "@DOSSIER@/pid-sleep-faux"
exit 0
"""


def vivant(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class TestAideLance(AvecTrain):
    def test_script_qui_laisse_tee_et_sleep_ne_bloque_pas(self):
        dossier = Path(self.temp.name)
        script = dossier / "faux-train.sh"
        script.write_text(FAUX_SCRIPT.replace("@DOSSIER@", str(dossier)), encoding="utf-8")
        debut = time.time()
        resultat = self.t.lance(script=script, delai=10)
        duree = time.time() - debut
        self.assertEqual(resultat.code, 0)
        self.assertLess(duree, 10)
        pids = [int((dossier / nom).read_text().strip()) for nom in ("pid-tee", "pid-sleep-faux")]
        time.sleep(0.3)  # laisse le noyau recueillir les processus tués
        for pid in pids:
            self.assertFalse(vivant(pid), f"le processus {pid} est resté vivant après lance()")


if __name__ == "__main__":
    unittest.main()
