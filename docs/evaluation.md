# Evaluation harness (Milestone 2)

Files: `tests/harness/cases.json` (the dataset: 17 cases, 9 adversarial, including two indirect prompt injections planted in search results) and `tests/harness/run_eval.py` (the runner).

Run from the `coach_repo` folder with your keys in the environment:

    python tests/harness/run_eval.py --k 3

Definitions: **pass@1** = passing runs / all runs. **pass^k** = share of cases that pass on all k runs.
Each run uses a fresh visitor and the real agents, tools, guards and model. The report lands in `tests/harness/results/<time>/report.md`.
