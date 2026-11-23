// Writes house-scanner-capture/2 (manifest.json, transforms.json, poses.jsonl, images/) — same contract as the WebXR export.
using System.Collections;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace HouseScanner
{
    public sealed class CaptureWriter : MonoBehaviour
    {
        string dir; StringBuilder frames = new(), poses = new(); Intrinsics k0; int n;
        public bool IsOpen => dir != null;
        static readonly CultureInfo C = CultureInfo.InvariantCulture;

        public void Begin(Intrinsics k)
        {
            k0 = k; n = 0; frames.Clear(); poses.Clear();
            dir = Path.Combine(Application.persistentDataPath, "scan-" + System.DateTime.UtcNow.ToString("yyyyMMdd-HHmmss"));
            Directory.CreateDirectory(Path.Combine(dir, "images"));
        }

        // Unity is left-handed (+z forward); the contract is right-handed OpenGL (-z forward). Flip z on the way out.
        static float[] ToGlColumnMajor(Pose p)
        {
            var m = Matrix4x4.TRS(p.position, p.rotation, Vector3.one);
            var flip = Matrix4x4.Scale(new Vector3(1, 1, -1));
            m = flip * m * flip;                               // ⚠ verify against a tape-measured wall in the 2-day test
            var a = new float[16]; for (int c = 0; c < 4; c++) for (int r = 0; r < 4; r++) a[c * 4 + r] = m[r, c]; return a;
        }

        public void AddFrame(int i, byte[] jpg, Pose cam, Pose head, Intrinsics k, double t, float sharp)
        {
            string file = $"images/frame_{i + 1:00000}.jpg";
            File.WriteAllBytes(Path.Combine(dir, file), jpg);   // TODO: background thread queue
            var m = ToGlColumnMajor(cam);
            frames.Append(n++ > 0 ? "," : "").Append($"{{\"file_path\":\"{file}\",\"fl_x\":{k.fx.ToString(C)},\"fl_y\":{k.fy.ToString(C)},\"cx\":{k.cx.ToString(C)},\"cy\":{k.cy.ToString(C)},\"w\":{k.w},\"h\":{k.h},\"transform_matrix\":[")
                  .Append($"[{m[0].ToString(C)},{m[4].ToString(C)},{m[8].ToString(C)},{m[12].ToString(C)}],[{m[1].ToString(C)},{m[5].ToString(C)},{m[9].ToString(C)},{m[13].ToString(C)}],[{m[2].ToString(C)},{m[6].ToString(C)},{m[10].ToString(C)},{m[14].ToString(C)}],[0,0,0,1]]}}");
            poses.Append($"{{\"i\":{i},\"t\":{(t * 1000).ToString(C)},\"file\":\"{file}\",\"cam\":[{string.Join(",", System.Array.ConvertAll(m, v => v.ToString(C)))}],\"head\":[{string.Join(",", System.Array.ConvertAll(ToGlColumnMajor(head), v => v.ToString(C)))}],\"sharp\":{sharp.ToString(C)}}}\n");
        }

        public IEnumerator Finish()
        {
            File.WriteAllText(Path.Combine(dir, "transforms.json"),
                $"{{\"camera_model\":\"OPENCV\",\"fl_x\":{k0.fx.ToString(C)},\"fl_y\":{k0.fy.ToString(C)},\"cx\":{k0.cx.ToString(C)},\"cy\":{k0.cy.ToString(C)},\"w\":{k0.w},\"h\":{k0.h},\"k1\":0,\"k2\":0,\"p1\":0,\"p2\":0,\"ply_file_path\":\"points3D.ply\",\"frames\":[{frames}]}}");
            File.WriteAllText(Path.Combine(dir, "poses.jsonl"), poses.ToString());
            File.WriteAllText(Path.Combine(dir, "manifest.json"),
                "{\"format\":\"house-scanner-capture/2\",\"app\":\"house-scanner-unity\",\"intrinsics\":\"passthrough camera api\",\"known_gaps\":[\"points3D.ply not written yet\"]}");
            // TODO: fused points3D.ply (Depth API + the same voxel fusion as index.html), zip the folder, offer adb pull / LAN upload
            yield return null; dir = null;
        }
    }
}
