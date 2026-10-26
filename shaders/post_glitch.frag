# Phantom Engine - Digital Glitch Post-Processing Shader
# RGB split, scanlines, noise, block displacement

uniform sampler2D inputTexture;
uniform float u_intensity;
uniform float u_speed;
uniform float u_time;
uniform float u_noise_amount;
uniform float u_displacement_amount;

varying vec2 vTexCoord;

uniform vec2 u_resolution;

void main() {
    vec2 uv = vTexCoord;
    
    // RGB chromatic split
    float split = u_intensity * 0.05;
    vec3 color;
    color.r = texture(inputTexture, uv + vec2(split, 0.0)).r;
    color.g = texture(inputTexture, uv).g;
    color.b = texture(inputTexture, uv - vec2(split, 0.0)).b;
    
    // Digital tear - horizontal displacement based on noise/time
    float tear = fract(sin(u_time * u_speed) * 1000.0) - 0.5;
    float displacement = tear * u_displacement_amount * u_intensity;
    
    // Scanlines
    float scanline = step(0.95, fract(vTexCoord.y * 60.0 + u_time * u_speed));
    color *= 1.0 - scanline * 0.2;
    
    // Block displacement
    vec2 blockSize = vec2(8.0, 8.0);
    vec2 blockCoord = floor(vTexCoord * (u_resolution / blockSize));
    float blockNoise = fract(sin(dot(blockCoord, vec2(12.9898, 78.233))) * 43758.5453);
    if (blockNoise > 0.95) {
        displacement += (blockNoise - 0.95) * u_displacement_amount * u_intensity;
    }
    
    // Apply displacement
    vec2 uv_displaced = uv + (uv - 0.5) * displacement * 2.0;
    color = vec3(texture(inputTexture, clamp(uv_displaced, 0.0, 1.0)).rgb);
    
    // Add noise
    if (u_noise_amount > 0.0) {
        float noise = fract(sin(dot(uv, vec2(13.7, 8.2)) + u_time * 100.0) * 43758.5453);
        color += (noise - 0.5) * u_noise_amount;
    }
    
    gl_FragColor = vec4(color, 1.0);
}
