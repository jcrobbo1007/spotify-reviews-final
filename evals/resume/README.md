# Interruption / resume evidence

Run during the 173,000-subset enrichment stage (2026-10-21). Planned for the 10,000 stage, but a wave-size bug
(`--requests-per-wave` bound at import) let that stage finish in two waves before the kill point; that log is kept as
`terminal_10000_no_interrupt.log`, the bug was fixed, and the demo moved to the next stage.

Sequence (`terminal.log`, written by `run_demo.py`; no screen recorder is available here, so this log is the recording):

1. `python -m pipeline run --paid --scope subset --stages enrich --requests-per-wave 300`
2. Waves 1–2 committed; wave 3 (`msgbatch_01QPjPmbAucRwhq4zGYznmMd`, 300 requests) submitted and in flight.
3. Process hard-killed (TerminateProcess) at 01:28:01.
4. Identical command restarted at 01:28:06. The pipeline detected the unclean stop, wrote `checkpoint_before.json`
   (75,241 completed IDs, the state saved before the kill), **reconciled the in-flight batch by polling it rather than
   resubmitting**, then submitted the remaining work with `phase: "resume"`.
5. Stage finished: `checkpoint_after.json` has 172,960 completed IDs; before ⊂ after.
6. Check in the log: `checkpoint_before IDs sent again in phase=resume calls: 0` — completed IDs were not re-billed.

The killed process's spend reservation for wave 3 ($0.473261) stayed in the shared ledger while it was in flight and was
settled to the actual charge ($0.262295) when the restarted process collected the batch.
