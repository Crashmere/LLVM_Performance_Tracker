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
