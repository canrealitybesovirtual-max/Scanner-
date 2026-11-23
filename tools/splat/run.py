"""One command: capture zip -> splat.  python run.py scan-photos.zip [--work work/<name>] [--iters 30000]"""
import argparse, json
from pathlib import Path
from ingest import ingest
from refine_poses import refine
from train import train
from export import export
from evaluate import evaluate

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("zip", type=Path); a.add_argument("--work", type=Path); a.add_argument("--iters", type=int, default=30000)
    a.add_argument("--max-splats", type=int, default=1_500_000); a.add_argument("--force", action="store_true")
    o = a.parse_args(); work = o.work or Path("work") / o.zip.stem
    ingest(o.zip, work, o.force)
    refine(work, o.force)
    train(work, o.iters)
    evaluate(work)
    export(work, o.max_splats)
    rep = json.loads((work / "report.json").read_text())
    print(json.dumps(rep, indent=1)); raise SystemExit(0 if rep["pass"] else 1)
