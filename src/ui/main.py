import os
import sys
from pathlib import Path
from io import BytesIO
import io
import uuid

import pandas as pd
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

# ---------------- UI ----------------
st.title("🏠 House Issue Marking Tool")

# ---------------- upload ----------------
uploaded_files = st.file_uploader(
    "Upload house images",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        image_bytes = uploaded_file.read()
        st.session_state.uploaded_images[uploaded_file.name] = image_bytes

image_names = list(st.session_state.uploaded_images.keys())

if not image_names:
    st.info("Upload images to begin")
    st.stop()

# ---------------- sidebar ----------------
with st.sidebar:
    selected_image_name = st.selectbox("Choose image", image_names)

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

    selected_violation = st.selectbox("Violation", violation_descriptions)
    selected_color = VIOLATION_COLORS.get(selected_violation, DEFAULT_BOX_COLOR)

# ---------------- image ----------------
image_bytes = st.session_state.uploaded_images[selected_image_name]
image = Image.open(BytesIO(image_bytes)).convert("RGB")
img_width, img_height = image.size

# 🔥 FIX: convert image to BytesIO (for Streamlit Cloud)
img_buffer = io.BytesIO()
image.save(img_buffer, format="PNG")
img_buffer.seek(0)

# ---------------- load annotations ----------------
if st.session_state.last_image != selected_image_name:
    st.session_state.saved_annotations = load_annotations_if_exists(
        selected_image_name,
        DATA_JSON_DIR
    )
    st.session_state.last_image = selected_image_name

initial_drawing = build_initial_drawing(st.session_state.saved_annotations)

# ---------------- canvas ----------------
canvas_result = st_canvas(
    fill_color=CANVAS_FILL_COLOR,
    stroke_width=CANVAS_STROKE_WIDTH,
    stroke_color=selected_color,
    background_image=img_buffer,  # ✅ FIXED
    update_streamlit=True,
    height=img_height,
    width=img_width,
    drawing_mode="rect",
    initial_drawing=initial_drawing,
    display_toolbar=True,
    key=f"canvas_{selected_image_name}",
)

# ---------------- process canvas ----------------
latest_box = None

if canvas_result.json_data is not None:
    objects = canvas_result.json_data.get("objects", [])

    canvas_annotations = []
    for shape in objects:
        if shape.get("type") != "rect":
            continue

        x = int(shape["left"])
        y = int(shape["top"])
        w = int(shape["width"] * shape.get("scaleX", 1))
        h = int(shape["height"] * shape.get("scaleY", 1))

        canvas_annotations.append({
            "violation": shape.get("violation", selected_violation),
            "bbox": [x, y, w, h],
            "color": shape.get("color", shape.get("stroke", selected_color)),
        })

    if len(canvas_annotations) < len(st.session_state.saved_annotations):
        st.session_state.saved_annotations = canvas_annotations
        st.rerun()

    elif len(canvas_annotations) > len(st.session_state.saved_annotations):
        latest_box = {
            "violation": selected_violation,
            "bbox": canvas_annotations[-1]["bbox"],
            "color": selected_color,
        }

# ---------------- buttons ----------------
col1, col2, col3 = st.columns(3)

with col1:
    if latest_box is not None:
        if st.button("Add Violation"):
            st.session_state.saved_annotations.append(latest_box)
            st.rerun()

with col2:
    if st.button("Save JSON"):
        json_path = save_annotations(
            selected_image_name,
            st.session_state.saved_annotations,
            DATA_JSON_DIR
        )
        st.success(f"Saved to {json_path}")

with col3:
    if st.button("Clear All"):
        st.session_state.saved_annotations = []
        st.rerun()

# ---------------- preview ----------------
st.subheader("Annotations")

if st.session_state.saved_annotations:
    df = pd.DataFrame(st.session_state.saved_annotations)
    st.dataframe(df)
else:
    st.info("No annotations yet")

st.json({
    "image_id": selected_image_name,
    "annotations": st.session_state.saved_annotations
})
