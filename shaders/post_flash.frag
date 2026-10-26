# Phantom Engine - Flash Post-Processing Shader
# Jump-scare flash/strobe transition shader

uniform sampler2D inputTexture;
uniform float u_intensity;
uniform float u_time;
uniform float u_flash_duration;
uniform float u_flash_frequency;
uniform float u_decay_rate;
uniform vec3 u_flash_color;

varying vec2 vTexCoord;

void main() {
    // Flash timer calculation
    float flashPhase = fract(u_time * u_flash_frequency);
    float flashAmount = 0.0;
    
    // Calculate flash envelope (attack and decay)
    if (flashPhase < 1.0 / u_flash_frequency) {
        flashAmount = (1.0 - flashPhase * u_flash_frequency) * u_intensity;
    } else {
        flashAmount = pow(1.0 - fract(u_time * u_flash_frequency), u_decay_rate) * u_intensity;
    }
    
    // Apply flash
    vec4 color = texture(inputTexture, vTexCoord);
    vec3 finalColor = color.rgb * (1.0 - flashAmount) + u_flash_color * flashAmount;
    
    gl_FragColor = vec4(finalColor, color.a);
}
