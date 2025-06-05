# Google Timeline Driving Analyzer

This Python script analyzes your Google Maps Timeline data (Location History) to identify and quantify trips made from a home address to specified work locations and back home within the same day. It uses the Google Geocoding API to determine the coordinates of your provided addresses and calculates travel distances based on your timeline's recorded activity segments.

## Features

-   Geocodes home and multiple work addresses using Google Maps API.
-   Displays potential geocoding matches for address reconciliation.
-   Processes Google Timeline JSON export (`Records.json`).
-   Identifies days with a "Home -> Work -> Home" travel pattern.
-   Calculates distances for trips to and from work using timeline data.
-   Outputs results to an XLSX spreadsheet, including:
    -   Date of travel
    -   Work location visited
    -   Distance to work (km)
    -   Distance from work (km)
    -   Total daily distance for the round trip (km)
-   Calculates total kilometers driven for all qualifying trips over the period.
-   Configurable proximity radius for matching GPS points to locations.

## Prerequisites

1.  **Python 3.7+**
2.  **Google Cloud Account & API Key**:
    * You need a Google Cloud Platform (GCP) project.
    * **Enable the "Geocoding API"** within the Google Maps Platform section of your GCP console.
    * **Enable Billing** for your GCP project. The Geocoding API has a free tier, but usage beyond that will incur costs.
    * Create an **API Key**. For security:
        * Restrict the API key to only allow the "Geocoding API".
        * Optionally, restrict it to your IP address if running locally, or by HTTP referrers/app restrictions if applicable.
        * **Keep your API key secure and do not commit it to public repositories.**
3.  **Google Timeline Data (Location History JSON file)**:
    * **Primary Method: Exporting from your Android Device**
        * Google Timeline data is now primarily stored on your Android device. You'll need to export it directly from the Google Maps app.
        * **Steps (may vary slightly depending on your Android version and Google Maps app version):**
            1.  Open the **Google Maps** app on your Android device.
            2.  Tap on your **profile picture** or initial in the top right corner.
            3.  Select "**Your Timeline**."
            4.  In the Timeline view, tap the **three vertical dots (⋮)** for more options (usually in the top right).
            5.  Select "**Settings and privacy**."
            6.  Scroll down to the "Timeline data" or "Location data" section.
            7.  Look for an option like "**Export Timeline data**" or "**Download a copy of your data**".
            8.  Follow the prompts to export your data. This usually saves a `.json` file (often named `Records.json`, `Timeline.json`, or similar) to your device's "Downloads" folder or a location you specify.
        * **Transfer the JSON file**: Once exported to your phone, you'll need to transfer this JSON file to the computer where you intend to run the Python script (e.g., via USB cable, cloud storage like Google Drive/Dropbox, email, etc.).
    * **Secondary Method: Google Takeout (May Not Provide Usable Data if Encrypted)**
        * Previously, Google Takeout ([https://takeout.google.com/](https://takeout.google.com/)) was the primary way. However, if your Timeline data is end-to-end encrypted and stored on your device, Takeout might only provide an `archive_browser.html` file or an "Encrypted Backups.txt" notice, not the usable JSON data.
        * If the in-app export fails or is unavailable, you *can still try* Google Takeout if end-to-end encryption and storing of Timeline data on your own physical device has not yet been configured. Only in this case:
            1.  Go to Google Takeout.
            2.  Deselect all products ("Deselect all").
            3.  Scroll down and select **"Location History"**. Ensure the format is set to **JSON**.
            4.  Proceed to create and download the export.
            5.  If you receive a usable JSON file (e.g., `Records.json`, often within `Takeout/Location History/Semantic Location History/` or `Takeout/Location History/`), this can be used.
    * **The script expects a single JSON file path for the `--timeline_json` argument.**

4.  **Virtual Environment and Python Libraries**: Set up a virtual environment, then install the required libraries using pip:
    ```bash
    python3 -m venv venv        
    source ./venv/bin/activate
    pip install googlemaps openpyxl pandas python-dateutil haversine
    ```

## Getting Your Google Maps API Key 🔑

To use this script, you need a Google Maps API key with the **Geocoding API** enabled. Follow these steps:

1.  **Go to Google Cloud Console**:
    * Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
    * If you don't have an account, you'll need to create one and set up a billing account. Google Maps Platform services require a billing account, though there is a generous free tier for many APIs.

2.  **Create or Select a Project**:
    * At the top of the page, click the project dropdown.
    * Either select an existing project or click **"NEW PROJECT"**.
    * If creating a new project, give it a name (e.g., "My Maps Projects") and an organization if applicable, then click **"CREATE"**.

3.  **Enable the Geocoding API**:
    * Once your project is selected, use the navigation menu (hamburger icon ☰) and go to **APIs & Services > Library**.
    * In the search bar, type "**Geocoding API**".
    * Click on "**Geocoding API**" from the search results.
    * Click the **"ENABLE"** button. If it's already enabled, you'll see a "MANAGE" button.

4.  **Create an API Key**:
    * In the navigation menu, go to **APIs & Services > Credentials**.
    * Click on **"+ CREATE CREDENTIALS"** at the top of the page.
    * Select **"API key"** from the dropdown.
    * Your new API key will be displayed. **Copy this key immediately** and store it securely. You'll need it for the script.

5.  **Restrict Your API Key (Highly Recommended for Security)**:
    * After the API key is created, a dialog box will appear showing the key. Click **"EDIT API KEY"** (or find the key in the list on the Credentials page and click the pencil icon to edit it).
    * Under **"API restrictions"**:
        * Select **"Restrict key"**.
        * In the "Select APIs" dropdown, choose "**Geocoding API**". This ensures your key can *only* be used for this specific service.
        * Click **"OK"**.
    * Under **"Application restrictions"** (optional but good practice):
        * You can restrict the key to be used only from certain IP addresses if you're running the script from a machine with a static IP. For local development, this might be an option.
        * If you were using it on a website, you'd use HTTP referrers.
    * Click **"SAVE"**.

6.  **Ensure Billing is Enabled**:
    * The Geocoding API usage is tied to your project's billing account.
    * In the navigation menu, go to **Billing**.
    * Make sure your project is linked to an active billing account. The Google Maps Platform offers a recurring monthly free credit for API usage, but a billing account is still required to activate the services.

**Important Notes**:
* **Keep your API key secure!** Do not share it publicly or commit it to version control systems like Git.
* Monitor your API usage and billing in the Google Cloud Console to avoid unexpected charges, though typical personal use for this script should fall within the free tier.

## Setup and Usage

1.  **Navigate to the Script**: The Python code is saved as `trip-tracker.py`.
2.  **Prepare Your Data**:
    * Have your Google Maps API Key ready.
    * Locate your Google Timeline `Records.json` file.
3.  **Run from Command Line**:
    Open your terminal or command prompt, navigate to the directory where you saved the script, and run it with the required arguments.

    **Command Syntax:**
    ```bash
    python trip-tracker.py \
        --home_address "Your Full Home Address" \
        --work_destinations "Work Address 1" "Optional Work Address 2" \
        --start_date "YYYY-MM-DD" \
        --end_date "YYYY-MM-DD" \
        --timeline_json "path/to/your/Records.json" \
        --api_key "YOUR_Maps_API_KEY" \
        [--output_xlsx "output_filename.xlsx"] \
        [--proximity_radius_m METERS]
    ```

    **Example:**
    ```bash
    python trip-tracker.py \
        --home_address "123 Main St, Anytown, USA" \
        --work_destinations "456 Business Rd, Workcity, USA" "789 Corporate Blvd, Workcity, USA" \
        --start_date "2023-01-01" \
        --end_date "2023-12-31" \
        --timeline_json "/path/to/GoogleTimeline/Records.json" \
        --api_key "AIzaSyXXXXXXXXXXXXXXXXXXX" \
        --output_xlsx "my_work_trips_2023.xlsx" \
        --proximity_radius_m 500
    ```

### Command-Line Arguments:

* `--home_address` (required): Your full home address as a string.
* `--work_destinations` (required): One or more work destination addresses as strings. If an address contains spaces, enclose it in quotes.
* `--start_date` (required): The start date for the analysis period (format: YYYY-MM-DD).
* `--end_date` (required): The end date for the analysis period (format: YYYY-MM-DD).
* `--timeline_json` (required): The file path to your exported Google Timeline `Records.json` file.
* `--api_key` (required): Your Google Maps Geocoding API key.
* `--output_xlsx` (optional): The desired filename for the output Excel report. Defaults to `travel_report.xlsx`.
* `--proximity_radius_m` (optional): The radius in meters for considering a GPS point as "at" a location (e.g., home or work). Defaults to 500 meters.

## Output

1.  **Console Output**:
    * Confirmation of input parameters.
    * Results of geocoding for home and work addresses, including potential matches. The script will automatically use the first match.
    * Progress messages during timeline processing.
    * A message for each day a qualifying "Home -> Work -> Home" trip is found, including the distance.
    * A final summary of the total number of qualifying days and total kilometers driven.
2.  **Excel File (`.xlsx`)**:
    * An Excel spreadsheet containing detailed information for each qualifying trip:
        * `Date`: Date of the trip.
        * `Work Location Visited (Query)`: The work address string you provided.
        * `Work Location Visited (Geocoded)`: The full address of the work location as resolved by Google Geocoding.
        * `Distance to Work (km)`: Distance of the leg from home to work.
        * `Distance from Work (km)`: Distance of the leg from work back to home.
        * `Total Distance (km)`: Total round trip distance for that day.
        * `Home Address (Geocoded)`: The full home address as resolved by Google Geocoding.

## Limitations & Considerations

* **Geocoding Accuracy**: The script relies on Google Geocoding. It prints multiple potential matches for addresses but automatically selects the first result. If this is not the correct one, the analysis might be inaccurate. You may need to be very specific with your input addresses or modify the script to allow interactive selection if the default choice is poor.
* **Timeline Data Quality**: The accuracy of the analysis depends heavily on the quality and completeness of your Google Timeline data. Missing data points, GPS inaccuracies, or incorrect `activitySegment` distances can affect results.
* **Definition of "Day"**: The script groups timeline events by UTC date derived directly from the timestamps in the JSON file. If your travel frequently crosses midnight UTC in a way that splits a single logical day of travel, this might affect daily aggregation.
* **Proximity Radius**: The `proximity_radius_m` is a critical parameter. Too small, and you might miss valid stays; too large, and you might incorrectly attribute visits.
* **Complex Commutes**: The script looks for a simple "Home -> Work -> Home" pattern. It doesn't explicitly handle trips with multiple work stops that still qualify, or more complex daily travel patterns (e.g., Home -> Work1 -> Work2 -> Home). It will record the first full H-W-H cycle it finds for a given day.
* **API Costs**: While the Geocoding API has a free monthly quota, extensive use (many addresses or frequent runs) could lead to charges. Monitor your usage in the Google Cloud Console.

## Troubleshooting

* **File Not Found**: Ensure the path to `--timeline_json` is correct.
* **Authentication/API Key Issues**: Double-check your API key is correct, has the Geocoding API enabled, and that billing is active on your GCP project. Check for error messages related to the API key.
* **No Results**:
    * Verify the date range is correct and contains travel data.
    * Check the `proximity_radius_m` value.
    * Ensure your addresses are being geocoded to the correct locations (check console output).
    * Your timeline data might not contain the specific "Home -> Work -> Home" pattern for the selected days/locations.
* **Incorrect Distances**: The script uses the `distance` field from `activitySegment` in your timeline. If these values are missing or inaccurate in your export, the calculated distances will be affected.