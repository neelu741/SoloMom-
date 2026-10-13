/* SoloMom Advisor Single-Page Application JS Client */

let currentPlanId = null;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadDashboardData();

  // Persona Switcher
  const personaSelect = document.getElementById("persona-select");
  if (personaSelect) {
    personaSelect.addEventListener("change", async (e) => {
      const selected = e.target.value;
      await fetch("/api/dashboard/switch-persona", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona: selected })
      });
      loadDashboardData();
    });
  }

  // Reset Demo button
  document.getElementById("btn-reset-demo").addEventListener("click", async () => {
    const selected = personaSelect ? personaSelect.value : "priya";
    if (confirm(`Reset demo database back to ${selected.toUpperCase()} initial state?`)) {
      await fetch("/api/dashboard/reset-demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona: selected })
      });
      location.reload();
    }
  });

  // Forms & Event listeners
  document.getElementById("form-dash-checkin").addEventListener("submit", handleCheckinSubmit);
  document.getElementById("form-add-expense").addEventListener("submit", handleAddExpenseSubmit);
  document.getElementById("btn-calc-realloc").addEventListener("click", handleReallocCalc);
  document.getElementById("form-add-task").addEventListener("submit", handleAddTaskSubmit);
  document.getElementById("form-triage").addEventListener("submit", handleTriageSubmit);
  document.getElementById("form-profile").addEventListener("submit", handleProfileSubmit);

  // Scenario Buttons
  document.querySelectorAll(".btn-scenario").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const scenario = e.target.getAttribute("data-scenario");
      triggerReplanScenario(scenario);
    });
  });

  // Approve / Undo Plan
  document.getElementById("btn-approve-plan").addEventListener("click", handleApprovePlan);
  document.getElementById("btn-undo-plan").addEventListener("click", handleUndoPlan);

  // Voice Note Handlers
  initVoiceRecorder();
  document.getElementById("form-voice-text").addEventListener("submit", handleVoiceTextSubmit);
});

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

function initVoiceRecorder() {
  const btn = document.getElementById("btn-record-voice");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
          const formData = new FormData();
          formData.append("file", audioBlob, "voice_note.webm");

          document.getElementById("record-text").innerText = "Transcribing & Processing...";
          try {
            const res = await fetch("/api/voice/process-audio", {
              method: "POST",
              body: formData
            }).then(r => r.json());

            renderVoiceResult(res.data);
          } catch (err) {
            console.error("Audio upload failed:", err);
          } finally {
            document.getElementById("record-text").innerText = "Hold / Click to Speak";
            document.getElementById("mic-icon").innerText = "🎤";
            document.getElementById("recording-timer").classList.add("hidden");
          }
        };

        mediaRecorder.start();
        isRecording = true;
        document.getElementById("mic-icon").innerText = "⏹️";
        document.getElementById("record-text").innerText = "Recording... Click to Stop";
        document.getElementById("recording-timer").classList.remove("hidden");

      } catch (err) {
        alert("Microphone permission denied or not available. Use the voice text form below.");
      }
    } else {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
      isRecording = false;
    }
  });
}

async function handleVoiceTextSubmit(e) {
  e.preventDefault();
  const textInput = document.getElementById("voice-text-input");
  const text = textInput.value;
  if (!text) return;

  const res = await fetch("/api/voice/process-text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  }).then(r => r.json());

  renderVoiceResult(res.data);
  textInput.value = "";
}

function renderVoiceResult(data) {
  if (!data) return;
  const box = document.getElementById("voice-result-box");
  box.classList.remove("hidden");

  document.getElementById("voice-transcript-display").innerText = "🗣️ Voice Transcript: \"" + data.transcript + "\"";
  
  const actionsDiv = document.getElementById("voice-actions-display");
  actionsDiv.innerHTML = "<b>Actions Executed by LLM & Rules:</b><br>" + 
    (data.actions_taken || []).map(a => `✅ ${a}`).join("<br>");

  loadDashboardData();
}

// Tab Navigation
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active-tab"));
      tab.classList.add("active-tab");

      const targetId = tab.getAttribute("data-tab");
      document.querySelectorAll(".tab-content").forEach(content => {
        content.classList.add("hidden");
        content.classList.remove("block");
      });
      document.getElementById(targetId).classList.remove("hidden");
      document.getElementById(targetId).classList.add("block");

      // Tab specific loads
      if (targetId === "tab-money") loadMoneyData();
      if (targetId === "tab-health") loadHealthData();
      if (targetId === "tab-tasks") loadTasksData();
      if (targetId === "tab-review") loadReviewData();
      if (targetId === "tab-profile") loadProfileData();
    });
  });
}

// Format Rupee Currency
function fmtINR(amount) {
  const n = Math.round(amount || 0);
  return "₹" + n.toLocaleString("en-IN");
}

// Load Dashboard Overview
async function loadDashboardData() {
  try {
    const [sumRes, cardRes, flagsRes] = await Promise.all([
      fetch("/api/dashboard/summary").then(r => r.json()),
      fetch("/api/dashboard/card").then(r => r.json()),
      fetch("/api/dashboard/flags").then(r => r.json()),
    ]);

    // Persona Badge & Dropdown Sync
    const activePersona = sumRes.active_persona || 'priya';
    const personaSelect = document.getElementById("persona-select");
    if (personaSelect && personaSelect.value !== activePersona) {
      personaSelect.value = activePersona;
    }

    const prof = sumRes.profile || {};
    const child = (sumRes.children && sumRes.children[0]) ? sumRes.children[0] : {};
    document.getElementById("persona-badge").innerHTML = 
      `👤 ${prof.name || 'Priya'} (${prof.age || ''}) & ${child.name || 'Aarav'} (${child.age_years || ''}y) | ${prof.occupation || ''} | ${fmtINR(prof.monthly_income)}`;

    // Update patient options in Triage
    const patientSelect = document.getElementById("triage-patient");
    if (patientSelect) {
      patientSelect.innerHTML = `
        <option value="${child.name || 'Child'}">${child.name || 'Child'} (${prof.name || 'Mother'}'s child)</option>
        <option value="${prof.name || 'Mother'}">${prof.name || 'Mother'} (${prof.occupation || 'Mother'})</option>
      `;
    }

    // Metrics Row
    const rep = sumRes.report || {};
    document.getElementById("dash-metrics").innerHTML = `
      <div class="bg-white border rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-500 font-medium">Monthly Income</div>
        <div class="text-lg font-bold text-slate-900">${fmtINR(rep.income)}</div>
      </div>
      <div class="bg-white border rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-500 font-medium">Planned Total</div>
        <div class="text-lg font-bold text-slate-900">${fmtINR(rep.total_planned)}</div>
      </div>
      <div class="bg-white border rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-500 font-medium">Spent So Far</div>
        <div class="text-lg font-bold text-rose-600">${fmtINR(rep.total_spent)}</div>
      </div>
      <div class="bg-white border rounded-xl p-4 shadow-sm">
        <div class="text-xs text-slate-500 font-medium">Days Remaining</div>
        <div class="text-lg font-bold text-indigo-600">${rep.progress?.days_left || 0} days</div>
      </div>
    `;

    // Today's Executive Personal Assistant Briefing Card
    document.getElementById("card-headline").innerText = cardRes.headline || "Executive Briefing";
    
    const greetingEl = document.getElementById("card-greeting");
    if (greetingEl) {
      greetingEl.innerText = cardRes.greeting || `Good morning ${prof.name || 'Ma\'am'}, here is your morning household briefing:`;
    }

    const bulletsDiv = document.getElementById("card-bullets");
    if (bulletsDiv) {
      bulletsDiv.innerHTML = "";
      const items = cardRes.items || [];
      if (items.length > 0) {
        items.forEach((item, idx) => {
          const categoryColors = {
            "Schedule": { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-800", badge: "bg-blue-100 text-blue-900" },
            "Finance": { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-800", badge: "bg-emerald-100 text-emerald-900" },
            "Bills & Deadlines": { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-800", badge: "bg-amber-100 text-amber-900" },
            "Health": { bg: "bg-rose-50", border: "border-rose-200", text: "text-rose-800", badge: "bg-rose-100 text-rose-900" },
            "Wellbeing": { bg: "bg-purple-50", border: "border-purple-200", text: "text-purple-800", badge: "bg-purple-100 text-purple-900" },
          };
          const style = categoryColors[item.category] || { bg: "bg-slate-50", border: "border-slate-200", text: "text-slate-800", badge: "bg-slate-100 text-slate-800" };
          
          bulletsDiv.innerHTML += `
            <div class="${style.bg} border ${style.border} rounded-xl p-3.5 transition hover:shadow-sm">
              <div class="flex items-start justify-between gap-2 mb-1.5">
                <div class="flex items-center space-x-2">
                  <span class="text-base">${item.icon || '📌'}</span>
                  <span class="font-bold text-xs uppercase tracking-wider px-2 py-0.5 rounded-md ${style.badge}">${item.category || 'TASK'}</span>
                  <span class="font-semibold text-sm text-slate-900">${item.title}</span>
                </div>
                <span class="text-[10px] text-slate-500 font-mono">#Item-${idx + 1}</span>
              </div>
              <p class="text-xs text-slate-700 leading-relaxed mb-2 pl-6">${item.detail}</p>
              <div class="flex items-center space-x-2 pl-6 pt-1 text-xs font-medium ${style.text}">
                <span>💡 <b>Assistant Proposal:</b></span>
                <span>${item.recommendation}</span>
              </div>
            </div>
          `;
        });
      } else {
        bulletsDiv.innerHTML = `<div class="text-xs text-slate-600 italic p-3 bg-slate-50 rounded-xl">No pending tasks or schedule flags right now. Everything is running smoothly!</div>`;
      }
    }

    const closingEl = document.getElementById("card-closing");
    if (closingEl) {
      closingEl.innerText = cardRes.closing || "I'm ready to update your calendar and budget whenever you give the word.";
    }

    const messageEl = document.getElementById("card-message");
    if (messageEl && (!cardRes.items || cardRes.items.length === 0)) {
      messageEl.innerText = cardRes.message || "";
      messageEl.classList.remove("hidden");
    }
    
    const actionsDiv = document.getElementById("card-actions");
    actionsDiv.innerHTML = "";
    (cardRes.actions || []).forEach(act => {
      const btn = document.createElement("button");
      btn.className = "bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg shadow-sm transition flex items-center space-x-1";
      btn.innerHTML = `<span>👉</span> <span>${act.label}</span>`;
      btn.addEventListener("click", () => {
        if (act.id === "book_vaccine" || act.id === "lighter_evening") {
          document.querySelector('[data-tab="tab-advisor"]').click();
        } else if (act.id === "trim_spending") {
          document.querySelector('[data-tab="tab-money"]').click();
        } else {
          document.querySelector('[data-tab="tab-tasks"]').click();
        }
      });
      actionsDiv.appendChild(btn);
    });

    // Scan Flags
    const flagsDiv = document.getElementById("flags-list");
    flagsDiv.innerHTML = "";
    if (!flagsRes || flagsRes.length === 0) {
      flagsDiv.innerHTML = `<div class="text-xs text-emerald-600 font-medium">🟢 All on track. No active risk flags today!</div>`;
    } else {
      flagsRes.forEach(f => {
        const badgeClass = f.severity === "high" ? "badge-high" : f.severity === "watch" ? "badge-watch" : "badge-info";
        flagsDiv.innerHTML += `
          <div class="flex items-start space-x-2 text-xs p-2 rounded-lg bg-slate-50 border">
            <span class="${badgeClass}">${f.severity.toUpperCase()}</span>
            <div>
              <span class="font-semibold text-slate-900">${f.title}:</span>
              <span class="text-slate-600">${f.detail}</span>
            </div>
          </div>
        `;
      });
    }

  } catch (err) {
    console.error("Error loading dashboard data:", err);
  }
}

// Daily Checkin Form Submit
async function handleCheckinSubmit(e) {
  e.preventDefault();
  const sleep_hours = parseFloat(document.getElementById("dash-sleep").value);
  const mood = document.getElementById("dash-mood").value;
  const note = document.getElementById("dash-note").value;

  await fetch("/api/logs/wellbeing", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sleep_hours, mood, note })
  });

  alert("✅ Daily log saved!");
  loadDashboardData();
}

// Load Money Data
async function loadMoneyData() {
  const rep = await fetch("/api/logs/budget").then(r => r.json());
  const listDiv = document.getElementById("budget-category-list");
  listDiv.innerHTML = "";

  const catSelect = document.getElementById("exp-category");
  catSelect.innerHTML = "";

  (rep.categories || []).forEach(cat => {
    catSelect.innerHTML += `<option value="${cat.category}">${cat.category}</option>`;

    const pct = Math.min(100, cat.pct_used || 0);
    const statusBadge = cat.status === "over" 
      ? `<span class="badge-high">OVER PLAN</span>` 
      : cat.status === "at_risk" 
      ? `<span class="badge-watch">AT RISK</span>` 
      : `<span class="badge-info">OK</span>`;

    listDiv.innerHTML += `
      <div class="border rounded-xl p-3 bg-slate-50 space-y-1 text-xs">
        <div class="flex justify-between items-center font-semibold text-slate-900">
          <span>${cat.category} ${cat.is_essential ? '<span class="text-rose-600 text-[10px]">[Essential]</span>' : ''}</span>
          ${statusBadge}
        </div>
        <div class="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
          <div class="bg-rose-500 h-2 rounded-full" style="width: ${pct}%"></div>
        </div>
        <div class="flex justify-between text-slate-500">
          <span>Spent: ${fmtINR(cat.spent)} / ${fmtINR(cat.planned)} (${cat.pct_used}%)</span>
          <span>Remaining: ${fmtINR(cat.remaining)}</span>
        </div>
      </div>
    `;
  });
}

// Add Expense Submit
async function handleAddExpenseSubmit(e) {
  e.preventDefault();
  const category = document.getElementById("exp-category").value;
  const amount = parseFloat(document.getElementById("exp-amount").value);
  const note = document.getElementById("exp-note").value;

  await fetch("/api/logs/expense", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, amount, note })
  });

  alert("✅ Logged expense!");
  loadMoneyData();
  loadDashboardData();
}

// Calculate Reallocation Preview
async function handleReallocCalc() {
  const amount = parseFloat(document.getElementById("realloc-amt").value);
  const res = await fetch("/api/logs/budget/reallocate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount, target_category: "Medical Buffer" })
  }).then(r => r.json());

  const resultDiv = document.getElementById("realloc-result");
  const plan = res.plan || {};
  let movesTxt = (plan.moves || []).map(m => `• Take ${fmtINR(m.amount)} from <b>${m.from}</b> → <b>${m.to}</b>`).join("<br>");
  resultDiv.innerHTML = `
    <div class="p-2 bg-white border border-indigo-200 rounded-lg">
      <b>Strategy:</b> Covered by target: ${fmtINR(plan.covered_by_target)}<br>
      ${movesTxt ? movesTxt : 'No non-essential moves required.'}
    </div>
  `;
}

// Load Health Data
async function loadHealthData() {
  const [wb, vacs] = await Promise.all([
    fetch("/api/logs/wellbeing").then(r => r.json()),
    fetch("/api/logs/vaccines").then(r => r.json())
  ]);

  // Wellbeing Summary
  document.getElementById("wellbeing-summary").innerHTML = `
    <div class="bg-rose-50 border border-rose-200 rounded-xl p-3 text-center">
      <div class="text-xs text-rose-700">7-Day Avg Sleep</div>
      <div class="text-lg font-bold text-rose-900">${wb.avg_sleep} hrs</div>
    </div>
    <div class="bg-indigo-50 border border-indigo-200 rounded-xl p-3 text-center">
      <div class="text-xs text-indigo-700">Low Sleep Streak</div>
      <div class="text-lg font-bold text-indigo-900">${wb.low_sleep_days} days</div>
    </div>
  `;

  // Vaccines
  const vacsDiv = document.getElementById("vaccines-list");
  vacsDiv.innerHTML = "";
  (vacs || []).forEach(v => {
    const isGiven = v.given_date !== null;
    const badge = isGiven ? `<span class="badge-info">GIVEN</span>` : (v.days_overdue > 0 ? `<span class="badge-high">${v.days_overdue} DAYS OVERDUE</span>` : `<span class="badge-watch">DUE SOON</span>`);
    
    vacsDiv.innerHTML += `
      <div class="border rounded-xl p-3 flex justify-between items-center text-xs">
        <div>
          <div class="font-bold text-slate-900">${v.vaccine_name} ${badge}</div>
          <div class="text-slate-500">Due: ${v.due_date} ${isGiven ? '| Given: ' + v.given_date : ''}</div>
        </div>
        ${!isGiven ? `<button onclick="markVaccine(${v.id})" class="bg-rose-600 text-white px-2 py-1 rounded text-xs">Mark Given</button>` : '✅'}
      </div>
    `;
  });
}

async function markVaccine(id) {
  await fetch(`/api/logs/vaccines/${id}/mark-given`, { method: "POST" });
  loadHealthData();
}

// Load Tasks Data
async function loadTasksData() {
  const tasks = await fetch("/api/dashboard/tasks").then(r => r.json());
  const listDiv = document.getElementById("tasks-list");
  listDiv.innerHTML = "";

  if (!tasks || tasks.length === 0) {
    listDiv.innerHTML = `<div class="text-xs text-slate-500 italic p-3">No tasks scheduled for this week.</div>`;
    return;
  }

  tasks.forEach(t => {
    const isDone = t.status === "completed";
    const bgClass = isDone ? "bg-emerald-50/60 border-emerald-200" : "bg-slate-50 border-slate-200";
    const titleClass = isDone ? "line-through text-slate-400 font-medium" : "text-slate-900 font-bold";
    const statusBadge = isDone 
      ? `<span class="bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded-full">✓ COMPLETED</span>`
      : `<span class="bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.5 rounded-full">${t.status.toUpperCase()}</span>`;

    listDiv.innerHTML += `
      <div class="border ${bgClass} rounded-xl p-3 flex justify-between items-center text-xs transition duration-150">
        <div class="flex items-start space-x-3">
          <button onclick="toggleTaskStatus(${t.id})" title="${isDone ? 'Mark as Pending' : 'Mark as Done'}" class="mt-0.5 w-5 h-5 rounded flex items-center justify-center border transition ${isDone ? 'bg-emerald-600 border-emerald-600 text-white' : 'bg-white border-slate-300 hover:border-emerald-500 text-transparent'}">
            <span class="text-xs font-bold leading-none">${isDone ? '✓' : ''}</span>
          </button>
          <div>
            <div class="${titleClass} flex items-center gap-1.5">
              <span>${t.kind === 'appointment' ? '🩺' : '📌'}</span>
              <span>${t.title}</span>
              ${t.is_essential && !isDone ? '<span class="text-rose-600 font-semibold">[Essential]</span>' : ''}
            </div>
            <div class="text-slate-500 text-[11px] mt-0.5">
              Due: ${t.due_date} ${t.start_time ? '| ' + t.start_time + ' - ' + t.end_time : ''}
            </div>
          </div>
        </div>

        <div class="flex items-center space-x-2">
          ${statusBadge}
          <button onclick="toggleTaskStatus(${t.id})" class="text-[11px] font-semibold px-2.5 py-1 rounded-lg border transition ${isDone ? 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50' : 'bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700 shadow-sm'}">
            ${isDone ? '↩ Undo' : '✓ Done'}
          </button>
        </div>
      </div>
    `;
  });
}

async function toggleTaskStatus(taskId) {
  try {
    await fetch(`/api/dashboard/tasks/${taskId}/toggle-complete`, { method: "POST" });
    await loadTasksData();
    // Also refresh dashboard summary so flags and cards re-evaluate if essential task is done
    loadDashboardData();
  } catch (err) {
    console.error("Failed to toggle task status:", err);
  }
}

// Add Task Submit
async function handleAddTaskSubmit(e) {
  e.preventDefault();
  alert("Task added to planner!");
  loadTasksData();
}

// Trigger Replan Scenario
async function triggerReplanScenario(scenario) {
  const proposal = await fetch("/api/advisor/replan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario })
  }).then(r => r.json());

  currentPlanId = proposal.plan_id;
  document.getElementById("prop-title").innerText = "Proposed Plan for: " + proposal.trigger_text;
  
  const sumDiv = document.getElementById("prop-summary");
  sumDiv.innerHTML = (proposal.summary || []).map(s => `• ${s}`).join("<br>");
  
  document.getElementById("replan-proposal-box").classList.remove("hidden");
}

async function handleApprovePlan() {
  if (!currentPlanId) return;
  await fetch("/api/advisor/replan/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: currentPlanId })
  });
  alert("🎉 Plan Approved and Applied!");
  document.getElementById("replan-proposal-box").classList.add("hidden");
  loadDashboardData();
}

async function handleUndoPlan() {
  if (!currentPlanId) return;
  await fetch("/api/advisor/replan/undo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: currentPlanId })
  });
  alert("Plan Undo / Rejected.");
  document.getElementById("replan-proposal-box").classList.add("hidden");
  loadDashboardData();
}

// Handle Symptom Triage Submit
async function handleTriageSubmit(e) {
  e.preventDefault();
  const patient_name = document.getElementById("triage-patient").value;
  const symptoms = document.getElementById("triage-symptoms").value;

  const res = await fetch("/api/doctor/triage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symptoms, patient_name })
  }).then(r => r.json());

  const box = document.getElementById("triage-result-box");
  box.classList.remove("hidden");

  if (res.is_emergency) {
    box.className = "border border-red-300 bg-red-50 rounded-xl p-4 text-xs space-y-2 text-red-900";
    box.innerHTML = `
      <h4 class="font-bold text-sm text-red-700">🚨 EMERGENCY MEDICAL WARNING</h4>
      <p>${res.recommendation}</p>
      <div class="font-bold">CALL EMERGENCY NOW: 108</div>
    `;
  } else {
    box.className = "border border-amber-300 bg-amber-50 rounded-xl p-4 text-xs space-y-2 text-amber-900";
    box.innerHTML = `
      <h4 class="font-bold text-sm">${res.headline}</h4>
      <p>${res.recommendation}</p>
      <button onclick="bookDoctorNow()" class="bg-rose-600 text-white font-bold px-3 py-1.5 rounded-lg text-xs">📅 Book Dr. Sharma Today (17:30 - 18:00)</button>
    `;
  }
}

async function bookDoctorNow() {
  await fetch("/api/doctor/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_time: "17:30" })
  });
  alert("🎉 Appointment requested with Dr. Sharma for today 17:30! Schedule reshuffled and ₹500 fee reserved.");
  loadDashboardData();
}

// Load Review Data
async function loadReviewData() {
  const sumRes = await fetch("/api/dashboard/summary").then(r => r.json());
  const rep = sumRes.report || {};
  document.getElementById("review-content").innerHTML = `
    <div class="p-4 bg-slate-50 border rounded-xl space-y-2">
      <div class="font-bold text-slate-900">🌟 Sunday Retrospective Summary</div>
      <div>• <b>Spending</b>: ${fmtINR(rep.total_spent)} spent out of ${fmtINR(rep.total_planned)} planned. Unallocated buffer: ${fmtINR(rep.unallocated)}.</div>
      <div>• <b>Health & Child Care</b>: Child vaccines & checkup milestone flagged and tracked.</div>
      <div>• <b>Next Week's Focus</b>: Cap non-essential spending to ₹150/day and maintain evening rest before 20:00.</div>
    </div>
  `;
}

// Load Profile Data
async function loadProfileData() {
  const res = await fetch("/api/dashboard/profile").then(r => r.json());
  const prof = res.profile || {};
  document.getElementById("prof-name").value = prof.name || "Priya";
  document.getElementById("prof-income").value = prof.monthly_income || 32000;
  document.getElementById("prof-city").value = prof.city || "Gurgaon";
  document.getElementById("prof-contact-name").value = prof.trusted_contact_name || "Sunita (neighbour)";
  document.getElementById("prof-contact-phone").value = prof.trusted_contact_phone || "9876543210";
}

async function handleProfileSubmit(e) {
  e.preventDefault();
  const name = document.getElementById("prof-name").value;
  const monthly_income = parseFloat(document.getElementById("prof-income").value);
  const city = document.getElementById("prof-city").value;
  const trusted_contact_name = document.getElementById("prof-contact-name").value;
  const trusted_contact_phone = document.getElementById("prof-contact-phone").value;

  await fetch("/api/dashboard/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, monthly_income, city, trusted_contact_name, trusted_contact_phone })
  });

  alert("✅ Profile memory saved!");
  loadDashboardData();
}
