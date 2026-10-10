# Meridian web application

For production hosting, follow [DEPLOYMENT.md](DEPLOYMENT.md).

Run `run_web.bat` from the repository root, then open http://127.0.0.1:8000/. The batch file uses the repository virtual environment to serve the FastAPI API and the built React application. After frontend changes, run `npm run build` in `web/frontend`.

The public `/overview` route shows aggregate traffic statistics, camera analysis, charts, and insights from the configured simulated Hyderabad camera network. Registration numbers, evidence, vehicle search, tracking, and ANPR uploads require an operator session. Both the React routes and FastAPI endpoints enforce that boundary.

Operator registration and login accept addresses with a local part ending in `.cop`, such as `sriram.cop@gmail.com`. The backend validates the rule independently of the form.

The video pipeline samples three frames per second, runs the existing YOLOv8 and Tesseract pipeline, and aggregates repeated reads. Detector confidence is the YOLO plate-region score, not a guarantee that OCR text is correct. Operators should compare every result with its evidence crop. The site shows recorded observations; it does not connect to live cameras or infer motion between sightings.
