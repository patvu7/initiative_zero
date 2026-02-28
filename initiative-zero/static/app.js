// ═══ CONSTANTS ═══
const OPERATOR = { name: 'S. Chen', role: 'Staff Eng' };
const SESSION_START = new Date().toISOString().split('.')[0] + 'Z';

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

let humanDecisionCount = 0;
let runStartTime = null;
let elapsedInterval = null;

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

// ═══ PIPELINE LOG ═══

/**
 * Append a timestamped entry to the Pipeline Log panel.
 * Automatically scrolls to the latest entry.
 * @param {string} zone - Zone identifier (e.g. "ZONE-1", "FIREWALL")
 * @param {string} message - Log message
 * @param {boolean} isHuman - Whether this is a human decision (styled differently)
 */
function pipelineLog(zone, message, isHuman = false) {
  const logEl = document.getElementById('pipeline-log');
  const wrap = document.getElementById('pipeline-log-wrap');
  if (!logEl) return;
  wrap.style.display = '';
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const zoneClass = zone === 'FIREWALL' ? 'log-firewall' : isHuman ? 'log-human' : 'log-zone';
  const humanTag = isHuman ? '[HUMAN] ' : '';
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML =
    '<span class="log-ts">[' + ts.split('T')[1] + ']</span> ' +
    '<span class="' + zoneClass + '">[' + zone + ']</span> ' +
    humanTag + escHtml(message);
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
}

function togglePipelineLog() {
  const wrap = document.getElementById('pipeline-log-wrap');
  if (wrap.style.display === 'none') {
    wrap.style.display = '';
  } else {
    wrap.style.display = 'none';
  }
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
  // Update run bar status
  const statusMap = {1:'initiated', 2:'analyzing', 3:'extracting', 4:'generating', 5:'testing', 6:'deploying'};
  document.getElementById('rb-status').textContent = statusMap[z] || 'active';
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
  if (z === 6 && !zoneRan[6]) { zoneRan[6] = true; loadDeploymentReadiness(); }
}

// ═══ ZONE 1: LEGACY ENV ═══

/**
 * Load available legacy files from the API and populate the file selector.
 */
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
    const filenameEl = document.getElementById('code-filename-display');
    filenameEl.textContent = 'src/' + filename;
    filenameEl.title = 'src/' + filename;
    document.getElementById('meta-loc').textContent = file.loc.toLocaleString();
    document.getElementById('meta-filename').textContent = filename;
  } catch (e) {
    toast('Error loading file: ' + e.message);
  }
}

function updateRunBar() {
  if (!state.runId) return;
  const bar = document.getElementById('run-bar');
  bar.style.display = 'flex';
  document.getElementById('rb-run-id').textContent = state.runId;
  document.getElementById('rb-source').textContent = state.sourceFile || '—';
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
      operator: OPERATOR.name
    });
    state.runId = result.run_id;
    updateRunBar();

    // Start elapsed timer
    runStartTime = Date.now();
    elapsedInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - runStartTime) / 1000);
      const mins = Math.floor(elapsed / 60);
      const secs = elapsed % 60;
      document.getElementById('rb-elapsed').textContent =
        mins + ':' + String(secs).padStart(2, '0');
    }, 1000);

    // Update sidebar system info
    const sidebarSystem = document.querySelector('.sidebar-system');
    const displayName = state.sourceFile.replace('.cbl', '').toUpperCase().replace(/_/g, '_');
    sidebarSystem.innerHTML =
      '<strong>System:</strong> ' + displayName + '<br>' +
      '<strong>Source:</strong> COBOL / DB2<br>' +
      '<strong>Run:</strong> ' + state.runId;

    // Update breadcrumb
    document.querySelector('.breadcrumb span:first-child').textContent = displayName;

    pipelineLog('ZONE-1', 'Run ' + state.runId + ' initiated by ' + OPERATOR.name + ' — source: ' + state.sourceFile);

    advanceZone(2);
  } catch (e) {
    toast('Error creating run: ' + e.message);
  }
}

// ═══ ZONE 2: ANALYSIS ═══

/**
 * Run Zone 2 analysis via Claude API.
 * Populates the analysis data grid, confidence rubric, reasoning panel,
 * architectural recommendations, and migration risk table. Updates run bar status.
 * @throws {Error} If API call fails or returns unparseable response
 */
async function runAnalysis() {
  updateStatus(2, 'running', '●');
  pipelineLog('ZONE-2', 'Analysis started — model: claude-sonnet-4-20250514');

  // Loading state: rotating progress messages
  const progressMessages = [
    'Mapping control flow paths\u2026',
    'Identifying business rules in PROCEDURE DIVISION\u2026',
    'Calculating cyclomatic complexity\u2026',
    'Assessing migration economics\u2026',
    'Building confidence rubric\u2026'
  ];
  let msgIndex = 0;
  const progressInterval = setInterval(() => {
    msgIndex = (msgIndex + 1) % progressMessages.length;
    const procText = document.querySelector('#a-proc .processing-text');
    if (procText) procText.textContent = progressMessages[msgIndex];
  }, 2500);

  try {
    const result = await api('/api/analysis/run', 'POST', { run_id: state.runId });
    clearInterval(progressInterval);
    state.analysis = result;
    const m = result.metrics;
    if (!m) {
      throw new Error(result.error || 'Analysis returned no metrics');
    }

    document.getElementById('a-proc').style.display = 'none';
    document.getElementById('a-results').style.display = 'block';

    // ── App Analysis ──
    const app = m.app_analysis || {};
    document.getElementById('a-purpose').textContent = app.purpose || '—';
    document.getElementById('a-stack').textContent = app.stack || '—';
    document.getElementById('a-deps').textContent =
      (app.dependencies_upstream || 0) + ' upstream, ' + (app.dependencies_downstream || 0) + ' downstream';
    const critEl = document.getElementById('a-criticality');
    critEl.textContent = app.criticality || '—';
    if (app.criticality === 'Tier 1') critEl.classList.add('bad');
    document.getElementById('a-domain').textContent = app.domain || '—';
    const dsEl = document.getElementById('a-data-sensitivity');
    dsEl.textContent = app.data_sensitivity || '—';
    if (app.data_sensitivity === 'High') dsEl.classList.add('bad');
    document.getElementById('a-criticality-detail').textContent = app.criticality_rationale || '';
    document.getElementById('a-sensitivity-detail').textContent = app.data_sensitivity_rationale || '';

    // ── Code Analysis ──
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

    document.getElementById('a-cyclomatic-detail').textContent = code.cyclomatic_detail || '';
    document.getElementById('a-deadcode-detail').textContent = code.dead_code_detail || '';
    renderDetailList('a-security-list', 'Security Concerns', code.security_detail || []);
    renderDetailList('a-workaround-list', 'Workaround Details', code.workaround_details || []);
    renderDetailList('a-quality-list', 'Code Quality', code.code_quality_notes || []);

    // ── Test Analysis ──
    const test = m.test_analysis || {};
    const cov = document.getElementById('a-coverage');
    cov.textContent = (test.estimated_coverage_pct || 0).toFixed(0) + '%';
    if ((test.estimated_coverage_pct || 0) < 50) cov.classList.add('bad');
    document.getElementById('a-unit').textContent = test.has_unit_tests || '—';
    const integ = document.getElementById('a-integration');
    integ.textContent = test.has_integration_tests || '—';
    if (test.has_integration_tests === 'None') integ.classList.add('bad');
    const edgeCases = test.untested_edge_cases || [];
    document.getElementById('a-edgecases').textContent = edgeCases.length + ' identified';
    if (edgeCases.length > 0) document.getElementById('a-edgecases').classList.add('bad');

    document.getElementById('a-coverage-rationale').textContent = test.coverage_rationale || '';
    renderDetailList('a-edgecase-list', 'Untested Edge Cases', edgeCases);
    renderDetailList('a-testing-risks-list', 'Testing Risks', test.testing_risks || []);

    // ── Cost Analysis ──
    const econ = m.migration_economics || {};
    document.getElementById('a-annual').textContent = econ.estimated_annual_maintenance || '—';
    const aiCost = document.getElementById('a-ai-cost');
    aiCost.textContent = econ.estimated_ai_migration_cost || '—';
    aiCost.classList.add('good');
    document.getElementById('a-manual-cost').textContent = econ.estimated_manual_migration_cost || '—';
    const roi = document.getElementById('a-roi');
    roi.textContent = (econ.roi_breakeven_months || '—') + ' months';
    roi.classList.add('good');
    document.getElementById('a-maintenance-breakdown').textContent = econ.maintenance_breakdown || '';
    renderDetailList('a-hidden-costs-list', 'Hidden Costs', econ.hidden_costs || []);

    // ── Migration Risks ──
    const risks = m.migration_risks || [];
    if (risks.length > 0) {
      document.getElementById('a-risks-label').style.display = '';
      document.getElementById('a-risks-table-wrap').style.display = '';
      const rtbody = document.getElementById('a-risks-tbody');
      rtbody.innerHTML = '';
      risks.forEach(r => {
        const tr = document.createElement('tr');
        const sevCls = r.severity === 'High' ? 'bad' : r.severity === 'Medium' ? 'warn' : '';
        tr.innerHTML =
          '<td>' + escHtml(r.risk) + '</td>' +
          '<td><span class="data-val ' + sevCls + '">' + escHtml(r.severity) + '</span></td>' +
          '<td>' + escHtml(r.mitigation) + '</td>';
        rtbody.appendChild(tr);
      });
    }

    // ── Confidence Rubric ──
    const rubric = m.confidence_rubric || {};
    const rubricGrid = document.getElementById('rubric-grid');
    rubricGrid.innerHTML = '';
    const dimLabels = {
      code_clarity: 'Code Clarity',
      business_rule_extractability: 'Rule Extractability',
      test_coverage_confidence: 'Test Coverage',
      dependency_isolation: 'Dep. Isolation',
      migration_complexity: 'Migration Simplicity'
    };
    for (const [key, label] of Object.entries(dimLabels)) {
      const dim = rubric[key] || {};
      const scorePct = Math.round((dim.score || 0) * 100);
      const scoreCls = scorePct >= 70 ? 'high' : scorePct >= 40 ? 'mid' : 'low';
      const item = document.createElement('div');
      item.className = 'rubric-item';
      item.innerHTML =
        '<div class="rubric-dim">' + escHtml(label) + '</div>' +
        '<div class="rubric-score ' + scoreCls + '">' + scorePct + '%</div>' +
        '<div class="rubric-weight">Weight: ' + Math.round((dim.weight || 0) * 100) + '%</div>' +
        '<div class="rubric-rationale">' + escHtml(dim.rationale || '—') + '</div>';
      rubricGrid.appendChild(item);
    }

    // ── Confidence bar + reasoning panel ──
    const confPct = Math.round((result.confidence_score || 0) * 100);
    const conf = result.confidence_score || 0;
    const recText = result.recommendation || 'Caution';
    const rationaleText = m.recommendation_rationale || '';

    setTimeout(() => {
      document.getElementById('conf-fill').style.width = confPct + '%';
      let v = 0;
      const iv = setInterval(() => {
        v++;
        document.getElementById('conf-score').textContent = v + '%';
        if (v >= confPct) {
          clearInterval(iv);
          document.getElementById('conf-rec').textContent =
            'Recommendation: ' + recText + (rationaleText ? ' — ' + rationaleText : '');
        }
      }, 16);
    }, 200);

    // Populate AI reasoning panel from analysis data
    const reasoningPanel = document.getElementById('reasoning-panel');
    reasoningPanel.style.display = 'block';

    const topRisk = risks.length > 0 ? risks.sort((a,b) =>
      (a.severity === 'High' ? 0 : a.severity === 'Medium' ? 1 : 2) -
      (b.severity === 'High' ? 0 : b.severity === 'Medium' ? 1 : 2)
    )[0] : null;

    document.getElementById('reasoning-approach').textContent =
      'Rule extraction and greenfield generation (not lift-and-shift). ' +
      rationaleText;

    document.getElementById('reasoning-not-lift').textContent =
      'Lift-and-shift would carry forward ' +
      (code.dead_code_pct || 0).toFixed(0) + '% dead code, ' +
      (code.workarounds_identified || 0) + ' identified workaround(s), and ' +
      (code.security_issues || 0) + ' security issue(s). ' +
      'Rule extraction eliminates all three by generating from requirements only.';

    document.getElementById('reasoning-risk').textContent = topRisk
      ? '[' + topRisk.severity + '] ' + topRisk.risk + ' — Mitigation: ' + topRisk.mitigation
      : 'No high-severity migration risks identified.';

    // Reference to Playbook maturity model
    const maturityBefore = 'Ad hoc';
    const maturityAfter = conf >= 0.7 ? 'Systematic' : 'Planned';
    document.getElementById('reasoning-maturity').textContent =
      'This system currently operates at "' + maturityBefore + '" modernization maturity. ' +
      'Completing this migration moves it to "' + maturityAfter + '" with ' +
      'documented business rules, automated testing, and a repeatable pipeline. ' +
      'Subsequent systems will benefit from reusable domain patterns.';

    // ── Architectural Recommendations (Playbook alignment) ──
    const arch = m.architectural_recommendations || {};
    const boundaries = arch.microservice_boundaries || [];
    const integrations = arch.integration_modernization || [];
    if (boundaries.length > 0 || integrations.length > 0) {
      document.getElementById('arch-recs-panel').style.display = '';
      const boundEl = document.getElementById('arch-boundaries');
      const integEl = document.getElementById('arch-integrations');
      boundEl.innerHTML = '';
      integEl.innerHTML = '';
      boundaries.forEach(b => {
        const div = document.createElement('div');
        div.className = 'detail-item';
        div.textContent = b;
        boundEl.appendChild(div);
      });
      integrations.forEach(ig => {
        const div = document.createElement('div');
        div.className = 'detail-item';
        div.textContent = ig;
        integEl.appendChild(div);
      });
    }

    pipelineLog('ZONE-2', 'Analysis complete — confidence: ' + confPct + '% — recommendation: ' + recText);
    toast('Analysis complete — confidence ' + confPct + '%');
  } catch (e) {
    clearInterval(progressInterval);
    document.getElementById('a-proc').style.display = 'none';
    toast('Analysis error: ' + e.message);
  }
}

function renderDetailList(containerId, label, items) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  if (!items || items.length === 0) return;
  const labelEl = document.createElement('div');
  labelEl.className = 'detail-label';
  labelEl.textContent = label;
  container.appendChild(labelEl);
  items.forEach(item => {
    const div = document.createElement('div');
    div.className = 'detail-item';
    div.textContent = typeof item === 'string' ? item : JSON.stringify(item);
    container.appendChild(div);
  });
}

function downloadAnalysisReport() {
  if (!state.runId) {
    toast('No analysis available');
    return;
  }
  window.open('/api/analysis/' + state.runId + '/report', '_blank');
}

function toggleReasoning() {
  const body = document.getElementById('reasoning-body');
  const toggle = document.getElementById('reasoning-toggle');
  if (body.style.display === 'none') {
    body.style.display = 'block';
    toggle.classList.add('open');
  } else {
    body.style.display = 'none';
    toggle.classList.remove('open');
  }
}

// ═══ ZONE 3: RULE STRAINER ═══

/**
 * Run Zone 3 business rule extraction via Claude API.
 * Populates the rules table, identifies behavioral observations (OBS-*),
 * and enables the SME review flow.
 * @throws {Error} If API call fails
 */
async function runStrainer() {
  updateStatus(3, 'running', '●');
  pipelineLog('ZONE-3', 'Extraction started');
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
    pipelineLog('ZONE-3', rules.length + ' rules extracted (' + explicitCount + ' explicit, ' + obsCount + ' behavioral observations)');
    toast(explicitCount + ' rules extracted' + (obsCount > 0 ? ' + ' + obsCount + ' behavioral observation' + (obsCount > 1 ? 's' : '') : ''));
  } catch (e) {
    document.getElementById('s-proc').style.display = 'none';
    toast('Extraction error: ' + e.message);
  }
}

// ═══ ZONE 3: SME REVIEW FLOW ═══

let smeReviewState = {
  flaggedRules: [],
  reviewedCount: 0
};

/**
 * Open the SME review panel for behavioral observation validation.
 * Fetches the full requirements document and presents flagged rules
 * for individual confirmation, modification, or rejection.
 */
async function openSmeReview() {
  document.getElementById('sme-pre-review').style.display = 'none';
  document.getElementById('sme-review-panel').style.display = 'block';

  // Fetch full requirements doc
  try {
    const reqDoc = await api('/api/extraction/' + state.runId + '/requirements');
    document.getElementById('sme-req-doc-preview').textContent = reqDoc.content || 'No content available';
  } catch (e) {
    document.getElementById('sme-req-doc-preview').textContent = 'Error loading requirements: ' + e.message;
  }

  // Identify rules that need SME review (behavioral/OBS rules)
  const allRules = state.rules || [];
  const flagged = allRules.filter(r =>
    r.rule_type === 'behavioral' || (r.id && r.id.startsWith('OBS'))
  );

  smeReviewState.flaggedRules = flagged;
  smeReviewState.reviewedCount = 0;

  const container = document.getElementById('sme-flagged-rules');
  container.innerHTML = '';

  if (flagged.length === 0) {
    // No behavioral rules — can approve immediately
    document.getElementById('sme-flagged-label').style.display = 'none';
    document.getElementById('btn-approve-spec').disabled = false;
    toast('No behavioral observations found — ready for approval');
    return;
  }

  document.getElementById('sme-flagged-label').style.display = '';
  document.getElementById('sme-flagged-label').textContent =
    flagged.length + ' Item' + (flagged.length > 1 ? 's' : '') + ' Requiring SME Review';

  flagged.forEach((r, i) => {
    const div = document.createElement('div');
    div.className = 'sme-review-item';
    div.id = 'sme-item-' + i;
    div.innerHTML =
      '<div class="sme-review-item-header">' +
        '<span class="sme-review-item-id">' + escHtml(r.id) + '</span>' +
        '<span class="sme-review-item-type">Behavioral Observation</span>' +
      '</div>' +
      '<div class="sme-review-item-text">' + escHtml(r.rule_text) + '</div>' +
      '<div class="sme-review-item-source">Source: ' + escHtml(r.source_reference || 'Inferred from code patterns') + '</div>' +
      '<div class="sme-review-item-actions" id="sme-actions-' + i + '">' +
        '<button class="btn green" onclick="reviewSmeItem(' + i + ', \'confirm\')">✓ Confirm Accurate</button>' +
        '<button class="btn amber" onclick="reviewSmeItem(' + i + ', \'modify\')">Modify & Confirm</button>' +
        '<button class="btn red" onclick="reviewSmeItem(' + i + ', \'reject\')">✗ Reject</button>' +
      '</div>' +
      '<div class="sme-review-item-status" id="sme-status-' + i + '"></div>';
    container.appendChild(div);
  });
}

function reviewSmeItem(index, action) {
  const item = document.getElementById('sme-item-' + index);
  const actions = document.getElementById('sme-actions-' + index);
  const status = document.getElementById('sme-status-' + index);
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const ruleId = smeReviewState.flaggedRules[index]?.id || 'OBS-' + index;

  actions.style.display = 'none';
  item.classList.add('reviewed');

  if (action === 'confirm') {
    status.textContent = '✓ Confirmed by ' + OPERATOR.name + ' at ' + ts;
    status.style.color = 'var(--green-tx)';
    pipelineLog('ZONE-3', 'SME review: ' + ruleId + ' confirmed by ' + OPERATOR.name, true);
  } else if (action === 'modify') {
    status.textContent = '✎ Modified & confirmed by ' + OPERATOR.name + ' at ' + ts;
    status.style.color = 'var(--amber-tx)';
    pipelineLog('ZONE-3', 'SME review: ' + ruleId + ' modified by ' + OPERATOR.name, true);
  } else {
    status.textContent = '✗ Rejected by ' + OPERATOR.name + ' at ' + ts;
    status.style.color = 'var(--red-tx)';
    item.style.borderColor = 'var(--red)';
    item.style.background = 'var(--red-dim)';
    pipelineLog('ZONE-3', 'SME review: ' + ruleId + ' rejected by ' + OPERATOR.name, true);
  }

  smeReviewState.reviewedCount++;

  // Enable approve button once all flagged items are reviewed
  if (smeReviewState.reviewedCount >= smeReviewState.flaggedRules.length) {
    document.getElementById('btn-approve-spec').disabled = false;
    toast('All observations reviewed — ready for approval');
  } else {
    const remaining = smeReviewState.flaggedRules.length - smeReviewState.reviewedCount;
    toast(remaining + ' item' + (remaining > 1 ? 's' : '') + ' remaining for review');
  }
}

function downloadPrd() {
  if (!state.runId) {
    toast('No extraction available');
    return;
  }
  window.open('/api/extraction/' + state.runId + '/prd', '_blank');
}

/**
 * Handle SME specification sign-off (approve or flag for BA review).
 * Records decision in the audit trail, triggers firewall crossing animation
 * on approval, and enables Zone 4 generation.
 * @param {string} action - "approve" or "flag"
 */
async function smeSign(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('sme-decision');
  document.getElementById('sme-actions').style.display = 'none';
  document.getElementById('sme-review-panel').style.display = 'none';
  document.getElementById('sme-pre-review').style.display = 'none';

  if (action === 'approve') {
    try {
      const result = await api('/api/extraction/' + state.runId + '/approve', 'POST', {
        operator: OPERATOR.name,
        rationale: 'Requirements document validated after SME review'
      });
      state.requirementsDocId = result.requirements_doc_id;
      dr.className = 'decision-record accepted show';
      dr.innerHTML = '<div class="dr-header">✓ SPEC APPROVED</div>' +
        '<div class="dr-body">Requirements document validated after SME review. ' +
        smeReviewState.flaggedRules.length + ' behavioral observation(s) reviewed. ' +
        'Cleared to cross security firewall.</div>' +
        '<div class="dr-ts">' + escHtml(result.operator) + ' (' + OPERATOR.role + ') · ' + escHtml(result.timestamp) + '</div>';
      document.getElementById('btn-to-gen').disabled = false;
      humanDecisionCount++;
      document.getElementById('rb-decisions').textContent = humanDecisionCount;
      document.getElementById('rb-crossings').textContent = '1';

      pipelineLog('ZONE-3', 'Spec approved by ' + OPERATOR.name + ' — firewall crossing authorized', true);

      // Firewall crossing animation
      const firewallDiv = document.querySelector('.firewall-divider');
      if (firewallDiv) {
        firewallDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firewallDiv.classList.add('crossing');
        setTimeout(() => {
          firewallDiv.classList.remove('crossing');
        }, 600);
      }
      pipelineLog('FIREWALL', 'Requirements doc crossed to external zone');

      toast('Spec approved — firewall crossing authorized');
    } catch (e) {
      document.getElementById('sme-actions').style.display = '';
      document.getElementById('sme-review-panel').style.display = 'block';
      toast('Approval error: ' + e.message);
    }
  } else {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = '<div class="dr-header">⚠ FLAGGED FOR BA REVIEW</div>' +
      '<div class="dr-body">Behavioral observations require business analyst confirmation before proceeding.</div>' +
      '<div class="dr-ts">' + OPERATOR.name + ' (' + OPERATOR.role + ') · ' + ts + '</div>';
    toast('Spec flagged — awaiting BA review');
  }
}

// ═══ ZONE 4: GENERATION ═══

/**
 * Run Zone 4 code generation via Claude API (external zone).
 * Generates Python code from requirements-only (no source code).
 * Displays requirements and generated code side-by-side with the
 * generation prompt visible for firewall proof.
 * @throws {Error} If API call fails
 */
async function runGeneration() {
  updateStatus(4, 'running', '●');
  pipelineLog('ZONE-4', 'Generation started — input: requirements only (no source code)');

  // Loading state: rotating progress messages
  const genProgressMessages = [
    'Building domain model from requirements\u2026',
    'Generating class structure\u2026',
    'Implementing business rule methods\u2026',
    'Adding error handling and validation\u2026',
    'Formatting Python output\u2026'
  ];
  let genMsgIndex = 0;
  const genProgressInterval = setInterval(() => {
    genMsgIndex = (genMsgIndex + 1) % genProgressMessages.length;
    const procText = document.querySelector('#g-proc .processing-text');
    if (procText) procText.textContent = genProgressMessages[genMsgIndex];
  }, 2500);

  try {
    const [genResult, reqResult] = await Promise.all([
      api('/api/generation/run', 'POST', {
        run_id: state.runId,
        requirements_doc_id: state.requirementsDocId
      }),
      api('/api/extraction/' + state.runId + '/requirements')
    ]);

    clearInterval(genProgressInterval);
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

    const lineCount = (genResult.code || '').split('\n').length;
    pipelineLog('ZONE-4', 'Python module generated — ' + lineCount + ' lines');
    toast('Python application generated from requirements');
  } catch (e) {
    clearInterval(genProgressInterval);
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

/**
 * Run Zone 5 test execution.
 * Phase 1: AI generates test cases from requirements via Claude API.
 * Phase 2: Executes generated code in a sandbox, classifies drift between
 * legacy and modern outputs, and populates the quality gate metrics.
 * @throws {Error} If API call fails
 */
async function runTesting() {
  updateStatus(5, 'running', '●');
  pipelineLog('ZONE-5', 'Test Agent generating test cases from requirements…');

  // Phase 1 progress messages
  const testGenMessages = [
    'Test Agent generating test cases from requirements…',
    'Analyzing business rules for test coverage…',
    'Generating boundary condition tests…',
    'Building error handling scenarios…',
    'Compiling test suite…'
  ];
  let testMsgIndex = 0;
  const testProgressInterval = setInterval(() => {
    testMsgIndex = (testMsgIndex + 1) % testGenMessages.length;
    const procText = document.querySelector('#t-proc .processing-text');
    if (procText) procText.textContent = testGenMessages[testMsgIndex];
  }, 2500);

  try {
    const results = await api('/api/testing/run', 'POST', { run_id: state.runId });
    clearInterval(testProgressInterval);
    state.testResults = results;

    // Count sources
    const aiCount = results.filter(r => r.source === 'ai_generated').length;
    const legacyCount = results.filter(r => r.source === 'legacy_trace').length;

    document.getElementById('t-proc').style.display = 'none';
    document.getElementById('t-results').style.display = 'block';

    pipelineLog('ZONE-5', results.length + ' test cases generated (' + aiCount + ' from AI, ' + legacyCount + ' from legacy traces)');

    // Populate test table with source column
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
      const sourceChip = r.source === 'ai_generated'
        ? '<span class="status-chip info">AI Generated</span>'
        : '<span class="status-chip ok">Legacy Trace</span>';
      const tr = document.createElement('tr');
      if (r.drift_type >= 2) tr.classList.add('highlight');
      tr.innerHTML =
        '<td>' + escHtml(r.test_case) + '</td>' +
        '<td>' + sourceChip + '</td>' +
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

    pipelineLog('ZONE-5', 'Results: ' + identicalCount + ' identical, ' + (totalTests - identicalCount - driftCount) + ' acceptable, ' + driftCount + ' semantic drift');
    toast(driftCount > 0
      ? driftCount + ' Type 2+ drift requires adjudication'
      : 'All tests passed — zero drift');
  } catch (e) {
    clearInterval(testProgressInterval);
    document.getElementById('t-proc').style.display = 'none';
    toast('Testing error: ' + e.message);
  }
}

/**
 * Adjudicate Type 2+ drift: accept the variance, preserve the legacy bug,
 * or escalate to compliance. Records decision in the audit trail.
 * @param {string} action - "accept", "preserve", or "escalate"
 */
async function adjudicate(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('drift-decision');
  document.getElementById('drift-actions').style.display = 'none';

  // Find a Type 2+ test result to adjudicate
  const driftResult = (state.testResults || []).find(r => r.drift_type >= 2);
  const testId = driftResult ? driftResult.test_id : null;

  const decisionLabel = action === 'accept' ? 'ACCEPT_VARIANCE' : action === 'preserve' ? 'PRESERVE_BUG' : 'ESCALATE';

  try {
    await api('/api/testing/' + state.runId + '/adjudicate', 'POST', {
      operator: OPERATOR.name,
      decision: decisionLabel,
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

  humanDecisionCount++;
  document.getElementById('rb-decisions').textContent = humanDecisionCount;
  pipelineLog('ZONE-5', 'Drift adjudicated: ' + decisionLabel + ' by ' + OPERATOR.name, true);

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

/**
 * Load deployment readiness data from all prior zones.
 * Populates the readiness summary grid, decisions audit trail,
 * and enables the production authorization gate.
 */
async function loadDeploymentReadiness() {
  updateStatus(6, 'running', '●');
  pipelineLog('ZONE-6', 'Loading deployment readiness data…');

  document.getElementById('deploy-proc').style.display = '';
  document.getElementById('deploy-results').style.display = 'none';

  try {
    const data = await api('/api/deployment/' + state.runId + '/readiness');

    document.getElementById('deploy-proc').style.display = 'none';
    document.getElementById('deploy-results').style.display = 'block';

    // Analysis card
    if (data.analysis) {
      const confPct = Math.round((data.analysis.confidence_score || 0) * 100);
      const confEl = document.getElementById('dr-confidence');
      confEl.textContent = confPct + '%';
      confEl.className = 'data-val' + (confPct >= 70 ? ' good' : confPct >= 40 ? ' warn' : ' bad');
      document.getElementById('dr-recommendation').textContent = data.analysis.recommendation || '—';
    }

    // Rules card
    if (data.rules) {
      document.getElementById('dr-rules-total').textContent = data.rules.total || '0';
      const approvedEl = document.getElementById('dr-spec-approved');
      if (data.rules.spec_approved_by) {
        approvedEl.textContent = '✓ ' + data.rules.spec_approved_by;
        approvedEl.className = 'data-val good';
      } else {
        approvedEl.textContent = 'Pending';
        approvedEl.className = 'data-val warn';
      }
    }

    // Tests card
    if (data.tests) {
      document.getElementById('dr-tests-total').textContent = data.tests.total || '0';
      const passable = (data.tests.identical || 0) + (data.tests.acceptable || 0);
      const total = data.tests.total || 1;
      const passRate = Math.round((passable / total) * 100);
      const prEl = document.getElementById('dr-pass-rate');
      prEl.textContent = passRate + '%';
      prEl.className = 'data-val' + (passRate >= 80 ? ' good' : ' warn');
      const driftParts = [];
      if (data.tests.identical > 0) driftParts.push(data.tests.identical + ' identical');
      if (data.tests.semantic > 0) driftParts.push(data.tests.semantic + ' semantic');
      if (data.tests.breaking > 0) driftParts.push(data.tests.breaking + ' breaking');
      document.getElementById('dr-drift-summary').textContent = driftParts.join(', ') || 'None';
    }

    // Decisions card
    if (data.decisions) {
      document.getElementById('dr-decisions-count').textContent = data.decisions.length;
      if (data.decisions.length > 0) {
        const latest = data.decisions[data.decisions.length - 1];
        document.getElementById('dr-latest-decision').textContent =
          latest.gate_name + ': ' + latest.decision;
      }

      // Populate decisions audit trail table
      if (data.decisions.length > 0) {
        document.getElementById('deploy-decisions-label').style.display = '';
        document.getElementById('deploy-decisions-wrap').style.display = '';
        const tbody = document.getElementById('deploy-decisions-tbody');
        tbody.innerHTML = '';
        data.decisions.forEach(d => {
          const tr = document.createElement('tr');
          tr.innerHTML =
            '<td class="rule-id">Zone ' + d.zone + '</td>' +
            '<td>' + escHtml(d.gate_name) + '</td>' +
            '<td><span class="status-chip ok">' + escHtml(d.decision) + '</span></td>' +
            '<td>' + escHtml(d.operator) + '</td>' +
            '<td style="font-family:var(--mono);font-size:10px;color:var(--tx4)">' + escHtml(d.created_at || '') + '</td>';
          tbody.appendChild(tr);
        });
      }
    }

    pipelineLog('ZONE-6', 'Deployment readiness loaded — awaiting authorization');
    toast('Deployment readiness summary loaded');
  } catch (e) {
    document.getElementById('deploy-proc').style.display = 'none';
    toast('Readiness load error: ' + e.message);
  }
}

/**
 * Handle production authorization decision.
 * "authorize" → records decision, shows success, marks shadow stage active
 * "review" → records decision, shows extended review record
 * @param {string} action - "authorize" or "review"
 */
async function productionDecision(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('canary-decision');
  document.getElementById('canary-actions').style.display = 'none';

  try {
    await api('/api/production/' + state.runId + '/decide', 'POST', {
      operator: OPERATOR.name,
      decision: action,
      rationale: action === 'authorize'
        ? 'Shadow deployment authorized after pipeline review'
        : 'Extended review requested — additional observation needed'
    });
  } catch (e) {
    toast('Production decision error: ' + e.message);
  }

  humanDecisionCount++;
  document.getElementById('rb-decisions').textContent = humanDecisionCount;

  const stages = document.querySelectorAll('#slice-bar .slice-stage');

  if (action === 'authorize') {
    pipelineLog('ZONE-6', 'Shadow deployment authorized by ' + OPERATOR.name, true);
    dr.className = 'decision-record accepted show';
    dr.innerHTML = '<div class="dr-header">✓ SHADOW DEPLOYMENT AUTHORIZED</div>' +
      '<div class="dr-body">Modern system deployed in shadow mode. All traffic mirrored for comparison. Zero live impact. Monitoring active.</div>' +
      '<div class="dr-ts">' + OPERATOR.name + ' (' + OPERATOR.role + ') · ' + ts + '</div>';
    if (stages.length > 0) {
      stages[0].classList.add('active');
      stages[0].querySelector('.slice-stage-status').textContent = '● Active';
    }
    updateStatus(6, 'done', '✓');
    toast('Shadow deployment authorized');
  } else {
    pipelineLog('ZONE-6', 'Extended review requested by ' + OPERATOR.name, true);
    dr.className = 'decision-record preserved show';
    dr.innerHTML = '<div class="dr-header">⏳ EXTENDED REVIEW REQUESTED</div>' +
      '<div class="dr-body">Additional review period. Pipeline results preserved for re-evaluation.</div>' +
      '<div class="dr-ts">' + OPERATOR.name + ' (' + OPERATOR.role + ') · ' + ts + '</div>';
    toast('Extended review requested');
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

// ═══ KEYBOARD SHORTCUTS ═══
document.addEventListener('keydown', (e) => {
  // Ctrl+Right to advance zone (when advance button is visible and enabled)
  if (e.key === 'ArrowRight' && e.ctrlKey) {
    const activePanel = document.querySelector('.zone-panel.active');
    const advBtn = activePanel?.querySelector('.btn-advance:not(:disabled)');
    if (advBtn) advBtn.click();
  }
});

// ═══ INIT ═══
updateStatus(1, 'running', '●');
loadFiles();

// Update sidebar footer with constants
document.querySelector('.sidebar-footer').innerHTML =
  'Operator: ' + OPERATOR.name + ' (' + OPERATOR.role + ')<br>' +
  'Session: ' + SESSION_START;
