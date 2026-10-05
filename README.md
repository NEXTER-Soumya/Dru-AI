# Dru AI

Dru AI is a Flask cattle-breed recognition app. Signed-in users can submit an
image, view the model's top breed prediction and confidence, and revisit or
delete past identifications from their Library. Dashboard Settings lets users
update their display name, choose a profile icon, select the default or one of
four accent palettes in light or dark mode, and permanently delete their
account and saved scan data.

## Requirements

- Python 3.10 or newer
- MongoDB
- Node.js and npm (for building the Vercel frontend)

Set `MONGO_URI` in `.env` to your MongoDB connection string. For deployments,
also set `FLASK_SECRET_KEY` to a stable, private random value. For local
development, the app creates a private fallback key under the ignored
`instance/` directory.

## Run

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
node build-frontend.mjs
.\venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000`. Sign up or sign in, then use **Identify** to
upload a JPEG, PNG, or WebP image up to 10 MB and 20 megapixels.

## Model and saved data

Breed inference runs in the user's browser with ONNX Runtime Web and the
exported `static/models/cattle_breed_model.onnx` model. The model uses the
training notebook's ResNet-18 architecture, 224 × 224 RGB resize, ImageNet
normalization, and the 50 ordered labels in
`static/models/cattle_breed_classes.json`. The first prediction downloads the
roughly 45 MB model and 14 MB WASM runtime to the browser; inference runs
locally after download.
Flask receives the image and browser-produced label/confidence only to validate
and save the result. Because client predictions can be modified, they are not
server-verified.

To export an updated model from the trained checkpoint, install the optional
export requirements and run the exporter:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-model-export.txt
.\venv\Scripts\python.exe tools\export_onnx.py
node build-frontend.mjs
```

Identification records are stored in the `scans` collection and uploaded image
bytes in the `scan_images` GridFS bucket in the `dru_ai_database` database.
Each record is associated with the signed-in user's MongoDB ID; Library and
image endpoints enforce that ownership. Breed overview, characteristics, care
guidance, and similar-breed information are loaded from
`models/indian_cattle_breeds_api.json` by matching the model's predicted breed
against each entry's `name` in the top-level `breeds` object. Breed names are
matched case-insensitively, with underscores treated as spaces. Additional
overview facts such as adult weight, lifespan, milk production, daily food
intake, primary use, and identification features come from
`models/indian_cattle_info_api.json`, matched by `model_label`.

## Deploy frontend on Vercel and backend on Render

The UI uses Flask templates for local development. `build-frontend.mjs` turns
those templates into static pages and copies the existing assets into the
dedicated `frontend/` directory. Vercel serves that directory as a static-only
project, while the Flask API and MongoDB connection stay on Render. The
browser downloads the ONNX model and performs inference locally. Vercel
rewrites `/api/*` and `/logout` to Render, so browser requests and session
cookies remain same-origin; no CORS setup is needed.

### Deploy the backend to Render

1. Create a **Web Service** from this GitHub repository. Use the repository
   root as the service's root directory and select Python.
2. Set the build command to `pip install -r requirements.txt` and the start
   command to `gunicorn --workers 1 --threads 1 app:app`.
3. Add these environment variables in Render:
   - `MONGO_URI`: the MongoDB Atlas connection URI.
   - `FLASK_SECRET_KEY`: a long, random, private secret that remains stable
     between deploys.
   - `FLASK_ENV`: `production` (enables secure session cookies).
4. Configure the MongoDB Atlas network access list so Render can connect.
   Prefer a restricted egress-IP allowlist where your Render plan supports it.
5. Wait for the service to deploy, then note its URL, such as
   `https://dru-ai-api.onrender.com`.

The service does not need PyTorch or the trained `.pth` checkpoint. It needs
the breed information JSON datasets and
`static/models/cattle_breed_classes.json` to validate browser-submitted labels.
The frontend loads only the WASM CPU runtime artifacts needed for inference.

### Deploy the frontend to Vercel

1. In the Vercel project settings, set **Root Directory** to `frontend`.
   Leave the Build Command and Output Directory overrides empty. The
   `frontend/` directory contains only static site files and its Vercel
   rewrite configuration, so Vercel will not package the Python app or
   PyTorch dependencies.
2. In the root `vercel.json`, set the two rewrite destinations to your Render
   service hostname (for example, `dru-ai-api.onrender.com`), then run
   `npm ci` and `node build-frontend.mjs` from the repository root to copy the
   updated config, ONNX Runtime Web files, and current templates/assets into
   `frontend/`.
3. Commit and push the root `vercel.json` and generated `frontend/` changes.
4. Import the same repository in Vercel, choosing `frontend` as the Root
   Directory if prompted.
5. Deploy, then open the Vercel URL and test sign-up, sign-in, image
   identification, Library, and logout. The first identification downloads
   the ONNX model to the user's browser.

Render should continue using the repository root as its Root Directory. Free
Render services may spin down when idle, so the first API request after a
quiet period can take longer.
