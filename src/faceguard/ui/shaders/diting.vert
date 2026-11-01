#version 440
layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 qt_TexCoord0;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float phase;
    float listen;
    float acknowledge;
    float still;
    float gaze;
    vec2 itemSize;
};
void main() {
    qt_TexCoord0 = qt_MultiTexCoord0;
    vec2 uv = qt_MultiTexCoord0;
    vec2 p = qt_Vertex.xy;
    float head = 1.0 - smoothstep(0.35, 0.69, uv.y);
    float body = 1.0 - smoothstep(0.75, 0.98, uv.y);
    float breath = sin(phase * 1.55) * (1.0 - still);
    p.x += (uv.x - 0.59) * itemSize.x * 0.009 * breath * body;
    p.y -= itemSize.y * 0.003 * breath * body;
    vec2 pivot = itemSize * vec2(0.60, 0.49);
    float angle = listen * 0.18 + acknowledge * 0.055 + gaze * 0.018 * (1.0 - still);
    vec2 d = p - pivot;
    vec2 turned = vec2(cos(angle) * d.x - sin(angle) * d.y,
                       sin(angle) * d.x + cos(angle) * d.y);
    p += (turned - d + vec2(itemSize.x * 0.015, itemSize.y * 0.075) * listen) * head;
    float tail = (1.0 - smoothstep(0.27, 0.42, uv.x)) * smoothstep(0.34, 0.53, uv.y)
                 * (1.0 - smoothstep(0.85, 0.98, uv.y));
    p.x += sin(phase * 0.95) * itemSize.x * 0.012 * tail * (1.0 - still);
    gl_Position = qt_Matrix * vec4(p, qt_Vertex.zw);
}
