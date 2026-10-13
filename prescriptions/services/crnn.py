"""Experimental inference for a single, pre-cropped handwritten text line."""

import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

HEIGHT = 64
WIDTH = 256
ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts"


def _prepare_image(image_path):
    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("L")
        image.thumbnail((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        canvas = Image.new("L", (WIDTH, HEIGHT), color=255)
        canvas.paste(image, (0, 0))
    import numpy as np

    pixels = 1.0 - (np.asarray(canvas, dtype=np.float32) / 255.0)
    return pixels[None, ..., None]


@lru_cache(maxsize=1)
def _load_model_and_vocabulary():
    model_path = ARTIFACTS_DIR / "crnn.keras"
    vocabulary_path = ARTIFACTS_DIR / "vocab.json"
    if not model_path.is_file() or not vocabulary_path.is_file():
        raise FileNotFoundError(
            "Experimental CRNN artifacts are missing. Train the line recognizer first."
        )

    import tensorflow as tf

    with vocabulary_path.open(encoding="utf-8") as vocabulary_file:
        vocabulary = json.load(vocabulary_file)
    if not isinstance(vocabulary, dict) or not vocabulary:
        raise ValueError("The CRNN vocabulary is empty or invalid.")
    model = tf.keras.models.load_model(model_path)
    return model, vocabulary, tf


def recognize_line(image_path):
    """Recognize one text-line crop; this does not detect lines in a page."""
    model, vocabulary, tf = _load_model_and_vocabulary()
    probabilities = model.predict(_prepare_image(image_path), verbose=0)
    if probabilities.shape[-1] != len(vocabulary) + 1:
        raise ValueError("The trained CRNN output does not match its vocabulary.")

    log_probabilities = tf.math.log(tf.clip_by_value(probabilities, 1e-7, 1.0))
    decoded, _ = tf.nn.ctc_greedy_decoder(
        tf.transpose(log_probabilities, [1, 0, 2]),
        tf.fill([tf.shape(probabilities)[0]], tf.shape(probabilities)[1]),
        blank_index=0,
    )
    inverse_vocabulary = {
        int(index): character for character, index in vocabulary.items()
    }
    sparse_result = decoded[0]
    characters = [
        (int(index[1]), inverse_vocabulary.get(int(value), "\ufffd"))
        for index, value in zip(sparse_result.indices.numpy(), sparse_result.values.numpy())
        if int(index[0]) == 0
    ]
    return "".join(character for _, character in sorted(characters))
