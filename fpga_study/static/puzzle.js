/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   FPGAお勉強アプリ — 回路パズルエディタ (puzzle.js)
   SVGベース・外部ライブラリ不使用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

'use strict';

/* ── 定数 ─────────────────────────────────── */
const GATE_W = 80, GATE_H = 56;
const PORT_R = 7;
const CANVAS_W = 640, CANVAS_H = 480;
const SVG_NS = 'http://www.w3.org/2000/svg';

const GATE_COLORS = {
  AND: '#4f46e5', OR: '#7c3aed', NOT: '#be185d', XOR: '#b45309',
  NAND: '#0891b2', NOR: '#047857', INPUT: '#16a34a', OUTPUT: '#dc2626',
};

/* ── ゲート形状パス (SVG path d 属性) ─────── */
function gateShape(type) {
  switch (type.toUpperCase()) {
    case 'AND':
      return 'M 10,4 L 50,4 Q 74,4 74,28 Q 74,52 50,52 L 10,52 Z';
    case 'OR':
      return 'M 10,4 Q 30,4 60,28 Q 30,52 10,52 Q 24,28 10,4 Z';
    case 'XOR':
      return 'M 14,4 Q 34,4 64,28 Q 34,52 14,52 Q 28,28 14,4 Z M 7,4 Q 21,28 7,52';
    case 'NOT':
      return 'M 10,14 L 10,42 L 60,28 Z';
    case 'NAND':
      return 'M 10,4 L 50,4 Q 74,4 74,28 Q 74,52 50,52 L 10,52 Z';
    case 'NOR':
      return 'M 10,4 Q 30,4 60,28 Q 30,52 10,52 Q 24,28 10,4 Z';
    default:
      return 'M 4,4 L 76,4 L 76,52 L 4,52 Z';
  }
}

/* ── SVG ヘルパー ─────────────────────────── */
function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function svgText(x, y, text, attrs = {}) {
  const t = svgEl('text', { x, y, 'font-size': 11, 'text-anchor': 'middle', 'dominant-baseline': 'middle', ...attrs });
  t.textContent = text;
  return t;
}

/* ── 入力ポート座標 ─────────────────────────
   NOT: 入力1、その他: 入力2
*/
function inputPorts(type) {
  const upper = type.toUpperCase();
  if (upper === 'NOT') return [{ x: 0, y: GATE_H / 2 }];
  return [
    { x: 0, y: GATE_H * 0.3 },
    { x: 0, y: GATE_H * 0.7 },
  ];
}
function outputPort(type) {
  const upper = type.toUpperCase();
  if (upper === 'NOT') return { x: GATE_W, y: GATE_H / 2 };
  if (upper === 'NAND' || upper === 'NOR') return { x: GATE_W, y: GATE_H / 2 };
  return { x: GATE_W, y: GATE_H / 2 };
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   PuzzleEditor クラス
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
class PuzzleEditor {
  constructor(mountEl, puzzleDef, chapterId, lessonId) {
    this.mountEl = mountEl;
    this.def = puzzleDef;
    this.chapterId = chapterId;
    this.lessonId = lessonId;

    this.nodes = [];
    this.wires = [];
    this.dragging = null;
    this.wiringFrom = null;
    this.passed = false;

    this._nextId = 1;
    this._gateCountRemain = {};
    for (const g of puzzleDef.available_gates || []) {
      this._gateCountRemain[g.type] = g.count;
    }

    this._build();
    this._placeFixed();
    this._render();
  }

  /* ── DOM 構築 ─────────────────────────── */
  _build() {
    const def = this.def;
    this.mountEl.innerHTML = '';
    this.mountEl.className = 'puzzle-section';

    // ヘッダー
    const toolbarItems = (def.available_gates || []).map(g => {
      const btn = document.createElement('button');
      btn.className = 'gate-btn';
      btn.dataset.gateType = g.type;
      btn.innerHTML = `${g.type}<span class="gate-btn-count" id="gcnt-${g.type}">×${g.count}</span>`;
      btn.addEventListener('click', () => this._addGate(g.type));
      return btn;
    });

    const resetBtn = document.createElement('button');
    resetBtn.className = 'btn btn-secondary';
    resetBtn.style.fontSize = '.8rem';
    resetBtn.textContent = '🔄 リセット';
    resetBtn.addEventListener('click', () => this._reset());

    const header = document.createElement('div');
    header.className = 'puzzle-header';
    const titleDiv = document.createElement('div');
    titleDiv.innerHTML = `<h2>🔧 ${escHtml(def.title)}</h2>` +
      (def.description ? `<p style="font-size:.85rem;color:var(--gray-500);margin-top:.25rem">${escHtml(def.description)}</p>` : '');
    const toolbar = document.createElement('div');
    toolbar.className = 'puzzle-toolbar';
    toolbarItems.forEach(b => toolbar.append(b));
    toolbar.append(resetBtn);
    header.append(titleDiv, toolbar);

    // キャンバス
    this.svg = svgEl('svg', {
      width: CANVAS_W, height: CANVAS_H,
      viewBox: `0 0 ${CANVAS_W} ${CANVAS_H}`,
      id: 'puzzle-canvas',
    });
    this.svg.style.cursor = 'default';
    this.svg.style.userSelect = 'none';

    // グリッド背景
    const defs = svgEl('defs');
    const pattern = svgEl('pattern', { id: 'grid', width: 20, height: 20, patternUnits: 'userSpaceOnUse' });
    pattern.append(svgEl('path', { d: 'M 20 0 L 0 0 0 20', fill: 'none', stroke: '#e5e7eb', 'stroke-width': '0.5' }));
    defs.append(pattern);
    this.svg.append(defs);
    this.svg.append(svgEl('rect', { width: CANVAS_W, height: CANVAS_H, fill: 'url(#grid)' }));

    this.wiresLayer = svgEl('g', { id: 'wires-layer' });
    this.nodesLayer = svgEl('g', { id: 'nodes-layer' });
    this.tempWireEl = svgEl('path', { stroke: '#4f46e5', 'stroke-width': 2, fill: 'none', 'stroke-dasharray': '6,4', display: 'none' });
    this.svg.append(this.wiresLayer, this.nodesLayer, this.tempWireEl);

    // SVG イベント
    this.svg.addEventListener('mousemove', e => this._onMouseMove(e));
    this.svg.addEventListener('mouseup', e => this._onMouseUp(e));
    this.svg.addEventListener('mouseleave', () => { this.dragging = null; });
    this.svg.addEventListener('touchmove', e => { e.preventDefault(); this._onMouseMove(e.touches[0]); }, { passive: false });
    this.svg.addEventListener('touchend', e => this._onMouseUp(e.changedTouches[0]));

    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'puzzle-canvas-wrap';
    canvasWrap.append(this.svg);

    // サイドバー（真理値表）
    this.sidebar = document.createElement('div');
    this.sidebar.className = 'puzzle-sidebar';
    this._buildTruthTable();

    const body = document.createElement('div');
    body.className = 'puzzle-body';
    body.append(canvasWrap, this.sidebar);

    // フッター
    this.messageEl = document.createElement('div');
    this.messageEl.className = 'puzzle-message';
    this.messageEl.textContent = 'ゲートを配置して配線し、「回路を確認」ボタンを押してください。';

    const checkBtn = document.createElement('button');
    checkBtn.className = 'btn btn-primary';
    checkBtn.textContent = '⚡ 回路を確認';
    checkBtn.addEventListener('click', () => this._checkCircuit());

    const footer = document.createElement('div');
    footer.className = 'puzzle-footer';
    footer.append(this.messageEl, checkBtn);

    this.mountEl.append(header, body, footer);
  }

  _buildTruthTable() {
    const def = this.def;
    const inputNames = (def.inputs || []).map(i => i.name);
    const outputNames = (def.outputs || []).map(o => o.name);

    const h3 = document.createElement('h3');
    h3.textContent = '目標の真理値表';
    const table = document.createElement('table');
    table.className = 'truth-table';
    table.id = 'truth-table';

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    [...inputNames, ...outputNames].forEach(n => {
      const th = document.createElement('th');
      th.textContent = n;
      headerRow.append(th);
    });
    thead.append(headerRow);

    const tbody = document.createElement('tbody');
    (def.target_truth_table || []).forEach((row, rowIdx) => {
      const tr = document.createElement('tr');
      tr.id = `tt-row-${rowIdx}`;
      [...inputNames, ...outputNames].forEach(n => {
        const td = document.createElement('td');
        const val = row.inputs[n] ?? row.outputs[n];
        td.textContent = val !== undefined ? val : '?';
        tr.append(td);
      });
      tbody.append(tr);
    });

    table.append(thead, tbody);
    this.sidebar.append(h3, table);
  }

  /* ── 固定ノード（入出力）を配置 ────────── */
  _placeFixed() {
    const def = this.def;
    const inputs = def.inputs || [];
    const outputs = def.outputs || [];
    const margin = 60;
    const inputX = 60;
    const outputX = CANVAS_W - 60;

    inputs.forEach((inp, i) => {
      const y = margin + i * (GATE_H + 40) + GATE_H / 2;
      this.nodes.push({
        id: `input_${inp.name}`, type: 'INPUT', fixed: true,
        x: inputX, y, name: inp.name,
      });
    });
    outputs.forEach((out, i) => {
      const y = margin + i * (GATE_H + 40) + GATE_H / 2;
      this.nodes.push({
        id: `output_${out.name}`, type: 'OUTPUT', fixed: true,
        x: outputX, y, name: out.name,
      });
    });
  }

  /* ── ゲート追加 ───────────────────────── */
  _addGate(type) {
    if ((this._gateCountRemain[type] || 0) <= 0) {
      showToast(`${type}ゲートはこれ以上追加できません`, 'warn');
      return;
    }
    this._gateCountRemain[type]--;
    const id = `gate_${this._nextId++}`;
    this.nodes.push({
      id, type, fixed: false,
      x: 200 + Math.random() * 200,
      y: 80 + Math.random() * 300,
    });
    this._render();
    this._updateCountBadges();
  }

  _updateCountBadges() {
    for (const [type, cnt] of Object.entries(this._gateCountRemain)) {
      const el = document.getElementById(`gcnt-${type}`);
      if (el) el.textContent = `×${cnt}`;
    }
  }

  /* ── リセット ─────────────────────────── */
  _reset() {
    this.nodes = this.nodes.filter(n => n.fixed);
    this.wires = [];
    this.wiringFrom = null;
    this.passed = false;
    for (const g of this.def.available_gates || []) {
      this._gateCountRemain[g.type] = g.count;
    }
    this._updateCountBadges();
    this._render();
    this.messageEl.className = 'puzzle-message';
    this.messageEl.textContent = 'ゲートを配置して配線し、「回路を確認」ボタンを押してください。';
    // 真理値表のハイライトをリセット
    const rows = this.mountEl.querySelectorAll('#truth-table tbody tr');
    rows.forEach(r => { r.classList.remove('check-pass', 'check-fail'); });
  }

  /* ── SVG 描画 ─────────────────────────── */
  _render() {
    this.wiresLayer.innerHTML = '';
    this.nodesLayer.innerHTML = '';

    for (const w of this.wires) this._renderWire(w);
    for (const n of this.nodes) this._renderNode(n);
  }

  _renderNode(node) {
    const g = svgEl('g', { transform: `translate(${node.x - GATE_W/2}, ${node.y - GATE_H/2})` });
    g.style.cursor = node.fixed ? 'default' : 'grab';

    if (node.type === 'INPUT') {
      g.append(svgEl('rect', { x: 0, y: GATE_H/2-14, width: 56, height: 28, rx: 6, fill: '#dcfce7', stroke: '#16a34a', 'stroke-width': 2 }));
      g.append(svgText(28, GATE_H/2, node.name, { fill: '#15803d', 'font-weight': 'bold', 'font-size': 13 }));
      // 出力ポート
      const px = 56, py = GATE_H/2;
      const portEl = svgEl('circle', { cx: px, cy: py, r: PORT_R, fill: 'white', stroke: '#16a34a', 'stroke-width': 2, cursor: 'crosshair' });
      portEl.addEventListener('mousedown', e => { e.stopPropagation(); this._startWire(node.id, 'output', 0, node.x - GATE_W/2 + px, node.y - GATE_H/2 + py); });
      portEl.addEventListener('touchstart', e => { e.preventDefault(); const t = e.touches[0]; this._startWire(node.id, 'output', 0, node.x - GATE_W/2 + px, node.y - GATE_H/2 + py); }, { passive: false });
      g.append(portEl);
    } else if (node.type === 'OUTPUT') {
      g.append(svgEl('rect', { x: 4, y: GATE_H/2-14, width: 56, height: 28, rx: 6, fill: '#fee2e2', stroke: '#dc2626', 'stroke-width': 2 }));
      g.append(svgText(32, GATE_H/2, node.name, { fill: '#b91c1c', 'font-weight': 'bold', 'font-size': 13 }));
      // 入力ポート
      const px = 0, py = GATE_H/2;
      const portEl = svgEl('circle', { cx: px, cy: py, r: PORT_R, fill: 'white', stroke: '#dc2626', 'stroke-width': 2, cursor: 'crosshair' });
      portEl.addEventListener('mousedown', e => { e.stopPropagation(); this._endWire(node.id, 'input', 0, node.x - GATE_W/2 + px, node.y - GATE_H/2 + py); });
      portEl.addEventListener('touchstart', e => { e.preventDefault(); this._endWire(node.id, 'input', 0, node.x - GATE_W/2 + px, node.y - GATE_H/2 + py); }, { passive: false });
      g.append(portEl);
    } else {
      // 通常ゲート
      const color = GATE_COLORS[node.type] || '#6b7280';
      const bg = node.type === 'NOT' || node.type === 'NAND' || node.type === 'NOR' ? '#fee2e2' : '#eef2ff';
      const shape = svgEl('path', { d: gateShape(node.type), fill: bg, stroke: color, 'stroke-width': 2 });
      g.append(shape);
      g.append(svgText(GATE_W/2, GATE_H/2, node.type, { fill: color, 'font-weight': 'bold', 'font-size': 10 }));

      // 小さい×ボタン
      const delBtn = svgEl('circle', { cx: GATE_W - 4, cy: 4, r: 7, fill: '#dc2626', cursor: 'pointer', opacity: 0.8 });
      const delX = svgText(GATE_W - 4, 4, '×', { fill: 'white', 'font-size': 10, 'font-weight': 'bold', cursor: 'pointer' });
      delBtn.addEventListener('click', e => { e.stopPropagation(); this._removeGate(node.id); });
      delX.addEventListener('click', e => { e.stopPropagation(); this._removeGate(node.id); });
      g.append(delBtn, delX);

      // 入力ポート
      const inPorts = inputPorts(node.type);
      inPorts.forEach((p, i) => {
        const portEl = svgEl('circle', { cx: p.x, cy: p.y, r: PORT_R, fill: 'white', stroke: color, 'stroke-width': 2, cursor: 'crosshair' });
        portEl.addEventListener('mousedown', e => { e.stopPropagation(); this._endWire(node.id, 'input', i, node.x - GATE_W/2 + p.x, node.y - GATE_H/2 + p.y); });
        portEl.addEventListener('touchstart', e => { e.preventDefault(); this._endWire(node.id, 'input', i, node.x - GATE_W/2 + p.x, node.y - GATE_H/2 + p.y); }, { passive: false });
        g.append(portEl);
      });

      // 出力ポート
      const op = outputPort(node.type);
      const isNot = node.type === 'NOT' || node.type === 'NAND' || node.type === 'NOR';
      if (isNot) {
        g.append(svgEl('circle', { cx: op.x - 8, cy: op.y, r: 5, fill: 'white', stroke: color, 'stroke-width': 2 }));
      }
      const outPortEl = svgEl('circle', { cx: op.x, cy: op.y, r: PORT_R, fill: 'white', stroke: color, 'stroke-width': 2, cursor: 'crosshair' });
      outPortEl.addEventListener('mousedown', e => { e.stopPropagation(); this._startWire(node.id, 'output', 0, node.x - GATE_W/2 + op.x, node.y - GATE_H/2 + op.y); });
      outPortEl.addEventListener('touchstart', e => { e.preventDefault(); this._startWire(node.id, 'output', 0, node.x - GATE_W/2 + op.x, node.y - GATE_H/2 + op.y); }, { passive: false });
      g.append(outPortEl);

      // ドラッグ
      g.addEventListener('mousedown', e => this._startDrag(e, node));
      g.addEventListener('touchstart', e => { e.preventDefault(); this._startDrag(e.touches[0], node); }, { passive: false });
    }

    this.nodesLayer.append(g);
  }

  _renderWire(wire) {
    const fromNode = this.nodes.find(n => n.id === wire.from_id);
    const toNode = this.nodes.find(n => n.id === wire.to_id);
    if (!fromNode || !toNode) return;

    const [x1, y1] = this._portCoord(fromNode, 'output', wire.from_port_idx || 0);
    const [x2, y2] = this._portCoord(toNode, 'input', wire.to_port_idx || 0);
    const cx = (x1 + x2) / 2;

    const path = svgEl('path', {
      d: `M ${x1},${y1} C ${cx},${y1} ${cx},${y2} ${x2},${y2}`,
      fill: 'none', stroke: '#4f46e5', 'stroke-width': 2.5, 'stroke-linecap': 'round',
    });
    // ワイヤーを削除するクリックイベント
    path.style.cursor = 'pointer';
    const wireId = wire.id;
    path.addEventListener('click', () => {
      this.wires = this.wires.filter(w => w.id !== wireId);
      this._render();
    });
    this.wiresLayer.append(path);
  }

  _portCoord(node, dir, idx) {
    if (node.type === 'INPUT') {
      return [node.x - GATE_W/2 + 56, node.y];
    }
    if (node.type === 'OUTPUT') {
      return [node.x - GATE_W/2, node.y];
    }
    if (dir === 'output') {
      const op = outputPort(node.type);
      return [node.x - GATE_W/2 + op.x, node.y - GATE_H/2 + op.y];
    }
    const ports = inputPorts(node.type);
    const p = ports[idx] || ports[0];
    return [node.x - GATE_W/2 + p.x, node.y - GATE_H/2 + p.y];
  }

  /* ── ドラッグ ─────────────────────────── */
  _startDrag(e, node) {
    if (node.fixed || this.wiringFrom) return;
    const rect = this.svg.getBoundingClientRect();
    const scaleX = CANVAS_W / rect.width;
    const scaleY = CANVAS_H / rect.height;
    this.dragging = {
      node,
      offX: (e.clientX - rect.left) * scaleX - node.x,
      offY: (e.clientY - rect.top) * scaleY - node.y,
    };
    this.svg.style.cursor = 'grabbing';
  }

  _onMouseMove(e) {
    const rect = this.svg.getBoundingClientRect();
    const scaleX = CANVAS_W / rect.width;
    const scaleY = CANVAS_H / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;

    if (this.dragging) {
      this.dragging.node.x = Math.max(GATE_W/2, Math.min(CANVAS_W - GATE_W/2, mx - this.dragging.offX));
      this.dragging.node.y = Math.max(GATE_H/2, Math.min(CANVAS_H - GATE_H/2, my - this.dragging.offY));
      this._render();
    }

    if (this.wiringFrom) {
      const [sx, sy] = this.wiringFrom.coord;
      const cx = (sx + mx) / 2;
      this.tempWireEl.setAttribute('d', `M ${sx},${sy} C ${cx},${sy} ${cx},${my} ${mx},${my}`);
      this.tempWireEl.setAttribute('display', '');
    }
  }

  _onMouseUp(e) {
    if (this.dragging) {
      this.dragging = null;
      this.svg.style.cursor = 'default';
    }
  }

  /* ── 配線 ─────────────────────────────── */
  _startWire(nodeId, dir, portIdx, x, y) {
    this.wiringFrom = { nodeId, dir, portIdx, coord: [x, y] };
  }

  _endWire(nodeId, dir, portIdx, x, y) {
    if (!this.wiringFrom) return;
    const from = this.wiringFrom;
    this.wiringFrom = null;
    this.tempWireEl.setAttribute('display', 'none');

    // 同じノードへの接続は無効
    if (from.nodeId === nodeId) return;
    // 出力→入力の向きチェック
    if (from.dir !== 'output' || dir !== 'input') {
      showToast('出力ポート(右)→入力ポート(左)の順に接続してください', 'warn');
      return;
    }

    // 重複チェック
    const dup = this.wires.find(w =>
      w.to_id === nodeId && w.to_port_idx === portIdx
    );
    if (dup) {
      this.wires = this.wires.filter(w => w !== dup);
    }

    this.wires.push({
      id: `w${Date.now()}`,
      from_id: from.nodeId,
      from_port_idx: from.portIdx,
      to_id: nodeId,
      to_port_idx: portIdx,
    });
    this._render();
  }

  /* ── ゲート削除 ───────────────────────── */
  _removeGate(id) {
    const node = this.nodes.find(n => n.id === id);
    if (node && !node.fixed) {
      this._gateCountRemain[node.type] = (this._gateCountRemain[node.type] || 0) + 1;
      this._updateCountBadges();
    }
    this.nodes = this.nodes.filter(n => n.id !== id);
    this.wires = this.wires.filter(w => w.from_id !== id && w.to_id !== id);
    this._render();
  }

  /* ── 回路チェック ─────────────────────── */
  async _checkCircuit() {
    try {
      const connections = this.wires.map(w => ({
        from_id: w.from_id,
        from_port: `output_${w.from_port_idx}`,
        to_id: w.to_id,
        to_port: `input_${w.to_port_idx}`,
      }));
      const gatePlacements = this.nodes
        .filter(n => n.type !== 'INPUT' && n.type !== 'OUTPUT')
        .map(n => ({ id: n.id, type: n.type, x: n.x, y: n.y }));

      const result = await fetch(
        `/api/chapters/${this.chapterId}/lessons/${this.lessonId}/puzzle/check`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ connections, gate_placements: gatePlacements }),
        }
      ).then(r => r.json());

      this.messageEl.textContent = result.message;
      this.messageEl.className = `puzzle-message ${result.passed ? 'pass' : 'fail'}`;

      // 真理値表の行をハイライト
      const rows = this.mountEl.querySelectorAll('#truth-table tbody tr');
      rows.forEach((r, i) => { r.classList.remove('check-pass', 'check-fail'); });

      if (result.passed) {
        rows.forEach(r => r.classList.add('check-pass'));
        showToast('🎉 パズル合格！', 'success');
        this.passed = true;
      } else {
        const failedInputSets = result.failed_cases.map(fc => JSON.stringify(fc.inputs));
        const ttRows = this.def.target_truth_table || [];
        ttRows.forEach((row, i) => {
          const rowEl = document.getElementById(`tt-row-${i}`);
          if (!rowEl) return;
          if (failedInputSets.includes(JSON.stringify(row.inputs))) {
            rowEl.classList.add('check-fail');
          } else {
            rowEl.classList.add('check-pass');
          }
        });
      }
    } catch (e) {
      showToast('確認に失敗しました: ' + e.message, 'error');
    }
  }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showToast(msg, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.append(toast);
  setTimeout(() => toast.remove(), duration);
}
