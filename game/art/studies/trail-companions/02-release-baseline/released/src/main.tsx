import { createRoot } from 'react-dom/client';
import { App } from './ui/App';
import './ui/styles.css';

// StrictMode is intentionally not used: the 3D engine must be created once.
createRoot(document.getElementById('root')!).render(<App />);
