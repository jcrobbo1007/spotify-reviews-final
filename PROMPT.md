Kickoff prompt — paste into Claude Code
Start Claude Code in `C:\Users\jcrob\code\spotify-reviews-final` (the repo already exists and is pushed). Copy `CLAUDE.md` into the repo root first. Do the pre-flight with Jack present (~20–30 min), then the rest runs unattended overnight.
You are building my Final Assignment for "From Zero to AI Agents": a multi-agent pipeline that turns 660,622 Spotify reviews into a product-priority recommendation with traceable evidence, plus a deployed dashboard + backend + database. The full brief and the dataset docs are the source of truth. Read `CLAUDE.md` now and follow it for the whole task.
Phase 0 — pre-flight (I'm here; ask me, don't guess)

1. Confirm the dataset is unzipped in `data/` (11 files: `spotify_reviews_18months.csv`, `cost_100.csv`, `checkpoint_500.csv`, `analysis_10000.csv`, `golden_50_to_label.csv`, `manifest.json`, `README.md`, `prepare_dataset.py`, `GRADING_CONTRACT.md`, `check_submission.py`, `COST_CALCULATOR.md`). Verify the CSV's SHA-256 against `manifest.json`. If anything is missing, stop and tell me.
2. Read `GRADING_CONTRACT.md` and `COST_CALCULATOR.md` in full. Summarise for me in ≤10 lines anything that changes the plan in `CLAUDE.md` (export schema, hashing, label_config, file names).
3. Confirm `.env` exists, is git-ignored (`git check-ignore .env`), and has the key(s) for the provider I choose. Never print key values.
4. Check logins non-interactively: `gh auth status`, `supabase --version` / projects list, `vercel whoami`. Anything not logged in, have me log in now — I won't be awake later.
5. Ask me these and record the answers in `config/run_decisions.json`:
   * Enrichment provider + exact model (recommend one cheap small model; give me the current price per MTok from the provider's pricing page with the date you checked).
   * Hard API spend cap in USD for the whole night (all stages combined).
   * Max workers (start 1, ramp to what rate limits allow).
   * Fallback model + max fallback fraction (default: none, or ≤2%).
   * Minimum acceptable coverage if the cap binds (brief allows ≥100,000; target all 660,609).
6. Build Stage 1 (ingest/profile) and the cost calculator, then run the paid 100-review cold pilot and the warm replay while I watch. Show me measured cost/100, s/100 and the base and conservative full-run projections against my cap. I say go or adjust before you scale.

Phase 1 — overnight, unattended
After my go: run 500 → refresh projection → 10,000 → refresh projection → full corpus, within the cap, exactly as `CLAUDE.md` specifies. Then verification, grouping, ranking, memo, grading export, `check_submission.py`, database load, backend + dashboard deploy, README. Commit and push at each milestone listed in `CLAUDE.md`. If you hit a decision that is irreversible or ambiguous, do the safe preparatory work, write the question at the top of `STATUS.md`, and continue with everything that doesn't depend on it.
What waits for me in the morning

* Hand-labelling the golden 50. Do NOT pre-fill, suggest or model-draft those labels — they must be mine. Prepare `evals/golden_50_labels.csv` with blank label columns plus the contract's definitions beside it, and have the eval script ready to run the moment I fill it in.
* Anything flagged at the top of `STATUS.md`.

Keep `STATUS.md` current (what's done, counts, spend so far vs cap, what's running, what's blocked) — it's the first thing I'll read when I wake up.
