# House Scanner

WebXR + three.js scanner for Meta Quest 3 / 3S. Walk your house in passthrough: the headset's depth sensor is back-projected into a 2 cm voxel point map and combined with the Space Setup planes and room mesh. Scans save on the headset (IndexedDB) with a persistent anchor, so you can continue later and they line up. Export as `.json` (everything) or `.ply` (points).

Deployed as a Render static site (`render.yaml`). Open the site URL in the Quest browser and press **Start scanning**.
