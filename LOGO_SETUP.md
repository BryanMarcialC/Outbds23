# Logo Setup Guide

## Adding Your Company Logo

To add your company logo to the Outbound application:

### 1. Prepare Your Logo
- **Format**: PNG is recommended (supports transparency)
- **Size**: Optimal width is 200-300 pixels
- **Name**: Save the file as `logo.png`

### 2. Place the Logo File
Place your `logo.png` file in the same directory as the main application files:

```
/workspace/
├── OutbMain.py
├── OutbMain_optimized.py
├── logo.png  ← Place your logo here
├── performance_config.py
└── ...
```

### 3. Logo Display
The logo will automatically appear at the top of the application, below the title, with a width of 200 pixels.

### 4. Troubleshooting

**Logo not showing?**
- Check that the file is named exactly `logo.png` (case-sensitive)
- Ensure the file is in the correct directory
- Verify the image file is not corrupted
- Check file permissions (should be readable)

**Logo too large/small?**
You can adjust the display size by modifying the `width` parameter in the code:

```python
st.image("logo.png", width=200)  # Change 200 to your desired width
```

### 5. Alternative Logo Names
If you need to use a different filename, update both application files:

**In OutbMain.py and OutbMain_optimized.py:**
```python
# Change this line:
st.image("logo.png", width=200)

# To your filename:
st.image("your_logo_name.png", width=200)
```

### 6. Logo Formats Supported
- PNG (recommended)
- JPEG/JPG
- GIF
- BMP
- SVG

### Notes
- The logo is optional - if no logo file is found, the application will continue to work normally
- The logo appears on all tabs of the application
- For best results, use a logo with a transparent background (PNG format)