# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Check and store the screenshots sent with feedback.

An uploaded file is never kept as received. It is opened as an image and drawn
afresh, which proves it is one and removes any hidden data. Files are stored
under random names, outside anything the web server publishes.
"""

from __future__ import annotations

import io
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from flask import current_app
from PIL import Image, ImageOps

DEFAULT_MAX_FILES = 3
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_PIXELS = 25_000_000
_DEFAULT_UPLOAD_DIR = "~/moh_feedback_uploads"
# Room for the text of the form alongside the largest allowed files
_FORM_OVERHEAD_BYTES = 1024 * 1024
_FORMATS = {"PNG": ("png", "image/png"), "JPEG": ("jpg", "image/jpeg")}
_ALPHA_MODES = ("RGBA", "LA", "PA")
_NAME_MAX_LENGTH = 255
_NOT_AN_IMAGE = "Only PNG or JPEG images can be attached."


class ScreenshotError(Exception):
    """A screenshot cannot be accepted; the message is shown to the sender."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class Screenshot:
    """An image that has been checked and re-drawn."""

    data: bytes
    extension: str
    content_type: str
    original_name: str


@dataclass(frozen=True)
class StoredScreenshot:
    """A screenshot saved on disk."""

    stored_name: str
    content_type: str
    original_name: str
    size_bytes: int


def max_files() -> int:
    return current_app.config.get("MOH_FEEDBACK_MAX_SCREENSHOTS", DEFAULT_MAX_FILES)


def max_bytes() -> int:
    return current_app.config.get(
        "MOH_FEEDBACK_SCREENSHOT_MAX_BYTES", DEFAULT_MAX_BYTES
    )


def _max_pixels() -> int:
    return current_app.config.get(
        "MOH_FEEDBACK_SCREENSHOT_MAX_PIXELS", DEFAULT_MAX_PIXELS
    )


def max_request_bytes() -> int:
    """Return the largest form that can hold the allowed screenshots."""
    return max_files() * max_bytes() + _FORM_OVERHEAD_BYTES


def _safe_name(raw: str) -> str:
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    printable = "".join(character for character in name if character.isprintable())
    return printable.strip()[:_NAME_MAX_LENGTH] or "screenshot"


def _redraw(raw: bytes) -> tuple[bytes, str, str]:
    """Return a new image file holding only the picture from ``raw``."""
    with Image.open(io.BytesIO(raw), formats=tuple(_FORMATS)) as image:
        # Some phones save a photo as a JPEG holding several pictures
        image_format = "JPEG" if image.format == "MPO" else str(image.format)
        width, height = image.size
        if width * height > _max_pixels():
            raise ScreenshotError("That image is too large. Please send a smaller one.")
        image.load()
        upright = ImageOps.exif_transpose(image)
        has_alpha = upright.mode in _ALPHA_MODES or "transparency" in upright.info
        mode = "RGBA" if image_format == "PNG" and has_alpha else "RGB"
        clean = Image.new(mode, upright.size)
        clean.paste(upright.convert(mode))
    output = io.BytesIO()
    if image_format == "JPEG":
        clean.save(output, "JPEG", quality=85)
    else:
        clean.save(output, "PNG")
    extension, content_type = _FORMATS[image_format]
    return output.getvalue(), extension, content_type


def clean_screenshot(storage: Any) -> Screenshot:
    """Return a checked copy of an uploaded file, or raise ``ScreenshotError``."""
    limit = max_bytes()
    raw = storage.read(limit + 1)
    if len(raw) > limit:
        megabytes = limit // (1024 * 1024)
        raise ScreenshotError(f"Each screenshot must be under {megabytes} MB.")
    try:
        data, extension, content_type = _redraw(raw)
    except ScreenshotError:
        raise
    except Exception as ex:  # pylint: disable=broad-except
        # Damaged files make the image decoders fail in many different ways
        raise ScreenshotError(_NOT_AN_IMAGE) from ex
    return Screenshot(data, extension, content_type, _safe_name(storage.filename or ""))


def prepare_screenshots(files: Iterable[Any]) -> list[Screenshot]:
    """Check the files chosen on the form; an unused file box sends a blank one."""
    chosen = [storage for storage in files if storage and storage.filename]
    limit = max_files()
    if len(chosen) > limit:
        raise ScreenshotError(f"You can attach up to {limit} screenshots.")
    return [clean_screenshot(storage) for storage in chosen]


def upload_dir() -> Path:
    configured = (
        current_app.config.get("MOH_FEEDBACK_UPLOAD_DIR") or _DEFAULT_UPLOAD_DIR
    )
    return Path(configured).expanduser()


def file_path(stored_name: str) -> Path:
    return upload_dir() / stored_name


def remove_files(stored: Iterable[StoredScreenshot]) -> None:
    for item in stored:
        file_path(item.stored_name).unlink(missing_ok=True)


def store_screenshots(screenshots: list[Screenshot]) -> list[StoredScreenshot]:
    """Save screenshots, leaving nothing behind if any of them cannot be saved."""
    stored: list[StoredScreenshot] = []
    if not screenshots:
        return stored
    try:
        upload_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
        for screenshot in screenshots:
            name = f"{uuid.uuid4().hex}.{screenshot.extension}"
            descriptor = os.open(
                file_path(name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "wb") as target:
                target.write(screenshot.data)
            stored.append(
                StoredScreenshot(
                    name,
                    screenshot.content_type,
                    screenshot.original_name,
                    len(screenshot.data),
                )
            )
    except OSError as ex:
        remove_files(stored)
        raise ScreenshotError(
            "We could not save your screenshots. Please try again without them."
        ) from ex
    return stored
