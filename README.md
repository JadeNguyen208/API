# Gold Direction — Gemini AI

Trang web tĩnh dùng **Serper** để lấy dữ liệu thị trường mới và **Gemini 3.6 Flash** để đánh giá xu hướng ngắn hạn của vàng XAU/USD.

## Chức năng

- Dùng Serper cho giá/tin mới và Gemini cho phần phân tích.
- Tập trung riêng vào vàng XAU/USD.
- Hiển thị hướng tăng/giảm/đi ngang, dự đoán 5 phút, 15 phút và 1 giờ, độ tin cậy, hỗ trợ/kháng cự, yếu tố hai chiều và rủi ro sắp tới.
- Có thể nhập giá GOLD Bid/Ask từ XM MT4/MT5 để dùng giá XM làm mốc ngắn hạn và tính spread.
- Vẽ biểu đồ nến MT5 cùng đường Supertrend ATR(10) × 3: đường xanh dưới giá là xu hướng MUA, đường đỏ trên giá là xu hướng BÁN.
- Tín hiệu Supertrend chỉ xác nhận trên nến đã đóng để hạn chế tín hiệu thay đổi trong lúc nến đang chạy.
- Có thể nhập một mã khác đang có trong Market Watch để xem đường xu hướng cho cổ phiếu hoặc tài sản mà broker cung cấp.
- Hiển thị các nguồn web do Serper trả về.
- Không ghi Gemini hoặc Serper API key vào repository hay bộ nhớ trình duyệt.

## Sử dụng

1. Tạo Gemini API key tại <https://aistudio.google.com/apikey> và Serper API key tại <https://serper.dev>.
2. Chạy `setup_xm.bat` một lần để cài bridge local.
3. Chạy `setup_keys.bat`, nhập hai key một lần. Ký tự nhập không hiện trên màn hình và key được lưu trong `.env` đã bị Git bỏ qua.
4. Mở XM MT5, chạy `start_xm.bat`, rồi bấm **PHÂN TÍCH VÀNG**. Trang tự dùng key local cho đến khi bạn thay hoặc thu hồi key.

Nếu không chạy bridge, vẫn có thể mở `index.html`/GitHub Pages và nhập key tạm trong trình duyệt như trước.

Nếu đang giao dịch trên XM, có thể nhập thêm giá `Bid` và `Ask` của mã `GOLD` đang hiển thị trên MT4/MT5. Phần này là tùy chọn; trang web không đăng nhập hoặc gửi lệnh tới XM.

## Tự lấy giá từ XM MT5

Tính năng này chỉ đọc giá tick, không có mã gửi lệnh và không lưu thông tin đăng nhập.

1. Cài và đăng nhập XM MT5 trên máy Windows.
2. Chạy `setup_xm.bat` một lần để tạo môi trường và cài thư viện MetaTrader5.
3. Mỗi lần sử dụng, mở XM MT5 rồi chạy `start_xm.bat`.
4. Trình duyệt sẽ mở `http://127.0.0.1:8766/`; Bid/Ask GOLD được cập nhật mỗi giây và biểu đồ nến cập nhật mỗi 5 giây.

Bridge có hai API chỉ-đọc:

- `GET /api/xm-tick`: Bid/Ask mới nhất của mã vàng đã cấu hình.
- `GET /api/xm-bars?symbol=GOLD&timeframe=M5&count=300`: nến OHLCV dùng để vẽ biểu đồ và tính Supertrend. Các khung hỗ trợ: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`.

Bridge cũng có `GET /api/config` cùng hai proxy nội bộ `POST /api/serper-search` và `POST /api/gemini-analyze`. Các endpoint này không trả API key về trình duyệt.

Tên mã phụ thuộc broker. Ví dụ, cổ phiếu có thể mang hậu tố thay vì chỉ là `AAPL`; hãy thêm mã vào Market Watch và nhập đúng tên hiển thị trên MT5. Bridge không chứa `order_send` và không tự đặt lệnh.

Có thể đặt biến môi trường `XM_SYMBOL` nếu mã vàng trên tài khoản không phải `GOLD`, và `XM_MT5_PATH` nếu máy có nhiều terminal MT5.

Mỗi lần phân tích hiện dùng bốn lượt tìm kiếm Serper, trong đó có một lượt tìm thông tin chính thức từ XM. Hạn mức và giá có thể thay đổi theo chính sách của nhà cung cấp.

## Bảo mật

Khi chạy local, bridge đọc `GEMINI_API_KEY` và `SERPER_API_KEY` từ file `.env`, làm proxy cho Gemini/Serper và không trả key về trình duyệt. Bridge chỉ lắng nghe `127.0.0.1`; các origin được phép mặc định là trang local và GitHub Pages của repo này. Có thể thêm origin bằng biến `XM_ALLOWED_ORIGINS`.

Không đưa API key vào `index.html`, commit Git, ảnh chụp màn hình hoặc tin nhắn. File `.env` là bản rõ trên chính máy nên chỉ phù hợp với máy cá nhân đáng tin cậy. Với website phục vụ nhiều người, dùng backend triển khai thật và secret manager của nền tảng.

Nếu một key từng được commit công khai, hãy tạo key mới rồi vô hiệu hóa key cũ trong Google AI Studio/Google Cloud Console.

## Lưu ý

Kết quả do AI tổng hợp và tín hiệu kỹ thuật đều có thể sai hoặc trễ, không phải lời khuyên đầu tư. Hãy backtest theo từng mã/khung thời gian trước khi dùng với tiền thật.
