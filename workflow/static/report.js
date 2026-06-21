function applyTableFilters(tableId) {
  const table = document.getElementById(tableId);
  if (!table || !table.tBodies.length) return;
  const search = document.querySelector(`[data-search="${tableId}"]`);
  const query = search ? search.value.toLowerCase() : "";
  const filters = Array.from(document.querySelectorAll(`[data-filter="${tableId}"]`));
  let visibleRows = 0;
  for (const row of table.tBodies[0].rows) {
    let visible = row.innerText.toLowerCase().includes(query);
    for (const filter of filters) {
      const value = filter.value;
      if (!value) continue;
      const column = Number(filter.dataset.column);
      const cellText = row.cells[column] ? row.cells[column].innerText : "";
      if (cellText !== value) visible = false;
    }
    row.style.display = visible ? "" : "none";
    if (visible) visibleRows += 1;
  }
  const count = document.querySelector(`[data-count="${tableId}"]`);
  if (count) {
    const totalRows = table.tBodies[0].rows.length;
    count.textContent = `${visibleRows} of ${totalRows} rows`;
  }
}

document.addEventListener("input", (event) => {
  const tableId = event.target.dataset.search || event.target.dataset.filter;
  if (tableId) applyTableFilters(tableId);
});

function showSuiteDrilldown(compilerPair, options = {}) {
  const panels = Array.from(document.querySelectorAll("[data-suite-drilldown]"));
  const selector = document.querySelector("[data-suite-drilldown-select]");
  const placeholder = document.querySelector("[data-suite-drilldown-placeholder]");
  let selectedPanel = null;

  for (const panel of panels) {
    const isSelected = Boolean(compilerPair) && panel.dataset.compilerPair === compilerPair;
    panel.hidden = !isSelected;
    if (isSelected) selectedPanel = panel;
  }

  if (selector) {
    selector.value = selectedPanel ? compilerPair : "";
  }

  if (placeholder) placeholder.hidden = Boolean(selectedPanel);
  if (!selectedPanel) return;

  resizePlotlyGraphs(selectedPanel);
  if (options.scroll) {
    selectedPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function resizePlotlyGraphs(container) {
  if (!window.Plotly || !window.Plotly.Plots) return;
  for (const graph of container.querySelectorAll(".plotly-graph-div")) {
    window.Plotly.Plots.resize(graph);
  }
}

function setupSuiteDrilldown() {
  const matrix = document.getElementById("compiler_pair_matrix");
  if (matrix && typeof matrix.on === "function") {
    matrix.on("plotly_click", (event) => {
      const point = event.points && event.points[0];
      if (point && point.y) {
        showSuiteDrilldown(String(point.y), { scroll: true });
      }
    });
  }

  document.addEventListener("change", (event) => {
    if (event.target.matches("[data-suite-drilldown-select]")) {
      showSuiteDrilldown(event.target.value, { scroll: true });
    }
  });
}

setupSuiteDrilldown();
