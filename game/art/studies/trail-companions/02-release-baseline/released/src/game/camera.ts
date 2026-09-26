// Third-person follow camera with orbit, auto-recentre, obstruction handling,
// plus photo (free orbit) and cinematic shot modes.
import * as pc from 'playcanvas';
import type { Vehicle } from './physics/vehicle';
import type { Physics } from './physics/physics';
import type { InputFrame } from './input';
import { clamp, lerp } from './world/noise';

export type CamMode = 'follow' | 'photo' | 'shot' | 'title' | 'free';

const damp = (k: number, dt: number) => 1 - Math.exp(-k * dt);
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

export class FollowCamera {
  entity: pc.Entity;
  mode: CamMode = 'follow';
  yaw = 0;
  pitch = 0.26;
  dist = 7.2;
  zoomDist = 7.2;
  orbitYaw = 0;
  orbitPitch = 0;
  lastLook = -10;
  time = 0;
  obstructDist = 99;
  pos = new pc.Vec3();
  target = new pc.Vec3();
  private shotFrom = new pc.Vec3();
  private shotTo = new pc.Vec3();
  private shotT = 0;
  private shotLookFrom = new pc.Vec3();
  private shotLookTo = new pc.Vec3();
  shakeEnabled = true;
  winchView = false;
  private tmp = new pc.Vec3();
  private fwd = new pc.Vec3();

  constructor(public app: pc.AppBase, private phys: Physics) {
    this.entity = new pc.Entity('camera');
    this.entity.addComponent('camera', {
      fov: 55,
      nearClip: 0.2,
      farClip: 1500,
      clearColor: new pc.Color(0.6, 0.68, 0.7),
    });
    // the sky is drawn by the Environment dome, not the engine skybox
    const cam = this.entity.camera!;
    cam.layers = cam.layers.filter((id) => id !== pc.LAYERID_SKYBOX);
    app.root.addChild(this.entity);
  }

  recenter() {
    this.orbitYaw = 0;
    this.orbitPitch = 0;
    this.lastLook = -10;
  }

  snap(v: Vehicle, pos: pc.Vec3) {
    this.yaw = v.yaw;
    this.recenter();
    this.update(v, pos, 1, null, true);
  }

  playShot(from: [number, number, number], to: [number, number, number]) {
    this.shotFrom.copy(this.pos);
    this.shotLookFrom.copy(this.target);
    this.shotTo.set(from[0], from[1], from[2]);
    this.shotLookTo.set(to[0], to[1], to[2]);
    this.shotT = 0;
    this.mode = 'shot';
  }

  endShot() {
    this.mode = 'follow';
  }

  /** vehicle position is the interpolated render position */
  update(v: Vehicle, vpos: pc.Vec3, dt: number, inp: InputFrame | null, snap = false) {
    this.time += dt;
    const cam = this.entity;
    // camera placed externally (demo director, cover shot, debug)
    if (this.mode === 'free') return;
    if (this.mode === 'title') {
      // slow showcase orbit centred on the car (it sits between the title panels)
      const a = v.yaw + 0.9 + this.time * 0.09;
      const d = 7.4;
      const px = vpos.x + Math.sin(a) * d, pz = vpos.z + Math.cos(a) * d;
      const py = Math.max(vpos.y + 1.7, this.phys.terrain.heightAt(px, pz) + 0.8);
      const want = new pc.Vec3(px, py, pz);
      if (snap) this.pos.copy(want); else this.pos.lerp(this.pos, want, damp(3, dt));
      this.target.set(vpos.x, vpos.y + 0.75, vpos.z);
      cam.setPosition(this.pos);
      cam.lookAt(this.target);
      return;
    }
    if (this.mode === 'shot') {
      this.shotT = Math.min(1, this.shotT + dt / 1.8);
      const t = this.shotT * this.shotT * (3 - 2 * this.shotT);
      this.pos.lerp(this.shotFrom, this.shotTo, t);
      this.target.lerp(this.shotLookFrom, this.shotLookTo, t);
      cam.setPosition(this.pos);
      cam.lookAt(this.target);
      return;
    }
    if (inp) {
      if (inp.zoom) this.zoomDist = clamp(this.zoomDist + inp.zoom * 0.8, 4.5, 14);
      if (inp.lookActive) {
        this.orbitYaw = wrap(this.orbitYaw - inp.lookX * 1.0);
        this.orbitPitch = clamp(this.orbitPitch + inp.lookY, -0.2, 0.9);
        this.lastLook = this.time;
      }
    }
    const photo = this.mode === 'photo';
    // auto recentre after 1.5 s without look input (not in photo/winch)
    if (!photo && !this.winchView && this.time - this.lastLook > 1.5) {
      const k = damp(1.6, dt);
      this.orbitYaw = lerp(this.orbitYaw, 0, k);
      this.orbitPitch = lerp(this.orbitPitch, 0, k);
    }
    // heading follow: body heading, turned around when reversing fast
    const heading = v.yaw;
    const followK = snap ? 1 : damp(v.speed > 1 ? 3.2 : 1.6, dt);
    this.yaw = wrap(this.yaw + wrap(heading - this.yaw) * followK);
    const speed = Math.abs(v.forwardSpeed);
    const baseDist = this.winchView ? Math.max(this.zoomDist, 10) : this.zoomDist + Math.min(speed * 0.08, 1.2);
    const basePitch = (this.winchView ? 0.5 : 0.28) + this.orbitPitch;
    const yaw = this.yaw + this.orbitYaw;

    // look target: slightly ahead of the car
    this.fwd.set(-Math.sin(heading), 0, -Math.cos(heading));
    const ahead = photo ? 0 : 3 + Math.min(speed * 0.2, 2.5);
    const tgt = this.tmp.set(vpos.x + this.fwd.x * ahead, vpos.y + 0.9, vpos.z + this.fwd.z * ahead);
    if (snap) this.target.copy(tgt);
    else this.target.lerp(this.target, tgt, damp(9, dt));

    const dirX = Math.sin(yaw) * Math.cos(basePitch);
    const dirY = Math.sin(basePitch);
    const dirZ = Math.cos(yaw) * Math.cos(basePitch);
    // obstruction: pull in quickly, release slowly
    const ox = vpos.x, oy = vpos.y + 1.25, oz = vpos.z;
    const hit = this.phys.castStatic(ox, oy, oz, dirX, dirY, dirZ, baseDist + 0.5, { x: 0, y: 0, z: 0 });
    let allowed = hit >= 0 ? Math.max(2.2, hit - 0.6) : baseDist;
    // terrain along the ray
    for (let d = 1; d <= baseDist; d += 0.5) {
      const px = ox + dirX * d, py = oy + dirY * d, pz = oz + dirZ * d;
      if (py < this.phys.terrain.heightAt(px, pz) + 0.35) { allowed = Math.min(allowed, Math.max(2.2, d - 0.5)); break; }
    }
    if (allowed < this.obstructDist || snap) this.obstructDist = lerp(this.obstructDist, allowed, snap ? 1 : damp(14, dt));
    else this.obstructDist = lerp(this.obstructDist, allowed, damp(1.2, dt));
    this.dist = Math.min(baseDist, this.obstructDist);

    const px = ox + dirX * this.dist;
    let py = oy + dirY * this.dist;
    const pz = oz + dirZ * this.dist;
    py = Math.max(py, this.phys.terrain.heightAt(px, pz) + 0.6);
    const want = new pc.Vec3(px, py, pz);
    if (snap) this.pos.copy(want);
    else this.pos.lerp(this.pos, want, damp(photo ? 6 : 10, dt));
    // gentle shake on hard impacts (optional)
    const shake = this.shakeEnabled ? v.impact * 0.05 : 0;
    cam.setPosition(this.pos.x, this.pos.y + (shake ? Math.sin(this.time * 55) * shake : 0), this.pos.z);
    cam.lookAt(this.target);
  }
}
