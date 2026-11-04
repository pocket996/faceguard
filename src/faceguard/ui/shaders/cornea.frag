// Analytic studio-light reflections on the actual convex, skinned cornea.
// No eye image, UV highlight, frame clock or pose-dependent white decal.
SHARED_VARS { vec4 reflection; };
void MAIN()
{
    vec3 n = normalize(NORMAL);
    vec3 v = normalize(VIEW_VECTOR);
    if (dot(n, v) < 0.0) n = -n;
    vec3 reflected = reflect(-v, n);
    float key = pow(max(0.0, dot(reflected, normalize(vec3(-0.40, 0.55, 0.73)))), 190.0);
    float fill = pow(max(0.0, dot(reflected, normalize(vec3(0.25, -0.10, 0.96)))), 360.0);
    float fresnel = pow(1.0 - max(0.0, dot(n, v)), 5.0);
    float alpha = clamp(key * .95 + fill * .35 + fresnel * .025, 0.0, .95) * highlightStrength;
    SHARED.reflection = vec4(vec3(1.0, .98, .94), alpha);
    BASE_COLOR = vec4(0.0);
    SPECULAR_AMOUNT = 0.0;
    ROUGHNESS = .08;
}
void POST_PROCESS()
{
    COLOR_SUM = SHARED.reflection;
}
