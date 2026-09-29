'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const {
  isSafeHttpUrl,
  preferTitle,
  collectControlSources,
  collectServiceSources,
  renderSourceLinksHtml,
} = require('../docs/source-links.js');

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function test(name, fn) {
  fn();
  console.log(`ok - ${name}`);
}

test('rejects non-http URLs', () => {
  assert.equal(isSafeHttpUrl('javascript:alert(1)'), false);
  assert.equal(isSafeHttpUrl('data:text/html,hi'), false);
  assert.equal(isSafeHttpUrl(''), false);
  assert.equal(isSafeHttpUrl(null), false);
  assert.equal(isSafeHttpUrl('https://docs.example.com/a'), true);
  assert.equal(isSafeHttpUrl('http://docs.example.com/a'), true);
});

test('preferTitle uses human title then URL leaf', () => {
  assert.equal(
    preferTitle('Pod Security', 'https://example.com/eks/pod-security.html'),
    'Pod Security',
  );
  assert.equal(
    preferTitle(
      'https://example.com/eks/pod-security.html',
      'https://example.com/eks/pod-security.html',
    ),
    'pod security',
  );
});

test('collectControlSources dedupes, skips malformed, associates services', () => {
  const sources = collectControlSources({
    references: [
      { url: 'https://example.com/ctrl', title: 'https://example.com/ctrl' },
      { url: 'javascript:alert(1)', title: 'bad' },
      null,
      'skip-me',
      { url: 'https://example.com/ctrl', title: 'Control Doc' },
    ],
    services: {
      ec2: {
        references: [
          { url: 'https://example.com/ctrl', title: 'https://example.com/ctrl' },
          { url: 'https://example.com/ec2', title: 'EC2 patching' },
        ],
      },
      s3: {
        references: [
          { url: 'https://example.com/ctrl', title: 'dup' },
        ],
      },
    },
    evidence_items: [
      {
        url: 'https://example.com/ctrl',
        title: 'Evidence title for control doc',
        applicability: { services: ['lambda'] },
      },
      {
        url: 'https://example.com/only-evidence',
        title: 'Evidence-only source',
        applicability: { services: [] },
      },
    ],
  });

  const byUrl = Object.fromEntries(sources.map((s) => [s.url, s]));
  assert.equal(sources.length, 3);
  assert.equal(byUrl['https://example.com/ctrl'].title, 'Control Doc');
  assert.deepEqual(byUrl['https://example.com/ctrl'].services, ['ec2', 'lambda', 's3']);
  assert.equal(byUrl['https://example.com/ec2'].title, 'EC2 patching');
  assert.deepEqual(byUrl['https://example.com/ec2'].services, ['ec2']);
  assert.equal(byUrl['https://example.com/only-evidence'].title, 'Evidence-only source');
  assert.deepEqual(byUrl['https://example.com/only-evidence'].services, []);
});

test('collectControlSources does not invent sources for empty controls', () => {
  assert.deepEqual(collectControlSources(null), []);
  assert.deepEqual(collectControlSources({}), []);
  assert.deepEqual(collectControlSources({ references: [] }), []);
});

test('collectServiceSources is scoped to one service', () => {
  const sources = collectServiceSources(
    {
      references: [
        { url: 'https://example.com/a', title: 'A' },
        { url: 'ftp://example.com/x', title: 'nope' },
      ],
    },
    'rds',
  );
  assert.equal(sources.length, 1);
  assert.deepEqual(sources[0], {
    url: 'https://example.com/a',
    title: 'A',
    services: ['rds'],
  });
});

test('renderSourceLinksHtml escapes text and attributes', () => {
  const html = renderSourceLinksHtml(
    [{
      url: 'https://example.com/a?x="y"&z=<1>',
      title: 'Title <script> & "q"',
      services: ['ec2"'],
    }],
    escHtml,
  );
  assert.match(html, /href="https:\/\/example\.com\/a\?x=&quot;y&quot;&amp;z=&lt;1&gt;"/);
  assert.match(html, /Title &lt;script&gt; &amp; &quot;q&quot;/);
  assert.match(html, /ec2&quot;/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.doesNotMatch(html, /<script>/);
});

test('renderSourceLinksHtml empty state', () => {
  assert.equal(
    renderSourceLinksHtml([], escHtml),
    '<div class="pa-no-refs">No reference links yet</div>',
  );
  assert.equal(
    renderSourceLinksHtml([], escHtml, { emptyHtml: '' }),
    '',
  );
});

console.log(`All source-link checks passed (${path.basename(__filename)}).`);
