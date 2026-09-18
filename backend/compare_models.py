import sys
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image
from ai_edge_litert.interpreter import Interpreter

from disease_info import CLASS_NAMES

BASE = Path(__file__).parent
KERAS_MODEL_PATH = BASE / "trained_plant_disease_model.keras"
TFLITE_MODEL_PATH = BASE / "trained_plant_disease_model.tflite"
IMG_SIZE = (128, 128)


def load_image(path):
    img = Image.open(path).convert("RGB")
    return np.expand_dims(np.array(img.resize(IMG_SIZE), dtype=np.float32), axis=0)


def run_keras(arr):
    model = tf.keras.models.load_model(KERAS_MODEL_PATH)
    preds = model.predict(arr, verbose=0)[0]
    idx = int(np.argmax(preds))
    confidence = round(float(np.max(preds)) * 100, 1)
    return CLASS_NAMES[idx], confidence


def run_tflite(arr):
    interpreter = Interpreter(model_path=str(TFLITE_MODEL_PATH))
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    interpreter.set_tensor(input_details[0]["index"], arr)
    interpreter.invoke()
    preds = interpreter.get_tensor(output_details[0]["index"])[0]

    idx = int(np.argmax(preds))
    confidence = round(float(np.max(preds)) * 100, 1)
    return CLASS_NAMES[idx], confidence


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_models.py <path-to-image>")
        sys.exit(1)

    image_path = sys.argv[1]
    arr = load_image(image_path)

    keras_class, keras_confidence = run_keras(arr)
    tflite_class, tflite_confidence = run_tflite(arr)

    print(f"{'Model':<10} {'Class':<40} {'Confidence':>10}")
    print(f"{'Keras':<10} {keras_class:<40} {keras_confidence:>9}%")
    print(f"{'TFLite':<10} {tflite_class:<40} {tflite_confidence:>9}%")


if __name__ == "__main__":
    main()
