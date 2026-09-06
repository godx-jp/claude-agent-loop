---
name: batch-review
description: "Vai REVIEW của vòng lặp issue tự động (tal). Nhặt PR của một LÔ 10–20 issue, giành lease review (bắt buộc khác session đã code), loại ngay PR không có gì mới, đọc diff từ nguồn theo TỪNG issue, chạy test liên quan, kết luận MỘT lần cho cả lô theo Conventional Comments, rồi merge khi CI xanh. Dùng khi người nói chạy session review, review PR của bot, /loop /batch-review."
---

# batch-review — vai REVIEW

**Một lần gọi = một PR = cả một lô.** `/loop` điều phối nhịp, không phải bạn.

Một PR gộp 10–20 issue, nên **một lần review này chính là review cho cả lô**, và **một lần
CI của PR này chính là CI cho cả lô**. Đừng đòi thêm lần nào nữa.

---

## Bước 0 — chính sách

```sh
tal config
```

Đọc `policyDocs.review`: checklist riêng của repo, chỗ đã từng cháy, cạm bẫy đã biết. Phần
lớn giá trị của review nằm ở đó; luật chung dưới đây chỉ là nền.

## Bước 1 — chọn PR, và LOẠI NGAY thứ không đáng review

```sh
tal gc
tal review-queue --json
```

Trước khi đọc bất cứ thứ gì, kiểm **có gì mới hay không**:

```sh
gh pr view <PR> --json commits,comments -q \
  '{last_commit: (.commits|last|.committedDate),
    last_verdict: ([.comments[]|select(.body|contains("tal:review verdict"))]|last|.createdAt)}'
```

`last_commit` cũ hơn `last_verdict` → không có gì mới. **BỎ QUA**, nói rõ "bản này đã
review". Nếu nó vẫn nằm trong `review-queue` thì nhãn đang lệch — **báo ra**, đừng chữa
bằng cách review lại.

```sh
tal review-claim <PR> --json
```

- exit **5** = PR do chính session này code. Tách vai là điều kiện để review có nghĩa —
  **không** dùng `--allow-self`. Chọn PR khác.
- exit **75** = session khác đang review. Bỏ qua, không chờ.

## Bước 2 — đọc từ NGUỒN, theo TỪNG issue

```sh
gh pr view <PR> --json body -q .body                    # thân PR: bản đồ issue → thay đổi
gh pr diff <PR>                                         # sự thật về code
gh pr view <PR> --json commits -q '.commits[].messageHeadline'
```

Mỗi commit mang `(#N)`, nên **soi theo từng issue**, không soi thành một khối:

```sh
gh pr diff <PR> --name-only
git log origin/<base>..<head> --format='%h %s'          # nhóm commit theo #N
```

Với issue đáng nghi, đọc riêng phần của nó: `git show <sha>`.

Thân PR mô tả khác diff → **đừng kết luận tác giả chưa sửa**. Xác định sự thật từ diff +
commit message, rồi nêu chênh lệch dưới dạng `todo` về thân PR, **không** phải
`issue (blocking)` về code.

**Vòng ≥ 2:** đối chiếu từng điểm `(blocking)` vòng trước. Điểm còn sót là điểm cũ lặp lại
— nói vậy, đừng trình bày như phát hiện mới. Điểm đã xử lý thì ghi nhận một dòng.

## Bước 3 — soi

Đi hết `policyDocs.review` trước. Nền chung luôn áp dụng:

- **Tiền và dữ liệu không sửa lại được**: snapshot bất biến bị ghi đè; làm tròn/quy đổi sai
  chỗ; đảo tiền không idempotent theo id sự kiện (webhook giao lại là chuyện thường).
- **Thời gian nghiệp vụ**: "hôm nay"/biên ca/hạn dùng theo timezone của chi nhánh, không
  theo đồng hồ app hay đồng hồ DB.
- **Cờ debug/bypass** ghi cứng bật trong file được commit; guard theo môi trường bị nới.
- **Bí mật / cấu hình của một máy** lọt vào file commit.
- **Di trú dữ liệu**: đổi schema mà không có migration; `->change()` chỉ test trên SQLite
  trong khi production là MySQL.
- **Thất bại im lặng**: thao tác đổi dữ liệu mà lỗi không đến được người dùng.
- **Test**: có test chứng minh hành vi mới, và test đó **thật sự chạy** (nằm trong
  testsuite, không phải một thư mục không ai gọi).

**Rủi ro riêng của lô — đây là thứ vai này phải canh mà vai đơn không có:**

| Dấu hiệu | Xử lý |
|---|---|
| Một issue trong lô có blast radius cao (migration, auth, tiền, config) | `issue (blocking)`: **đòi tách ra PR riêng**, không giữ trong lô |
| Hai issue trong lô sửa chồng lên nhau cùng một file | nêu rõ; đòi commit của cái sau phản ánh cái trước |
| Một issue không có commit nào | lẽ ra phải bị `batch drop` — `todo` cho tác giả |
| Chỉ MỘT issue có vấn đề chặn | ghi rõ **`batch drop #N` đủ để cứu 19 cái kia** — đừng đánh `changes` cho cả lô nếu gỡ một cái là xong |

**Tài liệu:**

```sh
tal docs-check <PR>
```

Là **gợi ý**, không phải rào. Đổi quy ước / đổi hành vi người dùng thấy được / thêm cạm
bẫy mới / đổi API mà không regen tài liệu → `issue (blocking)`. Refactor nội bộ, đổi tên,
thêm test → **đừng đòi**.

## Bước 4 — test LIÊN QUAN

```sh
tal tests --pr <PR>          # lệnh test liên quan tới diff của PR này
```

Chỉ chạy đủ để kiểm điều mình đang nghi. **Full suite BỊ CẤM** — `hook-guard` chặn thật.
Nó chạy ở CI của PR vào `mainBranch`, không phải ở đây.

## Bước 5 — kết luận MỘT lần cho cả lô, rồi ĐỌC LẠI

Ghi **sha đã review** vào nội dung verdict, và nhóm các điểm **theo issue**:

```sh
gh pr view <PR> --json headRefOid -q .headRefOid | cut -c1-9
tal review-verdict <PR> pass --body-file <file>      # hoặc: changes
```

Đọc lại — verdict là thứ điều khiển rào merge:

```sh
gh issue view <issue-neo> --json labels -q '[.labels[].name]|join(", ")'
```

- `pass` → issue neo mang nhãn review-passed, cả lô vào `merge-queue`.
- `changes` → nhãn changes-requested (ưu tiên cao nhất hàng đợi code).
- Nhãn không đúng → **nói ra**, đừng chạy verdict lần hai (thành verdict trùng, đúng cái
  đang phải chữa).
- Quá `maxAttempts` vòng → tal chuyển dead-letter. **Đừng review vòng nữa.**

## Bước 6 — merge

```sh
tal merge-queue -v
tal merge <PR>
```

Rào hai điều kiện, cưỡng chế bằng máy: **review đạt** và **CI của chính PR này xanh**. CI
đó chạy test liên quan, không phải full suite — và vì PR gộp cả lô, một lần CI đó là một
lần cho cả lô. **Không bao giờ `--force`.**

Sau merge, đọc lại: `gh pr view <PR> --json state,mergedAt`.

Khi base đã tích đủ, mở cổng ra production — **đây là nơi DUY NHẤT full suite chạy**:

```sh
tal release-to-main
```

---

## Định dạng — [Conventional Comments](https://conventionalcomments.org/)

`label (decoration): subject` rồi xuống dòng giải thích. Chỉ `(blocking)` mới chặn merge.
Mỗi điểm ghi rõ **issue nào**, `file:line`, và **kịch bản sai cụ thể**.

| label | dùng khi |
|---|---|
| `issue (blocking)` | lỗi thật, phải sửa mới merge được |
| `issue (non-blocking)` | vấn đề thật nhưng chấp nhận merge trước |
| `question` | chưa đủ căn cứ để phán là lỗi |
| `suggestion (non-blocking)` | có cách tốt hơn, không bắt buộc |
| `nitpick (non-blocking)` | sở thích, tuyệt đối không chặn |
| `praise` | chỗ làm tốt, nói thật lòng |
| `todo` | việc nhỏ nhưng phải làm |

```md
issue (blocking): #1240 · src/billing/refund.ts:84 — hoàn tiền hai lần khi webhook lặp

Không khoá theo `provider_event_id`, nên webhook giao lại (chuyện thường) tạo bản ghi hoàn
tiền thứ hai. Tiền ra khỏi két hai lần cho một giao dịch.
→ Đây là điểm chặn DUY NHẤT của lô: `tal batch drop 1240` là đủ để 19 issue kia đi tiếp.
```

**Không phán khi chưa đọc file.** Không dựng được kịch bản sai cụ thể (input/state → kết
quả sai) thì hạ xuống `question` hoặc `suggestion`. **Review sạch là kết quả hợp lệ** —
nói thẳng "không có điểm chặn".

## Khi nghi ngờ

Đọc `"$CLAUDE_PLUGIN_ROOT"/references/discipline.md`. Đừng nạp nó mỗi lượt.

## Báo cáo cuối lượt

PR nào, sha nào, lô gồm issue nào, verdict gì, vì sao. PR bị loại vì "không có gì mới"
cũng phải nói. Không kể lại từng bước.
