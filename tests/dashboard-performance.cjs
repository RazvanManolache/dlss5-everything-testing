'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const P = require('../dashboard/performance.js');

function run(fixture, mode, fps, extra={}) {
  return {id:`batch/${fixture}/${mode}`,fixture_id:fixture,mode,fps,game_fps:fps,
    neural_fps:mode==='native'?null:fps/2,group:'DirectX',api:'dx12',transport:'DirectX',
    architecture:'x64',status:'complete',freshness:'current',reference:false,
    timestamp:'2026-10-17T00:00:00+03:00',executable_sha256:'hash-'+fixture,
    benchmark_profile:'uncapped-1080p',comparison_batch:'runs/current',
    width:1920,height:1080,requested_seconds:20,warmup_seconds:5,vsync:false,
    measurement_complete:true,scene_mode:'showcase',controls:{frozen:true},background:true,
    execution_mode:mode==='native'?'native':'helper',...extra};
}
const trio=(fixture='fixture',rates=[100,50,75])=>['native','nvidia','phoenix'].map((m,i)=>run(fixture,m,rates[i]));
const close=(actual,expected)=>assert.ok(Math.abs(actual-expected)<1e-8,`${actual} != ${expected}`);

function x86Routes(fixture='x86') {
  const native=run(fixture,'native',100,{architecture:'x86',execution_variant:'baseline'});
  const rows=[native];
  for(const [variant,route,multiplier] of [['helper','helper',1],['x64-library','in_process_x64_library',2],['x86-driver','in_process_x86_driver',2.5]]) {
    for(const mode of ['nvidia','phoenix']) rows.push(run(fixture,mode,50,{id:`${fixture}/${mode}/${variant}`,architecture:'x86',
      execution_variant:variant,execution_label:variant,requested_execution_mode:route,execution_mode:route,
      neural_fps:(mode==='phoenix'?10:8)*multiplier,addon_sha256:'current',
      ...(variant==='x86-driver'&&mode==='nvidia'?{status:'not_applicable',fps:null,neural_fps:null}: {})}));
  }
  return rows;
}

test('execution variants remain separate and reuse one clean baseline without extra captures',()=>{
  const rows=x86Routes(),cohorts=P.collect(rows);
  assert.equal(cohorts.length,3);
  assert.deepEqual(new Set(cohorts.map(c=>c.execution_variant)),new Set(['helper','x64-library','x86-driver']));
  for(const c of cohorts)assert.equal(c.runs.native,rows[0]);
  assert.equal(P.analyse(rows,{route:'in_process_x64_library'}).cohorts.length,1);
  assert.equal(P.analyse(rows,{backends:['phoenix'],route:'in_process_x86_driver'}).matched.length,1);
});

test('x86 route rankings compare the same fixtures and count only the observed requested route',()=>{
  const rows=x86Routes(),ranking=P.executionRankings(rows);
  assert.equal(ranking.length,5);
  const nativeHost=ranking.find(r=>r.backend==='phoenix'&&r.variant==='x86-driver');
  close(nativeHost.meanFps,25);close(nativeHost.speedup,2.5);assert.equal(nativeHost.matched,1);
  assert.equal(nativeHost.wins,1);
  const nvidia=ranking.find(r=>r.backend==='nvidia'&&r.variant==='x64-library');
  close(nvidia.speedup,2);
  rows.find(r=>r.mode==='phoenix'&&r.execution_variant==='x64-library').execution_mode='helper';
  assert.equal(P.executionRankings(rows).find(r=>r.backend==='phoenix').matched,0);
});

test('incomplete provenance still keeps different requested execution variants separate',()=>{
  const rows=x86Routes().map(r=>({...r,benchmark_profile:null}));
  const cohorts=P.collect(rows);
  assert.equal(cohorts.filter(c=>c.runs.phoenix).length,3);
  assert.equal(P.analyse(rows).matched.length,0);
});

test('route rankings disclose initialization extending into the measured window',()=>{
  const rows=x86Routes();
  rows.find(r=>r.mode==='phoenix'&&r.execution_variant==='x64-library').startup_in_measurement=true;
  const ranking=P.executionRankings(rows);
  assert.equal(ranking.find(r=>r.backend==='phoenix'&&r.variant==='x64-library').startupAffected,1);
  assert.equal(ranking.find(r=>r.backend==='phoenix'&&r.variant==='helper').startupAffected,0);
});

test('matched means, native loss, normalized retention and head-to-head ratios',()=>{
  const a=P.analyse(trio());
  assert.equal(a.matched.length,1);assert.equal(a.rows.length,1);
  close(a.summaries[1].meanFps,50);close(a.summaries[1].meanDrop,50);
  close(a.summaries[2].meanDrop,25);close(a.summaries[2].dropInMean,25);
  close(a.summaries[2].geometricRetention,.75);close(a.speedup,1.5);
  assert.equal(a.phoenixWins,1);assert.equal(a.routeCounts.helper,2);
});
test('head-to-head overall ratio is geometric, not a ratio of pooled FPS',()=>{
  const a=P.analyse([...trio('a',[1000,100,200]),...trio('b',[1000,1000,500])]);
  close(a.speedup,1);assert.equal(a.phoenixWins,1);assert.equal(a.nvidiaWins,1);
});
test('mean per-fixture loss and loss in mean FPS are separately computed',()=>{
  const a=P.analyse([...trio('a',[1000,100,200]),...trio('b',[10,10,5])]);
  close(a.summaries[2].meanDrop,65);
  close(a.summaries[2].dropInMean,100*(1-205/1010));
});
test('failed, stale and invalid rates never become zero FPS or averaged samples',()=>{
  for(const extra of [{status:'failed'},{freshness:'stale'},{fps:NaN},{fps:Infinity},{fps:0}]){
    const rows=trio();Object.assign(rows[2],extra);
    const a=P.analyse(rows);assert.equal(a.matched.length,0);
    assert.equal(a.rows[0].values.phoenix,null);assert.equal(a.speedup,null);
  }
});
test('latest failure cannot resurrect an older passing measurement',()=>{
  const rows=trio(),failure={...rows[2],id:'new-failure',timestamp:'2026-10-17T01:00:00+03:00',status:'failed',fps:999};
  const a=P.analyse([...rows,failure]);assert.equal(a.failed,1);assert.equal(a.matched.length,0);
  assert.equal(a.rows[0].states.phoenix,'failed');assert.equal(a.rows[0].values.phoenix,null);
});
test('latest selection compares actual timestamps across UTC offsets',()=>{
  const rows=trio();rows[2].timestamp='2026-10-17T01:00:00+03:00';
  const later={...rows[2],id:'later',timestamp:'2026-10-16T23:00:00Z',status:'failed'};
  assert.equal(P.analyse([...rows,later]).matched.length,0);
});
test('profile, resolution, binary, batch, warmup and synchronization mismatches cannot pair',()=>{
  for(const extra of [{benchmark_profile:'other'},{width:1280},{executable_sha256:'other'},
    {comparison_batch:'runs/other'},{warmup_seconds:10},{vsync:true},{requested_seconds:30}]){
    const rows=trio();Object.assign(rows[2],extra);
    assert.equal(P.analyse(rows).matched.length,0);
  }
});
test('scene, motion, visibility and incomplete measurement mismatches cannot pair',()=>{
  for(const extra of [{scene_mode:'matched'},{controls:{frozen:false}},{controls:{frozen:true,camera_eye:[1,2,3]}},
    {gpu:'different rendering GPU'},{background:false},{measurement_complete:false}]){
    const rows=trio();Object.assign(rows[2],extra);
    assert.equal(P.analyse(rows).matched.length,0);
  }
});
test('NVIDIA and Phoenix addon versions must match when recorded',()=>{
  const rows=trio();rows[1].addon_sha256='old';rows[2].addon_sha256='new';
  assert.equal(P.analyse(rows).matched.length,0);
});
test('unknown provenance does not manufacture a matched pair',()=>{
  const rows=trio().map(r=>({...r,benchmark_profile:null}));
  assert.equal(P.analyse(rows).matched.length,0);
});
test('grouped bars average exactly the same matched fixtures for each backend',()=>{
  const rows=[...trio('a'),...trio('b',[200,60,80]),run('orphan','native',9999)];
  const a=P.analyse(rows,{group:'group'});
  assert.equal(a.rows.length,1);assert.equal(a.rows[0].count,2);
  close(a.rows[0].values.native,150);close(a.rows[0].values.nvidia,55);close(a.rows[0].values.phoenix,77.5);
});
test('neural throughput excludes native and never substitutes game FPS',()=>{
  const rows=trio();rows[1].neural_fps=10;rows[2].neural_fps=5;
  const a=P.analyse(rows,{metric:'neural_fps'});
  assert.deepEqual(a.backends,['nvidia','phoenix']);close(a.speedup,.5);
  close(a.rows[0].values.nvidia,10);close(a.rows[0].values.phoenix,5);
});
test('route filtering preserves native references and uses observed execution',()=>{
  const rows=[...trio('bridge'),...trio('direct').map(r=>({...r,execution_mode:r.mode==='native'?'native':'in_process'}))];
  const a=P.analyse(rows,{route:'helper'});
  assert.equal(a.cohorts.length,1);assert.equal(a.matched.length,1);
  assert.equal(a.summaries[0].meanFps,100);assert.equal(a.routeCounts.helper,2);
});
test('hidden native series can still supply the native reference for loss',()=>{
  const a=P.analyse(trio(),{backends:['nvidia','phoenix'],metric:'drop'});
  assert.deepEqual(a.backends,['nvidia','phoenix']);close(a.rows[0].values.nvidia,50);
  close(a.rows[0].values.phoenix,25);assert.equal(a.matched.length,1);
});
test('retention is distinct from loss, with native at 100 percent',()=>{
  const a=P.analyse(trio(),{metric:'retention'});
  close(a.rows[0].values.native,100);close(a.rows[0].values.phoenix,75);
});
test('measured game-loop gains retain negative loss rather than being clamped',()=>{
  const a=P.analyse(trio('fast',[100,150,200]),{metric:'drop'});
  close(a.rows[0].values.nvidia,-50);close(a.rows[0].values.phoenix,-100);
});
test('unassigned fixture metadata is displayed without breaking all comparisons',()=>{
  const row=run('unknown','native',50,{fixture_id:null,benchmark_profile:null});
  const a=P.analyse([row]);assert.equal(a.matched.length,0);assert.equal(a.rows.length,1);
  assert.equal(typeof a.rows[0].label,'string');
});
test('NVIDIA-normalized bars distinguish processed throughput from game FPS',()=>{
  const rows=trio();rows[1].neural_fps=20;rows[2].neural_fps=10;
  const processed=P.analyse(rows,{metric:'nvidia_neural'}),game=P.analyse(rows,{metric:'nvidia_game'});
  assert.deepEqual(processed.backends,['nvidia','phoenix']);
  close(processed.rows[0].values.nvidia,100);close(processed.rows[0].values.phoenix,50);
  close(game.rows[0].values.phoenix,150);close(processed.speedup,.5);
});

test('fresh-output and repeated game-loop rates stay distinct in charts and ratios',()=>{
  const rows=trio('async',[1000,20,25]);
  rows[1].game_fps=600;rows[2].game_fps=900;
  rows[1].neural_fps=20;rows[2].neural_fps=25;
  close(P.analyse(rows).speedup,1.25);
  close(P.analyse(rows,{metric:'game_fps'}).speedup,1.5);
  close(P.analyse(rows,{metric:'nvidia_game'}).rows[0].values.phoenix,150);
  assert.equal(P.metricKey('game_fps'),'game_fps');
});
test('hidden NVIDIA series remains the reference, but missing reference is never invented',()=>{
  const rows=trio(),a=P.analyse(rows,{backends:['phoenix'],metric:'nvidia_game'});
  close(a.rows[0].values.phoenix,150);
  assert.equal(P.analyse(rows.filter(r=>r.mode!=='nvidia'),{metric:'nvidia_game'}).rows[0].values.phoenix,null);
});
test('untimed successful DOS counts as execution evidence, never an FPS measurement',()=>{
  const rows=trio('dos').map(r=>({...r,fps:null,neural_fps:null,vsync:undefined,execution_mode:r.mode==='native'?'native':'in_process'}));
  const a=P.analyse(rows);assert.equal(a.matched.length,0);assert.equal(a.untimed,3);
  assert.equal(a.rows.length,1);
  assert.equal(a.routeCounts.in_process,2);assert.equal(a.speedup,null);
});

test('timed DOS enhances at its native resolution without inventing a matched guest-clock baseline',()=>{
  const rows=trio('dos-vga',[7.5,35,34.7]).map(r=>({...r,width:320,height:200,
    benchmark_profile:r.mode==='native'?'dos-guest-clock':'dos-host-clock',
    vsync:r.mode==='native'?null:true,background:r.mode==='native',
    execution_mode:r.mode==='native'?'native':'in_process',
    neural_fps:r.mode==='native'?null:r.fps}));
  const all=P.analyse(rows);
  assert.equal(all.rows.length,2);assert.equal(all.matched.length,0);
  const enhanced=P.analyse(rows,{metric:'neural_fps'});
  assert.equal(enhanced.matched.length,1);assert.equal(enhanced.pairCount,1);
  close(enhanced.rows[0].values.nvidia,35);close(enhanced.rows[0].values.phoenix,34.7);
  close(enhanced.speedup,34.7/35);
  assert.equal(P.analyse(rows,{metric:'drop'}).rows.every(r=>r.values.phoenix===null),true);
});
test('all individual fixtures remain available, not a truncated top-sixteen chart',()=>{
  const rows=Array.from({length:40},(_,i)=>trio('fixture-'+i)).flat();
  assert.equal(P.analyse(rows).rows.length,40);
  assert.equal(P.analyse(rows,{backends:[]}).rows.length,0);
});
