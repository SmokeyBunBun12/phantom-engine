# Phantom Engine - Skeleton PBR Shader
# Fragment shader with PBR lighting + bone glow, X-ray transparency

uniform sampler2D boneTexture;
uniform vec3 lightPosition;
uniform vec3 lightColor;
uniform vec3 viewPosition;
uniform float boneGlowIntensity;
uniform float xrayTransparency;
uniform float skeletonOpacity;
uniform float wireframeMode;

varying vec3 vPosition;
varying vec3 vNormal;
varying vec2 vTexCoord;
varying vec3 vBonePosition;
varying float vBoneWeight;

float calculateBlinnPhong(vec3 normal, vec3 lightDir, vec3 viewDir, vec3 lightColor, float shininess) {
    vec3 H = normalize(lightDir + viewDir);
    float NdotH = max(dot(normal, H), 0.0);
    float ambient = 0.1 * lightColor.x;
    float diffuse = (1.0 - shininess) * pow(NdotH, shininess) * lightColor.y;
    float specular = pow(NdotH, shininess) * lightColor.z;
    return ambient + diffuse + specular;
}

void main() {
    vec4 color = texture(boneTexture, vTexCoord);
    
    vec3 normal = normalize(vNormal);
    vec3 lightDir = normalize(lightPosition - vPosition);
    vec3 viewDir = normalize(-vPosition);
    float shininess = 32.0;
    float lighting = calculateBlinnPhong(normal, lightDir, viewDir, vec3(1.0), shininess);
    
    float boneGlow = boneGlowIntensity * pow(abs(dot(normalize(vBonePosition - vPosition), normal)), 2.0);
    color.rgb *= (1.0 + boneGlow);
    
    if (xrayTransparency > 0.0) {
        color.a *= xrayTransparency;
    }
    
    color.a *= skeletonOpacity;
    
    if (wireframeMode > 0.5) {
        vec3 grid = step(vec3(0.5), fract(vPosition * 10.0 + vec3(0.0, 0.0, 0.0))) - step(vec3(0.5), fract(vPosition * 10.0));
        color.rgb *= grid;
    }
    
    gl_FragColor = vec4(color.rgb * lighting, color.a);
}
