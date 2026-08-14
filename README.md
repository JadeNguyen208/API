# Gold Direction — Gemini AI

Trang web tĩnh dùng **Serper** để lấy dữ liệu thị trường mới và **Gemini 3.6 Flash** để đánh giá xu hướng ngắn hạn của vàng XAU/USD.

## Chức năng

- Dùng Serper cho giá/tin mới và Gemini cho phần phân tích.
- Tập trung riêng vào vàng XAU/USD.
- Hiển thị hướng tăng/giảm/đi ngang, dự đoán 5 phút, 15 phút và 1 giờ, độ tin cậy, hỗ trợ/kháng cự, yếu tố hai chiều và rủi ro sắp tới.
- Có thể nhập giá GOLD Bid/Ask từ XM MT4/MT5 để dùng giá XM làm mốc ngắn hạn và tính spread.
- Hiển thị các nguồn web do Serper trả về.
- Không ghi Gemini hoặc Serper API key vào repository hay bộ nhớ trình duyệt.

## Sử dụng

1. Mở `index.html` hoặc website GitHub Pages.
2. Tạo Gemini API key tại <https://aistudio.google.com/apikey>.
3. Tạo Serper API key tại <https://serper.dev>.
4. Nhập hai key và bấm **PHÂN TÍCH VÀNG**.

Nếu đang giao dịch trên XM, có thể nhập thêm giá `Bid` và `Ask` của mã `GOLD` đang hiển thị trên MT4/MT5. Phần này là tùy chọn; trang web không đăng nhập hoặc gửi lệnh tới XM.

## Tự lấy giá từ XM MT5

Tính năng này chỉ đọc giá tick, không có mã gửi lệnh và không lưu thông tin đăng nhập.

1. Cài và đăng nhập XM MT5 trên máy Windows.
2. Chạy `setup_xm.bat` một lần để tạo môi trường và cài thư viện MetaTrader5.
3. Mỗi lần sử dụng, mở XM MT5 rồi chạy `start_xm.bat`.
4. Trình duyệt sẽ mở `http://127.0.0.1:8766/`; Bid/Ask GOLD được cập nhật mỗi giây.

Có thể đặt biến môi trường `XM_SYMBOL` nếu mã vàng trên tài khoản không phải `GOLD`, và `XM_MT5_PATH` nếu máy có nhiều terminal MT5.

Mỗi lần phân tích hiện dùng bốn lượt tìm kiếm Serper, trong đó có một lượt tìm thông tin chính thức từ XM. Hạn mức và giá có thể thay đổi theo chính sách của nhà cung cấp.

## Bảo mật

Đây là ứng dụng tĩnh nên người dùng tự nhập key cho từng phiên. Không đưa API key vào `index.html`, commit Git hoặc bất kỳ file công khai nào. Với website phục vụ nhiều người, nên chuyển các lời gọi API sang backend và lưu `GEMINI_API_KEY` cùng `SERPER_API_KEY` trong secret/environment variable.

Nếu một key từng được commit công khai, hãy tạo key mới rồi vô hiệu hóa key cũ trong Google AI Studio/Google Cloud Console.

## Lưu ý

Kết quả do AI tổng hợp, có thể sai hoặc trễ và không phải lời khuyên đầu tư.
