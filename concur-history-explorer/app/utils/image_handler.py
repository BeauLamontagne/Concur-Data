"""Locate and serve receipt images from the extracted images directory."""

from pathlib import Path

IMAGES_BASE = Path(__file__).resolve().parents[3] / "db" / "images"


def find_receipt_image(receipt_image_id: str | None, ereceipt_image_id: str | None = None) -> Path | None:
    """Search for a receipt image by ID, returning the first matching file path."""
    ids_to_check = [i for i in (receipt_image_id, ereceipt_image_id) if i and str(i).strip() not in ("", "None", "nan")]
    if not ids_to_check or not IMAGES_BASE.exists():
        return None

    for image_id in ids_to_check:
        image_id = str(image_id).strip()
        # Search recursively — images may be nested under report folders
        for candidate in IMAGES_BASE.rglob(f"{image_id}*"):
            if candidate.is_file():
                return candidate

    return None


def get_image_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }.get(suffix, "application/octet-stream")
