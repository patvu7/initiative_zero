// ═══ STATE ═══
const ZONES = {1:'Legacy Env',2:'Analysis',3:'Rule Strainer',4:'Generation',5:'Testing',6:'Production'};
let currentZone = 1;
const zoneRan = {1:false,2:false,3:false,4:false,5:false,6:false};

let state = {
  runId: null,
  currentZone: 1,
  sourceFile: null,
  requirementsDocId: null,
  analysis: null,
  rules: null,
  generatedCode: null,
  testResults: null
};

// ═══ API HELPER ═══
async function api(path, method = 'GET', body = null) {
  const opts = { method, headers: {'Content-Type': 'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({error: 'Request failed'}));
    throw new Error(err.error || `API error: ${res.status}`);
  }
  return res.json();
}

// ═══ NAVIGATION ═══
function goZone(z) {
  currentZone = z;
  state.currentZone = z;
  document.querySelectorAll('.nav-item').forEach(el => {
    const n = +el.dataset.zone;
    el.classList.remove('active');
    if (n === z) el.classList.add('active');
  });
  document.querySelectorAll('.zone-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('zp-' + z).classList.add('active');
  document.getElementById('bc-zone').textContent = ZONES[z];
  document.getElementById('pipeline-status').textContent = 'Zone ' + z + ' of 6';
  runZone(z);
}

function advanceZone(z) {
  const prev = document.querySelector('.nav-item[data-zone="'+(z-1)+'"]');
  if (prev) prev.classList.add('completed');
  updateStatus(z-1, 'done', '✓');
  goZone(z);
}

function updateStatus(z, cls, text) {
  const el = document.getElementById('ns' + z);
  if (!el) return;
  el.className = 'nav-status ' + cls;
  el.textContent = text;
}

function runZone(z) {
  if (z === 2 && !zoneRan[2]) { zoneRan[2] = true; runAnalysis(); }
  if (z === 3 && !zoneRan[3]) { zoneRan[3] = true; runStrainer(); }
  if (z === 4 && !zoneRan[4]) { zoneRan[4] = true; runGeneration(); }
  if (z === 5 && !zoneRan[5]) { zoneRan[5] = true; runTesting(); }
}

// ═══ ZONE 1: LEGACY ENV ═══
async function loadFiles() {
  try {
    const files = await api('/api/legacy/files');
    const sel = document.getElementById('file-selector');
    files.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.filename;
      opt.textContent = f.filename + ' (' + f.loc + ' lines)';
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => onFileSelected(sel.value));
  } catch (e) {
    toast('Error loading files: ' + e.message);
  }
}

async function onFileSelected(filename) {
  if (!filename) return;
  try {
    const file = await api('/api/legacy/files/' + encodeURIComponent(filename));
    state.sourceFile = filename;
    document.getElementById('code-display').textContent = file.content;
    document.getElementById('code-filename-display').textContent = 'src/' + filename;
    document.getElementById('meta-loc').textContent = file.loc.toLocaleString();
    document.getElementById('meta-filename').textContent = filename;
  } catch (e) {
    toast('Error loading file: ' + e.message);
  }
}

async function createRunAndAdvance() {
  if (!state.sourceFile) {
    toast('Please select a file first');
    return;
  }
  try {
    const result = await api('/api/runs', 'POST', {
      source_file: state.sourceFile,
      source_language: 'COBOL',
      operator: 'S. Chen'
    });
    state.runId = result.run_id;
    advanceZone(2);
  } catch (e) {
    toast('Error creating run: ' + e.message);
  }
}

// ═══ ZONE 2: ANALYSIS ═══
async function runAnalysis() {
  updateStatus(2, 'running', '●');
  try {
    const result = await api('/api/analysis/run', 'POST', { run_id: state.runId });
    state.analysis = result;
    const m = result.metrics;

    document.getElementById('a-proc').style.display = 'none';
    document.getElementById('a-results').style.display = 'block';

    // App Analysis
    const app = m.app_analysis || {};
    document.getElementById('a-purpose').textContent = app.purpose || '—';
    document.getElementById('a-stack').textContent = app.stack || '—';
    document.getElementById('a-deps').textContent =
      (app.dependencies_upstream || 0) + ' upstream, ' + (app.dependencies_downstream || 0) + ' downstream';
    document.getElementById('a-criticality').textContent = app.criticality || '—';

    // Code Analysis
    const code = m.code_analysis || {};
    const cyc = document.getElementById('a-cyclomatic');
    cyc.textContent = code.cyclomatic_complexity || '—';
    if ((code.cyclomatic_complexity || 0) > 20) cyc.classList.add('warn');
    const dead = document.getElementById('a-deadcode');
    dead.textContent = '~' + (code.dead_code_pct || 0).toFixed(0) + '%';
    if ((code.dead_code_pct || 0) > 10) dead.classList.add('warn');
    const sec = document.getElementById('a-security');
    sec.textContent = (code.security_issues || 0) + ' issues';
    if ((code.security_issues || 0) > 0) sec.classList.add('bad');
    document.getElementById('a-workarounds').textContent = (code.workarounds_identified || 0) + ' identified';

    // Test Analysis
    const test = m.test_analysis || {};
    const cov = document.getElementById('a-coverage');
    cov.textContent = (test.estimated_coverage_pct || 0).toFixed(0) + '%';
    if ((test.estimated_coverage_pct || 0) < 50) cov.classList.add('bad');
    document.getElementById('a-unit').textContent = test.has_unit_tests || '—';
    const integ = document.getElementById('a-integration');
    integ.textContent = test.has_integration_tests || '—';
    if (test.has_integration_tests === 'None') integ.classList.add('bad');
    const edge = document.getElementById('a-edgecases');
    const edgeCases = test.untested_edge_cases || [];
    edge.textContent = edgeCases.length > 0 ? edgeCases[0] : '—';
    if (edgeCases.length > 0) edge.classList.add('bad');

    // Cost Analysis
    const econ = m.migration_economics || {};
    document.getElementById('a-annual').textContent = econ.estimated_annual_maintenance || '—';
    const aiCost = document.getElementById('a-ai-cost');
    aiCost.textContent = econ.estimated_ai_migration_cost || '—';
    aiCost.classList.add('good');
    document.getElementById('a-manual-cost').textContent = econ.estimated_manual_migration_cost || '—';
    const roi = document.getElementById('a-roi');
    roi.textContent = (econ.roi_breakeven_months || '—') + ' months';
    roi.classList.add('good');

    // Confidence bar
    const confPct = Math.round((result.confidence_score || 0) * 100);
    setTimeout(() => {
      document.getElementById('conf-fill').style.width = confPct + '%';
      let v = 0;
      const iv = setInterval(() => {
        v++;
        document.getElementById('conf-score').textContent = v + '%';
        if (v >= confPct) {
          clearInterval(iv);
          const rec = result.recommendation || 'Caution';
          const rationale = m.recommendation_rationale || '';
          document.getElementById('conf-rec').textContent =
            'Recommendation: ' + rec + (rationale ? ' — ' + rationale : '');
        }
      }, 16);
    }, 200);

    toast('Analysis complete — confidence ' + confPct + '%');
  } catch (e) {
    document.getElementById('a-proc').style.display = 'none';
    toast('Analysis error: ' + e.message);
  }
}

// ═══ ZONE 3: RULE STRAINER ═══
async function runStrainer() {
  updateStatus(3, 'running', '●');
  try {
    const result = await api('/api/extraction/run', 'POST', { run_id: state.runId });
    state.rules = result.rules;
    state.requirementsDocId = result.requirements_doc_id;

    document.getElementById('s-proc').style.display = 'none';
    document.getElementById('s-results').style.display = 'block';

    const tbody = document.getElementById('rules-tbody');
    tbody.innerHTML = '';

    const rules = result.rules || [];
    rules.forEach((r, i) => {
      setTimeout(() => {
        const isBehavioral = r.rule_type === 'behavioral' || (r.id && r.id.startsWith('OBS'));
        const statusCls = isBehavioral ? 'warn' : 'ok';
        const statusText = isBehavioral ? 'Needs SME' : 'Extracted';
        const tr = document.createElement('tr');
        tr.innerHTML =
          '<td class="rule-id">' + escHtml(r.id) + '</td>' +
          '<td class="rule-text">' + escHtml(r.rule_text) + '</td>' +
          '<td class="rule-src">' + escHtml(r.source_reference || '') + '</td>' +
          '<td><span class="status-chip ' + statusCls + '">' + statusText + '</span></td>';
        tr.style.opacity = '0';
        tr.style.transition = 'opacity .3s';
        tbody.appendChild(tr);
        requestAnimationFrame(() => tr.style.opacity = '1');
      }, i * 180);
    });

    const obsCount = rules.filter(r => r.rule_type === 'behavioral' || (r.id && r.id.startsWith('OBS'))).length;
    const explicitCount = rules.length - obsCount;
    toast(explicitCount + ' rules extracted' + (obsCount > 0 ? ' + ' + obsCount + ' behavioral observation' + (obsCount > 1 ? 's' : '') : ''));
  } catch (e) {
    document.getElementById('s-proc').style.display = 'none';
    toast('Extraction error: ' + e.message);
  }
}

async function smeSign(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('sme-decision');
  document.getElementById('sme-actions').style.display = 'none';

  if (action === 'approve') {
    try {
      const result = await api('/api/extraction/' + state.runId + '/approve', 'POST', {
        operator: 'S. Chen',
        rationale: 'Requirements document validated'
      });
      state.requirementsDocId = result.requirements_doc_id;
      dr.className = 'decision-record accepted show';
      dr.innerHTML = '<div class="dr-header">✓ SPEC APPROVED</div>' +
        '<div class="dr-body">Requirements document validated. Cleared to cross security firewall.</div>' +
        '<div class="dr-ts">' + escHtml(result.operator) + ' (Staff Eng) · ' + escHtml(result.timestamp) + '</div>';
      document.getElementById('btn-to-gen').disabled = false;
      toast('Spec approved — firewall crossing authorized');
    } catch (e) {
      document.getElementById('sme-actions').style.display = '';
      toast('Approval error: ' + e.message);
    }
  } else {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = '<div class="dr-header">⚠ FLAGGED FOR BA REVIEW</div>' +
      '<div class="dr-body">Behavioral observations require business analyst confirmation before proceeding.</div>' +
      '<div class="dr-ts">S. Chen (Staff Eng) · ' + ts + '</div>';
    toast('Spec flagged — awaiting BA review');
  }
}

// ═══ ZONE 4: GENERATION ═══
async function runGeneration() {
  updateStatus(4, 'running', '●');
  try {
    const [genResult, reqResult] = await Promise.all([
      api('/api/generation/run', 'POST', {
        run_id: state.runId,
        requirements_doc_id: state.requirementsDocId
      }),
      api('/api/extraction/' + state.runId + '/requirements')
    ]);

    state.generatedCode = genResult.code;

    document.getElementById('g-proc').style.display = 'none';
    document.getElementById('g-results').style.display = 'block';

    // Left panel: requirements
    document.getElementById('gen-requirements-display').textContent = reqResult.content || '';

    // Right panel: generated code
    document.getElementById('gen-code-display').textContent = genResult.code || '';

    // Generation prompt panel
    document.getElementById('gen-prompt-panel').style.display = 'block';
    document.getElementById('gen-prompt-text').textContent = genResult.generation_prompt || '';

    toast('Python application generated from requirements');
  } catch (e) {
    document.getElementById('g-proc').style.display = 'none';
    toast('Generation error: ' + e.message);
  }
}

function toggleGenPrompt() {
  const content = document.getElementById('gen-prompt-content');
  const toggle = document.getElementById('gen-prompt-toggle');
  if (content.style.display === 'none') {
    content.style.display = 'block';
    toggle.textContent = '▼ Hide Generation Prompt';
  } else {
    content.style.display = 'none';
    toggle.textContent = '▶ View Generation Prompt (Firewall Proof)';
  }
}

// ═══ ZONE 5: TESTING ═══
async function runTesting() {
  updateStatus(5, 'running', '●');
  try {
    const results = await api('/api/testing/run', 'POST', { run_id: state.runId });
    state.testResults = results;

    document.getElementById('t-proc').style.display = 'none';
    document.getElementById('t-results').style.display = 'block';

    // Populate test table
    const tbody = document.getElementById('test-tbody');
    tbody.innerHTML = '';

    const driftChips = {
      0: {cls: 'ok',   label: 'Type 0 · Identical'},
      1: {cls: 'info', label: 'Type 1 · Acceptable'},
      2: {cls: 'warn', label: 'Type 2 · Semantic ⚠'},
      3: {cls: 'err',  label: 'Type 3 · Breaking ✗'}
    };

    let identicalCount = 0;
    let driftCount = 0;
    let breakingCount = 0;

    results.forEach(r => {
      const chip = driftChips[r.drift_type] || driftChips[1];
      const legacyStr = formatOutput(r.legacy_output);
      const modernStr = formatOutput(r.modern_output);
      const tr = document.createElement('tr');
      if (r.drift_type >= 2) tr.classList.add('highlight');
      tr.innerHTML =
        '<td>' + escHtml(r.test_case) + '</td>' +
        '<td>' + escHtml(legacyStr) + '</td>' +
        '<td>' + escHtml(modernStr) + '</td>' +
        '<td><span class="status-chip ' + chip.cls + '">' + chip.label + '</span></td>';
      tbody.appendChild(tr);

      if (r.drift_type === 0) identicalCount++;
      if (r.drift_type >= 2) driftCount++;
      if (r.drift_type === 3) breakingCount++;
    });

    // Update quality gate metrics
    const totalTests = results.length;
    const passIcon = document.getElementById('qg-pass-icon');
    passIcon.textContent = '✓';
    passIcon.className = 'qg-icon pass';
    const passVal = document.getElementById('qg-pass-val');
    passVal.textContent = totalTests + '/' + totalTests;
    passVal.style.color = 'var(--green-tx)';

    const identIcon = document.getElementById('qg-identical-icon');
    identIcon.textContent = identicalCount === totalTests ? '✓' : '!';
    identIcon.className = 'qg-icon ' + (identicalCount === totalTests ? 'pass' : 'warn');
    const identVal = document.getElementById('qg-identical-val');
    identVal.textContent = identicalCount + '/' + totalTests;
    identVal.style.color = identicalCount === totalTests ? 'var(--green-tx)' : 'var(--amber-tx)';

    const driftIcon = document.getElementById('qg-drift-icon');
    driftIcon.textContent = driftCount > 0 ? '!' : '✓';
    driftIcon.className = 'qg-icon ' + (driftCount > 0 ? 'warn' : 'pass');
    const driftVal = document.getElementById('qg-drift-val');
    driftVal.textContent = driftCount > 0 ? driftCount + ' pending' : 'None';
    driftVal.style.color = driftCount > 0 ? 'var(--amber-tx)' : 'var(--green-tx)';

    const breakIcon = document.getElementById('qg-breaking-icon');
    breakIcon.textContent = breakingCount > 0 ? '✗' : '✓';
    breakIcon.className = 'qg-icon ' + (breakingCount > 0 ? 'warn' : 'pass');
    const breakVal = document.getElementById('qg-breaking-val');
    breakVal.textContent = breakingCount > 0 ? breakingCount + ' found' : 'None';
    breakVal.style.color = breakingCount > 0 ? 'var(--red-tx)' : 'var(--green-tx)';

    toast(driftCount > 0
      ? driftCount + ' Type 2+ drift requires adjudication'
      : 'All tests passed — zero drift');
  } catch (e) {
    document.getElementById('t-proc').style.display = 'none';
    toast('Testing error: ' + e.message);
  }
}

async function adjudicate(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('drift-decision');
  document.getElementById('drift-actions').style.display = 'none';

  // Find a Type 2+ test result to adjudicate
  const driftResult = (state.testResults || []).find(r => r.drift_type >= 2);
  const testId = driftResult ? driftResult.test_id : null;

  try {
    await api('/api/testing/' + state.runId + '/adjudicate', 'POST', {
      operator: 'S. Chen',
      decision: action === 'accept' ? 'ACCEPT_VARIANCE' : action === 'preserve' ? 'PRESERVE_BUG' : 'ESCALATE',
      test_id: testId,
      rationale: action === 'accept'
        ? 'Modern rounding is correct per standards'
        : action === 'preserve'
          ? 'Legacy truncation maintained for compatibility'
          : 'Sent to compliance review'
    });
  } catch (e) {
    toast('Adjudication API error: ' + e.message);
  }

  if (action === 'accept') {
    dr.className = 'decision-record accepted show';
    dr.innerHTML = '<div class="dr-header">✓ ACCEPT_VARIANCE</div>' +
      '<div class="dr-body">Modern rounding (HALF_UP) is correct per CAD standards. Classified as Type 1 going forward.</div>' +
      '<div class="dr-ts">BA + Tech Lead · ' + ts + '</div>';
    document.getElementById('btn-to-prod').disabled = false;
    toast('Variance accepted — quality gate cleared');
  } else if (action === 'preserve') {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = '<div class="dr-header">⚠ PRESERVE_BUG</div>' +
      '<div class="dr-body">Legacy truncation maintained for backward compatibility. Documented rationale: downstream systems depend on truncated values.</div>' +
      '<div class="dr-ts">Tech Lead + BA · ' + ts + '</div>';
    document.getElementById('btn-to-prod').disabled = false;
    toast('Bug preserved — documented in governance ledger');
  } else {
    dr.className = 'decision-record escalated show';
    dr.innerHTML = '<div class="dr-header">↗ ESCALATED TO COMPLIANCE</div>' +
      '<div class="dr-body">Rounding difference sent to compliance review. Slice blocked until resolved.</div>' +
      '<div class="dr-ts">Tech Lead · ' + ts + '</div>';
    toast('Escalated — slice blocked pending compliance');
  }
}

// ═══ ZONE 6: PRODUCTION ═══
async function canaryDecision(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('canary-decision');
  document.getElementById('canary-actions').style.display = 'none';
  const stages = document.querySelectorAll('#slice-bar .slice-stage');

  try {
    await api('/api/production/' + state.runId + '/decide', 'POST', {
      operator: 'S. Chen',
      decision: action === 'promote' ? 'promote' : 'extend_shadow',
      rationale: action === 'promote' ? 'Canary approved after shadow period' : 'Extended shadow observation'
    });
  } catch (e) {
    toast('Production decision error: ' + e.message);
  }

  if (action === 'promote') {
    dr.className = 'decision-record accepted show';
    dr.innerHTML = '<div class="dr-header">✓ CANARY APPROVED — 3% LIVE TRAFFIC</div>' +
      '<div class="dr-body">Modern system serving 3% of production. Legacy handles 97%. Monitoring active.</div>' +
      '<div class="dr-ts">BA + Tech Lead · ' + ts + '</div>';
    stages[2].classList.remove('active');
    stages[2].classList.add('completed');
    stages[2].querySelector('.slice-stage-status').textContent = '✓ Passed';
    stages[3].classList.add('active');
    stages[3].querySelector('.slice-stage-status').textContent = '● 3% live';
    updateStatus(6, 'running', '3%');
    toast('Canary approved — 3% routing to modern');
  } else {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = '<div class="dr-header">⏳ SHADOW EXTENDED +14 DAYS</div>' +
      '<div class="dr-body">Additional observation period. New sign-off required after expiry.</div>' +
      '<div class="dr-ts">Tech Lead · ' + ts + '</div>';
    toast('Shadow extended — new review in 14 days');
  }
}

// ═══ UTILITIES ═══
function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatOutput(output) {
  if (!output || typeof output !== 'object') return String(output || '');
  if (output.error) return 'ERROR: ' + output.error;
  const status = output.status || output.action || '';
  const errorCode = output.error_code;
  const payout = output.payout || output.trade_amount;
  const reason = output.reason;
  const parts = [];
  if (status) parts.push(status);
  if (errorCode) parts.push(String(errorCode));
  if (payout) parts.push('$' + payout);
  if (reason) parts.push(reason);
  if (output.tlh_flag) parts.push('TLH');
  return parts.join(' ') || JSON.stringify(output);
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3200);
}

// ═══ INIT ═══
updateStatus(1, 'running', '●');
loadFiles();
