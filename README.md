# PDF Compressor

PDF Compressor is a Python-based desktop application that allows users to compress PDF files efficiently. The application provides a user-friendly graphical interface built with PyQt5 and supports advanced compression options, including metadata removal and image downscaling.

## Features

- Drag-and-drop support for PDF files.
- Adjustable compression levels: Low, Medium, High, and Very High.
- Option to remove metadata from PDF files.
- Downscale large images to save space.
- Supports modern image formats like AVIF and WebP for better compression.
- Progress bar and status updates during compression.
- User-friendly interface with customizable options.

## Requirements

The application requires Python 3.7 or later. The following Python packages are used:

- PyQt5==5.15.9
- pillow==10.2.0
- PyMuPDF==1.23.5
- img2pdf==0.5.1
- pillow-avif-plugin==1.5.1
- webptools==0.0.9

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Pdf_Compress
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application using the batch file:
   ```
   launch_pdf_compressor.bat
   ```

2. Alternatively, you can run the application directly:
   ```bash
   python pdf_compressor.py
   ```

3. Drag and drop a PDF file into the application or use the "Browse" button to select a file.

4. Adjust the compression options as needed and click "Compress PDF".

5. Save the compressed PDF to your desired location.

## Development

To contribute to the project:

1. Fork the repository and clone it locally.
2. Create a new branch for your feature or bug fix.
3. Make your changes and test thoroughly.
4. Submit a pull request with a detailed description of your changes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments

- [PyQt5](https://riverbankcomputing.com/software/pyqt/intro) for the GUI framework.
- [Pillow](https://python-pillow.org/) for image processing.
- [PyMuPDF](https://pymupdf.readthedocs.io/) for PDF manipulation.
- [pillow-avif-plugin](https://github.com/0xC0DE6502/pillow-avif-plugin) for AVIF support.
- [webptools](https://github.com/nahidalam/webptools) for WebP support.
