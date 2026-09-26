import type { HudState } from '../game/store';
import { LANDMARKS } from '../game/world/layout';
import { fmtTime } from '../game/park';
import { Icon } from './icons';

const SURFACE_NAMES: Record<string, string> = { dirt: '土路', grass: '草地', gravel: '碎石', rock: '岩石', mud: '泥地' };
const DIRS = ['北', '东北', '东', '东南', '南', '西南', '西', '西北'];
const GOALS = LANDMARKS.filter((l) => l.isGoal);
const EXTRAS = LANDMARKS.filter((l) => !l.isGoal && l.id !== 'camp');

function Compass({ heading, target }: { heading: number; target: HudState['nearestLandmark'] }) {
  // heading: camera yaw, 0 = north, + = east (radians)
  const ticks = [];
  for (let i = 0; i < 8; i++) {
    let d = (i * Math.PI) / 4 - heading;
    d = Math.atan2(Math.sin(d), Math.cos(d));
    if (Math.abs(d) > 1.35) continue;
    ticks.push(<div key={i} className={`compass-tick ${i % 2 === 0 ? 'major' : ''}`} style={{ left: `${50 + (d / 1.35) * 50}%` }}>{DIRS[i]}</div>);
  }
  let marker = null;
  if (target) {
    let d = target.bearing - heading;
    d = Math.atan2(Math.sin(d), Math.cos(d));
    const c = Math.max(-1.35, Math.min(1.35, d));
    marker = <div className={`compass-target ${Math.abs(d) > 1.35 ? 'edge' : ''}`} style={{ left: `${50 + (c / 1.35) * 50}%` }}>{target.name} · {Math.round(target.dist)} m</div>;
  }
  return <div className="compass glass"><div className="compass-strip">{ticks}{marker}<div className="compass-center" /></div></div>;
}

/** 270° speed ring (0–40 km/h) */
function Gauge({ kmh, gear, reverse }: { kmh: number; gear: string; reverse: boolean }) {
  const R = 62, C = 2 * Math.PI * R, arc = C * 0.75;
  const f = Math.min(1, kmh / 40);
  return (
    <div className="gauge glass">
      <svg viewBox="0 0 150 150">
        <defs>
          <linearGradient id="gg" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="#7fd3c4" /><stop offset="1" stopColor="#f2b24c" />
          </linearGradient>
        </defs>
        <circle cx="75" cy="75" r={R} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="7" strokeLinecap="round" strokeDasharray={`${arc} ${C}`} transform="rotate(135 75 75)" />
        <circle cx="75" cy="75" r={R} fill="none" stroke="url(#gg)" strokeWidth="7" strokeLinecap="round" strokeDasharray={`${arc * f} ${C}`} transform="rotate(135 75 75)" style={{ transition: 'stroke-dasharray 0.12s linear' }} />
        {[0, 10, 20, 30, 40].map((v) => {
          const a = ((135 + (v / 40) * 270) * Math.PI) / 180;
          return <text key={v} x={75 + Math.cos(a) * 48} y={75 + Math.sin(a) * 48 + 3} fill="rgba(246,242,233,0.4)" fontSize="8" textAnchor="middle" fontWeight="700">{v}</text>;
        })}
      </svg>
      <div className="speed num">{Math.round(kmh)}</div>
      <div className="unit">KM/H</div>
      <div className={`gear ${gear === 'low' ? 'low' : ''} ${reverse ? 'rev' : ''}`} title="Q 切换高/低档">{reverse ? 'R 倒车' : gear === 'low' ? 'L 低档' : 'H 高档'}</div>
    </div>
  );
}

export function Hud({ s }: { s: HudState }) {
  const hidden = s.screen === 'photo' || s.cinematic || s.demo;
  const now = performance.now();
  const toasts = s.toasts.filter((t) => t.until > now);
  const kmh = Math.abs(s.speedKmh);
  const extraDone = EXTRAS.filter((l) => s.photos[l.id]).length;
  const park = s.park;
  const parkOn = !!park?.running;
  const BeamIcon = s.beam === 2 ? Icon.beamHigh : s.beam === 1 ? Icon.beamLow : Icon.beamOff;
  return (
    <div className={`hud ${parkOn ? 'park-on' : ''}`}>
      {!hidden && (
        <>
          <Compass heading={s.heading} target={s.nearestLandmark} />
          <div className="objective glass">
            <div className="flag"><Icon.flag /></div>
            <div>
              <div className="objective-main">{s.objective}</div>
              {!s.hasToolbox && s.visited.length > 0 && !s.upgraded && <div className="objective-sub">可选：旧锯木场支路上有一个工具箱</div>}
              {s.hasToolbox && !s.upgraded && <div className="objective-sub">带着工具箱回营地，换装全地形轮胎</div>}
              <div className="progress-dots">
                {GOALS.map((l) => <div key={l.id} className={`dot ${s.visited.includes(l.id) ? 'on' : ''}`} title={l.name} />)}
                <span className="extra">探索点 {extraDone}/{EXTRAS.length}</span>
              </div>
            </div>
          </div>
          <div className="dash">
            <div className="dash-chips">
              <div className="chip glass on">{SURFACE_NAMES[s.surface] ?? ''}{s.upgraded ? ' · 全地形胎' : ''}</div>
              <div className={`chip glass ${s.beam ? 'warm' : ''}`} title="L 大灯 · B 远近光"><BeamIcon />{s.beam === 2 ? '远光' : s.beam === 1 ? '近光' : '大灯关'}<span className="kbd">L</span></div>
              <div className={`chip glass ${s.lowRange ? 'warm' : ''}`} title="Q 高/低档">{s.lowRange ? '低档 4L' : '高档 4H'}<span className="kbd">Q</span></div>
            </div>
            <Gauge kmh={kmh} gear={s.gear} reverse={s.reverse} />
          </div>
          {parkOn && park && (
            <div className="park-panel glass">
              <div className="eyebrow">训练场计时</div>
              <div className="park-time num">{fmtTime(park.time)}</div>
              <div className="park-row"><span>旗门</span><span className="num">{park.gate}/{park.gates}</span></div>
              <div className="park-row"><span>最佳</span><span className="num">{park.best != null ? fmtTime(park.best) : '—'}</span></div>
              <div className="park-gates">{Array.from({ length: park.gates }, (_, i) => <span key={i} className={i < park.gate ? 'on' : ''} />)}</div>
            </div>
          )}
          {s.prompt && <div className="prompt glass">{s.prompt}</div>}
          {s.hint && <div className="hint glass">{s.hint}</div>}
          {s.waterWarn && <div className="danger">水深危险 · 立即倒车</div>}
          {s.winch.mode !== 'off' && (
            <div className="winch-panel glass">
              <div className="winch-title"><Icon.winch />绞盘</div>
              {s.winch.mode === 'select' && (
                <>
                  <div>{s.winch.target ? `目标：${s.winch.target}` : s.winch.message}</div>
                  <div className="keys">转动镜头挑选锚点 · 左键 / F 连接 · E 取消</div>
                </>
              )}
              {s.winch.mode === 'attached' && (
                <>
                  <div className="tension"><div style={{ width: `${Math.min(100, (s.winch.tension / 11000) * 100)}%` }} /></div>
                  <div className="num">张力 {(s.winch.tension / 1000).toFixed(1)} kN · 绳长 {s.winch.length.toFixed(1)} m</div>
                  <div className="keys">按住左键 / F 收绳 · 可配合低档轻油门 · E 断开</div>
                </>
              )}
            </div>
          )}
          {s.resetHold > 0.02 && (
            <div className="reset-ring">
              <svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="16" className="bg" /><circle cx="20" cy="20" r="16" className="fg" style={{ strokeDasharray: `${s.resetHold * 100.5} 100.5` }} /></svg>
              <span>复位中…</span>
            </div>
          )}
        </>
      )}
      {s.cinematic && (
        <div className="cinematic">
          <div className="bar top" />
          <div className="bar bottom" />
          <div className="cine-text">
            <div className="cine-title">{s.cinematic.title}</div>
            <div className="cine-sub">{s.cinematic.subtitle}</div>
          </div>
        </div>
      )}
      {!s.demo && (
        <div className="toasts">
          {toasts.map((t) => <div key={t.id} className={`toast glass ${t.kind}`}><span className="bar" />{t.text}</div>)}
        </div>
      )}
      {s.settings.showFps && <div className="fps">{s.fps} fps</div>}
      {s.debug && <pre className="debug">{s.debug}</pre>}
      <div className="fade" style={{ opacity: s.fade }} />
    </div>
  );
}
