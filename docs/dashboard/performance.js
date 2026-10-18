'use strict';
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.BenchPerformance = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  const MODES = ['native', 'nvidia', 'phoenix'];
  const executionLabel = run => run.execution_variant === 'x86-driver'
    ? 'x86 Phoenix DLSS5 + native driver' : run.execution_label || run.execution_variant;
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const mean = values => values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const geometricMean = values => values.length && values.every(v => finite(v) && v > 0)
    ? Math.exp(mean(values.map(Math.log))) : null;
  const measured = run => run && !run.reference && run.status === 'complete' && run.freshness === 'current';
  const rate = (run, metric) => measured(run) && finite(run[metric]) && run[metric] > 0 ? run[metric] : null;
  const isNeural = metric => ['neural_fps', 'nvidia_neural'].includes(metric);
  const metricKey = metric => isNeural(metric) ? 'neural_fps' : ['game_fps','nvidia_game'].includes(metric) ? 'game_fps' : 'fps';
  const isNvidiaRelative = metric => ['nvidia_game', 'nvidia_neural'].includes(metric);
  const isPercentage = metric => ['drop', 'retention', 'nvidia_game', 'nvidia_neural'].includes(metric);

  function cohortKey(run) {
    // Unknown provenance can be plotted, but can never manufacture a matched pair.
    if (!run.fixture_id || !run.executable_sha256 || !run.benchmark_profile || !run.comparison_batch ||
        !run.width || !run.height || !finite(run.requested_seconds) || !finite(run.warmup_seconds) ||
        typeof run.vsync !== 'boolean') return JSON.stringify(['unmatched', run.fixture_id || run.id,
          run.executable_sha256, run.benchmark_profile, run.comparison_batch, run.width, run.height,
          run.requested_seconds, run.warmup_seconds, run.vsync,
          run.mode === 'native' ? 'auto' : run.execution_variant || 'auto']);
    return JSON.stringify([run.fixture_id, run.executable_sha256, run.benchmark_profile,
      run.comparison_batch, run.width, run.height, run.requested_seconds, run.warmup_seconds, run.vsync,
      run.mode === 'native' ? 'auto' : run.execution_variant || 'auto']);
  }

  function collect(runs) {
    const map = new Map();
    const baselines = new Map();
    const baseKey = run => cohortKey({...run, execution_variant:'auto'});
    for (const run of runs) {
      if (!MODES.includes(run.mode) || run.reference) continue;
      const key = cohortKey(run);
      if (!map.has(key)) map.set(key, {key, fixture: run.fixture_id || run.id,
        label: String(run.fixture_id || run.label || run.id || 'Unknown fixture')+
          (run.mode !== 'native' && ![undefined, null, 'auto'].includes(run.execution_variant) ? ' / '+executionLabel(run) : ''),
        execution_variant: run.mode === 'native' ? 'auto' : run.execution_variant || 'auto',
        base_key:baseKey(run),
        group: run.group, api: run.api, transport: run.transport, architecture: run.architecture,
        width: run.width, height: run.height, runs: {}});
      const cohort = map.get(key), previous = cohort.runs[run.mode];
      // Choose the latest result BEFORE removing failures; never resurrect an old pass.
      const timestamp = Date.parse(run.timestamp || '') || 0;
      const previousTimestamp = previous ? Date.parse(previous.timestamp || '') || 0 : 0;
      if (!previous || timestamp > previousTimestamp ||
          (timestamp === previousTimestamp && String(run.id) > String(previous.id))) cohort.runs[run.mode] = run;
      if (run.mode === 'native') {
        const old = baselines.get(baseKey(run));
        if (!old || timestamp >= (Date.parse(old.timestamp || '') || 0)) baselines.set(baseKey(run), run);
      }
    }
    const explicit = new Set([...map.values()].filter(c=>c.execution_variant !== 'auto').map(c=>c.base_key));
    return [...map.values()].filter(c=>!(c.execution_variant === 'auto' && explicit.has(c.base_key) &&
      !c.runs.nvidia && !c.runs.phoenix)).map(c=>{
        // Reuse the one clean run in-memory, never save duplicate baseline captures.
        if (!c.runs.native && baselines.has(c.base_key)) c.runs.native=baselines.get(c.base_key);
        return c;
      });
  }

  function consistent(cohort) {
    if (JSON.parse(cohort.key)[0] === 'unmatched') return false;
    const active = Object.values(cohort.runs).filter(measured);
    if (active.some(run => run.measurement_complete !== true)) return false;
    const contexts = active.map(run => {
      const controls = run.controls || {};
      return JSON.stringify([run.scene_mode ?? null, run.background ?? null, run.gpu ?? null,
        ...['frozen','camera_mode','camera_eye','yaw','pitch','orbit_distance','character_pose']
          .map(key => controls[key] ?? null), controls.frozen ? controls.simulation_seconds ?? null : null]);
    });
    const addonHashes = active.filter(run => run.mode !== 'native' && run.addon_sha256).map(run => run.addon_sha256);
    return new Set(contexts).size === 1 && new Set(addonHashes).size <= 1;
  }

  function executionRankings(runs) {
    const cohorts=collect(runs).filter(c=>c.architecture==='x86');
    const expected={helper:'helper','x64-library':'in_process_x64_library','x86-driver':'in_process_x86_driver'};
    const labels={helper:'External x64 helper','x64-library':'x64 library inside x86','x86-driver':'x86 Phoenix DLSS5 + native driver'};
    const rows=[];
    for (const backend of ['phoenix','nvidia']) {
      const variants=backend==='phoenix'?Object.keys(expected):['helper','x64-library'];
      const fixtures=new Map();
      for (const cohort of cohorts) {
        if (!variants.includes(cohort.execution_variant)) continue;
        if (!fixtures.has(cohort.base_key)) fixtures.set(cohort.base_key,{});
        fixtures.get(cohort.base_key)[cohort.execution_variant]=cohort;
      }
      const matched=[...fixtures.values()].filter(group=>variants.every(variant=>{
        const c=group[variant],r=c?.runs[backend];
        return c&&consistent(c)&&rate(r,'neural_fps')&&r.execution_mode===expected[variant];
      })&&new Set(variants.map(variant=>group[variant].runs[backend].addon_sha256||'')).size===1);
      for (const variant of variants) {
        const members=cohorts.filter(c=>c.execution_variant===variant).map(c=>c.runs[backend]).filter(Boolean);
        const rates=matched.map(group=>rate(group[variant].runs[backend],'neural_fps'));
        const ratios=matched.map(group=>rate(group[variant].runs[backend],'neural_fps')/rate(group.helper.runs[backend],'neural_fps'));
        rows.push({backend,variant,label:labels[variant],matched:matched.length,
          passed:members.filter(measured).length,failed:members.filter(r=>r.status==='failed').length,
          startupAffected:matched.filter(group=>group[variant].runs[backend].startup_in_measurement).length,
          meanFps:mean(rates),speedup:geometricMean(ratios),
          wins:matched.filter(group=>rate(group[variant].runs[backend],'neural_fps')>=
            .99*Math.max(...variants.map(v=>rate(group[v].runs[backend],'neural_fps')))).length});
      }
    }
    return rows;
  }

  function valueFor(cohort, mode, metric) {
    const raw = rate(cohort.runs[mode], metricKey(metric));
    if (raw == null) return null;
    if (metric === 'fps' || metric === 'neural_fps' || metric === 'game_fps') return raw;
    if (isNvidiaRelative(metric)) {
      const reference = rate(cohort.runs.nvidia, metricKey(metric));
      return reference && consistent(cohort) ? 100 * raw / reference : null;
    }
    const native = rate(cohort.runs.native, 'fps');
    if (native == null || !consistent(cohort)) return null;
    return metric === 'drop' ? 100 * (1 - raw / native) : 100 * raw / native;
  }

  function aggregate(cohorts, backends, metric, group) {
    if (group === 'fixture') return cohorts.map(cohort => ({...cohort, count: 1,
      values: Object.fromEntries(backends.map(mode => [mode, valueFor(cohort, mode, metric)])),
      states: Object.fromEntries(backends.map(mode => [mode, cohort.runs[mode]?.status || 'missing']))}));
    const groups = new Map();
    for (const cohort of cohorts) {
      const routeLabel = mode => ({helper:'Background process',in_process:'In process',in_process_x64_library:'x64 library inside x86',in_process_x86_driver:'x86 Phoenix DLSS5 + native driver',in_process_portable:'Portable in process',not_started:'Not started'})[mode] || mode;
      const label = group === 'execution' ? [...new Set(backends.filter(m => m !== 'native')
        .map(m => routeLabel(cohort.runs[m]?.execution_mode || 'not_started')))].sort().join(' / ') || 'Native' : cohort[group] || 'Unknown';
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(cohort);
    }
    return [...groups].map(([label, members]) => ({key: label, label, count: members.length,
      values: Object.fromEntries(backends.map(mode => [mode, mean(members.map(c => valueFor(c, mode, metric)).filter(finite))])),
      states: Object.fromEntries(backends.map(mode => [mode, 'complete']))}));
  }

  function analyse(runs, options = {}) {
    const metric = ['fps', 'game_fps', 'neural_fps', 'drop', 'retention', 'nvidia_game', 'nvidia_neural'].includes(options.metric) ? options.metric : 'fps';
    const backends = MODES.filter(m => (options.backends || MODES).includes(m) &&
      (!(isNeural(metric) || isNvidiaRelative(metric)) || m !== 'native'));
    let cohorts = collect(runs).filter(c => backends.some(m => c.runs[m]));
    if (options.route && options.route !== 'all') cohorts = cohorts.filter(c =>
      backends.some(m => m !== 'native' && (c.runs[m]?.execution_mode === options.route || c.runs[m]?.requested_execution_mode === options.route)));
    const matched = cohorts.filter(c => backends.length && consistent(c) && backends.every(m => valueFor(c, m, metric) != null));
    const group = ['fixture', 'group', 'api', 'transport', 'architecture', 'execution'].includes(options.group) ? options.group : 'fixture';
    const plotted = options.pairedOnly || group !== 'fixture' ? matched : cohorts;
    let rows = aggregate(plotted, backends, metric, group);
    const sort = options.sort || 'name';
    const ratioMetric = metricKey(metric);
    const ratio = c => {
      const n = rate(c.runs?.nvidia, ratioMetric), p = rate(c.runs?.phoenix, ratioMetric);
      return n && p ? p / n : null;
    };
    const rank = row => sort === 'ratio' ? ratio(row) : sort === 'nvidia' || sort === 'phoenix' || sort === 'native'
      ? row.values[sort] : Math.max(...Object.values(row.values).filter(finite), -Infinity);
    rows.sort((a, b) => {
      if (sort !== 'name') {
        const av = rank(a), bv = rank(b);
        if (av == null && bv != null) return 1;
        if (bv == null && av != null) return -1;
        if (finite(av) && finite(bv) && av !== bv) return bv - av;
      }
      return a.label.localeCompare(b.label, undefined, {numeric: true}) || a.key.localeCompare(b.key);
    });
    const summaries = backends.map(mode => {
      const memberRates = matched.map(c => rate(c.runs[mode], ratioMetric)).filter(finite);
      const nativePairs = matched.filter(c => rate(c.runs.native, 'fps') && rate(c.runs[mode], 'fps'));
      const nativeMean = mean(nativePairs.map(c => rate(c.runs.native, 'fps')));
      const enhancedMean = mean(nativePairs.map(c => rate(c.runs[mode], 'fps')));
      return {mode, count: memberRates.length, meanFps: mean(memberRates), nativeCount: nativePairs.length,
        meanDrop: mean(nativePairs.map(c => 100 * (1 - rate(c.runs[mode], 'fps') / rate(c.runs.native, 'fps')))),
        dropInMean: nativeMean && enhancedMean ? 100 * (1 - enhancedMean / nativeMean) : null,
        geometricRetention: geometricMean(nativePairs.map(c => rate(c.runs[mode], 'fps') / rate(c.runs.native, 'fps')))};
    });
    const pairs = backends.includes('nvidia') && backends.includes('phoenix') ? matched.filter(c => ratio(c)) : [];
    const ratios = pairs.map(ratio);
    const routeCounts = {in_process: 0, helper: 0, other: 0};
    let failed = 0, untimed = 0;
    for (const cohort of cohorts) for (const mode of backends) {
      const run = cohort.runs[mode];
      if (run?.status === 'failed') failed++;
      if (measured(run) && rate(run, ratioMetric) == null) untimed++;
      if (mode !== 'native' && measured(run)) {
        const key = run.execution_mode?.startsWith('in_process') ? 'in_process' : run.execution_mode === 'helper' ? 'helper' : 'other';
        routeCounts[key]++;
      }
    }
    return {metric, backends, cohorts, rows, matched, summaries, failed, untimed, routeCounts,
      excluded: cohorts.length - matched.length, pairCount: pairs.length,
      speedup: geometricMean(ratios), medianSpeedup: ratios.length ?
        (() => {const sorted = [...ratios].sort((a, b) => a - b), mid = Math.floor(sorted.length / 2);
          return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;})() : null,
      phoenixWins: ratios.filter(v => v > 1.01).length,
      nvidiaWins: ratios.filter(v => v < 1 / 1.01).length,
      ties: ratios.filter(v => v >= 1 / 1.01 && v <= 1.01).length};
  }

  return {analyse, collect, cohortKey, consistent, mean, geometricMean, rate, valueFor,
    isNeural, metricKey, isNvidiaRelative, isPercentage, executionRankings};
});
