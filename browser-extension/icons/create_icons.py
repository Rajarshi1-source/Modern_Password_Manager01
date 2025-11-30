#!/usr/bin/env python3
"""
Create simple placeholder PNG icons for the browser extension
"""
import base64

# Minimal blue PNG data (16x16 pixels)
png_16_data = """
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlz
AAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAFYSURB
VDiNpZM9SwNBEIafgxDbpLGwsLGwsU2hYGMhFlYWVhYWFhYWthZWFhZWVlYWVlYWVhYWFhYWVhYW
VlYWVlYWVlYWVhYWVhYWVlYWVlYWVlYWVlYWVhYWVhYWVhYWVhYWVhYWVlYWVlYWVlYWVlYWVlYW
VlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYW
VlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYWVlYW
AAAABJRSUhEVGaff=
"""

# Simple blue square PNG (suitable for all sizes)
simple_png_data = """
iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==
"""

def create_icon_file(size, filename):
    """Create a simple PNG icon file"""
    try:
        # Decode the base64 PNG data
        png_data = base64.b64decode(simple_png_data.replace('\n', ''))
        
        # Write to file
        with open(filename, 'wb') as f:
            f.write(png_data)
        
        print(f"Created {filename} ({size}x{size})")
        return True
    except Exception as e:
        print(f"Error creating {filename}: {e}")
        return False

def main():
    """Create all required icon sizes"""
    sizes = [16, 32, 48, 128]
    
    print("Creating placeholder PNG icons...")
    
    for size in sizes:
        filename = f"icon-{size}.png"
        create_icon_file(size, filename)
    
    print("\nPlaceholder icons created!")
    print("Note: These are minimal 1x1 pixel placeholders.")
    print("Replace with proper icons generated from icon.svg for production use.")

if __name__ == "__main__":
    main()
