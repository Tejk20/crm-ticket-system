const state = { tickets: [], selectedTicket: null };
const $ = (selector) => document.querySelector(selector);

const featureCopy = {
  triage: ['Automated keyword triage', 'Watch an incoming message become a prioritized, categorized work item.'],
  search: ['Search at the speed of thought', 'Combine full-text search with status and priority filters to isolate the work that matters now.'],
  lifecycle: ['Ticket lifecycle control', 'Move from open to in progress to closed with timestamps that make ownership visible.'],
  collaboration: ['Team context, preserved', 'Internal notes keep handoffs crisp and give every teammate the context to act.']
};

function activateTab(tabName) {
  document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('hidden', panel.id !== `tab-${tabName}`));
  document.querySelectorAll('.tab-button').forEach((button) => button.classList.toggle('tab-active', button.dataset.tabTarget === tabName));
  document.querySelector(`#tab-${tabName}`)?.classList.add('fade-in-up');
  if (tabName === 'app') loadTickets();
}

document.querySelectorAll('[data-tab-target]').forEach((button) => button.addEventListener('click', () => activateTab(button.dataset.tabTarget)));
document.querySelectorAll('[data-feature]').forEach((card) => card.addEventListener('click', () => {
  const [title, copy] = featureCopy[card.dataset.feature];
  $('#feature-preview-title').textContent = title;
  $('#feature-preview-copy').textContent = copy;
  document.querySelectorAll('[data-feature]').forEach((item) => item.classList.remove('border-neon/70', 'bg-neon/10'));
  card.classList.add('border-neon/70', 'bg-neon/10');
}));

function setupAiDraftButton() {
  const noteInput = $('#note-input');
  if (!noteInput || $('#generate-reply')) return;
  const button = document.createElement('button');
  button.id = 'generate-reply';
  button.type = 'button';
  button.className = 'mb-2 rounded-lg border border-neon/30 bg-neon/10 px-3 py-2 text-xs font-bold text-neon transition hover:bg-neon/20 disabled:cursor-wait disabled:opacity-60';
  button.textContent = '🤖 Draft AI Response';
  noteInput.parentElement.insertBefore(button, noteInput);
  button.addEventListener('click', async () => {
    if (!state.selectedTicket) return;
    button.disabled = true;
    button.textContent = '⏳ Drafting...';
    try {
      const result = await request(`/api/tickets/${encodeURIComponent(state.selectedTicket.ticket_id)}/generate-reply`, { method: 'POST' });
      noteInput.value = result.draft_reply;
      showToast('AI Response Generated!');
    } catch (error) {
      showToast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = '🤖 Draft AI Response';
    }
  });
}

setupAiDraftButton();

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[character]));
}

function showToast(message, isError = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = `toast-visible fixed bottom-5 right-5 z-30 max-w-sm rounded-xl border px-4 py-3 text-sm font-semibold shadow-lg ${isError ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`;
  window.setTimeout(() => toast.classList.add('hidden'), 3500);
}

function statusStyle(status) {
  return { Open: 'bg-orange-400/15 text-orange-200', 'In Progress': 'bg-yellow-300/15 text-yellow-200', Closed: 'bg-neon/15 text-neon' }[status] || 'bg-white/10 text-emerald-100/70';
}

function priorityStyle(priority) {
  return { Urgent: 'bg-red-400/20 text-red-200 urgent-pulse', High: 'bg-orange-400/15 text-orange-200', Medium: 'bg-yellow-300/15 text-yellow-200', Low: 'bg-white/10 text-emerald-100/55' }[priority] || 'bg-white/10 text-emerald-100/55';
}

async function request(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((error) => `${error.loc?.at(-1) || 'Field'}: ${error.msg}`).join(' | ') : body.detail;
    throw new Error(detail || 'Something went wrong');
  }
  return body;
}


function renderTickets() {
  const list = $('#ticket-list');
  $('#queue-summary').textContent = `${state.tickets.length} ${state.tickets.length === 1 ? 'ticket' : 'tickets'} in view`;
  if (!state.tickets.length) {
    list.innerHTML = '<div class="flex flex-col items-center p-12 text-center"><div class="mb-3 grid h-12 w-12 place-items-center rounded-full bg-neon/10 text-xl text-neon">⌁</div><p class="font-display font-bold">No tickets found</p><p class="mt-1 text-sm text-emerald-100/45">Try adjusting your search or filters.</p></div>';
    return;
  }
  list.innerHTML = state.tickets.map((ticket) => `
    <button class="group grid w-full gap-3 px-5 py-4 text-left transition hover:bg-neon/5 sm:grid-cols-[105px_1fr_150px_130px_105px] sm:items-center" data-ticket-id="${escapeHtml(ticket.ticket_id)}">
      <span class="font-mono text-xs font-bold text-neon">${escapeHtml(ticket.ticket_id)}</span>
      <span class="min-w-0"><span class="block truncate text-sm font-bold">${escapeHtml(ticket.subject)}</span><span class="mt-1 block truncate text-xs text-emerald-100/45">${escapeHtml(ticket.customer_name)}</span></span>
      <span class="flex flex-wrap gap-1.5"><span class="w-fit rounded-full px-2.5 py-1 text-xs font-bold ${statusStyle(ticket.status)}">${escapeHtml(ticket.status)}</span><span class="w-fit rounded-full px-2.5 py-1 text-xs font-bold ${priorityStyle(ticket.priority)}">${escapeHtml(ticket.priority)}</span></span>
      <span class="text-xs font-semibold text-emerald-100/55">${escapeHtml(ticket.category)}</span>
      <span class="text-xs text-emerald-100/45 sm:text-right">${formatDate(ticket.created_at)}</span>
    </button>`).join('');
  list.querySelectorAll('[data-ticket-id]').forEach((element) => element.addEventListener('click', () => openTicket(element.dataset.ticketId)));
}

async function loadTickets() {
  const params = new URLSearchParams();
  if ($('#status-filter').value) params.set('status', $('#status-filter').value);
  if ($('#search-input').value.trim()) params.set('search', $('#search-input').value.trim());
  if ($('#priority-filter').value) params.set('priority', $('#priority-filter').value);
  $('#ticket-list').innerHTML = '<div class="skeleton space-y-3 p-6"><div class="h-4 w-3/4 rounded bg-slate-100"></div><div class="h-4 w-1/2 rounded bg-slate-100"></div><div class="h-4 w-2/3 rounded bg-slate-100"></div></div>';
  try {
    const [filteredTickets, allTickets] = await Promise.all([request(`/api/tickets?${params}`), request('/api/tickets')]);
    state.tickets = filteredTickets;
    state.allTickets = allTickets;
    $('#total-count').textContent = allTickets.length;
    $('#open-count').textContent = allTickets.filter((ticket) => ticket.status === 'Open').length;
    $('#progress-count').textContent = allTickets.filter((ticket) => ticket.status === 'In Progress').length;
    $('#closed-count').textContent = allTickets.filter((ticket) => ticket.status === 'Closed').length;
    $('#home-total').textContent = allTickets.length;
    renderTickets();
  } catch (error) { showToast(error.message, true); }
}

async function openTicket(ticketId) {
  try {
    state.selectedTicket = await request(`/api/tickets/${encodeURIComponent(ticketId)}`);
    const ticket = state.selectedTicket;
    $('#detail-id').textContent = ticket.ticket_id;
    $('#detail-subject').textContent = ticket.subject;
    $('#detail-customer').textContent = ticket.customer_name;
    $('#detail-email').textContent = ticket.customer_email;
    $('#detail-created').textContent = `Created ${formatDate(ticket.created_at)}`;
    $('#detail-updated').textContent = `Updated ${formatDate(ticket.updated_at)}`;
    $('#detail-description').textContent = ticket.description;
    $('#detail-priority').textContent = ticket.priority;
    $('#detail-priority').className = `rounded-full px-2.5 py-1 text-xs font-bold ${priorityStyle(ticket.priority)}`;
    $('#detail-category').textContent = ticket.category;
    $('#detail-status').value = ticket.status;
    $('#note-input').value = '';
    renderNotes(ticket.notes);
    $('#detail-modal').classList.remove('hidden');
  } catch (error) { showToast(error.message, true); }
}

function renderNotes(notes) {
  $('#note-count').textContent = `${notes.length} ${notes.length === 1 ? 'note' : 'notes'}`;
  $('#notes-list').innerHTML = notes.length ? notes.map((note) => `<div class="rounded-xl border border-slate-200 p-3"><p class="whitespace-pre-wrap text-sm leading-6 text-slate-700">${escapeHtml(note.note_text)}</p><p class="mt-2 text-xs text-slate-400">${formatDate(note.created_at)}</p></div>`).join('') : '<p class="text-sm text-slate-400">No notes yet.</p>';
}

async function updateTicket(payload, successMessage) {
  try {
    await request(`/api/tickets/${encodeURIComponent(state.selectedTicket.ticket_id)}`, { method: 'PUT', body: JSON.stringify(payload) });
    await openTicket(state.selectedTicket.ticket_id);
    await loadTickets();
    showToast(`${state.selectedTicket.ticket_id}: ${successMessage}`);
  } catch (error) { showToast(error.message, true); }
}

$('#ticket-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button');
  button.disabled = true;
  try {
    const created = await request('/api/tickets', { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    form.reset();
    await loadTickets();
    showToast(`${created.ticket_id} created successfully.`);
  } catch (error) { showToast(error.message, true); } finally { button.disabled = false; }
});

$('#search-input').addEventListener('input', loadTickets);
$('#status-filter').addEventListener('change', loadTickets);
$('#priority-filter').addEventListener('change', loadTickets);
$('#close-modal').addEventListener('click', () => $('#detail-modal').classList.add('hidden'));
$('#detail-modal').addEventListener('click', (event) => { if (event.target === $('#detail-modal')) $('#detail-modal').classList.add('hidden'); });
$('#update-status').addEventListener('click', () => updateTicket({ status: $('#detail-status').value }, 'Status updated.'));
document.querySelectorAll('[data-quick-status]').forEach((button) => button.addEventListener('click', () => updateTicket({ status: button.dataset.quickStatus }, `Marked ${button.dataset.quickStatus.toLowerCase()}.`)));
$('#copy-ticket-id').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(state.selectedTicket.ticket_id);
    showToast(`${state.selectedTicket.ticket_id} copied to clipboard.`);
  } catch (error) {
    showToast('Clipboard access is unavailable in this browser.', true);
  }
});
$('#save-note').addEventListener('click', () => {
  const note = $('#note-input').value.trim();
  if (!note) return showToast('Write a note before saving.', true);
  updateTicket({ notes: note }, 'Note saved.');
});

document.addEventListener('keydown', (event) => { if (event.key === 'Escape') $('#detail-modal').classList.add('hidden'); });
loadTickets();
