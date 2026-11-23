"""Stage 5: held-out quality gate.  python evaluate.py work/room1"""
import argparse, json
from pathlib import Path
from common import report, run


def evaluate(work: Path, min_psnr: float = 24.0, min_ssim: float = 0.80) -> bool:
    cfg = sorted((work / "train").rglob("config.yml"))[-1]; out = work / "eval.json"
    run(["ns-eval", "--load-config", cfg, "--output-path", out], work / "eval.log")
    r = json.loads(out.read_text())["results"]
    ok = r["psnr"] >= min_psnr and r["ssim"] >= min_ssim
    # TODO: floater metric: fraction of splats > 0.3 m from any fused-map voxel
    report(work, "evaluate", ok, psnr=round(r["psnr"], 2), ssim=round(r["ssim"], 3), lpips=round(r.get("lpips", -1), 3))
    return ok


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("work", type=Path); o = a.parse_args()
    raise SystemExit(0 if evaluate(o.work) else 1)
