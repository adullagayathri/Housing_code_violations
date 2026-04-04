import os
import json


def save_annotations(image_name, annotations, json_dir):
    os.makedirs(json_dir, exist_ok=True)

    output = {
        "image_id": image_name,
        "annotations": annotations
    }

    json_path = os.path.join(json_dir, f"{image_name}_annotations.json")

    with open(json_path, "w") as f:
        json.dump(output, f, indent=4)

    return json_path


def load_annotations_if_exists(image_name, json_dir):
    json_path = os.path.join(json_dir, f"{image_name}_annotations.json")

    if not os.path.exists(json_path):
        return []

    with open(json_path, "r") as f:
        data = json.load(f)

    return data.get("annotations", [])


def annotation_to_fabric_object(annotation):
    x, y, w, h = annotation["bbox"]
    color = annotation.get("color", "#000000")

    return {
        "type": "rect",
        "left": x,
        "top": y,
        "width": w,
        "height": h,
        "fill": "rgba(0,0,0,0)",
        "stroke": color,
        "strokeWidth": 4,
        "rx": 8,
        "ry": 8,
    }


def build_initial_drawing(annotations):
    return {
        "version": "4.4.0",
        "objects": [annotation_to_fabric_object(a) for a in annotations]
    }