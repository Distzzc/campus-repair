'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const states = {waiting:'待分配',assigned:'待接单',working:'处理中',confirm:'待确认',completed:'已完成',cancelled:'已取消'};
const categories = ['水电','网络','家具','空调','其他'];
const priorities = {normal:'普通',high:'优先',urgent:'紧急'};
const roles = {student:'学生',admin:'后勤管理员',worker:'维修人员'};
const actionNames = {create:'提交报修',assign:'分配维修人员',accept:'维修接单',finish:'提交维修结果',confirm:'确认完成',reopen:'反馈未解决',cancel:'取消报修',note:'补充记录',classify:'调整工单信息',attachment:'添加现场图片'};
let csrf = '', user = null, currentTicket = null, listPage = 1, listFilter = {}, pendingAction = '';
const freshKey = () => crypto.randomUUID();
const date = value => value ? new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value)) : '—';
function toast(message) { const element = $('#toast'); element.textContent = message; element.classList.add('visible'); setTimeout(() => element.classList.remove('visible'),4000); }
async function api(path, options = {}) {
  const {data, key, ...rest} = options;
  const headers = {'X-CSRF-Token':csrf, ...(options.headers || {})};
  let body;
  if (data instanceof FormData) body = data;
  else if (data !== undefined) { headers['Content-Type']='application/json'; body=JSON.stringify(data); }
  if (key) headers['Idempotency-Key']=key;
  let response;
  try { response = await fetch('/api/v1'+path, {...rest,headers,body,credentials:'same-origin',cache:'no-store'}); }
  catch (_) { throw new Error('网络连接失败，请检查后重试，已填写内容会保留。'); }
  let payload;
  try { payload = await response.json(); } catch (_) { throw new Error('服务暂时不可用，请稍后重试。'); }
  if (!response.ok) { if (response.status===401 && user) location.href='/login'; throw new Error(payload.error?.message || '请求失败，请重试'); }
  return payload.data;
}
function options(values, selected='') { return Object.entries(Array.isArray(values)?Object.fromEntries(values.map(x=>[x,x])):values).map(([key,label])=>`<option value="${esc(key)}" ${key===selected?'selected':''}>${esc(label)}</option>`).join(''); }
function badge(status) { return `<span class="badge ${esc(status)}">${esc(states[status])}</span>`; }
function errorPanel(error) { return `<section class="panel empty-state">${icon('help')}<strong>暂时无法加载</strong><p>${esc(error.message)}</p><button class="button secondary" data-action="retry">重新加载</button></section>`; }
function heading(title, subtitle, eyebrow='CAMPUS SERVICE CENTER') { $('#page-heading').textContent=title; $('#breadcrumb').textContent=title; $('#page-subtitle').textContent=subtitle; $('#page-eyebrow').textContent=eyebrow; }
function statsCards(stats) {
 const items = user.role==='worker' ? [['获派任务',stats.total,'ticket','violet','你的全部维修任务'],['待接单',stats.by_status.assigned,'clock','amber','等待你确认接单'],['处理中',stats.by_status.working,'tool','teal','正在推进的维修'],['已提交结果',stats.by_status.confirm+stats.by_status.completed,'check','teal','等待确认或已完成']]
 : [['报修总数',stats.total,'ticket','violet',user.role==='admin'?'全校工单，统一管理':'每一次反馈都有记录'],[user.role==='admin'?'待分配':'待处理',stats.by_status.waiting+(user.role==='admin'?0:stats.by_status.assigned),'clock','amber',user.role==='admin'?'等待管理员分配':'等待分配或维修接单'],['处理中',stats.by_status.working,'tool','','维修人员正在跟进'],['已完成',stats.by_status.completed,'check','teal','问题解决，安心使用']];
 return `<div class="stats-grid">${items.map(([label,n,ico,color,note])=>`<div class="stat-card"><div><span>${label}</span><span class="stat-icon ${color}">${icon(ico)}</span></div><div class="stat-number">${n}</div><span class="stat-note">${note}</span></div>`).join('')}</div>`;
}
function table(items) {
 if (!items.length) return `<div class="empty-state">${icon('ticket')}<strong>这里还没有工单</strong><p>试试调整筛选条件${user.role==='student'?'，或提交你的第一份报修':'，新的任务会显示在这里'}。</p>${user.role==='student'?'<a class="button small" href="/tickets/new">发起报修</a>':''}</div>`;
 return `<div class="table-wrap"><table><thead><tr><th>工单编号</th><th>报修事项 / 地点</th><th>故障分类</th><th>优先级</th><th>当前状态</th><th>提交时间</th><th></th></tr></thead><tbody>${items.map(ticket=>`<tr><td class="ticket-number">#BX${String(ticket.id).padStart(5,'0')}</td><td><a class="ticket-title" href="/tickets/${ticket.id}">${esc(ticket.title)}</a><span class="ticket-subtitle">${icon('pin')}${esc(ticket.location)}</span></td><td>${esc(ticket.category)}</td><td><span class="priority ${esc(ticket.priority)}">${esc(priorities[ticket.priority])}</span></td><td>${badge(ticket.status)}</td><td class="ticket-number">${date(ticket.created_at)}</td><td><a class="text-link" href="/tickets/${ticket.id}">详情 ${icon('arrow')}</a></td></tr>`).join('')}</tbody></table></div>`;
}
function toolbar() { return `<form id="filter-form" class="toolbar"><div class="search-field">${icon('search')}<input name="q" placeholder="搜索工单标题、地点或编号" maxlength="100" value="${esc(listFilter.q || '')}" aria-label="搜索工单"></div><select name="status" aria-label="工单状态"><option value="">全部状态</option>${options(states,listFilter.status)}</select><select name="category" aria-label="故障分类"><option value="">全部分类</option>${options(categories,listFilter.category)}</select><button class="button small secondary" type="submit">筛选</button><button class="link-button" type="button" data-action="clear-filter">重置</button></form>`; }
function pagination(result) { const pages=Math.max(1,Math.ceil(result.total/result.page_size)); return `<div class="table-footer"><span>共 ${result.total} 条记录 · 每页 ${result.page_size} 条</span><div class="pagination"><button data-action="previous" ${listPage<=1?'disabled':''} aria-label="上一页">‹</button><button class="current">${listPage} / ${pages}</button><button data-action="next" ${listPage>=pages?'disabled':''} aria-label="下一页">›</button></div></div>`; }
async function dashboard() {
 heading(user.role==='admin'?'服务工作台':user.role==='worker'?'维修工作台':'我的工作台','一站式校园报修，让校园生活更安心。');
 const [stats,result] = await Promise.all([api('/stats'),api('/tickets?page_size=5')]);
 $('#nav-count').textContent=stats.total;
 const description = user.role==='admin'?'集中查看校园服务需求，及时分配任务，让每一份报修都能得到妥善处理。':user.role==='worker'?'这里是你的维修任务清单。及时接单、记录进展，让同学们少一份等待。':'宿舍、教室或公共区域遇到问题？提交报修，我们会认真跟进每一份反馈。';
 $('#page-content').innerHTML=`<section class="welcome-banner"><div><h2>${esc(user.name)}，${new Date().getHours()<12?'上午好':'你好'} 👋</h2><p>${description}</p><div class="banner-label"><span class="live-dot"></span> 你的校园生活，我们一起守护 <span>↗</span></div></div><div class="banner-art" aria-hidden="true"><div class="art-disc"></div><div class="art-ticket"><i></i><i></i><i></i><i></i></div><span class="art-tick">${icon('check')}</span></div></section>${statsCards(stats)}<section class="panel"><div class="panel-heading"><div><h2>${user.role==='worker'?'最近维修任务':'最近报修工单'}</h2><p>跟进每一份报修，掌握最新进展</p></div><a class="text-link" href="/tickets">查看全部 ${icon('arrow')}</a></div>${table(result.items)}</section><div class="bottom-grid"><section class="panel"><div class="panel-heading"><h2>从报修到解决，进展看得见</h2></div><div class="steps">${[['ticket','提交报修','描述问题'],['user','分配人员','专人跟进'],['tool','维修处理','记录进度'],['check','确认完成','评价反馈']].map(([ico,title,note])=>`<div class="step"><div class="step-icon">${icon(ico)}</div><strong>${title}</strong><small>${note}</small></div>`).join('')}</div></section><section class="panel"><div class="panel-heading"><h2>报修小贴士</h2><a class="text-link" href="/help">使用指南 ${icon('arrow')}</a></div><div class="service-tip"><div class="tip-icon">${icon('help')}</div><div><h3>信息越完整，处理越高效</h3><p>请写明楼栋与房间、故障现象及发现时间，并上传清晰的现场照片。涉及人身安全时，请先远离现场。</p></div></div></section></div>`;
}
async function tickets() {
 heading(user.role==='admin'?'全部工单':user.role==='worker'?'维修任务':'我的报修','查看工单详情，跟进处理过程与最新动态。','WORK ORDERS');
 const params=new URLSearchParams({...listFilter,page:listPage,page_size:10});
 const result=await api('/tickets?'+params);
 $('#page-content').innerHTML=`<section class="panel"><div class="panel-heading"><div><h2>工单列表</h2><p>按状态、分类快速找到需要的记录</p></div><span class="muted">${result.total} 份工单</span></div>${toolbar()}${table(result.items)}${pagination(result)}</section>`;
 $('#filter-form').addEventListener('submit',event=>{event.preventDefault(); listFilter=Object.fromEntries(new FormData(event.target));listPage=1;loadPage();});
}
function createPage() {
 heading('发起报修','说清楚你遇到的问题，接下来的事交给我们。','NEW REPAIR REQUEST');
 if (user.role!=='student') { $('#page-content').innerHTML='<div class="panel empty-state">仅学生账户可发起报修，请切换至学生账户。</div>';return; }
 $('#page-content').innerHTML=`<div class="create-layout"><section class="panel"><form id="ticket-form"><div class="form-section"><h3>01 / 基本信息</h3><div class="form-grid"><label class="span-two">报修标题<input name="title" minlength="3" maxlength="100" placeholder="例如：宿舍洗手池水龙头持续漏水" required></label><label class="span-two">具体地点<input name="location" minlength="3" maxlength="160" placeholder="楼栋 + 楼层 + 房间号，例如：紫荆公寓3栋402室" required></label><label>故障分类<select name="category">${options(categories)}</select></label><label>优先级<select name="priority">${options(priorities)}</select></label></div></div><div class="form-section"><h3>02 / 描述问题</h3><label>故障描述<textarea name="description" minlength="10" maxlength="3000" rows="6" placeholder="请描述故障现象、发现时间，以及是否影响正常使用。无需推测故障原因。" required></textarea><small>10–3000字 · 你的原始描述会完整保留</small></label></div><div class="form-section"><h3>03 / 现场图片（选填）</h3><label class="upload-area">${icon('upload')}选择图片，帮助维修人员更快了解现场<input name="file" type="file" accept="image/png,image/jpeg,image/webp"><small>PNG、JPEG、WebP · 每张不超过5MB；后续可在详情中补充</small></label><p id="create-error" class="error-text" role="alert"></p></div><div class="form-actions"><a href="/tickets" class="button secondary">暂不提交</a><button class="button" type="submit">提交报修 ${icon('arrow')}</button></div></form></section><aside class="assist-panel">${icon('spark')}<h3>把问题描述得更清楚</h3><p>试试基础提示，检查信息是否完整。真实 AI 服务将在后续接入。</p><ul><li>发生在哪里？</li><li>看到了什么异常？</li><li>什么时候发现的？</li></ul><button type="button" class="button small secondary" data-action="suggest">检查描述完整度</button><div id="assist-result" class="assist-result" hidden></div><span class="assist-label">基础规则提示 · 未调用 AI · 不自动提交</span></aside></div>`;
 $('#ticket-form').addEventListener('submit', async event=>{
   event.preventDefault();const form=event.target,button=$('button[type=submit]',form),data=Object.fromEntries(new FormData(form)),file=data.file;delete data.file;
   if (file?.size>5*1024*1024) { $('#create-error').textContent='图片不得超过5MB';return; }
   data.original_description=data.description;button.disabled=true;button.textContent='正在提交…';form.dataset.key ||= freshKey();
   try { const result=await api('/tickets',{method:'POST',data,key:form.dataset.key});
     if(file?.size) { const files=new FormData();files.set('file',file);try{await api(`/tickets/${result.id}/attachments`,{method:'POST',data:files,key:freshKey()});}catch(error){toast('工单已创建，图片上传失败，请在详情中补充');await new Promise(resolve=>setTimeout(resolve,1500));} }
     location.href='/tickets/'+result.id;
   } catch(error) { $('#create-error').textContent=error.message;button.disabled=false;button.textContent='提交报修'; }
 });
}
function suggest() {
 const form=$('#ticket-form'),description=form.elements.description.value,locationValue=form.elements.location.value,result=$('#assist-result');
 const hints=[];if(locationValue.trim().length<3) hints.push('请补充楼栋、楼层和房间号。');if(description.trim().length<10) hints.push('请补充具体故障现象，至少10个字。');if(!/今天|昨天|上午|下午|晚上|时间|\d+[点日月天时]/.test(description)) hints.push('建议补充发现时间或持续时长。');
 let category='其他';for(const [words,name] of [[/水|电灯|插座|照明|漏|排水/,'水电'],[/网|信号|连接/,'网络'],[/桌|椅|门|床|柜/,'家具'],[/空调|制冷|制热/,'空调']]) if(words.test(description)){category=name;break;}
 result.hidden=false;result.innerHTML=`<strong>建议分类：${category}</strong><p>${hints.length?hints.map(esc).join('<br>'):'信息基本完整。提交前请再次确认地点与故障现象。'}</p><button type="button" class="link-button" data-action="apply-category" data-category="${category}">采用此分类 →</button><small>仅依据关键词，不判断故障原因。</small>`;
}
function allowedActions(ticket) {
 if(['completed','cancelled'].includes(ticket.status)) return [];
 let buttons=[];
 if(user.role==='admin') {if(ticket.status==='waiting')buttons.push(['assign','分配维修人员']);buttons.push(['classify','调整分类 / 优先级']);}
 if(user.role==='worker') {if(ticket.status==='assigned')buttons.push(['accept','接单并开始处理']);if(ticket.status==='working')buttons.push(['finish','提交维修结果']);}
 if(user.role==='student') {if(['waiting','assigned'].includes(ticket.status))buttons.push(['cancel','取消报修']);if(ticket.status==='confirm')buttons.push(['confirm','确认维修完成'],['reopen','问题未解决']);}
 buttons.push(['note',user.role==='student'?'补充报修信息':'添加处理记录']);return buttons;
}
async function detailPage(id) {
 const ticket=await api('/tickets/'+id);currentTicket=ticket;
 heading('工单详情','记录每一步进展，让处理过程清晰可见。','REPAIR DETAILS');
 $('#page-content').innerHTML=`<div class="detail-layout"><div><section class="panel"><div class="panel-heading"><span class="ticket-number">#BX${String(id).padStart(5,'0')}</span>${badge(ticket.status)}</div><div class="panel-body"><h2>${esc(ticket.title)}</h2><p class="detail-text">${esc(ticket.description)}</p>${ticket.description!==ticket.original_description?`<details><summary>查看原始描述</summary><p class="detail-text">${esc(ticket.original_description)}</p></details>`:''}<dl class="detail-meta">${[['报修地点',ticket.location],['故障分类',ticket.category],['优先级',priorities[ticket.priority]],['报修人',ticket.owner_name],['维修人员',ticket.assignee_name||'待分配'],['提交时间',date(ticket.created_at)]].map(([label,value])=>`<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl></div></section><section class="panel"><div class="panel-heading"><h2>现场图片 <span class="muted">${ticket.attachments.length}/10</span></h2></div><div class="panel-body">${ticket.attachments.length?`<div class="attachment-grid">${ticket.attachments.map(file=>`<a href="/api/v1/attachments/${file.id}" target="_blank" rel="noopener"><img src="/api/v1/attachments/${file.id}" alt="工单现场图片" loading="lazy"></a>`).join('')}</div>`:'<p class="muted">暂未添加现场图片。</p>'}${!['completed','cancelled'].includes(ticket.status)?`<label class="upload-area">${icon('upload')}补充现场图片<input id="attachment-file" type="file" accept="image/png,image/jpeg,image/webp"><small>每张不超过5MB，仅工单授权人员可访问</small></label>`:''}<p id="upload-error" class="error-text"></p></div></section>${ticket.review?`<section class="panel"><div class="panel-heading"><h2>维修评价</h2></div><div class="panel-body"><div class="review-stars">${'★'.repeat(ticket.review.rating)}${'☆'.repeat(5-ticket.review.rating)}</div><p class="detail-text">${esc(ticket.review.comment||'已完成评价，感谢反馈。')}</p></div></section>`:''}<section class="panel"><div class="panel-heading"><h2>处理时间线</h2><span class="muted">${ticket.events.length} 条记录</span></div><div class="panel-body timeline">${[...ticket.events].reverse().map(event=>`<div class="timeline-item"><h4>${esc(actionNames[event.action]||event.action)} <span class="muted">· ${esc(event.actor_name)}</span></h4><p>${esc(event.note)}</p><small>${date(event.created_at)} ${event.before_status!==event.after_status?' · '+esc(states[event.after_status]):''}</small></div>`).join('')}</div></section></div><aside class="detail-side"><section class="panel"><div class="panel-heading"><h2>下一步操作</h2></div><div class="panel-body">${allowedActions(ticket).map(([action,label])=>`<button class="button ${['cancel','reopen'].includes(action)?'secondary':''}" data-action="ticket-action" data-operation="${action}">${label}</button>`).join('')}${ticket.status==='completed'&&user.role==='student'&&!ticket.review?'<button class="button" data-action="ticket-action" data-operation="review">评价本次维修</button>':''}${['completed','cancelled'].includes(ticket.status)?'<p class="muted">工单已结束，完整处理记录将保留。</p>':''}<a class="text-link" href="/tickets">← 返回工单列表</a></div></section><section class="assist-panel">${icon('help')}<h3>有新的情况？</h3><p>可在处理中补充说明或图片。收到维修结果后，请及时确认；若问题未解决，可反馈后继续处理。</p></section></aside></div>`;
 $('#attachment-file')?.addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;const data=new FormData();data.set('file',file);event.target.disabled=true;try{await api(`/tickets/${id}/attachments`,{method:'POST',data,key:freshKey()});toast('图片已添加');await detailPage(id);}catch(error){$('#upload-error').textContent=error.message;event.target.disabled=false;}});
}
async function openAction(name) {
 pendingAction=name;const dialog=$('#action-dialog'),fields=$('#dialog-fields');$('#dialog-error').textContent='';$('#action-form').dataset.key=freshKey();$('#dialog-title').textContent=name==='review'?'评价本次维修':actionNames[name];
 if(name==='assign') { const workers=await api('/workers');fields.innerHTML=workers.length?`<label>维修人员<select name="assignee_id">${workers.map(worker=>`<option value="${worker.id}">${esc(worker.name)}</option>`).join('')}</select></label>`:'<p class="muted">还没有维修人员，请先凭邀请码注册维修账户。</p>'; }
 else if(name==='classify') fields.innerHTML=`<label>分类<select name="category">${options(categories,currentTicket.category)}</select></label><label>优先级<select name="priority">${options(priorities,currentTicket.priority)}</select></label>`;
 else if(name==='review')fields.innerHTML=`<label>满意度<select name="rating"><option value="5">5分 · 非常满意</option><option value="4">4分 · 满意</option><option value="3">3分 · 一般</option><option value="2">2分 · 不太满意</option><option value="1">1分 · 不满意</option></select></label><label>评价（选填）<textarea name="comment" maxlength="1000" placeholder="分享本次维修体验"></textarea></label>`;
 else fields.innerHTML=`<p class="muted">${name==='cancel'?'取消后工单将结束。':name==='confirm'?'确认现场问题已解决，工单将标记为已完成。':name==='accept'?'接单后进入处理中，请及时记录进展。':'请填写实际情况，内容将保存在工单时间线。'}</p><label>说明${['finish','reopen','note'].includes(name)?'（必填）':'（选填）'}<textarea name="note" maxlength="3000" ${['finish','reopen','note'].includes(name)?'required minlength="2"':''} placeholder="请输入说明"></textarea></label>`;
 dialog.showModal();
}
async function statisticsPage() {
 heading('数据概览','了解报修分布与处理进展。统计仅包含当前账户有权访问的工单。','SERVICE INSIGHTS');
 const stats=await api('/stats');
 $('#page-content').innerHTML=`${statsCards(stats)}<div class="bottom-grid"><section class="panel"><div class="panel-heading"><h2>工单状态分布</h2><span class="muted">共 ${stats.total} 份</span></div><div class="panel-body">${Object.entries(states).map(([key,label])=>`<div class="chart-row"><span>${label}</span><meter class="chart-meter" min="0" max="${Math.max(stats.total,1)}" value="${stats.by_status[key]}">${stats.by_status[key]}</meter><strong>${stats.by_status[key]}</strong></div>`).join('')}</div></section><section class="panel"><div class="panel-heading"><h2>故障分类</h2></div><div class="panel-body">${stats.categories.length?stats.categories.map(row=>`<div class="chart-row"><span>${esc(row.category)}</span><meter class="chart-meter" min="0" max="${stats.total}" value="${row.count}">${row.count}</meter><strong>${row.count}</strong></div>`).join(''):'<p class="muted">暂无数据</p>'}<div class="chart-summary">${stats.average_rating??'—'}<small> / 5</small></div><p class="muted">已评价工单平均满意度</p></div></section></div>`;
}
function profilePage() { heading('个人信息','你的账户与所属服务角色。','MY ACCOUNT');$('#page-content').innerHTML=`<section class="panel profile-card"><div class="profile-header"><span class="avatar">${esc(user.name[0])}</span><div><h2>${esc(user.name)}</h2><span class="muted">${roles[user.role]} · 已登录</span></div></div><div class="panel-body"><dl class="detail-meta">${[['用户名',user.username],['账户类型',roles[user.role]],['会话有效期','登录后8小时'],['可见范围',user.role==='student'?'仅本人报修':user.role==='worker'?'仅获派维修任务':'全部工单']].map(([k,v])=>`<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl></div></section>`; }
function helpPage() { heading('使用帮助','让报修更顺畅，让每一步操作更清楚。','HELP & SUPPORT');$('#page-content').innerHTML=`<section class="panel"><div class="panel-heading"><h2>校园服务指南</h2></div><div class="panel-body help-list"><h3>如何提交一份有效报修？</h3><p>学生点击“发起报修”，写明具体地点、故障现象与发现时间，选择分类和优先级，可上传现场图片。基础提示只检查关键词和缺失信息，不调用AI，不替你提交。</p><h3>管理员和维修人员如何协作？</h3><p>管理员在待分配工单中选择维修人员；获派人员接单后进入处理中，添加处理记录，维修结束后填写实际结果并提交，等待学生确认。</p><h3>维修后仍有问题怎么办？</h3><p>学生可在待确认工单选择“问题未解决”并说明现象，工单回到处理中。确认解决后完成工单，可以给予1–5分评价。</p><h3>什么时候可以取消？</h3><p>本人报修在待分配、待接单阶段可以取消。维修开始后无法直接取消，可通过补充信息与工作人员沟通。</p><h3>如何注册不同账户类型？</h3><p>学生可直接注册。维修人员和后勤管理员需要向管理方获取对应角色的邀请码，填写后创建独立真实账户。演示账号仅用于本机体验，不影响真实注册账户。</p><h3>隐私与图片</h3><p>报修与附件仅对本人、获派维修人员及管理员开放。图片限PNG/JPEG/WebP，每张5MB，每单最多10张。不要上传证件、密码等无关敏感信息。</p></div></section>`; }
async function loadPage() {
 const view=$('#workspace');if(!view)return;const page=view.dataset.page;
 $('#page-content').innerHTML='<div class="loading-state"><span class="spinner"></span>正在加载…</div>';
 try {if(page==='/')await dashboard();else if(page==='/tickets')await tickets();else if(page==='/tickets/new')createPage();else if(view.dataset.ticket)await detailPage(Number(view.dataset.ticket));else if(page==='/statistics')await statisticsPage();else if(page==='/profile')profilePage();else helpPage();}
 catch(error){$('#page-content').innerHTML=errorPanel(error);}
}
async function initialize() {
 const view=$('[data-view]');if(!view)return;
 try {const session=await api('/session');csrf=session.csrf;user=session.user;}catch(error){if($('#identity-error'))$('#identity-error').textContent=error.message;else $('#page-content').innerHTML=errorPanel(error);return;}
 if(view.dataset.view==='identity') {
  const registering=view.dataset.registering==='true';
  $('#toggle-password').addEventListener('click',()=>{const input=$('#password');input.type=input.type==='password'?'text':'password';$('#toggle-password').textContent=input.type==='password'?'显示':'隐藏';});
  $('#register-role')?.addEventListener('change',event=>{$('#invite-field').hidden=event.target.value==='student';$('#invite-field input').required=event.target.value!=='student';});
  $('#identity-form').addEventListener('submit',async event=>{event.preventDefault();const form=event.target,button=$('button[type=submit]',form);button.disabled=true;$('#identity-error').textContent='';try{const result=await api(registering?'/register':'/login',{method:'POST',data:Object.fromEntries(new FormData(form))});location.href=result.redirect;}catch(error){$('#identity-error').textContent=error.message;button.disabled=false;}});
 } else {
  $('#today').textContent=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'long',day:'numeric',weekday:'short'}).format(new Date());
  const closeMenu=()=>{$('#sidebar').classList.remove('open');$('#nav-backdrop').hidden=true;$('#menu-button').setAttribute('aria-expanded','false');};
  $('#menu-button').addEventListener('click',()=>{const open=$('#sidebar').classList.toggle('open');$('#nav-backdrop').hidden=!open;$('#menu-button').setAttribute('aria-expanded',String(open));});
  $('#close-menu').addEventListener('click',closeMenu);$('#nav-backdrop').addEventListener('click',closeMenu);
  $('#logout').addEventListener('click',async()=>{try{await api('/logout',{method:'POST'});location.href='/login';}catch(error){toast(error.message);}});
  await loadPage();
  try {const summary=await api('/stats');$('#nav-count').textContent=summary.total;}catch(_){}
 }
}
document.addEventListener('click',async event=>{const button=event.target.closest('[data-action]');if(!button)return;
 try {switch(button.dataset.action){case'retry':await loadPage();break;case'previous':listPage--;await loadPage();break;case'next':listPage++;await loadPage();break;case'clear-filter':listFilter={};listPage=1;await loadPage();break;case'suggest':suggest();break;case'apply-category':$('#ticket-form').elements.category.value=button.dataset.category;toast('已采用分类建议，请继续确认描述');break;case'ticket-action':await openAction(button.dataset.operation);break;}}
 catch(error){toast(error.message);}
});
$('#close-dialog').addEventListener('click',()=>$('#action-dialog').close());$('#cancel-dialog').addEventListener('click',()=>$('#action-dialog').close());
$('#action-form').addEventListener('submit',async event=>{event.preventDefault();const form=event.target,data=Object.fromEntries(new FormData(form)),button=$('button[type=submit]',form);data.version=currentTicket.version;if(data.assignee_id)data.assignee_id=Number(data.assignee_id);if(data.rating)data.rating=Number(data.rating);data.action=pendingAction;button.disabled=true;$('#dialog-error').textContent='';try{await api(`/tickets/${currentTicket.id}/${pendingAction==='review'?'review':'actions'}`,{method:'POST',data,key:form.dataset.key});$('#action-dialog').close();toast('操作成功，进度已更新');await detailPage(currentTicket.id);}catch(error){$('#dialog-error').textContent=error.message;}finally{button.disabled=false;}});
initialize();
