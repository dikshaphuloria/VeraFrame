# VeraFrame — Truth in Every Frame

> AI-powered video and image authenticity detector. Upload a video, image, or YouTube URL and VeraFrame analyzes frames, transitions, pixel-level manipulation, and metadata to determine if content is AI generated or edited.

![VeraFrame](frontend/app/favicon.ico)

---

## What it detects
 
| Signal | Method | Catches |
|--------|--------|---------|
| AI generation | Gemini Vision per-frame analysis | Sora, Kling, Runway, DALL-E |
| Impossible physics | Gemini transition analysis | Animals teleporting, objects morphing |
| Image manipulation | Error Level Analysis (ELA) | Photoshop, color edits, compositing |
| Editing software | EXIF metadata inspection | Lightroom, Canva, Facetune |
 
### Four verdicts
- 🤖 **AI Generated** — strong AI signals in frames or transitions
- ⚠️ **Possibly AI Generated** — some AI signals but uncertain
- ✂️ **Possibly Edited** — visually real but forensic analysis detected manipulation
- ✅ **Likely Real** — no AI or manipulation signals found
---
 
## How scoring works
 
VeraFrame uses a 4-signal pipeline. Each signal is calculated independently and fed into a unified scorer:
 
```
SIGNAL 1 — Frame analysis
  Each frame gets an AI confidence score from Gemini Vision.
  Scores are spread across ALL frames so 1 suspicious frame
  out of 10 gives ~10% signal, not 100%.
 
SIGNAL 2 — Transition analysis
  Consecutive frame pairs are checked for physically impossible
  changes. Modern AI fools per-frame checks but struggles with
  physics consistency between frames.
  Threshold: 2+ suspicious transitions at >= 85% confidence
  triggers "AI Generated" directly.
 
SIGNAL 3 — ELA (Error Level Analysis)
  Re-saves image at known JPEG quality, compares pixel-by-pixel.
  Edited regions have different compression history and show up
  as bright patches in the diff.
  Score > 25  = likely edited   → "Possibly Edited"
  Score > 55  = heavily edited  → "Possibly Edited" (higher confidence)
  Only runs on original uploaded images — not video frames,
  where re-encoding makes ELA scores meaningless.
 
SIGNAL 4 — Metadata
  Checks EXIF data for editing software (Photoshop, Lightroom etc).
  Binary signal — found or not found.
```
 
**Key design decision:** `is_ai_generated` and `is_edited` are kept as independent signals throughout the pipeline. Editing evidence never upgrades a frame to "AI Generated" — the scorer maps each signal to the correct verdict tier separately.
 
Verdict is derived from signal pattern, not a weighted average:
- Majority AI frames + high confidence → **AI Generated**
- Strong transition signal (2+ at >= 85%) → **AI Generated**
- Some AI frames or suspicious transitions → **Possibly AI Generated**
- No AI signals but ELA / metadata triggered → **Possibly Edited**
- No signals at all → **Likely Real**
### Confidence floors and ceilings
 
Confidence is clamped per verdict so the number never contradicts the label:
 
| Verdict | Floor | Ceiling |
|---------|-------|---------|
| AI Generated | 60% | 100% |
| Possibly AI Generated | 35% | 69.9% |
| Possibly Edited | 30% | 85% |
| Likely Real | 55% | 100% |
 
---
 
## Tech Stack
 
**Backend**
- Python 3.12 + FastAPI
- FFmpeg — smart frame extraction (rate adapts to video duration)
- Google Gemini Vision (`gemini-3.1-pro-preview`) — frame + transition analysis
- Pillow + NumPy — ELA pixel-level manipulation detection
- yt-dlp — YouTube and direct URL video downloading
- Server-Sent Events (SSE) — real-time progress streaming
**Frontend**
- Next.js 14 + TypeScript
- Cabinet Grotesk + Instrument Sans fonts
- Real-time SSE progress bar with step indicators
---
 
## Project Structure
 
```
veraframe/
├── backend/
│   ├── main.py          # FastAPI routes — thin layer only
│   ├── extractor.py     # FFmpeg frame extraction + base64 conversion
│   ├── analyzer.py      # Gemini Vision + ELA + metadata (raw signals only)
│   ├── scorer.py        # All verdict + confidence decisions
│   ├── models.py        # Shared constants (file size limits etc)
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx
    │   ├── globals.css
    │   ├── layout.tsx
    │   ├── favicon.ico
    │   ├── components/
    │   │   ├── DropZone.tsx    # File upload + URL input
    │   │   ├── ProgressBar.tsx # SSE step-by-step progress
    │   │   └── Results.tsx     # Verdict card + proof frames
    │   └── lib/
    │       └── api.ts          # TypeScript API client
    └── package.json
```
 
**Clean separation of concerns:**
- `analyzer.py` — collects raw signals only, makes no verdict decisions
- `scorer.py` — owns all threshold decisions, confidence ranges, and verdict logic
- `is_ai_generated` and `is_edited` are independent flags — editing evidence never pollutes AI generation scoring
---
 
## Getting Started
 
### Prerequisites
- Python 3.9+
- Node.js 18+
- FFmpeg
- Google API key (Gemini)


### Install FFmpeg (Mac)
```bash
brew install ffmpeg
```
 
### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
 
Create `.env` file:
```
GOOGLE_API_KEY=your_google_api_key_here
```
 
Start the server:
```bash
uvicorn main:app --reload
```
 
Backend runs on `http://localhost:8000`
 
### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
 
Frontend runs on `http://localhost:3000`
 
---
 
## API Endpoints
 
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Check API status + key loaded |
| `POST` | `/analyze-stream` | Upload video file — SSE streaming |
| `POST` | `/analyze-url-stream` | YouTube or direct video URL — SSE streaming |
| `POST` | `/analyze-image` | Single image or screenshot |
 
### Example — analyze a video file
```bash
curl -X POST http://localhost:8000/analyze-stream \
  -F "file=@video.mp4"
```
 
### Example — analyze a YouTube URL
```bash
curl -X POST http://localhost:8000/analyze-url-stream \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=..."}'
```
 
### Response shape
```json
{
  "verdict": "AI Generated",
  "overall_confidence": 87.5,
  "ai_frames": 3,
  "total_frames": 5,
  "artifacts_found": [
    "unnatural skin texture",
    "physically impossible light source"
  ],
  "proof_frames": [...],
  "transitions": {
    "total_analyzed": 4,
    "suspicious_count": 2,
    "results": [...]
  }
}
```
 
---
 
## Limitations
 
- **Invisible watermarks** (SynthID) require a dedicated SDK — not detectable via vision prompts
- **Modern AI generators** (Sora, Kling, Veo 3) are harder to detect than older models
- **ELA on video frames** is not run — re-encoding by FFmpeg makes scores meaningless; ELA only runs on directly uploaded images
- **ELA on PNG** is less reliable — lossless to lossy conversion inflates scores; borderline scores around 25 should be treated with caution
- **Non-human subjects** (animals, objects, landscapes) are harder to analyze than human faces
- **Subtle color edits** sit at the edge of ELA detection — scores around 25 are borderline
- Max file size: **100MB** · Max video length: **10 minutes**
---
 
## Known edge cases
 
| Case | Behavior |
|------|----------|
| Real video with many cuts | Transition threshold set high (85% confidence + 2 triggers) to reduce false positives |
| Low quality / compressed video | Correctly identified as real — compression artifacts ≠ AI artifacts |
| PNG images | ELA scores may be inflated — treat borderline results with caution |
| Non-human AI images (animals, landscapes) | Harder to detect — transition analysis becomes the primary signal |
| AI video with no humans | Transition analysis is primary signal |
| Gemini API failure | Falls back to neutral result (treated as real) to avoid false positives — pipeline continues |
 
---
 
## Roadmap
 
- [ ] Deploy to Vercel + Railway
- [ ] Add result history with database
- [ ] Shareable result links
- [ ] Browser extension for YouTube/TikTok
- [ ] SynthID SDK integration when publicly available
- [ ] Batch analysis mode
---
 
## License
 
MIT
 
---
 
Built using FastAPI, Next.js, and Google Gemini