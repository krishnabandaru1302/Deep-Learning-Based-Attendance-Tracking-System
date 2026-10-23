const $ = (s) => document.querySelector(s);
let currentMatch = null;
let modelReady = false;
const api = async (url, options = {}) => {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
};
const fileLabel = (input, target) => { $(target).textContent = input.files[0]?.name || 'No image selected'; };
const preview = (input, target) => { const img=$(target); if(img.dataset.url)URL.revokeObjectURL(img.dataset.url); if(input.files[0]){img.dataset.url=URL.createObjectURL(input.files[0]);img.src=img.dataset.url;img.classList.remove('hidden');}else{img.removeAttribute('src');img.classList.add('hidden');} };
$('#enroll-image').addEventListener('change', e => {fileLabel(e.target, '#enroll-file');preview(e.target,'#enroll-preview');});
$('#match-image').addEventListener('change', e => {fileLabel(e.target, '#match-file');preview(e.target,'#match-preview');});

$('#enroll-form').addEventListener('submit', async e => {
  e.preventDefault();
  const button = e.currentTarget.querySelector('button'); const msg = $('#enroll-message');
  if (!modelReady) { msg.textContent = 'Complete model setup before enrolling participants.'; msg.className = 'message error'; return; }
  button.disabled = true; msg.className = 'message'; msg.textContent = 'Creating enrollment…';
  try {
    const form = new FormData(e.currentTarget);
    form.set('image', $('#enroll-image').files[0]);
    await api('/api/people', {method:'POST', body:form});
    msg.textContent = 'Enrollment saved. The source image was not retained.'; e.currentTarget.reset(); fileLabel($('#enroll-image'),'#enroll-file'); await refresh();
  } catch(err) { msg.textContent = err.message; msg.className = 'message error'; }
  finally { button.disabled = false; }
});

$('#match-form').addEventListener('submit', async e => {
  e.preventDefault(); const button=e.currentTarget.querySelector('button'); const result=$('#match-result');
  if (!modelReady) { result.classList.remove('hidden'); result.innerHTML='<strong>Model setup required</strong><small>Install the recognition dependencies and add the VGGFace weights to enable check-ins.</small>'; return; }
  button.disabled=true; result.classList.remove('hidden'); result.textContent='Analyzing image…'; currentMatch=null;
  try {
    const form=new FormData(); form.set('image',$('#match-image').files[0]);
    currentMatch=await api('/api/matches',{method:'POST',body:form});
    if(!currentMatch.candidate_id){result.innerHTML='<strong>No candidate above the configured cutoff</strong><small>No record was created. Use a standard non-biometric attendance process.</small>';return;}
    result.innerHTML=`<strong>Suggested candidate: ${escapeHtml(currentMatch.candidate_name)}</strong><small>Cosine distance ${currentMatch.distance.toFixed(3)} · threshold ${currentMatch.threshold}. Lower distance means a closer match.</small><div>Review the image and identity before continuing.</div><div class="result-actions"><button class="button confirm" id="confirm-match">Send to review queue</button><button class="button reject" id="reject-match">Reject suggestion</button></div>`;
    $('#confirm-match').onclick=()=>record(true); $('#reject-match').onclick=()=>{currentMatch=null;result.innerHTML='<strong>Suggestion rejected</strong><small>No attendance record was created.</small>';};
  } catch(err){result.innerHTML=`<strong>Could not complete match</strong><small>${escapeHtml(err.message)}</small>`;}
  finally{button.disabled=false;}
});

async function record(confirmed){
  if(!confirmed||!currentMatch?.candidate_id)return;
  try{const data=new FormData();data.set('person_id',currentMatch.candidate_id);data.set('distance',currentMatch.distance);await api('/api/attendance',{method:'POST',body:data});$('#match-result').innerHTML='<strong>Attendance queued for review</strong><small>Confirm or reject the pending entry in the queue below.</small>';currentMatch=null;await refresh();}
  catch(err){$('#match-result').innerHTML=`<strong>Could not save attendance</strong><small>${escapeHtml(err.message)}</small>`;}
}

async function refresh(){
  try{
    const [people,records]=await Promise.all([api('/api/people'),api('/api/attendance')]);
    $('#people-count').textContent=people.length;
    $('#people-list').className='list'+(people.length?'':' empty');
    $('#people-list').innerHTML=people.length?people.map(p=>`<div class="row"><span>${escapeHtml(p.display_name)}<small>Added ${new Date(p.created_at).toLocaleDateString()}</small></span><button data-delete="${p.id}">Delete</button></div>`).join(''):'No participants enrolled yet.';
    $('#attendance-list').className='list'+(records.length?'':' empty');
    $('#attendance-list').innerHTML=records.length?records.map(r=>`<div class="row"><span>${escapeHtml(r.display_name)}<small>${new Date(r.observed_at).toLocaleString()} · distance ${Number(r.distance).toFixed(3)}</small></span>${r.review_status==='pending'?`<span class="result-actions"><button class="button confirm" data-review="confirmed" data-id="${r.id}">Confirm</button><button class="button reject" data-review="rejected" data-id="${r.id}">Reject</button></span>`:`<span class="badge">${escapeHtml(r.review_status)}</span>`}</div>`).join(''):'No attendance records yet.';
  }catch(err){$('#people-list').textContent=err.message;}
}
document.addEventListener('click',async e=>{
  if(e.target.matches('[data-delete]')){if(!confirm('Delete this participant and their attendance records?'))return;try{await api(`/api/people/${e.target.dataset.delete}`,{method:'DELETE'});await refresh();}catch(err){alert(err.message);}}
  if(e.target.matches('[data-review]')){try{await api(`/api/attendance/${e.target.dataset.id}/review`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:e.target.dataset.review})});await refresh();}catch(err){alert(err.message);}}
});
$('#refresh').addEventListener('click',refresh);
async function refreshModelStatus(){
  const indicator=$('#model-status');
  try{
    const health=await api('/api/health');
    modelReady=health.model_ready;
    indicator.className=`model-status ${health.model_ready?'ready':'missing'}`;
    const labels={ready:'Model ready',dependencies_missing:'Install model dependencies',weights_missing:'Add model weights'};
    indicator.lastChild.textContent=labels[health.model_state]||'Model unavailable';
  }catch{
    modelReady=false;
    indicator.className='model-status error';
    indicator.lastChild.textContent='Service unavailable';
  }
  document.querySelectorAll('#enroll-form .primary, #match-form .primary').forEach(button=>{
    button.disabled=!modelReady;
    button.title=modelReady?'':'Complete model setup to enable this action.';
  });
}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
refresh();
refreshModelStatus();
setInterval(refreshModelStatus,30000);
