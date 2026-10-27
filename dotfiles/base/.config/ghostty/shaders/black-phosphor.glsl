// Black Phosphor — restrained curved-glass CRT with breathing highlights.
// Based on the four-direction bloom approach in
// https://gist.github.com/dharmapurikar/1289cdbcafd5aacc9f28d136ec906097
//
// Five texture reads, one pass, no loops, no random noise, no flicker.
// The focused Ghostty window continuously redraws when shader animation is on.
// Change custom-shader-animation to false in config for battery-first use.
const float CURVATURE = 0.008;
const float GLOW_RADIUS_PX = 3.0;
const float GLOW_STRENGTH = 1.08;
const float RGB_FRINGE = 0.12;
const float BREATH_PERIOD_S = 11.0;
const float BREATH_AMPLITUDE = 0.38;
const float SCANLINE_PERIOD_PX = 6.0;
const float SCANLINE_DARK = 0.13;
const float APERTURE_DARK = 0.035;
const float VIGNETTE_DARK = 0.14;
const float RIM_DARK = 0.035;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 p = uv - 0.5;
    vec2 warped = uv + CURVATURE * p * dot(p, p);
    vec2 delta = vec2(GLOW_RADIUS_PX) / iResolution.xy;

    vec4 center = texture(iChannel0, warped);
    vec3 left   = texture(iChannel0, warped - vec2(delta.x, 0.0)).rgb;
    vec3 right  = texture(iChannel0, warped + vec2(delta.x, 0.0)).rgb;
    vec3 above  = texture(iChannel0, warped - vec2(0.0, delta.y)).rgb;
    vec3 below  = texture(iChannel0, warped + vec2(0.0, delta.y)).rgb;

    // Reuse halo samples for slight RGB separation. No extra texture reads.
    vec3 color = mix(center.rgb, vec3(left.r, center.g, right.b), RGB_FRINGE);
    vec3 neighbor = (left + right + above + below) * 0.25;

    // The theme gives normal text a lower peak channel than its bright ANSI
    // palette and bold ivory. The framebuffer has no actual bold-style flag.
    float peak = max(max(neighbor.r, neighbor.g), neighbor.b);
    float highlight = smoothstep(0.80, 0.93, peak);

    // C1-continuous 11-second wave (no per-fragment trigonometry).
    // Only halo intensity breathes; letter interiors remain steady.
    float triangle = 1.0 - abs(2.0 * fract(iTime / BREATH_PERIOD_S) - 1.0);
    float breathe = triangle * triangle * (3.0 - 2.0 * triangle);
    float glow = GLOW_STRENGTH *
        (1.0 + highlight * (0.08 + BREATH_AMPLITUDE * breathe));
    color += glow * max(neighbor - center.rgb, vec3(0.0));

    // Horizontal scanlines + restrained three-pixel RGB aperture grille.
    float scan = 1.0 - abs(2.0 * fract(fragCoord.y / SCANLINE_PERIOD_PX) - 1.0);
    float slot = fract(fragCoord.x * (1.0 / 3.0));
    float afterRed = step(1.0 / 3.0, slot);
    float beforeBlue = 1.0 - step(2.0 / 3.0, slot);
    vec3 grilleLoss = vec3(afterRed, 2.0 - afterRed - beforeBlue, beforeBlue);
    color *= 1.0 - APERTURE_DARK * grilleLoss;
    color *= 1.0 - SCANLINE_DARK * scan;

    // A faint curved-glass edge, without a fake bezel or overlay texture.
    float rim = smoothstep(0.45, 0.5, max(abs(p.x), abs(p.y)));
    color *= 1.0 - VIGNETTE_DARK * dot(p, p) - RIM_DARK * rim;
    fragColor = vec4(color, center.a);
}
