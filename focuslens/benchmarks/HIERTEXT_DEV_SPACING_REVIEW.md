# HierText DEV: audit trực quan 37 lỗi spacing/split–merge

## Phạm vi và bằng chứng

Đã **mở và đọc thật cả 37 crop** trên bảy contact sheet (tối đa sáu
crop/sheet), đối chiếu REF/recognition/FULL. Đây là `model_visual_review`
của openai/gpt-6.1-sol, không phải kiểm định con người. Không chạy inference,
không sửa prediction, nhãn, dataset hoặc production code. Không đọc crop,
annotation hay manifest TEST riêng. Lệnh verifier bắt buộc đọc `finalized.json`
chung để xác minh DEV selection; không đánh giá các dòng TEST trong đó.

Artifact local: `results/hiertext-dev-spacing-review/`:

- `audit.json`: đủ 37 ID duy nhất, reference và hai prediction nguyên văn,
  bản ghi raw, parent, crop path/hash, kích thước/aspect, token counts, source
  word texts/polygons, nhận xét trực quan từng dòng và metrics tái tính.
- `sheet-01.png`…`sheet-07.png`: cả bảy đã xem bằng Read; ID/số thứ tự liên kết
  trực tiếp nhận xét. Mở thêm bốn ảnh parent của dòng 3, 13, 25, 35 để kiểm tra
  logo, punctuation và chữ nhỏ. Không khẳng định parent khác đã được xem.
- `input-hashes.json`: hash trước kiểm tra, đối chiếu lại sau verifier; gồm năm
  baseline artifact, DEV manifest, validation annotation, 37 crop và 15 parent.
- `build.py`, `finish.py`: utility phân tích offline, không phải correction.
  `build.py` tái tạo audit chưa review; `finish.py` gắn nhận xét đã quan sát.

Join đã kiểm tra thứ tự/ID cả 200 raw rows với frozen baseline manifest và DEV
manifest; 37 dòng được chọn đúng taxonomy **26 spacing_only + 11
word_count_mismatch**. Đối chiếu từng dòng với `source/validation.jsonl.gz`,
word texts/polygon/hash annotation; crop hash/dimensions và pixel crop từ parent
phải khớp. Reference casefold/collapse whitespace, giữ punctuation như baseline.

## Phân loại quan sát, không suy diễn nguyên nhân

Primary class độc quyền, ưu tiên vấn đề annotation ở dòng 3; còn lại nếu có
mất/thay glyph thì không gọi là lỗi spacing thuần:

| Primary class | Số dòng |
| --- | ---: |
| Thiếu khoảng trắng giữa từ thông thường | 10 |
| Khoảng trắng quanh punctuation/abbreviation/citation/typography | 16 |
| Mất/thay glyph hoặc punctuation kèm nối từ | 10 |
| Annotation/typography cần audit riêng | 1 |
| Thừa khoảng trắng trong từ ở recognition | 0 |
| Contamination/geometry được xác lập là nguyên nhân | 0 |
| Chưa phân loại primary | 0 |

Các secondary uncertainty vẫn giữ: dòng 13 chưa chốt chính xác cụm `;,`;
dòng 25 bracket chỉ cao chín pixel; dòng 35 mờ và nghiêng. Không có contamination
rõ trên các crop đã xem, nhưng điều đó không chứng minh geometry vô can.

Ví dụ từ ảnh và raw prediction (số thứ tự trong audit):

- **4:** REF `FOR SALE By`, REC `FORSALEBY`: ba từ cách rõ, không phải thiếu
  chữ. FULL `FOR SALE BV` phục hồi khoảng trắng nhưng làm sai `y`.
- **6:** `conduct. Each` → `conduct.Each`; ảnh có gap, FULL đúng toàn dòng.
- **7–8:** `91` là superscript citation. Source tuyến tính hóa thành token có
  space; đây không tương đương gap từ thông thường, không nên split số tùy ý.
- **3:** ảnh logo đọc là `Campbell’s`, source `Camplell's.`; ảnh viết
  `Vegetable-Beef`, source `Vegetable - Beef`. Đây là cảnh báo lần accept
  trước có thể sai/convention khác, không tự đổi frozen nhãn hay tính điểm mới.
- **24:** `designis a wneelchair` vừa nối `design is`, vừa thay `h` bằng `n`.
  **33:** `Feedingof ... Prematre` vừa mất space, vừa mất `u`; FULL đúng.
- **30:** REC `METALHEADERBOARDS`; FULL `METAL HEADER BOARD` tách đúng nhưng
  mất `S`. **35:** REC `Wino By TeGls`, FULL rỗng: ảnh chữ rất nhỏ 65×15,
  không thể xử lý bằng chèn space đơn thuần.

Quan sát gap/glyph có độ tin cậy cao ở đa số dòng; việc quy cho resize,
decoder hay detector chỉ là giả thuyết. Không có detector boxes trong baseline.

## FULL so với recognition trên chính 37 dòng

| Primary metric | Recognition | FULL |
| --- | ---: | ---: |
| Exact | 0/37 | 4/37 |
| CER | 5.6563% | 9.7172% |
| WER | 42.9167% | 42.5000% |
| Empty | 0 | 1 |

Denominator: 1.379 ký tự và 240 từ sau normalize. FULL có bốn exact
improvements (6, 10, 33, 34), zero exact regressions **do selection đã chọn toàn
dòng REC sai**, không phải bằng chứng an toàn trên mọi DEV. Theo char edits:
10 tốt hơn, 3 bằng, 24 tệ hơn. FULL có thể phục hồi gap nhưng phá glyph như
các ví dụ trên; không đề xuất chuyển tất cả sang FULL. Không tính oracle score.

37 dòng chỉ thuộc **15 parent**: 7 dòng ở `7e96140176dfa7c4`, 6 ở
`611072ec17a82276`, 4 mỗi parent `a428a09438de3dc8` và `463ab4555c1b685d`:
21/37 từ bốn parent. Chi tiết đủ 15 trong audit; không xem 37 như mẫu độc lập.

## Đề xuất tối đa bốn bước tiếp theo — chưa thực hiện

1. **Audit policy tách biệt:** adjudicate logo dòng 3, cụm punctuation dòng 13,
   superscript 7–8 và curly/ASCII quotes với người đọc; giữ nguyên baseline.
   Nếu có nhãn phiên bản mới, báo riêng số dòng thay đổi và cả điểm nhãn cũ;
   tuyệt đối không quảng bá sửa annotation là model improvement.
2. **Kiểm tra runtime resize trước thí nghiệm:** `ocr.py` dùng recognizer local
   `en_PP-OCRv4_mobile_rec`, không truyền override width. Audit này chưa đọc
   installed preprocessing/decoder nên **không kết luận maxwidth truncation,
   CTC squeeze hoặc width cap cụ thể**. Bước sau cần ghi effective tensor sizes,
   aspect/padding của đúng runtime rồi mới thử một thay đổi width có kiểm soát.
   Chấp nhận khi primary CER/WER giảm trên toàn 200 DEV, báo exact, glyph-only
   edit counts, số chữ/số/punctuation bị hỏng và latency; không chỉ tối ưu 37.
3. **Margin/scale ablation nhỏ trên DEV**, tách từng yếu tố, ưu tiên chữ cao
   9–17px và tight bounds. Upscale không tạo thêm thông tin; chưa khẳng định
   cải thiện. So với frozen raw cùng input IDs: chỉ giữ candidate giảm CER/WER,
   không mất số/punctuation, báo regressions ở 163 dòng còn lại và theo parent.
4. **Gap từ geometry nếu có alternative inference được phép sau này:** dùng
   ảnh/box thực, không dùng GT word polygons hay reference để sửa prediction.
   Baseline hiện không có boxes, nên chưa có deployable geometry correction.
   Đánh giá riêng ordinary-word gaps, citation, `783mm`, apostrophe/hyphen;
   từ chối nếu thêm gap trong từ/number hoặc glyph CER tăng. Không dùng regex
   split/join, dictionary/LM hay chọn FULL theo ground truth.

Không thử experiment nào trong audit này; không tuning TEST, không nâng model.

## Kiểm tra đã chạy

- `PYTHONPATH=. .venv/bin/python results/hiertext-dev-spacing-review/build.py`:
  PASS, 3,615s nội bộ (gồm annotation parsing, source/crop pairing, tạo sheets).
- `PYTHONPATH=. .venv/bin/python results/hiertext-dev-spacing-review/finish.py`:
  PASS; thực thi đúng `.venv/bin/python -m focuslens.benchmarks.hiertext_dev verify`
  trong **0,326s**, exit 0. Verifier không inference; có ghi canonical
  `verification.json`, hash trước/sau giữ nguyên. Mọi input được track giữ hash.
- Hai helper parse AST thành công. Không có feature/fix nên không tạo smoke
  RED/GREEN giả, không chạy full suite/integration/word-baseline dư thừa.
- `git diff --no-index --check /dev/null focuslens/benchmarks/HIERTEXT_DEV_SPACING_REVIEW.md`:
  PASS, 0,002s; chỉ kiểm tra tài liệu mới, không claim global dirty diff sạch.

Provider/model `openai/gpt-6.1-sol`; inherited explore
`ses_ea016f16fffeja4UILdqVUitBE`; general implementer
`ses_ea0158ceaffegz7Oa8fXWLXWCO`. Không delegation, skill load, commit hay push. Dirty tree trước
task được giữ nguyên. Phạm vi hash không phải snapshot toàn repository/dataset.
