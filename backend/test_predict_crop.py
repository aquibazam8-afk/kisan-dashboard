"""
Tests for /predict's crop handling: PlantVillage predictions restricted to
the selected crop's classes, "wrong_crop" when the photo doesn't look like
that crop, "unsupported" for crops with no model, and paddy unchanged.
The TFLite interpreters are replaced with fakes that return fixed
probability vectors, so no model files are needed.

Run: python -m unittest test_predict_crop -v
"""
import asyncio
import io
import unittest
from unittest import mock

import numpy as np
from fastapi import UploadFile
from PIL import Image

import app
from disease_info import CLASS_NAMES
from paddy_disease_info import PADDY_CLASS_NAMES

OK_KEYS = {
    "status", "class", "crop", "disease", "healthy", "confidence",
    "low_confidence", "description", "action", "note",
}


class FakeInterpreter:
    """Stands in for a TFLite Interpreter: invoke() yields a fixed vector."""

    def __init__(self, probs):
        self.probs = np.asarray(probs, dtype=np.float32)
        self.invoked = False

    def set_tensor(self, index, value):
        pass

    def invoke(self):
        self.invoked = True

    def get_tensor(self, index):
        return self.probs[np.newaxis, :]

    def as_model(self):
        return self, [{"index": 0}], [{"index": 1}]


def _probs(mass_by_class, classes=CLASS_NAMES):
    """Probability vector over `classes` from {class name: probability}."""
    v = np.zeros(len(classes), dtype=np.float32)
    for name, p in mass_by_class.items():
        v[classes.index(name)] = p
    return v


def _upload():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (40, 140, 60)).save(buf, format="PNG")
    buf.seek(0)
    return UploadFile(file=buf, filename="leaf.png")


def _predict(crop, plantvillage=None, paddy=None):
    """Call /predict with fake models; returns (response, pv fake, paddy fake)."""
    pv = FakeInterpreter(plantvillage if plantvillage is not None else np.zeros(len(CLASS_NAMES)))
    pd = FakeInterpreter(paddy if paddy is not None else np.zeros(len(PADDY_CLASS_NAMES)))
    with mock.patch.object(app, "get_model", pv.as_model), \
         mock.patch.object(app, "get_paddy_model", pd.as_model):
        resp = asyncio.run(app.predict(file=_upload(), crop=crop))
    return resp, pv, pd


class CropFilteringTests(unittest.TestCase):
    def test_argmax_restricted_to_selected_crop(self):
        # Globally the top class is Tomato Early blight, but potato is selected
        # and holds 60% of the probability — so the answer must be a potato class.
        probs = _probs({
            "Tomato___Early_blight": 0.40,
            "Potato___Early_blight": 0.35,
            "Potato___Late_blight": 0.25,
        })
        resp, _, _ = _predict("potato", plantvillage=probs)
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(resp["class"], "Potato___Early_blight")
        # Renormalized within potato: 0.35 / 0.60
        self.assertEqual(resp["confidence"], 58.3)
        self.assertTrue(resp["low_confidence"])

    def test_maize_prefix_matches_corn_classes(self):
        probs = _probs({"Corn_(maize)___Common_rust_": 0.9, "Apple___Apple_scab": 0.1})
        resp, _, _ = _predict("maize", plantvillage=probs)
        self.assertEqual(resp["class"], "Corn_(maize)___Common_rust_")
        self.assertEqual(resp["confidence"], 100.0)

    def test_healthy_class_within_crop(self):
        probs = _probs({"Tomato___healthy": 0.7, "Tomato___Late_blight": 0.1, "Grape___Black_rot": 0.2})
        resp, _, _ = _predict("tomato", plantvillage=probs)
        self.assertEqual(resp["class"], "Tomato___healthy")
        self.assertTrue(resp["healthy"])
        self.assertEqual(resp["confidence"], 87.5)  # 0.7 / 0.8

    def test_success_shape_is_existing_shape_plus_status(self):
        probs = _probs({"Tomato___Late_blight": 1.0})
        resp, _, _ = _predict("tomato", plantvillage=probs)
        self.assertEqual(set(resp), OK_KEYS)


class WrongCropTests(unittest.TestCase):
    def test_low_crop_mass_is_wrong_crop(self):
        # The cabbage-photo case, but with maize selected: almost all the mass
        # is on a tomato class, so we must not report a maize disease.
        probs = _probs({"Tomato___Early_blight": 0.9, "Corn_(maize)___healthy": 0.1})
        resp, _, _ = _predict("maize", plantvillage=probs)
        self.assertEqual(resp["status"], "wrong_crop")
        self.assertNotIn("disease", resp)
        self.assertIn("maize", resp["message"]["en"])
        self.assertIn("मक्का", resp["message"]["hi"])

    def test_just_below_threshold_is_wrong_crop(self):
        probs = _probs({"Potato___Late_blight": 0.49, "Apple___healthy": 0.51})
        resp, _, _ = _predict("potato", plantvillage=probs)
        self.assertEqual(resp["status"], "wrong_crop")

    def test_exactly_at_threshold_is_diagnosed(self):
        probs = _probs({"Potato___Late_blight": 0.25, "Potato___healthy": 0.25, "Apple___healthy": 0.5})
        resp, _, _ = _predict("potato", plantvillage=probs)
        self.assertEqual(resp["status"], "ok")


class UnsupportedCropTests(unittest.TestCase):
    def test_crops_without_a_model_are_unsupported(self):
        # Even a confident tomato prediction must not leak through for these.
        probs = _probs({"Tomato___Early_blight": 1.0})
        for crop in ("veg", "arhar", "onion", "cauliflower", "banana", None):
            with self.subTest(crop=crop):
                resp, pv, pd = _predict(crop, plantvillage=probs)
                self.assertEqual(resp["status"], "unsupported")
                self.assertEqual(set(resp["message"]), {"en", "hi"})
                self.assertNotIn("disease", resp)
                self.assertFalse(pv.invoked)
                self.assertFalse(pd.invoked)


class PaddyTests(unittest.TestCase):
    def test_paddy_uses_paddy_model_over_all_its_classes(self):
        name = PADDY_CLASS_NAMES[1]
        probs = np.full(len(PADDY_CLASS_NAMES), 0.02, dtype=np.float32)
        probs[1] = 1.0 - 0.02 * (len(PADDY_CLASS_NAMES) - 1)
        resp, pv, pd = _predict("paddy", paddy=probs)
        self.assertTrue(pd.invoked)
        self.assertFalse(pv.invoked)
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(resp["class"], name)
        self.assertEqual(resp["confidence"], round(float(probs[1]) * 100, 1))
        self.assertEqual(resp["healthy"], name == "normal")
        self.assertEqual(set(resp), OK_KEYS)


if __name__ == "__main__":
    unittest.main()
