# PET Report Parser (Web Version)

A simple, client-side web tool for parsing and formatting pasted output from MIM7 as input for this tool.
Extracts relevant data in my radiology report format.

## Features

- **Paste and Parse:** Copy raw MIM findings text and process it instantly in your browser.
- **Auto-formatting:** Extracts key metrics (finding number, RECIST long/short, Max SUV, slice) and summarizes them into concise, readable lines.
- **Comparison Support:** If your report contains multiple dated entries per finding, the output highlights changes between the two most recent dates.
- **Clipboard & Download:** Copy the formatted output or save it as a `.txt` file with a single click.
- **Runs Locally:** No server or upload required—everything runs securely in your browser.

## Usage

1. **Open `*.html` in any modern web browser.**
2. Paste your PET report text into the input textarea.
3. Click **Process**.
4. Review the formatted output in the Output box.
5. Use **Copy Output** to copy the result, or **Save to File** to download it.

> The script is ready to process data as soon as the page is loaded.

## Example

**Input:**
```
Finding 1
yyyy-mm-dd
Max: 8.2 SUVbw
RECIST Long: 3.1 cm
RECIST Short: 2.6 cm
Slice with Max: 42 #
yyyy-mm-dd
Max: 6.5 SUVbw
RECIST Long: 2.8 cm
RECIST Short: 2.2 cm
Slice with Max: 38 #
```

**Output:**
```
Finding 1. 3.1 x 2.6 cm (axial image ) from 2.8 x 2.2 cm. Max SUV 8.2 from 6.5.
```

## Customization

- The parser is tuned for a specific MIM output. If reports differ, may need to adapt the regexes in the JavaScript section.
- Extend the script using the provided functions (`parsePetReport` and `formatPetOutput`) as needed.

## Installation

No installation required—just open the HTML file in your browser.

## Technologies

- HTML, CSS, and vanilla JavaScript
