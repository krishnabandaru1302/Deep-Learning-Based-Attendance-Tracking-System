const $ = (s) => document.querySelector(s);
let currentMatch = null;
let modelReady = false;
const api = async (url, options = {}) => {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
};
const fileLabel = (input, target) => { $(target).textContent = input.files[0]?.name || (input.id === 'match-image' ? 'No snapshot chosen yet' : 'No photo chosen yet'); };
const preview = (input, target) => { const img=$(target); if(img.dataset.url)URL.revokeObjectURL(img.dataset.url); if(input.files[0]){img.dataset.url=URL.createObjectURL(input.files[0]);img.src=img.dataset.url;img.classList.remove('hidden');}else{img.removeAttribute('src');img.classList.add('hidden');} };
$('#enroll-image').addEventListener('change', e => {fileLabel(e.target, '#enroll-file');preview(e.target,'#enroll-preview');});
$('#match-image').addEventListener('change', e => {fileLabel(e.target, '#match-file');preview(e.target,'#match-preview');});

$('#enroll-form').addEventListener('submit', async e => {
  e.preventDefault();
  const button = e.currentTarget.querySelector('button'); const msg = $('#enroll-message');
  if (!modelReady) { msg.textContent = 'Finish setup before adding people.'; msg.className = 'message error'; return; }
  button.disabled = true; msg.className = 'message'; msg.textContent = 'Creating enrollment…';
  try {
    const form = new FormData(e.currentTarget);
    form.set('image', $('#enroll-image').files[0]);
    await api('/api/people', {method:'POST', body:form});
    msg.textContent = 'Added to the class roster. The original photo was not retained.'; e.currentTarget.reset(); fileLabel($('#enroll-image'),'#enroll-file'); preview($('#enroll-image'),'#enroll-preview'); await refresh();
  } catch(err) { msg.textContent = err.message; msg.className = 'message error'; }
  finally { button.disabled = false; }
});

$('#match-form').addEventListener('submit', async e => {
  e.preventDefault(); const button=e.currentTarget.querySelector('button'); const result=$('#match-result');
  if (!modelReady) { result.classList.remove('hidden'); result.innerHTML='<strong>Photo matching needs setup</strong><small>Follow the setup steps before checking classroom snapshots.</small>'; return; }
  button.disabled=true; result.classList.remove('hidden'); result.textContent='Checking this snapshot…'; currentMatch=null;
  try {
    const form=new FormData(); form.set('image',$('#match-image').files[0]);
    currentMatch=await api('/api/matches',{method:'POST',body:form});
    if(!currentMatch.candidate_id){result.innerHTML='<strong>No close match found</strong><small>Nothing was recorded. Check the image or use your usual roll-call process.</small>';return;}
    result.innerHTML=`<strong>Possible match: ${escapeHtml(currentMatch.candidate_name)}</strong><small>Compare the person in the snapshot with the name above. Only confirm if you’re sure.</small><div class="result-actions"><button class="button confirm" id="confirm-match">Add to review list</button><button class="button reject" id="reject-match">Not this person</button></div>`;
    $('#confirm-match').onclick=()=>record(true); $('#reject-match').onclick=()=>{currentMatch=null;result.innerHTML='<strong>Suggestion dismissed</strong><small>No attendance entry was created.</small>';};
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
    $('#people-stat').textContent=people.length;
    $('#pending-count').textContent=records.filter(record=>record.review_status==='pending').length;
    $('#people-list').className='list'+(people.length?'':' empty');
    $('#people-list').innerHTML=people.length?people.map(p=>`<div class="row"><span>${escapeHtml(p.display_name)}<small>Added ${new Date(p.created_at).toLocaleDateString()}</small></span><button data-delete="${p.id}">Delete</button></div>`).join(''):'<span class="empty-icon" aria-hidden="true">☼</span><span>No one here yet. Add your first participant above.</span>';
    $('#attendance-list').className='list'+(records.length?'':' empty');
    $('#attendance-list').innerHTML=records.length?records.map(r=>`<div class="row"><span>${escapeHtml(r.display_name)}<small>${new Date(r.observed_at).toLocaleString()}</small></span>${r.review_status==='pending'?`<span class="result-actions"><button class="button confirm" data-review="confirmed" data-id="${r.id}">Confirm</button><button class="button reject" data-review="rejected" data-id="${r.id}">Reject</button></span>`:`<span class="badge">${escapeHtml(r.review_status)}</span>`}</div>`).join(''):'<span class="empty-icon empty-clock" aria-hidden="true">◷</span><span>Reviewed check-ins will appear here.</span>';
  }catch(err){$('#people-list').className='list empty';$('#people-list').textContent=`Could not load people: ${err.message}`;}
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
    const labels={ready:'Photo matching ready',dependencies_missing:'Finish setup',weights_missing:'Finish setup'};
    const details={dependencies_missing:['One quick setup step','The photo-matching tools need to be installed before you can add people or take attendance.'],weights_missing:['Turn on photo matching','The matching files aren’t installed yet. Follow the setup steps to add people and take attendance.']};
    indicator.lastChild.textContent=labels[health.model_state]||'Model unavailable';
    const notice=$('#setup-notice');
    notice.classList.toggle('hidden',modelReady);
    if(!modelReady){const [title,copy]=details[health.model_state]||['Recognition is unavailable','Check that the local service is running.'];$('#setup-title').textContent=title;$('#setup-copy').textContent=copy;}
  }catch{
    modelReady=false;
    indicator.className='model-status error';
    indicator.lastChild.textContent='Service unavailable';
    $('#setup-notice').classList.remove('hidden');
    $('#setup-title').textContent='Service unavailable';
    $('#setup-copy').textContent='We can’t reach the attendance service right now. Check that it’s running, then refresh this page.';
  }
  document.querySelectorAll('#enroll-form .primary, #match-form .primary').forEach(button=>{
    button.disabled=!modelReady;
    button.title=modelReady?'':'Finish setup to use photo matching.';
  });
}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
refresh();
refreshModelStatus();
setInterval(refreshModelStatus,30000);
