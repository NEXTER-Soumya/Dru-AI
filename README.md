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
