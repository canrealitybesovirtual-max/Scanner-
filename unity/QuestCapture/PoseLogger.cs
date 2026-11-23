// Ring buffer of head poses so a camera frame can be matched to the head pose at its timestamp; flags tracking jumps.
using System.Collections.Generic;
using UnityEngine;

namespace HouseScanner
{
    public sealed class PoseLogger : MonoBehaviour
    {
        [SerializeField] Transform head;                       // OVRCameraRig CenterEyeAnchor
        readonly List<(double t, Pose p)> ring = new();
        public float AngularSpeedDeg { get; private set; }
        public int TrackingJumps { get; private set; }
        Quaternion prevRot; Vector3 prevPos; bool has;

        void LateUpdate()
        {
            var t = Time.realtimeSinceStartupAsDouble; var p = new Pose(head.position, head.rotation);
            if (has)
            {
                AngularSpeedDeg = Mathf.Lerp(AngularSpeedDeg, Quaternion.Angle(prevRot, p.rotation) / Mathf.Max(1e-3f, Time.deltaTime), 0.3f);
                if (Vector3.Distance(prevPos, p.position) / Mathf.Max(1e-3f, Time.deltaTime) > 3f) TrackingJumps++;   // relocalisation
            }
            prevRot = p.rotation; prevPos = p.position; has = true;
            ring.Add((t, p)); if (ring.Count > 240) ring.RemoveAt(0);
            // TODO: read OVRManager tracking state / OVRPlugin.GetNodePositionTracked and log losses
        }

        public Pose HeadPoseAt(double t)
        {
            for (int i = ring.Count - 1; i > 0; i--)
                if (ring[i - 1].t <= t)
                {
                    var (ta, a) = ring[i - 1]; var (tb, b) = ring[i]; float k = (float)((t - ta) / System.Math.Max(1e-6, tb - ta));
                    return new Pose(Vector3.Lerp(a.position, b.position, k), Quaternion.Slerp(a.rotation, b.rotation, k));
                }
            return ring.Count > 0 ? ring[^1].p : default;
        }
    }
}
