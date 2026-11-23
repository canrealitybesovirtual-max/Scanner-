# Unity capture app (optional, later)

These are C# skeletons for a native capture app. It uses Meta's Passthrough Camera API, which gives real camera intrinsics, the camera's pose, and frames up to 1280×960. It writes the same `house-scanner-capture/2` zip as the WebXR app, so `tools/splat` takes either one.

**Assumptions to verify** (marked ⚠ in the code):
- Unity 6 or 2022.3 LTS with the Meta XR Core SDK v74+.
- The `PassthroughCameraApiSamples` helper classes, which are copied from Meta's sample repo.
- The `horizonos.permission.HEADSET_CAMERA` Android permission.
