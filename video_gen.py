"""
VideoGenerator — creates narrated MP4 slide videos from RAG answers.

Pipeline:
  1. Build a structured slide script from the RAG answer text.
  2. Render each slide as a Pillow image (text on a coloured background).
  3. Generate a gTTS narration MP3 per slide.
  4. Stitch frames + audio into a final MP4 via moviepy.

All dependencies are free, local, and require no GPU.
"""

from __future__ import annotations

import io
import logging
import math
import os
import tempfile
import textwrap
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from gtts import gTTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
SLIDE_BG_COLOR = (15, 23, 42)          # dark navy
SLIDE_ACCENT_COLOR = (37, 99, 235)     # blue
TEXT_COLOR = (248, 250, 252)           # near-white
TITLE_WRAP_WIDTH = 20                 # chars per line for title
BODY_WRAP_WIDTH = 36                  # chars per line for body
SLIDE_DURATION_SEC = 5.0              # minimum display time per slide
FONT_SIZE_TITLE = 52
FONT_SIZE_BODY = 32
LINE_SPACING = 1.5
PADDING = 80
AUDIO_SPEED_FACTOR = 1.1              # speed up TTS slightly to stay on slide

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Slide:
    """Represents one slide in the generated video."""
    title: str
    body: str
    audio_bytes: bytes = field(default=b"", repr=False)
    duration_sec: float = SLIDE_DURATION_SEC


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wrap_text(text: str, width: int) -> List[str]:
    """Wrap text into lines of at most `width` characters."""
    if not text:
        return []
    wrapped: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            wrapped.append("")
            continue
        lines = textwrap.wrap(paragraph, width=width, break_long_words=True, break_on_hyphens=True)
        wrapped.extend(lines if lines else [""])
    return wrapped


def _estimate_audio_duration(text: str) -> float:
    """Rough estimate of TTS duration in seconds (avg 150 words/min)."""
    words = len(text.split())
    return max(2.0, words / 2.5)


# ---------------------------------------------------------------------------
# Pillow frame renderer
# ---------------------------------------------------------------------------

def _load_font(size: int) -> "ImageFont.FreeTypeFont":   # type: ignore[name-defined]
    """Return a best-effort PIL ImageFont at the requested size."""
    try:
        from PIL import ImageFont
        # Try a few common paths on macOS / Linux / Windows
        for path in [
            f"/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        # Fall back to default
        return ImageFont.load_default(size=size)  # type: ignore
    except Exception:
        return ImageFont.load_default(size=size)  # type: ignore


def _draw_slide(title: str, body: str) -> "Image.Image":   # type: ignore[name-defined]
    """Render a single slide as a Pillow image."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), SLIDE_BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(FONT_SIZE_TITLE)
    font_body  = _load_font(FONT_SIZE_BODY)

    # --- Title area (top 30 % of frame) ---
    title_lines = _wrap_text(title, TITLE_WRAP_WIDTH)
    title_height = len(title_lines) * int(FONT_SIZE_TITLE * LINE_SPACING)

    # Accent bar under title
    bar_y = PADDING + title_height + 16
    draw.rectangle(
        [PADDING, bar_y, PADDING + 120, bar_y + 6],
        fill=SLIDE_ACCENT_COLOR,
    )

    # --- Body area (below title) ---
    body_top = bar_y + 32
    body_lines = _wrap_text(body, BODY_WRAP_WIDTH)

    y = body_top
    for line in body_lines:
        if y > FRAME_HEIGHT - PADDING - FONT_SIZE_BODY:
            break
        draw.text((PADDING, y), line, font=font_body, fill=TEXT_COLOR)
        y += int(FONT_SIZE_BODY * LINE_SPACING)

    # Slide number watermark (bottom-right)
    draw.text(
        (FRAME_WIDTH - PADDING - 60, FRAME_HEIGHT - PADDING - 24),
        "INVINCIBLE",
        font=font_body,
        fill=(100, 116, 139),
    )

    return img


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class VideoGenerator:
    """
    Generates narrated MP4 slide videos from RAG answer text.

    Parameters
    ----------
    output_dir : str | Path
        Directory where video files are saved. Created if missing.
    temp_dir : str | Path, optional
        Directory for intermediate files (frames, audio). Uses system temp if None.
    """

    def __init__(
        self,
        output_dir: str | Path = "./videos",
        temp_dir: str | Path | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        answer_text: str,
        session_id: str,
        title: str = "Document Overview",
    ) -> str:
        """
        Generate a narrated MP4 video from `answer_text`.

        Parameters
        ----------
        answer_text : str
            The full RAG answer (used as the video script).
        session_id : str
            Unique session identifier (used in the output filename).
        title : str
            Title shown on the first slide.

        Returns
        -------
        str
            Absolute path to the generated MP4 file.

        Raises
        ------
        RuntimeError
            If video generation fails at any step.
        """
        try:
            slides = self._build_slides(answer_text, title)
            if not slides:
                raise RuntimeError("No content to generate video from.")

            video_path = self._stitch_video(slides, session_id)
            return str(video_path)
        except Exception as exc:
            logger.exception("Video generation failed")
            raise RuntimeError(f"Video generation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _build_slides(self, answer_text: str, title: str) -> List[Slide]:
        """
        Split answer text into structured slides and generate TTS audio.
        """
        sections = self._split_into_sections(answer_text)
        slides: List[Slide] = []

        for idx, (sec_title, sec_body) in enumerate(sections):
            if not sec_body.strip():
                continue

            # First slide gets the provided title
            slide_title = title if idx == 0 else sec_title
            slide = Slide(title=slide_title, body=sec_body)

            # Generate audio in a thread so we don't block the main thread
            audio_event = threading.Event()
            audio_error: List[Optional[Exception]] = [None]

            def _tts_worker() -> None:
                try:
                    tts = gTTS(text=f"{slide_title}. {sec_body}", lang="en", slow=False)
                    buf = io.BytesIO()
                    tts.write_to_fp(buf)
                    buf.seek(0)
                    slide.audio_bytes = buf.read()
                    # Estimate duration based on word count
                    slide.duration_sec = max(
                        SLIDE_DURATION_SEC,
                        _estimate_audio_duration(f"{slide_title}. {sec_body}"),
                    )
                except Exception as exc:
                    audio_error[0] = exc
                finally:
                    audio_event.set()

            tts_thread = threading.Thread(target=_tts_worker, daemon=True)
            tts_thread.start()
            tts_thread.join(timeout=15)   # don't wait forever for TTS

            if audio_error[0]:
                logger.warning("TTS failed for slide %d: %s", idx, audio_error[0])
                slide.duration_sec = SLIDE_DURATION_SEC

            slides.append(slide)

        return slides

    def _split_into_sections(self, text: str) -> List[tuple[str, str]]:
        """
        Split answer text into (heading, body) sections.
        Uses sentence-level chunking to keep slides readable.
        """
        MAX_CHARS_PER_SLIDE = 600

        # Try to split on numbered/bulleted patterns first
        import re
        parts = re.split(r"(?=\n?\d+[\.\)]\s)", text)
        sections: List[tuple[str, str]] = []
        current_title = "Overview"
        current_body_parts: List[str] = []
        current_char_count = 0

        def _flush() -> None:
            if current_body_parts:
                body = "\n".join(current_body_parts).strip()
                if body:
                    sections.append((current_title, body))
            current_body_parts.clear()
            current_char_count = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Detect if this part looks like a heading
            heading_match = re.match(r"^\d+[\.\)]\s+(.{5,60})$", part)
            if heading_match and len(part) < 120:
                _flush()
                current_title = heading_match.group(1).strip()
                remaining = part[len(heading_match.group(0)):].strip()
                if remaining:
                    current_body_parts.append(remaining)
                    current_char_count += len(remaining)
            else:
                if current_char_count + len(part) > MAX_CHARS_PER_SLIDE:
                    _flush()
                    current_title = "Continued"
                current_body_parts.append(part)
                current_char_count += len(part)

        _flush()
        return sections

    def _stitch_video(self, slides: List[Slide], session_id: str) -> Path:
        """
        Render Pillow frames and stitch them with audio into an MP4.
        """
        try:
            from moviepy.editor import (
                AudioFileClip,
                ColorClip,
                CompositeVideoClip,
                ImageClip,
                concatenate_videoclips,
            )
        except ImportError as exc:
            raise ImportError(
                "moviepy is required for video generation. "
                "Install it with: pip install moviepy"
            ) from exc

        # Use a unique run ID for temp files to avoid collisions
        run_id = f"{session_id}_{os.urandom(4).hex()}"
        output_filename = f"video_{run_id}.mp4"
        output_path = self.output_dir / output_filename

        clip_list: List["VideoFileClip"] = []   # type: ignore[name-defined]
        audio_clips: List["AudioFileClip"] = []  # type: ignore[name-defined]
        temp_files: List[Path] = []
        final_clip = None

        try:
            for idx, slide in enumerate(slides):
                # Render frame
                frame_img = _draw_slide(slide.title, slide.body)

                # Save frame to temp PNG
                frame_path = self._temp_dir / f"frame_{run_id}_{idx}.png"
                frame_img.save(frame_path, "PNG")
                temp_files.append(frame_path)

                # Create ImageClip
                img_clip = ImageClip(str(frame_path))

                # Add audio if available
                if slide.audio_bytes:
                    audio_path = self._temp_dir / f"audio_{run_id}_{idx}.mp3"
                    audio_path.write_bytes(slide.audio_bytes)
                    temp_files.append(audio_path)
                    try:
                        audio_clip = AudioFileClip(str(audio_path))
                        # Trim slightly inside the reported MP3 duration to avoid
                        # decoder boundary reads at the final audio frame.
                        safe_duration = max(0.1, round(audio_clip.duration, 2) - 0.20)
                        audio_clip = audio_clip.subclip(0, safe_duration)
                        img_clip = img_clip.set_duration(safe_duration)
                        img_clip = img_clip.set_audio(audio_clip)
                        audio_clips.append(audio_clip)
                    except Exception as exc:
                        logger.warning("Could not attach audio for slide %d: %s", idx, exc)
                        img_clip = img_clip.set_duration(slide.duration_sec)
                else:
                    img_clip = img_clip.set_duration(slide.duration_sec)

                clip_list.append(img_clip)  # type: ignore

            if not clip_list:
                raise RuntimeError("No clips to concatenate.")

            try:
                final_clip = concatenate_videoclips(clip_list, method="compose")
                final_clip = final_clip.set_fps(24)

                final_clip.write_videofile(
                    str(output_path),
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    bitrate="2000k",
                    preset="fast",
                    threads=1,
                    logger=None,
                )
            except Exception as moviepy_exc:
                logger.error(f"MoviePy stitching error: {moviepy_exc}")
                raise RuntimeError(f"Video composition failed: {moviepy_exc}") from moviepy_exc

        finally:
            if final_clip is not None:
                try:
                    final_clip.close()
                except Exception:
                    pass

            for clip in clip_list:
                try:
                    clip.close()
                except Exception:
                    pass

            for audio_clip in audio_clips:
                try:
                    audio_clip.close()
                except Exception:
                    pass

            for tmp in temp_files:
                try:
                    if tmp.exists():
                        os.remove(str(tmp))
                except Exception:
                    pass

        return output_path
