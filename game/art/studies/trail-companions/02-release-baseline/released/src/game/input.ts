// Keyboard, mouse and gamepad input collected into a per-frame snapshot.

export interface InputFrame {
  drive: number;
  steer: number;
  handbrake: boolean;
  digital: boolean;
  lookX: number;
  lookY: number;
  zoom: number;
  lookActive: boolean;
}

type Handler = (code: string) => void;

export class Input {
  keys = new Set<string>();
  private pressed = new Set<string>();
  private mouseDX = 0;
  private mouseDY = 0;
  private wheel = 0;
  rmb = false;
  lmb = false;
  lmbPressed = false;
  mouseX = 0;
  mouseY = 0;
  onKey: Handler[] = [];
  enabled = true;
  private padPrev: boolean[] = [];

  constructor(private el: HTMLElement) {
    window.addEventListener('keydown', this.kd);
    window.addEventListener('keyup', this.ku);
    window.addEventListener('blur', this.clear);
    el.addEventListener('mousedown', this.md);
    window.addEventListener('mouseup', this.mu);
    window.addEventListener('mousemove', this.mm);
    el.addEventListener('wheel', this.wh, { passive: false });
    el.addEventListener('contextmenu', (e) => e.preventDefault());
  }

  destroy() {
    window.removeEventListener('keydown', this.kd);
    window.removeEventListener('keyup', this.ku);
    window.removeEventListener('blur', this.clear);
    this.el.removeEventListener('mousedown', this.md);
    window.removeEventListener('mouseup', this.mu);
    window.removeEventListener('mousemove', this.mm);
    this.el.removeEventListener('wheel', this.wh);
  }

  private kd = (e: KeyboardEvent) => {
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA')) return;
    if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Tab'].includes(e.code)) e.preventDefault();
    if (!this.keys.has(e.code)) {
      this.pressed.add(e.code);
      for (const h of this.onKey) h(e.code);
    }
    this.keys.add(e.code);
  };
  private ku = (e: KeyboardEvent) => { this.keys.delete(e.code); };
  clear = () => { this.keys.clear(); this.rmb = false; this.lmb = false; };
  private md = (e: MouseEvent) => {
    if (e.button === 2) this.rmb = true;
    if (e.button === 0) { this.lmb = true; this.lmbPressed = true; }
  };
  private mu = (e: MouseEvent) => {
    if (e.button === 2) this.rmb = false;
    if (e.button === 0) this.lmb = false;
  };
  private mm = (e: MouseEvent) => {
    this.mouseX = e.clientX; this.mouseY = e.clientY;
    if (this.rmb) { this.mouseDX += e.movementX; this.mouseDY += e.movementY; }
  };
  private wh = (e: WheelEvent) => { e.preventDefault(); this.wheel += Math.sign(e.deltaY); };

  down(code: string) { return this.enabled && this.keys.has(code); }
  /** true once per physical press */
  took(code: string) {
    if (this.pressed.has(code)) { this.pressed.delete(code); return this.enabled; }
    return false;
  }
  takeClick() { const c = this.lmbPressed; this.lmbPressed = false; return c && this.enabled; }

  gamepad(): Gamepad | null {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (const p of pads) if (p && p.connected && p.mapping === 'standard') return p;
    return null;
  }

  /** edge-detected gamepad button */
  padPressed(i: number): boolean {
    const p = this.gamepad();
    const now = !!p?.buttons[i]?.pressed;
    const was = !!this.padPrev[i];
    this.padPrev[i] = now;
    return now && !was;
  }

  frame(): InputFrame {
    const k = (c: string) => this.down(c);
    let drive = (k('KeyW') || k('ArrowUp') ? 1 : 0) - (k('KeyS') || k('ArrowDown') ? 1 : 0);
    let steer = (k('KeyD') || k('ArrowRight') ? 1 : 0) - (k('KeyA') || k('ArrowLeft') ? 1 : 0);
    let handbrake = k('Space');
    let digital = true;
    let lookX = this.mouseDX * 0.004, lookY = this.mouseDY * 0.003;
    const lookActive = this.rmb;
    const pad = this.enabled ? this.gamepad() : null;
    if (pad) {
      const dz = (v: number, d = 0.12) => (Math.abs(v) < d ? 0 : (v - Math.sign(v) * d) / (1 - d));
      const rt = pad.buttons[7]?.value ?? 0, lt = pad.buttons[6]?.value ?? 0;
      const sx = dz(pad.axes[0] ?? 0);
      if (Math.abs(sx) > 0 || rt > 0.02 || lt > 0.02) {
        digital = false;
        steer = Math.sign(sx) * Math.pow(Math.abs(sx), 1.4);
        drive = rt - lt;
      }
      if (pad.buttons[1]?.pressed) handbrake = true;
      const lx = dz(pad.axes[2] ?? 0, 0.15), ly = dz(pad.axes[3] ?? 0, 0.15);
      lookX += lx * 0.05; lookY += ly * 0.03;
    }
    this.mouseDX = 0; this.mouseDY = 0;
    const zoom = this.wheel; this.wheel = 0;
    if (!this.enabled) { drive = 0; steer = 0; handbrake = false; }
    return { drive, steer, handbrake, digital, lookX, lookY, zoom, lookActive: lookActive || Math.abs(lookX) > 0.001 };
  }
}
