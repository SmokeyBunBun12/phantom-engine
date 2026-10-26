# Phantom Engine - Post Base Shader
# Screen-space quad vertex shader for post-processing

attribute vec2 inPosition;
attribute vec2 inTexCoord;

uniform mat4 projMatrix;

varying vec2 vTexCoord;

void main() {
    vec4 position = vec4(inPosition, 0.0, 1.0);
    gl_Position = projMatrix * position;
    vTexCoord = inTexCoord;
}
