"""Run experimental CRNN inference on one already-cropped text line."""

import argparse

from prescriptions.services.crnn import recognize_line


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Path to a single handwritten text-line crop")
    args = parser.parse_args()
    result = recognize_line(args.image)
    if not result:
        raise RuntimeError("The experimental CRNN did not recognize any characters.")
    print(result)


if __name__ == "__main__":
    main()
