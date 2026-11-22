// 等待 GitHub Pages 线上页面更新。
// 用法: node wait-pages.mjs <url> <sinceIso> <timeoutSec>
// 退出码: 0 = 已确认更新, 2 = 超时

const url = process.argv[2];
const sinceIso = process.argv[3];
const timeoutSec = Number(process.argv[4] || 600);

if (!url) {
  console.error('用法: node wait-pages.mjs <url> <sinceIso> <timeoutSec>');
  process.exit(1);
}

const sinceMs = Date.parse(sinceIso || '') || Date.now();
const deadline = Date.now() + timeoutSec * 1000;
const intervalMs = 10000;

const started = Date.now();
let attempts = 0;
let last = { status: 0, lastModified: null };

function bust(u) {
  return u + (u.includes('?') ? '&' : '?') + '_=' + Date.now();
}

async function probe() {
  const res = await fetch(bust(url), {
    headers: { 'User-Agent': 'dsh-pages-publisher', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' },
    redirect: 'follow'
  });
  const lm = res.headers.get('last-modified');
  return { status: res.status, ok: res.ok, lastModified: lm, lastModifiedMs: lm ? Date.parse(lm) : 0 };
}

async function main() {
  while (Date.now() < deadline) {
    attempts++;
    try {
      const r = await probe();
      last = r;
      const elapsed = Math.round((Date.now() - started) / 1000);
      if (r.ok && r.lastModifiedMs && r.lastModifiedMs >= sinceMs) {
        console.log(`  [pages] 第 ${attempts} 次检查：已更新 (status=${r.status}, last-modified=${r.lastModified}, 用时 ${elapsed}s)`);
        process.exit(0);
      }
      // 某些部署不返回 Last-Modified: 页面可访问且已等待足够久时视为成功
      if (r.ok && !r.lastModifiedMs && elapsed >= 60) {
        console.log(`  [pages] 第 ${attempts} 次检查：页面可访问，未返回 last-modified（用时 ${elapsed}s），视为已发布。`);
        process.exit(0);
      }
      console.log(`  [pages] 第 ${attempts} 次检查：尚未更新 (status=${r.status}, last-modified=${r.lastModified || 'n/a'})，${intervalMs / 1000}s 后重试...`);
    } catch (err) {
      console.log(`  [pages] 第 ${attempts} 次检查：请求失败 (${err.message})，${intervalMs / 1000}s 后重试...`);
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  console.log(`  [pages] 超时：最后一次 status=${last.status}, last-modified=${last.lastModified || 'n/a'}`);
  process.exit(2);
}

main();
