# 🚦 City-Wide AI Traffic Engine

### Multi-Camera ANPR • Vehicle Identity Association • Route Reconstruction • Urban Traffic Analytics

A Python-based **AI-powered Automatic Number Plate Recognition (ANPR)** prototype designed to demonstrate how vehicle observations from multiple camera locations can be combined to build a city-wide traffic intelligence system.

The system uses **YOLOv8** for license plate detection and **Tesseract OCR** for recognizing vehicle registration numbers. Detected vehicles can then be associated across simulated camera locations to reconstruct observed routes and generate session-based traffic analytics.

> **Current Status:** Prototype
> **Input:** Uploaded vehicle images
> **Interface:** Desktop GUI
> **Future Direction:** Real-time CCTV/RTSP and city-wide traffic intelligence

---

## 📌 Project Overview

Traditional ANPR systems generally focus on detecting and recognizing a license plate from a single image or camera.

This project extends that concept toward a **multi-camera traffic intelligence platform**.

The workflow is:

```text
Vehicle Image
      ↓
YOLOv8 License Plate Detection
      ↓
License Plate Cropping
      ↓
Image Preprocessing
      ↓
Tesseract OCR
      ↓
Vehicle Registration Number
      ↓
Camera / Location Association
      ↓
Same-Vehicle Association
      ↓
Route Reconstruction
      ↓
Urban Traffic Analytics
```

The current prototype uses uploaded images instead of live CCTV streams. Each uploaded image is assigned to a simulated camera/location, allowing the system to demonstrate how the same vehicle can be identified across multiple locations.

---

# ✨ Key Features

## 🔍 Automatic Number Plate Recognition

The system performs an end-to-end ANPR pipeline:

* Detects license plates using a trained **YOLOv8 model**
* Extracts the detected plate region
* Crops the license plate
* Preprocesses the cropped image
* Uses **Tesseract OCR** to recognize the plate number
* Cleans the OCR output into an alphanumeric vehicle identifier
* Supports multiple detected plates within an image

---

## 📷 Multi-Camera Simulation

The prototype simulates multiple cameras positioned at different locations.

| Camera | Location          |
| ------ | ----------------- |
| CAM-01 | Suchitra Junction |
| CAM-02 | Kukatpally        |
| CAM-03 | JNTU Road         |
| CAM-04 | Miyapur           |

This allows a vehicle detected at one location to be associated with another observation later in the session.

---

# 🚗 Multi-Camera Vehicle Association

The recognized license plate number acts as the primary vehicle identity.

For example:

```text
TG257602
```

may be detected at:

```text
CAM-01 → Suchitra Junction
```

and later:

```text
CAM-03 → JNTU Road
```

The system can therefore reconstruct the observed route:

```text
Suchitra Junction → JNTU Road
```

This demonstrates the basic concept of **city-wide vehicle movement analysis**.

---

# 📊 Urban Traffic Analytics

The dashboard provides session-based analytics including:

* Total vehicle observations
* Unique vehicles
* Active cameras
* Multi-camera vehicles
* Camera-wise activity
* Vehicle observation frequency
* Multi-camera routes
* Traffic activity level

### Traffic Activity

The current prototype uses ANPR observation counts as a demonstration activity indicator:

| Observations | Activity |
| -----------: | -------- |
|            0 | No Data  |
|          1–2 | Low      |
|          3–5 | Moderate |
|           6+ | High     |

> ⚠️ This metric is **not a real-time road congestion measurement**. It is calculated from ANPR observations within the current image-upload session.

---

# 🖥️ Interactive Dashboard

The desktop GUI provides:

* 📷 Camera/location selection
* 📁 Single-image upload
* 📁 Multiple-image upload
* 🤖 AI detection
* 🖼️ Image preview
* 🔎 Detection results
* 🚗 Vehicle association
* 🛣️ Multi-camera trajectory display
* 📊 Urban traffic analytics
* 🕒 Detection event history
* 📂 Output folder access
* 🔄 Session data reset

---

# 🧠 Technology Stack

| Technology               | Purpose                                  |
| ------------------------ | ---------------------------------------- |
| **Python**               | Core programming language                |
| **YOLOv8 / Ultralytics** | License plate detection                  |
| **OpenCV**               | Image processing and preprocessing       |
| **Tesseract OCR**        | License plate text recognition           |
| **Pytesseract**          | Python interface for Tesseract           |
| **CustomTkinter**        | Desktop graphical interface              |
| **Pillow**               | Image loading and preview                |
| **Pandas**               | Detection and history data handling      |
| **CSV**                  | Lightweight persistent detection storage |

---

# 🏗️ System Architecture

```text
                    ┌──────────────────────┐
                    │      User / GUI      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Image Upload      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       YOLOv8         │
                    │  Plate Detection     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Image Preprocessing  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Tesseract OCR     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Plate / Vehicle ID  │
                    └───────┬───────┬──────┘
                            │       │
                  ┌─────────┘       └─────────┐
                  ▼                           ▼
        ┌──────────────────┐       ┌──────────────────┐
        │  Camera Event    │       │ Vehicle History  │
        └────────┬─────────┘       └────────┬─────────┘
                 │                          │
                 └──────────┬───────────────┘
                            ▼
                 ┌──────────────────────┐
                 │ Multi-Camera         │
                 │ Association          │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Route Reconstruction │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │ Traffic Analytics    │
                 └──────────────────────┘
```

---

# 📂 Project Structure

```text
SIH ANPR/
│
├── models/
│   └── best.pt
│
├── output/
│   ├── cropped_plate_*.jpg
│   └── preprocessed_plate_*.jpg
│
├── detector.py
├── gui.py
├── database.py
├── history.py
├── requirements.txt
├── vehicle_database.csv
└── README.md
```

### File Responsibilities

**`gui.py`**

Main desktop dashboard responsible for:

* Image upload
* Camera selection
* Detection
* Vehicle association
* Route visualization
* Analytics
* User interaction

**`detector.py`**

Responsible for the AI detection pipeline:

* YOLOv8 inference
* License plate bounding boxes
* Plate cropping
* Image preprocessing
* OCR
* OCR text cleaning

**`database.py`**

Handles persistent detection records using CSV storage.

**`history.py`**

Handles:

* Detection history
* Vehicle history
* Camera history
* Unique vehicle statistics
* Vehicle trajectories
* Analytics

**`models/best.pt`**

Trained YOLOv8 license plate detection model.

**`output/`**

Stores generated:

* Cropped license plates
* Preprocessed license plate images

---

# ⚙️ Installation

## 1. Install Python

Install **Python 3.12.x** on Windows.

Verify:

```powershell
python --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

---

## 3. Create a Virtual Environment

```powershell
python -m venv venv
```

Verify:

```powershell
.\venv\Scripts\python.exe --version
```

---

## 4. Install Dependencies

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

# 🔤 Install Tesseract OCR

Tesseract is a separate application and must be installed independently from the Python package.

The current project expects Tesseract at:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Verify the installation:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

Then verify the Python interface:

```powershell
.\venv\Scripts\python.exe -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

> Installing `pytesseract` alone is **not sufficient**. The Tesseract OCR application itself must also be installed.

---

# ▶️ Running the Application

From the project directory:

```powershell
.\venv\Scripts\python.exe gui.py
```

The desktop dashboard should launch.

---

# 🧪 How to Use

### Step 1 — Select a Camera

Choose a simulated camera/location from the dropdown.

Example:

```text
CAM-01 — Suchitra Junction
```

### Step 2 — Upload an Image

Choose:

* **Upload Image** for one image
* **Upload Multiple Images** for multiple images

For better OCR results, use images with clearly visible license plates.

### Step 3 — Run AI Detection

The system performs:

```text
Image
 ↓
YOLOv8
 ↓
Plate Detection
 ↓
Crop
 ↓
OpenCV Preprocessing
 ↓
Tesseract OCR
 ↓
Registration Number
```

### Step 4 — Test Multi-Camera Association

Process the same vehicle at different simulated cameras.

Example:

```text
Image 1
TG257602
CAM-01 — Suchitra Junction

        ↓

Image 2
TG257602
CAM-03 — JNTU Road
```

Result:

```text
Route:
Suchitra Junction → JNTU Road
```

---

# 🖼️ Recommended Input Images

For better detection and OCR performance, use:

* Clear vehicle photographs
* Front or rear vehicle views
* Clearly visible license plates
* Reasonable lighting
* Sufficient plate resolution
* Minimal motion blur

The current image-based system is primarily intended to demonstrate **ANPR, vehicle identity association and route reconstruction**.

---

# 🔬 How the AI Pipeline Works

## YOLOv8 — Detection

YOLOv8 is responsible for finding the **license plate location** in the vehicle image.

It produces a bounding box around the detected plate.

```text
Vehicle Image
      ↓
     YOLO
      ↓
┌─────────────────┐
│ License Plate   │
│   TG257602      │
└─────────────────┘
```

---

## OpenCV — Image Processing

Once the plate is detected, OpenCV is used to process the cropped region.

The purpose is to produce a cleaner image for OCR.

```text
Detected Plate
      ↓
Crop
      ↓
Preprocessing
      ↓
Improved OCR Input
```

---

## Tesseract OCR — Recognition

Tesseract reads the processed license plate image and converts the visual characters into text.

```text
Plate Image
    ↓
Tesseract OCR
    ↓
"TG257602"
```

The result is then cleaned to create the vehicle registration identifier used by the rest of the system.

---

# 💾 Data Storage

The prototype uses a **CSV-based lightweight database** to maintain detection records.

Example data concept:

```text
Vehicle ID
Camera ID
Location
Detection
Observation
```

This information enables the application to calculate vehicle history, camera activity and multi-camera movement.

For a production deployment, the CSV storage can be replaced by a centralized database.

---

# 🚗 Vehicle Journey Reconstruction

A major feature of the project is connecting observations of the same vehicle.

For example:

```text
TG257602

CAM-01
Suchitra Junction
      ↓
CAM-03
JNTU Road
      ↓
CAM-04
Miyapur
```

The system can use the sequence of camera observations to reconstruct the **observed vehicle route**.

This forms the foundation for larger-scale urban mobility analysis.

---

# 📈 Analytics Explained

### Total Observations

Number of valid ANPR observations in the current session.

### Unique Vehicles

Number of distinct license plate numbers detected.

### Active Cameras

Number of camera IDs that generated observations.

### Multi-Camera Vehicles

Vehicles observed at more than one camera.

### Camera Activity

Number of ANPR observations generated by each camera.

### Vehicle Observation Frequency

Number of observations recorded for each vehicle.

### Multi-Camera Movement

Camera/location sequence reconstructed for vehicles detected at multiple cameras.

### Traffic Activity

A prototype activity indicator based on the number of ANPR observations in the current session.

---

# 🛠️ Troubleshooting

### Tesseract Not Installed

Check:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Then run:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

---

### YOLO Model Not Found

Make sure the trained model exists at:

```text
models/best.pt
```

---

### Python Package Errors

Run:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

### Application Does Not Start

Run:

```powershell
.\venv\Scripts\python.exe gui.py
```

from the project directory and inspect the terminal error message.

---

# 🚀 Future Enhancements

The current prototype provides the foundation for a larger smart-city traffic platform.

### 📹 Real-Time CCTV / RTSP

Replace image uploads with live camera streams.

### 🚘 Real Vehicle Tracking

Integrate object tracking algorithms such as:

* ByteTrack
* BoT-SORT

### 🚦 Real Traffic Density Analysis

Future versions can analyze road-scene images/video to estimate:

* Vehicle count
* Vehicle classes
* Lane occupancy
* Queue length
* Congestion indicators

### 🗺️ City-Wide Route Visualization

Display vehicle movement between cameras on an interactive map.

### ☁️ Centralized Database

Replace local CSV storage with a scalable cloud or centralized database.

### 📊 Advanced Analytics

Potential analytics include:

* Peak traffic periods
* Vehicle flow
* Travel time
* Route frequency
* Congestion prediction
* Anomaly detection

### 🚨 Alert System

Potential future alerts for authorized use cases such as:

* Authorized blacklist matching
* Stolen vehicle detection
* Route anomalies
* Traffic buildup

---

# 🔄 Prototype vs Production

| Capability                | Current Prototype | Future Production |
| ------------------------- | :---------------: | :---------------: |
| License Plate Detection   |         ✅         |         ✅         |
| OCR                       |         ✅         |         ✅         |
| Image Upload              |         ✅         |         —         |
| Multiple Image Processing |         ✅         |         ✅         |
| Camera Simulation         |         ✅         |         —         |
| Multi-Camera Association  |         ✅         |         ✅         |
| Route Reconstruction      |         ✅         |         ✅         |
| Session Analytics         |         ✅         |         ✅         |
| Live CCTV                 |         ❌         |         ✅         |
| Real-Time Tracking        |         ❌         |         ✅         |
| True Traffic Density      |      Limited      |         ✅         |
| City Map Visualization    |         ❌         |         ✅         |
| Cloud Database            |         ❌         |         ✅         |

---

# 🔐 Privacy & Responsible Use

ANPR systems process vehicle registration information and, in real deployments, this information can be sensitive.

A production implementation should consider:

* Appropriate authorization
* Data retention policies
* Access control
* Secure data storage
* Audit logging
* Applicable privacy regulations
* Responsible handling of vehicle/location information

This project is currently a **demonstration prototype using locally supplied images**.

---

# 🎯 Project Objective

The long-term objective is to develop a **city-wide AI traffic intelligence platform** capable of combining observations from multiple cameras to understand vehicle movement and urban traffic patterns.

The overall concept can be summarized as:

```text
Detect
  ↓
Recognize
  ↓
Identify
  ↓
Associate
  ↓
Reconstruct
  ↓
Analyze
```

---

# 📌 Current Limitations

This project is currently a prototype rather than a production-ready traffic surveillance system.

Current limitations include:

* Uses uploaded images instead of live CCTV
* Camera locations are simulated
* Traffic activity is session-based
* CSV is used for data persistence
* No real-time vehicle tracking
* No calibrated congestion measurement
* No city map-based route visualization

These limitations also define the main areas for future development.

---

# 🌟 Why This Project Matters

The core idea is not simply **reading a license plate**.

The project demonstrates how individual AI capabilities can be connected into a larger intelligent system:

```text
Computer Vision
       +
OCR
       +
Vehicle Identity
       +
Multi-Camera Association
       +
Data Analytics
       =
Traffic Intelligence
```

This architecture provides a foundation that can eventually evolve from a desktop prototype into a **real-time smart-city traffic monitoring platform**.

---

# 👨‍💻 Project

**City-Wide AI Traffic Engine**

Built with:

**Python • YOLOv8 • OpenCV • Tesseract OCR • CustomTkinter • Pandas**

---

## 📄 License

Add your preferred open-source license before publishing the repository, for example **MIT License**, if appropriate for your project.

---

## ⭐ If You Found This Project Interesting

Consider giving the repository a ⭐ and following the project as it evolves toward real-time multi-camera traffic intelligence.
