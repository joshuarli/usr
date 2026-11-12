# Owner preferences

Learned from the owner's corrections while rebuilding dashboards. Each rule fixes something the owner rejected.

## Trends and time

- Every quantity with history gets a time-series panel: gridlines, y-axis labels, a legend that prints each series' latest visible value, and a hover readout.
- Tiles carry a sparkline footer when history exists.
- Add a forward projection when the data supports one. Show the actual line, then dashed scenario lines past a "now" divider, with endpoint values in the legend. Label it illustrative and name its assumptions.
- One sticky time bar drives every history chart: range presets, drag across any chart to zoom, pan, zoom out, reset, keyboard shortcuts (`z`, `Esc`, `[`, `]`), and the window kept in the URL.
- Show totals for the visible window above the charts. Use finer buckets, such as monthly instead of quarterly, when the window narrows.
- When zoomed, scale the y-axis to the visible points plus their nearest neighbours, so lines crossing the edge are not clipped.
- Benchmark files: `~/d/stats/cloudflare/src/client/components/TimeBar.tsx` and `TimeChart.tsx`.

## Visual restraint

- No tinted cards, colored card borders, per-row badges, or category chips. Show state as a small dot plus colored text that names it. Separate rows with hairlines instead of boxing them.
- Put the status strip in one container, with tiles separated by hairlines.
- Keep weights light (500 for figures) and one accent hue; series colors belong to charts.
- Keep the sidebar narrow and quiet: set `--ui-side-width`, use short labels, and drop the footer. Widen the content column to use the space.

## Text must fit

Clipped or awkwardly wrapped text is a defect, not a style choice.

- Never truncate with an ellipsis or hidden overflow. Never squeeze a label until it wraps: set labels `nowrap` and let the grid drop a column instead.
- Stack a name over its detail rather than placing them side by side in a narrow cell.
- Clean provider and source strings for display in the data-preparation step: title-case all-caps text, shorten verbose phrasing, mask numbers. Keep the raw source untouched and fail a check if the raw forms leak through.
- Keep panel meta to a few words; move caveats into a note under the chart.
- Run [`text-fit.js`](text-fit.js) through `agent-browser eval` at 1440, 1024, and 390 pixels wide, and in zoomed or filtered states. It reports clipped elements and short labels that wrap.

## Modules and checks

- Derive time series in a pure, tested module. When they re-aggregate audited figures, assert in the data step that they sum to those figures exactly.
- Keep time-window logic (presets, clamping, pan, zoom out, ticks, URL parsing, window totals) in its own tested module.
- Verify range presets, drag-to-zoom with real mouse input (`agent-browser mouse down/move/up`; synthetic pointer events fail `setPointerCapture`), pan, zoom out, reset, and the URL window. Every chart and the window totals must follow the same window.
- The text-fit script must report nothing at every width and window checked.
