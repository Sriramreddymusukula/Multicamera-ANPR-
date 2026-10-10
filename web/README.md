# Meridian web application

For production hosting, follow [DEPLOYMENT.md](DEPLOYMENT.md).

Run `run_web.bat` from the repository root, then open http://127.0.0.1:8000/. The batch file uses the repository virtual environment to serve the FastAPI API and the built React application. After frontend changes, run `npm run build` in `web/frontend`.

The public `/overview` route shows aggregate traffic statistics, camera analysis, charts, and insights from the configured simulated Hyderabad camera network. Registration numbers, evidence, vehicle search, tracking, and ANPR uploads require an operator session. Both the React routes and FastAPI endpoints enforce that boundary.

Operator registration and login accept addresses with a local part ending in `.cop`, such as `sriram.cop@gmail.com`. The backend validates the rule independently of the form.

The console accepts up to 10 images per batch or one video. Video processing samples three frames per second and joins compatible readings only when their observed positions and times are close. Low detector/OCR scores and conflicting video readings enter the authenticated `/reviews` queue unless Gemini returns the same normalized registration as the local model. In that case the observation is saved automatically, with both readings and original scores retained in the review ledger. Other uncertain observations do not enter vehicle history until an operator confirms a registration. Reviewers can reject a false detection. Bell alerts are enabled by default for new pending observations; browsers may require an initial click or key press before audio can play.

`ANPR_GEMINI_API_KEY` enables Gemini as a second reader for uncertain cropped plates. On Windows, the server can also read a key from `%LOCALAPPDATA%\Meridian\gemini.key`; on other systems it can use an ignored `web/backend/.gemini-key` file. An existing `ANPR_GOOGLE_VISION_API_KEY` remains supported as a fallback when Gemini is not configured. Keys remain server-side. Agreement with Gemini accepts the local reading; a disagreement or unreadable second result remains pending. No key is required for the local YOLOv8/Tesseract pipeline. Detector confidence describes the plate-region detector; OCR confidence and video frame agreement are separate signals and are not calibrated probabilities of a correct identity.

For new pending reviews, Gemini also suggests a visible vehicle colour and body style from the saved frame when a plate bounding box is available. The plate region is masked before this frame is sent. The review screen shows the observed camera, location, time, source, video frame count, alternate reads and nearby registration candidates. These are review aids, not an automatic vehicle identity or verified route. An operator can record a colour observation with a decision; it stays in the private review ledger and is not used for cross-camera matching. Reviews created before this feature may have no appearance suggestion.

The site shows recorded observations from uploaded media and a simulated camera network. It does not connect to live cameras or infer motion between sightings.
