/**
 * tenant-sec scoring engine — browser port
 * Mirrors the Python engine in src/tenant_sec/scoring/
 * No dependencies beyond js-yaml (loaded separately).
 */

// ── Aggregation functions ─────────────────────────────────────────────────

function nonNull(scores) {
  return scores.filter(s => s !== null && s !== undefined);
}

function aggMin(scores)    { const v = nonNull(scores); return v.length ? Math.min(...v) : null; }
function aggMean(scores)   { const v = nonNull(scores); return v.length ? v.reduce((a,b)=>a+b,0)/v.length : null; }
function aggMedian(scores) {
  const v = [...nonNull(scores)].sort((a,b)=>a-b);
  if (!v.length) return null;
  const m = Math.floor(v.length/2);
  return v.length % 2 ? v[m] : (v[m-1]+v[m])/2;
}
function aggPercentile(p) {
  return (scores) => {
    const v = [...nonNull(scores)].sort((a,b)=>a-b);
    if (!v.length) return null;
    const pos = (p/100) * (v.length-1);
    const lo = Math.floor(pos), hi = Math.min(lo+1, v.length-1);
    return v[lo] * (1-(pos-lo)) + v[hi] * (pos-lo);
  };
}
function aggThreshold(level, pct) {
  return (scores) => {
    const v = nonNull(scores);
    if (!v.length) return null;
    const passing = v.filter(s => s >= level).length / v.length;
    return passing >= pct ? level : Math.max(level-1, 0);
  };
}

const THRESHOLD_RE = /^threshold:L([0-3]):([0-9]+(?:\.[0-9]+)?)$/;

function getAggFn(spec) {
  if (spec === 'min')    return aggMin;
  if (spec === 'mean')   return aggMean;
  if (spec === 'median') return aggMedian;
  if (spec === 'p10')    return aggPercentile(10);
  if (spec === 'p20')    return aggPercentile(20);
  const m = THRESHOLD_RE.exec(spec);
  if (m) return aggThreshold(parseInt(m[1]), parseFloat(m[2]));
  throw new Error(`Unknown aggregation spec: ${spec}`);
}

// ── Staleness ─────────────────────────────────────────────────────────────

const STALE_MONTHS = { accredited: 12, community: 6, self: 6 };

function assessorTier(assessedBy) {
  if (assessedBy.startsWith('accredited:')) return 'accredited';
  if (assessedBy.startsWith('community:'))  return 'community';
  return 'self';
}

function addMonths(dateStr, months) {
  const d = new Date(dateStr + 'T00:00:00Z');
  d.setUTCMonth(d.getUTCMonth() + months);
  return d;
}

function isStale(assessedAt, assessedBy) {
  const tier = assessorTier(assessedBy);
  const months = STALE_MONTHS[tier] ?? 6;
  const expiry = addMonths(assessedAt, months);
  return new Date() > expiry;
}

// ── Resolve effective score for one provider+control ─────────────────────

function resolveEffectiveScore(provider, controlId, aggFn) {
  const entry = provider.controls?.[controlId];
  if (!entry) return null;

  if (entry.score === 'mixed') {
    const servicescores = Object.values(entry.services ?? {}).map(s => s.score);
    return aggFn(servicescores);
  }
  return typeof entry.score === 'number' ? entry.score : null;
}

// ── Main scoring function ─────────────────────────────────────────────────

/**
 * Score a list of providers against a scoring profile.
 *
 * @param {object[]} providers  - Parsed provider YAML objects
 * @param {object}   profile    - Parsed scoring profile YAML object
 * @param {object}   index      - Parsed controls/_index.yaml object
 * @returns {object[]} Ranked array of ScoredProvider objects
 */
export function scoreProviders(providers, profile, index) {
  const aggFn = getAggFn(profile.mixed_aggregation ?? 'mean');
  const weights = profile.weights ?? {};
  const mustHaves = profile.must_have ?? [];

  // Build domain→controlId map from index
  const domainControls = {};
  for (const [domain, info] of Object.entries(index.domains ?? {})) {
    domainControls[domain] = info.controls ?? [];
  }

  const results = providers.map(provider => {
    // Step 1: resolve effective scores for all controls we know about
    const effectiveScores = {};
    for (const [domain, controlIds] of Object.entries(domainControls)) {
      for (const cid of controlIds) {
        effectiveScores[cid] = resolveEffectiveScore(provider, cid, aggFn);
      }
    }

    // Step 2: must-have evaluation
    const mustHaveResults = mustHaves.map(mh => {
      const actual = effectiveScores[mh.control] ?? null;
      const passed = actual !== null && actual >= mh.min_level;
      return { control: mh.control, min_level: mh.min_level, actual_level: actual, passed };
    });
    const mustHavePassed = mustHaveResults.every(r => r.passed);

    // Step 3: domain scores (mean of assessed controls → 0-100)
    const domainScores = {};
    for (const [domain, controlIds] of Object.entries(domainControls)) {
      const assessed = controlIds
        .map(cid => effectiveScores[cid])
        .filter(s => s !== null && s !== undefined);
      domainScores[domain] = assessed.length
        ? (assessed.reduce((a,b)=>a+b,0) / assessed.length) * 100 / 3
        : null;
    }

    // Step 4: overall weighted score (redistribute weight for unassessed domains)
    let weightedSum = 0, totalWeight = 0;
    for (const [domain, weight] of Object.entries(weights)) {
      const ds = domainScores[domain];
      if (ds !== null && ds !== undefined) {
        weightedSum += ds * weight;
        totalWeight += weight;
      }
    }
    const overallScore = totalWeight > 0 ? weightedSum / totalWeight : 0;

    return {
      provider:         provider.provider,
      display_name:     provider.display_name,
      overall_score:    Math.round(overallScore * 10) / 10,
      domain_scores:    domainScores,
      must_have_results: mustHaveResults,
      must_have_passed: mustHavePassed,
      effective_scores: effectiveScores,
      stale:            isStale(provider.assessed_at, provider.assessed_by),
    };
  });

  // Step 5: rank descending, tie-break alphabetically
  results.sort((a,b) => b.overall_score - a.overall_score || a.provider.localeCompare(b.provider));
  results.forEach((r,i) => r.rank = i+1);
  return results;
}
