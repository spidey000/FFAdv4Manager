import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Viewport, { useSlicer } from 'three-slicer-viewer'
import SettingsPanel from 'three-slicer-viewer/components'
import { makeSlicerWorker } from 'three-slicer/client'
import {
  bundledCatalog, printerSettings, printerKeys, printerDefaultPreset,
  processPresets, filamentPresets,
} from 'three-slicer/settings'
import { schema, uiTree } from 'three-slicer/data'
import { makeCfg, disabledKeys } from 'three-slicer/toggle'
import './step_loader.js'
import PrinterManager from './PrinterManager.jsx'
import { AD4_STOCK_PROCESS, AD4_SAFE_PROCESS, AD4_SAFE_PROCESS_OVERRIDES, applyAd4SafeMachineLimits, applyAd4SafeProcess } from './ad4SafeProfile.js'
import {
  SAVE_PROCESS_OPTION, SAVE_FILAMENT_OPTION, ARTILLERY_PLA_BASIC,
  browserProfileStorage, readProfileLibrary, writeProfileLibrary, addCustomProfile, replaceCustomProfile, removeCustomProfile,
  makeArtilleryPlaBasic,
} from './profileLibrary.js'
import { fullPreviewLayer, getPreviewControls, previewMoveCount, scrubPreviewMove, selectPreviewLayer } from './previewBridge.js'
import { checkArtilleryHeating } from './temperatureSafety.js'
import { annotateAd4Gcode, captureAd4PlateThumbnail } from './ad4JobMetadata.js'

// Keep this hook adapter at module scope: three-slicer-viewer calls it as a hook.
const slicer = (deps) => useSlicer({ ...deps, makeWorker: makeSlicerWorker })
const panelData = { schema, uiTree, toggle: { makeCfg, disabledKeys } }
const AD4 = 'Flashforge Adventurer 4 Series 0.4 Nozzle'
const ad4Catalog = { ...bundledCatalog,
  printersByVendor: { Flashforge: { [AD4]: bundledCatalog.printersByVendor.Flashforge[AD4] } },
  printerTechByVendor: { Flashforge: 'FFF' },
}
const responsiveViewerCss = `
/* Inherited design tokens work through the viewer's Shadow DOM. */
.app-shell { font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
.app-body { padding-bottom: var(--demo-preview-bottom, 0px); }
.topbar { background: #1c232b; border-color: #303e49; }
.tb-logo { text-decoration:none; font-weight:650; letter-spacing:-.03em; }
.tb-btn, .tb-icon { border-radius: 10px; transition: background-color .16s ease, border-color .16s ease; }
.tb-tabs { border-radius: 11px; border-color: #34424d; }
.tb-tabs button.on { background:#a3e635; color:#152007; }
.vp-top-toolbar { background:rgba(23,29,35,.90); border-color:#35414b; border-radius:12px; box-shadow:0 8px 26px #0003; }
.vp-top-toolbar button { border-radius:9px; }
.plate-bar { background:rgba(23,29,35,.93); border-color:#35414b; border-radius:13px; padding:5px; }
.plate-bar button { min-width:32px; height:32px; border-radius:9px; }
.plate-tab.on { background:#a3e635; border-color:#a3e635; color:#162008; }
.stats-card {
  left:14px; top:14px; bottom:auto; max-width:min(430px,calc(100% - 28px)); max-height:min(65%,450px);
  overflow-y:auto; padding:12px 14px; background:rgba(28,35,43,.97); border:1px solid #3a4853;
  border-radius:15px; box-shadow:0 12px 38px #0005; line-height:1.6; backdrop-filter:blur(14px);
  font-variant-numeric:tabular-nums; color:#dce4ea;
}
.stats-card b { color:#b7f26b; }
.stats-card .stats-toggle {
  width:100%; min-height:36px; display:flex; justify-content:space-between; align-items:center; gap:14px;
  margin:0 0 8px; padding:0; border:0; background:transparent; color:#e9f2f6;
  font:600 12px/1.5 Inter, system-ui,sans-serif; text-align:left; cursor:pointer;
}
.stats-title-stack { display:flex; flex-direction:column; gap:2px; min-width:0; }
.stats-heading { display:flex; align-items:center; gap:6px; color:#b4ea70; }
.stats-glance { display:block; color:#eef3f7; font-size:12px; font-weight:600; letter-spacing:-.01em; white-space:nowrap; }
.stats-chevron { display:grid; place-items:center; flex:0 0 25px; width:25px; height:25px;
  border-radius:8px; color:#bac9d4; background:#2b3540; font-size:16px; }
.stats-card.is-collapsed { padding:7px 10px; overflow:visible; }
.stats-card.is-collapsed .stats-toggle { margin:0; min-height:36px; }
.stats-card.is-collapsed > :not(.stats-toggle) { display:none !important; }
.stats-card:not(.is-collapsed) .stats-glance { color:#90a1ae; font-size:11px; font-weight:500; }
.stats-card.has-warning .stats-heading { color:#ffb39b; }
.stats-card:focus-within { border-color:#709744; }
.ad4-topbar { display:flex; align-items:center; gap:7px; margin-left:auto; white-space:nowrap; font:12px/1.3 Inter,system-ui,sans-serif; }
.ad4-printer-state { display:inline-flex; align-items:center; gap:7px; min-width:0;
  padding:7px 9px; border:1px solid #364450; border-radius:10px; background:#26303a; color:#aebdca; }
.ad4-printer-state strong { color:#eaf0f5; font-size:11px; font-weight:750; }
.ad4-printer-state .state-dot { width:7px; height:7px; flex:0 0 7px; border-radius:50%; background:#fb806d; box-shadow:0 0 0 2px #fb806d18; }
.ad4-printer-state .state-dot.is-online { background:#a3e635; box-shadow:0 0 0 2px #a3e63522; }
.ad4-printer-state .state-text { overflow:hidden; text-overflow:ellipsis; }
.ad4-printer-state { font:inherit; cursor:pointer; }
.ad4-printer-state:hover { background:#34414d; border-color:#668d3e; }
.ad4-topbar .camera-trigger { position:static; display:grid; place-items:center; flex:0 0 36px;
  width:36px; height:36px; padding:6px; border:1px solid #35434e; border-radius:10px;
  background:#26303a; color:#bced70; cursor:pointer; }
.ad4-topbar .camera-trigger:hover { background:#34434e; }
.ad4-topbar .camera-trigger svg { width:19px; height:19px; }
@media(max-width:767px) {
  .app-shell { font-size:12px; }
  .topbar, .topbar:has(.tb-gcode) { flex:0 0 auto; height:auto; min-height:88px;
    display:grid; grid-template-columns:minmax(0,1fr) auto; grid-template-rows:39px 35px;
    column-gap:6px; row-gap:3px; padding:6px 10px 5px; }
  .topbar:has(.tb-gcode) { grid-template-rows:39px 35px 32px; min-height:120px; }
  .topbar .tb-left { grid-column:1; grid-row:1; display:flex; align-items:center; gap:5px; width:100%;
    min-width:0; flex:none; overflow-x:auto; overflow-y:hidden; scrollbar-width:none; }
  .topbar .tb-left > * { flex:0 0 auto; }
  .tb-logo { font-size:13px; white-space:nowrap; margin-right:2px; }
  .tb-re { display:none; }
  .topbar .tb-left::-webkit-scrollbar { display:none; }
  .tb-re { font-size:9px; margin-left:1px; padding:1px 3px; }
  .topbar .tb-left .tb-btn { flex:0 0 32px; display:grid; place-items:center; width:32px;
    height:34px; padding:5px; border-radius:9px; }
  .topbar .tb-left .tb-btn img { width:17px; height:17px; }
  .topbar .tb-left .tb-btn span { display:none; }
  .topbar .tb-left [data-testid="export-stl"] span { display:block; font-size:10px; font-weight:750; }
  .topbar .tb-left .tb-btn:disabled { display:none; }
  .topbar .tb-tabs { grid-column:1; grid-row:2; justify-self:start; height:34px; }
  .topbar .tb-tabs button { min-width:81px; padding:6px 12px; font-size:11px; }
  .topbar .tb-right { grid-column:2; grid-row:2; min-width:0; width:auto; gap:5px; justify-content:flex-end; }
  .topbar .tb-right .tb-icon { width:33px; height:33px; border-radius:9px; }
  .topbar .ad4-topbar { grid-column:2; grid-row:1; margin:0; justify-self:end; gap:5px; }
  .ad4-topbar .ad4-printer-state { max-width:114px; height:34px; padding:5px 7px; font-size:10px; }
  .ad4-topbar .camera-trigger { flex-basis:34px; width:34px; height:34px; }
  .topbar .tb-gcode { grid-column:1 / -1; grid-row:3; min-width:0; overflow:hidden; }
  .topbar .tb-gcode span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .sidebar { display:none !important; }
  .left-rail { flex-basis:40px; padding:6px 0; gap:4px; overflow-y:auto; scrollbar-width:none; }
  .left-rail button { width:34px; height:34px; }
  .vp-top-toolbar { top:8px; max-width:calc(100% - 18px); }
  .vp-top-toolbar button { width:30px; height:30px; }
  .plate-bar { right:10px; bottom:12px; max-width:calc(100% - 20px); overflow-x:auto; }
  .brush-panel { top:48px; left:8px; width:min(230px,calc(100% - 16px)); }
  .stats-card { left:10px; top:10px; max-width:min(350px,calc(100% - 20px)); max-height:48%; font-size:11px; }
  .stats-card.is-collapsed { max-width:min(235px,calc(100% - 20px)); }
  .stats-glance { font-size:11px; }
  .vp-status { display:none !important; }
  .bed-warn { left:10px; bottom:max(16px,calc(var(--demo-preview-bottom,0px) + 8px));
    max-width:min(55%,220px); font-size:11px; }
}
@media(max-width:380px) {
  .tb-logo { font-size:12px; }
  .tb-re { display:none; }
  .topbar .tb-left { gap:4px; }
  .topbar .tb-left .tb-btn { flex-basis:30px; width:30px; height:32px; }
  .ad4-topbar .ad4-printer-state { max-width:99px; padding:5px; }
  .ad4-topbar .camera-trigger { flex-basis:32px; width:32px; height:32px; }
}
@media(min-width:768px) and (max-width:1100px) {
  .sidebar { flex-basis:min(300px,35vw); width:min(300px,35vw); }
  .topbar { gap:7px; padding-inline:10px; }
  .tb-tabs button { padding-left:12px; padding-right:12px; }
}
@media(prefers-reduced-motion:reduce) { .stats-chevron, .tb-btn { transition:none; } }

/* V2: true canvas-first mobile composition; the upstream actions remain mounted and functional. */
.app-body { position:relative; }
.topbar .tb-btn, .topbar .tb-icon, .camera-trigger { box-shadow:0 1px 0 #ffffff08 inset; }
.empty-hint { width:min(370px,calc(100% - 32px)); height:auto; min-height:0;
  position:absolute; inset:48% auto auto 50%; box-sizing:border-box; max-width:calc(100% - 32px);
  transform:translate(-50%,-50%); padding:24px 22px 22px;
  background:rgba(25,33,41,.93); border:1px solid #354550;
  box-shadow:0 16px 55px #0007; backdrop-filter:blur(14px);
  border-radius:20px; gap:8px; pointer-events:none; }
.empty-hint .eh-icon { display:grid; place-items:center; width:55px; height:55px;
  margin-bottom:6px; border-radius:17px; background:#2d3f29; font-size:30px; opacity:1; }
.empty-hint .eh-title { font-size:17px; font-weight:750; letter-spacing:-.025em; line-height:1.25; color:#f1f6f8; }
.empty-hint .eh-sub { width:100%; max-width:290px; color:#98a9b6; font-size:10px; line-height:1.65;
  font-weight:500; letter-spacing:.02em; text-wrap:balance; }
.empty-hint .eh-btn { min-width:160px; min-height:44px; margin-top:12px;
  padding:10px 20px; border-radius:12px; background:#a3e635; color:#162008;
  box-shadow:0 5px 17px #a3e63520; font:750 13px/1.2 Inter,system-ui; }
.empty-hint .eh-btn:hover { background:#b8f26e; }
.empty-hint .eh-btn:focus-visible { outline:2px solid #efffb7; outline-offset:3px; }
.vp-status { color:#92a2ae; font:11px/1.35 Inter,system-ui; text-shadow:none; }
@media(max-width:767px) {
  .app-body:has(.empty-hint) .left-rail { display:none !important; }
  .viewport-col:has(.empty-hint) .vp-top-toolbar { display:none !important; }
  .viewport-col { background:#101419; }
  .topbar, .topbar:has(.tb-gcode) {
    min-height:91px; height:auto; flex:0 0 auto;
    grid-template-columns:minmax(0,1fr) max-content;
    grid-template-rows:40px 36px; row-gap:3px; column-gap:5px;
    padding:5px 12px 7px; background:#1c232b; border-bottom:1px solid #33414d;
  }
  .topbar:has(.tb-gcode) { grid-template-rows:40px 36px 30px; }
  .topbar .tb-left { grid-column:1 / -1; grid-row:1; z-index:0;
    width:100%; height:40px; gap:6px; padding-right:116px;
    min-width:0; overflow-x:auto; overflow-y:hidden; scrollbar-width:none; }
  .topbar .tb-left .tb-btn, .topbar .tb-left .tb-btn:disabled {
    flex:0 0 35px; width:35px; height:35px; display:grid; place-items:center;
    border-radius:11px; border:1px solid #34434f; background:#293440; padding:6px; }
  .topbar .tb-left .tb-btn:disabled { opacity:.35; }
  .topbar .tb-left .tb-btn:disabled:not(.tb-busy) { display:grid; }
  .topbar .tb-left .tb-btn img { width:18px; height:18px; }
  .topbar .tb-left [data-testid="export-stl"] span { font-size:10px; font-weight:800; }
  .tb-logo { flex:0 0 auto; margin-right:5px; font-size:14px; font-weight:800; }
  .topbar .tb-re { display:none; }
  .topbar .tb-tabs { grid-column:1; grid-row:2; justify-self:start; height:36px; background:#28333e;
    border-radius:11px; overflow:hidden; }
  .topbar .tb-tabs button { min-width:0; padding:7px 14px; min-height:35px;
    font-size:12px; border-radius:0; }
  .topbar .tb-tabs button:disabled { color:#7c8a96; opacity:1; }
  .topbar .tb-right { grid-column:2; grid-row:1; align-self:center;
    justify-self:end; width:auto; height:35px; margin-right:43px; gap:3px; }
  .topbar .tb-right .tb-icon { width:30px; height:34px; font-size:16px; }
  .topbar .tb-right .tb-icon:disabled { display:none; }
  .topbar .ad4-topbar { display:contents; }
  .topbar .ad4-printer-state { grid-column:2; grid-row:2; place-self:center end; margin:0; display:flex; flex-wrap:nowrap;
    width:auto; max-width:150px; min-width:0; height:35px; padding:5px 9px; gap:6px;
    border:1px solid #394956; border-radius:11px; background:#25313b; }
  .topbar .ad4-printer-state strong { font-size:11px; }
  .topbar .ad4-printer-state .state-text { font-size:10px; max-width:none; white-space:nowrap; }
  .topbar .camera-trigger { grid-column:2; grid-row:1; justify-self:end; align-self:center; margin:0;
    width:35px; height:35px; border-radius:11px; background:#293440; }
  .topbar .tb-gcode { grid-column:1/-1; grid-row:3; }
  .left-rail { position:absolute; left:8px; top:64px; width:43px; height:auto;
    flex:none; z-index:4; padding:5px 3px; gap:4px; background:rgba(24,33,41,.93);
    border:1px solid #384653; border-radius:13px; box-shadow:0 10px 28px #0005; }
  .left-rail button { width:36px; height:36px; border-radius:10px; }
  .left-rail .rail-sep { width:28px; margin:2px 0; }
  .vp-top-toolbar { left:50%; top:10px; max-width:calc(100% - 18px);
    padding:5px; border-radius:13px; background:#1b252eea; border-color:#354650; }
  .vp-top-toolbar button { width:32px; height:32px; }
  .vp-top-toolbar button:disabled { opacity:.22; }
  .vp-top-toolbar button img { width:19px; height:19px; }
  .empty-hint { inset:49% auto auto 50%; width:min(330px,calc(100% - 28px)); max-width:calc(100% - 28px); padding:24px 18px; border-radius:19px; }
  .empty-hint .eh-title { font-size:16px; }
  .empty-hint .eh-btn { min-height:44px; }
  .plate-bar { bottom:14px; }
  .vp-status { display:none !important; }
  .stats-card.is-collapsed { left:12px; top:12px; }
  .stats-card { border-radius:14px; }
}
@media(max-width:390px) {
  .topbar .tb-left { padding-right:94px; gap:4px; }
  .topbar .tb-left .tb-btn { flex-basis:32px; width:32px; height:33px; }
  .tb-logo { font-size:12px; margin-right:2px; }
  .topbar .ad4-printer-state { max-width:124px; padding:5px 7px; }
  .topbar .ad4-printer-state .state-text { font-size:9px; }
  .topbar .tb-tabs button { padding-inline:10px; font-size:11px; }
  .topbar .camera-trigger { width:33px; height:33px; }
}
@media(max-height:600px) and (max-width:767px) {
  .empty-hint { inset:48% auto auto 50%; padding:16px; }
  .empty-hint .eh-icon { width:44px; height:44px; font-size:26px; }
}
`
const responsiveSettingsCss = `
:host { color-scheme:dark; font-family:Inter,ui-sans-serif,system-ui,sans-serif; }
.settings-panel {
  --_light-bg:#141b22; --_light-surface:#1c232b; --_light-subtle:#26313b;
  --_light-control:#2a3642; --_light-border:#394853; --_light-divider:#2e3a45;
  --_light-text:#eef4f8; --_light-text-muted:#b9c6d0; --_light-text-faint:#8899a8;
  --_accent-ink:#b8ee72; --_accent-soft:#2b4025; --_accent-soft-border:#526f3a;
  --_on-accent:#162009;
  width:100%; max-width:100%; min-width:0; height:100%; background:#1c232b; border:0;
  color:#eef4f8; font:13px/1.55 Inter,system-ui,sans-serif;
}
:host(.sp-embedded) .settings-panel { width:100%; min-width:0; height:100%; }
.settings-panel .sp-top { padding:13px 14px 11px; background:#202a33; border-bottom:1px solid #32404a; }
.sp-search { display:block; width:100%; min-height:40px; padding:9px 12px 9px 36px;
  background-color:#141d26; border:1px solid #3a4853; border-radius:11px;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2396a8b6' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='10.8' cy='10.8' r='6.6'/%3E%3Cpath d='m16 16 5 5'/%3E%3C/svg%3E");
  background-position:11px center; background-repeat:no-repeat; background-size:16px; color:#f2f6f9; font:12px Inter,system-ui; margin-bottom:12px;
}
.sp-search::placeholder { color:#8296a5; }
.sp-search:focus { border-color:#a3e635; outline:1px solid #a3e635; }
.sp-builder { display:grid; grid-template-columns:82px minmax(0,1fr); align-items:center; gap:10px; font-size:12px; color:#aebfca; }
.sp-builder > span { font-weight:600; }
.sp-builder select, .settings-panel .row select, .settings-panel .row input:not([type="checkbox"]):not([type="color"]), .settings-panel .row textarea {
  width:100%; min-width:0; background:#141d26; color:#e9f0f6; border:1px solid #3a4954;
  border-radius:9px; min-height:36px; padding:7px 9px; font:12px/1.4 Inter,system-ui;
}
.sp-builder select { padding:7px 10px; min-height:38px; }
.settings-panel select:focus, .settings-panel input:focus, .settings-panel textarea:focus { border-color:#8dc846; outline:1px solid #8dc846; }
.sp-pages { display:flex; flex-wrap:nowrap; gap:5px; margin-top:12px; overflow-x:auto; padding:1px 0 6px; scrollbar-width:thin; }
.sp-pages button { flex:0 0 auto; border-radius:9px; border:1px solid #3b4855; color:#c1ccd5; background:#2a3640; min-height:33px; padding:6px 11px; font-size:11px; font-weight:600; }
.sp-pages button.on { background:#a3e635; border-color:#a3e635; color:#1a260e; font-weight:800; }
.sp-modes { display:flex; gap:3px; margin-top:8px; padding:4px; border-radius:10px; background:#172129; overflow-x:auto; }
.sp-modes button { flex:1 0 auto; min-width:45px; padding:7px 5px; font-size:10px; font-weight:600; border-radius:7px; color:#96a7b5; }
.sp-modes button.on { background:#2e4230; color:#c6ee9b; }
.settings-panel .sp-body { min-height:0; max-height:none; padding:14px 14px 30px; background:#1c232b; scrollbar-color:#4b5b68 transparent; }
.sp-body > h2 { margin:0 0 12px; font-size:16px; font-weight:750; letter-spacing:-.02em; }
.sp-body h3 { color:#dce8ef; font-size:12px; font-weight:700; margin:18px 0 8px; padding:0 0 7px; border-bottom:1px solid #35434c; }
.sp-body section:first-of-type h3 { margin-top:4px; }
.sp-body .muted { color:#8999a5; font-size:10px; }
.settings-panel .row { grid-template-columns:minmax(0,1fr) auto; grid-template-areas:"lbl badge" "key widget";
  column-gap:10px; row-gap:3px; padding:10px 0; min-height:57px; border-bottom:1px solid #2d3943; align-items:center; }
.settings-panel .row .lbl { color:#e3edf3; font-size:12px; font-weight:600; white-space:normal; line-height:1.45; }
.settings-panel .row .lbl:hover { color:#c4f487; }
.settings-panel .row .lbl-cell { max-width:100%; }
.settings-panel .row .key { font-size:10px; max-width:100%; color:#7f919d; }
.settings-panel .row .widget-cell { grid-area:widget; justify-self:end; max-width:100%; gap:6px; }
.settings-panel .row .inputwrap { min-width:0; gap:5px; }
.settings-panel .row input:not([type="checkbox"]):not([type="color"]), .settings-panel .row select { max-width:150px; }
.settings-panel .row textarea { min-width:135px; max-width:220px; }
.settings-panel input[type="checkbox"] { appearance:none; position:relative; width:36px; height:21px; margin:0;
  background:#42505a; border:1px solid #566875; border-radius:99px; cursor:pointer; transition:background .16s ease; }
.settings-panel input[type="checkbox"]::before { content:''; position:absolute; width:15px; height:15px;
  top:2px; left:2px; border-radius:50%; background:#e6edf1; transition:transform .16s ease; }
.settings-panel input[type="checkbox"]:checked { background:#a3e635; border-color:#a3e635; }
.settings-panel input[type="checkbox"]:checked::before { background:#1c290c; transform:translateX(15px); }
.settings-panel input[type="checkbox"]:disabled { cursor:not-allowed; opacity:.4; }
.settings-panel .row .unit { color:#9cabb5; }
.settings-panel .badge { font-size:9px; font-weight:650; border-radius:6px; padding:2px 5px; }
.settings-panel .reset-btn { min-width:25px; min-height:25px; border-radius:7px; border-color:#655239; background:#3e3529; }
.settings-panel .dirty-dot { background:#f2b76f; }
.settings-panel .row.disabled { opacity:.47; }
:host(.sp-embedded) .sp-body { max-height:none; padding:12px 14px 26px; }
@media(max-width:767px) {
  :host(.sp-embedded) .settings-panel { height:100%; }
  :host(.sp-embedded) .sp-top { flex:0 0 auto; padding:12px 12px 10px; }
  :host(.sp-embedded) .sp-body { flex:1 1 auto; min-height:0; max-height:none; overflow-y:auto; padding:10px 12px 28px; }
  .sp-pages { overflow-x:auto; flex-wrap:nowrap; }
  .sp-builder { grid-template-columns:68px minmax(0,1fr); }
  .settings-panel .row { grid-template-columns:minmax(0,1fr) auto; gap:3px 8px; }
  .settings-panel .row .key { max-width:110px; }
  .settings-panel .row input:not([type="checkbox"]):not([type="color"]), .settings-panel .row select, .settings-panel .row textarea { max-width:min(143px,38vw); }
}
@media(max-width:375px) {
  .settings-panel .row { grid-template-columns:minmax(0,1fr) minmax(95px,auto); }
  .settings-panel .row input:not([type="checkbox"]):not([type="color"]), .settings-panel .row select { max-width:112px; }
  .sp-modes button { min-width:38px; font-size:9px; }
}
@media(prefers-reduced-motion:reduce) {
  .settings-panel input[type="checkbox"], .settings-panel input[type="checkbox"]::before { transition:none; }
}

/* V2 — grouped settings, with a permanent search and intuitive visual hierarchy. */
.settings-panel .sp-top { position:relative; z-index:2; background:#1c252e;
  padding:13px 14px 12px; box-shadow:0 6px 20px #080c102f; }
.sp-search { box-shadow:0 2px 6px #0002 inset; }
.sp-search:focus-visible { outline:2px solid #a3e635; outline-offset:1px; }
.sp-pages { gap:6px; margin-top:14px; padding-bottom:7px; }
.sp-pages button { box-shadow:none; transition:background-color .16s ease,border-color .16s ease; }
.sp-pages button:not(.on):hover { background:#354451; border-color:#526271; }
.sp-modes { border:1px solid #2e3b47; background:#131b23; gap:2px; }
.sp-modes button.on { box-shadow:0 2px 8px #0003; background:#334a2d; }
.sp-body { scrollbar-gutter:stable; }
.sp-body > section, .sp-body > h2 + section {
  margin:0 0 12px; padding:12px; background:#222d37; border:1px solid #354550;
  border-radius:13px; box-shadow:0 5px 16px #080b101a; }
.sp-body section h3 { display:flex; gap:7px; align-items:center; margin:0 0 8px; padding:0 0 10px;
  color:#edf3f7; font-size:12px; letter-spacing:.005em; border-bottom:1px solid #364650; }
.sp-body section h3 .muted { font-size:10px; font-weight:400; }
.sp-body .row { padding:11px 2px; border-bottom:1px solid #34414c; }
.sp-body .row:last-child { border-bottom:0; }
.sp-body .row .lbl { color:#eef4f8; font-weight:650; font-size:12px; }
.sp-body .row .key { margin-top:1px; color:#879bab; font-size:10px; }
.sp-body .row .widget-cell { max-width:100%; }
.sp-body .row .badge { opacity:.85; border-radius:6px; letter-spacing:.01em; }
.sp-body .row input:not([type="checkbox"]):not([type="color"]):hover,
.sp-body .row select:hover, .sp-body .row textarea:hover { border-color:#506472; }
.sp-body .row input:not([type="checkbox"]):not([type="color"]):focus,
.sp-body .row select:focus, .sp-body .row textarea:focus { border-color:#a3e635; }
.sp-body .row input[type="checkbox"]:focus-visible { outline:2px solid #a3e635; outline-offset:3px; }
.sp-body .row .reset-btn { background:#3e3529; color:#f5c983; }
.sp-body .row .reset-btn:hover { background:#5a4630; }
.sp-body .row.custom { background:#27323c; border-radius:7px; padding:8px; }
@media(max-width:767px) {
  :host(.sp-embedded) .sp-top { padding:12px 12px 11px; }
  :host(.sp-embedded) .sp-body { padding:10px 10px 26px; }
  .sp-body > section, .sp-body > h2 + section { padding:10px; margin-bottom:10px; }
  .settings-panel .row { min-height:64px; }
  .settings-panel .row .widget-cell { gap:4px; }
  .sp-body .row .lbl { font-size:12px; }
  .settings-panel .row input:not([type="checkbox"]):not([type="color"]),
  .settings-panel .row select { min-height:38px; }
  .settings-panel .row .key { font-size:9px; }
}
@media(min-width:768px) {
  .settings-panel .sp-top { padding-inline:16px; }
  :host(.sp-embedded) .sp-body { padding:14px 16px 35px; }
}
`

function applyPreset(base, preset, keys, idKey, name) {
  const next = { ...base }
  for (const key of keys) delete next[key]
  Object.assign(next, preset)
  if (idKey) next[idKey] = name
  return next
}

export default function Demo() {
  const [settings, setSettings] = useState(() => ({ ...applyAd4SafeMachineLimits(printerSettings(AD4)), thumbnails: '80x60/PNG', printer_settings_id: AD4 }))
  const [plateSettings, setPlateSettings] = useState({})
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 767px)').matches)
  const [drawer, setDrawer] = useState(false)
  const [playbackExpanded, setPlaybackExpanded] = useState(() => !window.matchMedia('(max-width: 767px)').matches)
  const [sliceRequest, setSliceRequest] = useState(0)
  const [catalog, setCatalog] = useState(null)
  const [profileLibrary, setProfileLibrary] = useState(() => readProfileLibrary(browserProfileStorage()))
  const [saveDialog, setSaveDialog] = useState(null)
  const [profileName, setProfileName] = useState('')
  const [profileError, setProfileError] = useState('')
  const [profileNotice, setProfileNotice] = useState('')
  const profileNameRef = useRef(null)
  const [status, setStatus] = useState('Open or drag a model to get started')
  const [progress, setProgress] = useState(null)
  const machine = AD4
  const [autoSlice, setAutoSlice] = useState(false)
  const [objects, setObjects] = useState(0)
  const [sliced, setSliced] = useState(null)
  const [sending, setSending] = useState(false)
  const [printerState, setPrinterState] = useState('Disconnected')
  const [cameraSrc, setCameraSrc] = useState(null)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [managerOpen, setManagerOpen] = useState(false)
  const [testCapturedAt, setTestCapturedAt] = useState(() => new Date())
  const cameraButton = useRef(null)
  const cameraClose = useRef(null)
  const statsCollapsed = useRef(true)
  const [toolbarTarget, setToolbarTarget] = useState(null)
  const viewerHost = useRef(null)
  const animation = useRef(null)
  const manualSelection = useRef(false)
  const playback = useRef({ layer: 0, move: 0, last: 0, remainder: 0, speed: 1, count: 0, waiting: false })
  const [preview, setPreview] = useState({ mode: 'prepare', count: 0, layer: 0, move: 0, max: 0, single: false, playing: false, speed: 1, hasMoves: false, plate: 0 })
  const previewVisible = preview.mode === 'preview' && preview.count > 0
  const materialReady = Boolean(catalog && settings.filament_settings_id)

  useEffect(() => {
    if (!catalog) return
    const stockPresetName = printerDefaultPreset(AD4) || AD4_STOCK_PROCESS
    const standardSettings = catalog.process.settingsFor(AD4_STOCK_PROCESS) || catalog.process.settingsFor(stockPresetName)
    // The upstream AD4 "first recommended filament" is not necessarily PLA.
    // Select our known Artillery PLA Basic recipe explicitly on every fresh load.
    const genericPla = catalog.filament.settingsFor('Generic PLA @Flashforge AD4')
    if (!genericPla) {
      setStatus('Artillery PLA Basic cannot be loaded: Generic PLA source preset is missing.')
      return
    }
    const artillery = makeArtilleryPlaBasic(genericPla)
    setSettings(current => {
      let next = standardSettings ? applyPreset(current, applyAd4SafeProcess(standardSettings), catalog.process.keys, 'print_settings_id', AD4_SAFE_PROCESS) : current
      next = applyPreset(next, artillery, catalog.filament.keys, 'filament_settings_id', ARTILLERY_PLA_BASIC)
      return next
    })
  }, [catalog])
  useEffect(() => { setSliced(null) }, [settings, plateSettings, objects])
  useEffect(() => {
    if (!autoSlice || !objects || sliced || !materialReady) return
    const timer = setTimeout(() => setSliceRequest(value => value + 1), 650)
    return () => clearTimeout(timer)
  }, [autoSlice, objects, settings, plateSettings, sliced, materialReady])
  useEffect(() => {
    const refresh = () => fetch('/api/printer/status').then(r => r.json()).then(data =>
      setPrinterState(data.machine_status ?? data.status ?? 'Connected')).catch(() => setPrinterState('Disconnected'))
    refresh()
    const timer = setInterval(refresh, 8000)
    return () => clearInterval(timer)
  }, [])
  const captureCamera = () => fetch('/api/printer/camera')
    .then(r => { if (!r.ok) throw Error(); return r.blob() })
    .then(blob => { setCameraSrc(current => { if (current) URL.revokeObjectURL(current); return URL.createObjectURL(blob) }); setTestCapturedAt(new Date()) })
    .catch(() => setCameraSrc(null))
  useEffect(() => {
    if (cameraOpen) captureCamera()
    return () => setCameraSrc(current => { if (current) URL.revokeObjectURL(current); return null })
  }, [cameraOpen])

  const sendPrint = async (start) => {
    if (!sliced || sending) return
    if (!materialReady) { setStatus('Select a filament profile before printing.'); return }
    const heatingWarnings = checkArtilleryHeating(sliced.gcode, settings.filament_settings_id)
    if (heatingWarnings.length) {
      setStatus('Print blocked: generated G-code exceeds Artillery PLA Basic temperatures (' + heatingWarnings.join('; ') + ').')
      return
    }
    setSending(true)
    try {
      const response = await fetch(`/api/printer/jobs?start=${start ? 'true' : 'false'}`, {
        method: 'POST', headers: { 'Content-Type': 'text/plain; charset=utf-8' }, body: sliced.gcode,
      })
      const result = await response.json()
      if (!response.ok) throw Error(result.error || 'Unable to send the job')
      setStatus(start ? `Print requested · ${result.remote_name}` : `Uploaded · ${result.remote_name}`)
    } catch (error) { setStatus(`Printer error: ${error.message}`) }
    finally { setSending(false) }
  }

  const pausePlayback = () => {
    if (animation.current != null) cancelAnimationFrame(animation.current)
    animation.current = null
    playback.current.last = 0
    playback.current.remainder = 0
    setPreview(current => current.playing ? { ...current, playing: false } : current)
  }

  const selectLayer = (layer, single = preview.single) => {
    pausePlayback()
    manualSelection.current = true
    const index = Math.min(Math.max(0, Number(layer) || 0), Math.max(0, preview.count - 1))
    if (!selectPreviewLayer(viewerHost.current, index, single)) return
    fullPreviewLayer(viewerHost.current)
    playback.current.layer = index
    playback.current.move = 0
    setPreview(current => ({ ...current, layer: index, single, move: 0 }))
    requestAnimationFrame(() => setPreview(current => ({ ...current, max: previewMoveCount(viewerHost.current) })))
  }

  const stopPlayback = () => {
    pausePlayback()
    manualSelection.current = true
    if (selectPreviewLayer(viewerHost.current, 0, false)) {
      // A new layer is rendered by React after this event; the next frame starts at move zero.
      requestAnimationFrame(() => scrubPreviewMove(viewerHost.current, 0))
    }
    playback.current.layer = 0
    playback.current.move = 0
    setPreview(current => ({ ...current, layer: 0, move: 0, single: false }))
    requestAnimationFrame(() => setPreview(current => ({ ...current, max: previewMoveCount(viewerHost.current) })))
  }

  const playPlayback = (speed = 1) => {
    if (!previewVisible || !getPreviewControls(viewerHost.current)?.move) return
    if (animation.current != null) cancelAnimationFrame(animation.current)
    const state = playback.current
    state.count = preview.count
    state.layer = manualSelection.current ? preview.layer : 0
    state.move = manualSelection.current ? preview.move : 0
    state.speed = speed
    state.last = 0
    state.lastUi = 0
    state.remainder = 0
    state.waiting = false
    // Print from the first layer if a previous run ended at the last move.
    if (state.layer >= state.count - 1 && state.move >= previewMoveCount(viewerHost.current)) {
      state.layer = 0
      state.move = 0
    }
    selectPreviewLayer(viewerHost.current, state.layer, false)
    manualSelection.current = true
    setPreview(current => ({ ...current, layer: state.layer, single: false, playing: true, speed }))

    const tick = timestamp => {
      const run = playback.current
      if (run.waiting) {
        run.waiting = false
        scrubPreviewMove(viewerHost.current, 0)
      }
      const max = previewMoveCount(viewerHost.current)
      if (!getPreviewControls(viewerHost.current)) { pausePlayback(); return }
      const elapsed = run.last ? Math.min(100, timestamp - run.last) : 0
      run.last = timestamp
      run.remainder += elapsed * 0.08 * run.speed // 80 actual toolpath moves per simulated second.
      const step = Math.floor(run.remainder)
      run.remainder -= step
      if (step > 0 && max > 0) {
        run.move = Math.min(max, run.move + step)
        scrubPreviewMove(viewerHost.current, run.move)
      }
      if (max === 0 || run.move >= max) {
        if (run.layer >= run.count - 1) {
          animation.current = null
          setPreview(current => ({ ...current, layer: run.layer, move: max, max, playing: false }))
          return
        }
        run.layer++
        run.move = 0
        run.remainder = 0
        selectPreviewLayer(viewerHost.current, run.layer, false)
        run.waiting = true
      }
      if (timestamp - run.lastUi > 120 || run.waiting) {
        run.lastUi = timestamp
        setPreview(current => ({ ...current, layer: run.layer, move: run.move, max }))
      }
      animation.current = requestAnimationFrame(tick)
    }
    animation.current = requestAnimationFrame(tick)
  }

  useEffect(() => () => { if (animation.current != null) cancelAnimationFrame(animation.current) }, [])

  useEffect(() => {
    if (!previewVisible) return
    let frame
    let attempts = 0
    const inspect = () => {
      const controls = getPreviewControls(viewerHost.current)
      if (!controls && attempts++ < 12) { frame = requestAnimationFrame(inspect); return }
      setPreview(current => ({ ...current, hasMoves: Boolean(controls?.move), max: previewMoveCount(viewerHost.current) }))
    }
    frame = requestAnimationFrame(inspect)
    return () => cancelAnimationFrame(frame)
  }, [previewVisible, preview.plate, preview.count])

  useEffect(() => {
    const query = window.matchMedia('(max-width: 767px)')
    const update = () => setMobile(query.matches)
    query.addEventListener?.('change', update)
    return () => query.removeEventListener?.('change', update)
  }, [])


  // Style the real upstream Shadow DOM controls without replacing their functionality.
  // Discover nested settings hosts, including the desktop sidebar, not only the mobile drawer.
  useEffect(() => {
    const observed = new WeakSet()
    let frame = null
    const setText = (node, value) => {
      if (node && node.textContent !== value) node.textContent = value
    }
    const observe = (root, observer) => {
      if (!observed.has(root)) {
        observer.observe(root, { childList: true, subtree: true })
        observed.add(root)
      }
    }
    const installViewer = root => {
      if (!root.querySelector('[data-responsive-demo]')) {
        const style = document.createElement('style')
        style.dataset.responsiveDemo = ''
        style.textContent = responsiveViewerCss
        root.append(style)
      }
      const logo = root.querySelector('.tb-logo')
      if (logo && logo.getAttribute('href') !== import.meta.env.BASE_URL) logo.href = import.meta.env.BASE_URL
      const topbar = root.querySelector('.topbar')
      if (topbar) {
        let target = topbar.querySelector('[data-ad4-topbar]')
        if (!target) {
          target = document.createElement('div')
          target.className = 'ad4-topbar'
          target.dataset.ad4Topbar = ''
          topbar.insertBefore(target, topbar.querySelector('.tb-right'))
        }
        setToolbarTarget(current => current === target ? current : target)
      }
      const translations = {
        'mode-prepare': 'Prepare', 'mode-preview': 'Preview',
      }
      Object.entries(translations).forEach(([id, label]) =>
        setText(root.querySelector('[data-testid="' + id + '"]'), label))
      const open = root.querySelector('[data-testid="open-file"] span')
      if (open) setText(open, 'Open')
      const project = root.querySelector('[data-testid="save-project"] span')
      if (project && project.textContent === 'Save as 3mf') setText(project, 'Save 3MF')

      const emptyHint = root.querySelector('.empty-hint')
      if (emptyHint) {
        setText(emptyHint.querySelector('.eh-title'), 'Your next project starts here')
        setText(emptyHint.querySelector('.eh-btn'), 'Open 3D model')
        const picture = emptyHint.querySelector('.eh-icon')
        if (picture && picture.textContent !== '◈') setText(picture, '◈')
      }
      const drop = root.querySelector('.drop-overlay')
      if (drop && !drop.textContent.startsWith('Drop your')) {
        setText(drop, 'Drop your 3D file here')
      }
      const card = root.querySelector('.stats-card')
      if (!card) return
      let toggle = card.querySelector('.stats-toggle')
      if (!toggle) {
        toggle = document.createElement('button')
        toggle.type = 'button'
        toggle.className = 'stats-toggle'
        toggle.setAttribute('aria-label', 'Show or hide all slicing statistics')
        const stack = document.createElement('span')
        stack.className = 'stats-title-stack'
        const heading = document.createElement('span')
        heading.className = 'stats-heading'
        const glance = document.createElement('span')
        glance.className = 'stats-glance'
        const chevron = document.createElement('span')
        chevron.className = 'stats-chevron'
        chevron.setAttribute('aria-hidden', 'true')
        stack.append(heading, glance)
        toggle.append(stack, chevron)
        toggle.addEventListener('click', () => {
          statsCollapsed.current = !statsCollapsed.current
          card.classList.toggle('is-collapsed', statsCollapsed.current)
          toggle.setAttribute('aria-expanded', String(!statsCollapsed.current))
          setText(heading, statsCollapsed.current ? '✓ Slicing complete' : 'Slice details')
          setText(chevron, statsCollapsed.current ? '⌄' : '⌃')
        })
        card.prepend(toggle)
      }
      if (card.classList.contains('is-collapsed') !== statsCollapsed.current) {
        card.classList.toggle('is-collapsed', statsCollapsed.current)
      }
      const heading = toggle.querySelector('.stats-heading')
      const glance = toggle.querySelector('.stats-glance')
      const chevron = toggle.querySelector('.stats-chevron')
      const raw = Array.from(card.children).filter(node => node !== toggle)
      const firstLine = raw[0]?.textContent || ''
      const layers = firstLine.match(/(\d+)\s+layers/i)?.[1]
      const filament = raw.map(node => node.textContent).join(' ').match(/Filament\s+([\d.,]+)\s*mm/i)?.[1]
      const totalTime = card.querySelector('[data-testid="print-time"]')?.textContent.match(/(\d+h\s*\d+m)/i)?.[1]
      const pieces = []
      if (layers) pieces.push(layers + ' layers')
      if (totalTime) pieces.push(totalTime.replace(/\s+/g, ' '))
      if (filament) {
        const metres = Number(filament.replace(',', '.')) / 1000
        if (Number.isFinite(metres)) pieces.push(metres.toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' m')
      }
      setText(glance, pieces.join(' · ') || 'Tap to view details')
      setText(heading, statsCollapsed.current ? '✓ Slicing complete' : 'Slice details')
      setText(chevron, statsCollapsed.current ? '⌄' : '⌃')
      toggle.setAttribute('aria-expanded', String(!statsCollapsed.current))
      card.classList.toggle('has-warning', !!card.querySelector('.slice-warn'))
    }
    const installSettings = root => {
      if (!root.querySelector('[data-responsive-settings]')) {
        const style = document.createElement('style')
        style.dataset.responsiveSettings = ''
        style.textContent = responsiveSettingsCss
        root.append(style)
      }
      const search = root.querySelector('.sp-search')
      if (search && search.placeholder !== 'Search settings by name or key…') search.placeholder = 'Search settings by name or key…'
      setText(root.querySelector('.sp-builder > span'), 'Category')
      const modes = { all: 'All', simple: 'Basic', advanced: 'Advanced', expert: 'Expert', develop: 'Developer' }
      root.querySelectorAll('.sp-modes button').forEach(button => {
        const original = button.dataset.mode || button.textContent
        if (modes[original]) {
          button.dataset.mode = original
          setText(button, modes[original])
        }
      })
    }
    const install = () => {
      const queue = [document.getElementById('root')]
      while (queue.length) {
        const container = queue.pop()
        if (!container) continue
        for (const host of container.querySelectorAll('*')) {
          const root = host.shadowRoot
          if (!root) continue
          observe(root, observer)
          if (root.querySelector('.app-shell')) installViewer(root)
          if (root.querySelector('.settings-panel')) installSettings(root)
          queue.push(root)
        }
      }
    }
    const observer = new MutationObserver(() => {
      if (frame != null) return
      frame = requestAnimationFrame(() => { frame = null; install() })
    })
    install()
    observer.observe(document.getElementById('root'), { childList: true, subtree: true })
    return () => {
      observer.disconnect()
      if (frame != null) cancelAnimationFrame(frame)
      setToolbarTarget(null)
    }
  }, [])

  useEffect(() => {
    let live = true
    Promise.all([processPresets(), filamentPresets()]).then(([process, filament]) => {
      if (live) setCatalog({ process, filament })
    }).catch(() => {
      if (live) setStatus('Unable to load the preset catalogs')
    })
    return () => { live = false }
  }, [])

  useEffect(() => {
    if (!drawer) return
    const close = (event) => { if (event.key === 'Escape') { if (saveDialog) setSaveDialog(null); else setDrawer(false) } }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [drawer, saveDialog])

  useEffect(() => {
    if (saveDialog) profileNameRef.current?.focus()
  }, [saveDialog])

  useEffect(() => {
    if (!cameraOpen) return
    cameraClose.current?.focus()
    const close = event => { if (event.key === 'Escape') setCameraOpen(false) }
    window.addEventListener('keydown', close)
    return () => { window.removeEventListener('keydown', close); cameraButton.current?.focus() }
  }, [cameraOpen])

  // All bundled AD4 process profiles use identical conservative motion settings.
  // Saved user profiles are snapshots, so intentionally edited values are never overridden.
  const processOptions = useMemo(() => {
    if (!catalog || !machine) return []
    return [...new Set([AD4_SAFE_PROCESS, ...catalog.process.listFor(machine), ...profileLibrary.process.map(p => p.name)])]
  }, [catalog, machine, profileLibrary.process])
  const filamentOptions = useMemo(() => {
    if (!catalog || !machine) return []
    const recommended = catalog.filament.recommendedFor(machine)
    const original = recommended.length ? recommended : catalog.filament.listFor(machine)
    return [
      ...original,
      { name: ARTILLERY_PLA_BASIC, type: 'PLA', vendor: 'Artillery' },
      ...profileLibrary.filament.map(p => ({ name: p.name, type: 'Custom', vendor: 'You' })),
    ].filter((item, index, array) => array.findIndex(p => p.name === item.name) === index)
  }, [catalog, machine, profileLibrary.filament])

  const chooseProcess = (name) => {
    if (name === SAVE_PROCESS_OPTION) { openSaveDialog('process'); return }
    if (!catalog || !name) return
    const custom = profileLibrary.process.find(p => p.name === name)
    const original = name === AD4_SAFE_PROCESS
      ? catalog.process.settingsFor(AD4_STOCK_PROCESS)
      : catalog.process.settingsFor(name)
    const preset = custom?.values || (original && applyAd4SafeProcess(original))
    if (preset) setSettings(current => applyPreset(current, preset, catalog.process.keys, 'print_settings_id', name))
    setProfileNotice('')
  }
  const chooseFilament = (name) => {
    if (name === SAVE_FILAMENT_OPTION) { openSaveDialog('filament'); return }
    if (!catalog || !name) return
    const custom = profileLibrary.filament.find(p => p.name === name)
    const original = name === ARTILLERY_PLA_BASIC
      ? makeArtilleryPlaBasic(catalog.filament.settingsFor('Generic PLA @Flashforge AD4'))
      : catalog.filament.settingsFor(name)
    const preset = custom?.values || original
    if (preset) setSettings(current => applyPreset(current, preset, catalog.filament.keys, 'filament_settings_id', name))
    setProfileNotice('')
  }

  function openSaveDialog(type) {
    setProfileError('')
    setProfileName(type === 'process' ? 'My AD4 process' : 'My filament')
    setSaveDialog(type)
  }

  function persistLibrary(next) {
    // Commit to storage before reporting success. A blocked/private storage write
    // must never appear as a saved profile.
    writeProfileLibrary(browserProfileStorage(), next)
    setProfileLibrary(next)
  }

  function saveCurrentProfile(event) {
    event.preventDefault()
    if (!catalog || !saveDialog) return
    const type = saveDialog
    const keys = type === 'process' ? catalog.process.keys : catalog.filament.keys
    const names = type === 'process' ? processOptions : filamentOptions.map(item => item.name)
    try {
      const next = addCustomProfile(profileLibrary, type, profileName, settings, keys, names)
      persistLibrary(next)
      const savedName = next[type].at(-1).name
      const idKey = type === 'process' ? 'print_settings_id' : 'filament_settings_id'
      setSettings(current => ({ ...current, [idKey]: savedName }))
      setSaveDialog(null)
      setProfileError('')
      setProfileNotice(`Saved ${type} profile "${savedName}" in this browser.`)
    } catch (error) {
      setProfileError(error.message || 'Could not save the profile.')
    }
  }

  function updateSavedProfile(type) {
    const name = type === 'process' ? settings.print_settings_id : settings.filament_settings_id
    if (!catalog || !profileLibrary[type].some(p => p.name === name)) return
    const keys = type === 'process' ? catalog.process.keys : catalog.filament.keys
    try {
      persistLibrary(replaceCustomProfile(profileLibrary, type, name, settings, keys))
      setProfileNotice(`Updated "${name}" in this browser.`)
    } catch (error) { setProfileNotice(error.message || 'Could not update profile.') }
  }

  function deleteSavedProfile(type) {
    const name = type === 'process' ? settings.print_settings_id : settings.filament_settings_id
    if (!profileLibrary[type].some(p => p.name === name) || !window.confirm(`Delete saved ${type} profile "${name}"?`)) return
    try {
      persistLibrary(removeCustomProfile(profileLibrary, type, name))
      if (type === 'process') chooseProcess(AD4_SAFE_PROCESS)
      else chooseFilament(ARTILLERY_PLA_BASIC)
      setProfileNotice(`Deleted "${name}" from this browser.`)
    } catch (error) { setProfileNotice(error.message || 'Could not delete profile.') }
  }

  // The upstream desktop process selector is still mounted inside Viewport.
  // Normalize its bundled AD4 preset changes as well, without rewriting manual edits
  // or the intentionally independent saved custom process snapshots.
  const setSlicerSettings = update => setSettings(current => {
    const next = typeof update === 'function' ? update(current) : update
    if (!next || typeof next !== 'object') return current
    const changedProcess = next.print_settings_id && next.print_settings_id !== current.print_settings_id
    const bundled = changedProcess && catalog?.process.listFor(AD4).includes(next.print_settings_id)
    const custom = profileLibrary.process.some(p => p.name === next.print_settings_id)
    return bundled && !custom ? { ...next, ...AD4_SAFE_PROCESS_OVERRIDES } : next
  })

  // Keep the native preview controls mounted in the hidden mobile sidebar: the
  // dock below drives those same inputs, so Three Slicer's GPU toolpath and nozzle stay authoritative.
  const panels = { printerCard: false, sliceBar: false, ...(mobile ? { filamentCard: false, objectList: false,
    processCard: false, towerCard: false, resinCard: false } : {}) }
  const processPanel = (panelSettings, setPanelSettings, meta) => (
    <SettingsPanel embedded settings={panelSettings} setSettings={setPanelSettings}
      overriddenKeys={meta?.overriddenKeys} onRevertKey={meta?.onRevertKey} {...panelData} />
  )
  const progressText = progress == null ? status : `Slicing… ${Math.round(progress * 100)}%`

  return <main className={`demo-shell${previewVisible ? ' has-preview' : ''}${playbackExpanded ? ' playback-open' : ''}`}>
    <div className="viewport-host" ref={viewerHost}>
      <Viewport
        slicer={slicer}
        catalog={ad4Catalog}
        settings={settings}
        setSettings={setSlicerSettings}
        plateSettings={plateSettings}
        setPlateSettings={setPlateSettings}
        processPanel={processPanel}
        motionPanel={<SettingsPanel embedded settings={settings} setSettings={setSettings}
          only={{ builder: 'TabPrinter::build_kinematics_page' }} {...panelData} />}
        filamentPanel={(filamentSettings, setFilamentSettings) => <>
          <SettingsPanel embedded settings={filamentSettings} setSettings={setFilamentSettings}
            only={{ builder: 'TabFilament::build' }} {...panelData} />
          <SettingsPanel embedded settings={filamentSettings} setSettings={setFilamentSettings}
            only={{ builder: 'TabFilament::add_filament_overrides_page' }} {...panelData} />
        </>}
        panels={panels}
        features={cameraOpen || managerOpen ? { shortcuts: false } : undefined}
        sliceRequest={sliceRequest}
        onEvent={(event) => {
          if (event.type === 'progress') setProgress(event.value)
          if (event.type === 'slicing' && !event.value) setProgress(null)
          if (event.type === 'slicing' && event.value) pausePlayback()
          if (event.type === 'error') { setProgress(null); setStatus(`Error: ${event.value}`) }
          if (event.type === 'notice') setStatus(event.value)
          if (event.type === 'objects') setObjects(event.value.length)
          if (event.type === 'canvasMode') {
            if (event.value !== 'preview') pausePlayback()
            setPreview(current => ({ ...current, mode: event.value }))
          }
          if (event.type === 'layerCount') {
            pausePlayback()
            manualSelection.current = false
            setPreview(current => ({ ...current, count: event.value, layer: Math.min(current.layer, Math.max(0, event.value - 1)) }))
          }
          if (event.type === 'layerRange') {
            setPreview(current => ({ ...current, layer: event.value.hi }))
            requestAnimationFrame(() => setPreview(current => ({ ...current, max: previewMoveCount(viewerHost.current) })))
          }
          if (event.type === 'moveScrub' && animation.current == null) setPreview(current => ({ ...current, move: event.value.at, max: event.value.max }))
          if (event.type === 'selectedPlate') { pausePlayback(); manualSelection.current = false; setPreview(current => ({ ...current, plate: event.value, layer: 0, move: 0 })) }
        }}
        onSliced={({ plate, stats, gcode }) => {
          pausePlayback()
          manualSelection.current = false
          setProgress(null)
          setStatus(`Slicing complete · ${stats?.layers ?? '—'} layers`)
          // The renderer already provides the exact off-screen model thumbnail
          // used by ThreeSlicer exports; send it and the kernel's real duration.
          const rgba = captureAd4PlateThumbnail(plate)
          setSliced({ gcode: annotateAd4Gcode(gcode, stats, settings, rgba) })
          requestAnimationFrame(() => setPreview(current => ({ ...current, hasMoves: Boolean(getPreviewControls(viewerHost.current)?.move) })))
        }}
      />
    </div>

    {toolbarTarget && createPortal(<>
      <button type="button" className="ad4-printer-state" onClick={() => setManagerOpen(true)} title={`Adventurer 4 · ${printerState}`} aria-label={`Adventurer 4 · ${printerState}`}>
        <strong>AD4</strong><span className={`state-dot${printerState === 'Disconnected' ? '' : ' is-online'}`} />
        <span className="state-text">{printerState}</span>
      </button>
      <button ref={cameraButton} className="camera-trigger" type="button" title="View a printer camera snapshot"
        aria-label="View printer camera" onClick={() => setCameraOpen(true)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 7h3l1.5-2h7L17 7h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1Z"/>
          <circle cx="12" cy="13" r="3.5"/>
        </svg>
      </button>
    </>, toolbarTarget)}

    <div className="ad4-controls">
      <label><input type="checkbox" checked={autoSlice} onChange={event => setAutoSlice(event.target.checked)} /> Auto slice</label>
      {sliced ? <div className="ad4-print" role="group" aria-label="Send job to the Adventurer 4"><button disabled={sending} onClick={() => sendPrint(true)}>{sending ? 'Sending…' : 'Print'}</button>
        <button disabled={sending} onClick={() => sendPrint(false)} title="Upload without starting the print">Upload only</button></div>
        : <button onClick={() => setSliceRequest(value => value + 1)} disabled={!objects}>Slice</button>}
    </div>

    {previewVisible && <section className={`playback-dock${playbackExpanded ? '': ' is-compact'}`} aria-label="Toolpath playback">
      <div className="playback-heading">
        <div className="playback-title"><strong>Nozzle path</strong></div>
        <div className="playback-heading-right">
          <span>Layer {preview.layer + 1} / {preview.count}</span>
          <button type="button" className="playback-expand" onClick={() => setPlaybackExpanded(value => !value)}
            aria-label={playbackExpanded ? 'Collapse toolpath controls' : 'Expand toolpath controls'}
            aria-expanded={playbackExpanded} title={playbackExpanded ? 'Show compact controls' : 'Show all controls'}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>
      </div>
      <div className="playback-layer"><label htmlFor="preview-layer">Layers</label>
        <input id="preview-layer" type="range" min="1" max={preview.count} value={preview.layer + 1}
          onChange={event => selectLayer(Number(event.target.value) - 1)} aria-label="Select layer" />
        <button type="button" className={preview.single ? 'is-selected' : ''} aria-pressed={preview.single}
          onClick={() => selectLayer(preview.layer, !preview.single)} title="Show only this layer">Single layer</button>
      </div>
      <div className="playback-actions">
        <button type="button" disabled={!preview.hasMoves} onClick={() => playPlayback(1)} aria-label="Play toolpath" title="Play" className="playback-primary">▶</button>
        <button type="button" className="playback-extra" disabled={!preview.hasMoves} onClick={() => playPlayback(8)} aria-label="Fast-forward toolpath" title="Fast-forward ×8">⏩</button>
        <button type="button" className="playback-extra" disabled={!preview.hasMoves} onClick={pausePlayback} aria-label="Pause toolpath" title="Pause">Ⅱ</button>
        <button type="button" className="playback-extra" disabled={!preview.hasMoves} onClick={stopPlayback} aria-label="Stop and return to start" title="Stop and return to start">■</button>
        <label className="playback-extra" htmlFor="preview-move">Movement</label>
        <input id="preview-move" type="range" disabled={!preview.hasMoves} min="0" max={Math.max(1, preview.max)} value={Math.min(preview.move, Math.max(1, preview.max))}
          onChange={event => { pausePlayback(); scrubPreviewMove(viewerHost.current, Number(event.target.value)) }} aria-label="Scrub movements in this layer" />
        <span className="playback-count">{preview.hasMoves ? `${preview.move} / ${preview.max}` : 'No FFF nozzle path'}</span>
      </div>
    </section>}

    {managerOpen && <PrinterManager onClose={() => setManagerOpen(false)} />}

    {cameraOpen && <div className="camera-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setCameraOpen(false) }}>
      <section className="camera-modal" role="dialog" aria-modal="true" aria-labelledby="camera-title">
        <header className="camera-head"><div><span className="camera-eyebrow">PRINTER CAMERA</span><h2 id="camera-title">Printer camera</h2></div>
          <button ref={cameraClose} type="button" className="camera-close" onClick={() => setCameraOpen(false)} aria-label="Close camera">×</button></header>
        <figure className="camera-frame"><img src={cameraSrc || `${import.meta.env.BASE_URL}webcam-test.svg`} alt={cameraSrc ? 'Adventurer 4 snapshot' : 'Printer camera placeholder image'} />
          <figcaption>{cameraSrc ? 'Latest Adventurer 4 snapshot' : 'Demo image · Camera unavailable'}</figcaption></figure>
        <footer className="camera-foot"><span>Camera checked: {testCapturedAt.toLocaleString('en-US')}</span>
          <button type="button" onClick={captureCamera}>{cameraSrc ? 'Refresh snapshot' : 'Retry camera'}</button></footer>
      </section>
    </div>}

    {mobile ? <nav className="mobile-nav" aria-label="Quick actions">
        <button className="nav-setting" type="button" title="Slicing settings" aria-label="Open slicing settings" onClick={() => setDrawer(true)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" /><circle cx="9" cy="7" r="2" fill="#26313c"/><circle cx="15" cy="12" r="2" fill="#26313c"/><circle cx="8" cy="17" r="2" fill="#26313c"/>
          </svg>
        </button>
        <span className="nav-status" aria-live="polite">{progressText}</span>
        <label className="nav-auto"><input type="checkbox" role="switch" checked={autoSlice} onChange={event => setAutoSlice(event.target.checked)} /><span>Auto slice</span></label>
        {sliced ? <div className="nav-print-group" role="group" aria-label="Print actions">
          <button className="nav-slice" disabled={sending} onClick={() => sendPrint(true)}>{sending ? 'Sending…' : 'Print'}</button>
          <button className="nav-send" disabled={sending} onClick={() => sendPrint(false)}>Upload only</button>
        </div> : <button className="nav-slice" disabled={!objects || !materialReady} onClick={() => setSliceRequest(value => value + 1)}>Slice</button>}
      </nav> : <button type="button" className="desktop-profile-launcher" onClick={() => setDrawer(true)}
        aria-label="Open custom process and filament profiles">Presets &amp; settings</button>}
      {drawer && <div className="drawer-scrim" onClick={() => { if (!saveDialog) setDrawer(false) }} />}
      <section className={`settings-drawer${drawer ? ' is-open' : ''}`} role="dialog" aria-modal="true" aria-label="Slicing settings">
        <div className="drawer-handle" />
        <header className="drawer-header"><div><span className="drawer-kicker">Print configuration</span><strong>Slicing settings</strong><small>Presets, material and advanced parameters</small></div>
          <button className="close-drawer" onClick={() => setDrawer(false)} aria-label="Close settings">×</button></header>
        <div className="profile-selects">
          <div className="profile-picker">
            <label htmlFor="ad4-process-select">Process</label>
            <select id="ad4-process-select" disabled={!machine || !catalog} value={settings.print_settings_id ?? ''} onChange={event => chooseProcess(event.target.value)}>
              <option value="">Process preset</option>
              <optgroup label="Built-in and compatible">
                {processOptions.filter(name => !profileLibrary.process.some(p => p.name === name)).map(name => <option key={name} value={name}>{name}</option>)}
              </optgroup>
              {profileLibrary.process.length > 0 && <optgroup label="My saved processes">
                {profileLibrary.process.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}
              </optgroup>}
              <option value={SAVE_PROCESS_OPTION}>＋ Save current settings as new profile…</option>
            </select>
            {profileLibrary.process.some(p => p.name === settings.print_settings_id) && <div className="profile-quick-actions">
              <button type="button" onClick={() => updateSavedProfile('process')}>Update saved</button>
              <button type="button" className="profile-delete" onClick={() => deleteSavedProfile('process')}>Delete</button>
            </div>}
          </div>
          <div className="profile-picker">
            <label htmlFor="ad4-material-select">Material</label>
            <select id="ad4-material-select" disabled={!machine || !catalog} value={settings.filament_settings_id ?? ''} onChange={event => chooseFilament(event.target.value)}>
              <option value="">Material preset</option>
              <optgroup label="Built-in materials">
                {filamentOptions.filter(item => !profileLibrary.filament.some(p => p.name === item.name)).map(item =>
                  <option key={item.name} value={item.name}>{item.name}</option>)}
              </optgroup>
              {profileLibrary.filament.length > 0 && <optgroup label="My saved filaments">
                {profileLibrary.filament.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}
              </optgroup>}
              <option value={SAVE_FILAMENT_OPTION}>＋ Save current material as new profile…</option>
            </select>
            {profileLibrary.filament.some(p => p.name === settings.filament_settings_id) && <div className="profile-quick-actions">
              <button type="button" onClick={() => updateSavedProfile('filament')}>Update saved</button>
              <button type="button" className="profile-delete" onClick={() => deleteSavedProfile('filament')}>Delete</button>
            </div>}
          </div>
        </div>
        {profileNotice && <p className="profile-notice" role="status">{profileNotice}</p>}
        <div className="settings-surface"><SettingsPanel embedded settings={settings} setSettings={setSettings} {...panelData} /></div>
        <button className="drawer-slice" onClick={() => { setDrawer(false); sliced ? sendPrint(true) : setSliceRequest(value => value + 1) }}>{sliced ? 'Print' : 'Slice model'}</button>
      </section>
      {saveDialog && <div className="profile-save-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setSaveDialog(null) }}>
        <form className="profile-save-dialog" role="dialog" aria-modal="true" aria-labelledby="profile-save-title" onSubmit={saveCurrentProfile}>
          <span className="profile-save-eyebrow">My presets</span>
          <h2 id="profile-save-title">Save new {saveDialog === 'process' ? 'process' : 'filament'} profile</h2>
          <p>Save a separate copy of your current {saveDialog === 'process' ? 'print settings' : 'material settings'}.
            Existing profiles will not change.</p>
          <label htmlFor="new-profile-name">Profile name</label>
          <input ref={profileNameRef} id="new-profile-name" value={profileName} onChange={event => { setProfileName(event.target.value); setProfileError('') }}
            maxLength={80} required aria-invalid={!!profileError} aria-describedby={profileError ? 'profile-save-error' : undefined}
            placeholder={saveDialog === 'process' ? 'e.g. My detailed 0.2 mm' : 'e.g. Artillery PLA – White'} />
          {profileError && <p className="profile-save-error" id="profile-save-error" role="alert">{profileError}</p>}
          <p className="profile-save-note">Saved locally in this browser. Clear site data or use another device and these profiles will not be available there.</p>
          <div className="profile-save-actions">
            <button type="button" className="profile-cancel" onClick={() => setSaveDialog(null)}>Cancel</button>
            <button type="submit" className="profile-confirm">Save profile</button>
          </div>
        </form>
      </div>}
  </main>
}
