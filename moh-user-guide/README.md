# MOH Performance Monitoring Dashboard — User Guide

The React/Vite source for the dashboard's user guide, which is served at `/guide/`.

## Local development

```sh
npm ci
npm run dev
```

## Building

```sh
npm ci
npm run lint
npm run build
```

The build writes to `superset/templates/superset/user_guide_app/`, and those files are committed. Rebuild and commit them whenever you change the guide.

## How it is served

`superset/moh_assets.py` serves the built files at `/guide/`. Every file requires sign-in, because the pictures show internal dashboard figures. The server needs no Node.js and no frontend rebuild, only a Superset restart when the Python changes.

## Updating content

- Text, tabs, and filters: `src/data/guideData.ts`. Other sections: `src/App.tsx`.
- Pictures: `public/images/guide/`. Each is 1600 × 1000 px, referenced by `imagePath`. File names are case-sensitive on Linux, so use lowercase `.png`.
- Numbered markers: set `annotations[].position` as percentages of the picture.

Before adding a picture, check it for patient information, usernames, and anything else sensitive. Pictures must come from this dashboard.

## Printing

Use **Print** and choose **Save as PDF**. Portrait orientation with background graphics enabled works best.
