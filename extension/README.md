# BeeThere browser extension

This project builds the BeeThere Manifest V3 Chrome extension.

## Requirements

- Node.js 22.12 or newer
- npm
- Google Chrome for manual use

## Install dependencies

From the `extension` directory, run:

```shell
npm ci
```

## Build

Set the BeeThere API origin when you build:

```shell
BEE_THERE_API_BASE_URL=http://127.0.0.1:8000 npm run build
```

Use only the origin, without an API path. The build writes this value into the
extension and grants host permission only to that origin. The unpacked
extension is written to `extension/dist`.

## Test

```shell
npm test
```

The tests build the extension, load it in Puppeteer's bundled Chromium, open
the real toolbar action popup, and check the popup shell.

## Install in Chrome

1. Build the extension.
2. Open `chrome://extensions` in Chrome.
3. Enable **Developer mode**.
4. Select **Load unpacked**.
5. Select the generated `extension/dist` directory.
6. Select the BeeThere toolbar action to open the popup. You can pin the
   action from Chrome's Extensions menu.
