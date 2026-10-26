# Phantom Engine - Vignette and Color Grading Post-Processing Shader
# Cinematic vignette and color grading (contrast, saturation, tint)

uniform sampler2D inputTexture;
uniform float u_intensity;
uniform float u_roundness;
uniform float u_feather;
uniform vec3 u_color;
uniform float u_contrast;
uniform float u_saturation;
uniform float u_brightness;
uniform float u_temperature;
uniform float u_tint;
uniform float u_exposure;
uniform float u_gamma;

varying vec2 vTexCoord;

void main() {
    vec2 uv = vTexCoord;
    vec2 center = uv - 0.5;
    float dist = length(center);
    
    // Vignette calculation
    float vignette = 1.0 - u_intensity * pow(dist, u_roundness);
    vignette *= (1.0 - u_feather * dist);
    
    vec4 color = texture(inputTexture, uv);
    color.rgb *= vignette;
    
    // Color grading
    color.rgb = color.rgb * u_contrast;
    color.rgb *= u_saturation;
    color.rgb *= u_brightness;
    
    // Temperature adjustment (Kelvin)
    float tempScale = 1.0;
    if (u_temperature > 5000.0) {
        tempScale = 1.0 + ((u_temperature - 5000.0) / 5000.0) * 0.1;
    } else if (u_temperature < 5000.0) {
        tempScale = 1.0 - ((5000.0 - u_temperature) / 5000.0) * 0.1;
    }
    color.rgb *= tempScale;
    
    // Tint adjustment
    color.rgb.r *= (1.0 + u_tint);
    color.rgb.b *= (1.0 - u_tint);
    
    // Exposure adjustment
    color.rgb *= pow(2.0, u_exposure);
    
    // Gamma adjustment
    color.rgb = pow(color.rgb, 1.0 / max(0.1, u_gamma));
    
    gl_FragColor = vec4(color.rgb, color.a);
}
