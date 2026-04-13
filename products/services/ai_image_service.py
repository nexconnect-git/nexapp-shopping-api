"""AI image generation service for the products app.

Provides a styled placeholder PNG generator used when a real AI image
pipeline is not yet integrated.
"""

import io
import hashlib
import textwrap

from PIL import Image as PILImage, ImageDraw
from django.core.files.base import ContentFile

PALETTE = [
    (99, 102, 241),   # indigo
    (16, 185, 129),   # emerald
    (245, 158, 11),   # amber
    (239, 68, 68),    # red
    (59, 130, 246),   # blue
]


class AIImageService:
    """Stateless service for AI placeholder image generation."""

    @staticmethod
    def make_placeholder_image(prompt: str) -> bytes:
        """Create a styled 512x512 placeholder PNG using Pillow.

        Selects a background colour deterministically from ``prompt`` via MD5,
        draws a subtle grid overlay, and renders the prompt text as a label.

        Args:
            prompt: Text prompt used to seed the colour selection and label.

        Returns:
            Raw PNG bytes of the generated image.
        """
        color_idx = int(hashlib.md5(prompt.encode()).hexdigest(), 16) % len(PALETTE)
        bg_color = PALETTE[color_idx]
        img = PILImage.new("RGB", (512, 512), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Subtle grid overlay using a slightly darker shade of the bg colour
        for x in range(0, 512, 32):
            draw.line(
                [(x, 0), (x, 512)],
                fill=(*bg_color[:2], max(0, bg_color[2] - 30)),
                width=1,
            )
        for y in range(0, 512, 32):
            draw.line(
                [(0, y), (512, y)],
                fill=(*bg_color[:2], max(0, bg_color[2] - 30)),
                width=1,
            )

        draw.rectangle([(40, 200), (472, 312)], fill=(0, 0, 0, 120))
        label = textwrap.fill(f"AI: {prompt[:60]}", width=30)
        draw.text((256, 240), label, fill="white", anchor="mm")
        draw.text((256, 296), "\u2726 AI Generated \u2726", fill=(220, 220, 255), anchor="mm")

        image_buffer = io.BytesIO()
        img.save(image_buffer, format="PNG")
        return image_buffer.getvalue()

    @classmethod
    def generate_content_file(cls, prompt: str, filename: str) -> ContentFile:
        """Generate a placeholder PNG and return it as a Django ContentFile.

        Args:
            prompt: Text prompt for the image.
            filename: Desired filename for the ContentFile.

        Returns:
            A ``ContentFile`` containing the PNG bytes.
        """
        png_bytes = cls.make_placeholder_image(prompt)
        return ContentFile(png_bytes, name=filename)
