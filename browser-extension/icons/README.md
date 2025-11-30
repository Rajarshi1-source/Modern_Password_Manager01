# Browser Extension Icons

This directory contains the icon files for the Password Manager browser extension.

## Current Status

The icons are currently represented by an SVG template (`icon.svg`). To create the required PNG icons for the browser extension, you need to convert this SVG to the following sizes:

- `icon-16.png` (16x16 pixels)
- `icon-32.png` (32x32 pixels) 
- `icon-48.png` (48x48 pixels)
- `icon-128.png` (128x128 pixels)

## Converting SVG to PNG

### Using Online Tools:
1. Go to https://cloudconvert.com/svg-to-png
2. Upload the `icon.svg` file
3. Set the output size to each required dimension
4. Download and rename the files accordingly

### Using ImageMagick (if installed):
```bash
# Install ImageMagick first, then run:
magick icon.svg -resize 16x16 icon-16.png
magick icon.svg -resize 32x32 icon-32.png
magick icon.svg -resize 48x48 icon-48.png
magick icon.svg -resize 128x128 icon-128.png
```

### Using Node.js (sharp package):
```bash
npm install sharp
node -e "
const sharp = require('sharp');
const svg = require('fs').readFileSync('icon.svg');
[16, 32, 48, 128].forEach(size => {
  sharp(svg).resize(size, size).png().toFile(\`icon-\${size}.png\`);
});
"
```

## Design Notes

The icon features:
- Blue circular background representing security
- White padlock symbolizing password protection
- Golden accent representing premium security
- Clean, recognizable design at all sizes

## Temporary Solution

Until the PNG icons are generated, you can use any placeholder 16x16, 32x32, 48x48, and 128x128 PNG files with appropriate names to prevent the extension from failing to load.
