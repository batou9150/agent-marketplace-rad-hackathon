"use strict";
const PptxGenJS = require("/opt/homebrew/lib/node_modules/pptxgenjs");

// ───────── Tokens SFEIR (The Sharp Artisan v2026.1) ─────────
const CUIVRE = "845400", CUIVRE_POLI = "E5A040", CUIVRE_CLAIR = "FFB95C", CUIVRE_PROFOND = "5D3A00";
const NOIR = "000000", CHARCOAL = "1B1B1B", BLANC_CRAIE = "F9F9F9";
const CRAIE_1 = "F3F3F3", CRAIE_2 = "EEEEEE", BROUILLARD = "DADADA";
const ON_SURFACE_VARIANT = "514536", TEXT_ON_DARK = "F1F1F1", WHITE = "FFFFFF";
const OUTLINE = "847564";
const ERROR = "BA1A1A";
const SOUVERAIN = "2C5F8A", SOUVERAIN_DARK = "142D45", SOUVERAIN_LIGHT = "D4E4F2";
const EMERAUDE_LIGHT = "C8F5D6", EMERAUDE_DARK = "0D5A2E";
const INDIGO_LIGHT = "E9DDFF", INDIGO_DARK = "23005C";
const TERRE_DARK = "3D2100";
const RAMP_OCRE = [
  { fill: "FFF0D6", text: TERRE_DARK },
  { fill: "F2C878", text: TERRE_DARK },
  { fill: "E5A040", text: TERRE_DARK },
];

const TITLE_FONT = "Epilogue", BODY_FONT = "Epilogue";
const LABEL_FONT = "Space Grotesk", MONO_FONT = "JetBrains Mono";

const ASSETS = "/Users/baptistepirault/.claude/skills/sfeir-brand-guidelines/assets";
const LOGO_WHITE = ASSETS + "/logo-sfeir-white.png";
const LOGO_GREY = ASSETS + "/logo-sfeir-grey.png";

const M = 0.5, W = 9.0;
const BODY_TOP = 1.84, BODY_END = 5.00;
const T = { margin: 0, valign: "top" };
const TOTAL = 18;

// ───────── Helpers ─────────
function cols(n, g = 0.24) {
  const w = (W - (n - 1) * g) / n;
  return Array.from({ length: n }, (_, i) => ({ x: M + i * (w + g), w }));
}

const LINE_H = 0.18;

function wrapLines(text, w, size, bold = false) {
  const perChar = (bold ? 0.62 : 0.55) * size / 72;
  const perLine = Math.max(1, Math.floor(w / perChar));
  let lines = 0;
  for (const seg of String(text).split("\n")) {
    let l = 1, used = 0;
    for (const word of seg.split(/\s+/).filter(Boolean)) {
      const need = word.length + (used ? 1 : 0);
      if (used + need > perLine && used > 0) { l++; used = word.length; }
      else used += need;
    }
    lines += l;
  }
  return lines;
}

function box(s, o) {
  const { x, y, w, h, fill = CRAIE_1, accent, label, title, body, mono,
          titleColor = CHARCOAL, bodyColor = ON_SURFACE_VARIANT, labelColor } = o;
  const LBL = 7.5, TTL = 10.5, BDY = 9;
  s.addShape("rect", { x, y, w, h, fill: { color: fill }, line: { type: "none" } });
  if (accent) s.addShape("rect", { x, y, w: 0.04, h, fill: { color: accent }, line: { type: "none" } });
  const ix = x + 0.15, iw = w - 0.30;
  let cy = y + 0.09;
  if (label) {
    const n = wrapLines(label, iw, LBL);
    s.addText(label, { ...T, x: ix, y: cy, w: iw, h: 0.16 * n,
      fontFace: LABEL_FONT, fontSize: LBL, color: labelColor || accent || CUIVRE, charSpacing: 1.2 });
    cy += 0.19 * n + 0.02;
  }
  if (title) {
    const n = wrapLines(title, iw, TTL, true);
    s.addText(title, { ...T, x: ix, y: cy, w: iw, h: 0.20 * n,
      fontFace: TITLE_FONT, fontSize: TTL, bold: true, color: titleColor, charSpacing: 0 });
    cy += 0.20 * n + 0.04;
  }
  const monoH = mono ? 0.22 : 0;
  if (body) {
    const avail = y + h - cy - 0.09 - monoH;
    const need = wrapLines(body, iw, BDY) * LINE_H;
    if (need > avail + 0.01) {
      throw new Error("box: corps trop long de " + (need - avail).toFixed(2) + " in (titre « " + title + " »).");
    }
    s.addText(body, { ...T, x: ix, y: cy, w: iw, h: avail,
      fontFace: BODY_FONT, fontSize: BDY, color: bodyColor, lineSpacingMultiple: 1.15 });
  }
  if (mono) {
    s.addText(mono, { ...T, x: ix, y: y + h - 0.09 - 0.18, w: iw, h: 0.18,
      fontFace: MONO_FONT, fontSize: 8.5, color: accent || CUIVRE, charSpacing: 0.2 });
  }
}

function system(s, { x, y, w, h, fill, label, name, sub }) {
  s.addShape("rect", { x, y, w, h, fill: { color: fill }, line: { type: "none" } });
  s.addShape("rect", { x, y, w, h: 0.03, fill: { color: CUIVRE_POLI }, line: { type: "none" } });
  const cy = y + h / 2 - 0.34;
  s.addText(label, { ...T, x, y: cy, w, h: 0.16, align: "center",
    fontFace: LABEL_FONT, fontSize: 7.5, color: WHITE, charSpacing: 1.2 });
  s.addText(name, { ...T, x, y: cy + 0.20, w, h: 0.48, align: "center",
    fontFace: TITLE_FONT, fontSize: 12, bold: true, color: WHITE, charSpacing: 0 });
  if (sub) s.addText(sub, { ...T, x, y: cy + 0.72, w, h: 0.16, align: "center",
    fontFace: MONO_FONT, fontSize: 8, color: SOUVERAIN_LIGHT });
}

function arrow(s, { x, y, x2, y2, color = CUIVRE, dash = false, back = false, width = 1.25 }) {
  const o = { x: Math.min(x, x2), y: Math.min(y, y2), w: Math.abs(x2 - x), h: Math.abs(y2 - y),
    line: { color, width, dashType: dash ? "dash" : "solid",
            endArrowType: "triangle", beginArrowType: back ? "triangle" : "none" } };
  if (x2 < x) o.flipH = true;
  if (y2 < y) o.flipV = true;
  s.addShape("line", o);
}

function laneLabel(s, { x, y, w, color, text }) {
  s.addShape("rect", { x, y: y + 0.07, w: 0.30, h: 0.03, fill: { color }, line: { type: "none" } });
  s.addText(text, { ...T, x: x + 0.40, y, w: w - 0.40, h: 0.16,
    fontFace: LABEL_FONT, fontSize: 8, color, charSpacing: 1.2 });
}

function caption(s, { y, h = 0.95, label, text }) {
  const iw = W - 0.44;
  const need = wrapLines(text, iw, 10.5) * 0.215;
  if (need > h - 0.44 + 0.01) {
    throw new Error("caption: texte trop long de " + (need - h + 0.44).toFixed(2) + " in.");
  }
  s.addShape("rect", { x: M, y, w: W, h, fill: { color: NOIR }, line: { type: "none" } });
  s.addText(label, { ...T, x: M + 0.22, y: y + 0.11, w: iw, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: CUIVRE_CLAIR, charSpacing: 1.2 });
  s.addText(text, { ...T, x: M + 0.22, y: y + 0.34, w: iw, h: h - 0.44,
    fontFace: BODY_FONT, fontSize: 10.5, color: TEXT_ON_DARK, lineSpacingMultiple: 1.2 });
}

// Titre composé à la main : la période cuivre ne doit jamais être orpheline.
function titleRuns(lines, accent) {
  const runs = [];
  lines.forEach((ln, i) => {
    const last = i === lines.length - 1;
    const dot = last && ln.endsWith(".");
    const base = dot ? ln.slice(0, -1) : ln;
    runs.push({ text: base, options: { breakLine: !last } });
    if (dot) runs.push({ text: ".", options: { color: accent, breakLine: false } });
  });
  return runs;
}

function chrome(s, n, dark) {
  s.addImage({ path: dark ? LOGO_WHITE : LOGO_GREY, x: 0.50, y: 5.15, w: 0.6, h: 0.2 });
  s.addText(n + " / " + TOTAL, { ...T, x: 8.60, y: 5.16, w: 0.95, h: 0.24, align: "right",
    fontFace: LABEL_FONT, fontSize: 8, color: dark ? OUTLINE : ON_SURFACE_VARIANT, charSpacing: 1.2 });
}

function header(s, { eyebrow, title, chapeau, rule = true, n }) {
  s.background = { color: BLANC_CRAIE };
  s.addText(eyebrow, { ...T, x: M, y: 0.32, w: W, h: 0.20,
    fontFace: LABEL_FONT, fontSize: 10, color: CUIVRE, charSpacing: 1.5 });
  s.addText(titleRuns([title], CUIVRE), { ...T, x: M, y: 0.56, w: W, h: 0.52,
    fontFace: TITLE_FONT, fontSize: 26, bold: true, color: CHARCOAL, charSpacing: 0 });
  if (chapeau) s.addText(chapeau, { ...T, x: M, y: 1.08, w: W, h: 0.44,
    fontFace: BODY_FONT, fontSize: 11, color: ON_SURFACE_VARIANT, lineSpacingMultiple: 1.2 });
  if (rule) s.addShape("rect", { x: M, y: 1.72, w: W, h: 0.012, fill: { color: BROUILLARD }, line: { type: "none" } });
  chrome(s, n, false);
}

function divider(s, { num, section, lines, lede, n }) {
  s.background = { color: NOIR };
  s.addShape("rect", { x: M, y: 0.62, w: 0.40, h: 0.015, fill: { color: CUIVRE_CLAIR }, line: { type: "none" } });
  s.addText("— " + num + " · " + section, { ...T, x: 1.02, y: 0.53, w: 6, h: 0.22,
    fontFace: LABEL_FONT, fontSize: 11, color: CUIVRE_CLAIR, charSpacing: 1.8 });
  s.addText(titleRuns(lines, CUIVRE_CLAIR), { ...T, x: M, y: 1.80, w: 9, h: 1.60,
    fontFace: TITLE_FONT, fontSize: 46, bold: true, color: WHITE, charSpacing: 0, lineSpacingMultiple: 1.05 });
  if (lede) s.addText(lede, { ...T, x: M, y: 3.90, w: 6.4, h: 0.6,
    fontFace: BODY_FONT, fontSize: 14, color: "BFBFBF", lineSpacingMultiple: 1.25 });
  chrome(s, n, true);
}

// ───────── Deck ─────────
const p = new PptxGenJS();
p.defineLayout({ name: "SFEIR16x9", width: 10, height: 5.625 });
p.layout = "SFEIR16x9";
p.author = "SFEIR";
p.company = "SFEIR";
p.title = "Note COMEX — Vibe Guard";

// ── 1 · Couverture ────────────────────────────────────────────────
{
  const s = p.addSlide();
  s.background = { color: NOIR };
  s.addText("SFEIR · NOTE COMEX · SEPTEMBRE 2026", { ...T, x: M, y: 0.50, w: 8, h: 0.22,
    fontFace: LABEL_FONT, fontSize: 10, color: CUIVRE_CLAIR, charSpacing: 1.6 });
  s.addText(titleRuns(["Industrialiser", "le vibe coding."], CUIVRE_CLAIR),
    { ...T, x: M, y: 1.95, w: 8, h: 1.55,
      fontFace: TITLE_FONT, fontSize: 52, bold: true, color: WHITE, charSpacing: 0, lineSpacingMultiple: 1.02 });
  s.addText("Vibe Guard · agent d'audit et de remédiation natif Google Cloud,\npackagé pour la Marketplace et la Gemini Enterprise App du client.",
    { ...T, x: M, y: 3.88, w: 5.9, h: 0.6, fontFace: BODY_FONT, fontSize: 12, color: TEXT_ON_DARK, lineSpacingMultiple: 1.3 });
  s.addText("COMEX SFEIR · 18.09.2026\nCTO & ED · Alliances & Partenariats",
    { ...T, x: 7.0, y: 4.42, w: 2.5, h: 0.5, align: "right",
      fontFace: BODY_FONT, fontSize: 11, color: TEXT_ON_DARK, lineSpacingMultiple: 1.3 });
  chrome(s, 1, true);
}

// ── 2 · Déroulé ───────────────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 2, eyebrow: "— DÉROULÉ", title: "Quatre temps, trois arbitrages." });
  const rows = [
    ["01", "Le marché", "CONSTAT"],
    ["02", "L'actif Vibe Guard", "PRODUIT"],
    ["03", "Le modèle économique", "REVENUS"],
    ["04", "Exécution et risques", "PLAN"],
    ["—", "Décisions soumises au vote", "ARBITRAGE"],
  ];
  const Y = 2.20, H = 0.40;
  rows.forEach((r, i) => {
    const y = Y + i * H;
    const last = i === rows.length - 1;
    s.addShape("rect", { x: M, y, w: W, h: H - 0.04,
      fill: { color: last ? CRAIE_2 : (i % 2 ? CRAIE_1 : WHITE) }, line: { type: "none" } });
    s.addText(r[0], { ...T, x: M + 0.22, y: y + 0.09, w: 0.5, h: 0.22,
      fontFace: LABEL_FONT, fontSize: 11, color: CUIVRE, charSpacing: 1.2 });
    s.addText(r[1], { ...T, x: M + 0.90, y: y + 0.09, w: 5.5, h: 0.22,
      fontFace: TITLE_FONT, fontSize: 12, bold: true, color: CHARCOAL, charSpacing: 0 });
    s.addText(r[2], { ...T, x: 6.6, y: y + 0.10, w: 2.4, h: 0.22, align: "right",
      fontFace: LABEL_FONT, fontSize: 8.5, color: ON_SURFACE_VARIANT, charSpacing: 1.2 });
  });
  caption(s, { y: 4.30, h: 0.68, label: "OBJET DE LA SÉANCE",
    text: "Valider le lancement commercial, la distribution Marketplace et l'enablement d'octobre." });
}

// ── 3 · Divider 01 ────────────────────────────────────────────────
{
  const s = p.addSlide();
  divider(s, { n: 3, num: "01", section: "LE MARCHÉ",
    lines: ["La fin de la rente", "de développement."],
    lede: "Prototyper prend désormais quelques heures. Mettre en production reste un métier, et c'est le nôtre." });
}

// ── 4 · Deux forces, une impasse ──────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 4, eyebrow: "— 01 · LE MARCHÉ", title: "Deux forces, une impasse." });
  const c = cols(2, 0.40);
  const Y = 2.02, H = 1.22;
  box(s, { ...c[0], y: Y, h: H, fill: INDIGO_LIGHT, accent: INDIGO_DARK,
    label: "FORCE 01 · VÉLOCITÉ MÉTIER", title: "Des prototypes en heures",
    body: "Cursor, Lovable, Bolt, v0 · les métiers livrent sans solliciter l'ingénierie centrale" });
  box(s, { ...c[1], y: Y, h: H, fill: "FFDAD6", accent: ERROR,
    label: "FORCE 02 · SÉCURITÉ SATURÉE", title: "15 à 25 h de revue",
    body: "par application, à la main · les équipes centrales n'ont pas la bande passante" });
  arrow(s, { x: 2.65, y: Y + H + 0.08, x2: 3.60, y2: 3.66 });
  arrow(s, { x: 7.35, y: Y + H + 0.08, x2: 6.40, y2: 3.66 });
  const bx = 1.90, bw = 6.20, by = 3.74, bh = 1.18;
  s.addShape("rect", { x: bx, y: by, w: bw, h: bh, fill: { color: NOIR }, line: { type: "none" } });
  s.addText("CONSÉQUENCE", { ...T, x: bx + 0.22, y: by + 0.11, w: bw - 0.44, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: CUIVRE_CLAIR, charSpacing: 1.2 });
  s.addText("85 % des applications générées par IA échouent à passer en production",
    { ...T, x: bx + 0.22, y: by + 0.34, w: bw - 0.44, h: 0.54,
      fontFace: TITLE_FONT, fontSize: 13, bold: true, color: WHITE, charSpacing: 0, lineSpacingMultiple: 1.15 });
  s.addText("Blocage CISO et SRE : secrets en clair, isolation réseau, authentification",
    { ...T, x: bx + 0.22, y: by + 0.90, w: bw - 0.44, h: 0.18,
      fontFace: BODY_FONT, fontSize: 9.5, color: TEXT_ON_DARK });
}

// ── 5 · Trois postures ────────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 5, eyebrow: "— 01 · LE MARCHÉ", title: "Trois postures face au Shadow AI." });
  const c = cols(3, 0.21), Y = 2.15, H = 1.32;
  box(s, { ...c[0], y: Y, h: H, fill: CRAIE_2, accent: ERROR,
    label: "POSTURE 01", title: "Interdire",
    body: "ressentiment des métiers, Shadow IT amplifié, prototypes hors radar" });
  box(s, { ...c[1], y: Y, h: H, fill: CRAIE_2, accent: ERROR,
    label: "POSTURE 02", title: "Laisser passer",
    body: "fuites de données, dérive des coûts d'API, exposition non maîtrisée" });
  box(s, { ...c[2], y: Y, h: H, fill: EMERAUDE_LIGHT, accent: EMERAUDE_DARK,
    label: "POSTURE 03 · SFEIR", title: "Industrialiser",
    body: "contrôle automatisé, remédiation livrée, mise en production gouvernée" });
  caption(s, { y: 4.00, h: 0.90, label: "LE POSITIONNEMENT SFEIR",
    text: "Ni censeur ni spectateur : l'accélérateur qui rend le passage en production conforme par défaut." });
}

// ── 6 · Divider 02 ────────────────────────────────────────────────
{
  const s = p.addSlide();
  divider(s, { n: 6, num: "02", section: "L'ACTIF",
    lines: ["Vibe Guard."],
    lede: "Un agent autonome d'audit et de remédiation, qui s'exécute dans le tenant Google Cloud du client." });
}

// ── 7 · La chaîne ─────────────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 7, eyebrow: "— 02 · L'ACTIF", title: "Du dépôt au correctif, en une chaîne." });
  const c = cols(4, 0.26), Y = 2.15, H = 1.35;
  const steps = [
    { label: "01 · INGESTION", title: "Clone éphémère", body: "dépôt Git, clone jetable", mono: "SHALLOW CLONE" },
    { label: "02 · DÉTECTION", title: "Règles SFEIR", body: "Semgrep et Gitleaks, pack déterministe", mono: "AUTH · SECRETS" },
    { label: "03 · CONTEXTE", title: "Tri par Gemini", body: "Gemini 3.8 Flash, faux positifs écartés", mono: "NET-ISO · LLM-GOV" },
    { label: "04 · REMÉDIATION", title: "Code à déployer", body: "Terraform, manifests Cloud Run, gcloud", mono: "TERRAFORM · GCLOUD" },
  ];
  steps.forEach((st, i) => {
    box(s, { ...c[i], y: Y, h: H, accent: CUIVRE, label: st.label, title: st.title, body: st.body, mono: st.mono });
    if (i < 3) arrow(s, { x: c[i].x + c[i].w + 0.045, y: Y + H / 2, x2: c[i + 1].x - 0.045, y2: Y + H / 2 });
  });
  caption(s, { y: 3.85, h: 0.95, label: "ZERO-EGRESS · 15 SECONDES",
    text: "Tout s'exécute dans le tenant GCP du client : aucun stockage, purge à chaque scan." });
}

// ── 8 · Comparaison scanner ───────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 8, eyebrow: "— 02 · L'ACTIF", title: "Ce qu'un scanner classique ne fait pas." });
  const C1 = M, W1 = 2.05, C2 = 2.65, W2 = 3.05, C3 = 5.80, W3 = 3.70;
  const HY = 2.00, HH = 0.28;
  s.addShape("rect", { x: M, y: HY, w: W, h: HH, fill: { color: NOIR }, line: { type: "none" } });
  [["DIMENSION", C1], ["SCANNER TRADITIONNEL", C2], ["VIBE GUARD", C3]].forEach(([t, x]) => {
    s.addText(t, { ...T, x: x + 0.18, y: HY + 0.07, w: 3.2, h: 0.18,
      fontFace: LABEL_FONT, fontSize: 8, color: CUIVRE_CLAIR, charSpacing: 1.2 });
  });
  const rows = [
    ["Cible d'analyse", "Vulnérabilités CVE et dépendances", "Failles propres au code généré par IA"],
    ["Résultat fourni", "Rapport passif de 50 pages", "Terraform, Cloud Run et gcloud prêts à déployer"],
    ["Moteur IA", "Absent ou générique", "Gemini 3.8 Flash via Vertex AI"],
    ["Canal utilisateur", "Console réservée aux experts SecOps", "Conversationnel, dans la Gemini Enterprise App"],
    ["Souveraineté", "Données envoyées sur un SaaS externe", "Tenant GCP du client, scan éphémère"],
  ];
  const RH = 0.34;
  rows.forEach((r, i) => {
    const y = HY + HH + i * RH;
    s.addShape("rect", { x: M, y, w: W, h: RH, fill: { color: i % 2 ? CRAIE_1 : WHITE }, line: { type: "none" } });
    s.addText(r[0], { ...T, x: C1 + 0.18, y: y + 0.09, w: W1 - 0.2, h: 0.20,
      fontFace: TITLE_FONT, fontSize: 10, bold: true, color: CHARCOAL, charSpacing: 0 });
    s.addText(r[1], { ...T, x: C2 + 0.18, y: y + 0.10, w: W2 - 0.2, h: 0.20,
      fontFace: BODY_FONT, fontSize: 9.5, color: ON_SURFACE_VARIANT });
    s.addText(r[2], { ...T, x: C3 + 0.18, y: y + 0.10, w: W3 - 0.2, h: 0.20,
      fontFace: BODY_FONT, fontSize: 9.5, color: CHARCOAL });
  });
  caption(s, { y: 4.10, h: 0.88, label: "CE QUI CHANGE",
    text: "Vibe Guard ne signale pas un défaut : il livre le code d'infrastructure qui le referme." });
}

// ── 9 · Divider 03 ────────────────────────────────────────────────
{
  const s = p.addSlide();
  divider(s, { n: 9, num: "03", section: "LE MODÈLE ÉCONOMIQUE",
    lines: ["Trois étages,", "une seule vente."],
    lede: "Une mission flash ouvre une licence récurrente, qui ouvre le build. Chaque étage finance le suivant." });
}

// ── 10 · L'entonnoir ──────────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 10, eyebrow: "— 03 · LE MODÈLE ÉCONOMIQUE", title: "Un entonnoir à trois étages." });
  const c = cols(3, 0.21), Y = 2.15, H = 1.22;
  const stages = [
    { label: "01 · PORTE D'ENTRÉE", title: "Assessment flash", body: "2 à 3 jours · 3 000 à 4 500 € HT\nmarge brute 60 %" },
    { label: "02 · RENTE LOGICIELLE", title: "Licence CPPO", body: "25 k€ à 75 k€ par an · imputés sur l'EDP" },
    { label: "03 · PRESTATION", title: "Build et SecOps", body: "50 k€ à 150 k€ par mise en production" },
  ];
  stages.forEach((st, i) => {
    box(s, { ...c[i], y: Y, h: H, fill: RAMP_OCRE[i].fill, accent: TERRE_DARK,
      label: st.label, title: st.title, body: st.body,
      titleColor: RAMP_OCRE[i].text, bodyColor: RAMP_OCRE[i].text, labelColor: TERRE_DARK });
    if (i < 2) arrow(s, { x: c[i].x + c[i].w + 0.03, y: Y + H / 2, x2: c[i + 1].x - 0.03, y2: Y + H / 2 });
  });
  s.addText("VALEUR CROISSANTE DU CONTRAT", { ...T, x: M, y: 3.55, w: W, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: ON_SURFACE_VARIANT, charSpacing: 1.2 });
  caption(s, { y: 4.02, h: 0.88, label: "L'EFFET DE LEVIER",
    text: "L'assessment n'est pas une offre d'appel à perte : il finance sa conversion en licence." });
}

// ── 11 · Projection (sombre) ──────────────────────────────────────
{
  const s = p.addSlide();
  s.background = { color: NOIR };
  s.addText("— 03 · LE MODÈLE ÉCONOMIQUE", { ...T, x: M, y: 0.32, w: W, h: 0.20,
    fontFace: LABEL_FONT, fontSize: 10, color: CUIVRE_CLAIR, charSpacing: 1.5 });
  s.addText(titleRuns(["Projection à 12 mois."], CUIVRE_CLAIR), { ...T, x: M, y: 0.56, w: W, h: 0.52,
    fontFace: TITLE_FONT, fontSize: 28, bold: true, color: WHITE, charSpacing: 0 });
  s.addText("906 k€", { ...T, x: M, y: 1.30, w: 3.0, h: 0.80,
    fontFace: TITLE_FONT, fontSize: 52, bold: true, color: CUIVRE_CLAIR, charSpacing: 0 });
  s.addText("CHIFFRE D'AFFAIRES BRUT", { ...T, x: M, y: 2.08, w: 3.0, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 9.5, color: TEXT_ON_DARK, charSpacing: 1.2 });
  s.addText("520 k€", { ...T, x: 3.70, y: 1.30, w: 3.0, h: 0.80,
    fontFace: TITLE_FONT, fontSize: 52, bold: true, color: CUIVRE_CLAIR, charSpacing: 0 });
  s.addText("MARGE BRUTE · 57 %", { ...T, x: 3.70, y: 2.08, w: 3.0, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 9.5, color: TEXT_ON_DARK, charSpacing: 1.2 });
  s.addText("Scénario conservateur, sur 15 comptes grands comptes\ndu portefeuille existant.",
    { ...T, x: 7.0, y: 1.34, w: 2.5, h: 0.7, fontFace: BODY_FONT, fontSize: 11, color: TEXT_ON_DARK, lineSpacingMultiple: 1.3 });
  s.addText("CA BRUT", { ...T, x: 6.20, y: 2.62, w: 1.4, h: 0.16, align: "right",
    fontFace: LABEL_FONT, fontSize: 8, color: OUTLINE, charSpacing: 1.2 });
  s.addText("MARGE", { ...T, x: 7.80, y: 2.62, w: 1.5, h: 0.16, align: "right",
    fontFace: LABEL_FONT, fontSize: 8, color: OUTLINE, charSpacing: 1.2 });
  const rows = [
    ["Assessment flash", "20 missions vendues · 3 800 € en moyenne", "76 k€", "48 k€", false],
    ["Licences CPPO", "10 souscriptions annuelles · 35 000 €", "350 k€", "280 k€", false],
    ["Build et SecOps", "6 projets d'industrialisation · 80 000 €", "480 k€", "192 k€", false],
    ["TOTAL AN 1", "", "906 k€", "520 k€", true],
  ];
  const RY = 2.86, RH = 0.36;
  rows.forEach((r, i) => {
    const y = RY + i * RH;
    if (r[4]) s.addShape("rect", { x: M, y, w: W, h: RH, fill: { color: "1A1A1A" }, line: { type: "none" } });
    s.addText(r[0], { ...T, x: M + 0.22, y: y + 0.10, w: 2.4, h: 0.20,
      fontFace: TITLE_FONT, fontSize: 10.5, bold: true, color: r[4] ? CUIVRE_CLAIR : WHITE, charSpacing: 0 });
    if (r[1]) s.addText(r[1], { ...T, x: 3.00, y: y + 0.11, w: 3.1, h: 0.20,
      fontFace: BODY_FONT, fontSize: 9.5, color: TEXT_ON_DARK });
    s.addText(r[2], { ...T, x: 6.20, y: y + 0.10, w: 1.4, h: 0.20, align: "right",
      fontFace: BODY_FONT, fontSize: 10.5, color: r[4] ? CUIVRE_CLAIR : WHITE });
    s.addText(r[3], { ...T, x: 7.80, y: y + 0.10, w: 1.5, h: 0.20, align: "right",
      fontFace: BODY_FONT, fontSize: 10.5, color: r[4] ? CUIVRE_CLAIR : TEXT_ON_DARK });
  });
  chrome(s, 11, true);
}

// ── 12 · L'argument EDP ───────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 12, eyebrow: "— 03 · LE MODÈLE ÉCONOMIQUE", title: "L'argument qui raccourcit le cycle." });
  const Y = 2.05, H = 1.45;
  system(s, { x: M, y: Y, w: 2.40, h: H, fill: SOUVERAIN_DARK,
    label: "CÔTÉ CLIENT", name: "Engagement EDP", sub: "USE-IT-OR-LOSE-IT" });
  box(s, { x: 3.30, y: Y, w: 3.40, h: H, fill: SOUVERAIN_LIGHT, accent: SOUVERAIN,
    label: "LE VÉHICULE", title: "Private Offer CPPO",
    body: "portée par SFEIR, éditeur référencé sur la Marketplace · imputation à 100 % sur l'engagement pluriannuel déjà signé" });
  system(s, { x: 7.10, y: Y, w: 2.40, h: H, fill: SOUVERAIN,
    label: "CÔTÉ SFEIR", name: "Licence Vibe Guard", sub: "ARR 25 À 75 K€ / AN" });
  arrow(s, { x: 2.95, y: Y + H / 2, x2: 3.25, y2: Y + H / 2 });
  arrow(s, { x: 6.75, y: Y + H / 2, x2: 7.05, y2: Y + H / 2 });
  s.addText("CYCLE DE DÉCISION", { ...T, x: M, y: 3.72, w: 2.2, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: ON_SURFACE_VARIANT, charSpacing: 1.2 });
  s.addText("4 MOIS", { ...T, x: 2.55, y: 3.68, w: 1.0, h: 0.22,
    fontFace: LABEL_FONT, fontSize: 10, color: ON_SURFACE_VARIANT, charSpacing: 1.2 });
  arrow(s, { x: 3.50, y: 3.79, x2: 4.00, y2: 3.79 });
  s.addText("MOINS DE 3 SEMAINES", { ...T, x: 4.12, y: 3.68, w: 3.0, h: 0.22,
    fontFace: LABEL_FONT, fontSize: 10, color: CUIVRE, charSpacing: 1.2 });
  caption(s, { y: 4.05, h: 0.88, label: "POURQUOI LE CLIENT SIGNE VITE",
    text: "Aucun budget nouveau à débloquer : l'opération reste transparente pour sa direction financière." });
}

// ── 13 · Divider 04 ───────────────────────────────────────────────
{
  const s = p.addSlide();
  divider(s, { n: 13, num: "04", section: "EXÉCUTION",
    lines: ["Du pilote", "à la généralisation."],
    lede: "Homologation Marketplace, enablement interne, campagne conjointe : six mois jusqu'aux premiers CPPO." });
}

// ── 14 · Synergies Google Cloud ───────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 14, eyebrow: "— 04 · EXÉCUTION", title: "Ce que l'alliance Google y gagne." });
  const c = cols(3, 0.21), Y = 2.15, H = 1.30;
  box(s, { ...c[0], y: Y, h: H, accent: CUIVRE, label: "01 · CO-SELLING", title: "Consommation GCP",
    body: "Cloud Run, Secret Manager, Vertex AI, IAP · les AE et CE Google sont incités" });
  box(s, { ...c[1], y: Y, h: H, accent: CUIVRE, label: "02 · GEMINI ENTERPRISE", title: "Partenaire de référence",
    body: "des agents métier et techniques déployés dans les tenants privés des grands comptes" });
  box(s, { ...c[2], y: Y, h: H, accent: CUIVRE, label: "03 · VISIBILITÉ", title: "Vitrine Premier",
    body: "Google Cloud Summit, DevFest, hackathons GenAI" });
  caption(s, { y: 4.02, h: 0.88, label: "CE QUE ÇA NOUS ACHÈTE",
    text: "Une force de vente Google alignée sur notre offre, et un statut d'éditeur sur la Marketplace." });
}

// ── 15 · Calendrier ───────────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 15, eyebrow: "— 04 · EXÉCUTION", title: "Six mois, deux trimestres." });
  const AX = 3.05, AW = 6.45, COLW = AW / 6;
  const MONTHS = ["OCT", "NOV", "DÉC", "JAN", "FÉV", "MAR"];
  const DAYS = [31, 30, 31, 31, 28, 31];
  function px(mi, day) { return AX + (mi + (day - 1) / DAYS[mi]) * COLW; }
  s.addText("Q4 2026", { ...T, x: AX, y: 1.92, w: COLW * 3, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: CUIVRE, charSpacing: 1.2 });
  s.addText("Q1 2027", { ...T, x: AX + COLW * 3, y: 1.92, w: COLW * 3, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: ON_SURFACE_VARIANT, charSpacing: 1.2 });
  MONTHS.forEach((m, i) => {
    s.addText(m, { ...T, x: AX + i * COLW, y: 2.14, w: COLW, h: 0.18,
      fontFace: LABEL_FONT, fontSize: 8, color: ON_SURFACE_VARIANT, charSpacing: 1.0 });
    s.addShape("rect", { x: AX + i * COLW, y: 2.36, w: 0.01, h: 1.60,
      fill: { color: i === 3 ? BROUILLARD : "EFE7DC" }, line: { type: "none" } });
  });
  const bars = [
    ["Homologation Marketplace GCP", 0, 1, 0, 25, true],
    ["Enablement Sales, CTO et ED", 0, 20, 1, 15, true],
    ["Trois assessments pilotes", 1, 1, 2, 15, true],
    ["Campagne conjointe Google", 3, 5, 4, 28, false],
    ["Généralisation des CPPO", 4, 1, 5, 31, false],
  ];
  s.addShape("rect", { x: AX, y: 2.36, w: AW, h: 0.012, fill: { color: BROUILLARD }, line: { type: "none" } });
  const BY = 2.48, BS = 0.32;
  bars.forEach((b, i) => {
    const y = BY + i * BS;
    const x1 = px(b[1], b[2]), x2 = px(b[3], b[4]);
    s.addText(b[0], { ...T, x: M, y: y - 0.03, w: 2.45, h: 0.22,
      fontFace: TITLE_FONT, fontSize: 9.5, bold: true, color: CHARCOAL, charSpacing: 0 });
    s.addShape("rect", { x: x1, y, w: x2 - x1, h: 0.15,
      fill: { color: b[5] ? CUIVRE : CUIVRE_POLI }, line: { type: "none" } });
  });
  caption(s, { y: 4.08, h: 0.88, label: "LE CHEMIN CRITIQUE",
    text: "L'enablement d'octobre commande les trois pilotes, qui commandent la généralisation des Private Offers." });
}

// ── 16 · Risques ──────────────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 16, eyebrow: "— 04 · EXÉCUTION", title: "Trois risques, trois parades." });
  const HY = 2.00, HH = 0.28, C1 = M, W1 = 2.90, C2 = 3.40;
  s.addShape("rect", { x: M, y: HY, w: W, h: HH, fill: { color: NOIR }, line: { type: "none" } });
  s.addText("RISQUE", { ...T, x: C1 + 0.18, y: HY + 0.07, w: 2.5, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: CUIVRE_CLAIR, charSpacing: 1.2 });
  s.addText("PARADE", { ...T, x: C2 + 0.18, y: HY + 0.07, w: 3.0, h: 0.18,
    fontFace: LABEL_FONT, fontSize: 8, color: CUIVRE_CLAIR, charSpacing: 1.2 });
  const rows = [
    ["Responsabilité sur le code scanné", "Analyse statique déterministe, validation humaine systématique, CGU d'assistance sans transfert de responsabilité du run."],
    ["Fuite de données client", "Architecture Zero-Egress C1 / C2 : exécution dans le tenant du client, aucun stockage intermédiaire, purge à chaque scan."],
    ["Charge des équipes SFEIR", "Assessment automatisé à 85 % : moins de 1,5 jour de consultant expérimenté pour une mission de 3 jours facturés."],
  ];
  const RH = 0.56;
  rows.forEach((r, i) => {
    const y = HY + HH + i * RH;
    s.addShape("rect", { x: M, y, w: W, h: RH, fill: { color: i % 2 ? CRAIE_1 : WHITE }, line: { type: "none" } });
    s.addText(r[0], { ...T, x: C1 + 0.18, y: y + 0.10, w: W1 - 0.2, h: 0.40,
      fontFace: TITLE_FONT, fontSize: 10, bold: true, color: CHARCOAL, charSpacing: 0, lineSpacingMultiple: 1.15 });
    s.addText(r[1], { ...T, x: C2 + 0.18, y: y + 0.11, w: 5.7, h: 0.40,
      fontFace: BODY_FONT, fontSize: 9.5, color: ON_SURFACE_VARIANT, lineSpacingMultiple: 1.15 });
  });
  caption(s, { y: 4.12, h: 0.86, label: "CE QUE CELA IMPLIQUE",
    text: "Les trois risques se traitent par l'architecture et par le contrat, sans réserve budgétaire." });
}

// ── 17 · Décisions ────────────────────────────────────────────────
{
  const s = p.addSlide();
  header(s, { n: 17, eyebrow: "— 05 · ARBITRAGE", title: "Trois décisions demandées au COMEX." });
  const c = cols(3, 0.21), Y = 2.15, H = 1.30;
  box(s, { ...c[0], y: Y, h: H, fill: CRAIE_1, accent: CUIVRE, label: "DÉCISION 01",
    title: "Lancement commercial",
    body: "l'offre Vibe Coding Security Assessment entre au catalogue des offres d'appel SFEIR" });
  box(s, { ...c[1], y: Y, h: H, fill: CRAIE_1, accent: CUIVRE, label: "DÉCISION 02",
    title: "Distribution Marketplace",
    body: "Vibe Guard éligible aux Private Offers CPPO sous l'entité éditeur SFEIR" });
  box(s, { ...c[2], y: Y, h: H, fill: CRAIE_1, accent: CUIVRE, label: "DÉCISION 03",
    title: "Enablement interne",
    body: "une session de 2 heures pour les Sales, CTO et ED en octobre 2026" });
  caption(s, { y: 4.02, h: 0.88, label: "CE QUI LIE LES TROIS",
    text: "Sans référencement Marketplace, pas d'ARR. Sans enablement d'octobre, pas de pilote avant 2027." });
}

// ── 18 · Clôture ──────────────────────────────────────────────────
{
  const s = p.addSlide();
  s.background = { color: NOIR };
  s.addText("CONVICTION", { ...T, x: M, y: 0.50, w: 8, h: 0.22,
    fontFace: LABEL_FONT, fontSize: 10, color: CUIVRE_CLAIR, charSpacing: 1.6 });
  s.addText(titleRuns(["Le vibe coding", "ne s'interdit pas.", "Il s'industrialise."], CUIVRE_CLAIR),
    { ...T, x: M, y: 1.55, w: 8.5, h: 2.1,
      fontFace: TITLE_FONT, fontSize: 40, bold: true, color: WHITE, charSpacing: 0, lineSpacingMultiple: 1.06 });
  s.addText("Équipe projet Vibe Guard · CTO & ED · Direction des Alliances & Partenariats",
    { ...T, x: M, y: 3.98, w: 6.5, h: 0.24, fontFace: BODY_FONT, fontSize: 12, color: TEXT_ON_DARK });
  s.addShape("rect", { x: M, y: 4.38, w: 3.05, h: 0.42, fill: { color: CUIVRE_CLAIR }, line: { type: "none" } });
  s.addText("DÉMONSTRATION EN SÉANCE →", { margin: 0, x: M, y: 4.38, w: 3.05, h: 0.42,
    align: "center", valign: "middle", fontFace: LABEL_FONT, fontSize: 11, bold: true,
    color: CUIVRE_PROFOND, charSpacing: 0.7 });
  chrome(s, 18, true);
}

const OUT = process.argv[2] || "deck.pptx";
p.writeFile({ fileName: OUT }).then(f => console.log("écrit :", f));
