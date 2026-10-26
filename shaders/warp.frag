# Phantom Engine - Projection Warp Shader
# 4-corner projection mapping matrix warp shader

uniform sampler2D inputTexture;
uniform mat4 warpMatrix;

varying vec2 vTexCoord;

void main() {
    // Apply warp transformation
    vec2 uv = vTexCoord;
    
    // Transform UV coordinates
    vec4 transformed = warpMatrix * vec4(uv, 0.0, 1.0);
    uv = transformed.xy / transformed.w;
    
    // Clamp to valid range
    uv = clamp(uv, 0.0, 1.0);
    
    gl_FragColor = texture(inputTexture, uv);
}
