import { mkdir, readFile, writeFile } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";

const help = `
Usage:
  node filter-product-images.mjs <manifest.json> [--out filtered-manifest.json] [--seller-id 716241818]

Example:
  node filter-product-images.mjs ~/Downloads/taobao-shop-images-2026-04-24T06-51-53-384Z.json --out ./downloads/lumi-products-only.json
`;

const parseArgs = (argv) => {
  const options = {
    manifest: "",
    out: "",
    sellerId: "716241818"
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--out") {
      options.out = argv[++index];
    } else if (arg === "--seller-id") {
      options.sellerId = argv[++index];
    } else if (!options.manifest) {
      options.manifest = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return options;
};

const imageUrl = (image) => image.originalUrl || image.url || "";

const isNearSquare = (width, height) => {
  if (!width || !height) return false;
  const ratio = width / height;
  return ratio >= 0.88 && ratio <= 1.12;
};

const imageKind = (image) => {
  const width = Number(image.width || 0);
  const height = Number(image.height || 0);
  if (width >= 180 && width <= 260 && height >= 180 && height <= 260 && isNearSquare(width, height)) {
    return "main";
  }
  if (width >= 32 && width <= 52 && height >= 32 && height <= 52 && isNearSquare(width, height)) {
    return "thumb";
  }
  return "";
};

const isSellerProductImage = (image, sellerId) => {
  const url = imageUrl(image);
  if (!url.includes(`!!${sellerId}`) && !url.includes(`/${sellerId}/`)) return false;
  if (/-2-tps-|atmosphere|600000000/i.test(url)) return false;
  return /\.(?:jpg|jpeg|png|webp)(?:[?#]|$|_)/i.test(url);
};

const uniqueImages = (images) => {
  const seen = new Set();
  const result = [];
  for (const image of images) {
    const url = imageUrl(image);
    if (!url || seen.has(url)) continue;
    seen.add(url);
    result.push(image);
  }
  return result;
};

const filterManifest = (manifest, sellerId) => {
  const sourceImages = (manifest.items || []).flatMap((item) => item.images || []);
  const items = [];
  let current = null;

  for (const image of sourceImages) {
    if (!isSellerProductImage(image, sellerId)) continue;

    const kind = imageKind(image);
    if (!kind) continue;

    if (kind === "main") {
      if (current?.images?.length) items.push({ ...current, images: uniqueImages(current.images) });
      current = {
        itemId: "",
        title: `product_${String(items.length + 1).padStart(3, "0")}`,
        price: "",
        link: manifest.sourceUrl || "",
        images: [image]
      };
    } else if (current) {
      current.images.push(image);
    }
  }

  if (current?.images?.length) items.push({ ...current, images: uniqueImages(current.images) });

  return {
    sourceUrl: manifest.sourceUrl,
    capturedAt: manifest.capturedAt,
    filteredAt: new Date().toISOString(),
    filter: {
      sellerId,
      rules: [
        "URL contains seller image marker",
        "reject Taobao UI/tps/atmosphere assets",
        "keep product main images displayed around 210x210",
        "keep product thumbnails displayed around 40x40",
        "start a new product group at each main image"
      ]
    },
    totalItems: items.length,
    totalItemImages: items.reduce((sum, item) => sum + item.images.length, 0),
    items,
    pageImages: []
  };
};

const main = async () => {
  const options = parseArgs(process.argv.slice(2));
  if (options.help || !options.manifest) {
    console.log(help.trim());
    process.exit(options.help ? 0 : 1);
  }

  const manifestPath = resolve(options.manifest);
  const outputPath = resolve(
    options.out || `${manifestPath.replace(/\.json$/i, "")}.products-only.json`
  );
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const filtered = filterManifest(manifest, options.sellerId);

  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, JSON.stringify(filtered, null, 2));

  console.log(
    `Filtered ${basename(manifestPath)} -> ${outputPath}: products=${filtered.totalItems}, images=${filtered.totalItemImages}`
  );
};

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
