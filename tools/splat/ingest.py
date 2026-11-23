"""Stage 1: unzip + validate a capture, flag blur and tracking jumps.  python ingest.py scan.zip work/room1"""
import argparse, json, shutil, zipfile
from pathlib import Path
from common import load_capture, pose_jumps, report


def ingest(zip_path: Path, work: Path, force: bool = False) -> Path:
    cap_dir = work / "capture"
    if cap_dir.exists() and not force:
        return cap_dir
    shutil.rmtree(cap_dir, ignore_errors=True); cap_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        for n in z.namelist():                       # never extract outside cap_dir
            if n.startswith("/") or ".." in Path(n).parts:
                raise SystemExit(f"unsafe path in zip: {n}")
        z.extractall(cap_dir)
    cap = load_capture(cap_dir)
    sharp = [f.sharp for f in cap.frames if f.sharp]
    jumps = pose_jumps(cap.frames)
    # TODO: exposure normalisation (match per-frame mean luminance to a running median) before training
    # TODO: mask clipped pixels (windows) and Meta 'screen'/'window' labels into masks/frame_xxxxx.png
    ok = len(cap.frames) >= 60 and cap.points_ply is not None
    report(work, "ingest", ok, frames=len(cap.frames), has_points=cap.points_ply is not None,
           tracking_jumps=jumps, intrinsics=cap.manifest.get("intrinsics", "unknown"),
           sharp_median=sorted(sharp)[len(sharp) // 2] if sharp else None)
    if not ok:
        raise SystemExit("ingest FAIL: need ≥ 60 frames and points3D.ply (scan longer with camera colour on)")
    return cap_dir


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("zip", type=Path); a.add_argument("work", type=Path); a.add_argument("--force", action="store_true")
    o = a.parse_args(); ingest(o.zip, o.work, o.force)
