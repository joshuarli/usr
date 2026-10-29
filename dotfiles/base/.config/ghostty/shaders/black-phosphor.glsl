// Black Phosphor — static curved-glass CRT, with sharp glyph cores.
// One pass, seven texture samples; no loops, noise, or trigonometry.
// Color-aware highlights breathe without relying on cursor glyph dimensions.
// Ghostty redraws the focused terminal continuously for animation.
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

// A traveling band spans roughly 15-20 characters at 16 pt on Retina.
// A continuous phase, rather than an assumed character pitch, prevents
// partial-glyph artifacts when fonts, DPI, or padding change.
const float PULSE_PERIOD_S = 3.8;
const float PHASE_PER_PIXEL = 0.0029;
const float PULSE_INK = 0.28;
const float PULSE_FILL = 0.11;
const float BG_MIN = 0.065;
const float BG_FULL = 0.14;
const float SEL_MIN = 0.025;
const float SEL_FULL = 0.075;
const float PROBE_X_PX = 7.0;
const float PROBE_Y_PX = 5.0;
const float BRIGHTNESS = 1.18;

// Small channel-wise maximum distance (cheaper than length/distance).
float maxChannelDelta(vec3 a, vec3 b) {
    vec3 d = abs(a - b);
    return max(d.r, max(d.g, d.b));
}

// Ghostty exposes configured colors as normalized sRGB, while the input
// texture may be sampled in linear space. Compare in both representations.
// Squaring is a cheap approximation for dark, configured UI colors.
float themeColorDistance(vec3 sampled, vec3 reference) {
    return min(maxChannelDelta(sampled, reference),
               maxChannelDelta(sampled, reference * reference));
}

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
    color *= BRIGHTNESS;

    // The cursor uniforms encode a *glyph rectangle*, not a stable cell
    // grid. Bar/underline cursors and hidden cursors must not disable this.
    // Two opposite diagonal probes sample the unfiltered terminal image.
    // In filled ANSI highlight regions they agree on the background color;
    // on ordinary bright glyphs they typically agree on the default black.
    vec2 probe = vec2(PROBE_X_PX, PROBE_Y_PX) / iResolution.xy;
    vec3 probeA = texture(iChannel0, warped + probe).rgb;
    vec3 probeB = texture(iChannel0, warped - probe).rgb;
    vec3 fill = 0.5 * (probeA + probeB);

    float uniformity = 1.0 - smoothstep(0.07, 0.16,
                                       maxChannelDelta(probeA, probeB));
    float colored = smoothstep(BG_MIN, BG_FULL,
                              themeColorDistance(fill, iBackgroundColor));
    float notSelected = smoothstep(SEL_MIN, SEL_FULL,
                              themeColorDistance(fill, iSelectionBackgroundColor));
    float highlighted = uniformity * colored * notSelected;

    if (highlighted > 0.02) {
        // A wave travels across the highlighted region. Using pixels for
        // phase avoids incorrectly inferring character-cell dimensions
        // from the cursor style; it still passes visibly letter-by-letter.
        float phase = fract(iTime / PULSE_PERIOD_S -
                            (warped.x * iResolution.x) * PHASE_PER_PIXEL);
        float triangle = 1.0 - abs(2.0 * phase - 1.0);
        float wave = smoothstep(0.27, 0.93, triangle);
        float amount = highlighted * wave;

        // Animate the background slightly as well as the foreground.
        // That ensures even inverse-video (dark-on-light) labels visibly
        // pulse without blurring strokes or changing text geometry.
        vec3 contrast = center.rgb - fill;
        color = clamp(color + amount *
                      (PULSE_INK * contrast + PULSE_FILL * fill),
                      vec3(0.0), vec3(1.0));
    }

    fragColor = vec4(clamp(color, vec3(0.0), vec3(1.0)), center.a);
}
