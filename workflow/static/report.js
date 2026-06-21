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
  if (!compilerPair) return;

  const panels = Array.from(document.querySelectorAll("[data-suite-drilldown]"));
  const buttons = Array.from(document.querySelectorAll("[data-suite-drilldown-button]"));
  const placeholder = document.querySelector("[data-suite-drilldown-placeholder]");
  let selectedPanel = null;

  for (const panel of panels) {
    const isSelected = panel.dataset.compilerPair === compilerPair;
    panel.hidden = !isSelected;
    if (isSelected) selectedPanel = panel;
  }

  for (const button of buttons) {
    button.classList.toggle("is-active", button.dataset.suiteDrilldownButton === compilerPair);
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

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-suite-drilldown-button]");
    if (button) {
      showSuiteDrilldown(button.dataset.suiteDrilldownButton, { scroll: true });
    }
  });
}

setupSuiteDrilldown();
