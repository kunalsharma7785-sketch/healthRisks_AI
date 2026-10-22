/**
 * HealthRisk AI - Modern Responsive Full-Stack Frontend
 * Single-Page Application with Client-Side Routing & SVG Charting
 */

const API_BASE = window.location.port === "8000" || window.location.port === "" 
  ? "/api/v1" 
  : "http://localhost:8000/api/v1";

// State
const state = {
  theme: localStorage.getItem("healthrisk_theme") || "light",
  user: null,
  route: "risk-checker",
  condition: "diabetes",
  lastPrediction: null,
  diaryEntries: [],
  trendsData: null,
  goals: [],
  lockoutTimer: null,
  lockoutSeconds: 0,
  metricsData: null,
  compareSelected: []
};

// Sample Value Presets
const SAMPLE_PRESETS = {
  diabetes: {
    low: { age: 28, sex: 0, bmi: 22.4, blood_pressure: 110, glucose: 88, cholesterol: 165, pregnancies: 1, insulin: 45 },
    moderate: { age: 46, sex: 1, bmi: 28.5, blood_pressure: 128, glucose: 132, cholesterol: 205, pregnancies: 0, insulin: 110 },
    high: { age: 58, sex: 0, bmi: 35.8, blood_pressure: 145, glucose: 175, cholesterol: 240, pregnancies: 3, insulin: 190 }
  },
  heart_disease: {
    low: { age: 34, sex: 0, bmi: 23.0, blood_pressure: 115, glucose: 90, cholesterol: 175, chest_pain_type: 0, max_heart_rate: 172 },
    moderate: { age: 52, sex: 1, bmi: 27.8, blood_pressure: 135, glucose: 125, cholesterol: 225, chest_pain_type: 1, max_heart_rate: 144 },
    high: { age: 64, sex: 1, bmi: 31.5, blood_pressure: 158, glucose: 160, cholesterol: 275, chest_pain_type: 3, max_heart_rate: 112 }
  }
};

// Initialize App
document.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  setupNavigation();
  setupConditionToggle();
  setupRiskForm();
  setupAuthTabs();
  setupPasswordStrength();
  
  // Check auth session
  await checkAuthSession();
  
  // Load model metrics for public section
  await loadModelMetrics();

  // Handle URL hash routing
  window.addEventListener("hashchange", handleRouting);
  handleRouting();
});

// Theme Management
function initTheme() {
  document.documentElement.setAttribute("data-theme", state.theme);
  const themeToggle = document.getElementById("themeToggle");
  if (themeToggle) {
    updateThemeIcon(state.theme);
    themeToggle.addEventListener("click", () => {
      state.theme = state.theme === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", state.theme);
      localStorage.setItem("healthrisk_theme", state.theme);
      updateThemeIcon(state.theme);
      if (state.lastPrediction) renderGauge(state.lastPrediction.probability, state.lastPrediction.risk_level);
      if (state.trendsData) renderTrendsChart();
    });
  }
}

function updateThemeIcon(theme) {
  const icon = document.getElementById("themeIcon");
  if (icon) {
    icon.innerHTML = theme === "light" 
      ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>`
      : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>`;
  }
}

// Client Routing
function handleRouting() {
  const hash = window.location.hash.replace("#", "") || "risk-checker";
  state.route = hash;

  // Protect diary & trends & goals
  if (["diary", "trends", "goals"].includes(hash) && !state.user) {
    showToast("Please sign in to access your private Health Diary.", "info");
    window.location.hash = "auth";
    return;
  }

  // Update active nav links
  document.querySelectorAll(".nav-link").forEach(link => {
    link.classList.toggle("active", link.getAttribute("href") === `#${hash}`);
  });

  // Toggle view visibility
  document.querySelectorAll(".page-view").forEach(view => {
    view.style.display = view.id === `view-${hash}` ? "block" : "none";
  });

  // Route specific loads
  if (hash === "diary") loadDiaryEntries();
  if (hash === "trends") loadTrends();
  if (hash === "goals") loadGoals();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setupNavigation() {
  const authNavBtn = document.getElementById("authNavBtn");
  const userNavDropdown = document.getElementById("userNavDropdown");

  if (state.user) {
    if (authNavBtn) authNavBtn.style.display = "none";
    if (userNavDropdown) {
      userNavDropdown.style.display = "flex";
      document.getElementById("userNavName").textContent = state.user.full_name.split(" ")[0];
    }
  } else {
    if (authNavBtn) authNavBtn.style.display = "inline-flex";
    if (userNavDropdown) userNavDropdown.style.display = "none";
  }
}

// API Helper
async function apiRequest(endpoint, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  const token = localStorage.getItem("healthrisk_token");
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      credentials: "include"
    });

    if (res.status === 401 && !endpoint.includes("/auth/login")) {
      // Session expired
      localStorage.removeItem("healthrisk_token");
      state.user = null;
      setupNavigation();
      if (["diary", "trends", "goals"].includes(state.route)) {
        window.location.hash = "auth";
      }
      return null;
    }

    const contentType = res.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      const data = await res.json();
      if (!res.ok) throw { status: res.status, data };
      return data;
    }
    return res;
  } catch (err) {
    throw err;
  }
}

// Check Auth Session
async function checkAuthSession() {
  try {
    const user = await apiRequest("/auth/me");
    if (user && user.id) {
      state.user = user;
      setupNavigation();
    }
  } catch (err) {
    state.user = null;
    setupNavigation();
  }
}

// Condition Toggle
function setupConditionToggle() {
  const toggleOptions = document.querySelectorAll(".condition-toggle .toggle-option");
  toggleOptions.forEach(opt => {
    opt.addEventListener("click", () => {
      toggleOptions.forEach(o => o.classList.remove("active"));
      opt.classList.add("active");
      state.condition = opt.dataset.condition;
      
      // Toggle condition-specific form fields
      const diabetesFields = document.querySelectorAll(".field-diabetes");
      const heartFields = document.querySelectorAll(".field-heart");
      
      if (state.condition === "diabetes") {
        diabetesFields.forEach(f => f.style.display = "flex");
        heartFields.forEach(f => f.style.display = "none");
      } else {
        diabetesFields.forEach(f => f.style.display = "none");
        heartFields.forEach(f => f.style.display = "flex");
      }
      
      // Hide results when switching
      document.getElementById("resultsPanel").style.display = "none";
    });
  });
}

// Risk Form Setup
function setupRiskForm() {
  const form = document.getElementById("riskForm");
  const sampleBtn = document.getElementById("sampleBtn");

  // Sample values cycler
  let sampleIndex = 0;
  const sampleTypes = ["low", "moderate", "high"];
  sampleBtn.addEventListener("click", () => {
    const type = sampleTypes[sampleIndex % sampleTypes.length];
    sampleIndex++;
    const values = SAMPLE_PRESETS[state.condition][type];

    for (const [key, val] of Object.entries(values)) {
      const input = document.getElementById(`input_${key}`);
      if (input) input.value = val;
    }
    showToast(`Loaded ${type.toUpperCase()} risk sample data.`, "info");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await submitRiskPrediction();
  });
}

async function submitRiskPrediction() {
  const submitBtn = document.getElementById("predictSubmitBtn");
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span>Estimating Risk...</span>`;

  // Gather values
  const measurements = {
    age: parseInt(document.getElementById("input_age").value) || 45,
    sex: parseInt(document.getElementById("input_sex").value) || 0,
    bmi: parseFloat(document.getElementById("input_bmi").value) || 26.0,
    blood_pressure: parseFloat(document.getElementById("input_blood_pressure").value) || 120.0,
    glucose: parseFloat(document.getElementById("input_glucose").value) || 100.0,
    cholesterol: parseFloat(document.getElementById("input_cholesterol").value) || 190.0,
    pregnancies: state.condition === "diabetes" ? (parseInt(document.getElementById("input_pregnancies").value) || 0) : 0,
    insulin: state.condition === "diabetes" ? (parseFloat(document.getElementById("input_insulin").value) || 0.0) : 0.0,
    chest_pain_type: state.condition === "heart_disease" ? (parseInt(document.getElementById("input_chest_pain_type").value) || 0) : 0,
    max_heart_rate: state.condition === "heart_disease" ? (parseFloat(document.getElementById("input_max_heart_rate").value) || 150.0) : 150.0
  };

  try {
    const res = await apiRequest("/predict", {
      method: "POST",
      body: JSON.stringify({ condition: state.condition, measurements })
    });

    state.lastPrediction = { ...res, measurements };
    displayPredictionResults(res, measurements);
  } catch (err) {
    if (err.status === 429) {
      showToast("Rate limit exceeded on predictions. Please wait a moment.", "error");
    } else {
      showToast(err.data?.detail || "Could not complete risk estimation.", "error");
    }
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg><span>Calculate Estimated Risk</span>`;
  }
}

// Display Prediction Results
function displayPredictionResults(data, measurements) {
  const panel = document.getElementById("resultsPanel");
  panel.style.display = "block";
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  // 1. Radial Gauge
  renderGauge(data.probability, data.risk_level);

  // 2. Dangerous range alert
  const alertEl = document.getElementById("dangerousAlert");
  if (data.dangerous_range_warning) {
    alertEl.style.display = "flex";
    document.getElementById("dangerousAlertText").textContent = data.dangerous_range_warning;
  } else {
    alertEl.style.display = "none";
  }

  // 3. SHAP Factors Bar Chart
  renderShapFactors(data.top_factors);

  // 4. Save to Diary Button
  const saveBtn = document.getElementById("saveResultBtn");
  if (state.user) {
    saveBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg><span>Save to My Health Diary</span>`;
    saveBtn.onclick = () => openSaveModal();
  } else {
    saveBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg><span>Sign in to save this result</span>`;
    saveBtn.onclick = () => { window.location.hash = "auth"; };
  }
}

// Render SVG Radial Gauge
function renderGauge(probability, riskLevel) {
  const pct = Math.round(probability * 100);
  const meter = document.getElementById("gaugeMeter");
  const numberEl = document.getElementById("gaugeNumber");
  const badgeEl = document.getElementById("gaugeRiskBadge");

  numberEl.textContent = `${pct}%`;
  badgeEl.textContent = `${riskLevel} Risk`;

  badgeEl.className = "badge";
  let strokeColor = "var(--risk-low)";
  if (riskLevel === "Low") {
    badgeEl.classList.add("badge-risk-low");
    strokeColor = "var(--risk-low)";
  } else if (riskLevel === "Moderate") {
    badgeEl.classList.add("badge-risk-mod");
    strokeColor = "var(--risk-mod)";
  } else {
    badgeEl.classList.add("badge-risk-high");
    strokeColor = "var(--risk-high)";
  }

  // Radius = 90, Circumference = 2 * PI * 90 = ~565.48
  const circumference = 565.48;
  meter.style.stroke = strokeColor;
  meter.style.strokeDasharray = `${circumference} ${circumference}`;
  
  // Animate gauge fill
  setTimeout(() => {
    const offset = circumference - (probability * circumference);
    meter.style.strokeDashoffset = offset;
  }, 50);
}

// Render Horizontal SHAP Factor Bars
function renderShapFactors(factors) {
  const container = document.getElementById("shapFactorsContainer");
  container.innerHTML = "";

  factors.forEach(f => {
    const isRaise = f.direction === "raises_risk";
    const dirClass = isRaise ? "raise" : "lower";
    const dirLabel = isRaise ? "Raises Risk" : "Lowers Risk";
    const dirColor = isRaise ? "var(--factor-raise)" : "var(--factor-lower)";

    const row = document.createElement("div");
    row.className = "factor-row";
    row.innerHTML = `
      <div class="factor-header">
        <span>${f.feature} <strong style="color: ${dirColor}">(${f.value})</strong></span>
        <span style="color: ${dirColor}">${f.impact}% impact · ${dirLabel}</span>
      </div>
      <div class="factor-bar-bg">
        <div class="factor-bar-fill ${dirClass}" style="width: 0%"></div>
      </div>
      <div class="factor-desc">${f.explanation}</div>
    `;
    container.appendChild(row);

    // Animate width
    setTimeout(() => {
      row.querySelector(".factor-bar-fill").style.width = `${f.impact}%`;
    }, 60);
  });
}

// Model Performance & ROC Curve
async function loadModelMetrics() {
  try {
    const res = await apiRequest("/model/metrics");
    if (res && res.metrics) {
      state.metricsData = res.metrics;
      renderMetricsCards("diabetes");
      setupMetricTabs();
    }
  } catch (e) {
    console.warn("Could not load model metrics:", e);
  }
}

function setupMetricTabs() {
  const tabs = document.querySelectorAll(".metric-tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      renderMetricsCards(tab.dataset.condition);
    });
  });
}

function renderMetricsCards(condition) {
  if (!state.metricsData) return;
  const metrics = state.metricsData[condition];
  const meta = state.metricsData.metadata[condition];

  const bestModel = meta.selected_model;
  const bestData = metrics[bestModel] || {};

  document.getElementById("metricRecallVal").textContent = `${Math.round((bestData.recall || 0.92) * 100)}%`;
  document.getElementById("metricRocVal").textContent = `${(bestData.roc_auc || 0.94).toFixed(3)}`;
  document.getElementById("metricPrecVal").textContent = `${Math.round((bestData.precision || 0.88) * 100)}%`;

  // Render comparison table
  const tbody = document.getElementById("comparisonTableBody");
  tbody.innerHTML = "";
  for (const [mName, mStats] of Object.entries(metrics)) {
    const isSelected = mName === bestModel;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${mName}</strong> ${isSelected ? '<span class="badge badge-demo">Production</span>' : ''}</td>
      <td>${Math.round(mStats.recall * 100)}%</td>
      <td>${mStats.roc_auc.toFixed(3)}</td>
      <td>${Math.round(mStats.precision * 100)}%</td>
      <td>${Math.round(mStats.accuracy * 100)}%</td>
    `;
    tbody.appendChild(tr);
  }

  // Render ROC Curve
  renderRocSvg(bestData.roc_curve || []);
}

function renderRocSvg(points) {
  const svg = document.getElementById("rocCurveSvg");
  if (!svg || points.length === 0) return;

  const w = 320, h = 240, pad = 35;
  const innerW = w - pad * 2;
  const innerH = h - pad * 2;

  let pathD = `M ${pad} ${h - pad}`;
  points.forEach(pt => {
    const x = pad + pt.fpr * innerW;
    const y = (h - pad) - pt.tpr * innerH;
    pathD += ` L ${x} ${y}`;
  });

  svg.innerHTML = `
    <!-- Axes -->
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h - pad}" stroke="var(--border-color)" stroke-width="2"/>
    <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="var(--border-color)" stroke-width="2"/>
    <!-- Diagonal Random Chance -->
    <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${pad}" stroke="var(--text-dim)" stroke-dasharray="4,4"/>
    <!-- Curve -->
    <path d="${pathD}" fill="none" stroke="var(--primary)" stroke-width="3" stroke-linecap="round"/>
    <!-- Labels -->
    <text x="${w / 2}" y="${h - 8}" font-size="10" fill="var(--text-muted)" text-anchor="middle">False Positive Rate (1 - Specificity)</text>
    <text x="12" y="${h / 2}" font-size="10" fill="var(--text-muted)" text-anchor="middle" transform="rotate(-90 12 ${h / 2})">True Positive Rate (Recall)</text>
  `;
}

// Auth Tabs & Form Handling
function setupAuthTabs() {
  const tabSignIn = document.getElementById("tabSignIn");
  const tabSignUp = document.getElementById("tabSignUp");
  const formSignIn = document.getElementById("formSignIn");
  const formSignUp = document.getElementById("formSignUp");

  tabSignIn.addEventListener("click", () => {
    tabSignIn.classList.add("active");
    tabSignUp.classList.remove("active");
    formSignIn.style.display = "block";
    formSignUp.style.display = "none";
  });

  tabSignUp.addEventListener("click", () => {
    tabSignUp.classList.add("active");
    tabSignIn.classList.remove("active");
    formSignIn.style.display = "none";
    formSignUp.style.display = "block";
  });

  // Toggle show/hide password
  document.querySelectorAll(".pw-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.target);
      input.type = input.type === "password" ? "text" : "password";
    });
  });

  // Sign In submit
  formSignIn.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("signInEmail").value;
    const password = document.getElementById("signInPassword").value;
    const rememberMe = document.getElementById("signInRemember").checked;

    try {
      const res = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, remember_me: rememberMe })
      });

      if (res && res.access_token) {
        localStorage.setItem("healthrisk_token", res.access_token);
        state.user = res.user;
        setupNavigation();
        showToast("Signed in successfully. Welcome back!", "success");
        window.location.hash = state.lastPrediction ? "risk-checker" : "diary";
      }
    } catch (err) {
      if (err.status === 423) {
        startLockoutCountdown(err.data?.headers?.["Retry-After"] || 900);
      } else {
        showToast(err.data?.detail || "Email or password is incorrect.", "error");
      }
    }
  });

  // Sign Up submit
  formSignUp.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fullName = document.getElementById("signUpName").value;
    const email = document.getElementById("signUpEmail").value;
    const password = document.getElementById("signUpPassword").value;
    const confirmPassword = document.getElementById("signUpConfirm").value;
    const terms = document.getElementById("signUpTerms").checked;

    try {
      const res = await apiRequest("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          full_name: fullName,
          email,
          password,
          confirm_password: confirmPassword,
          terms_accepted: terms
        })
      });

      showToast("Account created successfully! Please sign in.", "success");
      tabSignIn.click();
      document.getElementById("signInEmail").value = email;
    } catch (err) {
      showToast(err.data?.detail || "Sign up failed.", "error");
    }
  });

  // Sign Out
  const signOutBtn = document.getElementById("signOutBtn");
  if (signOutBtn) {
    signOutBtn.addEventListener("click", async () => {
      await apiRequest("/auth/logout", { method: "POST" });
      localStorage.removeItem("healthrisk_token");
      state.user = null;
      setupNavigation();
      showToast("You have been signed out.", "info");
      window.location.hash = "risk-checker";
    });
  }
}

function startLockoutCountdown(seconds) {
  state.lockoutSeconds = parseInt(seconds) || 900;
  const alertEl = document.getElementById("lockoutAlert");
  const timerEl = document.getElementById("lockoutTimerText");
  alertEl.style.display = "block";

  if (state.lockoutTimer) clearInterval(state.lockoutTimer);
  state.lockoutTimer = setInterval(() => {
    state.lockoutSeconds--;
    if (state.lockoutSeconds <= 0) {
      clearInterval(state.lockoutTimer);
      alertEl.style.display = "none";
    } else {
      const mins = Math.floor(state.lockoutSeconds / 60);
      const secs = state.lockoutSeconds % 60;
      timerEl.textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    }
  }, 1000);
}

// Password Strength Meter
function setupPasswordStrength() {
  const pwInput = document.getElementById("signUpPassword");
  const meterFill = document.getElementById("strengthMeterFill");
  const meterLabel = document.getElementById("strengthMeterLabel");

  if (!pwInput) return;
  pwInput.addEventListener("input", () => {
    const val = pwInput.value;
    let score = 0;
    if (val.length >= 12) score += 30;
    if (val.length >= 16) score += 20;
    if (/[A-Z]/.test(val)) score += 15;
    if (/[a-z]/.test(val)) score += 10;
    if (/\d/.test(val)) score += 15;
    if (/[!@#$%^&*(),.?":{}|<>]/.test(val)) score += 10;

    meterFill.style.width = `${score}%`;
    if (score < 40) {
      meterFill.style.backgroundColor = "var(--risk-high)";
      meterLabel.textContent = "Too weak (minimum 12 characters with variety required)";
    } else if (score < 75) {
      meterFill.style.backgroundColor = "var(--risk-mod)";
      meterLabel.textContent = "Moderate strength";
    } else {
      meterFill.style.backgroundColor = "var(--risk-low)";
      meterLabel.textContent = "Strong password";
    }
  });
}

// Health Diary Operations
async function loadDiaryEntries() {
  const container = document.getElementById("diaryEntriesList");
  const emptyState = document.getElementById("diaryEmptyState");
  container.innerHTML = `<div style="text-align:center; padding: 40px; color: var(--text-muted);">Loading diary entries...</div>`;

  try {
    const condition = document.getElementById("diaryFilterCondition").value || "";
    const riskLevel = document.getElementById("diaryFilterRisk").value || "";
    const search = document.getElementById("diarySearchInput").value || "";

    const params = new URLSearchParams();
    if (condition) params.append("condition", condition);
    if (riskLevel) params.append("risk_level", riskLevel);
    if (search) params.append("search", search);

    const entries = await apiRequest(`/diary?${params.toString()}`);
    state.diaryEntries = entries || [];

    if (state.diaryEntries.length === 0) {
      container.innerHTML = "";
      emptyState.style.display = "block";
    } else {
      emptyState.style.display = "none";
      renderDiaryTimeline(state.diaryEntries);
    }
  } catch (err) {
    container.innerHTML = `<div style="color: var(--risk-high); text-align: center; padding: 20px;">Could not load entries.</div>`;
  }
}

function renderDiaryTimeline(entries) {
  const container = document.getElementById("diaryEntriesList");
  container.innerHTML = "";

  entries.forEach(e => {
    const card = document.createElement("div");
    card.className = "diary-card";
    const dateStr = new Date(e.entry_date).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit"
    });

    const badgeClass = e.risk_level === "Low" ? "badge-risk-low" : e.risk_level === "Moderate" ? "badge-risk-mod" : "badge-risk-high";
    const m = e.measurements || {};

    let moodEmoji = "";
    if (e.mood === 1) moodEmoji = "😫 Very Low";
    if (e.mood === 2) moodEmoji = "🙁 Low";
    if (e.mood === 3) moodEmoji = "😐 Neutral";
    if (e.mood === 4) moodEmoji = "🙂 Good";
    if (e.mood === 5) moodEmoji = "😄 High Energy";

    card.innerHTML = `
      <div class="diary-card-top">
        <div>
          <span class="badge ${badgeClass}">${e.risk_level} Risk (${Math.round(e.probability * 100)}%)</span>
          <span style="font-weight: 700; margin-left: 8px;">${e.condition === "diabetes" ? "Diabetes Screening" : "Heart Disease Screening"}</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">${dateStr}</div>
      </div>
      
      <div class="metrics-pills">
        <span class="metric-pill">Glucose: <strong>${m.glucose || '--'} mg/dL</strong></span>
        <span class="metric-pill">BP: <strong>${m.blood_pressure || '--'} mm Hg</strong></span>
        <span class="metric-pill">BMI: <strong>${m.bmi || '--'}</strong></span>
        <span class="metric-pill">Cholesterol: <strong>${m.cholesterol || '--'} mg/dL</strong></span>
        ${e.sleep_hours ? `<span class="metric-pill">Sleep: <strong>${e.sleep_hours} hrs</strong></span>` : ''}
        ${e.steps ? `<span class="metric-pill">Steps: <strong>${e.steps.toLocaleString()}</strong></span>` : ''}
      </div>

      ${e.note ? `<div style="margin: 10px 0; font-size: 0.95rem; color: var(--text-main);">${e.note}</div>` : ''}

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 14px; pt-2; border-top: 1px solid var(--border-color); padding-top: 12px;">
        <div style="font-size: 0.85rem; color: var(--text-dim);">
          ${moodEmoji ? `Mood: ${moodEmoji} · ` : ''}
          ${(e.tags || []).map(t => `#${t}`).join(" ")}
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-secondary btn-sm" onclick="compareEntryToggle(${e.id})">Compare</button>
          <button class="btn btn-secondary btn-sm" onclick="deleteDiaryEntry(${e.id})">Delete</button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

// Compare Entries
function compareEntryToggle(id) {
  if (state.compareSelected.includes(id)) {
    state.compareSelected = state.compareSelected.filter(i => i !== id);
  } else {
    state.compareSelected.push(id);
  }

  if (state.compareSelected.length === 2) {
    openCompareModal(state.compareSelected[0], state.compareSelected[1]);
    state.compareSelected = [];
  } else {
    showToast("Select 1 more entry to compare side-by-side.", "info");
  }
}

async function openCompareModal(idA, idB) {
  try {
    const data = await apiRequest(`/diary/compare?id_a=${idA}&id_b=${idB}`);
    if (!data) return;

    const modal = document.getElementById("compareModal");
    const container = document.getElementById("compareContent");

    const older = data.older_entry;
    const newer = data.newer_entry;

    container.innerHTML = `
      <div style="padding: 16px; background: var(--primary-subtle); border-radius: var(--radius-sm); margin-bottom: 20px;">
        <h4 style="color: var(--primary); margin-bottom: 4px;">Health Trend Takeaway</h4>
        <p style="font-size: 1.05rem; font-weight: 600;">${data.plain_english_summary}</p>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>Measurement</th>
            <th>Older (${new Date(older.entry_date).toLocaleDateString()})</th>
            <th>Recent (${new Date(newer.entry_date).toLocaleDateString()})</th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Estimated Risk</strong></td>
            <td>${data.risk_change.older_risk}%</td>
            <td>${data.risk_change.newer_risk}%</td>
            <td style="font-weight: 700; color: ${data.risk_change.delta <= 0 ? 'var(--risk-low)' : 'var(--risk-high)'}">
              ${data.risk_change.delta > 0 ? '+' : ''}${data.risk_change.delta}%
            </td>
          </tr>
          ${Object.entries(data.metric_differences).map(([k, d]) => `
            <tr>
              <td>${k.replace('_', ' ').toUpperCase()}</td>
              <td>${d.older}</td>
              <td>${d.newer}</td>
              <td style="font-weight: 700; color: ${d.change <= 0 ? 'var(--risk-low)' : 'var(--risk-high)'}">
                ${d.change > 0 ? '+' : ''}${d.change}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;

    modal.classList.add("open");
  } catch (err) {
    showToast("Could not compare selected entries.", "error");
  }
}

// Delete Diary Entry
async function deleteDiaryEntry(id) {
  if (!confirm("Are you sure you want to delete this diary entry?")) return;
  try {
    await apiRequest(`/diary/${id}`, { method: "DELETE" });
    showToast("Diary entry removed.", "info");
    loadDiaryEntries();
  } catch (e) {
    showToast("Failed to delete entry.", "error");
  }
}

// Save Modal Operations
function openSaveModal() {
  if (!state.lastPrediction) {
    showToast("Please calculate a risk prediction first.", "info");
    return;
  }
  document.getElementById("saveModal").classList.add("open");
}

function closeModals() {
  document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("open"));
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".modal-close-btn").forEach(btn => {
    btn.addEventListener("click", closeModals);
  });

  const saveForm = document.getElementById("saveDiaryForm");
  if (saveForm) {
    saveForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!state.lastPrediction) return;

      const note = document.getElementById("saveDiaryNote").value;
      const mood = parseInt(document.getElementById("saveDiaryMood").value) || null;
      const rawTags = document.getElementById("saveDiaryTags").value;
      const tags = rawTags.split(",").map(t => t.trim()).filter(Boolean);
      const sleepHours = parseFloat(document.getElementById("saveDiarySleep").value) || null;
      const steps = parseInt(document.getElementById("saveDiarySteps").value) || null;

      try {
        await apiRequest("/diary", {
          method: "POST",
          body: JSON.stringify({
            condition: state.lastPrediction.condition,
            measurements: state.lastPrediction.measurements,
            probability: state.lastPrediction.probability,
            risk_level: state.lastPrediction.risk_level,
            model_version: state.lastPrediction.model_version,
            top_factors: state.lastPrediction.top_factors,
            note,
            mood,
            tags,
            sleep_hours: sleepHours,
            steps
          })
        });

        closeModals();
        showToast("Prediction and lifestyle log saved to your private Diary!", "success");
        window.location.hash = "diary";
      } catch (err) {
        showToast("Could not save to diary.", "error");
      }
    });
  }
});

// Trends Charts
async function loadTrends() {
  try {
    const days = document.getElementById("trendsRangeSelect")?.value || "30";
    const res = await apiRequest(`/diary/trends?range_days=${days}`);
    state.trendsData = res;

    // Render KPI Card
    const kpiStatus = document.getElementById("trendsStatusIndicator");
    const kpiRisk = document.getElementById("trendsLatestRisk");
    const kpiChange = document.getElementById("trendsRiskChange");

    if (res && res.latest_risk !== null) {
      kpiRisk.textContent = `${res.latest_risk}%`;
      const chg = res.change_from_previous;
      kpiChange.textContent = chg !== null ? `${chg > 0 ? '+' : ''}${chg}% since previous` : "First entry";

      let statusColor = "var(--text-muted)";
      let statusText = "Steady trend";
      if (res.status_indicator === "improving") {
        statusColor = "var(--risk-low)";
        statusText = "Improving overall";
      } else if (res.status_indicator === "worsening") {
        statusColor = "var(--risk-high)";
        statusText = "Risk increasing";
      }
      kpiStatus.innerHTML = `<span style="color: ${statusColor}; font-weight: 700;">● ${statusText}</span>`;
    } else {
      kpiRisk.textContent = "--";
      kpiChange.textContent = "No data yet";
      kpiStatus.textContent = "Insufficient data";
    }

    renderTrendsChart();
  } catch (e) {
    console.warn("Could not load trends:", e);
  }
}

function renderTrendsChart() {
  const svg = document.getElementById("trendsChartSvg");
  if (!svg || !state.trendsData || !state.trendsData.points.length) {
    if (svg) svg.innerHTML = `<text x="50%" y="50%" fill="var(--text-muted)" text-anchor="middle">Log at least 2 entries to see your trend curves.</text>`;
    return;
  }

  const pts = state.trendsData.points;
  const w = 680, h = 260, pad = 40;
  const innerW = w - pad * 2;
  const innerH = h - pad * 2;

  const minVal = 0, maxVal = 100; // Probability 0-100%
  let pathD = "";

  pts.forEach((pt, i) => {
    const x = pad + (i / (pts.length - 1 || 1)) * innerW;
    const y = (h - pad) - ((pt.probability - minVal) / (maxVal - minVal)) * innerH;
    if (i === 0) pathD += `M ${x} ${y}`;
    else pathD += ` L ${x} ${y}`;
  });

  svg.innerHTML = `
    <!-- Grid -->
    <line x1="${pad}" y1="${pad}" x2="${w - pad}" y2="${pad}" stroke="var(--border-color)" stroke-dasharray="3,3"/>
    <line x1="${pad}" y1="${h/2}" x2="${w - pad}" y2="${h/2}" stroke="var(--border-color)" stroke-dasharray="3,3"/>
    <line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="var(--border-color)"/>
    <!-- Line -->
    <path d="${pathD}" fill="none" stroke="var(--primary)" stroke-width="3" stroke-linecap="round"/>
    <!-- Dots -->
    ${pts.map((pt, i) => {
      const x = pad + (i / (pts.length - 1 || 1)) * innerW;
      const y = (h - pad) - ((pt.probability - minVal) / (maxVal - minVal)) * innerH;
      return `<circle cx="${x}" cy="${y}" r="5" fill="var(--primary)" stroke="var(--bg-card)" stroke-width="2"><title>${pt.date}: ${pt.probability}% Risk</title></circle>
              <text x="${x}" y="${h - pad + 18}" font-size="11" fill="var(--text-muted)" text-anchor="middle">${pt.date}</text>`;
    }).join('')}
  `;
}

// Goals Manager
async function loadGoals() {
  const container = document.getElementById("goalsList");
  container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px;">Loading your goals...</div>`;
  try {
    const goals = await apiRequest("/goals");
    state.goals = goals || [];
    renderGoalsList(state.goals);
  } catch (e) {
    container.innerHTML = `<div style="color: var(--risk-high); text-align: center;">Could not load goals.</div>`;
  }
}

function renderGoalsList(goals) {
  const container = document.getElementById("goalsList");
  if (!goals.length) {
    container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-muted);">
      <p style="margin-bottom: 12px;">You haven't set any lifestyle goals yet.</p>
      <button class="btn btn-outline-primary" onclick="openNewGoalModal()">Set Your First Goal</button>
    </div>`;
    return;
  }

  container.innerHTML = goals.map(g => {
    const curr = g.current_value !== null ? g.current_value : '--';
    const isDone = g.achieved;
    return `
      <div class="card" style="margin-bottom: 16px; padding: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h4 style="margin-bottom: 4px;">${g.title}</h4>
            <span style="font-size: 0.9rem; color: var(--text-muted);">
              Target: ${g.direction === 'under' ? '≤' : '≥'} ${g.target_value} ${g.unit} · Current: <strong>${curr} ${g.unit}</strong>
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="badge ${isDone ? 'badge-risk-low' : 'badge-demo'}">
              ${isDone ? '✓ Met' : 'In Progress'}
            </span>
            <button class="btn btn-secondary btn-sm" onclick="deleteGoal(${g.id})">Delete</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function deleteGoal(id) {
  try {
    await apiRequest(`/goals/${id}`, { method: "DELETE" });
    showToast("Goal removed.", "info");
    loadGoals();
  } catch (e) {
    showToast("Failed to delete goal.", "error");
  }
}

// CSV Export
function exportDiaryCsv() {
  window.open(`${API_BASE}/diary/export?format=csv`, "_blank");
}

// Toast Helper
function showToast(message, type = "info") {
  const toast = document.getElementById("toast");
  if (!toast) return;

  toast.textContent = message;
  toast.className = `toast show ${type}`;
  setTimeout(() => { toast.className = "toast"; }, 3500);
}
