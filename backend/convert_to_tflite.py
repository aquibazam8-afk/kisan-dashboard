import os

import tensorflow as tf

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

MODELS = [
    ("trained_plant_disease_model.keras", "trained_plant_disease_model.tflite"),
    ("paddy_disease_model.keras", "paddy_disease_model.tflite"),
]


def convert(keras_filename, tflite_filename):
    keras_path = os.path.join(BACKEND_DIR, keras_filename)
    tflite_path = os.path.join(BACKEND_DIR, tflite_filename)

    model = tf.keras.models.load_model(keras_path)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()

    with open(tflite_path, "wb") as f:
        f.write(tflite_model)

    return keras_path, tflite_path


def print_size_mb(path):
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"{os.path.basename(path)}: {size_mb:.2f} MB")


def main():
    all_paths = []
    for keras_filename, tflite_filename in MODELS:
        keras_path, tflite_path = convert(keras_filename, tflite_filename)
        all_paths.append(keras_path)
        all_paths.append(tflite_path)

    print("\nFile sizes:")
    for path in all_paths:
        print_size_mb(path)


if __name__ == "__main__":
    main()
