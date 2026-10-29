// Black Phosphor — static curved-glass CRT, with sharp glyph cores.
// One pass, six texture samples; no loops, noise, or trigonometry.
// Only non-default background cells receive the moving phosphor wave.
// Ghostty redraws the focused terminal continuously to animate the wave.
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

const float PULSE_PERIOD_S = 3.8;
const float PHASE_PER_CELL = 0.075;
const float ROW_PHASE = 0.085;
const float PULSE_STRENGTH = 0.18;
const float BG_MIN = 0.045;
const float BG_FULL = 0.105;
const float SEL_MIN = 0.025;
const float SEL_FULL = 0.075;

float maxChannelDelta(vec3 a, vec3 b) {
    vec3 d = abs(a - b);
    return max(d.r, max(d.g, d.b));
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

    // Detect ANSI background-highlighted cells from their rendered fill.
    // SGR attributes aren't available to a postprocess shader; this is a
    // color-based approximation, not an exact reverse-video flag.
    // Cursor metrics give the true character grid without font-size guesses.
    if (iCurrentCursor.z >= 6.0 && iCurrentCursor.w >= 12.0) {
        vec2 cellSize = iCurrentCursor.zw;
        vec2 pixel = warped * iResolution.xy;
        // Modulo origin stays fixed when the cursor advances by whole cells.
        vec2 origin = mod(iCurrentCursor.xy, cellSize);
        vec2 cell = floor(vec2((pixel.x - origin.x) / cellSize.x,
                               (origin.y - pixel.y) / cellSize.y));

        // A glyph usually leaves the upper-left interior corner empty.
        // Sample the *input* terminal, before CRT masking and vignetting.
        vec2 corner = vec2(origin.x + (cell.x + 0.12) * cellSize.x,
                           origin.y - (cell.y + 0.12) * cellSize.y);
        if (all(greaterThan(corner, vec2(1.0))) &&
            all(lessThan(corner, iResolution.xy - vec2(1.0)))) {
            vec3 cellBg = texture(iChannel0, corner / iResolution.xy).rgb;
            float changedBg = maxChannelDelta(cellBg, iBackgroundColor);
            float selectionBg = maxChannelDelta(cellBg, iSelectionBackgroundColor);

            // SGR 7, 40-47/100-107, 48;5 and 48;2 all produce a
            // non-default fill. Do not animate mouse selections.
            float active = smoothstep(BG_MIN, BG_FULL, changedBg) *
                           smoothstep(SEL_MIN, SEL_FULL, selectionBg);
            vec2 cellTopLeft = vec2(origin.x + cell.x * cellSize.x,
                                     origin.y - cell.y * cellSize.y);
            if (iCursorVisible != 0 &&
                all(lessThan(abs(cellTopLeft - iCurrentCursor.xy), vec2(0.5)))) {
                active = 0.0;
            }

            // Skip pulse math for the vast majority of ordinary cells.
            // One extra cached sample, still a single postprocess pass.
            if (active > 0.01) {
                float ink = smoothstep(0.08, 0.24,
                    maxChannelDelta(center.rgb, cellBg));
                float phase = fract(iTime / PULSE_PERIOD_S -
                                    cell.x * PHASE_PER_CELL +
                                    cell.y * ROW_PHASE);
                float triangle = 1.0 - abs(2.0 * phase - 1.0);
                float wave = smoothstep(0.20, 0.92, triangle);

                // Contrast-preserving phosphor pulse: bright glyphs get
                // brighter and inverse-video dark glyphs get darker.
                // The neighboring phosphor halo breathes with the glyph.
                vec3 inkSignal = (center.rgb - cellBg) +
                                 0.45 * max(halo - center.rgb, vec3(0.0));
                color = clamp(color +
                    (PULSE_STRENGTH * active * ink * wave) * inkSignal,
                    vec3(0.0), vec3(1.0));
            }
        }
    }

    fragColor = vec4(color, center.a);
}
