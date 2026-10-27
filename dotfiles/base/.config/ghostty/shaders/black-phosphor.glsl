// Black Phosphor — crisp, static CRT.
// Three texture samples per pixel, one pass, no animation or curvature.
// A narrow horizontal halo simulates phosphor bleed without softening glyph
// cores or vertically smearing the font. No motion, loops, or trigonometry.
const float GLOW_RADIUS_PX = 1.5;
const float GLOW_STRENGTH = 0.48;
const float SCANLINE_PERIOD_PX = 6.0;
const float SCANLINE_DARK = 0.12;
const float APERTURE_DARK = 0.03;
const float VIGNETTE_DARK = 0.12;
const float RIM_DARK = 0.025;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 offset = vec2(GLOW_RADIUS_PX / iResolution.x, 0.0);

    vec4 center = texture(iChannel0, uv);
    vec3 left = texture(iChannel0, uv - offset).rgb;
    vec3 right = texture(iChannel0, uv + offset).rgb;

    // Preserve sharp foreground strokes and deep black background.
    vec3 halo = 0.5 * (left + right);
    vec3 color = center.rgb +
        GLOW_STRENGTH * max(halo - center.rgb, vec3(0.0));

    // Static scanline and RGB aperture grille (no time-dependent effects).
    float scan = 1.0 - abs(2.0 * fract(fragCoord.y / SCANLINE_PERIOD_PX) - 1.0);
    float slot = fract(fragCoord.x * (1.0 / 3.0));
    float afterRed = step(1.0 / 3.0, slot);
    float beforeBlue = 1.0 - step(2.0 / 3.0, slot);
    vec3 grilleLoss = vec3(afterRed, 2.0 - afterRed - beforeBlue, beforeBlue);
    color *= 1.0 - APERTURE_DARK * grilleLoss;
    color *= 1.0 - SCANLINE_DARK * scan;

    vec2 p = uv - 0.5;
    float rim = smoothstep(0.45, 0.5, max(abs(p.x), abs(p.y)));
    color *= 1.0 - VIGNETTE_DARK * dot(p, p) - RIM_DARK * rim;
    fragColor = vec4(color, center.a);
}
