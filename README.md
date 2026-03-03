# sustainable-garden

Sustainable Garden Designer MVP with:
- Expo/React frontend (`EcoScape/`)
- Flask backend API (`backend/`)

## 1) Run Flask backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python backend/app.py
```

Backend runs on `http://127.0.0.1:5001`.

## 2) Run frontend (Expo)

```bash
cd EcoScape
npm install
npm run web
```

Optional API override:

```bash
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:5001 npm run web
```

## Flask API endpoints

- `GET /api/health`
- `GET /api/config`
- `GET /api/recommendations?climateId=irvine`
- `GET /api/recommendations/zipcode?zipCode=94102`
- `GET /api/recommendations/zipcode?zipCode=94102&plantType=tree`
- `POST /api/score`
