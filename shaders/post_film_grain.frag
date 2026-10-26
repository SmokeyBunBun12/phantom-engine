# Phantom Engine - Film Grain Post-Processing Shader
# Film grain/noise generation

uniform sampler2D inputTexture;
uniform float u_intensity;

varying vec2 vTexCoord;

void main() {
    vec4 color = texture(inputTexture, vTexCoord);
    
    // Generate film grain noise
    float noise = fract(sin(dot(vTexCoord, vec2(12.9898, 78.233))) * 43758.5453);
    float grain = (noise - 0.5) * u_intensity;
    
    color.rgb += grain;
    
    gl_FragColor = color;
}
