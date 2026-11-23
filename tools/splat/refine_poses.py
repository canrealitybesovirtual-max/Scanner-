"""Stage 2: COLMAP pose + intrinsics refinement seeded with headset poses.  python refine_poses.py work/room1

Headset poses go in as a fixed-camera model -> point_triangulator -> bundle_adjuster (poses + focal + principal point
free) -> similarity-aligned back onto the headset trajectory, so the result stays metric, gravity-up, floor at 0."""
import argparse, json, shutil, sqlite3
from pathlib import Path
import numpy as np
from common import GL_TO_CV, load_capture, report, run, umeyama


def rot_to_qvec(R):
    w = np.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    x = np.copysign(np.sqrt(max(0.0, 1 + R[0, 0] - R[1, 1] - R[2, 2])) / 2, R[2, 1] - R[1, 2])
    y = np.copysign(np.sqrt(max(0.0, 1 - R[0, 0] + R[1, 1] - R[2, 2])) / 2, R[0, 2] - R[2, 0])
    z = np.copysign(np.sqrt(max(0.0, 1 - R[0, 0] - R[1, 1] + R[2, 2])) / 2, R[1, 0] - R[0, 1])
    return np.array([w, x, y, z])


def qvec_to_rot(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def refine(work: Path, force: bool = False) -> Path:
    cap = load_capture(work / "capture"); col = work / "colmap"; ns = work / "ns"
    if (ns / "transforms.json").exists() and not force:
        return ns
    shutil.rmtree(col, ignore_errors=True); (col / "seed").mkdir(parents=True)
    img_dir = cap.root / "images"; db = col / "database.db"; f0 = cap.frames[0]; log = col / "colmap.log"
    run(["colmap", "feature_extractor", "--database_path", db, "--image_path", img_dir, "--ImageReader.camera_model", "PINHOLE",
         "--ImageReader.single_camera", "1", "--ImageReader.camera_params", f"{f0.fx},{f0.fy},{f0.cx},{f0.cy}",
         "--SiftExtraction.max_num_features", "8192"], log)
    matcher = "exhaustive_matcher" if len(cap.frames) <= 400 else "sequential_matcher"
    run(["colmap", matcher, "--database_path", db] + (["--SequentialMatching.overlap", "20"] if matcher == "sequential_matcher" else []), log)
    # TODO: sequential + vocab-tree loop detection for whole-house captures (download vocab_tree_flickr100K_words256K.bin)

    ids = dict(sqlite3.connect(db).execute("SELECT name, image_id FROM images").fetchall())
    (col / "seed" / "cameras.txt").write_text(f"1 PINHOLE {f0.w} {f0.h} {f0.fx} {f0.fy} {f0.cx} {f0.cy}\n")
    lines = []
    for f in cap.frames:
        name = Path(f.file).name
        if name not in ids: continue
        w2c = np.linalg.inv(f.c2w_gl @ GL_TO_CV)                  # COLMAP wants world-to-camera, OpenCV axes
        q, t = rot_to_qvec(w2c[:3, :3]), w2c[:3, 3]
        lines.append(f"{ids[name]} {' '.join(map(str, q))} {' '.join(map(str, t))} 1 {name}\n\n")
    (col / "seed" / "images.txt").write_text("".join(lines)); (col / "seed" / "points3D.txt").write_text("")
    (col / "tri").mkdir(); (col / "refined").mkdir(); (col / "txt").mkdir()
    run(["colmap", "point_triangulator", "--database_path", db, "--image_path", img_dir, "--input_path", col / "seed", "--output_path", col / "tri"], log)
    run(["colmap", "bundle_adjuster", "--input_path", col / "tri", "--output_path", col / "refined",
         "--BundleAdjustment.refine_focal_length", "1", "--BundleAdjustment.refine_principal_point", "1",
         "--BundleAdjustment.refine_extra_params", "0"], log)
    run(["colmap", "model_converter", "--input_path", col / "refined", "--output_path", col / "txt", "--output_type", "TXT"], log)

    # read refined poses back
    cam = (col / "txt" / "cameras.txt").read_text().split("\n")
    p = [l for l in cam if l and not l.startswith("#")][0].split()
    fx, fy, cx, cy = map(float, p[4:8])
    refined = {}
    rows = [l for l in (col / "txt" / "images.txt").read_text().split("\n") if l and not l.startswith("#")]
    for l in rows[::2]:
        s = l.split(); q = np.array(list(map(float, s[1:5]))); t = np.array(list(map(float, s[5:8])))
        w2c = np.eye(4); w2c[:3, :3] = qvec_to_rot(q); w2c[:3, 3] = t
        refined[s[9]] = np.linalg.inv(w2c) @ GL_TO_CV                # back to c2w OpenGL
    names = [Path(f.file).name for f in cap.frames if Path(f.file).name in refined]
    src = np.array([refined[n][:3, 3] for n in names]); dst = np.array([f.c2w_gl[:3, 3] for f in cap.frames if Path(f.file).name in refined])
    s, R, t = umeyama(src, dst)                                       # keep headset metric frame
    S = np.eye(4); S[:3, :3] = s * R; S[:3, 3] = t
    corr = []
    ns.mkdir(exist_ok=True); frames = []
    for f in cap.frames:
        n = Path(f.file).name
        m = f.c2w_gl
        if n in refined:
            m = S @ refined[n]; m[:3, :3] /= s                        # rotation stays orthonormal
            corr.append(float(np.linalg.norm(m[:3, 3] - f.c2w_gl[:3, 3])))
        frames.append({"file_path": "images/" + n, "transform_matrix": m.tolist()})
    if (ns / "images").exists(): shutil.rmtree(ns / "images")
    shutil.copytree(img_dir, ns / "images")
    if cap.points_ply: shutil.copy(cap.points_ply, ns / "points3D.ply")
    (ns / "transforms.json").write_text(json.dumps({"camera_model": "OPENCV", "fl_x": fx, "fl_y": fy, "cx": cx, "cy": cy, "w": f0.w, "h": f0.h,
                                                     "k1": 0, "k2": 0, "p1": 0, "p2": 0, "ply_file_path": "points3D.ply", "frames": frames}, indent=1))
    reg = len(refined) / len(cap.frames); med = float(np.median(corr)) if corr else 1e9
    # TODO: parse mean reprojection error from colmap.log (bundle_adjuster "Final cost") and gate on < 1.5 px
    report(work, "refine", reg >= .9 and med < .05, registered=round(reg, 3), median_correction_m=round(med, 4), fx=fx, fy=fy, cx=cx, cy=cy, scale=round(s, 4))
    return ns


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("work", type=Path); a.add_argument("--force", action="store_true")
    o = a.parse_args(); refine(o.work, o.force)
