(function () {
  const ACCENT = "#1e4d5c";
  const ACCENT_PALE = "#a9bfc5";
  const OPEN = "#2f6b46";
  const CLOSED = "#c9c1b2";
  const LINE = "#8a5a2a";
  const PAGE_SIZE = 25;
  const FONT = "Segoe UI, Helvetica Neue, Arial, sans-serif";

  const state = {
    status: "all",
    period: "",
    agency: "",
    includeDuty: false,
    internships: false,
    interval: "quarter",
    compare: "quarter",
    search: "",
    sortKey: "",
    sortDir: "desc",
    page: 1,
  };
  let payload = null;
  let meta = {};
  const charts = {};

  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-SG", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  }

  function pct(part, whole) {
    return whole ? Math.round((part / whole) * 100) : 0;
  }

  function plural(n, word, many) {
    return n + " " + (n === 1 ? word : (many || word + "s"));
  }

  // ---------- Filtering ----------

  function passesBase(job) {
    if (!state.internships && job.internship) return false;
    if (!state.includeDuty && job.matchBasis === "duty_phrase") return false;
    if (state.agency && job.agency !== state.agency) return false;
    return true;
  }

  function passesStatus(job) {
    if (state.status === "open") return job.open;
    if (state.status === "closed") return !job.open;
    return true;
  }

  function passesPeriod(job) {
    if (!state.period) return true;
    const [kind, key] = state.period.split(":");
    return kind === "q" ? job.firstQuarter === key : job.firstMonth === key;
  }

  function inView() {
    return payload.jobs.filter((job) => passesBase(job) && passesStatus(job) && passesPeriod(job));
  }

  function ignoringPeriod() {
    return payload.jobs.filter((job) => passesBase(job) && passesStatus(job));
  }

  function countBy(jobs, keyFn) {
    const counts = new Map();
    jobs.forEach((job) => {
      const key = keyFn(job);
      if (key == null || key === "") return;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return counts;
  }

  // ---------- Periods ----------

  function quarterIndex(key) {
    const [y, q] = key.split("Q").map(Number);
    return y * 4 + (q - 1);
  }

  function quarterByIndex(index) {
    return (meta.quarters || []).find((q) => quarterIndex(q.key) === index);
  }

  function periodLabel(period) {
    return period.label + (period.note ? " (" + period.note + ")" : "");
  }

  function selectedPeriod() {
    if (!state.period) return null;
    const [kind, key] = state.period.split(":");
    const list = kind === "q" ? meta.quarters : meta.months;
    return (list || []).find((item) => item.key === key) || null;
  }

  function yoyAvailable() {
    return (meta.quarters || []).some((q) => {
      const prior = quarterByIndex(quarterIndex(q.key) - 4);
      return q.complete && prior && prior.complete;
    });
  }

  // Target quarter and the one it is compared with, or a reason it cannot be.
  function comparisonPair() {
    let target = null;
    const chosen = selectedPeriod();
    if (state.period && state.period.startsWith("q:")) {
      if (!chosen || !chosen.complete) {
        return { reason: (chosen ? periodLabel(chosen) : "This quarter") + " is not a complete quarter, so it is not compared." };
      }
      target = chosen;
    } else if (state.period) {
      return { reason: "Quarter comparison is available when the period is All time or a complete quarter." };
    } else {
      const complete = (meta.quarters || []).filter((q) => q.complete);
      target = complete[complete.length - 1] || null;
      if (!target) return { reason: "There is no complete quarter in the history yet." };
    }
    const offset = state.compare === "year" ? 4 : 1;
    const prior = quarterByIndex(quarterIndex(target.key) - offset);
    if (!prior || !prior.complete) {
      const what = state.compare === "year" ? "the same quarter last year" : "the previous quarter";
      return { target: target, reason: periodLabel(target) + " cannot be compared with " + what + " because that quarter is not fully inside the history." };
    }
    return { target: target, prior: prior };
  }

  function describeChange(now, before) {
    const gap = now - before;
    const enough = now >= meta.comparisonMinCount && before >= meta.comparisonMinCount;
    if (!enough) return { kind: "small", text: "too few postings to compare" };
    const change = before ? Math.round((gap / before) * 100) : 0;
    if (Math.abs(gap) < meta.comparisonMinChange || Math.abs(change) < meta.comparisonMinPercent) {
      return { kind: "flat", text: "about the same" };
    }
    return { kind: gap > 0 ? "up" : "down", text: (gap > 0 ? "up " : "down ") + Math.abs(change) + "%" };
  }

  // ---------- Header, scope, KPIs ----------

  function renderMeta() {
    const bits = [
      ["Data to", fmtDate(meta.processedThrough)],
      ["History from", fmtDate(meta.coverageStart)],
      ["Source", "Careers@Gov via OpenGovSG"],
    ];
    $("meta-row").innerHTML = bits.map(([label, value]) => "<span>" + label + " <strong>" + escapeHtml(value) + "</strong></span>").join("");
    document.querySelectorAll("[data-meta]").forEach((node) => {
      const key = node.getAttribute("data-meta");
      const value = meta[key];
      node.textContent = key === "coverageStart" ? fmtDate(value) : String(value == null ? "" : value);
    });
  }

  function renderScope(jobs) {
    const statusText = { all: "open and closed", open: "open now", closed: "closed" }[state.status];
    const period = selectedPeriod();
    const parts = [
      "<strong>" + plural(jobs.length, "procurement posting") + "</strong>",
      statusText,
      period ? "first seen in " + escapeHtml(periodLabel(period)) : "since " + escapeHtml(fmtDate(meta.coverageStart)),
    ];
    if (state.agency) parts.push("at " + escapeHtml(state.agency));
    const extra = [];
    if (state.includeDuty) extra.push("including duties-only matches");
    if (state.internships) extra.push("including internships");
    $("scope").innerHTML = "Showing " + parts.join(", ") + (extra.length ? " (" + extra.join(", ") + ")" : "") + ".";
  }

  function closingSoon(jobs) {
    return jobs.filter((job) => job.open && job.daysUntilClosing != null && job.daysUntilClosing >= 0 && job.daysUntilClosing <= meta.closingSoonDays);
  }

  function noPermanentShare(jobs) {
    const stated = jobs.filter((job) => job.contractType !== "Not stated");
    const none = stated.filter((job) => (meta.noPermanentOption || []).includes(job.contractType));
    return { share: pct(none.length, stated.length), count: none.length, stated: stated.length };
  }

  function kpi(label, value, note) {
    return '<article class="kpi"><span>' + escapeHtml(label) + "</span><strong>" + value + "</strong><small>" + note + "</small></article>";
  }

  function renderKpis(jobs) {
    const open = jobs.filter((job) => job.open);
    const closed = jobs.length - open.length;
    const agencies = new Set(jobs.map((job) => job.agency)).size;
    const cards = [];
    cards.push(kpi("Procurement postings", String(jobs.length),
      escapeHtml(open.length + " open · " + closed + " closed · " + plural(agencies, "agency", "agencies"))));

    const pair = comparisonPair();
    if (pair.prior) {
      const pool = ignoringPeriod().filter((job) => job.inTrend);
      const now = pool.filter((job) => job.trendQuarter === pair.target.key).length;
      const before = pool.filter((job) => job.trendQuarter === pair.prior.key).length;
      const change = describeChange(now, before);
      const cls = change.kind === "up" ? "delta-up" : change.kind === "down" ? "delta-down" : "";
      cards.push(kpi("New in " + pair.target.label, String(now),
        '<span class="' + cls + '">' + escapeHtml(change.text) + "</span> vs " + escapeHtml(pair.prior.label) + " (" + before + ")"));
    } else if (pair.target) {
      const pool = ignoringPeriod().filter((job) => job.inTrend && job.trendQuarter === pair.target.key);
      cards.push(kpi("New in " + pair.target.label, String(pool.length), "No comparable quarter yet"));
    } else {
      cards.push(kpi("New in a full quarter", "—", "Pick All time or a complete quarter"));
    }

    if (state.status === "closed") {
      cards.push(kpi("Closing within " + meta.closingSoonDays + " days", "—", "Closed postings selected"));
    } else {
      const soon = closingSoon(jobs);
      cards.push(kpi("Closing within " + meta.closingSoonDays + " days", String(soon.length),
        escapeHtml("of " + open.length + " open, as of " + fmtDate(meta.processedThrough))));
    }

    const np = noPermanentShare(jobs);
    cards.push(kpi("No permanent option", np.stated ? np.share + "%" : "—",
      escapeHtml(np.count + " of " + np.stated + " are fixed term or contract only")));
    $("kpis").innerHTML = cards.join("");
  }

  // ---------- What changed ----------

  function renderChanges(jobs) {
    const lines = [];
    if (!jobs.length) {
      $("changes").innerHTML = "<li>No postings match these filters.</li>";
      return;
    }
    const pair = comparisonPair();
    if (pair.prior) {
      const pool = ignoringPeriod().filter((job) => job.inTrend);
      const now = pool.filter((job) => job.trendQuarter === pair.target.key).length;
      const before = pool.filter((job) => job.trendQuarter === pair.prior.key).length;
      const change = describeChange(now, before);
      let text;
      if (change.kind === "small") {
        text = pair.target.label + " had " + plural(now, "new posting") + " and " + pair.prior.label + " had " + before + ". That is too few to call a change (each quarter needs at least " + meta.comparisonMinCount + ").";
      } else if (change.kind === "flat") {
        text = "New postings were about the same in " + pair.target.label + " (" + now + ") as in " + pair.prior.label + " (" + before + ").";
      } else {
        text = "New postings were " + change.text + " in " + pair.target.label + " (" + now + ") compared with " + pair.prior.label + " (" + before + ").";
      }
      lines.push(text);
    } else {
      lines.push(pair.reason);
    }

    if (state.status !== "closed") {
      const open = jobs.filter((job) => job.open);
      if (open.length) {
        const agencies = new Set(open.map((job) => job.agency)).size;
        const soon = closingSoon(jobs).length;
        lines.push(plural(open.length, "role is", "roles are") + " open now at " + plural(agencies, "agency", "agencies") + (soon ? "; " + soon + " close within " + meta.closingSoonDays + " days." : "."));
      } else {
        lines.push("None of these postings are open now.");
      }
    }

    const agencyCounts = Array.from(countBy(jobs, (job) => job.agency).entries()).sort((a, b) => b[1] - a[1]);
    if (agencyCounts.length) {
      const [name, count] = agencyCounts[0];
      lines.push(name + " has the most postings in view: " + count + " (" + pct(count, jobs.length) + "%).");
    }

    const np = noPermanentShare(jobs);
    const bands = countBy(jobs.filter((job) => job.experienceBand !== "Not stated"), (job) => job.experienceBand);
    const topBand = Array.from(bands.entries()).sort((a, b) => b[1] - a[1])[0];
    const statedYears = Array.from(bands.values()).reduce((a, b) => a + b, 0);
    if (np.stated) {
      let text = np.share + "% offer no permanent option (fixed term or contract only).";
      if (topBand) text += " The most common minimum asked is " + topBand[0] + " (" + pct(topBand[1], statedYears) + "% of postings that state one).";
      lines.push(text);
    }
    $("changes").innerHTML = lines.map((line) => "<li>" + escapeHtml(line) + "</li>").join("");
  }

  // ---------- Charts ----------

  function chart(id) {
    if (!charts[id]) charts[id] = echarts.init($(id), null, { renderer: "canvas" });
    return charts[id];
  }

  function emptyChart(id, text) {
    chart(id).setOption({
      title: { text: text, left: "center", top: "middle", textStyle: { fontSize: 13, fontWeight: 500, color: "#5e6874", fontFamily: FONT } },
      xAxis: { show: false }, yAxis: { show: false }, series: [],
    }, true);
  }

  function base(extra) {
    return Object.assign({
      animation: false,
      textStyle: { fontFamily: FONT, color: "#1b2430" },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    }, extra);
  }

  function renderTrend(jobs) {
    const periods = (state.interval === "quarter" ? meta.quarters : meta.months) || [];
    const chosen = selectedPeriod();
    let shown = periods;
    if (chosen) {
      shown = periods.filter((p) => p.start <= chosen.end && p.end >= chosen.start);
    }
    if (!shown.length || !jobs.length) {
      emptyChart("chart-trend", "No postings in this view.");
      return;
    }
    const key = state.interval === "quarter" ? "trendQuarter" : "trendMonth";
    const counts = countBy(jobs.filter((job) => job.inTrend), (job) => job[key]);
    const through = meta.processedThrough;
    const openAtEnd = shown.map((p) => {
      const end = p.end < through ? p.end : through;
      return jobs.filter((job) => job.firstSeen && job.firstSeen <= end && job.lastSeen >= end).length;
    });
    const labels = shown.map((p) => p.label + (p.complete ? "" : "*"));
    chart("chart-trend").setOption(base({
      grid: { left: 8, right: 12, top: 30, bottom: 8, containLabel: true },
      legend: { top: 0, left: 0, itemWidth: 14, itemHeight: 9, textStyle: { fontSize: 12 } },
      tooltip: {
        trigger: "axis",
        formatter: (items) => {
          const p = shown[items[0].dataIndex];
          return "<strong>" + escapeHtml(periodLabel(p)) + "</strong><br>" + items.map((i) => i.marker + escapeHtml(i.seriesName) + ": " + i.value).join("<br>");
        },
      },
      xAxis: { type: "category", data: labels, axisLabel: { fontSize: 11, hideOverlap: true }, axisTick: { alignWithLabel: true } },
      yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#ece7dc" } } },
      series: [
        {
          name: "New postings",
          type: "bar",
          barMaxWidth: 46,
          data: shown.map((p) => ({ value: counts.get(p.key) || 0, itemStyle: { color: p.complete ? ACCENT : ACCENT_PALE } })),
          label: { show: shown.length <= 8, position: "top", fontSize: 11, color: "#1b2430" },
        },
        { name: "Open at end of period", type: "line", data: openAtEnd, color: LINE, symbolSize: 6, lineStyle: { width: 2 } },
      ],
    }), true);
  }

  function renderAgencies(jobs) {
    const limit = meta.topAgencies || 10;
    const ranked = Array.from(countBy(jobs, (job) => job.agency || "Unknown agency").entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, limit);
    if (!ranked.length) {
      emptyChart("chart-agency", "No postings in this view.");
      return;
    }
    const names = ranked.map((item) => item[0]);
    const openCounts = names.map((name) => jobs.filter((job) => job.agency === name && job.open).length);
    const closedCounts = names.map((name, i) => ranked[i][1] - openCounts[i]);
    const c = chart("chart-agency");
    c.setOption(base({
      grid: { left: 8, right: 28, top: 26, bottom: 4, containLabel: true },
      legend: { top: 0, left: 0, itemWidth: 14, itemHeight: 9, textStyle: { fontSize: 12 } },
      xAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#ece7dc" } } },
      yAxis: {
        type: "category",
        inverse: true,
        data: names,
        axisLabel: { fontSize: 11, width: 190, overflow: "truncate" },
        triggerEvent: true,
      },
      series: [
        { name: "Open", type: "bar", stack: "a", data: openCounts, color: OPEN, barMaxWidth: 18 },
        {
          name: "Closed", type: "bar", stack: "a", data: closedCounts, color: CLOSED, barMaxWidth: 18,
          label: { show: true, position: "right", fontSize: 11, color: "#1b2430", formatter: (p) => ranked[p.dataIndex][1] },
        },
      ],
    }), true);
    c.off("click");
    c.on("click", (params) => {
      const name = params.componentType === "yAxis" ? params.value : names[params.dataIndex];
      if (!name) return;
      state.agency = state.agency === name ? "" : name;
      $("filter-agency").value = state.agency;
      state.page = 1;
      render();
    });
  }

  function renderShareBars(id, labels, jobs, keyFn) {
    const counts = countBy(jobs, keyFn);
    const used = labels.filter((label) => counts.get(label));
    if (!used.length) {
      emptyChart(id, "No postings in this view.");
      return;
    }
    const total = jobs.length;
    chart(id).setOption(base({
      grid: { left: 8, right: 74, top: 4, bottom: 4, containLabel: true },
      tooltip: { trigger: "item", formatter: (p) => escapeHtml(p.name) + ": " + p.value + " (" + pct(p.value, total) + "%)" },
      xAxis: { type: "value", show: false },
      yAxis: { type: "category", inverse: true, data: used, axisTick: { show: false }, axisLine: { show: false }, axisLabel: { fontSize: 12 } },
      series: [{
        type: "bar",
        data: used.map((label) => counts.get(label)),
        color: ACCENT,
        barMaxWidth: 18,
        label: { show: true, position: "right", fontSize: 11, color: "#1b2430", formatter: (p) => p.value + " · " + pct(p.value, total) + "%" },
      }],
    }), true);
  }

  // ---------- Jobs table ----------

  function closesText(job) {
    if (!job.closingDate) return "—";
    const date = escapeHtml(fmtDate(job.closingDate));
    if (!job.open || job.daysUntilClosing == null) return date;
    const d = job.daysUntilClosing;
    if (d < 0) return date;
    const soon = d <= meta.closingSoonDays;
    const when = d === 0 ? "today" : "in " + plural(d, "day");
    return date + '<br><span class="' + (soon ? "soon" : "muted") + '">' + when + "</span>";
  }

  function sortRows(rows) {
    const key = state.sortKey;
    const dir = state.sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      if (!key) {
        if (a.open !== b.open) return a.open ? -1 : 1;
        return (b.postingDate || "").localeCompare(a.postingDate || "") || (a.jobTitle || "").localeCompare(b.jobTitle || "");
      }
      let left = a[key];
      let right = b[key];
      if (typeof left === "boolean") { left = left ? 1 : 0; right = right ? 1 : 0; }
      if (left == null || left === "") return 1;
      if (right == null || right === "") return -1;
      if (left < right) return -1 * dir;
      if (left > right) return 1 * dir;
      return (a.jobTitle || "").localeCompare(b.jobTitle || "");
    });
    return rows;
  }

  function tableRows(jobs) {
    const query = state.search.trim().toLowerCase();
    let rows = jobs.slice();
    if (query) rows = rows.filter((job) => (job.jobTitle + " " + job.agency).toLowerCase().includes(query));
    return sortRows(rows);
  }

  function renderTable(jobs) {
    const rows = tableRows(jobs);
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    const slice = rows.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
    const body = $("job-body");
    if (!slice.length) {
      body.innerHTML = '<tr><td colspan="7">No postings match these filters.</td></tr>';
    } else {
      body.innerHTML = slice.map((job) => {
        const link = job.url
          ? '<a href="' + escapeHtml(job.url) + '" target="_blank" rel="noopener noreferrer">View posting<span class="sr-only"> for ' + escapeHtml(job.jobTitle) + "</span></a>"
          : "No link";
        const badge = job.open ? '<span class="badge open">Open</span>' : '<span class="badge closed">Closed</span>';
        const years = job.experienceMinYears == null ? "—" : String(job.experienceMinYears);
        return "<tr>" +
          '<td class="role"><strong>' + escapeHtml(job.jobTitle) + "</strong><span>" + escapeHtml(job.agency) + "</span></td>" +
          "<td>" + badge + "</td>" +
          "<td>" + escapeHtml(job.contractType) + "</td>" +
          "<td>" + years + "</td>" +
          '<td class="nowrap">' + escapeHtml(fmtDate(job.postingDate)) + "</td>" +
          '<td class="nowrap">' + closesText(job) + "</td>" +
          '<td class="nowrap">' + link + "</td>" +
          "</tr>";
      }).join("");
    }
    $("table-count").textContent = plural(rows.length, "posting");
    $("page-label").textContent = "Page " + state.page + " of " + pages;
    $("page-prev").disabled = state.page <= 1;
    $("page-next").disabled = state.page >= pages;
    document.querySelectorAll("[data-sort]").forEach((button) => {
      const active = button.getAttribute("data-sort") === state.sortKey;
      if (active) button.setAttribute("aria-sort", state.sortDir === "asc" ? "ascending" : "descending");
      else button.removeAttribute("aria-sort");
    });
  }

  // ---------- Controls ----------

  function populateFilters() {
    const period = $("filter-period");
    const quarterOptions = (meta.quarters || []).slice().reverse()
      .map((q) => '<option value="q:' + q.key + '">' + escapeHtml(periodLabel(q)) + "</option>").join("");
    const monthOptions = (meta.months || []).slice().reverse()
      .map((m) => '<option value="m:' + m.key + '">' + escapeHtml(periodLabel(m)) + "</option>").join("");
    period.innerHTML = '<option value="">All time</option><optgroup label="Quarters">' + quarterOptions + '</optgroup><optgroup label="Months">' + monthOptions + "</optgroup>";
    const agencies = Array.from(new Set(payload.jobs.map((job) => job.agency).filter(Boolean))).sort((a, b) => a.localeCompare(b));
    $("filter-agency").innerHTML = '<option value="">All agencies</option>' + agencies.map((a) => '<option value="' + escapeHtml(a) + '">' + escapeHtml(a) + "</option>").join("");
    const yearButton = $("compare-year");
    if (!yoyAvailable()) {
      yearButton.disabled = true;
      yearButton.title = "Available from " + meta.yoyAvailableFrom + ", once a full quarter has a full quarter a year earlier.";
      yearButton.textContent = "vs same quarter last year (from " + meta.yoyAvailableFrom + ")";
    }
  }

  function setPressed(selector, attr, value) {
    document.querySelectorAll(selector).forEach((button) => {
      button.setAttribute("aria-checked", button.getAttribute(attr) === value ? "true" : "false");
    });
  }

  function syncControls() {
    setPressed("[data-status]", "data-status", state.status);
    setPressed("[data-interval]", "data-interval", state.interval);
    setPressed("[data-compare]", "data-compare", state.compare);
    $("filter-period").value = state.period;
    $("filter-agency").value = state.agency;
    $("filter-duty").checked = state.includeDuty;
    $("filter-internships").checked = state.internships;
    $("table-search").value = state.search;
  }

  function render() {
    const jobs = inView();
    renderScope(jobs);
    renderKpis(jobs);
    renderChanges(jobs);
    renderTrend(jobs);
    renderAgencies(jobs);
    renderShareBars("chart-contract", meta.contractLabels || [], jobs, (job) => job.contractType);
    renderShareBars("chart-experience", meta.experienceBands || [], jobs, (job) => job.experienceBand);
    renderTable(jobs);
  }

  function resetFilters() {
    Object.assign(state, { status: "all", period: "", agency: "", includeDuty: false, internships: false, search: "", sortKey: "", sortDir: "desc", page: 1 });
    syncControls();
    render();
  }

  function bindSegmented(attr, key, rerender) {
    document.querySelectorAll("[" + attr + "]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.disabled) return;
        state[key] = button.getAttribute(attr);
        state.page = 1;
        setPressed("[" + attr + "]", attr, state[key]);
        rerender();
      });
    });
  }

  function bindControls() {
    bindSegmented("data-status", "status", render);
    bindSegmented("data-compare", "compare", render);
    bindSegmented("data-interval", "interval", () => renderTrend(inView()));
    [["filter-period", "period"], ["filter-agency", "agency"]].forEach(([id, key]) => {
      $(id).addEventListener("change", (event) => { state[key] = event.target.value; state.page = 1; render(); });
    });
    [["filter-duty", "includeDuty"], ["filter-internships", "internships"]].forEach(([id, key]) => {
      $(id).addEventListener("change", (event) => { state[key] = event.target.checked; state.page = 1; render(); });
    });
    $("reset").addEventListener("click", resetFilters);
    $("table-search").addEventListener("input", (event) => { state.search = event.target.value; state.page = 1; renderTable(inView()); });
    $("page-prev").addEventListener("click", () => { state.page -= 1; renderTable(inView()); });
    $("page-next").addEventListener("click", () => { state.page += 1; renderTable(inView()); });
    document.querySelectorAll("[data-sort]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.getAttribute("data-sort");
        if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        else {
          state.sortKey = key;
          state.sortDir = ["jobTitle", "contractType", "experienceMinYears", "closingDate"].includes(key) ? "asc" : "desc";
        }
        renderTable(inView());
      });
    });
    $("print").addEventListener("click", () => window.print());
    window.addEventListener("resize", () => Object.values(charts).forEach((c) => c.resize()));
    window.addEventListener("beforeprint", sizeChartsForPrint);
    window.addEventListener("afterprint", () => Object.values(charts).forEach((c) => c.resize()));
  }

  // Charts draw at a fixed pixel size, so they are resized to the A4 landscape column width before printing.
  function sizeChartsForPrint() {
    const pageWidth = 1040;
    const column = Math.floor((pageWidth - 6) / 2) - 20;
    Object.entries(charts).forEach(([id, c]) => {
      const short = $(id).classList.contains("short");
      const wide = $(id).closest(".card.wide");
      c.resize({ width: wide ? pageWidth - 20 : column, height: short ? 125 : 165 });
    });
  }

  function showStatus(message) {
    const node = $("status");
    node.hidden = false;
    node.textContent = message;
    node.className = "status error";
  }

  bindControls();
  fetch("data/dashboard_data.json")
    .then((response) => {
      if (!response.ok) throw new Error("Dashboard data is not available yet (" + response.status + ").");
      return response.json();
    })
    .then((data) => {
      payload = data;
      meta = data.metadata || {};
      renderMeta();
      populateFilters();
      syncControls();
      render();
    })
    .catch((error) => {
      showStatus(error.message + " Run the processing pipeline, then reload this page.");
    });
})();
