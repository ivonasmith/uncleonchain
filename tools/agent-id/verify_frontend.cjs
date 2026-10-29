// Synthetic DOM smoke test. No browser/network and no claim of visual acceptance.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const file = process.argv[2];
const html = fs.readFileSync(file, 'utf8');
assert(html.includes('src="./app.js"'));
assert(!/<script[^>]+src=["']https?:/.test(html), 'no remote script dependency');
assert(!/<script>/.test(html), 'no executable inline script');
const scripts = [fs.readFileSync(path.join(path.dirname(file), 'app.js'), 'utf8')];
const embedded = html.match(/<script type="application\/json" id="agent-data">([\s\S]*?)<\/script>/)[1];
function element() {
  return {children: [], attributes: {}, dataset: {}, handlers: {}, html: '',
    append(...items) { this.children.push(...items); },
    appendChild(child) { this.children.push(child); },
    replaceChildren(...items) { this.children = items; },
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(k, f) { this.handlers[k] = f; },
    insertAdjacentHTML(_where, value) { this.html += value; }};
}
const ids = Object.fromEntries(['through','updated','lag','coverage','cards','charts'].map(id => [id, element()]));
ids['agent-data'] = Object.assign(element(), {textContent: embedded});
const buttons = ['7','30','all'].map(range => Object.assign(element(), {dataset: {range}}));
const document = {getElementById: id => ids[id], createElement: element, querySelectorAll: () => buttons};
const context = vm.createContext({document, Date, Number, String, JSON, Math});
vm.runInContext(scripts[0], context);
assert.equal(ids.cards.children.length, 6);
assert.equal(ids.charts.children.length, 6);
for (const b of buttons) {
  b.handlers.click();
  assert.equal(ids.charts.children.length, 6);
  for (const c of ids.charts.children) assert(!/NaN|undefined/.test(c.html));
}
vm.runInContext("DATA.rows.forEach(r=>r.volume_bnb=null); render('all');", context);
assert(ids.charts.children[3].html.includes('U · 暂无完整数据'));
assert(ids.coverage.textContent.includes('不代表全生态总量'));
console.log('PASS: six cards, six SVG trends, 7/30/all range controls, no external script, no NaN, unknown gap state, scope label. Synthetic DOM only; visual review pending site integration.');
