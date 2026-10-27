// Neutral black-phosphor CRT for Ghostty.
// Inspired by https://gist.github.com/dharmapurikar/1289cdbcafd5aacc9f28d136ec906097
// One post-process pass, three texture samples, no animation or trigonometry.
const float GLOW_RADIUS_PX = 1.75;
const float GLOW_STRENGTH = 0.14;
const float SCANLINE_DARK = 0.035;
const float VIGNETTE_DARK = 0.14;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec4 center = texture(iChannel0, uv);

    // High-pass horizontal phosphor bleed: never lifts flat backgrounds.
    vec2 offset = vec2(GLOW_RADIUS_PX / iResolution.x, 0.0);
    vec3 adjacent = 0.5 * (
        texture(iChannel0, uv - offset).rgb +
        texture(iChannel0, uv + offset).rgb
    );
    vec3 color = center.rgb +
        GLOW_STRENGTH * max(adjacent - center.rgb, vec3(0.0));

    // Four-device-pixel triangular scanlines; darken by at most 3.5%.
    float scan = abs(2.0 * fract(fragCoord.y * 0.25) - 1.0);
    vec2 corner = uv - 0.5;
    color *= 1.0 - SCANLINE_DARK * scan -
        VIGNETTE_DARK * dot(corner, corner);

    fragColor = vec4(color, center.a);
}
