import { useEffect, useState } from 'react';
import { App } from './App.tsx';
import { Home } from './home/Home.tsx';
import { detectAutoConnect } from './lib/address.ts';

type Route = 'home' | 'app';

const read = (): Route | null => (location.hash.startsWith('#/app') ? 'app' : location.hash === '#/' ? 'home' : null);

/**
 * `#/` is the landing page, `#/app` the dashboard.
 * Opened from a Pi bridge or with ?pi=, go straight to the dashboard: those users want live data, not the intro.
 */
export function Root() {
  const [route, setRoute] = useState<Route | null>(read);
  const [checked, setChecked] = useState(route !== null);

  useEffect(() => {
    const onHash = () => setRoute(read());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    if (route !== null) return;
    let cancelled = false;
    void detectAutoConnect().then((found) => {
      if (cancelled) return;
      setRoute(found ? 'app' : 'home');
      setChecked(true);
    });
    return () => {
      cancelled = true;
    };
  }, [route]);

  if (!checked) return null;
  return (route ?? 'home') === 'app' ? <App /> : <Home />;
}
