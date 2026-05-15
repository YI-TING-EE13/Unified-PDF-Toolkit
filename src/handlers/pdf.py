import fitz  # PyMuPDF
import io
from PIL import Image
from typing import Optional
from ..core.base import BaseCompressor

class PDFCompressor(BaseCompressor):
    """
    Handles PDF compression using PyMuPDF (Fitz).
    
    Features:
    - Font Subsetting: Removes unused glyphs from embedded fonts.
    - Garbage Collection: Removes unused objects and compacts cross-reference tables.
    - Image Optimization: Downsamples and compresses embedded images to JPEG.
    """

    def __init__(
        self,
        level: str = "medium",
        optimize_images: bool = True,
        max_image_dimension: Optional[int] = None,
        jpeg_quality: Optional[int] = None,
        lossless_only: bool = False,
    ):
        super().__init__(level)
        self.optimize_images = optimize_images
        self.max_image_dimension = max_image_dimension
        self.jpeg_quality = jpeg_quality
        self.lossless_only = lossless_only

    def compress(self, input_path: str, output_path: str) -> bool:
        """
        Compresses a PDF file.

        Args:
            input_path (str): Path to source PDF.
            output_path (str): Path to write compressed PDF.

        Returns:
            bool: Success status.
        """
        if not self.validate(input_path):
            return False

        try:
            doc = fitz.open(input_path)
            
            # 1. Font Subsetting
            # This relies on creating a new PDF subset but doc.subset_fonts() modifies in-place for save
            try:
                doc.subset_fonts()
            except Exception as e:
                self.logger.warning(f"Font subsetting warning (non-fatal): {e}")

            # 2. Image Optimization (Only for Medium/High levels unless advanced settings override)
            if (
                self.optimize_images
                and not self.lossless_only
                and (self.level in ('medium', 'high') or self.max_image_dimension or self.jpeg_quality)
            ):
                self._optimize_images(doc)

            # 3. Save with Garbage Collection and Stream Deflation
            # garbage=4: Eliminate duplicate objects, checks validation
            # garbage=3: Merge duplicate objects
            # garbage=2: Remove unused objects
            garbage_level = 4 if self.level == 'high' else 3 if self.level == 'medium' else 2
            
            doc.save(
                output_path,
                garbage=garbage_level,
                deflate=True, # Compress all streams
                clean=True    # Clean contents syntax
            )
            doc.close()
            return True

        except Exception as e:
            self.logger.error(f"Failed to compress PDF {input_path}: {e}")
            return False

    def _optimize_images(self, doc):
        """
        Scans and optimizes images within the PDF document.
        
        Strategy:
        - Extract image streams.
        - Check if they are already efficient.
        - Resize if dimensions exceed threshold (based on compression level).
        - Convert to JPEG (DCTDecode) unless transparency exists.
        - Update PDF object dictionary to reflect new format.
        """
        # Configuration based on level
        if self.max_image_dimension:
            max_dim = self.max_image_dimension
        elif self.level == 'high':
            # Max dimension usually corresponds to ~72-96 DPI on A4
            max_dim = 1000 
        else: # medium
            # Max dimension usually corresponds to ~150 DPI on A4
            max_dim = 2000

        if self.jpeg_quality:
            jpg_quality = self.jpeg_quality
        elif self.level == 'high':
            # Lower quality for maximum space saving
            jpg_quality = 40
        else:
            # Balanced quality
            jpg_quality = 70

        # Collect unique images to avoid processing shared resources twice
        img_xrefs = set()
        for page in doc:
            for img in page.get_images():
                img_xrefs.add(img[0]) # The first item is the XREF ID

        total_imgs = len(img_xrefs)
        if total_imgs > 0:
            self.logger.info(f"Scanning {total_imgs} images for optimization...")

        for xref in img_xrefs:
            try:
                # 1. Extract Image Stream
                stream = doc.extract_image(xref)
                if not stream: 
                    continue
                
                img_bytes = stream["image"]
                
                # Skip small images (< 10KB) to avoid overhead on logos/icons
                if len(img_bytes) < 10240: 
                    continue

                # 2. Optimize with Pillow
                with Image.open(io.BytesIO(img_bytes)) as pil_img:
                    w, h = pil_img.size
                    
                    # Safety: Skip optimization for images with transparency (Alpha channel)
                    # Converting these to JPEG results in black backgrounds or visual artifacts.
                    if pil_img.mode in ('RGBA', 'LA') or (pil_img.mode == 'P' and 'transparency' in pil_img.info):
                         self.logger.debug(f"Skipping transparency image xref {xref}")
                         continue

                    # 3. Resizing and Conversion
                    buffer = io.BytesIO()
                    
                    # Downsample if image is larger than target bounds
                    if max(w, h) > max_dim:
                         ratio = max_dim / max(w, h)
                         new_size = (int(w * ratio), int(h * ratio))
                         
                         # Ensure valid mode for scaling/saving
                         if pil_img.mode not in ('RGB', 'L'):
                            pil_img = pil_img.convert('RGB')
                            
                         pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                    elif pil_img.mode not in ('RGB', 'L'):
                         # Convert simple non-transparent images to RGB for JPEG compatibility
                         pil_img = pil_img.convert('RGB')

                    # Save as optimized JPEG
                    pil_img.save(buffer, format="JPEG", quality=jpg_quality, optimize=True)
                    new_bytes = buffer.getvalue()

                    # 4. Update Stream (If size reduction achieved)
                    if len(new_bytes) < len(img_bytes):
                        try:
                            # CRITICAL: We must disable automatic compression (compress=False)
                            # because we are injecting pre-compressed JPEG bytes. 
                            # If True (default), PyMuPDF wraps our JPEG in a FlateDecode stream,
                            # but we set the filter to DCTDecode, creating a corrupted stream.
                            doc.update_stream(xref, new_bytes, compress=False)
                            
                            # Update PDF Dictionary to match new content
                            # Set Filter to DCTDecode (JPEG)
                            doc.xref_set_key(xref, "Filter", "/DCTDecode")
                            # Set ColorSpace
                            doc.xref_set_key(xref, "ColorSpace", "/DeviceRGB" if pil_img.mode == 'RGB' else "/DeviceGray")
                            
                            # Remove/Reset incompatible keys from original stream (e.g., Flate params)
                            doc.xref_set_key(xref, "DecodeParms", "null")
                            doc.xref_set_key(xref, "BitsPerComponent", "8")
                            
                            # Update dimensions
                            doc.xref_set_key(xref, "Width", str(pil_img.width))
                            doc.xref_set_key(xref, "Height", str(pil_img.height))
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to update structure for xref {xref}: {e}")
            except Exception as e:
                self.logger.debug(f"Skipping image xref {xref}: {e}")
