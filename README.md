
# Kitty-Dist Usage Guide

## How to Use Kitty_Dist.exe

1. **Download and extract the files** to a folder on your computer.
2. **Double-click `Kitty_Dist.exe`** to start the application.
3. **Log in to CodeTantra** in the browser window that opens.
4. The app will automatically fetch and submit solutions for your questions.

---

## If `Kitty_Dist.exe` is Flagged as a Virus

Some antivirus programs may flag the EXE as a false positive. If this happens:

1. **Use the Python script instead:**
    - Make sure you have Python installed.
    - Install required packages:
      ```bash
      pip install -r requirements.txt
      ```
    - Run the script:
      ```bash
      python Kitty_Dist.py
      ```

2. **Or use the provided batch file:**
    - Double-click `run_kitty_dist.bat` (if available) to automatically run the Python script.
    - If the batch file is missing, create a new file named `run_kitty_dist.bat` with the following content:
      ```bat
      @echo off
      python Kitty_Dist.py
      pause
      ```

---

## Notes

- The EXE and Python script provide the same functionality.
- If you encounter issues, ensure all dependencies from `requirements.txt` are installed.
- For any problems, check the [GitHub repository](https://github.com/Harshit-Patel01/Kitty_Dist) for updates or troubleshooting tips.

---

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository on GitHub.
2. Create a new branch for your feature or bugfix.
3. Make your changes and submit a pull request with a clear description.
4. Ensure your code follows the existing style and passes any tests.

For major changes, please open an issue first to discuss what you would like to change.

---

## License & Credits

Do not copy, redistribute, or use this work without giving proper credit to the original author.

If you use or modify this project, please link back to the original repository and mention the author in your documentation or distribution.
