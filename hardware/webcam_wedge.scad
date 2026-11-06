// GestureGuard optional parametric camera support. Units: millimeters.
// Open in OpenSCAD, choose tilt_deg, render (F6), export STL.
// A prototype, not a universal webcam adapter. Secure the camera's own clip.
tilt_deg = 12;       // Reproducible camera platform angle: 0..25 recommended.
base_width = 90;
base_depth = 85;
platform_depth = 58;
plate = 4;
front_height = 18;
rail_width = 7;
clip_lip = 3;
$fn = 48;

rear_height = front_height + platform_depth * tan(tilt_deg);
assert(tilt_deg >= 0 && tilt_deg <= 25, "Choose 0..25 degrees.");

module support_rail(x) {
    translate([x, 8, plate])
        rotate([90, 0, 90])
            linear_extrude(height = rail_width)
                polygon([[0, 0], [platform_depth, 0],
                         [platform_depth, rear_height], [0, front_height]]);
}

union() {
    difference() {
        cube([base_width, base_depth, plate]);
        // Cable-tie slots; do not assume these are threaded tripod mounts.
        for (x = [12, base_width - 16])
            translate([x, base_depth - 12, -1]) cube([4, 8, plate + 2]);
    }
    support_rail(8);
    support_rail(base_width - 8 - rail_width);
    translate([0, 8, plate + front_height])
        rotate([tilt_deg, 0, 0]) {
            cube([base_width, platform_depth / cos(tilt_deg), plate]);
            translate([0, 0, plate]) cube([base_width, clip_lip, clip_lip]);
        }
    // Human-readable reproducibility label, embossed on the front.
    translate([base_width / 2, 1, plate])
        linear_extrude(height = .6)
            text(str("GG  ", tilt_deg, " deg"), size = 5, halign = "center");
}
