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
- `models/cattle_breed_model.pth`

Set `MONGO_URI` in `.env` to your MongoDB connection string. For deployments,
also set `FLASK_SECRET_KEY` to a stable, private random value. For local
development, the app creates a private fallback key under the ignored
`instance/` directory. Help & Support provides direct email links to
`gmitprojectid@gmail.com` for queries and product feedback.

## Run

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000`. Sign up or sign in, then use **Identify** to
upload a JPEG, PNG, or WebP image up to 10 MB.

## Model and saved data

The inference adapter uses the training notebook's ResNet-18 architecture,
224 × 224 RGB resize, and ImageNet normalization. The checkpoint must contain
`model_state` and the 50-element `classes` list saved by the notebook. The
class list is used to map the highest-probability output back to its breed.

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
project, while the Flask API, MongoDB connection, and PyTorch model stay on
Render. Vercel rewrites `/api/*` and `/logout` to Render, so browser requests
and session cookies remain same-origin; no CORS setup is needed.

### Deploy the backend to Render

1. Create a **Web Service** from this GitHub repository. Use the repository
   root as the service's root directory and select Python.
2. Set the build command to `pip install -r requirements.txt` and the start
   command to `gunicorn app:app`.
3. Add these environment variables in Render:
   - `MONGO_URI`: the MongoDB Atlas connection URI.
   - `FLASK_SECRET_KEY`: a long, random, private secret that remains stable
     between deploys.
   - `FLASK_ENV`: `production` (enables secure session cookies).
4. Configure the MongoDB Atlas network access list so Render can connect.
   Prefer a restricted egress-IP allowlist where your Render plan supports it.
5. Wait for the service to deploy, then note its URL, such as
   `https://dru-ai-api.onrender.com`.

The service must include `models/cattle_breed_model.pth` and both JSON
datasets from this repository. The PyTorch model can require substantial
memory during startup and inference; choose a Render instance with enough
memory for the model.

### Deploy the frontend to Vercel

1. In the Vercel project settings, set **Root Directory** to `frontend`.
   Leave the Build Command and Output Directory overrides empty. The
   `frontend/` directory contains only static site files and its Vercel
   rewrite configuration, so Vercel will not package the Python app or
   PyTorch dependencies.
2. In the root `vercel.json`, set the two rewrite destinations to your Render
   service hostname (for example, `dru-ai-api.onrender.com`), then run
   `node build-frontend.mjs` from the repository root to copy the updated
   config and current templates/assets into `frontend/`.
3. Commit and push the root `vercel.json` and generated `frontend/` changes.
4. Import the same repository in Vercel, choosing `frontend` as the Root
   Directory if prompted.
5. Deploy, then open the Vercel URL and test sign-up, sign-in, image
   identification, Library, and logout.

Render should continue using the repository root as its Root Directory. Free
Render services may spin down when idle, so the first API request after a
quiet period can take longer.
