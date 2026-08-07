"""RenderCV PDF rendering for Tailored CV YAML."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class PdfRenderError(Exception):
    """Raised when Tailored YAML cannot be rendered to PDF."""


class RenderCvPdfRenderer:
    """Render Tailored CV YAML to PDF via the RenderCV CLI when available."""

    def render_pdf(self, tailored_yaml: str) -> bytes:
        """Return PDF bytes, or raise PdfRenderError on failure."""
        stripped = _strip_assistant_metadata(tailored_yaml)
        rendercv = shutil.which("rendercv")
        if rendercv is None:
            raise PdfRenderError("rendercv CLI not found on PATH")
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            yaml_path = tmp / "tailored.yaml"
            yaml_path.write_text(stripped, encoding="utf-8")
            try:
                completed = subprocess.run(
                    [rendercv, "render", str(yaml_path), "--output-folder", str(tmp / "out")],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PdfRenderError(str(exc)) from exc
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "").strip()
                raise PdfRenderError(detail or "rendercv failed")
            pdfs = list((tmp / "out").rglob("*.pdf"))
            if not pdfs:
                raise PdfRenderError("rendercv produced no PDF")
            return pdfs[0].read_bytes()


def _strip_assistant_metadata(yaml_text: str) -> str:
    """Drop optional assistant.* metadata so it is not shown on the PDF."""
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return yaml_text
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return yaml_text
    if not isinstance(data, dict):
        return yaml_text
    data.pop("assistant", None)
    return yaml.safe_dump(data, sort_keys=False)
