# Phantom Engine - Skeletal Shader
# Vertex shader for skeletal mesh skinning / transformation

uniform mat4 modelMatrix;
uniform mat4 viewMatrix;
uniform mat4 projectionMatrix;
uniform mat4 bones[MAX_BONES];

attribute vec3 inPosition;
attribute vec3 inNormal;
attribute vec2 inTexCoord;
attribute vec4 inBoneWeights;
attribute int inBoneIndices;

varying vec3 vPosition;
varying vec3 vNormal;
varying vec2 vTexCoord;
varying vec3 vBonePosition;
varying float vBoneWeight;

void main() {
    vec4 position = vec4(inPosition, 1.0);
    
    // Calculate final position with skinning
    // bone matrices are applied per-bone based on weights
    mat4 skinMatrix = mat4(1.0); // placeholder - real implementation would compose bone matrices
    vec4 skinnedPosition = skinMatrix * position;
    
    vec4 mvPosition = viewMatrix * modelMatrix * skinnedPosition;
    vec4 projPosition = projectionMatrix * mvPosition;
    
    vPosition = mvPosition.xyz;
    vNormal = normalize(mat3(modelMatrix) * inNormal);
    vTexCoord = inTexCoord;
    
    vBoneWeight = inBoneWeights.w;
    vBonePosition = inPosition;
    
    gl_Position = projPosition;
}
