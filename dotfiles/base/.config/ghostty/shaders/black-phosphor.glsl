// Black Phosphor — a static CRT with visible but disciplined phosphor character.
// Five texture samples in one pass; no loops, noise, or animation.
// Positive-only halo keeps the original glyph cores crisp.
const float CURVATURE = 0.004;
const float GLOW_RADIUS_PX = 2.25;
const float GLOW_STRENGTH = 0.75;
const float RGB_FRINGE = 0.055;
const float SCANLINE_PERIOD_PX = 6.0;
const float SCANLINE_DARK = 0.13;
const float APERTURE_DARK = 0.033;
const float VIGNETTE_DARK = 0.13;
const float RIM_DARK = 0.03;

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

    // Mild RGB separation reuses existing glow taps.
    vec3 color = mix(center.rgb, vec3(left.r, center.g, right.b), RGB_FRINGE);

    // Four-direction bloom brightens only neighboring glyph edges,
    // leaving the glyph center and black background unblurred.
    vec3 halo = 0.25 * (left + right + above + below);
    color += GLOW_STRENGTH * max(halo - center.rgb, vec3(0.0));

    // Static scanlines and subtle aperture grille keep the CRT texture.
    float scan = 1.0 - abs(2.0 * fract(fragCoord.y / SCANLINE_PERIOD_PX) - 1.0);
    float slot = fract(fragCoord.x * (1.0 / 3.0));
    float afterRed = step(1.0 / 3.0, slot);
    float beforeBlue = 1.0 - step(2.0 / 3.0, slot);
    vec3 grilleLoss = vec3(afterRed, 2.0 - afterRed - beforeBlue, beforeBlue);
    color *= 1.0 - APERTURE_DARK * grilleLoss;
    color *= 1.0 - SCANLINE_DARK * scan;

    // A hint of darkened glass at the corners, without a thick bezel.
    float rim = smoothstep(0.45, 0.5, max(abs(p.x), abs(p.y)));
    color *= 1.0 - VIGNETTE_DARK * dot(p, p) - RIM_DARK * rim;
    fragColor = vec4(color, center.a);
}
