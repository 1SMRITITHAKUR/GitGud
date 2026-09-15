from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import requests
import dotenv

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

progress = 0


class Auth(BaseModel):
    password: str


class IReq(Auth):
    amount: int = 1


class SReq(Auth):
    value: int


class PReq(Auth):
    repo: str


@app.get("/")
def get_index():
    return FileResponse("index.html")


@app.post("/progress/increment")
def increment_progress(request: IReq):
    if request.password != os.getenv("PASSWORD", "password"):
        raise HTTPException(401)

    global progress
    progress += request.amount
    return {"progress": progress}


@app.post("/progress/set")
def set_progress(request: SReq):
    if request.password != os.getenv("PASSWORD", "password"):
        raise HTTPException(401)

    global progress
    progress = request.value
    return {"progress": progress}


@app.get("/progress/get")
def get_progress():
    global progress
    return {"progress": progress}


@app.post("/image/set")
def process_image(request: PReq):
    if request.password != os.getenv("PASSWORD", "password"):
        raise HTTPException(401)

    try:
        req_url = f"https://api.github.com/repos/{request.repo}/contents/submissions"
        res = requests.get(req_url, headers={"User-Agent": "a"})
        res.raise_for_status()
        submissions_data = res.json()

        errors: list[Exception] = []
        for item in submissions_data:
            try:
                submission_name = item.get("name")
                if not submission_name:
                    continue

                def fetch_text(url: str) -> str:
                    try:
                        text_response = requests.get(url, headers={"User-Agent": "a"})
                        text_response.raise_for_status()
                        return text_response.text.strip()
                    except:
                        return ""

                base_url = f"https://raw.githubusercontent.com/{request.repo}/main/submissions/{submission_name}"
                meme_name = fetch_text(f"{base_url}/meme_name.txt")

                if not meme_name:
                    continue

                captions = []
                idx = 1
                caption = fetch_text(f"{base_url}/caption{idx}.txt")

                while caption:
                    captions.append(caption.replace(" ", "_"))
                    idx += 1
                    caption = fetch_text(f"{base_url}/caption{idx}.txt")

                captions_path = "/" + "/".join(captions) if captions else ""
                image_url = (
                    f"https://api.memegen.link/images/{meme_name}{captions_path}.png"
                )

                image_response = requests.get(image_url, headers={"User-Agent": "a"})
                image_response.raise_for_status()
                with open(f"output/{submission_name}.png", "wb") as out:
                    out.write(image_response.content)
            except Exception as e:
                errors.append(e)

        for e in errors:
            e = str(e)

        return {"status": "ok", "errors": [str(e) for e in errors]}
    except Exception as e:
        return {"error": str(e)}


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

    return FileResponse(file_path)
