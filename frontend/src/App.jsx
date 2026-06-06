// frontend/travel-planner-ui/src/App.jsx
// WANDR — Modern Animated Travel Planner UI
// Drop-in replacement: same API contract, completely redesigned

import { useState, useEffect, useCallback, useRef } from "react";

const API = "http://localhost:8000";

const fmt = (n) =>
  n != null ? `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

// ─── STYLES ─────────────────────────────────────────────────
const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0a0f1e;
    --bg2:       #0e1528;
    --surface:   #141b2d;
    --surface2:  #1a2240;
    --border:    rgba(255,255,255,0.07);
    --border2:   rgba(255,255,255,0.14);
    --text:      #f0f2f8;
    --muted:     #7a8aaa;
    --accent:    #4f8ef7;
    --accent2:   #7eb8ff;
    --gold:      #f0c060;
    --gold-d:    #c8963a;
    --green:     #3dd68c;
    --green-d:   #1a7a4a;
    --red:       #f87171;
    --red-d:     #7f1d1d;
    --glow:      0 0 40px rgba(79,142,247,0.15);
  }

  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* ─── BACKGROUND ORBS ─── */
  .orb-container {
    position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden;
  }
  .orb {
    position: absolute; border-radius: 50%;
    filter: blur(80px); opacity: 0.35;
    animation: orb-drift 20s ease-in-out infinite;
  }
  .orb-1 { width: 600px; height: 600px; background: #1e3a8a; top: -200px; left: -200px; animation-duration: 25s; }
  .orb-2 { width: 400px; height: 400px; background: #0f4c3a; bottom: -100px; right: -100px; animation-duration: 18s; animation-delay: -8s; }
  .orb-3 { width: 300px; height: 300px; background: #3b1f6a; top: 40%; right: 20%; animation-duration: 22s; animation-delay: -4s; }
  @keyframes orb-drift {
    0%, 100% { transform: translate(0,0) scale(1); }
    33%  { transform: translate(30px,-20px) scale(1.05); }
    66%  { transform: translate(-20px,30px) scale(0.95); }
  }

  /* ─── APP SHELL ─── */
  .app {
    position: relative; z-index: 1;
    max-width: 700px; margin: 0 auto;
    padding: 3rem 1.5rem 8rem;
  }

  /* ─── LOGO ─── */
  .logo-wrap { margin-bottom: 3rem; }
  .logo {
    font-family: 'DM Serif Display', serif;
    font-size: 2.25rem;
    font-style: italic;
    background: linear-gradient(135deg, #7eb8ff 0%, #4f8ef7 40%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
  }
  .tagline {
    font-size: 0.72rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-top: 0.2rem;
  }

  /* ─── CARD ─── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 1.75rem 2rem;
    margin-bottom: 1rem;
    transition: border-color 0.3s;
    animation: card-in 0.5s cubic-bezier(0.22,1,0.36,1) both;
  }
  .card:hover { border-color: var(--border2); }
  @keyframes card-in {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .card-title {
    font-family: 'DM Serif Display', serif;
    font-size: 1rem;
    font-weight: 400;
    margin-bottom: 1.25rem;
    color: var(--text);
    opacity: 0.9;
  }

  /* ─── FORM ─── */
  .field { margin-bottom: 1rem; }
  .field label {
    display: block;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.45rem;
  }
  .field input, .field textarea {
    width: 100%;
    padding: 0.65rem 0.95rem;
    border: 1px solid var(--border);
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    background: var(--bg2);
    color: var(--text);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .field input:focus, .field textarea:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(79,142,247,0.12);
  }
  .field input::placeholder, .field textarea::placeholder { color: var(--muted); opacity: 0.6; }
  .field textarea { resize: vertical; min-height: 72px; }
  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }

  /* ─── BUTTONS ─── */
  .btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.7rem 1.5rem;
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.875rem; font-weight: 500;
    cursor: pointer; border: none;
    transition: opacity 0.15s, transform 0.1s, box-shadow 0.2s;
    letter-spacing: 0.01em;
  }
  .btn:active { transform: scale(0.97); }
  .btn-primary {
    background: linear-gradient(135deg, #4f8ef7, #6366f1);
    color: #fff;
    box-shadow: 0 4px 24px rgba(79,142,247,0.3);
  }
  .btn-primary:hover { box-shadow: 0 6px 32px rgba(79,142,247,0.45); }
  .btn-primary:disabled { opacity: 0.45; cursor: not-allowed; box-shadow: none; }
  .btn-outline {
    background: var(--surface2);
    border: 1px solid var(--border2);
    color: var(--text);
  }
  .btn-outline:hover { background: var(--surface); }
  .btn-danger { background: linear-gradient(135deg, #ef4444, #b91c1c); color: #fff; }
  .btn-row { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.5rem; }

  /* ─── STEP BAR ─── */
  .steps {
    display: flex; align-items: center;
    margin-bottom: 2.5rem;
    animation: card-in 0.4s ease both;
  }
  .step { display: flex; align-items: center; gap: 0.45rem; }
  .step-num {
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 600;
    border: 1.5px solid var(--border2);
    color: var(--muted);
    background: var(--surface);
    transition: all 0.3s cubic-bezier(0.22,1,0.36,1);
  }
  .step-num.active {
    border-color: var(--accent);
    background: var(--accent);
    color: #fff;
    box-shadow: 0 0 16px rgba(79,142,247,0.4);
  }
  .step-num.done {
    border-color: var(--green);
    background: rgba(61,214,140,0.12);
    color: var(--green);
  }
  .step-label { font-size: 0.72rem; color: var(--muted); transition: color 0.3s; }
  .step-label.active { color: var(--text); font-weight: 500; }
  .step-line { flex: 1; height: 1px; background: var(--border2); margin: 0 0.5rem; }

  /* ─── AGENT CARDS ─── */
  .agents-grid {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 0.75rem; margin-bottom: 1.25rem;
  }
  .agent-card {
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.1rem 1.25rem;
    background: var(--bg2);
    transition: border-color 0.4s, box-shadow 0.4s;
    position: relative; overflow: hidden;
  }
  .agent-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: transparent;
    transition: background 0.4s;
    border-radius: 14px 14px 0 0;
  }
  .agent-card.done { border-color: rgba(61,214,140,0.3); box-shadow: 0 0 20px rgba(61,214,140,0.06); }
  .agent-card.done::before { background: linear-gradient(90deg, var(--green), transparent); }
  .agent-card.running { border-color: rgba(240,192,96,0.3); box-shadow: 0 0 20px rgba(240,192,96,0.06); }
  .agent-card.running::before { background: linear-gradient(90deg, var(--gold), transparent); }

  .agent-header {
    display: flex; align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }
  .agent-name {
    font-size: 0.7rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.1em;
    color: var(--muted);
  }
  .agent-icon {
    font-size: 0.85rem;
    margin-right: 0.3rem;
    display: inline-block;
    transition: transform 0.3s;
  }
  .agent-card.running .agent-icon { animation: icon-pulse 1.5s ease-in-out infinite; }
  @keyframes icon-pulse { 0%,100%{ transform: scale(1) } 50%{ transform: scale(1.15) } }

  .status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--border2);
    transition: background 0.4s, box-shadow 0.4s;
  }
  .status-dot.done { background: var(--green); box-shadow: 0 0 8px rgba(61,214,140,0.6); }
  .status-dot.running {
    background: var(--gold);
    box-shadow: 0 0 8px rgba(240,192,96,0.6);
    animation: dot-pulse 1s ease-in-out infinite;
  }
  @keyframes dot-pulse { 0%,100%{ opacity: 1 } 50%{ opacity: 0.3 } }

  .agent-value {
    font-family: 'DM Serif Display', serif;
    font-size: 1.3rem;
    font-weight: 400;
    color: var(--text);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    min-height: 1.8rem;
  }
  .agent-value.searching {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    color: var(--gold);
    display: flex; align-items: center; gap: 0.4rem;
    padding-top: 0.25rem;
  }
  .agent-note {
    font-size: 0.71rem; color: var(--muted);
    margin-top: 0.2rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  /* ─── TYPING DOTS ─── */
  .typing-dots span {
    display: inline-block; width: 4px; height: 4px;
    border-radius: 50%; background: var(--gold);
    margin-right: 2px;
    animation: typing 1.2s ease-in-out infinite;
  }
  .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
  .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes typing { 0%,80%,100%{ transform: scale(0.7); opacity: 0.4 } 40%{ transform: scale(1); opacity: 1 } }

  /* ─── BUDGET BAR ─── */
  .budget-wrap { margin: 1.25rem 0 0; }
  .budget-labels {
    display: flex; justify-content: space-between;
    font-size: 0.78rem; color: var(--muted); margin-bottom: 0.5rem;
  }
  .budget-labels strong { color: var(--text); }
  .budget-track {
    height: 5px; background: var(--border2);
    border-radius: 99px; overflow: hidden;
  }
  .budget-fill {
    height: 100%; border-radius: 99px;
    transition: width 0.8s cubic-bezier(0.22,1,0.36,1);
  }
  .budget-fill.ok   { background: linear-gradient(90deg, var(--green), #3dd68c88); }
  .budget-fill.over { background: linear-gradient(90deg, var(--red), #f8717188); }
  .budget-over-msg {
    font-size: 0.7rem; color: var(--red);
    margin-top: 0.35rem;
    display: flex; align-items: center; gap: 0.3rem;
  }

  /* ─── PILL ─── */
  .pill {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.25rem 0.7rem;
    border-radius: 99px;
    font-size: 0.68rem; font-weight: 600;
    letter-spacing: 0.05em;
  }
  .pill-running { background: rgba(240,192,96,0.1); color: var(--gold); border: 1px solid rgba(240,192,96,0.2); }
  .pill-waiting { background: rgba(79,142,247,0.1); color: var(--accent2); border: 1px solid rgba(79,142,247,0.2); }
  .pill-done    { background: rgba(61,214,140,0.1); color: var(--green); border: 1px solid rgba(61,214,140,0.2); }
  .pill-error   { background: rgba(248,113,113,0.1); color: var(--red); border: 1px solid rgba(248,113,113,0.2); }

  /* ─── NOTICE ─── */
  .notice {
    display: flex; align-items: flex-start; gap: 0.65rem;
    padding: 0.9rem 1.1rem;
    border-radius: 12px;
    font-size: 0.85rem;
    margin-bottom: 1rem;
    animation: card-in 0.4s ease both;
  }
  .notice-ok   { background: rgba(61,214,140,0.07); color: #6ee7b7; border: 1px solid rgba(61,214,140,0.18); }
  .notice-warn { background: rgba(240,192,96,0.07); color: var(--gold); border: 1px solid rgba(240,192,96,0.18); }
  .notice-err  { background: rgba(248,113,113,0.07); color: var(--red); border: 1px solid rgba(248,113,113,0.18); }

  /* ─── SPINNER ─── */
  .spinner {
    width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.2);
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    display: inline-block; flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ─── PROGRESS RING (decorative) ─── */
  .progress-ring-wrap {
    display: flex; justify-content: center;
    margin: 1.5rem 0 0.75rem;
  }
  .progress-ring { position: relative; width: 90px; height: 90px; }
  .progress-ring svg { transform: rotate(-90deg); }
  .progress-ring-label {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem;
  }
  .progress-ring-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.6rem; color: var(--muted);
    letter-spacing: 0.06em; text-transform: uppercase;
  }

  /* ─── ITINERARY ─── */
  .itinerary-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2.25rem 2.5rem;
    line-height: 1.8;
    font-size: 0.9rem;
    animation: card-in 0.6s ease both;
  }
  .itinerary-wrap h1, .itinerary-wrap h2, .itinerary-wrap h3 {
    font-family: 'DM Serif Display', serif;
    font-weight: 400;
    margin: 1.75rem 0 0.6rem;
    color: var(--text);
  }
  .itinerary-wrap h1 { font-size: 1.6rem; }
  .itinerary-wrap h2 { font-size: 1.2rem; color: var(--accent2); }
  .itinerary-wrap h3 { font-size: 1rem; }
  .itinerary-wrap p  { margin-bottom: 0.7rem; color: rgba(240,242,248,0.85); }
  .itinerary-wrap ul, .itinerary-wrap ol { padding-left: 1.4rem; margin-bottom: 0.7rem; }
  .itinerary-wrap li { margin-bottom: 0.25rem; color: rgba(240,242,248,0.85); }
  .itinerary-wrap strong { font-weight: 600; color: var(--text); }
  .itinerary-wrap em { font-style: italic; color: var(--muted); }
  .itinerary-wrap blockquote {
    border-left: 3px solid var(--accent);
    padding-left: 1rem; color: var(--muted); margin: 1rem 0;
    background: var(--bg2); border-radius: 0 8px 8px 0; padding: 0.75rem 1rem;
  }
  .itinerary-wrap table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 1rem 0; }
  .itinerary-wrap th, .itinerary-wrap td { padding: 0.55rem 0.75rem; border: 1px solid var(--border); text-align: left; }
  .itinerary-wrap th { background: var(--bg2); font-weight: 500; color: var(--accent2); }
  .itinerary-wrap code {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 5px; padding: 0.1em 0.4em;
    font-size: 0.82em; font-family: monospace; color: var(--gold);
  }
  .itinerary-wrap hr { border: none; border-top: 1px solid var(--border); margin: 1.75rem 0; }

  /* ─── VIEW TRANSITIONS ─── */
  .view-enter { animation: card-in 0.5s cubic-bezier(0.22,1,0.36,1) both; }

  /* ─── ANIMATED BG GRID ─── */
  .bg-grid {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
    background-size: 60px 60px;
    mask-image: radial-gradient(ellipse 80% 80% at 50% 0%, black 30%, transparent 100%);
  }

  /* ─── STAGGER ANIM HELPERS ─── */
  .stagger-1 { animation-delay: 0.05s; }
  .stagger-2 { animation-delay: 0.10s; }
  .stagger-3 { animation-delay: 0.15s; }
  .stagger-4 { animation-delay: 0.20s; }

  /* ─── SUPERVISOR PLAN ─── */
  .supervisor-pre {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 10px; padding: 1rem;
    font-size: 0.8rem; color: var(--muted);
    white-space: pre-wrap; line-height: 1.65;
    max-height: 240px; overflow-y: auto;
  }

  @media (max-width: 480px) {
    .app { padding: 2rem 1rem 6rem; }
    .agents-grid { grid-template-columns: 1fr; }
    .row-2, .row-3 { grid-template-columns: 1fr; }
  }
`;

// ─── MARKDOWN ────────────────────────────────────────────────
function renderMarkdown(md) {
  if (!md) return "";
  let html = md.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  html = html.replace(/```[\w]*\n([\s\S]*?)```/g,"<pre><code>$1</code></pre>");
  html = html.replace(/^### (.+)$/gm,"<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm,"<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm,"<h1>$1</h1>");
  html = html.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g,"<em>$1</em>");
  html = html.replace(/`([^`]+)`/g,"<code>$1</code>");
  html = html.replace(/^&gt; (.+)$/gm,"<blockquote>$1</blockquote>");
  html = html.replace(/^---+$/gm,"<hr/>");
  html = html.replace(/(^- .+\n?)+/gm,(b)=>`<ul>${b.trim().split("\n").map(l=>`<li>${l.replace(/^- /,"")}</li>`).join("")}</ul>`);
  html = html.replace(/(^\d+\. .+\n?)+/gm,(b)=>`<ol>${b.trim().split("\n").map(l=>`<li>${l.replace(/^\d+\. /,"")}</li>`).join("")}</ol>`);
  html = html.replace(/(^\|.+\|\n?)+/gm,(b)=>{
    const rows=b.trim().split("\n").filter(r=>!/^\|[-| ]+\|$/.test(r));
    if(!rows.length)return b;
    const head=rows[0].split("|").filter(Boolean).map(c=>`<th>${c.trim()}</th>`).join("");
    const body=rows.slice(1).map(r=>"<tr>"+r.split("|").filter(Boolean).map(c=>`<td>${c.trim()}</td>`).join("")+"</tr>").join("");
    return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  });
  html=html.replace(/\n\n+/g,"</p><p>");
  html=`<p>${html}</p>`;
  ["h1","h2","h3"].forEach(t=>{html=html.replace(new RegExp(`<p>(<${t}>)`,"g"),"$1").replace(new RegExp(`(</${t}>)<\\/p>`,"g"),"$1");});
  ["ul","ol","table","blockquote","pre","hr/"].forEach(t=>{
    const close=t.endsWith("/")?"":`</${t.replace("/","")}>`;
    html=html.replace(new RegExp(`<p>(<${t}>)`,"g"),"$1");
    if(close)html=html.replace(new RegExp(`(${close.replace("/","\\/")})<\\/p>`,"g"),"$1");
  });
  html=html.replace(/<p><\/p>/g,"");
  return html;
}

// ─── STEP BAR ────────────────────────────────────────────────
const STEPS = ["Details", "Agents", "Review", "Itinerary"];

function StepBar({ current }) {
  return (
    <div className="steps">
      {STEPS.map((label, i) => {
        const state = i < current ? "done" : i === current ? "active" : "";
        return (
          <div key={i} style={{ display:"flex", alignItems:"center", flex: i < STEPS.length-1 ? 1 : "none" }}>
            <div className="step">
              <div className={`step-num ${state}`}>{i < current ? "✓" : i + 1}</div>
              <span className={`step-label ${state}`}>{label}</span>
            </div>
            {i < STEPS.length - 1 && <div className="step-line" />}
          </div>
        );
      })}
    </div>
  );
}

// ─── AGENT GRID ──────────────────────────────────────────────
function AgentGrid({ status }) {
  const agents = [
    { key:"flights",    label:"Flights",    icon:"✈",  value: status.flights     ? fmt(status.flights.estimated_cost)     : null, note: status.flights?.summary },
    { key:"hotels",     label:"Hotels",     icon:"🏨", value: status.hotels      ? fmt(status.hotels.estimated_cost)      : null, note: status.hotels?.summary },
    { key:"activities", label:"Activities", icon:"🗺", value: status.activities  ? fmt(status.activities.estimated_cost)  : null, note: status.activities?.summary },
    { key:"visa",       label:"Visa",       icon:"📋", value: status.visa_info   ? (status.visa_info.required ? fmt(status.visa_info.estimated_cost) : "Not required") : null, note: status.visa_info?.summary },
  ];
  return (
    <div className="agents-grid">
      {agents.map((a, idx) => {
        const done = !!a.value;
        const running = !done && status.status === "running";
        return (
          <div key={a.key} className={`agent-card ${done?"done":running?"running":""} stagger-${idx+1}`} style={{ animationName:"card-in", animationDuration:"0.5s", animationFillMode:"both" }}>
            <div className="agent-header">
              <span className="agent-name">
                <span className="agent-icon">{a.icon}</span>{a.label}
              </span>
              <div className={`status-dot ${done?"done":running?"running":""}`} />
            </div>
            {done ? (
              <>
                <div className="agent-value">{a.value}</div>
                {a.note && <div className="agent-note">{a.note}</div>}
              </>
            ) : running ? (
              <div className="agent-value searching">
                <span className="typing-dots"><span/><span/><span/></span>
                Searching
              </div>
            ) : (
              <div className="agent-value" style={{ color:"var(--muted)", fontSize:"0.85rem", paddingTop:"0.2rem" }}>Pending</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── BUDGET BAR ──────────────────────────────────────────────
function BudgetBar({ total, budget }) {
  if (!budget) return null;
  const pct = Math.min((total / budget) * 100, 100);
  const over = total > budget;
  return (
    <div className="budget-wrap">
      <div className="budget-labels">
        <span>Estimated: <strong>{fmt(total)}</strong></span>
        <span>Budget: <strong>{fmt(budget)}</strong></span>
      </div>
      <div className="budget-track">
        <div className={`budget-fill ${over?"over":"ok"}`} style={{ width:`${pct}%` }} />
      </div>
      {over && (
        <div className="budget-over-msg">
          ⚠ Over budget by {fmt(total-budget)} — agents replanning with cheaper options
        </div>
      )}
    </div>
  );
}

// ─── PROGRESS RING ───────────────────────────────────────────
function ProgressRing({ done, total }) {
  const pct = total > 0 ? Math.round((done/total)*100) : 0;
  const r = 36; const circ = 2 * Math.PI * r;
  return (
    <div className="progress-ring-wrap">
      <div className="progress-ring">
        <svg width="90" height="90">
          <circle cx="45" cy="45" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6"/>
          <circle cx="45" cy="45" r={r} fill="none"
            stroke={done===total && total>0 ? "var(--green)" : "var(--accent)"}
            strokeWidth="6"
            strokeDasharray={circ}
            strokeDashoffset={circ*(1-pct/100)}
            strokeLinecap="round"
            style={{ transition:"stroke-dashoffset 0.8s cubic-bezier(0.22,1,0.36,1), stroke 0.4s" }}
          />
        </svg>
        <div className="progress-ring-label">
          <span style={{ color: done===total&&total>0 ? "var(--green)" : "var(--accent2)" }}>{done}/{total}</span>
          <span className="progress-ring-sub">agents</span>
        </div>
      </div>
    </div>
  );
}

// ─── VIEW 1 — PLAN FORM ──────────────────────────────────────
function PlanForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    destination:   "Tokyo, Japan",
    origin:        "Delhi, India",
    duration_days: "5",
    budget:        "80000",
    travel_dates:  "Jan 15 - Jan 20, 2026",
    num_travelers: "1",
    preferences:   "budget hotels, street food, anime",
  });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({ ...form, duration_days: parseInt(form.duration_days), budget: parseFloat(form.budget), num_travelers: parseInt(form.num_travelers) });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="card stagger-1" style={{ animationName:"card-in" }}>
        <div className="card-title">Where are you going?</div>
        <div className="row-2">
          <div className="field">
            <label>From</label>
            <input value={form.origin} onChange={set("origin")} placeholder="Delhi, India" required />
          </div>
          <div className="field">
            <label>To</label>
            <input value={form.destination} onChange={set("destination")} placeholder="Tokyo, Japan" required />
          </div>
        </div>
        <div className="field">
          <label>Travel dates</label>
          <input value={form.travel_dates} onChange={set("travel_dates")} placeholder="Jan 15 - Jan 20, 2026" required />
        </div>
      </div>

      <div className="card stagger-2" style={{ animationName:"card-in" }}>
        <div className="card-title">Trip details</div>
        <div className="row-3">
          <div className="field">
            <label>Duration (days)</label>
            <input type="number" min="1" max="30" value={form.duration_days} onChange={set("duration_days")} required />
          </div>
          <div className="field">
            <label>Budget (₹ INR)</label>
            <input type="number" min="1000" value={form.budget} onChange={set("budget")} required />
          </div>
          <div className="field">
            <label>Travelers</label>
            <input type="number" min="1" max="10" value={form.num_travelers} onChange={set("num_travelers")} required />
          </div>
        </div>
        <div className="field">
          <label>Preferences &amp; interests</label>
          <textarea value={form.preferences} onChange={set("preferences")} placeholder="budget hotels, street food, anime, photography…" />
        </div>
      </div>

      <div className="btn-row stagger-3" style={{ animation:"card-in 0.5s ease both", animationDelay:"0.15s" }}>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? <><span className="spinner" /> Planning…</> : "Plan my trip →"}
        </button>
      </div>
    </form>
  );
}

// ─── VIEW 2 — PROCESSING ─────────────────────────────────────
function Processing({ statusData }) {
  const st = statusData?.status;
  const agentKeys = ["flights","hotels","activities","visa_info"];
  const doneCount = agentKeys.filter(k => statusData?.[k]).length;

  return (
    <div className="view-enter">
      <div className="card">
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"1.25rem" }}>
          <div className="card-title" style={{ marginBottom:0 }}>AI agents at work</div>
          {st === "running" && <span className="pill pill-running"><span className="spinner" style={{ width:10, height:10 }} />Running</span>}
          {st === "awaiting_approval" && <span className="pill pill-waiting">✓ Ready</span>}
        </div>

        <ProgressRing done={doneCount} total={4} />

        {statusData && (
          <>
            <AgentGrid status={statusData} />
            <BudgetBar total={statusData.total_estimated_cost ?? 0} budget={statusData.budget} />
          </>
        )}

        {st === "running" && (
          <div style={{ fontSize:"0.78rem", color:"var(--muted)", textAlign:"center", marginTop:"1rem" }}>
            Agents run in parallel — typically 15–30 seconds
          </div>
        )}
      </div>

      {statusData?.budget_status === "over_budget" && (
        <div className="notice notice-warn">
          ⚠ Over budget — supervisor replanning with cheaper alternatives (retry {statusData.retry_count ?? 0}/3)
        </div>
      )}
    </div>
  );
}

// ─── VIEW 3 — REVIEW ─────────────────────────────────────────
function ReviewGate({ threadId, statusData, onApprove, onReject, loading }) {
  const s = statusData ?? {};
  return (
    <div className="view-enter">
      <div className="notice notice-ok">
        ✓ All agents finished — review the cost breakdown and approve to generate your itinerary.
      </div>

      <div className="card">
        <div className="card-title">Cost breakdown</div>
        <AgentGrid status={s} />
        <BudgetBar total={s.total_estimated_cost ?? 0} budget={s.budget} />
      </div>

      {s.supervisor_plan && (
        <div className="card">
          <div className="card-title">Supervisor's plan</div>
          <pre className="supervisor-pre">{s.supervisor_plan}</pre>
        </div>
      )}

      <div className="btn-row">
        <button className="btn btn-outline" onClick={onReject} disabled={loading}>✕ Reject</button>
        <button className="btn btn-primary" onClick={onApprove} disabled={loading}>
          {loading ? <><span className="spinner" /> Compiling…</> : "✓ Approve & generate itinerary"}
        </button>
      </div>
    </div>
  );
}

// ─── VIEW 4 — FINAL ──────────────────────────────────────────
function FinalItinerary({ data, onReset }) {
  const html = renderMarkdown(data?.itinerary ?? "");
  return (
    <div className="view-enter">
      <div className="notice notice-ok">
        ✓ Your personalised itinerary is ready! Total cost: <strong>{fmt(data?.total_estimated_cost)}</strong>
      </div>
      <div className="itinerary-wrap" dangerouslySetInnerHTML={{ __html: html }} />
      <div className="btn-row" style={{ marginTop:"1.5rem" }}>
        <button className="btn btn-outline" onClick={onReset}>← Plan another trip</button>
      </div>
    </div>
  );
}

// ─── ROOT ────────────────────────────────────────────────────
export default function App() {
  const [view, setView]         = useState("form");
  const [threadId, setThreadId] = useState(null);
  const [statusData, setStatus] = useState(null);
  const [finalData, setFinal]   = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const pollRef                 = useRef(null);

  const stepIndex = { form:0, processing:1, review:2, done:3 }[view] ?? 0;

  useEffect(() => {
    const tag = document.createElement("style");
    tag.innerHTML = STYLES;
    document.head.appendChild(tag);
    return () => document.head.removeChild(tag);
  }, []);

  const startPolling = useCallback((tid) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/status/${tid}`);
        const data = await res.json();
        setStatus(data);
        if (data.status === "awaiting_approval") { clearInterval(pollRef.current); setView("review"); }
        else if (data.status === "done") {
          clearInterval(pollRef.current);
          const r2 = await fetch(`${API}/api/trip/${tid}`);
          setFinal(await r2.json());
          setView("done");
        } else if (data.status === "error") {
          clearInterval(pollRef.current); setError(data.error ?? "Unknown error"); setView("error");
        }
      } catch(e) { console.error("Poll error",e); }
    }, 2500);
  }, []);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const handleSubmit = async (formData) => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API}/api/plan`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(formData) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Failed to start plan");
      setThreadId(data.thread_id); setView("processing"); startPolling(data.thread_id);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleApprove = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/approve`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ thread_id: threadId, approved: true }) });
      if (!res.ok) throw new Error("Approval failed");
      setView("processing"); startPolling(threadId);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleReject = async () => {
    await fetch(`${API}/api/approve`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ thread_id: threadId, approved: false }) });
    handleReset();
  };

  const handleReset = () => {
    clearInterval(pollRef.current);
    setView("form"); setThreadId(null); setStatus(null); setFinal(null); setError(null);
  };

  return (
    <>
      <div className="bg-grid" />
      <div className="orb-container">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>
      <div className="app">
        <div className="logo-wrap">
          <div className="logo">Wandr</div>
          <div className="tagline">AI-powered travel planning</div>
        </div>

        {view !== "form" && <StepBar current={stepIndex} />}

        {error && (
          <div className="notice notice-err">
            ✕ {error}
            <button className="btn btn-outline" style={{ marginLeft:"auto", padding:"0.25rem 0.65rem", fontSize:"0.75rem" }} onClick={handleReset}>Start over</button>
          </div>
        )}

        {view === "form"       && <PlanForm onSubmit={handleSubmit} loading={loading} />}
        {view === "processing" && <Processing statusData={statusData} />}
        {view === "review"     && <ReviewGate threadId={threadId} statusData={statusData} onApprove={handleApprove} onReject={handleReject} loading={loading} />}
        {view === "done"       && <FinalItinerary data={finalData} onReset={handleReset} />}
      </div>
    </>
  );
}