import fs from 'fs';
import path from 'path';
import { TARGET } from './env';

export interface PageDef {
  id: string;
  path: string;
  critical: boolean;
  tv?: boolean;
}

export const STATIC_PAGES: PageDef[] = [
  { id: 'login', path: '/login/', critical: true },
  { id: 'welcome', path: '/superset/welcome/', critical: true },
  { id: 'home', path: '/', critical: true },
  { id: 'dashlist', path: '/dashboard/list/', critical: true },
  { id: 'chartlist', path: '/chart/list/', critical: false },
  { id: 'guide', path: '/guide/', critical: false },
  { id: 'feedback', path: '/feedback/', critical: true },
  { id: 'aichat', path: '/ai-chat/', critical: false },
  { id: 'tv', path: '/moh-static/tv', critical: true, tv: true },
  { id: 'tv-all', path: '/moh-static/tv/group/all', critical: false, tv: true },
  { id: '404', path: '/nonexistent-page/', critical: false },
];

/** Tabs (1-based) the fast gate samples on every dashboard. */
const GATE_TABS = (process.env.MOH_UI_GATE_TABS || '1,4,5')
  .split(',')
  .map(Number);

export function discoveredDashboards(): { id: number; title: string; tabs: string[] }[] {
  const f = path.join(__dirname, '..', '.auth', `${TARGET}.dashboards.json`);
  try {
    return JSON.parse(fs.readFileSync(f, 'utf8'));
  } catch {
    return [];
  }
}

/** Every page to test. Dashboards are discovered at login (all, plus tabs). */
export function allPages(): PageDef[] {
  const dash: PageDef[] = [];
  for (const d of discoveredDashboards()) {
    dash.push({ id: `dash${d.id}`, path: `/superset/dashboard/${d.id}/`, critical: true });
    d.tabs.forEach((t, i) =>
      dash.push({
        id: `dash${d.id}-tab${i + 1}`,
        path: `/superset/dashboard/${d.id}/#${t}`,
        // gate profile samples a few tabs per dashboard (1-based, env-overridable);
        // the full profile covers all of them
        critical: GATE_TABS.includes(i + 1),
      }),
    );
  }
  return [...STATIC_PAGES, ...dash];
}

export const PROFILE = process.env.MOH_UI_PROFILE || 'full';

/** gate = fast deploy check (critical pages, 3 widths); full = everything. */
export function viewportsFor(p: PageDef): [number, number][] {
  if (PROFILE === 'gate') return [[375, 667], [768, 1024], [1440, 900]];
  const v: [number, number][] = [
    [320, 640], [375, 667], [768, 1024], [1024, 768], [1440, 900], [1920, 1080],
  ];
  if (p.tv) v.push([3840, 2160]);
  return v;
}

export function pagesForProfile(): PageDef[] {
  const all = allPages();
  return PROFILE === 'gate' ? all.filter(p => p.critical) : all;
}
