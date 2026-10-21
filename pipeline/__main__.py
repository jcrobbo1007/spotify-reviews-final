"""CLI. Paid stages run only with --paid; everything else is offline."""
import argparse
import sys


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare", help="Stage 1: ingest/profile full CSV, build subset, seed state (no API)")
    c = sub.add_parser("cost", help="Cost calculator: offline replay (default) or the paid 100-review pilot")
    c.add_argument("--replay", action="store_true", help="offline replay from saved usage x editable rates (default)")
    c.add_argument("--pilot", action="store_true", help="run the real 100-review pilot (needs --paid)")
    c.add_argument("--mode", choices=["cold", "warm"], default="cold")
    c.add_argument("--stages", default="enrich,verify,group,rank,memo")
    c.add_argument("--paid", action="store_true", help="allow paid API calls")
    r = sub.add_parser("run", help="Main staged run over the declared subset (paid stages need --paid); resumable")
    r.add_argument("--input", default="data/spotify_reviews_18months.csv")
    r.add_argument("--scope", choices=["500", "10000", "subset"], default="subset")
    r.add_argument("--stages", default="enrich,downstream")
    r.add_argument("--requests-per-wave", type=int, default=100)
    r.add_argument("--stop-after-waves", type=int, default=None)
    r.add_argument("--paid", action="store_true")
    k = sub.add_parser("rank", help="Regenerate ranking.csv from saved membership + records (no model, no key)")
    k.add_argument("--membership", default="outputs/membership.csv")
    k.add_argument("--records", default="outputs/records.jsonl")
    k.add_argument("--out", default="outputs/ranking.csv")
    ev = sub.add_parser("eval", help="Offline evaluations")
    ev.add_argument("which", choices=["golden"])
    x = sub.add_parser("export", help="Write grading/ export and run the zero-API checker (no model calls)")
    args = p.parse_args(argv)
    if args.cmd == "prepare":
        from . import prepare
        report, info, counts = prepare.main()
        print("brief checks:", {k: v["match"] for k, v in report["brief_checks"].items()})
        print("subset:", info)
        print("status counts:", counts)
    elif args.cmd == "run":
        if not args.paid:
            p.error("the run makes paid API calls; add --paid")
        from . import common, run, state
        d = common.decisions()
        ledger = state.Ledger(d["spend_cap_usd"], f"main-{args.scope}")
        stages = args.stages.split(",")
        if "enrich" in stages:
            print(run.enrich_stage(args.scope, ledger, args.requests_per_wave, args.stop_after_waves))
        if "downstream" in stages:
            vsum, ranking, out = run.downstream(ledger, d["scope"]["label"] + "; counts are subset counts")
            print("verify:", vsum, "| issues:", len(ranking), "| memo:", bool(out))
        print("ledger:", ledger.summary())
    elif args.cmd == "rank":
        from . import rank
        rows = rank.from_files(args.membership, args.records, args.out)
        print(f"wrote {args.out}: {len(rows)} issues")
    elif args.cmd == "eval":
        from . import golden
        golden.main()
    elif args.cmd == "export":
        from . import export
        print(export.main())
        res = export.checker()
        print({k: res.get(k) for k in ("status", "coverage", "issue_counts")})
    elif args.cmd == "cost":
        if args.pilot:
            if not args.paid:
                p.error("the pilot makes paid API calls; add --paid")
            from . import common, pilot, state
            d = common.decisions()
            ledger = state.Ledger(d["spend_cap_usd"], f"pilot-{args.mode}")
            print(pilot.run(args.mode, args.stages.split(","), ledger))
            print("ledger:", ledger.summary())
        else:
            from cost import calculator
            calculator.main()


if __name__ == "__main__":
    sys.exit(main())
