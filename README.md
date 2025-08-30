# Kitty-Dist API

This is a simple and efficient Flask-based API server designed to fetch and store solutions for questions using Google's Firebase Realtime Database. The project is deployed and hosted on PythonAnywhere.

**Repository:** [https://github.com/Harshit-Patel01/Kitty-Dist](https://github.com/Harshit-Patel01/Kitty-Dist)

---

## Features

- **Fetch Solutions:** Retrieve a specific solution by its unique question ID.
- **Add Solutions:** Add new solutions to the database.
- **Health Check:** A dedicated endpoint to verify the server's operational status.

---

## Technology Stack

- **Backend:** Python, Flask
- **Database:** Firebase Realtime Database
- **Hosting:** PythonAnywhere

---

## API Endpoints

### Get a Solution

- **URL:** `/solution/<question_id>`
- **Method:** `GET`
- **Description:** Fetches the solution for the specified `question_id`.
- **Success Response:**
  ```json
  {
    "solution": "The solution data from Firebase."
  }
  ```
- **Error Response:**
  ```json
  {
    "error": "Solution not found"
  }
  ```

### Add a New Solution

- **URL:** `/solutions`
- **Method:** `POST`
- **Description:** Adds a new question and solution to the database.
- **Body (raw JSON):**
  ```json
  {
    "id": "unique_question_id",
    "solution": "The solution to be stored."
  }
  ```
- **Success Response:**
  ```json
  {
    "status": "success",
    "message": "Solution saved"
  }
  ```

### Health Check

- **URL:** `/health`
- **Method:** `GET`
- **Description:** A simple endpoint to confirm that the API is running.
- **Success Response:**
  ```json
  {
    "status": "ok"
  }
  ```

---

## Project Structure

-   `server.py`: The main Flask application that runs the API server.
-   `Kitty_Dist.py`: A client-side script that automates browser interactions with CodeTantra to fetch and submit solutions.
-   `requirements.txt`: A list of all the Python packages required to run the project.

---

## Local Setup and Usage

### API Server

To run the API server on your local machine, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Harshit-Patel01/Kitty-Dist.git
    cd Kitty-Dist
    ```

2.  **Install dependencies:**
    Make sure you have Python installed. Then, install the required packages.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the server:**
    ```bash
    python server.py
    ```
    The server will start running on `http://127.0.0.1:5000`.

### Client-side Automation

The `Kitty_Dist.py` script is used to automate the process of fetching and submitting solutions on CodeTantra.

1.  **Run the script:**
    ```bash
    python Kitty_Dist.py
    ```
2.  **Log in:**
    A browser window will open. Log in to your CodeTantra account.
3.  **Automatic Submissions:**
    The script will monitor your activity and automatically fetch and submit solutions for the questions you are working on.
