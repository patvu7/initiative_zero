const ZONES = {1:'Legacy Env',2:'Analysis',3:'Rule Strainer',4:'Generation',5:'Testing',6:'Production'};
let currentZone = 1;
const zoneRan = {1:false,2:false,3:false,4:false,5:false,6:false};
const RULES = [
  {id:'BR-001',rule:'Deny if claim_amount > coverage_limit. Error: 1001.',src:'VALIDATE-CLAIM §1',status:'ok',statusText:'Extracted'},
  {id:'BR-002',rule:'Deny if policy_number is blank. Error: 1002.',src:'VALIDATE-CLAIM §2',status:'ok',statusText:'Extracted'},
  {id:'BR-003',rule:'net_claim = claim_amount − deductible',src:'CALC-PAYOUT §1',status:'ok',statusText:'Extracted'},
  {id:'BR-004',rule:'payout = min(net_claim, coverage_limit)',src:'CALC-PAYOUT §2',status:'ok',statusText:'Extracted'},
  {id:'BR-005',rule:'Set status = APPROVED after successful calculation',src:'CALC-PAYOUT §3',status:'ok',statusText:'Extracted'},
  {id:'BR-006',rule:'Write immutable audit log per claim decision',src:'WRITE-AUDIT-LOG',status:'ok',statusText:'Extracted'},
  {id:'OBS-01',rule:'Month-end batch recalculation found in DB2 logs — not in source code',src:'DB2 audit logs',status:'warn',statusText:'Needs SME'},
];

function goZone(z) {
  currentZone = z;
  // Update sidebar
  document.querySelectorAll('.nav-item').forEach(el => {
    const n = +el.dataset.zone;
    el.classList.remove('active');
    if (n === z) el.classList.add('active');
  });
  // Update panels
  document.querySelectorAll('.zone-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('zp-' + z).classList.add('active');
  // Update breadcrumb
  document.getElementById('bc-zone').textContent = ZONES[z];
  document.getElementById('pipeline-status').textContent = 'Zone ' + z + ' of 6';
  // Run zone animation if needed
  runZone(z);
}

function advanceZone(z) {
  // Mark previous as completed
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

function runAnalysis() {
  updateStatus(2, 'running', '●');
  setTimeout(() => {
    document.getElementById('a-proc').style.display = 'none';
    document.getElementById('a-results').style.display = 'block';
    // Animate confidence
    setTimeout(() => {
      document.getElementById('conf-fill').style.width = '82%';
      let v = 0;
      const iv = setInterval(() => {
        v++;
        document.getElementById('conf-score').textContent = v + '%';
        if (v >= 82) {
          clearInterval(iv);
          document.getElementById('conf-rec').textContent = 'Recommendation: Proceed — COBOL → Python';
        }
      }, 16);
    }, 200);
    toast('Analysis complete — confidence 82%');
  }, 2200);
}

function runStrainer() {
  updateStatus(3, 'running', '●');
  setTimeout(() => {
    document.getElementById('s-proc').style.display = 'none';
    document.getElementById('s-results').style.display = 'block';
    // Populate rules
    const tbody = document.getElementById('rules-tbody');
    RULES.forEach((r, i) => {
      setTimeout(() => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td class="rule-id">${r.id}</td><td class="rule-text">${r.rule}</td><td class="rule-src">${r.src}</td><td><span class="status-chip ${r.status}">${r.statusText}</span></td>`;
        tr.style.opacity = '0';
        tr.style.transition = 'opacity .3s';
        tbody.appendChild(tr);
        requestAnimationFrame(() => tr.style.opacity = '1');
      }, i * 180);
    });
    toast('6 rules extracted + 1 behavioral observation');
  }, 2500);
}

function smeSign(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('sme-decision');
  document.getElementById('sme-actions').style.display = 'none';

  if (action === 'approve') {
    dr.className = 'decision-record accepted show';
    dr.innerHTML = `<div class="dr-header">✓ SPEC APPROVED</div><div class="dr-body">Requirements document validated. Cleared to cross security firewall.</div><div class="dr-ts">S. Chen (Staff Eng) · ${ts}</div>`;
    document.getElementById('btn-to-gen').disabled = false;
    toast('Spec approved — firewall crossing authorized');
  } else {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = `<div class="dr-header">⚠ FLAGGED FOR BA REVIEW</div><div class="dr-body">OBS-01 requires business analyst confirmation before proceeding.</div><div class="dr-ts">S. Chen (Staff Eng) · ${ts}</div>`;
    toast('Spec flagged — awaiting BA review');
  }
}

function runGeneration() {
  updateStatus(4, 'running', '●');
  setTimeout(() => {
    document.getElementById('g-proc').style.display = 'none';
    document.getElementById('g-results').style.display = 'block';
    toast('Python application generated from requirements');
  }, 2200);
}

function runTesting() {
  updateStatus(5, 'running', '●');
  setTimeout(() => {
    document.getElementById('t-proc').style.display = 'none';
    document.getElementById('t-results').style.display = 'block';
    toast('1 Type 2 drift requires adjudication');
  }, 2200);
}

function adjudicate(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('drift-decision');
  document.getElementById('drift-actions').style.display = 'none';

  if (action === 'accept') {
    dr.className = 'decision-record accepted show';
    dr.innerHTML = `<div class="dr-header">✓ ACCEPT_VARIANCE</div><div class="dr-body">Modern rounding (HALF_UP) is correct per CAD standards. Classified as Type 1 going forward.</div><div class="dr-ts">BA + Tech Lead · ${ts}</div>`;
    document.getElementById('btn-to-prod').disabled = false;
    toast('Variance accepted — quality gate cleared');
  } else if (action === 'preserve') {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = `<div class="dr-header">⚠ PRESERVE_BUG</div><div class="dr-body">Legacy truncation maintained for backward compatibility. Documented rationale: downstream systems depend on truncated values.</div><div class="dr-ts">Tech Lead + BA · ${ts}</div>`;
    document.getElementById('btn-to-prod').disabled = false;
    toast('Bug preserved — documented in governance ledger');
  } else {
    dr.className = 'decision-record escalated show';
    dr.innerHTML = `<div class="dr-header">↗ ESCALATED TO COMPLIANCE</div><div class="dr-body">Rounding difference sent to compliance review. Slice blocked until resolved.</div><div class="dr-ts">Tech Lead · ${ts}</div>`;
    toast('Escalated — slice blocked pending compliance');
  }
}

function canaryDecision(action) {
  const ts = new Date().toISOString().split('.')[0] + 'Z';
  const dr = document.getElementById('canary-decision');
  document.getElementById('canary-actions').style.display = 'none';
  const stages = document.querySelectorAll('#slice-bar .slice-stage');

  if (action === 'promote') {
    dr.className = 'decision-record accepted show';
    dr.innerHTML = `<div class="dr-header">✓ CANARY APPROVED — 3% LIVE TRAFFIC</div><div class="dr-body">Modern system serving 3% of production. Legacy handles 97%. Monitoring active.</div><div class="dr-ts">BA + Tech Lead · ${ts}</div>`;
    stages[2].classList.remove('active');
    stages[2].classList.add('completed');
    stages[2].querySelector('.slice-stage-status').textContent = '✓ Passed';
    stages[3].classList.add('active');
    stages[3].querySelector('.slice-stage-status').textContent = '● 3% live';
    updateStatus(6, 'running', '3%');
    toast('Canary approved — 3% routing to modern');
  } else {
    dr.className = 'decision-record preserved show';
    dr.innerHTML = `<div class="dr-header">⏳ SHADOW EXTENDED +14 DAYS</div><div class="dr-body">Additional observation period. New sign-off required after expiry.</div><div class="dr-ts">Tech Lead · ${ts}</div>`;
    toast('Shadow extended — new review in 14 days');
  }
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3200);
}

// Init
updateStatus(1, 'running', '●');
