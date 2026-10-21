# Projection refreshes (measured on the main run; estimates are labelled)

Conservative = measured $/distinct text × 1.5. Subset = declared 173,000-review subset (planned run) (132,832 distinct texts).

| Checkpoint | Distinct texts classified | Requests (failed) | Retry frac | Measured enrich $ | $/distinct text | Subset base $ (est.) | Subset conservative $ (est.) | Full corpus base $ (est.) | Ledger spent, all stages $ | Fits cap? |
|---|---|---|---|---|---|---|---|---|---|---|
| 500 | 479 | 10 (0) | 0.0 | 0.008424 | 0.0000175876 | 2.3362 | 3.5043 | 8.5157 | 0.025619 | yes |
| 10000 | 8,448 | 172 (0) | 0.0 | 0.145988 | 0.0000172808 | 2.2954 | 3.4432 | 8.3672 | 0.163183 | yes |
