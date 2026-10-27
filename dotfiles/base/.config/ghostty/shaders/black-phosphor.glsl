// Neutral black-phosphor CRT for Ghostty.
// Inspired by https://gist.github.com/dharmapurikar/1289cdbcafd5aacc9f28d136ec906097
// One static pass: five texture samples; no loops, trigonometry, or time.
// Tuned for a visible CRT effect on a Retina Mac display.
const float GLOW_RADIUS_PX = 3.0;
const float GLOW_STRENGTH = 1.0;
const float RGB_FRINGE = 0.12;
const float SCANLINE_PERIOD_PX = 6.0;
const float SCANLINE_DARK = 0.20;
const float VIGNETTE_DARK = 0.24;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 delta = vec2(GLOW_RADIUS_PX) / iResolution.xy;

    vec4 center = texture(iChannel0, uv);
    vec3 left  = texture(iChannel0, uv - vec2(delta.x, 0.0)).rgb;
    vec3 right = texture(iChannel0, uv + vec2(delta.x, 0.0)).rgb;
    vec3 above = texture(iChannel0, uv - vec2(0.0, delta.y)).rgb;
    vec3 below = texture(iChannel0, uv + vec2(0.0, delta.y)).rgb;

    // Reuse the horizontal bloom taps for faint red/blue edge separation.
    vec3 color = mix(center.rgb, vec3(left.r, center.g, right.b), RGB_FRINGE);

    // Four-direction edge bleed. Keeping only the positive difference
    // preserves crisp glyph cores and avoids raising flat backgrounds.
    vec3 neighbor = (left + right + above + below) * 0.25;
    color += GLOW_STRENGTH * max(neighbor - center.rgb, vec3(0.0));

    // Static, branch-free triangle wave instead of animated or sine scanlines.
    float phase = fract(fragCoord.y / SCANLINE_PERIOD_PX);
    float scanline = 1.0 - abs(2.0 * phase - 1.0);
    vec2 corner = uv - 0.5;
    color *= (1.0 - SCANLINE_DARK * scanline) *
        (1.0 - VIGNETTE_DARK * dot(corner, corner));

    fragColor = vec4(color, center.a);
}
