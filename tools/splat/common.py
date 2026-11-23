"""Shared data contract for house-scanner-capture/2 (see docs/gaussian-splat-pipeline.md §3)."""
from __future__ import annotations
import json, math, subprocess, sys, time
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

FORMAT = "house-scanner-capture/2"
GL_TO_CV = np.diag([1.0, -1.0, -1.0, 1.0])          # OpenGL camera (-z fwd, +y up) <-> OpenCV (+z fwd, -y up)


@dataclass
class Frame:
    i: int
    file: str
    c2w_gl: np.ndarray            # 4x4, camera-to-world, OpenGL convention, metres
    fx: float; fy: float; cx: float; cy: float; w: int; h: int
    sharp: float | None = None
    t_ms: float | None = None


@dataclass
class Capture:
    root: Path
    manifest: dict
    frames: list[Frame] = field(default_factory=list)
    points_ply: Path | None = None


def load_capture(root: Path) -> Capture:
    """Read + validate an unzipped capture. Raises ValueError naming the first contract violation."""
    man = json.loads((root / "manifest.json").read_text()) if (root / "manifest.json").exists() else {"format": "house-scanner-capture/1?"}
    tj = json.loads((root / "transforms.json").read_text())
    frames = []
    for i, f in enumerate(tj["frames"]):
        g = {k: f.get(k, tj.get(k)) for k in ("fl_x", "fl_y", "cx", "cy", "w", "h")}
        if None in g.values():
            raise ValueError(f"frame {i}: missing intrinsics {g}")
        m = np.array(f["transform_matrix"], dtype=np.float64)
        if m.shape != (4, 4) or not np.allclose(m[3], [0, 0, 0, 1]):
            raise ValueError(f"frame {i}: bad transform_matrix")
        R = m[:3, :3]
        if abs(np.linalg.det(R) - 1) > 1e-3:
            raise ValueError(f"frame {i}: rotation not orthonormal (det {np.linalg.det(R):.4f})")
        if not (root / f["file_path"]).exists():
            raise ValueError(f"frame {i}: image {f['file_path']} missing")
        frames.append(Frame(i, f["file_path"], m, g["fl_x"], g["fl_y"], g["cx"], g["cy"], int(g["w"]), int(g["h"])))
    # optional raw log: sharpness + timestamps
    pj = root / "poses.jsonl"
    if pj.exists():
        for line in pj.read_text().splitlines():
            o = json.loads(line)
            if o["i"] < len(frames):
                frames[o["i"]].sharp, frames[o["i"]].t_ms = o.get("sharp"), o.get("t")
    ply = root / tj.get("ply_file_path", "points3D.ply")
    return Capture(root, man, frames, ply if ply.exists() else None)


def pose_jumps(frames: list[Frame], max_m: float = 0.10, max_dt_ms: float = 1500) -> list[int]:
    """Indices where tracking probably relocalised (big move in a short time): split points for COLMAP."""
    out = []
    for a, b in zip(frames, frames[1:]):
        d = np.linalg.norm(a.c2w_gl[:3, 3] - b.c2w_gl[:3, 3])
        dt = (b.t_ms - a.t_ms) if (a.t_ms and b.t_ms) else 500
        if d > max_m and dt < max_dt_ms and d / max(dt, 1) * 1000 > 1.5:   # > 1.5 m/s is not walking
            out.append(b.i)
    return out


def umeyama(src: np.ndarray, dst: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Similarity (s, R, t) with dst ≈ s·R·src + t. Used to put refined COLMAP poses back in headset metres."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    U, S, Vt = np.linalg.svd(xd.T @ xs / len(src))
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / (xs ** 2).sum() * len(src)
    return s, R, mu_d - s * R @ mu_s


def run(cmd: list[str], log: Path | None = None) -> None:
    """Run an external tool, echo the command, fail loudly."""
    print("$", " ".join(map(str, cmd)), flush=True)
    t0 = time.time()
    with (open(log, "a") if log else sys.stdout) as fh:
        r = subprocess.run(list(map(str, cmd)), stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode:
        raise SystemExit(f"command failed ({r.returncode}) after {time.time() - t0:.0f}s: {cmd[0]}" + (f" — see {log}" if log else ""))


def report(work: Path, stage: str, ok: bool, **metrics) -> None:
    p = work / "report.json"
    rep = json.loads(p.read_text()) if p.exists() else {"stages": {}}
    rep["stages"][stage] = {"pass": ok, **metrics}
    rep["pass"] = all(s["pass"] for s in rep["stages"].values())
    p.write_text(json.dumps(rep, indent=1))
    print(f"[{stage}] {'PASS' if ok else 'FAIL'} {metrics}")
