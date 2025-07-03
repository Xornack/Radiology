# Time Difference Calculator

A simple, self-contained web-based tool to calculate the time difference between two timestamps.

## How to Use

1.  Open the `time_difference.html` file in a web browser.
2.  Enter the start and end times. The time fields are flexible:
    *   A colon (`:`) is automatically added as you type.
    *   You can use 12-hour time with "am" or "pm" (e.g., "930am", "5pm").
    *   You can use 24-hour time (e.g., "1300", "23:30").
3.  Optionally, select a date for the start and end times.
    *   If no start date is provided, the current day is used.
    *   If no end date is provided, the start date is used.
4.  Click the "Calculate" button or press the "Enter" key to see the result.

## Features

*   Calculates the absolute time difference between two timestamps in hours and minutes (the order of entry does not matter).
*   Intelligent time input parsing for a smooth user experience.
*   All functionality is contained within a single HTML file.
*   Provides clear error messages for invalid input.
*   Simple and intuitive user interface.

## Project Structure

*   `time_difference.html`: The final, self-contained application file.
*   `index.html`, `style.css`, `app.js`: The original source files.
*   `tests/`: A directory containing the QUnit tests for the application.
*   `specification.md`: The project specification.
*   `dependencies.txt`: A list of project dependencies (currently empty).
*   `README.md`: This file.
