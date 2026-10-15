"""
Implémentation en mémoire de WatchStore et de TriageStore (tools/watch_store.py), pour les tests seulement : jamais importée par tools/.

Même interface, mêmes valeurs rendues (dates, instants avec fuseau, vecteurs float32, dict). Le test de contrat
tests/watch_store/test_contract.py fait passer les mêmes assertions au faux et à PostgreSQL, pour que le faux ne dérive pas.

Transactions : les écritures s'appliquent à un état de travail ; `commit()` le valide, `rollback()` revient au dernier état validé.
`FakeData.fail_on_commit(n)` fait échouer la n-ième validation à venir (WatchDatabaseUnavailable), pour tester « fichier et ligne
ensemble ». `FakeData.edit(fonction)` modifie l'état validé d'un test (vieillir un article, vider une table).
`FakeData.roles` note le rôle demandé à chaque ouverture (« rw » ou « ro »).
"""
import copy
import datetime as dt
import sys
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import watch_store as ws  # noqa: E402

TABLES = ("articles", "runs", "links", "refs", "scores", "forced", "excluded", "shared", "picks", "shadow", "calibration")


class FakeData:
    def __init__(self) -> None:
        self.work = {name: {} for name in TABLES}
        self.committed = copy.deepcopy(self.work)
        self.fail_at: int | None = None
        self.attempts = 0
        self.unavailable: Exception | None = None      # levée à l'ouverture (base éteinte, tables absentes)
        self.roles: list[str] = []
        self.commits = 0

    def open_watch(self, readonly: bool = False, dbname=None, connect=None) -> "FakeWatchStore":
        self._open(readonly)
        return FakeWatchStore(self)

    def open_triage(self, readonly: bool = False, dbname=None, connect=None) -> "FakeTriageStore":
        self._open(readonly)
        return FakeTriageStore(self)

    def _open(self, readonly: bool) -> None:
        self.roles.append("ro" if readonly else "rw")
        if self.unavailable is not None:
            raise self.unavailable

    def fail_on_commit(self, n: int = 1) -> None:
        self.fail_at = self.attempts + n

    def edit(self, function) -> None:
        function(self.work)
        self.committed = copy.deepcopy(self.work)

    def commit(self) -> None:
        self.attempts += 1
        if self.fail_at == self.attempts:
            self.work = copy.deepcopy(self.committed)
            raise ws.WatchDatabaseUnavailable("OperationalError")
        self.committed = copy.deepcopy(self.work)
        self.commits += 1

    def rollback(self) -> None:
        self.work = copy.deepcopy(self.committed)

    def table(self, name: str) -> dict:
        return self.work[name]


def install(testcase) -> FakeData:
    """Branche le faux à la place de la base pour la durée du test : les scripts ouvrent leurs magasins par watch_store."""
    data = FakeData()
    for name, opener in (("open_watch_store", data.open_watch), ("open_triage_store", data.open_triage)):
        patch = mock.patch.object(ws, name, opener)
        patch.start()
        testcase.addCleanup(patch.stop)
    return data


class _Fake:
    def __init__(self, data: FakeData) -> None:
        self.data = data

    def commit(self) -> None:
        self.data.commit()

    def rollback(self) -> None:
        self.data.rollback()

    def close(self) -> None:
        pass


class FakeWatchStore(_Fake):
    def article_exists(self, url):
        return url in self.data.table("articles")

    def earlier_duplicate(self, source, title, published, before_day):
        published = ws.as_date(published)
        return any(a["source"] == source and a["title"] == title and a["published"] == published
                   and a["collected"].astimezone().date() < before_day for a in self.data.table("articles").values())

    def add_article(self, url, source, title, file, published, complete, collected, links_extracted=False):
        if url in self.data.table("articles"):
            raise ValueError("article déjà présent")
        self.data.table("articles")[url] = {
            "url": url, "source": source, "title": title, "file": file, "published": ws.as_date(published),
            "complete": bool(complete), "collected": ws.as_moment(collected), "links_extracted": bool(links_extracted)}

    def add_links(self, article_url, links):
        if article_url not in self.data.table("articles"):
            raise ValueError("article inconnu")
        for link in links:
            self.data.table("links")[(article_url, link)] = True
        self.data.table("articles")[article_url]["links_extracted"] = True

    def record_run_ok(self, source, when):
        self.data.table("runs")[source] = {"last_try": ws.as_moment(when), "last_ok": ws.as_moment(when), "error": None}

    def record_run_error(self, source, when, error):
        previous = self.data.table("runs").get(source) or {"last_ok": None}
        self.data.table("runs")[source] = {"last_try": ws.as_moment(when), "last_ok": previous["last_ok"], "error": error}

    def source_runs(self):
        return {k: dict(v) for k, v in sorted(self.data.table("runs").items())}

    def links_todo(self):
        rows = [a for a in self.data.table("articles").values() if not a["links_extracted"] and a["url"].startswith("http")]
        return [(a["url"], a["title"]) for a in sorted(rows, key=lambda a: (a["collected"], a["url"]))]

    def articles_collected_since(self, since):
        wanted = [a for a in self.data.table("articles").values() if a["collected"] >= ws.start_of(since)]
        by_date = sorted(wanted, key=lambda a: (a["published"] is None, -(a["published"] or dt.date.min).toordinal(), a["url"]))
        return [(a["source"], a["title"], a["url"], a["published"], a["complete"], a["file"])
                for a in sorted(by_date, key=lambda a: a["source"])]

    def all_links(self):
        return sorted(self.data.table("links"))

    def articles(self):
        return [copy.deepcopy(a) for _, a in sorted(self.data.table("articles").items())]


class FakeTriageStore(_Fake):
    def replace_references(self, refs):
        table = self.data.table("refs")
        for url in [u for u, r in table.items() if r["origin"] != "partage"]:
            del table[url]
        for ref in refs:
            self.put_reference(*ref)

    def put_reference(self, url, title, origin, embedding):
        self.data.table("refs")[url] = {"title": title, "origin": origin,
                                        "embedding": np.asarray(embedding, dtype=np.float16).astype(np.float32)}

    def reference_vectors(self):
        return [r["embedding"].copy() for _, r in sorted(self.data.table("refs").items())]

    def put_score(self, **score):
        row = ws.normalize_score(score)
        self.data.table("scores")[row["file"]] = copy.deepcopy(row)

    def all_scores(self):
        return [copy.deepcopy(r) for _, r in sorted(self.data.table("scores").items())]

    def score_files(self):
        return set(self.data.table("scores"))

    def flagged_files(self, flag):
        column = {"compilation": "is_compilation", "promo": "is_promo"}[flag]
        return {f for f, r in self.data.table("scores").items() if r[column]}

    def weak_files(self, max_substance):
        return {f for f, r in self.data.table("scores").items() if r["substance"] is not None and r["substance"] <= max_substance}

    def location_of(self, file):
        row = self.data.table("scores").get(file)
        return None if row is None else row["location"]

    def set_location(self, file, location):
        if file in self.data.table("scores"):
            self.data.table("scores")[file]["location"] = location

    def score_urls(self):
        return [(f, r["url"], r["embedding"].copy()) for f, r in sorted(self.data.table("scores").items()) if r["url"]]

    def forced_files(self):
        return set(self.data.table("forced"))

    def excluded_files(self):
        return set(self.data.table("excluded"))

    def exclude(self, file, day):
        self.data.table("forced").pop(file, None)
        self.data.table("excluded")[file] = ws.as_date(day)

    def restore(self, file, day):
        self.data.table("excluded").pop(file, None)
        self.data.table("forced")[file] = ws.as_date(day)
        self.set_location(file, "watch")

    def shared_files(self):
        return set(self.data.table("shared"))

    def add_share(self, file, url, post_date, found):
        if file in self.data.table("shared"):
            raise ValueError("partage déjà présent")
        self.data.table("shared")[file] = {"url": url, "post_date": ws.as_date(post_date), "found": ws.as_date(found)}

    def share_total(self):
        return len(self.data.table("shared"))

    def shared_found_since(self, since):
        since = ws.as_date(since)
        return [(f, r["found"]) for f, r in sorted(self.data.table("shared").items()) if r["found"] is not None and r["found"] >= since]

    def picked_on_or_before(self, file, day):
        day = ws.as_date(day)
        return any(f == file and d <= day for d, f in self.data.table("picks"))

    def add_picks(self, day, files):
        for file in files:
            self.data.table("picks")[(ws.as_date(day), file)] = True

    def pick_days(self):
        return sorted(self.data.table("picks"))

    def put_shadow(self, **row):
        value = ws.normalize_shadow(row)
        self.data.table("shadow")[(value["url"], value["language"])] = copy.deepcopy(value)

    def shadow_rows(self):
        return [copy.deepcopy(r) for _, r in sorted(self.data.table("shadow").items())]

    def _shadow_for(self, score, language):
        return self.data.table("shadow").get((score["url"] or score["file"], language))

    def shadow_candidates(self, language, current_hash):
        out = []
        for file, s in sorted(self.data.table("scores").items()):
            if s["criteria"] is None or not s["complete"]:
                continue
            h = self._shadow_for(s, language)
            if h is None or h["prompts_hash"] != current_hash:
                out.append({"file": file, "location": s["location"], "title": s["title"]})
        return out

    def shadow_pairs(self, language):
        out = []
        for file, s in sorted(self.data.table("scores").items()):
            h = self._shadow_for(s, language)
            if s["criteria"] is None or h is None or h["criteria"] is None:
                continue
            side = lambda r: {"criteria": r["criteria"], "substance": r["substance"], "is_compilation": r["is_compilation"],  # noqa: E731
                              "in_themes": r["in_themes"], "is_promo": r["is_promo"]}
            out.append({"file": file, "title": s["title"], "source": s["source"], "fr": side(s), "en": side(h)})
        return out

    def refresh_calibration(self, entries, exported_at):
        table = self.data.table("calibration")
        moment = ws.as_moment(exported_at)
        for e in entries:
            kept = table.get(e["file"], {})
            table[e["file"]] = {
                "file": e["file"], "exported_at": moment, "verdict": e["verdict"], "relevance": e.get("relevance"),
                "substance": e.get("substance"), "in_themes": e.get("in_themes"), "is_compilation": e.get("is_compilation"),
                "is_promo": e.get("is_promo"), "missing": e.get("missing"),
                "opinion": kept.get("opinion"), "opinion_at": kept.get("opinion_at")}

    def apply_opinions(self, opinions, when=None):
        moment = ws.as_moment(when) or dt.datetime.now().astimezone()
        counts = {"keep": 0, "discard": 0, "cleared": 0, "unknown": 0}
        for file, keep in opinions.items():
            row = self.data.table("calibration").get(file)
            if row is None:
                counts["unknown"] += 1
            elif keep is None:
                counts["cleared"] += row["opinion"] is not None
                row["opinion"] = row["opinion_at"] = None
            else:
                row["opinion"], row["opinion_at"] = ("keep" if keep else "discard"), moment
                counts["keep" if keep else "discard"] += 1
        return counts

    def calibration_entries(self):
        out = []
        for file, row in sorted(self.data.table("calibration").items()):
            score = self.data.table("scores").get(file)
            out.append({**copy.deepcopy(row), "title": score["title"] if score and score["title"] else file})
        return out

    def calibration_opinions(self):
        return {f: ws.OPINION_OF[r["opinion"]] for f, r in sorted(self.data.table("calibration").items()) if r["opinion"]}
