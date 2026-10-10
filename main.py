from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import google.generativeai as genai

# Khởi tạo ứng dụng FastAPI
app = FastAPI(title="Video to Text API Server")

# Cấu hình CORS để cho phép Website Github Pages của bạn gọi API này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Hỗ trợ mọi tên miền (bạn có thể thay bằng tên miền cụ thể)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khuôn mẫu dữ liệu Frontend sẽ gửi lên
class LinkRequest(BaseModel):
    url: str
    api_key: str
    model: str = "gemini-2.5-flash"

# Nơi xử lý khi Web gọi đến
@app.post("/api/process-link")
async def process_link(request: LinkRequest):
    # Tạo tên file ngẫu nhiên để không bị trùng lặp nếu nhiều người dùng cùng lúc
    temp_filename = f"temp_audio_{uuid.uuid4().hex}"
    downloaded_file = ""
    
    try:
        # Bước 1: Dùng yt-dlp để "hút" phần Âm Thanh (Audio) từ Link MXH
        ydl_opts = {
            'format': 'bestaudio/best',      # Chỉ lấy âm thanh chất lượng tốt nhất
            'outtmpl': temp_filename + '.%(ext)s', # Định dạng file theo đúng chuẩn tải về
            'noplaylist': True,              # Không tải cả danh sách phát
            'quiet': True,
            
            # --- BẮT ĐẦU CẤU HÌNH NGỤY TRANG MẠNH NHẤT ---
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'tv'],
                    'player_skip': ['webpage']
                }
            }
            # --- KẾT THÚC CẤU HÌNH NGỤY TRANG ---
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Lấy thông tin và tiến hành tải ngầm
            info = ydl.extract_info(request.url, download=True)
            # Tìm xem tên file cuối cùng lưu trong máy chủ là gì (VD: temp_audio_123.m4a)
            downloaded_file = ydl.prepare_filename(info)

        # Bước 2: Upload file âm thanh lên Google Gemini AI
        genai.configure(api_key=request.api_key)
        
        # Upload lên không gian lưu trữ tạm của Google
        myfile = genai.upload_file(downloaded_file)
        
        # Bước 3: Yêu cầu AI chuyển thành văn bản
        prompt = "Hãy nghe toàn bộ âm thanh trong file này và chuyển nó thành văn bản (transcript) chi tiết bằng tiếng Việt. Trình bày rõ ràng, không bình luận thêm."
        model = genai.GenerativeModel(request.model)
        
        response = model.generate_content([myfile, prompt])
        
        # Bước 4: Xóa file rác trên hệ thống của Google để giải phóng bộ nhớ
        try:
            genai.delete_file(myfile.name)
        except:
            pass
            
        # Trả văn bản về cho màn hình người dùng
        return {"success": True, "text": response.text}

    except Exception as e:
        print(f"Lỗi hệ thống: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Bước 5: QUAN TRỌNG NHẤT - Phải xóa file vừa tải trên máy chủ để không bị đầy ổ cứng
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            print(f"Đã dọn dẹp file tạm: {downloaded_file}")

# Mã khởi chạy tự động (Dùng khi chạy thử trên máy tính)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
