import { useEffect, useRef, useSyncExternalStore } from 'react';
import { store, type HudState } from '../game/store';
import { startGame, ui } from '../game/boot';
import { Hud } from './Hud';
import { Journal, MapScreen, PauseMenu, PhotoOverlay, TitleScreen } from './Menus';
import { BrandMark } from './icons';

export function useStore() {
  return useSyncExternalStore(store.subscribe, store.get);
}

/** letterbox, captions and recording status while the demo director runs */
function DemoLayer({ s }: { s: HudState }) {
  const d = s.demo!;
  return (
    <div className="demo-layer">
      <div className="bar top" />
      <div className="bar bottom" />
      {d.caption && d.caption.startsWith('#') ? (
        <div className="demo-brand demo-caption show" key={d.caption}>
          <div className="n">{d.caption.slice(1)}</div>
          {d.sub && <div className="c">{d.sub}</div>}
        </div>
      ) : d.caption ? (
        <div className="demo-caption show" key={d.caption}>
          <div className="t">{d.caption}</div>
          {d.sub && <div className="s">{d.sub}</div>}
        </div>
      ) : null}
      <div className="demo-status glass">
        {d.recording && <span className="rec" />}
        <span>{d.recording ? '正在录制演示视频' : '演示模式'} · {Math.round(d.progress * 100)}%</span>
        <button className="btn small" onClick={() => ui.stopDemo()}>结束</button>
      </div>
      <div className="demo-progress" style={{ width: `${d.progress * 100}%` }} />
    </div>
  );
}

export function App() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const started = useRef(false);
  const s = useStore();
  useEffect(() => {
    if (started.current || !canvasRef.current) return;
    started.current = true;
    startGame(canvasRef.current);
  }, []);
  return (
    <div className="app">
      <canvas ref={canvasRef} className="game-canvas" tabIndex={0} />
      {s.screen === 'loading' && (
        <div className="loading">
          <div className="brand-mark"><BrandMark size={64} /></div>
          <div className="loading-title">FOREST TRAIL</div>
          <div className="loading-sub">松溪环线</div>
          <div className="loading-bar"><div style={{ width: `${Math.round(s.loading * 100)}%` }} /></div>
          <div className="loading-text">{s.loadingText}</div>
        </div>
      )}
      {s.screen !== 'loading' && s.screen !== 'title' && <Hud s={s} />}
      {s.screen === 'title' && !s.demo && <TitleScreen s={s} />}
      {s.screen === 'paused' && <PauseMenu s={s} />}
      {s.screen === 'map' && <MapScreen s={s} />}
      {s.screen === 'photo' && <PhotoOverlay />}
      {s.screen === 'journal' && <Journal s={s} />}
      {s.demo && <DemoLayer s={s} />}
    </div>
  );
}
