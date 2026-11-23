# Quest home scan → photorealistic Gaussian Splat

Design for turning a walk-through on a Quest 3/3S into a photorealistic, walkable Gaussian Splat (3DGS) of the home.

**Assumed stack**
- **Capture:** this repo's WebXR app (three.js, Quest Browser), which works today. An optional Unity/OpenXR capture app (`unity/QuestCapture`) is planned for raw camera access with real intrinsics.
- **Processing:** Python 3.10+ on a PC with an NVIDIA GPU (≥ 8 GB VRAM, CUDA 11.8/12.x), COLMAP 3.9+, and nerfstudio ≥ 1.1 (splatfacto) or Brush.
- **Viewer:** the WebXR viewer in this repo, which loads the trained splat.

**Unknowns.** Items marked ⚠ are unverified assumptions that the 2-day de-risk below has to settle.

---

## 1. MVP spec

| | MVP (must) | Later |
|---|---|---|
| Capture | Walk one or more rooms in passthrough. Record sharp RGB keyframes, headset poses, depth-fused 2 cm coloured points and normals. | Unity capture with Passthrough Camera API intrinsics and extrinsics, locked exposure, 30 fps video |
| Live quality | Live map that erases anything that moved (people, your body, moved chairs). Coverage guidance. Blur rejection. | Per-room coverage targets, re-shoot prompts on the photo gaps that training reports |
| Export | `house-scanner-capture/2` zip (see §3), Nerfstudio-compatible | Direct upload to the PC over the LAN |
| Processing | One command: ingest → COLMAP pose refinement seeded by headset poses → splatfacto → `.ply` (+ `.spz`) | Depth-supervised training, exposure compensation, sky/window masking |
| Viewer | WebXR: load `.ply`/`.spz` and walk through at 1:1 scale, aligned to the original floor | Anchored to the live room so the splat overlays the real one |
| Quality bar | Held-out PSNR ≥ 24 dB, no visible floaters at 1 m in the main room, 72 fps on Quest 3 with ≤ 1.5 M splats | ≥ 27 dB, whole-house ≤ 3 M splats streamed by room |

## 2. System architecture

```
Quest (WebXR app, index.html)                                   PC (tools/splat)
┌──────────────────────────────────────────────┐               ┌───────────────────────────────────────────────┐
│ XR frame loop (main thread, ≤3 ms budget)     │               │ run.py  ── orchestrates, resumable stages      │
│  ├ pose: XRViewerPose (unbounded/local-floor) │               │  1 ingest.py   validate zip, convert frames     │
│  ├ depth: GPU depth texture → async PBO read  │               │  2 refine_poses.py  COLMAP: features+matches,   │
│  ├ calib: depth format/orientation self-check │               │      triangulate with headset poses fixed,      │
│  ├ camera: getUserMedia RGB (+auto alignment) │  capture zip  │      bundle-adjust, reject outlier frames       │
│  └ keyframes: sharpness-gated JPEG + pose ────┼──────────────▶│  3 train.py    splatfacto (camera-opt on)       │
│ Worker: depth→voxels, ray free-space erasing, │  (USB/LAN/    │  4 export.py   ply → crop/align → spz           │
│   camera alignment search                     │   download)   │  5 evaluate.py PSNR/SSIM on held-out frames,    │
│ Map: 2 cm voxels (pos, normal, colour, count) │               │      floater count, pass/fail report            │
│   + flat 12 cm textured tiles                 │               └───────────────────────┬───────────────────────┘
│ IndexedDB: scans + keyframes                  │                                       │ scene.spz / scene.ply
└──────────────────────────────────────────────┘                                       ▼
                                                               viewer/splat-viewer.html (WebXR, Quest): walk through
```

The design rests on three ideas:

1. **Headset poses seed SfM.** COLMAP only refines the headset poses rather than solving from scratch. That makes it fast and robust in texture-poor rooms, and the result stays in metric, gravity-aligned, floor-at-0 coordinates.
2. **The live map is a quality gate.** The fused voxel map gives coverage, a dense point initialisation (`points3D.ply`) and later depth supervision.
3. **Splat quality comes from image quality.** Sharp, evenly exposed and well-distributed keyframes do more than any training trick, so capture enforces them.

## 3. Data contract and folder layout

```
<scan>-photos.zip                        # house-scanner-capture/2 (written by the app today)
├── manifest.json        format, app, created, frame convention, intrinsics source, known_gaps[]
├── transforms.json      Nerfstudio: camera_model OPENCV, global + per-frame fl_x fl_y cx cy w h, transform_matrix (c2w, OpenGL)
├── poses.jsonl          one line per frame: i, t(ms epoch), file, head[16], cam[16] (column-major), sharp, hfov_deg, cx, cy
├── points3D.ply         binary: x y z (float, metres) red green blue (uchar) — confirmed voxels only
└── images/frame_00001.jpg …   JPEG q.88, ≤1280 px wide

work/<scan>/                             # created by tools/splat/run.py
├── capture/            unzipped, validated copy
├── colmap/             database.db, sparse/0 (seeded), sparse/refined, report.json
├── ns/                 nerfstudio dataset (refined transforms.json + images + points3D.ply)
├── train/              nerfstudio outputs (config.yml, checkpoints)
├── export/             scene.ply, scene.spz, scene.meta.json (floor y, bounds, splat count)
└── report.json         every stage's metrics and pass/fail
```

**Conventions**
- World frame: metres, +y up, floor ≈ 0 when `local-floor` was used. With `unbounded`, y=0 is the session origin ⚠.
- Cameras use OpenGL conventions (−z forward, +y up), camera-to-world.
- COLMAP is OpenCV (+z forward, −y up), so the conversion is `c2w_cv = c2w_gl · diag(1,−1,−1,1)`.
- Matrices are written column-major in `poses.jsonl` (WebXR order) and row-major in `transforms.json` (Nerfstudio order).

## 4. Module interfaces

| Module | Input | Output | Contract |
|---|---|---|---|
| Capture (`index.html` keyframes / `unity/.../CaptureController.cs`) | XR frame, RGB frame, viewer pose | keyframe {jpeg, c2w, intrinsics, t, sharpness} | Never blocks the frame loop for more than 3 ms. Rejects blurred frames (Laplacian variance < 0.45 × running best). Rejects frames with < 0.22 m or < 12° change since the last keyframe. |
| Pose logging (`poses.jsonl` / `PoseLogger.cs`) | viewer pose + tracking state | jsonl line | Head pose and camera pose both stored, so the camera extrinsic can be re-solved offline. |
| Export (`exportPhotos()` / `CaptureWriter.cs`) | scan id | zip §3 | Deterministic file names. manifest lists every known gap. |
| Processing (`tools/splat/*.py`) | zip | `export/scene.{ply,spz}`, `report.json` | Each stage is idempotent and skipped if its output exists (`--force` to redo). Non-zero exit on FAIL. |
| Viewer (`viewer/splat-viewer.html`) | `.ply/.spz` URL + `scene.meta.json` | WebXR session | Floor aligned. ≥ 72 fps target. Falls back to a 2D orbit view. |

Code skeletons: `tools/splat/*.py`, `unity/QuestCapture/*.cs`, `viewer/splat-viewer.html`. All have TODOs.

## 5. Failure modes

**Tracking**
- **Drift over a whole house.** Poses slide 5–20 cm between distant rooms ⚠, which causes double walls in the splat.
  - Fix: COLMAP bundle adjustment with loop closures from exhaustive matching per room plus sequential matching across rooms.
  - Fix: split the scene per room if the BA residual is above 2 px.
- **Tracking loss and relocalisation jumps.** Fix: detect jumps over 10 cm in one frame in `poses.jsonl`, then split the capture into segments that COLMAP registers separately.
- **Head pose is not the camera pose.** The RGB camera sits about 3–5 cm off the head centre ⚠. Fix: refine the per-capture extrinsic in BA, or read it from the Passthrough Camera API in Unity.

**Lighting and exposure**
- **Auto-exposure flicker between frames.** It shows up as blotchy splats. Fix: appearance embeddings (`--pipeline.model.use-appearance-embedding True` in splatfacto-big) and exposure normalisation in ingest.
- **Windows over- or under-exposed.** Fix: capture at mid exposure and mask clipped pixels (> 250 in all channels) from the loss (TODO).
- **Lights switched mid-scan.** Rule: one lighting state per capture.

**Reflections and specular surfaces**
- **Mirrors, glass and glossy floors.** These create a "room behind the mirror" in both depth and the splat.
  - Detect: depth hits behind a known wall plane, or colour inconsistency across views.
  - Mask: Meta's semantic labels (window/screen) where they exist, otherwise a user-painted mask.
  - Live map: the free-space erasing keeps it from fusing.
- **TV and monitor screens.** They change content. Fix: mask any `screen` label.

**Raw camera access**
- **WebXR has no raw camera access.** It only gets `getUserMedia` frames of unknown intrinsics, latency and crop ⚠.
  - Mitigation today: auto-alignment searches FOV and principal point by multi-view colour consistency, then COLMAP refines intrinsics (`--ImageReader.single_camera 1`, refine focal and principal point).
- **Unity Passthrough Camera API.** It needs Horizon OS v74+, the `horizonos.permission.HEADSET_CAMERA` permission, and runs at 1280×960 and ~30 fps ⚠.
- **Timestamp skew.** The video frame and the pose are sampled at different times. Fix: only take keyframes while the head is steady (implemented). In Unity, use the camera timestamp to interpolate the pose.

**Processing**
- **COLMAP fails in texture-poor rooms (white walls).** Fix: keep the headset poses fixed for frames that won't register. The seeded triangulation still works.
- **Floaters near the camera path.** Fix: initialise from dense `points3D.ply` (not random), raise the opacity cull, and use depth supervision later.

## 6. Two-day de-risk prototype

**Day 1 – capture quality**

| # | Step | Command / action | Pass | Fail → action |
|---|---|---|---|---|
| 1 | Device check | Open the app on Quest 3, start scanning with "Real colours" ticked | HUD reaches "Scanning" in under 20 s. More shows `camera on · aligned` within 60 s | Not aligned: capture anyway and rely on COLMAP intrinsics |
| 2 | Capture one room | Walk 3 loops at 3 heights (knee, chest, overhead), 2 min, then Finish & save | ≥ 150 keyframes, ≤ 10% rejected as blurred, coverage ≥ 85% | Slow down. Raise the keyframe rate |
| 3 | Moving-object test | Stand in view, step away, re-look | Your shape disappears in under 2 s | Raise the erase strength or ray density |
| 4 | Export | Scans list → **Photos .zip** → copy to PC | `python tools/splat/ingest.py scan.zip work/room1` exits 0 | Fix the contract mismatch named in the error |
| 5 | Pose sanity | `python tools/splat/refine_poses.py work/room1` | Registered ≥ 90% of images, mean reprojection < 1.5 px, median pose correction < 5 cm | > 5 cm means a head/camera offset problem: enable extrinsic refinement |

**Day 2 – splat quality and the viewer**

| # | Step | Command / action | Pass | Fail → action |
|---|---|---|---|---|
| 6 | Train | `python tools/splat/train.py work/room1 --iters 30000` (≈ 25 min on an RTX 3080) | Held-out PSNR ≥ 24 dB, SSIM ≥ 0.80 (`evaluate.py`) | Below 22 dB: check intrinsics (step 5) and exposure flicker |
| 7 | Export | `python tools/splat/export.py work/room1 --max-splats 1500000` | `scene.ply` ≤ 350 MB, `scene.spz` ≤ 60 MB | Raise the opacity cull, or crop to the room bounds |
| 8 | View | `python -m http.server 8080 -d work/room1/export` and `viewer/splat-viewer.html?src=http://<pc-ip>:8080/scene.ply` in Quest Browser | ≥ 72 fps, floor level, scale 1:1 (a door looks 2 m tall) | Below 72 fps: lower `--max-splats` to 1 M |
| 9 | All-in-one | `python tools/splat/run.py scan.zip` | `work/<scan>/report.json` says `"pass": true` | Read the failing stage in the report |

Setup (once, on the PC):
```
conda create -n splat python=3.10 -y && conda activate splat
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu118
pip install nerfstudio==1.1.5 pycolmap==0.6.1 numpy pillow plyfile
# COLMAP 3.9 binary on PATH (apt install colmap  /  Windows release zip)
```

## 7. Prioritised risks

| # | Risk | Likelihood | Impact | Mitigation | Owner stage |
|---|---|---|---|---|---|
| 1 | Unknown camera intrinsics and extrinsic in WebXR | High | High (blurry, ghosted splat) | Auto-alignment on device, COLMAP intrinsic refinement, Unity PCA path | Capture / refine |
| 2 | Motion blur and rolling shutter in keyframes | High | High | Sharpness gate (done), steady-head gating (done), slow-walk guidance | Capture |
| 3 | Auto-exposure flicker | High | Medium | Appearance embeddings, exposure normalisation | Train |
| 4 | Pose drift across rooms | Medium | High | Seeded BA with loop closure, per-room split | Refine |
| 5 | Mirrors, glass, screens | Medium | Medium | Label masks, colour-consistency masks, live erasing | Ingest / train |
| 6 | Splat too heavy for Quest | Medium | High | Opacity/scale pruning, `.spz`, per-room streaming | Export / viewer |
| 7 | Quest browser memory or tab kill during long scans | Medium | Medium | Auto-save on exit (done), per-room save | Capture |
| 8 | COLMAP fails on white walls | Medium | Low (headset poses fall back) | Fixed-pose triangulation | Refine |
| 9 | Unity PCA availability or permission changes | Low | Medium | WebXR path stays primary | Capture |
