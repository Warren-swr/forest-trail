// GLSL chunk overrides for the PlayCanvas standard material.
import * as pc from 'playcanvas';

/** value-noise lattice hash built from the mod-289 permutation polynomial: it
 * only does exact small-integer float maths, so two cells always agree on a
 * shared corner. The fract(p * 233.34) style hash does not on every GPU
 * compiler and left straight seams across the sky clouds. */
export const LATTICE_HASH = /* glsl */ `
float ftPerm(float x) { return mod((x * 34.0 + 1.0) * x, 289.0); }
float ftLat(vec2 p) {
  p = mod(p, 289.0);
  return ftPerm(ftPerm(ftPerm(p.x) + p.y) + 17.0) * (1.0 / 289.0);
}`;

export const NOISE_GLSL = /* glsl */ `
${LATTICE_HASH}
vec2 ftGrad(vec2 i) {
  float h = ftLat(i) * 6.2831853;
  return vec2(cos(h), sin(h));
}
float ftHash(vec2 p) { return ftLat(p); }
// gradient noise in [0, 1]
float ftNoise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  float a = dot(ftGrad(i), f);
  float b = dot(ftGrad(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0));
  float c = dot(ftGrad(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0));
  float d = dot(ftGrad(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0));
  return 0.5 + 0.9 * mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
const mat2 ftRot = mat2(0.8, -0.6, 0.6, 0.8);
float ftFbm(vec2 p) { float v = ftNoise(p) * 0.5; p = ftRot * p * 2.03 + 7.1; v += ftNoise(p) * 0.3; p = ftRot * p * 2.01 + 3.3; v += ftNoise(p) * 0.2; return v; }
vec3 ftLin(vec3 c) { return pow(c, vec3(2.2)); }
`;

/** Height-aware fog that thickens in valleys and tints with sun direction. */
export const FOG_GLSL = /* glsl */ `
float dBlendModeFogFactor = 1.0;
uniform vec3 fog_color;
uniform float fog_start;
uniform float fog_end;
uniform vec3 ft_fogSun;
uniform vec3 ft_sunDir;
#ifdef VERTEXSHADER
  float getFogFactor(float depth) { return clamp((fog_end - depth) / (fog_end - fog_start), 0.0, 1.0); }
  vec3 addFog(vec3 color, float depth) { return mix(fog_color, color, getFogFactor(depth)); }
#else
  uniform vec3 view_position;
  float getFogFactor() { return 1.0; }
  vec3 addFog(vec3 color) {
    vec3 d = vPositionW - view_position;
    float dist = length(d);
    float f = clamp((dist - fog_start) / (fog_end - fog_start), 0.0, 1.0);
    float h = max(vPositionW.y, 0.0);
    float hf = mix(1.0, 0.55, clamp(h / 60.0, 0.0, 1.0));
    f = 1.0 - exp(-f * f * 1.7 * hf);
    f = clamp(f * 1.08, 0.0, 1.0);
    float sunAmt = pow(max(dot(normalize(d), ft_sunDir), 0.0), 6.0);
    vec3 fc = mix(fog_color, ft_fogSun, sunAmt * 0.8);
    return mix(color, fc * dBlendModeFogFactor, f);
  }
#endif
`;

export const TERRAIN_DIFFUSE = /* glsl */ `
uniform vec3 material_diffuse;
uniform sampler2D ft_splat;
uniform sampler2D ft_aux;
uniform float ft_worldHalf;
uniform float ft_worldSize;
uniform vec4 ft_redZ[4];
uniform vec4 ft_meadowZ[6];
uniform vec4 ft_autumnZ[4];
${NOISE_GLSL}
float ftZone(vec4 z, vec2 p) { return z.z > 0.0 ? 1.0 - smoothstep(z.z * 0.55, z.z, distance(p, z.xy)) : 0.0; }
// cellular cracks for dry dirt: distance to the nearest cell border
float ftCracks(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  float d1 = 8.0, d2 = 8.0;
  for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
    vec2 g = vec2(float(x), float(y));
    vec2 o = vec2(ftHash(i + g), ftHash(i + g + 17.3)) * 0.85 + 0.075;
    float d = length(g + o - f);
    if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) d2 = d;
  }
  return d2 - d1;
}
float ftWet;
float ftMud;
float ftRock;
void getAlbedo() {
  vec2 wp = vPositionW.xz;
  vec2 uv = (wp + ft_worldHalf) / ft_worldSize;
  vec4 s = texture2D(ft_splat, uv);
  vec4 a = texture2D(ft_aux, uv);
  float n1 = ftFbm(wp * 0.045);
  float n2 = ftNoise(ftRot * wp * 0.37);
  float n3 = ftNoise(ftRot * ftRot * wp * 2.3 + 11.0);
  float n4 = ftNoise(wp * 9.0 + 5.0);
  // meadow grass: moss to warm dry grass
  vec3 grassA = ftLin(vec3(0.36, 0.45, 0.24));
  vec3 grassB = ftLin(vec3(0.62, 0.58, 0.33));
  vec3 grassC = ftLin(vec3(0.27, 0.37, 0.22));
  vec3 grass = mix(grassA, grassB, smoothstep(0.35, 0.8, n1 + n2 * 0.25));
  grass = mix(grass, grassC, smoothstep(0.55, 0.9, n2) * 0.6);
  grass *= 0.9 + 0.2 * n3;
  // forest floor under canopy: needles and dark moss
  vec3 floorA = ftLin(vec3(0.33, 0.28, 0.2));
  vec3 floorB = ftLin(vec3(0.2, 0.27, 0.17));
  vec3 forest = mix(floorA, floorB, smoothstep(0.3, 0.7, n2 + n3 * 0.3)) * (0.85 + 0.25 * n4);
  vec3 base = mix(grass, forest, smoothstep(0.1, 0.75, a.a));
  // dirt with compacted wheel tracks and a grassy centre strip
  vec3 dirt = ftLin(vec3(0.55, 0.47, 0.36)) * (0.88 + 0.22 * n3) * (0.94 + 0.12 * n4);
  dirt = mix(dirt, ftLin(vec3(0.44, 0.37, 0.28)), a.r * 0.7);
  dirt = mix(dirt, grass * 0.9, a.g * 0.85);
  // wet mud: brown with darker puddles and lighter drying crust
  vec3 mud = ftLin(vec3(0.43, 0.36, 0.28)) * (0.85 + 0.25 * n3);
  float puddle = smoothstep(0.58, 0.72, ftNoise(ftRot * wp * 0.45 + 3.0));
  mud = mix(mud, ftLin(vec3(0.3, 0.26, 0.21)), puddle * 0.8 + a.r * 0.4);
  mud = mix(mud, ftLin(vec3(0.52, 0.46, 0.36)), smoothstep(0.62, 0.8, n2) * (1.0 - puddle) * 0.5);
  float speck = step(0.62, n4) * 0.25 + step(0.8, ftNoise(wp * 23.0)) * 0.2;
  vec3 gravel = ftLin(vec3(0.5, 0.47, 0.41)) * (0.78 + 0.22 * n3 + speck);
  // layered rock: strata bands, dark cracks and mossy patches
  float strata = 0.5 + 0.5 * sin(vPositionW.y * 2.4 + ftNoise(wp * 0.25) * 6.0);
  float crack = smoothstep(0.47, 0.5, abs(ftNoise(ftRot * wp * 1.3) - 0.5) * -1.0 + 0.98);
  vec3 rock = mix(ftLin(vec3(0.42, 0.41, 0.38)), ftLin(vec3(0.6, 0.58, 0.53)), strata * 0.6 + n3 * 0.4);
  rock *= 0.8 + 0.25 * n4;
  rock *= 1.0 - crack * 0.45;
  rock = mix(rock, ftLin(vec3(0.36, 0.42, 0.26)), smoothstep(0.55, 0.78, n2 + n1 * 0.2) * 0.55);
  // regional palettes
  float red = 0.0, meadow = 0.0, autumn = 0.0;
  for (int i = 0; i < 4; i++) { red = max(red, ftZone(ft_redZ[i], wp)); autumn = max(autumn, ftZone(ft_autumnZ[i], wp)); }
  for (int i = 0; i < 6; i++) meadow = max(meadow, ftZone(ft_meadowZ[i], wp));
  meadow *= 0.75 + 0.25 * n2;
  vec3 golden = mix(ftLin(vec3(0.72, 0.6, 0.3)), ftLin(vec3(0.62, 0.56, 0.3)), n3) * (0.9 + 0.15 * n4);
  base = mix(base, golden, meadow * (1.0 - a.a * 0.7) * 0.85);
  // autumn floor: leaf litter in red and orange flecks
  float leaf = smoothstep(0.55, 0.72, ftNoise(wp * 1.7 + 4.0));
  vec3 litter = mix(ftLin(vec3(0.58, 0.36, 0.18)), ftLin(vec3(0.66, 0.24, 0.13)), leaf);
  base = mix(base, litter, autumn * (0.35 + 0.45 * a.a) * (0.6 + 0.4 * n1));
  // red sandstone country
  vec3 sand = mix(ftLin(vec3(0.78, 0.52, 0.34)), ftLin(vec3(0.7, 0.4, 0.26)), n2) * (0.9 + 0.15 * n3);
  float strataR = 0.5 + 0.5 * sin(vPositionW.y * 1.6 + ftNoise(wp * 0.2) * 4.0);
  vec3 redRock = mix(ftLin(vec3(0.62, 0.3, 0.19)), ftLin(vec3(0.86, 0.56, 0.36)), strataR * 0.7 + n4 * 0.3);
  base = mix(base, mix(sand, ftLin(vec3(0.5, 0.5, 0.3)), 0.25 * (1.0 - n1)), red * 0.9);
  dirt = mix(dirt, sand * 0.95, red * 0.85);
  rock = mix(rock, redRock * (1.0 - crack * 0.35), red);
  gravel = mix(gravel, sand * 1.05, red * 0.7);
  // dry cracked dirt (away from ruts, puddles and grass strip)
  float cr = ftCracks(wp * 1.35);
  float dry = (1.0 - a.b) * (1.0 - a.r * 0.8) * smoothstep(0.35, 0.75, ftNoise(wp * 0.08 + 9.0) + red * 0.4);
  dirt *= 1.0 - (1.0 - smoothstep(0.015, 0.06, cr)) * 0.32 * dry;
  vec3 col = base;
  col = mix(col, dirt, s.r);
  col = mix(col, gravel, s.b);
  col = mix(col, rock, s.a);
  col = mix(col, mud, s.g);
  ftWet = max(a.b, s.g);
  ftMud = s.g;
  ftRock = s.a;
  col *= mix(1.0, 0.72, a.b * (1.0 - s.g * 0.6));
  dAlbedo = col;
}
`;

export const TERRAIN_GLOSS = /* glsl */ `
uniform float material_gloss;
void getGlossiness() {
  dGlossiness = mix(0.12, 0.55, ftWet) + ftRock * 0.08;
}
`;

/** fog override; `cap` < 1 keeps very distant scenery (mountain ranges) from vanishing into the haze */
export function applyFog(mat: pc.StandardMaterial, cap = 1) {
  const chunks = mat.getShaderChunks(pc.SHADERLANGUAGE_GLSL);
  chunks.set('fogPS', cap >= 1 ? FOG_GLSL : FOG_GLSL.replace('f = clamp(f * 1.08, 0.0, 1.0);', `f = clamp(f * 1.08, 0.0, ${cap.toFixed(3)});`));
  mat.shaderChunksVersion = '2.8';
}

/** zones as [x, z, radius] → flattened vec4 uniform array (padded with zero radius) */
export function zoneUniform(zones: [number, number, number][], count: number): Float32Array {
  const out = new Float32Array(count * 4);
  zones.slice(0, count).forEach((z, i) => out.set([z[0], z[1], z[2], 0], i * 4));
  return out;
}

export function makeTerrainMaterial(splat: pc.Texture, aux: pc.Texture, half: number, size: number): pc.StandardMaterial {
  const mat = new pc.StandardMaterial();
  mat.name = 'terrain';
  const chunks = mat.getShaderChunks(pc.SHADERLANGUAGE_GLSL);
  chunks.set('diffusePS', TERRAIN_DIFFUSE);
  chunks.set('glossPS', TERRAIN_GLOSS);
  chunks.set('fogPS', FOG_GLSL);
  mat.shaderChunksVersion = '2.8';
  mat.useMetalness = true;
  mat.metalness = 0;
  mat.gloss = 0.2;
  mat.setParameter('ft_splat', splat);
  mat.setParameter('ft_aux', aux);
  mat.setParameter('ft_worldHalf', half);
  mat.setParameter('ft_worldSize', size);
  mat.update();
  return mat;
}
