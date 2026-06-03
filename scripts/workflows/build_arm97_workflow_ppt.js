const fs = require("fs");
const path = require("path");
const PptxGenJS = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "../..");
const EXP = path.join(ROOT, "arm97_experiments/arm97_sobol512_segmented/mac");
const OUT_DIR = path.join(ROOT, "presentation_outputs");
const PPTX = path.join(OUT_DIR, "ARM97_SCM_UQ_Workflow_Demo10_Results.pptx");

fs.mkdirSync(OUT_DIR, { recursive: true });

function readCsv(file) {
  const text = fs.readFileSync(file, "utf8").trim();
  const lines = text.split(/\r?\n/);
  const header = lines.shift().split(",");
  return lines.map((line) => {
    const cols = line.split(",");
    const row = {};
    header.forEach((h, i) => (row[h] = cols[i]));
    return row;
  });
}

const metrics = readCsv(path.join(EXP, "metrics/arm97_sobol512_demo10_metrics.csv"));
const metricSummary = readCsv(path.join(EXP, "qc/demo10/demo10_metric_summary.csv"));
const status = readCsv(path.join(EXP, "design/experiment_run_status.csv"));

const successCount = status.filter((r) => r.status === "success").length;
const starts = status.map((r) => Number(r.start_epoch));
const ends = status.map((r) => Number(r.end_epoch));
const walls = status.map((r) => Number(r.wall_seconds)).sort((a, b) => a - b);
const elapsedMin = (Math.max(...ends) - Math.min(...starts)) / 60;
const medianWall = walls[Math.floor(walls.length / 2)];
const meanWall = walls.reduce((a, b) => a + b, 0) / walls.length;

const pptx = new PptxGenJS();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Codex";
pptx.company = "E3SM SCM UQ";
pptx.subject = "ARM97 SCM UQ workflow demo results";
pptx.title = "ARM97 SCM UQ Workflow Demo10 Results";
pptx.lang = "zh-CN";
pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "zh-CN",
};
pptx.defineLayout({ name: "CUSTOM_WIDE", width: 13.333, height: 7.5 });
pptx.layout = "CUSTOM_WIDE";

const C = {
  bg: "F6F5F0",
  ink: "172126",
  muted: "617078",
  teal: "2F6F7E",
  rust: "B24C3D",
  gold: "C18B2E",
  line: "D8DDD9",
  panel: "FFFFFF",
  dark: "112027",
  pale: "E8EFEF",
};

function slideBase(slide, eyebrow, title, subtitle) {
  slide.background = { color: C.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 13.333, h: 0.18, fill: { color: C.teal }, line: { color: C.teal } });
  slide.addText(eyebrow, { x: 0.52, y: 0.34, w: 3.5, h: 0.25, fontFace: "Aptos", fontSize: 8, bold: true, color: C.teal, charSpace: 1.2 });
  slide.addText(title, { x: 0.5, y: 0.62, w: 8.7, h: 0.5, fontFace: "Aptos Display", fontSize: 23, bold: true, color: C.ink, margin: 0 });
  if (subtitle) {
    slide.addText(subtitle, { x: 0.52, y: 1.13, w: 9.2, h: 0.32, fontSize: 10.5, color: C.muted, margin: 0 });
  }
  slide.addText("ARM97 SCM UQ workflow | local Mac demo", { x: 9.8, y: 7.08, w: 2.9, h: 0.22, fontSize: 7.5, color: "7C878B", align: "right" });
}

function pill(slide, text, x, y, w, color = C.teal) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 0.36, rectRadius: 0.05, fill: { color }, line: { color }, });
  slide.addText(text, { x: x + 0.08, y: y + 0.095, w: w - 0.16, h: 0.15, fontSize: 8, bold: true, color: "FFFFFF", align: "center", margin: 0 });
}

function card(slide, x, y, w, h, title, body, accent = C.teal) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.03, fill: { color: C.panel }, line: { color: C.line, width: 1 } });
  slide.addShape(pptx.ShapeType.rect, { x, y, w: 0.08, h, fill: { color: accent }, line: { color: accent } });
  slide.addText(title, { x: x + 0.22, y: y + 0.16, w: w - 0.35, h: 0.24, fontSize: 11, bold: true, color: C.ink, margin: 0 });
  slide.addText(body, { x: x + 0.22, y: y + 0.52, w: w - 0.35, h: h - 0.62, fontSize: 9, color: C.muted, breakLine: false, fit: "shrink", margin: 0.02, valign: "top" });
}

function stat(slide, label, value, x, y, w, color = C.teal) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 0.86, rectRadius: 0.03, fill: { color: "FFFFFF" }, line: { color: C.line } });
  slide.addText(value, { x: x + 0.12, y: y + 0.13, w: w - 0.24, h: 0.32, fontSize: 20, bold: true, color, margin: 0, align: "center" });
  slide.addText(label, { x: x + 0.12, y: y + 0.52, w: w - 0.24, h: 0.2, fontSize: 7.6, color: C.muted, margin: 0, align: "center" });
}

function addImage(slide, file, x, y, w, h) {
  slide.addImage({ path: path.join(ROOT, file), x, y, w, h });
}

function bullets(slide, items, x, y, w, h, color = C.ink) {
  slide.addText(items.map((t) => ({ text: t, options: { bullet: { type: "ul" } } })), {
    x, y, w, h, fontSize: 10.4, color, fit: "shrink", breakLine: false,
    paraSpaceAfterPt: 7, margin: 0.02,
  });
}

// 1
{
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.dark }, line: { color: C.dark } });
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 13.333, h: 0.18, fill: { color: C.gold }, line: { color: C.gold } });
  s.addText("E3SM SCM / ARM97 / PARAMETER UQ", { x: 0.72, y: 0.76, w: 5.5, h: 0.28, fontSize: 9, bold: true, color: "9FC9C9", charSpace: 1.4, margin: 0 });
  s.addText("ARM97 SCM UQ Workflow and Demo10 Results", { x: 0.68, y: 1.22, w: 11.6, h: 0.9, fontFace: "Aptos Display", fontSize: 32, bold: true, color: "FFFFFF", margin: 0, fit: "shrink" });
  s.addText("A local, scalable Sobol PPE workflow motivated by recent E3SM uncertainty quantification studies", { x: 0.72, y: 2.78, w: 10.4, h: 0.45, fontSize: 14, color: "D4E0DE", margin: 0 });
  const xs = [0.75, 3.05, 5.35, 7.65, 9.95];
  const labels = ["512 Sobol samples", "26,624 scripts", "Demo10 = 520 runs", "520/520 success", "QC PASS"];
  labels.forEach((l, i) => stat(s, l, i === 4 ? "PASS" : l.split(" ")[0], xs[i], 4.28, 1.85, i === 4 ? C.gold : "9FC9C9"));
  s.addText(`Generated ${new Date().toISOString().slice(0, 10)}`, { x: 0.76, y: 6.88, w: 3, h: 0.22, fontSize: 8, color: "9AA9AD", margin: 0 });
}

// 2
{
  const s = pptx.addSlide();
  slideBase(s, "MOTIVATION", "The two papers define the experiment logic", "Qian/Wuyin informs EAM parameter priorities; Jiang/Nathan informs the full UQ pipeline.");
  card(s, 0.7, 1.8, 5.7, 2.0, "Qian / Wuyin: Atmospheric PPE", "EAM responses involve multi-parameter interactions. One-at-a-time tuning can miss cloud, radiation, and precipitation tradeoffs. The priority families are CLUBB, ZM convection, cloud fraction, and ice sedimentation.", C.teal);
  card(s, 6.85, 1.8, 5.7, 2.0, "Jiang / Nathan: UQ Framework", "The recommended workflow is space-filling ensemble -> emulator -> global sensitivity analysis -> reduced parameter set -> calibration / prediction uncertainty. A full PPE is roughly 50 x the number of parameters.", C.rust);
  s.addShape(pptx.ShapeType.line, { x: 1.05, y: 4.5, w: 11.2, h: 0, line: { color: C.line, width: 2 } });
  ["Parameter prior", "Sobol PPE", "SCM ensemble", "Metrics", "Emulator / GSA", "Reduced set"].forEach((t, i) => {
    const x = 0.8 + i * 2.05;
    pill(s, t, x, 4.32, 1.55, i % 2 ? C.rust : C.teal);
    if (i < 5) s.addText("→", { x: x + 1.66, y: 4.37, w: 0.25, h: 0.2, fontSize: 13, color: C.muted, margin: 0 });
  });
  s.addText("Local objective: prove the run -> stitch -> metrics -> QC chain before scaling to 32, 64, and 512 samples.", { x: 1.15, y: 5.55, w: 10.9, h: 0.45, fontSize: 15, bold: true, color: C.ink, align: "center" });
}

// 3 workflow
{
  const s = pptx.addSlide();
  slideBase(s, "WORKFLOW", "End-to-end computational chain is now in place", "The core idea is to split each 26-day ARM97 output into 52 parallel 1.5-day segments.");
  const steps = [
    ["Parameter table", "10 EAM parameters\\nranges from papers and baseline"],
    ["Sobol design", "512 samples\\npower-of-two sample size"],
    ["Script generation", "52 scripts per sample\\n26,624 scripts total"],
    ["Local run", "MAX_JOBS=52\\nbatched by sample"],
    ["Stitch", "discard first 1 day\\nkeep final 0.5 day"],
    ["Metrics / QC", "scalar response table\\nQC plots + checks"],
  ];
  steps.forEach((d, i) => {
    const x = 0.55 + (i % 3) * 4.25;
    const y = 1.75 + Math.floor(i / 3) * 2.1;
    card(s, x, y, 3.65, 1.45, `${i + 1}. ${d[0]}`, d[1], i < 3 ? C.teal : C.rust);
    if (i !== 2 && i !== 5) s.addText("→", { x: x + 3.78, y: y + 0.55, w: 0.25, h: 0.3, fontSize: 18, color: C.muted, margin: 0 });
  });
  s.addText("Output: parameter-response table, one row per sample, with parameters + stitched 26-day scalar metrics.", { x: 1.0, y: 6.45, w: 11.2, h: 0.32, fontSize: 12, bold: true, color: C.ink, align: "center" });
}

// 4 design
{
  const s = pptx.addSlide();
  slideBase(s, "EXPERIMENT DESIGN", "Formal design: ARM97 Sobol-512 segmented PPE", "The local demo ran the first 10 samples; the full design has already been generated.");
  stat(s, "Sobol samples", "512", 0.75, 1.72, 1.75);
  stat(s, "segments / sample", "52", 2.75, 1.72, 1.75);
  stat(s, "total scripts", "26,624", 4.75, 1.72, 1.9);
  stat(s, "demo scripts", "520", 6.95, 1.72, 1.75);
  stat(s, "parameters", "10", 8.95, 1.72, 1.75);
  stat(s, "segment run", "36h", 10.95, 1.72, 1.75);
  const params = [
    "clubb_C1", "clubb_C8", "clubb_gamma_coef", "clubb_c_K10", "cldfrc_dp1",
    "cldfrc2m_rhmaxi", "ice_sed_ai", "zmconv_dmpdz", "zmconv_c0_lnd", "zmconv_c0_ocn"
  ];
  s.addText("Core parameter set", { x: 0.82, y: 3.05, w: 3.5, h: 0.3, fontSize: 13, bold: true, color: C.ink });
  params.forEach((p, i) => {
    const x = 0.85 + (i % 5) * 2.38;
    const y = 3.55 + Math.floor(i / 5) * 0.58;
    pill(s, p, x, y, 2.05, i % 2 ? C.rust : C.teal);
  });
  card(s, 0.8, 5.25, 11.8, 0.9, "Design rationale", "512 is a power of two, which is better aligned with Sobol balance properties than 500, while still preserving the Nathan-style scale of roughly 50 x the number of parameters.", C.gold);
}

// 5 runner
{
  const s = pptx.addSlide();
  slideBase(s, "RUNNER VALIDATION", "The local runner is now fixed and stable", "The demo exposed two workflow risks, both of which were corrected before the successful run.");
  card(s, 0.8, 1.65, 5.7, 1.55, "Issue 1: concurrency control failed", "The initial runner launched all 520 segments at once, creating excessive system load. It now batches by sample, with at most 52 active segments per batch.", C.rust);
  card(s, 6.85, 1.65, 5.7, 1.55, "Issue 2: background csh consumed stdin", "Background csh processes inherited the manifest stdin and caused early runner termination. The fix redirects each background task from /dev/null.", C.rust);
  stat(s, "controlled batch size", "52", 1.0, 4.05, 2.1, C.teal);
  stat(s, "demo success", "520/520", 3.55, 4.05, 2.1, C.teal);
  stat(s, "failed cases", "0", 6.1, 4.05, 2.1, C.teal);
  stat(s, "runner status", "stable", 8.65, 4.05, 2.1, C.gold);
  s.addText("Conclusion: the runner is ready for a 32/64-sample pilot; a full local 512-sample run is estimated at about two days.", { x: 1.0, y: 5.65, w: 11.0, h: 0.35, fontSize: 14, bold: true, color: C.ink, align: "center" });
}

// 6 runtime
{
  const s = pptx.addSlide();
  slideBase(s, "DEMO10 RUN", "Local run result for the first 10 samples", "All 520 segments succeeded; total wall time was about 51 minutes.");
  stat(s, "total elapsed", `${elapsedMin.toFixed(1)} min`, 0.7, 1.58, 2.1, C.teal);
  stat(s, "success", `${successCount}/520`, 3.1, 1.58, 2.1, C.teal);
  stat(s, "median segment", `${medianWall}s`, 5.5, 1.58, 2.1, C.teal);
  stat(s, "mean segment", `${meanWall.toFixed(0)}s`, 7.9, 1.58, 2.1, C.teal);
  stat(s, "full 512 estimate", "~43.5h", 10.3, 1.58, 2.1, C.gold);
  addImage(s, "arm97_experiments/arm97_sobol512_segmented/mac/qc/demo10/demo10_runtime_by_sample.png", 1.1, 3.0, 11.0, 3.25);
}

// 7 stitch
{
  const s = pptx.addSlide();
  slideBase(s, "STITCHING QC", "All 10 samples were reconstructed into 26-day outputs", "Each sample's 52 segments were stitched into a single NetCDF file.");
  stat(s, "stitched files", "10", 0.8, 1.55, 2.1, C.teal);
  stat(s, "time records / file", "1249", 3.25, 1.55, 2.1, C.teal);
  stat(s, "start", "1997-06-19", 5.7, 1.55, 2.1, C.teal);
  stat(s, "end", "1997-07-15", 8.15, 1.55, 2.1, C.teal);
  stat(s, "QC status", "PASS", 10.6, 1.55, 2.1, C.gold);
  const rows = [
    ["Run status", "520 success / 0 failed"],
    ["Time axis", "all files: 1249 records, 30-min cadence"],
    ["Numeric checks", "0 missing, 0 infinite values"],
    ["Physical sanity", "CLDTOT in [0,1], PRECT nonnegative"],
    ["Output products", "metrics table + parameter-response table + QC figures"],
  ];
  s.addTable(rows, {
    x: 1.2, y: 3.2, w: 10.9, h: 2.65,
    border: { type: "solid", color: C.line, pt: 0.8 },
    fill: { color: "FFFFFF" },
    color: C.ink,
    fontSize: 12,
    margin: 0.08,
    autoFit: false,
    valign: "mid",
    colW: [3.2, 7.7],
  });
}

// 8 metrics
{
  const s = pptx.addSlide();
  slideBase(s, "SCALAR METRICS", "Demo10 produced an analyzable response table", "Ten samples are not enough for formal sensitivity conclusions, but the response ranges are plausible and the workflow is scalable.");
  addImage(s, "arm97_experiments/arm97_sobol512_segmented/mac/qc/demo10/demo10_metric_min_mean_max.png", 0.75, 1.45, 7.35, 4.05);
  const tableRows = [["Metric", "Min", "Mean", "Max"]].concat(metricSummary.map((r) => [
    r.metric.replace("_mean", ""),
    Number(r.min).toFixed(3),
    Number(r.mean).toFixed(3),
    Number(r.max).toFixed(3),
  ]));
  s.addTable(tableRows, {
    x: 8.35, y: 1.5, w: 4.25, h: 4.9,
    border: { type: "solid", color: C.line, pt: 0.7 },
    fill: { color: "FFFFFF" },
    color: C.ink,
    fontSize: 9.3,
    margin: 0.05,
    bold: false,
    colW: [1.45, 0.9, 0.95, 0.95],
  });
}

// 9 distributions
{
  const s = pptx.addSlide();
  slideBase(s, "QC PLOTS", "Key metric distributions show no obvious anomalies", "Demo10 is used to validate the data chain and variable scales, not to make formal rankings.");
  addImage(s, "arm97_experiments/arm97_sobol512_segmented/mac/qc/demo10/demo10_metric_distributions.png", 0.75, 1.35, 11.9, 5.7);
}

// 10 scatter
{
  const s = pptx.addSlide();
  slideBase(s, "PARAMETER-RESPONSE QC", "Parameter-response scatter plots are generated correctly", "These plots validate data shape; formal GSA requires at least 32/64 samples, with 512 as the full design.");
  addImage(s, "arm97_experiments/arm97_sobol512_segmented/mac/qc/demo10/demo10_parameter_response_scatter.png", 0.35, 1.35, 12.65, 5.72);
}

// 11 next
{
  const s = pptx.addSlide();
  slideBase(s, "NEXT STEPS", "Scale the ensemble and move into UQ analysis", "The demo proves the engineering chain; the next goal is an ensemble large enough for inference.");
  card(s, 0.8, 1.55, 3.75, 1.3, "Immediate", "Run a 32-sample pilot, estimated at about 2.7 hours, reusing the same stitch, metrics, and QC scripts.", C.teal);
  card(s, 4.8, 1.55, 3.75, 1.3, "Analysis", "Run an initial emulator sanity check, parameter-response scatter review, and pilot-level sensitivity ranking.", C.rust);
  card(s, 8.8, 1.55, 3.75, 1.3, "Scale", "Confirm the 64-sample workflow, then decide whether to complete 512 locally or migrate to NERSC.", C.gold);
  bullets(s, [
    "Do not draw scientific conclusions from 10 samples; this is a workflow proof.",
    "32/64 samples can support preliminary ranking and anomaly detection.",
    "512 samples is the scale needed for a Nathan-style emulator / GSA workflow.",
    "The paper can emphasize a low-risk path from local pilot runs to NERSC-scale PPE."
  ], 1.15, 3.65, 11.0, 1.8);
  s.addText("Recommendation: run 32 samples next, then automate the same QC report for every ensemble size.", { x: 1.05, y: 6.25, w: 11.2, h: 0.34, fontSize: 14, bold: true, color: C.ink, align: "center" });
}

pptx.writeFile({ fileName: PPTX });
console.log(PPTX);
