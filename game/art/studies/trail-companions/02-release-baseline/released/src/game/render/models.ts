// GLB model library: loads containers, exposes mesh/material parts for
// instancing, and falls back to simple procedural shapes if a file is missing.
import * as pc from 'playcanvas';
import { applyFog } from './shaders';

export interface ModelPart {
  mesh: pc.Mesh;
  material: pc.Material;
  /** node transform relative to the model root */
  local: pc.Mat4;
  node: string;
}

export interface Model {
  name: string;
  parts: ModelPart[];
  container?: pc.ContainerResource;
  fallback: boolean;
}

const BASE = 'assets/models/';

export class ModelLibrary {
  models = new Map<string, Model>();
  /** materials named 'Glow' (window panes, bulbs): lit at night by the Environment */
  glowMats = new Set<pc.StandardMaterial>();
  constructor(private app: pc.AppBase) {}

  async load(names: string[], onProgress?: (done: number, total: number) => void): Promise<void> {
    let done = 0;
    await Promise.all(
      names.map(async (name) => {
        const m = await this.loadOne(name);
        this.models.set(name, m);
        onProgress?.(++done, names.length);
      }),
    );
  }

  get(name: string): Model {
    const m = this.models.get(name);
    if (m) return m;
    const fb = this.fallback(name);
    this.models.set(name, fb);
    return fb;
  }

  private loadOne(name: string): Promise<Model> {
    return new Promise((resolve) => {
      this.app.assets.loadFromUrl(`${BASE}${name}.glb`, 'container', (err, asset) => {
        if (err || !asset) {
          console.warn(`[models] ${name}.glb missing, using fallback`);
          resolve(this.fallback(name));
          return;
        }
        const res = asset.resource as pc.ContainerResource;
        const ent = res.instantiateRenderEntity();
        const parts: ModelPart[] = [];
        const rootInv = new pc.Mat4().copy(ent.getWorldTransform()).invert();
        const walk = (e: pc.GraphNode) => {
          const ee = e as pc.Entity;
          if (ee.render) {
            for (const mi of ee.render.meshInstances) {
              const mat = mi.material as pc.StandardMaterial;
              if (!(mat as unknown as { __ft?: boolean }).__ft) {
                if (mat.name === 'Glow') this.glowMats.add(mat);
                applyFog(mat);
                (mat as unknown as { __ft?: boolean }).__ft = true;
                mat.update();
              }
              const local = new pc.Mat4().mul2(rootInv, e.getWorldTransform());
              parts.push({ mesh: mi.mesh, material: mat, local, node: e.name });
            }
          }
          for (const c of e.children) walk(c);
        };
        walk(ent);
        resolve({ name, parts, container: res, fallback: false });
      });
    });
  }

  /** crude stand-ins so the game stays playable without the art pack */
  private fallback(name: string): Model {
    const device = this.app.graphicsDevice;
    const mat = new pc.StandardMaterial();
    const col = name.startsWith('pine') ? [0.2, 0.32, 0.22] : name.startsWith('aspen') ? [0.8, 0.6, 0.2] : name.startsWith('rock') ? [0.5, 0.5, 0.47] : [0.5, 0.4, 0.3];
    mat.diffuse = new pc.Color(col[0], col[1], col[2]);
    mat.gloss = 0.2;
    applyFog(mat);
    mat.update();
    let mesh: pc.Mesh;
    if (name.startsWith('pine') || name.startsWith('aspen') || name === 'snag') {
      const h = name.includes('young') ? 4 : name.includes('mid') ? 11 : name.includes('aspen') ? 10 : 18;
      mesh = pc.Mesh.fromGeometry(device, new pc.ConeGeometry({ baseRadius: h * 0.2, peakRadius: 0, height: h * 0.8, heightSegments: 1, capSegments: 8 }));
      const m: Model = { name, parts: [], fallback: true };
      const local = new pc.Mat4().setTranslate(0, h * 0.2 + h * 0.4, 0);
      m.parts.push({ mesh, material: mat, local, node: 'crown' });
      return m;
    }
    mesh = pc.Mesh.fromGeometry(device, new pc.BoxGeometry({ halfExtents: new pc.Vec3(0.5, 0.5, 0.5) }));
    return { name, parts: [{ mesh, material: mat, local: new pc.Mat4().setTranslate(0, 0.5, 0), node: 'box' }], fallback: true };
  }

  /** Create a plain entity hierarchy for a prop (non-instanced). */
  instantiate(name: string): pc.Entity {
    const m = this.get(name);
    if (m.container) return m.container.instantiateRenderEntity();
    const e = new pc.Entity(name);
    const mis = m.parts.map((p) => {
      const mi = new pc.MeshInstance(p.mesh, p.material);
      return mi;
    });
    const child = new pc.Entity('fb');
    const pos = new pc.Vec3();
    m.parts[0].local.getTranslation(pos);
    child.setLocalPosition(pos);
    child.addComponent('render', { meshInstances: mis });
    e.addChild(child);
    return e;
  }
}
