(function () {
  const COLORS = ["#1e4d5c", "#3d6b78", "#8a5a2a", "#3f6b4a", "#6b4c7a", "#a15c4a", "#2f5d50", "#8d7a4a", "#5c6570"];
  const PAGE_SIZE = 25;
  const state = {
    year: "",
    month: "",
    quarter: "",
    from: "",
    to: "",
    agency: "",
    sector: "",
    career: "",
    competency: "",
    scope: "all",
    internships: false,
    search: "",
    sortKey: "postingDate",
    sortDir: "desc",
    page: 1,
    trendMode: "month",
  };
  let payload = null;
  const charts = {};

  const status = document.getElementById("status");
  const metaRow = document.getElementById("meta-row");

  function showStatus(message, isError) {
    status.hidden = false;
    status.textContent = message;
    status.className = isError ? "status error" : "status";
  }

  function chart(id) {
    if (!charts[id]) {
      const node = document.getElementById(id);
      charts[id] = echarts.init(node, null, { renderer: "canvas" });
    }
    return charts[id];
  }

  function baseOption(extra) {
    return Object.assign({
      animation: false,
      color: COLORS,
      textStyle: { fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif", color: "#1b2430" },
      grid: { left: 48, right: 16, top: 24, bottom: 48, containLabel: true },
      tooltip: { trigger: "axis" },
    }, extra);
  }

  function passes(job, options) {
    const opts = options || {};
    if (!state.internships && job.internship) return false;
    if (!opts.ignoreScope) {
      if (state.scope === "current" && !job.currentlyListed) return false;
      if (state.scope === "closed" && job.currentlyListed) return false;
    }
    if (opts.onlyCurrent && !job.currentlyListed) return false;
    if (opts.onlyClosed && job.currentlyListed) return false;
    if (state.agency && job.agency !== state.agency) return false;
    if (state.sector && job.sector !== state.sector) return false;
    if (state.career && job.careerLevel !== state.career) return false;
    if (state.competency && !(job.competencies || []).includes(state.competency)) return false;
    const posted = job.postingDate || "";
    if (state.year && job.postingYear !== state.year) return false;
    if (state.quarter && job.postingQuarter !== state.quarter) return false;
    if (state.month && job.postingMonth !== state.month) return false;
    if (state.from && (!posted || posted < state.from)) return false;
    if (state.to && (!posted || posted > state.to)) return false;
    return true;
  }

  function selected(options) {
    return (payload.jobs || []).filter((job) => passes(job, options));
  }

  function median(values) {
    if (!values.length) return null;
    const sorted = values.slice().sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    if (sorted.length % 2) return sorted[mid];
    return Math.round((sorted[mid - 1] + sorted[mid]) / 2);
  }

  function renderMeta() {
    const meta = payload.metadata || {};
    const bits = [
      ["Coverage", meta.coverageStart && meta.coverageEnd ? meta.coverageStart + " to " + meta.coverageEnd : "not available"],
      ["History", meta.historySource === "upstream-replay" ? "replayed from upstream snapshots" : "current extract only"],
      ["Source rows", meta.sourceRows != null ? String(meta.sourceRows) : "unknown"],
      ["Last processed", meta.processedThrough || "unknown"],
    ];
    if (meta.snapshotsUsed != null) {
      bits.push(["Snapshots used", String(meta.snapshotsUsed) + (meta.snapshotsSkipped ? " (" + meta.snapshotsSkipped + " skipped)" : "")]);
    }
    metaRow.innerHTML = bits.map(([label, value]) => "<span>" + label + ": <strong>" + escapeHtml(value) + "</strong></span>").join("");
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderKpis() {
    const meta = payload.metadata;
    const historical = selected({ ignoreScope: true });
    const open = selected({ ignoreScope: true, onlyCurrent: true });
    const inView = selected();
    const closed = selected({ ignoreScope: true, onlyClosed: true });
    const durations = closed.map((job) => job.daysListed).filter((value) => typeof value === "number");
    const minSample = meta.medianMinSample || 10;
    const durationText = durations.length >= minSample ? String(median(durations)) + " days" : "Not enough closed postings";
    const agencies = new Set(open.map((job) => job.agency).filter(Boolean));
    const cards = [
      ["Observed procurement postings", String(historical.length), "Ignores listing-status filter"],
      ["Currently hiring", String(open.length), agencies.size + " agencies"],
      ["New this month", String(inView.filter((job) => job.isNewThisMonth).length), "First seen in the latest month"],
      ["New in latest refresh", String(inView.filter((job) => job.isNewThisRun).length), "First seen on the last run date"],
      ["Agencies hiring now", String(agencies.size), "Open postings in the other filters"],
      ["Median observed span", durationText, durations.length + " closed postings"],
    ];
    document.getElementById("kpis").innerHTML = cards.map(([label, value, note]) => (
      '<article class="kpi"><span>' + escapeHtml(label) + '</span><strong>' + escapeHtml(value) + '</strong><small>' + escapeHtml(note) + '</small></article>'
    )).join("");
  }

  function countBy(jobs, keyFn) {
    const counts = new Map();
    jobs.forEach((job) => {
      const key = keyFn(job);
      if (!key) return;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return counts;
  }

  function renderTrend() {
    const jobs = selected().filter((job) => job.inTrend);
    const key = state.trendMode === "quarter" ? "trendQuarter" : "trendMonth";
    const counts = countBy(jobs, (job) => job[key]);
    const labels = Array.from(counts.keys()).sort();
    const values = labels.map((label) => counts.get(label));
    const last = Math.max(labels.length - 1, 0);
    const start = labels.length > 12 ? ((labels.length - 12) / labels.length) * 100 : 0;
    chart("chart-trend").setOption(baseOption({
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels, axisLabel: { rotate: labels.length > 8 ? 45 : 0 } },
      yAxis: { type: "value", minInterval: 1, name: "Postings" },
      dataZoom: labels.length > 12 ? [{ type: "slider", start: start, end: 100 }, { type: "inside", start: start, end: 100 }] : [],
      series: [{ type: "bar", data: values, itemStyle: { color: "#1e4d5c" }, name: "Newly observed" }],
    }), true);
    if (!labels.length) {
      chart("chart-trend").setOption({
        title: { text: "No postings in this filter fall inside snapshot coverage.", left: "center", top: "middle", textStyle: { fontSize: 14, fontWeight: 500, color: "#5e6874", width: 280, overflow: "break" } },
        xAxis: { show: false },
        yAxis: { show: false },
        series: [],
      });
    }
    void last;
  }

  function renderBars(id, labels, counts, horizontal) {
    const data = labels.map((label) => counts.get(label) || 0);
    const hasAny = data.some((value) => value > 0);
    if (!hasAny) {
      chart(id).setOption(baseOption({
        title: { text: "Nothing to show for this filter.", left: "center", top: "middle", textStyle: { fontSize: 14, fontWeight: 500, color: "#5e6874" } },
        xAxis: { show: false },
        yAxis: { show: false },
        series: [],
      }), true);
      return;
    }
    chart(id).setOption(baseOption({
      grid: horizontal ? { left: 12, right: 24, top: 12, bottom: 12, containLabel: true } : { left: 48, right: 16, top: 24, bottom: 72, containLabel: true },
      tooltip: { trigger: "axis" },
      xAxis: horizontal ? { type: "value", minInterval: 1 } : { type: "category", data: labels, axisLabel: { rotate: 35, interval: 0 } },
      yAxis: horizontal ? { type: "category", data: labels, inverse: true } : { type: "value", minInterval: 1 },
      series: [{ type: "bar", data: data, itemStyle: { color: "#1e4d5c" } }],
    }), true);
  }

  function renderSector() {
    const jobs = selected();
    const counts = countBy(jobs, (job) => job.sector || "Other / Unclassified");
    const labels = payload.metadata.sectorLabels || Array.from(counts.keys());
    renderBars("chart-sector", labels, counts, false);
    const months = Array.from(countBy(jobs.filter((job) => job.inTrend), (job) => job.trendMonth).keys()).sort();
    const sectors = labels.filter((label) => (counts.get(label) || 0) > 0);
    const series = sectors.map((sector) => ({
      name: sector,
      type: "line",
      showSymbol: false,
      data: months.map((month) => jobs.filter((job) => job.inTrend && job.trendMonth === month && job.sector === sector).length),
    }));
    if (!months.length) {
      chart("chart-sector-trend").setOption(baseOption({
        title: { text: "No covered months in this filter.", left: "center", top: "middle", textStyle: { fontSize: 14, fontWeight: 500, color: "#5e6874" } },
        xAxis: { show: false },
        yAxis: { show: false },
        series: [],
      }), true);
      return;
    }
    chart("chart-sector-trend").setOption(baseOption({
      tooltip: { trigger: "axis" },
      legend: { type: "scroll", bottom: 0 },
      grid: { left: 48, right: 16, top: 16, bottom: 64, containLabel: true },
      xAxis: { type: "category", data: months },
      yAxis: { type: "value", minInterval: 1 },
      series: series,
    }), true);
  }

  function renderCareer() {
    const jobs = selected();
    const counts = countBy(jobs, (job) => job.careerLevel);
    renderBars("chart-career", payload.metadata.careerLabels || [], counts, false);
    const yearCounts = new Map();
    jobs.forEach((job) => {
      const years = job.experienceMinYears;
      const label = years == null ? "Not stated" : (years >= 16 ? "16+" : String(years));
      yearCounts.set(label, (yearCounts.get(label) || 0) + 1);
    });
    const labels = ["Not stated"].concat(Array.from({ length: 16 }, (_, index) => String(index)), ["16+"]);
    renderBars("chart-years", labels, yearCounts, false);
  }

  function topAgencies(jobs, limit) {
    const counts = countBy(jobs, (job) => job.agency || "Unknown agency");
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, limit);
  }

  function renderAgency() {
    const ranked = topAgencies(selected(), 12);
    const labels = ranked.map((item) => item[0]);
    const counts = new Map(ranked);
    renderBars("chart-agency", labels, counts, true);
    const openRanked = topAgencies(selected({ ignoreScope: true, onlyCurrent: true }), 12);
    renderBars("chart-agency-open", openRanked.map((item) => item[0]), new Map(openRanked), true);
  }

  function renderCompetency() {
    const counts = new Map();
    (payload.metadata.competencyLabels || []).forEach((label) => counts.set(label, 0));
    selected().forEach((job) => {
      (job.competencies || []).forEach((label) => {
        counts.set(label, (counts.get(label) || 0) + 1);
      });
    });
    renderBars("chart-competency", payload.metadata.competencyLabels || [], counts, false);
  }

  function sentence(text) {
    return '<article class="insight"><p>' + escapeHtml(text) + "</p></article>";
  }

  function renderInsights() {
    const jobs = selected();
    const open = selected({ ignoreScope: true, onlyCurrent: true });
    const meta = payload.metadata;
    const minCount = meta.insightMinPeriodCount || 5;
    const minChange = meta.insightMinChange || 3;
    const lines = [];
    if (!jobs.length) {
      document.getElementById("insight-list").innerHTML = sentence("No postings match these filters, so there is no workforce finding to report.");
      return;
    }
    const levelCounts = countBy(open, (job) => job.careerLevel);
    const topLevel = Array.from(levelCounts.entries()).sort((a, b) => b[1] - a[1])[0];
    if (topLevel) {
      lines.push(topLevel[0] + " is the largest share of current vacancies in this filter: " + topLevel[1] + " of " + open.length + " open postings.");
    } else {
      lines.push("No current vacancies remain in this filter.");
    }
    const agencyCounts = topAgencies(open, 3);
    if (agencyCounts.length) {
      lines.push("Open demand is led by " + agencyCounts.map((item) => item[0] + " (" + item[1] + ")").join(", ") + ".");
    }
    const clear = open.filter((job) => job.careerLevel !== "Broad / No Clear Preference");
    const early = clear.filter((job) => job.careerLevel === "Fresh Graduate / Entry Level" || job.careerLevel === "Early Career").length;
    const senior = clear.filter((job) => job.careerLevel === "Experienced / Senior").length;
    if (clear.length) {
      lines.push("Among " + clear.length + " open postings with a clear level, " + early + " are entry or early career and " + senior + " are experienced.");
    } else if (open.length) {
      lines.push("None of the " + open.length + " open postings state a narrow experience band, so the entry-versus-senior balance cannot be read.");
    }
    const sectorCounts = countBy(open, (job) => job.sector);
    const topSector = Array.from(sectorCounts.entries()).sort((a, b) => b[1] - a[1])[0];
    if (topSector) {
      lines.push(topSector[0] + " accounts for " + topSector[1] + " of " + open.length + " open postings. Other / Unclassified means the text did not support a sector.");
    }
    const competencyCounts = new Map();
    open.forEach((job) => (job.competencies || []).forEach((label) => competencyCounts.set(label, (competencyCounts.get(label) || 0) + 1)));
    const topCompetency = Array.from(competencyCounts.entries()).sort((a, b) => b[1] - a[1])[0];
    if (topCompetency) {
      lines.push("The most frequent competency label on open postings is " + topCompetency[0] + " (" + topCompetency[1] + " postings). A posting can carry more than one label.");
    }
    const trendJobs = jobs.filter((job) => job.inTrend && job.trendMonth);
    const months = Array.from(new Set(trendJobs.map((job) => job.trendMonth))).sort();
    if (months.length >= 2) {
      const latest = months[months.length - 1];
      const prior = months[months.length - 2];
      const latestCount = trendJobs.filter((job) => job.trendMonth === latest).length;
      const priorCount = trendJobs.filter((job) => job.trendMonth === prior).length;
      const gap = latestCount - priorCount;
      if (latestCount >= minCount && priorCount >= minCount && Math.abs(gap) >= minChange) {
        const direction = gap > 0 ? "higher" : "lower";
        lines.push("Newly observed postings were " + direction + " in " + latest + " (" + latestCount + ") than in " + prior + " (" + priorCount + "). The latest month can still be incomplete.");
      } else {
        lines.push("The move from " + prior + " (" + priorCount + ") to " + latest + " (" + latestCount + ") is too small to interpret. Both periods need at least " + minCount + " postings and a gap of " + minChange + ".");
      }
    } else {
      lines.push("There are not two covered months in this filter, so a month-to-month change is not reported.");
    }
    document.getElementById("insight-list").innerHTML = lines.map(sentence).join("");
  }

  function vacancyRows() {
    const query = state.search.trim().toLowerCase();
    let rows = selected({ ignoreScope: true, onlyCurrent: true });
    if (query) {
      rows = rows.filter((job) => (job.jobTitle + " " + job.agency).toLowerCase().includes(query));
    }
    const direction = state.sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      const left = a[state.sortKey] || "";
      const right = b[state.sortKey] || "";
      if (left < right) return -1 * direction;
      if (left > right) return 1 * direction;
      return (a.jobTitle || "").localeCompare(b.jobTitle || "");
    });
    return rows;
  }

  function renderTable() {
    const rows = vacancyRows();
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    const start = (state.page - 1) * PAGE_SIZE;
    const slice = rows.slice(start, start + PAGE_SIZE);
    const body = document.getElementById("vacancy-body");
    if (!slice.length) {
      body.innerHTML = '<tr><td colspan="7">No open procurement postings match these filters.</td></tr>';
    } else {
      body.innerHTML = slice.map((job) => {
        const link = job.url
          ? '<a href="' + escapeHtml(job.url) + '" rel="noopener noreferrer">View posting</a>'
          : "No link";
        return "<tr><td>" + escapeHtml(job.agency) + "</td><td>" + escapeHtml(job.jobTitle) + "</td><td>" + escapeHtml(job.sector) + "</td><td>" + escapeHtml(job.careerLevel) + "</td><td>" + escapeHtml(job.postingDate || "—") + "</td><td>" + escapeHtml(job.closingDate || "—") + "</td><td>" + link + "</td></tr>";
      }).join("");
    }
    document.getElementById("table-count").textContent = rows.length + " open postings";
    document.getElementById("page-label").textContent = "Page " + state.page + " of " + pages;
    document.getElementById("page-prev").disabled = state.page <= 1;
    document.getElementById("page-next").disabled = state.page >= pages;
  }

  function fillSelect(id, values, placeholder) {
    const select = document.getElementById(id);
    const current = select.value;
    const options = ['<option value="">' + escapeHtml(placeholder) + "</option>"].concat(
      values.filter(Boolean).map((value) => '<option value="' + escapeHtml(value) + '">' + escapeHtml(value) + "</option>")
    );
    select.innerHTML = options.join("");
    if (values.includes(current)) select.value = current;
  }

  function populateFilters() {
    const jobs = payload.jobs || [];
    fillSelect("filter-year", Array.from(new Set(jobs.map((job) => job.postingYear))).sort(), "All years");
    fillSelect("filter-quarter", Array.from(new Set(jobs.map((job) => job.postingQuarter))).sort(), "All quarters");
    fillSelect("filter-month", Array.from(new Set(jobs.map((job) => job.postingMonth))).sort(), "All months");
    fillSelect("filter-agency", Array.from(new Set(jobs.map((job) => job.agency))).sort((a, b) => a.localeCompare(b)), "All agencies");
    fillSelect("filter-sector", payload.metadata.sectorLabels || [], "All sectors");
    fillSelect("filter-career", payload.metadata.careerLabels || [], "All levels");
    fillSelect("filter-competency", payload.metadata.competencyLabels || [], "All competencies");
  }

  function render() {
    renderMeta();
    renderKpis();
    renderTrend();
    renderSector();
    renderCareer();
    renderAgency();
    renderCompetency();
    renderInsights();
    renderTable();
    Object.values(charts).forEach((item) => item.resize());
  }

  function bind(id, key, eventName) {
    document.getElementById(id).addEventListener(eventName || "change", (event) => {
      state[key] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
      state.page = 1;
      render();
    });
  }

  function resetFilters() {
    state.year = "";
    state.month = "";
    state.quarter = "";
    state.from = "";
    state.to = "";
    state.agency = "";
    state.sector = "";
    state.career = "";
    state.competency = "";
    state.scope = "all";
    state.internships = false;
    state.search = "";
    state.page = 1;
    document.getElementById("filters").reset();
    document.getElementById("filter-scope").value = "all";
    document.getElementById("filter-internships").checked = false;
    document.getElementById("table-search").value = "";
    render();
  }

  document.getElementById("reset").addEventListener("click", resetFilters);
  bind("filter-year", "year");
  bind("filter-month", "month");
  bind("filter-quarter", "quarter");
  bind("filter-from", "from");
  bind("filter-to", "to");
  bind("filter-agency", "agency");
  bind("filter-sector", "sector");
  bind("filter-career", "career");
  bind("filter-competency", "competency");
  bind("filter-scope", "scope");
  bind("filter-internships", "internships");
  document.getElementById("table-search").addEventListener("input", (event) => {
    state.search = event.target.value;
    state.page = 1;
    renderTable();
  });
  document.getElementById("page-prev").addEventListener("click", () => { state.page -= 1; renderTable(); });
  document.getElementById("page-next").addEventListener("click", () => { state.page += 1; renderTable(); });
  document.querySelectorAll("[data-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.getAttribute("data-sort");
      if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      else {
        state.sortKey = key;
        state.sortDir = key === "jobTitle" || key === "agency" || key === "sector" || key === "careerLevel" ? "asc" : "desc";
      }
      renderTable();
    });
  });
  document.getElementById("mode-month").addEventListener("click", () => {
    state.trendMode = "month";
    document.getElementById("mode-month").setAttribute("aria-pressed", "true");
    document.getElementById("mode-quarter").setAttribute("aria-pressed", "false");
    renderTrend();
  });
  document.getElementById("mode-quarter").addEventListener("click", () => {
    state.trendMode = "quarter";
    document.getElementById("mode-quarter").setAttribute("aria-pressed", "true");
    document.getElementById("mode-month").setAttribute("aria-pressed", "false");
    renderTrend();
  });
  window.addEventListener("resize", () => Object.values(charts).forEach((item) => item.resize()));

  fetch("data/dashboard_data.json")
    .then((response) => {
      if (!response.ok) throw new Error("Dashboard data is not available yet (" + response.status + ").");
      return response.json();
    })
    .then((data) => {
      payload = data;
      status.hidden = true;
      populateFilters();
      render();
    })
    .catch((error) => {
      showStatus(error.message + " Run the processing pipeline, then reload this page.", true);
    });
})();
