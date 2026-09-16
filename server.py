from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import dotenv
import logging

# Clean, minimal logging format
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

dotenv.load_dotenv()

os.makedirs("output", exist_ok=True)

app = FastAPI()

cors_origins_raw = os.getenv("CORS_ORIGINS")
if (
    not cors_origins_raw
    or not cors_origins_raw.strip()
    or cors_origins_raw.strip().upper() == "NONE"
):
    origins = ["*"]
else:
    origins = [
        origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()
    ]
    if not origins:
        origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROGRESS_FILE = "output/progress.txt"


def get_saved_progress() -> int:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0


def set_saved_progress(val: int):
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(val))


class Auth(BaseModel):
    password: str


class IReq(Auth):
    amount: int = 1


class SReq(Auth):
    value: int


class PReq(Auth):
    repo: str
    submissions: list[str] | None = None
    sha: str | None = None


@app.get("/")
def get_index():
    return FileResponse("index.html")


@app.post("/progress/increment")
def increment_progress(request: IReq):
    if request.password != os.getenv("PASSWORD", "password"):
        raise HTTPException(401)

    new_progress = get_saved_progress() + request.amount
    set_saved_progress(new_progress)
    return {"progress": new_progress}


@app.post("/progress/set")
def set_progress(request: SReq):
    if request.password != os.getenv("PASSWORD", "password"):
        raise HTTPException(401)

    set_saved_progress(request.value)
    return {"progress": request.value}


@app.get("/progress/get")
def get_progress():
    return {"progress": get_saved_progress()}


def process_images_background(
    repo: str, requested_submissions: list[str] | None, sha: str | None = None
):
    try:
        session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))

        headers = {"User-Agent": "a"}
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        req_url = f"https://api.github.com/repos/{repo}/contents/submissions"
        if sha:
            req_url += f"?ref={sha}"

        res = session.get(req_url, headers=headers)
        if res.status_code == 404:
            logging.info("No submissions folder found.")
            return
        res.raise_for_status()
        all_submissions = [
            item.get("name")
            for item in res.json()
            if item.get("name") and item.get("type") == "dir"
        ]

        submissions_to_process = set()
        if requested_submissions is not None:
            for sub in requested_submissions:
                if sub in all_submissions:
                    submissions_to_process.add(sub)
        else:
            submissions_to_process.update(all_submissions)

        for sub in all_submissions:
            if not os.path.exists(f"output/{sub}.png"):
                submissions_to_process.add(sub)

        if not submissions_to_process:
            logging.info("Everything up to date. No images to process.")
            return

        logging.info(f"Processing {len(submissions_to_process)} submissions...")

        for submission_name in submissions_to_process:
            try:

                def fetch_text(url: str) -> str:
                    try:
                        text_response = session.get(url, headers=headers)
                        text_response.raise_for_status()
                        return text_response.text.strip()
                    except:
                        return ""

                def sanitize_memegen_text(text: str) -> str:
                    text = text.replace("-", "--")
                    text = text.replace("_", "__")
                    text = text.replace(" ", "_")
                    text = text.replace("?", "~q")
                    text = text.replace("&", "~a")
                    text = text.replace("%", "~p")
                    text = text.replace("#", "~h")
                    text = text.replace("/", "~s")
                    text = text.replace("\\", "~b")
                    text = text.replace("<", "~l")
                    text = text.replace(">", "~g")
                    text = text.replace('"', "''")
                    return text

                ref = sha if sha else "main"
                base_url = f"https://raw.githubusercontent.com/{repo}/{ref}/submissions/{submission_name}"
                meme_name = fetch_text(f"{base_url}/meme_name.txt")

                if not meme_name:
                    continue

                captions = []
                idx = 1
                caption = fetch_text(f"{base_url}/caption{idx}.txt")

                while caption:
                    captions.append(sanitize_memegen_text(caption))
                    idx += 1
                    caption = fetch_text(f"{base_url}/caption{idx}.txt")

                captions_path = "/" + "/".join(captions) if captions else ""
                image_url = (
                    f"https://api.memegen.link/images/{meme_name}{captions_path}.png"
                )

                image_response = session.get(image_url, headers={"User-Agent": "a"})
                image_response.raise_for_status()

                tmp_path = f"output/tmp_{submission_name}.png"
                final_path = f"output/{submission_name}.png"
                with open(tmp_path, "wb") as out:
                    out.write(image_response.content)
                os.replace(tmp_path, final_path)

                logging.info(f"✓ Saved image for '{submission_name}'")
            except Exception as e:
                logging.error(f"✗ Failed '{submission_name}': {e}")

        logging.info("Finished background processing.")
    except Exception as e:
        logging.error(f"Background task failed: {e}")


@app.post("/image/set")
def process_image(request: PReq, background_tasks: BackgroundTasks):
    if request.password != os.getenv("PASSWORD", "password"):
        raise HTTPException(401)

    background_tasks.add_task(
        process_images_background, request.repo, request.submissions, request.sha
    )
    return {"status": "processing in background"}


@app.get("/image/get")
def get_images():
    try:
        return [
            f"/image/raw/{filename}"
            for filename in os.listdir("output")
            if filename.endswith((".png", ".jpg"))
        ]
    except Exception:
        return []


@app.get("/image/raw/{filename}")
def get_raw_image(filename: str):
    file_path = f"output/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(404, detail="Image not found")

    return FileResponse(
        file_path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
