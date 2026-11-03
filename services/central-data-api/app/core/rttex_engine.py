"""
Wrapper around `growtopia.rttex_converter` (from H-pun/growtopia-api).
Handles RTTEX <-> PNG conversions and 32x32 item sprite extraction from local .rttex sheets.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
import requests

from growtopia.rttex_converter import rttex_pack, rttex_unpack
from app.schemas import ItemRecord

LOCAL_GT_DIRS: list[Path] = [
    Path.home() / "AppData" / "Local" / "Growtopia" / "game",
    Path.home() / "AppData" / "Local" / "Growtopia" / "cache",
]


def unpack_rttex_to_png_bytes(
    raw_rttex: bytes,
    *,
    tile_x: int | None = None,
    tile_y: int | None = None,
    force_opaque: bool = False,
) -> bytes:
    """Convert raw `.rttex` (or `RTPACK`-compressed `.rttex`) bytes into `.png` bytes."""
    stream = rttex_unpack(
        raw_rttex,
        x=tile_x,
        y=tile_y,
        force_opaque=force_opaque,
    )
    if stream is None:
        raise ValueError("Invalid RTTEX file: missing RTTXTR/RTPACK header.")
    return stream.read()


def pack_png_to_rttex_bytes(raw_png: bytes) -> bytes:
    """Convert standard `.png` bytes into `RTPACK`-compressed `.rttex` bytes."""
    stream = rttex_pack(raw_png)
    if stream is None:
        raise ValueError("Failed to pack PNG into RTTEX format.")
    return stream.read()


def find_texture_file(file_name: str, textures_dir: Path) -> Path | None:
    """Locate an .rttex file in `textures_dir` or local Growtopia game/cache directories."""
    if not file_name:
        return None
    base_name = Path(file_name).name
    rel_path = Path(file_name)

    search_roots = [textures_dir, *LOCAL_GT_DIRS]
    for root in search_roots:
        if not root.exists():
            continue
        for candidate in (root / rel_path, root / base_name, root / "game" / rel_path, root / "game" / base_name):
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def extract_item_sprite_png(item: ItemRecord, textures_dir: Path, scale: int = 4) -> bytes:
    """
    Slice a 32x32 sprite from the item's `.rttex` texture file using H-pun/growtopia-api's
    `rttex_unpack` and upscale it cleanly using Nearest Neighbor for crisp Discord display.
    """
    texture_path = find_texture_file(item.file_name, textures_dir)
    if texture_path:
        try:
            raw_rttex = texture_path.read_bytes()
            png_bytes = unpack_rttex_to_png_bytes(
                raw_rttex,
                tile_x=item.tex_x,
                tile_y=item.tex_y,
            )
            with Image.open(BytesIO(png_bytes)) as sprite:
                if scale > 1:
                    sprite = sprite.resize(
                        (sprite.width * scale, sprite.height * scale),
                        resample=Image.Resampling.NEAREST,
                    )
                out = BytesIO()
                sprite.save(out, format="PNG")
                return out.getvalue()
        except Exception:
            pass

    # Cloud fallback: fetch official item sprite from Growtopia Wiki when local .rttex sheets aren't mounted
    try:
        from app.core.wiki_scraper import wiki_service

        wiki_info = wiki_service.fetch_item(item.name)
        sprite_url = (wiki_info.sprites.get("Item") or next(iter(wiki_info.sprites.values()), None)) if wiki_info and wiki_info.sprites else None
        if sprite_url:
            resp = requests.get(sprite_url, timeout=6)
            if resp.status_code == 200 and resp.content:
                with Image.open(BytesIO(resp.content)).convert("RGBA") as sprite:
                    if sprite.width <= 64 and scale > 1:
                        sprite = sprite.resize(
                            (sprite.width * scale, sprite.height * scale),
                            resample=Image.Resampling.NEAREST,
                        )
                    out = BytesIO()
                    sprite.save(out, format="PNG")
                    return out.getvalue()
    except Exception:
        pass

    # Fallback badge if the specific .rttex sheet is not found locally
    size = 32 * max(1, scale)
    img = Image.new("RGBA", (size, size), (34, 40, 49, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, size - 3, size - 3], outline=(0, 173, 181, 255), width=3)
    initials = "".join(word[0] for word in item.name.split()[:3]).upper() or "?"
    draw.text((size // 4, size // 3), f"#{item.id}\n{initials}", fill=(238, 238, 238, 255))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
