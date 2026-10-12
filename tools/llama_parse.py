"""
Thin wrapper around LlamaCloud's parsing API — upload a PDF/image/docx,
poll the job, pull back the extracted markdown.

Deliberately uses urllib (no SDK dependency) to match the rest of the
project's style. Multipart handling is manual.
"""
import json
import time
import urllib.error
import urllib.request
import uuid

LLAMA_PARSE_URL = "https://api.cloud.llamaindex.ai/api/parsing/upload"
LLAMA_JOB_URL = "https://api.cloud.llamaindex.ai/api/parsing/job"


class LlamaParseError(RuntimeError):
    pass


def _multipart_body(file_bytes: bytes, filename: str) -> tuple[bytes, str]:
    boundary = f"----boundary{uuid.uuid4().hex}"
    content_type = f"multipart/form-data; boundary={boundary}"
    lines = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode(),
        b"Content-Type: application/octet-stream",
        b"",
        file_bytes,
        f"--{boundary}--".encode(),
        b"",
    ]
    return b"\r\n".join(lines), content_type


def _upload(file_bytes: bytes, filename: str, api_key: str) -> str:
    body, content_type = _multipart_body(file_bytes, filename)
    req = urllib.request.Request(LLAMA_PARSE_URL, data=body, method="POST")
    req.add_header("Content-Type", content_type)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    job_id = payload.get("id")
    if not job_id:
        raise LlamaParseError(f"No job id in upload response: {payload}")
    return job_id


def _poll_until_done(job_id: str, api_key: str, max_wait_s: int = 90) -> None:
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        req = urllib.request.Request(f"{LLAMA_JOB_URL}/{job_id}")
        req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = json.loads(resp.read().decode("utf-8")).get("status", "").upper()
        if status == "SUCCESS":
            return
        if status in {"ERROR", "CANCELED", "PARTIAL_SUCCESS"}:
            raise LlamaParseError(f"LlamaParse job {job_id} finished with status {status}")
        time.sleep(2)
    raise LlamaParseError(f"LlamaParse job {job_id} did not finish in {max_wait_s}s")


def _fetch_markdown(job_id: str, api_key: str) -> str:
    req = urllib.request.Request(f"{LLAMA_JOB_URL}/{job_id}/result/markdown")
    req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("markdown", "")


def extract_document_markdown(file_bytes: bytes, filename: str, api_key: str) -> str:
    """
    Blocks until LlamaParse finishes extracting the document, then returns
    the markdown. Raises LlamaParseError on failure — callers should catch
    and surface a technical-failure state instead of letting a 500 bubble
    up to the UI.
    """
    if not api_key:
        raise LlamaParseError("LLAMA_API_KEY not configured")
    job_id = _upload(file_bytes, filename, api_key)
    _poll_until_done(job_id, api_key)
    return _fetch_markdown(job_id, api_key)
