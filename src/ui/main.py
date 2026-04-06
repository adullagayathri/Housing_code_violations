import os
import sys
from pathlib import Path
from io import BytesIO
import json

import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from src.config import (
    DATA_JSON_DIR,
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
from src.salesforce_backend import (
    salesforce_is_configured,
    save_submission_to_salesforce,
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

if "uploaded_images" not in st.session_state:
    st.session_state.uploaded_images = {}

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
    '<div class="sub-title">Upload house images, choose a violation, draw a box, add it, and save all violations together.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="help-box">
    <b>How to use:</b><br>
    1. Upload one or more house images or load a folder<br>
    2. Choose an image<br>
    3. Choose a violation<br>
    4. Draw one box around that issue<br>
    5. Click <b>Add Violation</b><br>
    6. Repeat for other issues<br>
    7. Click <b>Save JSON</b> once at the end
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------- violations list ----------------
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

# ---------------- add images ----------------
st.markdown("### Add Images")

image_source = st.radio(
    "Choose how to add images",
    ["Upload Images", "Load From Folder"],
    horizontal=True,
)

if st.button("Clear Loaded Images"):
    st.session_state.uploaded_images = {}
    st.session_state.saved_annotations = []
    st.session_state.last_image = None
    st.rerun()

if image_source == "Upload Images":
    uploaded_files = st.file_uploader(
        "Upload house images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            image_bytes = uploaded_file.read()
            st.session_state.uploaded_images[uploaded_file.name] = image_bytes

elif image_source == "Load From Folder":
    folder_path = st.text_input("Enter local folder path")

    if folder_path:
        valid_ext = (".jpg", ".jpeg", ".png")
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            folder_files = sorted(
                [f for f in os.listdir(folder_path) if f.lower().endswith(valid_ext)]
            )

            if folder_files:
                for file_name in folder_files:
                    full_path = os.path.join(folder_path, file_name)
                    with open(full_path, "rb") as f:
                        st.session_state.uploaded_images[file_name] = f.read()
                st.success(f"Loaded {len(folder_files)} images from folder")
            else:
                st.warning("No image files found in that folder.")
        else:
            st.error("Folder path is not valid.")

image_names = list(st.session_state.uploaded_images.keys())

if not image_names:
    st.info("Please upload images or load a folder to begin.")
    st.stop()

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Controls")

    selected_image_name = st.selectbox("Choose an image", image_names)

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
image_bytes = st.session_state.uploaded_images[selected_image_name]
image = Image.open(BytesIO(image_bytes)).convert("RGB")

max_width = 900
orig_width, orig_height = image.size
if orig_width > max_width:
    new_width = max_width
    new_height = int(orig_height * (new_width / orig_width))
    image = image.resize((new_width, new_height))

img_width, img_height = image.size

if st.session_state.last_image != selected_image_name:
    st.session_state.saved_annotations = load_annotations_if_exists(
        selected_image_name,
        DATA_JSON_DIR,
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
        background_image=image.convert("RGBA"),
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
        output_json = {
            "image_id": selected_image_name,
            "annotations": st.session_state.saved_annotations,
        }

        json_text = json.dumps(output_json, indent=2)

        image_bytes_to_save = st.session_state.uploaded_images.get(selected_image_name)

        if image_bytes_to_save is None:
            st.error("Could not find image bytes to save.")
        elif salesforce_is_configured():
            try:
                record_id = save_submission_to_salesforce(
                    image_name=selected_image_name,
                    image_bytes=image_bytes_to_save,
                    json_text=json_text,
                )
                st.success(f"Saved to Salesforce. Record ID: {record_id}")
            except Exception as e:
                st.error(f"Salesforce error: {str(e)}")
        else:
            json_path = save_annotations(
                selected_image_name,
                st.session_state.saved_annotations,
                DATA_JSON_DIR,
            )
            st.warning("Salesforce keys are not configured yet. Saved locally instead.")
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
    preview_rows = [
        {
            "Violation": a["violation"],
            "BBox": a["bbox"],
            "Color": a["color"],
        }
        for a in st.session_state.saved_annotations
    ]
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)
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
