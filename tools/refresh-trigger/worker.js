// 总调度准点触发器（2026-11-15）：Cloudflare Worker 的 Cron Trigger 到点调 GitHub workflow_dispatch。
// GitHub 自带的 schedule 每天晚 6～10 小时；workflow_dispatch 几秒内开跑。
// 只需要一个 secret：GH_TOKEN = GitHub fine-grained token，只授权 ivonasmith/uncleonchain 一个仓库，权限 Actions: Read and write。
const REPO = "ivonasmith/uncleonchain";
const WORKFLOW = "refresh.yml";
// cron（UTC）→ 档位。和 wrangler.toml 的 crons、config/site.json 的「时间」保持一致。
const SLOTS = { "5 0 * * *": "am", "30 8 * * *": "pm", "50 9 * * *": "retry" };

async function dispatch(env, slot) {
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const body = JSON.stringify({ ref: "main", inputs: { slot } });
  let last = "";
  for (let i = 0; i < 3; i++) {
    const r = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "refresh-trigger",
        "Content-Type": "application/json",
      },
      body,
    });
    if (r.status === 204) return `ok ${slot}`;
    last = `${r.status} ${await r.text()}`;
    await new Promise((s) => setTimeout(s, 5000 * (i + 1)));
  }
  throw new Error(`dispatch ${slot} 失败：${last}`);
}

export default {
  async scheduled(event, env, ctx) {
    const slot = SLOTS[event.cron] || "auto";
    ctx.waitUntil(dispatch(env, slot).then(console.log));
  },
  // 浏览器打开 Worker 网址只显示说明，不触发（避免被人随便点）
  async fetch() {
    return new Response("uncleonchain refresh trigger: " + JSON.stringify(SLOTS), { headers: { "content-type": "text/plain; charset=utf-8" } });
  },
};
