// Chunked terrain mesh with three LOD levels and skirts.
import * as pc from 'playcanvas';
import type { Terrain } from '../world/terrain';
import { makeTerrainMaterial, zoneUniform } from './shaders';
import { AUTUMN_ZONES, MEADOW_ZONES, RED_ZONES } from '../world/layout';

const CHUNK = 64;
const LOD_STEPS = [1, 2, 4];
const LOD_DIST = [110, 240];

interface Chunk {
  cx: number;
  cz: number;
  lods: pc.Entity[];
  current: number;
}

export class TerrainRender {
  entity: pc.Entity;
  material: pc.StandardMaterial;
  chunks: Chunk[] = [];
  splatTex: pc.Texture;
  auxTex: pc.Texture;

  constructor(app: pc.AppBase, private T: Terrain) {
    const device = app.graphicsDevice;
    this.splatTex = makeTex(device, T.mat, T.mn, 'splat');
    this.auxTex = makeTex(device, T.aux, T.mn, 'aux');
    this.material = makeTerrainMaterial(this.splatTex, this.auxTex, T.half, T.size);
    this.material.setParameter('ft_redZ[0]', zoneUniform(RED_ZONES, 4));
    this.material.setParameter('ft_meadowZ[0]', zoneUniform(MEADOW_ZONES, 6));
    this.material.setParameter('ft_autumnZ[0]', zoneUniform(AUTUMN_ZONES, 4));
    this.entity = new pc.Entity('terrain');
    const nC = T.size / CHUNK;
    for (let cz = 0; cz < nC; cz++) {
      for (let cx = 0; cx < nC; cx++) {
        const lods: pc.Entity[] = [];
        for (let l = 0; l < LOD_STEPS.length; l++) {
          const mesh = this.buildChunk(device, cx * CHUNK, cz * CHUNK, LOD_STEPS[l]);
          const mi = new pc.MeshInstance(mesh, this.material);
          mi.castShadow = false;
          mi.receiveShadow = true;
          const e = new pc.Entity(`terrain-${cx}-${cz}-${l}`);
          e.addComponent('render', { meshInstances: [mi], castShadows: false, receiveShadows: true });
          e.enabled = l === 0;
          this.entity.addChild(e);
          lods.push(e);
        }
        this.chunks.push({ cx: cx * CHUNK - T.half + CHUNK / 2, cz: cz * CHUNK - T.half + CHUNK / 2, lods, current: 0 });
      }
    }
    app.root.addChild(this.entity);
  }

  private buildChunk(device: pc.GraphicsDevice, ox: number, oz: number, step: number): pc.Mesh {
    const T = this.T;
    const n = CHUNK / step + 1;
    const vcount = n * n + 4 * n;
    const pos = new Float32Array(vcount * 3);
    const nor = new Float32Array(vcount * 3);
    const nrm = { x: 0, y: 1, z: 0 };
    let v = 0;
    const put = (ix: number, iz: number, drop: number) => {
      const gx = ox + ix * step, gz = oz + iz * step;
      const x = gx - T.half, z = gz - T.half;
      const h = T.heights[Math.min(T.n - 1, gz) * T.n + Math.min(T.n - 1, gx)];
      pos[v * 3] = x; pos[v * 3 + 1] = h - drop; pos[v * 3 + 2] = z;
      T.normalAt(x, z, nrm, Math.max(1.2, step));
      nor[v * 3] = nrm.x; nor[v * 3 + 1] = nrm.y; nor[v * 3 + 2] = nrm.z;
      v++;
    };
    for (let iz = 0; iz < n; iz++) for (let ix = 0; ix < n; ix++) put(ix, iz, 0);
    const idx: number[] = [];
    for (let iz = 0; iz < n - 1; iz++) {
      for (let ix = 0; ix < n - 1; ix++) {
        const a = iz * n + ix, b = a + 1, c = a + n, d = c + 1;
        // alternate diagonals to reduce directional artefacts
        if ((ix + iz) % 2 === 0) idx.push(a, c, b, b, c, d);
        else idx.push(a, c, d, a, d, b);
      }
    }
    // skirts along the four edges
    const drop = 1.5 * step;
    const edges: [number, number][][] = [
      Array.from({ length: n }, (_, i) => [i, 0] as [number, number]),
      Array.from({ length: n }, (_, i) => [n - 1, i] as [number, number]),
      Array.from({ length: n }, (_, i) => [n - 1 - i, n - 1] as [number, number]),
      Array.from({ length: n }, (_, i) => [0, n - 1 - i] as [number, number]),
    ];
    for (const e of edges) {
      const start = v;
      for (const [ix, iz] of e) put(ix, iz, drop);
      for (let i = 0; i < n - 1; i++) {
        const t0 = e[i][1] * n + e[i][0], t1 = e[i + 1][1] * n + e[i + 1][0];
        const b0 = start + i, b1 = start + i + 1;
        idx.push(t0, b1, b0, t0, t1, b1);
      }
    }
    const mesh = new pc.Mesh(device);
    mesh.setPositions(pos);
    mesh.setNormals(nor);
    mesh.setIndices(vcount > 65535 ? new Uint32Array(idx) : new Uint16Array(idx));
    mesh.update(pc.PRIMITIVE_TRIANGLES);
    return mesh;
  }

  update(camPos: pc.Vec3) {
    for (const c of this.chunks) {
      const d = Math.max(Math.abs(camPos.x - c.cx), Math.abs(camPos.z - c.cz)) - CHUNK / 2;
      const l = d < LOD_DIST[0] ? 0 : d < LOD_DIST[1] ? 1 : 2;
      if (l !== c.current) {
        c.lods[c.current].enabled = false;
        c.lods[l].enabled = true;
        c.current = l;
      }
    }
  }
}

export function makeTex(device: pc.GraphicsDevice, data: Uint8Array, size: number, name: string): pc.Texture {
  const tex = new pc.Texture(device, {
    name,
    width: size,
    height: size,
    format: pc.PIXELFORMAT_RGBA8,
    mipmaps: true,
    minFilter: pc.FILTER_LINEAR_MIPMAP_LINEAR,
    magFilter: pc.FILTER_LINEAR,
    addressU: pc.ADDRESS_CLAMP_TO_EDGE,
    addressV: pc.ADDRESS_CLAMP_TO_EDGE,
    levels: [data],
  });
  return tex;
}
