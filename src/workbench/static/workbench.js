"use strict";
const $ = (id) => document.getElementById(id);
let user = null,
  busy = false,
  loadOffset = 0,
  exceptionOffset = 0,
  detailId = null;
const pageSize = 25;
function text(id, value) {
  $(id).textContent = value ?? "";
}
function node(tag, value, cls) {
  const el = document.createElement(tag);
  el.textContent = value ?? "";
  if (cls) el.className = cls;
  return el;
}
function announce(message, error = false) {
  text("notice", message);
  $("notice").className = error ? "error" : "";
}
function signedOut() {
  user = null;
  $("workbench").hidden = true;
  $("identity").hidden = true;
  $("login-panel").hidden = false;
  $("token").value = "";
  $("metrics").replaceChildren();
  $("exceptions").replaceChildren();
  clearDetail();
  $("run-reason").value = "";
  $("ack-reason").value = "";
}
async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers:
      body === undefined
        ? {}
        : {
            "Content-Type": "application/json",
            "X-CSRF-Token": user?.csrf_token ?? "",
          },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401) signedOut();
    const error = new Error(result.detail || "Request failed.");
    error.status = response.status;
    throw error;
  }
  return result;
}
async function action(work) {
  if (busy) return;
  busy = true;
  $("workbench").inert = true;
  $("login").inert = true;
  $("logout").disabled = true;
  $("workbench").setAttribute("aria-busy", "true");
  announce("Loading evidence…");
  try {
    await work();
    if ($("notice").textContent === "Loading evidence…") announce("");
  } catch (error) {
    if ($("freshness").textContent === "Checking…") {
      text("freshness", "Status unavailable");
      $("freshness").className = "badge warn";
    }
    announce(
      error.message || "Unable to load evidence. Refresh to try again.",
      true,
    );
  } finally {
    busy = false;
    $("workbench").inert = false;
    $("login").inert = false;
    $("logout").disabled = false;
    $("workbench").setAttribute("aria-busy", "false");
  }
}
function clearDetail() {
  detailId = null;
  $("detail-content").hidden = true;
  $("detail-empty").hidden = false;
  text("detail-title", "Inspect a finding");
  for (const id of [
    "source",
    "evidence",
    "rule",
    "audit",
    "evidence-id",
    "resolution",
    "detail-state",
  ])
    text(id, "");
  $("acknowledge").hidden = true;
  $("ack-reason").value = "";
}
function clearReport() {
  $("metrics").replaceChildren();
  $("accounting").replaceChildren();
  text("publication", "");
  text("lineage", "");
  $("packet").hidden = true;
  $("packet").removeAttribute("href");
  text("report-state", "No saved reconciliation for this selection.");
}
async function enter() {
  $("login-panel").hidden = true;
  $("identity").hidden = false;
  $("workbench").hidden = false;
  text("actor", user.actor + " / " + user.role);
  $("operations").hidden = user.role !== "operator";
  const snapshots = await api("/api/snapshots");
  $("snapshot").replaceChildren();
  for (const item of snapshots.items) {
    const option = node("option", item.label + " · " + item.business_date);
    option.value = item.id;
    $("snapshot").append(option);
  }
  $("business-date").value =
    snapshots.items[0]?.business_date || new Date().toISOString().slice(0, 10);
  loadOffset = 0;
  exceptionOffset = 0;
  $("scope").value = "load";
  $("status").value = "unresolved";
  text("run-result", "");
  await refresh();
}
async function refresh(preferred) {
  const day = $("business-date").value;
  if (!day) throw new Error("Choose a business date.");
  const previous = preferred || $("load").value;
  clearReport();
  clearDetail();
  $("exceptions").replaceChildren();
  text("exception-count", "");
  text("exceptions-empty", "");
  text("exception-page", "");
  $("exceptions-prev").disabled = true;
  $("exceptions-next").disabled = true;
  text("freshness", "Checking…");
  text("freshness-detail", "");
  const [loads, feed] = await Promise.all([
    api(
      `/api/loads?business_date=${encodeURIComponent(day)}&limit=${pageSize}&offset=${loadOffset}`,
    ),
    api(`/api/freshness?business_date=${encodeURIComponent(day)}`),
  ]);
  $("load").replaceChildren();
  for (const item of loads.items) {
    const option = node(
      "option",
      `${item.load_id.slice(0, 8)} · ${item.status.replaceAll("_", " ")} ${item.is_current ? "· current" : ""} · ${item.started_at} UTC`,
    );
    option.value = item.load_id;
    $("load").append(option);
  }
  if (!loads.items.length) {
    const option = node("option", "No recorded loads on this page");
    option.value = "";
    $("load").append(option);
  }
  if (loads.items.some((item) => item.load_id === previous))
    $("load").value = previous;
  $("loads-prev").disabled = loadOffset === 0;
  $("loads-next").disabled = loads.items.length < pageSize;
  text(
    "load-page",
    loads.items.length
      ? `Attempts ${loadOffset + 1}–${loadOffset + loads.items.length} · newest first`
      : "No attempts found",
  );
  text(
    "freshness",
    feed.failed_refresh
      ? "Failed refresh"
      : {
          available: "Date published",
          stale: "Feed overdue",
          not_due: "Feed not yet due",
        }[feed.status],
  );
  $("freshness").className =
    "badge" +
    (feed.failed_refresh ? " bad" : feed.status === "stale" ? " warn" : "");
  text(
    "freshness-detail",
    `For ${feed.business_date} · due ${feed.deadline_utc} · checked ${feed.observed_at}${feed.failed_refresh ? ". Previous publication retained if available." : ". Availability applies to the selected date."}`,
  );
  exceptionOffset = 0;
  await selection();
}
async function selection() {
  clearReport();
  clearDetail();
  $("exceptions").replaceChildren();
  text("exception-count", "");
  text("exceptions-empty", "");
  text("exception-page", "");
  $("exceptions-prev").disabled = true;
  $("exceptions-next").disabled = true;
  const selected = $("load").value;
  if (selected) {
    try {
      const report = await api(`/api/loads/${selected}/reconciliation`),
        summary = report.summary;
      text(
        "publication",
        report.is_current ? "Current publication" : "Historical publication",
      );
      $("publication").className = "badge" + (report.is_current ? "" : " warn");
      text(
        "report-state",
        `${report.business_date} · ${report.requested_status.replaceAll("_", " ")}${report.requested_status === "no_op" ? ". Reuses saved evidence; this attempt did not replace current data." : ". Saved totals for this publication."}`,
      );
      const cards = [
        ["Source rows", summary.raw_rows, "Captured input"],
        ["Accepted rows", summary.accepted_rows, "Published activities"],
        [
          "Completed count",
          `${summary.source_completed_count} → ${summary.curated_completed_count}`,
          "Source → curated",
        ],
        [
          "Completed units",
          `${summary.source_completed_units ?? "Unknown"} → ${summary.curated_completed_units ?? "Unknown"}`,
          "Source → curated",
        ],
      ];
      for (const [label, value, caption] of cards) {
        const card = node(
          "div",
          "",
          "metric" + (label === "Accepted rows" ? " accent" : ""),
        );
        card.append(
          node("label", label),
          node("strong", value),
          node("small", caption),
        );
        $("metrics").append(card);
      }
      $("accounting").append(
        node("span", `${summary.excluded_duplicate_rows} duplicate extras`),
        node("span", `${summary.excluded_invalid_rows} invalid rows`),
        node(
          "span",
          summary.accounting_verified
            ? "✓ All rows accounted for"
            : "Accounting unverified",
        ),
      );
      for (const reason of summary.primary_reasons)
        $("accounting").append(
          node("span", `${reason.rule_id}: ${reason.rows}`),
        );
      if (!summary.source_status_complete)
        $("accounting").append(
          node(
            "span",
            `${summary.unknown_status_rows} unknown statuses; completed count is incomplete`,
          ),
        );
      if (!summary.source_units_complete)
        $("accounting").append(
          node(
            "span",
            `${summary.unknown_unit_rows} unreadable units; source total is unknown`,
          ),
        );
      text(
        "lineage",
        `Attempt: ${report.requested_load_id}\nPublication: ${report.publication_load_id} (${report.publication_status})`,
      );
      $("packet").href = `/api/loads/${selected}/evidence`;
      $("packet").hidden = false;
    } catch (error) {
      if (error.status !== 404) throw error;
      text(
        "report-state",
        "This attempt has no saved reconciliation. Inspect its findings below; previous publications remain selectable.",
      );
    }
  }
  await findings();
}
async function findings() {
  clearDetail();
  $("exceptions").replaceChildren();
  text("exceptions-empty", "");
  const query = new URLSearchParams({
    business_date: $("business-date").value,
    status: $("status").value,
    limit: pageSize,
    offset: exceptionOffset,
  });
  let result = { items: [] };
  if ($("scope").value === "date" || $("load").value) {
    if ($("scope").value === "load") query.set("load_id", $("load").value);
    result = await api("/api/exceptions?" + query);
  }
  for (const item of result.items) {
    const row = document.createElement("tr");
    row.dataset.id = item.exception_id;
    const rule = node("td", item.rule_id);
    rule.append(
      node(
        "small",
        item.field_name ||
          (item.row_ordinal == null ? "Load-level finding" : "Whole row"),
      ),
    );
    const state = node("td");
    state.append(
      node(
        "span",
        item.status,
        "badge" + (item.status === "open" ? " warn" : ""),
      ),
    );
    const cell = node("td"),
      button = node("button", "Inspect", "secondary");
    button.setAttribute(
      "aria-label",
      `Inspect ${item.rule_id} row ${item.row_ordinal ?? "load"}`,
    );
    button.onclick = () => action(() => inspect(item.exception_id));
    cell.append(button);
    row.append(node("td", item.row_ordinal ?? "—"), rule, state, cell);
    $("exceptions").append(row);
  }
  text("exception-count", `${result.items.length} on this page`);
  if (!result.items.length)
    text("exceptions-empty", "No findings match these filters.");
  text(
    "exception-page",
    result.items.length
      ? `Findings ${exceptionOffset + 1}–${exceptionOffset + result.items.length}`
      : "",
  );
  $("exceptions-prev").disabled = exceptionOffset === 0;
  $("exceptions-next").disabled = result.items.length < pageSize;
}
async function inspect(id) {
  clearDetail();
  const detail = await api(`/api/exceptions/${id}`);
  detailId = id;
  $("detail-content").hidden = false;
  $("detail-empty").hidden = true;
  for (const row of $("exceptions").children)
    row.classList.toggle("selected", row.dataset.id === id);
  text(
    "detail-title",
    `${detail.rule_id} · row ${detail.row_ordinal ?? "load"}`,
  );
  text(
    "detail-state",
    `${detail.status.toUpperCase()} · rule set ${detail.rule_set_version}`,
  );
  text(
    "resolution",
    detail.resolved_by_load_id
      ? `Resolved by ${detail.resolved_by_load_id} · ${detail.resolution_reason}. Original evidence retained.`
      : detail.acknowledged_by
        ? `Reviewed by ${detail.acknowledged_by}: ${detail.acknowledgement_reason}. Still unresolved.`
        : "Awaiting source correction or review.",
  );
  for (const [id, value] of [
    ["source", detail.untrusted_source],
    ["evidence", detail.untrusted_evidence],
    ["rule", detail.rule_definition],
    ["audit", detail.events],
  ])
    text(id, JSON.stringify(value ?? "No captured value", null, 2));
  text("evidence-id", detail.evidence_id);
  $("acknowledge").hidden =
    user.role !== "operator" || detail.status !== "open";
}
$("login").onsubmit = (event) => {
  event.preventDefault();
  action(async () => {
    const token = $("token").value;
    $("token").value = "";
    user = await api("/api/session", { token });
    await enter();
  });
};
$("logout").onclick = () =>
  action(async () => {
    await api("/api/session/logout", {});
    signedOut();
    announce("Signed out.");
  });
$("selection").onsubmit = (event) => {
  event.preventDefault();
  action(() => refresh());
};
$("business-date").onchange = () =>
  action(async () => {
    loadOffset = 0;
    $("load").replaceChildren();
    await refresh();
  });
$("load").onchange = () =>
  action(async () => {
    exceptionOffset = 0;
    await selection();
  });
for (const id of ["scope", "status"])
  $(id).onchange = () =>
    action(async () => {
      exceptionOffset = 0;
      await findings();
    });
for (const [id, delta] of [
  ["loads-prev", -pageSize],
  ["loads-next", pageSize],
])
  $(id).onclick = () =>
    action(async () => {
      loadOffset += delta;
      await refresh();
    });
for (const [id, delta] of [
  ["exceptions-prev", -pageSize],
  ["exceptions-next", pageSize],
])
  $(id).onclick = () =>
    action(async () => {
      exceptionOffset += delta;
      await findings();
    });
$("acknowledge").onsubmit = (event) => {
  event.preventDefault();
  action(async () => {
    const id = detailId;
    await api(`/api/exceptions/${id}/acknowledge`, {
      reason: $("ack-reason").value,
    });
    await findings();
    await inspect(id);
    announce("Review recorded. Acknowledgement does not resolve the finding.");
  });
};
$("run").onsubmit = (event) => {
  event.preventDefault();
  action(async () => {
    text("run-result", "Running snapshot. Wait for the recorded result…");
    let result;
    try {
      result = await api("/api/activity-runs", {
        snapshot: $("snapshot").value,
        business_date: $("business-date").value,
        reason: $("run-reason").value,
      });
    } catch (error) {
      text(
        "run-result",
        "No result received. Refresh load history before retrying; the server may have recorded an attempt.",
      );
      throw error;
    }
    text(
      "run-result",
      `${result.status.replaceAll("_", " ")} · ${result.load_id}${result.status === "failed" ? " · " + result.message : ""}`,
    );
    loadOffset = 0;
    await refresh(result.load_id);
    announce(
      result.status === "failed"
        ? "Load failed. Previous publication retained; inspect the recorded finding."
        : "Run recorded. Totals and findings refreshed.",
      result.status === "failed",
    );
  });
};
action(async () => {
  try {
    user = await api("/api/session");
  } catch (error) {
    if (error.status === 401) {
      announce("");
      return;
    }
    throw error;
  }
  await enter();
});
