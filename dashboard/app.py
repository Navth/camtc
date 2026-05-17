"""CAMTC Real-Time Dashboard — serves the HTML dashboard via FastAPI."""
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


def create_dashboard_app(simulator=None) -> FastAPI:
    app = FastAPI(title="CAMTC Dashboard")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/api/status")
    async def status():
        if simulator is None:
            return {"status": "no simulator"}
        return simulator.get_status()

    @app.get("/api/metrics")
    async def metrics():
        if simulator is None:
            return {}
        return simulator.get_metrics()

    @app.get("/api/nodes")
    async def nodes():
        if simulator is None:
            return []
        return [n.to_dict() for n in simulator.nodes]

    @app.get("/api/consensus")
    async def consensus():
        if simulator is None:
            return {}
        return simulator.nodes[0].consensus.to_dict() if simulator.nodes else {}

    @app.get("/api/reputation")
    async def reputation():
        if simulator is None:
            return {}
        return simulator.nodes[0].reputation.to_dict() if simulator.nodes else {}

    @app.get("/api/anchors")
    async def anchors():
        if simulator is None:
            return []
        return simulator.anchor.get_anchors()

    @app.get("/api/transactions/recent")
    async def recent_transactions():
        if simulator is None or not simulator.nodes:
            return []
        txs = simulator.nodes[0].ledger.get_all_transactions()
        return [tx.to_dict() for tx in txs[-100:]]

    @app.get("/api/latencies")
    async def latencies():
        if simulator is None:
            return {}
        return simulator.get_latency_stats()

    return app


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CAMTC Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0f1117; color: #e0e0e0; }
.header { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px 30px; border-bottom: 1px solid #2a2a4a; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 24px; color: #64ffda; }
.header .subtitle { color: #8892b0; font-size: 14px; margin-top: 4px; }
.status-badge { padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; }
.status-running { background: #1b3a2d; color: #64ffda; }
.status-stopped { background: #3a1b1b; color: #ff6b6b; }

.container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 20px; max-width: 1600px; margin: 0 auto; }
.card { background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; }
.card-wide { grid-column: span 2; }
.card-full { grid-column: span 4; }

.card h2 { font-size: 14px; color: #8892b0; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }

.metric-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #2a2a4a; }
.metric-row:last-child { border-bottom: none; }
.metric-label { color: #ccd6f6; font-size: 14px; }
.metric-value { font-weight: 700; font-size: 16px; font-family: 'Courier New', monospace; }
.metric-value.green { color: #64ffda; }
.metric-value.yellow { color: #ffd93d; }
.metric-value.red { color: #ff6b6b; }
.metric-value.blue { color: #64b5f6; }

.tier-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.tier-box { background: #0f1117; border-radius: 8px; padding: 16px; text-align: center; }
.tier-box h3 { font-size: 12px; color: #8892b0; margin-bottom: 8px; }
.tier-box .count { font-size: 28px; font-weight: 700; font-family: 'Courier New', monospace; }
.tier-1 .count { color: #ff6b6b; }
.tier-2 .count { color: #ffd93d; }
.tier-3 .count { color: #64ffda; }

.bar-chart { display: flex; align-items: flex-end; gap: 8px; height: 120px; padding-top: 10px; }
.bar { flex: 1; border-radius: 4px 4px 0 0; min-height: 4px; transition: height 0.3s ease; position: relative; }
.bar:hover { opacity: 0.8; }
.bar-label { position: absolute; bottom: -20px; left: 50%; transform: translateX(-50%); font-size: 10px; color: #8892b0; white-space: nowrap; }

.tx-table { width: 100%; border-collapse: collapse; }
.tx-table th { text-align: left; font-size: 11px; color: #8892b0; padding: 8px; border-bottom: 1px solid #2a2a4a; text-transform: uppercase; }
.tx-table td { padding: 6px 8px; font-size: 13px; border-bottom: 1px solid #1a1a2e; }
.tier-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.tier-1-badge { background: #3a1b1b; color: #ff6b6b; }
.tier-2-badge { background: #3a3a1b; color: #ffd93d; }
.tier-3-badge { background: #1b3a2d; color: #64ffda; }

.controls { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.btn { padding: 8px 16px; border-radius: 6px; border: 1px solid #2a2a4a; background: #1a1a2e; color: #e0e0e0; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.btn:hover { background: #2a2a4a; }
.btn-primary { background: #1b5e20; border-color: #64ffda; color: #64ffda; }
.btn-primary:hover { background: #2e7d32; }
.btn-danger { background: #3a1b1b; border-color: #ff6b6b; color: #ff6b6b; }

.latency-bars { display: flex; gap: 16px; align-items: center; }
.latency-bar-container { flex: 1; }
.latency-bar-bg { background: #0f1117; height: 8px; border-radius: 4px; overflow: hidden; }
.latency-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }

.consensus-flow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.phase-badge { padding: 4px 10px; border-radius: 4px; font-size: 12px; font-family: monospace; }
.phase-idle { background: #1a1a2e; color: #8892b0; }
.phase-active { background: #1b3a2d; color: #64ffda; }
.phase-committed { background: #1b5e20; color: #64ffda; }
.arrow { color: #8892b0; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.pulse { animation: pulse 2s infinite; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>CAMTC Simulator</h1>
    <div class="subtitle">Context-Adaptive Multi-Tier Hybrid Consensus</div>
  </div>
  <div style="display:flex;gap:12px;align-items:center;">
    <span id="statusBadge" class="status-badge status-stopped">Stopped</span>
    <span id="clock" style="color:#8892b0;font-family:monospace;font-size:13px;"></span>
  </div>
</div>

<div class="container">

  <!-- System Overview -->
  <div class="card card-wide">
    <h2>System Overview</h2>
    <div class="metric-row">
      <span class="metric-label">Validators</span>
      <span class="metric-value" id="nValidators">10</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Total Transactions</span>
      <span class="metric-value green" id="totalTx">0</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Committed Blocks</span>
      <span class="metric-value blue" id="totalBlocks">0</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Throughput (TPS)</span>
      <span class="metric-value green" id="throughput">0</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">Current Epoch</span>
      <span class="metric-value" id="epoch">0</span>
    </div>
    <div class="metric-row">
      <span class="metric-label">RL Thresholds</span>
      <span class="metric-value" id="thresholds">0.85 / 0.60</span>
    </div>
  </div>

  <!-- Tier Queue Depths -->
  <div class="card card-wide">
    <h2>Tier Queue Depths</h2>
    <div class="tier-grid">
      <div class="tier-box tier-1">
        <h3>TIER 1 — Emergency</h3>
        <div class="count" id="q1">0</div>
        <div style="font-size:11px;color:#8892b0;margin-top:4px;">Max batch: 5</div>
      </div>
      <div class="tier-box tier-2">
        <h3>TIER 2 — Urgent</h3>
        <div class="count" id="q2">0</div>
        <div style="font-size:11px;color:#8892b0;margin-top:4px;">Max batch: 20</div>
      </div>
      <div class="tier-box tier-3">
        <h3>TIER 3 — Routine</h3>
        <div class="count" id="q3">0</div>
        <div style="font-size:11px;color:#8892b0;margin-top:4px;">Max batch: 50</div>
      </div>
    </div>
  </div>

  <!-- Per-Tier Latency -->
  <div class="card card-wide">
    <h2>Mean Latency per Tier</h2>
    <div style="display:flex;flex-direction:column;gap:12px;">
      <div class="latency-bar-container">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <span style="color:#ff6b6b;font-size:13px;">Tier 1</span>
          <span style="color:#e0e0e0;font-family:monospace;font-size:13px;" id="lat1">— ms</span>
        </div>
        <div class="latency-bar-bg">
          <div class="latency-bar-fill" id="latBar1" style="width:0%;background:#ff6b6b;"></div>
        </div>
      </div>
      <div class="latency-bar-container">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <span style="color:#ffd93d;font-size:13px;">Tier 2</span>
          <span style="color:#e0e0e0;font-family:monospace;font-size:13px;" id="lat2">— ms</span>
        </div>
        <div class="latency-bar-bg">
          <div class="latency-bar-fill" id="latBar2" style="width:0%;background:#ffd93d;"></div>
        </div>
      </div>
      <div class="latency-bar-container">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <span style="color:#64ffda;font-size:13px;">Tier 3</span>
          <span style="color:#e0e0e0;font-family:monospace;font-size:13px;" id="lat3">— ms</span>
        </div>
        <div class="latency-bar-bg">
          <div class="latency-bar-fill" id="latBar3" style="width:0%;background:#64ffda;"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Consensus State -->
  <div class="card card-wide">
    <h2>Consensus State</h2>
    <div id="consensusInfo">
      <div class="metric-row">
        <span class="metric-label">Tier 1</span>
        <span id="cTier1" class="metric-value">IDLE</span>
      </div>
      <div class="metric-row">
        <span class="metric-label">Tier 2</span>
        <span id="cTier2" class="metric-value">IDLE</span>
      </div>
      <div class="metric-row">
        <span class="metric-label">Tier 3</span>
        <span id="cTier3" class="metric-value">IDLE</span>
      </div>
      <div class="metric-row">
        <span class="metric-label">Fallback Active</span>
        <span id="fallback" class="metric-value green">No</span>
      </div>
      <div class="metric-row">
        <span class="metric-label">Anchors Submitted</span>
        <span id="nAnchors" class="metric-value blue">0</span>
      </div>
    </div>
  </div>

  <!-- Controls -->
  <div class="card card-full">
    <h2>Simulation Controls</h2>
    <div class="controls">
      <button class="btn btn-primary" onclick="startBenchmark(1000)">Run 1K Transactions</button>
      <button class="btn btn-primary" onclick="startBenchmark(5000)">Run 5K Transactions</button>
      <button class="btn btn-primary" onclick="startBenchmark(10000)">Run 10K Transactions</button>
      <button class="btn" onclick="trainDNN()">Train PriorityNet DNN</button>
      <button class="btn" onclick="trainRL()">Train PPO Agent</button>
      <button class="btn btn-danger" onclick="injectByzantine(1)">Inject 1 Byzantine</button>
      <button class="btn btn-danger" onclick="triggerFallback()">Trigger Fallback</button>
      <button class="btn" onclick="resetSim()">Reset</button>
    </div>
  </div>

  <!-- Recent Transactions -->
  <div class="card card-full">
    <h2>Recent Transactions</h2>
    <div style="max-height:320px;overflow-y:auto;">
      <table class="tx-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Domain</th>
            <th>Priority</th>
            <th>Tier</th>
            <th>Latency</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody id="txTable">
          <tr><td colspan="7" style="text-align:center;color:#8892b0;padding:20px;">No transactions yet</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Reputation Scores -->
  <div class="card card-wide">
    <h2>Validator V-Scores</h2>
    <div id="reputationTable">
      <div style="text-align:center;color:#8892b0;padding:20px;">No data</div>
    </div>
  </div>

  <!-- Ethereum Anchors -->
  <div class="card card-wide">
    <h2>Ethereum Anchors</h2>
    <div id="anchorTable">
      <div style="text-align:center;color:#8892b0;padding:20px;">No anchors yet</div>
    </div>
  </div>

</div>

<script>
const API = window.location.port === '8080' ? '' : 'http://localhost:8000';
let refreshInterval = null;

function formatTime(ts) {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleTimeString();
}

async function fetchJSON(url) {
  try {
    const r = await fetch(API + url);
    return await r.json();
  } catch(e) { return null; }
}

async function postJSON(url, data) {
  try {
    await fetch(API + url, { method: 'POST', headers: {'Content-Type':'application/json'}, body: data ? JSON.stringify(data) : undefined });
  } catch(e) {}
}

async function refresh() {
  const status = await fetchJSON('/api/status');
  const metrics = await fetchJSON('/api/metrics');
  const nodes = await fetchJSON('/api/nodes');
  const consensus = await fetchJSON('/api/consensus');
  const rep = await fetchJSON('/api/reputation');
  const anchors = await fetchJSON('/api/anchors');
  const txs = await fetchJSON('/api/transactions/recent');
  const latencies = await fetchJSON('/api/latencies');

  // Status badge
  const badge = document.getElementById('statusBadge');
  if (status && status.running) {
    badge.textContent = 'Running';
    badge.className = 'status-badge status-running pulse';
  } else {
    badge.textContent = 'Stopped';
    badge.className = 'status-badge status-stopped';
  }

  // System overview
  if (metrics) {
    document.getElementById('totalTx').textContent = (metrics.total_tx || 0).toLocaleString();
    document.getElementById('totalBlocks').textContent = metrics.total_blocks || 0;
    document.getElementById('throughput').textContent = (metrics.tps || 0).toFixed(1);
    document.getElementById('epoch').textContent = metrics.epoch || 0;
    document.getElementById('thresholds').textContent = metrics.thresholds || '0.85 / 0.60';
  }

  // Queue depths
  if (nodes && nodes.length > 0) {
    const n = nodes[0];
    document.getElementById('q1').textContent = (n.mempool && n.mempool.tier1) || 0;
    document.getElementById('q2').textContent = (n.mempool && n.mempool.tier2) || 0;
    document.getElementById('q3').textContent = (n.mempool && n.mempool.tier3) || 0;
  }

  // Latency
  if (latencies) {
    const maxLat = 3500;
    ['tier1','tier2','tier3'].forEach((t, i) => {
      const ms = latencies[t + '_mean'] || 0;
      const el = document.getElementById('lat' + (i+1));
      const bar = document.getElementById('latBar' + (i+1));
      el.textContent = ms > 0 ? ms.toFixed(0) + ' ms' : '— ms';
      bar.style.width = Math.min(ms / maxLat * 100, 100) + '%';
    });
  }

  // Consensus
  if (consensus) {
    ['tier1','tier2','tier3'].forEach((t, i) => {
      const el = document.getElementById('cTier' + (i+1));
      const c = consensus[t];
      if (c) {
        const phase = c.phase || 'IDLE';
        el.textContent = phase + ' (q=' + c.quorum + ')';
        el.className = 'metric-value ' + (phase === 'COMMITTED' ? 'green' : phase === 'IDLE' ? '' : 'yellow');
      }
    });
    const fallback = consensus.tier1 && consensus.tier1.fallback_active;
    document.getElementById('fallback').textContent = fallback ? 'Yes' : 'No';
    document.getElementById('fallback').className = 'metric-value ' + (fallback ? 'red' : 'green');
  }

  // Anchors
  document.getElementById('nAnchors').textContent = anchors ? anchors.length : 0;

  // Transactions table
  const tbody = document.getElementById('txTable');
  if (txs && txs.length > 0) {
    tbody.innerHTML = txs.slice(-30).reverse().map(tx =>
      '<tr>' +
      '<td style="font-family:monospace;font-size:12px;">' + tx.tx_id + '</td>' +
      '<td>' + (tx.semantic_type || '—') + '</td>' +
      '<td>' + (tx.domain || '—') + '</td>' +
      '<td style="font-family:monospace;">' + (tx.priority_score || 0).toFixed(3) + '</td>' +
      '<td><span class="tier-badge tier-' + (tx.tier||3) + '-badge">T' + (tx.tier||3) + '</span></td>' +
      '<td style="font-family:monospace;">' + (tx.latency_ms ? tx.latency_ms.toFixed(0) + 'ms' : '—') + '</td>' +
      '<td style="font-size:12px;">' + formatTime(tx.timestamp) + '</td>' +
      '</tr>'
    ).join('');
  }

  // Reputation
  const repEl = document.getElementById('reputationTable');
  if (rep) {
    repEl.innerHTML = Object.entries(rep).map(([vid, r]) =>
      '<div class="metric-row">' +
      '<span class="metric-label">Node ' + vid + '</span>' +
      '<span class="metric-value ' + (r.vscore >= 0.3 ? 'green' : r.vscore >= 0.15 ? 'yellow' : 'red') + '">' +
      'VS=' + r.vscore.toFixed(3) + ' (R=' + r.rep.toFixed(2) + ' U=' + r.up.toFixed(2) + ' L=' + r.lat.toFixed(2) + ')' +
      '</span></div>'
    ).join('');
  }

  // Anchors table
  const anchorEl = document.getElementById('anchorTable');
  if (anchors && anchors.length > 0) {
    anchorEl.innerHTML = anchors.slice(-10).reverse().map(a =>
      '<div class="metric-row">' +
      '<span class="metric-label">#' + a.index + ' h=' + a.block_height + ' e=' + a.epoch + '</span>' +
      '<span class="metric-value blue" style="font-size:12px;">' + a.merkle_root + '...</span>' +
      '</div>'
    ).join('');
  }

  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}

function startBenchmark(n) { postJSON('/api/benchmark/start?n_transactions=' + n + '&tx_per_second=50'); }
function trainDNN() { postJSON('/api/train/dnn?epochs=200'); }
function trainRL() { postJSON('/api/train/rl?steps=5000'); }
function injectByzantine(n) { postJSON('/api/simulate/byzantine?n_faulty=' + n); }
function triggerFallback() { postJSON('/api/simulate/fallback?n_offline=2'); }
function resetSim() { postJSON('/api/reset'); }

refresh();
refreshInterval = setInterval(refresh, 1000);
</script>
</body>
</html>
"""
