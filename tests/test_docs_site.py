"""Static checks for the public docs site UI assets and Controls Explorer markup."""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_icon_and_favicon_assets_exist():
    icon = DOCS / "icon.png"
    favicon = DOCS / "favicon.ico"
    assert icon.is_file()
    assert favicon.is_file()
    assert icon.stat().st_size > 1000
    assert favicon.stat().st_size > 1000
    # ICO magic / reserved header fields
    data = favicon.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHI", data, 0)
    assert reserved == 0
    assert image_type == 1  # icon
    assert count >= 1


@pytest.mark.parametrize("page", ["index.html", "controls.html", "evaluate.html"])
def test_pages_link_favicon_and_logo_mark(page: str):
    html = (DOCS / page).read_text(encoding="utf-8")
    assert 'href="favicon.ico"' in html
    assert 'src="icon.png"' in html
    assert 'class="logo"' in html
    assert "tenant<span>-sec</span>" in html
    assert "rc-warning" in html
    assert "1.0-RC2" in html


def test_controls_explorer_drops_per_provider_warning_glyph():
    html = (DOCS / "controls.html").read_text(encoding="utf-8")
    assert "review_status === 'unreviewed' ? ' ⚠'" not in html
    assert "HUMAN REVIEW PENDING" not in html
    # Global banner remains
    assert "AI-assisted provisional assessments" in html


def test_evaluate_drops_per_card_review_badge_but_keeps_data_field():
    html = (DOCS / "evaluate.html").read_text(encoding="utf-8")
    assert "HUMAN REVIEW PENDING" not in html
    assert "review_status" in html  # still exported / present in data plumbing
    engine = (DOCS / "scoring-engine.js").read_text(encoding="utf-8")
    assert "review_status" in engine


def test_controls_detail_report_and_excerpt_controls():
    html = (DOCS / "controls.html").read_text(encoding="utf-8")
    assert "Report incorrect claim" in html
    assert 'id="navReportClaim"' in html
    assert "onclick=\"this.href=buildReportIssueUrl(activeCtrlId)\"" in html
    assert html.index('id="navReportClaim"') < html.index('class="gh-icon"')
    assert "buildReportIssueUrl" in html
    assert "github.com/ypapazov/tenant-sec/issues/new" in html
    assert "URLSearchParams" in html
    assert "const hasControl" in html
    assert "## Claimed problem" in html
    assert "## Suggested correction" in html
    assert "## Supporting sources" in html
    assert "See more" in html
    assert "scrollToControlDefinition" in html
    assert 'id="controlDefinition"' in html
    assert "buildStatementBlock" in html
    # Control id in detail header is escaped
    assert "${escHtml(ctrlId)}" in html


def test_report_issue_url_encoding_with_node():
    """Exercise the URL builder logic without a browser."""
    import subprocess

    script = r"""
function plainText(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/[\u0000-\u001f\u007f]/g, ' ').trim();
}
function formatOfferingLabel(prov) {
  if (!prov?.offering) return '';
  const o = prov.offering;
  const parts = [o.name || o.id, o.edition, (o.regions || []).join(', ')].filter(Boolean);
  return parts.join(' · ');
}
const focusedProvider = 'aws';
const expandedService = 's3';
const providers = {
  aws: {
    display_name: 'Amazon Web Services',
    assessment_id: 'aws/public/eu-west-1/standard',
    offering: { name: 'AWS Public Cloud', edition: 'standard', regions: ['eu-west-1'] },
  },
};
const controlDefs = {
  'iam.mfa-enforcement': { name: 'MFA Enforcement & Configuration' },
};
const location = { href: 'https://example.test/controls.html#aws/iam.mfa-enforcement/s3' };
function formatIdAsName(ctrlId) { return ctrlId; }
function buildReportIssueUrl(ctrlId) {
  const def = controlDefs[ctrlId];
  const controlTitle = plainText(def?.name ?? formatIdAsName(ctrlId)) || ctrlId;
  const pid = focusedProvider;
  const prov = pid ? providers[pid] : null;
  const service = expandedService;
  const title = `[Assessment feedback] ${ctrlId}` + (pid ? ` (${pid})` : '');
  const bodyLines = [
    '## Context',
    '',
    `- **Provider:** ${plainText(prov?.display_name || pid || 'All providers (no provider focused)')}`,
    `- **Assessment ID:** ${plainText(prov?.assessment_id || 'n/a')}`,
    `- **Offering:** ${plainText(formatOfferingLabel(prov) || 'n/a')}`,
    `- **Control ID:** ${plainText(ctrlId)}`,
    `- **Control title:** ${controlTitle}`,
  ];
  if (service) bodyLines.push(`- **Selected service:** ${plainText(service)}`);
  bodyLines.push(`- **Page URL:** ${plainText(location.href)}`);
  bodyLines.push('', '## Claimed problem', '', '## Suggested correction', '', '## Supporting sources', '');
  const params = new URLSearchParams({ title, body: bodyLines.join('\n') });
  return `https://github.com/ypapazov/tenant-sec/issues/new?${params.toString()}`;
}
const url = buildReportIssueUrl('iam.mfa-enforcement');
if (!url.startsWith('https://github.com/ypapazov/tenant-sec/issues/new?')) process.exit(2);
const u = new URL(url);
const title = u.searchParams.get('title');
const body = u.searchParams.get('body');
if (!title.includes('iam.mfa-enforcement')) process.exit(3);
if (!body.includes('aws/public/eu-west-1/standard')) process.exit(4);
if (!body.includes('Selected service:** s3')) process.exit(5);
if (!body.includes('MFA Enforcement & Configuration')) process.exit(6);
if (!body.includes('## Claimed problem')) process.exit(7);
// Adversarial control id must not break query parsing
controlDefs['x"&<>'] = { name: 'Weird <title>&"' };
const url2 = buildReportIssueUrl('x"&<>');
const u2 = new URL(url2);
if (u2.searchParams.get('title') !== '[Assessment feedback] x"&<> (aws)') process.exit(8);
console.log('ok');
"""
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ok" in result.stdout


def test_excerpt_helper_truncates():
    html = (DOCS / "controls.html").read_text(encoding="utf-8")
    match = re.search(
        r"function excerptText\(text, limit = 220\) \{.*?\n\}",
        html,
        re.DOTALL,
    )
    assert match, "excerptText helper missing"
    assert "truncated: true" in match.group(0)
