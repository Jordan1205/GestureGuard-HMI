# Optional printed camera support

The software needs only an existing webcam. `webcam_wedge.scad` is an optional parameterized OpenSCAD support to make camera placement repeatable. Set `tilt_deg`, width/depth, and front height; render and export STL in OpenSCAD. Different parameter settings yield reproducible angles; this simple version adjusts by reprinting or swapping the wedge rather than a mechanical hinge.

Use the webcam's own clip and a non-slip surface. Confirm the clip fits before printing. A short test segment is preferable to wasting a full print. The design has cable-tie slots and an embossed angle label. It has no calibrated distance sensor. Mark camera/base position and operator standing position with removable tape; record actual distances only if measured separately.

The CAD source is provided as an unvalidated prototype. It has not been printed or load-tested in this environment, and no STL is claimed as verified. Use the school's existing printer and filament if available; no added electronics are required. Optional screws, straps, or filament costs depend on local stock and have not been priced. An ESP32 low-voltage LED is future work and is not included. Do not connect the app to industrial machinery.
