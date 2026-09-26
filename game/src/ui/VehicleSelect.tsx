import type { HudState } from '../game/store';
import { ui } from '../game/boot';
import { VEHICLES, VEHICLE_ORDER, type VehicleId } from '../game/config';
import { PAINTS } from '../game/render/vehicleView';
import { Icon } from './icons';

const STAT_NAMES: [keyof typeof VEHICLES.scout.ratings, string][] = [
  ['power', '动力'], ['speed', '速度'], ['grip', '抓地'], ['comfort', '舒适'], ['agility', '灵活'],
];

/** paints that need the journey to be completed */
const LOCKED_UNTIL_DONE = new Set(['pine']);

export function VehicleSelect({ s, inline = false }: { s: HudState; inline?: boolean }) {
  const id = s.vehicle;
  const spec = VEHICLES[id];
  const idx = VEHICLE_ORDER.indexOf(id);
  const go = (d: number) => ui.setVehicle(VEHICLE_ORDER[(idx + d + VEHICLE_ORDER.length) % VEHICLE_ORDER.length] as VehicleId);
  return (
    <div className={`vsel ${inline ? 'inline' : 'glass'} fade-in`}>
      <div className="eyebrow">选择车辆 · {idx + 1}/{VEHICLE_ORDER.length}</div>
      <div className="vsel-tabs">
        {VEHICLE_ORDER.map((v) => (
          <button key={v} className={`vsel-tab ${v === id ? 'on' : ''}`} onClick={() => ui.setVehicle(v)}>{VEHICLES[v].short}</button>
        ))}
      </div>
      <div className="vsel-head">
        <div>
          <div className="vsel-brand">{spec.brand}</div>
          <div className="vsel-name">{spec.name}</div>
        </div>
        <div className="vsel-arrows">
          <button className="btn small" aria-label="上一辆" onClick={() => go(-1)}><Icon.chevL /></button>
          <button className="btn small" aria-label="下一辆" onClick={() => go(1)}><Icon.chevR /></button>
        </div>
      </div>
      <div className="vsel-tag">{spec.tagline}</div>
      {inline && <button className="btn small" onClick={() => ui.openPhoto()}>近距离检视车辆</button>}
      {STAT_NAMES.map(([k, n]) => (
        <div key={k} className="stat">
          <span>{n}</span>
          <div className="stat-bar"><div style={{ width: `${Math.round(spec.ratings[k] * 100)}%` }} /></div>
          <span className="v num">{Math.round(spec.ratings[k] * 10)}</span>
        </div>
      ))}
      <div className="specs">
        <div className="spec"><div className="k">整备质量</div><div className="v num">{spec.mass.toLocaleString()} kg</div></div>
        <div className="spec"><div className="k">轴距 / 含装备车长</div><div className="v num">{spec.wheelBase.toFixed(2)} / {spec.bodyLength.toFixed(2)} m</div></div>
        <div className="spec"><div className="k">悬挂结构</div><div className="v">整体桥 · {spec.suspension === 'coil' ? '螺旋弹簧' : '钢板弹簧'}</div></div>
        <div className="spec"><div className="k">轮胎直径</div><div className="v num">{(spec.wheelRadius * 2).toFixed(2)} m</div></div>
        <div className="spec"><div className="k">最高速 高 / 低档</div><div className="v num">{spec.highMaxKmh.toFixed(0)} / {spec.lowMaxKmh.toFixed(0)} km/h</div></div>
        <div className="spec"><div className="k">低档牵引力</div><div className="v num">{(spec.lowPeak / 1000).toFixed(1)} kN</div></div>
        <div className="spec"><div className="k">涉水深度</div><div className="v num">{spec.waterFailDepth.toFixed(2)} m</div></div>
      </div>
      <div className="paints">
        <span className="paints-label">车漆</span>
        {spec.paints.map((k) => {
          const locked = LOCKED_UNTIL_DONE.has(k) && !s.completed;
          const p = PAINTS[k];
          return (
            <button key={k} className={`swatch ${s.paint === k ? 'on' : ''}`} disabled={locked} title={locked ? `${p.name}：完成旅程后解锁` : p.name}
              onClick={() => ui.setPaint(k)} style={{ background: p.swatch }}>{locked ? '🔒' : ''}</button>
          );
        })}
      </div>
    </div>
  );
}
