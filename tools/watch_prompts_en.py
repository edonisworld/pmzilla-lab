"""PMZilla Lab : prompts et thèmes anglais du pré-tri de la veille (version anglaise, lot 5b).

Prompts officiels de l'édition publiée : ils décident quand `language: en` dans tri.yaml, et servent à la notation en
ombre. Ils traduisent `SYSTEM_PROMPT`, `USER_PROMPT`, `CRITERIA` et les thèmes de `watch_triage.py`, avec deux
ajustements volontaires du lot 5b (items compilation et promotionnel), mesurés par shadow-backfill puis shadow-report. Les clés JSON (resume, pourquoi,
compilation, dans_themes, promotionnel, these, etaye, original, sources, non_promo, ok, justification) sont des
identifiants de code : elles ne sont pas traduites. Correspondance phrase par phrase :
docs/pmzilla/watch-prompts-en-correspondance.md
"""

SYSTEM_PROMPT = """You evaluate articles for the library of an Agile Lead who supports an organisation in its \
product transformation. Their themes: {themes}.
Evaluate each criterion separately, from the text only: an article can meet some of them and not others. A \
criterion is true only if the article clearly meets it.
Write in English. Reply only in JSON."""

USER_PROMPT = """Title: {title}
Source: {source}

Text:
{text}

In this order:
1. resume: two sentences on what the article says.
2. pourquoi: one sentence on what the article brings to these themes (not a judgement of its quality), \
or "off topic".
3. compilation: "justification", then "ok". Be strict: true only if most of the text is a list of content by \
OTHER authors (articles, videos, books), each presented in a few lines, without a sustained argument by the \
author: a link roundup, "what I've been reading", a link newsletter, an event programme. false in all other \
cases, in particular: an essay that cites several sources, a podcast episode or an interview, a reading guide \
written by the author of the book, an article that comments at length on a single source. Also false: an \
article in which the author's own argument runs through the text, even when it is organised as a list of items \
each commented at some length. A short introduction followed by a list of other people's content stays true.
4. dans_themes: "justification", then "ok" set to true if the main subject of the article falls under at least \
one of the listed themes, even indirectly (for example leadership or change management for coaching, \
portfolio management for product strategy); false if it falls under another field (pure technology, \
health, finance, personal life…).
5. promotionnel: "justification", then "ok". Run this test: if you remove from the text every passage that \
presents an offer (book, workshop, webinar, club, newsletter, tool, service, call to buy or to \
sign up, paid course), is a complete, argued article left? If so, answer false, even if the offer is \
highlighted at the start or at the end. Answer true only if the main purpose of the text is to sell or to \
get the reader to sign up: a book excerpt or chapter published to launch that book (with a launch, pre-order \
or purchase mention); a book announcement; an announcement of, or registration for, a webinar, event, live \
session, paid course, cohort or programme; a commercial offer (presentation page for a tool or a service, \
invitation to download or to sign up). An author who mentions in passing their own book, newsletter, \
consultancy or services does not make promotional an article that develops a substantive thesis: answer false.
6. For each criterion below: "justification", one sentence that quotes or describes the specific element of the \
text you rely on, then "ok" (true or false) consistent with that justification.
{criteria}"""

CRITERIA = {  # clé : (question posée au modèle, raison affichée quand le critère manque)
    "these": ("The article defends a central idea or a clear position (an FAQ or an interview can have one).",
              "no clear position"),
    "etaye": ("The claims are backed by data, concrete cases or lessons from experience.",
              "claims not backed up"),
    "original": ("The article brings its own point of view, not a rewording of well-known notions.",
                 "rewording of well-known notions"),
    "sources": ("The article cites identifiable sources, authors or studies.", "no source cited"),
    "non_promo": ("The article is neither promotional nor a generic list of tips.",
                  "promotional or generic list"),
}

THEMES = [
    "product discovery and experimentation",
    "flow, flow metrics and predictability",
    "Product Operating Model and product transformation",
    "multi-team organisation, Team Topologies, dependencies",
    "OKRs, prioritisation, product strategy",
    "internal platforms and developer experience",
    "agile coaching, facilitation, Scrum Master stance",
    "AI in product work",
]
