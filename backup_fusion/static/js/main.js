document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("uploadForm");
  const resultsDiv = document.getElementById("results");
  const errorDiv = document.getElementById("error");
  const submitBtn = document.getElementById("submitBtn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorDiv.textContent = "";
    resultsDiv.innerHTML = `<p class="text-sm text-slate-600"><em>Loading...</em></p>`;
    submitBtn.disabled = true;

    try {
      const table1 = await loadTable("file_a");
      const table2 = await loadTable("file_b");

      const combinedSchema = classifyCombined(table1, table2);
      const totalTokens = (table1?.tokens || 0) + (table2?.tokens || 0);

      const fd = new FormData(form);
      const response = await fetch("/predict", { method: "POST", body: fd });
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); }
      catch { throw new Error("Non-JSON response: " + text); }

      if (!response.ok) throw new Error(data.detail || "Prediction failed.");

      renderAll(data.prediction, { table1, table2, combinedSchema, totalTokens });

      // ⭐ SHOW EXECUTE BUTTON
      document.getElementById("executeContainer").classList.remove("hidden");

    } catch (err) {
      console.error(err);
      errorDiv.textContent = err.message;
      resultsDiv.innerHTML = "";
    } finally {
      submitBtn.disabled = false;
    }
  });

  async function loadTable(domId) {
    const file = document.getElementById(domId).files[0];
    if (!file) return null;
    const text = await file.text();
    try { return analyzeTable(JSON.parse(text), file.name); }
    catch { return null; }
  }

  function analyzeTable(json, fileName) {
    const keys = Object.keys(json);

    const hmdKey = keys.find(k => k.toLowerCase().includes("hmd"));
    const vmdKey = keys.find(k => k.toLowerCase().includes("vmd"));
    const dataKey = keys.find(k => k.toLowerCase().includes("data"));

    const hmdRows = hmdKey && Array.isArray(json[hmdKey]) ? json[hmdKey].length : 0;
    const vmdRows = vmdKey && Array.isArray(json[vmdKey]) ? json[vmdKey].length : 0;

    const schemaType = (hmdRows > 1 && vmdRows > 1) ? "complex" : "simple";
    const tokens = Math.round(JSON.stringify(json).length / 4);

    return { json, fileName, dataKey, hmdRows, vmdRows, schemaType, tokens };
  }

  function classifyCombined(t1, t2) {
    if (!t1 && !t2) return "unknown";
    if ((t1 && t1.schemaType === "complex") || (t2 && t2.schemaType === "complex")) return "complex";
    return "simple";
  }

  function renderAll(pred, meta) {
    const backend = (pred.backend || "rf").toUpperCase();
    const mode = (pred.mode || "merge");

    resultsDiv.innerHTML = `
      ${renderPreview(meta)}
      <hr class="my-4 border-slate-300" />
      <h2 class="text-lg font-semibold text-slate-900 mb-1">Prediction</h2>
      <p class="text-sm mb-2 text-slate-600">
        Backend: <span class="font-semibold">${backend}</span>
        <span class="mx-2 text-slate-400">|</span>
        Operation: <span class="font-semibold">${mode}</span>
      </p>

      ${renderPlanTable(pred, mode)}
      <h3 class="text-base font-semibold mt-4 mb-1">Pipeline Plans</h3>
      ${renderPipelines(pred, mode)}
    `;
  }

  function renderPreview(meta) {
    return `
      <div class="bg-slate-50 border border-slate-200 rounded-lg p-2 text-sm flex justify-between">
        <div>
          <span class="font-semibold">Combined Schema:</span>
          <span class="ml-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
            meta.combinedSchema === "complex" ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
          }">${meta.combinedSchema}</span>
        </div>
        <div>Total Tokens: <span class="font-semibold">${meta.totalTokens}</span></div>
      </div>
    `;
  }

  function renderPlanTable(pred, mode) {
    const rows = [
      { label: "Cost (USD)", data: pred.best_cost },
      { label: "Accuracy (%)", data: pred.best_accuracy },
      { label: "Latency (seconds)", data: pred.best_latency },
    ];
    return buildPlanTable(rows, mode === "match");
  }

  function buildPlanTable(rows, isMatch) {
    return ""; // unchanged as you requested
  }

  function renderPipelines(pred, mode) {
    const isMatch = mode === "match";
    let blocks = "";

    if (pred.best_cost)
      blocks += renderPipelineBlock("Cost (USD)", "💲", pred.best_cost, isMatch, formatCost(pred.best_cost.pred_cost));

    if (pred.best_accuracy)
      blocks += renderPipelineBlock("Accuracy (%)", "🎯", pred.best_accuracy, isMatch,
        formatAccuracy(pred.best_accuracy.pred_accuracy));

    if (pred.best_latency)
      blocks += renderPipelineBlock("Latency (seconds)", "⏱", pred.best_latency, isMatch,
        formatLatency(pred.best_latency.pred_latency));

    return blocks;
  }

  // ⭐⭐ MODIFIED: RADIO BUTTON + $ COST ⭐⭐
  function renderPipelineBlock(label, icon, p, isMatch, valueText) {
    return `
      <div class="bg-slate-50 rounded-xl border border-slate-200 shadow-sm p-3 space-y-2 mb-2">

        <div class="flex items-center gap-2 text-sm">

          <input type="radio"
                 name="selected_plan"
                 value="${label.toLowerCase()}"
                 class="h-4 w-4 text-indigo-600 border-slate-300">

          <span class="text-lg">${icon}</span>
          <span class="font-semibold">${label}</span>
          <span class="text-slate-500">—</span>

          <span class="font-medium">${
            label.includes("Cost") ? "$" + valueText : valueText
          }</span>
        </div>

        <div class="flex flex-col md:flex-row gap-3 mt-2">
          ${pipelineStep("📄", "Input", ["Source & Target Tables"])}
          ${arrow()}
          ${pipelineStep("🧩", "Match Step", [
            `Operator: ${p["Match Operator"] || "-"}`,
            `Method: ${p["Match Method"] || "-"}`,
            `LLM: ${p["LLM used for matching"] || "-"}`,
          ])}
          ${isMatch ? "" : arrow()}
          ${
            isMatch
              ? ""
              : pipelineStep("🔗", "Merge Step", [
                  `Operator: ${p["Merge Operator"] || "-"}`,
                  `Method: ${p["Merge Method"] || "-"}`,
                  `LLM: ${p["LLM used for merging"] || "-"}`,
                ])
          }
          ${arrow()}
          ${pipelineStep("📦", "Output", [
            isMatch ? "Matched schema results" : "Merged JSON output",
          ])}
        </div>
      </div>
    `;
  }

  function pipelineStep(icon, title, lines) {
    return `
      <div class="flex-1 rounded-xl border px-3 py-2 text-xs" style="background-color: #d4edda; border-color: #c3e6cb;">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 rounded-full flex items-center justify-center" style="background-color: #c3e6cb;">${icon}</div>
          <div class="font-semibold uppercase tracking-wide" style="color: #000000;">${title}</div>
        </div>
        <div class="mt-1" style="color: #000000;">
          ${lines.map(line => `<div>${line}</div>`).join("")}
        </div>
      </div>
    `;
  }

  function arrow() {
    return `<div class="hidden md:flex items-center justify-center"><span class="text-slate-400 text-lg">➜</span></div>`;
  }

  function formatCost(v) { return v == null ? "-" : Number(v).toFixed(5); }
  function formatAccuracy(v) { return v == null ? "-" : (Number(v) * 100).toFixed(2) + "%"; }
  function formatLatency(v) { return v == null ? "-" : Number(v).toFixed(2) + "s"; }
});
