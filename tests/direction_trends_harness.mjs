// Print directionTrendRows for records read from stdin, using the production
// function from app.js, so the Python test can compare it with
// direction_trend_rows.
import { readFileSync } from "node:fs";

const source = readFileSync("site/assets/app.js", "utf8");
function fn(name) {
  const start = source.indexOf(`function ${name}(`);
  return source.slice(start, source.indexOf("\n}\n", start) + 2);
}
const constants = source.match(/const DIRECTION_TREND_WEEKS = .*;\nconst DISCOVERY_SOURCE = .*;/)[0];
const focusConstants = source.match(/const DIRECTION_RANKED = .*;\nconst DIRECTION_FOCUS_RECORDS = .*;/)[0];
const { directionTrendRows, discoveryAnchor, directionDisplay, directionFocusId, directionFocusRecords } = new Function(`${constants}\n${focusConstants}\n${fn("dayNumber")}\n${fn("discoveryAnchor")}\n${fn("signalIdentity")}\n${fn("directionTrendRows")}\n${fn("directionDisplay")}\n${fn("directionFocusId")}\n${fn("directionFocusRecords")}\nreturn { directionTrendRows, discoveryAnchor, directionDisplay, directionFocusId, directionFocusRecords };`)();
const { records, taxonomy, anchor, windows } = JSON.parse(readFileSync(0, "utf8"));
const models = windows.map((days) => directionTrendRows(records, taxonomy, anchor, days));
// The display order and focus for each window and group choice, and each
// direction's focus records, for the Python side to match.
const views = models.map((model) => ["", "__ranked", ...taxonomy.groups.map((group) => group.id)].map((group) => {
  const lines = directionDisplay(model, taxonomy, group);
  return { group, lines: lines.map((line) => (line.row ? line.row.id : `# ${line.heading} ${line.count}`)),
    focus: directionFocusId(model, lines.filter((line) => line.row).map((line) => line.row.id)) };
}));
const focus = models.map((model) => Object.fromEntries(model.rows.map((row) => [row.id,
  directionFocusRecords(records, row.id, anchor, model.windowDays).map((record) => record.name)])));
process.stdout.write(JSON.stringify({ anchor: discoveryAnchor(records), models, views, focus }));
