/**
 * Simple Node.js script to create basic PNG icons
 * Creates minimal blue square icons for all required sizes
 */

const fs = require('fs');

// Minimal 1x1 blue PNG as base64
const bluePng = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwACAAH+NQpONAAAAABJRU5ErkJggg==';

// Create icon files
const sizes = [16, 32, 48, 128];

console.log('Creating placeholder PNG icons...');

sizes.forEach(size => {
  const filename = `icon-${size}.png`;
  const buffer = Buffer.from(bluePng, 'base64');
  
  try {
    fs.writeFileSync(filename, buffer);
    console.log(`✓ Created ${filename}`);
  } catch (error) {
    console.error(`✗ Failed to create ${filename}:`, error.message);
  }
});

console.log('\nPlaceholder icons created successfully!');
console.log('Note: These are minimal 1x1 blue pixels scaled to each size.');
console.log('For production, replace with proper icons generated from icon.svg');
