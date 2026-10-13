"""Train the experimental CRNN from verified, single-line image/transcription pairs."""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from PIL import Image

HEIGHT = 64
WIDTH = 256
BATCH_SIZE = 8


def load_rows(csv_path):
    csv_path = Path(csv_path).resolve()
    frame = pd.read_csv(csv_path).dropna(subset=["image_path", "text"])
    rows = []
    for row in frame.itertuples(index=False):
        image_path = Path(str(row.image_path))
        if not image_path.is_absolute():
            image_path = csv_path.parent / image_path
        text = str(row.text)
        if not text.strip():
            raise ValueError(f"Empty transcription for {image_path}")
        if not image_path.is_file():
            raise FileNotFoundError(f"Training image does not exist: {image_path}")
        rows.append((str(image_path), text))
    if not rows:
        raise ValueError(f"No usable image/transcription pairs in {csv_path}")
    return rows


def build_vocabulary(rows):
    characters = sorted({character for _, text in rows for character in text})
    return {character: index + 1 for index, character in enumerate(characters)}


def prepare_image(path):
    with Image.open(path) as source:
        image = source.convert("L")
        image.thumbnail((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        canvas = Image.new("L", (WIDTH, HEIGHT), color=255)
        canvas.paste(image, (0, 0))
    pixels = 1.0 - (np.asarray(canvas, dtype=np.float32) / 255.0)
    return pixels[..., None]


def make_dataset(rows, vocabulary, batch_size):
    def generate():
        for image_path, text in rows:
            unknown = sorted(set(text) - set(vocabulary))
            if unknown:
                raise ValueError(f"Characters missing from vocabulary: {unknown!r}")
            labels = np.asarray([vocabulary[character] for character in text], dtype=np.int32)
            yield prepare_image(image_path), labels, np.int32(len(labels))

    dataset = tf.data.Dataset.from_generator(
        generate,
        output_signature=(
            tf.TensorSpec((HEIGHT, WIDTH, 1), tf.float32),
            tf.TensorSpec((None,), tf.int32),
            tf.TensorSpec((), tf.int32),
        ),
    )
    return dataset.shuffle(len(rows), reshuffle_each_iteration=True).padded_batch(
        batch_size,
        padded_shapes=([HEIGHT, WIDTH, 1], [None], []),
        padding_values=(np.float32(0), np.int32(0), np.int32(0)),
    ).prefetch(tf.data.AUTOTUNE)


def build_model(vocabulary_size):
    inputs = tf.keras.Input(shape=(HEIGHT, WIDTH, 1), name="image")
    features = tf.keras.layers.Conv2D(32, 3, padding="same", activation="relu")(inputs)
    features = tf.keras.layers.MaxPooling2D(pool_size=(2, 2))(features)
    features = tf.keras.layers.Conv2D(64, 3, padding="same", activation="relu")(features)
    features = tf.keras.layers.MaxPooling2D(pool_size=(2, 2))(features)
    features = tf.keras.layers.Conv2D(128, 3, padding="same", activation="relu")(features)
    features = tf.keras.layers.Permute((2, 1, 3))(features)
    features = tf.keras.layers.Reshape((64, 16 * 128))(features)
    features = tf.keras.layers.Bidirectional(
        tf.keras.layers.LSTM(128, return_sequences=True)
    )(features)
    features = tf.keras.layers.Bidirectional(
        tf.keras.layers.LSTM(128, return_sequences=True)
    )(features)
    probabilities = tf.keras.layers.Dense(
        vocabulary_size + 1,
        activation="softmax",
        name="character_probs",
    )(features)
    return tf.keras.Model(inputs, probabilities, name="prescription_crnn")


def train_step(model, optimizer, images, labels):
    with tf.GradientTape() as tape:
        probabilities = model(images, training=True)
        batch_size = tf.shape(images)[0]
        time_steps = tf.shape(probabilities)[1]
        loss_values = tf.nn.ctc_loss(
            labels=tf.sparse.from_dense(labels),
            logits=tf.math.log(tf.clip_by_value(probabilities, 1e-7, 1.0)),
            label_length=None,
            logit_length=tf.fill([batch_size], time_steps),
            logits_time_major=False,
            blank_index=0,
        )
        loss = tf.reduce_mean(loss_values)
    gradients = tape.gradient(loss, model.trainable_variables)
    optimizer.apply_gradients(
        (gradient, variable)
        for gradient, variable in zip(gradients, model.trainable_variables)
        if gradient is not None
    )
    return loss


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, help="CSV containing image_path,text columns")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--out", default="artifacts")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1:
        parser.error("--epochs and --batch-size must be positive")

    rows = load_rows(args.train)
    vocabulary = build_vocabulary(rows)
    dataset = make_dataset(rows, vocabulary, args.batch_size)
    model = build_model(len(vocabulary))
    optimizer = tf.keras.optimizers.Adam(learning_rate=1e-3)
    output_directory = Path(args.out)
    output_directory.mkdir(parents=True, exist_ok=True)
    vocabulary_path = output_directory / "vocab.json"
    with vocabulary_path.open("w", encoding="utf-8") as vocabulary_file:
        json.dump(vocabulary, vocabulary_file, ensure_ascii=False, indent=2)

    print(
        f"Training on {len(rows)} line crops; vocabulary size={len(vocabulary)}. "
        "No independent validation set is configured."
    )
    for epoch in range(1, args.epochs + 1):
        losses = [
            float(train_step(model, optimizer, images, labels).numpy())
            for images, labels, _ in dataset
        ]
        print(f"Epoch {epoch}/{args.epochs} - train CTC loss: {np.mean(losses):.4f}")
    model.save(os.fspath(output_directory / "crnn.keras"))
    print(f"Saved model and vocabulary in {output_directory.resolve()}")


if __name__ == "__main__":
    main()
