# Kỷ luật chung của vòng lặp — đọc khi có nghi ngờ

Hai vai dùng chung file này. Nó KHÔNG được nạp mỗi lượt: chỉ mở khi gặp đúng tình huống
bên dưới. Đọc nó mỗi lượt là trả lại đúng cái giá mà việc gom lô đang cắt đi.

## 1. Đọc ngược lại, đừng tin

Lỗi đắt nhất của vòng lặp này không phải viết code sai. Là **làm lại việc đã có**, hoặc
**tưởng đã gửi thứ chưa gửi**. Cả hai đến từ việc tin một câu trả lời thay vì đọc lại nguồn.
Không ai nói dối — công cụ và trạng thái đều có thể lệch.

| Muốn biết | ĐỌC | KHÔNG tin |
|---|---|---|
| Việc này đã ai làm chưa | `git log --all --grep="#<N>"`, `git grep` trên `origin/<base>` | mô tả issue, comment "chưa làm" |
| Bản sửa đã tới base chưa | `git merge-base --is-ancestor <sha> origin/<base>` | comment nói "đã ship" kèm sha |
| Diff thật của PR | `gh pr diff <PR>` | phần "Đã làm" trong thân PR |
| PR đã review chưa | nhãn trên **issue neo** | nhãn trên PR — nó sống sót qua push mới |
| Lô mình đang giữ | `tal assert` | thẻ `.tal-lease.json` đọc bằng mắt |
| Issue nào trong lô đã có commit | `tal batch status` | trí nhớ của lượt trước |
| Ai đang giữ gì | `tal status` | phỏng đoán |

## 2. Khi công cụ nói dối

Dấu hiệu: lệnh exit 0 nhưng đọc lại thấy không đổi.

1. **Đừng chạy lại lệnh** — nó sẽ lại exit 0 và bạn mất thêm một vòng.
2. **Đi đường vòng bằng `gh`/`git` trực tiếp** để hoàn thành việc.
3. **Mở issue cho lỗi công cụ**, kèm lệnh tái hiện và đoạn code nghi ngờ.
4. **Nếu lỗi nằm ở file đang có người giữ lease** (`tal status`) → **đừng sửa**. Bàn phần
   mình đã kiểm vào comment issue của họ. Hai bản sửa song song vào cùng một file chính là
   vấn đề mà cả cái vòng lặp này đang chữa.

## 3. Ba ca đã cắn thật, đáng biết trước

- **#1335 — `tal pr` nuốt `--body-file` khi PR đã tồn tại mà vẫn exit 0.** Thân PR kẹt ở
  vòng 1, reviewer đọc mô tả sai và trả về một PR **đã sửa** — hai vòng liền trên #1318.
  *Đã sửa trong `tal` (cmd_pr giờ gọi `gh pr edit` thật).* Giữ lại ở đây làm ví dụ cho
  luật: **lỗi công cụ thì sửa công cụ, đừng dạy mọi skill một nghi thức né tránh.**
- **Nhãn `review-passed` sót trên PR** làm rào merge tưởng một bản chưa ai xem là đã xem.
  Vì thế căn cứ luôn là nhãn trên **issue neo**, không phải nhãn trên PR.
- **Một issue bị kết luận "còn lỗi"** trong khi code đã ship ba ngày trước — vì đọc mô tả
  issue thay vì đọc `origin/<base>`.

## 4. `GIT_DIR` thắng cả `-C`

Git **xuất `GIT_DIR` cho hook**, và nó đè cả `-C` lẫn `cwd`. Nên `git -C <submodule> …`
viết trong một git hook KHÔNG chạy trong submodule. Ở worktree gốc `GIT_DIR` là `".git"`
tương đối nên tình cờ giải đúng; trong **worktree phụ** (vòng lặp luôn sống ở đó) nó là
đường dẫn tuyệt đối, nên mọi lookup rơi về repo chính và một pointer đã push đàng hoàng
vẫn bị báo dangling.

Cách sửa cho hook của repo:
`env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$path" …`.
Đừng "sửa" bằng `--no-verify` — cái hook đang kiểm là thứ có thật.

## 5. Không bao giờ

- **Không chạy full suite.** Rào cứng ở `hook-guard`. Vòng lặp chạy `tal tests --run`.
  Full suite chạy ở CI của PR vào `mainBranch`, hoặc do người gõ `tal fullsuite`.
- **Không push khi `tal assert` fail.** Lease đã cấp cho người khác thì commit của bạn là
  rác — DỪNG, báo lại, đừng biến xung đột thành hỏng dữ liệu.
- **Không `--no-verify`, `--force`, `--skip-*`** để vượt một cổng đang chặn. Cổng chặn vì
  có thứ thật cần xử lý.
- **Không commit WIP của người khác.** Stage đường dẫn tường minh, không `git add -A`.
- **Không bịa vấn đề để tỏ ra đã làm việc.** Một kết quả âm có bằng chứng vẫn là kết quả.
