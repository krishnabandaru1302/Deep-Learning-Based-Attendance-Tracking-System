const $ = (selector) => document.querySelector(selector);
let activeSession = null;
let modelReady = false;
const api = async (url, options = {}) => {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
};
const localValue = (date) => {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};
const fmt = (value, opts = {}) => value ? new Date(value).toLocaleString([], opts) : '—';
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function setDefaultSchedule() {
  const start = new Date();
  const end = new Date(start.getTime() + 90 * 60000);
  $('#scheduled-start').value = localValue(start);
  $('#scheduled-end').value = localValue(end);
}

function renderSession(session) {
  activeSession = session;
  const active = session?.status === 'active';
  $('#session-form').classList.toggle('hidden', active);
  $('#active-session').classList.toggle('hidden', !active);
  const badge = $('#session-badge');
  badge.className = `session-badge${active ? ' active' : ''}`;
  badge.innerHTML = `<i></i>${active ? 'Session in progress' : session ? 'Last session ended' : 'No active session'}`;
  $('#policy-scope').textContent = active ? 'Rule changes are saved for the next class; this session keeps its original settings.' : 'Saved rules apply to the next class session.';
  $('#attendance-subtitle').textContent = session ? `${session.class_name} · ${session.room_name}` : 'Start a session to see entry and exit activity.';
  if (!session) {
    $('#attendance-rows').innerHTML = '<tr><td colspan="4" class="empty-cell">No active session.</td></tr>';
    $('#event-list').innerHTML = '<p class="empty-cell">Camera events will appear here when the room worker is connected.</p>';
    $('#event-count').textContent = '0 events';
    paintCounts([]);
    return;
  }
  $('#active-class-name').textContent = session.class_name;
  $('#active-room-name').textContent = session.room_name;
  $('#active-session-time').textContent = `${fmt(session.scheduled_start, {dateStyle:'medium',timeStyle:'short'})} – ${fmt(session.scheduled_end, {timeStyle:'short'})}${active ? '' : ' · ended'}`;
  const rows = session.attendance || [];
  paintCounts(rows);
  $('#attendance-rows').innerHTML = rows.length ? rows.map(row => `<tr><td>${escapeHtml(row.display_name)}</td><td>${row.first_entry_at ? fmt(row.first_entry_at,{timeStyle:'short'}) : '—'}</td><td>${row.last_event_at ? `${escapeHtml(row.last_event_type)} · ${fmt(row.last_event_at,{timeStyle:'short'})}` : '—'}</td><td><span class="status-pill ${escapeHtml(row.status)}">${statusLabel(row)}</span></td></tr>`).join('') : '<tr><td colspan="4" class="empty-cell">No one is on the roster yet.</td></tr>';
  const events = session.events || [];
  $('#event-count').textContent = `${events.length} event${events.length === 1 ? '' : 's'}`;
  $('#event-list').innerHTML = events.length ? events.map(event => `<div class="event-row"><span>${fmt(event.occurred_at,{dateStyle:'short',timeStyle:'medium'})}</span><strong>${escapeHtml(event.display_name)}</strong><span class="event-kind">${escapeHtml(event.event_type)}</span><span>${escapeHtml(event.camera_id)}</span></div>`).join('') : '<p class="empty-cell">No camera events have been received for this session.</p>';
}

function statusLabel(row) {
  if (row.status === 'late') return `Late · ${row.late_by_minutes} min`;
  if (row.status === 'away') return 'Away';
  if (row.status === 'left_early') return 'Left early';
  if (row.status === 'absent') return 'Not seen';
  if (row.status === 'present' && row.long_breaks > 0) return `Present · ${row.long_breaks} long break${row.long_breaks === 1 ? '' : 's'}`;
  if (row.status === 'present' && row.late_by_minutes > 0) return `Present · arrived ${row.late_by_minutes} min late`;
  return row.status === 'present' ? 'Present' : row.status;
}

function paintCounts(rows) {
  $('#count-present').textContent = rows.filter(x => x.status === 'present').length;
  $('#count-late').textContent = rows.filter(x => x.status === 'late').length;
  $('#count-away').textContent = rows.filter(x => x.status === 'away' || x.status === 'left_early').length;
  $('#count-absent').textContent = rows.filter(x => x.status === 'absent').length;
}

async function loadPolicy() {
  const policy = await api('/api/settings/attendance');
  $('#late-grace').value = policy.late_grace_minutes;
  $('#early-grace').value = policy.early_leave_grace_minutes;
  $('#return-grace').value = policy.return_grace_minutes;
}

async function loadPeople() {
  const people = await api('/api/people');
  $('#people-count').textContent = people.length;
  $('#people-list').innerHTML = people.length ? people.map(person => `<div class="person-row"><span>${escapeHtml(person.display_name)}</span><button type="button" data-delete="${person.id}">Remove</button></div>`).join('') : '<p class="empty-cell">No students in this room’s roster.</p>';
}

async function loadCamera() {
  const camera = await api('/api/camera/status');
  const connected = camera.connected;
  const configured = camera.source_configured;
  const indicator = $('#camera-status');
  indicator.className = `camera-mode${connected ? ' connected' : ''}`;
  indicator.innerHTML = `<i></i><span>${connected ? 'Camera online' : 'Camera offline'}</span>`;
  $('#camera-detail').textContent = connected ? 'Connected' : configured ? 'Source configured' : 'Not configured';
  $('#camera-source').textContent = camera.worker_available ? 'Room worker ready' : 'Worker unavailable';
  $('#camera-notice-title').textContent = connected ? 'Room camera is connected' : configured ? 'Camera source is set, but no worker is running' : 'Camera service is not connected';
  $('#camera-notice-copy').textContent = connected ? 'Entry and exit events will be recorded from recognized doorway crossings.' : configured ? 'The stream address is present, but automatic attendance needs the camera worker to be running.' : 'Automatic entry and exit logging is paused. Configure the room camera and start its worker on the backend.';
}

async function loadSession() {
  const current = await api('/api/sessions/current');
  const session = current || await api('/api/sessions/latest');
  renderSession(session);
}

async function refreshAll() {
  const results = await Promise.allSettled([loadSession(), loadPeople(), loadCamera()]);
  const failed = results.find(result => result.status === 'rejected');
  if (failed) console.error('Could not refresh attendance workspace:', failed.reason);
}

$('#session-form').addEventListener('submit', async event => {
  event.preventDefault();
  const message = $('#session-message');
  const start = new Date($('#scheduled-start').value);
  const end = new Date($('#scheduled-end').value);
  if (end <= start) { message.textContent = 'Choose an end time after the start time.'; message.className = 'message error'; return; }
  message.textContent = 'Starting session…'; message.className = 'message';
  try {
    await api('/api/sessions', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({class_name:$('#class-name').value,room_name:$('#room-name').value,scheduled_start:start.toISOString(),scheduled_end:end.toISOString()})});
    message.textContent = ''; await loadSession();
  } catch (error) { message.textContent = error.message; message.className = 'message error'; }
});

$('#end-session').addEventListener('click', async () => {
  if (!activeSession) return;
  const message = $('#end-message');
  try { await api(`/api/sessions/${activeSession.id}/end`, {method:'POST'}); message.textContent = ''; await loadSession(); }
  catch (error) { message.textContent = error.message; message.className = 'message error'; }
});

$('#policy-form').addEventListener('submit', async event => {
  event.preventDefault();
  const message = $('#policy-message');
  const policy = {late_grace_minutes:Number($('#late-grace').value),early_leave_grace_minutes:Number($('#early-grace').value),return_grace_minutes:Number($('#return-grace').value)};
  message.textContent = 'Saving rules…'; message.className = 'message';
  try { await api('/api/settings/attendance',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(policy)}); message.textContent = activeSession ? 'Saved for the next class session.' : 'Attendance rules saved.'; }
  catch (error) { message.textContent = error.message; message.className = 'message error'; }
});

$('#enroll-form').addEventListener('submit', async event => {
  event.preventDefault();
  const message = $('#enroll-message');
  if (!modelReady) { message.textContent = 'Photo matching is unavailable until model setup is complete.'; message.className = 'message error'; return; }
  const form = new FormData(event.currentTarget);
  try { await api('/api/people',{method:'POST',body:form}); message.textContent='Student added to the class roster.'; event.currentTarget.reset(); $('#enroll-preview').classList.add('hidden'); $('#enroll-file').textContent='No photo selected'; await loadPeople(); }
  catch (error) { message.textContent=error.message; message.className='message error'; }
});

$('#enroll-image').addEventListener('change', event => {
  const file = event.target.files[0];
  $('#enroll-file').textContent = file?.name || 'No photo selected';
  const preview = $('#enroll-preview');
  if (preview.dataset.url) URL.revokeObjectURL(preview.dataset.url);
  if (file) { preview.dataset.url=URL.createObjectURL(file); preview.src=preview.dataset.url; preview.classList.remove('hidden'); }
  else { preview.removeAttribute('src'); preview.classList.add('hidden'); }
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-delete]');
  if (!button || !confirm('Remove this student and their attendance records?')) return;
  try { await api(`/api/people/${button.dataset.delete}`,{method:'DELETE'}); await loadPeople(); }
  catch (error) { alert(error.message); }
});
$('#refresh').addEventListener('click', refreshAll);

async function init() {
  setDefaultSchedule();
  try { const health=await api('/api/health'); modelReady=health.model_ready; const status=$('#model-status'); status.className=`model-status ${modelReady?'ready':health.status==='ok'?'missing':'error'}`; status.lastElementChild.textContent=modelReady?'Recognition ready':health.model_state==='weights_missing'?'Model weights missing':health.model_state==='dependencies_missing'?'Model setup needed':'Service unavailable'; }
  catch { $('#model-status').className='model-status error'; $('#model-status').lastElementChild.textContent='Service unavailable'; }
  const results=await Promise.allSettled([loadPolicy(),refreshAll()]);
  const failure=results.find(item=>item.status==='rejected');
  if (failure) console.error('Workspace setup failed:',failure.reason);
  window.setInterval(refreshAll,8000);
}
init();
