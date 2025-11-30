# Desktop Application Assets

This directory contains assets for the Password Manager desktop application.

## Icons

The application requires icons in different formats for different platforms:

- `icon.png` - Default icon (256x256 recommended)
- `icon.ico` - Windows icon (16x16, 32x32, 48x48, 64x64, 128x128, 256x256)
- `icon.icns` - macOS icon (contains multiple sizes)

## Creating Icons

### From SVG Source

If you have an SVG source file, you can generate all required formats:

1. **Install ImageMagick** or use an online converter
2. **Generate PNG sizes:**
   ```bash
   convert icon.svg -resize 256x256 icon.png
   convert icon.svg -resize 512x512 icon@2x.png
   ```

3. **Generate Windows ICO:**
   ```bash
   convert icon.svg -resize 16x16 icon-16.png
   convert icon.svg -resize 32x32 icon-32.png
   convert icon.svg -resize 48x48 icon-48.png
   convert icon.svg -resize 64x64 icon-64.png
   convert icon.svg -resize 128x128 icon-128.png
   convert icon.svg -resize 256x256 icon-256.png
   convert icon-16.png icon-32.png icon-48.png icon-64.png icon-128.png icon-256.png icon.ico
   ```

4. **Generate macOS ICNS:**
   - Use the `iconutil` command on macOS or online converters

### Icon Requirements

- **Minimum size:** 256x256 pixels
- **Format:** PNG with transparency
- **Style:** Should work well at small sizes (16x16)
- **Colors:** Should work on both light and dark backgrounds

## Current Status

The current `icon.png` is a placeholder. For production, you should replace it with:

1. A proper application icon that represents the Password Manager
2. Professional-quality graphics
3. Multiple sizes for different use cases

## Electron Builder Configuration

The `package.json` file is configured to use these icons:

```json
"build": {
  "win": {
    "icon": "assets/icon.ico"
  },
  "mac": {
    "icon": "assets/icon.icns"
  },
  "linux": {
    "icon": "assets/icon.png"
  }
}
```

Make sure to create the appropriate icon files for your target platforms.
