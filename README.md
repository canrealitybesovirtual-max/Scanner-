# House Scanner

WebXR + three.js scanner for Meta Quest 3 / 3S. Walk your house in passthrough: the headset's depth sensor is back-projected into a 2 cm voxel point map and combined with the Space Setup planes and room mesh. Scans save on the headset (IndexedDB) with a persistent anchor, so you can continue later and they line up. Export as `.json` (everything) or `.ply` (points).

Deployed as a Render static site (`render.yaml`). Open the site URL in the Quest browser and press **Start scanning**.

## Techniques

- Depth fusion weighted by distance and viewing angle (squared), 15-frame sensor warm-up skipped, your body and controllers excluded, free-space carving removes ghosts — ideas from [QuestRoomScan](https://github.com/genesisinteractive/QuestRoomScan) (MIT).
- Space Setup planes, room mesh and labelled furniture volumes, persistent anchors — WebXR scene APIs as used by Meta's [Reality Accelerator Toolkit](https://github.com/meta-quest/reality-accelerator-toolkit) (MIT).
- Passthrough camera colour through the browser (Horizon OS v74+), pinhole with an assumed horizontal FOV (`?hfov=80`, `?cy=0` to tune).
- Exports: `.json` (everything), `.ply` (coloured points), `.glb` (points + Quest room meshes, understanding in scene extras).
