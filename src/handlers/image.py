from PIL import Image
import os
from ..core.base import BaseCompressor

class ImageCompressor(BaseCompressor):
    """
    Handles compression for Image files (JPG, PNG) using Pillow.
    
    Capabilities:
    - Smart Resizing: Logic to reduce resolution while maintaining aspect ratio.
    - Format Optimization:
        - JPEG: Adjusts quality factor.
        - PNG: Adjusts compression level (zlib) or color palette (P mode).
    """

    # Configuration: (Resize Factor, JPEG Quality, PNG Compress Level)
    SETTINGS = {
        'low': (1.0, 85, 3),      # No resize, High Quality
        'medium': (0.9, 75, 6),   # 90% resize, Medium Quality
        'high': (0.7, 50, 9)      # 70% resize, Low Quality
    }

    def compress(self, input_path: str, output_path: str) -> bool:
        """
        Compresses an image file.
        
        Args:
            input_path (str): Path to source image.
            output_path (str): Target path.

        Returns:
            bool: Success status.
        """
        if not self.validate(input_path):
            return False

        try:
            resize_factor, jpeg_qual, png_level = self.SETTINGS.get(self.level, (0.9, 75, 6))
            
            with Image.open(input_path) as img:
                # Capture original format to preserve it (unless optimization requires change)
                fmt = img.format
                
                # Resize if configured (Scaling down)
                if resize_factor < 1.0:
                    new_size = (int(img.width * resize_factor), int(img.height * resize_factor))
                    # LANCZOS filter provides best quality for downsampling
                    resample_filter = Image.Resampling.LANCZOS
                    img = img.resize(new_size, resample=resample_filter)
                    self.logger.debug(f"Resized image to {new_size} (Factor: {resize_factor})")

                save_kwargs = {'optimize': True}

                if fmt == 'JPEG':
                    save_kwargs['quality'] = jpeg_qual
                    # JPEG does not support Alpha (RGBA) or Palette (P), convert to RGB
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                elif fmt == 'PNG':
                    save_kwargs['compress_level'] = png_level
                    # For 'High' compression, we can reduce bit depth to 8-bit palette (256 colors)
                    # This significantly reduces size for non-photorealistic PNGs.
                    if self.level == 'high' and img.mode != 'P':
                        img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
                
                img.save(output_path, **save_kwargs)
                return True

        except Exception as e:
            self.logger.error(f"Failed to compress Image {input_path}: {e}")
             # Clean up partial file
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return False
