"""Download the raw FinAccess 2024 survey xlsx from Google Drive."""

from pathlib import Path

import gdown

FILE_ID = "1NGPFK6IGwDpLLQJnrBRyMHiXzUypuZHn"
OUTPUT_PATH = Path("src/finaccess/2024_Finaccess_Publicdata.xlsx")


def main() -> None:
    if OUTPUT_PATH.exists():
        print(f"{OUTPUT_PATH} already exists, skipping download")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gdown.download(id=FILE_ID, output=str(OUTPUT_PATH), quiet=False)


if __name__ == "__main__":
    main()
