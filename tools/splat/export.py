"""Stage 4: export the splat, prune for Quest, write viewer metadata.  python export.py work/room1 --max-splats 1500000"""
import argparse, json
from pathlib import Path
import numpy as np
from plyfile import PlyData, PlyElement
from common import report, run


def export(work: Path, max_splats: int = 1_500_000) -> Path:
    cfg = sorted((work / "train").rglob("config.yml"))[-1]; out = work / "export"; out.mkdir(exist_ok=True)
    run(["ns-export", "gaussian-splat", "--load-config", cfg, "--output-dir", out], work / "export.log")
    raw = out / "splat.ply"
    ply = PlyData.read(str(raw)); v = ply["vertex"].data
    opacity = 1 / (1 + np.exp(-v["opacity"]))                          # stored as logit
    scale = np.exp(np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], 1)).max(1)
    keep = (opacity > 0.05) & (scale < 0.5)                            # drop near-invisible and huge "sky" splats
    # TODO: crop to the fused-map bounding box (+0.3 m) from points3D.ply to kill floaters outside the house
    idx = np.where(keep)[0]
    if len(idx) > max_splats:                                          # keep the most visible
        idx = idx[np.argsort(-(opacity[idx] * scale[idx] ** 2))[:max_splats]]
    PlyData([PlyElement.describe(v[idx], "vertex")], text=False).write(str(out / "scene.ply"))
    xyz = np.stack([v["x"][idx], v["y"][idx], v["z"][idx]], 1)
    meta = {"splats": int(len(idx)), "bounds_min": xyz.min(0).tolist(), "bounds_max": xyz.max(0).tolist(),
            "floor_y": float(np.percentile(xyz[:, 1], 2)), "frame": "headset metres, +y up"}
    (out / "scene.meta.json").write_text(json.dumps(meta, indent=1))
    # TODO: compress to .spz (github.com/nianticlabs/spz) for ~10x smaller Quest downloads
    mb = (out / "scene.ply").stat().st_size / 1e6
    report(work, "export", mb <= 350, splats=int(len(idx)), ply_mb=round(mb, 1))
    return out / "scene.ply"


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("work", type=Path); a.add_argument("--max-splats", type=int, default=1_500_000)
    o = a.parse_args(); export(o.work, o.max_splats)
