// Wraps Meta's Passthrough Camera API (WebCamTexture + PassthroughCameraUtils from the PCA samples).
using System.Collections;
using UnityEngine;

namespace HouseScanner
{
    public struct Intrinsics { public float fx, fy, cx, cy; public int w, h; }

    public sealed class PassthroughFrameSource : MonoBehaviour
    {
        public Intrinsics Intrinsics { get; private set; }
        public bool HasNewFrame => tex != null && tex.didUpdateThisFrame;
        public Pose LatestCameraPose { get; private set; }
        public double LatestTimestamp { get; private set; }
        WebCamTexture tex; Texture2D readback;

        public IEnumerator Init()
        {
            // TODO ⚠: request "horizonos.permission.HEADSET_CAMERA" via UnityEngine.Android.Permission and wait for the grant
            // TODO ⚠: pick the left camera: PassthroughCameraUtils.GetCameraIdByEye(PassthroughCameraEye.Left)
            tex = new WebCamTexture(/* deviceName */ null, 1280, 960, 30);
            tex.Play();
            while (tex.width < 100) yield return null;
            // TODO ⚠: var k = PassthroughCameraUtils.GetCameraIntrinsics(PassthroughCameraEye.Left);
            //          Intrinsics = new Intrinsics { fx = k.FocalLength.x, fy = k.FocalLength.y, cx = k.PrincipalPoint.x, cy = k.PrincipalPoint.y, w = k.Resolution.x, h = k.Resolution.y };
            readback = new Texture2D(tex.width, tex.height, TextureFormat.RGB24, false);
        }

        void Update()
        {
            if (!HasNewFrame) return;
            LatestTimestamp = Time.realtimeSinceStartupAsDouble;   // TODO ⚠: use the camera's sensor timestamp if exposed, else measure latency once
            // TODO ⚠: LatestCameraPose = PassthroughCameraUtils.GetCameraPoseInWorld(PassthroughCameraEye.Left);
        }

        public byte[] EncodeJpeg(int quality)
        {
            readback.SetPixels32(tex.GetPixels32()); readback.Apply(false);   // TODO: AsyncGPUReadback to avoid a frame hitch
            return readback.EncodeToJPG(quality);                              // TODO: encode on a worker thread
        }

        public float LaplacianVariance() { /* TODO: GPU downsample + Laplacian; return variance */ return 1f; }
    }
}
