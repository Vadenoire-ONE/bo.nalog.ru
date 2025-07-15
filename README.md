# README.md

# Python Balance Sheet Downloader for bo.nalog.gov.ru





This script automates the process of downloading financial balance sheets for Russian companies from the Federal Tax Service's public database ([bo.nalog.gov.ru](https://bo.nalog.gov.ru/)). It uses a list of INNs (Individual Taxpayer Numbers) as input and downloads the corresponding financial reports as ZIP archives.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [File Structure](#file-structure)
- [Disclaimer](#disclaimer)
- [License](#license)

## Features

- **Automated Downloading**: Fully automates the search, selection, and download process.
- **Batch Processing**: Processes a list of INNs from a simple text file.
- **Robust Error Handling**: Implements retry logic with exponential backoff for network stability.
- **Detailed Logging**: Logs all actions, successes, and errors to `balance_sheet_downloader.log` for easy debugging.
- **Download Verification**: Checks that files are downloaded successfully and that ZIP archives are not corrupt.
- **Organized Output**: Saves downloaded files into a structured directory format: `downloads///`.
- **Headless Mode**: Supports running without a visible browser window for server-based execution.
- **Summary Reporting**: Generates a `download_report.txt` file summarizing the results of the run.

## Prerequisites

Before you begin, ensure you have the following installed:

- [Python 3.11+](https://www.python.org/downloads/)
- [Google Chrome](https://www.google.com/chrome/)
- [Git](https://git-scm.com/downloads)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repository-name.git
    cd your-repository-name
    ```
    *(Replace `your-username` and `your-repository-name` with your actual GitHub details.)*

2.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Prepare your input file:**
    Create a file named `inns.txt` in the project's root directory. Add one INN per line.

    **Example `inns.txt`:**
    ```
    7707083893
    7702070139
    7706664522
    ```

2.  **Run the script from your terminal:**

    **Basic command:**
    ```bash
    python selena_from_nalog_gov.py inns.txt
    ```

    **Run in headless mode (recommended for speed):**
    ```bash
    python selena_from_nalog_gov.py inns.txt --headless
    ```

    **Specify a custom download directory:**
    ```bash
    python selena_from_nalog_gov.py inns.txt --download-dir C:\MyReports --headless
    ```

3.  **Check the output:**
    -   Downloaded ZIP archives will be located in the `downloads/` folder (or your custom directory), organized by INN and year.
    -   A log file `balance_sheet_downloader.log` will be created with detailed information about the run.
    -   A summary `download_report.txt` will be created, giving you a quick overview of successful and failed downloads.

IV. **How it works:**
    - For each INN in inns.txt:
        Open https://bo.nalog.gov.ru/search?query=[INN].
        Wait for <div class="results-search-table-item"> to load.
        Find and click on the entry matching the INN.
        On the organization card page, locate and click "Скачать таблицей или текстом".
        In the popup, click "Выбрать все".
        Click "Скачать архив" and verify the download.
        Click the "2023" button, repeat "Выбрать все" and "Скачать архив" for 2023.
        Verify each download.
        Log success or errors, then proceed to the next INN.
    3. Error Handling and Logging
        Implement checks for:
            Page load timeouts.
            Download completion (file presence, size).
            Captcha or access blocks.
        Log all actions and errors for auditing.

4. Output
Downloaded files should be organized in folders by INN and year.

Maintain a log file of all successful and failed downloads.

## File Structure

```
.
├── selena_from_nalog_gov.py    # The main Python script
├── requirements.txt            # Project dependencies
├── inns.txt                    # Your input file with INNs (you create this)
├── .gitignore                  # Specifies files to ignore for Git
└── README.md                   # This file
```

## Disclaimer

This script is intended for educational and research purposes only. The user is solely responsible for using this script in compliance with the terms of service of `bo.nalog.gov.ru` and any applicable laws. The author provides no warranty and assumes no liability for the use of this software. The structure of the target website may change at any time, which could break the script's functionality.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
