import { copyFileSync, mkdirSync } from 'node:fs';
mkdirSync('backend/static/dist', {recursive: true});
copyFileSync('node_modules/alpinejs/dist/cdn.min.js', 'backend/static/dist/alpine.min.js');
copyFileSync('backend/static/src/preview.js', 'backend/static/dist/preview.js');
