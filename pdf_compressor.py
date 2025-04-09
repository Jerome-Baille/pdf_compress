import sys
import os
import warnings
import tempfile
import time
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QFileDialog, QWidget, 
                             QProgressBar, QComboBox, QMessageBox, QFrame,
                             QSpacerItem, QSizePolicy, QSlider, QGroupBox,
                             QCheckBox, QToolTip, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMimeData, QUrl
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QFont, QPalette, QColor, QIcon
from PIL import Image
import io
import shutil
import fitz  # PyMuPDF
import img2pdf

# Import for WebP support
try:
    # Make sure Pillow has WebP support
    Image.init()  # Initialize the image library
    WEBP_AVAILABLE = "WEBP" in Image.MIME.keys()
    if WEBP_AVAILABLE:
        print("WebP format registered with Pillow")
    else:
        # Try to register WebP format manually
        from PIL import features
        if features.check('webp'):
            Image.register_mime("WEBP", "image/webp")
            Image.register_extension("WEBP", ".webp")
            WEBP_AVAILABLE = True
            print("WebP format manually registered with Pillow")
        else:
            WEBP_AVAILABLE = False
            print("WebP not available in this Pillow build, falling back to JPEG")
except Exception as e:
    WEBP_AVAILABLE = False
    print(f"WebP support error: {e}, falling back to JPEG")

# Import for AVIF support
try:
    # Try to import and register AVIF plugin
    # The pillow_avif plugin registers itself automatically when imported
    from pillow_avif import AvifImagePlugin
    
    # Verify AVIF is registered
    Image.init()  # Re-initialize to detect newly registered formats
    AVIF_AVAILABLE = "AVIF" in Image.MIME.keys()
    if AVIF_AVAILABLE:
        print("AVIF format registered with Pillow")
    else:
        # Try manual registration
        try:
            # Try to register the format manually if it's not detected
            Image.register_mime("AVIF", "image/avif")
            Image.register_extension("AVIF", ".avif")
            
            # Check again after manual registration
            Image.init()
            AVIF_AVAILABLE = "AVIF" in Image.MIME.keys()
            if AVIF_AVAILABLE:
                print("AVIF format manually registered with Pillow")
            else:
                AVIF_AVAILABLE = False
                print("AVIF format not registered with Pillow")
        except Exception as e:
            AVIF_AVAILABLE = False
            print(f"Failed to register AVIF format: {e}, falling back to WebP or JPEG")
except ImportError:
    AVIF_AVAILABLE = False
    print("AVIF not available, falling back to WebP or JPEG")

warnings.filterwarnings("ignore", category=DeprecationWarning)

class CompressorThread(QThread):
    progress_update = pyqtSignal(int)
    finished = pyqtSignal(str, str, str)  # message, original size, new size
    error = pyqtSignal(str)
    
    def __init__(self, input_path, output_path, compression_options):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.compression_options = compression_options
        
    def run(self):
        try:
            compression_level = self.compression_options.get('level', 'Medium')
            remove_metadata = self.compression_options.get('remove_metadata', True)
            
            # Define quality settings based on compression level
            quality_mapping = {
                "Low": 90,       # High quality
                "Medium": 75,    # Good balance
                "High": 50,      # Significant compression
                "Very High": 30  # Maximum compression
            }
            
            # DPI settings for rendering PDF pages to images
            dpi_mapping = {
                "Low": 300,      # High quality
                "Medium": 200,   # Good balance
                "High": 150,     # Significant compression
                "Very High": 100 # Maximum compression
            }            # Select best available format based on compression capabilities
            if AVIF_AVAILABLE:
                primary_format = "AVIF"  # AVIF offers best compression
            elif WEBP_AVAILABLE:
                primary_format = "WEBP"  # WebP is second best
            else:
                primary_format = "JPEG"  # JPEG as fallback
            
            # Print detected formats
            print(f"Available image formats: {', '.join(Image.MIME.keys())}")
            print(f"Using format: {primary_format}")
                
            quality = quality_mapping[compression_level]
            dpi = dpi_mapping[compression_level]
            
            # Print debug info
            print(f"Starting compression with level: {compression_level}, DPI: {dpi}, format: {primary_format}")
            print(f"Input file size: {os.path.getsize(self.input_path)} bytes")
            
            # Create temp directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Open the PDF with PyMuPDF (fitz)
                doc = fitz.open(self.input_path)
                total_pages = len(doc)
                
                # Extract each page as an image
                image_files = []
                for page_num in range(total_pages):
                    self.progress_update.emit(int((page_num + 1) / total_pages * 40))
                    
                    page = doc[page_num]
                    
                    # Render page to image at specified DPI
                    pix = page.get_pixmap(dpi=dpi)
                      # Convert to PIL Image for processing
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Save with selected format with fallback mechanism
                    try:
                        # Always use JPEG as the intermediate format because AVIF and WebP might 
                        # not be fully compatible with PyMuPDF for insertion
                        img_path = os.path.join(temp_dir, f"page_{page_num:04d}.jpg")
                        img.save(img_path, format="JPEG", quality=quality, optimize=True)
                    except Exception as e:
                        print(f"Error saving image: {e}")
                        # Fall back to a lower quality setting if there's an error
                        img_path = os.path.join(temp_dir, f"page_{page_num:04d}.jpg")
                        img.save(img_path, format="JPEG", quality=60, optimize=True)
                    
                    image_files.append(img_path)
                
                # Close the source PDF
                doc.close()
                
                self.progress_update.emit(70)  # 70% progress
                
                # Create a new PDF from the compressed images
                pdf_output = os.path.join(temp_dir, "compressed_output.pdf")
                
                # Get page dimensions from original PDF
                with fitz.open(self.input_path) as doc:
                    # Create a new PDF with blank pages of the same dimensions
                    new_pdf = fitz.open()
                    
                    # Process each compressed image
                    for i, img_path in enumerate(image_files):
                        self.progress_update.emit(70 + int((i + 1) / len(image_files) * 20))
                        
                        # Create a new page with the same dimensions as the original
                        page_rect = doc[i].rect
                        new_page = new_pdf.new_page(width=page_rect.width, height=page_rect.height)
                        
                        # Insert the compressed image into the page
                        with open(img_path, "rb") as img_file:
                            img_data = img_file.read()
                            new_page.insert_image(new_page.rect, stream=img_data)
                    
                    # If requested, remove metadata
                    if remove_metadata:
                        new_pdf.set_metadata({})
                    
                    # Save with maximum compression settings
                    new_pdf.save(
                        pdf_output,
                        garbage=4,       # Maximum garbage collection
                        deflate=True,    # Compress streams
                        clean=True,      # Clean content
                        linear=True,     # Optimize for web
                        pretty=False     # No pretty printing
                    )
                
                self.progress_update.emit(95)  # 95% done
                
                # Check the result
                original_size = os.path.getsize(self.input_path)
                compressed_size = os.path.getsize(pdf_output)
                
                if compressed_size >= original_size:
                    self.error.emit("Compression resulted in a larger file. Original file preserved.")
                    return
                
                # Copy the result to the output location
                shutil.copy2(pdf_output, self.output_path)
                
                # Calculate size reduction
                original_formatted = self.format_file_size(original_size)
                compressed_formatted = self.format_file_size(compressed_size)
                savings = ((original_size - compressed_size) / original_size) * 100
                
                self.progress_update.emit(100)  # 100% done
                self.finished.emit(
                    f"Compression complete! File size reduced by {savings:.1f}%",
                    original_formatted,
                    compressed_formatted
                )
                
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")
            
    def format_file_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

class DropAreaFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.parent = parent
        
        # Setup the layout and appearance
        layout = QVBoxLayout(self)
        
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        self.text_label = QLabel("Drop PDF file here or click to browse")
        self.text_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        self.text_label.setFont(font)
        
        layout.addStretch()
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()
        
        # Set styling
        self.setStyleSheet("""
            DropAreaFrame {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f8f8f8;
            }
            DropAreaFrame:hover {
                border: 2px dashed #3498db;
            }
        """)
        
    def setIconDrop(self):
        # You could add an actual icon here if available
        self.text_label.setText("Drop PDF file here or click to browse")
    
    def setIconProcessing(self):
        # Indicate processing state
        self.text_label.setText("Processing...")
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() and self._is_pdf(event.mimeData()):
            self.setStyleSheet("""
                DropAreaFrame {
                    border: 2px dashed #3498db;
                    border-radius: 10px;
                    background-color: #e8f4fc;
                }
            """)
            event.accept()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            DropAreaFrame {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f8f8f8;
            }
            DropAreaFrame:hover {
                border: 2px dashed #3498db;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls() and self._is_pdf(event.mimeData()):
            file_path = event.mimeData().urls()[0].toLocalFile()
            self.parent.set_pdf_file(file_path)
            event.accept()
        else:
            event.ignore()
        
        self.setStyleSheet("""
            DropAreaFrame {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f8f8f8;
            }
            DropAreaFrame:hover {
                border: 2px dashed #3498db;
            }
        """)
    
    def _is_pdf(self, mime_data: QMimeData):
        if mime_data.hasUrls() and len(mime_data.urls()) == 1:
            file_path = mime_data.urls()[0].toLocalFile()
            return file_path.lower().endswith('.pdf')
        return False
        
    def mousePressEvent(self, event):
        self.parent.browse_file()

class PDFCompressorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Compressor")
        self.setMinimumSize(600, 500)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999999;
            }
            QProgressBar {
                border: 1px solid #dcdcdc;
                border-radius: 5px;
                text-align: center;
                height: 15px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
            QComboBox {
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                padding: 5px;
                background: white;
            }
            QSlider::groove:horizontal {
                border: 1px solid #dcdcdc;
                height: 8px;
                background: #f0f0f0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #3498db;
                border: 1px solid #3498db;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QGroupBox {
                border: 1px solid #dcdcdc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                background-color: #f0f0f0;
            }
            QCheckBox {
                spacing: 5px;
                color: #333;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
        """)        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Create a QScrollArea to handle overflow content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(self.scroll_area)
        
        # Container widget for the scroll area
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(15)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(scroll_content)
        
        # Drop area frame
        self.drop_area = DropAreaFrame(self)
        self.drop_area.setMinimumHeight(200)
        self.drop_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scroll_layout.addWidget(self.drop_area)        # File info section
        self.file_info_frame = QFrame()
        self.file_info_frame.setFrameShape(QFrame.StyledPanel)
        self.file_info_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_info_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #dcdcdc;
                border-radius: 5px;
                background-color: white;
            }
        """)
        file_info_layout = QVBoxLayout(self.file_info_frame)
        
        self.file_label = QLabel("No file selected")
        self.file_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        self.file_label.setFont(font)
        file_info_layout.addWidget(self.file_label)
        self.scroll_layout.addWidget(self.file_info_frame)
        
        # Compression options group
        options_group = QGroupBox("Compression Options")
        options_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        options_layout = QVBoxLayout(options_group)
        
        # Compression level
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("Compression Level:"))
        
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["Low", "Medium", "High", "Very High"])
        self.compression_combo.setCurrentIndex(1)  # Medium by default
        self.compression_combo.setToolTip("Higher compression levels may take longer but produce smaller files")
        level_layout.addWidget(self.compression_combo)
        options_layout.addLayout(level_layout)
        
        # Additional options
        self.downscale_checkbox = QCheckBox("Downscale large images")
        self.downscale_checkbox.setChecked(True)
        self.downscale_checkbox.setToolTip("Reduces the resolution of very large images to save space")
        options_layout.addWidget(self.downscale_checkbox)
        
        self.metadata_checkbox = QCheckBox("Remove metadata")
        self.metadata_checkbox.setChecked(True)
        self.metadata_checkbox.setToolTip("Removes document metadata like author, creation date, etc.")
        options_layout.addWidget(self.metadata_checkbox)
        
        self.scroll_layout.addWidget(options_group)

        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scroll_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scroll_layout.addWidget(self.status_label)
        
        # Result section
        self.result_frame = QFrame()
        self.result_frame.setVisible(False)
        self.result_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.result_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #dcdcdc;
                border-radius: 5px;
                background-color: #e8f8f5;
                padding: 10px;
            }
        """)
        result_layout = QVBoxLayout(self.result_frame)
        
        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(self.result_label)
        
        self.scroll_layout.addWidget(self.result_frame)
        
        # Add a spacer at the end to push everything up
        self.scroll_layout.addStretch()
        
        # Button section
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_file)
        button_layout.addWidget(self.browse_button)

        self.compress_button = QPushButton("Compress PDF")
        self.compress_button.clicked.connect(self.compress_pdf)
        self.compress_button.setEnabled(False)
        button_layout.addWidget(self.compress_button)

        main_layout.addLayout(button_layout)
        
        # State variables
        self.current_file = None
        self.compressor_thread = None
    def set_pdf_file(self, file_path):
        """Set the PDF file selected by user via browsing or drag-drop"""
        if file_path and os.path.exists(file_path):
            self.current_file = file_path
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            self.file_label.setText(f"Selected: {file_name} ({self.format_file_size(file_size)})")
            self.compress_button.setEnabled(True)
            self.result_frame.setVisible(False)
            
            # Hide the drag and drop zone to save space after file selection
            self.drop_area.setVisible(False)
            
            # Change the browse button to a reset button
            self.browse_button.setText("Reset")
            self.browse_button.clicked.disconnect()
            self.browse_button.clicked.connect(self.reset_form)
    
    def browse_file(self):
        """Open file dialog to select a PDF file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select PDF File", 
            "", 
            "PDF Files (*.pdf)"
        )
        if file_path:
            self.set_pdf_file(file_path)
    def reset_form(self):
        """Reset the form to its initial state"""
        # Clear the current file selection
        self.current_file = None
        self.file_label.setText("No file selected")
        self.compress_button.setEnabled(False)
        
        # Show the drag and drop zone again
        self.drop_area.setVisible(True)
        
        # Hide the result frame if visible
        self.result_frame.setVisible(False)
        
        # Hide progress bar and reset status label
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("")
        
        # Change the reset button back to browse button
        self.browse_button.setText("Browse")
        self.browse_button.clicked.disconnect()
        self.browse_button.clicked.connect(self.browse_file)

    def compress_pdf(self):
        """Start the PDF compression process"""
        if not self.current_file:
            return

        # Suggest an output filename with "_compressed" suffix
        input_path = Path(self.current_file)
        suggested_name = f"{input_path.stem}_compressed{input_path.suffix}"
        suggested_dir = str(input_path.parent)
        
        output_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Compressed PDF", 
            os.path.join(suggested_dir, suggested_name), 
            "PDF Files (*.pdf)"
        )
        
        if output_path:
            if not output_path.lower().endswith('.pdf'):
                output_path += '.pdf'

            # Update UI for processing state
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.status_label.setText("Compressing PDF...")
            self.compress_button.setEnabled(False)
            self.browse_button.setEnabled(False)
            self.drop_area.setIconProcessing()
            self.result_frame.setVisible(False)

            # Prepare compression options
            compression_options = {
                'level': self.compression_combo.currentText(),
                'downscale_images': self.downscale_checkbox.isChecked(),
                'remove_metadata': self.metadata_checkbox.isChecked()
            }

            # Start compression in background thread
            self.compressor_thread = CompressorThread(self.current_file, output_path, compression_options)
            self.compressor_thread.progress_update.connect(self.update_progress)
            self.compressor_thread.finished.connect(self.compression_finished)
            self.compressor_thread.error.connect(self.compression_error)
            self.compressor_thread.start()

    def update_progress(self, value):
        """Update the progress bar"""
        self.progress_bar.setValue(value)    
    
    def compression_finished(self, message, original_size, compressed_size):
        """Handle the completion of compression"""
        self.status_label.setText(message)
        self.compress_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.drop_area.setIconDrop()
        
        # Show result summary
        self.result_frame.setVisible(True)
        self.result_label.setText(f"Original: {original_size} → Compressed: {compressed_size}")
        
        # Show success message
        QMessageBox.information(self, "Compression Complete", message)

    def compression_error(self, message):
        """Handle compression errors"""
        self.status_label.setText(message)
        self.compress_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.drop_area.setIconDrop()
        QMessageBox.critical(self, "Error", message)

    def format_file_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFCompressorApp()
    window.show()
    sys.exit(app.exec_())
