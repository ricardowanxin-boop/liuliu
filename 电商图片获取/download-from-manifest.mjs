import { createWriteStream } from "node:fs";
import { mkdir, readFile, writeFile, access } from "node:fs/promises";
import { basename, extname, join, resolve } from "node:path";
import { pipeline } from "node:stream/promises";

const DEFAULT_CONCURRENCY = 6;
const DEFAULT_RETRIES = 2;

const help = `
Usage:
  node download-from-manifest.mjs <manifest.json...> [--out ./downloads] [--concurrency 6] [--force] [--page-images]

Examples:
  node download-from-manifest.mjs ~/Downloads/taobao-shop-images-*.json --out ./downloads/lumi
  npm run download -- ~/Downloads/taobao-shop-images-*.json --out ./downloads/lumi --page-images
`;

const parseArgs = (argv) => {
  const options = {
    manifests: [],
    out: "./downloads",
    concurrency: DEFAULT_CONCURRENCY,
    force: false,
    pageImages: false
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--out") {
      options.out = argv[++index];
    } else if (arg === "--concurrency") {
      options.concurrency = Number(argv[++index] || DEFAULT_CONCURRENCY);
    } else if (arg === "--force") {
      options.force = true;
    } else if (arg === "--page-images") {
      options.pageImages = true;
    } else {
      options.manifests.push(arg);
    }
  }

  return options;
};

const sanitizeFilePart = (value, fallback) => {
  const cleaned = String(value || "")
    .normalize("NFKC")
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 72);
  return cleaned || fallback;
};

const exists = async (path) => {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
};

const extensionFrom = (url, contentType) => {
  const byType = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif"
  };

  const normalizedType = String(contentType || "").split(";")[0].trim().toLowerCase();
  if (byType[normalizedType]) return byType[normalizedType];

  try {
    const ext = extname(new URL(url).pathname).toLowerCase();
    if ([".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"].includes(ext)) return ext;
  } catch {
    // Ignore malformed URL here; caller already handles fetch errors.
  }

  return ".jpg";
};

const fetchWithRetry = async (url, { referer, retries }) => {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(url, {
        headers: {
          "user-agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
          accept: "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
          referer
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }
      return response;
    } catch (error) {
      lastError = error;
      if (attempt < retries) await new Promise((resolve) => setTimeout(resolve, 700 * (attempt + 1)));
    }
  }
  throw lastError;
};

const runPool = async (tasks, concurrency, worker) => {
  let nextIndex = 0;
  const workers = Array.from({ length: Math.max(1, concurrency) }, async () => {
    while (nextIndex < tasks.length) {
      const task = tasks[nextIndex];
      nextIndex += 1;
      await worker(task);
    }
  });
  await Promise.all(workers);
};

const buildTasks = (manifest, outDir, includePageImages) => {
  const tasks = [];
  const seenByItem = new Set();

  for (const [itemIndex, item] of (manifest.items || []).entries()) {
    const folderName = sanitizeFilePart(
      `${String(itemIndex + 1).padStart(3, "0")}_${item.itemId || "item"}_${item.title || "untitled"}`,
      `${String(itemIndex + 1).padStart(3, "0")}_item`
    );
    const folder = join(outDir, folderName);

    for (const [imageIndex, image] of (item.images || []).entries()) {
      const url = image.originalUrl || image.url;
      if (!url) continue;
      const key = `${folder}\n${url}`;
      if (seenByItem.has(key)) continue;
      seenByItem.add(key);
      tasks.push({
        url,
        rawUrl: image.url,
        referer: item.link || manifest.sourceUrl || "https://www.taobao.com/",
        folder,
        baseName: String(imageIndex + 1).padStart(2, "0"),
        itemTitle: item.title || "",
        itemId: item.itemId || ""
      });
    }
  }

  if (includePageImages && Array.isArray(manifest.pageImages)) {
    const folder = join(outDir, "_page-images");
    const seen = new Set();
    for (const [imageIndex, image] of manifest.pageImages.entries()) {
      const url = image.originalUrl || image.url;
      if (!url || seen.has(url)) continue;
      seen.add(url);
      tasks.push({
        url,
        rawUrl: image.url,
        referer: manifest.sourceUrl || "https://www.taobao.com/",
        folder,
        baseName: String(imageIndex + 1).padStart(3, "0"),
        itemTitle: "",
        itemId: ""
      });
    }
  }

  return tasks;
};

const main = async () => {
  const options = parseArgs(process.argv.slice(2));
  if (options.help || !options.manifests.length) {
    console.log(help.trim());
    process.exit(options.help ? 0 : 1);
  }

  const outDir = resolve(options.out);
  await mkdir(outDir, { recursive: true });

  const tasks = [];
  for (const manifestArg of options.manifests) {
    const manifestPath = resolve(manifestArg);
    const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
    await writeFile(join(outDir, `manifest-${basename(manifestPath)}`), JSON.stringify(manifest, null, 2));
    tasks.push(...buildTasks(manifest, outDir, options.pageImages));
  }

  if (!tasks.length) {
    console.log("No image tasks found in manifest files.");
    return;
  }

  let done = 0;
  let skipped = 0;
  let failed = 0;
  const failures = [];

  await runPool(tasks, options.concurrency, async (task) => {
    await mkdir(task.folder, { recursive: true });

    try {
      const response = await fetchWithRetry(task.url, {
        referer: task.referer,
        retries: DEFAULT_RETRIES
      });
      const ext = extensionFrom(task.url, response.headers.get("content-type"));
      const filePath = join(task.folder, `${task.baseName}${ext}`);

      if (!options.force && (await exists(filePath))) {
        skipped += 1;
      } else {
        await pipeline(response.body, createWriteStream(filePath));
        done += 1;
      }

      console.log(`[${done + skipped + failed}/${tasks.length}] saved ${filePath}`);
    } catch (error) {
      failed += 1;
      failures.push({ url: task.url, error: error.message });
      console.warn(`[${done + skipped + failed}/${tasks.length}] failed ${task.url}: ${error.message}`);
    }
  });

  if (failures.length) {
    await writeFile(join(outDir, "failures.json"), JSON.stringify(failures, null, 2));
  }

  console.log(`Done. saved=${done}, skipped=${skipped}, failed=${failed}, output=${outDir}`);
};

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
