# Phantom Engine - Chromatic Aberration Post-Processing Shader
# Chromatic aberration and lens distortion

uniform sampler2D inputTexture;
uniform float u_intensity;
uniform float u_offset;

varying vec2 vTexCoord;

void main() {
    vec2 uv = vTexCoord;
    
    // Chromatic aberration offsets
    vec2 chromaticOffset = vec2(u_intensity, -u_intensity) * u_offset;
    
    vec3 r = texture(inputTexture, uv + chromaticOffset).rgb;
    vec3 g = texture(inputTexture, uv).rgb;
    vec3 b = texture(inputTexture, uv - chromaticOffset).rgb;
    
    vec3 finalColor = vec3(r, g, b);
    
    // Add subtle lens distortion effect
    float distortion = 1.0 + u_intensity * 0.02;
    vec2 uv_distorted = uv * distortion;
    finalColor = texture(inputTexture, clamp(uv_distorted, 0.0, 1.0)).rgb;
    
    gl_FragColor = vec4(finalColor, 1.0);
}
