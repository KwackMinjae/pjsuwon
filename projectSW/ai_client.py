# ai_client.py
from pathlib import Path
import requests

class AIClientError(RuntimeError):
    pass

def call_ai_server(
    src_path: Path,
    dst_path: Path,
    style_id: str | None = None,
    api_base: str = "http://localhost:9000",
    api_key: str | None = None,
    timeout: int = 120,
):
    """
    외부 AI 서버에 이미지를 보내 합성 결과를 받아서 dst_path에 저장.
    서버는 POST {api_base}/infer 엔드포인트에
    - files: {"file": (filename, binary, mime)}
    - data:  {"style": "<style_id>"} (옵션)
    를 받는다고 가정.

    실패 시 AIClientError 예외를 던짐.
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    if not src_path.exists():
        raise AIClientError(f"input not found: {src_path}")

    url = f"{api_base.rstrip('/')}/infer"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 간단 MIME 추정
    ext = src_path.suffix.lower()
    mime = "image/jpeg"
    if ext in [".png"]: mime = "image/png"
    elif ext in [".webp"]: mime = "image/webp"

    files = {"file": (src_path.name, open(src_path, "rb"), mime)}
    data = {}
    if style_id:
        data["style"] = style_id

    try:
        with requests.post(url, files=files, data=data, headers=headers, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dst_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
    except requests.Timeout as e:
        raise AIClientError(f"AI server timeout: {url}") from e
    except requests.HTTPError as e:
        text = ""
        try:
            text = e.response.text[:300]
        except Exception:
            pass
        raise AIClientError(f"AI server error {e.response.status_code}: {text}") from e
    except requests.RequestException as e:
        raise AIClientError(f"AI server request failed: {e}") from e
    finally:
        try:
            files["file"][1].close()
        except Exception:
            pass
