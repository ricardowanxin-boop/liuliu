(() => {
  const CONFIG = {
    maxScrollRounds: 80,
    stableRoundsToStop: 5,
    scrollDelayMs: 900,
    minImageSide: 60,
    includeNonAliImages: false,
    preferOriginalAliImage: true,
    clickNextPage: false,
    maxPages: 1
  };

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const normalizeUrl = (value) => {
    if (!value || typeof value !== "string") return "";
    let url = value.trim().replace(/^url\(["']?(.+?)["']?\)$/i, "$1");
    if (!url || url.startsWith("data:") || url.startsWith("blob:")) return "";
    if (url.startsWith("//")) url = `https:${url}`;
    if (url.startsWith("http://")) url = url.replace(/^http:\/\//i, "https://");
    try {
      return new URL(url, location.href).href.replace(/#.*$/, "");
    } catch {
      return "";
    }
  };

  const aliOriginal = (url) => {
    if (!/alicdn\.com/i.test(url)) return url;
    const withoutQuery = url.split("?")[0];
    return withoutQuery.replace(
      /(\.(?:jpg|jpeg|png|webp))(?:_[^/?#]+)?(?:\.(?:webp|jpg|jpeg|png))?$/i,
      "$1"
    );
  };

  const isLikelyProductImage = (url) => {
    if (!url) return false;
    const isAli = /(?:img|gw|g-search\d*)\.alicdn\.com/i.test(url);
    if (!CONFIG.includeNonAliImages && !isAli) return false;
    return /\.(?:jpg|jpeg|png|webp)(?:[?#]|$|_)/i.test(url);
  };

  const getUrlsFromElement = (element) => {
    const urls = [];
    const attrs = [
      "src",
      "data-src",
      "data-ks-lazyload",
      "data-lazyload",
      "data-lazy-img",
      "data-img",
      "data-imgurl",
      "data-original",
      "data-bg"
    ];

    for (const attr of attrs) {
      const url = normalizeUrl(element.getAttribute?.(attr));
      if (url) urls.push(url);
    }

    const srcset = element.getAttribute?.("srcset") || element.getAttribute?.("data-srcset");
    if (srcset) {
      for (const candidate of srcset.split(",")) {
        const url = normalizeUrl(candidate.trim().split(/\s+/)[0]);
        if (url) urls.push(url);
      }
    }

    const backgroundImage = getComputedStyle(element).backgroundImage;
    if (backgroundImage && backgroundImage !== "none") {
      const matches = [...backgroundImage.matchAll(/url\(["']?(.+?)["']?\)/gi)];
      for (const match of matches) {
        const url = normalizeUrl(match[1]);
        if (url) urls.push(url);
      }
    }

    return [...new Set(urls)].filter(isLikelyProductImage);
  };

  const getElementImages = (root) => {
    const nodes = root.querySelectorAll("img, source, [style*='background']");
    const images = [];

    for (const node of nodes) {
      const rect = node.getBoundingClientRect();
      const urls = getUrlsFromElement(node);
      if (!urls.length) continue;

      const visibleEnough =
        Math.max(rect.width || node.naturalWidth || 0, rect.height || node.naturalHeight || 0) >=
        CONFIG.minImageSide;
      const canBeLazy = urls.some((url) => /alicdn\.com/i.test(url));
      if (!visibleEnough && !canBeLazy) continue;

      for (const rawUrl of urls) {
        const originalUrl = CONFIG.preferOriginalAliImage ? aliOriginal(rawUrl) : rawUrl;
        images.push({
          url: rawUrl,
          originalUrl,
          width: Math.round(rect.width || node.naturalWidth || 0),
          height: Math.round(rect.height || node.naturalHeight || 0),
          alt: (node.getAttribute("alt") || "").trim()
        });
      }
    }

    const byOriginal = new Map();
    for (const image of images) {
      const key = image.originalUrl || image.url;
      if (!byOriginal.has(key)) byOriginal.set(key, image);
    }
    return [...byOriginal.values()];
  };

  const getItemId = (href) => {
    try {
      const url = new URL(href, location.href);
      return url.searchParams.get("id") || url.pathname.match(/\/i(\d+)\./)?.[1] || "";
    } catch {
      return "";
    }
  };

  const cleanText = (text) =>
    (text || "")
      .replace(/\s+/g, " ")
      .replace(/[\u200b-\u200f\uFEFF]/g, "")
      .trim();

  const inferTitle = (card, link) => {
    const titleAttrs = [
      link?.getAttribute("title"),
      link?.getAttribute("aria-label"),
      card.getAttribute("title"),
      card.getAttribute("aria-label")
    ].map(cleanText);
    const attrTitle = titleAttrs.find((value) => value && value.length >= 4);
    if (attrTitle) return attrTitle;

    const text = cleanText(card.innerText);
    const lines = text
      .split(/(?=￥|官方|百亿|已降|销量|评价)|\s{2,}/)
      .map(cleanText)
      .filter(Boolean);
    return lines.find((line) => /[\u4e00-\u9fa5A-Za-z0-9]/.test(line) && line.length >= 6) || "";
  };

  const inferPrice = (card) => {
    const text = cleanText(card.innerText);
    return text.match(/(?:￥|¥)\s*\d+(?:\.\d+)?/)?.[0]?.replace(/\s+/g, "") || "";
  };

  const climbToCard = (link) => {
    let node = link;
    for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {
      const rect = node.getBoundingClientRect();
      const hasImages = node.querySelectorAll("img, [style*='background']").length > 0;
      const hasText = cleanText(node.innerText).length > 8;
      if (hasImages && hasText && rect.width >= 130 && rect.height >= 160) return node;
    }
    return link;
  };

  const collectProducts = () => {
    const productLinks = [...document.querySelectorAll("a[href]")]
      .filter((link) => /(?:item\.taobao\.com|detail\.tmall\.com|id=\d{6,})/i.test(link.href))
      .filter((link) => getElementImages(climbToCard(link)).length > 0);

    const byKey = new Map();
    for (const link of productLinks) {
      const card = climbToCard(link);
      const linkUrl = normalizeUrl(link.href);
      const itemId = getItemId(linkUrl);
      const images = getElementImages(card);
      if (!images.length) continue;

      const key = itemId || linkUrl || images[0].originalUrl;
      if (!byKey.has(key)) {
        byKey.set(key, {
          itemId,
          title: inferTitle(card, link),
          price: inferPrice(card),
          link: linkUrl,
          images
        });
      } else {
        const item = byKey.get(key);
        const imageMap = new Map(item.images.map((image) => [image.originalUrl || image.url, image]));
        for (const image of images) imageMap.set(image.originalUrl || image.url, image);
        item.images = [...imageMap.values()];
        if (!item.title) item.title = inferTitle(card, link);
        if (!item.price) item.price = inferPrice(card);
      }
    }

    return [...byKey.values()];
  };

  const collectPageImages = () => {
    const imageMap = new Map();
    for (const image of getElementImages(document.body)) {
      imageMap.set(image.originalUrl || image.url, image);
    }
    return [...imageMap.values()];
  };

  const findNextButton = () => {
    const candidates = [...document.querySelectorAll("a, button")]
      .filter((el) => {
        const label = cleanText(`${el.innerText} ${el.getAttribute("aria-label") || ""}`);
        return /下一页|下页|next|>/i.test(label);
      })
      .filter((el) => {
        const disabled =
          el.disabled ||
          el.getAttribute("aria-disabled") === "true" ||
          /\bdisabled\b|--disabled|is-disabled/.test(el.className || "");
        return !disabled && el.getBoundingClientRect().width > 0;
      });
    return candidates[0] || null;
  };

  const mergeItems = (targetMap, items) => {
    for (const item of items) {
      const key = item.itemId || item.link || item.images[0]?.originalUrl;
      if (!key) continue;
      if (!targetMap.has(key)) {
        targetMap.set(key, item);
        continue;
      }
      const oldItem = targetMap.get(key);
      const imageMap = new Map(oldItem.images.map((image) => [image.originalUrl || image.url, image]));
      for (const image of item.images) imageMap.set(image.originalUrl || image.url, image);
      oldItem.images = [...imageMap.values()];
      if (!oldItem.title) oldItem.title = item.title;
      if (!oldItem.price) oldItem.price = item.price;
    }
  };

  const downloadJson = (data) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    anchor.href = href;
    anchor.download = `taobao-shop-images-${stamp}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(href);
  };

  const run = async () => {
    const allItems = new Map();
    const pageImages = new Map();

    for (let page = 1; page <= CONFIG.maxPages; page += 1) {
      let lastItemCount = -1;
      let stableRounds = 0;

      for (let round = 1; round <= CONFIG.maxScrollRounds; round += 1) {
        mergeItems(allItems, collectProducts());
        for (const image of collectPageImages()) pageImages.set(image.originalUrl || image.url, image);

        const currentItemCount = allItems.size;
        console.log(
          `[taobao-image-collector] page ${page}, scroll ${round}, products ${currentItemCount}, page images ${pageImages.size}`
        );

        if (currentItemCount === lastItemCount) stableRounds += 1;
        else stableRounds = 0;
        lastItemCount = currentItemCount;

        if (stableRounds >= CONFIG.stableRoundsToStop) break;
        window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
        await sleep(CONFIG.scrollDelayMs);
      }

      if (!CONFIG.clickNextPage || page >= CONFIG.maxPages) break;
      const nextButton = findNextButton();
      if (!nextButton) break;
      nextButton.click();
      await sleep(2500);
    }

    const items = [...allItems.values()];
    const data = {
      sourceUrl: location.href,
      capturedAt: new Date().toISOString(),
      config: CONFIG,
      totalItems: items.length,
      totalItemImages: items.reduce((sum, item) => sum + item.images.length, 0),
      totalPageImages: pageImages.size,
      items,
      pageImages: [...pageImages.values()]
    };

    console.log("[taobao-image-collector] done", data);
    downloadJson(data);
  };

  run().catch((error) => {
    console.error("[taobao-image-collector] failed", error);
  });
})();
