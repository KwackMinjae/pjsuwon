from flask import Flask, jsonify, request, abort, send_from_directory, render_template
from werkzeug.utils import secure_filename
from pathlib import Path
import os, uuid, shutil, threading, queue, time

from db import Base, engine, get_db
from models import Job

# 🔹 CORS 추가
from flask_cors import CORS

# 🔹 외부 AI 클라이언트
from ai_client import call_ai_server, AIClientError

app = Flask(__name__)
CORS(app)  # 🔹 모든 출처 허용 (테스트/프런트 연동 편의용)

# --- DB 테이블 생성 (앱 시작 시 1회) ---
Base.metadata.create_all(bind=engine)

# --- 기본 라우트 ---
@app.get("/healthz")
def healthz():
    return jsonify(ok=True, service="face-hair-api")

@app.get("/api/hairstyles")
def hairstyles():
    return jsonify([
        {"id": "bob", "name": "단발", "description": "기본 단발"},
        {"id": "perm", "name": "펌", "description": "베이직 펌"}
    ])

# --- 파일 저장 경로/유틸 ---
STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", "./data"))
UPLOADS = STORAGE_ROOT / "uploads"
RESULTS = STORAGE_ROOT / "results"
for p in (UPLOADS, RESULTS):
    p.mkdir(parents=True, exist_ok=True)

ALLOWED = {"png", "jpg", "jpeg", "webp"}
def allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED

# --- 인메모리 큐 + 워커 ---
job_queue = queue.Queue()

def hair_process(src_path: Path, dst_path: Path):
    """
    1순위: 외부 AI 서버 호출 (환경변수 AI_API_BASE, AI_API_KEY 사용)
    실패하면 2순위: 더미 복사로 폴백
    """
    api_base = os.getenv("AI_API_BASE", "http://localhost:9000")  # 예: http://<친구서버>:9000
    api_key  = os.getenv("AI_API_KEY")  # 필요 없으면 비워둠

    try:
        call_ai_server(src_path=src_path, dst_path=dst_path,
                       style_id=None, api_base=api_base, api_key=api_key, timeout=300)
    except AIClientError:
        shutil.copyfile(src_path, dst_path)

def worker_loop():
    from db import get_db
    from models import Job

    while True:
        job_id = job_queue.get()
        if job_id is None:
            break
        db = next(get_db())
        job = db.get(Job, job_id)
        if not job:
            continue
        try:
            src = Path(job.src_path)
            dst = RESULTS / f"{job.id}_result{src.suffix}"
            hair_process(src, dst)
            job.result_path = str(dst)
            job.status = "DONE"
            db.commit()
        except Exception as e:
            job.status = "FAILED"
            job.error = str(e)
            db.commit()
        finally:
            job_queue.task_done()

# --- 업로드 API (POST) ---
@app.post("/api/upload")
def upload():
    if "file" not in request.files:
        abort(400, "file 필드가 없습니다")
    f = request.files["file"]
    if f.filename == "":
        abort(400, "파일명이 비었습니다")
    if not allowed(f.filename):
        abort(400, "허용 확장자: png/jpg/jpeg/webp")

    ext = f.filename.rsplit(".", 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    saved_path = UPLOADS / secure_filename(fname)
    f.save(saved_path)

    db = next(get_db())
    job = Job(status="PENDING", src_path=str(saved_path))
    db.add(job)
    db.commit()
    db.refresh(job)

    # 🔹 큐에 작업 넣기
    job_queue.put(job.id)

    return jsonify(job_id=job.id, status=job.status)

# --- 작업 조회 API (GET) ---
@app.get("/api/jobs/<int:job_id>")
def get_job(job_id: int):
    db = next(get_db())
    job = db.get(Job, job_id)
    if not job:
        abort(404, "작업을 찾을 수 없습니다")

    result_url = None
    if job.result_path:
        result_url = f"/files/results/{Path(job.result_path).name}"
    return jsonify(
        job_id=job.id,
        status=job.status,
        result_url=result_url,
        error=job.error
    )

# --- 결과 파일 서빙 ---
@app.get("/files/results/<path:filename>")
def serve_result(filename: str):
    return send_from_directory(RESULTS, filename, as_attachment=False)

# --- 테스트용 프론트 페이지 라우트 ---
@app.get("/")
def home():
    return render_template("index.html")

# --- 메인 실행 ---
if __name__ == "__main__":
    # 🔹 워커 스레드 시작
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()

    app.run(debug=True)
