// Black Phosphor — static curved-glass CRT, with sharp glyph cores.
// One pass, five texture samples, no time uniform or animated redraw.
// Curvature, scanlines, phosphor mask, and glow are tuned for Retina displays.
const float CURVATURE = 0.048;
const float GLOW_RADIUS_PX = 2.35;
const float GLOW_STRENGTH = 0.82;
const float RGB_FRINGE = 0.105;
const float SCANLINE_PERIOD_PX = 6.0;
const float SCANLINE_DARK = 0.18;
const float APERTURE_DARK = 0.06;
const float VIGNETTE_DARK = 0.165;
const float RIM_DARK = 0.05;
const float GLASS_EDGE_WIDTH = 0.006;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv - 0.5;
    vec2 warped = uv + CURVATURE * p * dot(p, p);
    vec2 dx = vec2(GLOW_RADIUS_PX / iResolution.x, 0.0);
    vec2 dy = vec2(0.0, GLOW_RADIUS_PX / iResolution.y);

    vec4 center = texture(iChannel0, warped);
    vec3 left = texture(iChannel0, warped - dx).rgb;
    vec3 right = texture(iChannel0, warped + dx).rgb;
    vec3 above = texture(iChannel0, warped - dy).rgb;
    vec3 below = texture(iChannel0, warped + dy).rgb;

    // Additive edge-only RGB separation: no softening of glyph cores.
    vec3 fringe = vec3(max(left.r - center.r, 0.0),
                       0.0,
                       max(right.b - center.b, 0.0));
    vec3 color = center.rgb + RGB_FRINGE * fringe;

    // Four-direction phosphor bloom, limited to outward-facing glyph edges.
    vec3 halo = 0.25 * (left + right + above + below);
    color += GLOW_STRENGTH * max(halo - center.rgb, vec3(0.0));

    // Scanlines track the bent glass instead of remaining ruler-straight.
    float scan = 1.0 - abs(2.0 * fract(
        warped.y * iResolution.y / SCANLINE_PERIOD_PX) - 1.0);
    float slot = fract(fragCoord.x * (1.0 / 3.0));
    float afterRed = step(1.0 / 3.0, slot);
    float beforeBlue = 1.0 - step(2.0 / 3.0, slot);
    vec3 grilleLoss = vec3(afterRed, 2.0 - afterRed - beforeBlue, beforeBlue);
    color *= (1.0 - APERTURE_DARK * grilleLoss) * (1.0 - SCANLINE_DARK * scan);

    // Soft black glass edge follows the warp; outside pixels fade to black.
    float edge = min(min(warped.x, 1.0 - warped.x),
                     min(warped.y, 1.0 - warped.y));
    float glass = smoothstep(0.0, GLASS_EDGE_WIDTH, edge);
    float rim = smoothstep(0.44, 0.5, max(abs(p.x), abs(p.y)));
    color *= (1.0 - VIGNETTE_DARK * dot(p, p) - RIM_DARK * rim) * glass;

    fragColor = vec4(color, center.a);
}
