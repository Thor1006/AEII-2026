# RF Drive: separate car-style radar demo

Open http://127.0.0.1:8766/drive/ using the existing local server. The original Room map remains at `/`. Both use one real COM5/COM6 collector and the existing approved 40-Hz profile. There is no second serial reader, firmware change, new dependency or external data transfer.

The custom illustrative vehicle marks the sensor origin at its front center. Its dimensions are symbolic. The reference plane is at sensor height, not a detected road or floor. Boxes group nearby returns for display (0.28-m centroid association, at most 64 groups); they do not classify cars, people or physical object sizes. The raw-return overlay shows individual measured x/y/z points. Gray arcs mean no return in that displayed angular sector, not confirmed clear space. Nearest-return and sector distances use measured 3D coordinates; grouping/clipping does not improve physical precision.

3D/Top, display range and raw overlay are local view controls. Start/Stop affects the one shared radar for every viewer. Closing this new page does not explicitly stop other views; existing global client-loss/session/thermal/timing stops remain. The original Room map retains its existing stop-on-close/reload behavior, so closing/reloading it can stop this shared stream; the Drive page truthfully shows that stop and provides Start. Adding `/drive/` requires one service restart, and the RAM Room map clears on its ordinary new-session reset.

Only actual frame history is buffered (at most 24 display frames); frames over 250 ms old are discarded. There is no interpolated position/synthetic traffic fallback. Source, displayed unique-frame rate, loss counters and data age remain distinct. Stale/stopped data is dimmed and labeled. Sparse detections remain sparse.

The original Room map's Close viewer button ends the shared local service for both pages. The Drive page has no service-shutdown button. A stopped acquisition can be resumed with Start while the service runs; a shut-down service must first be launched again using the established local server command.

Run `node test_geometry.js` with the existing runtime for geometry, groups/colors, cursor/session/queue and stale-state checks. Fixtures are offline-only. Source poster/proposal, existing Room map HTML and main project frontend/Pi packages are untouched. No commit/push.
