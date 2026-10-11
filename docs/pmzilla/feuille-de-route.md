# Roadmap: work queue

This page is the work queue of your repository. It starts empty. The order of the YAML block below is the priority. It is read by `tools/roadmap.py` (`check`, `next --budget <duration>`, `done <id>`) and by the `/next`, `/start` and `/close` commands. The reader only writes the state of the job passed to `done`: it never reorders and never estimates.

Add one entry per job to the `jobs` list (replace `jobs: []` by the list). Keys in English, free text in your language. Fields: `id` (`R-` followed by digits), `title`, `depends_on` (list of ids), `conditions` (text, to be confirmed by the user), `not_before` (date: the job is not offered before it), `due` (date: displayed, does not reorder), `state` (`ready`, `blocked`, `in-progress`, `done`), `estimate` (`45min`, `2h`, `1h30` or `tbd`), `method` (`openspec` or `direct-prompt`), `model` (`opus`, `sonnet`, `haiku` or `tbd`), `change` (name of the OpenSpec change, read by `/close`).

Rules checked by `check`: unique ids, known dependencies, no cycle, a `ready` job has all its dependencies `done`, a `done` job has no unfinished dependency.

An example entry, to copy into the block:

    - id: R-1
      title: "First job"
      depends_on: []
      conditions: ""
      state: ready
      estimate: 1h
      method: direct-prompt
      model: tbd

## Jobs described

Describe each job here, in free text, under its id (for example **R-1, first job.** What it is for, what done means). `/start <id>` reads this description.

```yaml
jobs: []
```
