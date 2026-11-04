#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float footRatio;
    float phase;
};
layout(binding = 1) uniform sampler2D source;
void main() {
    vec2 uv = qt_TexCoord0;
    float wave = sin(uv.y * 95.0 - phase * 1.5) * .0035 * uv.y;
    vec2 reflected = vec2(uv.x + wave, footRatio - uv.y * 1.05);
    vec4 sampleColor = texture(source, reflected);
    float fade = .22 * pow(1.0 - uv.y, 2.0) * step(0.0, reflected.y);
    fragColor = sampleColor * vec4(.84, .95, .93, 1.0) * fade * qt_Opacity;
}
