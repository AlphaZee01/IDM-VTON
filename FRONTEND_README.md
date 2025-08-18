# 🧥 IDM-VTON Test Frontend

A simple HTML frontend to test your IDM-VTON API directly without needing to connect to the uwear-virtual-shop repository.

## 🚀 Quick Start

### 1. Open the Frontend
Simply open `simple_frontend.html` in your web browser:
```bash
# Double-click the file or open in browser
open simple_frontend.html
```

### 2. Configure API Settings
1. **API Base URL**: Enter your Render deployment URL
   - Example: `https://your-app.onrender.com`
2. **API Key** (optional): Enter your API key if you set one
3. **Test Connection**: Click to verify your API is working

### 3. Upload Images
1. **Person Image**: Upload a photo of a person
2. **Garment Image**: Upload a photo of clothing item
3. **Drag & Drop**: You can also drag and drop images directly

### 4. Start Try-On
1. Click **"Start Try-On"** button
2. Watch the progress bar
3. View the result when complete

## 🎯 Features

- ✅ **Real-time Progress Tracking**: See the status of your try-on request
- ✅ **Drag & Drop Upload**: Easy image upload with preview
- ✅ **API Testing**: Test your API connection before trying
- ✅ **Error Handling**: Clear error messages and status updates
- ✅ **Responsive Design**: Works on desktop and mobile
- ✅ **Download Results**: Save your try-on results

## 🔧 API Endpoints Used

The frontend uses these API endpoints:

- `GET /health` - Test API connection
- `POST /api/v1/tryon` - Submit try-on request
- `GET /api/v1/tryon/{task_id}` - Check task status
- `GET /api/v1/tryon/{task_id}/result` - Download result

## 📱 How It Works

1. **Connection Test**: Verifies your API is accessible
2. **Image Upload**: Handles person and garment images
3. **Task Submission**: Sends images to your API
4. **Status Polling**: Checks progress every 2 seconds
5. **Result Display**: Shows the final try-on image

## 🎨 Customization

You can easily customize the frontend:

### Change API URL
Edit the default URL in the HTML:
```html
<input type="url" id="apiUrl" value="https://your-app.onrender.com">
```

### Modify Styling
Edit the CSS in the `<style>` section to change colors, layout, etc.

### Add Features
The JavaScript functions are well-commented and easy to extend.

## 🐛 Troubleshooting

### Connection Issues
- Check your API URL is correct
- Verify your API is deployed and running
- Check if you need an API key

### Upload Issues
- Ensure images are in supported formats (JPG, PNG)
- Check file size (should be under 10MB)
- Try refreshing the page

### Processing Issues
- Check your API logs for errors
- Verify model files are available
- Check memory/CPU limits on Render

## 📋 Testing Checklist

- [ ] API connection test passes
- [ ] Person image uploads correctly
- [ ] Garment image uploads correctly
- [ ] Try-on request submits successfully
- [ ] Progress updates show correctly
- [ ] Result image displays properly
- [ ] Download button works

## 🔗 Integration with uwear-virtual-shop

Once you've tested your API with this frontend, you can integrate it into your uwear-virtual-shop repository using the same API endpoints and patterns.

## 📞 Support

If you encounter issues:
1. Check the browser console for JavaScript errors
2. Verify your API is working with curl commands
3. Check your Render deployment logs
4. Test with the provided example images

---

**Note**: This frontend is for testing purposes. For production use, integrate the API calls into your main application.
