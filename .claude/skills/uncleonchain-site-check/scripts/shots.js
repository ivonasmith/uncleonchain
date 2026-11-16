// 站点截图自查：起本地静态服务，截关键页（桌面 + 手机，中 + 英），并查
//   - 手机宽度（390px）有没有横向滚动
//   - 浏览器控制台有没有报错
//   - 页面是不是还停在「读取中…」
// 用法：node shots.js [站点目录=site] [输出目录=scratchpad]
//   可用环境变量 SHOT_PAGES="/,/macro/" 只截指定路径
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(process.argv[2] || 'site');
const OUT = path.resolve(process.argv[3] || '/tmp/claude-0/shots');
const DEFAULT = ['/', '/macro/', '/core/', '/alpha/', '/launchpad/', '/leg-tracker/', '/calendar/',
                 '/smart-money/', '/ai-agent/', '/rwa/', '/journal/', '/en/', '/en/macro/'];
const PAGES = process.env.SHOT_PAGES ? process.env.SHOT_PAGES.split(',') : DEFAULT;
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.xml': 'application/xml', '.txt': 'text/plain', '.webp': 'image/webp' };

fs.mkdirSync(OUT, { recursive: true });

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  let f = path.join(ROOT, p);
  if (p.endsWith('/')) f = path.join(f, 'index.html');
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('404'); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
}).listen(0, '127.0.0.1');
const PORT = () => server.address().port;

const slug = p => (p.replace(/^\/|\/$/g, '') || 'home').replace(/\//g, '_');

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] });
  const views = [
    { name: 'desk', viewport: { width: 1440, height: 900 }, dsf: 2 },   // 给人看的：2x
    { name: 'phone', viewport: { width: 390, height: 844 }, dsf: 1 },   // 只查溢出，1x 就够
  ];
  const report = [];
  for (const v of views) {
    const ctx = await browser.newContext({ viewport: v.viewport, deviceScaleFactor: v.dsf });
    for (const pg of PAGES) {
      const page = await ctx.newPage();
      const errs = [];
      page.on('pageerror', e => errs.push('JS: ' + e.message));
      // 外部资源（字体、CDN）加载失败是沙盒代理的噪声，不算站点问题；只报本站 404 和 JS 报错
      page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push('console: ' + m.text().slice(0, 160)); });
      page.on('response', res => { if (res.status() >= 400 && res.url().includes('127.0.0.1')) errs.push(`本站 ${res.status()}: ${res.url().replace(/^https?:\/\/[^/]+/, '')}`); });
      const r = { page: pg, view: v.name, issues: [] };
      try {
        await page.goto(`http://127.0.0.1:${PORT()}${pg}`, { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(800);
        const m = await page.evaluate(() => ({
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          culprit: (() => { const W = document.documentElement.clientWidth; let worst = null;
            document.querySelectorAll('body *').forEach(el => { const r = el.getBoundingClientRect();
              if (r.right > W + 1 && (!worst || r.right > worst.r)) worst = { r: r.right, s: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ')[0] : '') };
            }); return worst ? worst.s : null; })(),
          loading: /读取中|Loading…/.test(document.body.innerText) ? document.body.innerText.match(/.{0,20}(读取中|Loading…).{0,10}/)[0] : null,
        }));
        if (v.name === 'phone' && m.overflow > 1) r.issues.push(`手机宽度横向溢出 ${m.overflow}px，最宽元素：${m.culprit}`);
        if (m.loading) r.issues.push(`仍有加载占位：「${m.loading}」`);
        const file = path.join(OUT, `${slug(pg)}_${v.name}.png`);
        await page.screenshot({ path: file });
        r.shot = file;
      } catch (e) {
        r.issues.push('打开失败：' + e.message.split('\n')[0]);
      }
      if (errs.length) r.issues.push(...errs.slice(0, 3));
      report.push(r);
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
  server.close();

  let bad = 0;
  for (const r of report) {
    if (r.issues.length) bad++;
    console.log(`${r.issues.length ? '⚠️ ' : '✓ '}${r.view.padEnd(5)} ${r.page.padEnd(16)} ${r.issues.join(' | ') || ''}`);
  }
  console.log(`\n截图 ${report.filter(r => r.shot).length} 张 → ${OUT}`);
  console.log(bad ? `有 ${bad} 项需要看` : '全部通过');
})().catch(e => { console.error('ERR', e.message); server.close(); process.exit(1); });
