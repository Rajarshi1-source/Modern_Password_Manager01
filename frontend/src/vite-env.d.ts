/// <reference types="vite/client" />

// Ambient declarations for stylesheet side-effect imports.
//
// Vite/esbuild strip `import './x.css'` at build time, but `tsc`
// (`npm run type-check`) still resolves these specifiers and needs a type for
// them. Declaring the `*.css` wildcard module lets type-check pass for both
// local stylesheets (e.g. './OceanWaveDashboard.css') and package stylesheets
// (e.g. 'leaflet/dist/leaflet.css').
declare module '*.css';
