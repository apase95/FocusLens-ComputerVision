# HierText DEV: Thử nghiệm Preprocessing Ablation & Đánh giá Đối chứng (200 Lines)

## 1. Mục tiêu & Bối cảnh

Dựa trên đề xuất tại pane `implementer` sau khi audit 37 ca lỗi khoảng trắng / ghép từ, thí nghiệm này được thiết kế để:
1. Xác thực cơ chế resize và tensor đầu vào của `en_PP-OCRv4_mobile_rec` trong runtime thực tế.
2. Đo kiểm trực tiếp tác động của các phương án tiền xử lý (Padding viền, Padding dọc, Scaling chữ nhỏ) trên **toàn bộ 200 dòng HierText DEV**.
3. Theo dõi độc lập cả số lượng dòng được cải thiện (**Improvements**) lẫn số lượng dòng vốn đúng bị làm sai (**Regressions**).

---

## 2. Làm rõ Phân loại Nhóm Đối chứng (200 Dòng DEV)

Nhóm 163 dòng nằm ngoài 37 ca lỗi spacing **không đồng nghĩa là 163 dòng đọc đúng**. Cơ cấu thực tế của baseline như sau:

- **Tổng số dòng DEV:** 200 dòng
- **Baseline ĐÚNG (Strict Exact):** **135 dòng** (67.5%)
- **Baseline SAI (Errors):** **65 dòng** (32.5%), gồm:
  - **37 dòng** thuộc nhóm lỗi khoảng trắng / tách-ghép từ (`spacing_err_37`) đã được audit trong [`HIERTEXT_DEV_SPACING_REVIEW.md`](HIERTEXT_DEV_SPACING_REVIEW.md).
  - **28 dòng** thuộc nhóm lỗi ký tự / glyph / symbol khác (`other_err_28`).

---

## 3. Xác thực Cơ chế Runtime Resize & Dynamic Width

Kiểm tra trực tiếp lớp `OCRReisizeNormImg` trong runtime (`paddlex/inference/models/text_recognition/predictor.py`):
- Runtime **hoàn toàn hỗ trợ Dynamic Width**: Tự động tính toán chiều rộng theo tỷ lệ $\text{imgW} = \text{int}(\text{imgH} \times \text{max\_wh\_ratio})$, với giới hạn tối đa $\text{max\_imgW} = 3200\text{px}$.
- Đo đạc thực tế trên 200 dòng:
  - Chiều rộng tensor sau resize dao động từ **199px đến 1907px** (trung bình ~800px, không có dòng nào chạm ngưỡng 3200px).
  - Nhóm 37 dòng lỗi spacing có tỷ lệ khung hình trung bình $16.22$ và chiều rộng $778.6\text{px}$, tương đương nhóm 163 dòng còn lại (tỷ lệ $16.78$, chiều rộng $805.4\text{px}$).
- **Kết luận:** Lỗi dính từ **không phải do tensor bị ép ngang hay bị cắt cụt chiều rộng ở 320px**.

---

## 4. Kết quả Thực nghiệm Đối chứng trên Toàn bộ 200 Dòng DEV

Artifact chi tiết chứa dự đoán từng dòng và tracking regression lưu tại: [`results/hiertext-dev-preprocessing-ablation/ablation.json`](file:///home/hodangthaiduy/Workspace/AI/focuslens/results/hiertext-dev-preprocessing-ablation/ablation.json).

| Cấu hình thử nghiệm | Khớp tuyệt đối (Exact) | CER (%) ↓ | WER (%) ↓ | Sửa lỗi Spacing | Cải thiện tổng (Imp) ↑ | Phá hỏng dòng đúng (Reg) ↓ | Net Thay đổi |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASELINE (Ảnh gốc)** | **135 / 200 (67.5%)** | **1.699%** | **11.184%** | — | — | — | — |
| **Candidate 1: Pad 4px toàn bộ** | 133 / 200 (66.5%) | 2.646% | 12.253% | +8 / 37 | +15 dòng | -17 dòng | **-2 dòng** |
| **Candidate 2: Pad dọc 4px (trên/dưới)** | 135 / 200 (67.5%) | 2.437% | 11.924% | +8 / 37 | +14 dòng | -14 dòng | **0 dòng** |
| **Candidate 3: Phóng to 1.25x (chữ < 25px)** | 125 / 200 (62.5%) | 2.381% | 15.625% | +3 / 37 | +3 dòng | -13 dòng | **-10 dòng** |

### Chi tiết hành vi:
1. **Candidate 1 (Pad 4px all sides):** Sửa được khoảng trắng ở 8 dòng (ví dụ `FOR SALE BY` được tách đúng), nhưng làm méo nét và biến dạng ký tự ở 17 dòng vốn dĩ đang nhận diện đúng $\rightarrow$ CER tăng vọt từ 1.699% lên 2.646%.
2. **Candidate 2 (Pad vertical):** Giảm thiểu tác động méo lề ngang, sửa được 14 dòng nhưng vẫn làm hỏng đúng 14 dòng khác $\rightarrow$ Net change bằng 0, CER xấu hơn baseline.
3. **Candidate 3 (Scaling chữ nhỏ):** Làm mờ nét chữ trên các crop độ phân giải thấp $\rightarrow$ Exact match tụt dốc thảm hại từ 67.5% xuống 62.5% (-10 dòng).

---

## 5. Kết luận & Quyết định Kỹ thuật

1. **Giữ nguyên Preprocessing hiện tại:** Dừng hoàn toàn việc triển khai padding hoặc scaling đại trà. Bằng chứng thực nghiệm cho thấy việc can thiệp cơ học vào ảnh không thể giải quyết dứt điểm lỗi spacing mà còn gây tổn hại nghiêm trọng đến các dòng khác.
2. **Chuyển trọng tâm sang Bước 2:** Thực hiện benchmark đối chứng PP-OCRv4 với một mô hình Recognizer thay thế có khả năng xử lý dòng văn bản dài (text-line) trên CPU.
