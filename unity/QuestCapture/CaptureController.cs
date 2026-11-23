// Orchestrates a capture: gates keyframes on motion + sharpness, hands them to the writer. Mirrors index.html maybeKeyframe().
using System.Collections;
using UnityEngine;

namespace HouseScanner
{
    public sealed class CaptureController : MonoBehaviour
    {
        [SerializeField] PassthroughFrameSource frames;
        [SerializeField] PoseLogger poses;
        [SerializeField] CaptureWriter writer;
        [SerializeField] float minMove = 0.22f, minTurnDeg = 12f, maxSpinDegPerSec = 70f, sharpKeep = 0.45f;

        Vector3 lastPos; Quaternion lastRot; bool hasLast; float bestSharp; int index;
        public int Kept => index; public int Blurred { get; private set; }

        IEnumerator Start()
        {
            yield return frames.Init();                      // permission + camera start; TODO: show a panel if denied
            writer.Begin(frames.Intrinsics);
        }

        void Update()
        {
            if (!frames.HasNewFrame || !writer.IsOpen) return;
            var cam = frames.LatestCameraPose;                // ⚠ camera pose in world at frame timestamp (PCA helper), not head pose
            var head = poses.HeadPoseAt(frames.LatestTimestamp);
            if (poses.AngularSpeedDeg > maxSpinDegPerSec) return;                 // blurred by rotation
            if (hasLast && Vector3.Distance(cam.position, lastPos) < minMove && Quaternion.Angle(cam.rotation, lastRot) < minTurnDeg) return;

            float sharp = frames.LaplacianVariance();          // TODO: compute on a 160x120 GPU downsample (compute shader) to stay < 1 ms
            bestSharp = Mathf.Max(bestSharp * 0.995f, sharp);
            if (sharp < bestSharp * sharpKeep) { Blurred++; return; }

            writer.AddFrame(index++, frames.EncodeJpeg(88), cam, head, frames.Intrinsics, frames.LatestTimestamp, sharp);
            lastPos = cam.position; lastRot = cam.rotation; hasLast = true;
        }

        public void Finish() => StartCoroutine(writer.Finish());   // TODO: also export fused points3D.ply from a depth-fusion component
    }
}
