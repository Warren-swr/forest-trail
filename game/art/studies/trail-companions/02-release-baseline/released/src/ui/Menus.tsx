import { useState, type ReactNode } from 'react';
import type { HudState, Settings } from '../game/store';
import { ui } from '../game/boot';
import { LANDMARKS } from '../game/world/layout';
import { MapView } from './MapView';
import { storageAvailable } from '../game/save';
import { MUSIC } from '../game/audio';
import { fmtTime } from '../game/park';
import { VehicleSelect } from './VehicleSelect';
import { BrandMark, Icon } from './icons';

export const CONTROLS: [string[], string][] = [
  [['W', '↑'], '油门'],
  [['S', '↓'], '制动，停稳后倒车'],
  [['A', 'D'], '转向'],
  [['Space'], '手刹'],
  [['Q'], '切换高 / 低档'],
  [['L'], '大灯开 / 关'],
  [['B'], '远光 / 近光'],
  [['N'], '白天 / 夜晚（平滑过渡）'],
  [['右键拖动'], '环视（1.5 秒后自动回正）'],
  [['滚轮'], '镜头远近'],
  [['C'], '镜头回正'],
  [['E'], '绞盘：选锚点 / 断开'],
  [['左键', 'F'], '绞盘：连接；按住收绳'],
  [['F'], '记录风景点 / 拾取'],
  [['R 长按'], '复位到最近安全点'],
  [['M'], '地图'],
  [['P'], '摄影模式'],
  [['Esc'], '暂停菜单'],
];

const extras = LANDMARKS.filter((l) => !l.isGoal && l.id !== 'camp');

export function TitleScreen({ s }: { s: HudState }) {
  const cont = !s.firstRun;
  const [panel, setPanel] = useState<null | 'controls' | 'credits' | 'settings'>(null);
  const photos = extras.filter((l) => s.photos[l.id]).length;
  return (
    <div className="title-screen">
      <div className="title-left fade-in">
        <div className="wordmark"><BrandMark /><div className="title-name">Forest Trail</div></div>
        <div className="title-cn">松溪环线</div>
        <p className="title-desc">
          挑一辆老式四驱车，沿松溪环线穿过森林、浅溪和山脊，记录三处风景再回到营地。
          慢一点，看清路，松油、换低档，必要时用绞盘；也可以去训练场挑战弹坑和交叉轴，或在夜里打开大灯探索峡谷吊桥。
        </p>
        <div className="title-actions">
          <button className="btn primary" onClick={() => ui.start()}><Icon.play />{cont ? '继续旅程' : '开始旅程'}</button>
          <div className="row2">
            <button className="btn" onClick={() => ui.startDemo(false)}><Icon.camera />观看演示</button>
            <button className="btn rec" onClick={() => ui.startDemo(true)}><span className="dot" />录制演示视频</button>
          </div>
        </div>
        <div className="title-links">
          <button className="btn ghost small" onClick={() => setPanel('controls')}><Icon.keys />操作</button>
          <button className="btn ghost small" onClick={() => setPanel('settings')}><Icon.gear />设置</button>
          <button className="btn ghost small" onClick={() => setPanel('credits')}><Icon.music />制作名单</button>
          <button className="btn ghost small" onClick={() => ui.makeCover()}><Icon.mountain />生成封面</button>
        </div>
        {cont && (
          <div className="title-progress">
            <span>风景 <b>{s.visited.length}/3</b></span>
            <span>探索点 <b>{photos}/{extras.length}</b></span>
            {s.park?.best != null && <span>训练场最佳 <b className="num">{fmtTime(s.park.best)}</b></span>}
            {s.completed && <span>旅程已完成</span>}
          </div>
        )}
        {!storageAvailable && <div className="title-warn">本地存储不可用，进度只保存在本次会话中</div>}
      </div>
      <VehicleSelect s={s} />
      <div className="title-bottom">
        <div className="seg">
          <button className={s.timeOfDay === 'day' ? 'on' : ''} onClick={() => ui.setTimeOfDay('day', 4)}><Icon.sun />白天</button>
          <button className={s.timeOfDay === 'night' ? 'on' : ''} onClick={() => ui.setTimeOfDay('night', 4)}><Icon.moon />夜晚</button>
        </div>
        <span className="hint">Enter 开始 · 支持标准手柄</span>
      </div>
      {panel && (
        <div className="overlay" style={{ pointerEvents: 'auto' }} onClick={() => setPanel(null)}>
          <div className="panel" style={{ width: 'min(620px, 92vw)' }} onClick={(e) => e.stopPropagation()}>
            <div className="panel-title">{panel === 'controls' ? '操作说明' : panel === 'credits' ? '制作名单' : '画质与声音'}<button className="btn small" onClick={() => setPanel(null)}>关闭</button></div>
            {panel === 'controls' && <Controls />}
            {panel === 'credits' && <Credits />}
            {panel === 'settings' && <SettingsForm s={s} />}
          </div>
        </div>
      )}
    </div>
  );
}

function Keys({ keys }: { keys: string[] }) {
  return <>{keys.map((k) => <span key={k} className="kbd">{k}</span>)}</>;
}

export function Controls() {
  return (
    <table className="controls">
      <tbody>{CONTROLS.map(([k, v]) => <tr key={v}><td className="k"><Keys keys={k} /></td><td>{v}</td></tr>)}</tbody>
      <tfoot><tr><td colSpan={2} className="pad-note">手柄：RT 油门 · LT 制动/倒车 · 左摇杆转向 · 右摇杆环视 · B 手刹 · X 高低档 · Y 绞盘 · A 确认/收绳/记录 · 十字键上 大灯 · 十字键右 远近光 · LB+RB 按住复位 · View 地图 · Menu 暂停</td></tr></tfoot>
    </table>
  );
}

export function Credits() {
  const tracks = [...new Map(Object.values(MUSIC).flat().map((t) => [t.title, t])).values()];
  return (
    <div className="credits">
      <p>设计、编程、全部 3D 模型（Blender 程序化脚本）、地形、着色器与合成音效：Forest Trail 项目原创。</p>
      <div className="section-label">背景音乐</div>
      {tracks.map((t) => <div key={t.title} className="track"><span>“{t.title}”</span><span>Kevin MacLeod · incompetech.com</span></div>)}
      <p style={{ marginTop: 12 }}>音乐以 Creative Commons 署名 4.0 许可证发布：<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">creativecommons.org/licenses/by/4.0</a>。完整来源见 docs/CREDITS.md。</p>
      <p>TOYOTA 与 Land Cruiser 为丰田汽车公司商标，此处仅作外观致敬。</p>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return <label className="row"><span>{label}</span>{children}</label>;
}

function Slider({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return <input type="range" min={0} max={1} step={0.05} value={value} onChange={(e) => onChange(Number(e.target.value))} />;
}

function SettingsForm({ s }: { s: HudState }) {
  const set = (p: Partial<Settings>) => ui.setSettings(p);
  return (
    <div className="settings">
      <Row label="画质">
        <div className="seg">
          {(['high', 'medium', 'low'] as const).map((q) => (
            <button key={q} className={s.settings.quality === q ? 'on' : ''} onClick={() => set({ quality: q })}>{q === 'high' ? '高' : q === 'medium' ? '中' : '低'}</button>
          ))}
        </div>
      </Row>
      <Row label="总音量"><Slider value={s.settings.master} onChange={(v) => set({ master: v })} /></Row>
      <Row label="音效"><Slider value={s.settings.effects} onChange={(v) => set({ effects: v })} /></Row>
      <Row label="背景音乐"><Slider value={s.settings.music} onChange={(v) => set({ music: v })} /></Row>
      <Row label="悬挂冲击镜头反馈"><input type="checkbox" checked={s.settings.shake} onChange={(e) => set({ shake: e.target.checked })} /></Row>
      <Row label="细腻油门（键盘油门增长更慢）"><input type="checkbox" checked={s.settings.fineThrottle} onChange={(e) => set({ fineThrottle: e.target.checked })} /></Row>
      <Row label="显示帧率"><input type="checkbox" checked={s.settings.showFps} onChange={(e) => set({ showFps: e.target.checked })} /></Row>
    </div>
  );
}

type Tab = 'main' | 'vehicle' | 'records' | 'park' | 'controls' | 'settings' | 'credits';

export function PauseMenu({ s }: { s: HudState }) {
  const [tab, setTab] = useState<Tab>('main');
  const nav: [Tab, string, () => ReactNode][] = [
    ['main', '旅程', Icon.flag], ['vehicle', '车辆与涂装', Icon.car], ['records', '风景记录', Icon.book], ['park', '训练场', Icon.timer],
    ['controls', '操作说明', Icon.keys], ['settings', '画质与声音', Icon.gear], ['credits', '制作名单', Icon.music],
  ];
  return (
    <div className="overlay">
      <div className="panel pause">
        <div className="pause-nav">
          <div className="brand"><BrandMark size={22} />FOREST TRAIL</div>
          <button className="nav-item" onClick={() => ui.resume()}><Icon.play />继续</button>
          <div className="nav-sep" />
          {nav.map(([k, n, Ic]) => (
            <button key={k} className={`nav-item ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}><Ic />{n}</button>
          ))}
        </div>
        <div className="pause-body">
          {tab === 'main' && (
            <>
              <h2>{s.objective || '自由驾驶'}</h2>
              <div className="menu-grid">
                <button className="card btn" style={{ display: 'block', textAlign: 'left' }} onClick={() => ui.openMap()}><h3>地图</h3><p>地形、道路、风景点和探索点（M）</p></button>
                <button className="card btn" style={{ display: 'block', textAlign: 'left' }} onClick={() => ui.openPhoto()}><h3>摄影模式</h3><p>暂停时间，环绕取景，景深（P）</p></button>
                <button className="card btn" style={{ display: 'block', textAlign: 'left' }} onClick={() => ui.setTimeOfDay(s.timeOfDay === 'day' ? 'night' : 'day', 8)}><h3>{s.timeOfDay === 'day' ? '切换到夜晚' : '切换到白天'}</h3><p>夜晚记得打开大灯（L），开阔路段用远光（B）</p></button>
                <button className="card btn" style={{ display: 'block', textAlign: 'left' }} onClick={() => ui.returnToCamp()}><h3>回营地</h3><p>传送回松溪营地，进度保留</p></button>
              </div>
              <div className="section-label">当前车辆</div>
              <div className="card"><VehicleSelect s={s} inline /></div>
            </>
          )}
          {tab === 'vehicle' && (<><h2>车辆与涂装</h2><p style={{ color: 'var(--ink-2)', fontSize: 13, marginTop: -8 }}>随时可以换车，车辆会停在原地；绞盘会先断开。</p><VehicleSelect s={s} inline /></>)}
          {tab === 'records' && (<><h2>风景记录</h2><Records s={s} /></>)}
          {tab === 'park' && (<><h2>越野训练场</h2><ParkRecords s={s} /></>)}
          {tab === 'controls' && (<><h2>操作说明</h2><Controls /></>)}
          {tab === 'settings' && (<><h2>画质与声音</h2><SettingsForm s={s} /><button className="btn danger small" style={{ marginTop: 18 }} onClick={() => { if (confirm('清除全部进度并重新开始？')) ui.resetProgress(); }}>清除进度</button></>)}
          {tab === 'credits' && (<><h2>制作名单</h2><Credits /></>)}
        </div>
      </div>
    </div>
  );
}

function ParkRecords({ s }: { s: HudState }) {
  const p = s.park;
  return (
    <div>
      <p style={{ color: 'var(--ink-2)', fontSize: 13.5, lineHeight: 1.7, marginTop: -6 }}>
        训练场在营地南侧。穿过 TRAIL PARK 拱门开始计时，依次通过 7 对旗门：炮弹坑群、交叉轴、陡坡（低档）、侧倾坡、连续起伏、搓板路，最后是原木台阶和岩石花园，回到拱门停表。离开赛道或复位会取消本次计时。
      </p>
      <div className="specs" style={{ maxWidth: 420 }}>
        <div className="spec"><div className="k">最佳成绩</div><div className="v num">{p?.best != null ? fmtTime(p.best) : '—'}</div></div>
        <div className="spec"><div className="k">上一次</div><div className="v num">{p?.last != null ? fmtTime(p.last) : '—'}</div></div>
      </div>
    </div>
  );
}

export function Records({ s }: { s: HudState }) {
  const shown = (l: typeof LANDMARKS[number]) => l.isGoal || (l.id === 'camp' && !!s.photos[l.id]);
  return (
    <>
      <div className="records">
        {LANDMARKS.filter(shown).map((l) => <RecordCard key={l.id} s={s} l={l} />)}
      </div>
      <div className="section-label">探索点 · {extras.filter((l) => s.photos[l.id]).length}/{extras.length}</div>
      <div className="records">
        {extras.map((l) => <RecordCard key={l.id} s={s} l={l} />)}
      </div>
      <div className="record-meta">
        旅程用时 {Math.floor(s.journeyTime / 60)} 分 {Math.floor(s.journeyTime % 60)} 秒 · 工具箱 {s.hasToolbox ? '已找到' : '未找到'} · 全地形轮胎 {s.upgraded ? '已安装' : '未安装'}
      </div>
    </>
  );
}

function RecordCard({ s, l }: { s: HudState; l: typeof LANDMARKS[number] }) {
  const done = s.visited.includes(l.id) || !!s.photos[l.id] || (l.id === 'camp' && s.completed);
  return (
    <div className={`record ${done ? 'done' : ''}`}>
      {s.photos[l.id] ? <img src={s.photos[l.id]} alt={l.name} /> : <div className="no-photo">未记录</div>}
      <div className="record-name">{l.name}</div>
      <div className="record-sub">{done ? l.subtitle : '在地图上寻找它'}</div>
    </div>
  );
}

export function MapScreen({ s }: { s: HudState }) {
  return (
    <div className="overlay" onClick={() => ui.resume()}>
      <div className="panel map-panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-title"><span style={{ display: 'flex', gap: 10, alignItems: 'center' }}><Icon.map />松溪环线 · 地图</span><span className="close-hint">M / Esc 关闭</span></div>
        <MapView s={s} />
      </div>
    </div>
  );
}

export function PhotoOverlay() {
  return (
    <div className="photo-overlay">
      <div className="photo-bar glass">
        <span>摄影模式 · 右键拖动取景 · 滚轮远近</span>
        <button className="btn small" onClick={() => ui.savePhoto()}><Icon.camera />保存照片</button>
        <button className="btn small" onClick={() => ui.resume()}>退出 (P)</button>
      </div>
    </div>
  );
}

export function Journal({ s }: { s: HudState }) {
  return (
    <div className="overlay">
      <div className="panel journal">
        <div className="panel-title">旅程完成</div>
        <p className="journal-text">你带着三处风景回到了松溪营地。纪念车漆「松林绿」已解锁，可在暂停菜单的“车辆与涂装”里更换。森林依然开放：去训练场刷新纪录，或者等到夜里，开着大灯去赤岩峡谷走一趟吊桥。</p>
        <Records s={s} />
        <button className="btn primary" onClick={() => ui.closeJournal()}>继续自由探索</button>
      </div>
    </div>
  );
}
