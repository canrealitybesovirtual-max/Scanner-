"""Stage 3: train splatfacto on the refined dataset.  python train.py work/room1 --iters 30000"""
import argparse
from pathlib import Path
from common import report, run


def train(work: Path, iters: int = 30000, big: bool = False) -> Path:
    out = work / "train"
    method = "splatfacto-big" if big else "splatfacto"
    run(["ns-train", method, "--data", work / "ns", "--output-dir", out, "--max-num-iterations", iters,
         "--viewer.quit-on-train-completion", "True",
         "--pipeline.model.camera-optimizer.mode", "SO3xR3",            # absorbs leftover head/camera offset
         "nerfstudio-data", "--eval-mode", "interval", "--eval-interval", "8",   # every 8th frame held out for evaluate.py
         "--load-3D-points", "True"], work / "train.log")
    # TODO: depth supervision from the fused voxel map (render per-frame depth PNGs at export time on the headset)
    # TODO: appearance embedding / exposure compensation when ingest reports exposure spread
    cfg = sorted(out.rglob("config.yml"))[-1]
    report(work, "train", True, config=str(cfg), iters=iters, method=method)
    return cfg


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("work", type=Path); a.add_argument("--iters", type=int, default=30000); a.add_argument("--big", action="store_true")
    o = a.parse_args(); train(o.work, o.iters, o.big)
