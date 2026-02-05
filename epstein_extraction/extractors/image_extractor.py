"""
Image metadata extraction (EXIF, dimensions, analysis)
"""
import os
import hashlib
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from loguru import logger
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import piexif

class ImageExtractor:
    """Extract metadata from image files"""

    def __init__(self):
        pass

    def extract(self, image_path: str) -> Optional[Dict]:
        """
        Extract all metadata from an image file

        Args:
            image_path: Path to image file

        Returns:
            Dictionary with extracted metadata
        """
        image_path = Path(image_path)

        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return None

        if not self._is_image_file(image_path):
            logger.warning(f"Not an image file: {image_path}")
            return None

        logger.info(f"Extracting image metadata: {image_path.name}")

        data = {
            'file_path': str(image_path.absolute()),
            'file_name': image_path.name,
            'media_type': 'image',
            'file_format': image_path.suffix.lower().replace('.', ''),
            'file_size_bytes': image_path.stat().st_size,
            'checksum': self._calculate_sha256(image_path),
            'original_filename': image_path.name,

            # EXIF data
            'date_taken': None,
            'camera_make': None,
            'camera_model': None,
            'gps_latitude': None,
            'gps_longitude': None,
            'gps_altitude': None,

            # Image properties
            'width_pixels': None,
            'height_pixels': None,
            'orientation': None,
        }

        try:
            img = Image.open(image_path)

            # Basic image properties
            data['width_pixels'] = img.width
            data['height_pixels'] = img.height
            data['orientation'] = self._get_orientation(img.width, img.height)

            # Extract EXIF data
            exif_data = img._getexif()
            if exif_data:
                self._extract_exif(data, exif_data)

            img.close()

        except Exception as e:
            logger.error(f"Failed to extract image metadata from {image_path.name}: {e}")
            return None

        return data

    def _is_image_file(self, file_path: Path) -> bool:
        """Check if file is a supported image format"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        return file_path.suffix.lower() in image_extensions

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file for deduplication"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_orientation(self, width: int, height: int) -> str:
        """Determine image orientation"""
        if width > height:
            return 'landscape'
        elif height > width:
            return 'portrait'
        else:
            return 'square'

    def _extract_exif(self, data: Dict, exif_data: dict):
        """Extract EXIF metadata from image"""
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)

            try:
                if tag == 'DateTime' or tag == 'DateTimeOriginal':
                    # Parse datetime
                    if isinstance(value, str):
                        try:
                            dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                            data['date_taken'] = dt
                        except ValueError:
                            logger.warning(f"Could not parse date: {value}")

                elif tag == 'Make':
                    data['camera_make'] = str(value)[:100]

                elif tag == 'Model':
                    data['camera_model'] = str(value)[:100]

                elif tag == 'GPSInfo':
                    self._extract_gps(data, value)

            except Exception as e:
                logger.debug(f"Error extracting EXIF tag {tag}: {e}")

    def _extract_gps(self, data: Dict, gps_info: dict):
        """Extract GPS coordinates from EXIF GPS data"""
        try:
            gps_data = {}
            for gps_tag_id in gps_info:
                gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                gps_data[gps_tag] = gps_info[gps_tag_id]

            # Extract latitude
            if 'GPSLatitude' in gps_data and 'GPSLatitudeRef' in gps_data:
                lat = self._convert_gps_to_decimal(
                    gps_data['GPSLatitude'],
                    gps_data['GPSLatitudeRef']
                )
                data['gps_latitude'] = lat

            # Extract longitude
            if 'GPSLongitude' in gps_data and 'GPSLongitudeRef' in gps_data:
                lon = self._convert_gps_to_decimal(
                    gps_data['GPSLongitude'],
                    gps_data['GPSLongitudeRef']
                )
                data['gps_longitude'] = lon

            # Extract altitude
            if 'GPSAltitude' in gps_data:
                alt = gps_data['GPSAltitude']
                if isinstance(alt, tuple):
                    data['gps_altitude'] = float(alt[0]) / float(alt[1])
                else:
                    data['gps_altitude'] = float(alt)

        except Exception as e:
            logger.warning(f"Failed to extract GPS data: {e}")

    def _convert_gps_to_decimal(self, gps_coord, ref) -> float:
        """
        Convert GPS coordinates from degrees/minutes/seconds to decimal

        Args:
            gps_coord: Tuple of (degrees, minutes, seconds)
            ref: Reference ('N', 'S', 'E', 'W')

        Returns:
            Decimal coordinate
        """
        degrees = float(gps_coord[0])
        minutes = float(gps_coord[1])
        seconds = float(gps_coord[2])

        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

        if ref in ['S', 'W']:
            decimal = -decimal

        return round(decimal, 8)

    def extract_embedded_images_from_pdf(self, pdf_path: str) -> list:
        """
        Extract embedded images from PDF

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of image paths
        """
        import fitz  # PyMuPDF

        pdf_path = Path(pdf_path)
        output_dir = pdf_path.parent / f"{pdf_path.stem}_images"
        output_dir.mkdir(exist_ok=True)

        extracted_images = []

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # Save image
                    image_filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                    image_path = output_dir / image_filename

                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)

                    extracted_images.append(str(image_path))
                    logger.info(f"Extracted image: {image_filename}")

            doc.close()

        except Exception as e:
            logger.error(f"Failed to extract images from PDF: {e}")

        return extracted_images


if __name__ == "__main__":
    # Test extraction
    extractor = ImageExtractor()

    # Test with a sample image (if available)
    test_file = Path("C:/Development/JaxSun.Ideas/tools/EpsteinDownloader/test_image.jpg")

    if test_file.exists():
        result = extractor.extract(str(test_file))
        if result:
            print(f"\nImage Metadata:")
            print(f"File: {result['file_name']}")
            print(f"Format: {result['file_format']}")
            print(f"Size: {result['file_size_bytes']} bytes")
            print(f"Dimensions: {result['width_pixels']}x{result['height_pixels']}")
            print(f"Orientation: {result['orientation']}")
            print(f"Date Taken: {result['date_taken']}")
            print(f"Camera: {result['camera_make']} {result['camera_model']}")
            print(f"GPS: {result['gps_latitude']}, {result['gps_longitude']}")
            print(f"Checksum: {result['checksum']}")
    else:
        print(f"Test file not found: {test_file}")
        print("Testing PDF image extraction instead...")

        # Test PDF image extraction
        test_pdf = Path("C:/Development/JaxSun.Ideas/tools/EpsteinDownloader/epstein_files/DataSet_9/EFTA00068050.pdf")
        if test_pdf.exists():
            images = extractor.extract_embedded_images_from_pdf(str(test_pdf))
            print(f"Extracted {len(images)} images from PDF")
