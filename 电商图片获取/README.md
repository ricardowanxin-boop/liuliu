# 淘宝店铺图片下载小脚本

这个方案不会接管或新建你的 Chrome 登录环境。你在已经登录的淘宝店铺页里运行采集脚本，浏览器会导出一个 JSON 清单；然后本地脚本按清单下载图片。

## 使用步骤

1. 在当前已登录的 Chrome 打开店铺页：

   `https://shop113713141.taobao.com/?spm=tbpc.mytb_followshop.item.shop`

2. 打开开发者工具 Console，把 `collect-taobao-images.browser.js` 的全部内容粘贴进去并回车。

   如果 Chrome 提示不允许粘贴，先在 Console 输入 `allow pasting` 并回车，再粘贴脚本。

3. 等页面自动向下滚动。结束后浏览器会下载一个类似这样的文件：

   `taobao-shop-images-2026-04-24T05-30-00-000Z.json`

4. 回到这个文件夹，在终端运行：

   ```bash
   node download-from-manifest.mjs ~/Downloads/taobao-shop-images-*.json --out ./downloads/lumi
   ```

图片会按商品分文件夹保存到 `./downloads/lumi`。
如果通配符匹配到多个清单文件，脚本会一起处理。

## 常用参数

- `--out ./downloads/lumi`：指定保存目录。
- `--concurrency 8`：并发下载数量，默认 6。
- `--force`：覆盖已经下载过的文件。
- `--page-images`：同时下载页面上采集到的其他图片，可能包含店铺 logo、图标、优惠券图。

## 只保留宝贝图

如果第一次采集混入了页面按钮、页脚广告、淘宝 UI 图标，先过滤清单，再下载：

```bash
node filter-product-images.mjs ~/Downloads/taobao-shop-images-*.json --out ./downloads/lumi-products-only.json
node download-from-manifest.mjs ./downloads/lumi-products-only.json --out ./downloads/lumi-products-only
```

过滤逻辑会保留当前店铺卖家素材 ID `716241818` 下的商品主图和缩略图，并排除淘宝页面素材。

示例：

```bash
node download-from-manifest.mjs ~/Downloads/taobao-shop-images-*.json --out ./downloads/lumi --concurrency 8
```

## 说明

- 默认只采集当前店铺页滚动加载出来的商品卡片图片。
- 如果要抓商品详情页里的详情图、主图全套、SKU 图，可以在这个基础上继续加详情页抓取。
- 淘宝页面结构经常变化，如果采集到的商品数明显不对，先刷新页面再运行一次。
