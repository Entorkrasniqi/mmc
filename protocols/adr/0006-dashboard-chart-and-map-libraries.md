# ADR 0006: Recharts for charts, d3-geo and Natural Earth for the map
- Status: Accepted
- Date: 2026-11-01

## Context
[ADR 0003](0003-local-web-app.md) chose React and Blueprint for the dashboard and noted that Blueprint has no charts or maps. The dashboard needs time series with alarm-limit bands and eclipse shading, and a ground track on a world map. The project runs on one machine and must work offline: no tile server, no API key, no network at run time.

## Options considered
Charts: (1) Recharts (MIT, React components, reference areas and lines built in); (2) uPlot (MIT, very fast, canvas, bands need custom drawing code); (3) Apache ECharts (Apache-2.0, very capable, about ten times the size).
Map: (1) Leaflet with map tiles (needs a tile server and a network); (2) an SVG map drawn with d3-geo (ISC) from land outlines shipped in the `world-atlas` package (Natural Earth, public domain); (3) a map component library with bundled vector tiles.

## Decision
Recharts for charts, and d3-geo with `world-atlas` `land-110m` (55 kB) for the map. Both licences are compatible with AGPL-3.0 (MIT, ISC; the data is public domain).

## Consequences
- A series is at most 600 to 2000 points (the API thins it), which Recharts draws without trouble; a much denser view would need uPlot or canvas.
- Bands and eclipse shading are `ReferenceArea`s. Recharts' range `Area` produced degenerate paths in version 3.10 with our data, so the min and max of a thinned bucket are drawn as two faint lines instead.
- The map is an equirectangular picture of the ground track with ground stations: no zooming, no day and night terminator, and the position itself is a spherical-Earth approximation. A later phase can swap the map component without touching the API.
- The dashboard's main JavaScript file is about 1 MB (304 kB gzipped); code splitting is not done.
