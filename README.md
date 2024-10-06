# AI Climate Monitor

## Overview

"AI Climate Monitor" is a Flask web application designed to visualize and analyze global climate data related to greenhouse gas emissions. The app utilizes data from NASA's STAC API and integrates with Google's Gemini AI model for predicting future emissions.

## Features

* **Visualize Global Climate Data:** Explore interactive maps and charts displaying emissions of CO2, CH4, and other greenhouse gases.
* **Country-Specific Analysis:** View data specific to a chosen country, allowing users to focus on regional trends.
* **Emissions Predictions:**  Utilize Gemini AI to predict future emissions and provide insights into potential implications.
* **Data Sources:**  Leverages publicly available NASA STAC data for a comprehensive overview of climate change.

## Installation

1. **Install Python:**
   - If you don't have Python installed, download and install Python 3.8 or later from the official website: [https://www.python.org/](https://www.python.org/)

2. **Install Required Libraries:**
   - Open a terminal and navigate to the project directory.
   - Install the necessary libraries using pip:
     ```bash
     pip install -r requirements.txt
     ```
   - If you don't have `requirements.txt` file, you can install them separately:
     ```bash
     pip install flask requests folium pandas matplotlib plotly google-generativeai branca tabulate dotenv 
     ```

3. **Install Google Generative AI:**
    - Follow the instructions on the Google Generative AI website to install the necessary libraries: [https://ai.google.dev/gemini-api/docs/quickstart?lang=python]([https://cloud.google.com/generative-ai](https://ai.google.dev/gemini-api/docs/quickstart?lang=python))
    - Make sure to install the `google-generativeai` library.

4. **Obtain Google API Key:**
   - Create a Google Cloud project and enable the Generative AI API.
   - Get an API key from the Google Cloud Console.
   - Create a `.env` file in the root directory of your project and add the following line, replacing `YOUR_GOOGLE_API_KEY` with your actual API key:
     ```
     GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY
     ```

## Running the App

1. **Start the Flask server:**
   - Open a terminal and navigate to the project directory.
   - Run the following command:
     ```bash
     flask run
     ```

2. **Access the web app:**
   - Open a web browser and go to `http://127.0.0.1:5000/`.  The web app will be accessible on your local machine.

## Data Sources

The app utilizes data from NASA's STAC API, specifically:

* **Global Annual CO2 Emissions and Removals:** OCO-2 MIP Top-down CO₂ Budgets
* **Global CO₂ Emissions:** ODIAC Fossil Fuel CO₂ Emissions
* **Global Ocean Carbon Absorption:** Air-Sea CO₂ Flux, ECCO-Darwin Model v5
* **Global Methane Emissions:** TM5-4DVar Isotopic CH₄ Inverse Fluxes
* **Global Arid Regions High Methane Concentrations:** EMIT Methane Point Source Plume Complexes

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

* This project is based on the NASA STAC API and Google Generative AI. 
* Thanks to the developers of Flask, Folium, Plotly, and other open-source libraries used in this project.
