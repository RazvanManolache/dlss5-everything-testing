'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const E = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = (value, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString(undefined, {maximumFractionDigits: digits, minimumFractionDigits: digits}) : '—';
  const count = (value) => Number(value || 0).toLocaleString();
  const color = (name) => ['#c6ef80','#83d8dc','#c8a2e8','#e8bc78','#eb9eac','#9bbfea'][Math.abs([...String(name)].reduce((a,c) => a + c.charCodeAt(0), 0)) % 6];
  const stamp = (iso) => {const date = new Date(iso); return Number.isNaN(date.valueOf()) ? 'Time unrecorded' : date.toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});};
  const unit = (value) => value == null ? 'Time unrecorded' : `${num(value)}s`;
  const captureTime = (c) => c.occurrences?.length > 1 ? [...new Set(c.occurrences.map(o=>unit(o.seconds)))].join(' / ') + ' · identical' : unit(c.seconds);
  const state = {view:'overview',query:'',suite:'all',arch:'all',mode:'all',freshness:'all',outcome:'all',motion:'all',groups:new Set(),sort:'newest',galleryMissing:false,compare:[],compareMode:'sides',wipe:50,gain:4,chartGroup:'fixture',chartMetric:'fps',allBars:true,perfBackends:new Set(['native','nvidia','phoenix']),perfRoute:'all',perfSort:'name',pairedOnly:false,logScale:false,tableSort:'fixture',tableDesc:false};
  state.execution = 'all';
  let data = window.BENCH_DATA || {fixtures:[],runs:[],captures:[],groups:[],warnings:[],build:{}};
  let fixtures, runs, captures, differenceGeneration = 0;
  let isLive = false;
  try {state.compare = JSON.parse(localStorage.getItem('museum-compare') || '[]').filter(x => typeof x === 'string').slice(0,4);} catch {}

  function indexData() {
    fixtures = new Map(data.fixtures.map(f => [f.id, f]));
    runs = new Map(data.runs.map(r => [r.id, r]));
    captures = new Map(data.captures.map(c => [c.id, {...c,run:runs.get(c.run_id)}]));
    $('mode').innerHTML = '<option value="all">All run types</option>' + [...new Set(data.runs.map(r=>r.mode))].sort().map(mode=>`<option value="${E(mode)}">${E(modeName(mode))}</option>`).join('');
    $('mode').value = state.mode;
    state.compare = state.compare.filter(id => captures.has(id));
  }
  function remember() {try {localStorage.setItem('museum-compare', JSON.stringify(state.compare));} catch {}}
  function toast(message) {const node=$('toast');node.textContent=message;node.classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('visible'),4200);}
  function matches(record, extra='', ignored=[]) {
    if (state.groups.size && !state.groups.has(record.group)) return false;
    if (!ignored.includes('suite') && state.suite !== 'all' && record.suite !== state.suite) return false;
    if (state.arch !== 'all' && record.architecture !== state.arch) return false;
    if (!ignored.includes('mode') && state.mode !== 'all' && record.mode !== state.mode) return false;
    if (!ignored.includes('execution') && state.execution !== 'all' && record.execution_mode !== state.execution && record.requested_execution_mode !== state.execution) return false;
    if (state.freshness !== 'all' && record.freshness !== state.freshness) return false;
    if (state.outcome !== 'all' && record.status !== state.outcome) return false;
    const motion=record.controls?.frozen===true?'frozen':record.controls?.frozen===false?'live':'unknown';
    if(state.motion!=='all'&&motion!==state.motion)return false;
    const haystack = [record.id,record.fixture_id,record.label,record.group,record.api,record.transport,record.architecture,record.gpu,record.mode,record.suite,record.execution_label,record.execution_variant,routeName(record.execution_mode),motion,extra].join(' ').toLowerCase();
    return state.query.toLowerCase().split(/\s+/).every(word => haystack.includes(word));
  }
  function filteredRuns() {return data.runs.filter(r => matches(r));}
  function filteredCaptures() {return [...captures.values()].filter(c => c.run && matches(c.run, [c.name,c.id,c.seconds,c.requested_seconds,...(c.occurrences||[]).flatMap(o=>[o.name,o.id,o.seconds,o.requested_seconds]),c.width&&`${c.width}x${c.height}`].join(' ')));}
  function fixtureRecord(game) {return {...game,fixture_id:game.id,suite:['working','clean'].includes(state.suite)?state.suite:'both',mode:'unknown',status:'missing',freshness:'unverified',fps:null,samples:[],captures:[]};}
  function missingFixtures() {return data.fixtures.filter(g => !data.runs.some(r => r.fixture_id===g.id && !r.reference && (!['working','clean'].includes(state.suite)||r.suite===state.suite))).map(fixtureRecord).filter(r => matches(r));}
  function uncapturedFixtures() {
    const visible=filteredRuns(), pictured=new Set(filteredCaptures().map(c=>c.run.fixture_id));
    return data.fixtures.filter(g=>!pictured.has(g.id)).map(g=>visible.filter(r=>r.fixture_id===g.id&&!r.reference).sort((a,b)=>b.timestamp.localeCompare(a.timestamp))[0]||fixtureRecord(g)).filter(r=>matches(r));
  }
  function measuredRuns() {
    const seen=new Set();
    return filteredRuns().filter(r=>typeof r.fps==='number' && Number.isFinite(r.fps) && !r.reference).sort((a,b)=>b.timestamp.localeCompare(a.timestamp)).filter(r=>{const k=[r.fixture_id,r.suite,r.mode,r.execution_variant||'auto'].join('|');if(seen.has(k))return false;seen.add(k);return true;});
  }
  const badge = (label,style='') => `<span class="badge ${style}">${E(label)}</span>`;
  function freshnessBadge(r) {return badge(r.freshness==='current'?'Current build':r.freshness==='stale'?'Older build':'Build unverified',r.freshness==='current'?'lime':'amber');}
  function statusBadge(r) {return badge({complete:'Complete',incomplete:'Incomplete',failed:'Failed',not_applicable:'Not applicable',missing:'Not run',reference:'Reference'}[r.status]||r.status,r.status==='complete'?'lime':r.status==='failed'?'red':r.status==='missing'?'':'amber');}
  const suiteName = (suite) => ({working:'ReShade / working',clean:'Clean set',both:'Both sets',unknown:'Unknown set',reference:'Reference'}[suite] || suite);
  const modeName = mode => ({native:'Native',nvidia:'NVIDIA DLSS5',phoenix:'Phoenix'})[mode] || mode;
  const routeName = route => ({in_process:'In process',helper:'Background process',in_process_x64_library:'x64 library inside x86',in_process_x86_driver:'x86 Phoenix + native driver',in_process_portable:'Portable in process',native:'Native baseline',not_started:'Not started'})[route] || route || '--';
  const executionBadge = r => {
    const observed=r.execution_mode, requested=r.execution_label;
    const tag=observed?`<span class="badge execution-tag ${observed==='helper'?'amber':'cyan'}" data-execution="${E(observed)}">${E(routeName(observed))}</span>`:'';
    return (requested&&requested!==routeName(observed)?badge(requested,'cyan'):'')+tag+
      (r.startup_in_measurement?badge('Startup in measurement','amber'):'');
  };
  const backendColor = mode => ({native:'#adb5bd',nvidia:'#c6ef80',phoenix:'#83d8dc'})[mode];
  function empty(title,message,button='') {return `<div class="empty-state"><span class="empty-icon">◫</span><h3>${E(title)}</h3><p>${E(message)}</p>${button}</div>`;}
  function chartEmpty() {return `<div class="empty-state chart-empty"><span class="empty-icon">▥</span><h3>No FPS samples yet</h3><p>Save a timed benchmark run to populate this chart. Build success and screenshots alone do not supply FPS measurements.</p></div>`;}
  function heading(title,description='',actions='') {return `<div class="section-header"><div><h2>${E(title)}</h2>${description?`<p>${E(description)}</p>`:''}</div>${actions}</div>`;}

  function renderChrome() {
    document.body.classList.toggle('performance-view',state.view==='performance');
    $('summary').hidden=state.view==='performance';
    const visibleRuns=filteredRuns(), images=filteredCaptures(), measured=measuredRuns();
    const current=new Set(visibleRuns.filter(r=>r.freshness==='current'&&r.status==='complete').map(r=>r.fixture_id));
    const cards=[['Fixture catalogue',count(data.fixtures.length),'82 Windows variants + DOS / VGA','↗'],['Saved captures',count(images.length),`${new Set(images.map(c=>c.run_id)).size} result sets in this selection`,'▦'],['Measured runs',count(measured.length),'Latest per fixture, set and mode','▥'],['Current build coverage',`${current.size}<small> / ${data.fixtures.length}</small>`,'Completed runs with a matching executable hash','◉']];
    $('summary').innerHTML=cards.map(([title,value,note,icon])=>`<article class="stat-card"><div class="stat-label">${E(title)}<span>${icon}</span></div><div class="stat-number">${value}</div><div class="stat-note">${E(note)}</div><div class="stat-accent"></div></article>`).join('');
    $('navCaptureCount').textContent=data.captures.length;
    $('navCompareCount').textContent=state.compare.length;
    document.querySelectorAll('[data-view]').forEach(a=>a.classList.toggle('active',a.dataset.view===state.view));
    $('groupList').innerHTML=data.groups.map(group=>`<button class="group-button ${state.groups.has(group)?'selected':''}" data-group="${E(group)}" aria-pressed="${state.groups.has(group)}"><i class="dot" style="background:${color(group)}"></i>${E(group)}<span>${data.fixtures.filter(f=>f.group===group).length}</span></button>`).join('');
    const groupSelect=$('groupSelect');
    groupSelect.innerHTML='<option value="all">All technologies</option>'+data.groups.map(g=>`<option value="${E(g)}">${E(g)}</option>`).join('')+(state.groups.size>1?'<option value="multiple">Multiple groups</option>':'');
    groupSelect.value=state.groups.size>1?'multiple':state.groups.size?[...state.groups][0]:'all';
    $('activeGroup').hidden=!state.groups.size;
    $('activeGroup').textContent='Technology selection: '+[...state.groups].join(' + ');
    const titles={overview:['A clearer view of every frame.','Explore your captures, compare rendering paths, and see what the numbers actually say.'],gallery:['The same museum. Every perspective.','Search saved screenshots by renderer, architecture, mode or capture time. Select up to four to compare.'],compare:['Look closer. Find the difference.','Compare captures side by side, wipe between two images, or inspect their absolute pixel difference.'],performance:['Backend performance','Native, NVIDIA DLSS5 and Phoenix. Matched timings and observed execution routes.'],results:['Every renderer. Every result.','The complete fixture catalogue, measured results, freshness and missing coverage in one place.']};
    const [title,sub]=titles[state.view];$('pageTitle').textContent=title;$('pageSubtitle').textContent=sub;
    for(const name of Object.keys(titles))$(`view-${name}`).hidden=name!==state.view;
    const stale=visibleRuns.filter(r=>r.freshness==='stale').length,partial=visibleRuns.filter(r=>r.status==='incomplete').length;
    const noCurrent=!data.runs.some(r=>r.status==='complete'&&r.freshness==='current');
    $('notice').innerHTML=noCurrent?`<span>↳</span><span><strong>No current-build runtime results yet.</strong> The catalogue is ready; saved references and incomplete captures stay clearly labelled. The dashboard never launches tests.</span>`:stale||partial?`<span>↳</span><span>This selection includes ${stale} older-build and ${partial} incomplete result sets. Filter to <strong>Current build only</strong> for matching executable hashes.</span>`:'';
    if(data.warnings?.length)$('notice').innerHTML+=`<span>${data.warnings.length} unreadable result file(s).</span>`;
    $('updated').textContent='Indexed '+stamp(data.generated_at);
  }

  function captureCard(c) {
    const r=c.run, chosen=state.compare.includes(c.id), fps=r.fps==null?'—':num(r.fps);
    return `<article class="capture-card ${chosen?'selected':''}"><div class="capture-image"><img src="${E(c.src)}" alt="${E(r.label)} ${E(r.mode)} screenshot" loading="lazy" data-open="${E(c.id)}"><div class="image-topline">${badge(r.label,'lime')}${badge(r.architecture)}</div><div class="image-bottomline"><span>${E(captureTime(c))}${c.width?' · '+c.width+'×'+c.height:''}${c.shared_frame?' · shared frame':''}</span><button class="compare-pick ${chosen?'chosen':''}" data-pick="${E(c.id)}" aria-pressed="${chosen}">${chosen?'✓ Selected':'+ Compare'}</button></div></div><div class="capture-body"><h3 class="capture-title">${E(r.label)} <span class="badge">${E(r.mode)}</span></h3><div class="badges">${statusBadge(r)}${freshnessBadge(r)}${executionBadge(r)}${r.controls?.frozen===true?badge('Frozen','cyan'):''}</div><div class="capture-path" title="${E(c.id)}">${E(c.id)}</div><div class="capture-meta"><div class="fps-value" title="${E(r.fps_scope||'Recorded FPS')}">${fps} <small>${['nvidia','phoenix'].includes(r.mode)?'processed FPS':'FPS'}${r.reference?' · reference only':''}</small></div><div class="meta-right">${E(suiteName(r.suite))}<br>${E(stamp(r.timestamp))}</div></div></div></article>`;
  }
  function missingCard(r) {return `<article class="capture-card"><div class="capture-image no-image"><strong>${E(r.label)}</strong><span>No saved screenshot</span></div><div class="capture-body"><h3 class="capture-title">${E(r.fixture_id)}</h3><div class="badges">${badge(r.architecture)}${badge(r.group)}${statusBadge(r)}${executionBadge(r)}${r.status!=='missing'?freshnessBadge(r):''}</div><div class="capture-path">${E(r.api)} → ${E(r.transport)}</div><div class="capture-meta"><div class="fps-value">${num(r.fps)} <small>${['nvidia','phoenix'].includes(r.mode)?'processed FPS':'FPS'}</small></div><span class="stat-note">${r.status==='missing'?'Awaiting a benchmark run':'Run saved without a screenshot'}</span></div></div></article>`;}
  function sortedCaptures() {
    return filteredCaptures().sort((a,b)=>state.sort==='fps'?(b.run.fps??-1)-(a.run.fps??-1):state.sort==='technology'?a.run.label.localeCompare(b.run.label):state.sort==='name'?a.name.localeCompare(b.name):b.run.timestamp.localeCompare(a.run.timestamp));
  }

  function coveragePanel() {
    const current=new Set(data.runs.filter(r=>!r.reference&&r.freshness==='current'&&r.status==='complete').map(r=>r.fixture_id));
    const any=new Set(data.runs.filter(r=>!r.reference).map(r=>r.fixture_id));
    const pct=data.fixtures.length?current.size/data.fixtures.length*100:0;
    return `<article class="panel"><h3>How much have we seen?</h3><p class="panel-subtitle">Coverage of the current executable build</p><div class="coverage-top"><div class="coverage-donut"><svg viewBox="0 0 110 110" aria-hidden="true"><circle cx="55" cy="55" r="47" fill="none" stroke="#30383a" stroke-width="7"/><circle cx="55" cy="55" r="47" fill="none" stroke="#c6ef80" stroke-width="7" stroke-dasharray="${pct*2.953} 295.31" stroke-linecap="round"/></svg><div>${num(pct,0)}<small>%</small></div></div><p><strong>${current.size} of ${data.fixtures.length} fixtures</strong>Completed with a matching build hash. Compilation is tracked separately.</p></div><div class="coverage-row"><span><i class="dot"></i>Current completed builds</span><b>${current.size}</b></div><div class="coverage-row"><span><i class="dot" style="background:var(--amber)"></i>Any saved run output</span><b>${any.size}</b></div><div class="coverage-row"><span><i class="dot" style="background:#596b72"></i>No saved run output</span><b>${data.fixtures.length-any.size}</b></div><div class="coverage-progress"><span style="width:${pct}%"></span></div><div class="chart-footnote">Build ${E(data.build?.fixture_version??'—')} · ${data.build?.published?'Both sets published':'Build status unrecorded'} · ${E(stamp(data.build?.built_at))}</div></article>`;
  }
  function renderOverview() {
    const images=sortedCaptures(),hero=images.find(c=>c.run.reference)||images[0];
    const heroHtml=`<article class="hero-card">${hero?`<img src="${E(hero.src)}" alt="Saved museum benchmark reference">`:''}<div class="hero-content">${badge(hero?.run.reference?'SAVED REFERENCE':hero?'SAVED CAPTURE':'YOUR BENCHMARK WORKSPACE','lime')}<h2>One scene. A world of differences.</h2><p>${hero?'A real saved capture from your workspace. Its provenance and build status stay attached as you compare.':'Your comparison wall starts here. Captures appear automatically when you save benchmark results.'}</p><button class="button primary" data-go="gallery">Explore the gallery ↗</button></div></article>`;
    $('view-overview').innerHTML=`<div class="overview-grid">${heroHtml}${coveragePanel()}</div>${heading('From the capture wall',`${images.length} saved images in this selection`,`<button class="text-button" data-go="gallery">View gallery ↗</button>`)}${images.length?`<div class="gallery-grid">${images.slice(0,3).map(captureCard).join('')}</div>`:empty('No captures match','Clear the filters or save a screenshot from one of the fixtures.')}<div class="chart-grid"><article class="panel">${heading('FPS at a glance','Recorded run averages, never estimated from screenshots')}${barsHtml(measuredRuns(),true)}</article><article class="panel"><h3>Your test bench, at a glance</h3><p class="panel-subtitle">Independent executables, shared museum assets</p><div class="details-list"><div class="detail-row"><span>Technology groups</span><strong>${data.groups.length}</strong></div><div class="detail-row"><span>Windows / DOS fixtures</span><strong>${data.fixtures.filter(g=>g.id!=='dos-vga').length} / ${data.fixtures.some(g=>g.id==='dos-vga')?1:0}</strong></div><div class="detail-row"><span>Build sets</span><strong>Clean + ReShade / working</strong></div><div class="detail-row"><span>Capture modes</span><strong>Matched + showcase</strong></div><div class="detail-row"><span>Timing</span><strong>Configurable duration + multiple captures</strong></div><div class="detail-row"><span>Scene controls</span><strong>Freeze · orbit · manual camera</strong></div></div><p class="chart-footnote">This is a read-only result browser. It does not install addons, change games, or start benchmark runs.</p><button class="button small" data-copy-command="1">Copy a frozen-run command</button></article></div>`;
  }
  function renderGallery() {
    const images=sortedCaptures(),missing=state.galleryMissing?uncapturedFixtures():[];
    const actions=`<div class="section-actions"><label class="check-label"><input id="showMissing" type="checkbox" ${state.galleryMissing?'checked':''}>Include fixtures without captures</label><select id="gallerySort" aria-label="Sort gallery"><option value="newest">Newest first</option><option value="technology">Technology</option><option value="fps">Highest FPS</option><option value="name">Image name</option></select>${state.compare.length?`<button class="button primary small" data-go="compare">Compare ${state.compare.length} →</button>`:''}</div>`;
    $('view-gallery').innerHTML=heading('Capture gallery',`${images.length} images${missing.length?' + '+missing.length+' fixtures awaiting captures':''}`,actions)+(images.length||missing.length?`<div class="gallery-grid">${images.map(captureCard).join('')}${missing.map(missingCard).join('')}</div>`:empty('Nothing in this view yet','Try a broader search or enable fixtures without captures to browse the full technology catalogue.',`<button class="button" data-show-missing="1">Browse untested fixtures</button>`));
    $('gallerySort').value=state.sort;
  }

  function barData(records, {group=state.chartGroup,metric=state.chartMetric}={}) {
    const groups=new Map();
    for(const r of records){const value=r[metric];if(typeof value!=='number'||!Number.isFinite(value))continue;
      const key=group==='fixture'?`${r.fixture_id} · ${r.suite} · ${r.mode}`:group==='group'?r.group:group==='transport'?r.transport:r.api;
      if(!groups.has(key))groups.set(key,{label:key,total:0,count:0,color:color(r.group)});
      const row=groups.get(key);row.total+=value;row.count++;}
    return [...groups.values()].map(g=>({...g,value:g.total/g.count})).sort((a,b)=>b.value-a.value);
  }
  function barsHtml(records,compact=false) {
    let rows=barData(records,compact?{group:'fixture',metric:'fps'}:{});if(!rows.length)return chartEmpty();const total=rows.length;
    if(compact||!state.allBars)rows=rows.slice(0,compact?7:16);
    const max=Math.max(...rows.map(r=>r.value),1);
    return `<div class="bars">${rows.map(r=>`<div class="bar-row" title="${E(r.label)}: ${num(r.value)} FPS, ${r.count} run average(s)"><span class="bar-label">${E(r.label)}</span><div class="bar-track"><div class="bar-fill" style="width:${r.value/max*100}%;background:${r.color}"></div></div><span class="bar-value">${num(r.value)}</span></div>`).join('')}</div><p class="chart-footnote">${compact?'':'Showing '+rows.length+' of '+total+' bars. '}Each grouped value is an arithmetic mean of recorded run averages. Software, hidden-window, different resolutions, and DOS workloads are not interchangeable benchmarks.</p>`;
  }
  function timelineHtml(records) {
    const selected=records.filter(r=>r.samples?.length).slice(0,4);if(!selected.length)return chartEmpty();
    const maxT=Math.max(1,...selected.flatMap(r=>r.samples.map(p=>p.seconds))),maxF=Math.max(1,...selected.flatMap(r=>r.samples.map(p=>p.fps)))*1.1;
    const X=t=>45+t/maxT*595,Y=f=>230-f/maxF*205;
    let svg='<svg class="timeline" viewBox="0 0 660 270" role="img" aria-label="Recorded FPS over elapsed seconds">';
    for(let i=0;i<=4;i++){const y=Y(maxF*i/4);svg+=`<line class="grid-line" x1="45" y1="${y}" x2="640" y2="${y}"/><text x="35" y="${y+3}" text-anchor="end">${num(maxF*i/4,0)}</text><text x="${X(maxT*i/4)}" y="252" text-anchor="middle">${num(maxT*i/4,1)}s</text>`;}
    const colors=['#c6ef80','#83d8dc','#c8a2e8','#e8bc78'];
    selected.forEach((r,i)=>{svg+=`<polyline points="${r.samples.map(p=>X(p.seconds)+','+Y(p.fps)).join(' ')}" fill="none" stroke="${colors[i]}" stroke-width="2"/>`;
      for(const p of r.samples)svg+=`<circle cx="${X(p.seconds)}" cy="${Y(p.fps)}" r="3" fill="${colors[i]}"><title>${E(r.fixture_id)} · ${num(p.seconds)}s · ${num(p.fps)} FPS</title></circle>`;});
    return svg+'</svg><div class="chart-legend">'+selected.map((r,i)=>`<span><i class="dot" style="background:${colors[i]}"></i>${E(r.fixture_id)} / ${E(r.mode)}</span>`).join('')+'</div><p class="chart-footnote">Up to four latest measured series in this selection. These are sampled FPS values, not raw frame-time percentiles or 1% lows.</p>';
  }
  function allowedBackend(mode) {
    return (state.mode==='all'||state.mode===mode) &&
      (state.execution==='native'?mode==='native':state.execution==='all'||mode!=='native') &&
      (state.suite==='all'||state.suite===(mode==='native'?'clean':'working'));
  }
  function performanceAnalysis(metric=state.chartMetric) {
    // Native references survive the display-only set/run-type filters.
    const context=data.runs.filter(r=>matches(r,'',['suite','mode','execution']))
      .filter(r=>state.execution==='all'||r.mode==='native'||r.execution_mode===state.execution||r.requested_execution_mode===state.execution);
    return window.BenchPerformance.analyse(context, {backends:[...state.perfBackends].filter(allowedBackend),
      metric, group:state.chartGroup, route:state.execution==='native'?'all':state.execution,
      pairedOnly:state.pairedOnly, sort:state.perfSort});
  }
  function percent(value) {return value==null?'--':`${value>0?'+':''}${num(value)}%`;}
  function speed(value) {return value==null?'--':`${num(value,2)}x`;}
  const metricLabel = metric => ['game_fps','nvidia_game'].includes(metric)?'game-loop':window.BenchPerformance.isNeural(metric)?'processed':'output';
  function perfSummary(analysis) {
    const neural=window.BenchPerformance.isNeural(analysis.metric);
    const delta=analysis.speedup==null?'':`${num(Math.abs(analysis.speedup-1)*100)}% ${analysis.speedup>=1?'higher':'lower'} ${metricLabel(analysis.metric)} FPS`;
    return `<div class="performance-summary">${analysis.summaries.map(s=>`<div class="performance-stat" data-backend="${s.mode}"><span><i class="dot" style="background:${backendColor(s.mode)}"></i>${E(modeName(s.mode))} average</span><strong>${num(s.meanFps)} <small>${metricLabel(analysis.metric)} FPS</small></strong><p>${s.count} matched cases${s.mode!=='native'&&!neural?`<br>${percent(s.meanDrop)} mean output FPS loss vs native`:''}</p></div>`).join('')}<div class="performance-stat" data-stat="speedup"><span>Phoenix / NVIDIA DLSS5</span><strong>${speed(analysis.speedup)}</strong><p>${delta}<br>${analysis.pairCount} pairs; geometric mean of FPS ratios</p></div></div>`;
  }
  function groupedBars(analysis) {
    if(!analysis.backends.length)return empty('No run types selected','No comparable series in this selection.');
    if(!analysis.rows.length)return empty('No matching timings','No completed current-build measurements match this selection. DOS guest-clock and host-clock rates are separate workloads.');
    const rows=state.allBars?analysis.rows:analysis.rows.slice(0,20);
    const values=rows.flatMap(r=>Object.values(r.values)).filter(v=>typeof v==='number'&&Number.isFinite(v));
    const percentMetric=window.BenchPerformance.isPercentage(analysis.metric), divergent=analysis.metric==='drop';
    const max=Math.max(...values.map(Math.abs),1);
    const label=value=>percentMetric?`${num(value)}%`:num(value);
    const scale=value=>state.logScale&&!percentMetric?Math.log1p(Math.max(value,0))/Math.log1p(max):Math.abs(value)/max;
    const legend=analysis.backends.map(mode=>`<span><i class="dot" style="background:${backendColor(mode)}"></i>${E(modeName(mode))}</span>`).join('');
    const bars=rows.map(row=>`<div class="backend-chart-row" data-fixture="${E(row.fixture||row.label)}"><div class="backend-chart-label"><strong title="${E(row.label)}">${E(row.label)}</strong><span>${row.width?`${row.width} x ${row.height}`:`${row.count} matched fixture${row.count===1?'':'s'}`}${row.fixture==='dos-vga'?row.runs?.native?' / DOS guest clock':' / DOS host clock':''}</span></div><div class="backend-series">${analysis.backends.map(mode=>{
      const value=row.values[mode], missing=value==null;
      const message=missing?(row.states[mode]==='failed'?'Failed':row.states[mode]==='not_applicable'?'Not applicable':row.states[mode]==='complete'?'No comparable timing':'Not available'):label(value);
      const width=missing?0:Math.min(100,scale(value)*100)*(divergent ? 0.5 : 1);
      const left=divergent?(value<0?50-width:50):0;
      const title=`${row.label} - ${modeName(mode)}: ${message}${analysis.metric==='drop'?' FPS loss vs native':''}`;
      return `<div class="backend-bar ${missing?'missing':''}" title="${E(title)}"><span class="backend-series-name">${E(modeName(mode))}</span><div class="backend-track ${divergent?'divergent':''}">${!missing?`<span class="backend-fill" style="left:${left}%;width:${width}%;background:${backendColor(mode)}"></span>`:''}</div><span class="backend-value ${row.states[mode]==='failed'?'failed-value':''}">${E(message)}</span></div>`;
    }).join('')}</div></div>`).join('');
    return `<div class="chart-legend backend-legend">${legend}<span>${window.BenchPerformance.isNvidiaRelative(analysis.metric)?'NVIDIA = 100%; higher is faster':divergent?'Negative = faster than native':state.logScale&&!percentMetric?'Log1p scale':'Linear scale'}</span></div><div class="backend-chart ${divergent?'drop-chart':''}">${bars}</div><p class="chart-footnote">Showing ${rows.length} of ${analysis.rows.length} ${state.chartGroup==='fixture'?'fixture/path cases':'groups'}. ${state.chartGroup!=='fixture'?'Grouped bars use the same matched cases for every displayed backend. ':''}Missing or failed measurements are not zero FPS.</p>`;
  }
  function comparisonTable(analysis) {
    const cohorts=state.pairedOnly?analysis.matched:analysis.cohorts;
    const metric=window.BenchPerformance.metricKey(analysis.metric);
    const B=window.BenchPerformance;
    const headers=analysis.backends.map(m=>`<th>${E(modeName(m))} ${metricLabel(analysis.metric)} FPS</th>`).join('');
    return `<div class="table-shell comparison-table"><table><thead><tr><th>Fixture</th><th>Resolution</th>${headers}<th>Phoenix / NVIDIA</th><th>NVIDIA execution</th><th>Phoenix execution</th></tr></thead><tbody>${cohorts.map(c=>{
      const n=B.rate(c.runs.nvidia,metric),p=B.rate(c.runs.phoenix,metric);
      const ratio=B.consistent(c)&&analysis.backends.includes('nvidia')&&analysis.backends.includes('phoenix')&&n&&p?p/n:null;
      const routeCell=mode=>{const r=c.runs[mode];return !r||!analysis.backends.includes(mode)?'--':`${executionBadge(r)}${r.status==='failed'?` ${badge('Failed','red')}`:''}`;};
      return `<tr><td><strong>${E(c.label)}</strong></td><td>${c.width||'--'} x ${c.height||'--'}</td>${analysis.backends.map(mode=>`<td title="${E(c.runs[mode]?.[metric==='fps'?'fps_scope':'neural_fps_scope']||'')}">${['failed','not_applicable'].includes(c.runs[mode]?.status)?statusBadge(c.runs[mode]):num(B.rate(c.runs[mode],metric))}</td>`).join('')}<td>${speed(ratio)}</td><td title="${E(c.runs.nvidia?.processing?.fallback_reason||c.runs.nvidia?.error||'')}">${routeCell('nvidia')}</td><td title="${E(c.runs.phoenix?.processing?.fallback_reason||c.runs.phoenix?.error||'')}">${routeCell('phoenix')}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function executionRankingTable() {
    const context=data.runs.filter(r=>matches(r,'',['suite','mode','execution']));
    const rows=window.BenchPerformance.executionRankings(context).filter(r=>state.perfBackends.has(r.backend));
    if (!rows.some(r=>r.passed||r.failed)) return '';
    return `<section class="performance-section" id="executionRanking">${heading('x86 execution comparison','Fresh completed outputs over the same successful fixtures per renderer. Startup-affected cases include initialization beyond the five-second fixture warmup; these are not steady-state GPU timings.')}<div class="table-shell"><table><thead><tr><th>Renderer</th><th>Execution path</th><th>Passed / failed</th><th>Matched fixtures</th><th>Mean processed FPS</th><th>Speed vs helper</th><th>Fastest or within 1%</th><th>Startup affected</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${E(modeName(r.backend))}</td><td>${E(r.label)}</td><td>${r.passed} / ${r.failed}</td><td>${r.matched}</td><td>${num(r.meanFps)}</td><td>${speed(r.speedup)}</td><td>${r.wins}</td><td>${r.startupAffected}</td></tr>`).join('')}</tbody></table></div></section>`;
  }
  function renderPerformance() {
    let a=performanceAnalysis();
    if((['native','nvidia','phoenix'].includes(state.perfSort)&&!a.backends.includes(state.perfSort))||
       (state.perfSort==='ratio'&&(state.chartGroup!=='fixture'||!a.backends.includes('nvidia')||!a.backends.includes('phoenix')))){
      state.perfSort='name';a=performanceAnalysis();
    }
    const neural=window.BenchPerformance.isNeural(a.metric), throughput=neural?a:performanceAnalysis('neural_fps');
    const backendChoices=['native','nvidia','phoenix'].map(mode=>{
      const allowed=allowedBackend(mode)&&!((neural||window.BenchPerformance.isNvidiaRelative(a.metric))&&mode==='native');
      return `<label><input type="checkbox" data-perf-backend="${mode}" ${state.perfBackends.has(mode)&&allowed?'checked':''} ${!allowed?'disabled':''}><i class="dot" style="background:${backendColor(mode)}"></i>${E(modeName(mode))}</label>`;
    }).join('');
    const controls=`<div class="performance-controls">
      <fieldset class="backend-choices"><legend>Run types</legend>${backendChoices}</fieldset>
      <label>Metric<select id="chartMetric">
        <option value="fps">Output FPS (fresh frames for enhanced runs)</option><option value="neural_fps">Processed-frame FPS</option><option value="game_fps">Game render loop FPS (includes repeats)</option>
        <option value="drop">FPS loss vs native (%)</option><option value="retention">Native FPS retained (%)</option>
        <option value="nvidia_neural">Processed FPS vs NVIDIA (%)</option><option value="nvidia_game">Game FPS vs NVIDIA (%)</option>
      </select></label>
      <label>Group by<select id="chartGroup">
        <option value="fixture">Individual fixture</option><option value="group">Technology group</option>
        <option value="api">Application API</option><option value="transport">Rendering transport</option>
        <option value="architecture">Architecture</option><option value="execution">Execution route</option>
      </select></label>
      <label>Processing route<select id="perfRoute"><option value="all">All routes</option>
        <option value="in_process">In process</option><option value="helper">Background process</option><option value="in_process_x64_library">x64 library inside x86</option><option value="in_process_x86_driver">x86 Phoenix + native driver</option><option value="in_process_portable">Portable in process</option><option value="native">Native baseline</option><option value="not_started">Not started</option></select></label>
      <label>Sort<select id="perfSort">
        <option value="name">Fixture / group name</option><option value="value">Highest chart value</option>
        <option value="native" ${!a.backends.includes('native')?'disabled':''}>Native value</option>
        <option value="nvidia" ${!a.backends.includes('nvidia')?'disabled':''}>NVIDIA value</option>
        <option value="phoenix" ${!a.backends.includes('phoenix')?'disabled':''}>Phoenix value</option>
        <option value="ratio" ${state.chartGroup!=='fixture'||!a.backends.includes('nvidia')||!a.backends.includes('phoenix')?'disabled':''}>Phoenix / NVIDIA ratio</option>
      </select></label>
      <label class="check-label"><input id="allBars" type="checkbox" ${state.allBars?'checked':''}>All bars</label>
      <label class="check-label"><input id="pairedOnly" type="checkbox" ${state.pairedOnly?'checked':''}>Matched fixtures only</label>
      <label class="check-label"><input id="logScale" type="checkbox" ${state.logScale?'checked':''} ${window.BenchPerformance.isPercentage(a.metric)?'disabled':''}>Log scale</label>
    </div>`;
    const summaries=`<div class="table-shell"><table><thead><tr><th>Backend</th><th>Matched fixtures</th><th>Average ${metricLabel(a.metric)} FPS</th><th title="Arithmetic mean of each fixture's output FPS loss, equally weighted">Mean per-fixture output FPS loss</th><th title="1 minus mean enhanced output FPS divided by mean native FPS">Drop in mean output FPS</th><th title="Geometric mean of per-fixture enhanced output/native FPS ratios">Normalized output FPS retained</th></tr></thead><tbody>${a.summaries.map(s=>`<tr><td>${E(modeName(s.mode))}</td><td>${s.count}</td><td>${num(s.meanFps)}</td><td>${percent(s.meanDrop)}</td><td>${percent(s.dropInMean)}</td><td>${s.geometricRetention==null?'--':num(s.geometricRetention*100)+'%'}</td></tr>`).join('')}</tbody></table></div>`;
    const routes=a.routeCounts;
    const details=(state.pairedOnly?a.matched:a.cohorts).flatMap(c=>a.backends.map(mode=>c.runs[mode]).filter(Boolean));
    const pairedNote=`${a.matched.length} matched cases / ${a.cohorts.length} fixture/path cases in selection. ${a.failed} failed runs; ${a.untimed} completed runs without this timing. Only successful current-build results with matching binary, profile, resolution and scene state enter matched averages. Hidden native/NVIDIA references remain available for relative metrics.`;
    $('view-performance').innerHTML=`${heading('Backend comparison',`Output FPS counts fresh enhanced results, not repeated background-host presentations. Game-loop FPS is a separate metric.`,`<button class="button small" data-export-performance="1">Export comparison CSV</button>`)}${controls}${perfSummary(a)}<p class="performance-context">${E(pairedNote)}</p><section class="performance-plot" aria-label="Backend comparison bars">${groupedBars(a)}</section><section class="performance-section">${heading('Overall FPS impact','The same matched fixture set is used for every displayed average.')}${summaries}<div class="performance-breakdown"><div><h3>Head to head</h3><p><strong>${a.phoenixWins}</strong> Phoenix faster <span>/</span> <strong>${a.nvidiaWins}</strong> NVIDIA faster <span>/</span> <strong>${a.ties}</strong> within 1%</p><p>Median Phoenix / NVIDIA: ${speed(a.medianSpeedup)}. Ratios use ${metricLabel(a.metric)} FPS.</p><p>Fresh-output Phoenix / NVIDIA: <strong>${speed(throughput.speedup)}</strong> across ${throughput.pairCount} paired fixtures.</p></div><div><h3>Where enhancement ran</h3><p><strong>${routes.in_process}</strong> in process <span>/</span> <strong>${routes.helper}</strong> background process${routes.other?` <span>/</span> ${routes.other} unknown`:''}</p><p>Successful selected enhancement runs, including untimed DOS. Native baselines are excluded.</p></div></div></section><section class="performance-section">${heading('Per-fixture comparison','Observed execution routes, with failures retained explicitly.')}${comparisonTable(a)}</section><details class="performance-details"><summary>Recorded FPS samples and individual runs</summary><div class="chart-grid"><section>${heading('Output FPS through time')}${timelineHtml(details.filter(r=>r.fps!=null))}</section></div>${resultsTable(details)}</details><p class="chart-footnote">Hidden-window, frozen-scene compatibility measurements. Different APIs, software renderers and resolutions are separate workloads; aggregate statistics are descriptive, not a playable-performance score or a visual-quality rating.</p>`;
    document.querySelector('.performance-plot').insertAdjacentHTML('afterend',executionRankingTable());
    $('chartGroup').value=state.chartGroup;$('chartMetric').value=state.chartMetric;
    $('perfRoute').value=state.perfRoute;$('perfSort').value=state.perfSort;
  }

  function resultRows(){return [...filteredRuns(),...missingFixtures()];}
  function resultsTable(rows) {
    if(!rows.length)return empty('No results in this selection','Clear a filter or save benchmark results to see them here.');
    const sorted=[...rows].sort((a,b)=>{const key=state.tableSort;const av=key==='fixture'?(a.fixture_id||a.label):a[key],bv=key==='fixture'?(b.fixture_id||b.label):b[key];if(av==null&&bv==null)return 0;if(av==null)return 1;if(bv==null)return -1;const result=typeof av==='number'?av-bv:String(av).localeCompare(String(bv));return state.tableDesc?-result:result;});
    const cols=[['fixture','Fixture'],['group','Technology group'],['transport','Transport'],['architecture','Arch'],['suite','Set'],['mode','Mode'],['execution_label','Requested path'],['execution_mode','Processing location'],['fps','Output FPS'],['game_fps','Game-loop FPS'],['neural_fps','Processed FPS'],['seconds','Seconds'],['freshness','Build'],['status','Outcome']];
    const cell=(r,key)=>key==='fixture'?`<strong>${E(r.fixture_id||r.label)}</strong>`:key==='suite'?E(suiteName(r.suite)):key==='execution_mode'?executionBadge(r):key==='freshness'?(r.status==='missing'?badge('No run'):freshnessBadge(r)):key==='status'?`<span title="${E(r.error)}">${statusBadge(r)}</span>`:['fps','game_fps','neural_fps','seconds'].includes(key)?num(r[key]):E(r[key]);
    return `<div class="table-shell"><table><thead><tr>${cols.map(([key,title])=>`<th><button data-table-sort="${key}">${E(title)}${key===state.tableSort?(state.tableDesc?' ↓':' ↑'):''}</button></th>`).join('')}<th>Captures</th></tr></thead><tbody>${sorted.map(r=>`<tr>${cols.map(([key])=>`<td>${cell(r,key)}</td>`).join('')}<td>${r.captures?.length?`<button class="metric-button" data-open="${E(r.captures[0])}">${r.captures.length} image${r.captures.length===1?'':'s'}</button>`:'—'}</td></tr>`).join('')}</tbody></table></div><div class="table-foot">${sorted.length} rows · Missing values are shown as —, never as zero FPS.</div>`;
  }
  function renderResults() {$('view-results').innerHTML=heading('Full fixture inventory',`${resultRows().length} rows match the active filters`,`<button class="button small" data-export-json="1">↓ Export JSON</button>`)+resultsTable(resultRows());}

  function compareOptions(selected) {
    return '<option value="">Choose a saved capture…</option>'+[...captures.values()].map(c=>`<option value="${E(c.id)}" ${c.id===selected?'selected':''}>${E(c.run.label)} · ${E(c.run.architecture)} · ${E(c.run.mode)} · ${E(captureTime(c))} · ${E(c.name)}</option>`).join('');
  }
  function renderCompare() {
    differenceGeneration++;
    const selected=state.compare.map(id=>captures.get(id)).filter(Boolean);
    const letters='ABCD';const slots=Math.max(2,selected.length);
    let html=`<div class="compare-toolbar"><div><h2 style="font-size:17px;font-weight:500;margin:0">Visual comparison</h2><p style="font-size:10px;margin:5px 0 0">Select captures below or add them from the gallery. Up to four side by side.</p></div><div class="section-actions"><div class="segmented"><button data-compare-mode="sides" class="${state.compareMode==='sides'?'active':''}">Side by side</button><button data-compare-mode="wipe" class="${state.compareMode==='wipe'?'active':''}" ${selected.length!==2?'disabled':''}>Wipe</button><button data-compare-mode="difference" class="${state.compareMode==='difference'?'active':''}" ${selected.length!==2?'disabled':''}>Pixel difference</button></div><button class="text-button" data-clear-compare="1">Clear</button></div></div>`;
    html+='<div class="compare-slots">'+Array.from({length:slots},(_,i)=>{const c=selected[i],r=c?.run;return `<div class="compare-slot"><div class="slot-header"><span class="slot-letter">${letters[i]}</span><select data-compare-slot="${i}" aria-label="Capture ${letters[i]}">${compareOptions(c?.id)}</select>${c?`<button class="icon-button" data-remove-slot="${i}" aria-label="Remove capture ${letters[i]}">×</button>`:''}</div><div class="slot-details">${r?`${E(suiteName(r.suite))} · ${E(r.mode)} · ${E(r.freshness)}<span>${num(r.fps)} FPS</span>`:'<span>Pick a real saved capture to begin.</span>'}</div></div>`;}).join('')+'</div>';
    if(!selected.length){html+=empty('Your comparison canvas is ready','Choose two captures to unlock the wipe slider and pixel-difference view. With more captures, compare up to four technologies side by side.');$('view-compare').innerHTML=html;return;}
    const mixed=new Set(selected.map(c=>[c.run.mode,c.run.architecture,c.run.suite,c.run.background,c.run.width,c.run.height].join('|'))).size>1;
    if(mixed||selected.some(c=>c.run.freshness!=='current'||c.run.status!=='complete'))html+='<div class="comparison-notice">These captures differ in context, are from older/unverified builds, or are incomplete. Visual differences are not proof of renderer quality or DLSS correctness. Check mode, camera, capture time, dimensions and set before drawing conclusions.</div>';
    if(state.compareMode==='sides'||selected.length!==2){html+=`<div class="compare-stage sides">${selected.map((c,i)=>`<div class="side-image"><span class="side-label">${letters[i]} · ${E(c.run.label)} · ${E(captureTime(c))}</span><img src="${E(c.src)}" alt="Capture ${letters[i]}: ${E(c.run.label)}" data-open="${E(c.id)}"></div>`).join('')}</div>`;}
    else if(state.compareMode==='wipe'){html+=`<div class="compare-stage wipe-stage"><img src="${E(selected[1].src)}" alt="Capture B"><img id="wipeOverlay" src="${E(selected[0].src)}" alt="Capture A" style="clip-path:inset(0 ${100-state.wipe}% 0 0)"><div class="wipe-line" id="wipeLine" style="left:${state.wipe}%"></div><span class="side-label">A · ${E(selected[0].run.label)}</span><span class="side-label" style="left:auto;right:12px">B · ${E(selected[1].run.label)}</span></div><div class="wipe-controls"><span>A</span><input id="wipeSlider" type="range" min="0" max="100" value="${state.wipe}" aria-label="Reveal amount of capture A"><span>B</span></div><p class="chart-footnote">Both images are fitted into the same viewer. Use pixel difference for a pixel-aligned comparison; it requires identical native dimensions.</p>`;}
    else html+=`<div class="chart-controls"><span>Difference brightness</span><select id="differenceGain"><option value="1">1×</option><option value="4">4×</option><option value="10">10×</option></select><button class="button small" id="downloadDifference" disabled>↓ Save difference PNG</button></div><div id="differenceStage" class="difference-wrap"><p>Loading original pixels…</p></div><p id="differenceMetrics" class="chart-footnote"></p>`;
    html+='<div class="compare-stats">'+selected.map((c,i)=>`<div class="compare-stat">${letters[i]} · ${E(c.run.label)}<strong>${num(c.run.fps)} <small style="font-size:10px;color:var(--muted)">output FPS</small></strong><p style="font-size:10px">${E(c.run.group)} · ${E(c.run.architecture)}<br>${E(c.run.mode)} · capture ${E(captureTime(c))}<br>${E(suiteName(c.run.suite))} · ${E(c.run.freshness)}</p><div class="badges">${statusBadge(c.run)}${executionBadge(c.run)}<a class="button small" href="${E(c.src)}" download="${E(c.name)}">↓ Original</a></div></div>`).join('')+'</div>';
    $('view-compare').innerHTML=html;
    if($('differenceGain')){$('differenceGain').value=String(state.gain);drawDifference(selected,differenceGeneration);}
  }

  async function drawDifference(selected,generation) {
    try {
      const images=await Promise.all(selected.map(c=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Could not load a capture.'));image.src=c.src;})));
      if(generation!==differenceGeneration)return;
      const [a,b]=images;
      if(a.naturalWidth!==b.naturalWidth||a.naturalHeight!==b.naturalHeight){$('differenceStage').innerHTML=empty('Different native dimensions',`A is ${a.naturalWidth} × ${a.naturalHeight}; B is ${b.naturalWidth} × ${b.naturalHeight}. Choose matching sizes. Images are never silently resized for pixel difference.`);return;}
      const w=a.naturalWidth,h=a.naturalHeight;
      if(w*h>17000000)throw new Error('Images are too large for the in-browser difference viewer.');
      const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d',{willReadFrequently:true});
      ctx.drawImage(a,0,0);const pa=ctx.getImageData(0,0,w,h);ctx.clearRect(0,0,w,h);ctx.drawImage(b,0,0);const pb=ctx.getImageData(0,0,w,h);const out=ctx.createImageData(w,h);let total=0,changed=0;
      for(let i=0;i<pa.data.length;i+=4){let different=false;for(let k=0;k<3;k++){const d=Math.abs(pa.data[i+k]-pb.data[i+k]);total+=d;different||=d!==0;out.data[i+k]=Math.min(255,d*state.gain);}out.data[i+3]=255;if(different)changed++;}
      ctx.putImageData(out,0,0);$('differenceStage').replaceChildren(canvas);
      $('differenceMetrics').textContent=`${w} × ${h} native pixels · Mean absolute RGB difference: ${num(total/(w*h*3),3)} / 255 · Changed pixels: ${num(changed/(w*h)*100,2)}%. Display gain does not change these measurements. This is an image comparison, not a temporal-quality score.`;
      $('downloadDifference').disabled=false;$('downloadDifference').onclick=()=>canvas.toBlob(blob=>downloadBlob(blob,'museum-pixel-difference.png'),'image/png');
    }catch(error){if(generation===differenceGeneration&&$('differenceStage'))$('differenceStage').innerHTML=empty('Pixel difference unavailable',error.message+' If opened as a file, use Dashboard.cmd to enable local image reads.');}
  }

  function render(){indexData();renderChrome();({overview:renderOverview,gallery:renderGallery,compare:renderCompare,performance:renderPerformance,results:renderResults}[state.view])();}
  function navigate(view){if(!['overview','gallery','compare','performance','results'].includes(view))view='overview';state.view=view;if(location.hash!==`#${view}`)history.replaceState(null,'',`#${view}`);render();}
  function pick(id){if(!captures.has(id))return;if(state.compare.includes(id))state.compare=state.compare.filter(x=>x!==id);else if(state.compare.length<4)state.compare.push(id);else{toast('Choose up to four captures. Remove one to add another.');return;}if(state.compare.length!==2)state.compareMode='sides';remember();render();}
  function openCapture(id){const c=captures.get(id);if(!c)return;const r=c.run;$('lightboxContent').innerHTML=`<img class="lightbox-image" src="${E(c.src)}" alt="${E(r.label)} original capture"><div class="lightbox-caption"><div><h3>${E(r.label)} · ${E(r.architecture)}</h3><p>${E(c.id)}</p><div class="badges">${statusBadge(r)}${freshnessBadge(r)}${executionBadge(r)}${badge(r.mode)}${badge(captureTime(c))}</div><p>${num(r.fps)} output FPS · ${E(suiteName(r.suite))} · ${E(r.transport)} · ${E(stamp(r.timestamp))}</p></div><div class="section-actions"><button class="button primary" data-lightbox-pick="${E(id)}">${state.compare.includes(id)?'Remove from compare':'+ Add to compare'}</button><a class="button" href="${E(c.src)}" download="${E(c.name)}">↓ Original image</a></div></div>`;$('lightbox').showModal();}
  function downloadBlob(blob,name){if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);}
  function exportCsv(){const rows=resultRows(),fields=['fixture_id','group','api','transport','architecture','suite','mode','execution_variant','execution_label','requested_execution_mode','execution_mode','fps','game_fps','neural_fps','fps_scope','seconds','frames','freshness','status','error'];const quote=v=>{let s=String(v??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};const csv=[fields.join(','),...rows.map(r=>fields.map(k=>quote(r[k])).join(','))].join('\r\n');downloadBlob(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}),'museum-benchmark-results.csv');toast(`Exported ${rows.length} filtered result rows.`);}
  function exportPerformance() {
    const a=performanceAnalysis(), B=window.BenchPerformance, cohorts=state.pairedOnly?a.matched:a.cohorts;
    const fields=['fixture','execution_variant','execution_label','width','height','profile','metric',...a.backends.flatMap(m=>[m+'_value',m+'_status',m+'_execution',m+'_game_loop_fps',m+'_processed_fps',m+'_output_fps_loss_pct']),'phoenix_over_nvidia'];
    const records=cohorts.map(c=>{
      const record={fixture:c.fixture,execution_variant:c.execution_variant,execution_label:c.label,width:c.width,height:c.height,profile:Object.values(c.runs)[0]?.benchmark_profile,metric:a.metric};
      const rawMetric=B.metricKey(a.metric), baseline=B.rate(c.runs.native,'fps');
      for(const m of a.backends){const r=c.runs[m],game=B.rate(r,'fps');
        record[m+'_value']=B.valueFor(c,m,a.metric);
        record[m+'_status']=r?.status||'missing';record[m+'_execution']=r?.execution_mode;
        record[m+'_game_loop_fps']=B.rate(r,'game_fps');record[m+'_processed_fps']=B.rate(r,'neural_fps');
        record[m+'_output_fps_loss_pct']=baseline&&game&&B.consistent(c)?100*(1-game/baseline):null;
      }
      const n=B.rate(c.runs.nvidia,rawMetric),p=B.rate(c.runs.phoenix,rawMetric);
      record.phoenix_over_nvidia=a.backends.includes('nvidia')&&a.backends.includes('phoenix')&&B.consistent(c)&&n&&p?p/n:null;
      return record;
    });
    const quote=value=>{let s=String(value??'');if(typeof value==='string'&&/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
    downloadBlob(new Blob(['\uFEFF'+[fields.join(','),...records.map(r=>fields.map(k=>quote(r[k])).join(','))].join('\r\n')],{type:'text/csv;charset=utf-8'}),'museum-backend-comparison.csv');
    toast(`Exported ${records.length} fixture comparisons.`);
  }
  async function refresh(silent=false){
    if(data.public_snapshot){$('connection').textContent='Published snapshot';$('refresh').textContent='Reload snapshot';document.querySelector('.sidebar-bottom').innerHTML='<span class="status-dot"></span> PUBLISHED RESULTS<span>Read-only snapshot</span>';if(!silent)location.reload();return;}
    if(!/^https?:$/.test(location.protocol)){if(!silent)toast('Offline snapshot. Run Dashboard.cmd to refresh results from disk.');return;}
    try {const response=await fetch('../api/data',{cache:'no-store'});if(!response.ok)throw new Error('Server unavailable');const next=await response.json();if(!Array.isArray(next.fixtures)||!Array.isArray(next.captures))throw new Error('Invalid result index');data=next;isLive=true;$('connection').textContent='Local data connected';$('connection').classList.add('live');render();if(!silent)toast('Results refreshed. No tests launched.');}
    catch {isLive=false;$('connection').textContent='Offline snapshot';$('connection').classList.remove('live');if(!silent)toast('Could not reach the local indexer. Start Dashboard.cmd to refresh.');}
  }

  ['search','suite','arch','mode','execution','freshness','outcome','motion'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',e=>{state[id==='search'?'query':id]=e.target.value;if(id==='execution')state.perfRoute=e.target.value;render();}));
  const compactFilters=matchMedia('(max-width:600px)');
  const sizeFilters=()=>{$('filterDetails').open=!compactFilters.matches;};
  compactFilters.addEventListener('change',sizeFilters);sizeFilters();
  $('groupSelect').addEventListener('change',e=>{if(e.target.value==='multiple')return;state.groups=e.target.value==='all'?new Set():new Set([e.target.value]);render();});
  $('clearGroup').onclick=()=>{state.groups.clear();render();};
  $('resetFilters').onclick=()=>{for(const id of ['suite','arch','mode','execution','freshness','outcome','motion']){state[id]='all';$(id).value='all';}state.query='';$('search').value='';state.groups.clear();state.perfBackends=new Set(['native','nvidia','phoenix']);state.perfRoute='all';state.pairedOnly=false;render();};
  $('refresh').onclick=()=>refresh();$('exportCsv').onclick=()=>state.view==='performance'?exportPerformance():exportCsv();
  $('closeLightbox').onclick=()=>$('lightbox').close();
  $('lightbox').addEventListener('click',e=>{if(e.target===$('lightbox'))$('lightbox').close();});
  document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)&&!$('lightbox').open){e.preventDefault();$('search').focus();}});
  document.addEventListener('click',async e=>{
    const button=e.target.closest('button,a,[data-open]');if(!button)return;
    if(button.dataset.view){e.preventDefault();navigate(button.dataset.view);}
    if(button.dataset.go)navigate(button.dataset.go);
    if(button.dataset.group){const g=button.dataset.group;state.groups.has(g)?state.groups.delete(g):state.groups.add(g);render();}
    if(button.dataset.pick)pick(button.dataset.pick);
    if(button.dataset.open)openCapture(button.dataset.open);
    if(button.dataset.lightboxPick){pick(button.dataset.lightboxPick);$('lightbox').close();}
    if(button.dataset.showMissing){state.galleryMissing=true;render();}
    if(button.dataset.compareMode){state.compareMode=button.dataset.compareMode;renderCompare();}
    if(button.dataset.removeSlot!==undefined){state.compare.splice(Number(button.dataset.removeSlot),1);state.compareMode='sides';remember();render();}
    if(button.dataset.clearCompare){state.compare=[];state.compareMode='sides';remember();render();}
    if(button.dataset.tableSort){state.tableDesc=state.tableSort===button.dataset.tableSort?!state.tableDesc:button.dataset.tableSort==='fps';state.tableSort=button.dataset.tableSort;render();}
    if(button.dataset.exportJson){downloadBlob(new Blob([JSON.stringify({generated_at:data.generated_at,results:resultRows(),notes:data.notes},null,2)],{type:'application/json'}),'museum-filtered-results.json');}
    if(button.dataset.exportPerformance)exportPerformance();
    if(button.dataset.copyCommand){const command='.\\Run-All.cmd --freeze --seconds 30 --capture-at 5,15,25';try{await navigator.clipboard.writeText(command);toast('Command copied. The dashboard has not started a run.');}catch{toast(command);}}
  });
  document.addEventListener('change',e=>{
    const t=e.target;
    if(t.id==='showMissing'){state.galleryMissing=t.checked;renderGallery();}
    if(t.id==='gallerySort'){state.sort=t.value;renderGallery();}
    if(t.id==='chartGroup'){state.chartGroup=t.value;if(t.value!=='fixture'&&state.perfSort==='ratio')state.perfSort='name';renderPerformance();}
    if(t.id==='chartMetric'){state.chartMetric=t.value;renderPerformance();}
    if(t.id==='allBars'){state.allBars=t.checked;renderPerformance();}
    if(t.dataset.perfBackend){t.checked?state.perfBackends.add(t.dataset.perfBackend):state.perfBackends.delete(t.dataset.perfBackend);renderPerformance();}
    if(t.id==='perfRoute'){state.perfRoute=t.value;state.execution=t.value;$('execution').value=t.value;render();}
    if(t.id==='perfSort'){state.perfSort=t.value;renderPerformance();}
    if(t.id==='pairedOnly'){state.pairedOnly=t.checked;renderPerformance();}
    if(t.id==='logScale'){state.logScale=t.checked;renderPerformance();}
    if(t.dataset.compareSlot!==undefined){const i=Number(t.dataset.compareSlot);if(t.value){state.compare[i]=t.value;}else state.compare.splice(i,1);state.compare=state.compare.filter(Boolean).slice(0,4);if(state.compare.length!==2)state.compareMode='sides';remember();render();}
    if(t.id==='differenceGain'){state.gain=Number(t.value);drawDifference(state.compare.map(id=>captures.get(id)),++differenceGeneration);}
  });
  document.addEventListener('input',e=>{if(e.target.id==='wipeSlider'){state.wipe=Number(e.target.value);$('wipeOverlay').style.clipPath=`inset(0 ${100-state.wipe}% 0 0)`;$('wipeLine').style.left=state.wipe+'%';}});
  window.addEventListener('hashchange',()=>navigate(location.hash.slice(1)));
  indexData();navigate(location.hash.slice(1)||'overview');
  // Refresh on explicit page load only. No automatic benchmark execution or background scheduling.
  refresh(true);
})();
