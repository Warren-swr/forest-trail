// Wind sway for foliage: a copy of the engine's transformVS chunk that bends
// vertices by their height in model space. The phase comes from the instance
// origin so neighbouring trees do not move in lockstep. Shadow and depth
// passes use the same chunk, so shadows sway with the leaves.
import * as pc from 'playcanvas';

const WIND_TRANSFORM = /* glsl */ `
#ifdef PIXELSNAP
uniform vec4 uScreenSize;
#endif
#ifdef SCREENSPACE
uniform float projectionFlipY;
#endif
uniform float ft_time;
uniform float ft_windAmp;
uniform float ft_windHeight;
uniform float ft_windGust;
vec4 evalWorldPosition(vec3 vertexPosition, mat4 modelMatrix) {
	vec3 localPos = getLocalPosition(vertexPosition);
	vec4 posW = modelMatrix * vec4(localPos, 1.0);
	vec3 origin = modelMatrix[3].xyz;
	float h = clamp(localPos.y / ft_windHeight, 0.0, 1.4);
	float w = h * h;
	float ph = dot(origin.xz, vec2(0.071, 0.113));
	float gust = 0.55 + 0.45 * sin(ft_time * 0.31 + origin.x * 0.012 + origin.z * 0.007);
	float sway = sin(ft_time * 1.25 + ph) * 0.65 + sin(ft_time * 2.9 + ph * 1.7 + localPos.y * 0.8) * 0.35;
	float flutter = sin(ft_time * 7.0 + dot(localPos, vec3(3.1, 1.7, 2.3)) + ph * 3.0) * 0.12 * h;
	vec2 dir = vec2(0.8, 0.6);
	posW.xz += dir * (sway * gust * ft_windGust + flutter) * w * ft_windAmp;
	#ifdef SCREENSPACE
		posW.zw = vec2(0.0, 1.0);
	#endif
	return posW;
}
vec4 getPosition() {
	dModelMatrix = getModelMatrix();
	vec4 posW = evalWorldPosition(vertex_position.xyz, dModelMatrix);
	dPositionW = posW.xyz;
	vec4 screenPos;
	#ifdef UV1LAYOUT
		screenPos = vec4(vertex_texCoord1.xy * 2.0 - 1.0, 0.5, 1);
		#ifdef WEBGPU
			screenPos.y *= -1.0;
		#endif
	#else
		#ifdef SCREENSPACE
			screenPos = posW;
			screenPos.y *= projectionFlipY;
		#else
			screenPos = matrix_viewProjection * posW;
		#endif
		#ifdef PIXELSNAP
			screenPos.xy = (screenPos.xy * 0.5) + 0.5;
			screenPos.xy *= uScreenSize.xy;
			screenPos.xy = floor(screenPos.xy);
			screenPos.xy *= uScreenSize.zw;
			screenPos.xy = (screenPos.xy * 2.0) - 1.0;
		#endif
	#endif
	return screenPos;
}
vec3 getWorldPosition() {
	return dPositionW;
}
`;

/** sway amplitude (m at the reference height) and reference height (m) per model family */
export const WIND: Record<string, [number, number]> = {
  pine_tall_a: [0.35, 18], pine_tall_b: [0.35, 18], pine_mid: [0.28, 11], pine_young: [0.14, 4.5],
  aspen_gold: [0.32, 10], snag: [0.08, 9], maple_red: [0.3, 8.5], maple_orange: [0.3, 8.4],
  birch: [0.36, 11.7], larch_gold: [0.32, 14],
  bush_a: [0.05, 1.2], bush_b: [0.05, 1.2], fern: [0.06, 0.5],
  grass_tuft: [0.09, 0.6], grass_tall: [0.16, 0.95], flowers_a: [0.08, 0.55], flowers_b: [0.09, 0.56],
};

const done = new WeakSet<pc.Material>();

export function applyWind(mat: pc.StandardMaterial, amp: number, height: number) {
  if (done.has(mat)) return;
  done.add(mat);
  mat.getShaderChunks(pc.SHADERLANGUAGE_GLSL).set('transformVS', WIND_TRANSFORM);
  mat.shaderChunksVersion = '2.8';
  mat.setParameter('ft_windAmp', amp);
  mat.setParameter('ft_windHeight', height);
  mat.update();
}

/** global wind clock and strength */
export function updateWind(device: pc.GraphicsDevice, time: number, gust = 1) {
  device.scope.resolve('ft_time').setValue(time);
  device.scope.resolve('ft_windGust').setValue(gust);
}
