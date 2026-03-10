const stages = ["lead", "contacted", "proposal", "won"];
const stageLabels = {
  lead: "Leads",
  contacted: "Contato",
  proposal: "Proposta",
  won: "Fechado",
};

const sectionMeta = {
  dashboard: ["Dashboard", "Visão geral — Março 2026"],
  clients: ["Clientes", "Cadastros, contratos e histórico"],
  kanban: ["Funil", "Pipeline comercial em Kanban"],
  interactions: ["Atendimentos", "Reunião, e-mail, ligação e WhatsApp"],
  tasks: ["Tarefas", "Gestão de atividades da equipe"],
  finance: ["Financeiro", "Mensalidades e status de pagamento"],
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(`Falha em ${path}`);
  return response.json();
}

function money(value) {
  return `R$ ${Number(value || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
}

function formatType(type) {
  return { reuniao: "Reunião", email: "E-mail", ligacao: "Ligação", whatsapp: "WhatsApp" }[type] || type;
}

async function loadDashboard() {
  const [data, tasks, interactions] = await Promise.all([
    api("/api/dashboard"),
    api("/api/tasks"),
    api("/api/interactions?limit=6"),
  ]);

  document.getElementById("dashboardCards").innerHTML = `
    <article class="metric"><small>MRR</small><h2>${money(data.mrr)}</h2><span>Receita recorrente</span></article>
    <article class="metric"><small>Clientes Ativos</small><h2>${data.active_clients}</h2><span>Contratos vigentes</span></article>
    <article class="metric"><small>Inadimplentes</small><h2>${data.overdue_count}</h2><span>Faturas em aberto</span></article>
    <article class="metric alert"><small>Em Atraso</small><h2>${money(data.overdue_total)}</h2><span>Valor vencido</span></article>
  `;

  const pending = tasks.filter((t) => !t.done).slice(0, 6);
  document.getElementById("pendingTasks").innerHTML = pending.length
    ? pending
        .map(
          (t) => `
          <div class="list li">
            <div class="item-title"><span class="dot">•</span>${t.title}</div>
            <div class="item-sub">${t.client_name || "Sem cliente"} · ${t.assignee}</div>
          </div>
        `
        )
        .join("")
    : '<p class="item-sub">Nenhuma tarefa pendente.</p>';

  document.getElementById("latestInteractions").innerHTML = interactions.length
    ? interactions
        .map(
          (i) => `
          <div class="list li">
            <div class="item-title">${i.client_name}</div>
            <div class="item-sub">${formatType(i.type)} · ${i.summary}</div>
          </div>
        `
        )
        .join("")
    : '<p class="item-sub">Sem atendimentos recentes.</p>';
}

async function loadClients(query = "") {
  const clients = await api(`/api/clients?q=${encodeURIComponent(query)}`);
  document.getElementById("clientList").innerHTML = clients
    .map(
      (c) => `<li><button onclick="showClient(${c.id})">${c.name} <span class="badge">${c.company}</span></button></li>`
    )
    .join("");

  document.getElementById("financeList").innerHTML = clients
    .map(
      (c) => `<div class="list li"><div class="item-title">${c.name}</div><div class="item-sub">${c.company} · ${money(c.recurring_fee)}</div></div>`
    )
    .join("");
}

async function showClient(id) {
  const c = await api(`/api/clients/${id}`);
  document.getElementById("clientProfile").innerHTML = `
    <h3>${c.name} — ${c.company}</h3>
    <p><strong>Contato:</strong> ${c.email} · ${c.phone}</p>
    <p><strong>Mensalidade:</strong> ${money(c.recurring_fee)} · <strong>Status:</strong> ${c.status}</p>
    <h3>Histórico</h3>
    <ul class="list">${c.interactions
      .map((i) => `<li>${formatType(i.type)} · ${i.summary}</li>`)
      .join("") || "<li>Sem histórico</li>"}</ul>
    <h3>Financeiro</h3>
    <ul class="list">${c.payments
      .map((p) => `<li>${p.reference_month} · ${money(p.amount)} · ${p.status}</li>`)
      .join("") || "<li>Sem pagamentos</li>"}</ul>
  `;
}

async function loadTasks() {
  const tasks = await api("/api/tasks");
  document.getElementById("taskList").innerHTML = tasks
    .map(
      (t) => `<li>
        <label><input type="checkbox" ${t.done ? "checked" : ""} onchange="toggleTask(${t.id}, this.checked)"> ${t.title}</label>
        <div class="item-sub">${t.assignee} · ${t.priority} · ${t.client_name || "Sem cliente"}</div>
      </li>`
    )
    .join("");
}

async function loadDeals() {
  const deals = await api("/api/deals");
  document.getElementById("kanbanBoard").innerHTML = stages
    .map((stage) => {
      const cards = deals
        .filter((d) => d.stage === stage)
        .map(
          (d) => `<div class="deal" draggable="true" ondragstart="dragDeal(event, ${d.id})">${d.title}<br><small>${d.client_name} · ${money(d.value)}</small></div>`
        )
        .join("");
      return `<div class="column" ondrop="dropDeal(event, '${stage}')" ondragover="allowDrop(event)"><h4>${stageLabels[stage]}</h4>${cards}</div>`;
    })
    .join("");
}

async function loadInteractions() {
  const interactions = await api("/api/interactions?limit=30");
  document.getElementById("interactionList").innerHTML = interactions
    .map(
      (i) => `<div class="list li"><div class="item-title">${i.client_name}</div><div class="item-sub">${formatType(i.type)} · ${i.summary}</div></div>`
    )
    .join("");
}

async function toggleTask(id, done) {
  await api(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ done }) });
  await loadTasks();
  await loadDashboard();
}

function allowDrop(ev) {
  ev.preventDefault();
}

function dragDeal(ev, id) {
  ev.dataTransfer.setData("dealId", id);
}

async function dropDeal(ev, stage) {
  ev.preventDefault();
  const id = ev.dataTransfer.getData("dealId");
  await api(`/api/deals/${id}/stage`, { method: "PATCH", body: JSON.stringify({ stage }) });
  await loadDeals();
}

function activateTab(tab) {
  document.querySelectorAll(".menu-item").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.getElementById(`tab-${tab}`).classList.add("active");
  const [title, subtitle] = sectionMeta[tab];
  document.getElementById("sectionTitle").textContent = title;
  document.getElementById("sectionSubtitle").textContent = subtitle;
}

window.showClient = showClient;
window.toggleTask = toggleTask;
window.allowDrop = allowDrop;
window.dragDeal = dragDeal;
window.dropDeal = dropDeal;

document.getElementById("menu").addEventListener("click", (e) => {
  if (e.target.classList.contains("menu-item")) activateTab(e.target.dataset.tab);
});

document.getElementById("searchClient").addEventListener("input", (e) => loadClients(e.target.value));

document.getElementById("clientForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  payload.recurring_fee = Number(payload.recurring_fee || 0);
  await api("/api/clients", { method: "POST", body: JSON.stringify(payload) });
  e.target.reset();
  await loadClients();
  await loadDashboard();
});

document.getElementById("taskForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
  e.target.reset();
  await loadTasks();
  await loadDashboard();
});

document.getElementById("dealForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  payload.value = Number(payload.value || 0);
  payload.stage = "lead";
  await api("/api/deals", { method: "POST", body: JSON.stringify(payload) });
  e.target.reset();
  await loadDeals();
});

document.getElementById("interactionForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  payload.client_id = Number(payload.client_id);
  await api("/api/interactions", { method: "POST", body: JSON.stringify(payload) });
  e.target.reset();
  await loadInteractions();
  await loadDashboard();
});

document.getElementById("paymentForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = Object.fromEntries(new FormData(e.target).entries());
  payload.client_id = Number(payload.client_id);
  payload.amount = Number(payload.amount || 0);
  await api("/api/payments", { method: "POST", body: JSON.stringify(payload) });
  e.target.reset();
  await loadDashboard();
});

Promise.all([loadDashboard(), loadClients(), loadTasks(), loadDeals(), loadInteractions()]);
