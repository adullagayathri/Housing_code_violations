import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from src.config import (
    CSV_PATH,
    DATA_JSON_DIR,
    IMAGE_DIR,
    CANVAS_FILL_COLOR,
    CANVAS_STROKE_WIDTH,
    VIOLATION_COLORS,
    DEFAULT_BOX_COLOR,
)
from src.ui.canvas_utils import (
    save_annotations,
    load_annotations_if_exists,
    build_initial_drawing,
)

st.set_page_config(
    page_title="House Issue Marking Tool",
    page_icon="🏠",
    layout="wide",
)

# ---------------- session state ----------------
if "saved_annotations" not in st.session_state:
    st.session_state.saved_annotations = []

if "last_image" not in st.session_state:
    st.session_state.last_image = None

# ---------------- styling ----------------
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #2F2A26;
        margin-bottom: 0.2rem;
    }

    .sub-title {
        font-size: 1.05rem;
        color: #5C5148;
        margin-bottom: 1rem;
    }

    .info-card {
        background: white;
        padding: 18px;
        border-radius: 16px;
        border: 2px solid #F3D9BE;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    .legend-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        font-size: 1rem;
    }

    .legend-dot {
        width: 16px;
        height: 16px;
        border-radius: 50%;
        display: inline-block;
    }

    .help-box {
        background: #FFF3E6;
        border: 2px solid #F4C99A;
        padding: 16px;
        border-radius: 14px;
        font-size: 1rem;
        color: #4A3F36;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">🏠 House Issue Marking Tool</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Choose a house image, select a violation, draw a box, add it, and save all violations together.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="help-box">
    <b>How to use:</b><br>
    1. Choose a house image<br>
    2. Choose a violation<br>
    3. Draw one box around that issue<br>
    4. Click <b>Add Violation</b><br>
    5. Repeat for other issues<br>
    6. Click <b>Save JSON</b> once at the end
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- checks ----------------
if not os.path.exists(CSV_PATH):
    st.error(f"CSV file not found: {CSV_PATH}")
    st.stop()

if not os.path.exists(IMAGE_DIR):
    st.error(f"Image folder not found: {IMAGE_DIR}")
    st.stop()

# ---------------- load csv ----------------
try:
    df = pd.read_csv(CSV_PATH)
except Exception as e:
    st.error(f"Could not read CSV: {e}")
    st.stop()

required_cols = [
    "Violation_Description",
    "CodeViolationDescription"
]

missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    # fallback if the CSV has different column names
    pass

# If your CSV already has a violation column with clean names, use that.
# Otherwise replace this with a hardcoded list.
violation_descriptions = [
    "Peeling Paint",
    "Vehicles on Unpaved",
    "Abandoned/Junk Vehicles",
    "Overgrown Vegetation",
    "Bad Roof",
    "Broken Window",
    "Broken Door",
    "Rubbish / Garbage",
    "Damaged Walk/Driveway",
    "Damaged Siding / Soffit",
    "Damaged Foundation",
    "Damaged Porch / Steps",
    "Abandoned / Unsafe",
]

# ---------------- load images ----------------
valid_ext = (".jpg", ".jpeg", ".png")
image_files = sorted([f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(valid_ext)])

if not image_files:
    st.warning("No images found in the image folder.")
    st.stop()

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Controls")

    selected_image_name = st.selectbox("Choose a house image", image_files)

    selected_violation = st.selectbox("Choose a violation", violation_descriptions)
    selected_color = VIOLATION_COLORS.get(selected_violation, DEFAULT_BOX_COLOR)

    st.markdown("### Violation Color")
    st.markdown(
        f"""
        <div class="legend-row">
            <span class="legend-dot" style="background:{selected_color};"></span>
            <span>{selected_violation}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### All Violation Colors")
    for violation, color in VIOLATION_COLORS.items():
        st.markdown(
            f"""
            <div class="legend-row">
                <span class="legend-dot" style="background:{color};"></span>
                <span>{violation}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------- image handling ----------------
selected_image_path = os.path.join(IMAGE_DIR, selected_image_name)
image = Image.open(selected_image_path)
img_width, img_height = image.size

# load saved annotations only when image changes
if st.session_state.last_image != selected_image_name:
    st.session_state.saved_annotations = load_annotations_if_exists(
        selected_image_name,
        DATA_JSON_DIR
    )
    st.session_state.last_image = selected_image_name

initial_drawing = build_initial_drawing(st.session_state.saved_annotations)

left, right = st.columns([4, 2], gap="large")

with left:
    st.markdown("### Mark Issues on the Image")

    canvas_result = st_canvas(
        fill_color=CANVAS_FILL_COLOR,
        stroke_width=CANVAS_STROKE_WIDTH,
        stroke_color=selected_color,
        background_image=image,
        update_streamlit=True,
        height=img_height,
        width=img_width,
        drawing_mode="rect",
        initial_drawing=initial_drawing,
        display_toolbar=True,
        key=f"canvas_{selected_image_name}",
    )

with right:
    st.markdown("### Selected Violation")
    st.markdown(
        f"""
        <div class="info-card">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                <span class="legend-dot" style="background:{selected_color};"></span>
                <span><b>{selected_violation}</b></span>
            </div>
            <div>This color will be used for the next box you draw.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------- detect newest drawn box ----------------
latest_box = None

if canvas_result.json_data is not None:
    objects = canvas_result.json_data.get("objects", [])

    if len(objects) > len(st.session_state.saved_annotations):
        shape = objects[-1]

        if shape.get("type") == "rect":
            x = int(shape["left"])
            y = int(shape["top"])
            w = int(shape["width"] * shape.get("scaleX", 1))
            h = int(shape["height"] * shape.get("scaleY", 1))

            latest_box = {
                "violation": selected_violation,
                "bbox": [x, y, w, h],
                "color": selected_color,
            }

# ---------------- action buttons ----------------
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if latest_box is not None:
        if st.button("➕ Add Violation", use_container_width=True):
            st.session_state.saved_annotations.append(latest_box)
            st.rerun()
    else:
        st.button("➕ Add Violation", use_container_width=True, disabled=True)

with col2:
    if st.button("💾 Save JSON", use_container_width=True):
        json_path = save_annotations(
            selected_image_name,
            st.session_state.saved_annotations,
            DATA_JSON_DIR
        )
        st.success(f"Saved to {json_path}")

with col3:
    if st.button("🗑️ Clear All", use_container_width=True):
        st.session_state.saved_annotations = []
        json_file = os.path.join(DATA_JSON_DIR, f"{selected_image_name}_annotations.json")
        if os.path.exists(json_file):
            os.remove(json_file)
        st.rerun()

# ---------------- preview ----------------
st.markdown("### Added Violations")

if st.session_state.saved_annotations:
    preview_df = pd.DataFrame(
        [
            {
                "Violation": a["violation"],
                "BBox": a["bbox"],
                "Color": a["color"],
            }
            for a in st.session_state.saved_annotations
        ]
    )
    st.dataframe(preview_df, use_container_width=True, hide_index=True)
else:
    st.info("No violations added yet.")

if latest_box is not None:
    st.warning("You drew a box. Click 'Add Violation' to keep it.")

with st.expander("View JSON Output"):
    st.json(
        {
            "image_id": selected_image_name,
            "annotations": st.session_state.saved_annotations,
        }
    )