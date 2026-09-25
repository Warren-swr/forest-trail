// Chunked, instanced rendering of scattered vegetation and rocks with LODs.
import * as pc from 'playcanvas';
import type { Instance } from '../world/scatter';
import type { ModelLibrary, ModelPart } from './models';

interface LayerChunk {
  cx: number;
  cz: number;
  /** one entity per LOD */
  lods: pc.Entity[];
  current: number;
}

export interface LayerOptions {
  chunk: number;
  /** distance thresholds: lod i is used while d < dist[i]; beyond the last = hidden */
  dist: number[];
  castShadows: boolean[];
  /** model names per kind per LOD ('__none' = not drawn at that LOD) */
  models: string[][];
  heightPad: number;
}

const tmpM = new pc.Mat4();
const tmpR = new pc.Mat4();
const tmpQ = new pc.Quat();
const tmpV = new pc.Vec3();
const tmpS = new pc.Vec3();

export class InstancedLayer {
  chunks: LayerChunk[] = [];
  entity: pc.Entity;

  constructor(app: pc.AppBase, lib: ModelLibrary, instances: Instance[], private opt: LayerOptions, name: string) {
    const device = app.graphicsDevice;
    this.entity = new pc.Entity(name);
    const buckets = new Map<string, Instance[]>();
    for (const it of instances) {
      const cx = Math.floor(it.x / opt.chunk), cz = Math.floor(it.z / opt.chunk);
      const k = `${cx},${cz}`;
      let b = buckets.get(k);
      if (!b) buckets.set(k, (b = []));
      b.push(it);
    }
    const format = pc.VertexFormat.getDefaultInstancingFormat(device);
    for (const [k, list] of buckets) {
      const [cx, cz] = k.split(',').map(Number);
      let minY = Infinity, maxY = -Infinity;
      for (const it of list) { minY = Math.min(minY, it.y); maxY = Math.max(maxY, it.y); }
      const aabb = new pc.BoundingBox(
        new pc.Vec3((cx + 0.5) * opt.chunk, (minY + maxY + opt.heightPad) / 2, (cz + 0.5) * opt.chunk),
        new pc.Vec3(opt.chunk / 2 + 4, (maxY - minY + opt.heightPad) / 2 + 2, opt.chunk / 2 + 4),
      );
      const lodMis: pc.MeshInstance[][] = opt.dist.map(() => []);
      for (let kind = 0; kind < opt.models.length; kind++) {
        const ofKind = list.filter((i) => i.kind === kind);
        if (!ofKind.length) continue;
        for (let l = 0; l < opt.dist.length; l++) {
          const modelName = opt.models[kind][Math.min(l, opt.models[kind].length - 1)];
          // '__none': this kind is not drawn at this LOD
          if (modelName === '__none') continue;
          const model = lib.get(modelName);
          for (const part of model.parts) {
            const mi = this.buildInstanced(device, format, part, ofKind, aabb);
            mi.castShadow = opt.castShadows[l];
            lodMis[l].push(mi);
          }
        }
      }
      const lods = lodMis.map((mis, l) => {
        const e = new pc.Entity(`${name}-${k}-${l}`);
        e.addComponent('render', { meshInstances: mis, castShadows: opt.castShadows[l], receiveShadows: true });
        e.enabled = false;
        this.entity.addChild(e);
        return e;
      });
      this.chunks.push({ cx: (cx + 0.5) * opt.chunk, cz: (cz + 0.5) * opt.chunk, lods, current: -1 });
    }
    app.root.addChild(this.entity);
  }

  private buildInstanced(device: pc.GraphicsDevice, format: pc.VertexFormat, part: ModelPart, list: Instance[], aabb: pc.BoundingBox) {
    const data = new Float32Array(list.length * 16);
    for (let i = 0; i < list.length; i++) {
      const it = list[i];
      tmpQ.setFromEulerAngles(0, (it.yaw * 180) / Math.PI, 0);
      tmpV.set(it.x, it.y, it.z);
      tmpS.set(it.s, it.s, it.s);
      tmpR.setTRS(tmpV, tmpQ, tmpS);
      tmpM.mul2(tmpR, part.local);
      data.set(tmpM.data, i * 16);
    }
    const vb = new pc.VertexBuffer(device, format, list.length, { data });
    const mi = new pc.MeshInstance(part.mesh, part.material);
    mi.setInstancing(vb);
    mi.setCustomAabb(aabb);
    return mi;
  }

  private scale = 1;
  setDistanceScale(s: number) {
    this.scale = s;
    for (const c of this.chunks) c.current = -2;
  }

  update(cam: pc.Vec3) {
    const d2 = this.opt.dist.map((d, i) => (i === this.opt.dist.length - 1 ? d * (0.75 + this.scale * 0.25) : d * this.scale));
    for (const c of this.chunks) {
      const d = Math.hypot(cam.x - c.cx, cam.z - c.cz) - this.opt.chunk * 0.5;
      let l = -1;
      for (let i = 0; i < d2.length; i++) if (d < d2[i]) { l = i; break; }
      if (l === c.current) continue;
      if (c.current >= 0) c.lods[c.current].enabled = false;
      if (c.current === -2) for (const e of c.lods) e.enabled = false;
      if (l >= 0) c.lods[l].enabled = true;
      c.current = l;
    }
  }
}
