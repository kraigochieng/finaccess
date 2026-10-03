"""Download the raw FinAccess 2024 survey csv from Google Drive."""

from pathlib import Path

import gdown

FILE_ID = "1f0lc2OBkJpWX3FUJr21xn6CLbbY7Pk_k"
OUTPUT_PATH = Path("src/finaccess/2024_Finaccess_Publicdata.csv")


def main() -> None:
    if OUTPUT_PATH.exists():
        print(f"{OUTPUT_PATH} already exists, skipping download")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gdown.download(id=FILE_ID, output=str(OUTPUT_PATH), quiet=False)


if __name__ == "__main__":
    main()
